package ec.aingel.mobile

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class TerritoryTest {
    @Test fun theAnswerComesOnlyFromTheSession() {
        // Signed out: nothing to gate yet.
        assertEquals(TERRITORY_OUTSIDE, territoryOf(JSONObject().put("user", JSONObject.NULL)))
        // Not answered for the current policy version (null or missing): the gate asks.
        assertEquals("", territoryOf(JSONObject().put("user", JSONObject().put("username", "ana").put("territory", JSONObject.NULL))))
        assertEquals("", territoryOf(JSONObject().put("user", JSONObject().put("username", "ana"))))
        assertEquals(TERRITORY_INSIDE, territoryOf(JSONObject().put("user", JSONObject().put("territory", TERRITORY_INSIDE))))
        assertEquals(TERRITORY_OUTSIDE, territoryOf(JSONObject().put("user", JSONObject().put("territory", TERRITORY_OUTSIDE))))
    }

    @Test fun registrationSendsTheAnswerWithThePolicyVersion() {
        val body = territoryFields(JSONObject().put("username", "ana"), TERRITORY_OUTSIDE, "2026-10-12")
        assertEquals("outside_restricted", body.getString("territory"))
        assertEquals("2026-10-12", body.getString("territory_version"))
        assertEquals("ana", body.getString("username"))
    }

    @Test fun theListFollowsTheAppLanguage() {
        val session = JSONObject().put("restricted_territories", JSONObject().put("es-EC", "Cuba, Venezuela").put("en-US", "Cuba, Venezuela (en)"))
        assertEquals("Cuba, Venezuela", restrictedList(session, spanish = true))
        assertEquals("Cuba, Venezuela (en)", restrictedList(session, spanish = false))
        assertEquals("", restrictedList(null, spanish = true))
    }
}
