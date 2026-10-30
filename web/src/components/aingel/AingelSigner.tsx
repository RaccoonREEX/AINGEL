/*
 * AINGEL's floating hands: React port of <aingel-signer> (AINGEL_Manos_y_Senas v1.0.0, catalogue v1.5.0).
 * Articulated rig (palm + 5 fingers, 3 phalanges, opposable thumb): one-hand manual alphabet, numbers,
 * words, actions and phrases. Same hand shapes, keyframes, easing and drawing as the catalogue.
 * AINGEL DESIGN, PENDING LSEC VALIDATION by Deaf signers before use with users.
 */
import { useEffect, useRef } from "react";
import type { SignId } from "./signLexicon";
import { HANDS_SPEED, RA, RB, S, handGeo, hasSign, hsVec, type KF, type P3, type Pose } from "./signData";

export { hasSign };

// ---------- Sampling ----------
const PK = ["x", "y", "s", "yaw", "pitch", "roll", "a"] as const;
type Sample = Record<(typeof PK)[number], number> & { h: number[] };
const prep = (track: KF[] | undefined, rest: Pose): [number, Pose][] => {
  if (!track) return [[0, rest], [1, rest]];
  const cur: Pose = { ...rest, a: 1 };
  return track.map(([k, o]) => { Object.assign(cur, o); return [k, { ...cur }]; });
};
const cache: Record<SignId, { d: number; A: [number, Pose][]; B: [number, Pose][] }> = {};
const sign = (id: SignId) => cache[id] ?? (cache[id] = { d: S[id].d, A: prep(S[id].A, RA), B: prep(S[id].B, RB) });
const ease = (k: number) => (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);
function sample(tr: [number, Pose][], u: number): Sample {
  for (let i = 0; i < tr.length - 1; i++) {
    if (u <= tr[i + 1][0]) {
      const a = tr[i][1], b = tr[i + 1][1], k = ease(Math.max(0, Math.min(1, (u - tr[i][0]) / Math.max(1e-4, tr[i + 1][0] - tr[i][0]))));
      const o = {} as Sample;
      PK.forEach((p) => { o[p] = a[p] + (b[p] - a[p]) * k; });
      const va = hsVec(a.hs), vb = hsVec(b.hs);
      o.h = va.map((x, j) => x + (vb[j] - x) * k);
      return o;
    }
  }
  const l = tr[tr.length - 1][1], r = {} as Sample;
  PK.forEach((p) => { r[p] = l[p]; });
  r.h = hsVec(l.hs);
  return r;
}

// ---------- 3D hand geometry ----------
// ---------- 3D hand geometry ----------
const PALM = [[-0.34, 0.52], [0.3, 0.52], [0.46, 0.12], [0.43, -0.4], [0.12, -0.5], [-0.12, -0.48], [-0.37, -0.4], [-0.42, 0.1]];
function rot(p: P3, yaw: number, pitch: number, roll: number): P3 {
  let x = p[0], y = p[1], z = p[2], c, s, t;
  c = Math.cos(yaw); s = Math.sin(yaw); t = x * c + z * s; z = -x * s + z * c; x = t;
  c = Math.cos(pitch); s = Math.sin(pitch); t = y * c - z * s; z = y * s + z * c; y = t;
  c = Math.cos(roll); s = Math.sin(roll); t = x * c - y * s; y = x * s + y * c; x = t;
  return [x, y, z];
}
const lerp3 = (A: P3, B: P3, k: number): P3 => [A[0] + (B[0] - A[0]) * k, A[1] + (B[1] - A[1]) * k, A[2] + (B[2] - A[2]) * k];
function hull(pts: P3[]): P3[] {
  const P2 = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cr = (o: P3, a: P3, b: P3) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo: P3[] = [], up: P3[] = [];
  for (let i = 0; i < P2.length; i++) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], P2[i]) <= 0) lo.pop(); lo.push(P2[i]); }
  for (let i = P2.length - 1; i >= 0; i--) { while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], P2[i]) <= 0) up.pop(); up.push(P2[i]); }
  up.pop(); lo.pop();
  return lo.concat(up);
}

/** Seconds a sequence takes (each sign plus its 0.32 s transition), at speed 1. */
export const sequenceSeconds = (seq: SignId[]) => seq.reduce((t, id) => t + (S[id] ? S[id].d + 0.32 : 0), 0);

type Props = {
  width: number; height: number;
  /** Centre and radius of the orb (the signer's "head"), in px. */
  cx: number; cy: number; r: number;
  seq: SignId[];
  /** Changing it restarts the sequence. */
  playKey: number;
  speed?: number;
  loop?: boolean;
  reducedMotion?: boolean;
  /** Index of the sign that starts, or -1 when the sequence ends. */
  onSign?: (index: number) => void;
};

export default function AingelSigner({ width, height, cx, cy, r, seq, playKey, speed = HANDS_SPEED, loop = false, reducedMotion = false, onSign }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const props = useRef({ cx, cy, r, seq, speed, loop, reducedMotion, onSign });
  props.current = { cx, cy, r, seq: seq.filter(hasSign), speed, loop, reducedMotion, onSign };
  const restart = useRef(true);
  useEffect(() => { restart.current = true; }, [playKey]);
  useEffect(() => {
    const el = canvas.current!;
    const d = Math.min(2, window.devicePixelRatio || 1), W = width, Hh = height;
    el.width = W * d; el.height = Hh * d;
    const off = document.createElement("canvas"), off2 = document.createElement("canvas");
    off.width = off2.width = W * d; off.height = off2.height = Hh * d;
    const ctx = el.getContext("2d")!, o = off.getContext("2d")!, m = off2.getContext("2d")!;
    const systemReduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    let t = 0, last = 0, raf = 0, idx = -2, visible = true;
    let cur: { A: Sample; B: Sample } | null = null;
    const io = "IntersectionObserver" in window ? new IntersectionObserver((e) => { visible = e[0].isIntersecting; }) : null;
    io?.observe(el);

    const rest = () => ({ A: sample(prep(undefined, RA), 0), B: sample(prep(undefined, RB), 0), i: -1 });
    const target = () => {
      const p = props.current, sq = p.seq;
      if (!sq.length) return rest();
      const durs = sq.map((id) => sign(id).d);
      let total = 0;
      for (const du of durs) total += du + 0.32;
      const cycle = total + 1.2;
      let tt = t;
      if (p.loop) tt = tt % cycle; else if (tt > cycle) tt = cycle;
      let acc = 0;
      for (let i = 0; i < sq.length; i++) {
        const len = durs[i] + 0.32;
        if (tt < acc + len) { const sg = sign(sq[i]), u = Math.max(0, (tt - acc - 0.16) / durs[i]); return { A: sample(sg.A, Math.min(1, u)), B: sample(sg.B, Math.min(1, u)), i }; }
        acc += len;
      }
      return rest();
    };

    const drawHand = (p: Sample, side: number) => {
      if (p.a < 0.02) return;
      const R = props.current.r, PS = R * 0.82 * p.s, ox = props.current.cx + p.x * R, oy = props.current.cy + p.y * R, g = handGeo(p.h);
      if (!(PS > 1)) return;
      const tf = (q: P3): P3 => { const rr = rot(q, p.yaw, p.pitch, p.roll), k = 1 / (1 - rr[2] * 0.1); return [ox + side * rr[0] * PS * k, oy + rr[1] * PS * k, rr[2]]; };
      const nrm = rot([0, 0, 1], p.yaw, p.pitch, p.roll), back = nrm[2] < -0.15;
      const palm3: P3[] = [];
      PALM.forEach((q) => { palm3.push(tf([q[0], q[1], 0.02])); palm3.push(tf([q[0] * 0.94, q[1] * 0.96, -0.24])); });
      const palm = hull(palm3), cuff3: P3[] = [];
      [[-0.39, 0.44], [0.35, 0.44], [0.37, 0.68], [-0.41, 0.68]].forEach((q) => { cuff3.push(tf([q[0], q[1], 0.1])); cuff3.push(tf([q[0], q[1], -0.28])); });
      const cuff = hull(cuff3);
      const palmZ = (rot([0, 0, 0.02], p.yaw, p.pitch, p.roll)[2] + rot([0, 0, -0.24], p.yaw, p.pitch, p.roll)[2]) / 2;
      const fingers = g.map((f, i) => {
        const pts = f.pts.map(tf), curl = f.thumb ? 0 : (p.h[5 + i * 2] + p.h[6 + i * 2]) / 2;
        return { i, thumb: !!f.thumb, w: f.w * PS * (f.thumb ? 1.28 : 1.16), pts, curl, z: (pts[2][2] + pts[3][2]) / 2, over: false };
      });
      const thumb = fingers[4];
      const web = [tf([0.42, 0.28, -0.05]), thumb.pts[0], thumb.pts[1], tf([0.36, -0.32, -0.05])];
      [o, m].forEach((c) => { c.setTransform(d, 0, 0, d, 0, 0); c.clearRect(0, 0, W, Hh); c.lineCap = "round"; c.lineJoin = "round"; });
      const ol = Math.max(1.8, PS * 0.062), il = Math.max(1.3, PS * 0.042), INK = "#092E66", pw = PS * 0.2;
      const poly = (c: CanvasRenderingContext2D, pts: P3[]) => { c.beginPath(); pts.forEach((q, i) => (i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]))); c.closePath(); };
      const path = (c: CanvasRenderingContext2D, pts: P3[]) => { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); };
      const inside = (pt: P3, pl: P3[]) => { let c = false; for (let i = 0, j = pl.length - 1; i < pl.length; j = i++) { const a1 = pl[i], b1 = pl[j]; if ((a1[1] > pt[1]) !== (b1[1] > pt[1]) && pt[0] < ((b1[0] - a1[0]) * (pt[1] - a1[1])) / (b1[1] - a1[1]) + a1[0]) c = !c; } return c; };
      const dist = (A: P3, B: P3) => Math.hypot(A[0] - B[0], A[1] - B[1]);
      const segDist = (pt: P3, pts: P3[]) => { let best = 1e9; for (let i = 0; i < pts.length - 1; i++) { const A = pts[i], B = pts[i + 1], vx = B[0] - A[0], vy = B[1] - A[1], L2 = vx * vx + vy * vy || 1, tt = Math.max(0, Math.min(1, ((pt[0] - A[0]) * vx + (pt[1] - A[1]) * vy) / L2)); best = Math.min(best, Math.hypot(pt[0] - A[0] - vx * tt, pt[1] - A[1] - vy * tt)); } return best; };
      // A finger gets its own outline when it passes IN FRONT of the palm or another finger.
      fingers.forEach((f) => {
        const probe = f.thumb ? [f.pts[2], f.pts[3]] : [f.pts[2], f.pts[3], lerp3(f.pts[1], f.pts[2], 0.5)];
        f.over = probe.some((q) => inside(q, palm) && q[2] > palmZ + 0.04);
        fingers.forEach((g2) => {
          if (g2 === f || f.over) return;
          if (f.z <= g2.z + 0.06) return;
          if (probe.some((q) => segDist(q, g2.pts) < (f.w + g2.w) * 0.42)) f.over = true;
        });
      });
      const base = fingers.filter((f) => !f.over), over = fingers.filter((f) => f.over).sort((x, y) => x.z - y.z);
      const shape = (c: CanvasRenderingContext2D, col: string, extra: number, dx: number, dy: number, list = fingers) => {
        c.save(); c.translate(dx, dy); c.strokeStyle = c.fillStyle = col;
        c.lineWidth = pw + extra; poly(c, palm); c.fill(); c.stroke(); poly(c, cuff); c.fill(); c.stroke();
        c.lineWidth = thumb.w * 0.85 + extra; poly(c, web); c.fill(); c.stroke();
        list.forEach((f) => { c.lineWidth = f.w + extra; path(c, f.pts); c.stroke(); });
        c.restore();
      };
      // 1 · single silhouette
      shape(o, INK, ol * 2, 0, 0, base); shape(o, "#FFFFFF", 0, 0, 0, base);
      // 2 · grooves between touching fingers
      const nonThumb = base.filter((f) => !f.thumb).sort((x, y) => x.i - y.i);
      o.strokeStyle = INK; o.lineWidth = il;
      for (let n = 0; n < nonThumb.length - 1; n++) {
        const f1 = nonThumb[n], f2 = nonThumb[n + 1];
        if (f2.i !== f1.i + 1) continue;
        const e1 = f1.curl > 0.55 ? f1.pts[1] : f1.pts[3], e2 = f2.curl > 0.55 ? f2.pts[1] : f2.pts[3];
        const s1 = lerp3(f1.pts[0], f1.pts[1], 0.4), s2 = lerp3(f2.pts[0], f2.pts[1], 0.4);
        if (dist(e1, e2) > (f1.w + f2.w) * 0.62) continue;
        const ms = lerp3(s1, s2, 0.5), me = lerp3(e1, e2, 0.5), mm = lerp3(ms, me, 0.82);
        if (dist(ms, mm) < f1.w * 0.35) continue;
        path(o, [ms, mm]); o.stroke();
      }
      // 3 · fingers in front, back to front
      over.forEach((f) => {
        const seg = f.thumb ? [lerp3(f.pts[1], f.pts[2], 0.1), f.pts[2], f.pts[3]] : [lerp3(f.pts[0], f.pts[1], 0.35), f.pts[1], f.pts[2], f.pts[3]];
        o.strokeStyle = INK; o.lineWidth = f.w + il * 2; path(o, seg); o.stroke();
        o.strokeStyle = "#FFFFFF"; o.lineWidth = f.w; path(o, seg); o.stroke();
        if (f.thumb) { o.lineWidth = f.w * 1.05; path(o, [f.pts[0], f.pts[1], seg[0]]); o.stroke(); }
      });
      // 4 · volume: inner shade on the edge away from the light
      const k = Math.max(2, PS * 0.1);
      shape(m, "#C3D4EC", 0, 0, 0); m.globalCompositeOperation = "destination-out"; shape(m, "#000", 0, -k, -k * 1.1); m.globalCompositeOperation = "source-over";
      o.save(); o.setTransform(1, 0, 0, 1, 0, 0); o.globalCompositeOperation = "source-atop"; o.globalAlpha = 0.9; o.drawImage(off2, 0, 0); o.restore();
      // 5 · golden cuff and back seams
      o.strokeStyle = "#EBA934"; o.lineWidth = Math.max(1.8, PS * 0.08); path(o, [tf([-0.4, 0.57, 0.1]), tf([0.36, 0.57, 0.1])]); o.stroke();
      o.strokeStyle = INK; o.lineWidth = il * 0.8; path(o, [tf([-0.39, 0.45, 0.1]), tf([0.35, 0.45, 0.1])]); o.stroke();
      if (back && Math.abs(nrm[2]) > 0.45) {
        o.strokeStyle = "rgba(9,46,102,.5)"; o.lineWidth = il * 0.8;
        [[0.2, 0.22, 0.22, -0.18], [0, 0.24, 0, -0.22], [-0.2, 0.22, -0.22, -0.16]].forEach((l) => { path(o, [tf([l[0], l[1], -0.24]), tf([l[2], l[3], -0.24])]); o.stroke(); });
      }
      ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
      const al = Math.min(1, p.a);
      ctx.globalAlpha = 0.22 * al; ctx.filter = `blur(${Math.round(6 * d * p.s)}px)`;
      ctx.drawImage(off, 5 * d * p.s, 13 * d * p.s);
      ctx.filter = "none"; ctx.globalAlpha = al; ctx.drawImage(off, 0, 0); ctx.restore();
    };

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (!visible || document.hidden) { last = 0; return; }
      const p = props.current;
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 0.016; last = now;
      if (restart.current) { restart.current = false; t = 0; idx = -2; }
      t += dt * p.speed * (p.reducedMotion || systemReduce.matches ? 0.6 : 1);
      const tg = target();
      if (tg.i !== idx) { const was = idx; idx = tg.i; if (tg.i >= 0 || was >= 0) p.onSign?.(tg.i); }
      const k = 1 - Math.exp(-dt / 0.085);
      if (!cur) cur = { A: { ...tg.A, h: [...tg.A.h] }, B: { ...tg.B, h: [...tg.B.h] } };
      (["A", "B"] as const).forEach((hk) => {
        const c = cur![hk], g = tg[hk];
        PK.forEach((q) => { c[q] += (g[q] - c[q]) * k; });
        c.h = c.h.map((x, j) => x + (g.h[j] - x) * k);
      });
      ctx.setTransform(d, 0, 0, d, 0, 0); ctx.clearRect(0, 0, W, Hh);
      const hA = cur.A, hB = cur.B;
      if (hA.s * Math.min(1, hA.a) >= hB.s * Math.min(1, hB.a)) { drawHand(hB, -1); drawHand(hA, 1); } else { drawHand(hA, 1); drawHand(hB, -1); }
    };
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); io?.disconnect(); };
  }, [width, height]);
  return <canvas ref={canvas} className="aingel-hands" style={{ width, height }} aria-hidden="true" />;
}
