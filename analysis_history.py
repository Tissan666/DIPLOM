"""SQLite-backed storage for completed analysis reports."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4


SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_reports (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_label TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    total_count INTEGER NOT NULL,
    suspicious_count INTEGER NOT NULL,
    manual_review_count INTEGER NOT NULL,
    report_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_created_at
ON analysis_reports(created_at DESC);
"""


def save_analysis_report(db_path: str | Path, report: dict[str, Any], source_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist an analysis report and return the report with history metadata."""
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report_id = uuid4().hex
    stored_report = dict(report)
    stored_report["history"] = {
        "report_id": report_id,
        "created_at": created_at,
        "history_url": f"/api/history/{report_id}",
    }
    metadata = _extract_metadata(stored_report, source_key=source_key)
    record = {
        "id": report_id,
        "created_at": created_at,
        **metadata,
    }

    with _connect(db_path) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            """
            INSERT INTO analysis_reports (
                id,
                created_at,
                source_type,
                source_label,
                risk_level,
                total_count,
                suspicious_count,
                manual_review_count,
                report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["created_at"],
                record["source_type"],
                record["source_label"],
                record["risk_level"],
                record["total_count"],
                record["suspicious_count"],
                record["manual_review_count"],
                json.dumps(stored_report, ensure_ascii=False, default=str),
            ),
        )

    return stored_report, record


def list_analysis_reports(db_path: str | Path, limit: int = 30) -> list[dict[str, Any]]:
    """Return recent analysis-report metadata."""
    bounded_limit = max(1, min(int(limit), 100))
    with _connect(db_path) as connection:
        connection.executescript(SCHEMA)
        rows = connection.execute(
            """
            SELECT
                id,
                created_at,
                source_type,
                source_label,
                risk_level,
                total_count,
                suspicious_count,
                manual_review_count
            FROM analysis_reports
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_analysis_report(db_path: str | Path, report_id: str) -> dict[str, Any] | None:
    """Return one stored report by id."""
    with _connect(db_path) as connection:
        connection.executescript(SCHEMA)
        row = connection.execute(
            "SELECT report_json FROM analysis_reports WHERE id = ?",
            (report_id,),
        ).fetchone()

    if row is None:
        return None
    return json.loads(row["report_json"])


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _extract_metadata(report: dict[str, Any], source_key: str) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    request_meta = report.get("request") if isinstance(report.get("request"), dict) else {}

    source_type = str(request_meta.get("source_type") or summary.get("source_type") or source_key or "unknown")
    source_label = str(
        request_meta.get("source_url")
        or summary.get("source_url")
        or request_meta.get("source_site")
        or summary.get("source_site")
        or source_key
        or "unknown"
    )
    risk_level = str(summary.get("risk_level") or summary.get("rating_manipulation_risk") or "unknown")

    return {
        "source_type": source_type,
        "source_label": source_label,
        "risk_level": risk_level,
        "total_count": _int_value(summary.get("total_reviews") or summary.get("total_records") or 0),
        "suspicious_count": _int_value(summary.get("suspicious_reviews") or summary.get("suspicious_ratings") or 0),
        "manual_review_count": _int_value(summary.get("manual_review_reviews") or 0),
    }


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "source_type": row["source_type"],
        "source_label": row["source_label"],
        "risk_level": row["risk_level"],
        "total_count": row["total_count"],
        "suspicious_count": row["suspicious_count"],
        "manual_review_count": row["manual_review_count"],
        "history_url": f"/api/history/{row['id']}",
    }
