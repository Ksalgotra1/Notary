"""
Visible AI watermark overlay.

Composites a semi-transparent "AI-Generated · Notary Verified" badge onto
every generated image before M0 embedding. This satisfies:
  - India IT Rules 2026, IN-SGI-02: prominent visible label
  - EU AI Act Article 50, EU-ART50-03: content disclosed as AI-generated

The watermark is applied BEFORE M0 manifest embedding so it is part of the
canonical signed bytes. M1 covers the watermarked image, not the raw output.

Supported formats: PNG, JPEG, WebP.
Non-image media types (video, audio) are returned unchanged.
"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

# Badge layout constants
_BADGE_TEXT = "AI-Generated · Notary Verified"
_MARGIN_FRACTION = 0.025       # margin from edges = 2.5% of image min-dimension
_FONT_HEIGHT_FRACTION = 0.030  # badge text height = 3% of image height (min 18px)
_MIN_FONT_SIZE = 18
_MAX_FONT_SIZE = 36
_PADDING_X = 12                # horizontal padding inside badge pill
_PADDING_Y = 6                 # vertical padding inside badge pill
_BADGE_FILL = (0, 0, 0, 170)   # dark semi-transparent background (RGBA)
_TEXT_FILL = (255, 255, 255, 255)  # white text

_SUPPORTED_MEDIA_TYPES = {"image/png", "image/jpeg", "image/webp"}
_FORMAT_MAP = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WEBP",
}


def apply_watermark(image_bytes: bytes, media_type: str) -> bytes:
    """
    Overlay a visible provenance badge onto image bytes.

    Args:
        image_bytes: Raw image bytes (PNG / JPEG / WebP).
        media_type:  MIME type string, e.g. "image/png".

    Returns:
        Watermarked image bytes in the same format, or the original bytes
        unchanged if the media type is not a supported image type.
    """
    if media_type not in _SUPPORTED_MEDIA_TYPES:
        logger.debug("watermark: skipping non-image media type %s", media_type)
        return image_bytes

    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = img.size

        # ── Font sizing ──────────────────────────────────────────────
        font_size = max(_MIN_FONT_SIZE, min(_MAX_FONT_SIZE, int(h * _FONT_HEIGHT_FRACTION)))
        try:
            # Try to load a bundled truetype font for clean rendering
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except (OSError, IOError):
            try:
                # Linux fallback
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        # ── Measure text ─────────────────────────────────────────────
        draw_tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = draw_tmp.textbbox((0, 0), _BADGE_TEXT, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        badge_w = text_w + _PADDING_X * 2
        badge_h = text_h + _PADDING_Y * 2

        margin = max(8, int(min(w, h) * _MARGIN_FRACTION))
        badge_x = w - badge_w - margin
        badge_y = h - badge_h - margin

        # ── Draw badge on a transparent overlay ──────────────────────
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Rounded-rect pill background
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=badge_h // 2,
            fill=_BADGE_FILL,
        )

        # Text centred inside the pill
        text_x = badge_x + _PADDING_X - bbox[0]
        text_y = badge_y + _PADDING_Y - bbox[1]
        draw.text((text_x, text_y), _BADGE_TEXT, font=font, fill=_TEXT_FILL)

        # Composite onto original
        watermarked = Image.alpha_composite(img, overlay)

        # ── Serialise back to original format ────────────────────────
        fmt = _FORMAT_MAP[media_type]
        out = io.BytesIO()
        if fmt == "JPEG":
            watermarked = watermarked.convert("RGB")  # JPEG has no alpha channel
            watermarked.save(out, format="JPEG", quality=95, optimize=True)
        else:
            watermarked.save(out, format=fmt)

        result = out.getvalue()
        logger.info(
            "watermark: applied badge to %s image (%d x %d px), %d -> %d bytes",
            media_type, w, h, len(image_bytes), len(result),
        )
        return result

    except Exception as exc:
        # Non-blocking: a failed watermark must not break generation
        logger.warning("watermark: overlay failed (%s) -- returning original bytes", exc)
        return image_bytes
