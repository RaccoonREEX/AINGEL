package ec.aingel.mobile

import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test

class ProtocolTest {
    @Test fun companionPayloadContainsOnlySyntheticQuestionAndOptionalPublicTopic() {
        val question = companionPayload(" Synthetic question ", null)
        assertEquals(setOf("text", "synthetic"), question.keys().asSequence().toSet())
        assertEquals("Synthetic question", question.getString("text")); assertTrue(question.getBoolean("synthetic"))
        val topic = companionPayload("Question", CompanionTopic("Sleep", "en"))
        assertEquals(setOf("text", "synthetic", "topic_title", "topic_lang"), topic.keys().asSequence().toSet())
        assertEquals("Sleep", topic.getString("topic_title")); assertEquals("en", topic.getString("topic_lang"))
        listOf("", "a".repeat(1001)).forEach { value ->
            try { companionPayload(value, null); fail("Invalid question accepted") } catch (_: ApiFailure) { }
        }
        try { companionPayload("Question", CompanionTopic("Sleep", "other")); fail("Invalid topic language accepted") }
        catch (_: ApiFailure) { }
    }
    @Test fun signsOnlyLookUpFinalPhrasesInTheSpecificLanguageAndRejectUnsafeClipIds() {
        assertNull(eligibleSignPhrase("profile", "lsec", CaptionTurn("1", "hello", false)))
        assertNull(eligibleSignPhrase("profile", "other", CaptionTurn("1", "hello", true)))
        assertNull(eligibleSignPhrase("profile", "none", CaptionTurn("1", "hello", true)))
        assertNull(eligibleSignPhrase(null, "lsec", CaptionTurn("1", "hello", true)))
        assertNull(eligibleSignPhrase("profile", "lsec", CaptionTurn("1", " ", true)))
        assertNull(eligibleSignPhrase("profile", "lsec", CaptionTurn("1", "a".repeat(301), true)))
        assertNotNull(eligibleSignPhrase("profile", "lsec", CaptionTurn("1", "\uD83D\uDE00".repeat(300), true)))
        assertEquals(SignPhrase("profile", "lsec", "1", "hello"), eligibleSignPhrase("profile", "lsec", CaptionTurn("1", "hello", true)))
        assertEquals(SignPhrase("profile", "asl", "1", "hello"), eligibleSignPhrase("profile", "asl", CaptionTurn("1", "hello", true)))
        assertTrue(validSignClipId("sample_1-approved"))
        listOf("", "../private", "bad/path", "BAD", "-bad", "a".repeat(65)).forEach { assertFalse(validSignClipId(it)) }
    }
    @Test fun startingANewSpeechInvalidatesAPendingClipLookup() {
        val guard = SignLookupGuard()
        val priorPhrase = guard.advance()
        assertTrue(guard.isCurrent(priorPhrase))
        guard.advance()
        assertFalse(guard.isCurrent(priorPhrase))
        val latestPhrase = guard.advance()
        assertTrue(guard.isCurrent(latestPhrase))
    }
    @Test fun onlyHttpsMedlinePlusLinksAreOpened() {
        assertNotNull(verifiedMedlinePlusUrl("https://medlineplus.gov/spanish/diabetes.html"))
        listOf("http://medlineplus.gov/", "https://evil.example/", "https://medlineplus.gov.evil.example/",
            "https://medlineplus.gov@evil.example/", "https://user@medlineplus.gov/", "https://medlineplus.gov:444/")
            .forEach { assertNull(verifiedMedlinePlusUrl(it)) }
    }
    @Test fun supportChoiceUsesTheConfiguredPreferenceAndHasAQuietDefault() {
        assertEquals(R.string.support_contact, supportMessageResource("contact_caregiver"))
        assertEquals(R.string.support_quiet, supportMessageResource("quiet_reassurance"))
        assertEquals(R.string.support_quiet, supportMessageResource(null))
        assertEquals(R.string.support_quiet, supportMessageResource("unknown"))
    }
    @Test fun validationCodesAreParsedWithoutDisplayingArbitraryServerText() {
        assertEquals("face_photo_blurry", safeApiError(JSONArray().put("face_photo_blurry")))
        assertEquals("credentials_invalid", safeApiError(JSONObject().put("error", "credentials_invalid")))
        assertEquals("authentication_required", safeApiError(JSONObject().put("detail", "Authentication credentials were not provided.")))
        assertEquals("request_invalid", safeApiError(JSONArray().put("Private information from a server response")))
        assertEquals("request_invalid", safeApiError(JSONObject().put("detail", "")))
    }
    @Test fun releaseRequiresHttps() {
        assertEquals(DEFAULT_BACKEND, validBackend(DEFAULT_BACKEND, false))
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
    @Test fun onlyLegacyCleartextLoopbackServersAreMigrated() {
        listOf("http://127.0.0.1:8010/", "http://localhost:8010/", "http://10.0.2.2:8010/")
            .forEach { assertTrue(isLegacyLoopbackBackend(it)) }
        listOf(null, "https://aingel.mapatechstudio.com/", "https://localhost/", "https://other.example/",
            "http://localhost.attacker.test/", "http://192.168.1.1/")
            .forEach { assertFalse(isLegacyLoopbackBackend(it)) }
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
