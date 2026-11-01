import assert from "node:assert/strict";
import { createServer } from "vite";

// The download button may only point to a real installer named by the release manifest, with its SHA-256.
const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const { validRelease } = await vite.ssrLoadModule("/src/components/DesktopDownload.tsx");
  const release = { product: "AINGEL Desktop", version: "0.1.0", date: "2026-10-31", file: "AINGEL-Desktop-Setup-0.1.0.exe", size_bytes: 333404, sha256: "9".repeat(64), signed: false };
  assert.deepEqual(validRelease(release), release);
  assert.equal(validRelease(null), null);
  assert.equal(validRelease({ ...release, sha256: "pending" }), null);
  assert.equal(validRelease({ ...release, file: "https://example.com/setup.exe" }), null);
  assert.equal(validRelease({ ...release, file: "../../setup.exe" }), null);
  assert.equal(validRelease({ ...release, version: undefined }), null);
  console.log("desktop download: ok");
} finally {
  await vite.close();
}
