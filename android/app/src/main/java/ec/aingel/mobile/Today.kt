package ec.aingel.mobile

import org.json.JSONObject
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Today's active routines in time order, the next pending one and minutes until it (same rules as the web). */
internal data class TodaySummary(val list: List<JSONObject>, val done: Int, val next: JSONObject?, val minutesUntil: Int?)

internal fun zone(id: String?): ZoneId = try { ZoneId.of(id ?: "America/Guayaquil") } catch (_: Exception) { ZoneId.of("America/Guayaquil") }

private fun minutesOf(at: String) = (at.take(2).toIntOrNull() ?: 0) * 60 + (at.drop(3).take(2).toIntOrNull() ?: 0)

internal fun summarizeToday(items: List<JSONObject>, zoneId: ZoneId, now: ZonedDateTime = ZonedDateTime.now(zoneId)): TodaySummary {
    val day = now.dayOfWeek.value - 1
    val list = items.filter { r -> r.optBoolean("active", true) && r.optJSONArray("weekdays")?.let { w -> (0 until w.length()).any { w.optInt(it) == day } } == true }
        .sortedBy { it.optString("at") }
    val minute = now.hour * 60 + now.minute
    val pending = list.filterNot { it.optBoolean("confirmed_today") }
    val next = pending.firstOrNull { minutesOf(it.optString("at")) >= minute } ?: pending.firstOrNull()
    return TodaySummary(list, list.size - pending.size, next, next?.let { minutesOf(it.optString("at")) - minute })
}

internal fun longDate(localeTag: String, zoneId: ZoneId): String {
    val locale = Locale.forLanguageTag(localeTag)
    val pattern = if (locale.language == "es") "EEEE, d 'de' MMMM" else "EEEE, MMMM d"
    return ZonedDateTime.now(zoneId).format(DateTimeFormatter.ofPattern(pattern, locale)).replaceFirstChar { it.titlecase(locale) }
}

internal fun hhmm(at: String) = at.take(5)

internal fun timeOf(iso: String, zoneId: ZoneId): String = try {
    ZonedDateTime.parse(iso).withZoneSameInstant(zoneId).toLocalTime().let { "%02d:%02d".format(it.hour, it.minute) }
} catch (_: Exception) { "" }

internal fun greetingPart(zoneId: ZoneId): Int = LocalTime.now(zoneId).let { if (it.hour < 12) 0 else if (it.hour < 19) 1 else 2 }

internal fun initials(name: String) = name.split(Regex("\\s+")).filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }.ifBlank { "A" }

/** Pulls the object out of "¿Dónde dejé mis llaves?" / "Where did I leave my keys?". */
internal fun memoryEntity(question: String): String = question.replace(Regex("[¿?¡!.]"), " ")
    .replace(Regex("^\\s*(d[oó]nde)\\s+(dej[eé]|vi|est[aá]n?|puse|qued[oó]|guard[eé])\\s+((mis|mi|el|la|los|las|un|una)\\s+)?", RegexOption.IGNORE_CASE), "")
    .replace(Regex("^\\s*where\\s+(did\\s+i\\s+(leave|put|see)|is|are|were)\\s+((my|the|a)\\s+)?", RegexOption.IGNORE_CASE), "")
    .replace(Regex("\\s*(este objeto|this object)\\s*", RegexOption.IGNORE_CASE), "").trim()

/** Things AINGEL does itself with the camera when asked by voice, instead of sending the request to Meta. */
internal enum class CameraCommand { SEE, WATCH, WATCH_STOP }

internal fun cameraCommandOf(question: String): CameraCommand? {
    val q = java.text.Normalizer.normalize(question.lowercase(), java.text.Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")
    val watch = Regex("(vigilancia|vista continua|vigila|vigilar|sigue mirando|mira todo el tiempo|avisame (de )?lo que (veas|haya)|continuous watch|keep watching)")
    return when {
        Regex("\\b(deten|detente|detener|para (la|el)|parar|apaga|apagar|desactiva|desactivar|termina|terminar|quita|stop|turn off)\\b").containsMatchIn(q) &&
            (watch.containsMatchIn(q) || q.contains("camara") || q.contains("camera")) -> CameraCommand.WATCH_STOP
        watch.containsMatchIn(q) -> CameraCommand.WATCH
        // Whole phrases, so «descríbeme qué tengo hoy» or "look at my schedule" stay questions for AINGEL.
        Regex("(\\bque ves\\b|que estas viendo|estas viendo|que hay (delante|enfrente|frente)|que tengo (delante|enfrente)|\\b(describe|describir) (lo que|que hay|el lugar|esto|todo)|" +
            "^\\s*(describe|describir)\\s*$|mira (esto|aqui|por la)|" +
            "(usa|activa|abre|enciende) la camara|por la camara|camara del (celular|telefono)|lo que yo (veo|no puedo ver)|que es esto|" +
            "what do you see|what is in front|look (at this|around|through the camera))").containsMatchIn(q) -> CameraCommand.SEE
        else -> null
    }
}

/** «Parece ser tu hijo David.» for the family members the server recognized locally in a scene, minus [skip] ids. */
internal fun knownPeople(scene: JSONObject, skip: Set<String> = emptySet()): List<Pair<String, String>> {
    val people = scene.optJSONArray("people") ?: return emptyList()
    return (0 until people.length()).mapNotNull { people.optJSONObject(it) }
        .map { it.optString("id") to it.optString("line") }
        .filter { (id, line) -> id.isNotBlank() && line.isNotBlank() && id !in skip }
}

internal fun withKnownPeople(scene: JSONObject, text: String, skip: Set<String> = emptySet()): String =
    (knownPeople(scene, skip).map { it.second } + text).filter { it.isNotBlank() }.joinToString(" ")

/** Oldest conversation pairs dropped until all turns fit the server limit (backend conversation.MAX_TOTAL_CHARS). */
internal fun boundedHistory(pairs: List<Pair<String, String>>, question: String, limit: Int = 8000): List<Pair<String, String>> {
    var kept = pairs
    while (kept.isNotEmpty() && question.length + kept.sumOf { it.first.length + it.second.length } > limit) kept = kept.drop(1)
    return kept
}

internal enum class AskIntent { MEMORY, ROUTINES, MESSAGES, SUPPORT, UNKNOWN }

internal fun intentOf(question: String): AskIntent {
    // Only the app's own intents are answered locally; «¿Dónde queda el hospital?» or «¿Qué debo hacer si me duele
    // el pecho?» go to Meta (audit 29-10-2026; same rules as web Home.tsx).
    val q = " " + java.text.Normalizer.normalize(question.lowercase(), java.text.Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")
        .replace(Regex("[¿?¡!.,;:\"«»“”]"), " ").replace(Regex("\\s+"), " ").trim() + " "
    return when {
        Regex(" (donde (deje|puse|guarde|vi|quedo|quedaron) |donde (esta|estan) (mi|mis) |where (did i (leave|put|see)|(is|are) my) )").containsMatchIn(q) -> AskIntent.MEMORY
        Regex(" (que tengo (que hacer )?(para )?hoy|que (hay|me toca) (para )?hoy|mi agenda|mis rutinas|mis pendientes|what do i (have|need to do)( to do)? today|" +
            "what('s| is) on my (agenda|schedule)|my (agenda|routines|schedule)) ").containsMatchIn(q) -> AskIntent.ROUTINES
        Regex(" (que me (han|ha) dicho|que me dijeron|mis mensajes|(ultimo|ultimos|nuevo|nuevos) mensajes?|tengo mensajes|what have i been told|" +
            "what have people told me|my (latest |last |new )?messages?|(any|new) messages) ").containsMatchIn(q) -> AskIntent.MESSAGES
        Regex("^ (necesito (apoyo|ayuda)( por favor)?|ayudame( por favor)?|ayuda|help( me)?( please)?|i need (support|help)) $").containsMatchIn(q) -> AskIntent.SUPPORT
        else -> AskIntent.UNKNOWN
    }
}
