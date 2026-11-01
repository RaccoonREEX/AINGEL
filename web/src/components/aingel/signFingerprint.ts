/*
 * A fingerprint of what each sign looks like: its keyframes plus the hand shapes (poses) they use, as the 3D hands
 * play them on web and Android. A validation in the sign registry (backend care/sign_registry.json) names the
 * fingerprint it reviewed, so changing an animation afterwards makes it «pending» again instead of keeping a
 * validation that no longer applies.
 */
import { S } from "./signData";
import { ensureSign } from "./hands3d/convert";
// @ts-expect-error untyped engine module from the AINGEL hands package
import { library } from "./hands3d/library.js";

/** Interface gestures of AINGEL itself (not signs of any language): never in the registry. */
export const INTERFACE_GESTURES = new Set(["listen_ear"]);

function posesIn(value: unknown, found: Set<string>) {
  if (Array.isArray(value)) value.forEach((item) => posesIn(item, found));
  else if (value && typeof value === "object") {
    for (const [key, inner] of Object.entries(value)) {
      if (key === "pose" && typeof inner === "string") found.add(inner);
      else posesIn(inner, found);
    }
  }
}

/** The canonical text a sign's fingerprint is computed from. */
export function canonical(id: string): string {
  ensureSign(id);
  const sign = library.signs.get(id) as { keyframes: unknown } | undefined;
  if (!sign) throw new Error(`unknown sign ${id}`);
  const names = new Set<string>();
  posesIn(sign.keyframes, names);
  const poses = Object.fromEntries([...names].sort().map((name) => [name, (library.poses.get(name) as { fingers: unknown } | undefined)?.fingers ?? null]));
  return JSON.stringify({ keyframes: sign.keyframes, poses });
}

/** Every catalogue sign (words, letters, numbers), in a stable order. */
export function signIds(): string[] {
  return Object.keys(S).filter((id) => !INTERFACE_GESTURES.has(id)).sort();
}

/** {id: sha256 hex} with the given digest (node:crypto in scripts). */
export function fingerprints(sha256: (text: string) => string): Record<string, string> {
  return Object.fromEntries(signIds().map((id) => [id, sha256(canonical(id))]));
}
