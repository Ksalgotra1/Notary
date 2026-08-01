# Notary

**Tamper-evident provenance for AI-generated media**

Backblaze Generative Media Hackathon · Team: Krishna + 1 · Deadline: Aug 3, 2026

---

## What it does

Every AI-generated image, video, or audio asset gets a notarized, tamper-evident record of exactly how it was made — provider, model, prompt, parameters, timestamp — embedded in the file itself and locked in Backblaze B2.

Three differentiating features on top of the provenance pipeline:

1. **Compliance Engine** — evaluates each asset against India IT Rules 2026 + EU AI Act Article 50 and produces a per-requirement pass/fail scorecard with actionable recommendations
2. **AI Forensic Verification** — when hash verification fails, Gemini Vision analyzes *what* was tampered (text overlay, color shift, cropping, etc.), not just *that* it was tampered
3. **Public Verification Portal** — a shareable `/verify/{run_id}` URL anyone can visit without login to see provenance info and verify a copy of the file

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Backblaze B2 account with `notary-media` bucket (File Lock enabled)
- Google AI Pro API key(s) or GitHub PAT / Pollinations fallback (zero-auth resilient cascade)

### Backend
```bash
cd backend/
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your B2 credentials and provider keys
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend/
npm install
npm run dev
```

Visit `http://localhost:5173`

---

## Architecture

```
React (Vite)  →  FastAPI  →  Provider Cascade Pipeline  →  Backblaze B2
                                    │
            ┌───────────────────────┼───────────────────────┐
            ↓                       ↓                       ↓
     Google Genblaze         GitHub Models            Pollinations.ai
 (GeminiImage / Key-Rotate)   (gpt-image-1)           (FLUX Fallback)
                                    │
                                    ↓
                             compliance.py   (India IT Rules + EU AI Act)
                             forensics.py    (Gemini Vision tamper analysis)
```

- **B2 Storage**: B2 is the sole durable store. The SQLite cache is a disposable read-index.
- **Resilient Cascade**: Automatically tries Google Genblaze (with multi-key account rotation) → GitHub Models → Pollinations.ai FLUX (zero-auth fallback).
- **Security**: Provider API keys never reach the frontend.
- **WORM Compliance**: Manifests are WORM-locked via B2 Object Lock.

---

## Tech stack

- **Backend**: FastAPI, Python 3.11+, aiosqlite
- **Pipeline & Storage**: Genblaze (`genblaze-core`, `genblaze-s3`, `genblaze-google`), Backblaze B2 (Object Lock + Lifecycle Rules)
- **AI Providers**: Google Gemini/Imagen, GitHub Models, Pollinations.ai (FLUX), Gemini 2.0 Flash (Forensics Vision)
- **Frontend**: React (Vite), Vanilla CSS, Axios, React Router

---

## No login required

This is a single-workspace demo. No authentication by design.
