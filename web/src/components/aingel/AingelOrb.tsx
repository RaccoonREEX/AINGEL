import { useEffect, useRef } from "react";
import { OrbRenderer } from "./orb-core";
import type { LevelSource, OrbState } from "./orb.types";

export type { OrbState, LevelSource } from "./orb.types";

type Props = {
  state?: OrbState;
  /** 0..1, or a reader polled every frame (preferred: no React re-render per frame). */
  audioLevel?: number | LevelSource;
  /** false: grey orb without a face; switching to true plays the activation. */
  configured?: boolean;
  size?: number;
  face?: boolean;
  eyes?: boolean;
  arcs?: boolean;
  tone?: "light" | "dark";
  density?: number;
  reducedMotion?: boolean;
  /** 3a: eyes become windows onto the element behind the orb (e.g. the camera). */
  vision?: boolean;
  background?: string;
  className?: string;
};

/** Decorative AINGEL orb. State is also announced in text by the screens; the canvas is hidden from AT. */
export default function AingelOrb({
  state = "idle", audioLevel, configured = true, size = 240, face = true, eyes = true, arcs = true,
  tone = "light", density = 0, reducedMotion = false, vision = false, background, className,
}: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<OrbRenderer | null>(null);
  const options = { state, audioLevel, configured, size, face, eyes, arcs, tone, density, reducedMotion, vision, background };
  useEffect(() => {
    const orb = new OrbRenderer(canvas.current!, options);
    renderer.current = orb;
    orb.start();
    return () => { orb.stop(); renderer.current = null; };
  }, []);
  useEffect(() => { renderer.current?.update(options); });
  return (
    <div className={className ? `aingel-orb ${className}` : "aingel-orb"} style={{ width: size, height: size }} aria-hidden="true">
      <canvas ref={canvas} />
    </div>
  );
}
