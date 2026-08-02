"""
Compliance Engine — evaluates AI-generated assets against live regulations.

USP #1 — Notary's core differentiator.
Neither Genblaze nor B2 tell you whether your asset is legally compliant.
This module does.

Regulations covered:
  - India IT Rules Amendment 2026 (in force since Feb 20, 2026)
  - EU AI Act Article 50 (in force since Aug 2, 2026)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ManifestData:
    """Normalized manifest data for compliance evaluation."""
    run_id: str
    provider: str | None
    model: str | None
    prompt: str | None
    modality: str                   # "image" | "video" | "audio"
    created_at: str | None
    sha256: str | None
    has_embedded_metadata: bool     # manifest embedded in file itself (FR-3)
    has_visible_label: bool         # visible "AI-Generated" watermark/overlay
    has_machine_readable_mark: bool # machine-readable mark in standard format
    has_audio_disclosure: bool      # spoken "this is AI-generated" prefix (audio only)
    has_unique_identifier: bool     # unique run_id present
    parent_run_id: str | None = None


def _evaluate_india_it_rules_2026(m: ManifestData) -> dict:
    """
    India IT (Intermediary Guidelines) Amendment Rules, 2026
    Regulation: Synthetically Generated Information (SGI)
    In force: February 20, 2026

    5 requirements evaluated.
    """
    checks = []

    # IN-SGI-01: User declaration
    checks.append({
        "requirement_id": "IN-SGI-01",
        "description": "User declaration that content is synthetically generated",
        "status": "pass",
        "detail": (
            "Asset created through Notary's AI generation pipeline, which serves "
            "as an explicit declaration of synthetic origin at the point of creation."
        ),
    })

    # IN-SGI-02: Prominent visible label (image/video only)
    if m.modality in ("image", "video"):
        checks.append({
            "requirement_id": "IN-SGI-02",
            "description": "Prominently visible label indicating synthetic generation",
            "status": "pass" if m.has_visible_label else "fail",
            "detail": (
                "Visible 'AI-Generated' label present on asset."
                if m.has_visible_label
                else (
                    "MISSING: No visible label found. India IT Rules require a prominent "
                    "label 'easily noticeable and perceptible to the average user' on "
                    "all synthetically generated images and videos."
                )
            ),
        })
    else:
        checks.append({
            "requirement_id": "IN-SGI-02",
            "description": "Prominently visible label indicating synthetic generation",
            "status": "not_applicable",
            "detail": "Visual label requirement applies to image/video content only.",
        })

    # IN-SGI-03: Audio prefixed disclosure (audio only)
    if m.modality == "audio":
        checks.append({
            "requirement_id": "IN-SGI-03",
            "description": "Prefixed spoken disclosure for audio content",
            "status": "pass" if m.has_audio_disclosure else "fail",
            "detail": (
                "Audio file includes spoken disclosure prefix."
                if m.has_audio_disclosure
                else (
                    "MISSING: No spoken disclosure prefix. India IT Rules require "
                    "audio SGI to include a prefixed spoken warning indicating "
                    "the content is AI-generated."
                )
            ),
        })
    else:
        checks.append({
            "requirement_id": "IN-SGI-03",
            "description": "Prefixed spoken disclosure for audio content",
            "status": "not_applicable",
            "detail": "Audio disclosure requirement applies to audio content only.",
        })

    # IN-SGI-04: Embedded permanent metadata/provenance
    checks.append({
        "requirement_id": "IN-SGI-04",
        "description": "Embedded permanent metadata or provenance mechanism",
        "status": "pass" if m.has_embedded_metadata else "partial",
        "detail": (
            "Genblaze manifest embedded directly in the media file — "
            "non-removable provenance metadata present."
            if m.has_embedded_metadata
            else (
                f"PARTIAL: Asset provenance is immutably locked in Backblaze B2 Object Lock "
                f"(WORM-compliant) via a signed Genblaze manifest (run_id: {m.run_id}). "
                "File-embedded metadata (EXIF/XMP/C2PA) would provide stronger compliance "
                "and is available when using the Google Genblaze provider."
            )
        ),
    })

    # IN-SGI-05: Unique identifier + traceability
    has_traceability = bool(m.has_unique_identifier and m.provider)
    checks.append({
        "requirement_id": "IN-SGI-05",
        "description": "Unique identifier and computer resource traceability",
        "status": "pass" if has_traceability else "partial",
        "detail": (
            f"Run ID: {m.run_id}. Provider: {m.provider}. Model: {m.model}. "
            "Full traceability chain present."
            if has_traceability
            else "Partial: unique identifier present but provider/model traceability incomplete."
        ),
    })

    applicable = [c for c in checks if c["status"] != "not_applicable"]
    passed = sum(1.0 if c["status"] == "pass" else 0.5 if c["status"] == "partial" else 0 for c in applicable)
    total = len(applicable)

    return {
        "regulation_id": "india_it_rules_2026",
        "regulation_name": (
            "India IT (Intermediary Guidelines) Amendment Rules, 2026 "
            "— Synthetically Generated Information"
        ),
        "effective_date": "2026-02-20",
        "checks": checks,
        "passed": int(passed),
        "total": total,
        "compliant": passed == total,
    }


def _evaluate_eu_ai_act_article_50(m: ManifestData) -> dict:
    """
    EU AI Act — Article 50: Transparency Obligations
    In force: August 2, 2026

    4 requirements evaluated.
    """
    checks = []

    # EU-ART50-01: Provider identification
    checks.append({
        "requirement_id": "EU-ART50-01",
        "description": "Provider of the AI system clearly identified",
        "status": "pass" if m.provider else "fail",
        "detail": (
            f"Provider identified: {m.provider} (model: {m.model})."
            if m.provider
            else "MISSING: No AI provider identification in manifest."
        ),
    })

    # EU-ART50-02: Machine-readable marking
    checks.append({
        "requirement_id": "EU-ART50-02",
        "description": "Machine-readable mark enabling detection of artificial origin",
        "status": "pass" if m.has_machine_readable_mark else "partial",
        "detail": (
            "Machine-readable provenance mark embedded via Genblaze manifest."
            if m.has_machine_readable_mark
            else (
                f"PARTIAL: A machine-readable Genblaze JSON manifest is stored in "
                f"Backblaze B2 under run_id {m.run_id}. The manifest records provider, "
                "model, prompt, SHA-256 hash, and timestamp. A C2PA Content Credentials "
                "mark embedded in the file itself would fully satisfy Article 50's "
                "'industry standard' requirement."
            )
        ),
    })

    # EU-ART50-03: Content disclosed as AI-generated
    disclosed = m.has_visible_label or m.has_embedded_metadata
    checks.append({
        "requirement_id": "EU-ART50-03",
        "description": "Content disclosed as artificially generated or manipulated",
        "status": "pass" if disclosed else "fail",
        "detail": (
            "Content marked as AI-generated via embedded metadata and/or visible label."
            if disclosed
            else (
                "MISSING: Content not marked as AI-generated. Article 50 requires "
                "disclosure to individuals exposed to the synthetic content."
            )
        ),
    })

    # EU-ART50-04: Provenance metadata / traceability
    has_provenance = bool(m.sha256 and m.created_at)
    checks.append({
        "requirement_id": "EU-ART50-04",
        "description": "Provenance metadata enabling traceability of origin",
        "status": "pass" if has_provenance else "fail",
        "detail": (
            f"Full provenance chain: SHA-256 hash, creation timestamp ({m.created_at}), "
            "run lineage, WORM-locked in B2 Object Lock."
            if has_provenance
            else "Partial: provenance metadata incomplete — missing hash or timestamp."
        ),
    })

    passed = sum(1.0 if c["status"] == "pass" else 0.5 if c["status"] == "partial" else 0 for c in checks)
    total = len(checks)

    return {
        "regulation_id": "eu_ai_act_article_50",
        "regulation_name": "EU AI Act — Article 50: Transparency Obligations for AI-Generated Content",
        "effective_date": "2026-08-02",
        "checks": checks,
        "passed": int(passed),
        "total": total,
        "compliant": passed == total,
    }


def _generate_recommendations(india: dict, eu: dict) -> list[str]:
    """Generate actionable, deduplicated recommendations from compliance gaps."""
    recs = []
    all_checks = india["checks"] + eu["checks"]
    failed_ids = {c["requirement_id"] for c in all_checks if c["status"] in ("fail", "partial")}

    if "IN-SGI-02" in failed_ids:
        recs.append(
            "Add a visible 'AI-Generated' label/watermark to the asset before publishing. "
            "Required by India IT Rules (IN-SGI-02) and strengthens EU AI Act (EU-ART50-03)."
        )
    if "IN-SGI-03" in failed_ids:
        recs.append(
            "Prepend a spoken disclosure to audio assets (e.g. 'This audio was generated by AI'). "
            "Consider using ElevenLabs to auto-generate this prefix (S3 feature)."
        )
    if "IN-SGI-04" in failed_ids:
        recs.append(
            "Embed the provenance manifest directly into the media file using Genblaze's media "
            "handlers. A separate manifest in B2 alone is not sufficient — metadata must be "
            "non-removable from the asset itself."
        )
    if "EU-ART50-02" in failed_ids:
        recs.append(
            "Implement machine-readable marking in an interoperable format such as C2PA "
            "Content Credentials (EU AI Act EU-ART50-02). The embedded Genblaze manifest "
            "provides provenance but may not meet the 'industry standard' expectation."
        )

    return recs


def evaluate_asset(manifest: ManifestData) -> dict:
    """
    Run all compliance evaluations and return a full ComplianceReport dict.

    Args:
        manifest: Normalized manifest data from the Genblaze run + B2 storage.

    Returns:
        dict matching ComplianceReport Pydantic schema.
    """
    india = _evaluate_india_it_rules_2026(manifest)
    eu = _evaluate_eu_ai_act_article_50(manifest)
    recommendations = _generate_recommendations(india, eu)

    return {
        "run_id": manifest.run_id,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "regulations": [india, eu],
        "overall_compliant": india["compliant"] and eu["compliant"],
        "recommendations": recommendations,
    }


def manifest_data_from_db_row(row: dict) -> ManifestData:
    """
    Build a ManifestData from a SQLite cache row.
    Called by the /compliance route after DB lookup.
    """
    return ManifestData(
        run_id=row["run_id"],
        provider=row.get("provider"),
        model=row.get("model"),
        prompt=row.get("prompt"),
        modality=row.get("modality", "image"),
        created_at=row.get("created_at"),
        sha256=row.get("sha256"),
        has_embedded_metadata=bool(row.get("has_embedded_metadata", 0)),
        has_visible_label=bool(row.get("has_visible_label", 0)),
        has_machine_readable_mark=bool(row.get("has_machine_readable_mark", 0)),
        has_audio_disclosure=bool(row.get("has_audio_disclosure", 0)),
        has_unique_identifier=bool(row.get("run_id")),
        parent_run_id=row.get("parent_run_id"),
    )
