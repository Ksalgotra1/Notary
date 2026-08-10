"""Genblaze-first media generation and B2 provenance storage.

Every supported provider executes through ``genblaze_core.Pipeline`` and
``ObjectStorageSink``. The sink writes the asset and canonical Genblaze
manifest to Backblaze B2; manifests can be protected with B2 File Lock.
"""
from __future__ import annotations

import logging
import os
import json
import hashlib
import base64
import mimetypes
import tempfile
import uuid
import asyncio
import time
from urllib.parse import urlencode, quote

from datetime import datetime, timedelta, timezone
from pathlib import Path

from genblaze_core.exceptions import ProviderError
from genblaze_core.models.asset import Asset
from genblaze_core.models.enums import Modality
from genblaze_core.models.step import Step
from genblaze_core.providers.base import ProviderCapabilities, SyncProvider
from genblaze_core.runnable.config import RunnableConfig

logger = logging.getLogger(__name__)

IMAGE_MODEL_ID = "gemini-2.5-flash-image"
VIDEO_MODEL_ID = "veo-3.0-generate-001"
NVIDIA_IMAGE_MODEL_PRIMARY = "black-forest-labs/flux.1-schnell"
HF_SPACE_ID = "black-forest-labs/FLUX.2-klein-4B"
HF_SPACE_MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
POLLINATIONS_IMAGE_MODEL = "flux"


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _hf_space_url(space_id: str) -> str:
    return "https://" + space_id.lower().replace("/", "-").replace(".", "-") + ".hf.space"


class HuggingFaceSpaceImageProvider(SyncProvider):
    """Run the public FLUX.2 Klein Space through Genblaze.

    ``HF_TOKEN`` is optional for a public Space. When supplied, it is only
    sent to Hugging Face as transport authentication; it is never recorded in
    the Genblaze step payload or provenance manifest.
    """

    name = "huggingface-space"

    def __init__(
        self,
        *,
        space_id: str,
        token: str | None,
        timeout_seconds: float,
        space_url: str | None = None,
        ssl_verify: bool = True,
    ) -> None:
        super().__init__()
        self._space_id = space_id
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._space_url = space_url or _hf_space_url(space_id)
        self._ssl_verify = ssl_verify

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.IMAGE],
            supported_inputs=["text"],
            models=[HF_SPACE_MODEL_ID],
            output_formats=["image/png", "image/jpeg", "image/webp"],
        )

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        try:
            from gradio_client import Client

            client = Client(
                self._space_url,
                token=self._token or None,
                verbose=False,
                httpx_kwargs={"timeout": self._timeout_seconds},
                ssl_verify=self._ssl_verify,
            )
            result = client.predict(
                step.prompt or "",
                [],
                "Distilled (4 steps)",
                0,
                True,
                1024,
                1024,
                4,
                1.0,
                False,
                api_name="/infer",
            )
            image_result = result[0] if isinstance(result, (list, tuple)) else result
            source = image_result.get("path") if isinstance(image_result, dict) else str(image_result)
            image_bytes = Path(source).read_bytes()
            if not image_bytes:
                raise ValueError("Space returned an empty image file")
            suffix = Path(source).suffix or ".png"
            media_type = mimetypes.guess_type(source)[0] or "image/png"
            handle, destination = tempfile.mkstemp(prefix="notary-hf-space-", suffix=suffix)
            os.close(handle)
            Path(destination).write_bytes(image_bytes)
        except Exception as exc:
            raise ProviderError(f"Hugging Face Space image generation failed: {exc}") from exc

        # Only operational, non-secret details are preserved in provenance.
        step.provider_payload = {
            "huggingface_space": {
                "space_id": self._space_id,
                "space_url": self._space_url,
                "authenticated": bool(self._token),
            }
        }
        step.assets.append(Asset(url=Path(destination).as_uri(), media_type=media_type))
        return step


class PollinationsImageProvider(SyncProvider):
    """Genblaze adapter for Pollinations' authenticated image API."""

    name = "pollinations"

    def __init__(self, *, api_key: str | None, timeout_seconds: float) -> None:
        super().__init__()
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.IMAGE],
            supported_inputs=["text"],
            models=[POLLINATIONS_IMAGE_MODEL],
            output_formats=["image/png", "image/jpeg", "image/webp"],
        )

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        try:
            import httpx

            if self._api_key:
                response = httpx.post(
                    "https://gen.pollinations.ai/v1/images/generations",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": step.model,
                        "prompt": step.prompt or "",
                        "n": 1,
                        "size": "1024x1024",
                        "response_format": "b64_json",
                    },
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
                item = response.json()["data"][0]
                encoded = item.get("b64_json")
                if not encoded:
                    raise ValueError("Pollinations response did not contain b64_json output")
                image_bytes = base64.b64decode(encoded, validate=True)
                media_type = "image/png"
            else:
                query = urlencode({
                    "model": step.model,
                    "width": 1024,
                    "height": 1024,
                    "nologo": "true",
                })
                prompt = quote(step.prompt or "AI generated image", safe="")
                response = httpx.get(
                    f"https://image.pollinations.ai/prompt/{prompt}?{query}",
                    timeout=self._timeout_seconds,
                    follow_redirects=True,
                )
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "image" not in content_type.lower():
                    raise ValueError(f"Pollinations returned non-image content: {content_type or 'unknown'}")
                image_bytes = response.content
                media_type = content_type.split(";", 1)[0].strip() or "image/png"
            if not image_bytes:
                raise ValueError("Pollinations returned an empty image")
            handle, destination = tempfile.mkstemp(prefix="notary-pollinations-", suffix=".png")
            os.close(handle)
            Path(destination).write_bytes(image_bytes)
        except Exception as exc:
            raise ProviderError(f"Pollinations image generation failed: {exc}") from exc

        step.provider_payload = {
            "pollinations": {
                "model": step.model,
                "status": "succeeded",
                "authenticated": bool(self._api_key),
            }
        }
        step.assets.append(Asset(url=Path(destination).as_uri(), media_type=media_type))
        return step


class StorageConfigurationError(RuntimeError):
    """Raised when immutable B2 storage is not configured for a run."""


class MultiKeyGoogleProvider:
    """Rotate separate Google accounts only when a quota/rate limit is hit."""

    def __init__(self, api_keys: list[str], provider_cls):
        self._keys = [key.strip() for key in api_keys if key.strip()]
        if not self._keys:
            raise ValueError("At least one Google API key is required")
        self._provider_cls = provider_cls
        self._idx = 0

    def get_provider(self):
        return self._provider_cls(api_key=self._keys[self._idx])

    def advance(self) -> bool:
        self._idx += 1
        return self._idx < len(self._keys)

    @property
    def current_key_index(self) -> int:
        return self._idx


def load_google_keys() -> list[str]:
    return [key.strip() for key in os.getenv("GOOGLE_API_KEYS", "").split(",") if key.strip()]


def _is_quota_error(exc: Exception) -> bool:
    message = f"{type(exc).__name__} {exc}".lower()
    return any(token in message for token in ("quota", "rate limit", "ratelimit", "429", "resource exhausted"))


def _require_b2_configuration() -> None:
    missing = [name for name in ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET_NAME") if not os.getenv(name)]
    if missing:
        raise StorageConfigurationError(
            "B2 is required for Notary generation. Configure " + ", ".join(missing) + "."
        )
    if os.getenv("B2_OBJECT_LOCK_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        raise StorageConfigurationError(
            "B2_OBJECT_LOCK_ENABLED must be true. Create the B2 bucket with File Lock enabled."
        )


def get_b2_backend():
    """Create the Genblaze B2 backend; no local durable-storage fallback exists."""
    _require_b2_configuration()
    from genblaze_s3 import S3StorageBackend

    return S3StorageBackend.for_backblaze(
        os.environ["B2_BUCKET_NAME"],
        region=os.getenv("B2_REGION", "us-east-005"),
        key_id=os.environ["B2_KEY_ID"],
        app_key=os.environ["B2_APP_KEY"],
        public_url_base=os.getenv("B2_PUBLIC_URL_BASE") or None,
        auto_lifecycle=os.getenv("B2_AUTO_LIFECYCLE", "false").lower() in {"1", "true", "yes", "on"},
        preflight=True,
    )


def get_storage_backend():
    """Compatibility name for operational modules; always returns B2."""
    return get_b2_backend()


def get_b2_storage():
    """Build a Genblaze sink with hierarchical keys and manifest retention."""
    from genblaze_core import KeyStrategy, ObjectStorageSink
    from genblaze_core.storage.base import ObjectLockConfig

    retention_days = int(os.getenv("B2_MANIFEST_RETENTION_DAYS", "365"))
    if retention_days < 1:
        raise StorageConfigurationError("B2_MANIFEST_RETENTION_DAYS must be at least 1")
    mode = os.getenv("B2_OBJECT_LOCK_MODE", "COMPLIANCE").upper()
    if mode not in {"GOVERNANCE", "COMPLIANCE"}:
        raise StorageConfigurationError("B2_OBJECT_LOCK_MODE must be GOVERNANCE or COMPLIANCE")

    return ObjectStorageSink(
        get_b2_backend(),
        prefix="notary",
        key_strategy=KeyStrategy.HIERARCHICAL,
        manifest_lock=ObjectLockConfig(
            retain_until=datetime.now(timezone.utc) + timedelta(days=retention_days),
            mode=mode,
        ),
        strict_manifest_reads=True,
    )


def _pipeline_result_record(result, *, provider: str, model: str, embedded: bool = False) -> dict:
    run, manifest = result
    if not manifest.verify_hash():
        raise RuntimeError("Genblaze returned a manifest with an invalid canonical hash")
    assets = [asset for step in run.steps for asset in step.assets]
    if not assets:
        raise RuntimeError("Genblaze pipeline completed without an output asset")
    asset = assets[-1]
    if not asset.sha256 or not manifest.manifest_uri:
        raise RuntimeError("Genblaze output is missing a SHA-256 or durable manifest URI")
    return {
        "run_id": run.run_id,
        "parent_run_id": run.parent_run_id,
        "asset_url": asset.url,
        "manifest_uri": manifest.manifest_uri,
        "sha256": asset.sha256,
        "provider": provider,
        "model": model,
        "has_embedded_metadata": embedded,
        "has_visible_label": embedded,  # True for M1 (watermarked + embedded), False for M0 (raw)
        "has_machine_readable_mark": embedded,
        "manifest_verified": True,
        "object_lock_enabled": True,
    }


async def _run_pipeline(provider, *, model: str, prompt: str, modality, parent_result=None, run_metadata: dict | None = None):
    from genblaze_core import Pipeline

    pipeline = Pipeline("notary-generate", preflight=True)
    if parent_result is not None:
        pipeline.from_result(parent_result)
    pipeline.metadata(app="notary", provenance_version="1", **(run_metadata or {}))
    result = await pipeline.step(
        provider,
        model=model,
        prompt=prompt,
        modality=modality,
        metadata={"app": "notary", "provenance_version": "1"},
    ).arun(sink=get_b2_storage(), timeout=240)
    return result


def _single_output_asset(result):
    run, manifest = result
    assets = [asset for step in run.steps for asset in step.assets]
    if not assets:
        errors = [str(step.error) for step in run.steps if step.error]
        detail = f": {' | '.join(errors)}" if errors else ""
        raise RuntimeError(f"Genblaze pipeline completed without an output asset{detail}")
    return run, manifest, assets[-1]


async def _create_embedded_receipt(raw_result, *, provider: str, model: str, receipt_run_id: str) -> dict:
    """Create M1 for the final bytes that carry the immutable M0 manifest."""
    from genblaze_core import Modality
    from genblaze_core.media import get_handler
    from genblaze_core.models.asset import Asset
    from genblaze_core.models.enums import StepType
    from genblaze_core.models.manifest import Manifest
    from genblaze_core.models.run import Run
    from genblaze_core.models.step import Step
    from genblaze_core.pipeline.result import PipelineResult

    raw_run, raw_manifest, raw_asset = _single_output_asset(raw_result)
    if not raw_manifest.verify() or not raw_manifest.manifest_uri:
        raise RuntimeError("Raw generation manifest is not verifiable or has no durable URI")
    handler = get_handler(raw_asset.media_type)
    if handler is None:
        raise RuntimeError(f"Genblaze has no inline embedding handler for {raw_asset.media_type}")

    backend = get_b2_backend()
    raw_key = backend.key_from_url(raw_asset.url)
    if not raw_key:
        raise RuntimeError("Raw asset URL is not owned by the configured B2 backend")
    raw_bytes = backend.get(raw_key)
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(raw_asset.media_type)
    if not suffix:
        raise RuntimeError(f"Inline embedding is not enabled for {raw_asset.media_type}")

    # Apply visible watermark before manifest embedding so the badge is
    # part of the canonical signed bytes covered by M1.
    from watermark import apply_watermark
    raw_bytes = apply_watermark(raw_bytes, raw_asset.media_type)

    # Compute 64-bit perceptual hash (pHash) of watermarked image for
    # compression-resilient verification.  Survives JPEG re-encoding,
    # screenshots, and minor crops.
    phash_hex = None
    try:
        import imagehash
        from PIL import Image
        import io as _io
        pil_image = Image.open(_io.BytesIO(raw_bytes))
        phash_value = imagehash.phash(pil_image)
        phash_hex = str(phash_value)
        logger.info("phash: computed perceptual hash %s for run %s", phash_hex, receipt_run_id)
    except Exception as phash_exc:
        logger.warning("phash: computation failed for %s (%s) — continuing without pHash", receipt_run_id, phash_exc)

    with tempfile.TemporaryDirectory(prefix="notary-embed-") as directory:
        path = Path(directory) / f"embedded{suffix}"
        path.write_bytes(raw_bytes)
        handler.embed(path, raw_manifest)
        embedded_bytes = path.read_bytes()

        # Inject C2PA Content Credentials JUMBF header after Genblaze manifest
        # embedding so the C2PA signature covers the embedded provenance.
        has_c2pa = False
        try:
            from c2pa_signer import inject_c2pa_manifest
            source_step = next(step for step in reversed(raw_run.steps) if step.assets)
            c2pa_bytes = inject_c2pa_manifest(
                embedded_bytes,
                raw_asset.media_type,
                {
                    "run_id": raw_run.run_id,
                    "provider": provider,
                    "model": model,
                    "prompt": source_step.prompt if source_step else "",
                    "manifest_uri": raw_manifest.manifest_uri,
                },
            )
            if len(c2pa_bytes) > len(embedded_bytes):
                embedded_bytes = c2pa_bytes
                has_c2pa = True
                logger.info("c2pa: Content Credentials injected for run %s", receipt_run_id)
        except Exception as c2pa_exc:
            logger.warning("c2pa: injection failed for %s (%s) — continuing without C2PA", receipt_run_id, c2pa_exc)

        final_bytes = embedded_bytes
        final_sha256 = hashlib.sha256(final_bytes).hexdigest()

        final_asset = Asset(
            url=path.as_uri(), media_type=raw_asset.media_type,
            sha256=final_sha256, size_bytes=len(final_bytes),
            metadata={"embedded_manifest_run_id": raw_run.run_id, "has_c2pa": has_c2pa},
        )
        source_step = next(step for step in reversed(raw_run.steps) if step.assets)
        receipt_step = Step(
            provider="notary", model="genblaze-inline-manifest-v1",
            step_type=StepType.CUSTOM, modality=Modality.IMAGE,
            prompt=source_step.prompt, inputs=[raw_asset], assets=[final_asset],
            metadata={"operation": "embed_genblaze_manifest", "source_run_id": raw_run.run_id, "has_c2pa": has_c2pa},
        )
        receipt_run = Run(
            run_id=receipt_run_id, name="notary-embedded-receipt",
            parent_run_id=raw_run.run_id, steps=[receipt_step],
            metadata={
                "app": "notary",
                "provenance_version": "2",
                "source_manifest_uri": raw_manifest.manifest_uri,
                "source_run_id": raw_run.run_id,
                "generation_provider": provider,
                "generation_model": model,
                "has_c2pa": has_c2pa,
            },
        )
        receipt_manifest = Manifest.from_run(receipt_run)

        # Sign the canonical M1 manifest with Ed25519 — independent trust anchor.
        # Stored in the manifest metadata so it is WORM-locked alongside the run.
        try:
            from signing import sign_manifest, canonical_manifest_json
            import json as _json
            sig = sign_manifest(canonical_manifest_json(receipt_manifest.to_dict()))
            receipt_run.metadata["ed25519_signature"] = sig
            receipt_manifest = Manifest.from_run(receipt_run)
            logger.debug("signing: M1 manifest signed for run %s", receipt_run_id)
        except Exception as _sig_exc:
            logger.warning("signing: Ed25519 signing failed for %s (%s) — continuing without signature", receipt_run_id, _sig_exc)

        # Write the final signed bytes back to the temp file so the B2 sink
        # uploads the C2PA-signed version, not the pre-C2PA version.
        path.write_bytes(final_bytes)

        await asyncio.to_thread(get_b2_storage().write_run, receipt_run, receipt_manifest)

    receipt_result = PipelineResult(receipt_run, receipt_manifest)
    receipt_record = _pipeline_result_record(receipt_result, provider=provider, model=model, embedded=True)
    receipt_record["has_c2pa"] = has_c2pa
    receipt_record["phash"] = phash_hex
    # M0 is retained as an internal lineage node; M1 is the shareable artifact.
    receipt_record["source_record"] = _pipeline_result_record(
        raw_result, provider=provider, model=model, embedded=False,
    )
    return receipt_record



async def _run_embedded_image(provider, *, provider_name: str, model: str, prompt: str, parent_result=None) -> dict:
    from genblaze_core import Modality

    receipt_run_id = str(uuid.uuid4())
    raw_result = await _run_pipeline(
        provider, model=model, prompt=prompt, modality=Modality.IMAGE,
        parent_result=parent_result,
        run_metadata={"embedded_receipt_run_id": receipt_run_id},
    )
    return await _create_embedded_receipt(
        raw_result, provider=provider_name, model=model, receipt_run_id=receipt_run_id,
    )


def verify_embedded_receipt(receipt_manifest, file_bytes: bytes, source_manifest=None) -> bool:
    """Verify M0 extracted from an image and its locked M1 transform receipt."""
    from genblaze_core.media import get_handler
    from genblaze_core.models.manifest import parse_manifest

    source_uri = receipt_manifest.run.metadata.get("source_manifest_uri")
    if not source_uri:
        return True  # Video and legacy records are verified by their own manifest/hash only.
    output_assets = [asset for step in receipt_manifest.run.steps for asset in step.assets]
    if not output_assets:
        return False
    output = output_assets[-1]
    handler = get_handler(output.media_type)
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(output.media_type)
    if handler is None or suffix is None:
        return False

    with tempfile.TemporaryDirectory(prefix="notary-verify-") as directory:
        path = Path(directory) / f"submitted{suffix}"
        path.write_bytes(file_bytes)
        try:
            embedded_m0 = handler.extract(path)
        except Exception:
            return False
    if not embedded_m0.verify() or embedded_m0.run.run_id != receipt_manifest.run.parent_run_id:
        return False
    if embedded_m0.run.metadata.get("embedded_receipt_run_id") != receipt_manifest.run.run_id:
        return False
    if not output.sha256 or hashlib.sha256(file_bytes).hexdigest() != output.sha256:
        return False

    if source_manifest is None:
        backend = get_b2_backend()
        source_key = backend.key_from_url(source_uri)
        if not source_key:
            return False
        try:
            source_manifest = parse_manifest(json.loads(backend.get(source_key).decode("utf-8")))
        except Exception:
            return False
    return source_manifest.verify() and source_manifest.canonical_hash == embedded_m0.canonical_hash


async def _run_google_image(prompt: str, keys: list[str], parent_result=None) -> dict:
    from genblaze_core import Modality
    from genblaze_google import GeminiImageProvider
    from metrics import record_generation

    rotation = MultiKeyGoogleProvider(keys, GeminiImageProvider)
    t0 = time.monotonic()
    while True:
        try:
            res = await _run_embedded_image(
                rotation.get_provider(), provider_name="google", model=IMAGE_MODEL_ID,
                prompt=prompt, parent_result=parent_result,
            )
            await record_generation(
                run_id=res["run_id"], provider="google", model=IMAGE_MODEL_ID,
                modality="image", success=True, latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return res
        except Exception as exc:
            await record_generation(
                run_id=None, provider="google", model=IMAGE_MODEL_ID,
                modality="image", success=False, latency_ms=int((time.monotonic() - t0) * 1000),
                error_type=type(exc).__name__,
            )
            if not _is_quota_error(exc) or not rotation.advance():
                raise RuntimeError(f"Google Genblaze pipeline failed: {exc}") from exc
            logger.warning("Google quota exhausted on key %d; rotating key", rotation.current_key_index)


async def _run_nvidia_image(prompt: str, parent_result=None, nvidia_api_key: str | None = None) -> dict:
    from genblaze_core import Modality
    from genblaze_nvidia import NvidiaImageProvider
    from metrics import record_generation

    api_key = nvidia_api_key or os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is not configured")
    timeout = float(os.getenv("NVIDIA_IMAGE_TIMEOUT_SECONDS", "45"))
    provider = NvidiaImageProvider(api_key=api_key, http_timeout=timeout, nvcf_timeout=timeout)
    t0 = time.monotonic()
    try:
        res = await _run_embedded_image(
            provider, provider_name="nvidia", model=NVIDIA_IMAGE_MODEL_PRIMARY,
            prompt=prompt, parent_result=parent_result,
        )
        await record_generation(
            run_id=res["run_id"], provider="nvidia", model=NVIDIA_IMAGE_MODEL_PRIMARY,
            modality="image", success=True, latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return res
    except Exception as exc:
        await record_generation(
            run_id=None, provider="nvidia", model=NVIDIA_IMAGE_MODEL_PRIMARY,
            modality="image", success=False, latency_ms=int((time.monotonic() - t0) * 1000),
            error_type=type(exc).__name__,
        )
        raise RuntimeError(f"NVIDIA Genblaze pipeline failed: {exc}") from exc


async def _run_huggingface_space_image(prompt: str, parent_result=None) -> dict:
    from metrics import record_generation

    space_id = os.getenv("HF_SPACE_ID", HF_SPACE_ID)
    space_url = os.getenv("HF_SPACE_URL") or _hf_space_url(space_id)
    timeout = float(os.getenv("HF_SPACE_TIMEOUT_SECONDS", "180"))
    ssl_verify = _env_flag("HF_SSL_VERIFY", True)
    t0 = time.monotonic()
    try:
        res = await _run_embedded_image(
            HuggingFaceSpaceImageProvider(
                space_id=space_id,
                token=os.getenv("HF_TOKEN") or None,
                timeout_seconds=timeout,
                space_url=space_url,
                ssl_verify=ssl_verify,
            ),
            provider_name="huggingface-space",
            model=HF_SPACE_MODEL_ID,
            prompt=prompt,
            parent_result=parent_result,
        )
        await record_generation(
            run_id=res["run_id"], provider="huggingface-space", model=HF_SPACE_MODEL_ID,
            modality="image", success=True, latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return res
    except Exception as exc:
        await record_generation(
            run_id=None, provider="huggingface-space", model=HF_SPACE_MODEL_ID,
            modality="image", success=False, latency_ms=int((time.monotonic() - t0) * 1000),
            error_type=type(exc).__name__,
        )
        raise exc


async def _run_pollinations_image(prompt: str, parent_result=None) -> dict:
    from metrics import record_generation

    api_key = os.getenv("POLLINATIONS_API_KEY") or None
    model = os.getenv("POLLINATIONS_IMAGE_MODEL", POLLINATIONS_IMAGE_MODEL)
    timeout = float(os.getenv("POLLINATIONS_TIMEOUT_SECONDS", "90"))
    t0 = time.monotonic()
    try:
        res = await _run_embedded_image(
            PollinationsImageProvider(api_key=api_key, timeout_seconds=timeout),
            provider_name="pollinations",
            model=model,
            prompt=prompt,
            parent_result=parent_result,
        )
        await record_generation(
            run_id=res["run_id"], provider="pollinations", model=model,
            modality="image", success=True, latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return res
    except Exception as exc:
        await record_generation(
            run_id=None, provider="pollinations", model=model,
            modality="image", success=False, latency_ms=int((time.monotonic() - t0) * 1000),
            error_type=type(exc).__name__,
        )
        raise exc


async def run_image_pipeline(
    prompt: str,
    api_keys: list[str] | None = None,
    parent_result=None,
    nvidia_api_key: str | None = None,
) -> dict:
    """Use Genblaze-backed providers in a resilient, declared order.

    User-supplied keys (from BYOK) take precedence over server .env keys.
    They are used in-flight only and never logged or stored.
    """
    errors = []
    keys = api_keys or load_google_keys()
    if keys:
        try:
            return await _run_google_image(prompt, keys, parent_result)
        except Exception as exc:
            errors.append(str(exc))
            logger.warning("Google pipeline unavailable; trying NVIDIA: %s", exc)
    if nvidia_api_key or os.getenv("NVIDIA_API_KEY"):
        try:
            return await _run_nvidia_image(prompt, parent_result, nvidia_api_key=nvidia_api_key)
        except Exception as exc:
            errors.append(str(exc))
            logger.warning("NVIDIA pipeline unavailable; trying Hugging Face Space: %s", exc)
    try:
        return await _run_huggingface_space_image(prompt, parent_result)
    except Exception as exc:
        errors.append(str(exc))
        logger.warning("Hugging Face Space pipeline unavailable; trying Pollinations: %s", exc)
    try:
        return await _run_pollinations_image(prompt, parent_result)
    except Exception as exc:
        errors.append(str(exc))
    raise RuntimeError("No Genblaze image provider succeeded. " + " | ".join(errors))


async def run_video_pipeline(prompt: str, api_keys: list[str] | None = None, parent_result=None) -> dict:
    """Generate Veo video through Genblaze, rotating Google keys on quota."""
    from genblaze_core import Modality
    from genblaze_google import VeoProvider

    keys = api_keys or load_google_keys()
    if not keys:
        raise RuntimeError("Video generation requires GOOGLE_API_KEYS for the Genblaze Veo provider")
    rotation = MultiKeyGoogleProvider(keys, VeoProvider)
    while True:
        try:
            result = await _run_pipeline(
                rotation.get_provider(), model=VIDEO_MODEL_ID,
                prompt=prompt, modality=Modality.VIDEO, parent_result=parent_result,
            )
            return _pipeline_result_record(result, provider="google", model=VIDEO_MODEL_ID)
        except Exception as exc:
            if not _is_quota_error(exc) or not rotation.advance():
                raise RuntimeError(f"Google Veo Genblaze pipeline failed: {exc}") from exc
            logger.warning("Veo quota exhausted on key %d; rotating key", rotation.current_key_index)


async def run_remix_pipeline(
    parent_run_id: str,
    parent_manifest_uri: str,
    prompt: str,
    modality: str = "image",
    api_keys: list[str] | None = None,
    nvidia_api_key: str | None = None,
) -> dict:
    """Create Genblaze-native lineage using ``Pipeline.from_result``."""
    from genblaze_core.models.manifest import parse_manifest
    from genblaze_core.pipeline.result import PipelineResult

    backend = get_b2_backend()
    key = backend.key_from_url(parent_manifest_uri)
    if not key:
        raise RuntimeError("Parent manifest URI is not owned by the configured B2 backend")
    parent_manifest = parse_manifest(json.loads(backend.get(key).decode("utf-8")))
    if not parent_manifest.verify_hash() or parent_manifest.run.run_id != parent_run_id:
        raise RuntimeError("Parent Genblaze manifest failed verification")
    parent_result = PipelineResult(parent_manifest.run, parent_manifest)
    if modality == "video":
        return await run_video_pipeline(prompt, api_keys=api_keys, parent_result=parent_result)
    return await run_image_pipeline(prompt, api_keys=api_keys, parent_result=parent_result, nvidia_api_key=nvidia_api_key)
