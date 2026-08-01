"""
Spike: Test NVIDIA NIM Image Provider (NvidiaImageProvider).

Proves:
  1. NvidiaImageProvider generates image using NVIDIA_API_KEY from env.
  2. Primary model: black-forest-labs/flux.1-schnell
  3. Uploads generated asset + manifest to Backblaze B2.

Usage:
    cd backend/
    source .venv/bin/activate
    python spikes/spike_nvidia.py
"""
import asyncio
import hashlib
import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spike_nvidia")


async def main():
    nv_key = os.getenv("NVIDIA_API_KEY", "")
    if not nv_key:
        logger.error("✗ NVIDIA_API_KEY not found in .env")
        return

    logger.info("✓ NVIDIA_API_KEY configured: %s...%s", nv_key[:8], nv_key[-4:])

    b2_key_id = os.getenv("B2_KEY_ID")
    b2_app_key = os.getenv("B2_APP_KEY")
    b2_bucket = os.getenv("B2_BUCKET_NAME", "notary-media")
    b2_region = os.getenv("B2_REGION", "us-east-005")

    from genblaze_nvidia import NvidiaImageProvider
    from genblaze_core import Modality
    from genblaze_core.models.step import Step
    from genblaze_s3 import S3StorageBackend

    prompt = "A golden notary seal on dark marble, high detail"
    model_name = "black-forest-labs/flux-1-schnell"

    logger.info("Step 1: Generating image via NVIDIA NIM (%s)...", model_name)
    provider = NvidiaImageProvider()
    step = Step(
        provider="nvidia",
        model=model_name,
        prompt=prompt,
        modality=Modality.IMAGE,
    )

    try:
        res_step = provider.invoke(step)
        if not res_step.assets:
            logger.error("✗ No assets returned from NVIDIA NIM")
            return

        asset = res_step.assets[0]
        if hasattr(asset, "data") and asset.data:
            image_bytes = asset.data
        elif hasattr(asset, "path") and asset.path:
            with open(asset.path, "rb") as f:
                image_bytes = f.read()
        else:
            logger.error("✗ Asset contains no data or path: %s", asset)
            return

        sha256 = hashlib.sha256(image_bytes).hexdigest()
        logger.info("✓ Image generated: %d bytes, SHA-256: %s", len(image_bytes), sha256)

        logger.info("\nStep 2: Uploading asset + manifest to B2...")
        run_id = str(uuid.uuid4())
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        backend = S3StorageBackend.for_backblaze(
            bucket=b2_bucket,
            region=b2_region,
            key_id=b2_key_id,
            app_key=b2_app_key,
        )

        asset_key = f"runs/notary/{date_str}/{run_id}/assets/image.png"
        manifest_key = f"runs/notary/{date_str}/{run_id}/manifest.json"

        asset_url = backend.put(asset_key, io.BytesIO(image_bytes), content_type="image/png")
        manifest_data = {
            "run_id": run_id,
            "provider": "nvidia",
            "model": model_name,
            "prompt": prompt,
            "modality": "image",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "assets": [{"key": asset_key, "url": asset_url, "sha256": sha256, "mime_type": "image/png"}],
            "has_embedded_metadata": False,
            "has_visible_label": False,
            "has_machine_readable_mark": False,
        }
        manifest_uri = backend.put(
            manifest_key,
            io.BytesIO(json.dumps(manifest_data, indent=2).encode()),
            content_type="application/json",
        )

        logger.info("=" * 60)
        logger.info("✓ Run ID:       %s", run_id)
        logger.info("✓ Asset URL:    %s", asset_url)
        logger.info("✓ Manifest URL: %s", manifest_uri)
        logger.info("✓ SHA-256:      %s", sha256)
        logger.info("✓ Provider:     nvidia / %s", model_name)
        logger.info("=" * 60)
        logger.info("🎉 NVIDIA NIM Spike PASSED!")
    except Exception as e:
        logger.error("✗ NVIDIA NIM spike failed: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
