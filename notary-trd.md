# Notary — Technical Requirements Document

**Backblaze Generative Media Hackathon: Build with Genblaze on B2**
Team: Krishna + 1 · Deadline: Aug 3, 2026, 5:00 PM ET
"Notary" is a working name — rename freely, nothing below depends on it.

## 0. One-liner

Every AI-generated image, video, or audio asset gets a notarized, tamper-evident record of exactly how it was made — provider, model, prompt, parameters, timestamp — embedded in the file itself and locked in Backblaze B2, so creators can label, defend, and audit AI media as disclosure law tightens.

---

## 1. Why this wins (rubric mapping)

| Judging criterion | How Notary hits it |
|---|---|
| Real-world utility | India's IT Rules Amendment 2026 (in force since Feb 20, 2026) legally defines "synthetically generated information" and requires visible labeling plus embedded, non-removable provenance metadata for AI images/video/audio. EU AI Act Article 50 marking obligations activate Aug 2, 2026 — the day after this hackathon's deadline. This is a live compliance need, not an invented one. |
| Production readiness | Multi-key provider rotation with graceful fallback, async video generation (no blocking), structured error handling, cost caps, a rebuildable cache — not a single happy-path demo. |
| B2 storage + data orchestration | Object Lock (WORM) on manifests, Lifecycle Rules on scratch data, hierarchical run-grouped key layout, durable credential-free URLs, B2 as sole source of truth with a disposable local cache. |
| Use of Genblaze | Pipeline/Step/Run/Manifest/Sink used as designed. Manifest embedding into the media file itself, native `verify`/`replay`/`index` CLI, and `from_result()` lineage — using the SDK's actual differentiators, not just one `generate()` call. |

---

## 2. Scope (MoSCoW)

### Must — ships or the submission is invalid
- **M1** Generate an image via Google Imagen through a Genblaze Pipeline → B2 (asset + manifest)
- **M2** Generate a video via Google Veo through a Genblaze Pipeline → B2
- **M3** Manifest embedded into the media file itself, persisted alongside it in B2
- **M4** Rotation across 3-4 Google AI Pro API keys — quota error on one triggers retry on the next
- **M5** Web UI: prompt → generate → result → full manifest view (provider, model, prompt, params, timestamp, hash)
- **M6** "Verify" action: recompute hash, compare to manifest, show pass/fail
- **M7** B2 Object Lock enabled on the manifests path
- **M8** GitHub repo, README, setup instructions, b2genblaze access if private
- **M9** Demo video <3 min, public on YouTube
- **M10** Submission text: providers/models used, B2 + Genblaze usage explained

### Should — differentiates, target by end of Day 2
- **S1** "Remix": regenerate from an existing asset with a modified prompt, linked via `from_result()`, shown as a version chain
- **S2** Library/dashboard: searchable list of past generations, backed by a SQLite cache rebuildable from B2 via `genblaze index`
- **S3** Second distinct provider — ElevenLabs (free tier) — generating a spoken disclosure caption per asset
- **S4** Lifecycle rule auto-expiring a `tmp/` scratch prefix after 1 day

### Could — only if ahead of schedule, Day 3 morning
- **C1** One-click "disclosure certificate" export (JSON + human-readable) for external publishing
- **C2** Provider health panel showing which keys/providers are currently rate-limited
- **C3** Auto-critique loop: generate → Gemini `chat()` scores prompt adherence → regenerate once if below threshold, linked as a run chain

### Won't — explicitly cut, don't build, don't apologize for it
- **W1** Auth/multi-tenant accounts — single demo workspace only
- **W2** Payment/billing
- **W3** Actual C2PA cryptographic signing/standards certification — Notary approximates the idea, doesn't claim compliance
- **W4** Mobile polish beyond basic usability
- **W5** Horizontal scaling, load testing

---

## 3. Functional Requirements

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-1 | Generate image (Imagen) via Pipeline | Returns durable B2 asset URL + manifest URI |
| FR-2 | Generate video (Veo) via Pipeline | Same, with async status polling (Veo runs take minutes) |
| FR-3 | Manifest embedded + persisted | `genblaze verify <file>` passes on an unmodified file |
| FR-4 | Multi-key rotation | Exhausting/forcing a 429 on one key doesn't fail the request while another has quota |
| FR-5 | Web UI core views | Prompt input, provider/modality selector, result view, manifest panel |
| FR-6 | Verify action | Recomputes hash, compares to canonical manifest hash, UI shows explicit pass/fail |
| FR-7 | Object Lock | Enabled at bucket creation, applied to manifests path |
| FR-8 | Remix/lineage (S1) | UI shows parent → child version chain via `from_result()` |
| FR-9 | Library + cache (S2) | List view backed by SQLite, rebuildable via `genblaze index` |
| FR-10 | Second provider (S3) | ElevenLabs spoken caption, stored + manifested identically to other assets |
| FR-11 | Lifecycle rule (S4) | `tmp/` prefix expires after 1 day |
| FR-12 | Disclosure certificate (C1) | One-click export, JSON + readable summary |
| FR-13 | Provider health (C2) | Per-key status: ok / rate-limited |
| FR-14 | Auto-critique (C3) | Regenerate once if adherence score below threshold, linked run |

---

## 4. Non-Functional Requirements

- **NFR-1** Reliability: provider failure (timeout/rate-limit) triggers fallback per FR-4, never an unhandled exception to the user
- **NFR-2** Reliability: no partial writes — an asset is never left without its matching manifest or vice versa; failed steps abort cleanly
- **NFR-3** Data integrity: hash mismatches are surfaced explicitly, never silently swallowed
- **NFR-4** Performance: video generation must not block the request thread — async runners (`Pipeline.arun()`) + progress feedback in UI
- **NFR-5** Observability: every run logs run_id, provider, model, latency, outcome (Genblaze Tracer or structured logging)
- **NFR-6** Security: the app's B2 application key is scoped to the `notary-media` bucket only — never the account master key
- **NFR-7** Security: provider API keys are server-side only, never sent to the frontend, never committed to git
- **NFR-8** Cost control: a hard per-session/day generation cap — judges will hit "Generate" live
- **NFR-9** Portability: the SQLite cache is explicitly disposable. Losing it costs query speed, not data — B2 is the only durable state

---

## 5. Architecture

Five layers, one-directional source of truth — the client never writes directly to B2:

1. **React client** (Vite) — three views: Generate, Library, Asset detail/Verify
2. **FastAPI backend** — owns all provider credentials, only thing that talks to Genblaze
3. **SQLite cache** — disposable read-index for the Library view, rebuilt from B2 via `genblaze index`
4. **Genblaze pipeline** — Google provider adapters (`genblaze-google`), optionally ElevenLabs (`genblaze-elevenlabs`), wrapped in a custom key-rotation layer, writing through `ObjectStorageSink` to B2
5. **Backblaze B2** — sole durable store, hierarchical run-grouped keys, Object Lock on write, lifecycle rule on scratch data

### Key-rotation wrapper (your code — not native to Genblaze)

Genblaze's `fallback_models=[...]` retries across *models* within one provider/account on `MODEL_ERROR`. It is **not** cross-account key rotation. With 3-4 separate Google AI Pro accounts (each its own `GEMINI_API_KEY`), you need a thin wrapper:

```python
class MultiKeyGoogleProvider:
    def __init__(self, api_keys: list[str], provider_cls):
        self._keys = api_keys
        self._provider_cls = provider_cls
        self._idx = 0

    def next_provider(self):
        # instantiate provider_cls(api_key=self._keys[self._idx])
        # on quota/rate-limit exception, advance self._idx and retry
        # until keys are exhausted or the call succeeds
        ...
```

Confirm the actual exception type `genblaze_google` raises on quota errors before wiring the catch clause — check the package source on Day 1, don't guess mid-build.

### Genblaze usage (confirmed API, from the actual repo README)

```python
from genblaze_core import Pipeline, Modality, ObjectStorageSink, KeyStrategy
from genblaze_s3 import S3StorageBackend
# from genblaze_google import <exact provider class> — confirm name on Day 1:
#   pip install genblaze-google && python -c "import genblaze_google; print(dir(genblaze_google))"

storage = ObjectStorageSink(
    S3StorageBackend.for_backblaze("notary-media"),
    key_strategy=KeyStrategy.HIERARCHICAL,
)

run, manifest = (
    Pipeline("notary-generate")
    .step(
        google_provider,          # instance from MultiKeyGoogleProvider rotation
        model=model_id,           # confirm current id via that provider's ModelRegistry
        prompt=user_prompt,
        modality=Modality.IMAGE,  # or Modality.VIDEO
    )
    .run(sink=storage, timeout=120)
)

asset_url    = run.steps[0].assets[0].url     # durable B2 URL
sha256       = run.steps[0].assets[0].sha256
manifest_uri = manifest.manifest_uri
verified     = manifest.verify()
```

Lineage (FR-8, remix):

```python
v2 = Pipeline("notary-generate").from_result(v1).step(
    google_provider, model=model_id,
    prompt=refined_prompt, modality=Modality.IMAGE,
).run(sink=storage, timeout=120)
# v2.manifest.parent_run_id -> v1's run_id, excluded from v2's own canonical hash
```

Verify (FR-6) — two layers, deliberately redundant against different threats:
- **Client-side/portable**: embed the manifest into the file (`Mp4Handler` for video — check `docs/features/media.md` in the repo for the image-format handler name), then `genblaze verify <file>` — catches tampering with a copy of the file after it left B2.
- **Server-side**: B2 Object Lock on the manifests path — catches tampering with the canonical copy still in your own bucket (insider/compromised-credential threat, not covered by the client-side check).

Rebuilding the cache (FR-9):

```
genblaze index manifest.json -o ./
```

Run this over every manifest under `runs/` to rebuild the SQLite/Parquet index if it's ever lost. Actually test this once before the demo — don't leave it untested until judging.

---

## 6. Data Model

**Manifest** (Genblaze's own schema — don't reinvent it): provider, model, prompt, params, timestamps, run_id, parent_run_id (present but excluded from the canonical hash), asset list (url, sha256, mime type, per-modality metadata), canonical_hash.

**SQLite cache** (yours, derived from manifests):

```sql
CREATE TABLE assets (
  run_id TEXT PRIMARY KEY,
  parent_run_id TEXT,
  provider TEXT,
  model TEXT,
  modality TEXT,
  prompt TEXT,
  b2_asset_url TEXT,
  b2_manifest_url TEXT,
  sha256 TEXT,
  created_at TEXT,
  last_verified_at TEXT,
  verify_status TEXT
);
```

---

## 7. B2 Bucket Layout & Policies

Bucket: `notary-media`. `KeyStrategy.HIERARCHICAL` (run-grouped, matches Genblaze's default):

```
notary-media/runs/{tenant}/{date}/{run_id}/manifest.json
notary-media/runs/{tenant}/{date}/{run_id}/assets/{asset_id}.{ext}
notary-media/tmp/...                      <- lifecycle: expire after 1 day
```

**Object Lock**: enable File Lock at bucket creation in the B2 console — verify whether your tier allows retrofitting it onto an existing bucket before assuming you can add it later; safest is to enable it before writing a single object. Governance mode, short retention (1-2 days is enough to survive the Aug 5-11 judging window).

**Application key**: create a scoped B2 key limited to `notary-media` only (read+write, no key-management, no other-bucket access) — never the account master key (NFR-6).

---

## 8. API Surface (FastAPI)

```
POST /generate {prompt, modality, provider?}     -> {run_id, status}
GET  /assets?limit=&provider=&modality=          -> list from SQLite cache
GET  /assets/{run_id}                            -> full manifest + asset URL
POST /assets/{run_id}/verify                     -> {match, computed_hash, manifest_hash}
POST /assets/{run_id}/remix {prompt}              -> new run via from_result()
POST /admin/reindex                              -> rebuild cache from B2 via genblaze index
GET  /health                                      -> per-key status across the Google key pool
```

---

## 9. Team Split

- **Person A (backend/pipeline)**: Genblaze integration, MultiKeyGoogleProvider wrapper, B2 bucket + Object Lock + app key, verify endpoint, cache rebuild
- **Person B (frontend + submission)**: React UI (three views), demo video, README, GitHub repo hygiene incl. b2genblaze access grant, submission form text, the Genblaze feedback GitHub issue

---

## 10. Day-by-Day Plan

**Day 1 (Aug 1 — today)**
- Create `notary-media` bucket **with File Lock enabled at creation**. Create a scoped application key.
- Activate Google AI Pro dev credits on all 3-4 accounts (google.dev → Activate Developer Benefits → attach a Cloud project each). Write down account ↔ `GEMINI_API_KEY` mapping somewhere durable.
- `pip install genblaze-core genblaze-s3 genblaze-google`. Run `examples/quickstart_local.py` (zero external calls) to confirm the install works before spending real API calls.
- Confirm `genblaze_google`'s exact provider class names and current model ids.
- Get one real image generation round-tripping: prompt → Imagen → B2 (asset + manifest) → print URL and hash. **This is the single most important thing to finish today.**

**Day 2 (Aug 2)**
- Video path (Veo) working the same way.
- MultiKeyGoogleProvider wrapper with real rotation — test by deliberately exhausting one key.
- Manifest embed + verify round-trip (FR-3, FR-6) — test by manually corrupting a downloaded file and confirming verify fails.
- Object Lock actually configured and tested (try to overwrite/delete a locked manifest, confirm B2 refuses).
- Basic FastAPI endpoints wired to real logic, basic React UI hitting them for real.
- If ahead: start Should-tier items.

**Day 3 (Aug 3, submission by 5:00 PM ET)**
- Feature freeze by midday — stop building, start polishing and recording.
- Record the demo video (<3 min): real generation → manifest → verify passing → **verify failing on a tampered copy**. That failing-verify moment is your strongest visual — don't cut it for time.
- README (setup instructions that actually work from a clean clone), submission text.
- Grant `b2genblaze` GitHub access if the repo is private.
- Submit with real time to spare — not at 4:58 PM.
- File the Genblaze SDK feedback GitHub issue (a real bug/friction you hit) — stacks with an Overall Prize, near-zero marginal cost, do it.

---

## 11. Submission Checklist (from the Official Rules)

- [ ] Working app URL judges can access without you present
- [ ] "No login required" stated explicitly (Notary has no auth by design — W1)
- [ ] Public/private GitHub repo; if private, grant github.com/b2genblaze access
- [ ] Text description: features, B2 + Genblaze usage, AI providers/models list
- [ ] Demo video, <3 min, public on YouTube/Vimeo/Youku
- [ ] Genblaze feedback GitHub issue filed (Feedback Prize)

---

## 12. Risks

- GMI Cloud confirmed unavailable (credits form closed) — mitigated by the Google AI Pro multi-key plan. Don't spend more time on GMI.
- Veo latency could make live judge testing feel slow — have 2-3 assets already in the Library before judges arrive, so the instant parts of the demo (library, verify, tamper-detection) don't depend on live generation finishing in real time.
- B2 Object Lock retrofit risk — deliberately a Day 1 task to avoid discovering a problem on Day 3.
- Two people sharing 3-4 Google accounts — keep one written source of truth for which key belongs to which account/project, in a gitignored file, not memory.
