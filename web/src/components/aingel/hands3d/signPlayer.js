// Reproductor: playSign, playSequence, pause, resume, stop, setSpeed, setPose. Un reproductor por vista.
import { makeHandState, cloneHand, copyHand, blendHand } from './poseController.js';
import { compileSign, sampleClip, EASE } from './animationController.js';

const FADE = .28;
export class SignPlayer {
  constructor(lib, host) {
    this.lib = lib; this.host = host; this.speed = 1; this.paused = false; this.loop = false; this.restAfter = true;
    this.queue = []; this.seq = null; this.clip = null; this.t = 0; this.hold = 0; this.fadeFrom = null; this.fade = 1;
    this.state = { right: makeHandState(lib.rest.right, lib), left: makeHandState(lib.rest.left, lib), contacts: [] };
    this._sample = { right: cloneHand(this.state.right), left: cloneHand(this.state.left), contacts: [] };
  }
  _emit(type, detail) { this.host.dispatchEvent(new CustomEvent(type, { bubbles: true, detail })); }
  _start(def, gap) {
    const d = this.lib.sign(def);
    if (!d) { console.warn('[aingel-hands] seña desconocida:', def); return this._next(); }
    this.clip = compileSign(d, this.lib, this.state);
    this.t = 0; this.hold = gap || 0; this.fadeFrom = { right: cloneHand(this.state.right), left: cloneHand(this.state.left) }; this.fade = 0;
    this._emit('signstart', { id: this.clip.id, label: this.clip.label, status: d.status || null });
  }
  _next() {
    let it = this.queue.shift();
    if (!it && this.loop && this.seq) { this.queue = this.seq.slice(); it = this.queue.shift(); }
    if (!it) {
      const was = this.clip; this.clip = null;
      if (was) this._emit('sequenceend', {});
      if (was && this.restAfter) this.setPose(null, { hand: 'both', toRest: true, duration: .6, silent: true });
      return;
    }
    this._start(it.sign, it.gap);
  }
  playSign(sign, opts = {}) { this.loop = !!opts.loop; this.seq = opts.loop ? [{ sign, gap: opts.gap ?? .3 }] : null; this.queue = [{ sign }]; this.paused = false; this._next(); }
  playSequence(seq, opts = {}) {
    const s = Array.isArray(seq) ? { items: seq } : this.lib.sequence(seq);
    if (!s) return console.warn('[aingel-hands] secuencia desconocida:', seq);
    const items = s.items.map(x => typeof x === 'string' ? { sign: x, gap: s.gap ?? .25 } : { sign: x.sign, gap: x.gap ?? s.gap ?? .25 });
    this.loop = !!opts.loop; this.seq = items; this.queue = items.slice(); this.paused = false; this._next();
  }
  pause() { this.paused = true; }
  resume() { this.paused = false; }
  stop() { this.queue = []; this.seq = null; this.loop = false; this.clip = null; this.paused = false; this.setPose(null, { hand: 'both', toRest: true, duration: .5, silent: true }); }
  setSpeed(s) { this.speed = Math.max(.1, Math.min(3, +s || 1)); }
  // setPose('fist' | {pose, fingers, position, rotation}, {hand:'right'|'left'|'both', duration, toRest})
  setPose(pose, o = {}) {
    const hand = o.hand || 'both', spec = typeof pose === 'string' ? { pose } : (pose || {});
    const kf = { t: o.duration ?? .35, ease: o.ease || 'easeInOutCubic' };
    const pick = h => o.toRest ? this.lib.rest[h] : (o[h] || spec);
    if (hand === 'right' || hand === 'both') kf.right = pick('right');
    if (hand === 'left' || hand === 'both') kf.left = o.toRest ? pick('left') : (o.left || (hand === 'both' && spec.position && !o.noMirror ? 'mirror' : spec));
    this.queue = []; this.seq = null; this.loop = false; this.paused = false;
    this.clip = compileSign({ id: o.silent ? '_rest' : '_pose', keyframes: [kf] }, this.lib, this.state);
    this.t = 0; this.hold = 0; this.fade = 1; this.fadeFrom = null;
    this.clip.transient = true;
  }
  get playing() { return !!this.clip && !this.paused; }
  update(dt) {
    if (!this.clip || this.paused) return false;
    if (this.hold > 0) { this.hold -= dt * this.speed; return false; }
    this.t += dt * this.speed;
    sampleClip(this.clip, this.t, this._sample);
    if (this.fade < 1 && this.fadeFrom) {
      this.fade = Math.min(1, this.fade + dt * this.speed / FADE);
      const k = EASE.easeInOutSine(this.fade);
      blendHand(this.state.right, this.fadeFrom.right, this._sample.right, k);
      blendHand(this.state.left, this.fadeFrom.left, this._sample.left, k);
    } else { copyHand(this.state.right, this._sample.right); copyHand(this.state.left, this._sample.left); }
    this.state.contacts = this._sample.contacts;
    if (this.t >= this.clip.duration) {
      const c = this.clip;
      if (!c.transient) this._emit('signend', { id: c.id });
      if (c.transient) this.clip = null; else this._next();
    }
    return true;
  }
}
