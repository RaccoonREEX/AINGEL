package ec.aingel.mobile

import android.content.Context
import android.graphics.SurfaceTexture
import android.opengl.EGL14
import android.opengl.EGLConfig
import android.opengl.EGLContext
import android.opengl.EGLDisplay
import android.opengl.EGLExt
import android.opengl.EGLSurface
import android.opengl.GLES30
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.view.Choreographer
import android.view.TextureView
import org.json.JSONArray
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.nio.ShortBuffer
import kotlin.math.*

/*
 * Native port of AINGEL's three.js hands (AINGEL_Manos_y_Senas v1.0.0, engine v0.1.1) for Android: same rig
 * (capsules and cylinders made in code), same three-tone glove shader and inverted-hull outline, same sign
 * player (0.28 s cross-fade, keyframe easing, return to rest). The poses and signs are the ones the web
 * converts from the 2D catalogue, exported to assets/hands3d/signs3d.json (npm run export:android-hands).
 * AINGEL design, pending LSEC validation.
 */

// ---------- Quaternions (three.js conventions) ----------
internal class Quat(var x: Float = 0f, var y: Float = 0f, var z: Float = 0f, var w: Float = 1f) {
    fun set(o: Quat) = apply { x = o.x; y = o.y; z = o.z; w = o.w }
    fun copy() = Quat(x, y, z, w)
}
internal fun qMul(a: Quat, b: Quat, out: Quat = Quat()): Quat {
    val x = a.x * b.w + a.w * b.x + a.y * b.z - a.z * b.y
    val y = a.y * b.w + a.w * b.y + a.z * b.x - a.x * b.z
    val z = a.z * b.w + a.w * b.z + a.x * b.y - a.y * b.x
    val w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z
    out.x = x; out.y = y; out.z = z; out.w = w; return out
}
/** Euler angles in degrees, as three.js Quaternion.setFromEuler with order "XYZ" or "ZXY". */
internal fun qEuler(deg: FloatArray, order: String, out: Quat = Quat()): Quat {
    val r = PI.toFloat() / 360f
    val c1 = cos(deg[0] * r); val c2 = cos(deg[1] * r); val c3 = cos(deg[2] * r)
    val s1 = sin(deg[0] * r); val s2 = sin(deg[1] * r); val s3 = sin(deg[2] * r)
    if (order == "XYZ") { out.x = s1 * c2 * c3 + c1 * s2 * s3; out.y = c1 * s2 * c3 - s1 * c2 * s3; out.z = c1 * c2 * s3 + s1 * s2 * c3; out.w = c1 * c2 * c3 - s1 * s2 * s3 }
    else { out.x = s1 * c2 * c3 - c1 * s2 * s3; out.y = c1 * s2 * c3 + s1 * c2 * s3; out.z = c1 * c2 * s3 + s1 * s2 * c3; out.w = c1 * c2 * c3 - s1 * s2 * s3 }
    return out
}
internal fun qMirror(q: Quat, out: Quat = Quat()) = out.apply { x = q.x; y = -q.y; z = -q.z; w = q.w }
/** three.js Quaternion.slerpQuaternions(a, b, t). */
internal fun qSlerp(a: Quat, b: Quat, t: Float, out: Quat): Quat {
    if (t <= 0f) return out.set(a)
    if (t >= 1f) return out.set(b)
    var cos = a.w * b.w + a.x * b.x + a.y * b.y + a.z * b.z
    var bx = b.x; var by = b.y; var bz = b.z; var bw = b.w
    if (cos < 0f) { bx = -bx; by = -by; bz = -bz; bw = -bw; cos = -cos }
    if (cos >= 1f) return out.set(a)
    val sqrSin = 1f - cos * cos
    if (sqrSin <= 1.1920929e-7f) {
        val s = 1f - t
        out.x = s * a.x + t * bx; out.y = s * a.y + t * by; out.z = s * a.z + t * bz; out.w = s * a.w + t * bw
        val l = sqrt(out.x * out.x + out.y * out.y + out.z * out.z + out.w * out.w)
        out.x /= l; out.y /= l; out.z /= l; out.w /= l; return out
    }
    val sinHalf = sqrt(sqrSin); val half = atan2(sinHalf, cos)
    val ra = sin((1 - t) * half) / sinHalf; val rb = sin(t * half) / sinHalf
    out.x = a.x * ra + bx * rb; out.y = a.y * ra + by * rb; out.z = a.z * ra + bz * rb; out.w = a.w * ra + bw * rb
    return out
}

// ---------- 4×4 matrices, column-major (GL) ----------
private fun mCompose(px: Float, py: Float, pz: Float, q: Quat, sx: Float, sy: Float, sz: Float, m: FloatArray = FloatArray(16)): FloatArray {
    val x2 = q.x + q.x; val y2 = q.y + q.y; val z2 = q.z + q.z
    val xx = q.x * x2; val xy = q.x * y2; val xz = q.x * z2; val yy = q.y * y2; val yz = q.y * z2; val zz = q.z * z2
    val wx = q.w * x2; val wy = q.w * y2; val wz = q.w * z2
    m[0] = (1 - (yy + zz)) * sx; m[1] = (xy + wz) * sx; m[2] = (xz - wy) * sx; m[3] = 0f
    m[4] = (xy - wz) * sy; m[5] = (1 - (xx + zz)) * sy; m[6] = (yz + wx) * sy; m[7] = 0f
    m[8] = (xz + wy) * sz; m[9] = (yz - wx) * sz; m[10] = (1 - (xx + yy)) * sz; m[11] = 0f
    m[12] = px; m[13] = py; m[14] = pz; m[15] = 1f
    return m
}
private fun mMul(a: FloatArray, b: FloatArray, out: FloatArray = FloatArray(16)): FloatArray {
    android.opengl.Matrix.multiplyMM(out, 0, a, 0, b, 0); return out
}
private val IDENTITY_Q = Quat()

// ---------- Data: rig dimensions, poses and signs from signs3d.json ----------
private val FINGERS = listOf("thumb", "index", "middle", "ring", "pinky")
private val JOINT_NAMES = mapOf("thumb" to listOf("metacarpal", "proximal", "distal")).withDefault { listOf("proximal", "intermediate", "distal") }
private const val JOINTS = 15

internal class Dim(val base: FloatArray, val len: FloatArray, val r: FloatArray, val rest: List<FloatArray>)
internal class HandSpec(val pose: String?, val position: FloatArray?, val rotation: FloatArray?, val scale: Float?)
internal class KeyFrame(val t: Float, val ease: String, val right: HandSpec, val left: HandSpec)
internal class HandsData(val handScale: Float, val dim: Map<String, Dim>, val rest: Pair<HandSpec, HandSpec>, val poses: Map<String, Array<Quat>>, val signs: Map<String, List<KeyFrame>>)

private fun JSONArray.floats() = FloatArray(length()) { getDouble(it).toFloat() }
private fun angle(v: Any?): FloatArray = when (v) { is JSONArray -> FloatArray(3) { if (it < v.length()) v.getDouble(it).toFloat() else 0f }; is Number -> floatArrayOf(v.toFloat(), 0f, 0f); else -> FloatArray(3) }
private fun spec(o: JSONObject) = HandSpec(o.optString("pose").ifEmpty { null }, o.optJSONArray("position")?.floats(), o.optJSONArray("rotation")?.floats(),
    if (o.has("scale")) o.getDouble("scale").toFloat() else null)

/** Finger angles → one quaternion per joint (order ZXY, as the web engine's applyFingers). */
private fun poseJoints(fingers: JSONObject): Array<Quat> {
    val out = Array(JOINTS) { Quat() }; var k = 0
    for (f in FINGERS) { val fo = fingers.optJSONObject(f); for (j in JOINT_NAMES.getValue(f)) { if (fo != null && fo.has(j)) qEuler(angle(fo.get(j)), "ZXY", out[k]); k++ } }
    return out
}

internal object HandsAssets {
    @Volatile private var cached: HandsData? = null
    fun load(context: Context): HandsData = cached ?: synchronized(this) {
        cached ?: parse(JSONObject(context.assets.open("hands3d/signs3d.json").bufferedReader().use { it.readText() })).also { cached = it }
    }
    private fun parse(j: JSONObject): HandsData {
        val dimJ = j.getJSONObject("dim")
        val dim = FINGERS.associateWith { f -> val d = dimJ.getJSONObject(f); val rest = d.getJSONArray("rest")
            Dim(d.getJSONArray("base").floats(), d.getJSONArray("len").floats(), d.getJSONArray("r").floats(), List(3) { angle(rest.get(it)) }) }
        val posesJ = j.getJSONObject("poses"); val poses = posesJ.keys().asSequence().associateWith { poseJoints(posesJ.getJSONObject(it)) }
        val signsJ = j.getJSONObject("signs")
        val signs = signsJ.keys().asSequence().associateWith { id -> val a = signsJ.getJSONArray(id)
            List(a.length()) { val k = a.getJSONObject(it); KeyFrame(k.getDouble("t").toFloat(), k.optString("ease", "easeInOutSine"), spec(k.getJSONObject("right")), spec(k.getJSONObject("left"))) } }
        val rest = j.getJSONObject("rest")
        return HandsData(j.getDouble("handScale").toFloat(), dim, spec(rest.getJSONObject("right")) to spec(rest.getJSONObject("left")), poses, signs)
    }
}

// ---------- Hand state and sign player (port of signPlayer.js / animationController.js) ----------
internal class HandState(val pos: FloatArray = FloatArray(3), val rot: Quat = Quat(), val j: Array<Quat> = Array(JOINTS) { Quat() }, var scl: Float = 1f) {
    fun copyFrom(s: HandState) = apply { s.pos.copyInto(pos); rot.set(s.rot); for (i in 0 until JOINTS) j[i].set(s.j[i]); scl = s.scl }
    fun clone() = HandState().copyFrom(this)
}
private fun blend(out: HandState, a: HandState, b: HandState, k: Float) {
    for (i in 0..2) out.pos[i] = a.pos[i] + (b.pos[i] - a.pos[i]) * k
    qSlerp(a.rot, b.rot, k, out.rot); for (i in 0 until JOINTS) qSlerp(a.j[i], b.j[i], k, out.j[i])
    out.scl = a.scl + (b.scl - a.scl) * k
}
private val EASE: Map<String, (Float) -> Float> = mapOf(
    "linear" to { k -> k },
    "easeInOutSine" to { k -> -(cos(PI.toFloat() * k) - 1) / 2 },
    "easeInOutQuad" to { k -> if (k < .5f) 2 * k * k else 1 - (-2 * k + 2).pow(2) / 2 },
    "easeInOutCubic" to { k -> if (k < .5f) 4 * k * k * k else 1 - (-2 * k + 2).pow(3) / 2 },
    "easeOutCubic" to { k -> 1 - (1 - k).pow(3) },
    "easeInCubic" to { k -> k * k * k },
)

internal class SignPlayer(private val data: HandsData, private val onSign: (Int) -> Unit) {
    private class Kf(val t: Float, val ease: (Float) -> Float, val right: HandState, val left: HandState)
    private class Clip(val kfs: List<Kf>, val duration: Float, val transient: Boolean)
    val right = resolve(data.rest.first, HandState()); val left = resolve(data.rest.second, HandState())
    var speed = 1f
    /** True while a sign, the pause between signs or the return to rest is running. */
    val busy get() = clip != null
    private val queue = ArrayDeque<String>()
    private var clip: Clip? = null; private var t = 0f; private var hold = 0f; private var fade = 1f
    private var fadeFrom: Pair<HandState, HandState>? = null; private var index = -1
    private val sampleR = HandState(); private val sampleL = HandState()

    private fun resolve(s: HandSpec, prev: HandState): HandState {
        val h = prev.clone()
        s.pose?.let { p -> data.poses[p]?.forEachIndexed { i, q -> h.j[i].set(q) } }
        s.position?.copyInto(h.pos); s.rotation?.let { qEuler(it, "XYZ", h.rot) }; s.scale?.let { h.scl = it }
        return h
    }
    private fun compile(kfs: List<KeyFrame>, transient: Boolean): Clip {
        val out = mutableListOf(Kf(0f, EASE.getValue("linear"), right.clone(), left.clone()))
        var prev = out[0]
        for (k in kfs) {
            val e = Kf(max(0f, k.t), EASE[k.ease] ?: EASE.getValue("easeInOutSine"), resolve(k.right, prev.right), resolve(k.left, prev.left))
            if (e.t == 0f) out[0] = e else out.add(e); prev = e
        }
        return Clip(out.sortedBy { it.t }, out.maxOf { it.t }, transient)
    }
    private fun toRest(duration: Float) {
        clip = compile(listOf(KeyFrame(duration, "easeInOutCubic", data.rest.first, data.rest.second)), true); t = 0f; hold = 0f; fade = 1f; fadeFrom = null
    }
    private fun next() {
        val id = queue.removeFirstOrNull()
        if (id == null) { val was = clip; clip = null; if (was != null && !was.transient) { index = -1; onSign(-1); toRest(.6f) }; return }
        val kfs = data.signs[id] ?: return next()
        clip = compile(kfs, false); t = 0f; hold = if (index >= 0) .08f else 0f; fadeFrom = right.clone() to left.clone(); fade = 0f
        index++; onSign(index)
    }
    fun play(seq: List<String>) { queue.clear(); index = -1; clip = null; queue.addAll(seq.filter { it in data.signs }); if (queue.isEmpty()) toRest(.5f) else next() }

    /** Advances the animation; returns true when the hands moved. */
    fun update(dt: Float): Boolean {
        val c = clip ?: return false
        if (hold > 0f) { hold -= dt * speed; return false }
        t += dt * speed
        var i = 0; val k = c.kfs
        while (i < k.size - 2 && t > k[i + 1].t) i++
        val a = k[i]; val b = k[min(i + 1, k.size - 1)]
        val span = b.t - a.t; val u = if (span > 0) ((t - a.t) / span).coerceIn(0f, 1f) else 1f; val e = b.ease(u)
        blend(sampleR, a.right, b.right, e); blend(sampleL, a.left, b.left, e)
        val from = fadeFrom
        if (fade < 1f && from != null) {
            fade = min(1f, fade + dt * speed / .28f); val s = EASE.getValue("easeInOutSine")(fade)
            blend(right, from.first, sampleR, s); blend(left, from.second, sampleL, s)
        } else { right.copyFrom(sampleR); left.copyFrom(sampleL) }
        if (t >= c.duration) { if (c.transient) clip = null else next() }
        return true
    }
}

// ---------- Geometry made in code (as THREE.CapsuleGeometry / CylinderGeometry) ----------
private class Mesh(val vbo: Int, val ibo: Int, val count: Int)
private class MeshData(val v: FloatArray, val i: ShortArray)

/** Capsule along Y, centred: hemispheres of [capSeg] rings joined by a cylinder of length [len]. */
private fun capsule(r: Float, len: Float, capSeg: Int, radial: Int, lift: Float): MeshData {
    val rings = mutableListOf<Triple<Float, Float, Float>>()   // y, ring radius, normal angle
    for (i in 0..capSeg) { val a = -PI.toFloat() / 2 + (PI.toFloat() / 2) * i / capSeg; rings.add(Triple(-len / 2 + r * sin(a), r * cos(a), a)) }
    for (i in 0..capSeg) { val a = (PI.toFloat() / 2) * i / capSeg; rings.add(Triple(len / 2 + r * sin(a), r * cos(a), a)) }
    val v = ArrayList<Float>(); val idx = ArrayList<Short>()
    rings.forEach { (y, rr, a) ->
        for (s in 0..radial) {
            val th = 2 * PI.toFloat() * s / radial; val sx = sin(th); val cz = cos(th)
            v.addAll(listOf(rr * sx, y + lift, rr * cz, cos(a) * sx, sin(a), cos(a) * cz))
        }
    }
    val row = radial + 1
    for (ri in 0 until rings.size - 1) for (s in 0 until radial) {
        val a = ri * row + s; val b = a + row
        idx.addAll(listOf(a, a + 1, b, a + 1, b + 1, b).map { it.toShort() })   // counter-clockwise seen from outside
    }
    return MeshData(v.toFloatArray(), idx.toShortArray())
}
private fun cylinder(rt: Float, rb: Float, h: Float, radial: Int): MeshData {
    val v = ArrayList<Float>(); val idx = ArrayList<Short>()
    val slope = (rb - rt) / h
    for ((y, rr) in listOf(h / 2 to rt, -h / 2 to rb)) for (s in 0..radial) {
        val th = 2 * PI.toFloat() * s / radial; val l = sqrt(1 + slope * slope)
        v.addAll(listOf(rr * sin(th), y, rr * cos(th), sin(th) / l, slope / l, cos(th) / l))
    }
    val row = radial + 1
    for (s in 0 until radial) idx.addAll(listOf(s, s + row, s + 1, s + 1, s + row, s + 1 + row).map { it.toShort() })
    for ((y, rr, ny) in listOf(Triple(h / 2, rt, 1f), Triple(-h / 2, rb, -1f))) {
        val centre = v.size / 6; v.addAll(listOf(0f, y, 0f, 0f, ny, 0f))
        for (s in 0..radial) { val th = 2 * PI.toFloat() * s / radial; v.addAll(listOf(rr * sin(th), y, rr * cos(th), 0f, ny, 0f)) }
        for (s in 0 until radial) { val a = centre + 1 + s; idx.addAll((if (ny > 0) listOf(centre, a, a + 1) else listOf(centre, a + 1, a)).map { it.toShort() }) }
    }
    return MeshData(v.toFloatArray(), idx.toShortArray())
}

// ---------- Renderer ----------
private const val VERT = """#version 300 es
layout(location=0) in vec3 position; layout(location=1) in vec3 normal;
uniform mat4 mv; uniform mat4 proj; uniform float t; out vec3 vN;
void main(){ mat3 nm = transpose(inverse(mat3(mv))); vec3 n = normalize(nm * normal); vN = n;
  vec4 p = mv * vec4(position, 1.0); p.xyz += n * t; gl_Position = proj * p; }"""
private const val FRAG = """#version 300 es
precision mediump float; uniform vec3 c0; uniform vec3 c1; uniform vec3 c2; uniform float outline; in vec3 vN; out vec4 color;
void main(){ if (outline > 0.5) { color = vec4(c0, 1.0); return; }
  float d = dot(normalize(vN), normalize(vec3(-.45, .55, .75))); vec3 col = d > .22 ? c0 : (d > -.3 ? c1 : c2); color = vec4(col, 1.0); }"""
private fun rgb(h: Int) = floatArrayOf(((h shr 16) and 255) / 255f, ((h shr 8) and 255) / 255f, (h and 255) / 255f)
private val GLOVE = listOf(rgb(0xFFFFFF), rgb(0xDCE7F6), rgb(0xB9CBE8))
private val CUFF = listOf(rgb(0xEBA934), rgb(0xD4922A), rgb(0xB97C22))
private val INK = rgb(0x092E66)

private class HandsRenderer(private val data: HandsData) {
    private var program = 0; private val u = HashMap<String, Int>(); private val meshes = HashMap<String, Mesh>()
    private val proj = FloatArray(16); private val view = FloatArray(16).also { android.opengl.Matrix.setIdentityM(it, 0); it[14] = -20f }
    private var outlineT = .04f
    private val tmpA = FloatArray(16); private val tmpB = FloatArray(16); private val mv = FloatArray(16); private val q1 = Quat(); private val q2 = Quat()

    fun init() {
        fun shader(type: Int, src: String) = GLES30.glCreateShader(type).also { GLES30.glShaderSource(it, src); GLES30.glCompileShader(it) }
        program = GLES30.glCreateProgram().also { GLES30.glAttachShader(it, shader(GLES30.GL_VERTEX_SHADER, VERT)); GLES30.glAttachShader(it, shader(GLES30.GL_FRAGMENT_SHADER, FRAG)); GLES30.glLinkProgram(it) }
        val ok = IntArray(1); GLES30.glGetProgramiv(program, GLES30.GL_LINK_STATUS, ok, 0)
        check(ok[0] != 0) { "hands shader: " + GLES30.glGetProgramInfoLog(program) }
        listOf("mv", "proj", "t", "c0", "c1", "c2", "outline").forEach { u[it] = GLES30.glGetUniformLocation(program, it) }
        GLES30.glEnable(GLES30.GL_DEPTH_TEST); GLES30.glEnable(GLES30.GL_CULL_FACE)
    }
    private fun mesh(key: String, make: () -> MeshData) = meshes.getOrPut(key) {
        val d = make(); val ids = IntArray(2); GLES30.glGenBuffers(2, ids, 0)
        val vb: FloatBuffer = ByteBuffer.allocateDirect(d.v.size * 4).order(ByteOrder.nativeOrder()).asFloatBuffer().put(d.v).also { it.position(0) }
        val ib: ShortBuffer = ByteBuffer.allocateDirect(d.i.size * 2).order(ByteOrder.nativeOrder()).asShortBuffer().put(d.i).also { it.position(0) }
        GLES30.glBindBuffer(GLES30.GL_ARRAY_BUFFER, ids[0]); GLES30.glBufferData(GLES30.GL_ARRAY_BUFFER, d.v.size * 4, vb, GLES30.GL_STATIC_DRAW)
        GLES30.glBindBuffer(GLES30.GL_ELEMENT_ARRAY_BUFFER, ids[1]); GLES30.glBufferData(GLES30.GL_ELEMENT_ARRAY_BUFFER, d.i.size * 2, ib, GLES30.GL_STATIC_DRAW)
        Mesh(ids[0], ids[1], d.i.size)
    }

    /** w, h, cx, cy, r in dp: the orb centre and radius define the units, as HandsView.layout(). */
    fun layout(w: Float, h: Float, cx: Float, cy: Float, r: Float) {
        android.opengl.Matrix.orthoM(proj, 0, -cx / r, (w - cx) / r, -(h - cy) / r, cy / r, .1f, 60f)
        outlineT = max(1.5f, min(2.6f, r * .03f)) / r
    }

    private fun draw(m: Mesh, model: FloatArray, colors: List<FloatArray>) {
        mMul(view, model, mv)
        GLES30.glUniformMatrix4fv(u.getValue("mv"), 1, false, mv, 0)
        GLES30.glBindBuffer(GLES30.GL_ARRAY_BUFFER, m.vbo); GLES30.glBindBuffer(GLES30.GL_ELEMENT_ARRAY_BUFFER, m.ibo)
        GLES30.glEnableVertexAttribArray(0); GLES30.glVertexAttribPointer(0, 3, GLES30.GL_FLOAT, false, 24, 0)
        GLES30.glEnableVertexAttribArray(1); GLES30.glVertexAttribPointer(1, 3, GLES30.GL_FLOAT, false, 24, 12)
        // Inverted hull: back faces pushed out along the normal, in ink.
        GLES30.glCullFace(GLES30.GL_FRONT); GLES30.glUniform1f(u.getValue("t"), outlineT); GLES30.glUniform1f(u.getValue("outline"), 1f)
        GLES30.glUniform3fv(u.getValue("c0"), 1, INK, 0)
        GLES30.glDrawElements(GLES30.GL_TRIANGLES, m.count, GLES30.GL_UNSIGNED_SHORT, 0)
        GLES30.glCullFace(GLES30.GL_BACK); GLES30.glUniform1f(u.getValue("t"), 0f); GLES30.glUniform1f(u.getValue("outline"), 0f)
        GLES30.glUniform3fv(u.getValue("c0"), 1, colors[0], 0); GLES30.glUniform3fv(u.getValue("c1"), 1, colors[1], 0); GLES30.glUniform3fv(u.getValue("c2"), 1, colors[2], 0)
        GLES30.glDrawElements(GLES30.GL_TRIANGLES, m.count, GLES30.GL_UNSIGNED_SHORT, 0)
    }

    private fun hand(s: HandState, side: Int) {
        val mirror = side < 0
        val rootRot = if (mirror) qMirror(s.rot, q1) else q1.set(s.rot)
        val k = data.handScale * s.scl
        val root = mCompose(s.pos[0], s.pos[1], s.pos[2], rootRot, k, k, k, FloatArray(16))
        draw(mesh("palm") { capsule(.34f, .34f, 6, 18, 0f) }, mMul(root, mCompose(0f, .43f, 0f, IDENTITY_Q, 1.08f, .8f, .42f, tmpA)), GLOVE)
        draw(mesh("cuff") { cylinder(.3f, .32f, .26f, 24) }, mMul(root, mCompose(0f, -.1f, 0f, IDENTITY_Q, 1f, 1f, .62f, tmpA)), GLOVE)
        draw(mesh("band") { cylinder(.333f, .336f, .075f, 24) }, mMul(root, mCompose(0f, -.13f, 0f, IDENTITY_Q, 1f, 1f, .64f, tmpA)), CUFF)
        var ji = 0
        for (f in FINGERS) {
            val d = data.dim.getValue(f); var parent = root
            for (i in 0..2) {
                val rest = qEuler(d.rest[i], "ZXY", q2); val restQ = if (mirror) qMirror(rest, Quat()) else rest.copy()
                val pose = if (mirror) qMirror(s.j[ji], Quat()) else s.j[ji]
                val q = qMul(restQ, pose)
                val local = if (i == 0) mCompose(d.base[0] * side, d.base[1], d.base[2], q, 1f, 1f, 1f, tmpB) else mCompose(0f, d.len[i - 1], 0f, q, 1f, 1f, 1f, tmpB)
                val joint = mMul(parent, local, FloatArray(16))
                val r = d.r[i]; val len = d.len[i]
                draw(mesh("c$r/$len") { capsule(r, len, 4, 12, len / 2) }, joint, GLOVE)
                parent = joint; ji++
            }
        }
    }

    fun render(player: SignPlayer, width: Int, height: Int) {
        GLES30.glViewport(0, 0, width, height)
        GLES30.glClearColor(0f, 0f, 0f, 0f); GLES30.glClear(GLES30.GL_COLOR_BUFFER_BIT or GLES30.GL_DEPTH_BUFFER_BIT)
        GLES30.glUseProgram(program); GLES30.glUniformMatrix4fv(u.getValue("proj"), 1, false, proj, 0)
        hand(player.right, 1); hand(player.left, -1)
    }
}

/**
 * Transparent TextureView with its own GL thread. All engine state lives on that thread; [play], [setSpeed]
 * and [layout] post to it, and [onSign] is called back on the main thread.
 */
internal class Hands3DView(context: Context, private val onSign: (Int) -> Unit, private val onUnavailable: () -> Unit) : TextureView(context), TextureView.SurfaceTextureListener {
    private val thread = HandlerThread("aingel-hands-gl").also { it.start() }
    private val gl = Handler(thread.looper); private val main = Handler(Looper.getMainLooper())
    private var egl: Triple<EGLDisplay, EGLContext, EGLSurface>? = null
    private var renderer: HandsRenderer? = null; private var player: SignPlayer? = null
    private var size = 0 to 0; private var layoutArgs: FloatArray? = null
    private var running = false; private var lastNanos = 0L; private var dirty = true; private var pending: List<String>? = null

    init { isOpaque = false; surfaceTextureListener = this; importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS }

    fun layout(w: Float, h: Float, cx: Float, cy: Float, r: Float) { gl.post { layoutArgs = floatArrayOf(w, h, cx, cy, r); renderer?.layout(w, h, cx, cy, r); dirty = true; wake() } }
    fun play(seq: List<String>) { gl.post { val p = player; if (p == null) pending = seq else { p.play(seq); wake() } } }
    fun setSpeed(s: Float) { gl.post { speed = s.coerceIn(.1f, 3f); player?.speed = speed } }
    private var speed = 1f

    private val frame = object : Choreographer.FrameCallback {
        override fun doFrame(now: Long) {
            val p = player; val r = renderer; val e = egl
            if (p == null || r == null || e == null) { running = false; return }
            val dt = if (lastNanos == 0L) .016f else min(.05f, (now - lastNanos) / 1e9f); lastNanos = now
            val moved = p.update(dt)
            if (moved || dirty) { dirty = false; r.render(p, size.first, size.second); EGL14.eglSwapBuffers(e.first, e.third) }
            if (p.busy || dirty) Choreographer.getInstance().postFrameCallback(this) else { running = false; lastNanos = 0L }
        }
    }
    private fun wake() { if (!running && egl != null) { running = true; Choreographer.getInstance().postFrameCallback(frame) } }

    override fun onSurfaceTextureAvailable(st: SurfaceTexture, w: Int, h: Int) { gl.post {
        try {
            val display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY); EGL14.eglInitialize(display, IntArray(2), 0, IntArray(2), 1)
            fun choose(samples: Int): EGLConfig? {
                val attrs = intArrayOf(EGL14.EGL_RED_SIZE, 8, EGL14.EGL_GREEN_SIZE, 8, EGL14.EGL_BLUE_SIZE, 8, EGL14.EGL_ALPHA_SIZE, 8, EGL14.EGL_DEPTH_SIZE, 16,
                    EGL14.EGL_RENDERABLE_TYPE, EGLExt.EGL_OPENGL_ES3_BIT_KHR, EGL14.EGL_SAMPLE_BUFFERS, if (samples > 0) 1 else 0, EGL14.EGL_SAMPLES, samples, EGL14.EGL_NONE)
                val out = arrayOfNulls<EGLConfig>(1); val n = IntArray(1)
                return if (EGL14.eglChooseConfig(display, attrs, 0, out, 0, 1, n, 0) && n[0] > 0) out[0] else null
            }
            val config = choose(4) ?: choose(0) ?: error("no EGL config")
            val ctx = EGL14.eglCreateContext(display, config, EGL14.EGL_NO_CONTEXT, intArrayOf(EGL14.EGL_CONTEXT_CLIENT_VERSION, 3, EGL14.EGL_NONE), 0)
            val surface = EGL14.eglCreateWindowSurface(display, config, st, intArrayOf(EGL14.EGL_NONE), 0)
            check(ctx != EGL14.EGL_NO_CONTEXT && surface != EGL14.EGL_NO_SURFACE && EGL14.eglMakeCurrent(display, surface, surface, ctx)) { "EGL setup failed" }
            egl = Triple(display, ctx, surface); size = w to h
            val data = HandsAssets.load(context)
            renderer = HandsRenderer(data).also { it.init(); layoutArgs?.let { a -> it.layout(a[0], a[1], a[2], a[3], a[4]) } }
            player = SignPlayer(data) { i -> main.post { onSign(i) } }.also { p -> p.speed = speed; pending?.let { p.play(it) }; pending = null }
            dirty = true; wake()
        } catch (e: Exception) {
            android.util.Log.w("AingelHands3D", "OpenGL hands unavailable, using 2D hands", e)
            main.post { onUnavailable() }
        }
    } }
    override fun onSurfaceTextureSizeChanged(st: SurfaceTexture, w: Int, h: Int) { gl.post { size = w to h; dirty = true; wake() } }
    override fun onSurfaceTextureUpdated(st: SurfaceTexture) {}
    override fun onSurfaceTextureDestroyed(st: SurfaceTexture): Boolean {
        gl.post {
            egl?.let { (d, c, s) -> EGL14.eglMakeCurrent(d, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT); EGL14.eglDestroySurface(d, s); EGL14.eglDestroyContext(d, c) }
            egl = null; renderer = null; player = null; running = false
            thread.quitSafely()
        }
        return true
    }
}
