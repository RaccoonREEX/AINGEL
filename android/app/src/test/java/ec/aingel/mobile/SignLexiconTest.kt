package ec.aingel.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SignLexiconTest {
    @Test fun timeGoesFirstAndPossessivesBecomeMe() {
        // Same result as the catalogue's «Escribe una frase» (AINGEL_Senas.dc.html).
        assertEquals(listOf("manana", "querer", "ir", "parque", "yo", "hija"), buildSentence("Mañana quiero ir al parque con mi hija")!!.seq)
        assertEquals(listOf("ayer", "mama", "leer", "libro"), buildSentence("Ayer mi mamá leyó un libro")!!.seq.filter { it != "yo" })
    }

    @Test fun questionsEndWithTheQuestionSign() {
        assertEquals(listOf("tener", "comer", "pregunta"), buildSentence("¿Tienes hambre?")!!.seq)
        assertEquals("pregunta", buildSentence("¿Dónde está el baño?")!!.seq.last())
    }

    @Test fun howAreYouIsAskedNotEaten() {
        // 29-10-2026: «cómo estás» was signed as «comer».
        assertEquals(listOf("tu", "bien", "pregunta"), buildSentence("cómo estás")!!.seq)
        assertEquals(listOf("tu", "bien", "pregunta"), buildSentence("como estas")!!.seq)  // dictation without accents
        assertEquals(listOf("hola", "tu", "bien", "pregunta"), buildSentence("Hola, ¿cómo estás?")!!.seq)
        assertEquals(listOf("tu", "bien", "pregunta"), buildSentence("¿Cómo te sientes?")!!.seq)
        assertEquals(listOf("tu", "bien", "pregunta"), buildSentence("¿Cómo está usted?")!!.seq.filter { it != "u" && it.length > 1 })
        assertEquals(listOf("tu", "mama", "bien", "pregunta"), buildSentence("¿Cómo está tu mamá?")!!.seq)
        assertEquals(listOf("tu", "bien", "pregunta"), buildSentence("How are you?")!!.seq)
        // Only «como» meaning «I eat» stays «comer».
        assertEquals(listOf("yo", "comer", "comida"), buildSentence("Yo como el almuerzo")!!.seq)
        assertEquals(listOf("yo", "comer", "a", "r", "r", "o", "z"), buildSentence("Como arroz")!!.seq)  // «I eat rice», no question
        assertEquals(listOf("tu", "llamar", "pregunta"), buildSentence("¿Cómo te llamas?")!!.seq)
    }

    @Test fun metaGlossBecomesHandsWithinTheVocabulary() {
        val gloss = org.json.JSONArray("""[{"sign":"yo"},{"spell":"ñaña"},{"sign":"n3"}]""")
        assertEquals(listOf("yo", "ñ", "a", "ñ", "a", "n3"), glossSeq(gloss))
        assertNull(glossSeq(org.json.JSONArray("""[{"sign":"feliz"}]""")))  // not an AINGEL sign: local rule instead
        assertNull(glossSeq(org.json.JSONArray("[]")))
        assertTrue(GLOSS_VOCABULARY.keys.all { hasSign(it) })
        assertEquals("tú / you", GLOSS_VOCABULARY["tu"])
    }

    @Test fun unknownWordsAreFingerspelledAndArticlesDropped() {
        val b = buildSentence("Me llamo Rosa")!!
        assertEquals(listOf("yo", "r", "o", "s", "a"), b.seq)
        assertEquals(WordKind.SPELL, b.words.last().second)
        val skipped = buildSentence("el agua")!!.words.first()
        assertEquals("el" to WordKind.SKIP, skipped)
        assertEquals(listOf("porfavor"), buildSentence("por favor")!!.seq)
        assertEquals(listOf("n", "i", "ñ", "o"), spellSeq("Niño"))
        assertNull(buildSentence("   "))
    }

    @Test fun everySignUsedHasAnAnimationNameAndBoardPictogram() {
        val all = listOf("Hola, ¿cómo estás?", "Necesito ayuda", "Tengo dolor", "Voy al baño", "Mañana vamos al doctor", "Papá viene hoy", "Espera, por favor")
            .flatMap { buildSentence(it)!!.seq }
        all.forEach { assertTrue(it, hasSign(it)) }
        SIGN_BOARD.forEach { assertTrue(it, hasSign(it) && it in SIGN_PICTOGRAMS) }
        "abcdefghijklmnñopqrstuvwxyz".forEach { assertTrue("$it", hasSign(it.toString())) }
        (0..10).forEach { assertTrue(hasSign("n$it")) }
    }
}
