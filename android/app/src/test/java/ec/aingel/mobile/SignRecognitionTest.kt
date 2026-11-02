package ec.aingel.mobile

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class SignRecognitionTest {
    private fun result(vararg ids: String) =
        JSONObject().put("signs", JSONArray().apply { ids.forEach { put(JSONObject().put("id", it).put("certainty", "likely")) } })

    @Test fun keepsTheBoardSignsInOrderAndNothingElse() {
        assertEquals(listOf("hola", "gracias"), recognizedSigns(result("hola", "gracias")))
        assertEquals(listOf("agua"), recognizedSigns(result("teletransporte", "agua")))
        assertEquals(emptyList<String>(), recognizedSigns(JSONObject().put("mode", "mock")))
    }
}
