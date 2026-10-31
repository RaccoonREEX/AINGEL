package ec.aingel.mobile

import org.json.JSONArray
import org.json.JSONObject

/** The server trusts this declaration; only explicit user opt-in may set it. */
internal fun conversationPayload(turns: JSONArray, actions: List<String>, synthetic: Boolean): JSONObject =
    JSONObject().put("turns", turns).put("actions", JSONArray(actions)).apply {
        if (synthetic) put("synthetic", true)
    }
