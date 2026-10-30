// Renderer compartido: UN WebGLRenderer y UN bucle rAF para todas las vistas de la página.
// Cada vista pinta su escena en el renderer compartido y la copia a su propio <canvas> 2D.
import * as THREE from 'three';
import { HandRig, disposeShared, outlineMaterial } from './handRig.js';
import { solveContact } from './poseController.js';
import { SignPlayer } from './signPlayer.js';
import { library } from './library.js';

let renderer = null, raf = 0, last = 0, rW = 0, rH = 0;
// Perfil: fps medidos, coste de render y escala de resolución adaptativa (1 → 0.75 → 0.6 si el equipo no llega).
export const stats = { fps: 60, renderMs: 0, scale: 1, views: 0 };
let acc = 0, frames = 0, slow = 0, fast = 0, drawn = false;
const DPR_CAP = 2;
const views = new Set();
function ensureRenderer() {
  if (renderer) return renderer;
  renderer = new THREE.WebGLRenderer({ antialias: (window.devicePixelRatio || 1) < 1.75, alpha: true, powerPreference: 'default', stencil: false, depth: true, preserveDrawingBuffer: false });
  renderer.setPixelRatio(1); renderer.setClearColor(0x000000, 0); renderer.autoClear = false; renderer.setScissorTest(true);
  rW = rH = 0;
  return renderer;
}
function loop(now) {
  raf = requestAnimationFrame(loop);
  const raw = last ? (now - last) / 1000 : .016, dt = Math.min(.05, raw); last = now;
  if (document.hidden) return;
  let active = false; drawn = false;
  for (const v of views) active = v.tick(dt, now) || active;
  stats.views = views.size;
  if (!active) { acc = 0; frames = 0; return; }
  acc += raw; if (drawn) frames++;
  if (acc >= 1) {
    stats.fps = Math.round(frames / acc); acc = 0; frames = 0;
    if (stats.fps < 45 || stats.renderMs > 10) { fast = 0; if (++slow >= 2 && stats.scale > .6) { stats.scale = stats.scale > .8 ? .75 : .6; slow = 0; views.forEach(x => x.relayout()); } }
    else if (stats.fps >= 58 && stats.renderMs < 4) { slow = 0; if (++fast >= 4 && stats.scale < 1) { stats.scale = stats.scale < .7 ? .75 : 1; fast = 0; views.forEach(x => x.relayout()); } }
  }
}
const _box = new THREE.Box3();

export class HandsView {
  constructor(host) {
    this.host = host; this.visible = true; this.dirty = true;
    this.canvas = document.createElement('canvas');
    this.canvas.setAttribute('aria-hidden', 'true');
    this.canvas.style.cssText = 'display:block;width:100%;height:100%;pointer-events:none';
    host.appendChild(this.canvas); this.ctx = this.canvas.getContext('2d');
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 60); this.camera.position.set(0, 0, 20);
    this.right = new HandRig(1); this.left = new HandRig(-1);
    this.rigs = { right: this.right, left: this.left };
    this.scene.add(this.right.root, this.left.root);
    this.player = new SignPlayer(library, host);
    ensureRenderer(); views.add(this);
    if (!raf) { last = 0; raf = requestAnimationFrame(loop); }
    if ('IntersectionObserver' in window) { this.io = new IntersectionObserver(e => { this.visible = e[0].isIntersecting; if (this.visible) this.dirty = true; }); this.io.observe(host); }
  }
  // w,h en px CSS; cx,cy,r = centro y radio del orb en px (opcionales).
  relayout() { if (this._lay) this.layout.apply(this, this._lay); }
  layout(w, h, cx, cy, r) {
    this._lay = [w, h, cx, cy, r];
    w = Math.max(1, w | 0); h = Math.max(1, h | 0);
    if (!(r > 0)) { r = Math.min(w / 6, h / 5.6); cx = w / 2; cy = 1.8 * r + (h - 5.6 * r) / 2; }
    const dpr = Math.min(DPR_CAP, window.devicePixelRatio || 1) * stats.scale;
    this.w = w; this.h = h; this.r = r; this.pw = Math.round(w * dpr); this.ph = Math.round(h * dpr);
    this.canvas.width = this.pw; this.canvas.height = this.ph;
    const c = this.camera; c.left = -cx / r; c.right = (w - cx) / r; c.top = cy / r; c.bottom = -(h - cy) / r; c.updateProjectionMatrix();
    this.dirty = true;
  }
  // fps: límite opcional por vista (atributo fps). Devuelve true si la vista está animando.
  tick(dt, now) {
    if (!this.visible || !this.w) return false;
    this._dt = (this._dt || 0) + dt;
    if (this.fpsCap) {
      const iv = 1000 / this.fpsCap;
      if (now < (this._due || 0) - 1) return this.player.playing;        // aún no toca
      this._due = Math.max((this._due || 0) + iv, now);                    // plazo acumulado: media exacta = fpsCap
      if (this._due - now > iv) this._due = now + iv;
    }
    const moved = this.player.update(this._dt); this._dt = 0;
    if (!moved && !this.dirty) return false;
    this.dirty = false; this._lastR = now;
    drawn = true; const t0 = performance.now(); this.render(); stats.renderMs = stats.renderMs * .9 + (performance.now() - t0) * .1;
    return true;
  }
  _contain(rig) {
    const c = this.camera, m = 4 / this.r, p = rig.root.position, R = 2.1;
    if (p.x - R > c.left + m && p.x + R < c.right - m && p.y - R > c.bottom + m && p.y + R < c.top - m) return;   // lejos del borde: sin cálculo
    _box.setFromObject(rig.root);
    let dx = 0, dy = 0;
    if (_box.max.x - _box.min.x < c.right - c.left - 2 * m) { if (_box.min.x < c.left + m) dx = c.left + m - _box.min.x; else if (_box.max.x > c.right - m) dx = c.right - m - _box.max.x; }
    if (_box.max.y - _box.min.y < c.top - c.bottom - 2 * m) { if (_box.min.y < c.bottom + m) dy = c.bottom + m - _box.min.y; else if (_box.max.y > c.top - m) dy = c.top - m - _box.max.y; }
    if (dx || dy) { rig.root.position.x += dx; rig.root.position.y += dy; rig.root.updateMatrixWorld(true); }
  }
  render() {
    const S = this.player.state;
    this.right.apply(S.right); this.left.apply(S.left);
    this.scene.updateMatrixWorld(true);
    this._contain(this.right); this._contain(this.left);
    for (const c of S.contacts || []) solveContact(this.rigs, c);
    const R = ensureRenderer(), w = this.pw, h = this.ph;
    if (w > rW || h > rH) { rW = Math.max(rW, w); rH = Math.max(rH, h); R.setSize(rW, rH, false); }
    const om = outlineMaterial(); if (om) om.uniforms.t.value = Math.max(1.5, Math.min(2.6, this.r * .03)) / this.r;
    R.setViewport(0, 0, w, h); R.setScissor(0, 0, w, h); R.clear(); R.render(this.scene, this.camera);
    this.ctx.clearRect(0, 0, w, h);
    this.ctx.drawImage(R.domElement, 0, rH - h, w, h, 0, 0, w, h);
  }
  dispose() {
    views.delete(this); if (this.io) this.io.disconnect();
    this.right.dispose(); this.left.dispose(); this.canvas.remove();
    if (!views.size) {
      cancelAnimationFrame(raf); raf = 0;
      if (renderer) { renderer.dispose(); renderer.forceContextLoss(); renderer = null; }
      disposeShared();
    }
  }
}
