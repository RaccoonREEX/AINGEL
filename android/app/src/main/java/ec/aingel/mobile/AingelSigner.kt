package ec.aingel.mobile

import android.graphics.Bitmap
import android.graphics.PorterDuff
import android.graphics.PorterDuffXfermode
import android.graphics.Rect
import android.graphics.RectF
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.Dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import kotlin.math.*

/*
 * AINGEL's floating hands: Kotlin port of <aingel-signer> (AINGEL_Manos_y_Senas v1.0.0, catalogue v1.5.0),
 * same as web/src/components/aingel/AingelSigner.tsx. Articulated rig (palm + 5 fingers, 3 phalanges,
 * opposable thumb): manual alphabet, numbers, words, actions. AINGEL DESIGN, PENDING LSEC VALIDATION.
 */
private class Shape(val t: FloatArray, val f: List<FloatArray>, val sp: Float = 0f)
private val X = floatArrayOf(1f, 1f); private val O0 = floatArrayOf(0f, 0f)
private fun f2(a: Float, b: Float) = floatArrayOf(a, b)
private fun H(t: FloatArray, f: List<FloatArray>, sp: Float = 0f) = Shape(t, f, sp)
private val TA = floatArrayOf(.55f, .95f, .35f, .45f)
private val HS = mapOf(
    "relax" to H(floatArrayOf(.7f, .3f, .2f, .2f), listOf(f2(.25f, .3f), f2(.3f, .35f), f2(.35f, .4f), f2(.4f, .45f)), .06f),
    "open" to H(floatArrayOf(1.05f, 0f, 0f, 0f), listOf(O0, O0, O0, O0), .16f),
    "flat" to H(floatArrayOf(.25f, .55f, .15f, .2f), listOf(O0, O0, O0, O0)),
    "a" to H(floatArrayOf(.12f, 0f, 0f, 0f), listOf(X, X, X, X)),
    "b" to H(TA, listOf(O0, O0, O0, O0)),
    "c" to H(floatArrayOf(.95f, .45f, .2f, .3f), listOf(f2(.45f, .5f), f2(.45f, .5f), f2(.45f, .5f), f2(.45f, .5f))),
    "d" to H(floatArrayOf(.65f, .85f, .35f, .45f), listOf(O0, f2(.6f, .75f), f2(.6f, .75f), f2(.6f, .75f))),
    "e" to H(floatArrayOf(.5f, 1f, .55f, .65f), listOf(f2(.25f, 1f), f2(.25f, 1f), f2(.25f, 1f), f2(.25f, 1f))),
    "f" to H(floatArrayOf(.65f, .85f, .3f, .35f), listOf(f2(.55f, .65f), O0, O0, O0), .16f),
    "g" to H(floatArrayOf(.55f, .15f, 0f, 0f), listOf(O0, X, X, X)),
    "h" to H(TA, listOf(O0, O0, X, X)),
    "i" to H(TA, listOf(X, X, X, O0)),
    "k" to H(floatArrayOf(.3f, .55f, 0f, .15f), listOf(O0, f2(.45f, 0f), X, X), .2f),
    "l" to H(floatArrayOf(1.55f, 0f, 0f, 0f), listOf(O0, X, X, X)),
    "m" to H(floatArrayOf(.5f, 1f, .5f, .5f), listOf(f2(.95f, .6f), f2(.95f, .6f), f2(.95f, .6f), X)),
    "n" to H(floatArrayOf(.5f, 1f, .5f, .5f), listOf(f2(.95f, .6f), f2(.95f, .6f), X, X)),
    "o" to H(floatArrayOf(.7f, .8f, .3f, .4f), listOf(f2(.6f, .65f), f2(.6f, .65f), f2(.6f, .65f), f2(.6f, .65f))),
    "r" to H(TA, listOf(O0, O0, X, X), -.12f),
    "s" to H(floatArrayOf(.6f, .95f, .3f, .4f), listOf(X, X, X, X)),
    "t" to H(floatArrayOf(.35f, .65f, .05f, .05f), listOf(f2(.85f, .45f), X, X, X)),
    "u" to H(TA, listOf(O0, O0, X, X)),
    "v" to H(TA, listOf(O0, O0, X, X), .48f),
    "w" to H(floatArrayOf(.55f, 1f, .45f, .55f), listOf(O0, O0, O0, X), .3f),
    "x" to H(TA, listOf(f2(.05f, 1f), X, X, X)),
    "y" to H(floatArrayOf(1.55f, 0f, 0f, 0f), listOf(X, X, X, O0), .3f),
    "idx" to H(TA, listOf(O0, X, X, X)),
    "n3" to H(floatArrayOf(1.1f, 0f, 0f, 0f), listOf(O0, O0, X, X), .3f),
    "n4" to H(TA, listOf(O0, O0, O0, O0), .2f),
    "claw" to H(floatArrayOf(1f, .3f, .3f, .5f), listOf(f2(.25f, .75f), f2(.25f, .75f), f2(.25f, .75f), f2(.25f, .75f)), .18f),
    "bent" to H(floatArrayOf(.3f, .5f, .1f, .1f), listOf(f2(.95f, 0f), f2(.95f, 0f), f2(.95f, 0f), f2(.95f, 0f))),
    "pinch" to H(floatArrayOf(.75f, .75f, .25f, .35f), listOf(f2(.5f, .55f), f2(.4f, .4f), f2(.3f, .3f), f2(.25f, .25f)), .05f),
)

/** A keyframe: only what changes; the rest is inherited. x, y in head radii (y down); angles in radians. */
private class P(val x: Float? = null, val y: Float? = null, val s: Float? = null, val yaw: Float? = null, val pitch: Float? = null, val roll: Float? = null, val hs: String? = null, val a: Float? = null)
private class Sign(val d: Float, val A: List<Pair<Float, P>>? = null, val B: List<Pair<Float, P>>? = null)
private val RA = P(-1.3f, 3.0f, .85f, .2f, .9f, .15f, "relax", 0f)
private val RB = P(1.3f, 3.0f, .85f, .2f, .9f, .15f, "relax", 0f)
private fun letter(hs: String, x: Float = -1.55f, y: Float = 1.0f, yaw: Float = 0f, pitch: Float = 0f, roll: Float = 0f) = P(x, y, 1.05f, yaw, pitch, roll, hs)
private fun still(p: P) = listOf(0f to p, .5f to P(y = p.y!! - .04f), 1f to P(y = p.y))
private val SIGNS: Map<String, Sign> = buildMap {
    val ex = mapOf("c" to letter("c", yaw = .95f), "o" to letter("o", yaw = .75f), "g" to letter("g", roll = -1.45f, yaw = .3f), "h" to letter("h", roll = -1.45f, yaw = .3f),
        "k" to letter("k", yaw = .2f), "e" to letter("e", yaw = .15f), "t" to letter("t", yaw = .1f))
    "a b c d e f g h i k l m n o r s t u v w x y".split(" ").forEach { put(it, Sign(1f, still(ex[it] ?: letter(it)))) }
    put("j", Sign(1.3f, listOf(0f to letter("i", y = .9f), .35f to P(y = 1.35f), .7f to P(x = -.8f, y = 1.5f, roll = .7f), 1f to P(x = -.7f, y = 1.35f, roll = 1.1f))))
    put("z", Sign(1.5f, listOf(0f to letter("idx", x = -1.35f, y = .8f), .25f to P(x = -.75f), .55f to P(x = -1.35f, y = 1.4f), .8f to P(x = -.75f), 1f to P())))
    put("ñ", Sign(1.3f, listOf(0f to letter("n"), .3f to P(x = -.9f, roll = .25f), .55f to P(x = -1.15f, roll = -.2f), .8f to P(x = -.9f, roll = .2f), 1f to P(x = -1.05f, roll = 0f))))
    put("p", Sign(1f, still(letter("k", roll = 2.5f, pitch = .4f, y = 1.4f))))
    put("q", Sign(1f, still(letter("g", roll = 2.7f, pitch = .3f, y = 1.4f))))
    put("n0", Sign(1f, still(letter("o", yaw = .7f)))); put("n1", Sign(1f, still(letter("idx")))); put("n2", Sign(1f, still(letter("v"))))
    put("n3", Sign(1f, still(letter("n3")))); put("n4", Sign(1f, still(letter("n4")))); put("n5", Sign(1f, still(letter("open"))))
    fun nb(hs: String) = still(P(1.0f, 1.3f, 1.05f, 0f, 0f, 0f, hs))
    val open10 = letter("open", x = -1.0f, y = 1.3f)
    put("n6", Sign(1.2f, still(open10), nb("idx"))); put("n7", Sign(1.2f, still(open10), nb("v")))
    put("n8", Sign(1.2f, still(open10), nb("n3"))); put("n9", Sign(1.2f, still(open10), nb("n4")))
    put("n10", Sign(1.3f, listOf(0f to open10, .3f to P(roll = .2f), .6f to P(roll = -.15f), 1f to P(roll = 0f)),
        listOf(0f to P(.95f, 1.25f, 1.05f, 0f, 0f, 0f, "open"), .3f to P(roll = .2f), .6f to P(roll = -.15f), 1f to P(roll = 0f))))
    put("yo", Sign(1.2f, listOf(0f to P(-.35f, 2.1f, 1f, 1.5f, 0f, 1.6f, "idx"), .4f to P(x = -.15f, y = 2.0f, s = .95f), .7f to P(x = -.2f), 1f to P())))
    put("tu", Sign(1.2f, listOf(0f to P(-.5f, 1.6f, 1f, .3f, 1.2f, 0f, "idx"), .45f to P(y = 1.45f, s = 1.3f, pitch = 1.45f), 1f to P())))
    put("hola", Sign(1.5f, listOf(0f to P(-.9f, -.3f, 1.05f, 0f, 0f, -.1f, "b"), .35f to P(x = -1.4f, y = -.1f, roll = -.35f, hs = "open"), .55f to P(roll = .05f), .75f to P(roll = -.35f), 1f to P(roll = -.1f))))
    put("gracias", Sign(1.5f, listOf(0f to P(-.2f, .85f, 1f, .2f, .2f, .1f, "flat"), .25f to P(), .75f to P(x = -.55f, y = 1.55f, s = 1.25f, pitch = 1.1f), 1f to P())))
    put("porfavor", Sign(1.6f, listOf(0f to P(-.25f, 2.0f, 1f, 0f, .1f, .3f, "flat"), .25f to P(x = .1f, y = 1.85f), .5f to P(x = .15f, y = 2.15f), .75f to P(x = -.25f, y = 2.25f), 1f to P(x = -.25f, y = 2.0f))))
    put("si", Sign(1.2f, listOf(0f to P(-.75f, 1.5f, 1f, .4f, 0f, 0f, "s"), .25f to P(pitch = .8f, y = 1.6f), .5f to P(pitch = 0f, y = 1.5f), .75f to P(pitch = .8f, y = 1.6f), 1f to P(pitch = 0f, y = 1.5f))))
    put("no", Sign(1.2f, listOf(0f to P(-.75f, 1.3f, 1f, .1f, 0f, 0f, "idx"), .25f to P(roll = .4f), .5f to P(roll = -.4f), .75f to P(roll = .4f), 1f to P(roll = 0f))))
    put("bien", Sign(1.2f, listOf(0f to P(-.7f, 1.7f, 1f, 1.4f, 0f, 0f, "a"), .45f to P(y = 1.45f, s = 1.2f), 1f to P())))
    put("mal", Sign(1.2f, listOf(0f to P(-.7f, 1.45f, 1f, 1.4f, 0f, 3.1f, "a"), .45f to P(y = 1.75f, s = 1.15f), 1f to P())))
    put("agua", Sign(1.4f, listOf(0f to P(-.35f, .85f, 1f, 1.2f, 0f, 0f, "c"), .3f to P(x = -.15f, y = .6f, roll = -.6f), .55f to P(x = -.3f, y = .85f, roll = 0f), .8f to P(x = -.15f, y = .6f, roll = -.6f), 1f to P(x = -.3f, y = .85f, roll = 0f))))
    val comida = Sign(1.3f, listOf(0f to P(-.3f, .95f, 1f, 1.1f, .5f, .5f, "pinch"), .25f to P(x = -.1f, y = .62f), .5f to P(x = -.3f, y = .95f), .75f to P(x = -.1f, y = .62f), 1f to P(x = -.3f, y = .95f)))
    put("comida", comida); put("comer", comida)
    put("medicina", Sign(1.6f, listOf(0f to P(.05f, 1.75f, .95f, .2f, .3f, 2.4f, "k"), .25f to P(x = .25f), .5f to P(x = .1f, y = 1.6f), .75f to P(x = .25f, y = 1.75f), 1f to P(x = .05f)),
        listOf(0f to P(.45f, 2.05f, 1f, 0f, 1.35f, -1.5f, "flat"), 1f to P())))
    put("casa", Sign(1.5f, listOf(0f to P(-.25f, 1.0f, 1f, .6f, 0f, .7f, "flat"), .3f to P(), 1f to P(x = -.75f, y = 1.65f, roll = .05f)),
        listOf(0f to P(.25f, 1.0f, 1f, .6f, 0f, .7f, "flat"), .3f to P(), 1f to P(x = .75f, y = 1.65f, roll = .05f))))
    put("parque", Sign(1.6f, listOf(0f to P(-.15f, 1.1f, 1.05f, 0f, 0f, 0f, "open"), .25f to P(roll = .25f), .5f to P(roll = -.2f), .75f to P(x = -.6f, roll = .25f), 1f to P(roll = 0f)),
        listOf(0f to P(.3f, 2.25f, .95f, 1.2f, 1.3f, -1.5f, "flat"), 1f to P())))
    put("pelota", Sign(1.4f, listOf(0f to P(-.75f, 1.75f, 1f, 1.2f, 0f, .3f, "claw"), .4f to P(x = -.45f), 1f to P(x = -.5f, y = 1.7f)),
        listOf(0f to P(.75f, 1.75f, 1f, 1.2f, 0f, .3f, "claw"), .4f to P(x = .45f), 1f to P(x = .5f, y = 1.7f))))
    put("libro", Sign(1.5f, listOf(0f to P(-.15f, 1.7f, 1f, 1.5f, 0f, .1f, "flat"), .3f to P(), .8f to P(x = -.6f, yaw = .1f, pitch = .9f, roll = 1.0f), 1f to P()),
        listOf(0f to P(.15f, 1.7f, 1f, 1.5f, 0f, .1f, "flat"), .3f to P(), .8f to P(x = .6f, yaw = .1f, pitch = .9f, roll = 1.0f), 1f to P())))
    put("bano", Sign(1.3f, listOf(0f to P(-.75f, 1.45f, 1f, 0f, 0f, 0f, "t"), .25f to P(roll = .35f), .5f to P(roll = -.3f), .75f to P(roll = .35f), 1f to P(roll = 0f))))
    put("doctor", Sign(1.4f, listOf(0f to P(.15f, 1.75f, .95f, .3f, .5f, 2.3f, "u"), .3f to P(y = 1.9f), .55f to P(y = 1.75f), .8f to P(y = 1.9f), 1f to P(y = 1.75f)),
        listOf(0f to P(.45f, 2.1f, .95f, .2f, 1.4f, -1.3f, "flat"), 1f to P())))
    put("familia", Sign(1.7f, listOf(0f to P(-.25f, 1.6f, 1f, .3f, 0f, 0f, "f"), .5f to P(x = -.85f, y = 1.85f), 1f to P(x = -.3f, y = 2.1f)),
        listOf(0f to P(.25f, 1.6f, 1f, .3f, 0f, 0f, "f"), .5f to P(x = .85f, y = 1.85f), 1f to P(x = .3f, y = 2.1f))))
    put("mama", Sign(1.3f, listOf(0f to P(-.3f, .85f, .95f, 1.3f, 0f, 0f, "open"), .25f to P(x = -.12f), .5f to P(x = -.3f), .75f to P(x = -.12f), 1f to P(x = -.3f))))
    put("papa", Sign(1.3f, listOf(0f to P(-.3f, -.55f, .95f, 1.3f, 0f, 0f, "open"), .25f to P(x = -.12f), .5f to P(x = -.3f), .75f to P(x = -.12f), 1f to P(x = -.3f))))
    fun cradle(side: Float) = listOf(0f to P(side * .3f, 2.0f, .95f, 0f, 1.3f, side * -1.4f, "flat"), .3f to P(x = side * .45f, y = 1.9f), .6f to P(x = side * .15f, y = 2.1f), 1f to P(x = side * .3f, y = 2.0f))
    put("hija", Sign(1.6f, cradle(-1f), cradle(1f)))
    put("hijo", Sign(1.6f, listOf(0f to P(-.75f, -.15f, .95f, 1.2f, 0f, -.3f, "b"), .35f to P(), .7f to P(x = -.3f, y = 2.0f, yaw = 0f, pitch = 1.3f, roll = 1.4f, hs = "flat"), 1f to P()),
        listOf(0f to RB, .55f to RB, .75f to P(.3f, 2.05f, .95f, 0f, 1.3f, -1.4f, "flat"), 1f to P())))
    put("dolor", Sign(1.4f, listOf(0f to P(-.55f, 1.8f, 1f, 1.5f, 0f, 1.5f, "idx"), .25f to P(x = -.3f, roll = 1.2f), .5f to P(x = -.5f, roll = 1.6f), .75f to P(x = -.3f, roll = 1.2f), 1f to P(x = -.5f, roll = 1.5f)),
        listOf(0f to P(.55f, 1.8f, 1f, 1.5f, 0f, 1.5f, "idx"), .25f to P(x = .3f, roll = 1.2f), .5f to P(x = .5f, roll = 1.6f), .75f to P(x = .3f, roll = 1.2f), 1f to P(x = .5f, roll = 1.5f))))
    val ayuda = Sign(1.5f, listOf(0f to P(0f, 2.0f, 1f, 1.4f, 0f, 0f, "a"), .3f to P(), 1f to P(y = 1.4f)), listOf(0f to P(.15f, 2.35f, 1f, 0f, 1.35f, -1.5f, "flat"), .3f to P(), 1f to P(y = 1.75f)))
    put("ayuda", ayuda); put("ayudar", ayuda)
    put("hoy", Sign(1.3f, listOf(0f to P(-.55f, 1.7f, 1f, 0f, 1.35f, .2f, "flat"), .25f to P(y = 1.95f), .5f to P(y = 1.7f), .75f to P(y = 1.95f), 1f to P(y = 1.75f)),
        listOf(0f to P(.55f, 1.7f, 1f, 0f, 1.35f, .2f, "flat"), .25f to P(y = 1.95f), .5f to P(y = 1.7f), .75f to P(y = 1.95f), 1f to P(y = 1.75f))))
    put("manana", Sign(1.3f, listOf(0f to P(-.65f, .35f, .95f, 1.3f, 0f, 0f, "a"), .3f to P(), 1f to P(x = -.95f, y = .7f, s = 1.2f, pitch = .8f))))
    put("ayer", Sign(1.3f, listOf(0f to P(-.75f, .55f, 1f, 1.3f, 0f, 0f, "a"), .3f to P(), 1f to P(x = -.95f, y = 0f, s = .85f, roll = -.8f))))
    put("caminar", Sign(1.6f, listOf(0f to P(-.3f, 1.6f, 1f, 0f, 0f, 3.14f, "v"), .25f to P(x = -.45f, roll = 2.8f), .5f to P(x = -.6f, roll = 3.4f), .75f to P(x = -.75f, roll = 2.8f), 1f to P(x = -.9f, roll = 3.14f))))
    put("leer", Sign(1.6f, listOf(0f to P(-.15f, 1.35f, .95f, .2f, .6f, 2.9f, "v"), .35f to P(y = 1.75f), .55f to P(y = 1.45f), .85f to P(y = 1.85f), 1f to P()),
        listOf(0f to P(.35f, 1.95f, 1f, 0f, 0f, -.15f, "flat"), 1f to P())))
    put("beber", Sign(1.4f, listOf(0f to P(-.45f, 1.2f, 1f, 1.2f, 0f, 0f, "c"), .45f to P(x = -.15f, y = .65f, roll = -.9f), .7f to P(), 1f to P(x = -.45f, y = 1.2f, roll = 0f))))
    put("dormir", Sign(1.8f, listOf(0f to P(-.5f, -.25f, 1f, 0f, 0f, .1f, "open"), .6f to P(y = .2f, hs = "pinch"), .75f to P(), 1f to P(x = -.8f, y = .35f, roll = .9f, hs = "flat"))))
    fun wait(x: Float) = listOf(0f to P(x, 1.6f, 1f, .1f, 0f, .1f, "open"), .2f to P(hs = "claw"), .4f to P(hs = "open"), .6f to P(hs = "claw"), .8f to P(hs = "open"), 1f to P())
    put("esperar", Sign(1.5f, wait(-.8f), wait(.8f)))
    put("ir", Sign(1.3f, listOf(0f to P(-.35f, 1.9f, .95f, .3f, 1.2f, 0f, "idx"), .6f to P(x = -.9f, y = 1.3f, s = 1.25f, pitch = 1.5f), 1f to P())))
    put("venir", Sign(1.3f, listOf(0f to P(-.9f, 1.3f, 1.25f, .3f, 1.5f, 0f, "idx"), .6f to P(x = -.35f, y = 1.95f, s = .95f, pitch = 1.2f, hs = "x"), 1f to P())))
    put("llamar", Sign(1.4f, listOf(0f to P(-1.15f, .15f, 1f, 0f, 0f, -.5f, "y"), .3f to P(x = -1.05f), .55f to P(x = -1.15f), .8f to P(x = -1.05f), 1f to P(x = -1.15f))))
    put("necesitar", Sign(1.3f, listOf(0f to P(-.7f, 1.4f, 1f, .4f, 0f, 0f, "x"), .3f to P(y = 1.7f, pitch = .9f), .55f to P(y = 1.4f, pitch = 0f), .8f to P(y = 1.7f, pitch = .9f), 1f to P(y = 1.45f, pitch = 0f))))
    put("querer", Sign(1.4f, listOf(0f to P(-.75f, 1.4f, 1.15f, 2.9f, .3f, 0f, "claw"), .6f to P(x = -.45f, y = 1.85f, s = .95f, hs = "claw"), 1f to P()),
        listOf(0f to P(.75f, 1.4f, 1.15f, 2.9f, .3f, 0f, "claw"), .6f to P(x = .45f, y = 1.85f, s = .95f), 1f to P())))
    put("tener", Sign(1.3f, listOf(0f to P(-.75f, 1.45f, 1.15f, .2f, .6f, 0f, "open"), .55f to P(x = -.35f, y = 1.95f, s = .95f, hs = "s"), 1f to P())))
    fun play(x: Float) = listOf(0f to P(x, 1.6f, 1f, 0f, 0f, 0f, "y"), .25f to P(roll = .45f), .5f to P(roll = -.3f), .75f to P(roll = .45f), 1f to P(roll = 0f))
    put("jugar", Sign(1.4f, play(-.75f), play(.75f)))
    fun ask(x: Float) = listOf(0f to P(x, 1.7f, 1f, 0f, 1.4f, .3f, "open"), .5f to P(y = 1.55f, roll = .5f), 1f to P())
    put("pregunta", Sign(1.2f, ask(-.75f), ask(.75f)))
}
internal fun hasSign(id: String) = id in SIGNS

// ---------- Sampling: x, y, s, yaw, pitch, roll, a + 13 hand-shape values ----------
private class Pose(val v: FloatArray, val hs: String)
private fun prep(track: List<Pair<Float, P>>?, rest: P): List<Pair<Float, Pose>> {
    fun full(p: P) = Pose(floatArrayOf(p.x!!, p.y!!, p.s!!, p.yaw!!, p.pitch!!, p.roll!!, p.a ?: 0f), p.hs!!)
    if (track == null) return listOf(0f to full(rest), 1f to full(rest))
    val c = floatArrayOf(rest.x!!, rest.y!!, rest.s!!, rest.yaw!!, rest.pitch!!, rest.roll!!, 1f); var hs = rest.hs!!
    return track.map { (k, o) ->
        o.x?.let { c[0] = it }; o.y?.let { c[1] = it }; o.s?.let { c[2] = it }; o.yaw?.let { c[3] = it }; o.pitch?.let { c[4] = it }; o.roll?.let { c[5] = it }; o.a?.let { c[6] = it }; o.hs?.let { hs = it }
        k to Pose(c.copyOf(), hs)
    }
}
private class Prepared(val d: Float, val A: List<Pair<Float, Pose>>, val B: List<Pair<Float, Pose>>)
private val PREPARED = HashMap<String, Prepared>()
private fun prepared(id: String) = PREPARED.getOrPut(id) { val s = SIGNS.getValue(id); Prepared(s.d, prep(s.A, RA), prep(s.B, RB)) }
private fun ease(k: Float) = if (k < .5f) 2 * k * k else 1 - (-2 * k + 2).pow(2) / 2
private fun hsVec(name: String): FloatArray {
    val h = HS[name] ?: HS.getValue("relax")
    return floatArrayOf(h.t[0], h.t[1], h.t[2], h.t[3], h.sp) + h.f.flatMap { listOf(it[0], it[1]) }
}
/** Sample = 7 pose values followed by 13 hand-shape values. */
private fun sample(tr: List<Pair<Float, Pose>>, u: Float): FloatArray {
    for (i in 0 until tr.size - 1) if (u <= tr[i + 1].first) {
        val a = tr[i].second; val b = tr[i + 1].second
        val k = ease(((u - tr[i].first) / max(1e-4f, tr[i + 1].first - tr[i].first)).coerceIn(0f, 1f))
        val va = hsVec(a.hs); val vb = hsVec(b.hs)
        return FloatArray(20) { j -> if (j < 7) a.v[j] + (b.v[j] - a.v[j]) * k else va[j - 7] + (vb[j - 7] - va[j - 7]) * k }
    }
    val l = tr.last().second
    return l.v + hsVec(l.hs)
}
private val REST_A by lazy { sample(prep(null, RA), 0f) }
private val REST_B by lazy { sample(prep(null, RB), 0f) }

// ---------- 3D hand geometry ----------
private val KN = arrayOf(f2(.35f, -.42f), f2(.12f, -.48f), f2(-.11f, -.46f), f2(-.33f, -.38f))
private val FLEN = floatArrayOf(.95f, 1.07f, 1.0f, .8f); private val FW = floatArrayOf(.17f, .176f, .166f, .142f); private val SPF = floatArrayOf(1f, -.15f, -.55f, -1.05f)
private val PALM = arrayOf(f2(-.34f, .52f), f2(.3f, .52f), f2(.46f, .12f), f2(.43f, -.4f), f2(.12f, -.5f), f2(-.12f, -.48f), f2(-.37f, -.4f), f2(-.42f, .1f))
private typealias P3 = FloatArray
private fun chain(base: P3, dir: P3, bend: P3, lens: FloatArray, angs: FloatArray): List<P3> {
    val pts = mutableListOf(base.copyOf()); var p = base.copyOf(); var th = 0f
    for (i in lens.indices) {
        th += angs[i]; val c = cos(th); val s = sin(th)
        p = floatArrayOf(p[0] + (dir[0] * c + bend[0] * s) * lens[i], p[1] + (dir[1] * c + bend[1] * s) * lens[i], p[2] + (dir[2] * c + bend[2] * s) * lens[i])
        pts.add(p)
    }
    return pts
}
private class Finger(val i: Int, val thumb: Boolean, val w: Float, val pts: List<P3>, val curl: Float) { val z = (pts[2][2] + pts[3][2]) / 2; var over = false }
private fun handGeo(h: FloatArray): List<Pair<Float, List<P3>>> {
    val sp = max(h[4], .1f); val out = mutableListOf<Pair<Float, List<P3>>>()
    for (f in 0 until 4) {
        val a = sp * SPF[f]; val m = h[5 + f * 2]; val q = h[6 + f * 2]; val L = FLEN[f]
        out.add(FW[f] to chain(floatArrayOf(KN[f][0], KN[f][1], 0f), floatArrayOf(sin(a), -cos(a), 0f), floatArrayOf(0f, 0f, 1f), floatArrayOf(L * .46f, L * .3f, L * .24f), floatArrayOf(m * 1.5f, q * 1.65f, q * 1.1f)))
    }
    val ta = h[0]; val to = h[1]; val dx = sin(ta) * (1 - 1.5f * to); val dy = -cos(ta) * (1 - .25f * to); val dz = .95f * to; val n = sqrt(dx * dx + dy * dy + dz * dz)
    out.add(.19f to chain(floatArrayOf(.36f, .26f, 0f), floatArrayOf(dx / n, dy / n, dz / n), floatArrayOf(-.75f, 0f, .66f), floatArrayOf(.42f, .31f, .26f), floatArrayOf(h[2] * 1.0f + .15f, h[3] * 1.3f, h[3] * .9f)))
    return out
}
private fun rot(p: P3, yaw: Float, pitch: Float, roll: Float): P3 {
    var x = p[0]; var y = p[1]; var z = p[2]; var c: Float; var s: Float; var t: Float
    c = cos(yaw); s = sin(yaw); t = x * c + z * s; z = -x * s + z * c; x = t
    c = cos(pitch); s = sin(pitch); t = y * c - z * s; z = y * s + z * c; y = t
    c = cos(roll); s = sin(roll); t = x * c - y * s; y = x * s + y * c; x = t
    return floatArrayOf(x, y, z)
}
private fun lerp3(A: P3, B: P3, k: Float) = floatArrayOf(A[0] + (B[0] - A[0]) * k, A[1] + (B[1] - A[1]) * k, A[2] + (B[2] - A[2]) * k)
private fun hull(pts: List<P3>): List<P3> {
    val s = pts.sortedWith(compareBy<P3>({ it[0] }, { it[1] }))
    fun cr(o: P3, a: P3, b: P3) = (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    val lo = mutableListOf<P3>(); val up = mutableListOf<P3>()
    for (p in s) { while (lo.size >= 2 && cr(lo[lo.size - 2], lo[lo.size - 1], p) <= 0) lo.removeAt(lo.size - 1); lo.add(p) }
    for (p in s.asReversed()) { while (up.size >= 2 && cr(up[up.size - 2], up[up.size - 1], p) <= 0) up.removeAt(up.size - 1); up.add(p) }
    up.removeAt(up.size - 1); lo.removeAt(lo.size - 1)
    return lo + up
}

private const val INK = 0xFF092E66.toInt()
private const val SHADE = 0xFFC3D4EC.toInt()
private const val GOLD = 0xFFEBA934.toInt()
private const val WHITE = 0xFFFFFFFF.toInt()

/** Offscreen layers, as the catalogue's two canvases plus a small one for the soft drop shadow. */
private class Layers(val w: Int, val h: Int) {
    val o: Bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888); val oc = android.graphics.Canvas(o)
    val m: Bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888); val mc = android.graphics.Canvas(m)
    val small: Bitmap = Bitmap.createBitmap(max(1, w / 8), max(1, h / 8), Bitmap.Config.ARGB_8888); val sc = android.graphics.Canvas(small)
    val fill = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply { style = android.graphics.Paint.Style.FILL }
    val line = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply { style = android.graphics.Paint.Style.STROKE; strokeCap = android.graphics.Paint.Cap.ROUND; strokeJoin = android.graphics.Paint.Join.ROUND }
    val blit = android.graphics.Paint(android.graphics.Paint.FILTER_BITMAP_FLAG)
    val dstOut = PorterDuffXfermode(PorterDuff.Mode.DST_OUT); val srcAtop = PorterDuffXfermode(PorterDuff.Mode.SRC_ATOP)
    val path = android.graphics.Path()
}

private class SignerState { var t = 0f; var idx = -2; var restart = true; var a: FloatArray? = null; var b: FloatArray? = null; var layers: Layers? = null }

/** Seconds a sequence takes (each sign plus its 0.32 s transition), at speed 1. */
internal fun sequenceSeconds(seq: List<String>) = seq.sumOf { (SIGNS[it]?.d?.plus(.32f) ?: 0f).toDouble() }.toFloat()

/**
 * AINGEL's hands around the orb. [cx], [cy], [r] are the orb centre and radius within the box (the signer's head).
 * [onSign] gets the index of the sign that starts, or -1 when the sequence ends.
 */
@Composable fun AingelSigner(width: Dp, height: Dp, cx: Dp, cy: Dp, r: Dp, seq: List<String>, playKey: Int, speed: Float = HANDS_SPEED, reducedMotion: Boolean = false, onSign: (Int) -> Unit = {}) {
    val st = remember { SignerState() }
    val sequence by rememberUpdatedState(seq.filter(::hasSign))
    val signCallback by rememberUpdatedState(onSign)
    val pace by rememberUpdatedState(speed)
    LaunchedEffect(playKey) { st.restart = true }
    var frame by remember { mutableLongStateOf(0L) }
    var dt by remember { mutableFloatStateOf(.016f) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(lifecycle) {
        if (!OrbAnimation.enabled) return@LaunchedEffect
        lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            var last = 0L
            while (true) withFrameNanos { now -> dt = if (last == 0L) .016f else min(.05f, (now - last) / 1e9f); last = now; frame = now }
        }
    }
    Canvas(Modifier.size(width, height).clearAndSetSemantics { }) {
        frame
        if (st.restart) { st.restart = false; st.t = 0f; st.idx = -2 }
        st.t += dt * pace * (if (reducedMotion) .6f else 1f)
        // Target pose for this instant (catalogue timing: 0.32 s between signs, 1.2 s pause at the end).
        var ta = REST_A; var tb = REST_B; var index = -1
        if (sequence.isNotEmpty()) {
            val durs = sequence.map { prepared(it).d }
            val cycle = durs.sum() + .32f * durs.size + 1.2f
            val tt = min(st.t, cycle); var acc = 0f
            for (i in sequence.indices) {
                val len = durs[i] + .32f
                if (tt < acc + len) { val sg = prepared(sequence[i]); val u = min(1f, max(0f, (tt - acc - .16f) / durs[i])); ta = sample(sg.A, u); tb = sample(sg.B, u); index = i; break }
                acc += len
            }
        }
        if (index != st.idx) { val was = st.idx; st.idx = index; if (index >= 0 || was >= 0) signCallback(index) }
        val k = 1 - exp(-dt / .085f)
        val a = st.a ?: ta.copyOf().also { st.a = it }; val b = st.b ?: tb.copyOf().also { st.b = it }
        for (j in 0 until 20) { a[j] += (ta[j] - a[j]) * k; b[j] += (tb[j] - b[j]) * k }
        val w = size.width.toInt(); val h = size.height.toInt()
        if (w <= 0 || h <= 0) return@Canvas
        val layers = st.layers?.takeIf { it.w == w && it.h == h } ?: Layers(w, h).also { st.layers = it }
        val R = r.toPx(); val ox = cx.toPx(); val oy = cy.toPx(); val dens = density
        drawIntoCanvas { canvas ->
            val target = canvas.nativeCanvas
            if (a[2] * min(1f, a[6]) >= b[2] * min(1f, b[6])) { drawHand(target, layers, b, -1f, ox, oy, R, dens); drawHand(target, layers, a, 1f, ox, oy, R, dens) }
            else { drawHand(target, layers, a, 1f, ox, oy, R, dens); drawHand(target, layers, b, -1f, ox, oy, R, dens) }
        }
    }
}

/** One hand, as the catalogue: silhouette, grooves, fingers in front, inner shade, golden cuff, soft shadow. */
private fun drawHand(target: android.graphics.Canvas, L: Layers, p: FloatArray, side: Float, cx: Float, cy: Float, R: Float, dens: Float) {
    val alpha = p[6]
    if (alpha < .02f) return
    val ps = R * .82f * p[2]; val ox = cx + p[0] * R; val oy = cy + p[1] * R; val yaw = p[3]; val pitch = p[4]; val roll = p[5]
    if (ps <= 1f) return
    val h = p.copyOfRange(7, 20)
    fun tf(q: P3): P3 { val rr = rot(q, yaw, pitch, roll); val k = 1 / (1 - rr[2] * .1f); return floatArrayOf(ox + side * rr[0] * ps * k, oy + rr[1] * ps * k, rr[2]) }
    val nrm = rot(floatArrayOf(0f, 0f, 1f), yaw, pitch, roll); val back = nrm[2] < -.15f
    val palm = hull(PALM.flatMap { q -> listOf(tf(floatArrayOf(q[0], q[1], .02f)), tf(floatArrayOf(q[0] * .94f, q[1] * .96f, -.24f))) })
    val cuff = hull(listOf(f2(-.39f, .44f), f2(.35f, .44f), f2(.37f, .68f), f2(-.41f, .68f)).flatMap { q -> listOf(tf(floatArrayOf(q[0], q[1], .1f)), tf(floatArrayOf(q[0], q[1], -.28f))) })
    val palmZ = (rot(floatArrayOf(0f, 0f, .02f), yaw, pitch, roll)[2] + rot(floatArrayOf(0f, 0f, -.24f), yaw, pitch, roll)[2]) / 2
    val fingers = handGeo(h).mapIndexed { i, (fw, pts) ->
        val thumb = i == 4
        Finger(i, thumb, fw * ps * (if (thumb) 1.28f else 1.16f), pts.map(::tf), if (thumb) 0f else (h[5 + i * 2] + h[6 + i * 2]) / 2)
    }
    val thumb = fingers[4]
    val web = listOf(tf(floatArrayOf(.42f, .28f, -.05f)), thumb.pts[0], thumb.pts[1], tf(floatArrayOf(.36f, -.32f, -.05f)))
    L.o.eraseColor(0); L.m.eraseColor(0)
    val ol = max(1.8f * dens / 2, ps * .062f); val il = max(1.3f * dens / 2, ps * .042f); val pw = ps * .2f
    fun poly(pts: List<P3>) = L.path.apply { reset(); pts.forEachIndexed { i, q -> if (i == 0) moveTo(q[0], q[1]) else lineTo(q[0], q[1]) }; close() }
    fun line(pts: List<P3>) = L.path.apply { reset(); moveTo(pts[0][0], pts[0][1]); for (i in 1 until pts.size) lineTo(pts[i][0], pts[i][1]) }
    fun inside(pt: P3, pl: List<P3>): Boolean {
        var c = false; var j = pl.size - 1
        for (i in pl.indices) { val a1 = pl[i]; val b1 = pl[j]; if ((a1[1] > pt[1]) != (b1[1] > pt[1]) && pt[0] < (b1[0] - a1[0]) * (pt[1] - a1[1]) / (b1[1] - a1[1]) + a1[0]) c = !c; j = i }
        return c
    }
    fun dist(A: P3, B: P3) = hypot(A[0] - B[0], A[1] - B[1])
    fun segDist(pt: P3, pts: List<P3>): Float {
        var best = 1e9f
        for (i in 0 until pts.size - 1) {
            val A = pts[i]; val B = pts[i + 1]; val vx = B[0] - A[0]; val vy = B[1] - A[1]; val l2 = (vx * vx + vy * vy).takeIf { it != 0f } ?: 1f
            val t = (((pt[0] - A[0]) * vx + (pt[1] - A[1]) * vy) / l2).coerceIn(0f, 1f)
            best = min(best, hypot(pt[0] - A[0] - vx * t, pt[1] - A[1] - vy * t))
        }
        return best
    }
    // A finger gets its own outline when it passes IN FRONT of the palm or another finger.
    fingers.forEach { f ->
        val probe = if (f.thumb) listOf(f.pts[2], f.pts[3]) else listOf(f.pts[2], f.pts[3], lerp3(f.pts[1], f.pts[2], .5f))
        f.over = probe.any { inside(it, palm) && it[2] > palmZ + .04f }
        fingers.forEach { g2 ->
            if (g2 !== f && !f.over && f.z > g2.z + .06f && probe.any { segDist(it, g2.pts) < (f.w + g2.w) * .42f }) f.over = true
        }
    }
    val base = fingers.filter { !it.over }; val over = fingers.filter { it.over }.sortedBy { it.z }
    fun shape(c: android.graphics.Canvas, col: Int, extra: Float, dx: Float, dy: Float, list: List<Finger>, xfer: PorterDuffXfermode? = null) {
        c.save(); c.translate(dx, dy)
        L.fill.color = col; L.line.color = col; L.fill.xfermode = xfer; L.line.xfermode = xfer
        L.line.strokeWidth = pw + extra; c.drawPath(poly(palm), L.fill); c.drawPath(L.path, L.line); c.drawPath(poly(cuff), L.fill); c.drawPath(L.path, L.line)
        L.line.strokeWidth = thumb.w * .85f + extra; c.drawPath(poly(web), L.fill); c.drawPath(L.path, L.line)
        list.forEach { f -> L.line.strokeWidth = f.w + extra; c.drawPath(line(f.pts), L.line) }
        c.restore(); L.fill.xfermode = null; L.line.xfermode = null
    }
    // 1 · single silhouette
    shape(L.oc, INK, ol * 2, 0f, 0f, base); shape(L.oc, WHITE, 0f, 0f, 0f, base)
    // 2 · grooves between touching fingers
    val nonThumb = base.filter { !it.thumb }.sortedBy { it.i }
    L.line.color = INK; L.line.strokeWidth = il
    for (n in 0 until nonThumb.size - 1) {
        val f1 = nonThumb[n]; val f2 = nonThumb[n + 1]
        if (f2.i != f1.i + 1) continue
        val e1 = if (f1.curl > .55f) f1.pts[1] else f1.pts[3]; val e2 = if (f2.curl > .55f) f2.pts[1] else f2.pts[3]
        val s1 = lerp3(f1.pts[0], f1.pts[1], .4f); val s2 = lerp3(f2.pts[0], f2.pts[1], .4f)
        if (dist(e1, e2) > (f1.w + f2.w) * .62f) continue
        val ms = lerp3(s1, s2, .5f); val me = lerp3(e1, e2, .5f); val mm = lerp3(ms, me, .82f)
        if (dist(ms, mm) < f1.w * .35f) continue
        L.oc.drawPath(line(listOf(ms, mm)), L.line)
    }
    // 3 · fingers in front, back to front
    over.forEach { f ->
        val seg = if (f.thumb) listOf(lerp3(f.pts[1], f.pts[2], .1f), f.pts[2], f.pts[3]) else listOf(lerp3(f.pts[0], f.pts[1], .35f), f.pts[1], f.pts[2], f.pts[3])
        L.line.color = INK; L.line.strokeWidth = f.w + il * 2; L.oc.drawPath(line(seg), L.line)
        L.line.color = WHITE; L.line.strokeWidth = f.w; L.oc.drawPath(line(seg), L.line)
        if (f.thumb) { L.line.strokeWidth = f.w * 1.05f; L.oc.drawPath(line(listOf(f.pts[0], f.pts[1], seg[0])), L.line) }
    }
    // 4 · volume: inner shade on the edge away from the light
    val k = max(2f, ps * .1f)
    shape(L.mc, SHADE, 0f, 0f, 0f, fingers); shape(L.mc, INK, 0f, -k, -k * 1.1f, fingers, L.dstOut)
    L.blit.alpha = (.9f * 255).toInt(); L.blit.xfermode = L.srcAtop; L.oc.drawBitmap(L.m, 0f, 0f, L.blit); L.blit.xfermode = null
    // 5 · golden cuff and back seams
    L.line.color = GOLD; L.line.strokeWidth = max(1.8f, ps * .08f); L.oc.drawPath(line(listOf(tf(floatArrayOf(-.4f, .57f, .1f)), tf(floatArrayOf(.36f, .57f, .1f)))), L.line)
    L.line.color = INK; L.line.strokeWidth = il * .8f; L.oc.drawPath(line(listOf(tf(floatArrayOf(-.39f, .45f, .1f)), tf(floatArrayOf(.35f, .45f, .1f)))), L.line)
    if (back && abs(nrm[2]) > .45f) {
        L.line.color = 0x80092E66.toInt(); L.line.strokeWidth = il * .8f
        listOf(floatArrayOf(.2f, .22f, .22f, -.18f), floatArrayOf(0f, .24f, 0f, -.22f), floatArrayOf(-.2f, .22f, -.22f, -.16f)).forEach { l ->
            L.oc.drawPath(line(listOf(tf(floatArrayOf(l[0], l[1], -.24f)), tf(floatArrayOf(l[2], l[3], -.24f)))), L.line)
        }
    }
    // Soft drop shadow (blurred copy, 22 %), then the hand.
    val al = min(1f, alpha)
    L.small.eraseColor(0); L.blit.alpha = 255
    L.sc.drawBitmap(L.o, Rect(0, 0, L.w, L.h), Rect(0, 0, L.small.width, L.small.height), L.blit)
    val sx = 5 * dens * p[2]; val sy = 13 * dens * p[2]
    L.blit.alpha = (.22f * al * 255).toInt()
    target.drawBitmap(L.small, null, RectF(sx, sy, sx + L.w, sy + L.h), L.blit)
    L.blit.alpha = (al * 255).toInt()
    target.drawBitmap(L.o, 0f, 0f, L.blit)
}
