"""
Day 1 spike — proves the full path works end to end:
  prompt → Imagen (via genblaze_google) → B2 (via genblaze_s3) → print URL + hash

NOT production code. Throwaway validation script.
Run AFTER filling in the TODO items from discovery.py output.

Usage:
    cd backend/
    source .venv/bin/activate
    python spike_imagen.py
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# ── Confirmed via discovery + model probe on 2026-08-01 ──────────────────
# ImagenProvider models require entitlement (404 for new users).
# GeminiImageProvider works with any Google AI API key.
PROVIDER_CLASS_NAME = "GeminiImageProvider"     # genblaze_google
MODEL_ID = "gemini-2.5-flash-image"             # confirmed via models.known()
# ──────────────────────────────────────────────────────────────────────────


async def main():
    # 1. Import SDK (will fail if not installed — run pip install first)
    try:
        from genblaze_core import Pipeline, Modality, ObjectStorageSink, KeyStrategy
        from genblaze_s3 import S3StorageBackend
        import genblaze_google as gg
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        print("  Run: pip install genblaze-core genblaze-s3 genblaze-google")
        return

    # 2. Get provider class
    ProviderCls = getattr(gg, PROVIDER_CLASS_NAME, None)
    if ProviderCls is None:
        print(f"✗ Provider class '{PROVIDER_CLASS_NAME}' not found in genblaze_google")
        print(f"  Available: {[x for x in dir(gg) if not x.startswith('_')]}")
        return

    # 3. Connect to B2
    b2_key_id = os.getenv("B2_KEY_ID")
    b2_app_key = os.getenv("B2_APP_KEY")
    b2_bucket = os.getenv("B2_BUCKET_NAME", "notary-media")

    if not b2_key_id or not b2_app_key:
        print("✗ B2_KEY_ID or B2_APP_KEY not set in .env")
        return

    storage = ObjectStorageSink(
        S3StorageBackend.for_backblaze(
            bucket=b2_bucket,
            region="us-east-005",
            key_id=b2_key_id,
            app_key=b2_app_key,
        ),
        key_strategy=KeyStrategy.HIERARCHICAL,
    )

    # 4. Get first Google API key
    api_keys = [k.strip() for k in os.getenv("GOOGLE_API_KEYS", "").split(",") if k.strip()]
    if not api_keys:
        print("✗ GOOGLE_API_KEYS not set in .env")
        return

    provider = ProviderCls(api_key=api_keys[0])
    print(f"✓ Provider: {PROVIDER_CLASS_NAME} (key index 0)")
    print(f"✓ Model: {MODEL_ID}")
    print(f"✓ B2 bucket: {b2_bucket}")
    print(f"\nRunning pipeline...")

    # 5. Run the pipeline
    run, manifest = await (
        Pipeline("notary-spike")
        .step(
            provider,
            model=MODEL_ID,
            prompt="A golden notary seal on a dark marble desk, photorealistic, dramatic lighting",
            modality=Modality.IMAGE,
        )
        .arun(sink=storage, timeout=120)
    )

    # 6. Print results
    asset = run.steps[0].assets[0]
    print(f"\n{'=' * 60}")
    print(f"✓ Asset URL:      {asset.url}")
    print(f"✓ SHA-256:        {asset.sha256}")
    print(f"✓ Manifest URI:   {manifest.manifest_uri}")
    print(f"✓ Verified:       {manifest.verify()}")
    print(f"✓ Run ID:         {run.run_id}")
    print(f"{'=' * 60}")
    print("\nA4 DONE — paste these into meta.md and share with Person B.")


if __name__ == "__main__":
    asyncio.run(main())
