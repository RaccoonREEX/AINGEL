package ec.aingel.mobile

import org.json.JSONObject
import java.util.concurrent.atomic.AtomicLong

/*
 * Three separate layers decide whether AINGEL may capture: Android's runtime permission (may the app touch the
 * hardware at all, asked by the screens), the person's own consent per purpose (backend care.consent, read from
 * GET profiles/<id>/consent/) and the server's check on every request. This file is the second layer, as pure logic.
 */

/** What a capture opens on the phone, and the person's purpose it needs. */
enum class Capture(val purpose: String) { CAMERA("camera_local"), MICROPHONE("microphone_local") }

/** granted | declined | revoked | pending as the person decided [purpose]; "missing" when unknown (not loaded). */
internal fun purposeStatus(consent: JSONObject?, purpose: String): String {
    val purposes = consent?.optJSONArray("purposes") ?: return "missing"
    for (i in 0 until purposes.length()) {
        val item = purposes.optJSONObject(i) ?: continue
        if (item.optString("id") == purpose) return item.optString("status").ifBlank { "missing" }
    }
    return "missing"
}

/** Opening [capture] needs the person's explicit grant; undecided, refused or unknown never opens anything. */
internal fun mayStart(consent: JSONObject?, capture: Capture): Boolean = purposeStatus(consent, capture.purpose) == "granted"

private fun epochOf(consent: JSONObject?): Long = consent?.optLong("epoch", -1L) ?: -1L

/**
 * A running [capture] started under [previous] must stop once [current] no longer grants it. An epoch change alone
 * (the person declined something else) keeps it; an epoch that went back means these are not the decisions it
 * started under. [current] null means nothing new was learned (offline): the server still refuses on its own.
 */
internal fun mustStop(previous: JSONObject?, current: JSONObject?, capture: Capture): Boolean =
    current != null && (!mayStart(current, capture) || epochOf(current) < epochOf(previous))

/**
 * Server answers after which a running capture stops instead of retrying: the person's decision changed while the
 * request ran (consent_changed), the grants it needs are missing (privacy_review_required,
 * private_test_consent_required), the camera was explicitly refused (camera_consent_revoked), the profile cannot be
 * used (legal_review_required, subject_confirmation_required, adult_declaration_required) or the account is no
 * longer the one that started it (authentication_required, session_changed). consent_subject_only is not here: it
 * answers someone else trying to decide, which changes nothing about a capture.
 */
internal fun stopsCapture(errorCode: String): Boolean = errorCode in setOf(
    "consent_changed", "privacy_review_required", "private_test_consent_required", "camera_consent_revoked",
    "legal_review_required", "subject_confirmation_required", "adult_declaration_required",
    "authentication_required", "session_changed")

/**
 * The capture to close and report as stopped after the decisions changed: only one that was really open. A screen
 * that is still checking before opening (a mode just chosen) is not "stopped" and is left to that check, which says
 * "not authorized" instead: the camera or microphone never turned on and nobody withdrew anything.
 */
internal fun stoppedCapture(cameraOpen: Boolean, cameraAllowed: Boolean, micOpen: Boolean, micAllowed: Boolean): Capture? = when {
    cameraOpen && !cameraAllowed -> Capture.CAMERA
    micOpen && !micAllowed -> Capture.MICROPHONE
    else -> null
}

/** Captures that depend on [purpose]: refusing it in the app stops them at once, before the server answers. */
internal fun capturesFor(purpose: String): Set<Capture> = when (purpose) {
    "camera_local", "meta_photos", "meta_video" -> setOf(Capture.CAMERA)
    "microphone_local", "meta_voice" -> setOf(Capture.MICROPHONE)
    else -> emptySet()
}

/**
 * Late results of work started under an authorization: [open] before the work, [accepts] before applying its result.
 * [revoke] (a refusal, a stop) makes every earlier token stale, so an answer arriving afterwards is dropped.
 */
class ResultGate {
    private val generation = AtomicLong()
    fun open(): Long = generation.get()
    fun revoke() { generation.incrementAndGet() }
    fun accepts(token: Long): Boolean = generation.get() == token
}

/** This account's own acceptance of the phone's speech service, only ever from the current session payload. */
internal fun speechServiceOf(session: JSONObject?): Boolean = session?.optJSONObject("user")?.optBoolean("speech_service", false) == true

/**
 * "device": the phone recognizes speech on the device (nothing leaves it, microphone_local suffices); "service": the
 * system recognizer, which may send the voice to its vendor, accepted by this account; "ask": not accepted (offer
 * to accept or to type).
 */
internal fun recognitionMode(onDeviceAvailable: Boolean, accountAccepted: Boolean): String = when {
    onDeviceAvailable -> "device"
    accountAccepted -> "service"
    else -> "ask"
}
