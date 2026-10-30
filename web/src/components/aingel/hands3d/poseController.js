// Poses → cuaterniones por articulación, estados de mano y contactos (IK CCD).
import * as THREE from 'three';
import { JOINT_KEYS, JOINTS, DIM, eulerQ } from './handRig.js';

export function emptyJoints() { const j = {}; JOINT_KEYS.forEach(k => j[k] = new THREE.Quaternion()); return j; }
export function cloneJoints(src) { const j = {}; JOINT_KEYS.forEach(k => j[k] = src[k].clone()); return j; }
export function applyFingers(joints, fingers) {
  for (const f in fingers || {}) {
    if (!JOINTS[f]) { console.warn('[aingel-hands] dedo desconocido', f); continue; }
    for (const jn in fingers[f]) {
      const k = f + '.' + jn;
      if (!joints[k]) { console.warn('[aingel-hands] articulación desconocida', k); continue; }
      eulerQ(fingers[f][jn], 'ZXY', joints[k]);
    }
  }
  return joints;
}
export function fingersToJoints(fingers) { return applyFingers(emptyJoints(), fingers); }

// AINGEL: per-hand scale (`scale` in hand specs, `scl` in states) so a hand can come towards the viewer, as in the 2D signer.
export function makeHandState(spec, lib) {
  const s = { pos: new THREE.Vector3(), rot: new THREE.Quaternion(), j: emptyJoints(), scl: spec.scale ?? 1 };
  if (spec.pose) s.j = cloneJoints(lib.poseJoints(spec.pose));
  if (spec.fingers) applyFingers(s.j, spec.fingers);
  if (spec.position) s.pos.fromArray(spec.position);
  if (spec.rotation) eulerQ(spec.rotation, 'XYZ', s.rot);
  return s;
}
export function cloneHand(s) { return { pos: s.pos.clone(), rot: s.rot.clone(), j: cloneJoints(s.j), scl: s.scl ?? 1 }; }
export function copyHand(dst, s) { dst.pos.copy(s.pos); dst.rot.copy(s.rot); dst.scl = s.scl ?? 1; JOINT_KEYS.forEach(k => dst.j[k].copy(s.j[k])); return dst; }
export function blendHand(out, a, b, k) {
  out.pos.lerpVectors(a.pos, b.pos, k); out.rot.slerpQuaternions(a.rot, b.rot, k); out.scl = (a.scl ?? 1) + ((b.scl ?? 1) - (a.scl ?? 1)) * k;
  JOINT_KEYS.forEach(key => out.j[key].slerpQuaternions(a.j[key], b.j[key], k));
  return out;
}

// Contacto: lleva la punta del dedo "a" a la punta del dedo "b" rotando solo la cadena de "a".
const _t = new THREE.Vector3(), _e = new THREE.Vector3(), _j = new THREE.Vector3(), _v1 = new THREE.Vector3(), _v2 = new THREE.Vector3();
const _qw = new THREE.Quaternion(), _pq = new THREE.Quaternion(), _ql = new THREE.Quaternion(), _id = new THREE.Quaternion();
const MAX_STEP = 30 * Math.PI / 180;
export function solveContact(rigs, c) {
  const [ha, fa] = c.a.split('.'), [hb, fb] = c.b.split('.');
  const ra = rigs[ha], rb = rigs[hb];
  if (!ra || !rb || !DIM[fa] || !DIM[fb]) return;
  const chain = ra.chain(fa), orig = ra._orig; chain.forEach((g, i) => orig[i].copy(g.quaternion));
  rb.tip(fb, _t); ra.tip(fa, _e);
  const gap = (DIM[fa].r[2] + DIM[fb].r[2]) * .8;
  const dir = _v1.subVectors(_e, _t); if (dir.lengthSq() > 1e-8) _t.addScaledVector(dir.normalize(), gap);
  for (let it = 0; it < 10; it++) {
    ra.tip(fa, _e); if (_e.distanceTo(_t) < .01) break;
    for (let i = chain.length - 1; i >= 0; i--) {
      const g = chain[i];
      g.getWorldPosition(_j); ra.tip(fa, _e);
      _v1.subVectors(_e, _j).normalize(); _v2.subVectors(_t, _j).normalize();
      if (_v1.dot(_v2) > .99995) continue;
      _qw.setFromUnitVectors(_v1, _v2);
      const ang = 2 * Math.acos(Math.min(1, Math.abs(_qw.w)));
      if (ang > MAX_STEP) _qw.slerpQuaternions(_id, _qw, MAX_STEP / ang);
      g.parent.getWorldQuaternion(_pq);
      _ql.copy(_pq).invert().multiply(_qw).multiply(_pq);
      g.quaternion.premultiply(_ql); g.updateMatrixWorld(true);
    }
  }
  const w = Math.max(0, Math.min(1, c.w));
  if (w < 1) chain.forEach((g, i) => g.quaternion.slerpQuaternions(orig[i], g.quaternion, w));
  ra.root.updateMatrixWorld(true);
}
