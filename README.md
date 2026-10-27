# AINGEL

**Adaptive Intelligence for Navigation, Guidance & Everyday Living**

AINGEL translates the world into what you can perceive. One adaptive multimodal accessibility companion, with evidence-backed memory as its intended core. Built for the Meta Global AI Developer Hackathon 2026.

**Current state: initial research and backend scene slice, not a complete MVP.** Android, React UI, Care, memory and realtime captions are not implemented. One actual Meta scene call has succeeded using a synthetic image. No deployment or APK exists.

Start with the [takeover report](docs/TAKEOVER_REPORT.md), [architecture](docs/ARCHITECTURE.md), [verified rules](docs/HACKATHON_RULES.md), [models](docs/META_MODELS.md), [scope](docs/SCOPE.md) and [dated roadmap](docs/ROADMAP.md).

## Implemented

- Django/DRF authenticated multipart scene endpoint and public minimal health endpoint.
- Image byte/format/pixel checks, re-encoding without source metadata, no persistence.
- Explicit mock result that never claims to have analyzed an image.
- Server-only Meta Responses adapter with a fixed destination, timeout, sanitized failures, model provenance and measured request latency. A live synthetic-image request succeeded with Spark 1.3 in 3,453 ms; see [validation](docs/META_LIVE_VALIDATION.md).
- English/Spanish request locale validation; this is not a translated user interface.

## Local setup (PowerShell)

Requires Python 3.12. From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
$env:AINGEL_AI_MODE = 'mock'
# Supply a locally generated stable random secret before using persistent sessions.
$env:DJANGO_SECRET_KEY = '<local-random-secret>'
Set-Location backend
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py test
..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010 --noreload
```

`GET /api/health/` checks the process. The scene endpoint requires an authenticated Django session with CSRF. An interactive login/bootstrap UI is not implemented yet. Tests use an isolated in-memory database and authentication fixtures. Do not expose this development server publicly.

## Configuration

`.env.example` documents variables; this scaffold reads the process environment and does **not** auto-load `.env` files. Keep keys out of shell history, frontend variables, screenshots and Git. Configure secrets through a local environment/secret manager, never by pasting them into chat.

| Variable | Purpose |
|---|---|
| `AINGEL_AI_MODE` | `mock` default or `meta`; unknown values fail closed |
| `MODEL_API_KEY` | Meta credential, server environment only |
| `DJANGO_SECRET_KEY` | Stable random server secret; absent value is ephemeral for scaffold checks |
| `DJANGO_DEBUG` | Off by default |
| `AINGEL_SYNTHETIC_TESTS_ONLY` | Must remain `1`; personal-content enablement is not implemented |

Real mode requires a configured key and `synthetic=true` per request. This flag records a caller assertion; it cannot technically verify whether media is synthetic. Use only known fixtures until the account's free-credit/privacy warning is resolved. There is no automatic fallback to mock on a Meta failure.

## Validation and next delivery

Ten backend tests passed on 2026-10-26: auth rejection, explicit mock provenance, invalid/oversize media, unsupported locale, missing credential, privacy gate, Meta request/response contract, incomplete-response rejection and upstream-error sanitization. One separate live Meta smoke check succeeded. These do not establish AI accuracy or end-to-end product operation.

Next gate: React test surface with HTTP-session login/CSRF, then Android camera/TTS. The opt-in [live smoke runner](backend/scripts/smoke_meta.py) accepts a local credential-file path and never prints/saves its secret. [API](docs/API.md), [deployment](docs/DEPLOYMENT.md), [accessibility](docs/ACCESSIBILITY.md), [localization](docs/LOCALIZATION.md), [privacy](docs/PRIVACY.md), [datasets](docs/DATASET_RESEARCH.md), [demo](docs/DEMO_SCRIPT.md), [limits](docs/KNOWN_LIMITATIONS.md).

Screenshots, demo link, Android minimum version/signing/build instructions and production URL will be added only when those artifacts exist. [Halo](docs/HALO_VISION.md) is future hardware, not a working device. Repository license selection and third-party notices are pending before publication.
