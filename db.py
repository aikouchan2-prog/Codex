"""SQLite access layer for scheduled Discord posts."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path(__file__).parent / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  webhook_url  TEXT    NOT NULL,
  content      TEXT    NOT NULL DEFAULT '',
  image_path   TEXT,
  scheduled_at TEXT    NOT NULL,
  status       TEXT    NOT NULL DEFAULT 'pending',
  sent_at      TEXT,
  error        TEXT,
  created_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_due ON posts(status, scheduled_at);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def create_post(
    webhook_url: str,
    content: str,
    image_path: str | None,
    scheduled_at_utc: datetime,
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO posts (webhook_url, content, image_path, scheduled_at, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (
                webhook_url,
                content,
                image_path,
                scheduled_at_utc.strftime("%Y-%m-%dT%H:%M:%S"),
                _now_iso(),
            ),
        )
        return int(cur.lastrowid)


def list_posts(limit: int = 200) -> list[sqlite3.Row]:
    with _connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM posts ORDER BY scheduled_at DESC LIMIT ?", (limit,)
            )
        )


def get_post(post_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()


def cancel_post(post_id: int) -> bool:
    """Cancel a pending post. Returns True if a row was updated."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE posts SET status='cancelled' WHERE id=? AND status='pending'",
            (post_id,),
        )
        return cur.rowcount > 0


def claim_due(now_utc: datetime, limit: int = 20) -> list[sqlite3.Row]:
    """Atomically claim due pending posts, flipping them to 'sending'.

    Returns the rows that were successfully claimed.
    """
    now_str = now_utc.strftime("%Y-%m-%dT%H:%M:%S")
    with _connect() as conn:
        rows = list(
            conn.execute(
                """
                SELECT * FROM posts
                WHERE status='pending' AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                LIMIT ?
                """,
                (now_str, limit),
            )
        )
        claimed: list[sqlite3.Row] = []
        for row in rows:
            cur = conn.execute(
                "UPDATE posts SET status='sending' WHERE id=? AND status='pending'",
                (row["id"],),
            )
            if cur.rowcount == 1:
                claimed.append(row)
        return claimed


def mark_sent(post_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE posts SET status='sent', sent_at=?, error=NULL WHERE id=?",
            (_now_iso(), post_id),
        )


def mark_failed(post_id: int, error: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE posts SET status='failed', error=? WHERE id=?",
            (error[:1000], post_id),
        )


def reset_stuck_sending() -> int:
    """On startup, recover rows that were 'sending' when the process died."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE posts SET status='pending' WHERE status='sending'"
        )
        return cur.rowcount
