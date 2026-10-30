// Biblioteca de poses, señas y secuencias registradas en código.
// AINGEL: sin fetch a /data; las señas se generan desde el catálogo 2D (convert.ts) y se registran al usarlas.
import { fingersToJoints, emptyJoints } from './poseController.js';
import relaxed from './relaxed.json';

export const library = {
  poses: new Map(), signs: new Map(), sequences: new Map(), _pj: new Map(),
  // Reposo de data/index.json del paquete, con la mano algo más pequeña (escala AINGEL).
  rest: {
    right: { pose: 'relaxed', position: [-1.35, -2.9, 0.4], rotation: [-25, 20, 15], scale: 0.8 },
    left: { pose: 'relaxed', position: [1.35, -2.9, 0.4], rotation: [-25, 20, 15], scale: 0.8 }
  },
  registerPose(d) { this.poses.set(d.id, d); this._pj.delete(d.id); return d; },
  registerSign(d) { this.signs.set(d.id, d); return d; },
  registerSequence(d) { this.sequences.set(d.id, d); return d; },
  poseJoints(id) {
    if (!this._pj.has(id)) {
      const d = this.poses.get(id);
      if (!d) { console.warn('[aingel-hands] pose desconocida:', id); return emptyJoints(); }
      this._pj.set(id, fingersToJoints(d.fingers));
    }
    return this._pj.get(id);
  },
  sign(x) { return typeof x === 'string' ? this.signs.get(x) : x; },
  sequence(x) { return typeof x === 'string' ? this.sequences.get(x) : x; }
};
library.registerPose(relaxed);
library.ready = Promise.resolve(library);
