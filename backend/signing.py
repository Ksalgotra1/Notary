"""
Ed25519 manifest signing.

Provides an independent cryptographic trust anchor separate from B2 Object Lock.
Even if B2 credentials are compromised and a forged manifest is written to the
bucket, the forged manifest will fail signature verification because the attacker
does not have the private key.

Key lifecycle:
  - On first startup, `init_signing_keys()` generates an Ed25519 keypair and
    persists it to `certs/ed25519_private.pem` and `certs/ed25519_public.pem`.
  - The certs/ directory must be in .gitignore (see below).
  - Private key path is configurable via `ED25519_PRIVATE_KEY_PATH` env var.

Usage in pipeline:
    from signing import sign_manifest
    signature = sign_manifest(json.dumps(manifest_dict, sort_keys=True))
    manifest.metadata["ed25519_signature"] = signature

Public verification:
    from signing import verify_manifest_signature
    ok = verify_manifest_signature(manifest_json, signature_b64)

.well-known endpoint:
    from signing import get_public_key_pem
    return Response(get_public_key_pem(), media_type="application/x-pem-file")
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_CERTS_DIR = Path(os.getenv("NOTARY_CERTS_DIR", "certs"))
_PRIVATE_KEY_PATH = Path(os.getenv("ED25519_PRIVATE_KEY_PATH", str(_CERTS_DIR / "ed25519_private.pem")))
_PUBLIC_KEY_PATH = Path(os.getenv("ED25519_PUBLIC_KEY_PATH", str(_CERTS_DIR / "ed25519_public.pem")))

# In-memory cache — loaded once at startup by init_signing_keys()
_private_key = None
_public_key = None


def init_signing_keys() -> None:
    """
    Load or generate Ed25519 keypair on startup.
    Safe to call multiple times (idempotent — only generates once).
    """
    global _private_key, _public_key

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, PublicFormat, NoEncryption,
        load_pem_private_key,
    )

    _CERTS_DIR.mkdir(parents=True, exist_ok=True)

    if _PRIVATE_KEY_PATH.exists():
        # Load existing keypair
        pem_data = _PRIVATE_KEY_PATH.read_bytes()
        _private_key = load_pem_private_key(pem_data, password=None)
        _public_key = _private_key.public_key()
        logger.info("signing: loaded Ed25519 keypair from %s", _PRIVATE_KEY_PATH)
    else:
        # Generate and persist new keypair
        _private_key = Ed25519PrivateKey.generate()
        _public_key = _private_key.public_key()

        _PRIVATE_KEY_PATH.write_bytes(
            _private_key.private_bytes(
                encoding=Encoding.PEM,
                format=PrivateFormat.PKCS8,
                encryption_algorithm=NoEncryption(),
            )
        )
        _PUBLIC_KEY_PATH.write_bytes(
            _public_key.public_bytes(encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo)
        )
        logger.info("signing: generated new Ed25519 keypair, saved to %s", _CERTS_DIR)


def _ensure_loaded() -> None:
    if _private_key is None or _public_key is None:
        raise RuntimeError(
            "Ed25519 signing keys are not initialised. "
            "Call signing.init_signing_keys() at application startup."
        )


def sign_manifest(manifest_json: str) -> str:
    """
    Sign a canonical manifest JSON string with Ed25519.

    The manifest_json should be serialised with sorted keys and no extra
    whitespace to ensure the signature is deterministic:
        json.dumps(manifest_dict, sort_keys=True, separators=(',', ':'))

    Returns:
        URL-safe base64-encoded Ed25519 signature string.
    """
    _ensure_loaded()
    signature_bytes = _private_key.sign(manifest_json.encode("utf-8"))
    return base64.urlsafe_b64encode(signature_bytes).decode("ascii")


def verify_manifest_signature(manifest_json: str, signature_b64: str) -> bool:
    """
    Verify an Ed25519 signature against the canonical manifest JSON.

    Args:
        manifest_json: The canonical manifest JSON (same serialisation as at signing time).
        signature_b64: URL-safe base64-encoded signature produced by sign_manifest().

    Returns:
        True if the signature is valid; False otherwise (never raises).
    """
    _ensure_loaded()
    try:
        from cryptography.exceptions import InvalidSignature
        sig_bytes = base64.urlsafe_b64decode(signature_b64.encode("ascii"))
        _public_key.verify(sig_bytes, manifest_json.encode("utf-8"))
        return True
    except (Exception,):  # InvalidSignature, ValueError, etc.
        return False


def get_public_key_pem() -> str:
    """
    Return the PEM-encoded Ed25519 public key for the /.well-known endpoint.
    Third parties can use this to independently verify manifest signatures.
    """
    _ensure_loaded()
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    return _public_key.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def canonical_manifest_json(manifest_dict: dict) -> str:
    """
    Produce a deterministic JSON string for signing — sorted keys, no whitespace.
    Use this consistently both when signing and when verifying.
    """
    return json.dumps(manifest_dict, sort_keys=True, separators=(",", ":"))
