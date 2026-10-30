# Production backend configuration

`AINGEL_ENV=local` retains the loopback development defaults. `AINGEL_ENV=production`
fails on missing or unsafe configuration. This is preparation, not proof of a safe deployment.

Required environment settings:

- `DJANGO_SECRET_KEY`: stable, randomly generated, at least 50 characters.
- `AINGEL_ENCRYPTION_KEY`: stable Fernet key, stored separately as a secret.
- `AINGEL_ALLOWED_HOSTS`: comma-separated explicit lowercase hostnames, no wildcards or ports.
- `AINGEL_CSRF_TRUSTED_ORIGINS` and `AINGEL_WEBSOCKET_ORIGINS`: comma-separated HTTPS origins on the allowed hostnames, including a port if needed.
- `AINGEL_TRUSTED_PROXY_NETWORKS`: comma-separated narrow IP networks from which the reverse proxy connects to ASGI.
- `AINGEL_DB_NAME`, `AINGEL_DB_USER`, `AINGEL_DB_PASSWORD`, `AINGEL_DB_HOST`, and `AINGEL_DB_SSLROOTCERT`; optionally `AINGEL_DB_PORT` (default 5432). The server certificate must validate against this CA and match the host (`verify-full`).
- `AINGEL_REDIS_URL`: a `rediss://` URL without query options to a TLS-protected Redis service; certificate and hostname verification are required. `AINGEL_REDIS_CA_CERT` is the absolute path to the Redis trust CA; it is used only for Redis and does not replace public roots for Meta. Protect credentials and CA trust; Django uses this shared cache for request throttling and caption leases. DRF throttles are approximate, not hard quotas.
- `AINGEL_PRIVATE_MEDIA_ROOT`: absolute path to persistent private storage outside every publicly served directory.

`DJANGO_DEBUG` must be disabled. Secure cookies and HTTPS are required. `AINGEL_HSTS_SECONDS` defaults to 0; set a positive value only after HTTPS is confirmed. `AINGEL_HSTS_INCLUDE_SUBDOMAINS=1` extends HSTS to subdomains and should only be used after those subdomains are ready.

Only a trusted TLS-terminating reverse proxy may reach ASGI. It must replace, never append or relay from the client, `X-Real-IP` with the single actual client IP and `X-Forwarded-Proto` with `https`. The ASGI guard rejects requests and WebSocket handshakes from other peers, missing/duplicate headers, and non-HTTPS headers. The proxy must validate its own incoming TLS and apply appropriate request, connection, and registration limits. Block direct external access to ASGI. Use a tightly scoped proxy network; a broad network permits any process inside it to forge the headers. Forward WebSocket upgrades on `/ws/` and route `/api/` and `/ws/` to ASGI, with the web app on the same origin. Never serve private media directly.

`AINGEL_AI_MODE=mock` is the default. The controlled synthetic Meta demo additionally requires `AINGEL_AI_MODE=meta`, `AINGEL_META_SYNTHETIC_TEST_ACK=1`, `AINGEL_SYNTHETIC_TESTS_ONLY=1`, `AINGEL_REAL_DATA=0`, and a server-only `MODEL_API_KEY`. A client's `synthetic=true` is a declaration: it cannot detect or prevent personal or health data from being sent. Restrict this demo to controlled participants and synthetic material. The separate private own-media test uses `AINGEL_AI_MODE=meta`, `AINGEL_PRIVATE_OWN_MEDIA_TEST=1`, `AINGEL_REAL_DATA=1`, `AINGEL_SYNTHETIC_TESTS_ONLY=0`, and a server-only `MODEL_API_KEY`. That mode requires the profile owner, separate Meta plus camera or microphone authorizations, and `private_test=true` on each scene/locate request or WebSocket start; it disables personalized conversation and gloss. Web supports this declaration; Android implementation and device validation must be confirmed against the release being deployed. It cannot detect health or other sensitive content within image or audio, so use only the authorized participant’s own carefully chosen material. Restrict access to this private environment; these flags are not a substitute for access controls or a security review.

In production, all Meta requests also require the requesting account's numeric
database ID in the comma-separated `AINGEL_META_ALLOWED_USER_IDS` server
environment variable. An unset or empty list blocks all Meta requests; mock
mode is unaffected. Create the trusted account first, verify its identity and
obtain its ID from the authenticated session response or Django administration,
then configure the ID privately and restart the backend. This allowlist restricts
who can use the provider; it does not classify submitted content, impose a
global spend limit, or replace the explicit per-feature consent checks.

Apply migrations as a separate deployment step; configure `purge_expired_memories` daily. Back up the database, private media, and the stable encryption and Django keys as one recoverable set, then verify restoration. No local SQLite data is transferred by these settings. Do not seed demo accounts in a public environment.
