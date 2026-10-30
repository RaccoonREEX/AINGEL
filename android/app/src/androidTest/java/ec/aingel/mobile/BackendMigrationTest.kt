package ec.aingel.mobile

import android.content.Context
import android.content.ContextWrapper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class BackendMigrationTest {
    private fun isolatedContext(): Context {
        val suffix = UUID.randomUUID().toString()
        return object : ContextWrapper(InstrumentationRegistry.getInstrumentation().targetContext) {
            override fun getSharedPreferences(name: String, mode: Int) =
                super.getSharedPreferences("migration-test-$suffix-$name", mode)
        }
    }

    @Test fun oldLoopbackIsMigratedOnceAndSessionIsDiscarded() = runBlocking {
        val context = isolatedContext()
        val server = MockWebServer(); server.start()
        try {
            val api = ApiClient(context)
            api.configure(server.url("/").toString())
            server.enqueue(MockResponse().addHeader("Set-Cookie", "sessionid=synthetic; Path=/; HttpOnly").setBody("{}"))
            api.request("auth/session/")
            assertNotNull(context.getSharedPreferences("aingel-session", Context.MODE_PRIVATE).getString("cookies", null))
            // Recreate a pre-upgrade installation with a saved local backend.
            context.getSharedPreferences("aingel-config", Context.MODE_PRIVATE).edit()
                .remove("backend-default-migrated-v1").commit()
            val migrated = ApiClient(context)
            assertEquals(DEFAULT_BACKEND, migrated.base)
            assertNull(context.getSharedPreferences("aingel-session", Context.MODE_PRIVATE).getString("cookies", null))
            // A deliberate local configuration after migration remains usable for tests.
            migrated.configure(server.url("/").toString())
            assertEquals(server.url("/").toString(), ApiClient(context).base)
            migrated.clear()
        } finally { server.shutdown() }
    }

    @Test fun customHttpsBackendIsPreserved() {
        val context = isolatedContext()
        context.getSharedPreferences("aingel-config", Context.MODE_PRIVATE).edit()
            .putString("backend", "https://custom.example/").commit()
        assertEquals("https://custom.example/", ApiClient(context).base)
    }
}
