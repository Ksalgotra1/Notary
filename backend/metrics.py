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
    provider_stats: dict[str, dict] = defaultdict(lambda: {"success": 0, "fail": 0, "latency_ms": []})

    asset_count = 0
    events_total = 0
    events_success = 0
    recent_from_db: list[dict] = []

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            # 1. Provider health from generation_events (exclude stale "unknown")
            async with db.execute(
                "SELECT provider, success, latency_ms FROM generation_events "
                "WHERE provider != 'unknown' ORDER BY created_at DESC LIMIT 100"
            ) as cur:
                rows = await cur.fetchall()
                for row in rows:
                    p = row["provider"]
                    if row["success"]:
                        provider_stats[p]["success"] += 1
                    else:
                        provider_stats[p]["fail"] += 1
                    provider_stats[p]["latency_ms"].append(row["latency_ms"])

            # 2. Total event counts
            async with db.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes "
                "FROM generation_events"
            ) as cur:
                row = await cur.fetchone()
                events_total = row["total"] or 0
                events_success = row["successes"] or 0

            # 3. Ground-truth: count assets (matches library exactly)
            async with db.execute("SELECT COUNT(*) as cnt FROM assets WHERE is_distributed = 1") as cur:
                row = await cur.fetchone()
                asset_count = row["cnt"] or 0

            # 4. Recent events for live feed
            async with db.execute(
                "SELECT run_id, provider, model, modality, success, latency_ms, created_at "
                "FROM generation_events ORDER BY created_at DESC LIMIT 10"
            ) as cur:
                rows = await cur.fetchall()
                for row in rows:
                    recent_from_db.append({
                        "run_id": row["run_id"],
                        "provider": row["provider"],
                        "model": row["model"],
                        "modality": row["modality"],
                        "success": bool(row["success"]),
                        "latency_ms": row["latency_ms"],
                        "created_at": row["created_at"],
                    })
    except Exception:
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
        health = "green" if success_rate >= 70 else "yellow" if success_rate >= 30 else "red"
        providers[pname] = {
            "success": stats["success"],
            "fail": stats["fail"],
            "total": total,
            "success_rate_pct": success_rate,
            "avg_latency_ms": avg_latency,
            "health": health,
        }

    # ── Source of truth: assets table ─────────────────────────────────
    # Library page shows COUNT(*) FROM assets.
    # Dashboard MUST show the exact same number — both read the same table.
    # Every row in assets = 1 successful generation that completed fully.
    # Failed attempts never get written to assets, so total_failed comes
    # from generation_events where success=0.
    total_gens    = asset_count
    total_success = asset_count
    total_failed  = max(0, events_total - events_success)

    recent = recent_from_db if recent_from_db else list(reversed(_recent_events))[:10]

    return {
        "total_generations": total_gens,
        "total_successful": total_success,
        "total_failed": total_failed,
        "overall_success_rate_pct": 100 if total_gens > 0 else 0,
        "providers": providers,
        "recent_events": recent,
    }

