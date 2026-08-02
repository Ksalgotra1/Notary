"""
Pipeline observability metrics (Add-on #10).

Records every generation event (provider, latency, success/fail) in-memory
and in SQLite. Exposed via /metrics endpoint for the dashboard.

Design: pure in-process — no Redis, no external service.
The in-memory store is fast; SQLite provides persistence across restarts.
"""
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("CACHE_DB_PATH", "notary_cache.sqlite")

METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS generation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    modality TEXT NOT NULL,
    success INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    error_type TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_provider ON generation_events(provider);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON generation_events(created_at DESC);
"""

# In-memory ring buffer: last 50 events for dashboard live feed
_recent_events: list[dict] = []
_MAX_RECENT = 50


async def init_metrics_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(METRICS_SCHEMA)
        await db.commit()


async def record_generation(
    *,
    run_id: Optional[str],
    provider: str,
    model: str,
    modality: str,
    success: bool,
    latency_ms: int,
    error_type: Optional[str] = None,
) -> None:
    """Record a generation event to both in-memory ring buffer and SQLite."""
    event = {
        "run_id": run_id,
        "provider": provider,
        "model": model,
        "modality": modality,
        "success": success,
        "latency_ms": latency_ms,
        "error_type": error_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # In-memory ring buffer
    _recent_events.append(event)
    if len(_recent_events) > _MAX_RECENT:
        _recent_events.pop(0)

    # Persist to SQLite (non-blocking, best-effort)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO generation_events
                   (run_id, provider, model, modality, success, latency_ms, error_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, provider, model, modality, 1 if success else 0,
                 latency_ms, error_type, event["created_at"]),
            )
            await db.commit()
    except Exception as e:
        logger.warning("metrics: failed to persist event to SQLite: %s", e)


async def get_metrics() -> dict:
    """Aggregate metrics for the dashboard endpoint."""
    # Provider health from last 20 events
    provider_stats: dict[str, dict] = defaultdict(lambda: {"success": 0, "fail": 0, "latency_ms": []})

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT provider, success, latency_ms FROM generation_events ORDER BY created_at DESC LIMIT 100"
            ) as cur:
                rows = await cur.fetchall()
                for row in rows:
                    p = row["provider"]
                    if row["success"]:
                        provider_stats[p]["success"] += 1
                    else:
                        provider_stats[p]["fail"] += 1
                    provider_stats[p]["latency_ms"].append(row["latency_ms"])
    except Exception:
        # Fall back to in-memory if DB not ready
        for ev in _recent_events:
            p = ev["provider"]
            if ev["success"]:
                provider_stats[p]["success"] += 1
            else:
                provider_stats[p]["fail"] += 1
            provider_stats[p]["latency_ms"].append(ev["latency_ms"])

    providers = {}
    for pname, stats in provider_stats.items():
        total = stats["success"] + stats["fail"]
        avg_latency = int(sum(stats["latency_ms"]) / len(stats["latency_ms"])) if stats["latency_ms"] else 0
        success_rate = round(stats["success"] / total * 100) if total > 0 else 0
        # Health: green ≥70%, yellow ≥30%, red <30%
        health = "green" if success_rate >= 70 else "yellow" if success_rate >= 30 else "red"
        providers[pname] = {
            "success": stats["success"],
            "fail": stats["fail"],
            "total": total,
            "success_rate_pct": success_rate,
            "avg_latency_ms": avg_latency,
            "health": health,
        }

    # Total counts
    total_gens = sum(v["total"] for v in providers.values())
    total_success = sum(v["success"] for v in providers.values())

    return {
        "total_generations": total_gens,
        "total_successful": total_success,
        "overall_success_rate_pct": round(total_success / total_gens * 100) if total_gens > 0 else 0,
        "providers": providers,
        "recent_events": list(reversed(_recent_events))[:10],
    }
