import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const source = await import("node:fs").then((fs) => fs.readFileSync("src/components/SyntheticConversationConsent.tsx", "utf8"));
  // The demo sends only the server's example questions: no `synthetic` declaration exists any more.
  assert.doesNotMatch(source, /synthetic:\s*true/);
  const home = await import("node:fs").then((fs) => fs.readFileSync("src/screens/Home.tsx", "utf8"));
  assert.match(home, /\{ fixture: fixture\.id, locale \}/);
  assert.doesNotMatch(home, /conversationTestFields/);
  const { default: Consent } = await vite.ssrLoadModule("/src/components/SyntheticConversationConsent.tsx");
  const render = (es, checked, disabled = false) => renderToStaticMarkup(React.createElement(Consent, { es, checked, disabled, onChange: () => {}, onPick: () => {} }));
  const spanish = render(true, false);
  assert.match(spanish, /type="checkbox"/);
  assert.doesNotMatch(spanish, /checked=""/);
  assert.match(spanish, /perfil ficticio, sin tus datos/);
  assert.match(spanish, /no se envía a Meta nada que escribas o digas/);
  assert.match(render(true, true), /checked=""/);
  assert.match(render(true, true), /Cargando ejemplos/);
  assert.match(render(true, false, true), /disabled=""/);
  assert.match(render(false, false), /nothing you type or say is sent to Meta/);
  console.log("Synthetic conversation fixture checks passed.");
} finally {
  await vite.close();
}
