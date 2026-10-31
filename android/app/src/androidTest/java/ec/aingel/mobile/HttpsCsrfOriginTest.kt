package ec.aingel.mobile

import android.content.Context
import android.content.ContextWrapper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/** Ensures Django's HTTPS CSRF origin validation receives an explicit same-origin header. */
@RunWith(AndroidJUnit4::class)
class HttpsCsrfOriginTest {
    @Test fun jsonAndMultipartWritesCarrySameOrigin() = runBlocking {
        val suffix = UUID.randomUUID().toString()
        val context = object : ContextWrapper(InstrumentationRegistry.getInstrumentation().targetContext) {
            override fun getSharedPreferences(name: String, mode: Int) =
                super.getSharedPreferences("csrf-origin-$suffix-$name", mode)
        }
        MockWebServer().use { server ->
            server.start()
            val api = ApiClient(context)
            val base = server.url("/").toString()
            api.configure(base)
            server.enqueue(MockResponse().setBody("{\"csrf\":\"test-csrf\",\"user\":null}"))
            api.request("auth/session/")
            server.takeRequest()
            server.enqueue(MockResponse().setBody("{}"))
            api.request("auth/login/", "POST", JSONObject().put("username", "example"))
            val login = server.takeRequest()
            assertEquals(base.removeSuffix("/"), login.getHeader("Origin"))
            assertEquals("test-csrf", login.getHeader("X-CSRFToken"))
            server.enqueue(MockResponse().setBody("{}"))
            api.upload("scene/", byteArrayOf(1, 2, 3), mapOf("synthetic" to "true"))
            val upload = server.takeRequest()
            assertEquals(base.removeSuffix("/"), upload.getHeader("Origin"))
            assertEquals("test-csrf", upload.getHeader("X-CSRFToken"))
            api.clear()
        }
    }
}
