/*
 * 2D catalogue → three.js hands. The signs are NOT redesigned: each 2D hand shape and keyframe of
 * signData.ts (aingel-signer.js, catalogue v1.5.0) is converted to the 3D rig.
 *  - Hand shapes: the 2D hand geometry is turned into the 21 MediaPipe-style points and passed to the
 *    package's own landmarksToPose(), which returns the rig's finger angles (thumb included).
 *  - Keyframes: 2D yaw/pitch/roll (y down) become the rig's wrist rotation; the 2D palm centre becomes the
 *    wrist position; the 2D scale becomes the per-hand scale. Hand A (dominant) is the right hand.
 */
import * as THREE from "three";
import { HS, S, handGeo, hsVec, type Pose } from "../signData";
import type { SignId } from "../signLexicon";
// @ts-expect-error untyped engine module from the AINGEL hands package
import { landmarksToPose } from "./landmarksToPose.js";
// @ts-expect-error untyped engine module from the AINGEL hands package
import { library } from "./library.js";

const R2D = 180 / Math.PI;
/** 2D hand size 1 ≈ this rig scale (rig hands are 1.2 orb radii at scale 1). */
const SIZE = 0.85;
/** Lead-in from the previous pose into the sign's first keyframe, seconds. */
const LEAD = 0.3;
const PALM_CENTRE = 0.43 * 1.2;   // rig: palm capsule centre above the wrist, × HAND_SCALE

type Fingers = Record<string, Record<string, number[]>>;

/** 2D hand shape → rig finger angles, via the package's MediaPipe converter. */
export function shapeToPose(name: string): { id: string; fingers: Fingers } {
  const g = handGeo(hsVec(name));
  const pts: number[][] = new Array(21);
  pts[0] = [0.12, 0.5, 0];                                     // wrist below the middle knuckle
  g[4].pts.forEach((p, i) => { pts[1 + i] = p; });             // thumb CMC, MCP, IP, tip
  for (let f = 0; f < 4; f++) g[f].pts.forEach((p, i) => { pts[5 + f * 4 + i] = p; });
  // MediaPipe convention: y down, z negative towards the camera (our z points to the viewer).
  const landmarks = pts.map(([x, y, z]) => ({ x, y, z: -z }));
  return { id: "2d_" + name, fingers: landmarksToPose(landmarks, { handedness: "Right" }).fingers };
}

/** 2D yaw → pitch → roll with y down becomes, with y up, Rz(−roll)·Rx(−pitch)·Ry(yaw); returned as XYZ degrees. */
function rotation(p: Pose): { deg: number[]; q: THREE.Quaternion } {
  const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(-p.pitch, p.yaw, -p.roll, "ZXY"));
  const e = new THREE.Euler().setFromQuaternion(q, "XYZ");
  return { deg: [e.x * R2D, e.y * R2D, e.z * R2D].map((v) => Math.round(v * 10) / 10), q };
}

export function handSpec(p: Pose, side: 1 | -1) {
  if (p.a < 0.5) return library.rest[side > 0 ? "right" : "left"];   // unused hand: package rest pose
  const { deg, q } = rotation(p), scale = p.s * SIZE;
  const up = new THREE.Vector3(0, PALM_CENTRE * scale, 0).applyQuaternion(q);
  if (side < 0) up.x = -up.x;                                         // the left rig is the mirrored right one
  const r2 = (v: number) => Math.round(v * 1000) / 1000;
  return {
    pose: "2d_" + p.hs,
    position: [r2(p.x - up.x), r2(-p.y - up.y), r2(0.4 + (p.s - 0.85) * 1.5)],
    rotation: deg,
    scale: r2(scale),
  };
}

const RA_REST: Pose = { x: -1.3, y: 3.0, s: 0.85, yaw: 0.2, pitch: 0.9, roll: 0.15, hs: "relax", a: 0 };
const RB_REST: Pose = { ...RA_REST, x: 1.3 };
const full = (track: [number, Partial<Pose>][] | undefined, rest: Pose): [number, Pose][] => {
  if (!track) return [];
  const cur: Pose = { ...rest, a: 1 };
  return track.map(([k, o]) => { Object.assign(cur, o); return [k, { ...cur }]; });
};

/** The 2D poses of both hands at every keyframe time of a sign (u in 0..1). */
export function keyframePoses(id: SignId): { k: number; A: Pose; B: Pose }[] {
  const s = S[id];
  const A = full(s.A, RA_REST), B = full(s.B, RB_REST);
  const times = [...new Set([...A, ...B].map(([k]) => k))].sort((a, b) => a - b);
  // A hand's pose at time k: its own keyframe, or the 2D interpolation when only the other hand has one there.
  const at = (tr: [number, Pose][], k: number, rest: Pose): Pose => {
    if (!tr.length) return rest;
    for (let i = 0; i < tr.length - 1; i++) {
      const [t0, a] = tr[i], [t1, b] = tr[i + 1];
      if (k > t1 + 1e-6) continue;
      const u = Math.max(0, Math.min(1, (k - t0) / Math.max(1e-4, t1 - t0))), e = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
      const mix = (x: number, y: number) => x + (y - x) * e;
      return { x: mix(a.x, b.x), y: mix(a.y, b.y), s: mix(a.s, b.s), yaw: mix(a.yaw, b.yaw), pitch: mix(a.pitch, b.pitch), roll: mix(a.roll, b.roll), a: e < 0.5 ? a.a : b.a, hs: e < 0.5 ? a.hs : b.hs };
    }
    return tr[tr.length - 1][1];
  };
  return times.map((k) => ({ k, A: at(A, k, RA_REST), B: at(B, k, RB_REST) }));
}

let posesReady = false;
/** Registers the 3D version of a catalogue sign (once) and returns whether it exists. */
export function ensureSign(id: SignId): boolean {
  if (library.signs.has(id)) return true;
  const s = S[id];
  if (!s) return false;
  if (!posesReady) { Object.keys(HS).forEach((n) => library.registerPose(shapeToPose(n))); posesReady = true; }
  const keyframes = keyframePoses(id).map(({ k, A: pa, B: pb }, i) => ({
    t: Math.round((LEAD + k * s.d) * 1000) / 1000,
    ease: i === 0 ? "easeInOutCubic" : "easeInOutQuad",
    right: handSpec(pa, 1),
    left: handSpec(pb, -1),
  }));
  library.registerSign({ id, label: id, status: "aingel-design-unvalidated", source: { type: "aingel-signer v1.5.0 (2D)", reviewedBy: null }, keyframes });
  return true;
}
