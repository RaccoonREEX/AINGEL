package ec.aingel.mobile

import org.json.JSONObject

/** The server remains authoritative; this is the local explicit declaration for this session. */
internal fun privateMediaAllowed(profile: JSONObject?, selectedId: String?, kind: String): Boolean {
    if (kind !in setOf("camera", "microphone") || profile == null || selectedId.isNullOrBlank()) return false
    val consent = profile.optJSONObject("consents") ?: return false
    return profile.optString("id") == selectedId && profile.optString("role") == "owner" &&
        consent.optBoolean("meta_data") && consent.optBoolean(kind)
}

internal fun imageRequestFields(profile: JSONObject?, selectedId: String?, synthetic: Boolean): MutableMap<String, String> {
    val id = profile?.optString("id").orEmpty()
    val fields = mutableMapOf("locale" to (profile?.optString("locale") ?: "es-EC"), "profile" to id, "synthetic" to synthetic.toString())
    if (!synthetic && selectedId != null) {
        if (!privateMediaAllowed(profile, selectedId, "camera")) throw ApiFailure("private_test_consent_required")
        fields["private_test"] = "true"
    }
    return fields
}

internal fun captionStartPayload(locale: String, profileId: String, privateTest: Boolean): JSONObject =
    JSONObject().put("type", "start").put("locale", locale).put("profile", profileId)
        .apply { if (privateTest) { put("private_test", true); put("synthetic", false) } }
