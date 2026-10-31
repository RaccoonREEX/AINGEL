package ec.aingel.mobile

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VisionTest {
    @Test fun newPictureCarriesTheAuthorizationAndTheQuestion() {
        val fields = visionFields(mutableMapOf("locale" to "es-EC", "profile" to "p", "private_test" to "true"), "  ¿Cómo es su cara?  ", "deep")
        assertEquals(mapOf("locale" to "es-EC", "profile" to "p", "private_test" to "true", "question" to "¿Cómo es su cara?", "detail_level" to "deep"), fields)
        assertFalse(visionFields(mutableMapOf("locale" to "es-EC"), " ").containsKey("question"))
    }

    @Test fun followUpSendsOnlyTheSessionLanguageAndQuestion() {
        val fields = visionFollowUpFields("es-EC", "t".repeat(32), "¿Y sus ojos?")
        assertEquals(setOf("locale", "session", "question"), fields.keys)
        assertEquals(600, visionFollowUpFields("es-EC", "s", "a".repeat(900))["question"]!!.length)
    }

    @Test fun sessionEndsBeforeTheServersDoes() {
        val token = "x".repeat(32)
        assertEquals(token to 1_000L + 900_000 - 5_000, visionSessionOf(JSONObject().put("session", token).put("session_seconds", 900), 1_000L))
        assertNull(visionSessionOf(JSONObject().put("session", "short").put("session_seconds", 900), 0))
        assertNull(visionSessionOf(JSONObject().put("session", token), 0))
        assertTrue(endsVisionSession("consent_changed"))
        assertFalse(endsVisionSession("meta_unavailable"))
    }

    @Test fun longTextIsSpokenInWholeParagraphsAndSentences() {
        val paragraph = "Una frase de prueba con varias palabras. ".repeat(40).trim()  // ~1600 characters
        val text = listOf(paragraph, paragraph, paragraph).joinToString("\n\n")
        val parts = speechChunks(text, max = 3000)
        assertEquals(3, parts.size)
        assertTrue(parts.all { it.length <= 3000 })
        assertEquals(text.replace(Regex("\\s+"), " "), parts.joinToString(" ").replace(Regex("\\s+"), " "))
        val long = speechChunks("Una frase. ".repeat(500), max = 300)
        assertTrue(long.all { it.length <= 300 && it.endsWith(".") })
        assertEquals(listOf("Hola."), speechChunks("Hola."))
    }
}
