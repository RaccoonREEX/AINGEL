// Preparado para captura: MediaPipe Hand Landmarker (21 puntos) → pose del rig AINGEL → keyframes.
// No abre la cámara. Recibe los resultados ya calculados (worldLandmarks preferentemente, en metros).
// Índices MediaPipe: 0 muñeca · pulgar 1-4 · índice 5-8 · medio 9-12 · anular 13-16 · meñique 17-20.
import * as THREE from 'three';
import { DIM, eulerQ } from './handRig.js';

const CH = { thumb: [1, 2, 3, 4], index: [5, 6, 7, 8], middle: [9, 10, 11, 12], ring: [13, 14, 15, 16], pinky: [17, 18, 19, 20] };
const NAMES = { thumb: ['metacarpal', 'proximal', 'distal'], index: ['proximal', 'intermediate', 'distal'], middle: ['proximal', 'intermediate', 'distal'], ring: ['proximal', 'intermediate', 'distal'], pinky: ['proximal', 'intermediate', 'distal'] };
const R2D = 180 / Math.PI;
const r1 = v => Math.round(v * 10) / 10;

// landmarks: [{x,y,z}×21] · handedness: 'Right' | 'Left' (de la persona, ya corregido el espejo de la cámara)
export function landmarksToPose(landmarks, { handedness = 'Right' } = {}) {
  const P = landmarks.map(p => new THREE.Vector3(p.x, -p.y, -p.z));      // y arriba, z hacia la cámara
  const isLeft = handedness === 'Left';
  if (isLeft) P.forEach(p => p.x = -p.x);                                   // se normaliza a mano derecha; el rig espeja
  const Y = P[9].clone().sub(P[0]).normalize();
  let X = P[5].clone().sub(P[17]).normalize();                             // hacia el pulgar
  const Z = new THREE.Vector3().crossVectors(X, Y).normalize();            // normal de la palma
  X = new THREE.Vector3().crossVectors(Y, Z).normalize();
  const basis = new THREE.Matrix4().makeBasis(X, Y, Z), inv = basis.clone().invert();
  const wristQ = new THREE.Quaternion().setFromRotationMatrix(basis);
  const e = new THREE.Euler().setFromQuaternion(wristQ, 'XYZ');
  const fingers = {};
  for (const f in CH) {
    const ids = CH[f], out = {}; let parentQ = new THREE.Quaternion();
    for (let i = 0; i < 3; i++) {
      const d = P[ids[i + 1]].clone().sub(P[ids[i]]).applyMatrix4(inv).normalize();  // dirección local a la palma
      const rest = eulerQ(DIM[f].rest[i]);
      const local = d.clone().applyQuaternion(parentQ.clone().multiply(rest).invert());
      const fx = Math.atan2(local.z, local.y) * R2D, fz = -Math.atan2(local.x, Math.hypot(local.y, local.z)) * R2D;
      out[NAMES[f][i]] = [r1(fx), 0, r1(i === 0 ? fz : 0)];
      parentQ = parentQ.multiply(rest).multiply(eulerQ(out[NAMES[f][i]]));
    }
    fingers[f] = out;
  }
  return { fingers, rotation: [r1(e.x * R2D), r1(e.y * R2D), r1(e.z * R2D)] };
}

// frames: [{t (s), right?: {landmarks, image:{x,y}}, left?: {...}}] → definición de seña reproducible.
// toPosition: convierte la posición de la muñeca en imagen (0..1) a unidades del orb.
export function framesToSign(frames, { id = 'captura', label, step = 3, toPosition = p => [(.5 - p.x) * 6, (.5 - p.y) * 6, .8] } = {}) {
  const keyframes = [];
  frames.forEach((fr, i) => {
    if (i % step && i !== frames.length - 1) return;
    const kf = { t: +fr.t.toFixed(3), ease: 'linear' };
    for (const h of ['right', 'left']) {
      if (!fr[h]) continue;
      const p = landmarksToPose(fr[h].landmarks, { handedness: h === 'right' ? 'Right' : 'Left' });
      kf[h] = { fingers: p.fingers, rotation: p.rotation, position: toPosition(fr[h].image || { x: .5, y: .5 }) };
    }
    keyframes.push(kf);
  });
  return { id, label: label || id, status: 'captured-unverified', source: { type: 'mediapipe' }, keyframes };
}
