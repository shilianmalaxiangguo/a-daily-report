from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from pipelines.cloudflare_free_turnover_pipeline import run_turnover_pipeline

DEFAULT_ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / ".generated" / "r2"
DEFAULT_PUBLIC_COPY_PATH = (
    Path(__file__).resolve().parents[2]
    / "snap-ui"
    / "public"
    / "data"
    / "snap-ui"
    / "turnover"
    / "top50-share"
    / "latest.json"
)

__all__ = [
    "DEFAULT_ARTIFACT_ROOT",
    "DEFAULT_PUBLIC_COPY_PATH",
    "refresh_top50_turnover_artifact",
    "main",
]


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _copy_public_artifact(source_path, public_copy_path):
    public_copy_path = Path(public_copy_path)
    public_copy_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = public_copy_path.with_suffix(public_copy_path.suffix + ".tmp")
    shutil.copyfile(source_path, temp_path)
    os.replace(temp_path, public_copy_path)
    return public_copy_path


def _summarize_payload(payload):
    rows = payload.get("rows") or []
    latest_row = rows[-1] if rows else {}
    return {
        "row_count": len(rows),
        "latest_share_pct": latest_row.get("share_pct", 0),
        "has_sector_breakdown": bool(payload.get("latest_sector_breakdown")),
        "query_window": payload.get("query_window") or {},
    }


def refresh_top50_turnover_artifact(
    trade_date,
    *,
    db_path=None,
    artifact_root=DEFAULT_ARTIFACT_ROOT,
    public_copy_path=DEFAULT_PUBLIC_COPY_PATH,
    market_data_service=None,
    database_service=None,
    pro=None,
    rank_limit=100,
    export_limit=50,
    window_days=25,
    copy_public=True,
):
    artifact_root = Path(artifact_root)
    result = run_turnover_pipeline(
        trade_date,
        db_path=db_path,
        artifact_root=artifact_root,
        pro=pro,
        market_data_service=market_data_service,
        database_service=database_service,
        rank_limit=rank_limit,
        export_limit=export_limit,
        window_days=window_days,
    )
    r2_artifact_path = artifact_root / result["export"]["r2_key"]
    payload = _load_json(r2_artifact_path)
    summary = _summarize_payload(payload)
    if copy_public:
        public_copy_path = _copy_public_artifact(r2_artifact_path, public_copy_path)
    else:
        public_copy_path = None
    return {
        "trade_date": trade_date,
        "r2_artifact_path": str(r2_artifact_path),
        "public_copy_path": str(public_copy_path) if public_copy_path else "",
        "content_hash": result["export"]["content_hash"],
        **summary,
    }


def _build_parser():
    parser = argparse.ArgumentParser(description="Refresh local Tushare Top50 turnover share artifact.")
    parser.add_argument("trade_date", help="Trade date in YYYY-MM-DD format")
    parser.add_argument("--db-path", default=None, help="SQLite D1-compatible DB path")
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT), help="Local R2 artifact root")
    parser.add_argument("--public-copy-path", default=str(DEFAULT_PUBLIC_COPY_PATH), help="snap-ui public latest.json target")
    parser.add_argument("--no-public-copy", action="store_true", help="Only write .generated/r2 artifact")
    parser.add_argument("--rank-limit", type=int, default=100)
    parser.add_argument("--export-limit", type=int, default=50)
    parser.add_argument("--window-days", type=int, default=25)
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    result = refresh_top50_turnover_artifact(
        args.trade_date,
        db_path=args.db_path,
        artifact_root=args.artifact_root,
        public_copy_path=args.public_copy_path,
        rank_limit=args.rank_limit,
        export_limit=args.export_limit,
        window_days=args.window_days,
        copy_public=not args.no_public_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
