# AINGEL

**Adaptive Intelligence for Navigation, Guidance & Everyday Living**

AINGEL is a multimodal accessibility assistant for adults with visual, hearing and communication support needs. It
describes what the camera or the screen shows, reads documents aloud, captions speech and computer audio, and holds a
natural conversation — using Meta's models, under each person's own consent, on the web, on Android and on Windows.

**Live product:** <https://aingel.mapatechstudio.com> · **Hackathon:** Meta Global AI Developer Hackathon 2026 ·
**Track:** Indie Developer · **Theme:** Build for Your World

> **Resumen ejecutivo (español).** AINGEL es un asistente de accesibilidad para personas adultas con necesidades de
> apoyo visual, auditivo o de comunicación. Describe lo que muestra la cámara o la pantalla —distinguiendo
> fotografías de dibujos, describiendo en un dibujo la figura antes que sus trazos, priorizando la expresión aparente
> de las personas y el contenido de vídeos, fotos y documentos—, lee documentos, subtitula la voz y el audio
> del equipo, y conversa con naturalidad. Usa modelos Standard de Meta (Muse Spark 1.3, Muse Voice Transcribe y
> SAM 3.1) solo con el consentimiento expreso de cada persona, por finalidad y revocable en cualquier momento. Funciona
> en web, Android y Windows, y está desplegado en <https://aingel.mapatechstudio.com>. No es un dispositivo médico, el
> reconocimiento facial está desactivado y las señas son ilustrativas, no una traducción certificada de LSEC.

## The problem

People who are blind or have low vision, who are deaf or hard of hearing, or who communicate differently still meet
a world built for one way of seeing, hearing and speaking: a photo in a chat, a scanned letter, a video call without
captions, a face whose expression they cannot read. Existing tools usually cover one sense on one device. AINGEL puts
those supports in one assistant that follows the person across phone, browser and computer, and asks them before any
of their data leaves the server.

## What AINGEL does today

| Need | What AINGEL does | Meta model |
|---|---|---|
| "What is in front of me?" | Describes a photo at four levels (brief, standard, detailed, deep). Deep makes two passes in parallel, one over the whole picture and one over five enlarged regions, then a synthesis. Follow-up questions about the same picture for 15 minutes. | Muse Spark 1.3 |
| "Is this a photo or a drawing?" | Decides from the image itself, in the same call, whether it is a photograph, a drawing, a digital illustration, a painting, a photo of a sheet with a drawing, a document or uncertain. In a drawing it describes the figure first (what it represents, its orientation, proportions and features) and the technique after (lines, strokes, shading), never mistaking a stroke for a feature; a photo gets no talk of strokes. | Muse Spark 1.3 |
| "How does this person look?" | Leads with the person's **apparent** expression and the visible cues for it, then appearance and context — never claiming to know how anyone feels. Says the head's orientation and describes only what that view shows: an eye or ear hidden in a profile is never described. | Muse Spark 1.3 |
| "Where are my keys?" | Finds a named object in a photo and returns its position. | SAM 3.1 |
| "What is on my screen?" (Windows) | Hotkeys describe the active window or the whole screen, focusing on the video, photo, document or chart shown — not on Windows itself. The interface is described only when asked. | Muse Spark 1.3 |
| "Read me this" | Opens PDFs and photos of pages: text is read locally; scanned pages are transcribed, and pages explained or questioned on request. | Muse Spark 1.3 |
| "What are they saying?" | Live captions of the person's own voice (web, Android) and of the computer's audio, such as a video call (Windows). | Muse Voice Transcribe 1.0 |
| Conversation | A warm, natural assistant that can search the web when needed and trigger the app's own tools by voice. | Muse Spark 1.3 (with web search) |
| Signs | A 3D signing avatar for the alphabet, numbers and 43 words — **illustrative designs**, shown as validated only after signers approve them in the sign registry (none is validated yet). | — |

Around them: routines, reminders and a support circle of up to four caregivers; per-profile accessibility
preferences (large text, contrast, pace, form of address); English and Spanish interfaces; TOTP two-factor
authentication.

## Privacy and safety by design

- **Adults only:** sign-up requires a self-declaration of being 18 or older, as Meta's terms require.
- **Restricted territories:** sign-up asks whether the person is in a territory where Meta does not allow its AI.
  - Answering yes creates no account.
  - Existing accounts answer once.
  - A proxy-provided country code can add a technical check.
- **Consent per purpose, never by default:** conversation, photos, screen, documents, own voice, computer audio,
  video and personalization are separate decisions taken by the person, revocable at any time.
- **Revocation stops work in progress:** answers computed after a revocation are discarded, follow-up sessions are
  deleted and captions stop.
- **Standard models only:** Meta does not train on that content. A test fails if a Contributor model ID appears in
  the request code.
- **Minimal data:**
  - images for follow-ups are kept encrypted for up to 15 minutes, documents for up to 2 hours;
  - audio and transcripts are not stored;
  - the usage ledger keeps billed units only.
- **Cost protection:** platform and per-account quotas are checked atomically in Redis, with one heavy request per
  account at a time and optional daily spending caps (an estimate, not Meta's invoice).
- **Facial recognition is disabled.** The experimental local matcher is off by default (`AINGEL_FACE_RECOGNITION_ENABLED=0`)
  and is not part of the product.
- **Not a medical device:** AINGEL does not diagnose, and never states that a route or place is safe.

Details: [docs/PUBLIC_ACCESS.md](docs/PUBLIC_ACCESS.md) · [docs/META_MODEL_API_TERMS.md](docs/META_MODEL_API_TERMS.md) ·
[docs/PRIVACY_ARCHITECTURE.md](docs/PRIVACY_ARCHITECTURE.md) · [docs/VISION_PEOPLE_EXPRESSIONS.md](docs/VISION_PEOPLE_EXPRESSIONS.md) ·
[docs/VISION_CONTENT_TYPE.md](docs/VISION_CONTENT_TYPE.md).

## Architecture

```
 Web (React + Vite)   Android (Kotlin + Compose)   Windows (.NET 8 WPF)
          \                    |                         /
           +---------- HTTPS / WSS (Caddy) -------------+
                               |
              Django 5 + DRF + Channels (Daphne, ASGI)
              consent · quotas · usage ledger · sessions
                 |                 |                 |
           PostgreSQL 16     Redis (cache,      Meta Model API
                             channels, quotas)  (Spark, Voice, SAM)
```

- **Meta is called only by the server.** The API key never reaches a client.
- **Each Meta endpoint checks first:**
  - adulthood and territory;
  - the person's grant for that purpose;
  - quota and budget.
- **Live captions:** a WebSocket relay to Muse Voice Transcribe, with consent rechecked every 5 seconds.
- **Production stack:** Docker Compose behind the existing Caddy proxy. PostgreSQL and two Redis instances are
  reachable only over TLS on an internal network. Both images run as non-root users.

| Directory | Contents |
|---|---|
| `backend/` | Django project: `care` (accounts, profiles, consent, territory, signs) and `assistance` (vision, documents, captions, conversation, quotas, usage) |
| `web/` | React + TypeScript single-page app |
| `android/` | Native Android app (Kotlin, Jetpack Compose, CameraX) |
| `desktop/` | AINGEL Desktop for Windows (WPF, no NuGet packages) and its installer |
| `deploy/` | Dockerfiles, Compose file, Nginx and Caddy examples |
| `docs/` | Design, privacy, terms, validation and audit records |

## Run it

**Requirements:**
- Python 3.12;
- Node 20.19+ or 22.12+;
- JDK 17+ (Android Studio's bundled JBR works) and the Android SDK;
- .NET 8 SDK on Windows.

For production: Docker Engine with Compose v2, a TLS reverse proxy, PostgreSQL 16 and Redis 7.

**Backend and web (local, no Meta calls):**

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.lock.txt
cd backend && DJANGO_SECRET_KEY=dev ../.venv/bin/python manage.py migrate && DJANGO_SECRET_KEY=dev ../.venv/bin/python manage.py runserver 127.0.0.1:8010
```

```bash
cd web && npm ci && npm run dev
```

On Windows, `Start-Aingel.ps1` does both.

`AINGEL_AI_MODE=mock` (the default) never contacts Meta. The server's own synthetic fixtures can be sent to Meta
with `AINGEL_AI_MODE=meta`, `AINGEL_SYNTHETIC_TESTS_ONLY=1`, `AINGEL_META_SYNTHETIC_TEST_ACK=1` and a key in
`MODEL_API_KEY`.

**Android:**

```bash
cd android && ./gradlew assembleDebug
```

**Windows:**

```bash
cd desktop && dotnet build AingelDesktop.slnx -c Release
```

`desktop/Build-Installer.ps1` builds the installer, which needs the .NET 8 Desktop Runtime.

**Production:** see [deploy/README.md](deploy/README.md) and [docs/VPS_RECONCILIATION.md](docs/VPS_RECONCILIATION.md).
Production with consent uses:

```
AINGEL_ENV=production
AINGEL_AI_MODE=meta
AINGEL_REAL_DATA=1
AINGEL_SYNTHETIC_TESTS_ONLY=0
AINGEL_PRIVATE_OWN_MEDIA_TEST=0
AINGEL_META_ACCESS=public
AINGEL_FACE_RECOGNITION_ENABLED=0
MODEL_API_KEY=<from your secret manager>
DJANGO_SECRET_KEY=<from your secret manager>
AINGEL_ENCRYPTION_KEY=<Fernet key from your secret manager>
AINGEL_META_LIMIT_PER_MINUTE=60
AINGEL_META_LIMIT_PER_DAY=5000
AINGEL_META_USER_LIMIT_PER_MINUTE=12
AINGEL_META_USER_LIMIT_PER_DAY=300
```

The server refuses to start with inconsistent modes or missing secrets. `.env.example` lists the variables; never
commit real values.

## Tests

| Suite | Command |
|---|---|
| Backend (Django) | `cd backend && DJANGO_SECRET_KEY=x python manage.py test` |
| Quotas on real Redis (isolated, never production) | `AINGEL_TEST_REDIS_URL=redis://… AINGEL_TEST_REDIS_ISOLATED=1 python manage.py test assistance.test_meta_quota_redis` — see [docs/REDIS_REAL_VALIDATION.md](docs/REDIS_REAL_VALIDATION.md) |
| Web | `cd web && npm run typecheck && npm run build && npm run test:vision` (and the other `test:*` scripts) |
| Android | `cd android && ./gradlew testDebugUnitTest lintDebug` |
| Windows | `cd desktop && dotnet build AingelDesktop.slnx -c Release && dotnet AingelDesktop.Tests/bin/Release/net8.0-windows/AingelDesktop.Tests.dll` |
| Container images | `python -m unittest discover -s deploy/tests` |

- **Continuous integration:** [.github/workflows/ci.yml](.github/workflows/ci.yml) runs these on every push, without
  secrets and without calling Meta. It also builds both Docker images and starts the web container.
- **What the tests prove:** the tests that touch Meta intercept the HTTP client and check what AINGEL sends. They
  prove the rules, consent and quotas, **not** how accurate Meta's answers are.
- **Latest recorded results:** [docs/HACKATHON_AUDIT_2026.md](docs/HACKATHON_AUDIT_2026.md).

## Limitations and experimental features

- **No validation with disabled users yet:** AINGEL has not been validated in a study with people with disabilities;
  the accessibility work follows guidelines and project testing.
- **Signs:**
  - the signing avatar shows AINGEL's own designs, pending validation by LSEC signers; it is not a translation of
    Ecuadorian Sign Language;
  - sign recognition by camera is experimental.
- **Experimental and off in production:**
  - continuous video watching;
  - the local family face matcher.
- **Descriptions** come from a single photo or frame: they can be wrong, and they never establish safety, identity
  or how someone feels.
- **Accuracy is unmeasured:** how well Meta tells photographs from drawings, or reads expressions, has not been
  measured; the tests check the instructions AINGEL sends.
- **Interface languages:** Spanish and English only.

More: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Built during the hackathon

- **Timeline:** every commit in this repository is dated between 26 October and 2 November 2026, after the
  application period of the Meta Global AI Developer Hackathon closed on 25 October.
- **AINGEL 3.0 was built in this window:**
  - deep vision;
  - Desktop;
  - documents;
  - system-audio captions;
  - the sign registry;
  - the installer;
  - public access with consent;
  - quotas and billing;
  - restricted territories;
  - screen-content focus;
  - expression-first descriptions;
  - photo/drawing identification, with drawings described figure first and technique after (from a blind user's
    feedback).
- **Records:** [docs/AINGEL3_FINAL_REPORT.md](docs/AINGEL3_FINAL_REPORT.md) and the `docs/AINGEL3_PHASE*.md` files
  document each phase.
- **How it was built:** the owner directed the development with AI coding assistants (Anthropic's Claude Code and
  OpenAI's Codex), as the Official Rules allow for technical assistance.

## Credits and third-party software

- **Meta's models:** used as remote services under the Meta Model API Terms of Service; no model weights are
  included.
- **Thinking Orbs** (MIT): the AINGEL orb is adapted from it.
- **three.js** (MIT): renders the 3D hands.
- **React** (MIT).
- **Montserrat** (SIL OFL 1.1).
- **AndroidX, Jetpack Compose, CameraX, OkHttp** (Apache 2.0).
- **Django, Django REST framework, Channels, Daphne, Twisted, pypdf, pypdfium2, OpenCV, Pillow and others:** see
  each one's license.
- **MedlinePlus summaries** (U.S. National Library of Medicine).

Full notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [docs/THIRD_PARTY_INVENTORY.md](docs/THIRD_PARTY_INVENTORY.md),
[docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md) and [docs/licenses/](docs/licenses/).

## License

**Copyright © 2026 [owner — pending approval]. All rights reserved.**

- **Source visible for evaluation:** the source is visible so the project can be evaluated; it is **not open
  source**.
- **What is not allowed without written permission:** copying, modifying, redistributing or using AINGEL
  commercially.
- **What stays the same:** the license granted to the hackathon organizers under the Official Rules, and the
  licenses of third-party components.

See [LICENSE](LICENSE).
