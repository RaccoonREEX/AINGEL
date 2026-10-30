/*
 * AINGEL's articulated three.js hands around the orb (AINGEL_Manos_y_Senas v1.0.0). Same props and onSign
 * contract as AingelSigner; calls onUnavailable when WebGL or the engine cannot start, so the screen can fall
 * back to the 2D hands. Signs: AINGEL design, pending LSEC validation.
 */
import { useEffect, useRef } from "react";
import type { Hands3D } from "./hands3d";
import { HANDS_SPEED } from "./signData";
import type { SignId } from "./signLexicon";

type Props = {
  width: number; height: number;
  /** Centre and radius of the orb (the signer's "head"), in px. */
  cx: number; cy: number; r: number;
  seq: SignId[];
  /** Changing it (from 0) plays seq from the start. */
  playKey: number;
  speed?: number;
  reducedMotion?: boolean;
  onSign?: (index: number) => void;
  onUnavailable: () => void;
};

export default function AingelHands3D({ width, height, cx, cy, r, seq, playKey, speed = HANDS_SPEED, reducedMotion = false, onSign, onUnavailable }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const hands = useRef<Hands3D | null>(null);
  const latest = useRef({ width, height, cx, cy, r, seq, playKey, speed, reducedMotion, onSign, onUnavailable });
  latest.current = { width, height, cx, cy, r, seq, playKey, speed, reducedMotion, onSign, onUnavailable };
  const pace = () => latest.current.speed * (latest.current.reducedMotion || window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0.6 : 1);

  useEffect(() => {
    let dead = false;
    import("./hands3d").then((m) => {
      if (dead || !host.current) return;
      try {
        const h = m.createHands(host.current, (i) => latest.current.onSign?.(i));
        const p = latest.current;
        h.layout(p.width, p.height, p.cx, p.cy, p.r); h.setSpeed(pace());
        if (p.playKey > 0 && p.seq.length) h.play(p.seq);
        hands.current = h;
      } catch { latest.current.onUnavailable(); }
    }).catch(() => { if (!dead) latest.current.onUnavailable(); });
    return () => { dead = true; hands.current?.dispose(); hands.current = null; };
  }, []);
  useEffect(() => { hands.current?.layout(width, height, cx, cy, r); }, [width, height, cx, cy, r]);
  useEffect(() => { hands.current?.setSpeed(pace()); }, [speed, reducedMotion]);
  useEffect(() => { if (playKey > 0) hands.current?.play(seq); }, [playKey]);

  return <div ref={host} className="aingel-hands" style={{ width, height }} aria-hidden="true" />;
}
