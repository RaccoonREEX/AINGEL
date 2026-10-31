import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const { default: Consent, conversationTestFields } = await vite.ssrLoadModule("/src/components/SyntheticConversationConsent.tsx");
  assert.deepEqual(conversationTestFields(false), {});
  assert.deepEqual(conversationTestFields(true), { synthetic: true });
  const render = (es, checked, disabled = false) => renderToStaticMarkup(React.createElement(Consent, { es, checked, disabled, onChange: () => {} }));
  const spanish = render(true, false);
  assert.match(spanish, /type="checkbox"/);
  assert.doesNotMatch(spanish, /checked=""/);
  assert.match(spanish, /No incluyas nombres, datos personales ni de salud/);
  assert.match(spanish, /no los detecta automáticamente/);
  assert.match(render(true, true), /checked=""/);
  assert.match(render(true, false, true), /disabled=""/);
  assert.match(render(false, false), /personal or health information/);
  console.log("Synthetic conversation opt-in checks passed.");
} finally {
  await vite.close();
}
