package ec.aingel.mobile

import android.content.Context
import android.content.ContextWrapper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/** Explicit opt-in live smoke test. It never uses or clears the user's saved session. */
@RunWith(AndroidJUnit4::class)
class PublicBackendConnectivityTest {
    @Test fun anonymousSessionWorksOverPublicHttps() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("aingelLiveNetwork") == "true")
        val suffix = UUID.randomUUID().toString()
        val context = object : ContextWrapper(InstrumentationRegistry.getInstrumentation().targetContext) {
            override fun getSharedPreferences(name: String, mode: Int) =
                super.getSharedPreferences("live-connectivity-$suffix-$name", mode)
        }
        val api = ApiClient(context)
        try {
            assertEquals("https://aingel.mapatechstudio.com/", api.base)
            val session = api.request("auth/session/") as JSONObject
            assertTrue(session.isNull("user"))
            assertTrue(session.getString("csrf").isNotBlank())
            assertTrue(api.csrf.isNotBlank())
        } finally {
            api.clear()
            context.getSharedPreferences("aingel-config", Context.MODE_PRIVATE).edit().clear().commit()
            context.getSharedPreferences("aingel-session", Context.MODE_PRIVATE).edit().clear().commit()
        }
    }
}
