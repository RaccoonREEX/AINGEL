package ec.aingel.mobile

import org.json.JSONObject

/** The server remains authoritative; this is the local explicit declaration for this session. */
internal fun privateMediaAllowed(profile: JSONObject?, selectedId: String?, kind: String): Boolean {
    if (kind !in setOf("camera", "microphone") || profile == null || selectedId.isNullOrBlank()) return false
    // The old coarse flags no longer authorize anything: only the owner who is the person may try, and the server
    // checks that person's own grants for each purpose (backend care.consent.private_media_allowed).
    return profile.optString("id") == selectedId && profile.optString("role") == "owner" && profile.optString("subject_status") == "self"
}

internal fun imageRequestFields(profile: JSONObject?, selectedId: String?): MutableMap<String, String> {
    val id = profile?.optString("id").orEmpty()
    val fields = mutableMapOf("locale" to (profile?.optString("locale") ?: "es-EC"), "profile" to id)
    if (selectedId != null) {
        if (!privateMediaAllowed(profile, selectedId, "camera")) throw ApiFailure("private_test_consent_required")
        fields["private_test"] = "true"
    }
    return fields
}

/** Synthetic test: only a server fixture id (assistance.synthetic); no image, profile or typed object name. */
internal fun fixtureImageFields(locale: String, fixture: String): Map<String, String> = mapOf("locale" to locale, "fixture" to fixture)

internal fun captionStartPayload(locale: String, profileId: String, privateTest: Boolean): JSONObject =
    JSONObject().put("type", "start").put("locale", locale).put("profile", profileId)
        .apply { if (privateTest) put("private_test", true) }
