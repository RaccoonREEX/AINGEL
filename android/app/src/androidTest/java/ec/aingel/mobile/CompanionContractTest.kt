package ec.aingel.mobile

import android.content.Context
import android.content.ContextWrapper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/** Runs only against the device's local mock server, with synthetic values. */
@RunWith(AndroidJUnit4::class)
class CompanionContractTest {
    @Test fun requestIncludesOnlyExplicitSyntheticTextAndPublicTopic() = runBlocking {
        val server = MockWebServer(); server.start()
        try {
            val suffix = UUID.randomUUID().toString()
            val context = object : ContextWrapper(InstrumentationRegistry.getInstrumentation().targetContext) {
                override fun getSharedPreferences(name: String, mode: Int) = super.getSharedPreferences("companion-test-$suffix-$name", mode)
            }
            val api = ApiClient(context)
            api.configure(server.url("/").toString())
            server.enqueue(MockResponse().addHeader("Set-Cookie", "sessionid=synthetic; Path=/; HttpOnly").setBody("{\"csrf\":\"synthetic\"}"))
            api.request("auth/session/"); server.takeRequest()
            val profile = UUID.randomUUID().toString()
            server.enqueue(MockResponse().setBody("""{"mode":"mock","model":null,"text":"Synthetic reply","source":null,"latency_ms":null}"""))
            val payload = companionPayload("Synthetic question", CompanionTopic("Sleep", "en"))
            val result = api.request("profiles/$profile/companion/chat/", "POST", payload) as JSONObject
            assertEquals("mock", result.getString("mode")); assertEquals("Synthetic reply", result.getString("text"))
            val sent = server.takeRequest()
            assertEquals("POST", sent.method)
            assertEquals("/api/v1/profiles/$profile/companion/chat/", sent.path)
            assertEquals("synthetic", sent.getHeader("X-CSRFToken"))
            assertTrue(sent.getHeader("Cookie")!!.contains("sessionid=synthetic"))
            val body = JSONObject(sent.body.readUtf8())
            assertEquals(setOf("text", "topic_title", "topic_lang"), body.keys().asSequence().toSet())
            assertEquals("Synthetic question", body.getString("text"))
            api.clear()
        } finally { server.shutdown() }
    }
}
