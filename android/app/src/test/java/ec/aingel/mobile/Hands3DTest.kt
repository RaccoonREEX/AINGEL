package ec.aingel.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class Hands3DTest {
    private fun near(expected: Float, actual: Float) = assertEquals(expected, actual, 1e-4f)

    @Test fun eulerMatchesThreeJs() {
        // Values from THREE.Quaternion().setFromEuler(new THREE.Euler(x°, y°, z°, order)).
        val xyz = qEuler(floatArrayOf(-25f, 20f, 15f), "XYZ")
        near(-0.1892f, xyz.x); near(0.1959f, xyz.y); near(0.0882f, xyz.z); near(0.9581f, xyz.w)
        val zxy = qEuler(floatArrayOf(18f, -40f, -32f), "ZXY")
        near(0.0482f, zxy.x); near(-0.3652f, zxy.y); near(-0.3073f, zxy.z); near(0.8774f, zxy.w)
    }

    @Test fun slerpKeepsEndsAndUnitLength() {
        val a = qEuler(floatArrayOf(0f, 0f, 0f), "XYZ"); val b = qEuler(floatArrayOf(90f, 0f, 0f), "XYZ"); val out = Quat()
        qSlerp(a, b, 0f, out).let { near(a.x, it.x); near(a.w, it.w) }
        qSlerp(a, b, 1f, out).let { near(b.x, it.x); near(b.w, it.w) }
        qSlerp(a, b, .5f, out).let { near(1f, it.x * it.x + it.y * it.y + it.z * it.z + it.w * it.w); near(0.3827f, it.x); near(0.9239f, it.w) }
    }

    @Test fun exportedSignsCoverTheLexiconAndBoard() {
        val json = File("src/main/assets/hands3d/signs3d.json").readText()
        val ids = buildList {
            addAll(SIGN_BOARD); addAll("abcdefghijklmnñopqrstuvwxyz".map { it.toString() }); addAll((0..10).map { "n$it" })
            listOf("Mañana quiero ir al parque con mi hija", "¿Tienes dolor?", "Necesito mi medicina, por favor").forEach { addAll(buildSentence(it)!!.seq) }
        }
        ids.distinct().forEach { assertTrue("missing 3D sign $it", json.contains("\"$it\":[")) }
    }
}
