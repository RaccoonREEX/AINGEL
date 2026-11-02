import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

// Meta's Restricted Territories (backend care.territory): the real components, without a backend.
const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const { TerritoryChoice, territoryFields } = await vite.ssrLoadModule("/src/screens/Auth.tsx");
  const { errorKey, APIError } = await vite.ssrLoadModule("/src/api.ts");
  const list = "Afganistán, Venezuela y Sáhara Occidental";
  const render = (value, es = true) => renderToStaticMarkup(React.createElement(TerritoryChoice, { value, onChange: () => {}, es, list }));
  // Two radio choices in a group, neither chosen by default; the list and the data note are read with them.
  const blank = render(null);
  assert.match(blank, /<fieldset/);
  assert.equal((blank.match(/type="radio"/g) || []).length, 2);
  assert.doesNotMatch(blank, /checked=""/);
  assert.match(blank, /Venezuela/);
  assert.match(blank, /no guardamos tu país ni tu ubicación/);
  assert.match(blank, /aria-describedby=/);
  // «Inside» explains that no account is created, as an alert.
  assert.doesNotMatch(render("outside_restricted"), /role="alert"/);
  assert.match(render("inside_restricted"), /role="alert"[^>]*>AINGEL usa la IA de Meta/);
  assert.match(render("inside_restricted", false), /will not be created/);
  const existing = renderToStaticMarkup(React.createElement(TerritoryChoice, { value: "inside_restricted", onChange: () => {}, es: true, list, account: true }));
  assert.match(existing, /Tu cuenta seguirá cerrada mientras estés allí/);
  assert.doesNotMatch(existing, /No se creará la cuenta/);
  // The fields the server expects, with the version it sent.
  assert.deepEqual(territoryFields("outside_restricted", "2026-10-12"), { territory: "outside_restricted", territory_version: "2026-10-12" });
  // Server refusals get their own messages, not the generic Meta failure.
  assert.equal(errorKey(new APIError(400, { error: "territory_declaration_required" })), "errorTerritoryDeclare");
  assert.equal(errorKey(new APIError(403, { error: "territory_restricted" })), "errorTerritory");
  assert.equal(errorKey(new APIError(403, { error: "meta_territory_restricted" })), "errorTerritory");
  console.log("Territory checks passed.");
} finally {
  await vite.close();
}
