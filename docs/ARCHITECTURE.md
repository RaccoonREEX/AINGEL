# AINGEL architecture — initial design, 2026-10-26

Adaptive Intelligence for Navigation, Guidance & Everyday Living. One multimodal companion with evidence-backed memory. Evidence before assertion.

## Proposed production topology

```mermaid
flowchart TD
  Android[Android Kotlin Compose CameraX TTS] -->|HTTPS| API[Django REST API and authentication]
  Web[React TypeScript Vite Care and demo] -->|HTTPS| API
  Android -->|authenticated WSS| Voice[Channels bounded audio relay]
  Web -->|authenticated WSS| Voice
  Voice -->|PCM handshake with server secret| STT[Meta Voice Transcribe]
  API --> Auth[Owner and Care Circle permission checks]
  Auth --> Tools[Bounded tool dispatcher]
  Tools --> Spark[Meta Muse Spark 1.3 Standard]
  Tools --> SAM[Meta SAM 3.1]
  Tools --> Memory[Evidence and structured memory services]
  Memory --> DB[(PostgreSQL)]
  Memory --> Media[Private evidence storage]
  Tools --> Care[Routines and original family messages]
  Care --> DB
  API --> Locale[Locale and capability policy]
```

```mermaid
flowchart LR
  Halo[Future Halo: camera mic haptics privacy shutter] --> Phone[Paired Android gateway]
  Phone --> Backend[Same AINGEL APIs]
  Halo -. research only .-> Edge[Measured Glimmer edge inference]
```

## Decisions

Use Kotlin/Compose/CameraX/AudioRecord/OkHttp/Android TTS for Android, React/TypeScript/Vite with centralized resources for web, Django/DRF for backend. PostgreSQL in production; SQLite may support local scaffold tests. Add Channels for live audio. Redis only when needed for channel coordination or rate limiting; Celery is deferred until a measured background job needs it. Avoid a vector database for exact object/event retrieval.

Start with one scene endpoint: authenticated image upload, bounded decode/re-encode without EXIF, server-side Meta request, concise locale-aware text, explicit mock/meta provenance, latency. No implicit media persistence. Use direct HTTP to Meta Responses API; parse output content rather than assuming SDK-only convenience properties.

Then SAM grounding with its documented special-token parser, then explicit-confirmation memory saves and deterministic retrieval, then live voice. Ask tools are allowlisted with schema validation, profile scoping, turn/token ceilings and no arbitrary model-selected URLs or SQL. Tools that write require user intent. Image text and caregiver messages are data, never system instructions.

## Minimal persistence plan

Start with user/assisted profile and accessibility preferences. Add memory events referencing private evidence (UUID, owner, observed_at, source, retention, confidence origin, confirmation). Care membership grants explicit scopes, expiration/revocation; every read/write checks membership and owner. Routines and messages retain author, original language and timestamps. No facial identity or diagnostic profile key.

Missing memory yields a deterministic no-evidence result; an LLM never supplies a missing factual location. Last-seen evidence is historical, never proof of current position or completed medical routines. Do not fabricate confidence from prose. Deleting evidence invalidates linked memory claims. Use UTC storage and user timezone presentation.

## Status at takeover

Implemented now: authenticated Django/DRF scene endpoint, bounded image normalization, explicit mock adapter, server-side Meta HTTP adapter with synthetic-fixture gate and nine passing boundary tests. Meta adapter tests use a stub; no real model call is claimed. SQLite is local only. No Android APK, web product, deployment or complete memory/Care flow exists yet. Roadmap diagrams are not deployed functionality.

## Acceptance gates

Scene: real synthetic-image Meta call through backend; unsupported/corrupt/oversize image rejection; no leaked key/media. Memory: latest matching owner evidence, no-evidence response, cross-user denial, deletion and stale evidence tests. Voice: correct handshake, partial replacement, disconnect/backpressure and unsupported-language handling. Care: explicit grants, revocation and provenance. UI: keyboard/TalkBack, contrast, 200–400% zoom, narrow layout, reduced motion, large text and RTL. Production: HTTPS, backups/restore, quotas, private media and no debug exposure.
