"""Regression tests for the non-circular M0/M1 image provenance chain."""
import hashlib
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genblaze_core.media import get_handler
from genblaze_core.models.asset import Asset
from genblaze_core.models.enums import Modality, StepType
from genblaze_core.models.manifest import Manifest
from genblaze_core.models.run import Run
from genblaze_core.models.step import Step
from pipeline import verify_embedded_receipt


class EmbeddedReceiptTests(unittest.TestCase):
    def _build_chain(self, image_path: Path):
        raw_bytes = image_path.read_bytes()
        receipt_id = str(uuid.uuid4())
        raw_asset = Asset(
            url="https://example.invalid/raw.png",
            media_type="image/png",
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
            size_bytes=len(raw_bytes),
        )
        raw_step = Step(
            provider="test-provider", model="test-model", prompt="provenance test",
            modality=Modality.IMAGE, assets=[raw_asset],
        )
        m0 = Manifest.from_run(Run(
            steps=[raw_step],
            metadata={"embedded_receipt_run_id": receipt_id},
        ))
        get_handler("image/png").embed(image_path, m0)
        final_bytes = image_path.read_bytes()
        final_asset = Asset(
            url="https://example.invalid/final.png",
            media_type="image/png",
            sha256=hashlib.sha256(final_bytes).hexdigest(),
            size_bytes=len(final_bytes),
        )
        receipt_step = Step(
            provider="notary", model="genblaze-inline-manifest-v1",
            step_type=StepType.CUSTOM, modality=Modality.IMAGE,
            inputs=[raw_asset], assets=[final_asset],
        )
        m1 = Manifest.from_run(Run(
            run_id=receipt_id,
            parent_run_id=m0.run.run_id,
            steps=[receipt_step],
            metadata={"source_manifest_uri": "https://example.invalid/m0.json"},
        ))
        return m0, m1, final_bytes

    def test_post_embed_hash_and_extracted_m0_verify(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "asset.png"
            shutil.copyfile(Path(__file__).resolve().parents[2] / "frontend/src/assets/hero.png", image_path)
            m0, m1, final_bytes = self._build_chain(image_path)

            self.assertTrue(m0.verify())
            self.assertTrue(m1.verify())
            self.assertEqual(hashlib.sha256(final_bytes).hexdigest(), m1.run.steps[0].assets[0].sha256)
            self.assertTrue(verify_embedded_receipt(m1, final_bytes, source_manifest=m0))

    def test_single_byte_tamper_fails_receipt_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "asset.png"
            shutil.copyfile(Path(__file__).resolve().parents[2] / "frontend/src/assets/hero.png", image_path)
            m0, m1, final_bytes = self._build_chain(image_path)

            tampered = bytearray(final_bytes)
            tampered[-1] ^= 0x01
            tampered_path = Path(directory) / "tampered.png"
            tampered_path.write_bytes(tampered)
            extracted_m0 = get_handler("image/png").extract(tampered_path)
            self.assertTrue(extracted_m0.verify())
            self.assertFalse(verify_embedded_receipt(m1, bytes(tampered), source_manifest=m0))


if __name__ == "__main__":
    unittest.main()
