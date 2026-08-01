"""
Cache rebuild script for Notary (FR-9).

Rebuilds notary_cache.sqlite by scanning all manifest.json files stored
in the Backblaze B2 notary-media bucket under runs/.

Usage:
    cd backend/
    source .venv/bin/activate
    python rebuild_cache.py
"""
import asyncio
import json
import logging
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rebuild_cache")

DB_PATH = os.getenv("CACHE_DB_PATH", "notary_cache.sqlite")


def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            run_id TEXT PRIMARY KEY,
            parent_run_id TEXT,
            provider TEXT,
            model TEXT,
            modality TEXT,
            prompt TEXT,
            b2_asset_url TEXT,
            b2_manifest_url TEXT,
            sha256 TEXT,
            created_at TEXT,
            last_verified_at TEXT,
            verify_status TEXT,
            has_embedded_metadata INTEGER DEFAULT 0,
            has_visible_label INTEGER DEFAULT 0,
            has_machine_readable_mark INTEGER DEFAULT 0,
            has_audio_disclosure INTEGER DEFAULT 0,
            compliance_evaluated_at TEXT,
            india_compliant INTEGER,
            eu_compliant INTEGER
        )
    """
    )
    conn.commit()
    conn.close()


def bulk_upsert(manifests: list[dict], db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    count = 0
    for m in manifests:
        run_id = m.get("run_id")
        if not run_id:
            continue

        assets = m.get("assets", [])
        first_asset = assets[0] if assets else {}

        cur.execute(
            """
            INSERT INTO assets (
                run_id, parent_run_id, provider, model, modality, prompt,
                b2_asset_url, b2_manifest_url, sha256, created_at,
                has_embedded_metadata, has_visible_label, has_machine_readable_mark
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                provider=excluded.provider,
                model=excluded.model,
                b2_asset_url=excluded.b2_asset_url,
                sha256=excluded.sha256
        """,
            (
                run_id,
                m.get("parent_run_id"),
                m.get("provider", "unknown"),
                m.get("model", "unknown"),
                m.get("modality", "image"),
                m.get("prompt", ""),
                first_asset.get("url", ""),
                m.get("manifest_uri", ""),
                first_asset.get("sha256", ""),
                m.get("created_at", ""),
                1 if m.get("has_embedded_metadata") else 0,
                1 if m.get("has_visible_label") else 0,
                1 if m.get("has_machine_readable_mark") else 0,
            ),
        )
        count += 1

    conn.commit()
    conn.close()
    return count


async def main():
    logger.info("Initializing DB schema at %s...", DB_PATH)
    init_db(DB_PATH)

    b2_key_id = os.getenv("B2_KEY_ID")
    b2_app_key = os.getenv("B2_APP_KEY")
    b2_bucket = os.getenv("B2_BUCKET_NAME", "notary-media")
    b2_region = os.getenv("B2_REGION", "us-east-005")

    if not b2_key_id or not b2_app_key:
        logger.error("B2 credentials not configured in .env")
        return

    logger.info("Connecting to Backblaze B2 bucket '%s' (%s)...", b2_bucket, b2_region)
    from genblaze_s3 import S3StorageBackend

    backend = S3StorageBackend.for_backblaze(
        bucket=b2_bucket,
        region=b2_region,
        key_id=b2_key_id,
        app_key=b2_app_key,
    )

    logger.info("Scanning B2 bucket for manifests under 'runs/'...")
    page = backend.list(prefix="runs/")
    
    entries = getattr(page, "entries", [])
    keys = [e.key if hasattr(e, "key") else str(e) for e in entries]

    manifest_keys = [str(k) for k in keys if str(k).endswith("manifest.json")]
    logger.info("Found %d manifest(s) in B2", len(manifest_keys))

    manifests = []
    for key in manifest_keys:
        try:
            raw_bytes = backend.get(key)
            data = json.loads(raw_bytes.decode())
            manifests.append(data)
            logger.info("  ✓ Loaded manifest: %s", key)
        except Exception as e:
            logger.warning("  ✗ Failed to load manifest %s: %s", key, e)

    inserted = bulk_upsert(manifests, DB_PATH)
    logger.info("🎉 Cache rebuild complete! Upserted %d record(s) into SQLite.", inserted)


if __name__ == "__main__":
    asyncio.run(main())
