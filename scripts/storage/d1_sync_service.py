from __future__ import annotations

import sqlite3
from pathlib import Path

__all__ = [
    "D1SyncService",
]


SYNC_TABLES = [
    "provider_source_runs",
    "stock_daily_quotes_recent",
    "market_daily_totals",
    "turnover_rank_daily",
    "turnover_share_series",
    "report_artifacts",
]


def _quote_sql_value(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


class D1SyncService:
    def __init__(self, sqlite_db_path):
        self.sqlite_db_path = Path(sqlite_db_path)

    def _connect(self):
        conn = sqlite3.connect(str(self.sqlite_db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _table_columns(self, conn, table_name):
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [row["name"] for row in rows]

    def _export_table_sql(self, conn, table_name):
        columns = self._table_columns(conn, table_name)
        if not columns:
            return []
        rows = conn.execute(f"SELECT {', '.join(columns)} FROM {table_name}").fetchall()
        statements = []
        column_sql = ", ".join(columns)
        for row in rows:
            value_sql = ", ".join(_quote_sql_value(row[column]) for column in columns)
            statements.append(f"INSERT OR REPLACE INTO {table_name} ({column_sql}) VALUES ({value_sql});")
        return statements

    def export_sql(self, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            statements = []
            for table_name in reversed(SYNC_TABLES):
                statements.append(f"DELETE FROM {table_name};")
            for table_name in SYNC_TABLES:
                statements.extend(self._export_table_sql(conn, table_name))
        output_path.write_text("\n".join(statements) + "\n", encoding="utf-8")
        return output_path

    def build_execute_command(self, database_name, sql_path, *, remote=True):
        command = [
            "wrangler",
            "d1",
            "execute",
            str(database_name),
        ]
        command.append("--remote" if remote else "--local")
        command.extend(["--file", str(sql_path)])
        return command
