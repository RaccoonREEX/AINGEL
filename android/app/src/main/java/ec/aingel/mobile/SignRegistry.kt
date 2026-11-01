package ec.aingel.mobile

import org.json.JSONObject

/**
 * The sign registry (backend care.sign_registry): which of AINGEL's signs people who sign LSEC validated, for the
 * exact animation this app plays (assets/hands3d/signFingerprints.json, from `npm run export:android-hands`).
 * Only whole sentences of validated signs move the hands; otherwise the full text stays and the app says that sign
 * interpretation is unavailable or partial. AINGEL's own designs play only when the person chooses them, labelled
 * as illustrations (AINGEL 3.0 §16).
 */
internal sealed interface SignPlan {
    data class Play(val illustrative: Boolean) : SignPlan
    data class Blocked(val validated: Int, val total: Int) : SignPlan { val partial get() = validated > 0 }
}

/** {sign id: fingerprint} from the exported fingerprints file. */
internal fun fingerprintsFrom(json: String): Map<String, String> {
    val data = JSONObject(json)
    return data.keys().asSequence().associateWith { data.getString(it) }
}

/** Signs validated for the animation this app plays: a validation of another version does not count. */
internal fun validatedSigns(registry: JSONObject?, local: Map<String, String>): Set<String> {
    val signs = registry?.optJSONObject("signs") ?: return emptySet()
    return signs.keys().asSequence().filter { id ->
        val sign = signs.optJSONObject(id) ?: return@filter false
        val fingerprint = sign.optString("fingerprint")
        sign.optString("status") == "validated" && fingerprint.isNotEmpty() && fingerprint == local[id]
    }.toSet()
}

/** Whether to animate [seq]: never part of a sentence, since leaving signs out would change what was said. */
internal fun planSigns(seq: List<String>, validated: Set<String>, illustrative: Boolean): SignPlan {
    val covered = seq.count { it in validated }
    if (seq.isNotEmpty() && covered == seq.size) return SignPlan.Play(illustrative = false)
    if (illustrative) return SignPlan.Play(illustrative = true)
    return SignPlan.Blocked(covered, seq.size)
}
