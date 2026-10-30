package ec.aingel.mobile

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HomeModesTest {
    @Test fun menuFollowsTheAccountProfile() {
        val deaf = homeProfile(JSONObject().put("hearing_assistance", true).put("visual_assistance", false))
        assertEquals(listOf(HomeMode.HEAR, HomeMode.SEE, HomeMode.WRITE), deaf.modes)
        val blind = homeProfile(JSONObject().put("hearing_assistance", false).put("visual_assistance", true))
        assertEquals(listOf(HomeMode.DESCRIBE, HomeMode.WATCH), blind.modes)
        assertEquals(5, homeProfile(JSONObject()).modes.size)
        assertTrue(homeProfile(JSONObject().put("hearing_assistance", false).put("visual_assistance", false)).modes.isEmpty())
    }

    @Test fun wakePhraseIsRecognisedAsDictationWritesIt() {
        listOf("Hola AINGEL", "hola ángel", "Ola Aingel", "hola, angel").forEach { assertTrue(it, VoiceControl.heard(it, "Hola AINGEL")) }
        assertFalse(VoiceControl.heard("ángel", "Hola AINGEL"))
        assertTrue(VoiceControl.heard("ángel", "AINGEL"))
        assertFalse(VoiceControl.heard("hola Ana", "Hola AINGEL"))
        assertFalse(VoiceControl.heard("evangelio", "AINGEL"))
    }

    @Test fun questionAfterThePhraseIsKept() {
        assertEquals("qué tengo que hacer hoy", VoiceControl.afterPhrase("Hola AINGEL qué tengo que hacer hoy"))
        assertEquals("¿qué me han dicho?", VoiceControl.afterPhrase("hola Ángel, ¿qué me han dicho?"))
        assertEquals("", VoiceControl.afterPhrase("Hola AINGEL"))
    }

    @Test fun cameraRequestsAreAingelsOwnJob() {
        // Phrases said on the phone on 29-10-2026, which Meta had refused («No tengo acceso a su cámara»).
        assertEquals(CameraCommand.SEE, cameraCommandOf("pero deberías de activar la opción para que tú veas por la cámara del celular lo que yo no puedo ver"))
        assertEquals(CameraCommand.SEE, cameraCommandOf("dime estás viendo lo que yo veo"))
        assertEquals(CameraCommand.SEE, cameraCommandOf("¿Qué ves?"))
        assertEquals(CameraCommand.WATCH, cameraCommandOf("quiero que por favor actives la opción de vista continua"))
        assertEquals(CameraCommand.WATCH_STOP, cameraCommandOf("detén la vigilancia"))
        assertEquals(null, cameraCommandOf("¿Hay algún tipo de restaurante cerca del Quicentro?"))
        assertEquals(null, cameraCommandOf("yo soy ciego"))
        // Audit 29-10-2026: questions that only mention describing or looking stay with AINGEL.
        assertEquals(null, cameraCommandOf("descríbeme qué tengo hoy"))
        assertEquals(null, cameraCommandOf("look at my schedule"))
        assertEquals(CameraCommand.SEE, cameraCommandOf("Describe lo que hay delante"))
        assertEquals(CameraCommand.WATCH_STOP, cameraCommandOf("apaga la cámara"))
    }

    @Test fun conversationHistoryFitsTheServerLimit() {
        val long = "x".repeat(1000)
        val pairs = List(5) { "q$it$long" to "a$it$long" }
        val kept = boundedHistory(pairs, long)
        assertTrue(long.length + kept.sumOf { it.first.length + it.second.length } <= 8000)
        assertEquals("q4", kept.last().first.take(2))  // the newest pairs stay
        assertEquals(pairs, boundedHistory(pairs, "hola", limit = 20_000))
    }

    @Test fun busyMicrophoneIsRetriedNotReportedAsUnsupported() {
        // 29-10-2026: «Escuchar y traducir» right after the «Hola AINGEL» listener said the phone could not recognize speech.
        listOf(android.speech.SpeechRecognizer.ERROR_RECOGNIZER_BUSY, android.speech.SpeechRecognizer.ERROR_CLIENT,
            android.speech.SpeechRecognizer.ERROR_SERVER_DISCONNECTED).forEach { assertTrue(transientRecognizerError(it)) }
        listOf(android.speech.SpeechRecognizer.ERROR_NO_MATCH, android.speech.SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS,
            android.speech.SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED).forEach { assertFalse(transientRecognizerError(it)) }
    }

    @Test fun recognizedFamilyIsSaidBeforeTheDescription() {
        val scene = JSONObject("""{"text":"Lleva un suéter verde.","people":[{"id":"f1","line":"Parece ser tu hijo David."}]}""")
        assertEquals("Parece ser tu hijo David. Lleva un suéter verde.", withKnownPeople(scene, scene.optString("text")))
        // Continuous watching: not repeated while the same person stays in front.
        assertEquals("Lleva un suéter verde.", withKnownPeople(scene, scene.optString("text"), skip = setOf("f1")))
        assertEquals("Hay una mesa.", withKnownPeople(JSONObject("""{"text":"Hay una mesa."}"""), "Hay una mesa."))
    }
}
