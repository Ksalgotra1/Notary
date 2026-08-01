"""
GitHub Models provider for image generation.

GitHub Models exposes an OpenAI-compatible API at models.github.com.
Supported image models (as of 2026-08):
  - openai/gpt-image-1  (high quality, fast)
  - black-forest-labs/FLUX.1-schnell  (open-source, very fast)

Free tier: included with any GitHub account. No card needed.
Rate limits: ~15 image requests/min, 150/day (personal accounts).

This is a thin custom wrapper — not a Genblaze SDK provider class, but
structured to drop into our pipeline.py provider cascade.
"""
import os
import base64
import logging
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)

GITHUB_IMAGE_MODELS = {
    "gpt-image-1": {
        "endpoint": "https://models.inference.ai.azure.com",
        "path": "/images/generations",
        "model_name": "gpt-image-1",
    },
    "flux-schnell": {
        "endpoint": "https://models.inference.ai.azure.com",
        "path": "/images/generations",
        "model_name": "black-forest-labs/FLUX.1-schnell",
    },
}

DEFAULT_MODEL = "gpt-image-1"


class GitHubModelsImageProvider:
    """
    Wraps GitHub Models image generation API.

    Returns image bytes + metadata in a shape compatible with
    our pipeline.py result format.
    """

    def __init__(self, pat: str | None = None, model: str = DEFAULT_MODEL):
        self._pat = pat or os.getenv("GITHUB_PAT", "")
        if not self._pat:
            raise ValueError("GITHUB_PAT not set — cannot use GitHub Models provider")
        self._model_key = model
        self._model_cfg = GITHUB_IMAGE_MODELS.get(model, GITHUB_IMAGE_MODELS[DEFAULT_MODEL])
        self.provider_name = "github-models"
        self.model_id = self._model_cfg["model_name"]

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
    ) -> bytes:
        """
        Generate an image and return raw PNG/JPEG bytes.

        Raises:
            httpx.HTTPStatusError: on API error (4xx/5xx)
            ValueError: if response doesn't contain image data
        """
        headers = {
            "Authorization": f"Bearer {self._pat}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_cfg["model_name"],
            "prompt": prompt,
            "n": n,
            "size": size,
            "response_format": "b64_json",
        }

        url = self._model_cfg["endpoint"] + self._model_cfg["path"]
        logger.info("GitHubModelsImageProvider: generating with model=%s", self._model_cfg["model_name"])

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        b64 = data["data"][0].get("b64_json")
        if not b64:
            raise ValueError(f"No b64_json in response: {data}")

        return base64.b64decode(b64)


async def generate_with_github_models(
    prompt: str,
    model: str = DEFAULT_MODEL,
    pat: str | None = None,
) -> dict:
    """
    Generate an image via GitHub Models and return result metadata.

    Compatible shape with run_image_pipeline() return dict.
    The caller is responsible for uploading image_bytes to B2
    and building the manifest (done in pipeline.py).

    Returns:
        {
            "image_bytes": bytes,
            "provider": "github-models",
            "model": str,
            "prompt": str,
        }
    """
    provider = GitHubModelsImageProvider(pat=pat, model=model)
    image_bytes = await provider.generate_image(prompt=prompt)
    logger.info("GitHubModelsImageProvider: generated %d bytes", len(image_bytes))
    return {
        "image_bytes": image_bytes,
        "provider": "github-models",
        "model": provider.model_id,
        "prompt": prompt,
    }
