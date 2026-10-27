package ec.aingel.mobile

import org.json.JSONObject

internal data class CompanionTopic(val title: String, val language: String)

/** This payload deliberately contains only a synthetic prompt and an optional public topic. */
internal fun companionPayload(text: String, topic: CompanionTopic?): JSONObject {
    val question = text.trim()
    if (question.isEmpty() || question.codePointCount(0, question.length) > 1000) throw ApiFailure("companion_input_invalid")
    val result = JSONObject().put("text", question).put("synthetic", true)
    if (topic != null) {
        if (topic.title.isBlank() || topic.language !in setOf("es", "en")) throw ApiFailure("companion_input_invalid")
        result.put("topic_title", topic.title).put("topic_lang", topic.language)
    }
    return result
}
