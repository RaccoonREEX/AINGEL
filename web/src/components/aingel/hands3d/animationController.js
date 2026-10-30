// Keyframes → clip compilado → muestreo interpolado (posición con trayectoria, slerp de muñeca y dedos).
import * as THREE from 'three';
import { eulerQ } from './handRig.js';
import { cloneHand, cloneJoints, applyFingers, blendHand } from './poseController.js';

export const EASE = {
  linear: k => k,
  easeInOutSine: k => -(Math.cos(Math.PI * k) - 1) / 2,
  easeInOutQuad: k => k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2,
  easeInOutCubic: k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2,
  easeOutCubic: k => 1 - Math.pow(1 - k, 3),
  easeInCubic: k => k * k * k,
  easeOutBack: k => { const c1 = 1.2, c3 = c1 + 1; return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2); }
};
const HANDS = ['right', 'left'];

function resolveHand(spec, prev, lib) {
  const s = cloneHand(prev);
  if (!spec) return s;
  if (spec.pose) s.j = cloneJoints(lib.poseJoints(spec.pose));
  if (spec.fingers) applyFingers(s.j, spec.fingers);
  if (spec.position) s.pos.fromArray(spec.position);
  if (spec.rotation) eulerQ(spec.rotation, 'XYZ', s.rot);
  if (spec.scale != null) s.scl = spec.scale;   // AINGEL: per-hand scale
  return s;
}
function mirrorHand(s) { const m = cloneHand(s); m.pos.x = -m.pos.x; return m; }
const toV = a => a ? new THREE.Vector3().fromArray(a) : null;

export function compileSign(def, lib, start) {
  const kfs = [{ t: 0, ease: EASE.linear, right: cloneHand(start.right), left: cloneHand(start.left), via: {}, contacts: [] }];
  let prev = kfs[0];
  for (const kf of def.keyframes || []) {
    const right = resolveHand(kf.right, prev.right, lib);
    const left = kf.left === 'mirror' ? mirrorHand(right) : resolveHand(kf.left, prev.left, lib);
    const via = { right: toV(kf.right && kf.right.via) };
    if (kf.left === 'mirror') { via.left = via.right ? via.right.clone().setX(-via.right.x) : null; } else via.left = toV(kf.left && kf.left.via);
    let contacts = (kf.contacts || []).map(c => Array.isArray(c) ? { a: c[0], b: c[1], w: c[2] ?? 1 } : { a: c.a, b: c.b, w: c.w ?? 1 });
    if (kf.left === 'mirror') contacts = contacts.concat(contacts.filter(c => c.a.startsWith('right.') && c.b.startsWith('right.')).map(c => ({ a: c.a.replace('right.', 'left.'), b: c.b.replace('right.', 'left.'), w: c.w })));
    const entry = { t: Math.max(0, kf.t || 0), ease: EASE[kf.ease] || EASE.easeInOutSine, right, left, via, contacts };
    if (entry.t === 0) kfs[0] = entry; else kfs.push(entry);
    prev = entry;
  }
  kfs.sort((a, b) => a.t - b.t);
  return { id: def.id, label: def.label || def.id, duration: def.duration ?? kfs[kfs.length - 1].t, kfs };
}

const _b0 = new THREE.Vector3(), _b1 = new THREE.Vector3();
export function sampleClip(clip, t, out) {
  const kfs = clip.kfs; let i = 0;
  while (i < kfs.length - 2 && t > kfs[i + 1].t) i++;
  const a = kfs[i], b = kfs[Math.min(i + 1, kfs.length - 1)];
  const span = b.t - a.t, u = span > 0 ? Math.min(1, Math.max(0, (t - a.t) / span)) : 1, k = b.ease(u);
  for (const h of HANDS) {
    blendHand(out[h], a[h], b[h], k);
    const v = b.via[h];
    if (v) { const m = 1 - k; _b0.copy(a[h].pos).multiplyScalar(m * m); _b1.copy(v).multiplyScalar(2 * m * k); out[h].pos.copy(_b0).add(_b1).addScaledVector(b[h].pos, k * k); }
  }
  const oc = out.contacts || (out.contacts = []); let n = 0;
  const push = (ca, cb, w) => { if (w <= .01) return; const e = oc[n] || (oc[n] = { a: '', b: '', w: 0 }); e.a = ca; e.b = cb; e.w = w; n++; };
  for (const c of a.contacts) { let w1 = 0; for (const d of b.contacts) if (d.a === c.a && d.b === c.b) { w1 = d.w; break; } push(c.a, c.b, c.w + (w1 - c.w) * k); }
  for (const d of b.contacts) { let seen = false; for (const c of a.contacts) if (d.a === c.a && d.b === c.b) { seen = true; break; } if (!seen) push(d.a, d.b, d.w * k); }
  oc.length = n;
  return out;
}
