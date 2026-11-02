import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer } from "vite";

// Load the real modules with Vite without starting an HTTP server or contacting a backend.
const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const { validatedSigns, planSigns } = await vite.ssrLoadModule("/src/components/aingel/signRegistry.ts");
  const { fingerprints } = await vite.ssrLoadModule("/src/components/aingel/signFingerprint.ts");
  const shipped = JSON.parse(readFileSync(new URL("../src/components/aingel/signFingerprints.json", import.meta.url), "utf8"));
  const android = JSON.parse(readFileSync(new URL("../../android/app/src/main/assets/hands3d/signFingerprints.json", import.meta.url), "utf8"));
  const registry = JSON.parse(readFileSync(new URL("../../backend/care/data/sign_registry.json", import.meta.url), "utf8"));

  // The fingerprints shipped with the apps are those of the animations they play (rerun the export after a change).
  assert.deepEqual(fingerprints((text) => createHash("sha256").update(text, "utf8").digest("hex")), shipped);
  assert.deepEqual(android, shipped);
  assert.deepEqual(Object.keys(registry.signs).sort(), Object.keys(shipped).sort());
  assert.equal(registry.language, "lsec");

  // A validation counts only for the animation it reviewed.
  const sign = (status, fingerprint) => ({ kind: "word", status, fingerprint, regions: [], source: "", license: "" });
  const reg = { signs: { hola: sign("validated", shipped.hola), agua: sign("validated", "0".repeat(64)), casa: sign("in_review", null) } };
  assert.deepEqual([...validatedSigns(reg, shipped)], ["hola"]);
  assert.equal(validatedSigns(null, shipped).size, 0);

  // Only whole sentences of validated signs move the hands; otherwise the full text stays and the gap is said.
  const ok = new Set(["hola", "gracias"]);
  assert.deepEqual(planSigns(["hola", "gracias"], ok, false), { play: true, illustrative: false });
  assert.deepEqual(planSigns(["hola", "agua"], ok, false), { play: false, reason: "partial", validated: 1, total: 2 });
  assert.deepEqual(planSigns(["agua"], new Set(), false), { play: false, reason: "unavailable", validated: 0, total: 1 });
  assert.deepEqual(planSigns(["agua"], new Set(), true), { play: true, illustrative: true });
  assert.equal(planSigns([], ok, false).play, false);
  console.log(`sign registry: ok (${Object.keys(shipped).length} signs, ${Object.values(registry.signs).filter((s) => s.reviews.length).length} reviewed)`);
} finally {
  await vite.close();
}
