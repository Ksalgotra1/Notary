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
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CERTS_DIR = Path(__file__).resolve().parent / "certs"
KEY_PATH = CERTS_DIR / "es256_private.key"
CERT_PATH = CERTS_DIR / "es256_certs.pem"
ROOT_CERT_PATH = CERTS_DIR / "c2pa_root_ca.pem"


def _certificate_chain_is_current() -> bool:
    """Return whether the on-disk credentials are a leaf + root CA chain."""
    if not all(path.exists() for path in (KEY_PATH, CERT_PATH, ROOT_CERT_PATH)):
        return False

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        chain = CERT_PATH.read_bytes().split(b"-----END CERTIFICATE-----")
        certificates = [
            x509.load_pem_x509_certificate(item + b"-----END CERTIFICATE-----")
            for item in chain
            if b"-----BEGIN CERTIFICATE-----" in item
        ]
        leaf, root = certificates
        root_constraint = root.extensions.get_extension_for_class(
            x509.BasicConstraints
        ).value
        return (
            len(certificates) == 2
            and leaf.issuer == root.subject
            and root.subject == root.issuer
            and root_constraint.ca
            and ROOT_CERT_PATH.read_bytes() == root.public_bytes(
                encoding=serialization.Encoding.PEM
            )
        )
    except Exception:
        return False


def _ensure_certs_exist() -> tuple[Path, Path]:
    """Ensure a development leaf signing certificate and trusted local root exist."""
    if _certificate_chain_is_current():
        return KEY_PATH, CERT_PATH

    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from datetime import datetime, timedelta, timezone
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        now = datetime.now(timezone.utc)
        root_key = ec.generate_private_key(ec.SECP256R1())
        root_subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Notary Cryptographic Authority"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Notary Provenance Engine"),
        ])
        root_cert = (
            x509.CertificateBuilder()
            .subject_name(root_subject)
            .issuer_name(root_subject)
            .public_key(root_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, key_cert_sign=True, crl_sign=False,
                    content_commitment=False, key_encipherment=False,
                    data_encipherment=False, key_agreement=False,
                    encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256())
        )

        private_key = ec.generate_private_key(ec.SECP256R1())
        signing_subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Notary Content Credentials Signing"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Notary Provenance Engine"),
        ])
        signing_cert = (
            x509.CertificateBuilder()
            .subject_name(signing_subject)
            .issuer_name(root_subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=825))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, key_cert_sign=False, crl_sign=False,
                    content_commitment=False, key_encipherment=False,
                    data_encipherment=False, key_agreement=False,
                    encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.EMAIL_PROTECTION]),
                critical=False,
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()), critical=False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                    root_cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
                ),
                critical=False,
            )
            .sign(root_key, hashes.SHA256())
        )

        KEY_PATH.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        ROOT_CERT_PATH.write_bytes(root_cert.public_bytes(serialization.Encoding.PEM))
        CERT_PATH.write_bytes(
            signing_cert.public_bytes(serialization.Encoding.PEM)
            + root_cert.public_bytes(serialization.Encoding.PEM)
        )
        logger.info("c2pa: generated a local root CA and ES256 signing chain in %s", CERTS_DIR)
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
    if media_type not in ("image/png", "image/jpeg", "image/webp"):
        logger.warning("c2pa: unsupported media type %s — skipping C2PA injection", media_type)
        return image_bytes

    try:
        import c2pa
        import io

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

        # Create signer via C2paSignerInfo → Signer.from_info() (c2pa-python ≥ 0.35)
        signer_info = c2pa.C2paSignerInfo(
            alg="es256",
            sign_cert=cert_file.read_bytes(),
            private_key=key_file.read_bytes(),
            ta_url=None,
        )
        signer = c2pa.Signer.from_info(signer_info)

        # This is a development root, so it must be added explicitly to this
        # context's trust store. External verifiers will display it as an
        # unrecognized issuer until production credentials chain to the C2PA
        # trust list.
        settings = c2pa.Settings.from_dict({
            "version": 1,
            "trust": {"user_anchors": ROOT_CERT_PATH.read_text()},
            "verify": {
                "verify_after_sign": True,
                "remote_manifest_fetch": False,
                "ocsp_fetch": False,
            },
        })
        context = c2pa.Context(settings=settings, signer=signer)

        builder = c2pa.Builder(json.dumps(c2pa_manifest_dict), context=context)

        # Stream-based signing
        source_stream = io.BytesIO(image_bytes)
        dest_stream = io.BytesIO()

        builder.sign(media_type, source_stream, dest_stream)

        signed_bytes = dest_stream.getvalue()
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
