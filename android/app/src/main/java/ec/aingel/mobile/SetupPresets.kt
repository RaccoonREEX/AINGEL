package ec.aingel.mobile

import org.json.JSONObject

/** Onboarding answers (ONBOARDING_Y_PRESETS v1.1.0). Levels are 0-based like the design. */
internal data class SetupAnswers(
    val vision: Int? = null, val hearing: Int? = null, val autism: Int? = null, val dementia: Int? = null,
    val signs: Boolean = false, val signLanguage: String = "lsec", val reads: String = "yes", val addressing: String = "usted",
)

/** Preset keys the server stores today; the others are shown as "coming soon" and kept in the notes. */
internal val SUPPORTED_PRESETS = setOf("visual_assistance", "voice_output", "large_text", "high_contrast", "hearing_assistance",
    "sign_language", "simple_instructions", "reduced_motion", "one_step", "memory_assistance", "speech_pace_slow", "easy_read", "default")

internal fun presetKeys(a: SetupAnswers): List<String> = buildList {
    a.vision?.let { add("visual_assistance"); if (it >= 2) { add("voice_output"); add("voice_first") } else { add("large_text"); add("high_contrast") } }
    a.hearing?.let { add("hearing_assistance"); if (it >= 2) add("text_first"); add("haptic_alerts") }
    if (a.signs) { add("sign_language"); if (a.reads == "no") add("no_reading"); if (a.reads == "difficulty") add("easy_read") }
    a.autism?.let { add("simple_instructions"); add("reduced_motion"); if (it >= 1) add("one_step"); if (it >= 2) add("routine_preview") }
    a.dementia?.let { add("memory_assistance"); add("speech_pace_slow"); if (it >= 1) add("can_configure"); if (it >= 2) add("simplified_home") }
    if (isEmpty()) add("default")
}

internal fun presetPreferences(a: SetupAnswers): JSONObject {
    val keys = presetKeys(a).toSet()
    val none = keys == setOf("default")
    return JSONObject()
        .put("visual_assistance", none || "visual_assistance" in keys)
        .put("hearing_assistance", none || "hearing_assistance" in keys)
        .put("memory_assistance", none || "memory_assistance" in keys)
        .put("large_text", "large_text" in keys).put("high_contrast", "high_contrast" in keys)
        .put("voice_output", "voice_output" in keys).put("reduced_motion", "reduced_motion" in keys)
        .put("simple_instructions", "simple_instructions" in keys)
}

/** Merges the answers into the server's communication object without dropping its other fields. */
internal fun presetCommunication(current: JSONObject, a: SetupAnswers, preferredName: String): JSONObject =
    JSONObject(current.toString())
        .put("preferred_name", preferredName.trim().take(100))
        .put("addressing", when (a.addressing) { "usted" -> "formal"; "tu" -> "informal"; else -> "preferred_name" })
        .put("pace", if (a.dementia != null) "slow" else "standard")
        .put("interaction", if ((a.autism ?: -1) >= 1) "one_step" else "standard")
        .put("sentence_length", if (a.signs && a.reads != "yes") "short" else current.optString("sentence_length", "short"))
        .put("sign_language", if (a.signs) a.signLanguage else "none")
