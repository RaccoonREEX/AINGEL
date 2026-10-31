package ec.aingel.mobile

import kotlinx.coroutines.runBlocking
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.Dns
import okhttp3.HttpUrl
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.net.InetAddress
import java.net.ServerSocket
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

/** End-to-end HTTP behaviour of the API core against a local MockWebServer (no real network). */
class ApiTransportTest {
    private class MemoryCookies : CookieJar {
        val cookies = mutableListOf<Cookie>()
        @Synchronized override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
            for (cookie in cookies) { this.cookies.removeAll { it.name == cookie.name }; this.cookies.add(cookie) }
        }
        @Synchronized override fun loadForRequest(url: HttpUrl) = cookies.filter { it.matches(url) }
        @Synchronized fun clear() = cookies.clear()
    }

    private lateinit var server: MockWebServer
    private val jar = MemoryCookies()
    private fun transport(
        base: String = server.url("/").toString(),
        online: Boolean? = null,
        configure: okhttp3.OkHttpClient.Builder.() -> Unit = {},
    ) = ApiTransport(SessionCookieGate(jar, jar::clear), base, defaultHttpClientBuilder().apply(configure), online = { online })

    private fun json(body: String, status: Int = 200) = MockResponse().setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body)
    private fun failure(block: suspend () -> Any): ApiFailure = runBlocking {
        try { block(); fail("Expected ApiFailure"); throw AssertionError() } catch (e: ApiFailure) { e }
    }

    @Before fun start() { server = MockWebServer(); server.start() }
    @After fun stop() { server.shutdown() }

    @Test fun firstWriteBootstrapsCsrfFromSession() = runBlocking {
        val api = transport()
        server.enqueue(json("{\"csrf\":\"boot-token\",\"user\":null}").addHeader("Set-Cookie", "csrftoken=cookie-secret; Path=/; SameSite=Lax"))
        server.enqueue(json("{\"user\":{\"id\":1},\"csrf\":\"rotated\"}"))
        api.request("auth/login/", "POST", JSONObject().put("username", "synthetic"))
        val session = server.takeRequest()
        assertEquals("GET", session.method); assertEquals("/api/v1/auth/session/", session.path)
        val login = server.takeRequest()
        assertEquals("POST", login.method); assertEquals("/api/v1/auth/login/", login.path)
        assertEquals("boot-token", login.getHeader("X-CSRFToken"))
        assertEquals(server.url("/").toString().removeSuffix("/"), login.getHeader("Origin"))
        assertTrue(login.getHeader("Cookie").orEmpty().contains("csrftoken=cookie-secret"))
        // Login rotates the token; the next write must use the rotated one without another bootstrap.
        assertEquals("rotated", api.csrf)
        server.enqueue(json("{}"))
        api.request("auth/logout/", "POST")
        assertEquals("rotated", server.takeRequest().getHeader("X-CSRFToken"))
        assertEquals(3, server.requestCount)
    }

    @Test fun csrfRejectionRefreshesTokenAndRetriesOnce() = runBlocking {
        val api = transport()
        server.enqueue(json("{\"csrf\":\"stale\"}"))
        api.request("auth/session/")
        server.takeRequest()
        server.enqueue(MockResponse().setResponseCode(403).setHeader("Content-Type", "text/html")
            .setBody("<h1>Forbidden <span>(403)</span></h1><p>CSRF verification failed. Request aborted.</p>"))
        server.enqueue(json("{\"csrf\":\"fresh\"}"))
        server.enqueue(json("{\"id\":\"p1\"}"))
        val result = api.request("profiles/", "POST", JSONObject().put("display_name", "Synthetic")) as JSONObject
        assertEquals("p1", result.getString("id"))
        assertEquals("stale", server.takeRequest().getHeader("X-CSRFToken"))
        assertEquals("/api/v1/auth/session/", server.takeRequest().path)
        val retry = server.takeRequest()
        assertEquals("fresh", retry.getHeader("X-CSRFToken")); assertEquals("{\"display_name\":\"Synthetic\"}", retry.body.readUtf8())
    }

    @Test fun persistentCsrfFailureSurfacesCsrfFailed() {
        val api = transport()
        val origin = json("{\"detail\":\"CSRF Failed: Origin checking failed - https://x.example does not match any trusted origins.\"}", 403)
        server.enqueue(json("{\"csrf\":\"a\"}")); server.enqueue(origin)
        server.enqueue(json("{\"csrf\":\"b\"}")); server.enqueue(origin)
        val error = failure { api.request("auth/login/", "POST") }
        assertEquals("csrf_failed", error.code); assertEquals(403, error.status)
        assertFalse(error.message.orEmpty().contains("x.example"))
        assertEquals(4, server.requestCount)
    }

    @Test fun multipartUploadAlsoBootstrapsCsrf() = runBlocking {
        val api = transport()
        server.enqueue(json("{\"csrf\":\"upload-token\"}")); server.enqueue(json("{\"objects\":[]}"))
        api.uploadImages("scene/", listOf(byteArrayOf(1, 2, 3)), mapOf("synthetic" to "true"))
        server.takeRequest()
        val upload = server.takeRequest()
        assertEquals("upload-token", upload.getHeader("X-CSRFToken"))
        assertEquals(server.url("/").toString().removeSuffix("/"), upload.getHeader("Origin"))
    }

    @Test fun redirectsProduceSpecificErrorsWithoutFollowing() {
        val api = transport()
        server.enqueue(MockResponse().setResponseCode(301).setHeader("Location", "https://aingel.example/api/v1/auth/session/").setBody("<html>Moved</html>"))
        val upgrade = failure { api.request("auth/session/") }
        assertEquals("https_required", upgrade.code); assertEquals(301, upgrade.status)
        server.enqueue(MockResponse().setResponseCode(302).setHeader("Location", "/api/v1/profiles"))
        val slash = failure { api.request("profiles") }
        assertEquals("redirect_unexpected", slash.code); assertEquals(302, slash.status)
        server.enqueue(json("{\"csrf\":\"t\"}"))
        server.enqueue(MockResponse().setResponseCode(307).setHeader("Location", server.url("/elsewhere").toString()))
        assertEquals("redirect_unexpected", failure { api.request("auth/login/", "POST") }.code)
        assertEquals(4, server.requestCount)
    }

    @Test fun proxyHtmlAndStatusErrorsMapToSafeCodes() {
        val api = transport()
        server.enqueue(MockResponse().setResponseCode(502).setHeader("Content-Type", "text/html").setBody("<html><center>nginx</center></html>"))
        val gateway = failure { api.request("auth/session/") }
        assertEquals("server_html_error", gateway.code); assertEquals(502, gateway.status)
        server.enqueue(MockResponse().setResponseCode(502))
        assertEquals("server_unavailable", failure { api.request("auth/session/") }.code)
        server.enqueue(MockResponse().setResponseCode(404).setHeader("Content-Type", "text/html").setBody("<h1>Not Found</h1>"))
        assertEquals("not_found", failure { api.request("missing/") }.code)
        server.enqueue(json("{\"detail\":\"Request was throttled. Expected available in 12 seconds.\"}", 429).setHeader("Retry-After", "12"))
        val throttled = failure { api.request("profiles/") }
        assertEquals("rate_limited", throttled.code); assertEquals(429, throttled.status); assertEquals(12L, throttled.retryAfterSeconds)
        server.enqueue(json("{\"detail\":\"Authentication credentials were not provided.\"}", 403))
        val anonymous = failure { api.request("profiles/") }
        assertEquals("authentication_required", anonymous.code); assertEquals(403, anonymous.status)
        // csrf is still blank, so the first write bootstraps it before the login itself.
        server.enqueue(json("{\"csrf\":\"t\"}")); server.enqueue(json("{\"error\":\"credentials_invalid\"}", 400))
        val invalid = failure { api.request("auth/login/", "POST") }
        assertEquals("credentials_invalid", invalid.code); assertEquals(400, invalid.status)
        server.enqueue(json("{\"display_name\":[\"This field may not be blank.\"]}", 400))
        assertEquals("validation_failed", failure { api.request("profiles/", "POST") }.code)
    }

    @Test fun timeoutsDnsTlsAndRefusedConnectionsAreDistinguished() {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))
        val slow = transport { readTimeout(300, TimeUnit.MILLISECONDS) }
        assertEquals("timeout", failure { slow.request("auth/session/") }.code)

        val noDns = object : Dns { override fun lookup(hostname: String) = throw UnknownHostException("synthetic") }
        assertEquals("dns_failed", failure { transport(base = "https://aingel.invalid/") { dns(noDns) }.request("auth/session/") }.code)
        assertEquals("network_unavailable", failure { transport(base = "https://aingel.invalid/", online = false) { dns(noDns) }.request("auth/session/") }.code)

        // A plain-HTTP listener answering a TLS ClientHello fails the handshake.
        ServerSocket(0, 1, InetAddress.getLoopbackAddress()).use { plain ->
            thread(isDaemon = true) {
                runCatching { while (true) plain.accept().use { it.getOutputStream().write("HTTP/1.1 400 Bad Request\r\n\r\n".toByteArray()); it.getOutputStream().flush(); Thread.sleep(200) } }
            }
            val tls = failure { transport(base = "https://127.0.0.1:${plain.localPort}/") { readTimeout(5, TimeUnit.SECONDS) }.request("auth/session/") }
            assertEquals("tls_failed", tls.code)
        }

        val closed = MockWebServer().apply { start() }
        val port = closed.port
        closed.shutdown()
        assertEquals("server_unreachable", failure { transport(base = "http://127.0.0.1:$port/").request("auth/session/") }.code)
    }

    @Test fun clearingTheSessionDropsTokenAndCookies() = runBlocking {
        val api = transport()
        server.enqueue(json("{\"csrf\":\"one\"}").addHeader("Set-Cookie", "sessionid=synthetic; Path=/; HttpOnly; SameSite=Lax"))
        api.request("auth/session/")
        assertEquals("one", api.csrf); assertEquals(1, jar.cookies.size)
        api.clear()
        assertEquals("", api.csrf); assertTrue(jar.cookies.isEmpty())
        server.enqueue(json("{\"csrf\":\"two\"}")); server.enqueue(json("{}"))
        api.request("auth/login/", "POST")
        server.takeRequest()
        assertNull(server.takeRequest().getHeader("Cookie"))
        assertEquals("two", server.takeRequest().getHeader("X-CSRFToken"))
    }

    @Test fun secureCookiesAreNeverSentOverPlainHttp() = runBlocking {
        val api = transport()
        server.enqueue(json("{\"csrf\":\"t\"}").addHeader("Set-Cookie", "sessionid=secret; Path=/; Secure; HttpOnly; SameSite=Lax"))
        api.request("auth/session/")
        server.enqueue(json("{}"))
        api.request("auth/session/")
        server.takeRequest()
        assertNull(server.takeRequest().getHeader("Cookie"))
    }
}
