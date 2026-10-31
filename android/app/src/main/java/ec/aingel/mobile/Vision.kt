package ec.aingel.mobile

import org.json.JSONObject

/**
 * AINGEL 3.0 deep vision (backend assistance.vision, `vision/`). The server picks the detail level and the kind of
 * image from the question (a drawing, a face, a page…) unless the request names them; each answer opens a short
 * session so follow-ups («¿Y sus ojos?») are answered about the same picture without sending it again.
 */
internal const val VISION_PATH = "vision/"

/** A new picture: the person's own authorization fields ([imageRequestFields]) plus what they asked. */
internal fun visionFields(base: MutableMap<String, String>, question: String?, level: String? = null): Map<String, String> = base.apply {
    question?.trim()?.takeIf { it.isNotEmpty() }?.let { put("question", it.take(600)) }
    level?.let { put("detail_level", it) }
}

/** A follow-up: only the session, the language and the question. The server rechecks the person's consent, so no
 * profile or test declaration is sent again (it refuses them next to a session). */
internal fun visionFollowUpFields(locale: String, session: String, question: String?, level: String? = null): Map<String, String> =
    buildMap {
        put("locale", locale); put("session", session)
        question?.trim()?.takeIf { it.isNotEmpty() }?.let { put("question", it.take(600)) }
        level?.let { put("detail_level", it) }
    }

/** The follow-up session of an answer and when it ends on this phone's clock, or null. */
internal fun visionSessionOf(result: JSONObject, now: Long): Pair<String, Long>? {
    val token = result.optString("session").takeIf { it.length in 16..64 } ?: return null
    val seconds = result.optLong("session_seconds", 0).coerceIn(0, 3600)
    return if (seconds == 0L) null else token to now + seconds * 1000 - 5_000
}

/** Errors that end a follow-up session: it expired, or the person's decisions changed. */
internal fun endsVisionSession(code: String?) = code in setOf("visual_session_expired", "consent_changed", "camera_consent_revoked", "privacy_review_required")

/**
 * [text] in parts the speech engine accepts (Android limits one utterance to about 4000 characters): whole
 * paragraphs when they fit, else whole sentences, and only a sentence longer than [max] is cut.
 */
internal fun speechChunks(text: String, max: Int = 3000): List<String> {
    val chunks = mutableListOf<String>()
    var current = StringBuilder()
    fun flush() { if (current.isNotBlank()) chunks.add(current.toString().trim()); current = StringBuilder() }
    fun add(piece: String, separator: String) {
        if (current.isNotEmpty() && current.length + separator.length + piece.length > max) flush()
        if (current.isNotEmpty()) current.append(separator)
        current.append(piece)
    }
    for (paragraph in text.split(Regex("\\n\\s*\\n")).map { it.trim() }.filter { it.isNotEmpty() }) {
        if (paragraph.length <= max) { add(paragraph, "\n\n"); continue }
        paragraph.split(Regex("(?<=[.!?…])\\s+")).forEachIndexed { index, sentence ->
            val separator = if (index == 0) "\n\n" else " "
            if (sentence.length <= max) add(sentence, separator) else sentence.chunked(max).forEach { add(it, separator) }
        }
    }
    flush()
    return chunks.ifEmpty { listOf(text) }
}
