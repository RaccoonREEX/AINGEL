export type OrbState =
  | "idle"
  | "listening"
  | "thinking"
  | "searching"
  | "speaking"
  | "happy"
  | "confused"
  | "retrying";

/** Reads the current audio level (0..1). Called once per animation frame, never through React state. */
export type LevelSource = () => number;

export type OrbOptions = {
  state: OrbState;
  size: number;
  configured: boolean;
  face: boolean;
  eyes: boolean;
  arcs: boolean;
  tone: "light" | "dark";
  /** Fixed number of dots; 0 picks clamp(1.5 * size, 140, 520). */
  density: number;
  reducedMotion: boolean;
  /** 3a: AINGEL looks through its eyes — the eyes become windows onto whatever is drawn behind the canvas. */
  vision?: boolean;
  /** Fill colour painted behind the orb (needed in vision mode so only the eyes are see-through). */
  background?: string;
  /** Level for listening/speaking. A number, or a reader polled each frame. */
  audioLevel?: number | LevelSource;
};
