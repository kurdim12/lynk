# AI Product Specialist Engine

A real-time, bilingual (Arabic + English), brand-safe digital product
specialist. A visitor speaks to an avatar; it answers **only** from a brand's
approved knowledge base, in the visitor's language, with synchronized voice and
lip-sync.

Built as a multi-tenant engine, not a one-off: **one brand = one config file +
its approved docs.** Lynk & Co is tenant #1.

## Pipeline

```
WebRTC mic ─▶ Deepgram STT (AR/EN) ─▶ RAG grounding ─▶ Claude (brand-safe)
            ─▶ ElevenLabs TTS (Levantine) ─▶ Simli (lip-synced video) ─▶ kiosk
```

Orchestrated by **Pipecat 1.4** (WebRTC transport, VAD, barge-in, turn-taking).
Every provider sits behind its interface — that's where the fallbacks plug in.

## Layout

```
server/
├── config.py            # env + tenant loader (ENV: refs keep secrets out of JSON)
├── tenants/
│   └── lynk-and-co.json # tenant #1: persona, languages, provider models, KB settings
├── data/lynk-and-co/    # the brand's APPROVED docs (replace the placeholder file)
├── kb/                  # chunker · embedder · vector store · retriever · ingest
├── brain/               # system prompt (brand-safety contract) · RAG grounding
├── fallbacks.py         # provider fallback chains · audio-only · readiness
├── cache.py             # pre-rendered answer cache (last line of the fallback chain)
├── bot.py               # the Pipecat pipeline
└── app.py               # FastAPI: health/status + WebRTC /offer signaling
kiosk/                   # Next.js portrait-totem kiosk (AR/EN, attract loop, QR, WebRTC)
scripts/
├── demo_kb.py           # offline demo of the KB brain (no keys)
├── onboard_tenant.py    # scaffold a new brand (config + placeholder docs)
└── prerender_cache.py   # render a tenant's FAQ answers into the cache
tests/                   # offline test suite (no keys)
```

## The SaaS seam

A brand is one JSON file in `tenants/` + approved docs in `data/<tenant>/`.
Onboarding = add those, run ingest. No code changes. The in-memory KB is the
event default (no DB to fail on the floor); `PgVectorStore` is the same interface
for SaaS scale.

## Run

All commands run from the repo root.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env          # fill in keys

# Build the KB index from approved docs:
python -m server.kb.ingest lynk-and-co

# API (health / KB status / readiness):
uvicorn server.app:app --reload --port 8000
#   GET /health
#   GET /tenants/lynk-and-co/status  -> kb_chunks, missing_keys, live_ready
```

## Try the KB brain with no keys (offline)

The whole grounding flow runs with a deterministic, dependency-free embedder —
no API keys, no network:

```bash
EMBEDDER=stub python -m server.kb.ingest lynk-and-co
EMBEDDER=stub python scripts/demo_kb.py        # asks AR + EN questions, shows grounding
```

The demo asks English and Arabic questions plus an off-topic one, and prints the
retrieved approved passages and the assembled brand-safety prompt — including the
safe "I don't have that" path when nothing relevant is found. (If
`ANTHROPIC_API_KEY` is set, it also generates the avatar's real spoken answer.)

## Onboard another brand (the SaaS seam)

```bash
python scripts/onboard_tenant.py acme-motors --name "Acme Motors" --languages ar,en
# → replace the placeholder doc with approved docs, then:
EMBEDDER=stub python -m server.kb.ingest acme-motors
```

`aurora-ev` ships as a worked second tenant. Each tenant has its own config,
approved docs, KB index, voice, and avatar — no code changes to add one.

## Fallbacks

Every provider can declare a `fallback` in the tenant config; the bot uses the
first one whose credentials are set, and runs **audio-only** when no avatar is
ready. Pre-render FAQ answers as a last-resort cache:

```bash
EMBEDDER=stub python scripts/prerender_cache.py lynk-and-co   # offline (stub answers)
python scripts/prerender_cache.py lynk-and-co                 # real answers with a key
```

`/tenants/<id>/status` reports per-provider readiness, `audio_only_capable`, and
`cached_answers`.

## Kiosk

A Next.js portrait-totem front-end (`kiosk/`): AR/EN with RTL, an attract loop,
QR lead capture, and a WebRTC client that calls `/offer`. See `kiosk/README.md`.

```bash
cd kiosk && npm install && npm run build      # builds + type-checks (no browser needed)
```

## Tests

```bash
pip install -r server/requirements-dev.txt
python -m pytest
```

The suite is fully offline (stub embedder, no keys): config + tenant loader,
chunker, embedder, vector store, retriever, system prompt, RAG grounding, the
full ingest → retrieve → ground flow in Arabic and English, and the FastAPI
health/status endpoints.

## Status

**Verified here (runs offline, covered by tests):** config + tenant loader,
chunker, embedder (stub), vector store + store factory, retriever, brand-safety
system prompt, RAG grounding, full ingest → retrieve → ground flow in Arabic and
English, multi-tenant isolation + onboarding scaffolder, provider fallback chains
+ audio-only decisioning, the pre-rendered answer cache, and the API
health/status endpoints. The Next.js kiosk builds and type-checks (`npm run
build`).

**Runs on your machine (needs keys + a browser/mic):** the Pipecat bot
(`server/bot.py`) and the WebRTC `/offer` endpoint. A live voice/video loop can't
run in a sandbox, so validate it on first run with keys set. Its pieces are wired
against the real Pipecat 1.4 API (verified by introspection):
`LLMContext` + `LLMContextAggregatorPair`, `SmallWebRTCTransport`,
`SileroVADAnalyzer`, and the `AnthropicLLMService` / `DeepgramSTTService` /
`ElevenLabsTTSService` / `SimliVideoService` constructors.

## Before live use

- Replace `server/data/lynk-and-co/vehicle-info.md` (a **placeholder**) with the
  brand's approved spec sheet. The avatar says only what's in these files.
- Set the cloned Levantine `ELEVENLABS_VOICE_ID` and the brand's `SIMLI_FACE_ID`.
- The tenant config uses `voyage` as the production embedder (`VOYAGE_API_KEY`).
  Re-run ingest without `EMBEDDER=stub` to build a semantic index.
  **`kb.min_score` is embedder-specific** — the shipped `0.12` is tuned for the
  offline stub; retune it for Voyage so off-topic questions fall below the floor.
- The live loop needs the Pipecat extras (already in `requirements.txt`):
  `pip install 'pipecat-ai[anthropic,deepgram,elevenlabs,simli,silero,webrtc]'`.

## Next

The roadmap items — kiosk, first-class fallbacks, and `PgVectorStore` +
tenant #2 — are now built and verified offline. What remains is live validation
and production data:

1. Run the live loop end-to-end with keys + a browser/mic; validate the kiosk's
   WebRTC client against the running `/offer`.
2. Replace the placeholder docs with each brand's approved spec sheets; set the
   cloned Levantine voice and the brand's Simli face; retune `min_score` for the
   production (Voyage) embedder.
3. Point a tenant at a live Postgres (`vector_store: pgvector` + `DATABASE_URL`)
   and validate `PgVectorStore` against it.
```
