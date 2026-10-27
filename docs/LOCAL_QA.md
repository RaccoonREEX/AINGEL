# Local validation record — 2026-10-26

## Automated

55 Django tests pass. Coverage includes CSRF before login, registration/login/logout, independent caregiver permissions, invitations/target/expiry/four-slot limit, revocation, factual no-evidence/latest-owner-memory retrieval, private evidence deletion, routine validation/manual attribution, messages, TOTP setup/challenge/replay/recovery/expiry/session invalidation, consented family enrollment boundaries and matching unknown/ambiguity rejection, SAM malformed/empty/mocked responses, caption auth/origin/synthetic gate/PCM and event forwarding. Stubs are used where appropriate; these tests do not measure AI accuracy.

Frontend TypeScript/Vite production build and pip dependency consistency checks pass. Migration consistency is checked before delivery. No production load test, external penetration test or full WCAG audit has been performed.

## Actual Meta calls

- Spark: synthetic blue square/red circle described from the React page through HTTP-session-authenticated Django, in Spanish; 2,156 ms observed in that browser call. Earlier adapter-only run is documented separately.
- SAM: synthetic red circle localized on the right, actual model confidence ~0.945, box coordinates and mask decoded. Adapter latency 1,437 ms; see `SAM_SMOKE_RESULT.json`. Confidence is a model output, not an established probability of safe assistance.
- Voice: original OS-synthesized English WAV, 4.455 seconds; local authenticated WebSocket relay produced 10 partial events and one final turn matching the test script. See `CAPTIONS_SMOKE_RESULT.json`. No microphone was activated automatically.

## Browser checks in Edge

- Principal sign-in and private profile/routines render.
- Empty memory search gives no-evidence response; explicit synthetic observation saves and displays author/time/expiry.
- Family account sign-in, delegated settings save, and memory read denied without permission.
- English/Spanish switch updates interface labels and preserves original family content.
- Family recognition is off by default; caregiver cannot enable it.
- Mobile QA frame has 390 CSS-pixel outer width, 373-pixel inner document width with scrollbar, and no horizontal document overflow. Browser viewport override did not apply and was reset; a real iframe at the desired width was used instead.

Not manually verified: Google Authenticator camera scanning on a phone, actual browser microphone/voice playback quality, family-photo positive matching, TalkBack/screen readers, native Android install, production HTTPS and backup restore. Do not describe those as passing.

## Second pass — 2026-10-27

89 backend tests, 13 Android JVM tests, 14 offline dataset tests and five device tests pass. A fresh synthetic Meta Voice run returned eight partials and one final transcript; see the updated `CAPTIONS_SMOKE_RESULT.json`. Communication configuration and local MedlinePlus search were checked in Edge and on the Samsung using test profiles. See `KNOWLEDGE_AND_SIGNS.md` for scope and limits.
