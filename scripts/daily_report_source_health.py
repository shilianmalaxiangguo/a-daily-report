#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as _dt
import html
import json
import os
import queue
import re
import threading
import time
from pathlib import Path

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, _get_snapshot_path
from input.runtime import _fetch_quicktiny_exchange_monitor_payload
from market_data.tushare_client import (
    TUSHARE_HTTP_URL_ENV,
    TUSHARE_TOKEN_ENV,
    check_tushare_runtime_ready,
    load_local_env_file,
    resolve_tushare_runtime_config,
)
from market_data.tushare_market_activity_service import fetch_investor_qa_rows
from market_data.xueqiu_hot_stock_service import (
    XUEQIU_COOKIE_CAPTURE_DIR_ENV,
    XUEQIU_COOKIE_ENV,
    get_xueqiu_cookie,
    try_fetch_xueqiu_a_share_hot_24h,
    try_fetch_xueqiu_hot_stock_arguments,
)
from storage.database_service import DatabaseService


SCHEMA_VERSION = "daily_report_source_health.v1"
OVERALL_READY = "ready"
OVERALL_STOP = "stop_generation"
RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_WARNING = "warning"
RESULT_SKIPPED = "skipped"
STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_SUSPECTED_EXPIRED = "suspected_expired"
STATUS_NOT_REQUIRED = "not_required"
STATUS_NOT_CHECKED = "not_checked"
STATUS_FAILED = "failed"
STATUS_TIMEOUT = "timeout"
STATUS_COVERED = "covered"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_SKIPPED = "skipped"
DEFAULT_SOURCE_TIMEOUT_SECONDS = 15
TUSHARE_SOURCE_TIMEOUT_SECONDS = 10
TUSHARE_PROBE_TIMEOUT_SECONDS = 8
TUSHARE_PROBE_ATTEMPTS = 2


class SourceHealthCriticalError(RuntimeError):
    pass


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _logs_root(root_dir=None) -> Path:
    return Path(root_dir or _project_root()) / "logs" / "source_health"


def _now_text(now=None) -> str:
    value = now or _dt.datetime.now()
    if isinstance(value, _dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _load_env_if_needed(env):
    if env is not None:
        return env
    load_local_env_file()
    return os.environ


def _env_value(env, key) -> str:
    return str((env or {}).get(key) or "").strip()


def _credential_status(env, keys, *, mode="any") -> str:
    keys = list(keys or [])
    if not keys:
        return STATUS_NOT_REQUIRED
    values = [_env_value(env, key) for key in keys]
    if mode == "all":
        return STATUS_OK if all(values) else STATUS_MISSING
    return STATUS_OK if any(values) else STATUS_MISSING


def redact_sensitive_text(text, *, env=None) -> str:
    value = str(text or "")
    value = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer ***", value)
    value = re.sub(r"(token=)[^;\s\"']+", r"\1***", value, flags=re.IGNORECASE)
    value = re.sub(r"(cookie:\s*)[^\n\r]+", r"\1***", value, flags=re.IGNORECASE)
    value = re.sub(r"postgres(?:ql)?://[^\s\"']+", "postgresql://***", value, flags=re.IGNORECASE)
    value = re.sub(
        r"((?:TOKEN|COOKIE|API_KEY|DATABASE_URL|PASSWORD|SECRET)[\"']?\s*[:=]\s*[\"']?)[^\"'\s,;]+",
        r"\1***",
        value,
        flags=re.IGNORECASE,
    )
    for key, secret in (env or os.environ).items():
        if not any(marker in str(key).upper() for marker in ("TOKEN", "COOKIE", "API_KEY", "DATABASE_URL", "PASSWORD", "SECRET")):
            continue
        secret_text = str(secret or "").strip()
        if len(secret_text) >= 4:
            value = value.replace(secret_text, "***")
    return value


def _duration_ms(started_at) -> int:
    return int(max(0.0, time.perf_counter() - started_at) * 1000)


def _safe_provider(provider, *, env=None, fallback="") -> str:
    return redact_sensitive_text(str(provider or fallback or ""), env=env)


def _run_with_timeout(fn, *, timeout_seconds):
    started_at = time.perf_counter()
    result_queue = queue.Queue(maxsize=1)

    def runner():
        try:
            result_queue.put({"ok": True, "value": fn()}, block=False)
        except Exception as exc:
            result_queue.put({"ok": False, "error": str(exc), "error_type": exc.__class__.__name__}, block=False)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    try:
        result = result_queue.get(timeout=timeout_seconds)
    except queue.Empty:
        return {
            "status": STATUS_TIMEOUT,
            "value": None,
            "duration_ms": _duration_ms(started_at),
            "error": f"source health check timed out after {timeout_seconds}s",
        }
    if result.get("ok"):
        return {
            "status": STATUS_OK,
            "value": result.get("value"),
            "duration_ms": _duration_ms(started_at),
        }
    return {
        "status": STATUS_FAILED,
        "value": None,
        "duration_ms": _duration_ms(started_at),
        "error": result.get("error", ""),
        "error_type": result.get("error_type", ""),
    }


def _postgres_default_probe(target_date):
    def _as_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    service = DatabaseService.from_environment()
    if getattr(service, "repository", None) is None:
        return {
            "connected": False,
            "covered": False,
            "row_count": 0,
        }
    coverage = service.daily_report_fact_coverage(target_date) or {}
    tables = coverage.get("tables") if isinstance(coverage, dict) else {}
    target_count = sum(_as_int((item or {}).get("target_count")) for item in (tables or {}).values())
    snapshot = service.load_daily_report_snapshot(target_date) or {}
    field_count = _as_int(snapshot.get("field_count")) if isinstance(snapshot, dict) else 0
    target_field_count = _as_int(snapshot.get("target_field_count")) if isinstance(snapshot, dict) else 0
    structured_fact_count = _as_int(snapshot.get("structured_fact_count")) if isinstance(snapshot, dict) else 0
    target_structured_fact_count = _as_int(snapshot.get("target_structured_fact_count")) if isinstance(snapshot, dict) else 0
    row_count = max(target_count, field_count, target_field_count, structured_fact_count, target_structured_fact_count)
    return {
        "connected": True,
        "covered": row_count > 0,
        "row_count": row_count,
    }


def _check_row(
    *,
    check_id,
    group,
    task,
    provider,
    purpose,
    credential_keys=None,
    credential_status=STATUS_NOT_CHECKED,
    connectivity_status=STATUS_NOT_CHECKED,
    target_date_status=STATUS_NOT_CHECKED,
    row_count=0,
    duration_ms=0,
    required_for_generation=False,
    result=RESULT_SKIPPED,
    advice="",
    safe_error="",
):
    return {
        "id": check_id,
        "group": group,
        "task": task,
        "provider": provider,
        "purpose": purpose,
        "credential_keys": list(credential_keys or []),
        "credential_status": credential_status,
        "connectivity_status": connectivity_status,
        "target_date_status": target_date_status,
        "row_count": int(row_count or 0),
        "duration_ms": int(duration_ms or 0),
        "required_for_generation": bool(required_for_generation),
        "result": result,
        "advice": str(advice or ""),
        "safe_error": str(safe_error or ""),
    }


def _first_check_row_count(result):
    checks = (result or {}).get("checks") if isinstance(result, dict) else []
    if checks and isinstance(checks[0], dict):
        return int(checks[0].get("row_count") or 0)
    return 0


def _tushare_check(env, *, checker, timeout_seconds, probe_timeout_seconds=TUSHARE_PROBE_TIMEOUT_SECONDS):
    credential_keys = [TUSHARE_TOKEN_ENV, TUSHARE_HTTP_URL_ENV]
    config = resolve_tushare_runtime_config(env=env)
    has_token = bool(str(config.get("token") or "").strip())
    has_http_url = bool(str(config.get("http_url") or "").strip())
    uses_b_channel = str(config.get("http_url") or "").strip().lower().endswith("/tushare/pro")
    channel_name = "Tushare B 通道" if uses_b_channel else "Tushare A 通道"
    fallback_provider = "tushare.b.daily" if uses_b_channel else "tushare.pro.index_basic"
    credential_status = STATUS_OK if has_token and has_http_url else STATUS_MISSING
    if credential_status != STATUS_OK:
        return _check_row(
            check_id="tushare.runtime",
            group="基础市场事实",
            task=channel_name,
            provider=fallback_provider,
            purpose="基础事实",
            credential_keys=credential_keys,
            credential_status=credential_status,
            connectivity_status=STATUS_NOT_CHECKED,
            target_date_status=STATUS_NOT_APPLICABLE,
            required_for_generation=True,
            result=RESULT_FAIL,
            advice=f"配置 {channel_name} token 和 HTTP URL 后再生成日报",
        )
    probe_timeout_seconds = min(float(probe_timeout_seconds or timeout_seconds), float(timeout_seconds))
    if probe_timeout_seconds.is_integer():
        probe_timeout_seconds = int(probe_timeout_seconds)
    probes = []
    result = {}
    ok = False
    for _attempt in range(TUSHARE_PROBE_ATTEMPTS):
        probe = _run_with_timeout(
            lambda: checker(
                token=config["token"],
                http_url=config["http_url"],
                timeout_seconds=probe_timeout_seconds,
            ),
            timeout_seconds=timeout_seconds,
        )
        probes.append(probe)
        result = probe.get("value") or {}
        ok = bool(isinstance(result, dict) and result.get("ok"))
        if ok:
            break
    probe = probes[-1]
    duration_ms = sum(int(item.get("duration_ms") or 0) for item in probes)
    if probe["status"] == STATUS_TIMEOUT:
        return _check_row(
            check_id="tushare.runtime",
            group="基础市场事实",
            task=channel_name,
            provider=fallback_provider,
            purpose="基础事实",
            credential_keys=credential_keys,
            credential_status=credential_status,
            connectivity_status=STATUS_TIMEOUT,
            target_date_status=STATUS_NOT_APPLICABLE,
            duration_ms=duration_ms,
            required_for_generation=True,
            result=RESULT_FAIL,
            advice=f"{channel_name}检查超时，先检查接口、网络或配额",
            safe_error=redact_sensitive_text(probe.get("error"), env=env),
        )
    return _check_row(
        check_id="tushare.runtime",
        group="基础市场事实",
        task=channel_name,
        provider=_safe_provider((result or {}).get("provider"), env=env, fallback=fallback_provider),
        purpose="基础事实",
        credential_keys=credential_keys,
        credential_status=credential_status,
        connectivity_status=STATUS_OK if ok else STATUS_FAILED,
        target_date_status=STATUS_NOT_APPLICABLE,
        row_count=_first_check_row_count(result),
        duration_ms=duration_ms,
        required_for_generation=True,
        result=RESULT_PASS if ok else RESULT_FAIL,
        advice=f"{channel_name}可用" if ok else f"{channel_name}不可用，先检查 token、HTTP URL 或权限",
        safe_error=redact_sensitive_text((result or {}).get("error_message") or probe.get("error"), env=env),
    )


def _postgres_check(
    env,
    *,
    target_date,
    postgres_only,
    postgres_checker=None,
    timeout_seconds=DEFAULT_SOURCE_TIMEOUT_SECONDS,
):
    credential_keys = ["A_DAILY_REPORT_DATABASE_URL", "DATABASE_URL"]
    configured_credential_status = _credential_status(env, credential_keys, mode="any")
    requires_target_date_fact = bool(postgres_only)
    if postgres_checker is None:
        def postgres_checker():
            return _postgres_default_probe(target_date)
    probe = _run_with_timeout(postgres_checker, timeout_seconds=timeout_seconds)
    raw_value = probe.get("value")
    if isinstance(raw_value, dict):
        connected = bool(raw_value.get("connected", True))
        covered = bool(raw_value.get("covered"))
        row_count = int(raw_value.get("row_count") or 0)
    else:
        connected = bool(raw_value)
        covered = bool(raw_value) and requires_target_date_fact
        row_count = 0
    credential_status = STATUS_OK if connected else configured_credential_status
    if connected and (covered or not requires_target_date_fact):
        result = RESULT_PASS
        advice = "PostgreSQL 连接可用，生成后继续同步事实" if not requires_target_date_fact else "PostgreSQL 目标日期事实可用"
    elif requires_target_date_fact:
        result = RESULT_FAIL
        advice = "PostgreSQL-only 需要可用事实库和目标日期事实，先配置数据库连接、启动本机默认事实库或补齐该日期事实"
    else:
        result = RESULT_FAIL
        advice = "PostgreSQL 事实库不可用，先配置数据库连接或启动本机默认事实库后再生成日报"
    return _check_row(
        check_id="postgres.fact_store",
        group="持久化事实",
        task="PostgreSQL 日报事实库",
        provider="postgresql.daily_report_facts",
        purpose="持久化事实",
        credential_keys=credential_keys,
        credential_status=credential_status,
        connectivity_status=STATUS_OK if connected else (STATUS_TIMEOUT if probe["status"] == STATUS_TIMEOUT else STATUS_FAILED),
        target_date_status=STATUS_COVERED if covered else (STATUS_MISSING if requires_target_date_fact else STATUS_NOT_CHECKED),
        row_count=row_count,
        duration_ms=probe["duration_ms"],
        required_for_generation=True,
        result=result,
        advice=advice,
        safe_error=redact_sensitive_text(probe.get("error"), env=env),
    )


def _xueqiu_cookie_status(env) -> str:
    cookie = get_xueqiu_cookie() if env is os.environ else (_env_value(env, XUEQIU_COOKIE_ENV) or _env_value(env, XUEQIU_COOKIE_CAPTURE_DIR_ENV))
    return STATUS_OK if cookie else STATUS_MISSING


def _xueqiu_hot_check(env, *, fetcher, timeout_seconds):
    credential_keys = [XUEQIU_COOKIE_ENV, XUEQIU_COOKIE_CAPTURE_DIR_ENV]
    credential_status = _xueqiu_cookie_status(env)
    if credential_status != STATUS_OK:
        return _check_row(
            check_id="xueqiu.hot_stock",
            group="当日热度与叙事",
            task="雪球 A 股 24 小时热榜",
            provider="xueqiu.hot_stock.type22",
            purpose="决策事实",
            credential_keys=credential_keys,
            credential_status=credential_status,
            connectivity_status=STATUS_NOT_CHECKED,
            target_date_status=STATUS_NOT_APPLICABLE,
            required_for_generation=True,
            result=RESULT_FAIL,
            advice="更新 XUEQIU_COOKIE 或 XUEQIU_COOKIE_CAPTURE_DIR 后再生成日报",
        ), []
    probe = _run_with_timeout(lambda: fetcher(timeout=timeout_seconds), timeout_seconds=timeout_seconds)
    result = probe.get("value") or {}
    rows = result.get("rows") if isinstance(result, dict) else []
    ok = probe["status"] == STATUS_OK and isinstance(result, dict) and result.get("status") == "ok" and bool(rows)
    diagnostic = result.get("diagnostic_note") if isinstance(result, dict) else probe.get("error")
    if not ok and "登录态" in str(diagnostic or ""):
        credential_status = STATUS_SUSPECTED_EXPIRED
    row = _check_row(
        check_id="xueqiu.hot_stock",
        group="当日热度与叙事",
        task="雪球 A 股 24 小时热榜",
        provider=_safe_provider(
            (result or {}).get("provider") if isinstance(result, dict) else "",
            env=env,
            fallback="xueqiu.hot_stock.type22",
        ),
        purpose="决策事实",
        credential_keys=credential_keys,
        credential_status=credential_status,
        connectivity_status=STATUS_OK if ok else (STATUS_TIMEOUT if probe["status"] == STATUS_TIMEOUT else STATUS_FAILED),
        target_date_status=STATUS_NOT_APPLICABLE,
        row_count=len(rows or []),
        duration_ms=probe["duration_ms"],
        required_for_generation=True,
        result=RESULT_PASS if ok else RESULT_FAIL,
        advice="雪球热榜可用" if ok else "修复雪球登录态后再生成日报",
        safe_error=redact_sensitive_text(diagnostic or probe.get("error"), env=env),
    )
    return row, rows[:8] if ok else []


def _xueqiu_argument_check(env, *, hot_rows, fetcher, timeout_seconds, hot_passed):
    credential_keys = [XUEQIU_COOKIE_ENV, XUEQIU_COOKIE_CAPTURE_DIR_ENV]
    credential_status = _xueqiu_cookie_status(env)
    if not hot_passed:
        return _check_row(
            check_id="xueqiu.hot_argument",
            group="当日热度与叙事",
            task="雪球热榜 AI 理由",
            provider="xueqiu.hot_stock.argument",
            purpose="决策事实",
            credential_keys=credential_keys,
            credential_status=credential_status,
            connectivity_status=STATUS_NOT_CHECKED,
            target_date_status=STATUS_NOT_APPLICABLE,
            required_for_generation=True,
            result=RESULT_FAIL,
            advice="先修复雪球 A 股 24 小时热榜，再检查热榜理由",
        )
    symbols = [
        str(row.get("full_code") or row.get("symbol") or row.get("code") or "").strip().upper()
        for row in (hot_rows or [])[:8]
        if isinstance(row, dict)
    ]
    symbols = [item for item in symbols if item]
    if not symbols:
        return _check_row(
            check_id="xueqiu.hot_argument",
            group="当日热度与叙事",
            task="雪球热榜 AI 理由",
            provider="xueqiu.hot_stock.argument",
            purpose="决策事实",
            credential_keys=credential_keys,
            credential_status=credential_status,
            connectivity_status=STATUS_NOT_CHECKED,
            target_date_status=STATUS_NOT_APPLICABLE,
            required_for_generation=True,
            result=RESULT_FAIL,
            advice="雪球热榜没有可用于理由接口的股票代码",
        )
    probe = _run_with_timeout(lambda: fetcher(symbols, timeout=timeout_seconds), timeout_seconds=timeout_seconds)
    result = probe.get("value") or {}
    rows = result.get("rows") if isinstance(result, dict) else []
    ok = probe["status"] == STATUS_OK and isinstance(result, dict) and result.get("status") == "ok" and bool(rows)
    diagnostic = result.get("diagnostic_note") if isinstance(result, dict) else probe.get("error")
    if not ok and "登录态" in str(diagnostic or ""):
        credential_status = STATUS_SUSPECTED_EXPIRED
    return _check_row(
        check_id="xueqiu.hot_argument",
        group="当日热度与叙事",
        task="雪球热榜 AI 理由",
        provider=_safe_provider(
            (result or {}).get("provider") if isinstance(result, dict) else "",
            env=env,
            fallback="xueqiu.hot_stock.argument",
        ),
        purpose="决策事实",
        credential_keys=credential_keys,
        credential_status=credential_status,
        connectivity_status=STATUS_OK if ok else (STATUS_TIMEOUT if probe["status"] == STATUS_TIMEOUT else STATUS_FAILED),
        target_date_status=STATUS_NOT_APPLICABLE,
        row_count=len(rows or []),
        duration_ms=probe["duration_ms"],
        required_for_generation=True,
        result=RESULT_PASS if ok else RESULT_FAIL,
        advice="雪球热榜理由可用" if ok else "修复雪球理由接口或登录态后再生成日报",
        safe_error=redact_sensitive_text(diagnostic or probe.get("error"), env=env),
    )


def _quicktiny_check(env, *, fetcher, timeout_seconds):
    credential_keys = ["QUICKTINY_EXCHANGE_MONITOR_TOKEN", "QUICKTINY_TOKEN"]
    credential_status = _credential_status(env, credential_keys, mode="any")
    if credential_status != STATUS_OK:
        return _check_row(
            check_id="quicktiny.exchange_monitor",
            group="加工模型",
            task="QuickTiny 异动检测",
            provider="quicktiny.exchange_monitor",
            purpose="决策事实",
            credential_keys=credential_keys,
            credential_status=credential_status,
            connectivity_status=STATUS_NOT_CHECKED,
            target_date_status=STATUS_NOT_APPLICABLE,
            required_for_generation=True,
            result=RESULT_FAIL,
            advice="配置 QuickTiny token 后再生成日报，异动检测是生成条件",
        )
    probe = _run_with_timeout(lambda: fetcher(timeout=timeout_seconds), timeout_seconds=timeout_seconds)
    payload = probe.get("value") or {}
    rows = payload.get("data") if isinstance(payload, dict) else []
    ok = probe["status"] == STATUS_OK and isinstance(rows, list) and bool(rows)
    return _check_row(
        check_id="quicktiny.exchange_monitor",
        group="加工模型",
        task="QuickTiny 异动检测",
        provider="quicktiny.exchange_monitor",
        purpose="决策事实",
        credential_keys=credential_keys,
        credential_status=credential_status,
        connectivity_status=STATUS_OK if ok else (STATUS_TIMEOUT if probe["status"] == STATUS_TIMEOUT else STATUS_FAILED),
        target_date_status=STATUS_NOT_APPLICABLE,
        row_count=len(rows or []),
        duration_ms=probe["duration_ms"],
        required_for_generation=True,
        result=RESULT_PASS if ok else RESULT_FAIL,
        advice="QuickTiny 异动检测可用" if ok else "QuickTiny 异动检测不可用或返回空数据，先修复后再生成日报",
        safe_error=redact_sensitive_text(probe.get("error"), env=env),
    )


def _extract_investor_qa_probe_rows(probe):
    raw_value = probe.get("value")
    if isinstance(raw_value, dict):
        rows = (
            raw_value.get("rows")
            or raw_value.get("items")
            or raw_value.get("records")
            or raw_value.get("data")
            or []
        )
        raw_status = str(raw_value.get("status") or "").strip().lower()
        diagnostic = raw_value.get("diagnostic_note") or raw_value.get("error") or raw_value.get("message")
    else:
        rows = raw_value if isinstance(raw_value, list) else []
        raw_status = ""
        diagnostic = probe.get("error")
    call_succeeded = (
        probe["status"] == STATUS_OK
        and isinstance(rows, list)
        and raw_status not in {"error", "failed", "fail"}
    )
    return rows if isinstance(rows, list) else [], call_succeeded, diagnostic


def _investor_qa_check(env, *, target_date, fetcher, timeout_seconds):
    credential_keys = ["TUSHARE_TOKEN", "TUSHARE_HTTP_URL", "INVESTOR_QA_ENDPOINT_URL"]
    tushare_credential_status = _credential_status(env, ["TUSHARE_TOKEN", "TUSHARE_HTTP_URL"], mode="all")
    endpoint_credential_status = _credential_status(env, ["INVESTOR_QA_ENDPOINT_URL"], mode="any")
    credential_status = (
        STATUS_OK
        if tushare_credential_status == STATUS_OK or endpoint_credential_status == STATUS_OK
        else STATUS_MISSING
    )
    if credential_status != STATUS_OK:
        return _check_row(
            check_id="investor.qa",
            group="回补和备用",
            task="投资者问答补充源",
            provider="tushare.irm_qa+investor_qa.endpoint",
            purpose="风险补充",
            credential_keys=credential_keys,
            credential_status=credential_status,
            connectivity_status=STATUS_NOT_CHECKED,
            target_date_status=STATUS_NOT_APPLICABLE,
            required_for_generation=True,
            result=RESULT_FAIL,
            advice="Tushare 上证e互动/深证互动易问答接口存在，但当前凭证未返回可用数据；开通 Tushare 问答权限或配置外部问答端点后再生成日报",
        )
    endpoint_url = _env_value(env, "INVESTOR_QA_ENDPOINT_URL")
    official_timeout_seconds = min(5, max(1, int(timeout_seconds or DEFAULT_SOURCE_TIMEOUT_SECONDS)))
    external_timeout_seconds = min(
        max(1, int(timeout_seconds or DEFAULT_SOURCE_TIMEOUT_SECONDS)),
        max(1, int(timeout_seconds or DEFAULT_SOURCE_TIMEOUT_SECONDS) - official_timeout_seconds),
    )

    def _fetch_official_rows():
        return fetcher(
            target_date,
            endpoint_url="",
            timeout_seconds=official_timeout_seconds,
            use_tushare=True,
            lookback_trade_days=10,
        )

    official_probe = _run_with_timeout(_fetch_official_rows, timeout_seconds=official_timeout_seconds)
    official_rows, official_succeeded, official_diagnostic = _extract_investor_qa_probe_rows(official_probe)
    selected_rows = official_rows if official_succeeded and official_rows else []
    selected_probe = official_probe
    selected_provider = "tushare.irm_qa"
    selected_diagnostic = official_diagnostic
    probe_statuses = [official_probe["status"]]
    succeeded_any = official_succeeded
    total_duration_ms = int(official_probe.get("duration_ms") or 0)

    if not selected_rows and endpoint_url:
        def _fetch_external_rows():
            return fetcher(
                target_date,
                endpoint_url=endpoint_url,
                timeout_seconds=external_timeout_seconds,
                use_tushare=False,
                lookback_trade_days=10,
            )

        external_probe = _run_with_timeout(_fetch_external_rows, timeout_seconds=external_timeout_seconds)
        external_rows, external_succeeded, external_diagnostic = _extract_investor_qa_probe_rows(external_probe)
        probe_statuses.append(external_probe["status"])
        succeeded_any = succeeded_any or external_succeeded
        total_duration_ms += int(external_probe.get("duration_ms") or 0)
        if external_succeeded and external_rows:
            selected_rows = external_rows
            selected_probe = external_probe
            selected_provider = "investor_qa.endpoint"
            selected_diagnostic = external_diagnostic
        elif not selected_diagnostic:
            selected_probe = external_probe
            selected_diagnostic = external_diagnostic

    has_rows = bool(selected_rows)
    optional_without_endpoint = not endpoint_url and not has_rows
    if has_rows or succeeded_any:
        connectivity_status = STATUS_OK
    elif STATUS_TIMEOUT in probe_statuses:
        connectivity_status = STATUS_TIMEOUT
    else:
        connectivity_status = STATUS_FAILED
    if has_rows:
        advice = "投资者问答补充源可用"
    elif optional_without_endpoint:
        advice = "未配置外部问答端点，Tushare 问答未返回近 10 日可用记录；继续生成，风险快照缺少这类澄清来源"
    elif endpoint_url:
        advice = "Tushare 问答和外部问答端点均未返回目标日期近 10 日问答，确认 Tushare 权限和外部端点覆盖范围"
    elif connectivity_status == STATUS_TIMEOUT:
        advice = "Tushare 上证e互动/深证互动易问答接口存在，但本次探测超时或当前凭证未返回可用数据；开通 Tushare 问答权限后可不配置外部端点"
    else:
        advice = "Tushare 上证e互动/深证互动易问答接口存在，但当前凭证未返回可用数据；开通 Tushare 问答权限后可不配置外部端点"
    target_date_status = STATUS_COVERED if has_rows else (STATUS_MISSING if succeeded_any else STATUS_NOT_CHECKED)
    if optional_without_endpoint:
        target_date_status = STATUS_NOT_APPLICABLE
    return _check_row(
        check_id="investor.qa",
        group="回补和备用",
        task="投资者问答补充源",
        provider=selected_provider if has_rows else ("tushare.irm_qa+investor_qa.endpoint" if endpoint_url else "tushare.irm_qa"),
        purpose="风险补充",
        credential_keys=credential_keys,
        credential_status=credential_status,
        connectivity_status=connectivity_status,
        target_date_status=target_date_status,
        row_count=len(selected_rows or []),
        duration_ms=total_duration_ms,
        required_for_generation=not optional_without_endpoint,
        result=RESULT_PASS if has_rows else (RESULT_WARNING if optional_without_endpoint else RESULT_FAIL),
        advice=advice,
        safe_error=redact_sensitive_text(selected_diagnostic or selected_probe.get("error"), env=env),
    )


def _optional_missing_row(*, check_id, group, task, provider, purpose, credential_keys, advice):
    return _check_row(
        check_id=check_id,
        group=group,
        task=task,
        provider=provider,
        purpose=purpose,
        credential_keys=credential_keys,
        credential_status=STATUS_MISSING,
        connectivity_status=STATUS_NOT_CHECKED,
        target_date_status=STATUS_NOT_APPLICABLE,
        required_for_generation=False,
        result=RESULT_WARNING,
        advice=advice,
    )


def _credential_only_check(*, env, check_id, group, task, provider, purpose, credential_keys, required=False, enabled=True, advice_missing=""):
    if not enabled:
        return _check_row(
            check_id=check_id,
            group=group,
            task=task,
            provider=provider,
            purpose=purpose,
            credential_keys=credential_keys,
            credential_status=STATUS_NOT_REQUIRED,
            connectivity_status=STATUS_SKIPPED,
            target_date_status=STATUS_NOT_APPLICABLE,
            required_for_generation=False,
            result=RESULT_SKIPPED,
            advice="当前配置未启用该来源",
        )
    credential_status = _credential_status(env, credential_keys, mode="any")
    if credential_status == STATUS_OK:
        return _check_row(
            check_id=check_id,
            group=group,
            task=task,
            provider=provider,
            purpose=purpose,
            credential_keys=credential_keys,
            credential_status=credential_status,
            connectivity_status=STATUS_NOT_CHECKED,
            target_date_status=STATUS_NOT_APPLICABLE,
            required_for_generation=required,
            result=RESULT_PASS,
            advice="凭证已配置，完整采集阶段继续验证接口载荷",
        )
    return _check_row(
        check_id=check_id,
        group=group,
        task=task,
        provider=provider,
        purpose=purpose,
        credential_keys=credential_keys,
        credential_status=credential_status,
        connectivity_status=STATUS_NOT_CHECKED,
        target_date_status=STATUS_NOT_APPLICABLE,
        required_for_generation=required,
        result=RESULT_FAIL if required else RESULT_WARNING,
        advice=advice_missing or "凭证未配置，完整采集阶段可能缺少该来源",
    )


def _replay_snapshot_check(target_date):
    snapshot_path = Path(_get_snapshot_path(str(target_date), mode=LEDGER_MODE_FROZEN))
    exists = snapshot_path.exists()
    return _check_row(
        check_id="replay.snapshot",
        group="复盘事实",
        task="replay 官方快照",
        provider="snapshots.official",
        purpose="基础事实",
        credential_keys=[],
        credential_status=STATUS_NOT_REQUIRED,
        connectivity_status=STATUS_NOT_APPLICABLE,
        target_date_status=STATUS_COVERED if exists else STATUS_MISSING,
        row_count=1 if exists else 0,
        required_for_generation=True,
        result=RESULT_PASS if exists else RESULT_FAIL,
        advice="replay 快照存在" if exists else f"{target_date} 缺少官方快照，不能进入 replay",
    )


def _remote_llm_enabled(env) -> bool:
    raw = _env_value(env, "A_DAILY_REPORT_ENABLE_REMOTE_CALENDAR_LLM")
    if raw:
        return raw.lower() in {"1", "true", "yes", "on"}
    return bool(_env_value(env, "DEEPSEEK_API_KEY"))


def _summarize(checks):
    stop_reasons = [
        f"{item['task']}: {item['advice']}"
        for item in checks
        if item.get("required_for_generation") and item.get("result") == RESULT_FAIL
    ]
    warnings = [
        f"{item['task']}: {item['advice']}"
        for item in checks
        if item.get("result") == RESULT_WARNING
    ]
    return stop_reasons, warnings


def _run_live_source_checks(
    *,
    env,
    target_date,
    tushare_checker,
    xueqiu_hot_fetcher,
    xueqiu_argument_fetcher,
    quicktiny_fetcher,
    postgres_checker,
    source_timeout_seconds,
):
    checks_by_key = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            "tushare": executor.submit(
                _tushare_check,
                env,
                checker=tushare_checker,
                timeout_seconds=TUSHARE_SOURCE_TIMEOUT_SECONDS,
            ),
            "postgres": executor.submit(
                _postgres_check,
                env,
                target_date=target_date,
                postgres_only=False,
                postgres_checker=postgres_checker,
                timeout_seconds=source_timeout_seconds,
            ),
            "xueqiu_hot": executor.submit(
                _xueqiu_hot_check,
                env,
                fetcher=xueqiu_hot_fetcher,
                timeout_seconds=source_timeout_seconds,
            ),
            "quicktiny": executor.submit(
                _quicktiny_check,
                env,
                fetcher=quicktiny_fetcher,
                timeout_seconds=source_timeout_seconds,
            ),
        }

        hot_check, hot_rows = futures["xueqiu_hot"].result()
        checks_by_key["xueqiu_hot"] = hot_check
        checks_by_key["xueqiu_argument"] = _xueqiu_argument_check(
            env,
            hot_rows=hot_rows,
            fetcher=xueqiu_argument_fetcher,
            timeout_seconds=source_timeout_seconds,
            hot_passed=hot_check.get("result") == RESULT_PASS,
        )
        checks_by_key["tushare"] = futures["tushare"].result()
        checks_by_key["postgres"] = futures["postgres"].result()
        checks_by_key["quicktiny"] = futures["quicktiny"].result()

    return [
        checks_by_key["tushare"],
        checks_by_key["postgres"],
        checks_by_key["xueqiu_hot"],
        checks_by_key["xueqiu_argument"],
        checks_by_key["quicktiny"],
    ]


def run_source_health_check(
    target_date,
    *,
    root_dir=None,
    env=None,
    replay=False,
    postgres_only=False,
    write_artifacts=True,
    now=None,
    tushare_checker=check_tushare_runtime_ready,
    xueqiu_hot_fetcher=try_fetch_xueqiu_a_share_hot_24h,
    xueqiu_argument_fetcher=try_fetch_xueqiu_hot_stock_arguments,
    quicktiny_fetcher=_fetch_quicktiny_exchange_monitor_payload,
    investor_qa_fetcher=None,
    postgres_checker=None,
    source_timeout_seconds=DEFAULT_SOURCE_TIMEOUT_SECONDS,
):
    started_at = time.perf_counter()
    env = _load_env_if_needed(env)
    target_date = str(target_date or "").strip()
    checks = []

    if postgres_only:
        checks.append(
            _postgres_check(
                env,
                target_date=target_date,
                postgres_only=True,
                postgres_checker=postgres_checker,
                timeout_seconds=source_timeout_seconds,
            )
        )
    elif replay:
        checks.append(_replay_snapshot_check(target_date))
    else:
        checks.extend(
            _run_live_source_checks(
                env=env,
                target_date=target_date,
                tushare_checker=tushare_checker,
                xueqiu_hot_fetcher=xueqiu_hot_fetcher,
                xueqiu_argument_fetcher=xueqiu_argument_fetcher,
                quicktiny_fetcher=quicktiny_fetcher,
                postgres_checker=postgres_checker,
                source_timeout_seconds=source_timeout_seconds,
            )
        )
        checks.append(
            _credential_only_check(
                env=env,
                check_id="iwencai.api",
                group="回补和备用",
                task="iwencai 回补接口",
                provider="iwencai.openapi",
                purpose="回补来源",
                credential_keys=["IWENCAI_API_KEY", "IWENCAI_BASE_URL"],
                advice_missing="未配置 IWENCAI_API_KEY，问财回补路径会在完整采集阶段降级",
            )
        )
        checks.append(
            _credential_only_check(
                env=env,
                check_id="xuangubao.news",
                group="回补和备用",
                task="选股通资讯",
                provider="xuangubao.fetch_xuangubao_data",
                purpose="展示增强",
                credential_keys=["XUANGUBAO_IVANKA_TOKEN"],
                advice_missing="未配置 XUANGUBAO_IVANKA_TOKEN，盘中资讯补充可能缺失",
            )
        )
        checks.append(
            _investor_qa_check(
                env=env,
                target_date=target_date,
                fetcher=investor_qa_fetcher or fetch_investor_qa_rows,
                timeout_seconds=source_timeout_seconds,
            )
        )
        llm_enabled = _remote_llm_enabled(env)
        checks.append(
            _credential_only_check(
                env=env,
                check_id="deepseek.calendar_llm",
                group="LLM",
                task="DeepSeek 远程日历分析",
                provider="deepseek.chat",
                purpose="展示增强",
                credential_keys=["DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"],
                enabled=llm_enabled,
                advice_missing="远程日历分析已启用但 DEEPSEEK_API_KEY 未配置",
            )
        )

    stop_reasons, warnings = _summarize(checks)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "target_date": target_date,
        "generated_at": _now_text(now),
        "duration_ms": _duration_ms(started_at),
        "overall_result": OVERALL_STOP if stop_reasons else OVERALL_READY,
        "stop_reasons": stop_reasons,
        "blocking_failures": list(stop_reasons),
        "warnings": warnings,
        "checks": checks,
        "artifacts": {},
    }
    if write_artifacts:
        payload["artifacts"] = write_source_health_artifacts(payload, root_dir=root_dir)
    return payload


def write_source_health_artifacts(payload, *, root_dir=None):
    root = _logs_root(root_dir)
    root.mkdir(parents=True, exist_ok=True)
    target_date = str((payload or {}).get("target_date") or "unknown")
    json_path = root / f"{target_date}_source_health.json"
    html_path = root / f"{target_date}_source_health.html"
    latest_json = root / "latest_source_health.json"
    latest_html = root / "latest_source_health.html"
    artifacts = {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "latest_json_path": str(latest_json),
        "latest_html_path": str(latest_html),
    }
    payload["artifacts"] = artifacts
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    html_text = render_source_health_html(payload)
    json_path.write_text(json_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_html.write_text(html_text, encoding="utf-8")
    return artifacts


def _mark(status, *, result=None):
    if result == RESULT_SKIPPED or status in {STATUS_NOT_APPLICABLE, STATUS_NOT_REQUIRED, STATUS_NOT_CHECKED, STATUS_SKIPPED}:
        return "-"
    if status in {STATUS_OK, STATUS_COVERED}:
        return "✓"
    return "×"


def _result_label(result):
    return {
        RESULT_PASS: "可生成",
        RESULT_FAIL: "停止生成",
        RESULT_WARNING: "可生成（可选补充未就绪）",
        RESULT_SKIPPED: "可跳过",
    }.get(result, str(result or ""))


def _overall_label(overall):
    return {
        OVERALL_READY: "可生成",
        OVERALL_STOP: "停止生成",
    }.get(str(overall or ""), str(overall or ""))


def render_source_health_html(payload) -> str:
    payload = payload or {}
    rows = []
    check_items = list(payload.get("checks") or [])

    def _status_mark(status, *, result=None):
        mark = _mark(status, result=result)
        css = "mark-neutral"
        if mark == "✓":
            css = "mark-ok"
        elif mark == "×":
            css = "mark-bad"
        return f'<span class="status-mark {css}">{html.escape(mark)}</span>'

    for item in payload.get("checks") or []:
        result = item.get("result", "")
        css = "source-pass" if result == RESULT_PASS else "source-fail" if result == RESULT_FAIL else "source-warning" if result == RESULT_WARNING else "source-skip"
        rows.append(
            "<tr class=\"{css}\">"
            "<td>{task}</td><td>{purpose}</td><td>{credential}</td><td>{connectivity}</td>"
            "<td>{target_date}</td><td>{row_count}</td><td>{duration}</td><td>{result}</td><td>{advice}</td>"
            "</tr>".format(
                css=css,
                task=html.escape(str(item.get("task") or "")),
                purpose=html.escape(str(item.get("purpose") or "")),
                credential=_status_mark(item.get("credential_status"), result=result),
                connectivity=_status_mark(item.get("connectivity_status"), result=result),
                target_date=_status_mark(item.get("target_date_status"), result=result),
                row_count=html.escape(str(item.get("row_count") if item.get("row_count") not in (None, "") else "-")),
                duration=html.escape(f"{int(item.get('duration_ms') or 0)} ms"),
                result=html.escape(_result_label(result)),
                advice=html.escape(str(item.get("advice") or item.get("safe_error") or "")),
            )
        )
    total = len(check_items)
    passed = sum(1 for item in check_items if (item or {}).get("result") == RESULT_PASS)
    failed = sum(1 for item in check_items if (item or {}).get("result") == RESULT_FAIL)
    warnings = len(payload.get("warnings") or [])
    overall = str(payload.get("overall_result") or "")
    overall_css = "overall-ready" if overall == OVERALL_READY else "overall-stop"
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>日报生成前数据源检查 - {target_date}</title>
  <style>
    :root {{
      --reader-bg: #fff9ef;
      --reader-surface: rgba(255, 252, 246, 0.92);
      --reader-surface-strong: #fffaf3;
      --reader-line: rgba(108, 69, 55, 0.16);
      --reader-line-strong: rgba(108, 69, 55, 0.28);
      --reader-text: #2d1712;
      --reader-muted: #6c4537;
      --reader-muted-soft: #8b6a5b;
      --accent-red: #e73922;
      --accent-orange: #ff8a1f;
      --accent-green: #176e54;
      --accent-blue: #2364aa;
      --accent-amber: #a36500;
      color-scheme: light;
      font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", "Avenir Next", -apple-system, BlinkMacSystemFont, sans-serif;
      letter-spacing: 0;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--reader-bg);
      color: var(--reader-text);
      font-size: 15px;
      line-height: 1.72;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }}
    .bear-source-health {{
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 34px 0 44px;
    }}
    .hero {{
      border-bottom: 1px solid var(--reader-line-strong);
      padding: 0 0 18px;
      margin-bottom: 18px;
    }}
    .kicker {{
      margin: 0 0 8px;
      color: var(--accent-red);
      font-size: 12px;
      font-weight: 900;
      line-height: 1.35;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0;
      color: var(--reader-text);
      font-size: 28px;
      line-height: 1.28;
      font-weight: 900;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin: 14px 0 0;
      color: var(--reader-muted);
      font-size: 13px;
      font-weight: 700;
    }}
    .summary-chip,
    .overall-pill {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      border: 1px solid var(--reader-line);
      border-radius: 999px;
      padding: 4px 10px;
      background: rgba(255, 255, 255, 0.5);
    }}
    .overall-pill {{
      font-weight: 900;
    }}
    .overall-ready {{
      color: var(--accent-green);
      border-color: rgba(23, 110, 84, 0.28);
      background: rgba(224, 245, 235, 0.78);
    }}
    .overall-stop {{
      color: var(--accent-red);
      border-color: rgba(231, 57, 34, 0.28);
      background: rgba(255, 238, 235, 0.82);
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--reader-line);
      border-radius: 8px;
      background: var(--reader-surface);
      box-shadow: 0 18px 44px rgba(104, 56, 24, 0.08);
    }}
    table {{
      border-collapse: separate;
      border-spacing: 0;
      width: 100%;
      min-width: 980px;
      font-size: 13px;
    }}
    th,
    td {{
      border-bottom: 1px solid rgba(108, 69, 55, 0.12);
      padding: 10px 11px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #fff0dc;
      color: #5f211a;
      font-size: 12px;
      font-weight: 900;
      line-height: 1.35;
      white-space: nowrap;
    }}
    td:first-child {{
      min-width: 172px;
      color: var(--reader-text);
      font-weight: 900;
    }}
    td:nth-child(2),
    td:nth-child(8) {{
      white-space: nowrap;
      font-weight: 800;
    }}
    td:nth-child(3),
    td:nth-child(4),
    td:nth-child(5),
    td:nth-child(6),
    td:nth-child(7) {{
      white-space: nowrap;
    }}
    tbody tr:last-child td {{
      border-bottom: 0;
    }}
    tbody tr:hover td {{
      background-image: linear-gradient(0deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.34));
    }}
    .source-pass td {{
      background-color: rgba(235, 250, 242, 0.64);
    }}
    .source-fail td {{
      background-color: rgba(255, 238, 235, 0.72);
    }}
    .source-warning td {{
      background-color: rgba(255, 247, 218, 0.78);
    }}
    .source-skip td {{
      background-color: rgba(255, 250, 243, 0.72);
      color: var(--reader-muted-soft);
    }}
    .status-mark {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      border: 1px solid var(--reader-line);
      border-radius: 999px;
      font-size: 13px;
      font-weight: 900;
      line-height: 1;
      background: #fffaf3;
    }}
    .mark-ok {{
      color: var(--accent-green);
      border-color: rgba(23, 110, 84, 0.26);
      background: rgba(224, 245, 235, 0.9);
    }}
    .mark-bad {{
      color: var(--accent-red);
      border-color: rgba(231, 57, 34, 0.28);
      background: rgba(255, 238, 235, 0.9);
    }}
    .mark-neutral {{
      color: var(--reader-muted-soft);
      background: rgba(255, 250, 243, 0.86);
    }}
  </style>
</head>
<body>
  <main class="bear-source-health">
    <section class="hero">
      <p class="kicker">Source Health</p>
      <h1>日报生成前数据源检查</h1>
      <div class="summary">
        <span class="summary-chip">日期：{target_date}</span>
        <span class="overall-pill {overall_css}">结论：{overall_label}</span>
        <span class="summary-chip">耗时：{duration} ms</span>
        <span class="summary-chip">通过：{passed}/{total}</span>
        <span class="summary-chip">停止项：{failed}</span>
        <span class="summary-chip">提示：{warnings}</span>
      </div>
    </section>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>数据源任务</th><th>用途</th><th>凭证</th><th>接口</th><th>目标日期</th><th>记录数</th><th>耗时</th><th>结论</th><th>建议</th></tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
  </main>
</body>
</html>
""".format(
        target_date=html.escape(str(payload.get("target_date") or "")),
        overall_css=html.escape(overall_css),
        overall_label=html.escape(_overall_label(overall)),
        duration=html.escape(str(payload.get("duration_ms") or 0)),
        passed=passed,
        total=total,
        failed=failed,
        warnings=warnings,
        rows="\n      ".join(rows),
    )


def render_source_health_terminal_lines(payload):
    payload = payload or {}
    lines = [
        "生成前数据源检查: {} / {}".format(
            _overall_label(payload.get("overall_result", "unknown")),
            payload.get("target_date", ""),
        )
    ]
    for item in payload.get("checks") or []:
        lines.append(
            "- {task}: {result} | 凭证={credential} | 接口={connectivity} | 目标日期={target} | 记录数={rows} | 耗时={duration}ms".format(
                task=item.get("task", ""),
                result=_result_label(item.get("result", "")),
                credential=_mark(item.get("credential_status"), result=item.get("result")),
                connectivity=_mark(item.get("connectivity_status"), result=item.get("result")),
                target=_mark(item.get("target_date_status"), result=item.get("result")),
                rows=item.get("row_count", 0),
                duration=item.get("duration_ms", 0),
            )
        )
    if payload.get("stop_reasons"):
        lines.append("关键数据不完整，停止生成；缺失项：{}".format("、".join(payload.get("stop_reasons") or [])))
    artifacts = payload.get("artifacts") or {}
    if artifacts.get("html_path"):
        lines.append(f"数据源检查表: {artifacts.get('html_path')}")
    return lines


def source_health_failure_message(payload) -> str:
    payload = payload or {}
    reasons = "、".join(payload.get("stop_reasons") or payload.get("blocking_failures") or [])
    html_path = (payload.get("artifacts") or {}).get("html_path", "")
    return "生成前数据源检查未通过，停止生成：{}。\n数据源检查表：{}".format(reasons or "关键数据不完整", html_path or "未生成")


def assert_source_health_ready(payload):
    if (payload or {}).get("overall_result") == OVERALL_STOP:
        raise SourceHealthCriticalError(source_health_failure_message(payload))
    return payload


def _default_target_date():
    return (_dt.datetime.now() - _dt.timedelta(days=1)).strftime("%Y-%m-%d")


def main(argv=None):
    parser = argparse.ArgumentParser(description="日报生成前数据源健康检查")
    parser.add_argument("date", nargs="?", default=None, help="目标日期，格式 YYYY-MM-DD")
    parser.add_argument("--replay", action="store_true", help="只检查 replay 所需快照")
    parser.add_argument("--postgres-only", action="store_true", help="按 PostgreSQL-only 条件检查")
    args = parser.parse_args(argv)
    payload = run_source_health_check(
        args.date or _default_target_date(),
        replay=bool(args.replay),
        postgres_only=bool(args.postgres_only),
    )
    for line in render_source_health_terminal_lines(payload):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
