package ec.aingel.mobile

import android.content.Context
import android.content.ContextWrapper
import android.media.Image
import android.os.SystemClock
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/**
 * Live, synthetic only: frames drawn here (a blue square crossing a plain background; no camera, no person) go through
 * the same H.264 encoder and MP4 muxer as the camera (ClipRecorder), are uploaded by the app's own client to a
 * backend on this debug loopback (vision/clip/, `synthetic=true`), and that backend asks Meta what changed.
 * Opt-in: -Pandroid.testInstrumentationRunnerArguments.aingelLiveVideo=true, with a local backend in meta mode and
 * AINGEL_VIDEO_CLIPS=1 behind `adb reverse tcp:8010 tcp:<port>`. It creates one test account on that local backend.
 */
@RunWith(AndroidJUnit4::class)
class SyntheticVideoToMetaTest {
    private val width = 640
    private val height = 480

    @Test fun syntheticClipThroughThePhoneEncoderReachesMeta() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("aingelLiveVideo") == "true")
        val backend = args.getString("aingelBackend") ?: "http://127.0.0.1:8010/"
        val suffix = UUID.randomUUID().toString()
        val context = object : ContextWrapper(InstrumentationRegistry.getInstrumentation().targetContext) {
            override fun getSharedPreferences(name: String, mode: Int) = super.getSharedPreferences("synthetic-video-$suffix-$name", mode)
        }

        val encodeStarted = SystemClock.elapsedRealtime()
        val recorder = ClipRecorder()
        for (i in 0 until 75) recorder.feedFrame(width, height, 0, i * 100_000L, timeoutUs = 50_000) { draw(it, i) }
        val clip = recorder.clip(6.0, 3.0, context.cacheDir)
        recorder.close()
        val encodeMs = SystemClock.elapsedRealtime() - encodeStarted
        assertNotNull("the encoder produced no clip", clip)

        val api = ApiClient(context)
        api.configure(backend)
        val terms = (api.request("auth/session/") as JSONObject).getString("terms_version")
        api.request("auth/register/", "POST", JSONObject().put("username", "synthetic-video-${suffix.take(8)}")
            .put("password", "Synthetic-" + UUID.randomUUID()).put("adult", true).put("terms_version", terms))
        val sent = SystemClock.elapsedRealtime()
        val result = api.uploadClip("vision/clip/", clip!!, mapOf("locale" to "es-EC", "session" to suffix, "seq" to "1", "synthetic" to "true"))
        val roundTripMs = SystemClock.elapsedRealtime() - sent
        Log.i("AINGEL-video-test", "bytes=${clip.size} encode_ms=$encodeMs roundtrip_ms=$roundTripMs seconds=${result.optDouble("seconds")} " +
            "events=${result.optJSONArray("events")} say=${result.optString("say")} server=${result.optJSONObject("timings")}")
        api.clear()

        assertEquals("meta", result.getString("mode"))
        assertTrue("Meta reported no change for a moving square", (result.optJSONArray("events")?.length() ?: 0) > 0)
    }

    /** Frame [i]: light grey background, a blue square entering from the left after one second. */
    private fun draw(image: Image, i: Int) {
        val square = if (i >= 10) (i - 10) * 9 - 80 else Int.MIN_VALUE
        fun inside(x: Int, y: Int) = square != Int.MIN_VALUE && x in square until square + 80 && y in 180 until 260
        val (yPlane, uPlane, vPlane) = image.planes
        for (y in 0 until height) for (x in 0 until width) {
            yPlane.buffer.put(y * yPlane.rowStride + x * yPlane.pixelStride, (if (inside(x, y)) 60 else 200).toByte())
        }
        for (y in 0 until height / 2) for (x in 0 until width / 2) {
            val blue = inside(x * 2, y * 2)
            uPlane.buffer.put(y * uPlane.rowStride + x * uPlane.pixelStride, (if (blue) 210 else 128).toByte())
            vPlane.buffer.put(y * vPlane.rowStride + x * vPlane.pixelStride, (if (blue) 100 else 128).toByte())
        }
    }
}
