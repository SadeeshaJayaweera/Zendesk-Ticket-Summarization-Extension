"""SQLite Audit Logger with WAL Mode for Zendesk Ticket Summarizer.

Logs all summarization events, note postings, and automated webhook triggers
to a resilient, lock-contention-safe SQLite database file.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger("zendesk_summarizer.audit")

DEFAULT_DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "data", "audit.db"))


class AuditLogger:
    """SQLite-backed audit logger with Write-Ahead Logging (WAL) enabled."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.abspath(DEFAULT_DB_PATH)
        self._lock = Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a configured SQLite connection with WAL mode and busy timeout."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging for high concurrency and zero reader blocking
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Initialize audit logs schema if not present."""
        try:
            with self._lock, self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_id INTEGER,
                        event_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        model_used TEXT,
                        summary_style TEXT,
                        source TEXT,
                        details TEXT,
                        created_at TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_ticket_id ON audit_logs(ticket_id);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);"
                )
        except Exception as exc:
            logger.warning("Could not initialize SQLite audit database: %s", exc)

    def log_event(
        self,
        event_type: str,
        ticket_id: Optional[int] = None,
        status: str = "success",
        model_used: Optional[str] = None,
        summary_style: Optional[str] = None,
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record an audit event to SQLite."""
        try:
            created_at = datetime.utcnow().isoformat() + "Z"
            details_json = json.dumps(details) if details else None

            with self._lock, self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_logs (
                        ticket_id, event_type, status, model_used, summary_style, source, details, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        ticket_id,
                        event_type,
                        status,
                        model_used,
                        summary_style,
                        source,
                        details_json,
                        created_at,
                    ),
                )
            return True
        except Exception as exc:
            logger.warning("Failed to write to SQLite audit log: %s", exc)
            return False

    def query_recent_logs(self, limit: int = 50, ticket_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query recent audit events."""
        try:
            with self._lock, self._get_connection() as conn:
                if ticket_id is not None:
                    cur = conn.execute(
                        "SELECT * FROM audit_logs WHERE ticket_id = ? ORDER BY id DESC LIMIT ?",
                        (ticket_id, limit),
                    )
                else:
                    cur = conn.execute(
                        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
                        (limit,),
                    )
                rows = cur.fetchall()
                results = []
                for r in rows:
                    item = dict(r)
                    if item.get("details"):
                        try:
                            item["details"] = json.loads(item["details"])
                        except Exception:
                            pass
                    results.append(item)
                return results
        except Exception as exc:
            logger.warning("Failed to query SQLite audit log: %s", exc)
            return []


# Global singleton instance
_global_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db_path: Optional[str] = None) -> AuditLogger:
    """Retrieve singleton AuditLogger instance."""
    global _global_audit_logger
    if _global_audit_logger is None:
        _global_audit_logger = AuditLogger(db_path=db_path)
    return _global_audit_logger
