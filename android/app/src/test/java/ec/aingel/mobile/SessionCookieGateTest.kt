package ec.aingel.mobile

import okhttp3.Call
import okhttp3.Callback
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class SessionCookieGateTest {
    private class TestCookies : CookieJar {
        val stored = mutableListOf<Cookie>()
        override fun loadForRequest(url: HttpUrl): List<Cookie> = stored.filter { it.matches(url) }
        override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) { stored.clear(); stored.addAll(cookies) }
    }

    @Test fun responseFromOldSessionCannotRestoreCookiesAfterLogoutOrServerChange() {
        val server = MockWebServer()
        server.start()
        try {
            val stored = TestCookies()
            val gate = SessionCookieGate(stored) { stored.stored.clear() }
            val oldJar = gate.cookieJar()
            val oldClient = OkHttpClient.Builder().cookieJar(oldJar).build()
            server.enqueue(MockResponse().setHeadersDelay(750, TimeUnit.MILLISECONDS).addHeader("Set-Cookie", "sessionid=old; Path=/; HttpOnly").setBody("{}"))
            val complete = CountDownLatch(1)
            oldClient.newCall(Request.Builder().url(server.url("/old")).build()).enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) { complete.countDown() }
                override fun onResponse(call: Call, response: Response) { response.close(); complete.countDown() }
            })
            assertNotNull(server.takeRequest(5, TimeUnit.SECONDS))

            gate.invalidate()
            val newClient = oldClient.newBuilder().cookieJar(gate.cookieJar()).build()
            server.enqueue(MockResponse().addHeader("Set-Cookie", "sessionid=new; Path=/; HttpOnly").setBody("{}"))
            newClient.newCall(Request.Builder().url(server.url("/new")).build()).execute().use { assertEquals(200, it.code) }
            assertTrue(complete.await(5, TimeUnit.SECONDS))
            assertEquals("new", stored.stored.single().value)
            assertTrue(oldJar.loadForRequest(server.url("/")).isEmpty())
        } finally { server.shutdown() }
    }
}
