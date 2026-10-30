import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { analyserLevel, configureAnalyser } from "./useAudioLevel";

/**
 * Opens the microphone only when `start()` is called (after an explicit user action) and exposes a
 * frame-polled level. Audio stays in memory; tracks are stopped on `stop()` and on unmount.
 */
export function useMicrophoneLevel() {
  const stream = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  // Bumped by stop() / unmount and by every start(): a stream that arrives for an older generation is released.
  const generation = useRef(0);
  const [active, setActive] = useState(false);
  const [error, setError] = useState(false);
  const level = useMemo(() => analyserLevel(() => analyser.current), []);

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    analyser.current?.disconnect();
    analyser.current = null;
    void context.current?.close().catch(() => {});
    context.current = null;
    setActive(false);
  }, []);
  const stop = useCallback(() => { generation.current++; release(); }, [release]);

  /** true when listening, false on failure, null when stop() / unmount / a newer start() superseded this call. */
  const start = useCallback(async (): Promise<boolean | null> => {
    if (stream.current) return true;
    const gen = ++generation.current;
    setError(false);
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      // stop(), unmount or a newer start() happened while the permission prompt was open.
      if (gen !== generation.current) { media.getTracks().forEach((track) => track.stop()); return null; }
      const ctx = new AudioContext();
      const node = configureAnalyser(ctx.createAnalyser());
      ctx.createMediaStreamSource(media).connect(node);
      stream.current = media; context.current = ctx; analyser.current = node;
      setActive(true);
      return true;
    } catch {
      if (gen !== generation.current) return null;
      setError(true);
      release();
      return false;
    }
  }, [release]);

  useEffect(() => stop, [stop]);
  return { start, stop, active, error, level };
}
