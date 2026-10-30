// Rig articulado + modelo visual de una mano (geometría propia, sin modelos de terceros).
// Espacio local: muñeca en el origen, dedos hacia +Y, palma mirando a +Z. Unidad = radio del orb.
import * as THREE from 'three';

export const FINGERS = ['thumb', 'index', 'middle', 'ring', 'pinky'];
export const JOINTS = {
  thumb: ['metacarpal', 'proximal', 'distal'],
  index: ['proximal', 'intermediate', 'distal'],
  middle: ['proximal', 'intermediate', 'distal'],
  ring: ['proximal', 'intermediate', 'distal'],
  pinky: ['proximal', 'intermediate', 'distal']
};
export const JOINT_KEYS = FINGERS.flatMap(f => JOINTS[f].map(j => f + '.' + j));

// Mano derecha. base = nudillo, len = longitud de falanges, r = radios, rest = rotación de reposo [x,y,z]°
export const DIM = {
  thumb:  { base: [.29, .17, .06],  len: [.26, .21, .19], r: [.094, .09, .084], rest: [[18, -40, -32], [0, 0, 0], [0, 0, 0]] },
  index:  { base: [.255, .76, 0],   len: [.33, .22, .19], r: [.079, .075, .071], rest: [[0, 0, -5], [0, 0, 0], [0, 0, 0]] },
  middle: { base: [.085, .79, 0],   len: [.36, .24, .2],  r: [.081, .077, .073], rest: [[0, 0, -1], [0, 0, 0], [0, 0, 0]] },
  ring:   { base: [-.085, .77, 0],  len: [.34, .22, .19], r: [.077, .073, .069], rest: [[0, 0, 4], [0, 0, 0], [0, 0, 0]] },
  pinky:  { base: [-.25, .71, 0],   len: [.27, .18, .16], r: [.069, .065, .061], rest: [[0, 0, 9], [0, 0, 0], [0, 0, 0]] }
};

export const HAND_SCALE = 1.2;   // tamaño de la mano respecto al orb
const D2R = Math.PI / 180;
export function eulerQ(a, order = 'ZXY', out = new THREE.Quaternion()) {
  if (typeof a === 'number') a = [a, 0, 0];
  return out.setFromEuler(new THREE.Euler((a[0] || 0) * D2R, (a[1] || 0) * D2R, (a[2] || 0) * D2R, order));
}
export function mirrorQ(q, out = new THREE.Quaternion()) { return out.set(q.x, -q.y, -q.z, q.w); }

// Paleta AINGEL en sRGB directo (los ShaderMaterial escriben el color tal cual).
const hex = h => new THREE.Vector3(((h >> 16) & 255) / 255, ((h >> 8) & 255) / 255, (h & 255) / 255);
export const PALETTE = { glove: [0xFFFFFF, 0xDCE7F6, 0xB9CBE8], cuff: [0xEBA934, 0xD4922A, 0xB97C22], ink: 0x092E66 };

let shared = null;
function toneMaterial(c) {
  return new THREE.ShaderMaterial({
    name: 'aingel-tone',
    uniforms: { c0: { value: hex(c[0]) }, c1: { value: hex(c[1]) }, c2: { value: hex(c[2]) } },
    vertexShader: 'varying vec3 vN; void main(){ vN = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: 'uniform vec3 c0; uniform vec3 c1; uniform vec3 c2; varying vec3 vN; void main(){ float d = dot(normalize(vN), normalize(vec3(-.45, .55, .75))); vec3 col = d > .22 ? c0 : (d > -.3 ? c1 : c2); gl_FragColor = vec4(col, 1.0); }'
  });
}
function makeShared() {
  const geos = new Map();
  const outline = new THREE.ShaderMaterial({
    name: 'aingel-outline', side: THREE.BackSide,
    uniforms: { t: { value: .03 }, c: { value: hex(PALETTE.ink) } },
    vertexShader: 'uniform float t; void main(){ vec4 p = modelViewMatrix * vec4(position, 1.0); vec3 n = normalize(normalMatrix * normal); p.xyz += n * t; gl_Position = projectionMatrix * p; }',
    fragmentShader: 'uniform vec3 c; void main(){ gl_FragColor = vec4(c, 1.0); }'
  });
  const geo = (key, make) => { if (!geos.has(key)) geos.set(key, make()); return geos.get(key); };
  return {
    refs: 0, geos, outline, glove: toneMaterial(PALETTE.glove), cuff: toneMaterial(PALETTE.cuff),
    capsule: (r, len) => geo('c' + r + '_' + len, () => { const g = new THREE.CapsuleGeometry(r, len, 4, 12); g.translate(0, len / 2, 0); return g; }),
    palm: () => geo('palm', () => new THREE.CapsuleGeometry(.34, .34, 6, 18)),
    cuffGeo: () => geo('cuff', () => new THREE.CylinderGeometry(.3, .32, .26, 24)),
    band: () => geo('band', () => new THREE.CylinderGeometry(.333, .336, .075, 24))
  };
}
export function disposeShared() {
  if (!shared || shared.refs > 0) return;
  shared.geos.forEach(g => g.dispose());
  shared.outline.dispose(); shared.glove.dispose(); shared.cuff.dispose();
  shared = null;
}

export class HandRig {
  constructor(side) {
    const S = shared || (shared = makeShared()); S.refs++;
    this.side = side; this.mirror = side < 0;
    this.root = new THREE.Group(); this.root.name = side > 0 ? 'rightHand' : 'leftHand'; this.root.scale.setScalar(HAND_SCALE);
    this.joints = {}; this.tipJoint = {}; this.tipOffset = {};
    const add = (parent, geo, mat, pos, scale, name) => {
      const m = new THREE.Mesh(geo, mat), o = new THREE.Mesh(geo, S.outline);
      m.name = name; o.name = name + '_outline';
      [m, o].forEach(x => { if (pos) x.position.set(pos[0], pos[1], pos[2]); if (scale) x.scale.set(scale[0], scale[1], scale[2]); x.matrixAutoUpdate = false; x.updateMatrix(); });
      parent.add(m, o);
    };
    add(this.root, S.palm(), S.glove, [0, .43, 0], [1.08, .8, .42], 'palm');
    add(this.root, S.cuffGeo(), S.glove, [0, -.1, 0], [1, 1, .62], 'cuff');
    add(this.root, S.band(), S.cuff, [0, -.13, 0], [1, 1, .64], 'cuffBand');
    FINGERS.forEach(f => {
      const d = DIM[f]; let parent = this.root;
      JOINTS[f].forEach((jn, i) => {
        const g = new THREE.Group(); g.name = f + '.' + jn;
        if (i === 0) g.position.set(d.base[0] * side, d.base[1], d.base[2]); else g.position.set(0, d.len[i - 1], 0);
        const rq = eulerQ(d.rest[i]); g.userData.rest = this.mirror ? mirrorQ(rq) : rq;
        g.quaternion.copy(g.userData.rest);
        add(g, S.capsule(d.r[i], d.len[i]), S.glove, null, null, g.name);
        parent.add(g); parent = g; this.joints[g.name] = g;
      });
      this.tipJoint[f] = parent; this.tipOffset[f] = new THREE.Vector3(0, d.len[2] + d.r[2] * .55, 0);
    });
    this._q = new THREE.Quaternion();
    this._orig = [new THREE.Quaternion(), new THREE.Quaternion(), new THREE.Quaternion()];
    this._chains = {}; FINGERS.forEach(f => this._chains[f] = JOINTS[f].map(j => this.joints[f + '.' + j]));
  }
  apply(state) {
    this.root.position.copy(state.pos); this.root.scale.setScalar(HAND_SCALE * (state.scl ?? 1));   // AINGEL: per-hand scale
    if (this.mirror) mirrorQ(state.rot, this.root.quaternion); else this.root.quaternion.copy(state.rot);
    for (const k of JOINT_KEYS) {
      const g = this.joints[k], q = state.j[k];
      g.quaternion.copy(g.userData.rest).multiply(this.mirror ? mirrorQ(q, this._q) : q);
    }
  }
  tip(f, out = new THREE.Vector3()) { return this.tipJoint[f].localToWorld(out.copy(this.tipOffset[f])); }
  chain(f) { return this._chains[f]; }
  dispose() { this.root.removeFromParent(); if (shared) shared.refs--; }
}
export function outlineMaterial() { return shared && shared.outline; }
