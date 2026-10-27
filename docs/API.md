# API — scaffold

`GET /api/health/` returns process status; no auth required, no provider/account details.

`POST /api/v1/scene/` accepts multipart `image`, `locale` (`en-US` or `es-EC`) and optional boolean `synthetic` (default false). Authenticated Django session and CSRF required. Current per-user throttle is 10/minute in the local cache; distributed/global quota enforcement remains a production task. No public login UI exists yet.

Max one 5 MiB JPEG/PNG/WebP; decoded image max 12 million pixels. Re-encode JPEG max 1600px dimension without original metadata. Media is not saved. Success: `text`, `mode`, `model`, `latency_ms`; mock uses null model/latency and explicitly states no analysis. Results set `Cache-Control: no-store`.

Errors use stable codes: `image_too_large`, `image_format_unsupported`, `image_invalid` (400); credential, privacy, provider/empty/incomplete response or invalid AI mode (503). Standard DRF serializer/auth/CSRF/throttle responses use its normal format. Clients must translate errors using resource keys, not show raw provider messages.

Contract tests use an HTTP stub. One separate actual Spark 1.3 call succeeded through this endpoint using a synthetic image (3,453 ms adapter latency); broad output/schema coverage and quality evaluation remain pending. Memory, Care, login/bootstrap and audio WebSocket routes do not exist yet.
