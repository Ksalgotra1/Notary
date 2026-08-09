"""Unit tests for C2PA Content Credentials signing and cert generation."""
import sys
import unittest
from pathlib import Path

# Ensure backend modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from c2pa_signer import _ensure_certs_exist, inject_c2pa_manifest, CERTS_DIR, ROOT_CERT_PATH


class TestCertGeneration(unittest.TestCase):
    """Verify that X.509 ES256 certs are generated and valid."""

    def test_certs_exist_after_ensure(self):
        key_path, cert_path = _ensure_certs_exist()
        self.assertTrue(key_path.exists(), "Private key file should exist")
        self.assertTrue(cert_path.exists(), "Certificate file should exist")

    def test_key_is_pem_encoded(self):
        key_path, _ = _ensure_certs_exist()
        content = key_path.read_text()
        self.assertIn("BEGIN PRIVATE KEY", content)

    def test_cert_is_pem_encoded(self):
        _, cert_path = _ensure_certs_exist()
        content = cert_path.read_text()
        self.assertIn("BEGIN CERTIFICATE", content)

    def test_signing_certificate_has_correct_cn_and_root_chain(self):
        from cryptography import x509
        _, cert_path = _ensure_certs_exist()
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        cn = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value
        self.assertEqual(cn, "Notary Content Credentials Signing")

        root = x509.load_pem_x509_certificate(ROOT_CERT_PATH.read_bytes())
        self.assertEqual(cert.issuer, root.subject)
        self.assertTrue(
            root.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        )


class TestC2PAInjection(unittest.TestCase):
    """Verify C2PA injection gracefully handles edge cases."""

    def test_fallback_on_invalid_image_bytes(self):
        """Invalid bytes should be returned unchanged — no crash."""
        dummy_bytes = b"not_a_valid_image_at_all"
        result = inject_c2pa_manifest(
            dummy_bytes,
            "image/png",
            {"run_id": "test-run-123", "provider": "google", "model": "imagen-3"},
        )
        # Should gracefully fall back to original bytes
        self.assertEqual(result, dummy_bytes)

    def test_unsupported_media_type_returns_original(self):
        """Unsupported MIME types should pass through unchanged."""
        dummy_bytes = b"some video bytes"
        result = inject_c2pa_manifest(
            dummy_bytes,
            "video/mp4",
            {"run_id": "test-video", "provider": "google", "model": "veo"},
        )
        self.assertEqual(result, dummy_bytes)

    def test_injection_on_real_png(self):
        """If c2pa-python is installed, a real PNG should gain bytes (JUMBF header)."""
        try:
            import c2pa
        except ImportError:
            self.skipTest("c2pa-python not installed")

        # Create a minimal valid 1x1 red PNG using Pillow
        from PIL import Image
        import io
        img = Image.new("RGB", (64, 64), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        result = inject_c2pa_manifest(
            png_bytes,
            "image/png",
            {
                "run_id": "test-real-png",
                "provider": "google",
                "model": "gemini-2.5-flash-image",
                "prompt": "a red square",
                "manifest_uri": "https://example.invalid/manifest.json",
            },
        )
        # The local root CA is trusted by the signing context, so a valid
        # image must receive an embedded C2PA JUMBF manifest.
        self.assertGreater(len(result), len(png_bytes),
                           "C2PA injection should embed a JUMBF manifest")


if __name__ == "__main__":
    unittest.main()
