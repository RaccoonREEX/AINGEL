# Deployment — pending

No public deployment, domain, TLS configuration, Docker image or APK exists yet. Local execution is documented in README. Current settings are loopback-only scaffold settings and SQLite; do not expose runserver.

Production gate: verified VPS destination and domain, Dockerized ASGI service, PostgreSQL, private evidence directory/object store, HTTPS reverse proxy with WSS and upload/time limits, stable secret manager, debug disabled, explicit hosts/origins, secure cookies, process limits, global quotas and provider budget policy. Use Redis when channel/rate coordination needs it. Do not interpret billing email alerts as hard spending caps.

Before first deploy: back up existing services, isolate AINGEL from the CRM, run migrations/checks, verify health and auth-denied behavior, confirm private media access, smoke-test synthetic Meta inference, test rollback and restore. Record exact commands against actual infrastructure when inspected. Target first staging deployment Nov 1, 2026; first submission Nov 3.
