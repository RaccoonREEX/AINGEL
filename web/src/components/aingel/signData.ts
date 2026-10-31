/*
 * AINGEL signs catalogue v1.5.0 (AINGEL_Manos_y_Senas v1.0.0, aingel-signer.js): hand shapes, sign keyframes and
 * hand geometry. Shared by the 2D signer (AingelSigner.tsx) and the three.js hands (hands3d/convert.ts), so both
 * play exactly the same signs. AINGEL DESIGN, PENDING LSEC VALIDATION by Deaf signers.
 */
import type { SignId } from "./signLexicon";

/** Default pace of AINGEL's hands everywhere (1.5×, chosen on 29-10-2026); the translator lets the person slow it down. */
export const HANDS_SPEED = 1.5;

type V = number[];
export type Shape = { t: V; f: V[]; sp: number };
const X: V = [1, 1], O0: V = [0, 0];
const H = (t: V, f: V[], sp = 0): Shape => ({ t, f, sp });
const TA: V = [0.55, 0.95, 0.35, 0.45];
export const HS: Record<string, Shape> = {
  relax: H([0.7, 0.3, 0.2, 0.2], [[0.25, 0.3], [0.3, 0.35], [0.35, 0.4], [0.4, 0.45]], 0.06),
  open: H([1.05, 0, 0, 0], [O0, O0, O0, O0], 0.16),
  flat: H([0.25, 0.55, 0.15, 0.2], [O0, O0, O0, O0], 0),
  a: H([0.12, 0, 0, 0], [X, X, X, X]),
  b: H(TA, [O0, O0, O0, O0], 0),
  c: H([0.95, 0.45, 0.2, 0.3], [[0.45, 0.5], [0.45, 0.5], [0.45, 0.5], [0.45, 0.5]], 0),
  d: H([0.65, 0.85, 0.35, 0.45], [O0, [0.6, 0.75], [0.6, 0.75], [0.6, 0.75]]),
  e: H([0.5, 1, 0.55, 0.65], [[0.25, 1], [0.25, 1], [0.25, 1], [0.25, 1]]),
  f: H([0.65, 0.85, 0.3, 0.35], [[0.55, 0.65], O0, O0, O0], 0.16),
  g: H([0.55, 0.15, 0, 0], [O0, X, X, X]),
  h: H(TA, [O0, O0, X, X], 0),
  i: H(TA, [X, X, X, O0]),
  k: H([0.3, 0.55, 0, 0.15], [O0, [0.45, 0], X, X], 0.2),
  l: H([1.55, 0, 0, 0], [O0, X, X, X]),
  m: H([0.5, 1, 0.5, 0.5], [[0.95, 0.6], [0.95, 0.6], [0.95, 0.6], X]),
  n: H([0.5, 1, 0.5, 0.5], [[0.95, 0.6], [0.95, 0.6], X, X]),
  o: H([0.7, 0.8, 0.3, 0.4], [[0.6, 0.65], [0.6, 0.65], [0.6, 0.65], [0.6, 0.65]], 0),
  r: H(TA, [O0, O0, X, X], -0.12),
  s: H([0.6, 0.95, 0.3, 0.4], [X, X, X, X]),
  t: H([0.35, 0.65, 0.05, 0.05], [[0.85, 0.45], X, X, X]),
  u: H(TA, [O0, O0, X, X], 0),
  v: H(TA, [O0, O0, X, X], 0.48),
  w: H([0.55, 1, 0.45, 0.55], [O0, O0, O0, X], 0.3),
  x: H(TA, [[0.05, 1], X, X, X]),
  y: H([1.55, 0, 0, 0], [X, X, X, O0], 0.3),
  idx: H(TA, [O0, X, X, X]),
  n3: H([1.1, 0, 0, 0], [O0, O0, X, X], 0.3),
  n4: H(TA, [O0, O0, O0, O0], 0.2),
  claw: H([1, 0.3, 0.3, 0.5], [[0.25, 0.75], [0.25, 0.75], [0.25, 0.75], [0.25, 0.75]], 0.18),
  bent: H([0.3, 0.5, 0.1, 0.1], [[0.95, 0], [0.95, 0], [0.95, 0], [0.95, 0]], 0),
  pinch: H([0.75, 0.75, 0.25, 0.35], [[0.5, 0.55], [0.4, 0.4], [0.3, 0.3], [0.25, 0.25]], 0.05),
};

// Poses: x,y in head radii (0,0 = face centre, y down); s scale; yaw/pitch/roll radians; hs hand shape; a alpha.
export type Pose = { x: number; y: number; s: number; yaw: number; pitch: number; roll: number; a: number; hs: string };
export type KF = [number, Partial<Pose>];
export type Sign = { d: number; A?: KF[]; B?: KF[] };
export const RA: Pose = { x: -1.3, y: 3.0, s: 0.85, yaw: 0.2, pitch: 0.9, roll: 0.15, hs: "relax", a: 0 };
export const RB: Pose = { x: 1.3, y: 3.0, s: 0.85, yaw: 0.2, pitch: 0.9, roll: 0.15, hs: "relax", a: 0 };
const FS = { x: -1.55, y: 1.0, s: 1.05, yaw: 0, pitch: 0, roll: 0 };
const letter = (hs: string, extra: Partial<Pose> = {}): Partial<Pose> => ({ ...FS, hs, ...extra });
const still = (p: Partial<Pose>): KF[] => [[0, p], [0.5, { y: (p.y ?? 0) - 0.04 }], [1, { y: p.y }]];
const P = (o: Partial<Pose>) => o;
export const S: Record<SignId, Sign> = {};
"a b c d e f g h i k l m n o r s t u v w x y".split(" ").forEach((k) => {
  const ex = ({ c: { yaw: 0.95 }, o: { yaw: 0.75 }, g: { roll: -1.45, yaw: 0.3 }, h: { roll: -1.45, yaw: 0.3 }, k: { yaw: 0.2 }, e: { yaw: 0.15 }, t: { yaw: 0.1 } } as Record<string, Partial<Pose>>)[k];
  S[k] = { d: 1.0, A: still(letter(k, ex)) };
});
S.j = { d: 1.3, A: [[0, letter("i", { y: 0.9 })], [0.35, { y: 1.35 }], [0.7, { x: -0.8, y: 1.5, roll: 0.7 }], [1, { x: -0.7, y: 1.35, roll: 1.1 }]] };
S.z = { d: 1.5, A: [[0, letter("idx", { x: -1.35, y: 0.8 })], [0.25, { x: -0.75 }], [0.55, { x: -1.35, y: 1.4 }], [0.8, { x: -0.75 }], [1, {}]] };
S["ñ"] = { d: 1.3, A: [[0, letter("n")], [0.3, { x: -0.9, roll: 0.25 }], [0.55, { x: -1.15, roll: -0.2 }], [0.8, { x: -0.9, roll: 0.2 }], [1, { x: -1.05, roll: 0 }]] };
S.p = { d: 1.0, A: still(letter("k", { roll: 2.5, pitch: 0.4, y: 1.4 })) };
S.q = { d: 1.0, A: still(letter("g", { roll: 2.7, pitch: 0.3, y: 1.4 })) };
S.n0 = { d: 1, A: still(letter("o", { yaw: 0.7 })) };
S.n1 = { d: 1, A: still(letter("idx")) };
S.n2 = { d: 1, A: still(letter("v")) };
S.n3 = { d: 1, A: still(letter("n3")) };
S.n4 = { d: 1, A: still(letter("n4")) };
S.n5 = { d: 1, A: still(letter("open")) };
const nb = (hs: string) => still({ x: 1.0, y: 1.3, s: 1.05, yaw: 0, pitch: 0, roll: 0, hs });
S.n6 = { d: 1.2, A: still(letter("open", { x: -1.0, y: 1.3 })), B: nb("idx") };
S.n7 = { d: 1.2, A: still(letter("open", { x: -1.0, y: 1.3 })), B: nb("v") };
S.n8 = { d: 1.2, A: still(letter("open", { x: -1.0, y: 1.3 })), B: nb("n3") };
S.n9 = { d: 1.2, A: still(letter("open", { x: -1.0, y: 1.3 })), B: nb("n4") };
S.n10 = { d: 1.3, A: [[0, letter("open", { x: -1.0, y: 1.3 })], [0.3, { roll: 0.2 }], [0.6, { roll: -0.15 }], [1, { roll: 0 }]], B: [[0, { x: 0.95, y: 1.25, s: 1.05, yaw: 0, pitch: 0, roll: 0, hs: "open" }], [0.3, { roll: 0.2 }], [0.6, { roll: -0.15 }], [1, { roll: 0 }]] };
S.yo = { d: 1.2, A: [[0, P({ x: -0.35, y: 2.1, s: 1, yaw: 1.5, pitch: 0, roll: 1.6, hs: "idx" })], [0.4, { x: -0.15, y: 2.0, s: 0.95 }], [0.7, { x: -0.2 }], [1, {}]] };
// The index points out of the screen, at the person AINGEL talks to (a positive pitch tilted it back, at AINGEL itself).
S.tu = { d: 1.2, A: [[0, P({ x: -0.5, y: 1.6, s: 1, yaw: 0.3, pitch: -1.2, roll: 0, hs: "idx" })], [0.45, { y: 1.45, s: 1.3, pitch: -1.45 }], [1, {}]] };
S.hola = { d: 1.5, A: [[0, P({ x: -0.9, y: -0.3, s: 1.05, yaw: 0, pitch: 0, roll: -0.1, hs: "b" })], [0.35, { x: -1.4, y: -0.1, roll: -0.35, hs: "open" }], [0.55, { roll: 0.05 }], [0.75, { roll: -0.35 }], [1, { roll: -0.1 }]] };
S.gracias = { d: 1.5, A: [[0, P({ x: -0.2, y: 0.85, s: 1, yaw: 0.2, pitch: 0.2, roll: 0.1, hs: "flat" })], [0.25, {}], [0.75, { x: -0.55, y: 1.55, s: 1.25, pitch: 1.1 }], [1, {}]] };
S.porfavor = { d: 1.6, A: [[0, P({ x: -0.25, y: 2.0, s: 1, yaw: 0, pitch: 0.1, roll: 0.3, hs: "flat" })], [0.25, { x: 0.1, y: 1.85 }], [0.5, { x: 0.15, y: 2.15 }], [0.75, { x: -0.25, y: 2.25 }], [1, { x: -0.25, y: 2.0 }]] };
S.si = { d: 1.2, A: [[0, P({ x: -0.75, y: 1.5, s: 1, yaw: 0.4, pitch: 0, roll: 0, hs: "s" })], [0.25, { pitch: 0.8, y: 1.6 }], [0.5, { pitch: 0, y: 1.5 }], [0.75, { pitch: 0.8, y: 1.6 }], [1, { pitch: 0, y: 1.5 }]] };
S.no = { d: 1.2, A: [[0, P({ x: -0.75, y: 1.3, s: 1, yaw: 0.1, pitch: 0, roll: 0, hs: "idx" })], [0.25, { roll: 0.4 }], [0.5, { roll: -0.4 }], [0.75, { roll: 0.4 }], [1, { roll: 0 }]] };
S.bien = { d: 1.2, A: [[0, P({ x: -0.7, y: 1.7, s: 1, yaw: 1.4, pitch: 0, roll: 0, hs: "a" })], [0.45, { y: 1.45, s: 1.2 }], [1, {}]] };
S.mal = { d: 1.2, A: [[0, P({ x: -0.7, y: 1.45, s: 1, yaw: 1.4, pitch: 0, roll: 3.1, hs: "a" })], [0.45, { y: 1.75, s: 1.15 }], [1, {}]] };
S.agua = { d: 1.4, A: [[0, P({ x: -0.35, y: 0.85, s: 1, yaw: 1.2, pitch: 0, roll: 0, hs: "c" })], [0.3, { x: -0.15, y: 0.6, roll: -0.6 }], [0.55, { x: -0.3, y: 0.85, roll: 0 }], [0.8, { x: -0.15, y: 0.6, roll: -0.6 }], [1, { x: -0.3, y: 0.85, roll: 0 }]] };
S.comida = { d: 1.3, A: [[0, P({ x: -0.3, y: 0.95, s: 1, yaw: 1.1, pitch: 0.5, roll: 0.5, hs: "pinch" })], [0.25, { x: -0.1, y: 0.62 }], [0.5, { x: -0.3, y: 0.95 }], [0.75, { x: -0.1, y: 0.62 }], [1, { x: -0.3, y: 0.95 }]] };
S.medicina = { d: 1.6, B: [[0, P({ x: 0.45, y: 2.05, s: 1, yaw: 0, pitch: 1.35, roll: -1.5, hs: "flat" })], [1, {}]], A: [[0, P({ x: 0.05, y: 1.75, s: 0.95, yaw: 0.2, pitch: 0.3, roll: 2.4, hs: "k" })], [0.25, { x: 0.25 }], [0.5, { x: 0.1, y: 1.6 }], [0.75, { x: 0.25, y: 1.75 }], [1, { x: 0.05 }]] };
S.casa = { d: 1.5, A: [[0, P({ x: -0.25, y: 1.0, s: 1, yaw: 0.6, pitch: 0, roll: 0.7, hs: "flat" })], [0.3, {}], [1, { x: -0.75, y: 1.65, roll: 0.05 }]], B: [[0, P({ x: 0.25, y: 1.0, s: 1, yaw: 0.6, pitch: 0, roll: 0.7, hs: "flat" })], [0.3, {}], [1, { x: 0.75, y: 1.65, roll: 0.05 }]] };
S.parque = { d: 1.6, B: [[0, P({ x: 0.3, y: 2.25, s: 0.95, yaw: 1.2, pitch: 1.3, roll: -1.5, hs: "flat" })], [1, {}]], A: [[0, P({ x: -0.15, y: 1.1, s: 1.05, yaw: 0, pitch: 0, roll: 0, hs: "open" })], [0.25, { roll: 0.25 }], [0.5, { roll: -0.2 }], [0.75, { x: -0.6, roll: 0.25 }], [1, { roll: 0 }]] };
S.pelota = { d: 1.4, A: [[0, P({ x: -0.75, y: 1.75, s: 1, yaw: 1.2, pitch: 0, roll: 0.3, hs: "claw" })], [0.4, { x: -0.45 }], [1, { x: -0.5, y: 1.7 }]], B: [[0, P({ x: 0.75, y: 1.75, s: 1, yaw: 1.2, pitch: 0, roll: 0.3, hs: "claw" })], [0.4, { x: 0.45 }], [1, { x: 0.5, y: 1.7 }]] };
S.libro = { d: 1.5, A: [[0, P({ x: -0.15, y: 1.7, s: 1, yaw: 1.5, pitch: 0, roll: 0.1, hs: "flat" })], [0.3, {}], [0.8, { x: -0.6, yaw: 0.1, pitch: 0.9, roll: 1.0 }], [1, {}]], B: [[0, P({ x: 0.15, y: 1.7, s: 1, yaw: 1.5, pitch: 0, roll: 0.1, hs: "flat" })], [0.3, {}], [0.8, { x: 0.6, yaw: 0.1, pitch: 0.9, roll: 1.0 }], [1, {}]] };
S.bano = { d: 1.3, A: [[0, P({ x: -0.75, y: 1.45, s: 1, yaw: 0, pitch: 0, roll: 0, hs: "t" })], [0.25, { roll: 0.35 }], [0.5, { roll: -0.3 }], [0.75, { roll: 0.35 }], [1, { roll: 0 }]] };
S.doctor = { d: 1.4, B: [[0, P({ x: 0.45, y: 2.1, s: 0.95, yaw: 0.2, pitch: 1.4, roll: -1.3, hs: "flat" })], [1, {}]], A: [[0, P({ x: 0.15, y: 1.75, s: 0.95, yaw: 0.3, pitch: 0.5, roll: 2.3, hs: "u" })], [0.3, { y: 1.9 }], [0.55, { y: 1.75 }], [0.8, { y: 1.9 }], [1, { y: 1.75 }]] };
S.familia = { d: 1.7, A: [[0, P({ x: -0.25, y: 1.6, s: 1, yaw: 0.3, pitch: 0, roll: 0, hs: "f" })], [0.5, { x: -0.85, y: 1.85 }], [1, { x: -0.3, y: 2.1 }]], B: [[0, P({ x: 0.25, y: 1.6, s: 1, yaw: 0.3, pitch: 0, roll: 0, hs: "f" })], [0.5, { x: 0.85, y: 1.85 }], [1, { x: 0.3, y: 2.1 }]] };
S.mama = { d: 1.3, A: [[0, P({ x: -0.3, y: 0.85, s: 0.95, yaw: 1.3, pitch: 0, roll: 0, hs: "open" })], [0.25, { x: -0.12 }], [0.5, { x: -0.3 }], [0.75, { x: -0.12 }], [1, { x: -0.3 }]] };
S.papa = { d: 1.3, A: [[0, P({ x: -0.3, y: -0.55, s: 0.95, yaw: 1.3, pitch: 0, roll: 0, hs: "open" })], [0.25, { x: -0.12 }], [0.5, { x: -0.3 }], [0.75, { x: -0.12 }], [1, { x: -0.3 }]] };
const cradle = (side: number): KF[] => [[0, P({ x: side * 0.3, y: 2.0, s: 0.95, yaw: 0, pitch: 1.3, roll: side * -1.4, hs: "flat" })], [0.3, { x: side * 0.45, y: 1.9 }], [0.6, { x: side * 0.15, y: 2.1 }], [1, { x: side * 0.3, y: 2.0 }]];
S.hija = { d: 1.6, A: cradle(-1), B: cradle(1) };
S.hijo = { d: 1.6, A: [[0, P({ x: -0.75, y: -0.15, s: 0.95, yaw: 1.2, pitch: 0, roll: -0.3, hs: "b" })], [0.35, {}], [0.7, { x: -0.3, y: 2.0, yaw: 0, pitch: 1.3, roll: 1.4, hs: "flat" }], [1, {}]], B: [[0, RB], [0.55, RB], [0.75, P({ x: 0.3, y: 2.05, s: 0.95, yaw: 0, pitch: 1.3, roll: -1.4, hs: "flat" })], [1, {}]] };
S.dolor = { d: 1.4, A: [[0, P({ x: -0.55, y: 1.8, s: 1, yaw: 1.5, pitch: 0, roll: 1.5, hs: "idx" })], [0.25, { x: -0.3, roll: 1.2 }], [0.5, { x: -0.5, roll: 1.6 }], [0.75, { x: -0.3, roll: 1.2 }], [1, { x: -0.5, roll: 1.5 }]], B: [[0, P({ x: 0.55, y: 1.8, s: 1, yaw: 1.5, pitch: 0, roll: 1.5, hs: "idx" })], [0.25, { x: 0.3, roll: 1.2 }], [0.5, { x: 0.5, roll: 1.6 }], [0.75, { x: 0.3, roll: 1.2 }], [1, { x: 0.5, roll: 1.5 }]] };
S.ayuda = { d: 1.5, B: [[0, P({ x: 0.15, y: 2.35, s: 1, yaw: 0, pitch: 1.35, roll: -1.5, hs: "flat" })], [0.3, {}], [1, { y: 1.75 }]], A: [[0, P({ x: 0, y: 2.0, s: 1, yaw: 1.4, pitch: 0, roll: 0, hs: "a" })], [0.3, {}], [1, { y: 1.4 }]] };
S.hoy = { d: 1.3, A: [[0, P({ x: -0.55, y: 1.7, s: 1, yaw: 0, pitch: 1.35, roll: 0.2, hs: "flat" })], [0.25, { y: 1.95 }], [0.5, { y: 1.7 }], [0.75, { y: 1.95 }], [1, { y: 1.75 }]], B: [[0, P({ x: 0.55, y: 1.7, s: 1, yaw: 0, pitch: 1.35, roll: 0.2, hs: "flat" })], [0.25, { y: 1.95 }], [0.5, { y: 1.7 }], [0.75, { y: 1.95 }], [1, { y: 1.75 }]] };
S.manana = { d: 1.3, A: [[0, P({ x: -0.65, y: 0.35, s: 0.95, yaw: 1.3, pitch: 0, roll: 0, hs: "a" })], [0.3, {}], [1, { x: -0.95, y: 0.7, s: 1.2, pitch: 0.8 }]] };
S.ayer = { d: 1.3, A: [[0, P({ x: -0.75, y: 0.55, s: 1, yaw: 1.3, pitch: 0, roll: 0, hs: "a" })], [0.3, {}], [1, { x: -0.95, y: 0.0, s: 0.85, roll: -0.8 }]] };
S.caminar = { d: 1.6, A: [[0, P({ x: -0.3, y: 1.6, s: 1, yaw: 0, pitch: 0, roll: 3.14, hs: "v" })], [0.25, { x: -0.45, roll: 2.8 }], [0.5, { x: -0.6, roll: 3.4 }], [0.75, { x: -0.75, roll: 2.8 }], [1, { x: -0.9, roll: 3.14 }]] };
S.leer = { d: 1.6, B: [[0, P({ x: 0.35, y: 1.95, s: 1, yaw: 0, pitch: 0, roll: -0.15, hs: "flat" })], [1, {}]], A: [[0, P({ x: -0.15, y: 1.35, s: 0.95, yaw: 0.2, pitch: 0.6, roll: 2.9, hs: "v" })], [0.35, { y: 1.75 }], [0.55, { y: 1.45 }], [0.85, { y: 1.85 }], [1, {}]] };
S.comer = S.comida;
S.beber = { d: 1.4, A: [[0, P({ x: -0.45, y: 1.2, s: 1, yaw: 1.2, pitch: 0, roll: 0, hs: "c" })], [0.45, { x: -0.15, y: 0.65, roll: -0.9 }], [0.7, {}], [1, { x: -0.45, y: 1.2, roll: 0 }]] };
S.dormir = { d: 1.8, A: [[0, P({ x: -0.5, y: -0.25, s: 1, yaw: 0, pitch: 0, roll: 0.1, hs: "open" })], [0.6, { y: 0.2, hs: "pinch" }], [0.75, {}], [1, { x: -0.8, y: 0.35, roll: 0.9, hs: "flat" }]] };
S.esperar = { d: 1.5, A: [[0, P({ x: -0.8, y: 1.6, s: 1, yaw: 0.1, pitch: 0, roll: 0.1, hs: "open" })], [0.2, { hs: "claw" }], [0.4, { hs: "open" }], [0.6, { hs: "claw" }], [0.8, { hs: "open" }], [1, {}]], B: [[0, P({ x: 0.8, y: 1.6, s: 1, yaw: 0.1, pitch: 0, roll: 0.1, hs: "open" })], [0.2, { hs: "claw" }], [0.4, { hs: "open" }], [0.6, { hs: "claw" }], [0.8, { hs: "open" }], [1, {}]] };
S.ir = { d: 1.3, A: [[0, P({ x: -0.35, y: 1.9, s: 0.95, yaw: 0.3, pitch: 1.2, roll: 0, hs: "idx" })], [0.6, { x: -0.9, y: 1.3, s: 1.25, pitch: 1.5 }], [1, {}]] };
S.venir = { d: 1.3, A: [[0, P({ x: -0.9, y: 1.3, s: 1.25, yaw: 0.3, pitch: 1.5, roll: 0, hs: "idx" })], [0.6, { x: -0.35, y: 1.95, s: 0.95, pitch: 1.2, hs: "x" }], [1, {}]] };
S.llamar = { d: 1.4, A: [[0, P({ x: -1.15, y: 0.15, s: 1, yaw: 0, pitch: 0, roll: -0.5, hs: "y" })], [0.3, { x: -1.05 }], [0.55, { x: -1.15 }], [0.8, { x: -1.05 }], [1, { x: -1.15 }]] };
S.ayudar = S.ayuda;
S.necesitar = { d: 1.3, A: [[0, P({ x: -0.7, y: 1.4, s: 1, yaw: 0.4, pitch: 0, roll: 0, hs: "x" })], [0.3, { y: 1.7, pitch: 0.9 }], [0.55, { y: 1.4, pitch: 0 }], [0.8, { y: 1.7, pitch: 0.9 }], [1, { y: 1.45, pitch: 0 }]] };
S.querer = { d: 1.4, A: [[0, P({ x: -0.75, y: 1.4, s: 1.15, yaw: 2.9, pitch: 0.3, roll: 0, hs: "claw" })], [0.6, { x: -0.45, y: 1.85, s: 0.95, hs: "claw" }], [1, {}]], B: [[0, P({ x: 0.75, y: 1.4, s: 1.15, yaw: 2.9, pitch: 0.3, roll: 0, hs: "claw" })], [0.6, { x: 0.45, y: 1.85, s: 0.95 }], [1, {}]] };
S.tener = { d: 1.3, A: [[0, P({ x: -0.75, y: 1.45, s: 1.15, yaw: 0.2, pitch: 0.6, roll: 0, hs: "open" })], [0.55, { x: -0.35, y: 1.95, s: 0.95, hs: "s" }], [1, {}]] };
S.jugar = { d: 1.4, A: [[0, P({ x: -0.75, y: 1.6, s: 1, yaw: 0, pitch: 0, roll: 0, hs: "y" })], [0.25, { roll: 0.45 }], [0.5, { roll: -0.3 }], [0.75, { roll: 0.45 }], [1, { roll: 0 }]], B: [[0, P({ x: 0.75, y: 1.6, s: 1, yaw: 0, pitch: 0, roll: 0, hs: "y" })], [0.25, { roll: 0.45 }], [0.5, { roll: -0.3 }], [0.75, { roll: 0.45 }], [1, { roll: 0 }]] };
S.pregunta = { d: 1.2, A: [[0, P({ x: -0.75, y: 1.7, s: 1, yaw: 0, pitch: 1.4, roll: 0.3, hs: "open" })], [0.5, { y: 1.55, roll: 0.5 }], [1, {}]], B: [[0, P({ x: 0.75, y: 1.7, s: 1, yaw: 0, pitch: 1.4, roll: 0.3, hs: "open" })], [0.5, { y: 1.55, roll: 0.5 }], [1, {}]] };

export const hasSign = (id: SignId) => !!S[id];

export const hsVec = (name: string) => {
  const h = HS[name] || HS.relax, v = [h.t[0], h.t[1], h.t[2], h.t[3], h.sp];
  h.f.forEach((f) => v.push(f[0], f[1]));
  return v;
};

// Hand space: x right, y down, z toward the viewer (palm side); origin at the palm centre.
export type P3 = [number, number, number];
const KN = [[0.35, -0.42], [0.12, -0.48], [-0.11, -0.46], [-0.33, -0.38]], FLEN = [0.95, 1.07, 1.0, 0.8], FW = [0.17, 0.176, 0.166, 0.142], SPF = [1, -0.15, -0.55, -1.05];
export function chain(base: P3, dir: P3, bend: P3, lens: number[], angs: number[]): P3[] {
  const pts: P3[] = [[...base]];
  let p: P3 = [...base], th = 0;
  for (let i = 0; i < lens.length; i++) {
    th += angs[i];
    const c = Math.cos(th), s = Math.sin(th);
    p = [p[0] + (dir[0] * c + bend[0] * s) * lens[i], p[1] + (dir[1] * c + bend[1] * s) * lens[i], p[2] + (dir[2] * c + bend[2] * s) * lens[i]];
    pts.push(p);
  }
  return pts;
}
export function handGeo(h: number[]) {
  const sp = Math.max(h[4], 0.1), fingers: { w: number; thumb?: boolean; pts: P3[] }[] = [];
  for (let f = 0; f < 4; f++) {
    const a = sp * SPF[f], m = h[5 + f * 2], q = h[6 + f * 2], L = FLEN[f];
    fingers.push({ w: FW[f], pts: chain([KN[f][0], KN[f][1], 0], [Math.sin(a), -Math.cos(a), 0], [0, 0, 1], [L * 0.46, L * 0.3, L * 0.24], [m * 1.5, q * 1.65, q * 1.1]) });
  }
  const ta = h[0], to = h[1], dx = Math.sin(ta) * (1 - 1.5 * to), dy = -Math.cos(ta) * (1 - 0.25 * to), dz = 0.95 * to, n = Math.hypot(dx, dy, dz);
  fingers.push({ w: 0.19, thumb: true, pts: chain([0.36, 0.26, 0], [dx / n, dy / n, dz / n], [-0.75, 0, 0.66], [0.42, 0.31, 0.26], [h[2] * 1.0 + 0.15, h[3] * 1.3, h[3] * 0.9]) });
  return fingers;
}
