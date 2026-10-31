package ec.aingel.mobile

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PrivateMediaTest {
    private fun profile(role: String = "owner", subject: String = "self") =
        JSONObject().put("id", "profile-1").put("locale", "es-EC").put("role", role).put("subject_status", subject)
            .put("consents", JSONObject().put("camera", true).put("microphone", true).put("meta_data", true))  // legacy: no effect

    @Test fun privateImageRequiresExplicitOwnerDeclarationAndSeparateConsent() {
        assertEquals("true", imageRequestFields(profile(), "profile-1", false)["private_test"])
        assertEquals("false", imageRequestFields(profile(), "profile-1", false)["synthetic"])
        assertFalse(imageRequestFields(profile(), null, false).containsKey("private_test"))
        for (p in listOf(profile(role = "caregiver"), profile(subject = "pending_confirmation"), profile(subject = "pending_consent"))) {
            try { imageRequestFields(p, "profile-1", false); fail("private image accepted without authorization") }
            catch (e: ApiFailure) { assertEquals("private_test_consent_required", e.code) }
        }
        assertFalse(privateMediaAllowed(profile(), "other-profile", "camera"))
        assertFalse(privateMediaAllowed(profile(subject = "subject_linked"), "profile-1", "microphone"))
    }

    @Test fun syntheticFixtureNeverClaimsPrivateTest() {
        val fields = imageRequestFields(profile(), "profile-1", true)
        assertEquals("true", fields["synthetic"])
        assertFalse(fields.containsKey("private_test"))
    }

    @Test fun captionDeclarationIsExplicitAndPreservesOrdinaryRequest() {
        val selected = captionStartPayload("es-EC", "profile-1", true)
        assertTrue(selected.getBoolean("private_test")); assertFalse(selected.getBoolean("synthetic"))
        assertEquals("profile-1", selected.getString("profile"))
        val ordinary = captionStartPayload("es-EC", "profile-1", false)
        assertFalse(ordinary.has("private_test")); assertFalse(ordinary.has("synthetic"))
    }
}
