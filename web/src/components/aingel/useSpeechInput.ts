import { useCallback, useEffect, useRef, useState } from "react";
import { useMicrophoneLevel } from "./useMicrophoneLevel";
import {
  Recognizer, browserServiceAccepted, recognitionPlace, setBrowserServiceAccepted,
  type RecognitionLike as Recognition, type RecognitionPlace,
} from "./browserSpeech";

export type SpeechOutcome =
  | { kind: "heard"; text: string }
  | { kind: "nothing" }
  /** No recogniser, or it failed (network/service): the person should continue by typing. */
  | { kind: "unavailable" };

/**
 * Microphone + speech recognition. The microphone opens only on start() (after a tap), the orb level
 * comes from the same stream, and everything is released when listening ends. Recognition runs only on the
 * device when the browser confirms it can, or with the person's acceptance that the browser's vendor may
 * process the audio (browserSpeech.ts); otherwise start() returns "consent" and nothing opens.
 */
export function useSpeechInput(lang: string) {
  // start/stop/level from the microphone hook are stable, so these callbacks keep their identity.
  const { start: micStart, stop: micStop, level, error: micError } = useMicrophoneLevel();
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognition = useRef<Recognition | null>(null);
  const heard = useRef("");
  const failed = useRef(false);
  const done = useRef<((o: SpeechOutcome) => void) | null>(null);
  // Bumped by cancel() / unmount and by every start(), so a start() still waiting for the microphone gives up.
  const generation = useRef(0);
  const [place, setPlace] = useState<RecognitionPlace>(Recognizer ? "browser_service" : "unsupported");
  const [accepted, setAccepted] = useState(browserServiceAccepted);
  // Read by start(), so a start() right after accept() sees the decision before the next render.
  const acceptedNow = useRef(accepted);
  useEffect(() => {
    let current = true;
    void recognitionPlace(lang).then((value) => { if (current) setPlace(value); });
    return () => { current = false; };
  }, [lang]);
  const accept = useCallback((value: boolean) => { setBrowserServiceAccepted(value); acceptedNow.current = value; setAccepted(value); }, []);

  const finish = useCallback(() => {
    const callback = done.current;
    done.current = null;
    recognition.current?.stop();
    recognition.current = null;
    micStop();
    setListening(false);
    if (!callback) return;
    const text = heard.current.trim();
    callback(text ? { kind: "heard", text } : !Recognizer || failed.current ? { kind: "unavailable" } : { kind: "nothing" });
  }, [micStop]);

  const cancel = useCallback(() => {
    generation.current++;
    done.current = null;
    recognition.current?.abort();
    recognition.current = null;
    micStop();
    setListening(false);
  }, [micStop]);

  /** true when listening, false when the microphone failed, "consent" when the browser may send the audio to its
   * vendor and the person has not accepted that (nothing opens), null when cancel() / unmount / a newer start()
   * superseded this call: then nothing starts and onDone is never called. */
  const start = useCallback(async (onDone: (o: SpeechOutcome) => void): Promise<boolean | null | "consent"> => {
    if (Recognizer && place !== "device" && !acceptedNow.current) return "consent";
    cancel();
    const gen = ++generation.current;
    heard.current = ""; failed.current = false; setTranscript("");
    const mic = await micStart();
    // cancel() (or unmount) ran meanwhile; it already released the microphone.
    if (gen !== generation.current) return null;
    if (!mic) return mic;
    done.current = onDone;
    setListening(true);
    if (Recognizer) {
      const rec = new Recognizer();
      rec.lang = lang; rec.interimResults = true; rec.continuous = false;
      // Confirmed available on the device: require it, so the browser cannot fall back to its service.
      if (place === "device") rec.processLocally = true;
      rec.onresult = (e) => {
        let text = "";
        for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
        heard.current = text; setTranscript(text);
      };
      // A failed recogniser keeps the listening state (and the orb level) until the person taps stop.
      rec.onerror = (e) => { if (e.error !== "no-speech" && e.error !== "aborted") failed.current = true; };
      rec.onend = () => {
        if (recognition.current !== rec) return;
        if (failed.current && !heard.current.trim()) { recognition.current = null; return; }
        finish();
      };
      recognition.current = rec;
      try { rec.start(); } catch { recognition.current = null; failed.current = true; }
    }
    return true;
  }, [cancel, finish, lang, micStart, place]);

  useEffect(() => cancel, [cancel]);
  return { start, finish, cancel, listening, transcript, level, micError, supported: !!Recognizer, place, accepted, accept };
}
