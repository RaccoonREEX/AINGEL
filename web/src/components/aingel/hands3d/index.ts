/*
 * AINGEL three.js hands (AINGEL_Manos_y_Senas v1.0.0, engine v0.1.1, three.js 0.184.0 · MIT) driving the
 * catalogue signs converted from the 2D signer. Loaded on demand, so three.js only downloads with the translator.
 */
// @ts-expect-error untyped engine module from the AINGEL hands package
import { HandsView, stats } from "./handRenderer.js";
import { ensureSign } from "./convert";
import type { SignId } from "../signLexicon";

export type Hands3D = {
  layout(w: number, h: number, cx: number, cy: number, r: number): void;
  /** Plays the signs in order (unknown ids are skipped); an empty list returns the hands to rest. */
  play(seq: SignId[]): void;
  setSpeed(speed: number): void;
  dispose(): void;
  stats: { fps: number; renderMs: number; scale: number; views: number };
};

export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { return false; }
}

/** onSign gets the index of the sign that starts, or -1 when the sequence ends. Throws without WebGL. */
export function createHands(host: HTMLElement, onSign: (index: number) => void): Hands3D {
  if (!webglAvailable()) throw new Error("webgl-unavailable");
  const view = new HandsView(host);
  let index = -1;
  host.addEventListener("signstart", () => { index++; onSign(index); });
  host.addEventListener("sequenceend", () => { index = -1; onSign(-1); });
  return {
    layout: (w, h, cx, cy, r) => view.layout(w, h, cx, cy, r),
    play(seq) {
      index = -1;
      const items = seq.filter(ensureSign).map((sign) => ({ sign, gap: 0.08 }));
      if (items.length) view.player.playSequence(items); else view.player.stop();
    },
    setSpeed: (speed) => view.player.setSpeed(speed),
    dispose: () => view.dispose(),
    stats,
  };
}
