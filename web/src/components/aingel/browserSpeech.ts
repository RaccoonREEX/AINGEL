/**
 * The browser's own speech services: where they run and what AINGEL allows. Two different things:
 *
 * - Speech recognition (SpeechRecognition / webkitSpeechRecognition) turns the microphone into text. It is the
 *   browser's service, not AINGEL's: browsers may send the audio to their vendor (Chrome does unless it can process it
 *   on the device), and the Web Speech API does not always say which. AINGEL uses it only when the browser confirms
 *   on-device processing for the language (`available({ processLocally: true })`, then `processLocally = true`), or
 *   after the signed-in account accepts that the audio may go to the browser's provider (recorded by the backend for
 *   that account only, and withdrawable). Typing always works.
 *   AINGEL never sends this audio anywhere itself; the recognized text follows the person's Meta authorizations.
 * - Text-to-speech (speechSynthesis) reads text aloud. AINGEL uses only voices the browser marks as local
 *   (SpeechSynthesisVoice.localService); a network voice would send the text being read to its provider.
 */

export type RecognitionLike = {
  lang: string; interimResults: boolean; continuous: boolean; processLocally?: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null;
  start: () => void; stop: () => void; abort: () => void;
};
type RecognizerClass = (new () => RecognitionLike) & {
  available?: (options: { langs: string[]; processLocally: boolean }) => Promise<string>;
};

export const Recognizer: RecognizerClass | undefined =
  typeof window !== "undefined" ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : undefined;

/** "device": the browser confirms on-device recognition; "browser_service": it may use its vendor's service. */
export type RecognitionPlace = "device" | "browser_service" | "unsupported";

export async function recognitionPlace(lang: string): Promise<RecognitionPlace> {
  if (!Recognizer) return "unsupported";
  if (typeof Recognizer.available === "function") {
    try {
      if ((await Recognizer.available({ langs: [lang], processLocally: true })) === "available") return "device";
    } catch { /* unknown: treated as a possible transfer */ }
  }
  return "browser_service";
}

/**
 * Whether recognition may start: "device" when the browser processes on the device; "service" when it may use its
 * vendor and the signed-in account accepted that (recorded by the backend for that account, never in browser
 * storage, so another account on this browser never inherits it); otherwise "ask".
 */
export function recognitionDecision(place: RecognitionPlace, accountAccepted: boolean): "device" | "service" | "ask" | "none" {
  if (place === "unsupported") return "none";
  if (place === "device") return "device";
  return accountAccepted ? "service" : "ask";
}

/** A local voice for [lang], or null (none installed, or the voice list is not loaded yet). */
export function localVoice(lang: string): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices().filter((v) => v.localService);
  const exact = lang.toLowerCase();
  return voices.find((v) => v.lang.toLowerCase() === exact)
    ?? voices.find((v) => v.lang.toLowerCase().startsWith(exact.slice(0, 2))) ?? null;
}

/**
 * Speaks [utterance] with a local voice only. false when this browser has no local voice for its language (the text
 * stays on screen); a voice list still loading is waited for once.
 */
export function speakLocally(utterance: SpeechSynthesisUtterance): boolean {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  const synth = window.speechSynthesis;
  const go = () => {
    const voice = localVoice(utterance.lang);
    if (!voice) return false;
    utterance.voice = voice;
    synth.cancel();
    synth.speak(utterance);
    return true;
  };
  if (synth.getVoices().length) return go();
  const once = () => { synth.removeEventListener("voiceschanged", once); go(); };
  synth.addEventListener("voiceschanged", once);
  return true;
}
