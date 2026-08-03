"""
Notary — FastAPI backend
All provider credentials stay server-side (NFR-7).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
from cache import init_db
from routes import router
from metrics import init_metrics_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_metrics_db()
    yield


app = FastAPI(
    title="Notary API",
    description="Tamper-evident provenance for AI-generated media",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    """Health & provider status endpoint."""
    import os
    keys = [k for k in os.getenv("GOOGLE_API_KEYS", "").split(",") if k.strip()]
    return {
        "status": "ok",
        "google_keys_configured": len(keys),
        "nvidia_key_configured": bool(os.getenv("NVIDIA_API_KEY")),
        # HuggingFace and Pollinations are always available as free-tier fallbacks
        "huggingface_available": True,
        "pollinations_available": True,
        "b2_bucket": os.getenv("B2_BUCKET_NAME", "notary-media"),
        "b2_region": os.getenv("B2_REGION", "us-east-005"),
        "b2_file_lock_required": True,
        "b2_object_lock_requested": os.getenv("B2_OBJECT_LOCK_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
    }
