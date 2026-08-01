"""
Genblaze pipeline integration + provider cascade.

Provider cascade for image generation:
  1. GeminiImageProvider (Google) — best quality, requires Pro/billing
  2. GitHub Models (gpt-image-1) — free with any GitHub account, no card needed

The cascade tries providers in order, rotating keys on quota errors.
B2 storage via genblaze-s3 is used for both paths.
"""
import hashlib
import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Confirmed via discovery + model probe on 2026-08-01 ────────────────────
# ImagenProvider slugs (imagen-4.0-*) require account entitlement (404 for new users).
# GeminiImageProvider works with any Google AI API key — no entitlement needed.
IMAGE_PROVIDER_CLASS_NAME = "GeminiImageProvider"       # genblaze_google
VIDEO_PROVIDER_CLASS_NAME = "VeoProvider"               # genblaze_google.provider
IMAGE_MODEL_ID = "gemini-2.5-flash-image"               # confirmed via models.known()
VIDEO_MODEL_ID = "veo-3.0-generate-001"                 # confirmed via models.known()

# GitHub Models fallback
GITHUB_IMAGE_MODEL = "gpt-image-1"
GITHUB_IMAGE_ENDPOINT = "https://models.inference.ai.azure.com/images/generations"

# Pollinations.ai fallback (free, no auth, no card, always works)
POLLINATIONS_MODEL = "flux"
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


class MultiKeyGoogleProvider:
    """
    Cross-account key rotation for Google AI Pro.

    Genblaze's fallback_models retries across *models* within one account.
    This wrapper rotates across *accounts* (separate GEMINI_API_KEYs) on quota errors.
    """

    def __init__(self, api_keys: list[str], provider_cls):
        if not api_keys:
            raise ValueError("MultiKeyGoogleProvider: no API keys provided")
        self._keys = [k.strip() for k in api_keys if k.strip()]
        self._provider_cls = provider_cls
        self._idx = 0
        logger.info("MultiKeyGoogleProvider: %d keys loaded", len(self._keys))

    def get_provider(self):
        return self._provider_cls(api_key=self._keys[self._idx])

    def advance(self) -> bool:
        self._idx += 1
        if self._idx >= len(self._keys):
            logger.error("MultiKeyGoogleProvider: all %d keys exhausted", len(self._keys))
            return False
        logger.warning(
            "MultiKeyGoogleProvider: rotating to key %d/%d",
            self._idx + 1, len(self._keys),
        )
        return True

    def reset(self) -> None:
        self._idx = 0

    @property
    def current_key_index(self) -> int:
        return self._idx

    @property
    def keys_remaining(self) -> int:
        return len(self._keys) - self._idx


def load_google_keys() -> list[str]:
    raw = os.getenv("GOOGLE_API_KEYS", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        logger.warning("No GOOGLE_API_KEYS found in environment")
    return keys


def get_b2_storage():
    """Build an ObjectStorageSink pointing at the notary-media B2 bucket."""
    from genblaze_core import ObjectStorageSink, KeyStrategy
    from genblaze_s3 import S3StorageBackend
    return ObjectStorageSink(
        S3StorageBackend.for_backblaze(
            bucket=os.getenv("B2_BUCKET_NAME", "notary-media"),
            region=os.getenv("B2_REGION", "us-east-005"),
            key_id=os.getenv("B2_KEY_ID"),
            app_key=os.getenv("B2_APP_KEY"),
        ),
        key_strategy=KeyStrategy.HIERARCHICAL,
    )


def get_b2_backend():
    """Return the raw S3StorageBackend for manual uploads (GitHub path)."""
    from genblaze_s3 import S3StorageBackend
    return S3StorageBackend.for_backblaze(
        bucket=os.getenv("B2_BUCKET_NAME", "notary-media"),
        region=os.getenv("B2_REGION", "us-east-005"),
        key_id=os.getenv("B2_KEY_ID"),
        app_key=os.getenv("B2_APP_KEY"),
    )


def _is_quota_error(e: Exception) -> bool:
    """Detect quota/rate-limit errors by type name + message."""
    err_type = type(e).__name__.lower()
    err_msg = str(e).lower()
    quota_keywords = ("quota", "ratelimit", "rate_limit", "resource", "429", "exhausted")
    return any(kw in err_type for kw in quota_keywords) or \
           any(kw in err_msg for kw in ("quota", "rate limit", "429", "resource exhausted"))


# ── Path A: Google Genblaze Pipeline ─────────────────────────────────────

async def _run_google_pipeline(prompt: str, api_keys: list[str]) -> dict:
    """
    Generate image via GeminiImageProvider → Genblaze Pipeline → B2.
    Rotates across keys on quota errors.

    Returns the standard result dict on success.
    Raises RuntimeError if all keys are exhausted.
    Raises the original exception for non-quota errors.
    """
    from genblaze_core import Pipeline, Modality
    from genblaze_google import GeminiImageProvider

    storage = get_b2_storage()
    multi_key = MultiKeyGoogleProvider(api_keys, GeminiImageProvider)

    last_error = None
    while True:
        provider = multi_key.get_provider()
        try:
            run, manifest = await (
                Pipeline("notary-generate")
                .step(
                    provider,
                    model=IMAGE_MODEL_ID,
                    prompt=prompt,
                    modality=Modality.IMAGE,
                )
                .arun(sink=storage, timeout=120)
            )
            asset = run.steps[0].assets[0]
            return {
                "run_id": run.run_id,
                "asset_url": asset.url,
                "manifest_uri": manifest.manifest_uri,
                "sha256": asset.sha256,
                "provider": "google",
                "model": IMAGE_MODEL_ID,
                "has_embedded_metadata": True,
                "has_visible_label": False,
                "has_machine_readable_mark": False,
            }
        except Exception as e:
            if _is_quota_error(e):
                last_error = e
                logger.warning("Quota on key %d: %s — rotating", multi_key.current_key_index, e)
                if not multi_key.advance():
                    raise RuntimeError(f"All Google keys exhausted: {last_error}") from last_error
            else:
                raise


# ── Path B: GitHub Models + manual B2 upload ─────────────────────────────

async def _run_github_pipeline(prompt: str) -> dict:
    """
    Generate image via GitHub Models gpt-image-1, upload manually to B2.

    We don't have a Genblaze provider for GitHub Models, so we:
    1. Call the API directly (OpenAI-compatible endpoint)
    2. Upload asset + manifest JSON to B2 via genblaze-s3 backend
    3. Return the same result dict shape as the Google path

    This path is used as fallback when Google quota is exhausted.
    """
    import base64
    import httpx

    pat = os.getenv("GITHUB_PAT", "")
    if not pat:
        raise RuntimeError("GITHUB_PAT not set — cannot use GitHub Models fallback")

    logger.info("Using GitHub Models fallback (gpt-image-1)")

    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GITHUB_IMAGE_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(GITHUB_IMAGE_ENDPOINT, json=payload, headers=headers)
        resp.raise_for_status()

    b64 = resp.json()["data"][0]["b64_json"]
    image_bytes = base64.b64decode(b64)
    sha256 = hashlib.sha256(image_bytes).hexdigest()

    # Upload to B2
    run_id = str(uuid.uuid4())
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bucket = os.getenv("B2_BUCKET_NAME", "notary-media")
    region = os.getenv("B2_REGION", "us-east-005")
    tenant = "notary"

    asset_key = f"runs/{tenant}/{date_str}/{run_id}/assets/image.png"
    manifest_key = f"runs/{tenant}/{date_str}/{run_id}/manifest.json"
    base_url = f"https://{bucket}.s3.{region}.backblazeb2.com"

    backend = get_b2_backend()
    asset_url = backend.put(asset_key, io.BytesIO(image_bytes), content_type="image/png")

    manifest_data = {
        "run_id": run_id,
        "provider": "github-models",
        "model": GITHUB_IMAGE_MODEL,
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

    logger.info("GitHub path: asset=%s manifest=%s", asset_url, manifest_uri)
    return {
        "run_id": run_id,
        "asset_url": asset_url,
        "manifest_uri": manifest_uri,
        "sha256": sha256,
        "provider": "github-models",
        "model": GITHUB_IMAGE_MODEL,
        "has_embedded_metadata": False,
        "has_visible_label": False,
        "has_machine_readable_mark": False,
    }


# ── Path C: Pollinations.ai (free, no auth, always works) ────────────────

async def _run_pollinations_pipeline(prompt: str) -> dict:
    """Generate image via Pollinations.ai FLUX (free, no auth, no card)."""
    from urllib.parse import quote

    logger.info("Using Pollinations.ai fallback (%s)", POLLINATIONS_MODEL)
    url = f"{POLLINATIONS_BASE}/{quote(prompt)}?width=1024&height=1024&nologo=true"

    async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    image_bytes = resp.content
    content_type = resp.headers.get("content-type", "image/jpeg")
    ext = "png" if "png" in content_type else "jpeg"
    sha256 = hashlib.sha256(image_bytes).hexdigest()

    run_id = str(uuid.uuid4())
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    asset_key = f"runs/notary/{date_str}/{run_id}/assets/image.{ext}"
    manifest_key = f"runs/notary/{date_str}/{run_id}/manifest.json"

    backend = get_b2_backend()
    asset_url = backend.put(asset_key, io.BytesIO(image_bytes), content_type=content_type)

    manifest_data = {
        "run_id": run_id, "provider": "pollinations", "model": POLLINATIONS_MODEL,
        "prompt": prompt, "modality": "image",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": [{"key": asset_key, "url": asset_url, "sha256": sha256, "mime_type": content_type}],
        "has_embedded_metadata": False, "has_visible_label": False, "has_machine_readable_mark": False,
    }
    manifest_uri = backend.put(
        manifest_key, io.BytesIO(json.dumps(manifest_data, indent=2).encode()),
        content_type="application/json",
    )

    return {
        "run_id": run_id, "asset_url": asset_url, "manifest_uri": manifest_uri,
        "sha256": sha256, "provider": "pollinations", "model": POLLINATIONS_MODEL,
        "has_embedded_metadata": False, "has_visible_label": False, "has_machine_readable_mark": False,
    }


# ── Public API: cascade ───────────────────────────────────────────────────

async def run_image_pipeline(prompt: str, api_keys: list[str] | None = None) -> dict:
    """
    Generate an image with provider cascade:
      1. Google GeminiImageProvider (Genblaze Pipeline → B2)  [if keys + quota]
      2. GitHub Models gpt-image-1 (direct → B2)              [if GITHUB_PAT]
      3. Pollinations.ai FLUX (direct → B2)                    [always available]
    """
    keys = api_keys or load_google_keys()

    if keys:
        try:
            logger.info("Trying Google path (%d keys)", len(keys))
            return await _run_google_pipeline(prompt, keys)
        except Exception as e:
            if _is_quota_error(e) or "exhausted" in str(e).lower():
                logger.warning("Google path failed: %s — trying next provider", e)
            else:
                logger.warning("Google error (%s: %s) — trying next provider", type(e).__name__, e)

    if os.getenv("GITHUB_PAT"):
        try:
            logger.info("Trying GitHub Models path")
            return await _run_github_pipeline(prompt)
        except Exception as e:
            logger.warning("GitHub Models failed: %s — trying Pollinations", e)

    logger.info("Using Pollinations.ai (always available)")
    return await _run_pollinations_pipeline(prompt)


async def run_video_pipeline(prompt: str, api_keys: list[str] | None = None) -> dict:
    """
    Generate a video via Veo → B2.
    TODO Day 2.
    """
    raise NotImplementedError("Wire on Day 2 after image path is confirmed")


async def run_remix_pipeline(
    parent_run_id: str,
    parent_manifest_uri: str,
    prompt: str,
    modality: str,
    api_keys: list[str] | None = None,
) -> dict:
    """
    Regenerate from an existing asset via from_result() — FR-8 (S1).
    TODO Day 2.
    """
    raise NotImplementedError("Wire on Day 2 after base pipeline is confirmed")
