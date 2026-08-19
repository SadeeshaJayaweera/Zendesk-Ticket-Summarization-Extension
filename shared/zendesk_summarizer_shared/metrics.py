"""Lightweight Metrics Collector for Zendesk Ticket Summarizer.

Tracks operational metrics including summaries generated, notes posted,
webhooks processed, error distributions, and system uptime.
"""

import time
from datetime import datetime
from threading import Lock
from typing import Any, Dict


class MetricsCollector:
    """Thread-safe in-memory metrics collector."""

    def __init__(self):
        self._lock = Lock()
        self._start_time = time.time()
        self._start_datetime = datetime.utcnow().isoformat() + "Z"

        self._summaries_generated = 0
        self._summaries_by_style: Dict[str, int] = {}
        self._summaries_by_provider: Dict[str, int] = {}

        self._notes_posted = 0
        self._webhooks_received = 0
        self._webhooks_by_status: Dict[str, int] = {}

        self._errors_total = 0
        self._errors_by_category: Dict[str, int] = {
            "zendesk": 0,
            "llm": 0,
            "webhook": 0,
            "rate_limit": 0,
            "internal": 0,
        }

    def record_summary_generated(self, style: str = "standard", provider: str = "gemini"):
        """Increment summary generation counters."""
        with self._lock:
            self._summaries_generated += 1
            self._summaries_by_style[style] = self._summaries_by_style.get(style, 0) + 1
            self._summaries_by_provider[provider] = self._summaries_by_provider.get(provider, 0) + 1

    def record_note_posted(self):
        """Increment posted note counter."""
        with self._lock:
            self._notes_posted += 1

    def record_webhook_received(self, status: str = "success"):
        """Increment webhook counter."""
        with self._lock:
            self._webhooks_received += 1
            self._webhooks_by_status[status] = self._webhooks_by_status.get(status, 0) + 1

    def record_error(self, category: str = "internal"):
        """Increment error counter by category."""
        with self._lock:
            self._errors_total += 1
            cat = category.lower()
            if cat not in self._errors_by_category:
                cat = "internal"
            self._errors_by_category[cat] = self._errors_by_category.get(cat, 0) + 1

    def get_metrics(self) -> Dict[str, Any]:
        """Return snapshot of current metrics."""
        with self._lock:
            uptime = int(time.time() - self._start_time)
            return {
                "service": "zendesk-ticket-summarizer",
                "uptime_seconds": uptime,
                "server_start_time": self._start_datetime,
                "summaries_generated": {
                    "total": self._summaries_generated,
                    "by_style": dict(self._summaries_by_style),
                    "by_provider": dict(self._summaries_by_provider),
                },
                "notes_posted": {
                    "total": self._notes_posted,
                },
                "webhooks": {
                    "total_received": self._webhooks_received,
                    "by_status": dict(self._webhooks_by_status),
                },
                "errors": {
                    "total": self._errors_total,
                    "by_category": dict(self._errors_by_category),
                },
            }

    def reset(self):
        """Reset counters (used for unit tests)."""
        with self._lock:
            self._summaries_generated = 0
            self._summaries_by_style.clear()
            self._summaries_by_provider.clear()
            self._notes_posted = 0
            self._webhooks_received = 0
            self._webhooks_by_status.clear()
            self._errors_total = 0
            self._errors_by_category = {k: 0 for k in self._errors_by_category}


# Global singleton instance
_global_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Retrieve singleton MetricsCollector instance."""
    return _global_metrics
