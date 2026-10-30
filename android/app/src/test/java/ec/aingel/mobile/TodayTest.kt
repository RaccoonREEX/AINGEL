package ec.aingel.mobile

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.time.ZoneId
import java.time.ZonedDateTime

class TodayTest {
    private val zone = ZoneId.of("America/Guayaquil")
    private fun routine(id: String, at: String, done: Boolean = false, days: List<Int> = (0..6).toList()) =
        JSONObject().put("id", id).put("at", "$at:00").put("active", true).put("confirmed_today", done).put("weekdays", JSONArray(days))

    @Test fun nextIsFirstPendingAfterNow() {
        val now = ZonedDateTime.of(2026, 10, 27, 10, 35, 0, 0, zone) // Tuesday
        val s = summarizeToday(listOf(routine("b", "11:00"), routine("a", "07:30", done = true), routine("c", "16:30"), routine("x", "09:00", days = listOf(0))), zone, now)
        assertEquals(listOf("a", "b", "c"), s.list.map { it.getString("id") })
        assertEquals(1, s.done); assertEquals("b", s.next?.getString("id")); assertEquals(25, s.minutesUntil)
    }

    @Test fun overdueFallsBackToFirstPending() {
        val now = ZonedDateTime.of(2026, 10, 27, 23, 0, 0, 0, zone)
        val s = summarizeToday(listOf(routine("a", "08:00")), zone, now)
        assertEquals("a", s.next?.getString("id")); assertTrue(s.minutesUntil!! < 0)
    }

    @Test fun intentsAndEntities() {
        assertEquals(AskIntent.MEMORY, intentOf("¿Dónde dejé mis llaves?"))
        assertEquals("llaves", memoryEntity("¿Dónde dejé mis llaves?"))
        assertEquals("keys", memoryEntity("Where did I leave my keys?"))
        assertEquals(AskIntent.ROUTINES, intentOf("¿Qué tengo que hacer hoy?"))
        assertEquals(AskIntent.MESSAGES, intentOf("¿Qué me han dicho?"))
        assertEquals(AskIntent.UNKNOWN, intentOf("Cuéntame un chiste"))
        // Audit 29-10-2026: general questions that only share a word with an intent go to Meta.
        assertEquals(AskIntent.UNKNOWN, intentOf("¿Qué debo hacer si me duele el pecho?"))
        assertEquals(AskIntent.UNKNOWN, intentOf("¿Dónde queda el hospital?"))
        assertEquals(AskIntent.UNKNOWN, intentOf("Ayúdame a entender la diabetes"))
        assertEquals(AskIntent.MEMORY, intentOf("Where is my phone?"))
        assertEquals(AskIntent.SUPPORT, intentOf("Necesito ayuda"))
    }
}
