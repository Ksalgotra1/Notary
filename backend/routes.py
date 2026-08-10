"""API routes for the Notary backend."""
import hashlib
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional
import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from aiosqlite import Connection

from cache import get_db, get_asset, list_assets, insert_asset, update_verify_status, update_compliance, update_policy_audit, get_lineage, find_cached_generation
from compliance import evaluate_asset, manifest_data_from_db_row
from policy import audit_image_bytes, review_prompt
from models import (
    AssetDetail, AssetListResponse, AssetSummary,
    ComplianceReport,
    ForensicDetail,
    GenerateRequest, GenerateResponse, PromptReviewRequest, PromptReviewResponse, PolicyAuditSummary,
    PublicAssetInfo, PublicVerifyRequest,
    RemixRequest,
    VerifyResponse,
)
from pipeline import run_image_pipeline, run_video_pipeline, run_remix_pipeline, get_b2_backend, get_b2_storage, verify_embedded_receipt
from forensics import analyze_tampering
from rebuild_cache import main as run_rebuild_cache
from metrics import record_generation, get_metrics
from audit import run_full_audit

logger = logging.getLogger(__name__)
router = APIRouter()


async def _read_b2_asset_bytes(row: dict) -> bytes:
    """Read asset bytes from B2. Falls back to direct HTTP for non-B2 URLs."""
    try:
        backend = get_b2_backend()
        key = backend.key_from_url(row["b2_asset_url"])
        if key:
            data = backend.get(key)
            if isinstance(data, bytes):
                return data
            if hasattr(data, "read"):
                value = data.read()
                return await value if hasattr(value, "__await__") else value
            return bytes(data)
    except Exception as e:
        logger.debug("B2 read failed for %s: %s — trying HTTP", row["b2_asset_url"], e)

    # Fallback: direct HTTP download for non-B2 URLs (HuggingFace, etc.)
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(row["b2_asset_url"])
        resp.raise_for_status()
        return resp.content


async def _read_asset_url_bytes(asset_url: str) -> bytes:
    """Read asset bytes by URL. Falls back to direct HTTP for non-B2 URLs."""
    try:
        backend = get_b2_backend()
        key = backend.key_from_url(asset_url)
        if key:
            data = backend.get(key)
            return data if isinstance(data, bytes) else bytes(data.read())
    except Exception as e:
        logger.debug("B2 read failed for %s: %s — trying HTTP", asset_url, e)

    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(asset_url)
        resp.raise_for_status()
        return resp.content


async def _write_policy_audit_manifest(
    *, run_id: str, prompt: str, modality: str, profile: str, prompt_audit: dict, visual_audit: dict,
) -> str:
    """Write a separate locked M2 policy-audit record; M1 bytes never change."""
    from genblaze_core.models.enums import Modality as GenblazeModality, StepType
    from genblaze_core.models.manifest import Manifest
    from genblaze_core.models.run import Run
    from genblaze_core.models.step import Step

    audit_run = Run(
        run_id=str(uuid.uuid4()), name="notary-policy-audit", parent_run_id=run_id,
        metadata={
            "app": "notary", "provenance_version": "2", "audit_type": "policy",
            "policy_profile": profile, "prompt_audit": prompt_audit, "visual_audit": visual_audit,
        },
        steps=[Step(
            provider="notary-policy", model=visual_audit.get("model") or "deterministic-policy-v1",
            step_type=StepType.CUSTOM,
            modality=GenblazeModality.VIDEO if modality == "video" else GenblazeModality.IMAGE,
            prompt=prompt,
            metadata={"policy_profile": profile, "prompt_audit": prompt_audit, "visual_audit": visual_audit},
        )],
    )
    manifest = Manifest.from_run(audit_run)
    await asyncio.to_thread(get_b2_storage().write_run, audit_run, manifest)
    if not manifest.manifest_uri:
        raise RuntimeError("Policy audit manifest was not assigned a durable B2 URI")
    return manifest.manifest_uri


async def _run_and_store_policy_audit(db: Connection, req: GenerateRequest, result: dict) -> PolicyAuditSummary:
    prompt_audit = review_prompt(req.prompt, req.policy_profile)
    if req.modality.value == "image":
        try:
            visual_audit = await audit_image_bytes(
                await _read_asset_url_bytes(result["asset_url"]), profile=req.policy_profile, prompt=req.prompt,
            )
        except Exception as exc:
            logger.warning("Visual audit could not read generated asset %s: %s", result["run_id"], exc)
            visual_audit = {
                "status": "unavailable", "mode": "asset_read_error", "model": None, "findings": [],
                "summary": "Visual audit could not read the generated asset; provenance verification remains available.",
            }
    else:
        visual_audit = {
            "status": "unavailable", "mode": "unsupported_modality", "model": None, "findings": [],
            "summary": "Visual audit currently supports images only.",
        }
    try:
        manifest_uri = await _write_policy_audit_manifest(
            run_id=result["run_id"], prompt=req.prompt, modality=req.modality.value,
            profile=req.policy_profile, prompt_audit=prompt_audit, visual_audit=visual_audit,
        )
    except Exception as exc:
        logger.warning("Policy audit manifest could not be locked for %s: %s", result["run_id"], exc)
        manifest_uri = None
    await update_policy_audit(
        db, result["run_id"], profile=req.policy_profile,
        prompt_audit_json=json.dumps(prompt_audit), visual_audit_json=json.dumps(visual_audit),
        policy_manifest_url=manifest_uri,
    )
    return PolicyAuditSummary(
        profile=req.policy_profile, prompt_audit=PromptReviewResponse(**prompt_audit),
        visual_audit=visual_audit, manifest_uri=manifest_uri,
    )


def _policy_audit_from_row(row: dict) -> PolicyAuditSummary | None:
    if not row.get("prompt_audit_json"):
        return None
    try:
        return PolicyAuditSummary(
            profile=row.get("policy_profile") or "general",
            prompt_audit=PromptReviewResponse(**json.loads(row["prompt_audit_json"])),
            visual_audit=json.loads(row["visual_audit_json"]) if row.get("visual_audit_json") else None,
            manifest_uri=row.get("policy_manifest_url"),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Could not parse policy audit cache for %s: %s", row.get("run_id"), exc)
        return None


def _runtime_asset_url(asset_url: str) -> str:
    """Create a short-lived browser delivery URL without altering the manifest URL.
    Falls back to the original URL for assets not owned by the configured B2 backend
    (e.g. HuggingFace Space URLs returned by Genblaze's internal provider cascade).
    """
    try:
        backend = get_b2_backend()
        key = backend.key_from_url(asset_url)
        if key:
            return backend.get_url(key, expires_in=3600)
    except Exception as e:
        logger.debug("_runtime_asset_url: B2 URL generation failed (%s), returning original", e)
    return asset_url



async def _load_verified_manifest(row: dict):
    """Read and validate the canonical Genblaze manifest stored in B2.
    Falls back to direct HTTP for non-B2 manifest URLs."""
    from genblaze_core.models.manifest import parse_manifest

    raw = None
    try:
        backend = get_b2_backend()
        key = backend.key_from_url(row["b2_manifest_url"])
        if key:
            raw = backend.get(key)
    except Exception as e:
        logger.debug("B2 manifest read failed: %s — trying HTTP", e)

    if raw is None:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(row["b2_manifest_url"])
            resp.raise_for_status()
            raw = resp.content

    if hasattr(raw, "read"):
        raw = raw.read()
    manifest = parse_manifest(json.loads(bytes(raw).decode("utf-8")))
    if not manifest.verify_hash():
        raise ValueError("Genblaze manifest canonical hash verification failed")
    if manifest.run.run_id != row["run_id"]:
        raise ValueError("Genblaze manifest run ID does not match the requested asset")
    assets = [asset for step in manifest.run.steps for asset in step.assets]
    if not assets or not assets[-1].sha256:
        raise ValueError("Genblaze manifest has no verifiable output asset")
    return manifest, assets[-1]


async def _forensic_detail(row: dict, submitted_bytes: bytes) -> ForensicDetail | None:
    try:
        analysis = await analyze_tampering(
            original_bytes=await _read_b2_asset_bytes(row),
            tampered_bytes=submitted_bytes,
            modality=row.get("modality", "image"),
        )
        return ForensicDetail(**analysis) if analysis else None
    except Exception as e:
        logger.warning("Forensic analysis failed: %s", e)
        return None


# ── Core generation endpoints ─────────────────────────────────────

@router.get("/.well-known/notary-public-key.pem", response_class=Response)
async def notary_public_key():
    """
    Publish the Notary Ed25519 public key for independent manifest verification.
    Third parties can use this to verify that manifests were signed by Notary
    and have not been forged, even if B2 credentials were compromised.
    """
    try:
        from signing import get_public_key_pem
        return Response(
            content=get_public_key_pem(),
            media_type="application/x-pem-file",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Public key not available: {exc}") from exc


@router.post("/policy/prompt-review", response_model=PromptReviewResponse)
async def prompt_review(req: PromptReviewRequest):
    """Review a prompt without sending it to a provider or altering it."""
    try:
        return PromptReviewResponse(**review_prompt(req.prompt, req.policy_profile))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _enforce_prompt_policy(req: GenerateRequest) -> dict:
    try:
        audit = review_prompt(req.prompt, req.policy_profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if audit["status"] == "block":
        raise HTTPException(status_code=422, detail={"message": "Prompt is blocked by the selected policy profile.", "policy_audit": audit})
    if audit["requires_acknowledgement"] and not req.policy_acknowledged:
        raise HTTPException(status_code=409, detail={"message": "Review policy warnings before generation.", "policy_audit": audit})
    return audit


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, db: Connection = Depends(get_db)):
    """FR-1/FR-2: Generate image or video via Genblaze Pipeline → B2."""
    _enforce_prompt_policy(req)

    # ── Prompt cache: return existing result if exact match within TTL ──
    cached = await find_cached_generation(db, req.prompt, req.modality.value)
    if cached:
        logger.info("Cache HIT for prompt=%s modality=%s → run_id=%s",
                     req.prompt[:40], req.modality.value, cached["run_id"])
        return GenerateResponse(
            run_id=cached["run_id"],
            status="completed",
            asset_url=_runtime_asset_url(cached["b2_asset_url"]),
            manifest_uri=cached["b2_manifest_url"],
            sha256=cached["sha256"],
            provider=cached["provider"],
            model=cached["model"],
        )
    # ── End cache check ──

    t0 = time.monotonic()
    # BYOK: resolve per-request user-supplied keys (never logged, never stored)
    user_google_keys = [req.google_api_key] if req.google_api_key else None
    user_nvidia_key = req.nvidia_api_key or None
    try:
        if req.modality.value == "video":
            res = await run_video_pipeline(req.prompt, api_keys=user_google_keys)
        else:
            res = await run_image_pipeline(req.prompt, api_keys=user_google_keys, nvidia_api_key=user_nvidia_key)
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        await record_generation(
            run_id=None, provider="unknown", model="unknown",
            modality=req.modality.value, success=False,
            latency_ms=latency_ms, error_type=type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail=str(exc))

    latency_ms = int((time.monotonic() - t0) * 1000)
    await record_generation(
        run_id=res["run_id"],
        provider=res.get("provider", "unknown"),
        model=res.get("model", "unknown"),
        modality=req.modality.value,
        success=True,
        latency_ms=latency_ms,
    )

    await _save_asset_to_db(db, req, res)
    policy_audit = await _run_and_store_policy_audit(db, req, res)
    return GenerateResponse(
        run_id=res["run_id"],
        status="completed",
        asset_url=_runtime_asset_url(res["asset_url"]),
        manifest_uri=res["manifest_uri"],
        sha256=res["sha256"],
        provider=res.get("provider"),
        model=res.get("model"),
        policy_audit=policy_audit,
    )


@router.get("/assets", response_model=AssetListResponse)
async def list_assets_route(
    limit: int = Query(20, ge=1, le=100),
    provider: Optional[str] = None,
    modality: Optional[str] = None,
    db: Connection = Depends(get_db),
):
    """FR-9: List assets from SQLite cache."""
    rows = await list_assets(db, limit=limit, provider=provider, modality=modality)
    response_rows = []
    for row in rows:
        response_row = dict(row)
        response_row["b2_asset_url"] = _runtime_asset_url(row["b2_asset_url"])
        response_rows.append(response_row)
    return AssetListResponse(
        assets=[AssetSummary(**r) for r in response_rows],
        total=len(rows),
    )


@router.get("/assets/{run_id}", response_model=AssetDetail)
async def get_asset_route(run_id: str, db: Connection = Depends(get_db)):
    """FR-5: Full manifest + asset URL for a single run."""
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    response_row = dict(row)
    response_row["b2_asset_url"] = _runtime_asset_url(row["b2_asset_url"])
    response_row["policy_audit"] = _policy_audit_from_row(row)
    return AssetDetail(**response_row)


@router.post("/assets/{run_id}/verify", response_model=VerifyResponse)
async def verify_asset(run_id: str, db: Connection = Depends(get_db)):
    """
    FR-6 + FR-16: Recompute hash from B2 asset, compare to manifest.
    On mismatch, trigger AI forensic analysis (USP #2).
    """
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    try:
        manifest, manifest_asset = await _load_verified_manifest(row)
        original_bytes = await _read_b2_asset_bytes(row)
        computed_hash = hashlib.sha256(original_bytes).hexdigest()
        embedded_chain_valid = verify_embedded_receipt(manifest, original_bytes)
    except Exception as e:
        logger.warning("Native Genblaze verification failed for %s: %s", run_id, e)
        raise HTTPException(status_code=502, detail=f"Unable to verify canonical provenance: {e}") from e

    manifest_hash = manifest_asset.sha256
    match = (
        embedded_chain_valid
        and computed_hash.lower() == manifest_hash.lower()
        and row["sha256"].lower() == manifest_hash.lower()
    )

    verified_at = datetime.now(timezone.utc).isoformat()
    status_str = "pass" if match else "fail"
    await update_verify_status(db, run_id, status_str, verified_at)

    return VerifyResponse(
        match=match,
        computed_hash=computed_hash,
        manifest_hash=manifest_hash,
        verified_at=verified_at,
        forensic_analysis=None,
        manifest_valid=embedded_chain_valid,
    )


@router.post("/assets/{run_id}/remix", response_model=GenerateResponse)
async def remix_asset(run_id: str, req: RemixRequest, db: Connection = Depends(get_db)):
    """FR-8 (S1): Regenerate from existing asset with modified prompt via lineage tracking."""
    parent = await get_asset(db, run_id)
    if not parent:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    res = await run_remix_pipeline(
        parent_run_id=run_id,
        parent_manifest_uri=parent["b2_manifest_url"],
        prompt=req.prompt,
        modality=parent["modality"],
    )

    await _save_asset_to_db(db, req, res, modality=parent["modality"])
    return GenerateResponse(
        run_id=res["run_id"],
        status="completed",
        asset_url=_runtime_asset_url(res["asset_url"]),
        manifest_uri=res["manifest_uri"],
        sha256=res["sha256"],
    )


# ── USP #1: Compliance Engine ─────────────────────────────────────

@router.get("/assets/{run_id}/compliance", response_model=ComplianceReport)
async def get_compliance(run_id: str, db: Connection = Depends(get_db)):
    """FR-15 (USP #1): Evaluate asset against India IT Rules 2026 + EU AI Act Article 50."""
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    manifest = manifest_data_from_db_row(row)
    report = evaluate_asset(manifest)

    # Persist compliance result back to cache
    await update_compliance(
        db, run_id,
        india_compliant=report["regulations"][0]["compliant"],
        eu_compliant=report["regulations"][1]["compliant"],
        evaluated_at=report["evaluated_at"],
    )

    return ComplianceReport(**report)


# ── USP #3: Public Verification Portal ───────────────────────────

@router.get("/public/verify/{run_id}", response_model=PublicAssetInfo)
async def public_asset_info(run_id: str, db: Connection = Depends(get_db)):
    """
    FR-17 (USP #3): Public provenance info — no auth required.
    Safe for sharing: no secrets, no internal URLs exposed.
    """
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    manifest = manifest_data_from_db_row(row)
    report = evaluate_asset(manifest)

    return PublicAssetInfo(
        run_id=row["run_id"],
        provider=row["provider"],
        model=row["model"],
        modality=row["modality"],
        prompt=row["prompt"],
        created_at=row["created_at"],
        sha256=row["sha256"],
        compliance_report=ComplianceReport(**report),
        policy_audit=_policy_audit_from_row(row),
    )


@router.post("/public/verify/{run_id}", response_model=VerifyResponse)
async def public_verify(
    run_id: str,
    req: PublicVerifyRequest,
    db: Connection = Depends(get_db),
):
    """
    FR-17 (USP #3): Public file verification.
    User supplies SHA-256 computed client-side (Web Crypto API) to avoid
    uploading large video files to the server.
    On mismatch, forensic analysis is triggered (USP #2).
    """
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    try:
        _, manifest_asset = await _load_verified_manifest(row)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Canonical provenance is unavailable: {e}") from e
    manifest_hash = manifest_asset.sha256
    is_match = req.file_hash.lower() == manifest_hash.lower()

    # pHash resilient fallback: if SHA-256 fails, check perceptual similarity
    phash_match = None
    if not is_match and row.get("phash"):
        try:
            from cache import _hamming_distance
            file_phash = getattr(req, "file_phash", None)
            if file_phash:
                distance = _hamming_distance(file_phash, row["phash"])
                phash_match = {
                    "stored_phash": row["phash"],
                    "submitted_phash": file_phash,
                    "hamming_distance": distance,
                    "similarity_pct": round((1 - distance / 64) * 100, 1),
                    "is_perceptual_match": distance <= 4,
                    "verdict": (
                        "Visually identical - file modified by compression or re-encoding"
                        if distance <= 4
                        else "Perceptually similar but visually different"
                        if distance <= 15
                        else "Visually distinct - likely a different image"
                    ),
                }
        except Exception:
            pass

    verified_at = datetime.now(timezone.utc).isoformat()
    return VerifyResponse(
        match=is_match,
        computed_hash=req.file_hash,
        manifest_hash=manifest_hash,
        verified_at=verified_at,
        forensic_analysis=None,
        manifest_valid=True,
        phash_match=phash_match,
    )


@router.get("/public/verify/search")
async def phash_search(
    phash: str = Query(..., description="Hex-encoded pHash to search for"),
    max_distance: int = Query(4, ge=0, le=64, description="Maximum Hamming distance"),
    db: Connection = Depends(get_db),
):
    """
    Search for assets that are perceptually similar to a given pHash.
    Returns assets within the specified Hamming distance threshold.
    Useful for finding originals of screenshots, compressed copies, etc.
    """
    from cache import find_by_phash
    results = await find_by_phash(db, phash, max_distance)
    return {
        "query_phash": phash,
        "max_distance": max_distance,
        "total_matches": len(results),
        "matches": [
            {
                "run_id": r["run_id"],
                "provider": r["provider"],
                "model": r["model"],
                "prompt": r["prompt"],
                "sha256": r["sha256"],
                "phash": r["phash"],
                "phash_distance": r["phash_distance"],
                "phash_similarity": r["phash_similarity"],
            }
            for r in results
        ],
    }


@router.post("/public/verify/{run_id}/file", response_model=VerifyResponse)
async def public_verify_file(
    run_id: str,
    file_hash: str = Form(...),
    file: UploadFile = File(...),
    db: Connection = Depends(get_db),
):
    """Verify a public upload using true streaming 64KB chunking — O(1) memory on hash match."""
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # True streaming: hash computed chunk-by-chunk, no full buffer in RAM.
    # File bytes are only loaded if forensics is needed (mismatch path only).
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB hard limit
    sha256_hasher = hashlib.sha256()
    total_size = 0

    while chunk := await file.read(65536):  # 64 KB chunk
        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Uploaded file exceeds maximum limit of 100 MB")
        sha256_hasher.update(chunk)

    computed_hash = sha256_hasher.hexdigest()

    if computed_hash.lower() != file_hash.lower():
        raise HTTPException(status_code=400, detail="Submitted hash does not match uploaded file content")

    try:
        manifest, manifest_asset = await _load_verified_manifest(row)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Canonical provenance is unavailable: {e}") from e
    manifest_hash = manifest_asset.sha256
    is_match = computed_hash.lower() == manifest_hash.lower()
    embedded_chain_valid = True
    forensic = None
    phash_match = None
    if is_match:
        await file.seek(0)
        submitted_bytes = await file.read()
        embedded_chain_valid = verify_embedded_receipt(manifest, submitted_bytes)
        is_match = embedded_chain_valid
    else:
        # SHA-256 mismatch: compute pHash similarity before expensive Gemini forensics
        stored_phash = row.get("phash")
        if not stored_phash:
            # Backfill pHash on first verify: fetch original bytes via authenticated B2 SDK.
            try:
                import imagehash
                from PIL import Image
                import io as _io
                _orig_bytes = await _read_b2_asset_bytes(row)
                _orig_pil = Image.open(_io.BytesIO(_orig_bytes))
                stored_phash = str(imagehash.phash(_orig_pil))
                await db.execute("UPDATE assets SET phash = ? WHERE run_id = ?", (stored_phash, run_id))
                await db.commit()
                logger.info("phash: backfilled stored_phash %s for run %s", stored_phash, run_id)
            except Exception as _ph_err:
                logger.warning("phash: backfill via B2 failed for %s (%s)", run_id, _ph_err)

        if stored_phash:
            try:
                import imagehash
                from PIL import Image
                import io as _io
                from cache import _hamming_distance
                await file.seek(0)
                uploaded_bytes = await file.read()
                uploaded_pil = Image.open(_io.BytesIO(uploaded_bytes))
                uploaded_phash = str(imagehash.phash(uploaded_pil))
                distance = _hamming_distance(uploaded_phash, stored_phash)
                phash_match = {
                    "stored_phash": stored_phash,
                    "submitted_phash": uploaded_phash,
                    "hamming_distance": distance,
                    "similarity_pct": round((1 - distance / 64) * 100, 1),
                    "is_perceptual_match": distance <= 4,
                    "verdict": (
                        "Visually identical - file modified by compression or re-encoding"
                        if distance <= 4
                        else "Perceptually similar but visually different"
                        if distance <= 15
                        else "Visually distinct - likely a different image"
                    ),
                }
            except Exception as exc:
                logger.warning("phash: comparison failed in verify (%s)", exc)

        # Re-read file for Gemini Vision forensic analysis.
        await file.seek(0)
        submitted_bytes = await file.read()
        forensic = await _forensic_detail(row, submitted_bytes)

    return VerifyResponse(
        match=is_match,
        computed_hash=computed_hash,
        manifest_hash=manifest_hash,
        verified_at=datetime.now(timezone.utc).isoformat(),
        forensic_analysis=forensic,
        manifest_valid=embedded_chain_valid,
        phash_match=phash_match,
    )



# ── Admin ──────────────────────────────────────────────────

@router.post("/admin/reindex")
async def reindex():
    """FR-9: Rebuild the SQLite cache from canonical manifests in B2."""
    try:
        await run_rebuild_cache()
        return {"status": "reindex_completed", "message": "Cache successfully rebuilt from B2 manifests."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache rebuild failed: {e}")


@router.post("/admin/audit")
async def run_audit():
    """Full B2 integrity audit using Genblaze canonical-manifest verification."""
    try:
        report = await run_full_audit()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {e}")


# ── Observability ───────────────────────────────────────────────

@router.get("/metrics")
async def get_pipeline_metrics():
    """Add-on #10: Provider cascade metrics for the observability dashboard."""
    return await get_metrics()


# ── Provenance Badge ───────────────────────────────────────────

_BADGE_COLORS = {
    "pass":    ("#2ea44f", "#22863a", "✓ Verified"),
    "fail":    ("#d73a49", "#cb2431", "✗ Tampered"),
    None:      ("#e3a008", "#c49208", "● Unverified"),
    "unknown": ("#e3a008", "#c49208", "● Unverified"),
}


@router.get("/badge/{run_id}", response_class=Response)
async def provenance_badge(run_id: str, db: Connection = Depends(get_db)):
    """
    Add-on #11: Return a dynamically-generated SVG badge (shields.io style).
    Embeddable on any website: <img src="/badge/{run_id}" />
    """
    row = await get_asset(db, run_id)
    status = row["verify_status"] if row else None
    bg_color, border_color, label = _BADGE_COLORS.get(status, _BADGE_COLORS[None])

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="22">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#555" stop-opacity="1"/>
      <stop offset="1" stop-color="#333" stop-opacity="1"/>
    </linearGradient>
    <linearGradient id="status" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{bg_color}" stop-opacity="1"/>
      <stop offset="1" stop-color="{border_color}" stop-opacity="1"/>
    </linearGradient>
  </defs>
  <rect rx="4" width="200" height="22" fill="url(#bg)"/>
  <rect rx="4" x="90" width="110" height="22" fill="url(#status)"/>
  <rect x="86" width="4" height="22" fill="url(#status)"/>
  <text x="6" y="15" fill="#fff" font-family="DejaVu Sans,sans-serif" font-size="11"
        font-weight="bold">🛡️ Notary</text>
  <text x="96" y="15" fill="#fff" font-family="DejaVu Sans,sans-serif" font-size="11"
        font-weight="bold">{label}</text>
</svg>"""
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-cache, max-age=0"},
    )


# ── Provenance Lineage DAG ────────────────────────────────────────

@router.get("/assets/{run_id}/lineage")
async def get_asset_lineage(run_id: str, db: Connection = Depends(get_db)):
    """
    Add-on: Return the full provenance lineage DAG for an asset.
    Walks parent_run_id upward to root and downward to all descendants.
    Returns nodes (assets) and edges (parent→child) for graph rendering.
    """
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    lineage = await get_lineage(db, run_id)
    return lineage


# ── Real-Time SSE Generation Stream ──────────────────────────────

import asyncio
import json as json_mod


@router.post("/generate/stream")
async def generate_stream(req: GenerateRequest, db: Connection = Depends(get_db)):
    """Stream the same Genblaze-only provider cascade used by ``/generate``."""
    async def event_stream():
        t0 = time.monotonic()

        def emit_genblaze(stage: str, message: str, **extra):
            event = {"stage": stage, "message": message, "elapsed_ms": int((time.monotonic() - t0) * 1000), **extra}
            return f"data: {json_mod.dumps(event)}\n\n"

        try:
            policy_audit = _enforce_prompt_policy(req)
        except HTTPException as exc:
            detail = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
            yield emit_genblaze("policy_blocked", detail, policy_audit=exc.detail.get("policy_audit") if isinstance(exc.detail, dict) else None)
            return
        yield emit_genblaze("policy_reviewed", f"{policy_audit['status'].upper()} policy review completed.", policy_audit=policy_audit)

        # ── Prompt cache: skip provider cascade if exact match within TTL ──
        cached = await find_cached_generation(db, req.prompt, req.modality.value)
        if cached:
            client_result = {
                "run_id": cached["run_id"],
                "asset_url": _runtime_asset_url(cached["b2_asset_url"]),
                "manifest_uri": cached["b2_manifest_url"],
                "sha256": cached["sha256"],
                "provider": cached["provider"],
                "model": cached["model"],
            }
            yield emit_genblaze("cache_hit", f"Exact prompt match found (cached {cached['created_at'][:16]}). Skipping provider cascade.", **client_result)
            yield emit_genblaze("completed", "Served from cache!", **client_result)
            return
        # ── End cache check ──

        yield emit_genblaze("starting", "Starting the Genblaze pipeline with B2 File Lock provenance...")
        # BYOK: resolve per-request user-supplied keys (never logged, never stored)
        user_google_keys = [req.google_api_key] if req.google_api_key else None
        user_nvidia_key = req.nvidia_api_key or None
        try:
            res = await (
                run_video_pipeline(req.prompt, api_keys=user_google_keys)
                if req.modality.value == "video"
                else run_image_pipeline(req.prompt, api_keys=user_google_keys, nvidia_api_key=user_nvidia_key)
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            await record_generation(
                run_id=res["run_id"], provider=res["provider"], model=res["model"],
                modality=req.modality.value, success=True, latency_ms=latency_ms,
            )
            await _save_asset_to_db(db, req, res)
            policy_audit = await _run_and_store_policy_audit(db, req, res)
            client_result = {**res, "asset_url": _runtime_asset_url(res["asset_url"])}
            client_result["policy_audit"] = policy_audit.model_dump()
            yield emit_genblaze("completed", f"{res['provider']} Genblaze pipeline completed.", **client_result)
        except Exception as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            await record_generation(
                run_id=None, provider="unknown", model="unknown", modality=req.modality.value,
                success=False, latency_ms=latency_ms, error_type=type(exc).__name__,
            )
            yield emit_genblaze("failed", str(exc)[:240])
        return

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _save_asset_to_db(db, req, res, modality: str | None = None):
    """Helper to persist a generation result to the SQLite cache."""
    created_at = datetime.now(timezone.utc).isoformat()
    def row_for(record: dict, *, is_distributed: bool) -> dict:
        return {
            "run_id": record["run_id"],
            "parent_run_id": record.get("parent_run_id"),
            "provider": record.get("provider", "google"),
            "model": record.get("model", "unknown"),
            "modality": modality or req.modality.value,
            "prompt": req.prompt,
            "b2_asset_url": record["asset_url"],
            "b2_manifest_url": record["manifest_uri"],
            "sha256": record["sha256"],
            "created_at": created_at,
            "last_verified_at": None,
            "verify_status": None,
            "has_embedded_metadata": 1 if record.get("has_embedded_metadata") else 0,
            "has_visible_label": 1 if record.get("has_visible_label") else 0,
            "has_machine_readable_mark": 1 if record.get("has_machine_readable_mark") else 0,
            "has_audio_disclosure": 0,
            "compliance_evaluated_at": None,
            "india_compliant": None,
            "eu_compliant": None,
            "is_distributed": 1 if is_distributed else 0,
            "phash": record.get("phash"),
        }

    source_record = res.get("source_record")
    if source_record:
        await insert_asset(db, row_for(source_record, is_distributed=False))
        # The M1 receipt's parent_run_id points to the internal M0 run — this is
        # a provenance-chain detail, not a user-initiated remix.  Null it out on
        # the user-facing row so the UI doesn't show a false "Parent" link.
        m1_row = row_for(res, is_distributed=True)
        m1_row["parent_run_id"] = None
        await insert_asset(db, m1_row)
    else:
        await insert_asset(db, row_for(res, is_distributed=True))


# ── Download Original Asset (preserves C2PA) ─────────────────────

@router.get("/assets/{run_id}/download")
async def download_original_asset(run_id: str, db: Connection = Depends(get_db)):
    """
    Proxy-stream the original asset bytes from B2 with Content-Disposition:
    attachment so the browser downloads instead of rendering. This preserves
    C2PA JUMBF headers that would be stripped by right-click → Save As.
    """
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    b2_url = row["b2_asset_url"]
    if not b2_url:
        raise HTTPException(status_code=404, detail="No asset URL found for this run")

    # Determine file extension from URL or media type
    ext = "webp"
    if b2_url.endswith(".png"):
        ext = "png"
    elif b2_url.endswith(".jpg") or b2_url.endswith(".jpeg"):
        ext = "jpg"
    elif b2_url.endswith(".mp4"):
        ext = "mp4"

    media_types = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "mp4": "video/mp4"}
    content_type = media_types.get(ext, "application/octet-stream")

    try:
        asset_bytes = await _read_b2_asset_bytes(row)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch asset from storage: {exc}")

    filename = f"notary-{run_id[:8]}.{ext}"
    return Response(
        content=asset_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )

# ── Provenance Certificate ───────────────────────────────────────

@router.get("/assets/{run_id}/certificate", response_class=Response)
async def provenance_certificate(run_id: str, db: Connection = Depends(get_db)):
    """
    Add-on: Return a downloadable HTML provenance certificate.
    Self-contained, print-friendly. Two-column layout: Identity + Crypto
    attestations on top, full compliance tables on the bottom.
    """
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    manifest = manifest_data_from_db_row(row)
    report = evaluate_asset(manifest)
    india = report["regulations"][0]
    eu = report["regulations"][1]

    verify_url = f"https://notary.app/verify/{run_id}"
    created_dt = row["created_at"]

    def check_icon(status):
        return {"pass": "✓", "fail": "✗", "partial": "~", "not_applicable": "—"}.get(status, "—")

    def check_class(status):
        return {"pass": "chk-pass", "fail": "chk-fail", "partial": "chk-partial", "not_applicable": "chk-na"}.get(status, "")

    india_rows = ""
    for c in india["checks"]:
        india_rows += (
            f'<tr class="{check_class(c["status"])}">'
            f'<td class="icon-cell">{check_icon(c["status"])}</td>'
            f'<td class="rule-id">{c["requirement_id"]}</td>'
            f'<td>{c["description"]}</td>'
            f'<td class="status-cell">{c["status"].upper()}</td>'
            f'</tr>'
        )

    eu_rows = ""
    for c in eu["checks"]:
        eu_rows += (
            f'<tr class="{check_class(c["status"])}">'
            f'<td class="icon-cell">{check_icon(c["status"])}</td>'
            f'<td class="rule-id">{c["requirement_id"]}</td>'
            f'<td>{c["description"]}</td>'
            f'<td class="status-cell">{c["status"].upper()}</td>'
            f'</tr>'
        )

    overall_compliant = india["compliant"] and eu["compliant"]
    overall_label = "FULLY COMPLIANT" if overall_compliant else "PARTIALLY COMPLIANT"
    overall_class = "badge-compliant" if overall_compliant else "badge-partial"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Notary Provenance Certificate — {run_id[:8]}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 13px;
    background: #f1f3f5;
    color: #1c1e21;
    padding: 32px 24px;
    line-height: 1.5;
  }}

  /* ── Toolbar ── */
  .toolbar {{
    max-width: 860px;
    margin: 0 auto 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .toolbar-label {{
    font-size: 12px;
    color: #6b7280;
    letter-spacing: 0.03em;
  }}
  .print-btn {{
    background: #1c1e21;
    color: #fff;
    border: none;
    padding: 7px 18px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    letter-spacing: 0.02em;
  }}
  .print-btn:hover {{ background: #374151; }}

  /* ── Certificate Card ── */
  .cert {{
    max-width: 860px;
    margin: 0 auto;
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }}

  /* ── Header Band ── */
  .cert-header {{
    background: #1c1e21;
    color: #fff;
    padding: 28px 36px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
  }}
  .cert-header-left h1 {{
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin-bottom: 3px;
  }}
  .cert-header-left p {{
    font-size: 11px;
    color: #9ca3af;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }}
  .cert-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    white-space: nowrap;
  }}
  .badge-compliant {{
    background: #d1fae5;
    color: #065f46;
    border: 1px solid #6ee7b7;
  }}
  .badge-partial {{
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #fcd34d;
  }}

  /* ── Body ── */
  .cert-body {{ padding: 32px 36px; }}

  /* ── Two-Column Top Section ── */
  .top-columns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 28px;
  }}

  /* ── Section ── */
  .section {{ margin-bottom: 28px; }}
  .section-title {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6b7280;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 6px;
    margin-bottom: 14px;
  }}

  /* ── Identity Fields ── */
  .field-list {{ display: flex; flex-direction: column; gap: 10px; }}
  .field-row {{
    display: grid;
    grid-template-columns: 100px 1fr;
    gap: 8px;
    align-items: baseline;
  }}
  .field-key {{
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9ca3af;
    padding-top: 1px;
  }}
  .field-val {{
    font-size: 12.5px;
    color: #111827;
    word-break: break-all;
    line-height: 1.45;
  }}
  .mono {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; }}

  /* ── Crypto Attestations ── */
  .attest-list {{ display: flex; flex-direction: column; gap: 8px; }}
  .attest-row {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 9px 12px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
  }}
  .attest-icon {{
    font-size: 13px;
    line-height: 1;
    margin-top: 1px;
    flex-shrink: 0;
  }}
  .attest-label {{
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    margin-bottom: 1px;
  }}
  .attest-val {{
    font-size: 12px;
    color: #111827;
    font-family: 'JetBrains Mono', monospace;
  }}
  .attest-row.ok .attest-icon {{ color: #059669; }}
  .attest-row.ok {{ border-left: 3px solid #059669; }}
  .attest-row.info .attest-icon {{ color: #6366f1; }}
  .attest-row.info {{ border-left: 3px solid #6366f1; }}

  /* ── Compliance Score ── */
  .score-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }}
  .score-pill {{
    display: inline-block;
    background: #1c1e21;
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    padding: 3px 12px;
    border-radius: 20px;
    font-family: 'JetBrains Mono', monospace;
  }}

  /* ── Compliance Tables ── */
  table {{ width: 100%; border-collapse: collapse; font-size: 11.5px; }}
  thead tr {{ background: #f9fafb; }}
  th {{
    text-align: left;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9ca3af;
    padding: 7px 10px;
    border-bottom: 1px solid #e5e7eb;
  }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }}
  .icon-cell {{ width: 28px; font-size: 13px; text-align: center; }}
  .rule-id {{ font-family: 'JetBrains Mono', monospace; font-size: 10.5px; width: 110px; color: #374151; white-space: nowrap; }}
  .status-cell {{ font-weight: 700; font-size: 10px; white-space: nowrap; width: 80px; }}
  tr.chk-pass .icon-cell {{ color: #059669; }}
  tr.chk-pass .status-cell {{ color: #059669; }}
  tr.chk-fail .icon-cell {{ color: #dc2626; }}
  tr.chk-fail .status-cell {{ color: #dc2626; }}
  tr.chk-partial .icon-cell {{ color: #d97706; }}
  tr.chk-partial .status-cell {{ color: #d97706; }}
  tr.chk-na .icon-cell, tr.chk-na .status-cell {{ color: #9ca3af; }}

  /* ── Footer ── */
  .cert-footer {{
    background: #f9fafb;
    border-top: 1px solid #e5e7eb;
    padding: 16px 36px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .cert-footer p {{ font-size: 11px; color: #9ca3af; }}
  .cert-footer a {{ color: #4b5563; text-decoration: underline; }}

  /* ── Print ── */
  @media print {{
    .toolbar {{ display: none !important; }}
    body {{ background: #fff; padding: 0; }}
    .cert {{ border: none; border-radius: 0; box-shadow: none; max-width: 100%; }}
    .cert-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>

<div class="toolbar no-print">
  <span class="toolbar-label">Notary Provenance Certificate — {run_id[:8]}</span>
  <button class="print-btn" onclick="window.print()">Download / Save as PDF</button>
</div>

<div class="cert">

  <!-- Header -->
  <div class="cert-header">
    <div class="cert-header-left">
      <h1>Notary — Provenance Certificate</h1>
      <p>Immutable AI Content Provenance &amp; Regulatory Compliance Record</p>
    </div>
    <span class="cert-badge {overall_class}">{overall_label}</span>
  </div>

  <div class="cert-body">

    <!-- Two-column top: Identity left, Crypto right -->
    <div class="top-columns">

      <!-- Asset Identity -->
      <div class="section">
        <div class="section-title">Asset Identity</div>
        <div class="field-list">
          <div class="field-row">
            <span class="field-key">Run ID</span>
            <span class="field-val mono">{run_id}</span>
          </div>
          <div class="field-row">
            <span class="field-key">Created</span>
            <span class="field-val">{created_dt}</span>
          </div>
          <div class="field-row">
            <span class="field-key">Provider</span>
            <span class="field-val">{row['provider']}</span>
          </div>
          <div class="field-row">
            <span class="field-key">Model</span>
            <span class="field-val mono">{row['model']}</span>
          </div>
          <div class="field-row">
            <span class="field-key">Prompt</span>
            <span class="field-val">{row['prompt']}</span>
          </div>
          <div class="field-row">
            <span class="field-key">SHA-256</span>
            <span class="field-val mono">{row['sha256']}</span>
          </div>
        </div>
      </div>

      <!-- Cryptographic Attestations -->
      <div class="section">
        <div class="section-title">Cryptographic Attestations</div>
        <div class="attest-list">
          <div class="attest-row ok">
            <span class="attest-icon">&#10003;</span>
            <div>
              <div class="attest-label">Ed25519 Manifest Signature</div>
              <div class="attest-val">Independent trust anchor</div>
            </div>
          </div>
          <div class="attest-row ok">
            <span class="attest-icon">&#10003;</span>
            <div>
              <div class="attest-label">C2PA Content Credentials</div>
              <div class="attest-val">ES256 JUMBF — contentcredentials.org</div>
            </div>
          </div>
          <div class="attest-row ok">
            <span class="attest-icon">&#10003;</span>
            <div>
              <div class="attest-label">B2 Object Lock</div>
              <div class="attest-val">COMPLIANCE mode — WORM immutable</div>
            </div>
          </div>
          <div class="attest-row ok">
            <span class="attest-icon">&#10003;</span>
            <div>
              <div class="attest-label">Visible Watermark</div>
              <div class="attest-val">AI-Generated · Notary Verified</div>
            </div>
          </div>
          <div class="attest-row info">
            <span class="attest-icon">&#9432;</span>
            <div>
              <div class="attest-label">Claim Generator</div>
              <div class="attest-val">Notary/3.0.0 (C2PA; ES256)</div>
            </div>
          </div>
          <div class="attest-row info">
            <span class="attest-icon">&#9432;</span>
            <div>
              <div class="attest-label">Digital Source Type</div>
              <div class="attest-val">trainedAlgorithmicMedia (IPTC)</div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- India Compliance Table -->
    <div class="section">
      <div class="score-header">
        <div class="section-title" style="margin-bottom:0;border:none">India IT (Intermediary Guidelines) Amendment Rules, 2026</div>
        <span class="score-pill">{india['passed']}/{india['total']}</span>
      </div>
      <table>
        <thead><tr><th></th><th>Rule</th><th>Requirement</th><th>Result</th></tr></thead>
        <tbody>{india_rows}</tbody>
      </table>
    </div>

    <!-- EU Compliance Table -->
    <div class="section">
      <div class="score-header">
        <div class="section-title" style="margin-bottom:0;border:none">EU AI Act — Article 50: Transparency Obligations</div>
        <span class="score-pill">{eu['passed']}/{eu['total']}</span>
      </div>
      <table>
        <thead><tr><th></th><th>Rule</th><th>Requirement</th><th>Result</th></tr></thead>
        <tbody>{eu_rows}</tbody>
      </table>
    </div>

  </div>

  <!-- Footer -->
  <div class="cert-footer">
    <p>Generated by <strong>Notary</strong> — powered by Backblaze B2 Object Lock &amp; Genblaze.</p>
    <p>Verify: <a href="{verify_url}">{verify_url}</a></p>
    <p>Issued {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
  </div>

</div>

<script>
  window.addEventListener('DOMContentLoaded', () => {{
    setTimeout(() => {{ window.print(); }}, 350);
  }});
</script>
</body>
</html>"""

    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Content-Disposition": f'inline; filename="notary-certificate-{run_id[:8]}.pdf"',
        },
    )
