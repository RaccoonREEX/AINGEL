import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

// Load the real component with Vite without starting an HTTP server or contacting a backend.
const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const { default: Consent, canTestPrivateMedia, imageTestFields, audioTestFields } = await vite.ssrLoadModule("/src/components/PrivateMediaConsent.tsx");
  const owner = { id: "one", locale: "es-EC", role: "owner", consents: { camera: true, microphone: true, meta_data: true } };
  assert.equal(canTestPrivateMedia(owner, "image"), true);
  assert.equal(canTestPrivateMedia(owner, "audio"), true);
  assert.equal(canTestPrivateMedia({ ...owner, role: "caregiver" }, "image"), false);
  assert.equal(canTestPrivateMedia({ ...owner, consents: { camera: true } }, "image"), false);
  assert.equal(canTestPrivateMedia({ ...owner, consents: { camera: true, meta_data: true } }, "audio"), false);
  assert.deepEqual(imageTestFields(owner, false, false), { synthetic: false });
  assert.deepEqual(imageTestFields(owner, true, false), { synthetic: false, private_test: true });
  assert.deepEqual(imageTestFields(owner, true, true), { synthetic: true });
  assert.deepEqual(imageTestFields({ ...owner, role: "caregiver" }, true, false), { synthetic: false });
  assert.deepEqual(audioTestFields(owner, false, false), {});
  assert.deepEqual(audioTestFields(owner, false, true), { synthetic: true });
  assert.deepEqual(audioTestFields(owner, true, false), { private_test: true });
  assert.deepEqual(audioTestFields({ ...owner, role: "caregiver" }, true, false), {});
  assert.deepEqual(audioTestFields({ ...owner, consents: { microphone: true } }, true, false), {});
  const render = (profile, checked = false) => renderToStaticMarkup(React.createElement(Consent, { profile, kind: "image", checked, onChange: () => {} }));
  assert.match(render(owner), /type="checkbox"/);
  assert.doesNotMatch(render(owner), /checked=""/);
  assert.match(render(owner, true), /checked=""/);
  assert.match(render({ ...owner, role: "caregiver" }, true), /<fieldset[^>]*disabled=""/);
  assert.doesNotMatch(render({ ...owner, role: "caregiver" }, true), /checked=""/);
  assert.match(render(owner), /no detecta automáticamente/);
  console.log("Private-media consent checks passed.");
} finally {
  await vite.close();
}
