/*
 * AingelOrb for Android: Compose Canvas port of the AINGEL UI package v1.1.1 orb
 * (orb/aingel-orb.referencia.js), kept numerically identical to web/src/components/aingel/orb-core.ts:
 * Fibonacci dot sphere, gold band, navy face with blinking eyes, blue and gold orbits, per-state
 * presets, activation sequence and audio-reactive deformation. Behaviour follows the Thinking Orbs
 * integration brief (MIT, Copyright (c) 2026 Yogesh); see THIRD_PARTY_NOTICES.md.
 */
package ec.aingel.mobile

import android.provider.Settings
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.Dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import kotlin.math.*
import kotlin.random.Random

enum class AingelOrbState { IDLE, LISTENING, THINKING, SEARCHING, SPEAKING, HAPPY, CONFUSED, RETRYING }

/** UI tests switch the frame loop off: an endless animation would keep Compose from ever being idle. */
internal object OrbAnimation { @Volatile var enabled = true }

private class OrbParams(
    var rot: Float = 0.12f, var scale: Float = 1f, var dot: Float = 1f, var blue: Float = 0f, var gold: Float = 0.35f,
    var wave: Float = 0f, var sweep: Float = 0f, var scan: Float = 0f, var dim: Float = 0f, var arcSpin: Float = 0.04f,
    var breath: Float = 1f, var pulse: Float = 0f, var arcA: Float = 1f, var squint: Float = 0f, var gazeX: Float = 0f,
    var gazeY: Float = 0f, var look: Float = 0f, var tall: Float = 1f, var laugh: Float = 0f, var asym: Float = 0f,
    var bounce: Float = 0f, var wobble: Float = 0f,
) {
    fun values() = floatArrayOf(rot, scale, dot, blue, gold, wave, sweep, scan, dim, arcSpin, breath, pulse, arcA, squint, gazeX, gazeY, look, tall, laugh, asym, bounce, wobble)
    fun approach(t: OrbParams, k: Float) {
        val a = values(); val b = t.values()
        for (i in a.indices) a[i] += (b[i] - a[i]) * k
        rot = a[0]; scale = a[1]; dot = a[2]; blue = a[3]; gold = a[4]; wave = a[5]; sweep = a[6]; scan = a[7]; dim = a[8]
        arcSpin = a[9]; breath = a[10]; pulse = a[11]; arcA = a[12]; squint = a[13]; gazeX = a[14]; gazeY = a[15]; look = a[16]
        tall = a[17]; laugh = a[18]; asym = a[19]; bounce = a[20]; wobble = a[21]
    }
}

private val PRESETS = mapOf(
    AingelOrbState.IDLE to OrbParams(),
    AingelOrbState.LISTENING to OrbParams(tall = 1.12f, gazeY = -0.15f, rot = 0.2f, scale = 1.02f, dot = 1.05f, blue = 0.85f, gold = 0.25f, arcSpin = 0.1f, breath = 0.3f),
    AingelOrbState.THINKING to OrbParams(squint = 0.62f, gazeX = 0.55f, gazeY = -0.7f, rot = 0.5f, scale = 0.95f, dot = 0.95f, blue = 0.4f, gold = 0.7f, wave = 0.035f, sweep = 1f, dim = 0.4f, arcSpin = 0.7f, breath = 0.2f),
    AingelOrbState.SEARCHING to OrbParams(look = 1f, squint = 0.2f, rot = 0.28f, scale = 0.97f, blue = 0.6f, gold = 0.3f, scan = 1f, dim = 0.5f, arcSpin = 0.35f, breath = 0.2f),
    AingelOrbState.SPEAKING to OrbParams(rot = 0.22f, scale = 1.02f, dot = 1.05f, blue = 0.3f, gold = 0.9f, arcSpin = 0.1f, breath = 0.3f),
    AingelOrbState.HAPPY to OrbParams(laugh = 1f, bounce = 1f, rot = 0.18f, gold = 0.75f, arcSpin = 0.14f, breath = 0.4f),
    AingelOrbState.CONFUSED to OrbParams(asym = 1f, wobble = 1f, rot = 0.05f, gazeX = -0.35f, gazeY = -0.35f, blue = 0.1f, arcSpin = -0.03f, breath = 0.5f),
    AingelOrbState.RETRYING to OrbParams(squint = 0.5f, gazeY = 0.6f, rot = -0.16f, scale = 0.9f, dot = 0.9f, blue = 0.1f, gold = 0.1f, dim = 0.3f, arcSpin = -0.25f, breath = 0f, pulse = 1f, arcA = 0.45f),
)

private val NAVY = floatArrayOf(9f, 46f, 102f)
private val BLUE = floatArrayOf(7f, 86f, 177f)
private val GOLD = floatArrayOf(235f, 169f, 52f)
private val GREY = floatArrayOf(150f, 162f, 182f)
private val WHITE = floatArrayOf(255f, 255f, 255f)
private val SKY = floatArrayOf(120f, 170f, 235f)
private fun mix(a: FloatArray, b: FloatArray, k: Float) = floatArrayOf(a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k)
private fun color(c: FloatArray, a: Float = 1f) = Color(c[0] / 255f, c[1] / 255f, c[2] / 255f, a.coerceIn(0f, 1f))

private class Pt(val x: Float, val y: Float, val z: Float, val ph: Float, val lon: Float, val lat: Float, val gold: Boolean)

/** Mutable renderer state; advanced once per frame, never through Compose state. */
private class OrbEngine {
    var pts: List<Pt> = emptyList(); var builtFor = -1
    val p = OrbParams(); var t = Random.nextFloat() * 10f; var lvl = 0f; var rotY = Random.nextFloat() * 6f; var arcRot = 0f
    var wasCfg: Boolean? = null; var revealStart = -100f; var faceK = 1f; var mute = 0f
    var nextBlink = 1.5f + Random.nextFloat() * 2.5f; var blinkStart = -10f
    var vk = 0f

    fun build(n: Int) {
        val ga = (PI * (3 - sqrt(5.0))).toFloat()
        var nx = 0.34f; var ny = 0.88f; var nz = 0.33f
        val nl = sqrt(nx * nx + ny * ny + nz * nz); nx /= nl; ny /= nl; nz /= nl
        pts = (0 until n).map { i ->
            val y = 1 - (i + 0.5f) / n * 2; val r = sqrt(1 - y * y); val th = ga * i
            val x = cos(th) * r; val z = sin(th) * r
            Pt(x, y, z, Random.nextFloat() * 6.283f, atan2(z, x), y, abs(x * nx + y * ny + z * nz) < 0.085f)
        }
        builtFor = n
    }
}

/**
 * Decorative AINGEL orb. [audioLevel] is read every frame (0..1) while listening or speaking;
 * screens announce the state in text, so the canvas is hidden from accessibility services.
 */
@Composable
fun AingelOrb(
    state: AingelOrbState,
    size: Dp,
    modifier: Modifier = Modifier,
    configured: Boolean = true,
    reducedMotion: Boolean = false,
    /** 3a: the eyes become windows onto whatever is drawn behind the orb (the camera preview). */
    vision: Boolean = false,
    background: Color? = null,
    /** Tone for black backgrounds (cover screens, aingel-orb.js tone="dark"): white face, light dots, sky arc. */
    dark: Boolean = false,
    audioLevel: () -> Float = { 0f },
) {
    val engine = remember { OrbEngine() }
    val context = LocalContext.current
    val systemReduced = remember { Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f }
    val inputs by rememberUpdatedState(Triple(state, configured, reducedMotion || systemReduced))
    val look by rememberUpdatedState(vision to background)
    val tone by rememberUpdatedState(dark)
    val level by rememberUpdatedState(audioLevel)
    var frame by remember { mutableLongStateOf(0L) }
    var dt by remember { mutableFloatStateOf(0.016f) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(lifecycle) {
        if (!OrbAnimation.enabled) return@LaunchedEffect
        lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            var last = 0L
            while (true) withFrameNanos { now ->
                dt = if (last == 0L) 0.016f else min(0.05f, (now - last) / 1e9f)
                last = now; frame = now
            }
        }
    }
    // Offscreen compositing lets BlendMode.DstOut cut the eyes through to the view underneath.
    Canvas(modifier.size(size).graphicsLayer(compositingStrategy = CompositingStrategy.Offscreen).clearAndSetSemantics { }) {
        frame // read so every frame invalidates the draw
        val (st, cfg, rm) = inputs
        engine.step(this, dt, st, cfg, rm, if (st == AingelOrbState.LISTENING || st == AingelOrbState.SPEAKING) level().coerceIn(0f, 1f) else 0f, look.first, look.second, tone)
    }
}

private fun OrbEngine.step(scope: DrawScope, dt: Float, state: AingelOrbState, configured: Boolean, rm: Boolean, raw: Float,
                            vision: Boolean, background: Color?, dark: Boolean = false) = with(scope) {
    val base = if (dark) WHITE else NAVY; val blue = if (dark) SKY else BLUE; val face = if (dark) WHITE else NAVY; val eye = if (dark) NAVY else WHITE
    val S = this.size.minDimension
    val n = (S / density * 1.5f).roundToInt().coerceIn(140, 520)
    if (builtFor != n) build(n)
    val sp = if (rm) 0.25f else 1f
    t += dt * sp
    p.approach(PRESETS.getValue(state), 1 - exp(-dt / 0.3f))
    lvl += (raw - lvl) * (if (raw > lvl) 0.35f else 0.10f)
    val L = if (rm) lvl * 0.2f else lvl

    if (wasCfg == null) { wasCfg = configured; faceK = if (configured) 1f else 0f; mute = if (configured) 0f else 1f }
    if (configured && wasCfg == false) revealStart = t
    wasCfg = configured
    val rs = t - revealStart; val revealing = configured && rs >= 0 && rs < 2.4f
    val boost = if (revealing && !rm) 11 * (1 - rs / 2.4f).pow(2) else 0f
    val kf = 1 - exp(-dt / 0.25f)
    val eyesK: Float
    if (!configured) { faceK += (0 - faceK) * kf; mute += (1 - mute) * (1 - exp(-dt / 0.5f)); eyesK = 0f }
    else if (revealing) {
        val fxr = (rs - 1.0f) / 0.55f
        faceK = if (fxr <= 0) 0f else if (fxr >= 1) 1f else 1 + 2.70158f * (fxr - 1).pow(3) + 1.70158f * (fxr - 1).pow(2)
        mute = max(0f, 1 - rs / 1.3f); eyesK = ((rs - 1.45f) / 0.3f).coerceIn(0f, 1f)
    } else { faceK += (1 - faceK) * kf; mute += (0 - mute) * kf; eyesK = ((faceK - 0.75f) / 0.25f).coerceIn(0f, 1f) }
    rotY += (p.rot * (1 + L * 0.25f) + boost) * dt * sp
    arcRot += (p.arcSpin + boost * 1.25f) * dt * sp

    vk += ((if (vision) 1f else 0f) - vk) * (1 - exp(-dt / (if (rm) 0.2f else 0.35f)))
    background?.let { drawRect(it) }
    val cx = S / 2; val cy = S / 2
    val hop = abs(sin(t * 9)) * p.bounce
    val breath = 1 + sin(t * 1.3f) * 0.016f * p.breath
    val pulse = 1 + sin(t * 2.4f) * 0.035f * p.pulse
    val R = S * 0.29f * p.scale * breath * pulse * (1 + L * 0.10f) * (1 + hop * 0.018f)
    val tilt = 0.36f + sin(t * 0.4f) * 0.05f + p.wobble * sin(t * 1.1f) * 0.14f
    val cY = cos(rotY); val sY = sin(rotY); val cX = cos(tilt); val sX = sin(tilt)
    val sweepPos = sin(t * 1.7f) * 0.9f; val scanAng = (t * 2.2f) % 6.2832f
    val dotBase = S * 0.0058f
    // Back dots first, then front dots, as in the reference renderer.
    for (pass in 0..1) for (pt in pts) {
        val x1 = pt.x * cY - pt.z * sY; val z1 = pt.x * sY + pt.z * cY; val y1 = pt.y
        val y2 = y1 * cX - z1 * sX; val z2 = y1 * sX + z1 * cX
        if ((pass == 0) != (z2 < 0)) continue
        val rad = 1 + L * 0.15f * (0.55f + 0.45f * sin(pt.lon * 3 + t * 5 + pt.ph * 0.3f)) + p.wave * sin(pt.lat * 8 - t * 4)
        var hi = 0f
        if (p.sweep > 0.01f) { val d = pt.lat - sweepPos; hi = max(hi, p.sweep * exp(-d * d / 0.02f)) }
        if (p.scan > 0.01f) {
            var ang = atan2(-y2, x1); if (ang < 0) ang += 6.2832f
            var da = abs(ang - scanAng); if (da > 3.1416f) da = 6.2832f - da
            hi = max(hi, p.scan * exp(-da * da / 0.12f) * (if (z2 > -0.2f) 1f else 0.3f))
        }
        val depth = (z2 + 1) / 2
        val alpha = (0.12f + 0.88f * depth.pow(1.4f)) * (1 - p.dim * (1 - hi))
        val rr = dotBase * (0.5f + 0.6f * depth) * p.dot * (1 + L * 0.2f) * (1 + hi * 0.7f)
        var col = mix(base, blue, p.blue * (0.35f + 0.65f * depth))
        if (pt.gold) col = mix(col, GOLD, p.gold * (1 - mute))
        if (mute > 0.01f) col = mix(col, GREY, mute * 0.75f)
        if (hi > 0.02f) col = mix(col, if (p.sweep > p.scan || dark) GOLD else BLUE, hi * 0.8f)
        drawCircle(color(col, min(1f, alpha)), rr, Offset(cx + x1 * R * rad, cy - y2 * R * rad))
    }

    if (t >= nextBlink) { blinkStart = t; nextBlink = t + (if (Random.nextFloat() < 0.2f) 0.34f else 2.6f + Random.nextFloat() * 3.4f) }
    val bp = (t - blinkStart) / 0.19f
    val bf = if (bp >= 0 && bp < 1) 1 - sin(bp * PI.toFloat()) * 0.92f else 1f
    val fr0 = R * 0.57f * (1 + L * 0.05f) * (1 + (if (rm) 0f else 0.4f) * vk); val fr = fr0 * faceK
    val fx = cx + sin(rotY * 0.5f) * S * 0.003f; val fy = cy
    if (revealing && !rm && rs > 1.0f && rs < 1.9f) {
        val rq = (rs - 1.0f) / 0.9f
        drawCircle(color(GOLD, (1 - rq) * 0.55f), fr0 * (1 + rq * 0.95f), Offset(fx, fy), style = Stroke(S * 0.007f))
    }
    if (fr > 0.5f) drawCircle(color(face), fr, Offset(fx, fy))
    if (eyesK > 0.01f && fr > 0.5f) {
        val fg = fr * 0.225f * (1 + 0.2f * vk); val fw = fr * 0.13f * (1 + 0.35f * p.laugh) * (1 + 1.4f * vk)
        val gx = (p.gazeX + sin(t * 0.7f) * 0.12f * p.squint) * fr * 0.11f + p.look * sin(t * 1.5f) * fr * 0.16f + p.wobble * sin(t * 0.8f) * fr * 0.07f
        val gy = p.gazeY * fr * 0.11f + L * sin(t * 9) * fr * 0.01f - hop * fr * 0.035f
        for (fe in intArrayOf(-1, 1)) {
            val sq = min(1f, p.squint + (if (fe < 0) p.asym * 0.66f else 0f))
            val tl = p.tall + (if (fe > 0) p.asym * 0.14f else 0f)
            val fh = fr * 0.30f * tl * (1 - 0.7f * sq * (1 - vk)) * bf * eyesK * (1 + L * 0.08f) * (1 + 0.6f * vk)
            val ex = fx + fe * fg + gx - fw / 2
            val ecy = fy + gy + (if (fe < 0) p.asym * fr * 0.035f else -p.asym * fr * 0.02f)
            val top = ecy - fh / 2 - p.laugh * fr * 0.03f; val hl = fh * (1 - 0.2f * p.laugh)
            val radius = min(fw / 2, hl / 2)
            if (vk > 0.01f) drawRoundRect(Color.Black, Offset(ex, top), Size(fw, hl), CornerRadius(radius, radius), alpha = vk, blendMode = BlendMode.DstOut)
            drawRoundRect(color(eye, 1 - vk), Offset(ex, top), Size(fw, hl), CornerRadius(radius, radius))
            if (vk > 0.01f) drawRoundRect(Color.White.copy(alpha = 0.9f * vk), Offset(ex, top), Size(fw, hl), CornerRadius(radius, radius), style = Stroke(max(1.5f, S * 0.006f)))
            if (p.laugh > 0.02f) {
                val ry = hl * 0.5f; val cyc = top + hl + ry * (1 - p.laugh * 1.25f)
                drawOval(color(face), Offset(ex + fw / 2 - fw * 0.62f, cyc - ry), Size(fw * 1.24f, ry * 2))
            }
        }
    }
    val aR = S * 0.44f * (1 + L * 0.035f); val g = 0.07f; val rot = arcRot + sin(t * 0.5f) * 0.04f
    val arcs = listOf(Triple(blue, (PI / 2 + g).toFloat() to (PI * 1.5 - g).toFloat(), (PI * 1.2).toFloat()),
        Triple(GOLD, (-PI / 2 + g).toFloat() to (PI / 2 - g).toFloat(), (PI * 0.21).toFloat()))
    for ((base, range, node) in arcs) {
        val c = if (mute > 0.01f) mix(base, GREY, mute * 0.8f) else base
        val a = p.arcA * (1 - 0.5f * mute)
        val start = Math.toDegrees((range.first + rot).toDouble()).toFloat()
        val sweep = Math.toDegrees((range.second - range.first).toDouble()).toFloat()
        drawArc(color(c, a), start, sweep, false, Offset(cx - aR, cy - aR), Size(aR * 2, aR * 2), style = Stroke(S * 0.0115f, cap = StrokeCap.Round))
        drawCircle(color(c, a), S * 0.022f, Offset(cx + cos(node + rot) * aR, cy + sin(node + rot) * aR))
    }
}
