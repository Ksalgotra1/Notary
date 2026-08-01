"""
AI Forensic Verification — uses Gemini Vision to analyze what changed
in a tampered file, not just that it changed.

USP #2 — Notary's second differentiator.
Genblaze verify() is binary (pass/fail on hash).
Notary tells you WHAT was modified and HOW.

Degrades gracefully: if Gemini is unavailable, verify still returns
the hash result — forensic_analysis is just null (NFR-10).
"""
import os
import base64
import json
import logging

import httpx

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models"
    f"/{GEMINI_MODEL}:generateContent"
)

FORENSIC_PROMPT = """You are a forensic media analyst. You have been given two versions of the same AI-generated media file:

IMAGE 1 — ORIGINAL: The canonical, unmodified version retrieved from the tamper-evident provenance archive.
IMAGE 2 — SUBMITTED: A copy submitted for verification that has FAILED the hash check.

Analyze both images carefully and respond with ONLY a JSON object in this exact format:
{
    "modifications_detected": ["precise description of change 1", "precise description of change 2"],
    "severity": "minor",
    "conclusion": "One sentence describing whether this appears intentional or accidental."
}

Rules:
- "modifications_detected": List specific, precise observations (what changed, where in the image).
  Examples: "Text overlay 'AI Art' added in bottom-right corner", "Sky hue shifted from blue to orange",
  "Image cropped by ~15% on the right edge", "Resolution downscaled from 1024x1024 to 512x512".
- "severity": Must be exactly one of: "minor" (compression artifacts, slight color shift),
  "moderate" (cropping, resize, filter), "major" (text added, faces changed, content inserted/removed).
- "conclusion": One sentence only. State whether the change is intentional manipulation or an
  accidental artifact (e.g. re-encoding, format conversion).

Return ONLY the JSON object. No markdown, no explanation, no extra text."""


def _get_api_key() -> str | None:
    keys = os.getenv("GOOGLE_API_KEYS", "").split(",")
    active = [k.strip() for k in keys if k.strip()]
    return active[0] if active else None


async def analyze_tampering(
    original_bytes: bytes,
    tampered_bytes: bytes,
    modality: str = "image",
    api_key: str | None = None,
) -> dict | None:
    """
    Send original and tampered media to Gemini Vision for forensic analysis.

    Args:
        original_bytes: Canonical asset bytes fetched from B2.
        tampered_bytes: User-supplied (potentially tampered) copy bytes.
        modality: "image" or "video" — determines MIME type.
        api_key: Override; defaults to first key in GOOGLE_API_KEYS.

    Returns:
        dict with keys: modifications_detected, severity, conclusion, analysis_model
        Returns None on any failure (NFR-10: forensic analysis is non-blocking).
    """
    key = api_key or _get_api_key()
    if not key:
        logger.warning("forensics: no API key available — skipping forensic analysis")
        return None

    # Determine MIME type
    if modality == "video":
        mime_type = "video/mp4"
    else:
        mime_type = "image/png"

    orig_b64 = base64.b64encode(original_bytes).decode()
    tampered_b64 = base64.b64encode(tampered_bytes).decode()

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": FORENSIC_PROMPT},
                    {"text": "IMAGE 1 — ORIGINAL:"},
                    {"inline_data": {"mime_type": mime_type, "data": orig_b64}},
                    {"text": "IMAGE 2 — SUBMITTED (hash mismatch detected):"},
                    {"inline_data": {"mime_type": mime_type, "data": tampered_b64}},
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
            "maxOutputTokens": 512,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GEMINI_API_URL,
                json=payload,
                params={"key": key},
            )
            resp.raise_for_status()
            data = resp.json()

        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        analysis = json.loads(raw_text)

        return {
            "modifications_detected": analysis.get("modifications_detected", []),
            "severity": analysis.get("severity", "unknown"),
            "conclusion": analysis.get("conclusion", ""),
            "analysis_model": GEMINI_MODEL,
        }

    except httpx.HTTPStatusError as e:
        logger.warning("forensics: Gemini API HTTP error %s — degrading gracefully", e.response.status_code)
        return None
    except httpx.TimeoutException:
        logger.warning("forensics: Gemini API timeout — degrading gracefully")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logger.warning("forensics: failed to parse Gemini response (%s) — degrading gracefully", e)
        return None
    except Exception as e:
        logger.warning("forensics: unexpected error (%s) — degrading gracefully", e)
        return None
