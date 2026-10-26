"""Local, append-only correction history, scoped to exact CSV and engine version."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from classifier import Result, eligibility

CALENDAR_FREQUENCIES = {"Daily", "Weekdays (Mon–Fri)", "Weekly", "Fortnightly",
                        "Twice monthly", "Monthly", "Quarterly"}


def dataset_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corrected_policy(frequency: str, minutes: str = "") -> tuple[str, str]:
    if frequency == "Unknown":
        return "Unknown", "Unknown"
    if frequency in CALENDAR_FREQUENCIES:
        return frequency, eligibility(1440)
    if frequency != "Fixed interval (minutes)":
        raise ValueError("Choose a supported frequency.")
    try:
        value = Decimal(minutes)
    except InvalidOperation as exc:
        raise ValueError("Enter a positive finite number of minutes.") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError("Enter a positive finite number of minutes.")
    # Decimal comparison protects the exact boundary for reviewer input too.
    decision = eligibility(value)
    return f"Every {value} minutes", decision


class CorrectionStore:
    def __init__(self, path: str | Path = ".local/corrections.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS originals (
                    dataset TEXT NOT NULL, workflow TEXT NOT NULL, engine TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (dataset, workflow, engine)
                );
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL, workflow TEXT NOT NULL, engine TEXT NOT NULL,
                    timestamp TEXT NOT NULL, cadence TEXT NOT NULL, decision TEXT NOT NULL,
                    reason TEXT NOT NULL, source TEXT NOT NULL, reviewer TEXT,
                    provenance TEXT NOT NULL DEFAULT 'reviewer-supplied',
                    FOREIGN KEY(dataset, workflow, engine) REFERENCES originals(dataset, workflow, engine)
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys = ON")
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def register(self, dataset: str, result: Result):
        payload = json.dumps(result.to_dict(), sort_keys=True)
        with self.connect() as db:
            existing = db.execute("SELECT result_json FROM originals WHERE dataset=? AND workflow=? AND engine=?",
                                  (dataset, result.workflow, result.engine_version)).fetchone()
            if existing and existing[0] != payload:
                raise ValueError("Original result changed without a new engine version; refusing to overwrite audit history.")
            db.execute("INSERT OR IGNORE INTO originals VALUES (?, ?, ?, ?)",
                       (dataset, result.workflow, result.engine_version, payload))

    def older_versions(self, dataset: str, engine: str) -> list[str]:
        with self.connect() as db:
            return [row[0] for row in db.execute(
                "SELECT DISTINCT engine FROM originals WHERE dataset=? AND engine!=? ORDER BY engine",
                (dataset, engine))]

    def append(self, dataset: str, result: Result, frequency: str, minutes: str,
               reason: str, source: str, reviewer: str = "") -> dict:
        if not reason.strip() or not source.strip():
            raise ValueError("A reason and supporting source are required.")
        cadence, decision = corrected_policy(frequency, minutes)
        self.register(dataset, result)
        with self.connect() as db:
            cursor = db.execute("""INSERT INTO corrections
                (dataset,workflow,engine,timestamp,cadence,decision,reason,source,reviewer)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (dataset, result.workflow, result.engine_version, datetime.now(timezone.utc).isoformat(),
                 cadence, decision, reason.strip(), source.strip(), reviewer.strip() or None))
            return dict(db.execute("SELECT * FROM corrections WHERE id=?", (cursor.lastrowid,)).fetchone())

    def history(self, dataset: str, result: Result) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM corrections WHERE dataset=? AND workflow=? AND engine=? ORDER BY id",
                              (dataset, result.workflow, result.engine_version))
            return [dict(r) for r in rows]

    def original(self, dataset: str, result: Result) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT result_json FROM originals WHERE dataset=? AND workflow=? AND engine=?",
                             (dataset, result.workflow, result.engine_version)).fetchone()
            return json.loads(row[0]) if row else None

    def review(self, dataset: str, result: Result) -> dict:
        corrections = self.history(dataset, result)
        return {"original": self.original(dataset, result) or result.to_dict(), "corrections": corrections,
                "effective": corrections[-1] if corrections else {
                    "cadence": result.cadence, "decision": result.decision, "provenance": "system-inferred"}}
