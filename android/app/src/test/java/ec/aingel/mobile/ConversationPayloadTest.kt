package ec.aingel.mobile

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ConversationPayloadTest {
    @Test fun declarationIsPresentOnlyWhenExplicitlyEnabled() {
        val turns = JSONArray().put(JSONObject().put("role", "user").put("text", "Ejemplo inventado"))
        val normal = conversationPayload(turns, emptyList(), false)
        assertFalse(normal.has("synthetic"))
        val declared = conversationPayload(turns, listOf("open_sign_translator"), true)
        assertTrue(declared.getBoolean("synthetic"))
        assertEquals("Ejemplo inventado", declared.getJSONArray("turns").getJSONObject(0).getString("text"))
        assertEquals("open_sign_translator", declared.getJSONArray("actions").getString(0))
    }
}
