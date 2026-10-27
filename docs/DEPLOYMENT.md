# Deployment â€” pending

No public deployment, domain, TLS configuration, Docker image exists yet; an Android debug APK is built locally, installed on Samsung SM-F721B/Android 16 and has passed a native backend integration test (camera/audio/family accuracy still pending). Local React/Vite and Django/Daphne run on loopback with persistent session/encryption secrets and SQLite. Start-Aingel.ps1 bootstraps migrations/demo/retention and launches hidden services; do not expose these development servers.

Production gate: verified VPS destination and domain, Dockerized ASGI service, PostgreSQL, private evidence directory/object store, HTTPS reverse proxy with WSS and upload/time limits, stable secret manager, debug disabled, explicit hosts/origins, secure cookies, process limits, global quotas and provider budget policy. Use Redis when channel/rate coordination needs it. Do not interpret billing email alerts as hard spending caps.

Before first deploy: back up existing services, isolate AINGEL from the CRM, run migrations/checks, verify health and auth-denied behavior, confirm private media access, smoke-test synthetic Meta inference, test rollback and restore. Record exact commands against actual infrastructure when inspected. Target first staging deployment Nov 1, 2026; first submission Nov 3.


Current production blockers: configure PostgreSQL, shared cache for auth/WS quotas, HTTPS and Secure cookies, explicit production Origin/hosts, secret manager with AINGEL_ENV=production and AINGEL_ENCRYPTION_KEY, evidence/media permissions, daily purge job and secure backup/restore. Backup the database, private media and both local keys as one recoverable set; do not copy .local into an image or public repository. The local encryption fallback is deliberately unavailable outside local mode. Biometric consent/privacy and model/data provenance need separate commercialization review. No production deployment validation has occurred.
