package ec.aingel.mobile

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class SetupPresetsTest {
    @Test fun noConditionsKeepsStandardTools() {
        assertEquals(listOf("default"), presetKeys(SetupAnswers()))
        val prefs = presetPreferences(SetupAnswers())
        assertTrue(prefs.getBoolean("visual_assistance") && prefs.getBoolean("hearing_assistance") && prefs.getBoolean("memory_assistance"))
        assertFalse(prefs.getBoolean("large_text"))
    }

    @Test fun profoundHearingAndEarlyDementiaMatchTheDesign() {
        val answers = SetupAnswers(hearing = 3, dementia = 0, signs = true, signLanguage = "lsec", reads = "difficulty")
        assertEquals(listOf("hearing_assistance", "text_first", "haptic_alerts", "sign_language", "easy_read", "memory_assistance", "speech_pace_slow"), presetKeys(answers))
        val prefs = presetPreferences(answers)
        assertTrue(prefs.getBoolean("hearing_assistance")); assertTrue(prefs.getBoolean("memory_assistance"))
        assertFalse(prefs.getBoolean("visual_assistance"))
        val comm = presetCommunication(JSONObject().put("distress", "contact_caregiver").put("sentence_length", "standard"), answers, " Rosa ")
        assertEquals("Rosa", comm.getString("preferred_name")); assertEquals("formal", comm.getString("addressing"))
        assertEquals("slow", comm.getString("pace")); assertEquals("short", comm.getString("sentence_length"))
        assertEquals("lsec", comm.getString("sign_language")); assertEquals("contact_caregiver", comm.getString("distress"))
    }

    @Test fun severeVisionAndAutismLevels() {
        val keys = presetKeys(SetupAnswers(vision = 2, autism = 2))
        assertTrue("voice_output" in keys && "voice_first" in keys && "large_text" !in keys)
        assertTrue("one_step" in keys && "routine_preview" in keys)
        assertEquals("one_step", presetCommunication(JSONObject(), SetupAnswers(autism = 1), "").getString("interaction"))
    }

    @Test fun levelShapingMatchesWeb() {
        assertEquals(0f, shapeLevel(0.01f), 0f)
        assertEquals(1f, shapeLevel(0.3f), 0f)
        assertTrue(shapeLevel(0.05f) in 0.3f..0.7f)
        assertEquals(0f, pcmLevel(ShortArray(16), 16), 0f)
    }
}
