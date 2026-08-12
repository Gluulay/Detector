"""
Lightweight persistence for submitted proofs, using SQLite (built into
Python, no extra dependency). Good enough for a small-to-medium site;
if you outgrow it later, swap this module for a real database without
touching main.py's endpoint logic.
"""

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Optional

from . import config

os.makedirs(config.UPLOAD_DIR, exist_ok=True)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                reference_id TEXT,
                provider TEXT,
                image_path TEXT NOT NULL,
                fraud_score REAL NOT NULL,
                verdict TEXT NOT NULL,
                status TEXT NOT NULL,
                reasons TEXT NOT NULL,
                reviewed INTEGER NOT NULL DEFAULT 0,
                reviewer_note TEXT
            )
            """
        )
        conn.commit()


def save_submission(
    image_bytes: bytes,
    reference_id: Optional[str],
    detection: dict,
    status: str,
) -> dict:
    submission_id = str(uuid.uuid4())
    image_path = os.path.join(config.UPLOAD_DIR, f"{submission_id}.jpg")
    with open(image_path, "wb") as f:
        f.write(image_bytes)

    provider = detection.get("details", {}).get("provider", {}).get("guess")

    record = {
        "id": submission_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reference_id": reference_id,
        "provider": provider,  # "kpay" | "wavepay" | None (couldn't tell)
        "image_path": image_path,
        "fraud_score": detection["fraud_score"],
        "verdict": detection["verdict"],
        "status": status,
        "reasons": json.dumps(detection["reasons"]),
        "reviewed": 0,
        "reviewer_note": None,
    }

    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO submissions
                (id, created_at, reference_id, provider, image_path, fraud_score,
                 verdict, status, reasons, reviewed, reviewer_note)
            VALUES
                (:id, :created_at, :reference_id, :provider, :image_path, :fraud_score,
                 :verdict, :status, :reasons, :reviewed, :reviewer_note)
            """,
            record,
        )
        conn.commit()

    return record


def list_submissions(status: Optional[str] = None, provider: Optional[str] = None) -> list:
    query = "SELECT * FROM submissions"
    clauses = []
    params: list = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if provider:
        clauses.append("provider = ?")
        params.append(provider)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"

    with closing(_connect()) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def get_submission(submission_id: str) -> Optional[dict]:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
    return dict(row) if row else None


def mark_reviewed(
    submission_id: str, status: str, note: Optional[str]
) -> Optional[dict]:
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE submissions SET reviewed = 1, status = ?, reviewer_note = ? WHERE id = ?",
            (status, note, submission_id),
        )
        conn.commit()
    return get_submission(submission_id)
