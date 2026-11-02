#!/usr/bin/env python3.14
"""Lean command entry for the current market-reading report.

The historical ``daily_report_entry_demo`` module still exposes compatibility
helpers for old replay tests.  This command deliberately imports only the
current snapshot, source-health, small-cap and sector-reading path.
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from daily_report_reading_checks import (
    ReportCriticalDataMissingError,
    build_market_reading_preflight,
)
from daily_report_snapshot_io import (
    LEDGER_MODE_FROZEN,
    LEDGER_MODE_REPLAY,
    _save_data_snapshot,
    load_data_snapshot,
)
from daily_report_source_health import (
    OVERALL_STOP,
    render_source_health_terminal_lines,
    run_source_health_check,
    source_health_failure_message,
)
from observability.opik_runtime import build_report_run_observer
from report.sector_daily_report import save_sector_daily, sector_daily_output_path
from report.sector_fact_loader import collect_market_reading_data


def _resolve_daily_report_output_mode(args):
    return str(getattr(args, "output_mode", "") or "").strip() or "sector"


def _existing_legacy_report_paths(target_date: str, *, replay: bool = False):
    reports = Path(__file__).resolve().parents[1] / "reports"
    if replay:
        reports /= "replay"
    suffix = "_replay" if replay else ""
    stem = f"{target_date}_A股日报_完整版{suffix}"
    return reports / f"{stem}.md", reports / f"{stem}.html"


def _sector_full_html_anchor(target_date: str, run_mode: str):
    return _existing_legacy_report_paths(target_date, replay=run_mode == LEDGER_MODE_REPLAY)[1]


def _save_standalone_sector_reading_page(data, target_date: str, *, run_mode: str, source_mode=None):
    anchor = _sector_full_html_anchor(target_date, run_mode)
    source_html = None
    source_path = None
    if source_mode in (LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY):
        source_path = sector_daily_output_path(_sector_full_html_anchor(target_date, source_mode))
        if source_path.is_file():
            candidate = source_path.read_text(encoding="utf-8")
            if 'id="sector-hypothesis-record"' in candidate or 'id="sector-retained-history"' in candidate:
                source_html = candidate
    origin = (
        "as_of_report"
        if datetime.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat() == target_date
        else "historical_rebuild"
    )
    try:
        return save_sector_daily(
            source_html,
            target_date,
            snapshot={"date": target_date, "data": data},
            full_html_path=anchor,
            origin=origin,
            historical_snapshot=source_mode in (LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY),
            source_html_path=source_path if source_html else None,
        )
    except ValueError:
        if run_mode != LEDGER_MODE_FROZEN:
            raise
        official_page = sector_daily_output_path(anchor)
        if not official_page.exists():
            raise
        replay_anchor = _sector_full_html_anchor(target_date, LEDGER_MODE_REPLAY)
        return save_sector_daily(
            source_html,
            target_date,
            snapshot={"date": target_date, "data": data},
            full_html_path=replay_anchor,
            origin="historical_rebuild",
            historical_snapshot=source_mode in (LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY),
            source_html_path=source_path if source_html else None,
        )


def _snapshot_observation_payload(snapshot_path, requested_mode, *, error=None):
    resolved = str(getattr(error, "snapshot_path", "") or snapshot_path or "")
    actual = str(getattr(error, "mode", "") or requested_mode or "")
    if not getattr(error, "mode", None) and resolved:
        path = Path(resolved)
        if path.parent.name == "replay" or path.name.endswith("_replay.json"):
            actual = LEDGER_MODE_REPLAY
    output = {
        "snapshot_path": resolved,
        "requested_mode": str(requested_mode or ""),
        "actual_mode": actual,
        "size_limited": bool(getattr(error, "size_limited", False)),
    }
    bytes_written = getattr(error, "bytes_written", None)
    if isinstance(bytes_written, int):
        output["snapshot_size_bytes"] = bytes_written
    elif resolved:
        try:
            output["snapshot_size_bytes"] = Path(resolved).stat().st_size
        except OSError:
            pass
    return output


def _save_data_snapshot_with_observation(data, target_date, run_mode, observer, *, overwrite_existing=False):
    payload = {"target_date": target_date, "requested_mode": run_mode,
               "overwrite_existing": bool(overwrite_existing)}
    try:
        path = _save_data_snapshot(data, target_date, mode=run_mode, overwrite_existing=overwrite_existing)
    except Exception as error:
        observer.record_step("save_data_snapshot", status="error", input_payload=payload,
                             output_payload=_snapshot_observation_payload("", run_mode, error=error), error=error)
        raise
    observer.record_step("save_data_snapshot", status="success", input_payload=payload,
                         output_payload=_snapshot_observation_payload(path, run_mode))
    return path


def _target_close_missing(preflight):
    status = {check.get("label"): check.get("status") for check in (preflight or {}).get("checks") or []}
    return status.get("指数背景") == "missing" and status.get("板块样本") == "missing"


def _parser():
    parser = argparse.ArgumentParser(description="A股日报数据获取入口：当前板块阅读")
    parser.add_argument("date", nargs="?", help="目标日期 YYYY-MM-DD，默认上海日期的昨天")
    parser.add_argument("--output-mode", choices=("sector", "full", "short"), default=None,
                        help="sector 生成当前板块日报（默认）；full 仅定位历史原件；short 已停用")
    parser.add_argument("--replay", action="store_true", help="只读选定的冻结快照，不联网刷新")
    parser.add_argument("--snapshot-source", choices=("official", "replay"), default="official",
                        help="回放来源：official 正式快照（默认），replay 历史重建快照")
    parser.add_argument("--historical-rebuild", action="store_true", help="按目标日来源重新整理，只写 replay")
    parser.add_argument("--force-live", action="store_true", help="明确重新采集当日事实")
    parser.add_argument("--no-report", action="store_true", help="核对资料但不保存快照或阅读页")
    parser.add_argument("--source-health-only", action="store_true", help="只检查阅读所需来源")
    for name in ("position", "tomorrow-empty", "postgres-only", "import-json-to-postgres", "stock",
                 "stock-name", "overwrite-official"):
        option = "--" + name
        parser.add_argument(option, default=None, help=argparse.SUPPRESS)
    parser.add_argument("-p", dest="position", default=None, help=argparse.SUPPRESS)
    return parser


def main(argv=None):
    started_at = time.perf_counter()
    parser = _parser()
    args = parser.parse_args(argv)
    output_mode = _resolve_daily_report_output_mode(args)
    if output_mode == "short":
        parser.error("short 旧账户共识生成已停用；请使用当前板块日报")
    if any(getattr(args, name.replace("-", "_"), None) for name in
           ("position", "tomorrow-empty", "postgres-only", "import-json-to-postgres", "stock",
            "stock-name", "overwrite-official")):
        parser.error("当前日报不接收旧账户、单票处方、导入或正式覆盖参数")
    today = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).date()
    raw_date = args.date or (today - datetime.timedelta(days=1)).isoformat()
    try:
        target_date = datetime.date.fromisoformat(raw_date).isoformat()
        if raw_date != target_date:
            raise ValueError
    except ValueError:
        parser.error("目标日期格式不符，请使用 YYYY-MM-DD")
    if target_date > today.isoformat():
        parser.error("目标日期不能晚于当前上海日期，停止生成")
    if args.snapshot_source == "replay" and not args.replay:
        parser.error("--snapshot-source replay 必须与 --replay 一起使用")
    if sum((args.replay, args.historical_rebuild, args.force_live)) > 1:
        parser.error("--replay、--historical-rebuild、--force-live 只能选择一种资料来源")
    if args.force_live and target_date != today.isoformat():
        parser.error("--force-live 仅用于当日板块阅读")
    if output_mode == "full":
        if args.no_report or args.source_health_only or args.historical_rebuild or args.force_live or args.snapshot_source != "official":
            parser.error("full 只定位已有历史原件，不生成新建议")
        originals = [path for path in _existing_legacy_report_paths(target_date, replay=args.replay) if path.is_file()]
        print("历史原件：旧操作层已废除，内容不是当前建议；本次不重算、不写入。")
        for path in originals:
            print(f"历史文件: {path}")
        if not originals:
            print(f"{target_date} 没有已有完整版原件；不会重新生成旧建议。")
        return 0 if originals else 1

    snapshot_mode = LEDGER_MODE_REPLAY if args.snapshot_source == "replay" else LEDGER_MODE_FROZEN
    data = None
    selected_data_path = "live"
    if args.replay:
        data, _ = load_data_snapshot(target_date, mode=snapshot_mode)
        selected_data_path = "replay"
    elif not (args.force_live or args.historical_rebuild):
        data, _ = load_data_snapshot(target_date)
        if isinstance(data, dict):
            selected_data_path = "snapshot"
        elif target_date != today.isoformat():
            raise ReportCriticalDataMissingError(
                f"{target_date} 正式冻结快照缺失；请显式选择 replay 或 historical-rebuild"
            )
    if args.replay and not isinstance(data, dict):
        raise ReportCriticalDataMissingError(f"{target_date} 选定来源的冻结快照缺失，停止生成")
    observer = build_report_run_observer(
        run_name=f"daily-report.current.{target_date}",
        trace_input={"target_date": target_date, "output_mode": "sector", "data_path": selected_data_path,
                     "snapshot_source": args.snapshot_source},
        metadata={"runner": "daily_report_current"},
    )
    status, error, saved_paths, preflight = "success", None, {}, {}
    try:
        health = run_source_health_check(
            target_date, replay=selected_data_path in {"snapshot", "replay"}, snapshot_mode=snapshot_mode,
            reading_mode=True, historical_rebuild=bool(args.historical_rebuild), include_cffex=False,
            artifact_dir=Path(__file__).resolve().parents[1] / "logs" / "source_health" / "sector" /
                         ("replay" if selected_data_path != "live" else "live"),
        )
        for line in render_source_health_terminal_lines(health):
            print(line)
        if health.get("overall_result") == OVERALL_STOP:
            raise ReportCriticalDataMissingError(source_health_failure_message(health))
        if args.source_health_only:
            return 0
        if selected_data_path == "live":
            data = collect_market_reading_data(target_date)
        preflight = build_market_reading_preflight(data, target_date,
                                                    historical_snapshot=selected_data_path in {"snapshot", "replay"})
        observer.record_step("market_reading_preflight", status="success",
                             input_payload={"target_date": target_date}, output_payload=preflight)
        for check in preflight.get("checks") or []:
            if check.get("status") == "missing":
                print(f"- {check.get('label', '')}: 待确认（不转成账户决定）")
        if selected_data_path == "live" and _target_close_missing(preflight):
            raise ReportCriticalDataMissingError(f"{target_date} 的收盘行情尚未取得，停止生成")
        if args.no_report:
            return 0
        run_mode = LEDGER_MODE_REPLAY if (args.replay or args.historical_rebuild or target_date != today.isoformat()) else LEDGER_MODE_FROZEN
        official_page = sector_daily_output_path(_sector_full_html_anchor(target_date, LEDGER_MODE_FROZEN))
        if official_page.exists():
            run_mode = LEDGER_MODE_REPLAY
        if selected_data_path == "live":
            snapshot_path = _save_data_snapshot_with_observation(data, target_date, run_mode, observer)
            if Path(str(snapshot_path)).parent.name == "replay" or Path(str(snapshot_path)).name.endswith("_replay.json"):
                run_mode = LEDGER_MODE_REPLAY
        path = _save_standalone_sector_reading_page(
            data, target_date, run_mode=run_mode,
            source_mode=snapshot_mode if selected_data_path in {"snapshot", "replay"} else None)
        saved_paths = {"sector_reading": str(path)}
        observer.record_step("save_sector_reading", status="success",
                             input_payload={"target_date": target_date, "run_mode": run_mode},
                             output_payload={"path": str(path)})
        print(f"日报优先阅读: {path}")
        return 0
    except Exception as exc:
        status, error = "error", exc
        observer.record_step("daily_report_entry", status="error", input_payload={"target_date": target_date},
                             output_payload={}, error=exc)
        raise
    finally:
        observer.finish(status=status, output_payload={
            "target_date": target_date, "output_mode": "sector", "data_path": selected_data_path,
            "snapshot_source": args.snapshot_source, "replay": bool(args.replay),
            "report_saved": bool(saved_paths), "primary_report_path": saved_paths.get("sector_reading", ""),
            "elapsed_seconds": round(time.perf_counter() - started_at, 3), "preflight": preflight,
            "error": str(error) if error else "",
        })


if __name__ == "__main__":
    from orchestrator.run_log_runtime import run_with_log_capture
    raise SystemExit(run_with_log_capture(main, argv=sys.argv))
