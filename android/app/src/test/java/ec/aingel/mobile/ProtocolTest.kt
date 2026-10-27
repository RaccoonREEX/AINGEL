package ec.aingel.mobile

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ProtocolTest {
    @Test fun releaseRequiresHttps() {
        assertNull(validBackend("http://127.0.0.1:8010/", false))
        assertNull(validBackend("http://example.com/", false))
        assertEquals("https://care.example/", validBackend("https://care.example", false))
    }
    @Test fun debugHttpIsLoopbackOnly() {
        assertNotNull(validBackend("http://127.0.0.1:8010/", true))
        assertNotNull(validBackend("http://10.0.2.2:8010/", true))
        assertNull(validBackend("http://192.168.1.4/", true))
        assertNull(validBackend("http://localhost.attacker.test/", true))
    }
    @Test fun backendRejectsEmbeddedSecretsOrPaths() {
        listOf("https://user:password@care.example/", "https://care.example/?token=secret",
            "https://care.example/#secret", "https://care.example/api/").forEach { assertNull(validBackend(it, true)) }
    }
    @Test fun cumulativePartialReplacesInsteadOfDuplicating() {
        val first = reduceCaption(emptyList(), JSONObject("""{"type":"transcript","turnId":"one","transcript":"hello"}"""))
        val next = reduceCaption(first, JSONObject("""{"type":"transcript","turnId":"one","transcript":"hello world"}"""))
        assertEquals(1, next.size); assertEquals("hello world", next.single().text)
    }
    @Test fun completionWithoutTextKeepsPartialAndFinalizes() {
        val partial = listOf(CaptionTurn("one", "a sentence", false))
        val next = reduceCaption(partial, JSONObject("""{"type":"speechComplete","turnId":"one"}"""))
        assertEquals("a sentence", next.single().text); assertTrue(next.single().final)
        assertEquals(next, reduceCaption(next, JSONObject("""{"type":"transcript","turnId":"one","transcript":"late partial"}""")))
    }
    @Test fun captionHistoryIsBoundedAndIgnoresUntrustedKinds() {
        val history = (1..100).map { CaptionTurn(it.toString(), "synthetic", true) }
        assertEquals(history, reduceCaption(history, JSONObject("""{"type":"error","transcript":"not speech"}""")))
        val next = reduceCaption(history, JSONObject("""{"type":"speechComplete","turnId":"101","transcript":"last"}"""))
        assertEquals(100, next.size); assertEquals("2", next.first().id); assertEquals("101", next.last().id)
    }
}
