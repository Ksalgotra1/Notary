"""Provider-order and secret-handling tests for the image fallback cascade."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pipeline
from genblaze_core.models.enums import Modality
from genblaze_core.models.step import Step


class ImageCascadeTests(unittest.IsolatedAsyncioTestCase):
    async def test_declared_order_reaches_huggingface_after_google_and_nvidia(self):
        calls = []

        async def fail_google(*args, **kwargs):
            calls.append("google")
            raise RuntimeError("google unavailable")

        async def fail_nvidia(*args, **kwargs):
            calls.append("nvidia")
            raise RuntimeError("nvidia unavailable")

        async def succeed_hf(*args, **kwargs):
            calls.append("huggingface")
            return {"run_id": "hf-run"}

        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}, clear=False), \
             patch.object(pipeline, "_run_google_image", fail_google), \
             patch.object(pipeline, "_run_nvidia_image", fail_nvidia), \
             patch.object(pipeline, "_run_huggingface_space_image", succeed_hf), \
             patch.object(pipeline, "_run_pollinations_image", AsyncMock()):
            result = await pipeline.run_image_pipeline("test", api_keys=["google-key"])

        self.assertEqual(result["run_id"], "hf-run")
        self.assertEqual(calls, ["google", "nvidia", "huggingface"])

    async def test_pollinations_is_final_stage_only_when_its_key_exists(self):
        calls = []

        async def fail_hf(*args, **kwargs):
            calls.append("huggingface")
            raise RuntimeError("space unavailable")

        async def succeed_pollinations(*args, **kwargs):
            calls.append("pollinations")
            return {"run_id": "pollinations-run"}

        with patch.dict(os.environ, {"POLLINATIONS_API_KEY": "poll-key"}, clear=True), \
             patch.object(pipeline, "_run_huggingface_space_image", fail_hf), \
             patch.object(pipeline, "_run_pollinations_image", succeed_pollinations):
            result = await pipeline.run_image_pipeline("test", api_keys=[])

        self.assertEqual(result["run_id"], "pollinations-run")
        self.assertEqual(calls, ["huggingface", "pollinations"])

    async def test_pollinations_runs_as_public_fallback_without_key(self):
        calls = []

        async def fail_hf(*args, **kwargs):
            calls.append("huggingface")
            raise RuntimeError("space unavailable")

        async def succeed_pollinations(*args, **kwargs):
            calls.append("pollinations")
            return {"run_id": "public-pollinations-run"}

        with patch.dict(os.environ, {}, clear=True), \
             patch.object(pipeline, "_run_huggingface_space_image", fail_hf), \
             patch.object(pipeline, "_run_pollinations_image", succeed_pollinations):
            result = await pipeline.run_image_pipeline("test", api_keys=[])

        self.assertEqual(result["run_id"], "public-pollinations-run")
        self.assertEqual(calls, ["huggingface", "pollinations"])

    async def test_hf_token_is_not_written_to_provider_payload(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image:
            image.write(b"not-a-real-png-but-a-local-provider-output")
            image_path = image.name

        class FakeClient:
            def __init__(self, *args, **kwargs):
                self.token = kwargs["token"]

            def predict(self, *args, **kwargs):
                return ({"path": image_path},)

        try:
            with patch.dict(sys.modules, {"gradio_client": SimpleNamespace(Client=FakeClient)}):
                provider = pipeline.HuggingFaceSpaceImageProvider(
                    space_id="example/space",
                    token="secret-hf-token",
                    timeout_seconds=1,
                    space_url="https://example-space.hf.space",
                )
                step = provider.generate(
                    Step(
                        provider="huggingface-space", model="example/space",
                        modality=Modality.IMAGE, prompt="test",
                    )
                )
            self.assertEqual(step.provider_payload["huggingface_space"]["space_id"], "example/space")
            self.assertTrue(step.provider_payload["huggingface_space"]["authenticated"])
            self.assertNotIn("secret-hf-token", str(step.provider_payload))
            self.assertEqual(len(step.assets), 1)
        finally:
            Path(image_path).unlink(missing_ok=True)
            if 'step' in locals() and step.assets:
                clean_path = step.assets[0].url.removeprefix("file://").lstrip("/")
                Path(clean_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
