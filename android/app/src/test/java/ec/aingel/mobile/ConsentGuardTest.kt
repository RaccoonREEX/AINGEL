package ec.aingel.mobile

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ConsentGuardTest {
    @Test fun onlyAReallyOpenCaptureIsReportedAsStopped() {
        // A mode just chosen and still checking (nothing open): no "stopped", its own check says "not authorized".
        assertNull(stoppedCapture(cameraOpen = false, cameraAllowed = false, micOpen = false, micAllowed = false))
        // Open and still allowed: nothing to report.
        assertNull(stoppedCapture(cameraOpen = true, cameraAllowed = true, micOpen = true, micAllowed = true))
        // Open and no longer allowed: that one is closed and reported.
        assertEquals(Capture.CAMERA, stoppedCapture(cameraOpen = true, cameraAllowed = false, micOpen = false, micAllowed = false))
        assertEquals(Capture.MICROPHONE, stoppedCapture(cameraOpen = false, cameraAllowed = false, micOpen = true, micAllowed = false))
    }

    private fun consent(epoch: Long, camera: String, microphone: String) = JSONObject().put("subject_status", "self").put("epoch", epoch).put("is_subject", true)
        .put("purposes", JSONArray()
            .put(JSONObject().put("id", "camera_local").put("to", "local").put("status", camera))
            .put(JSONObject().put("id", "microphone_local").put("to", "local").put("status", microphone))
            .put(JSONObject().put("id", "meta_photos").put("to", "meta").put("status", "granted")))

    private fun session(username: String, accepted: Boolean?) = JSONObject().put("speech_service_version", "2026-10-30")
        .put("user", JSONObject().put("username", username).apply { if (accepted != null) put("speech_service", accepted) })

    @Test fun onlyAnExplicitGrantStartsEachCapture() {
        for (capture in Capture.entries) {
            val granted = if (capture == Capture.CAMERA) consent(1, "granted", "declined") else consent(1, "declined", "granted")
            assertTrue(mayStart(granted, capture))
            for (status in listOf("declined", "revoked", "pending", "")) {
                val other = if (capture == Capture.CAMERA) consent(1, status, "granted") else consent(1, "granted", status)
                assertFalse("$capture $status", mayStart(other, capture))
            }
            assertFalse(mayStart(null, capture))
            assertFalse(mayStart(JSONObject(), capture))
            assertFalse(mayStart(JSONObject().put("purposes", JSONArray().put(JSONObject().put("id", "meta_photos").put("status", "granted"))), capture))
        }
        // The camera grant does not open the microphone, nor the other way round.
        assertFalse(mayStart(consent(1, "granted", "pending"), Capture.MICROPHONE))
        assertFalse(mayStart(consent(1, "pending", "granted"), Capture.CAMERA))
    }

    @Test fun purposeStatusReadsTheDecisionOrMissing() {
        val c = consent(3, "revoked", "pending")
        assertEquals("revoked", purposeStatus(c, "camera_local"))
        assertEquals("pending", purposeStatus(c, "microphone_local"))
        assertEquals("missing", purposeStatus(c, "meta_voice"))
        assertEquals("missing", purposeStatus(null, "camera_local"))
        assertEquals("missing", purposeStatus(JSONObject().put("purposes", JSONArray().put("camera_local")), "camera_local"))
    }

    @Test fun epochChangeStopsOnlyWhenTheCaptureIsNoLongerGranted() {
        val before = consent(4, "granted", "granted")
        // Another purpose was declined (the epoch moved) but the grant is kept: keep going.
        assertFalse(mustStop(before, consent(5, "granted", "granted"), Capture.CAMERA))
        assertFalse(mustStop(before, consent(5, "granted", "granted"), Capture.MICROPHONE))
        // The capture's own purpose was revoked or declined: stop.
        assertTrue(mustStop(before, consent(5, "revoked", "granted"), Capture.CAMERA))
        assertFalse(mustStop(before, consent(5, "revoked", "granted"), Capture.MICROPHONE))
        assertTrue(mustStop(before, consent(5, "granted", "declined"), Capture.MICROPHONE))
        // Back to pending (e.g. the subject changed) is no longer a grant either.
        assertTrue(mustStop(before, consent(4, "pending", "granted"), Capture.CAMERA))
        // Nothing new learned (offline): no decision here; the server keeps refusing on its own.
        assertFalse(mustStop(before, null, Capture.CAMERA))
        // First reading while running (nothing before): stops only without a grant.
        assertFalse(mustStop(null, consent(1, "granted", "granted"), Capture.CAMERA))
        assertTrue(mustStop(null, consent(1, "revoked", "granted"), Capture.CAMERA))
        // An epoch that went back is not the record the capture started under.
        assertTrue(mustStop(before, consent(2, "granted", "granted"), Capture.CAMERA))
    }

    @Test fun refusalCodesStopCapturesButOtherFailuresRetry() {
        for (code in listOf("consent_changed", "privacy_review_required", "camera_consent_revoked", "private_test_consent_required",
                "legal_review_required", "authentication_required", "session_changed",
                "territory_declaration_required", "meta_territory_restricted")) assertTrue(code, stopsCapture(code))
        for (code in listOf("consent_subject_only", "video_busy", "server_unavailable", "throttled", "clip_invalid", "image_required", "")) assertFalse(code, stopsCapture(code))
    }

    @Test fun refusingAPurposeStopsTheCapturesThatDependOnIt() {
        assertEquals(setOf(Capture.CAMERA), capturesFor("camera_local"))
        assertEquals(setOf(Capture.CAMERA), capturesFor("meta_photos"))
        assertEquals(setOf(Capture.CAMERA), capturesFor("meta_video"))
        assertEquals(setOf(Capture.MICROPHONE), capturesFor("microphone_local"))
        assertEquals(setOf(Capture.MICROPHONE), capturesFor("meta_voice"))
        assertTrue(capturesFor("meta_conversation").isEmpty())
        assertTrue(capturesFor("profile_personalization").isEmpty())
    }

    @Test fun lateResultsAfterARevocationAreDropped() {
        val gate = ResultGate()
        val first = gate.open()
        assertTrue(gate.accepts(first))
        gate.revoke()
        assertFalse(gate.accepts(first))  // the answer that arrives after the stop
        val next = gate.open()
        assertTrue(gate.accepts(next))  // work started after a new grant
        gate.revoke(); gate.revoke()
        assertFalse(gate.accepts(next))
    }

    @Test fun recognitionPrefersTheDeviceAndOtherwiseNeedsThisAccountsAcceptance() {
        assertEquals("device", recognitionMode(onDeviceAvailable = true, accountAccepted = false))
        assertEquals("device", recognitionMode(onDeviceAvailable = true, accountAccepted = true))
        assertEquals("service", recognitionMode(onDeviceAvailable = false, accountAccepted = true))
        assertEquals("ask", recognitionMode(onDeviceAvailable = false, accountAccepted = false))
    }

    @Test fun speechAcceptanceNeverCarriesOverToAnotherAccount() {
        // Account A accepted; then account B signs in on the same phone and its payload does not say so.
        var accepted = speechServiceOf(session("ana", true))
        assertEquals("service", recognitionMode(false, accepted))
        accepted = speechServiceOf(session("bruno", null))
        assertEquals("ask", recognitionMode(false, accepted))
        assertEquals("ask", recognitionMode(false, speechServiceOf(session("bruno", false))))
        // Signed out: no user, no acceptance.
        assertFalse(speechServiceOf(JSONObject().put("user", JSONObject.NULL)))
        assertFalse(speechServiceOf(null))
    }
}
