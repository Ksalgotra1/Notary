# meta.md — Agent Operating Instructions

## Read order
1. `notary-trd.md` — the spec. What to build, why, in what order.
2. This file — how to work while building it, and current status.

Read both in full before writing any code. The TRD alone isn't enough context — this file carries state the TRD doesn't (what's resolved, what's still open, what's off-limits).

## Ground truth hierarchy
- `notary-trd.md` is the spec. Don't deviate from Must-tier scope. Don't build anything in the Won't list, even if it looks easy — that's scope creep against an explicit decision, not an oversight.
- This file governs process: build order, verification gates, when to stop and ask.
- If the TRD and reality conflict (a genblaze API doesn't exist as described), reality wins — but log it below before proceeding, and if it changes the architecture meaningfully, stop and ask rather than silently improvising around it.

## Current status
Source of truth for progress — more reliable than trusting a previous session's memory. Check items off only when genuinely done (tested, not just written).

**Day 1**
- [ ] `notary-media` B2 bucket created with File Lock enabled at creation
- [ ] Scoped B2 application key created (not master key)
- [ ] Google AI Pro dev credits activated on all accounts in use; key↔account map recorded in `.env.accounts` (gitignored)
- [ ] `genblaze-core genblaze-s3 genblaze-google` installed; `quickstart_local.py` runs clean
- [ ] `genblaze_google` exact provider class names + model ids confirmed (see Decisions Log)
- [ ] First real image generation round-trips: prompt → Imagen → B2 → hash printed

**Day 2**
- [ ] Video path (Veo) working end to end
- [ ] MultiKeyGoogleProvider rotation tested (force one key to exhaustion)
- [ ] Manifest embed + verify tested against a deliberately corrupted file
- [ ] Object Lock tested (attempt to overwrite/delete a locked manifest, confirm refusal)
- [ ] FastAPI endpoints wired to real logic (no mocked responses)
- [ ] React UI hitting the real backend

**Day 3**
- [ ] Feature freeze
- [ ] Demo video recorded, including a verify-failure shot
- [ ] README + submission text written
- [ ] b2genblaze access granted if repo private
- [ ] Submitted on Devpost
- [ ] Genblaze feedback GitHub issue filed

## Decisions Log
The TRD flags several things as "confirm before building" rather than asserting them as fact, because they weren't verified against the actual `genblaze_google` source. Every time one resolves, write it here so it isn't re-derived or re-guessed in a later session.

Template:
```
### <date> — <question>
Answer: <what you found>
Source: <file/command that confirmed it>
```

Known open items:
- Exact class names in `genblaze_google` (image provider, video provider)
- Current Imagen/Veo model id strings in that provider's `ModelRegistry` defaults
- Exact exception type raised on quota/rate-limit errors (needed for `MultiKeyGoogleProvider`'s catch clause)
- Whether B2 Object Lock can be retrofitted onto an existing bucket, or must be set at creation
- Exact media-embed handler name for images (`Mp4Handler` is confirmed for video; the image equivalent isn't)

## Verification gates — definition of done
Code compiling is not done.
- **M1/M2**: a real asset URL and real SHA-256 hash printed from an actual run, not a mock
- **M3**: `genblaze verify <file>` returns true on the unmodified output of a real run
- **M4**: a test deliberately exhausts one key's quota and the pipeline completes anyway on another key
- **M6**: a deliberately corrupted copy of a real asset fails verify; an unmodified copy passes
- **M7**: an attempt to overwrite or delete a locked manifest is refused
- **Cache rebuild**: the cache has actually been deleted and rebuilt from B2 at least once before Day 3

## Coding conventions
- Python 3.11+, type hints on all function signatures
- Async FastAPI handlers for anything calling a Genblaze pipeline (`Pipeline.arun()`) — video generation is slow, don't block the event loop
- Every provider call wrapped in explicit exception handling per NFR-1 — no bare `except: pass`, no unhandled exception reaching the client as a raw 500
- Secrets in `.env`, never hardcoded, never logged, never committed — verify `.gitignore` covers it before the first commit
- No print-debugging left in code that reaches Day 3 — use actual logging

## When to proceed autonomously vs. stop and ask
**Proceed without asking**: implementation details within a Must/Should item that don't change the TRD's architecture — variable names, internal function structure, dependency-injection pattern, etc.

**Stop and ask Krishna before**:
- Touching anything in the Won't-scope list
- Any change to the B2 bucket layout or Object Lock config after it's been set once
- A genblaze API doesn't match what the TRD assumed and the fix isn't a one-line correction
- Day 2 is ending and Must-tier items aren't done — that's a scope conversation, not something to solve by quietly cutting NFR corners

## Repo layout (proposed)
```
notary/
  notary-trd.md
  meta.md
  backend/
    main.py              # FastAPI app
    pipeline.py          # Genblaze integration, MultiKeyGoogleProvider
    cache.py             # SQLite cache + rebuild logic
    .env.example
  frontend/
    src/
  README.md
```
