import assert from "node:assert/strict";
import fs from "node:fs";
import { createServer } from "vite";

// Source checks read the same text whatever line endings the checkout uses.
const source = (file) => fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");

const state = (epoch, statuses) => ({
  version: "v", subject_status: "self", is_subject: true, subject_adult: true, credits_notice: "", epoch,
  purposes: Object.entries(statuses).map(([id, status]) => ({ id, status, to: "local", title: id, detail: "" })),
});
const granted = { camera_local: "granted", microphone_local: "granted", meta_photos: "granted" };

const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const watch = await vite.ssrLoadModule("/src/consentWatch.ts");

  // Before starting: only the person's current grant opens a capture; unknown or unverifiable means no.
  let current = state(0, granted), fail = false;
  const changes = [];
  const watcher = watch.createConsentWatcher(async () => { if (fail) throw new Error("offline"); return current; }, (c) => changes.push(c));
  assert.equal(await watcher.allowed("camera"), true);
  assert.equal(await watcher.allowed("microphone"), true);
  for (const status of ["pending", "declined", "revoked"]) assert.equal(watch.mayStart(state(0, { camera_local: status }), "camera"), false);
  assert.equal(watch.mayStart(null, "camera"), false);

  // During a capture: revoking the camera stops the camera (not the microphone), and the epoch aborts pending work.
  current = state(1, { ...granted, camera_local: "revoked" });
  await watcher.tick();
  assert.deepEqual(changes.at(-1), { epoch: true, camera: true, microphone: false });
  assert.equal(await watcher.allowed("camera"), false); // a new grant is needed to start again

  // Revoking a Meta purpose leaves local captures alone but still aborts pending requests and late answers.
  current = state(1, granted);
  await watcher.tick();
  const before = changes.length;
  current = state(2, { ...granted, meta_photos: "revoked" });
  await watcher.tick();
  assert.deepEqual(changes.slice(before), [{ epoch: true, camera: false, microphone: false }]);

  // A grant does not interrupt anything; two checks that cannot be made in a row stop everything.
  const quiet = changes.length;
  current = state(2, { ...granted, meta_photos: "granted" });
  await watcher.tick();
  assert.equal(changes.length, quiet);
  fail = true;
  await watcher.tick();
  assert.equal(changes.length, quiet);
  await watcher.tick();
  assert.deepEqual(changes.at(-1), { epoch: true, camera: true, microphone: true, unverified: true });
  assert.equal(await watcher.allowed("microphone"), false);

  // Backend answers that end a capture.
  for (const code of ["consent_changed", "privacy_review_required", "camera_consent_revoked"]) assert.equal(watch.stopsCapture(code), true);
  assert.equal(watch.stopsCapture("meta_unavailable"), false);

  // Every capture entry point checks first and reacts to changes (wiring checked in the source).
  const home = source("src/screens/Home.tsx");
  assert.match(home, /if \(!\(await consent\.allowed\("camera"\)\)\)[^\n]*\n\s*setVision\(true\);\n\s*const opened = await camera\.start/);
  assert.match(home, /if \(!\(await consent\.allowed\("microphone"\)\)\)[^\n]*\n\s*const started = await speech\.start/);
  assert.match(home, /inflight\.current\.forEach\(\(control\) => control\.abort\(\)\)/);
  assert.doesNotMatch(home, /await api<(Scene|Located|ConversationReply)>/, "requests that depend on consent must be abortable");
  const signs = source("src/screens/SignTranslator.tsx");
  assert.match(signs, /consent\.allowed\("camera"\)/);
  assert.match(signs, /consent\.allowed\("microphone"\)/);
  const hear = source("src/Hear.tsx");
  assert.match(hear, /consent\.allowed\("microphone"\)/);
  assert.match(hear, /if \(stopsCapture\(String\(message\.code \?\? ""\)\)\) \{ revoke\(revokedText\); return; \}/);
  assert.match(source("src/components/ConsentPanel.tsx"), /announceConsentChange\(profile\.id\)/);
  const camera = source("src/components/aingel/useCamera.ts");
  assert.match(camera, /stream\.current\?\.getTracks\(\)\.forEach\(\(t\) => t\.stop\(\)\)/, "stopping the camera ends its tracks");
  console.log("Revocation checks passed.");
} finally {
  await vite.close();
}
