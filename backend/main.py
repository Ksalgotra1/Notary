"""
Notary — FastAPI backend
All provider credentials stay server-side (NFR-7).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cache import init_db
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Notary API",
    description="Tamper-evident provenance for AI-generated media",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
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
        "b2_bucket": os.getenv("B2_BUCKET_NAME", "notary-media"),
        "b2_region": os.getenv("B2_REGION", "us-east-005"),
    }
