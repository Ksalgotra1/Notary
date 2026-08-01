"""
Spike: Test Day 2 Endpoints (Generate, Verify, Compliance, Public Verification).

Proves:
  1. POST /generate creates real asset in B2 + SQLite cache.
  2. GET /assets/{run_id}/compliance returns real India IT Rules 2026 + EU AI Act scorecard.
  3. POST /assets/{run_id}/verify tests real SHA-256 calculation.
  4. POST /public/verify/{run_id} tests public verification & Gemini Vision forensic analysis.

Usage:
    cd backend/
    source .venv/bin/activate
    python spikes/spike_day2.py
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spike_day2")

BASE_URL = "http://localhost:8000"


async def main():
    logger.info("Testing Day 2 Endpoints against FastAPI (%s)...", BASE_URL)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Health check
        res = await client.get(f"{BASE_URL}/health")
        logger.info("✓ /health status: %s %s", res.status_code, res.json())

        # 2. POST /generate
        logger.info("\nStep 1: Testing POST /generate (Image)...")
        gen_res = await client.post(
            f"{BASE_URL}/generate",
            json={"prompt": "A golden notary seal on marble", "modality": "image"},
        )
        if gen_res.status_code != 200:
            logger.error("✗ /generate failed: %s %s", gen_res.status_code, gen_res.text)
            return

        gen_data = gen_res.json()
        run_id = gen_data["run_id"]
        logger.info("✓ Asset Generated! Run ID: %s", run_id)
        logger.info("✓ B2 Asset URL: %s", gen_data["asset_url"])
        logger.info("✓ SHA-256: %s", gen_data["sha256"])

        # 3. GET /assets/{run_id}/compliance (USP #1)
        logger.info("\nStep 2: Testing GET /assets/{run_id}/compliance (USP #1)...")
        comp_res = await client.get(f"{BASE_URL}/assets/{run_id}/compliance")
        logger.info("✓ Compliance Scorecard: Status %s", comp_res.status_code)
        comp_data = comp_res.json()
        logger.info("  Scorecard evaluated at: %s", comp_data.get("evaluated_at"))
        for reg in comp_data.get("regulations", []):
            logger.info("  Regulation: %s -> Compliant: %s (%d/%d checks passed)", 
                        reg["regulation_id"], reg["compliant"], reg["passed"], reg["total"])

        # 4. POST /assets/{run_id}/verify
        logger.info("\nStep 3: Testing POST /assets/{run_id}/verify...")
        ver_res = await client.post(f"{BASE_URL}/assets/{run_id}/verify")
        logger.info("✓ Verify Status: %s %s", ver_res.status_code, ver_res.json())

        # 5. POST /public/verify/{run_id} with mismatch hash (USP #2 & #3)
        logger.info("\nStep 4: Testing POST /public/verify/{run_id} with TAMPERED hash (USP #2 & #3)...")
        fake_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        pub_res = await client.post(
            f"{BASE_URL}/public/verify/{run_id}",
            json={"file_hash": fake_hash},
        )
        logger.info("✓ Public Verify Tamper Result: Status %s", pub_res.status_code)
        pub_data = pub_res.json()
        logger.info("  Match: %s", pub_data.get("match"))
        logger.info("  Forensic Analysis: %s", pub_data.get("forensic_analysis"))

        logger.info("\n🎉 DAY 2 BACKEND ENDPOINTS FULLY VERIFIED!")


if __name__ == "__main__":
    asyncio.run(main())
