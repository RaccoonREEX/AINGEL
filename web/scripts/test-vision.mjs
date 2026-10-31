import assert from "node:assert/strict";
import { createServer } from "vite";

// Load the real module with Vite without starting an HTTP server or contacting a backend.
const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const { visionForm, followUpForm, speechParts, endsSession, FIXTURES } = await vite.ssrLoadModule("/src/components/aingel/vision.ts");
  const entries = (form) => Object.fromEntries([...form.entries()].map(([key, value]) => [key, typeof value === "string" ? value : "<file>"]));

  // A server fixture carries only its id and the level: never typed text, a profile or an image.
  assert.deepEqual(entries(visionForm("es-EC", { fixture: "drawing_dog" }, "deep")),
    { locale: "es-EC", source_kind: "gallery", detail_level: "deep", fixture: "drawing_dog" });
  assert.deepEqual(Object.keys(FIXTURES), ["shapes", "drawing_dog", "drawing_ambiguous", "face_drawn", "document_page", "chart_bars", "screen_desktop"]);

  // The person's own image: their profile, the explicit test declaration and the question.
  const own = visionForm("es-EC", { image: new Blob(["x"]), profile: "p1", testFields: { private_test: true }, question: "  ¿Cómo es su cara?  " }, "", "camera");
  assert.deepEqual(entries(own), { locale: "es-EC", source_kind: "camera", image: "<file>", profile: "p1", private_test: "true", question: "¿Cómo es su cara?" });
  assert.equal(entries(visionForm("es-EC", { image: new Blob(["x"]), profile: "p1", testFields: {}, question: "a".repeat(900) })).question.length, 600);

  // A follow-up: the session, never the profile or a test declaration (the server rechecks the consent).
  assert.deepEqual(entries(followUpForm("es-EC", "token", { question: "¿Y sus ojos?", region: "top", level: "" })),
    { locale: "es-EC", session: "token", question: "¿Y sus ojos?", focus_region: "top" });
  assert.ok(endsSession("consent_changed") && endsSession("visual_session_expired") && !endsSession("meta_unavailable"));

  // Long answers are spoken in parts made of whole paragraphs and sentences.
  const paragraph = "Una frase de prueba con varias palabras. ".repeat(20).trim();
  const parts = speechParts([paragraph, paragraph, paragraph].join("\n\n"), 1200);
  assert.equal(parts.length, 3);
  assert.ok(parts.every((part) => part.length <= 1200));
  const sentences = speechParts("Una frase corta. ".repeat(200), 300);
  assert.ok(sentences.every((part) => part.length <= 300 && part.endsWith(".")));
  assert.deepEqual(speechParts("Hola."), ["Hola."]);
  console.log("vision: ok");
} finally {
  await vite.close();
}
