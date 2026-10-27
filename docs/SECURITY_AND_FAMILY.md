# Security and family matching — local prototype

## Authentication

Django sessions with HTTP-only, SameSite cookies; CSRF applies before password authentication as well as to authenticated writes. Password validation and IP-based auth throttling protect registration/login. Password-only authentication establishes no full session when a TOTP device is enabled; a five-minute pending challenge must be completed. MFA attempts are bounded, successful TOTP counters cannot be replayed, and recovery codes are keyed hashes consumed transactionally once. QR generation is local. TOTP and pending secrets are Fernet-encrypted.

The setup requires current password plus a valid newly provisioned code. Disabling requires password and an unused TOTP/recovery code. Changing MFA epoch invalidates other pre-existing HTTP sessions; WebSocket opening also checks epoch. Loss of all factors has no automated recovery flow yet. These are local features verified in automated tests, not a claim of an external security audit or a real Google account connection. [PyOTP documentation](https://pyauth.github.io/pyotp/).

Per-process cache limits must move to a shared production cache. Local HTTP cookies are not Secure because the preview uses loopback HTTP. HTTPS, secure cookie flags, session policy, password reset and production hardening remain release gates. Preserve both `.local/server-secret.txt` and `.local/encryption.key` privately; a production instance needs explicit stable secrets.

## Care permissions

One primary profile per owning account; caregivers can support multiple explicitly linked profiles. At most four accepted caregivers plus live pending invitation reservations. Invitations target a registered account, use a random code stored as SHA-256 only, expire in seven days and require acceptance by that exact account. Profile row locking serializes slot changes on PostgreSQL. Local SQLite is a development database, not a concurrency benchmark.

Only the principal grants/revokes permissions. Configuration and memory-read grants are independent. Caregivers may not create or delete memories even when granted read access. Membership revocation immediately denies subsequent backend reads; it cannot erase information someone already viewed. The last caregiver can always be removed; readiness becomes draft. Audit events omit health/memory content.

## Family recognition

Scope amendment explicitly requested by the user: photo-based assistance for remembering or hearing who a consenting familiar person may be. This is not stranger identification or login authentication.

Default disabled. Only the principal can enable with password and consent. A linked adult family member must enroll their own clear single-face photo and affirm consent. The server stores a 128-dimensional SFace template encrypted at rest, tied to the membership, with 30-day expiration. Uploads are decoded transiently and discarded. Querying is principal-only with capture consent; no photo or embedding is sent to Meta.

Models: OpenCV Zoo YuNet `face_detection_yunet_2023mar.onnx` (MIT) and SFace `face_recognition_sface_2021dec.onnx` (Apache-2.0), with official model-directory license copies in `docs/licenses/` and pinned upstream commit/SHA-256 in `FACE_MODELS.json`. Only model weights were downloaded, not a biometric training corpus. These license statements do not establish that all upstream training-data consent/provenance or downstream regulatory requirements have been audited. That review remains open before commercialization.

Matching rejects cosine similarity below 0.55 or top-two margin below 0.10. These conservative prototype thresholds are engineering settings, **not measured safety or accuracy guarantees**. Results say possible match. No liveness/spoof detection. Enrollment and positive-recognition flows use stubbed vectors in permission tests; actual local model loading and no-face rejection were checked on a synthetic white image. Real-family precision, false-match rate, demographic bias, lighting/pose robustness and participatory usability remain unmeasured.

Revoking membership cascades deletion of its template. A family member can delete their own enrollment. Turning the feature off deletes all its profile templates. Expired templates cannot match and are physically removed by the retention cleanup command on local startup. Schedule and verify daily cleanup before production; no recurring automation was created.

## Media and provider boundaries

Private evidence is served only through scoped authenticated views with no-store caching; there is no public `/media/` route. Memory expires after seven days and requires explicit principal confirmation. Content is a human report, not objective proof of present location or completed medicine intake. Image analysis, SAM and voice require synthetic-input assertions while the free-credit privacy warning is unresolved; this assertion is not a sensitive-content classifier.

SAM uses the official `meta-sam-parser` under its SAM License (not MIT); retain its license on redistribution. Captions require an authenticated allowed-origin WebSocket, server-side Meta handshake, PCM pacing/size bounds, and explicit stop. Audio/transcripts are not persisted by this relay. Browser microphone capture itself still needs manual device QA.
