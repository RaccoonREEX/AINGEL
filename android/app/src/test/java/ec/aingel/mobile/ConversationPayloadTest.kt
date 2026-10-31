package ec.aingel.mobile

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ConversationPayloadTest {
    @Test fun realConversationNeverDeclaresItselfSynthetic() {
        val turns = JSONArray().put(JSONObject().put("role", "user").put("text", "Ejemplo inventado"))
        val payload = conversationPayload(turns, listOf("open_sign_translator"))
        assertEquals(setOf("turns", "actions"), payload.keys().asSequence().toSet())
        assertEquals("Ejemplo inventado", payload.getJSONArray("turns").getJSONObject(0).getString("text"))
        assertEquals("open_sign_translator", payload.getJSONArray("actions").getString(0))
    }

    @Test fun syntheticDemoSendsOnlyAServerFixtureId() {
        val payload = fixtureConversationPayload("greeting", "es-EC")
        assertEquals(setOf("fixture", "locale"), payload.keys().asSequence().toSet())
        assertEquals("greeting", payload.getString("fixture"))
    }
}
