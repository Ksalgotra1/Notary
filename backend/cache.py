"""
Disposable SQLite cache (NFR-9).
Source of truth is always B2. This is a read-index for fast Library queries.
Losing this costs query speed, not data — rebuild with ``backend/rebuild_cache.py``.
"""
import aiosqlite
import os
from typing import AsyncGenerator

DB_PATH = os.getenv("CACHE_DB_PATH", "notary_cache.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    run_id TEXT PRIMARY KEY,
    parent_run_id TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    modality TEXT NOT NULL,
    prompt TEXT NOT NULL,
    b2_asset_url TEXT NOT NULL,
    b2_manifest_url TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_verified_at TEXT,
    verify_status TEXT,
    -- Compliance tracking (USP #1)
    has_embedded_metadata INTEGER DEFAULT 0,
    has_visible_label INTEGER DEFAULT 0,
    has_machine_readable_mark INTEGER DEFAULT 0,
    has_audio_disclosure INTEGER DEFAULT 0,
    compliance_evaluated_at TEXT,
    india_compliant INTEGER,
    eu_compliant INTEGER,
    is_distributed INTEGER DEFAULT 1,
    policy_profile TEXT,
    prompt_audit_json TEXT,
    visual_audit_json TEXT,
    policy_manifest_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_assets_created_at ON assets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assets_modality ON assets(modality);
CREATE INDEX IF NOT EXISTS idx_assets_provider ON assets(provider);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        # Existing local caches predate policy audit and internal M0 records.
        for column, definition in (
            ("is_distributed", "INTEGER DEFAULT 1"),
            ("policy_profile", "TEXT"),
            ("prompt_audit_json", "TEXT"),
            ("visual_audit_json", "TEXT"),
            ("policy_manifest_url", "TEXT"),
        ):
            try:
                await db.execute(f"ALTER TABLE assets ADD COLUMN {column} {definition}")
            except Exception as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        await db.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def insert_asset(db: aiosqlite.Connection, asset: dict) -> None:
    await db.execute(
        """
        INSERT OR REPLACE INTO assets (
            run_id, parent_run_id, provider, model, modality, prompt,
            b2_asset_url, b2_manifest_url, sha256, created_at,
            has_embedded_metadata, has_visible_label,
            has_machine_readable_mark, has_audio_disclosure, is_distributed
        ) VALUES (
            :run_id, :parent_run_id, :provider, :model, :modality, :prompt,
            :b2_asset_url, :b2_manifest_url, :sha256, :created_at,
            :has_embedded_metadata, :has_visible_label,
            :has_machine_readable_mark, :has_audio_disclosure, :is_distributed
        )
        """,
        asset,
    )
    await db.commit()


async def get_asset(db: aiosqlite.Connection, run_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM assets WHERE run_id = ?", (run_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_assets(
    db: aiosqlite.Connection,
    limit: int = 20,
    provider: str | None = None,
    modality: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM assets WHERE is_distributed = 1"
    params: list = []
    if provider:
        query += " AND provider = ?"
        params.append(provider)
    if modality:
        query += " AND modality = ?"
        params.append(modality)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def find_cached_generation(
    db: aiosqlite.Connection,
    prompt: str,
    modality: str,
    max_age_hours: float | None = None,
) -> dict | None:
    """
    Return a recent generation with an exact prompt+modality match.
    Only returns assets that are distributed (is_distributed=1).
    max_age_hours defaults to CACHE_MAX_AGE_HOURS env var, or 4h.
    """
    from datetime import datetime, timezone, timedelta

    if max_age_hours is None:
        max_age_hours = float(os.getenv("CACHE_MAX_AGE_HOURS", "4"))
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    async with db.execute(
        """SELECT * FROM assets
           WHERE prompt = ? AND modality = ? AND is_distributed = 1
             AND created_at >= ?
           ORDER BY created_at DESC LIMIT 1""",
        (prompt, modality, cutoff),
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_verify_status(
    db: aiosqlite.Connection,
    run_id: str,
    status: str,
    verified_at: str,
) -> None:
    await db.execute(
        "UPDATE assets SET verify_status = ?, last_verified_at = ? WHERE run_id = ?",
        (status, verified_at, run_id),
    )
    await db.commit()


async def update_compliance(
    db: aiosqlite.Connection,
    run_id: str,
    india_compliant: bool,
    eu_compliant: bool,
    evaluated_at: str,
) -> None:
    await db.execute(
        """UPDATE assets
           SET india_compliant = ?, eu_compliant = ?, compliance_evaluated_at = ?
           WHERE run_id = ?""",
        (int(india_compliant), int(eu_compliant), evaluated_at, run_id),
    )
    await db.commit()


async def update_policy_audit(
    db: aiosqlite.Connection,
    run_id: str,
    *,
    profile: str,
    prompt_audit_json: str,
    visual_audit_json: str | None,
    policy_manifest_url: str | None,
) -> None:
    await db.execute(
        """UPDATE assets
           SET policy_profile = ?, prompt_audit_json = ?, visual_audit_json = ?, policy_manifest_url = ?
           WHERE run_id = ?""",
        (profile, prompt_audit_json, visual_audit_json, policy_manifest_url, run_id),
    )
    await db.commit()


async def get_lineage(db: aiosqlite.Connection, run_id: str) -> dict:
    """
    Walk the parent_run_id chain up to the root AND down to all children,
    returning the provenance DAG as a list of nodes and edges.
    Internal nodes (is_distributed=0) are filtered out, and edges bypass them.
    """
    raw_nodes = {}
    parent_map = {}

    # Walk UP to root
    current = run_id
    while current:
        if current in raw_nodes:
            break
        async with db.execute("SELECT * FROM assets WHERE run_id = ?", (current,)) as cur:
            row = await cur.fetchone()
            if not row:
                break
            row = dict(row)
            raw_nodes[current] = row
            parent = row.get("parent_run_id")
            if parent:
                parent_map[current] = parent
            current = parent

    # Walk DOWN: find all descendants
    queue = [run_id]
    while queue:
        parent_id = queue.pop(0)
        async with db.execute(
            "SELECT * FROM assets WHERE parent_run_id = ?", (parent_id,)
        ) as cur:
            children = await cur.fetchall()
            for child in children:
                child = dict(child)
                cid = child["run_id"]
                if cid not in raw_nodes:
                    raw_nodes[cid] = child
                    parent_map[cid] = parent_id
                    queue.append(cid)

    nodes = {}
    edges = []

    def get_nearest_distributed_ancestor(n_id):
        curr = parent_map.get(n_id)
        while curr:
            if curr in raw_nodes and raw_nodes[curr].get("is_distributed", 1):
                return curr
            curr = parent_map.get(curr)
        return None

    for nid, row in raw_nodes.items():
        if row.get("is_distributed", 1):
            nodes[nid] = {
                "run_id": nid,
                "prompt": row["prompt"],
                "provider": row["provider"],
                "model": row["model"],
                "modality": row["modality"],
                "created_at": row["created_at"],
                "verify_status": row["verify_status"],
                "b2_asset_url": row["b2_asset_url"],
            }
            ancestor = get_nearest_distributed_ancestor(nid)
            if ancestor:
                edges.append({"source": ancestor, "target": nid})

    # Find root (node with no incoming edge)
    targets = {e["target"] for e in edges}
    root = None
    for nid in nodes:
        if nid not in targets:
            root = nid
            break

    return {
        "root": root or run_id,
        "nodes": list(nodes.values()),
        "edges": edges,
        "total_nodes": len(nodes),
    }
