package ec.aingel.mobile

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class SignRegistryTest {
    private val hola = "1".repeat(64)
    private val local = mapOf("hola" to hola, "agua" to "2".repeat(64))

    private fun registry(vararg signs: Pair<String, Pair<String, String?>>) = JSONObject().put("signs", JSONObject().apply {
        signs.forEach { (id, state) -> put(id, JSONObject().put("status", state.first).put("fingerprint", state.second ?: JSONObject.NULL)) }
    })

    @Test fun aValidationCountsOnlyForTheAnimationItReviewed() {
        val reviewed = registry("hola" to ("validated" to hola), "agua" to ("validated" to "0".repeat(64)), "casa" to ("in_review" to null))
        assertEquals(setOf("hola"), validatedSigns(reviewed, local))
        assertEquals(emptySet<String>(), validatedSigns(null, local))
    }

    @Test fun onlyWholeValidatedSentencesMoveTheHands() {
        val ok = setOf("hola", "gracias")
        assertEquals(SignPlan.Play(illustrative = false), planSigns(listOf("hola", "gracias"), ok, illustrative = false))
        val partial = planSigns(listOf("hola", "agua"), ok, illustrative = false) as SignPlan.Blocked
        assertTrue(partial.partial)
        assertEquals(1 to 2, partial.validated to partial.total)
        assertEquals(SignPlan.Blocked(0, 1), planSigns(listOf("agua"), emptySet(), illustrative = false))
        assertEquals(SignPlan.Play(illustrative = true), planSigns(listOf("agua"), emptySet(), illustrative = true))
    }

    @Test fun theShippedFingerprintsCoverEveryAnimatedSign() {
        val prints = fingerprintsFrom(File("src/main/assets/hands3d/signFingerprints.json").readText())
        val animated = JSONObject(File("src/main/assets/hands3d/signs3d.json").readText()).getJSONObject("signs").keys().asSequence().toSet()
        // Every animated sign but AINGEL's own interface gesture (listening) has a fingerprint.
        assertEquals(animated - "listen_ear", prints.keys)
        assertTrue(prints.values.all { Regex("[0-9a-f]{64}").matches(it) })
    }
}
