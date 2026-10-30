package ec.aingel.mobile

import java.text.Normalizer

/*
 * Vocabulary and sentence rule of the AINGEL signs catalogue v1.5.0 (same as web/src/components/aingel/signLexicon.ts).
 * The signs are an AINGEL DESIGN pending validation by Deaf LSEC signers. The sentence rule is a simple one
 * (time first, question last, unknown words fingerspelled, articles dropped), NOT LSEC grammar.
 */
private val WORDS = listOf(
    Triple("yo", "yo", "I"), Triple("tu", "tú", "you"), Triple("hola", "hola", "hello"), Triple("gracias", "gracias", "thank you"), Triple("porfavor", "por favor", "please"),
    Triple("si", "sí", "yes"), Triple("no", "no", "no"), Triple("bien", "bien", "good"), Triple("mal", "mal", "bad"), Triple("agua", "agua", "water"), Triple("comida", "comida", "food"),
    Triple("medicina", "medicina", "medicine"), Triple("casa", "casa", "home"), Triple("parque", "parque", "park"), Triple("pelota", "pelota", "ball"), Triple("libro", "libro", "book"),
    Triple("bano", "baño", "bathroom"), Triple("doctor", "doctor", "doctor"), Triple("familia", "familia", "family"), Triple("mama", "mamá", "mum"), Triple("papa", "papá", "dad"),
    Triple("hija", "hija", "daughter"), Triple("hijo", "hijo", "son"), Triple("dolor", "dolor", "pain"), Triple("ayuda", "ayuda", "help"), Triple("hoy", "hoy", "today"),
    Triple("manana", "mañana", "tomorrow"), Triple("ayer", "ayer", "yesterday"), Triple("pregunta", "¿pregunta?", "question?"),
    Triple("caminar", "caminar", "walk"), Triple("leer", "leer", "read"), Triple("comer", "comer", "eat"), Triple("beber", "beber", "drink"), Triple("dormir", "dormir", "sleep"),
    Triple("esperar", "esperar", "wait"), Triple("ir", "ir", "go"), Triple("venir", "venir", "come"), Triple("llamar", "llamar", "call"), Triple("ayudar", "ayudar", "help"),
    Triple("necesitar", "necesitar", "need"), Triple("querer", "querer", "want"), Triple("tener", "tener", "have"), Triple("jugar", "jugar", "play"),
)
private val NAMES: Map<String, Pair<String, String>> = buildMap {
    WORDS.forEach { (id, es, en) -> put(id, es to en) }
    "abcdefghijklmnñopqrstuvwxyz".forEach { put(it.toString(), it.uppercase() to it.uppercase()) }
    for (i in 0..10) put("n$i", "$i" to "$i")
}
internal fun signName(id: String, spanish: Boolean) = NAMES[id]?.let { if (spanish) it.first else it.second } ?: id

private val LEX: Map<String, String?> = buildMap {
    fun add(id: String, ws: String) = ws.split(" ").forEach { put(it, id) }
    add("yo", "yo me mi mis conmigo i me my"); add("tu", "tu tus te ti usted ustedes vos contigo you your")
    add("hola", "hola buenos buenas saludos hello hi"); add("gracias", "gracias agradezco thanks thank"); add("si", "si claro vale yes ok"); add("no", "no nunca nada never")
    add("bien", "bien bueno buena feliz contento contenta tranquilo tranquila good fine well happy"); add("mal", "mal malo mala enfermo enferma triste bad sick sad")
    add("agua", "agua water"); add("comida", "comida almuerzo desayuno cena merienda food lunch breakfast dinner")
    add("medicina", "medicina medicinas medicamento medicamentos pastilla pastillas remedio remedios medicine medicines pill pills")
    add("casa", "casa hogar home house"); add("parque", "parque parques park"); add("pelota", "pelota balon ball"); add("libro", "libro libros cuento book books"); add("bano", "bano bathroom toilet")
    add("doctor", "doctor doctora medico medica hospital"); add("familia", "familia family"); add("mama", "mama madre mami mum mom mother"); add("papa", "papa padre papi dad father")
    add("hija", "hija hijas nieta daughter granddaughter"); add("hijo", "hijo hijos nieto son grandson"); add("dolor", "dolor duele duelen dolores pain hurts"); add("ayuda", "ayuda auxilio socorro help")
    add("hoy", "hoy ahora today now"); add("manana", "manana tomorrow"); add("ayer", "ayer yesterday")
    add("caminar", "caminar camino caminas camina caminamos camine caminare caminaremos pasear paseo walk walked"); add("leer", "leer leo lees lee lei leyo leere leyendo leemos read reading")
    add("comer", "comer como comes come comemos comi comere hambre eat hungry"); add("beber", "beber bebo bebes bebe tomar tomo tomas toma sed drink thirsty")
    add("dormir", "dormir duermo duermes duerme dormi dormire sueno descansar descanso sleep tired"); add("esperar", "esperar espero esperas espera espere esperame wait")
    add("ir", "ir voy vas va vamos van fui iremos ire go going"); add("venir", "venir vengo vienes viene vienen ven vino vendra come coming")
    add("llamar", "llamar llama llamo llamas llame llamame telefono call phone"); add("ayudar", "ayudar ayudo ayudas ayudame ayudeme ayude")
    add("necesitar", "necesitar necesito necesitas necesita necesitamos need"); add("querer", "querer quiero quieres quiere queremos quisiera want")
    add("tener", "tener tengo tienes tiene tenemos have"); add("jugar", "jugar juego juegas juega jugamos jugue play")
    listOf("cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez").forEachIndexed { i, w -> put(w, "n$i"); put("$i", "n$i") }
    put("una", null)
}
private val STOP = ("el la los las un una unos unas de del al a en con y o que por para es esta estas estoy estan son era fue muy lo le les se su sus este ese eso esto ya " +
    "tambien pero como cual donde cuando quien cuanto mas the an to of and or is are am was in on at with for it").split(" ").toSet()
private val QW = "que como donde cuando quien cual cuanto what how where when who which why".split(" ").toSet()
private val TIME = setOf("hoy", "manana", "ayer")
/** What follows «cómo» / «how» in «¿cómo estás?» and its variants: asked to you, or to someone else (or «usted»). */
private val HOW_YOU = listOf("estas", "te va", "te sientes", "te encuentras", "has estado", "andas", "sigues", "amaneciste", "are you").map { it.split(" ") }
private val HOW_THEY = listOf("esta", "estan", "le va", "les va", "se siente", "se sienten", "se encuentra", "ha estado", "anda", "sigue", "amanecio", "is", "are").map { it.split(" ") }

/** Lowercase without accents, keeping ñ. */
private fun norm(w: String) = Normalizer.normalize(w.lowercase().replace('ñ', '\u0001'), Normalizer.Form.NFD).replace(Regex("\\p{M}"), "").replace('\u0001', 'ñ')
internal fun spellSeq(txt: String) = norm(txt).filter { it in 'a'..'z' || it == 'ñ' }.map { it.toString() }.take(16)

enum class WordKind { SIGN, SPELL, SKIP }
data class BuiltSentence(val seq: List<String>, val words: List<Pair<String, WordKind>>)

/** Catalogue rule: time (today / yesterday / tomorrow) first, question last, unknown words fingerspelled. */
internal fun buildSentence(txt: String): BuiltSentence? {
    val raw = txt.trim()
    if (raw.isEmpty()) return null
    val first = raw.split(Regex("\\s+"))[0].replace(Regex("[¿¡]"), "")
    // An opening «como» without accent nor «?» is «I eat» («Como arroz»), not «how».
    var isQ = '?' in raw || (norm(first) in QW && (norm(first) != "como" || 'ó' in first.lowercase()))
    val toks = raw.replace(Regex("[¿¡!?.,;:]"), " ").split(Regex("\\s+")).filter { it.isNotBlank() }
    val words = mutableListOf<Pair<String, WordKind>>(); val time = mutableListOf<String>(); val main = mutableListOf<String>(); val tail = mutableListOf<String>()
    var i = 0
    while (i < toks.size) {
        val w = norm(toks[i]).replace('ñ', 'n'); val nx = toks.getOrNull(i + 1)?.let { norm(it).replace('ñ', 'n') } ?: ""
        val after = toks.drop(i + 1).map { norm(it).replace('ñ', 'n') }
        val toYou = if (w == "como" || w == "how") HOW_YOU.firstOrNull { after.take(it.size) == it } else null
        val toThem = if ((w == "como" || w == "how") && toYou == null) HOW_THEY.firstOrNull { after.take(it.size) == it } else null
        when {
            // «¿Cómo estás?» → TÚ BIEN ? ; «¿Cómo está tu mamá?» → TÚ MAMÁ BIEN ? (not «comer»: 29-10-2026).
            toYou != null || toThem != null -> {
                val n = (toYou ?: toThem)!!.size
                words.add(toks.subList(i, i + 1 + n).joinToString(" ") to WordKind.SIGN)
                if (toYou != null || toks.size == i + 1 + n) main.add("tu")
                tail.add("bien"); isQ = true; i += n
            }
            // «Cómo» asking (accented, or opening a question) is the question word, not «I eat».
            w == "como" && ('ó' in toks[i].lowercase() || (i == 0 && '?' in raw)) -> words.add(toks[i] to WordKind.SKIP)
            // An opening «Como» is first person («Como arroz» → YO COMER …), as on the web.
            w == "como" && i == 0 -> { words.add(toks[i] to WordKind.SIGN); main.add("yo"); main.add("comer") }
            w == "por" && nx == "favor" -> { words.add("${toks[i]} ${toks[i + 1]}" to WordKind.SIGN); main.add("porfavor"); i++ }
            (w == "me" && nx == "llamo") || (w == "mi" && nx == "nombre") || (w == "my" && nx == "name") -> {
                var j = i + 2
                if (norm(toks.getOrNull(j) ?: "") in setOf("es", "is")) j++
                words.add(toks.subList(i, minOf(j, toks.size)).joinToString(" ") to WordKind.SIGN); main.add("yo")
                toks.getOrNull(j)?.let { words.add(it to WordKind.SPELL); main.addAll(spellSeq(it)) }
                i = j
            }
            LEX[w] != null -> { val id = LEX.getValue(w)!!; words.add(toks[i] to WordKind.SIGN); if (id in TIME) time.add(id) else main.add(id) }
            w in STOP || w in QW -> words.add(toks[i] to WordKind.SKIP)
            else -> {
                val sp = spellSeq(toks[i]).take(10)
                if (sp.isNotEmpty()) { words.add(toks[i] to WordKind.SPELL); main.addAll(sp) } else words.add(toks[i] to WordKind.SKIP)
            }
        }
        i++
    }
    val all = time + main + tail
    val seq = all.filterIndexed { k, id -> k == 0 || id != all[k - 1] || id.length == 1 }.toMutableList()
    if (isQ) seq.add("pregunta")
    return if (seq.isEmpty()) null else BuiltSentence(seq.take(40), words)
}

/** Signs Meta may use when it signs a sentence by meaning (backend assistance.gloss): words and numbers. */
internal val GLOSS_VOCABULARY: Map<String, String> = buildMap {
    WORDS.forEach { (id, es, en) -> put(id, if (es == en) es else "$es / $en") }
    for (i in 0..10) put("n$i", "$i")
}

/** Meta's gloss as the hands' sequence (fingerspelled words become letters), or null if any item is unusable. */
internal fun glossSeq(gloss: org.json.JSONArray?): List<String>? {
    if (gloss == null || gloss.length() == 0) return null
    val seq = mutableListOf<String>()
    for (k in 0 until gloss.length()) {
        val item = gloss.optJSONObject(k) ?: return null
        val sign = item.optString("sign"); val spell = item.optString("spell")
        when {
            sign.isNotEmpty() && sign in GLOSS_VOCABULARY -> seq.add(sign)
            spell.isNotEmpty() -> seq.addAll(spellSeq(spell).ifEmpty { return null })
            else -> return null
        }
    }
    return seq.take(40)
}

/** Board for signs → voice / text: the catalogue words most useful in daily care. */
internal val SIGN_BOARD = listOf("hola", "gracias", "porfavor", "si", "no", "yo", "tu", "bien", "mal", "dolor", "agua", "comer", "medicina", "bano", "ayuda", "doctor", "familia", "casa", "dormir", "pregunta")

private fun circle(x: Float, y: Float, r: Float) = "M${x - r} ${y}a$r $r 0 1 0 ${2 * r} 0a$r $r 0 1 0 ${-2 * r} 0"
private const val HAND = "M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10.5V4a1.5 1.5 0 0 1 3 0v6.5M14 10.5V5.5a1.5 1.5 0 0 1 3 0V13c0 4-2.5 7-6.5 7S5 17.5 4.5 15l-1-3a1.4 1.4 0 0 1 2.5-1.2L8 13"
/** 24×24 stroke pictograms for the board (same as the web). */
internal val SIGN_PICTOGRAMS = mapOf(
    "hola" to HAND + "M19.5 3.5c1.3.9 2 2.2 2 3.8M3 3.5c-.5 1.2-.4 2.4.3 3.4",
    "gracias" to "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
    "porfavor" to "M5 12.5c2.2-.2 3.5 1 4.5 2.5M5 12.5V7a1.4 1.4 0 0 1 2.8 0v4.5M19 12.5c-2.2-.2-3.5 1-4.5 2.5M19 12.5V7a1.4 1.4 0 0 0-2.8 0v4.5M9.5 15l2.5 5 2.5-5",
    "si" to circle(12f, 12f, 8.5f) + "M8 12.3l2.7 2.7 5.5-5.5",
    "no" to circle(12f, 12f, 8.5f) + "M9 9l6 6M15 9l-6 6",
    "yo" to circle(12f, 7f, 3.2f) + "M5.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M12 14.5v3",
    "tu" to circle(12f, 7f, 3.2f) + "M5.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5",
    "bien" to "M7 11v8H4v-8zM7 11l3.5-6.5a1.8 1.8 0 0 1 3.3 1.3L13 10h5a2 2 0 0 1 2 2.3l-1 5.4a2 2 0 0 1-2 1.6H7",
    "mal" to "M7 13V5H4v8zM7 13l3.5 6.5a1.8 1.8 0 0 0 3.3-1.3L13 14h5a2 2 0 0 0 2-2.3l-1-5.4a2 2 0 0 0-2-1.6H7",
    "dolor" to "M13 2.5L6 13.5h5.5L10 21.5l8-11.5h-5.5z",
    "agua" to "M6 4h12l-1.5 15.5a1.5 1.5 0 0 1-1.5 1.4H9a1.5 1.5 0 0 1-1.5-1.4zM7 10h10",
    "comer" to circle(14f, 12f, 6.5f) + circle(14f, 12f, 3f) + "M4.5 4v16M3 4v4a1.5 1.5 0 0 0 3 0V4",
    "medicina" to "M7.05 16.95a3.5 3.5 0 0 1 0-4.95l5-5a3.5 3.5 0 0 1 4.95 4.95l-5 5a3.5 3.5 0 0 1-4.95 0zM9.5 9.5l5 5",
    "bano" to "M4 11h16v2a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6zM6 11V5.5A2.5 2.5 0 0 1 10.5 4M9 19l-1 2M15 19l1 2",
    "ayuda" to circle(12f, 12f, 8.5f) + circle(12f, 12f, 3.5f) + "M6 6l3.5 3.5M14.5 14.5L18 18M18 6l-3.5 3.5M9.5 14.5L6 18",
    "doctor" to "M5 4v5a4 4 0 0 0 8 0V4M9 13v2a5 5 0 0 0 10 0v-2" + circle(19f, 11f, 2f),
    "familia" to circle(8f, 7f, 2.6f) + circle(16f, 7f, 2.6f) + "M3 19c.5-3.2 2.4-5 5-5s4.5 1.8 5 5M11 19c.5-3.2 2.4-5 5-5s4.5 1.8 5 5",
    "casa" to "M4 11l8-6.5 8 6.5M6 9.5V20h12V9.5M10 20v-5h4v5",
    "dormir" to "M19 14.5A7.5 7.5 0 1 1 9.5 5a6 6 0 0 0 9.5 9.5z",
    "pregunta" to "M9 9a3 3 0 1 1 4.2 2.8c-.8.4-1.2 1-1.2 1.9V15M12 18.6v.2",
)
