"""
C2PA Content Credentials Signer Module.

Injects standard C2PA JUMBF metadata headers into watermarked media assets
using c2pa-python and local X.509 ES256 certs.

Satisfies EU AI Act Article 50 (EU-ART50-02) machine-readable marking
requirement.  Degrades gracefully: if c2pa-python is unavailable or signing
fails, the original bytes are returned unchanged (NFR-10 alignment).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CERTS_DIR = Path(__file__).resolve().parent / "certs"
KEY_PATH = CERTS_DIR / "es256_private.key"
CERT_PATH = CERTS_DIR / "es256_certs.pem"


def _ensure_certs_exist() -> tuple[Path, Path]:
    """Ensure X.509 EC P-256 cert pair exists; generate automatically if missing."""
    if KEY_PATH.exists() and CERT_PATH.exists():
        return KEY_PATH, CERT_PATH

    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from datetime import datetime, timedelta, timezone
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        private_key = ec.generate_private_key(ec.SECP256R1())
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Notary Cryptographic Authority"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Notary Provenance Engine"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
            .sign(private_key, hashes.SHA256())
        )

        KEY_PATH.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        logger.info("c2pa: generated new X.509 ES256 certificate pair in %s", CERTS_DIR)
    except Exception as exc:
        logger.error("c2pa: failed to generate certificates: %s", exc)
        raise RuntimeError(f"C2PA certificate setup failed: {exc}") from exc

    return KEY_PATH, CERT_PATH


def inject_c2pa_manifest(
    image_bytes: bytes,
    media_type: str,
    manifest_data: dict[str, Any],
) -> bytes:
    """
    Embed a standard C2PA Content Credentials manifest into image bytes.

    Args:
        image_bytes: Input image bytes (watermarked PNG/JPEG/WebP).
        media_type: MIME type ("image/png", "image/jpeg", "image/webp").
        manifest_data: Dict containing provider, model, prompt, run_id, sha256.

    Returns:
        Signed image bytes with embedded C2PA JUMBF header.
        Falls back gracefully to original input bytes on any error.
    """
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(media_type)
    if not suffix:
        logger.warning("c2pa: unsupported media type %s — skipping C2PA injection", media_type)
        return image_bytes

    try:
        import c2pa

        key_file, cert_file = _ensure_certs_exist()

        # Build the C2PA manifest with standard assertions.
        c2pa_manifest_dict = {
            "claim_generator": "Notary/3.0.0 (C2PA; ES256)",
            "title": f"Notary Provenance — {manifest_data.get('run_id', 'unknown')[:8]}",
            "assertions": [
                {
                    "label": "stds.schema-org.CreativeWork",
                    "data": {
                        "@context": "https://schema.org",
                        "@type": "CreativeWork",
                        "author": [
                            {
                                "@type": "Organization",
                                "name": "Notary Provenance Engine",
                            }
                        ],
                    },
                },
                {
                    "label": "c2pa.actions",
                    "data": {
                        "actions": [
                            {
                                "action": "c2pa.created",
                                "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
                                "softwareAgent": f"Notary ({manifest_data.get('provider', 'AI')} / {manifest_data.get('model', 'unknown')})",
                            }
                        ]
                    },
                },
                {
                    "label": "org.notary.provenance",
                    "data": {
                        "run_id": manifest_data.get("run_id"),
                        "provider": manifest_data.get("provider"),
                        "model": manifest_data.get("model"),
                        "prompt": manifest_data.get("prompt", ""),
                        "sha256": manifest_data.get("sha256"),
                        "manifest_uri": manifest_data.get("manifest_uri"),
                    },
                },
            ],
        }

        signer_info_cls = getattr(c2pa, "SignerInfo", None) or getattr(c2pa, "C2paSignerInfo", None)
        if signer_info_cls is None:
            raise AttributeError("c2pa module has no SignerInfo or C2paSignerInfo attribute")

        try:
            signer_info = signer_info_cls(
                alg="es256",
                sign_cert=cert_file.read_bytes(),
                private_key=key_file.read_bytes(),
            )
        except TypeError:
            signer_info = signer_info_cls(
                alg="es256",
                sign_cert=cert_file.read_bytes(),
                private_key=key_file.read_bytes(),
                ta_url=None,
            )
        builder = c2pa.Builder(json.dumps(c2pa_manifest_dict))

        with tempfile.TemporaryDirectory(prefix="notary-c2pa-") as tmpdir:
            src_path = Path(tmpdir) / f"input{suffix}"
            dst_path = Path(tmpdir) / f"signed{suffix}"
            src_path.write_bytes(image_bytes)

            builder.sign(signer_info, str(src_path), str(dst_path))
            signed_bytes = dst_path.read_bytes()
            logger.info(
                "c2pa: injected Content Credentials JUMBF header (%d → %d bytes)",
                len(image_bytes), len(signed_bytes),
            )
            return signed_bytes

    except ImportError:
        logger.warning("c2pa: c2pa-python package is not installed — skipping C2PA injection")
        return image_bytes
    except Exception as exc:
        logger.warning("c2pa: injection failed (%s) — falling back to original bytes", exc)
        return image_bytes
