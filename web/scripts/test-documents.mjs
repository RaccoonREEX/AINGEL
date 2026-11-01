import assert from "node:assert/strict";
import { createServer } from "vite";

// Load the real module with Vite without starting an HTTP server or contacting a backend.
const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const { openForm, askBody, clampPage, endsDocument, DOCUMENT_FIXTURES } = await vite.ssrLoadModule("/src/components/aingel/documents.ts");
  const entries = (form) => Object.fromEntries([...form.entries()].map(([key, value]) => [key, typeof value === "string" ? value : "<file>"]));

  // A server fixture carries only its id: no file, profile or declaration.
  assert.deepEqual(entries(openForm("es-EC", { fixture: "book_pdf" })), { locale: "es-EC", fixture: "book_pdf" });
  assert.deepEqual(Object.keys(DOCUMENT_FIXTURES), ["book_pdf", "scanned_pdf"]);
  // The person's own file: their profile and the explicit test declaration.
  assert.deepEqual(entries(openForm("es-EC", { file: new Blob(["%PDF"]), name: "libro.pdf", profile: "p1", testFields: { private_test: true } })),
    { locale: "es-EC", file: "<file>", profile: "p1", private_test: "true" });

  // Only a question action carries the typed text, bounded.
  assert.deepEqual(askBody("explain", 2, "page", "texto escrito"), { action: "explain", page: 2, scope: "page" });
  assert.equal(askBody("question", 1, "document", "a".repeat(900)).question.length, 600);
  assert.deepEqual(askBody("question", 1, "page", "  "), { action: "question", page: 1, scope: "page" });

  assert.equal(clampPage(0, 4), 1);
  assert.equal(clampPage(9, 4), 4);
  assert.equal(clampPage(Number("x"), 4), 1);
  assert.ok(endsDocument("consent_changed") && endsDocument("document_expired") && !endsDocument("meta_unavailable"));
  console.log("documents: ok");
} finally {
  await vite.close();
}
