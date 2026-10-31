package ec.aingel.mobile

import org.json.JSONArray
import org.json.JSONObject

/** The person's own conversation: it reaches Meta only under their authorization, which the server checks. */
internal fun conversationPayload(turns: JSONArray, actions: List<String>): JSONObject =
    JSONObject().put("turns", turns).put("actions", JSONArray(actions))

/** Synthetic demo: only the id of a question the server wrote (assistance.synthetic); nothing typed or said. */
internal fun fixtureConversationPayload(fixture: String, locale: String): JSONObject =
    JSONObject().put("fixture", fixture).put("locale", locale)
