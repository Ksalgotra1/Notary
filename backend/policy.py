"""Explainable pre-generation policy review and optional visual audit.

Policy status is deliberately separate from cryptographic provenance. A pass
means the selected policy profile found no issue; it never means the file's
bytes are authentic. Byte authenticity is established by the M0/M1 chain.
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

import httpx


POLICY_PROFILES = {"general", "public-release", "brand-safe"}

_BLOCK_RULES = (
    (
        "POL-001",
        re.compile(r"\b(?:sexual|nude|naked|explicit).{0,40}\b(?:minor|child|underage)\b", re.I),
        "Sexualized content involving a minor cannot be generated.",
        "Use an adult, non-explicit subject or choose a different concept.",
    ),
    (
        "POL-002",
        re.compile(r"\b(?:fake|forge|counterfeit).{0,40}\b(?:passport|driver.?s? license|identity card|government id)\b", re.I),
        "Requests to forge identity documents are not allowed.",
        "Use a clearly fictional prop that cannot be mistaken for identification.",
    ),
)

_WARNING_RULES = (
    (
        "POL-101",
        re.compile(r"\b(?:politician|president|prime minister|celebrity|public figure)\b", re.I),
        "Depicts a public figure; publish with context and an AI-generated disclosure.",
        "Describe the scene as an illustration or use a fictional spokesperson.",
    ),
    (
        "POL-102",
        re.compile(r"\b(?:breaking news|news footage|live report|eyewitness)\b", re.I),
        "Could be mistaken for real news coverage.",
        "Add 'fictional illustration' or 'simulated scene' to the prompt.",
    ),
    (
        "POL-103",
        re.compile(r"\b(?:medical advice|diagnosis|investment advice|guaranteed return)\b", re.I),
        "High-impact advice claims need human review before publication.",
        "Reframe as an educational illustration without claims or guarantees.",
    ),
    (
        "POL-104",
        re.compile(r"\b(?:logo|trademark|brand campaign|packaging)\b", re.I),
        "May involve brand or trademark review before public release.",
        "Use original branding or confirm permission to use the referenced mark.",
    ),
)


def review_prompt(prompt: str, profile: str = "general") -> dict[str, Any]:
    """Return transparent rule matches; this never alters the user's prompt."""
    if profile not in POLICY_PROFILES:
        raise ValueError(f"Unsupported policy profile: {profile}")
    findings: list[dict[str, str]] = []
    for rule_id, pattern, detail, suggestion in _BLOCK_RULES:
        if pattern.search(prompt):
            findings.append({"rule_id": rule_id, "severity": "block", "detail": detail, "suggestion": suggestion})

    if not findings and profile != "general":
        for rule_id, pattern, detail, suggestion in _WARNING_RULES:
            if pattern.search(prompt):
                findings.append({"rule_id": rule_id, "severity": "warning", "detail": detail, "suggestion": suggestion})

    status = "block" if any(item["severity"] == "block" for item in findings) else "warning" if findings else "pass"
    return {
        "profile": profile,
        "status": status,
        "findings": findings,
        "requires_acknowledgement": status == "warning",
        "prompt_was_modified": False,
    }


async def audit_image_bytes(image_bytes: bytes, *, profile: str, prompt: str) -> dict[str, Any]:
    """Optionally ask Gemini Vision to inspect pixels. Never fabricate a pass."""
    if os.getenv("POST_GENERATION_VISUAL_AUDIT", "false").lower() not in {"1", "true", "yes", "on"}:
        return {
            "status": "unavailable", "mode": "disabled", "model": None, "findings": [],
            "summary": "Visual audit is disabled; provenance verification remains available.",
        }
    key = next((item.strip() for item in os.getenv("GOOGLE_API_KEYS", "").split(",") if item.strip()), None)
    if not key:
        return {
            "status": "unavailable", "mode": "no_credentials", "model": None, "findings": [],
            "summary": "Visual audit is unavailable because no Google Vision credential is configured.",
        }

    model = os.getenv("VISUAL_AUDIT_MODEL", "gemini-2.0-flash")
    instruction = (
        "Audit this generated image against the selected policy profile. Do not claim byte authenticity. "
        "Return JSON only: {\"status\": \"pass\"|\"warning\"|\"fail\", "
        "\"findings\": [string], \"summary\": string}. "
        f"Profile: {profile}. Original prompt: {prompt}"
    )
    payload = {
        "contents": [{"parts": [
            {"text": instruction},
            {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode()}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0, "maxOutputTokens": 400},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": key}, json=payload,
            )
            response.raise_for_status()
        raw = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        result = json.loads(raw.removeprefix("```json").removesuffix("```").strip())
        status = result.get("status") if result.get("status") in {"pass", "warning", "fail"} else "warning"
        return {"status": status, "mode": "vision", "model": model, "findings": result.get("findings", []), "summary": result.get("summary", "Visual audit completed.")}
    except Exception as exc:
        return {
            "status": "unavailable", "mode": "provider_error", "model": model, "findings": [],
            "summary": f"Visual audit could not run: {type(exc).__name__}.",
        }
