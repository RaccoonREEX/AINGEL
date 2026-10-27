package ec.aingel.mobile

import android.content.Context
import android.content.ContextWrapper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okio.Buffer
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class SignClipTest {
    @Test fun clipUsesAuthenticatedLocalSessionAndRejectsWrongContentType() = runBlocking {
        val server = MockWebServer(); server.start()
        try {
            val suffix = UUID.randomUUID().toString()
            val context = object : ContextWrapper(InstrumentationRegistry.getInstrumentation().targetContext) {
                override fun getSharedPreferences(name: String, mode: Int) = super.getSharedPreferences("clip-test-$suffix-$name", mode)
            }
            val api = ApiClient(context)
            api.configure(server.url("/").toString())
            server.enqueue(MockResponse().addHeader("Set-Cookie", "sessionid=synthetic; Path=/; HttpOnly").setBody("{\"csrf\":\"synthetic\"}"))
            api.request("auth/session/"); server.takeRequest()
            val profile = UUID.randomUUID().toString()
            val fakeVideo = byteArrayOf(1, 2, 3, 4, 5)
            server.enqueue(MockResponse().addHeader("Content-Type", "video/mp4").setBody(Buffer().write(fakeVideo)))
            assertArrayEquals(fakeVideo, api.signClip(profile, "reviewed_1"))
            val request = server.takeRequest()
            assertEquals("/api/v1/profiles/$profile/signs/clips/reviewed_1/", request.path)
            assertTrue(request.getHeader("Cookie")!!.contains("sessionid=synthetic"))
            server.enqueue(MockResponse().addHeader("Content-Type", "text/html").setBody("not a video"))
            try { api.signClip(profile, "reviewed_1"); fail("Non-video response must be rejected") }
            catch (failure: ApiFailure) { assertEquals("sign_clip_invalid", failure.code) }
            try { api.signClip(profile, "../other"); fail("Unsafe clip IDs must be rejected") }
            catch (failure: ApiFailure) { assertEquals("sign_clip_invalid", failure.code) }
            val source = MemoryVideoSource(fakeVideo)
            val target = ByteArray(4)
            assertEquals(3, source.readAt(2, target, 1, 3)); assertArrayEquals(byteArrayOf(0, 3, 4, 5), target)
            assertEquals(-1, source.readAt(5, target, 0, 1)); source.close(); assertEquals(-1, source.readAt(0, target, 0, 1))
            api.clear()
        } finally { server.shutdown() }
    }
}
