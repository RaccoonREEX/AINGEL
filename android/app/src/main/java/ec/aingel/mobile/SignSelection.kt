package ec.aingel.mobile

/** The visual catalog only covers explicitly reviewed, complete phrases. */
internal data class SignPhrase(val profileId: String, val language: String, val turnId: String, val text: String)

internal fun supportsSignCatalog(language: String?): Boolean = language == "lsec" || language == "asl"

internal fun eligibleSignPhrase(profileId: String?, language: String?, turn: CaptionTurn?): SignPhrase? {
    if (profileId.isNullOrBlank() || !supportsSignCatalog(language) || turn == null || !turn.final || turn.text.isBlank() || turn.text.codePointCount(0, turn.text.length) > 300) return null
    return SignPhrase(profileId, language!!, turn.id, turn.text)
}

internal fun validSignClipId(id: String): Boolean = id.matches(Regex("[a-z0-9][a-z0-9_-]{0,63}"))

internal class SignLookupGuard {
    private var generation = 0L
    @Synchronized fun advance(): Long = ++generation
    @Synchronized fun isCurrent(value: Long): Boolean = generation == value
}
