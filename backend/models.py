"""Request/response models — typed contract between frontend and backend."""
from pydantic import BaseModel
from enum import Enum
from typing import Optional


class Modality(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class GenerateRequest(BaseModel):
    prompt: str
    modality: Modality = Modality.IMAGE
    provider: Optional[str] = None  # reserved for future multi-provider


class GenerateResponse(BaseModel):
    run_id: str
    status: str  # "completed" | "processing" | "failed"
    asset_url: Optional[str] = None
    manifest_uri: Optional[str] = None
    sha256: Optional[str] = None


class AssetSummary(BaseModel):
    run_id: str
    parent_run_id: Optional[str] = None
    provider: str
    model: str
    modality: str
    prompt: str
    b2_asset_url: str
    sha256: str
    created_at: str


class AssetDetail(AssetSummary):
    b2_manifest_url: str
    last_verified_at: Optional[str] = None
    verify_status: Optional[str] = None
    params: Optional[dict] = None
    timestamps: Optional[dict] = None


# ── USP Feature 1: Compliance Engine ─────────────────────────────

class ComplianceCheck(BaseModel):
    requirement_id: str       # e.g. "IN-SGI-02", "EU-ART50-01"
    description: str
    status: str               # "pass" | "fail" | "partial" | "not_applicable"
    detail: str               # human-readable reason


class RegulationResult(BaseModel):
    regulation_id: str        # "india_it_rules_2026" | "eu_ai_act_article_50"
    regulation_name: str
    effective_date: str
    checks: list[ComplianceCheck]
    passed: int
    total: int
    compliant: bool


class ComplianceReport(BaseModel):
    run_id: str
    evaluated_at: str
    regulations: list[RegulationResult]
    overall_compliant: bool
    recommendations: list[str]  # actionable steps to close gaps


# ── USP Feature 2: AI Forensic Verification ──────────────────────

class ForensicDetail(BaseModel):
    modifications_detected: list[str]  # e.g. ["Text overlay in bottom-right"]
    severity: str                      # "minor" | "moderate" | "major"
    conclusion: str                    # one-sentence summary
    analysis_model: str                # e.g. "gemini-2.0-flash"


class VerifyResponse(BaseModel):
    match: bool
    computed_hash: str
    manifest_hash: str
    verified_at: str
    forensic_analysis: Optional[ForensicDetail] = None  # only when match=False


# ── USP Feature 3: Public Verification Portal ────────────────────

class PublicVerifyRequest(BaseModel):
    file_hash: str  # SHA-256 computed client-side (Web Crypto API)


class PublicAssetInfo(BaseModel):
    run_id: str
    provider: str
    model: str
    modality: str
    prompt: str
    created_at: str
    sha256: str
    compliance_report: Optional[ComplianceReport] = None


# ── Other models ─────────────────────────────────────────────────

class RemixRequest(BaseModel):
    prompt: str


class AssetListResponse(BaseModel):
    assets: list[AssetSummary]
    total: int
