# First live scene validation — 2026-10-26

User supplied the location of a newly created Meta API key in a local Desktop text file. The smoke runner reads it into process memory; no credential or local credential filename is written to the result report, repository or console. No account permissions or billing settings were changed.

## Method

`backend/scripts/smoke_meta.py` creates an original 640×480 white canvas with a blue square at left and a red circle at right. It sends a multipart request through Django APIClient and the real authenticated scene view (authentication is supplied by the test harness without a persistent account). Image normalization and the production HTTP adapter run, and Meta inference is real. This is not a browser/network-server/Android end-to-end test.

## Observed calls

1. Original request, 600 output-token ceiling and no explicit reasoning effort: scene service returned HTTP 503 `meta_incomplete`. The provider did not mark generation completed. The exact provider stop reason was not retained, so token exhaustion is a hypothesis, not a verified diagnosis.
2. Explicit `reasoning.effort=minimal` and 1,000 output-token ceiling: HTTP 200, mode `meta`, model `muse-spark-1.3`, measured adapter latency **3,453 ms**. Returned Spanish text correctly named the two colored shapes. See [sanitized result](META_SMOKE_RESULT.json).

One successful fixture is not an accuracy benchmark or evidence of real-world mobility safety. No personal image/audio was sent. The synthetic test image remains in memory. Free-credit content-use restrictions remain unresolved for real user data.

## Reproduction

From `backend/`, using the isolated environment:

```powershell
..\.venv\Scripts\python.exe scripts\smoke_meta.py --key-file '<local credential file>'
```

Optional `--report` saves only fixture description, transport, HTTP status and sanitized endpoint result. Each run makes a real billed API call; this is intentionally separate from the normal test suite. Credential loading accepts exactly one `LLM_` token. Never paste the secret into commands or chat.

## Next acceptance gates

Browser UI and HTTP-session login/CSRF, then Android camera/TTS. The current success validates scene request compatibility and actual Meta connectivity; it does not validate the remaining MVP flows.
