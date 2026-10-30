import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { analyserLevel, configureAnalyser } from "./useAudioLevel";
import type { LevelSource } from "./orb.types";

/**
 * Level of audio AINGEL plays through an <audio> element (e.g. a TTS provider's file or stream):
 * element -> MediaElementSource -> Analyser -> destination. Ready for ElevenLabs, WebRTC or HTML5 audio.
 */
export function useOutputAudioLevel() {
  const context = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const attached = useRef(new WeakSet<HTMLMediaElement>());
  const level = useMemo(() => analyserLevel(() => analyser.current), []);
  const attach = useCallback((element: HTMLMediaElement | null) => {
    if (!element || attached.current.has(element)) return;
    const ctx = context.current ?? (context.current = new AudioContext());
    let node = analyser.current;
    if (!node) {
      node = analyser.current = configureAnalyser(ctx.createAnalyser());
      node.connect(ctx.destination);
    }
    ctx.createMediaElementSource(element).connect(node);
    attached.current.add(element);
  }, []);
  useEffect(() => () => { void context.current?.close().catch(() => {}); }, []);
  return { attach, level };
}

/**
 * Browser speech synthesis exposes no audio samples, so the orb follows the real progress of the
 * voice instead: each spoken word boundary drives the level, which then releases smoothly.
 */
export function useSpeechSynthesisLevel(lang: string, rate = 1) {
  const [speaking, setSpeaking] = useState(false);
  const pulse = useRef({ at: 0, strength: 0 });
  const supported = typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  const level: LevelSource = useMemo(() => () => {
    const { at, strength } = pulse.current;
    if (!at) return 0;
    const age = (performance.now() - at) / 1000;
    return strength * Math.max(0, 1 - age / 0.32);
  }, []);
  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
    pulse.current = { at: 0, strength: 0 };
    setSpeaking(false);
  }, [supported]);
  const speak = useCallback((text: string, onEnd?: () => void) => {
    if (!supported) return false;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = rate;
    utterance.onstart = () => { setSpeaking(true); pulse.current = { at: performance.now(), strength: 0.55 }; };
    utterance.onboundary = (e) => {
      const word = text.slice(e.charIndex, e.charIndex + (e.charLength || 6));
      pulse.current = { at: performance.now(), strength: Math.min(0.95, 0.45 + word.length * 0.06) };
    };
    const done = () => { pulse.current = { at: 0, strength: 0 }; setSpeaking(false); onEnd?.(); };
    utterance.onend = done;
    utterance.onerror = done;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    return true;
  }, [lang, rate, supported]);
  useEffect(() => () => { if (supported) window.speechSynthesis.cancel(); }, [supported]);
  return { speak, stop, speaking, supported, level };
}
