package ec.aingel.mobile

import android.content.Context
import androidx.camera.core.ImageCapture
import kotlinx.coroutines.delay
import org.json.JSONObject

/*
 * Experimental sign recognition (backend assistance.sign_recognition): a short burst of frames from the open camera,
 * compared by Meta with AINGEL's own sign set. It can be wrong; the person corrects it on the sign board.
 */
internal const val SIGN_FRAMES = 5

/** [SIGN_FRAMES] consecutive frames, a little apart, while the person signs. */
internal suspend fun ImageCapture.signFrames(context: Context): List<ByteArray> = List(SIGN_FRAMES) { i ->
    if (i > 0) delay(120)
    jpegFrame(context)
}

/** The recognized sign ids, in order; only ids of the sign board come back (the server rejects any other). */
internal fun recognizedSigns(result: JSONObject): List<String> {
    val signs = result.optJSONArray("signs") ?: return emptyList()
    return (0 until signs.length()).mapNotNull { signs.optJSONObject(it)?.optString("id") }.filter { it in SIGN_BOARD }
}
