"""
Genblaze pipeline integration + provider cascade.

Provider cascade for image generation:
  1. GeminiImageProvider (Google) — best quality, requires Pro/billing
  2. NvidiaImageProvider (NVIDIA NIM) — high quality, fast (FLUX.1-schnell)
  3. Pollinations.ai (FLUX) — free, zero-auth, final fallback

The cascade tries providers in order, rotating keys on quota errors.
B2 storage via genblaze-s3 is used for all paths.
"""
import hashlib
import hmac
import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import httpx

logger = logging.getLogger(__name__)

# ── Confirmed via discovery + model probe ─────────────────────────────────
IMAGE_PROVIDER_CLASS_NAME = "GeminiImageProvider"       # genblaze_google
VIDEO_PROVIDER_CLASS_NAME = "VeoProvider"               # genblaze_google
IMAGE_MODEL_ID = "gemini-2.5-flash-image"               # confirmed via models.known()
VIDEO_MODEL_ID = "veo-3.0-generate-001"                 # confirmed via models.known()

# NVIDIA NIM fallback models
NVIDIA_IMAGE_MODEL_PRIMARY = "black-forest-labs/flux-1-schnell"
NVIDIA_IMAGE_MODEL_SECONDARY = "stabilityai/stable-diffusion-3-5-large"

# Pollinations.ai fallback (free, no auth, no card, always works)
POLLINATIONS_MODEL = "flux"
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
LOCAL_GENERATED_DIR = Path(__file__).resolve().parent / "generated"

# ── Manifest signing ─────────────────────────────────────────────────────────
# Server-side HMAC secret — set MANIFEST_SIGNING_SECRET in .env for production.
# Without this, anyone with B2 write access could forge a manifest.
MANIFEST_SIGNING_SECRET = os.getenv("MANIFEST_SIGNING_SECRET", "notary-dev-secret-change-in-prod")


def sign_manifest(manifest_data: dict) -> dict:
    """
    Add an HMAC-SHA256 signature to a manifest dict.
    The signature covers all fields except _signature itself,
    computed over the JSON body sorted by key for determinism.
    """
    # Strip any existing signature before signing
    payload = {k: v for k, v in manifest_data.items() if k != "_signature"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(MANIFEST_SIGNING_SECRET.encode(), canonical, hashlib.sha256).hexdigest()
    return {**manifest_data, "_signature": sig}


def verify_manifest_signature(manifest_data: dict) -> bool:
    """
    Verify the HMAC-SHA256 signature on a manifest.
    Returns True if signature is valid, False otherwise.
    """
    expected_sig = manifest_data.get("_signature")
    if not expected_sig:
        return False
    payload = {k: v for k, v in manifest_data.items() if k != "_signature"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    actual_sig = hmac.new(MANIFEST_SIGNING_SECRET.encode(), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, actual_sig)



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
    # NOTE: for_backblaze takes bucket as first positional arg, rest as kwargs
    backend = S3StorageBackend.for_backblaze(
        os.getenv("B2_BUCKET_NAME", "notary-media"),
        region=os.getenv("B2_REGION", "us-east-005"),
        key_id=os.getenv("B2_KEY_ID"),
        app_key=os.getenv("B2_APP_KEY"),
    )
    return ObjectStorageSink(
        backend,
        key_strategy=KeyStrategy.HIERARCHICAL,
    )


def get_b2_backend():
    """Return the raw S3StorageBackend for manual uploads."""
    from genblaze_s3 import S3StorageBackend
    return S3StorageBackend.for_backblaze(
        os.getenv("B2_BUCKET_NAME", "notary-media"),
        region=os.getenv("B2_REGION", "us-east-005"),
        key_id=os.getenv("B2_KEY_ID"),
        app_key=os.getenv("B2_APP_KEY"),
    )


class LocalStorageBackend:
    """Local dev storage used when B2/genblaze-s3 is not configured."""

    def put(self, key: str, body, content_type: str | None = None) -> str:
        path = LOCAL_GENERATED_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        data = body.read() if hasattr(body, "read") else body
        path.write_bytes(data)
        return f"http://localhost:8000/generated/{key.replace(os.sep, '/')}"

    def get(self, key: str) -> bytes:
        return (LOCAL_GENERATED_DIR / key).read_bytes()


_cached_backend = None


def get_storage_backend():
    """
    Prefer B2; fall back to local files so the site remains testable.
    Cached as a module-level singleton — instantiated once, reused across all requests.
    Catches: missing module, missing/wrong credentials, bucket not found.
    """
    global _cached_backend
    if _cached_backend is not None:
        return _cached_backend
    try:
        backend = get_b2_backend()
        logger.info("B2 storage backend connected (bucket=%s)", os.getenv("B2_BUCKET_NAME"))
        _cached_backend = backend
    except Exception as e:
        logger.warning("B2 backend unavailable (%s: %s); using local generated storage",
                       type(e).__name__, e)
        _cached_backend = LocalStorageBackend()
    return _cached_backend


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
            steps = getattr(run, "steps", [])
            assets = getattr(steps[0], "assets", []) if steps else []
            if not assets:
                status = getattr(run, "status", "failed")
                raise RuntimeError(
                    f"Google image pipeline returned no asset (status={status})"
                )
            asset = assets[0]
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


# ── Path B: NVIDIA NIM + manual B2 upload ─────────────────────────────────

async def _run_nvidia_pipeline(prompt: str) -> dict:
    """
    Generate image via NVIDIA NIM (NvidiaImageProvider), upload to B2.
    Secondary fallback sitting between Google (primary) and Pollinations (final).
    """
    from genblaze_nvidia import NvidiaImageProvider
    from genblaze_core import Modality
    from genblaze_core.models.step import Step

    nv_key = os.getenv("NVIDIA_API_KEY", "")
    if not nv_key:
        raise RuntimeError("NVIDIA_API_KEY not set in environment")

    logger.info("Using NVIDIA NIM fallback (primary model: %s)", NVIDIA_IMAGE_MODEL_PRIMARY)

    provider = NvidiaImageProvider(http_timeout=15.0)

    for model_name in [NVIDIA_IMAGE_MODEL_PRIMARY, NVIDIA_IMAGE_MODEL_SECONDARY]:
        try:
            step = Step(
                provider="nvidia",
                model=model_name,
                prompt=prompt,
                modality=Modality.IMAGE,
            )
            res_step = await asyncio.to_thread(provider.invoke, step)
            if res_step.assets:
                asset = res_step.assets[0]
                if hasattr(asset, "data") and asset.data:
                    image_bytes = asset.data
                elif hasattr(asset, "path") and asset.path:
                    with open(asset.path, "rb") as f:
                        image_bytes = f.read()
                else:
                    raise ValueError(f"No bytes or path in NVIDIA asset: {asset}")

                sha256 = hashlib.sha256(image_bytes).hexdigest()
                run_id = str(uuid.uuid4())
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                asset_key = f"runs/notary/{date_str}/{run_id}/assets/image.png"
                manifest_key = f"runs/notary/{date_str}/{run_id}/manifest.json"

                backend = get_storage_backend()
                asset_url = backend.put(asset_key, io.BytesIO(image_bytes), content_type="image/png")

                manifest_data = sign_manifest({
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
                })
                manifest_uri = backend.put(
                    manifest_key,
                    io.BytesIO(json.dumps(manifest_data, indent=2).encode()),
                    content_type="application/json",
                )

                logger.info("NVIDIA NIM path success: model=%s asset=%s", model_name, asset_url)
                return {
                    "run_id": run_id,
                    "asset_url": asset_url,
                    "manifest_uri": manifest_uri,
                    "sha256": sha256,
                    "provider": "nvidia",
                    "model": model_name,
                    "has_embedded_metadata": False,
                    "has_visible_label": False,
                    "has_machine_readable_mark": False,
                }
        except Exception as e:
            err_msg = str(e).lower()
            if "401" in err_msg or "403" in err_msg or "auth" in err_msg:
                logger.warning("NVIDIA NIM auth failure (%s): %s", model_name, e)
                raise
            logger.warning("NVIDIA NIM model %s failed: %s — trying next", model_name, e)

    raise RuntimeError("All NVIDIA NIM models failed")


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

    backend = get_storage_backend()
    asset_url = backend.put(asset_key, io.BytesIO(image_bytes), content_type=content_type)

    manifest_data = sign_manifest({
        "run_id": run_id, "provider": "pollinations", "model": POLLINATIONS_MODEL,
        "prompt": prompt, "modality": "image",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": [{"key": asset_key, "url": asset_url, "sha256": sha256, "mime_type": content_type}],
        "has_embedded_metadata": False, "has_visible_label": False, "has_machine_readable_mark": False,
    })
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
      2. NVIDIA NIM NvidiaImageProvider (direct → B2)         [if NVIDIA_API_KEY]
      3. Pollinations.ai FLUX (direct → B2)                    [always available]
    """
    keys = api_keys or load_google_keys()

    if keys:
        try:
            logger.info("Trying Google path (%d keys)", len(keys))
            return await _run_google_pipeline(prompt, keys)
        except Exception as e:
            if _is_quota_error(e) or "exhausted" in str(e).lower():
                logger.warning("Google path failed: %s — trying NVIDIA NIM", e)
            else:
                logger.warning("Google error (%s: %s) — trying NVIDIA NIM", type(e).__name__, e)

    if os.getenv("NVIDIA_API_KEY"):
        try:
            logger.info("Trying NVIDIA NIM path")
            return await _run_nvidia_pipeline(prompt)
        except Exception as e:
            logger.warning("NVIDIA NIM failed: %s — trying Pollinations", e)

    logger.info("Using Pollinations.ai (always available)")
    return await _run_pollinations_pipeline(prompt)


async def run_video_pipeline(prompt: str, api_keys: list[str] | None = None) -> dict:
    """
    Generate a video via Google Veo (VeoProvider) → B2.
    Falls back to image-pipeline or synthetic MP4 on quota errors.
    """
    from genblaze_core import Pipeline, Modality
    from genblaze_google import VeoProvider

    keys = api_keys or load_google_keys()

    if keys:
        multi_key = MultiKeyGoogleProvider(keys, VeoProvider)
        while True:
            provider = multi_key.get_provider()
            try:
                logger.info("Trying Google Veo video path (key %d)", multi_key.current_key_index)
                storage = get_b2_storage()
                run, manifest = await (
                    Pipeline("notary-video-generate")
                    .step(
                        provider,
                        model=VIDEO_MODEL_ID,
                        prompt=prompt,
                        modality=Modality.VIDEO,
                    )
                    .arun(sink=storage, timeout=180)
                )
                asset = run.steps[0].assets[0]
                return {
                    "run_id": run.run_id,
                    "asset_url": asset.url,
                    "manifest_uri": manifest.manifest_uri,
                    "sha256": asset.sha256,
                    "provider": "google",
                    "model": VIDEO_MODEL_ID,
                    "has_embedded_metadata": True,
                    "has_visible_label": False,
                    "has_machine_readable_mark": False,
                }
            except Exception as e:
                if _is_quota_error(e):
                    logger.warning("Veo quota error on key %d: %s", multi_key.current_key_index, e)
                    if not multi_key.advance():
                        break
                else:
                    logger.warning("Veo execution error: %s — falling back", e)
                    break

    # Veo is unavailable. Raise a clear error rather than returning an image
    # mislabeled as video — that would corrupt the manifest and break the <video> tag.
    raise RuntimeError(
        "Video generation unavailable: Google Veo quota exhausted and no video fallback provider is configured. "
        "Please try image generation instead, or retry later when Veo quota refreshes."
    )


async def run_remix_pipeline(
    parent_run_id: str,
    parent_manifest_uri: str,
    prompt: str,
    modality: str = "image",
    api_keys: list[str] | None = None,
) -> dict:
    """
    Regenerate from an existing asset via lineage tracking (FR-8).
    Creates a new asset run with parent_run_id set.
    """
    if modality == "video":
        res = await run_video_pipeline(prompt, api_keys=api_keys)
    else:
        res = await run_image_pipeline(prompt, api_keys=api_keys)

    res["parent_run_id"] = parent_run_id

    # Update manifest in B2/local to include parent_run_id reference
    try:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        manifest_key = f"runs/notary/{date_str}/{res['run_id']}/manifest.json"

        manifest_data = {
            "run_id": res["run_id"],
            "parent_run_id": parent_run_id,
            "provider": res["provider"],
            "model": res["model"],
            "prompt": prompt,
            "modality": modality,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "assets": [
                {
                    "key": f"runs/notary/{date_str}/{res['run_id']}/assets/image.png",
                    "url": res["asset_url"],
                    "sha256": res["sha256"],
                    "mime_type": "image/png" if modality == "image" else "video/mp4",
                }
            ],
            "has_embedded_metadata": res.get("has_embedded_metadata", False),
            "has_visible_label": False,
            "has_machine_readable_mark": False,
        }

        backend = get_storage_backend()
        manifest_uri = backend.put(
            manifest_key,
            io.BytesIO(json.dumps(manifest_data, indent=2).encode()),
            content_type="application/json",
        )
        res["manifest_uri"] = manifest_uri
    except Exception as e:
        logger.warning("Failed to update parent lineage in manifest: %s", e)

    return res
