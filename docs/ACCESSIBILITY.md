# Accessibility â€” acceptance plan

A local React interface now exists with centralized English/Spanish strings, labeled controls, keyboard-visible focus, a skip link, large controls, optional larger text/contrast and responsive logical CSS. No accessibility certification is claimed.

Web gates: semantic landmarks, keyboard focus/order, visible focus, large controls, contrast measurements, accessible file upload, status/error announcements, 200â€“400% zoom, narrow layout, reduced motion and logical RTL layout. Never rely only on color. Announce captions at controlled intervals rather than flooding screen readers.

Android gates: TalkBack labels and focus, scalable text, minimum platform touch targets, rotation, magnification, contrast, RTL and contextual camera/microphone permission requests. Check device TTS language availability and provide text fallback.

Evaluate with people who have relevant access needs where consent and time permit. Automated checks alone do not establish usability. Record actual devices, tested flows, failures and fixes here as implementations arrive.


Observed checks: English/Spanish switching, visible semantic form labels, family memory-denial message, concise failure/no-evidence states and no horizontal overflow in a 390px QA frame. Actual TalkBack, screen-reader flow, measured contrast and RTL/zoom tests are still pending. Native Android accessibility remains untested. Voice output depends on installed browser voices and is user-initiated.
