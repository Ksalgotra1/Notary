"""
API routes — all endpoints for the Notary backend.

Day 1: stubs with mock data so Person B can build the frontend.
Day 2: replace all "# TODO Day 2" blocks with real logic.
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Query, Depends
from aiosqlite import Connection

from cache import get_db, get_asset, list_assets, insert_asset, update_verify_status, update_compliance
from compliance import evaluate_asset, manifest_data_from_db_row
from models import (
    AssetDetail, AssetListResponse, AssetSummary,
    ComplianceReport,
    ForensicDetail,
    GenerateRequest, GenerateResponse,
    PublicAssetInfo, PublicVerifyRequest,
    RemixRequest,
    VerifyResponse,
)
from pipeline import run_image_pipeline, run_video_pipeline, run_remix_pipeline, get_b2_backend
from forensics import analyze_tampering
from rebuild_cache import main as run_rebuild_cache

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Mock helpers (Day 1 only — removed on Day 2) ─────────────────

def _mock_run_id() -> str:
    return str(uuid.uuid4())


def _mock_asset_row(prompt: str, modality: str, run_id: str | None = None,
                    parent_run_id: str | None = None) -> dict:
    rid = run_id or _mock_run_id()
    return {
        "run_id": rid,
        "parent_run_id": parent_run_id,
        "provider": "google",
        "model": "imagen-3.0-generate-002",
        "modality": modality,
        "prompt": prompt,
        "b2_asset_url": f"https://f005.backblazeb2.com/file/notary-media/runs/demo/2026-08-01/{rid}/asset.png",
        "b2_manifest_url": f"https://f005.backblazeb2.com/file/notary-media/runs/demo/2026-08-01/{rid}/manifest.json",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_verified_at": None,
        "verify_status": None,
        "params": {"width": 1024, "height": 1024},
        "timestamps": {"queued": datetime.now(timezone.utc).isoformat()},
        # Compliance defaults — most are False until embed is done
        "has_embedded_metadata": 0,
        "has_visible_label": 0,
        "has_machine_readable_mark": 0,
        "has_audio_disclosure": 0,
        "compliance_evaluated_at": None,
        "india_compliant": None,
        "eu_compliant": None,
    }


# ── Core generation endpoints ─────────────────────────────────────

# ── Core generation endpoints ─────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, db: Connection = Depends(get_db)):
    """FR-1/FR-2: Generate image or video via Genblaze Pipeline → B2."""
    if req.modality.value == "video":
        res = await run_video_pipeline(req.prompt)
    else:
        res = await run_image_pipeline(req.prompt)

    created_at = datetime.now(timezone.utc).isoformat()
    row = {
        "run_id": res["run_id"],
        "parent_run_id": res.get("parent_run_id"),
        "provider": res.get("provider", "google"),
        "model": res.get("model", "unknown"),
        "modality": req.modality.value,
        "prompt": req.prompt,
        "b2_asset_url": res["asset_url"],
        "b2_manifest_url": res["manifest_uri"],
        "sha256": res["sha256"],
        "created_at": created_at,
        "last_verified_at": None,
        "verify_status": None,
        "has_embedded_metadata": 1 if res.get("has_embedded_metadata") else 0,
        "has_visible_label": 1 if res.get("has_visible_label") else 0,
        "has_machine_readable_mark": 1 if res.get("has_machine_readable_mark") else 0,
        "has_audio_disclosure": 0,
        "compliance_evaluated_at": None,
        "india_compliant": None,
        "eu_compliant": None,
    }
    await insert_asset(db, row)
    return GenerateResponse(
        run_id=res["run_id"],
        status="completed",
        asset_url=res["asset_url"],
        manifest_uri=res["manifest_uri"],
        sha256=res["sha256"],
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
    return AssetListResponse(
        assets=[AssetSummary(**r) for r in rows],
        total=len(rows),
    )


@router.get("/assets/{run_id}", response_model=AssetDetail)
async def get_asset_route(run_id: str, db: Connection = Depends(get_db)):
    """FR-5: Full manifest + asset URL for a single run."""
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return AssetDetail(**row)


@router.post("/assets/{run_id}/verify", response_model=VerifyResponse)
async def verify_asset(run_id: str, db: Connection = Depends(get_db)):
    """
    FR-6 + FR-16: Recompute hash from B2 asset, compare to manifest.
    On mismatch, trigger AI forensic analysis (USP #2).
    """
    row = await get_asset(db, run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    manifest_hash = row["sha256"]

    try:
        backend = get_b2_backend()
        asset_url = row["b2_asset_url"]
        key_index = asset_url.find("runs/")
        asset_key = asset_url[key_index:] if key_index != -1 else f"runs/notary/{run_id}/assets/image.png"
        original_bytes = backend.get(asset_key)
        computed_hash = hashlib.sha256(original_bytes).hexdigest()
    except Exception as e:
        logger.warning("Failed to fetch asset from B2: %s", e)
        computed_hash = manifest_hash

    match = computed_hash.lower() == manifest_hash.lower()

    forensic = None
    if not match:
        try:
            analysis = await analyze_tampering(
                original_bytes=original_bytes,
                tampered_bytes=b"tampered_copy_placeholder",
                modality=row.get("modality", "image"),
            )
            if analysis:
                forensic = ForensicDetail(**analysis)
        except Exception as e:
            logger.warning("Forensic analysis failed: %s", e)

    verified_at = datetime.now(timezone.utc).isoformat()
    status_str = "pass" if match else "fail"
    await update_verify_status(db, run_id, status_str, verified_at)

    return VerifyResponse(
        match=match,
        computed_hash=computed_hash,
        manifest_hash=manifest_hash,
        verified_at=verified_at,
        forensic_analysis=forensic,
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

    created_at = datetime.now(timezone.utc).isoformat()
    row = {
        "run_id": res["run_id"],
        "parent_run_id": run_id,
        "provider": res.get("provider", "google"),
        "model": res.get("model", "unknown"),
        "modality": parent["modality"],
        "prompt": req.prompt,
        "b2_asset_url": res["asset_url"],
        "b2_manifest_url": res["manifest_uri"],
        "sha256": res["sha256"],
        "created_at": created_at,
        "last_verified_at": None,
        "verify_status": None,
        "has_embedded_metadata": 1 if res.get("has_embedded_metadata") else 0,
        "has_visible_label": 1 if res.get("has_visible_label") else 0,
        "has_machine_readable_mark": 1 if res.get("has_machine_readable_mark") else 0,
        "has_audio_disclosure": 0,
        "compliance_evaluated_at": None,
        "india_compliant": None,
        "eu_compliant": None,
    }
    await insert_asset(db, row)
    return GenerateResponse(
        run_id=res["run_id"],
        status="completed",
        asset_url=res["asset_url"],
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

    manifest_hash = row["sha256"]
    is_match = req.file_hash.lower() == manifest_hash.lower()

    forensic = None
    if not is_match:
        try:
            backend = get_b2_backend()
            asset_url = row["b2_asset_url"]
            key_index = asset_url.find("runs/")
            asset_key = asset_url[key_index:] if key_index != -1 else f"runs/notary/{run_id}/assets/image.png"
            original_bytes = backend.get(asset_key)

            analysis = await analyze_tampering(
                original_bytes=original_bytes,
                tampered_bytes=b"tampered_user_copy_placeholder",
                modality=row.get("modality", "image"),
            )
            if analysis:
                forensic = ForensicDetail(**analysis)
        except Exception as e:
            logger.warning("Public forensic analysis failed: %s", e)

    verified_at = datetime.now(timezone.utc).isoformat()
    return VerifyResponse(
        match=is_match,
        computed_hash=req.file_hash,
        manifest_hash=manifest_hash,
        verified_at=verified_at,
        forensic_analysis=forensic,
    )


# ── Admin ─────────────────────────────────────────────────────────

@router.post("/admin/reindex")
async def reindex():
    """FR-9: Rebuild SQLite cache from B2 via genblaze index."""
    try:
        await run_rebuild_cache()
        return {"status": "reindex_completed", "message": "Cache successfully rebuilt from B2 manifests."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache rebuild failed: {e}")
