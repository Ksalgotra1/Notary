"""
Day 1 spike — GitHub Models path.

Proves: GitHub Models → image bytes → B2 upload → URL + SHA-256 printed.
Run this while Google quota is unavailable.

Usage:
    cd backend/
    source .venv/bin/activate
    python spike_github.py
"""
import asyncio
import hashlib
import os
import uuid
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()


async def main():
    pat = os.getenv("GITHUB_PAT", "")
    if not pat:
        print("✗ GITHUB_PAT not set in .env")
        return

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
    tenant = "demo"

    print(f"✓ GitHub PAT: {pat[:10]}...{pat[-4:]}")
    print(f"✓ Run ID: {run_id}")
    print(f"✓ B2 bucket: {b2_bucket} ({b2_region})")
    print(f"\nStep 1: Generating image via GitHub Models (gpt-image-1)...")

    # 1. Generate image via GitHub Models
    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://models.inference.ai.azure.com/images/generations",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"✗ GitHub Models error {e.response.status_code}: {e.response.text[:300]}")
        return

    import base64
    data = resp.json()
    b64 = data["data"][0].get("b64_json")
    if not b64:
        print(f"✗ No image data in response: {data}")
        return

    image_bytes = base64.b64decode(b64)
    sha256 = hashlib.sha256(image_bytes).hexdigest()
    print(f"✓ Image generated: {len(image_bytes):,} bytes")
    print(f"✓ SHA-256: {sha256}")

    # 2. Upload to B2 via genblaze-s3 ObjectStorageSink
    print(f"\nStep 2: Uploading to B2...")
    from genblaze_core import ObjectStorageSink, KeyStrategy
    from genblaze_s3 import S3StorageBackend

    backend = S3StorageBackend.for_backblaze(
        bucket=b2_bucket,
        region=b2_region,
        key_id=b2_key_id,
        app_key=b2_app_key,
    )

    asset_key = f"runs/{tenant}/{date_str}/{run_id}/assets/image.png"
    manifest_key = f"runs/{tenant}/{date_str}/{run_id}/manifest.json"

    # Upload asset
    import io
    backend.put_object(key=asset_key, body=io.BytesIO(image_bytes), content_type="image/png")
    asset_url = f"https://{b2_bucket}.s3.{b2_region}.backblazeb2.com/{asset_key}"
    print(f"✓ Asset uploaded: {asset_url}")

    # 3. Build + upload manifest
    import json
    manifest = {
        "run_id": run_id,
        "provider": "github-models",
        "model": "gpt-image-1",
        "prompt": prompt,
        "modality": "image",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": [
            {
                "key": asset_key,
                "url": asset_url,
                "sha256": sha256,
                "mime_type": "image/png",
                "size_bytes": len(image_bytes),
            }
        ],
        "has_embedded_metadata": False,
        "has_visible_label": False,
        "has_machine_readable_mark": False,
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode()
    backend.put_object(key=manifest_key, body=io.BytesIO(manifest_bytes), content_type="application/json")
    manifest_url = f"https://{b2_bucket}.s3.{b2_region}.backblazeb2.com/{manifest_key}"
    print(f"✓ Manifest uploaded: {manifest_url}")

    print(f"\n{'=' * 60}")
    print(f"✓ Run ID:       {run_id}")
    print(f"✓ Asset URL:    {asset_url}")
    print(f"✓ Manifest URL: {manifest_url}")
    print(f"✓ SHA-256:      {sha256}")
    print(f"✓ Provider:     github-models / gpt-image-1")
    print(f"{'=' * 60}")
    print("\nA4 DONE (GitHub path). Paste results into meta.md.")


if __name__ == "__main__":
    asyncio.run(main())
