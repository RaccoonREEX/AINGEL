/**
 * The sign registry (backend care.sign_registry): which of AINGEL's signs people who sign LSEC validated, for the
 * exact animation this app plays (signFingerprints.json, written by `npm run export:android-hands`).
 *
 * By default only validated signs are shown as sign language. When a sentence needs any sign that is not
 * validated, nothing is animated: the full text stays on screen and the app says that sign interpretation is not
 * available or only partial (AINGEL 3.0 §16: no arbitrary hand sequences that look like a translation). AINGEL's
 * own designs can still be shown when the person chooses them, always labelled as illustrations.
 */
import fingerprints from "./signFingerprints.json";

export type RegistrySign = { kind: "word" | "letter" | "number"; status: string; fingerprint: string | null; regions: string[]; source: string; license: string };
export type Registry = { language: string; language_name: string; signs: Record<string, RegistrySign>; summary: { total: number; validated: number } };

const LOCAL = fingerprints as Record<string, string>;
export const ILLUSTRATIVE_KEY = "aingel.illustrativeSigns";

/** Signs validated for the animation this app plays: a validation of another version does not count. */
export function validatedSigns(registry: Registry | null, local: Record<string, string> = LOCAL): Set<string> {
  const ids = new Set<string>();
  for (const [id, sign] of Object.entries(registry?.signs ?? {})) {
    if (sign.status === "validated" && sign.fingerprint && sign.fingerprint === local[id]) ids.add(id);
  }
  return ids;
}

export type SignPlan =
  | { play: true; illustrative: boolean }
  | { play: false; reason: "unavailable" | "partial"; validated: number; total: number };

/** Whether to animate [seq]: all validated, or the person chose AINGEL's illustrative designs. Never part of a
 * sentence: leaving signs out would change what was said. */
export function planSigns(seq: string[], validated: Set<string>, illustrative: boolean): SignPlan {
  const covered = seq.filter((id) => validated.has(id)).length;
  if (seq.length > 0 && covered === seq.length) return { play: true, illustrative: false };
  if (illustrative) return { play: true, illustrative: true };
  return { play: false, reason: covered === 0 ? "unavailable" : "partial", validated: covered, total: seq.length };
}

export function readIllustrative(): boolean {
  try { return window.localStorage.getItem(ILLUSTRATIVE_KEY) === "1"; } catch { return false; }
}

export function saveIllustrative(value: boolean) {
  try { window.localStorage.setItem(ILLUSTRATIVE_KEY, value ? "1" : "0"); } catch { /* the choice lasts for this page only */ }
}

export const localFingerprint = (id: string): string | undefined => LOCAL[id];
