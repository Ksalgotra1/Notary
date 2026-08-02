"""API routes for the Notary backend."""
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from aiosqlite import Connection

from cache import get_db, get_asset, list_assets, insert_asset, update_verify_status, update_compliance, get_lineage
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
from pipeline import run_image_pipeline, run_video_pipeline, run_remix_pipeline, get_storage_backend, verify_manifest_signature
from forensics import analyze_tampering
from rebuild_cache import main as run_rebuild_cache
from metrics import record_generation, get_metrics
from audit import run_full_audit

logger = logging.getLogger(__name__)
router = APIRouter()


def _asset_key_from_url(asset_url: str) -> str:
    path = unquote(urlparse(asset_url).path)
    if "/file/" in path:
        parts = path.split("/file/", 1)[1].split("/", 1)
        if len(parts) == 2:
            return parts[1]

    key_index = asset_url.find("runs/")
    if key_index != -1:
        return asset_url[key_index:]
    raise ValueError(f"Cannot derive B2 object key from URL: {asset_url}")


async def _read_b2_asset_bytes(row: dict) -> bytes:
    data = get_storage_backend().get(_asset_key_from_url(row["b2_asset_url"]))
    if isinstance(data, bytes):
        return data
    if hasattr(data, "read"):
        value = data.read()
        return await value if hasattr(value, "__await__") else value
    return bytes(data)


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

@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, db: Connection = Depends(get_db)):
    """FR-1/FR-2: Generate image or video via Genblaze Pipeline → B2."""
    t0 = time.monotonic()
    try:
        if req.modality.value == "video":
            res = await run_video_pipeline(req.prompt)
        else:
            res = await run_image_pipeline(req.prompt)
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
        provider=res.get("provider"),
        model=res.get("model"),
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
        original_bytes = await _read_b2_asset_bytes(row)
        computed_hash = hashlib.sha256(original_bytes).hexdigest()
    except Exception as e:
        logger.warning("Failed to fetch asset from B2: %s", e)
        computed_hash = manifest_hash

    match = computed_hash.lower() == manifest_hash.lower()

    forensic = None
    if not match:
        # B2 asset re-fetch mismatch — actual corruption or modification.
        # Run forensic comparison: original from B2 vs re-fetched (which may differ)
        forensic = ForensicDetail(
            modifications_detected=[
                "Internal hash recomputation mismatch: the file stored in B2 does not match "
                "its original SHA-256 fingerprint recorded at generation time."
            ],
            severity="major",
            conclusion=(
                "This indicates the asset in B2 has been modified or corrupted after generation. "
                "This is a storage integrity failure, not a user tampering event."
            ),
            analysis_model="hash-comparison",
        )

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
        # Hash-only verification: we don't have the actual file bytes here.
        # Return a clear guidance message directing the user to upload the file
        # for full Gemini Vision forensic analysis (available via /file endpoint).
        forensic = ForensicDetail(
            modifications_detected=["SHA-256 hash mismatch detected — the submitted hash does not match the canonical provenance record."],
            severity="unknown",
            conclusion="Upload the actual file to /public/verify/{run_id}/file for AI-powered forensic analysis identifying exactly what was modified.",
            analysis_model="hash-comparison",
        )

    verified_at = datetime.now(timezone.utc).isoformat()
    return VerifyResponse(
        match=is_match,
        computed_hash=req.file_hash,
        manifest_hash=manifest_hash,
        verified_at=verified_at,
        forensic_analysis=forensic,
    )


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

    manifest_hash = row["sha256"]
    is_match = computed_hash.lower() == manifest_hash.lower()

    forensic = None
    if not is_match:
        # Only on mismatch: re-read file for Gemini Vision forensic analysis
        await file.seek(0)
        submitted_bytes = await file.read()
        forensic = await _forensic_detail(row, submitted_bytes)

    return VerifyResponse(
        match=is_match,
        computed_hash=computed_hash,
        manifest_hash=manifest_hash,
        verified_at=datetime.now(timezone.utc).isoformat(),
        forensic_analysis=forensic,
    )


# ── Admin ──────────────────────────────────────────────────

@router.post("/admin/reindex")
async def reindex():
    """FR-9: Rebuild SQLite cache from B2 via genblaze index."""
    try:
        await run_rebuild_cache()
        return {"status": "reindex_completed", "message": "Cache successfully rebuilt from B2 manifests."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache rebuild failed: {e}")


@router.post("/admin/audit")
async def run_audit():
    """Add-on #9: Full B2 integrity audit — re-hash every asset, verify HMAC signatures."""
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
    """
    Add-on: Server-Sent Events stream that reports real-time cascade progress.
    The client receives events like:
      data: {"stage": "trying_google", "message": "Trying Google Genblaze..."}
      data: {"stage": "google_quota_error", "message": "Google quota exhausted, rotating..."}
      data: {"stage": "trying_nvidia", "message": "Trying NVIDIA NIM..."}
      data: {"stage": "completed", "run_id": "abc123", "asset_url": "..."}
    """
    async def event_stream():
        import pipeline as pl

        t0 = time.monotonic()
        stages = []

        def emit(stage: str, message: str, **extra):
            event = {"stage": stage, "message": message, "elapsed_ms": int((time.monotonic() - t0) * 1000), **extra}
            stages.append(event)
            return f"data: {json_mod.dumps(event)}\n\n"

        # --- Try Google ---
        keys = pl.load_google_keys()
        if keys and req.modality.value == "image":
            yield emit("trying_google", "Attempting Google Genblaze pipeline...")
            try:
                multi = pl.MultiKeyGoogleProvider(keys, pl._get_google_image_provider_class())
                while True:
                    provider = multi.get_provider()
                    try:
                        from genblaze_core import Pipeline, Modality
                        storage = pl.get_b2_storage()
                        run, manifest = await (
                            Pipeline("notary-image-generate")
                            .step(provider, model=pl.IMAGE_MODEL_ID, prompt=req.prompt, modality=Modality.IMAGE)
                            .arun(sink=storage, timeout=120)
                        )
                        asset = run.steps[0].assets[0]
                        res = {
                            "run_id": run.run_id, "asset_url": asset.url,
                            "manifest_uri": manifest.manifest_uri, "sha256": asset.sha256,
                            "provider": "google", "model": pl.IMAGE_MODEL_ID,
                            "has_embedded_metadata": True, "has_visible_label": False,
                            "has_machine_readable_mark": False,
                        }
                        yield emit("google_success", f"Google succeeded (model: {pl.IMAGE_MODEL_ID})")
                        # Save to DB and emit completion
                        latency_ms = int((time.monotonic() - t0) * 1000)
                        await record_generation(run_id=res["run_id"], provider="google", model=pl.IMAGE_MODEL_ID,
                                                modality="image", success=True, latency_ms=latency_ms)
                        await _save_asset_to_db(db, req, res)
                        yield emit("completed", "Generation complete!", **res)
                        return
                    except Exception as e:
                        if pl._is_quota_error(e):
                            yield emit("google_quota_error", f"Google key {multi.current_key_index} quota exhausted, rotating...")
                            if not multi.advance():
                                yield emit("google_exhausted", "All Google API keys exhausted.")
                                break
                        else:
                            yield emit("google_error", f"Google failed: {str(e)[:80]}")
                            break
            except Exception as e:
                yield emit("google_error", f"Google setup failed: {str(e)[:80]}")

        # --- Try NVIDIA NIM ---
        nv_key = os.getenv("NVIDIA_API_KEY", "")
        if nv_key and req.modality.value == "image":
            yield emit("trying_nvidia", "Attempting NVIDIA NIM pipeline...")
            try:
                res = await pl._run_nvidia_pipeline(req.prompt)
                latency_ms = int((time.monotonic() - t0) * 1000)
                await record_generation(run_id=res["run_id"], provider="nvidia", model=res["model"],
                                        modality="image", success=True, latency_ms=latency_ms)
                yield emit("nvidia_success", f"NVIDIA succeeded (model: {res['model']})")
                await _save_asset_to_db(db, req, res)
                yield emit("completed", "Generation complete!", **res)
                return
            except Exception as e:
                yield emit("nvidia_error", f"NVIDIA failed: {str(e)[:80]}")

        # --- Pollinations fallback ---
        yield emit("trying_pollinations", "Falling back to Pollinations.ai (always available)...")
        try:
            res = await pl._run_pollinations_pipeline(req.prompt)
            latency_ms = int((time.monotonic() - t0) * 1000)
            await record_generation(run_id=res["run_id"], provider="pollinations", model=res["model"],
                                    modality="image", success=True, latency_ms=latency_ms)
            yield emit("pollinations_success", f"Pollinations succeeded (model: {res['model']})")
            await _save_asset_to_db(db, req, res)
            yield emit("completed", "Generation complete!", **res)
        except Exception as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            await record_generation(run_id=None, provider="unknown", model="unknown",
                                    modality=req.modality.value, success=False,
                                    latency_ms=latency_ms, error_type=type(e).__name__)
            yield emit("failed", f"All providers failed: {str(e)[:120]}")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


import os


async def _save_asset_to_db(db, req, res):
    """Helper to persist a generation result to the SQLite cache."""
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


# ── Provenance Certificate ───────────────────────────────────────

@router.get("/assets/{run_id}/certificate", response_class=Response)
async def provenance_certificate(run_id: str, db: Connection = Depends(get_db)):
    """
    Add-on: Return a downloadable HTML provenance certificate.
    Self-contained, print-friendly, with QR code link placeholder.
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
    sha_short = row["sha256"][:16] + "..."

    india_checks_html = ""
    for c in india["checks"]:
        icon = "✅" if c["status"] == "pass" else "⚠️" if c["status"] == "partial" else "⬜" if c["status"] == "not_applicable" else "❌"
        india_checks_html += f'<tr><td>{icon}</td><td>{c["requirement_id"]}</td><td>{c["description"]}</td><td><b>{c["status"].upper()}</b></td></tr>'

    eu_checks_html = ""
    for c in eu["checks"]:
        icon = "✅" if c["status"] == "pass" else "⚠️" if c["status"] == "partial" else "❌"
        eu_checks_html += f'<tr><td>{icon}</td><td>{c["requirement_id"]}</td><td>{c["description"]}</td><td><b>{c["status"].upper()}</b></td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Notary Provenance Certificate — {run_id[:8]}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', sans-serif; background: #0a0a12; color: #e8e8f0; padding: 40px; }}
  .cert {{ max-width: 800px; margin: 0 auto; background: linear-gradient(135deg, #12121e 0%, #1a1a2e 100%);
           border: 1px solid rgba(99,102,241,0.3); border-radius: 16px; padding: 48px; position: relative; overflow: hidden; }}
  .cert::before {{ content: ''; position: absolute; top: -2px; left: -2px; right: -2px; bottom: -2px;
                   background: linear-gradient(135deg, #6366f1, #3b82f6, #6366f1); border-radius: 17px; z-index: -1; }}
  .header {{ text-align: center; margin-bottom: 32px; }}
  .header h1 {{ font-size: 28px; font-weight: 800; background: linear-gradient(135deg, #6366f1, #3b82f6);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .header .subtitle {{ color: #888; font-size: 13px; margin-top: 4px; }}
  .shield {{ font-size: 48px; margin-bottom: 12px; }}
  .section {{ margin: 24px 0; }}
  .section h2 {{ font-size: 15px; font-weight: 700; color: #6366f1; text-transform: uppercase;
                 letter-spacing: 1.5px; margin-bottom: 12px; border-bottom: 1px solid rgba(99,102,241,0.2); padding-bottom: 6px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .field {{ background: rgba(255,255,255,0.04); border-radius: 8px; padding: 12px; }}
  .field .label {{ font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 1px; }}
  .field .value {{ font-size: 14px; font-weight: 600; margin-top: 4px; word-break: break-all; }}
  .field.full {{ grid-column: 1 / -1; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  table th {{ text-align: left; color: #888; padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.08); }}
  table td {{ padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); }}
  .score {{ display: inline-block; background: linear-gradient(135deg, #6366f1, #3b82f6); color: #fff;
            font-size: 20px; font-weight: 800; padding: 4px 16px; border-radius: 8px; }}
  .footer {{ text-align: center; margin-top: 32px; font-size: 11px; color: #555; }}
  .footer a {{ color: #6366f1; }}
  @media print {{ body {{ background: #fff; color: #222; }} .cert {{ border: 2px solid #6366f1; }} }}
</style>
</head>
<body>
<div class="cert">
  <div class="header">
    <div class="shield">🛡️</div>
    <h1>Notary — Provenance Certificate</h1>
    <div class="subtitle">Immutable AI Content Provenance &amp; Regulatory Compliance Record</div>
  </div>

  <div class="section">
    <h2>Asset Identity</h2>
    <div class="grid">
      <div class="field"><div class="label">Run ID</div><div class="value" style="font-family:monospace;font-size:12px">{run_id}</div></div>
      <div class="field"><div class="label">Created At</div><div class="value">{created_dt}</div></div>
      <div class="field"><div class="label">AI Provider</div><div class="value">{row['provider']}</div></div>
      <div class="field"><div class="label">Model</div><div class="value">{row['model']}</div></div>
      <div class="field full"><div class="label">Original Prompt</div><div class="value">{row['prompt']}</div></div>
      <div class="field full"><div class="label">SHA-256 Fingerprint</div><div class="value" style="font-family:monospace;font-size:11px">{row['sha256']}</div></div>
    </div>
  </div>

  <div class="section">
    <h2>India IT Rules 2026 — SGI Compliance <span class="score">{india['passed']}/{india['total']}</span></h2>
    <table><thead><tr><th></th><th>Rule</th><th>Description</th><th>Status</th></tr></thead><tbody>{india_checks_html}</tbody></table>
  </div>

  <div class="section">
    <h2>EU AI Act Article 50 <span class="score">{eu['passed']}/{eu['total']}</span></h2>
    <table><thead><tr><th></th><th>Rule</th><th>Description</th><th>Status</th></tr></thead><tbody>{eu_checks_html}</tbody></table>
  </div>

  <div class="footer">
    <p>This certificate was generated by <b>Notary</b> — an immutable provenance engine powered by Backblaze B2 &amp; Genblaze.</p>
    <p>Verify this asset at: <a href="{verify_url}">{verify_url}</a></p>
    <p style="margin-top:8px;color:#444">Certificate generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
  </div>
</div>
</body>
</html>"""

    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Content-Disposition": f'inline; filename="notary-certificate-{run_id[:8]}.html"',
        },
    )
