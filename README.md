# Notary

Notary is a provenance and verification workspace for AI-generated images and videos. Every generated asset runs through a Genblaze `Pipeline`, is persisted with its canonical Genblaze manifest in Backblaze B2, and has B2 File Lock retention applied to that manifest.

## Why it matters

Marketing, legal, and newsroom teams need to know whether a published AI asset is the exact asset approved by their workflow. Notary creates a durable provenance record, verifies a submitted copy against the canonical B2 asset, and gives anyone a shareable verification URL.

The three product layers beyond storage and generation are:

- Compliance scorecards for India SGI transparency requirements and EU AI Act Article 50. Image records include an inline Genblaze manifest, but Notary does not claim C2PA signing or standards certification.
- Forensic comparison: on a hash mismatch with a submitted file, Gemini Vision compares the B2 canonical original and submitted copy and describes the observed modification. Hash verification still completes if Gemini is unavailable.
- Public verification portal at `/verify/{run_id}` with browser-side SHA-256 and optional file upload for forensic analysis.

## Genblaze and B2 usage

Every image provider is executed through `genblaze_core.Pipeline`. `ObjectStorageSink` writes output assets and canonical manifests to the B2 S3-compatible backend using hierarchical run keys. The sink applies `ObjectLockConfig` to every manifest; B2 File Lock must be enabled when the bucket is created.

The image cascade is Google Gemini Image (rotating configured Google keys on quota), NVIDIA NIM FLUX.1 Schnell, the public Hugging Face `black-forest-labs/FLUX.2-klein-4B` Space, then Pollinations FLUX when `POLLINATIONS_API_KEY` is configured. The Hugging Face Space uses `HF_TOKEN` only for backend transport authentication and quota; it is never stored in B2. Every successful output still passes through Genblaze and B2. Video uses Google Veo through the same pipeline.

Before generation, the creator can select a policy profile. Notary evaluates transparent deterministic rules and never rewrites a prompt silently: warnings require acknowledgement and blocks explain the matched rule. After generation, an optional Gemini Vision pixel audit can be enabled with `POST_GENERATION_VISUAL_AUDIT=true`; its result is stored in a separate B2 File Lock policy-audit manifest linked to the final M1 receipt. A disabled or unavailable visual audit is reported as unavailable, never as a pass. Policy assessment and cryptographic file verification are intentionally separate.

## Setup

Prerequisites: Python 3.11+, Node 18+, and a Backblaze B2 bucket created with File Lock enabled. `HF_TOKEN` is optional for the public Space fallback; Google, NVIDIA, and Pollinations credentials enable their respective stages.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# configure B2 credentials, File Lock settings, and at least one provider
uvicorn main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. For browser previews from a private bucket, deploy a signed-URL/proxy layer or configure an approved public/CDN B2 URL via `B2_PUBLIC_URL_BASE`.

## Verification model

For images, Notary uses a two-record chain to avoid a self-referential hash: M0 records raw generation and is embedded unchanged in the derived image; M1 is a locked Genblaze transform receipt whose output SHA-256 is computed over the final embedded bytes. The public run ID is M1. File verification validates M1, extracts and validates M0, checks their parent/receipt linkage, and compares the submitted final-file hash to M1. A single-byte post-embed modification therefore fails verification. Video uses its canonical manifest and output hash without an inline image manifest. `POST /public/verify/{run_id}` compares a browser-computed hash, while `/file` performs the complete file check and invokes forensics on a mismatch. `POST /admin/audit` paginates B2 manifests and repeats the canonical-manifest-plus-asset check for the archive.

## Providers

- Google: `gemini-2.5-flash-image`, `veo-3.0-generate-001`
- NVIDIA NIM: `black-forest-labs/flux.1-schnell`
- Hugging Face public Space: `black-forest-labs/FLUX.2-klein-4B`
- Pollinations (optional): `flux`
- Forensics: Gemini 2.0 Flash Vision
