import type { LevelSource } from "./orb.types";

/** Values from the integration brief: time-domain RMS, gate, curve, fast attack / slow release. */
export const ANALYSER_FFT = 1024;
export const ANALYSER_SMOOTHING = 0.65;
const GATE = 0.02;
const ATTACK = 0.35;
const RELEASE = 0.1;

export function configureAnalyser(analyser: AnalyserNode) {
  analyser.fftSize = ANALYSER_FFT;
  analyser.smoothingTimeConstant = ANALYSER_SMOOTHING;
  return analyser;
}

/** Normalises a raw level: noise gate, perceptual curve and clamp to 0..1. */
export function shapeLevel(rms: number) {
  if (rms < GATE) return 0;
  return Math.min(1, Math.pow(Math.min(1, rms * 5), 0.65));
}

/**
 * Builds a frame-polled level reader for an analyser. Reads at most once per animation frame,
 * so several orbs can share one source.
 */
export function analyserLevel(getAnalyser: () => AnalyserNode | null | undefined): LevelSource {
  let level = 0, stamp = -1, buffer = new Float32Array(ANALYSER_FFT);
  return () => {
    const now = performance.now();
    if (now - stamp < 8) return level;
    stamp = now;
    const node = getAnalyser();
    let target = 0;
    if (node) {
      if (buffer.length !== node.fftSize) buffer = new Float32Array(node.fftSize);
      node.getFloatTimeDomainData(buffer);
      let sum = 0;
      for (let i = 0; i < buffer.length; i++) sum += buffer[i] * buffer[i];
      target = shapeLevel(Math.sqrt(sum / buffer.length));
    }
    level += (target - level) * (target > level ? ATTACK : RELEASE);
    return level;
  };
}
