/*
 * AingelOrb canvas renderer.
 * Ported from the AINGEL UI package v1.1.1 (fuente/aingel-orb.js) so the orb looks and moves exactly
 * like the approved mock-up: Fibonacci dot sphere, gold band, navy face with blinking eyes, blue and
 * gold orbits, per-state presets, activation sequence and audio-reactive deformation.
 * The behaviour follows the Thinking Orbs integration brief (MIT, Copyright (c) 2026 Yogesh); see
 * THIRD_PARTY_NOTICES.md.
 *
 * Modifications for the React app:
 * - audio level comes from an injected source (microphone, assistant output) instead of a global
 * - no simulated voice envelope: without a source the orb stays at rest
 * - reduced motion can also be forced by the profile preference
 */
import type { LevelSource, OrbOptions, OrbState } from "./orb.types";

type RGB = [number, number, number];
const C: Record<"navy" | "blue" | "gold" | "white" | "sky", RGB> = {
  navy: [9, 46, 102],
  blue: [7, 86, 177],
  gold: [235, 169, 52],
  white: [255, 255, 255],
  sky: [120, 170, 235],
};
const GREY: RGB = [150, 162, 182];

type Params = {
  rot: number; scale: number; dot: number; blue: number; gold: number; eyes: number; wave: number;
  sweep: number; scan: number; dim: number; arcSpin: number; breath: number; pulse: number; arcA: number;
  squint: number; gazeX: number; gazeY: number; look: number; tall: number; laugh: number; asym: number;
  bounce: number; wobble: number;
};
const BASE: Params = {
  rot: 0.12, scale: 1, dot: 1, blue: 0, gold: 0.35, eyes: 0, wave: 0, sweep: 0, scan: 0, dim: 0, arcSpin: 0.04,
  breath: 1, pulse: 0, arcA: 1, squint: 0, gazeX: 0, gazeY: 0, look: 0, tall: 1, laugh: 0, asym: 0, bounce: 0, wobble: 0,
};
const KEYS = Object.keys(BASE) as (keyof Params)[];
const P = (o: Partial<Params>): Params => ({ ...BASE, ...o });
const PRESETS: Record<OrbState, Params> = {
  idle: P({ eyes: 1 }),
  listening: P({ tall: 1.12, gazeY: -0.15, rot: 0.2, scale: 1.02, dot: 1.05, blue: 0.85, gold: 0.25, arcSpin: 0.1, breath: 0.3 }),
  thinking: P({ squint: 0.62, gazeX: 0.55, gazeY: -0.7, rot: 0.5, scale: 0.95, dot: 0.95, blue: 0.4, gold: 0.7, wave: 0.035, sweep: 1, dim: 0.4, arcSpin: 0.7, breath: 0.2 }),
  searching: P({ look: 1, squint: 0.2, rot: 0.28, scale: 0.97, blue: 0.6, gold: 0.3, scan: 1, dim: 0.5, arcSpin: 0.35, breath: 0.2 }),
  speaking: P({ rot: 0.22, scale: 1.02, dot: 1.05, blue: 0.3, gold: 0.9, arcSpin: 0.1, breath: 0.3 }),
  happy: P({ laugh: 1, bounce: 1, rot: 0.18, gold: 0.75, arcSpin: 0.14, breath: 0.4 }),
  confused: P({ asym: 1, wobble: 1, rot: 0.05, gazeX: -0.35, gazeY: -0.35, blue: 0.1, arcSpin: -0.03, breath: 0.5 }),
  retrying: P({ squint: 0.5, gazeY: 0.6, rot: -0.16, scale: 0.9, dot: 0.9, blue: 0.1, gold: 0.1, dim: 0.3, arcSpin: -0.25, breath: 0, pulse: 1, arcA: 0.45 }),
};

type Point = { x: number; y: number; z: number; ph: number; lon: number; lat: number; gold: boolean };
type Dot = { x: number; y: number; r: number; c: string };

const mix = (a: RGB, b: RGB, k: number): RGB => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const rgba = (c: RGB, a: number) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a.toFixed(3)})`;
function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath(); ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

const systemReduce = typeof window !== "undefined" && window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)")
  : { matches: false };

export class OrbRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private o: OrbOptions;
  private pts: Point[] = [];
  private p = P({ eyes: 1 });
  private t = Math.random() * 10;
  private lvl = 0;
  private rotY = Math.random() * 6;
  private arcRot = 0;
  private last = 0;
  private wasCfg: boolean | null = null;
  private revealStart = -100;
  private faceK = 1;
  private mute = 0;
  private nextBlink = 1.5 + Math.random() * 2.5;
  private blinkStart = -10;
  private visible = true;
  private running = false;
  private raf = 0;
  private io: IntersectionObserver | null = null;
  private vk = 0;

  constructor(canvas: HTMLCanvasElement, options: OrbOptions) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d")!;
    this.o = options;
    this.resize();
    this.build();
  }

  update(next: OrbOptions) {
    const prev = this.o;
    this.o = next;
    if (next.size !== prev.size) { this.resize(); if (!next.density) this.build(); }
    if (next.density !== prev.density) this.build();
  }

  start() {
    if (this.running) return;
    this.running = true;
    if ("IntersectionObserver" in window) {
      this.io = new IntersectionObserver((e) => { this.visible = e[0].isIntersecting; });
      this.io.observe(this.canvas);
    }
    const loop = (now: number) => {
      if (!this.running) return;
      if (this.visible && !document.hidden) this.frame(now);
      else this.last = 0;
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.raf);
    this.io?.disconnect();
    this.io = null;
  }

  private resize() {
    const s = this.o.size, d = Math.min(2, window.devicePixelRatio || 1);
    this.canvas.width = s * d; this.canvas.height = s * d;
    this.canvas.style.width = s + "px"; this.canvas.style.height = s + "px";
    this.ctx.setTransform(d, 0, 0, d, 0, 0);
  }

  private build() {
    const n = this.o.density || Math.round(Math.max(140, Math.min(520, this.o.size * 1.5)));
    const ga = Math.PI * (3 - Math.sqrt(5)), pts: Point[] = [];
    let nx = 0.34, ny = 0.88, nz = 0.33;
    const nl = Math.hypot(nx, ny, nz); nx /= nl; ny /= nl; nz /= nl;
    for (let i = 0; i < n; i++) {
      const y = 1 - ((i + 0.5) / n) * 2, r = Math.sqrt(1 - y * y), th = ga * i;
      const x = Math.cos(th) * r, z = Math.sin(th) * r;
      pts.push({ x, y, z, ph: Math.random() * 6.283, lon: Math.atan2(z, x), lat: y, gold: Math.abs(x * nx + y * ny + z * nz) < 0.085 });
    }
    this.pts = pts;
  }

  private readLevel(): number {
    const { state, audioLevel } = this.o;
    if (state !== "listening" && state !== "speaking") return 0;
    const v = typeof audioLevel === "function" ? (audioLevel as LevelSource)() : audioLevel ?? 0;
    return Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0;
  }

  private frame(now: number) {
    const o = this.o;
    const dt = this.last ? Math.min(0.05, (now - this.last) / 1000) : 0.016; this.last = now;
    const rm = o.reducedMotion || systemReduce.matches, sp = rm ? 0.25 : 1;
    this.t += dt * sp;
    const t = this.t, p = this.p, target = PRESETS[o.state] || PRESETS.idle, k = 1 - Math.exp(-dt / 0.3);
    for (const key of KEYS) p[key] += (target[key] - p[key]) * k;
    const raw = this.readLevel();
    this.lvl += (raw - this.lvl) * (raw > this.lvl ? 0.35 : 0.1);
    const L = rm ? this.lvl * 0.2 : this.lvl;

    if (this.wasCfg === null) { this.wasCfg = o.configured; this.faceK = o.configured ? 1 : 0; this.mute = o.configured ? 0 : 1; }
    if (o.configured && !this.wasCfg) this.revealStart = t;
    this.wasCfg = o.configured;
    const rs = t - this.revealStart, revealing = o.configured && rs >= 0 && rs < 2.4;
    const boost = revealing && !rm ? 11 * Math.pow(1 - rs / 2.4, 2) : 0;
    const kf = 1 - Math.exp(-dt / 0.25);
    let eyesK: number;
    if (!o.configured) { this.faceK += (0 - this.faceK) * kf; this.mute += (1 - this.mute) * (1 - Math.exp(-dt / 0.5)); eyesK = 0; }
    else if (revealing) {
      const fxr = (rs - 1.0) / 0.55;
      this.faceK = fxr <= 0 ? 0 : fxr >= 1 ? 1 : 1 + 2.70158 * Math.pow(fxr - 1, 3) + 1.70158 * Math.pow(fxr - 1, 2);
      this.mute = Math.max(0, 1 - rs / 1.3); eyesK = Math.max(0, Math.min(1, (rs - 1.45) / 0.3));
    } else { this.faceK += (1 - this.faceK) * kf; this.mute += (0 - this.mute) * kf; eyesK = Math.max(0, Math.min(1, (this.faceK - 0.75) / 0.25)); }
    const mute = this.mute;
    this.rotY += (p.rot * (1 + L * 0.25) + boost) * dt * sp;
    this.arcRot += (p.arcSpin + boost * 1.25) * dt * sp;

    // 3a vision: eased 0..1 over 350 ms; the orb grows and the eyes open into transparent windows.
    this.vk += ((o.vision && o.face ? 1 : 0) - this.vk) * (1 - Math.exp(-dt / (rm ? 0.2 : 0.35)));
    const vk = this.vk, box = o.size;
    // The canvas is the orb's own box, so the sphere keeps its size; the face and eyes grow instead.
    const S = box, ctx = this.ctx, cx = box / 2, cy = box / 2, dark = o.tone === "dark";
    ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
    ctx.clearRect(0, 0, box, box);
    if (o.background) { ctx.fillStyle = o.background; ctx.fillRect(0, 0, box, box); }
    const hop = Math.abs(Math.sin(t * 9)) * p.bounce;
    const breath = 1 + Math.sin(t * 1.3) * 0.016 * p.breath;
    const pulse = 1 + Math.sin(t * 2.4) * 0.035 * p.pulse;
    const R = S * (o.arcs ? 0.29 : 0.38) * p.scale * breath * pulse * (1 + L * 0.1) * (1 + hop * 0.018);
    const tilt = 0.36 + Math.sin(t * 0.4) * 0.05 + p.wobble * Math.sin(t * 1.1) * 0.14;
    const cY = Math.cos(this.rotY), sY = Math.sin(this.rotY), cX = Math.cos(tilt), sX = Math.sin(tilt);
    const sweepPos = Math.sin(t * 1.7) * 0.9, scanAng = (t * 2.2) % 6.2832;
    const baseC = dark ? C.white : C.navy, hiC = dark ? C.gold : C.blue, blueC = dark ? C.sky : C.blue;
    const back: Dot[] = [], front: Dot[] = [], dotBase = S * (o.arcs ? 0.0058 : 0.0072);
    for (const pt of this.pts) {
      const x1 = pt.x * cY - pt.z * sY, z1 = pt.x * sY + pt.z * cY, y1 = pt.y;
      const y2 = y1 * cX - z1 * sX, z2 = y1 * sX + z1 * cX;
      const rad = 1 + L * 0.15 * (0.55 + 0.45 * Math.sin(pt.lon * 3 + t * 5 + pt.ph * 0.3)) + p.wave * Math.sin(pt.lat * 8 - t * 4);
      let hi = 0;
      if (p.sweep > 0.01) { const d = pt.lat - sweepPos; hi = Math.max(hi, p.sweep * Math.exp((-d * d) / 0.02)); }
      if (p.scan > 0.01) {
        let ang = Math.atan2(-y2, x1); if (ang < 0) ang += 6.2832;
        let da = Math.abs(ang - scanAng); if (da > 3.1416) da = 6.2832 - da;
        hi = Math.max(hi, p.scan * Math.exp((-da * da) / 0.12) * (z2 > -0.2 ? 1 : 0.3));
      }
      const depth = (z2 + 1) / 2;
      const alpha = (0.12 + 0.88 * Math.pow(depth, 1.4)) * (1 - p.dim * (1 - hi));
      const rr = dotBase * (0.5 + 0.6 * depth) * p.dot * (1 + L * 0.2) * (1 + hi * 0.7);
      let col = mix(baseC, blueC, p.blue * (0.35 + 0.65 * depth));
      if (pt.gold) col = mix(col, C.gold, p.gold * (1 - mute));
      if (mute > 0.01) col = mix(col, GREY, mute * 0.75);
      if (hi > 0.02) col = mix(col, p.sweep > p.scan ? C.gold : hiC, hi * 0.8);
      (z2 < 0 ? back : front).push({ x: cx + x1 * R * rad, y: cy - y2 * R * rad, r: rr, c: rgba(col, Math.min(1, alpha)) });
    }
    for (const arr of [back, front]) for (const d of arr) { ctx.fillStyle = d.c; ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, 6.2832); ctx.fill(); }

    if (o.face) {
      if (t >= this.nextBlink) { this.blinkStart = t; this.nextBlink = t + (Math.random() < 0.2 ? 0.34 : 2.6 + Math.random() * 3.4); }
      const bp = (t - this.blinkStart) / 0.19, bf = bp >= 0 && bp < 1 ? 1 - Math.sin(bp * Math.PI) * 0.92 : 1;
      const fr0 = R * 0.57 * (1 + L * 0.05) * (1 + (rm ? 0 : 0.4) * vk), fr = fr0 * this.faceK, fx = cx + Math.sin(this.rotY * 0.5) * S * 0.003, fy = cy;
      if (revealing && !rm && rs > 1.0 && rs < 1.9) {
        const rq = (rs - 1.0) / 0.9;
        ctx.strokeStyle = rgba(C.gold, (1 - rq) * 0.55); ctx.lineWidth = S * 0.007;
        ctx.beginPath(); ctx.arc(fx, fy, fr0 * (1 + rq * 0.95), 0, 6.2832); ctx.stroke();
      }
      if (fr > 0.5) { ctx.fillStyle = rgba(dark ? C.white : C.navy, 1); ctx.beginPath(); ctx.arc(fx, fy, fr, 0, 6.2832); ctx.fill(); }
      if (o.eyes && eyesK > 0.01 && fr > 0.5) {
        const fg = fr * 0.225 * (1 + 0.2 * vk), fw = fr * 0.13 * (1 + 0.35 * p.laugh) * (1 + 1.4 * vk);
        const gx = (p.gazeX + Math.sin(t * 0.7) * 0.12 * p.squint) * fr * 0.11 + p.look * Math.sin(t * 1.5) * fr * 0.16 + p.wobble * Math.sin(t * 0.8) * fr * 0.07;
        const gy = p.gazeY * fr * 0.11 + L * Math.sin(t * 9) * fr * 0.01 - hop * fr * 0.035;
        const faceC = rgba(dark ? C.white : C.navy, 1);
        for (let fe = -1; fe <= 1; fe += 2) {
          const sq = Math.min(1, p.squint + (fe < 0 ? p.asym * 0.66 : 0));
          const tl = p.tall + (fe > 0 ? p.asym * 0.14 : 0);
          const bfe = p.asym > 0.5 && fe < 0 ? Math.min(bf, 1) : bf;
          const fh = fr * 0.3 * tl * (1 - 0.7 * sq * (1 - vk)) * bfe * eyesK * (1 + L * 0.08) * (1 + 0.6 * vk);
          const ex2 = fx + fe * fg + gx - fw / 2;
          const ecy = fy + gy + (fe < 0 ? p.asym * fr * 0.035 : -p.asym * fr * 0.02);
          const top = ecy - fh / 2 - p.laugh * fr * 0.03, hl = fh * (1 - 0.2 * p.laugh);
          if (vk > 0.01) {
            ctx.globalCompositeOperation = "destination-out"; ctx.globalAlpha = vk;
            roundRect(ctx, ex2, top, fw, hl, fw / 2); ctx.fill();
            ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
          }
          ctx.fillStyle = dark ? rgba(C.navy, 1 - vk) : rgba(C.white, 1 - vk); roundRect(ctx, ex2, top, fw, hl, fw / 2); ctx.fill();
          if (vk > 0.01) { ctx.strokeStyle = rgba(C.white, 0.9 * vk); ctx.lineWidth = Math.max(1.5, S * 0.006); roundRect(ctx, ex2, top, fw, hl, fw / 2); ctx.stroke(); }
          if (p.laugh > 0.02) {
            const ry = hl * 0.5, cyc2 = top + hl + ry * (1 - p.laugh * 1.25);
            ctx.fillStyle = faceC; ctx.beginPath(); ctx.ellipse(ex2 + fw / 2, cyc2, fw * 0.62, ry, 0, 0, 6.2832); ctx.fill();
          }
        }
      }
    }
    if (o.arcs) {
      const aR = S * 0.44 * (1 + L * 0.035), g = 0.07, rot = this.arcRot + Math.sin(t * 0.5) * 0.04;
      ctx.lineCap = "round"; ctx.lineWidth = S * 0.0115;
      const arcs: [RGB, number, number, number][] = [
        [dark ? C.sky : C.blue, Math.PI / 2 + g, Math.PI * 1.5 - g, Math.PI * 1.2],
        [C.gold, -Math.PI / 2 + g, Math.PI / 2 - g, Math.PI * 0.21],
      ];
      for (const [color, a0, a1, node] of arcs) {
        const acol = mute > 0.01 ? mix(color, GREY, mute * 0.8) : color, aal = p.arcA * (1 - 0.5 * mute);
        ctx.strokeStyle = rgba(acol, aal);
        ctx.beginPath(); ctx.arc(cx, cy, aR, a0 + rot, a1 + rot); ctx.stroke();
        ctx.fillStyle = rgba(acol, aal);
        ctx.beginPath(); ctx.arc(cx + Math.cos(node + rot) * aR, cy + Math.sin(node + rot) * aR, S * 0.022, 0, 6.2832); ctx.fill();
      }
    }
  }
}
