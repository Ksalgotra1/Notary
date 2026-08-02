"""Rebuild the disposable SQLite index from canonical Genblaze manifests in B2."""
import asyncio
import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("rebuild_cache")


async def main() -> int:
    from cache import get_db, init_db, insert_asset
    from genblaze_core.models.manifest import parse_manifest
    from pipeline import get_b2_backend

    await init_db()
    backend = get_b2_backend()
    keys, token = [], None
    while True:
        page = backend.list(prefix="notary/runs/", continuation_token=token)
        keys.extend(entry.key for entry in page.entries if entry.key.endswith("manifest.json"))
        token = page.next_token
        if not token:
            break

    rebuilt = 0
    async for db in get_db():
        for key in keys:
            try:
                manifest = parse_manifest(json.loads(backend.get(key).decode("utf-8")))
                if not manifest.verify_hash():
                    logger.warning("Skipping manifest with invalid canonical hash: %s", key)
                    continue
                run = manifest.run
                assets = [asset for step in run.steps for asset in step.assets]
                if not assets:
                    continue
                asset = assets[-1]
                step = next(step for step in reversed(run.steps) if step.assets)
                metadata = run.metadata or {}
                # M0 is an internal source node. M1 is the public artifact
                # whose bytes include M0 and whose output SHA is authoritative.
                is_receipt = bool(metadata.get("source_manifest_uri"))
                is_source = bool(metadata.get("embedded_receipt_run_id"))
                await insert_asset(db, {
                    "run_id": run.run_id,
                    "parent_run_id": run.parent_run_id,
                    "provider": metadata.get("generation_provider", step.provider),
                    "model": metadata.get("generation_model", step.model),
                    "modality": step.modality.value,
                    "prompt": step.prompt or "",
                    "b2_asset_url": asset.url,
                    "b2_manifest_url": manifest.manifest_uri or backend.get_durable_url(key),
                    "sha256": asset.sha256,
                    "created_at": run.created_at.isoformat(),
                    "has_embedded_metadata": int(is_receipt),
                    "has_visible_label": 0,
                    "has_machine_readable_mark": int(is_receipt),
                    "has_audio_disclosure": 0,
                    "is_distributed": int(not is_source),
                })
                rebuilt += 1
            except Exception as exc:
                logger.warning("Unable to index %s: %s", key, exc)
    return rebuilt


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Indexed {asyncio.run(main())} Genblaze runs")
