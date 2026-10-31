import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

// A fake browser: one network voice and one local voice, and a recognizer whose on-device answer the test controls.
const spoken = [];
let voices = [];
let onDevice = "unavailable";
const store = new Map();
globalThis.window = {
  SpeechRecognition: Object.assign(function Recognition() {}, { available: async () => onDevice }),
  speechSynthesis: {
    getVoices: () => voices, cancel() {}, speak: (u) => spoken.push(u),
    addEventListener() {}, removeEventListener() {},
  },
  localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) },
};
globalThis.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; this.lang = ""; this.voice = null; } };

const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const speech = await vite.ssrLoadModule("/src/components/aingel/browserSpeech.ts");

  // Recognition: on the device only when the browser confirms it; otherwise a possible transfer to its vendor.
  assert.equal(await speech.recognitionPlace("es-EC"), "browser_service");
  onDevice = "available";
  assert.equal(await speech.recognitionPlace("es-EC"), "device");
  onDevice = "downloadable";
  assert.equal(await speech.recognitionPlace("es-EC"), "browser_service");

  // Two accounts in turn on this browser: the first one's acceptance (even a leftover flag of the old design in
  // localStorage) never lets the second one's voice go to the vendor. Only the signed-in account's own decision,
  // which the backend records per account (care/test_speech_service.py), counts.
  store.set("aingel.browser-speech-service.v1", "accepted");
  const first = { accepted: true }, second = { accepted: false };
  assert.equal(speech.recognitionDecision("browser_service", first.accepted), "service");
  assert.equal(speech.recognitionDecision("browser_service", second.accepted), "ask");
  assert.equal(speech.recognitionDecision("device", second.accepted), "device");
  assert.equal(speech.recognitionDecision("unsupported", true), "none");
  const fs = await import("node:fs");
  for (const file of ["src/components/aingel/browserSpeech.ts", "src/components/aingel/useSpeechInput.ts"]) {
    assert.doesNotMatch(fs.readFileSync(file, "utf8"), /localStorage|sessionStorage/, `${file} must not read browser storage`);
  }
  const hook = fs.readFileSync("src/components/aingel/useSpeechInput.ts", "utf8");
  assert.match(hook, /useEffect\(\(\) => cancel, \[consent\.identity, cancel\]\)/, "a new account or profile cancels recognition");
  assert.match(hook, /if \(!consent\.accepted && placeNow\.current !== "device"\) cancel\(\)/, "a withdrawal stops recognition");

  // Text-to-speech never uses a network voice.
  voices = [{ lang: "es-EC", localService: false, name: "network" }];
  const remoteOnly = new SpeechSynthesisUtterance("ZZQ private text"); remoteOnly.lang = "es-EC";
  assert.equal(speech.speakLocally(remoteOnly), false);
  assert.equal(spoken.length, 0);
  voices = [{ lang: "es-EC", localService: false, name: "network" }, { lang: "es-ES", localService: true, name: "local" }];
  const local = new SpeechSynthesisUtterance("Hola"); local.lang = "es-EC";
  assert.equal(speech.speakLocally(local), true);
  assert.equal(spoken.at(-1).voice.name, "local");

  const { default: Consent, micPrivacyLine } = await vite.ssrLoadModule("/src/components/BrowserSpeechConsent.tsx");
  assert.match(micPrivacyLine(true, "device"), /en este dispositivo/);
  assert.match(micPrivacyLine(true, "browser_service"), /su propio servicio/);
  assert.doesNotMatch(micPrivacyLine(true, "browser_service"), /dispositivo/);
  const html = renderToStaticMarkup(React.createElement(Consent, { es: true, onAccept() {}, onDecline() {} }));
  assert.match(html, /servicio de su fabricante/);
  assert.match(html, /Prefiero escribir/);
  console.log("Browser speech checks passed.");
} finally {
  await vite.close();
}
