# Accessibility — acceptance plan

No user interface or accessibility certification exists yet. The backend accepts locale and returns concise text plus explicit mode/error codes.

Web gates: semantic landmarks, keyboard focus/order, visible focus, large controls, contrast measurements, accessible file upload, status/error announcements, 200–400% zoom, narrow layout, reduced motion and logical RTL layout. Never rely only on color. Announce captions at controlled intervals rather than flooding screen readers.

Android gates: TalkBack labels and focus, scalable text, minimum platform touch targets, rotation, magnification, contrast, RTL and contextual camera/microphone permission requests. Check device TTS language availability and provide text fallback.

Evaluate with people who have relevant access needs where consent and time permit. Automated checks alone do not establish usability. Record actual devices, tested flows, failures and fixes here as implementations arrive.
