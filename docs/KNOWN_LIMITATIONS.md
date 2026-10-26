# Known limitations — 2026-10-26

- Only backend scaffold and research exist. No Android build, React UI, Care, memory engine, SAM parser or live captions yet.
- Nine tests verify local auth/media/provider boundaries using stubs; no live Meta call or AI quality result.
- No server key configured. No claim that a browser login grants backend API authentication.
- Account free credits carry a product-improvement warning; personal-media enablement is blocked pending review.
- Synthetic flag is a caller assertion, not content verification.
- Two accepted request locales are not complete UI/AI/TTS language support.
- Local SQLite, session plumbing and in-process throttling are development choices; public login/bootstrap, stable secrets, production isolation and global quotas remain pending.
- No memory/no-hallucination acceptance test can pass until factual memory retrieval exists. It is explicitly required for the next slices.
- Dataset review is triage, with unresolved licenses/consent details; no dataset downloaded.
- Entry track remains unverified; submission form has no selected track. No agreement, publication or submission performed.
