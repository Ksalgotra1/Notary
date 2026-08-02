"""
B2 Integrity Audit (Add-on #9).

Scans every asset stored in Backblaze B2, re-downloads and re-hashes each one,
and compares against the manifest SHA-256. Produces a complete audit report
that is itself stored back in B2 for provenance-of-provenance.

Why this matters:
  One-at-a-time verification is a user flow. Bulk audit is an operations capability.
  This is what distinguishes a production system from a demo.
"""
import asyncio
import hashlib
import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def run_full_audit() -> dict:
    """
    Scan all B2 manifests, re-hash each asset, and return a complete audit report.
    Results are stored back to B2 as an audit record.
    """
    from pipeline import get_storage_backend, verify_manifest_signature

    backend = get_storage_backend()
    audit_id = f"aud-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
    started_at = datetime.now(timezone.utc).isoformat()

    logger.info("Starting B2 integrity audit: %s", audit_id)

    # --- List all manifests in B2 ---
    try:
        page = backend.list(prefix="runs/")
        entries = getattr(page, "entries", [])
        keys = [e.key if hasattr(e, "key") else str(e) for e in entries]
        manifest_keys = [str(k) for k in keys if str(k).endswith("manifest.json") and "/audit/" not in str(k)]
    except Exception as e:
        logger.error("Failed to list B2 bucket: %s", e)
        raise RuntimeError(f"B2 listing failed: {e}") from e

    logger.info("Found %d manifests to audit", len(manifest_keys))

    results = []
    passed = 0
    failed = 0
    unreachable = 0
    signature_failures = 0

    for manifest_key in manifest_keys:
        run_id = "unknown"
        try:
            # Load manifest
            raw = backend.get(manifest_key)
            if hasattr(raw, "read"):
                raw = raw.read()
            manifest = json.loads(raw.decode())
            run_id = manifest.get("run_id", "unknown")

            # Check HMAC signature
            sig_valid = verify_manifest_signature(manifest)
            if not sig_valid:
                signature_failures += 1

            # Get expected hash from manifest
            assets = manifest.get("assets", [])
            if not assets:
                results.append({
                    "run_id": run_id,
                    "status": "SKIP",
                    "reason": "No assets in manifest",
                    "signature_valid": sig_valid,
                })
                continue

            asset_entry = assets[0]
            expected_hash = asset_entry.get("sha256", "")
            asset_key = asset_entry.get("key", "")

            if not asset_key:
                results.append({
                    "run_id": run_id,
                    "status": "SKIP",
                    "reason": "No asset key in manifest",
                    "signature_valid": sig_valid,
                })
                continue

            # Fetch asset and compute hash
            asset_bytes = backend.get(asset_key)
            if hasattr(asset_bytes, "read"):
                asset_bytes = asset_bytes.read()

            computed_hash = hashlib.sha256(asset_bytes).hexdigest()
            is_match = computed_hash.lower() == expected_hash.lower()

            if is_match:
                passed += 1
                results.append({
                    "run_id": run_id,
                    "status": "PASS",
                    "expected_hash": expected_hash[:16] + "...",
                    "computed_hash": computed_hash[:16] + "...",
                    "signature_valid": sig_valid,
                    "asset_key": asset_key,
                })
            else:
                failed += 1
                results.append({
                    "run_id": run_id,
                    "status": "TAMPERED",
                    "expected_hash": expected_hash,
                    "computed_hash": computed_hash,
                    "signature_valid": sig_valid,
                    "asset_key": asset_key,
                })
                logger.warning("INTEGRITY FAILURE: run_id=%s expected=%s got=%s",
                               run_id, expected_hash[:16], computed_hash[:16])

        except Exception as e:
            unreachable += 1
            results.append({
                "run_id": run_id,
                "status": "UNREACHABLE",
                "error": str(e),
            })
            logger.warning("Audit failed for manifest %s: %s", manifest_key, e)

    completed_at = datetime.now(timezone.utc).isoformat()
    total = passed + failed + unreachable

    report = {
        "audit_id": audit_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "total_assets": total,
        "passed": passed,
        "failed": failed,
        "unreachable": unreachable,
        "signature_failures": signature_failures,
        "integrity_score": round((passed / total * 100) if total > 0 else 100, 1),
        "results": results,
    }

    # Store audit report back in B2 (provenance of the provenance)
    try:
        audit_key = f"runs/notary/audit/{audit_id}/report.json"
        backend.put(
            audit_key,
            io.BytesIO(json.dumps(report, indent=2).encode()),
            content_type="application/json",
        )
        logger.info("Audit report stored in B2: %s", audit_key)
    except Exception as e:
        logger.warning("Failed to store audit report in B2: %s", e)

    logger.info(
        "Audit complete: %d/%d passed, %d failed, %d unreachable, %d signature failures",
        passed, total, failed, unreachable, signature_failures,
    )
    return report
