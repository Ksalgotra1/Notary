"""Operational B2 integrity audit using Genblaze canonical manifests."""
import hashlib
import io
import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def run_full_audit() -> dict:
    """Verify every paginated Genblaze manifest and its output assets in B2."""
    from genblaze_core.models.manifest import parse_manifest
    from pipeline import get_b2_backend, verify_embedded_receipt

    backend = get_b2_backend()
    audit_id = f"aud-{datetime.now(timezone.utc):%Y-%m-%d-%H%M%S}-{str(uuid.uuid4())[:8]}"
    manifest_keys = []
    token = None
    while True:
        page = backend.list(prefix="notary/runs/", continuation_token=token)
        manifest_keys.extend(entry.key for entry in page.entries if entry.key.endswith("manifest.json"))
        token = page.next_token
        if not token:
            break

    results = []
    passed = failed = unreachable = manifest_failures = 0
    for key in manifest_keys:
        try:
            manifest = parse_manifest(json.loads(backend.get(key).decode("utf-8")))
            manifest_ok = manifest.verify_hash()
            if not manifest_ok:
                manifest_failures += 1
            assets = [asset for step in manifest.run.steps for asset in step.assets]
            asset_ok = bool(assets)
            for asset in assets:
                asset_key = backend.key_from_url(asset.url)
                if not asset_key or not asset.sha256:
                    asset_ok = False
                    continue
                asset_bytes = backend.get(asset_key)
                asset_ok = asset_ok and hashlib.sha256(asset_bytes).hexdigest() == asset.sha256
                if manifest.run.metadata.get("source_manifest_uri"):
                    asset_ok = asset_ok and verify_embedded_receipt(manifest, asset_bytes)
            status = "PASS" if manifest_ok and asset_ok else "TAMPERED"
            passed += status == "PASS"
            failed += status != "PASS"
            results.append({"run_id": manifest.run.run_id, "status": status, "manifest_valid": manifest_ok, "assets_valid": asset_ok})
        except Exception as exc:
            unreachable += 1
            results.append({"run_id": "unknown", "status": "UNREACHABLE", "error": str(exc)})

    total = passed + failed + unreachable
    report = {
        "audit_id": audit_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_assets": total,
        "passed": passed,
        "failed": failed,
        "unreachable": unreachable,
        "manifest_failures": manifest_failures,
        "integrity_score": round((passed / total * 100) if total else 100, 1),
        "results": results,
    }
    backend.put(
        f"notary/audits/{audit_id}/report.json",
        io.BytesIO(json.dumps(report, indent=2).encode("utf-8")),
        content_type="application/json",
    )
    return report
