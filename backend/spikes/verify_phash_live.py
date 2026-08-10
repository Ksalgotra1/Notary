"""
Live verification script for pHash perceptual hashing resilience against FastAPI backend.
"""
import asyncio
import io
import logging
from PIL import Image
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phash_live_verify")

BASE_URL = "http://localhost:8000"

async def main():
    logger.info("Connecting to FastAPI backend at %s...", BASE_URL)
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Check health
        health = await client.get(f"{BASE_URL}/health")
        logger.info("✓ /health: %s", health.status_code)

        # 2. Get recent asset or generate new one
        assets_res = await client.get(f"{BASE_URL}/assets?limit=1&modality=image")
        assets = assets_res.json()
        if assets:
            target = assets[0]
            run_id = target["run_id"]
            logger.info("✓ Using existing asset run_id: %s", run_id)
        else:
            logger.info("Generating new asset for pHash test...")
            gen_res = await client.post(
                f"{BASE_URL}/generate",
                json={"prompt": "Red apple on a dark background", "modality": "image"},
            )
            if gen_res.status_code != 200:
                logger.error("Failed to generate asset: %s", gen_res.text)
                return
            target = gen_res.json()
            run_id = target["run_id"]
            logger.info("✓ Generated asset run_id: %s", run_id)

        asset_url = target.get("b2_asset_url") or target.get("asset_url")
        stored_phash = target.get("phash")
        logger.info("✓ Stored pHash in DB: %s", stored_phash)

        # 3. Download asset bytes or construct test image if asset URL unreachable locally
        image_bytes = None
        if asset_url:
            try:
                img_resp = await client.get(asset_url)
                if img_resp.status_code == 200:
                    image_bytes = img_resp.content
                    logger.info("✓ Downloaded asset bytes (%d bytes)", len(image_bytes))
            except Exception as e:
                logger.warning("Could not download asset directly (%s), using synthetic test image", e)

        if not image_bytes:
            # Create a synthetic image for test
            img = Image.new("RGB", (256, 256), color="red")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()

        # 4. Modify image: Compress to low-quality JPEG & Resize (simulates WhatsApp sharing)
        orig_pil = Image.open(io.BytesIO(image_bytes))
        buf_compressed = io.BytesIO()
        resized_pil = orig_pil.resize((orig_pil.width // 2, orig_pil.height // 2))
        resized_pil.save(buf_compressed, format="JPEG", quality=25)
        compressed_bytes = buf_compressed.getvalue()

        logger.info("✓ Created compressed & resized derivative (%d bytes)", len(compressed_bytes))

        # 5. POST to /public/verify/{run_id}/file
        files = {"file": ("compressed.jpg", compressed_bytes, "image/jpeg")}
        verify_res = await client.post(f"{BASE_URL}/public/verify/{run_id}/file", files=files)
        logger.info("✓ /public/verify/{run_id}/file Status: %s", verify_res.status_code)
        
        verify_data = verify_res.json()
        logger.info("  SHA-256 Match: %s (Expected False due to compression)", verify_data.get("match"))
        
        phash_info = verify_data.get("phash_match")
        if phash_info:
            logger.info("  🎉 pHash Match Result:")
            logger.info("     - Stored pHash:     %s", phash_info.get("stored_phash"))
            logger.info("     - Submitted pHash:  %s", phash_info.get("submitted_phash"))
            logger.info("     - Hamming Distance: %d", phash_info.get("hamming_distance"))
            logger.info("     - Similarity %:     %.1f%%", phash_info.get("similarity_pct"))
            logger.info("     - Perceptual Match: %s", phash_info.get("is_perceptual_match"))
            logger.info("     - Verdict:          '%s'", phash_info.get("verdict"))
        else:
            logger.warning("  No pHash match info returned.")

        # 6. Search endpoint test
        if stored_phash:
            search_res = await client.get(f"{BASE_URL}/public/verify/search", params={"phash": stored_phash, "max_distance": 4})
            logger.info("✓ /public/verify/search Status: %s", search_res.status_code)
            search_data = search_res.json()
            logger.info("  Total Matches Found: %d", search_data.get("total_matches"))

if __name__ == "__main__":
    asyncio.run(main())
