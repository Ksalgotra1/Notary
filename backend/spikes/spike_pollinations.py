"""
Day 1 spike — Pollinations.ai path (FINAL — no auth, no card, always works).

Proves: Pollinations.ai → image bytes → B2 upload → URL + SHA-256 printed.

Usage:
    cd backend/
    source .venv/bin/activate
    python spike_pollinations.py
"""
import asyncio
import hashlib
import io
import json
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

load_dotenv()

POLLINATIONS_MODEL = "flux"
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


async def main():
    b2_key_id = os.getenv("B2_KEY_ID")
    b2_app_key = os.getenv("B2_APP_KEY")
    b2_bucket = os.getenv("B2_BUCKET_NAME", "notary-media")
    b2_region = os.getenv("B2_REGION", "us-east-005")

    if not b2_key_id or not b2_app_key:
        print("✗ B2 credentials not set in .env")
        return

    prompt = "A golden notary seal on a dark marble desk, photorealistic, dramatic lighting"
    run_id = str(uuid.uuid4())
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"✓ Run ID: {run_id}")
    print(f"✓ B2 bucket: {b2_bucket} ({b2_region})")
    print(f"\nStep 1: Generating image via Pollinations.ai...")

    # 1. Generate image (GET request, no auth needed)
    url = f"{POLLINATIONS_BASE}/{quote(prompt)}?width=1024&height=1024&nologo=true&seed={hash(run_id) % 100000}"

    async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    image_bytes = resp.content
    content_type = resp.headers.get("content-type", "image/jpeg")
    ext = "png" if "png" in content_type else "jpeg"
    sha256 = hashlib.sha256(image_bytes).hexdigest()

    print(f"✓ Image generated: {len(image_bytes):,} bytes ({content_type})")
    print(f"✓ SHA-256: {sha256}")

    # 2. Upload to B2
    print(f"\nStep 2: Uploading to B2...")
    from genblaze_s3 import S3StorageBackend

    backend = S3StorageBackend.for_backblaze(
        bucket=b2_bucket,
        region=b2_region,
        key_id=b2_key_id,
        app_key=b2_app_key,
    )

    tenant = "notary"
    asset_key = f"runs/{tenant}/{date_str}/{run_id}/assets/image.{ext}"
    manifest_key = f"runs/{tenant}/{date_str}/{run_id}/manifest.json"

    asset_url = backend.put(asset_key, io.BytesIO(image_bytes), content_type=content_type)
    print(f"✓ Asset uploaded: {asset_url}")

    # 3. Upload manifest
    manifest_data = {
        "run_id": run_id,
        "provider": "pollinations",
        "model": POLLINATIONS_MODEL,
        "prompt": prompt,
        "modality": "image",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": [
            {
                "key": asset_key,
                "url": asset_url,
                "sha256": sha256,
                "mime_type": content_type,
                "size_bytes": len(image_bytes),
            }
        ],
        "has_embedded_metadata": False,
        "has_visible_label": False,
        "has_machine_readable_mark": False,
    }
    manifest_uri = backend.put(
        manifest_key,
        io.BytesIO(json.dumps(manifest_data, indent=2).encode()),
        content_type="application/json",
    )
    print(f"✓ Manifest uploaded: {manifest_uri}")

    print(f"\n{'=' * 60}")
    print(f"✓ Run ID:       {run_id}")
    print(f"✓ Asset URL:    {asset_url}")
    print(f"✓ Manifest URL: {manifest_uri}")
    print(f"✓ SHA-256:      {sha256}")
    print(f"✓ Provider:     pollinations / {POLLINATIONS_MODEL}")
    print(f"{'=' * 60}")
    print("\n🎉 A4 DONE — Real AI image generated and stored in B2 with provenance!")


if __name__ == "__main__":
    asyncio.run(main())
