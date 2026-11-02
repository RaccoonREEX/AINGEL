package ec.aingel.mobile

import android.util.Base64
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayInputStream
import java.security.KeyStore
import java.security.cert.CertificateFactory
import java.util.UUID
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManagerFactory
import javax.net.ssl.X509TrustManager

/**
 * Real Django over real HTTPS, not MockWebServer: the app's own transport (ApiTransport) against
 * backend/scripts/serve_https_check.py (this branch's code, Daphne with TLS, production's Secure cookies and CSRF rules,
 * throwaway database, AI in mock mode) behind `adb reverse tcp:8443 tcp:8443`.
 * Opt-in: -e aingelHttpsBackend https://127.0.0.1:8443/ -e aingelHttpsCa <base64 DER printed by the script>.
 * Only loopback or .test hosts are accepted: it creates one account, so it never runs against production.
 */
@RunWith(AndroidJUnit4::class)
class RealDjangoHttpsCsrfTest {
    private class MemoryCookies : CookieJar {
        val all = mutableListOf<Cookie>()
        override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
            synchronized(all) { cookies.forEach { c -> all.removeAll { it.name == c.name }; all.add(c) } }
        }
        override fun loadForRequest(url: HttpUrl) = synchronized(all) { all.filter { it.matches(url) } }
    }

    @Test fun sessionRegisterAndWritesWithRealCsrfOverHttps() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        val base = args.getString("aingelHttpsBackend")
        val ca = args.getString("aingelHttpsCa")
        assumeTrue(base != null && ca != null)
        val url = base!!.toHttpUrl()
        assertTrue("HTTPS only", url.isHttps)
        assertTrue("never production: loopback or .test hosts only", url.host in setOf("127.0.0.1", "localhost") || url.host.endsWith(".test"))

        // Trust only the throwaway certificate of this run.
        val certificate = CertificateFactory.getInstance("X.509").generateCertificate(ByteArrayInputStream(Base64.decode(ca, Base64.DEFAULT)))
        val keys = KeyStore.getInstance(KeyStore.getDefaultType()).apply { load(null); setCertificateEntry("check", certificate) }
        val trust = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()).apply { init(keys) }.trustManagers.single() as X509TrustManager
        val tls = SSLContext.getInstance("TLS").apply { init(null, arrayOf(trust), null) }
        val cookies = MemoryCookies()
        val transport = ApiTransport(SessionCookieGate(cookies) { synchronized(cookies.all) { cookies.all.clear() } }, base,
            defaultHttpClientBuilder().sslSocketFactory(tls.socketFactory, trust))

        val session = transport.request("auth/session/") as JSONObject
        val terms = session.getString("terms_version")
        val csrfCookie = synchronized(cookies.all) { cookies.all.single { it.name == "csrftoken" } }
        assertTrue("Django marks the CSRF cookie Secure over HTTPS", csrfCookie.secure)

        // A real write: the transport sends X-CSRFToken and the same-origin Origin header; Django accepts it.
        val username = "https-check-" + UUID.randomUUID().toString().take(8)
        val registered = transport.request("auth/register/", "POST", JSONObject().put("username", username)
            .put("password", "Https-Check-" + UUID.randomUUID()).put("adult", true).put("terms_version", terms).put("territory", TERRITORY_OUTSIDE).put("territory_version", session.getString("territory_version"))) as JSONObject
        assertEquals(username, registered.getJSONObject("user").getString("username"))
        assertTrue("the session cookie is Secure too", synchronized(cookies.all) { cookies.all.single { it.name == "sessionid" }.secure })

        // Django's own CSRF rejects writes without the same-origin header or from another origin, even with the token.
        val token = synchronized(cookies.all) { cookies.all.single { it.name == "csrftoken" }.value }
        val client = transport.client
        suspend fun logout(origin: String?): Int = withContext(Dispatchers.IO) {
            val request = Request.Builder().url(base + "api/v1/auth/logout/").header("X-CSRFToken", token)
                .apply { if (origin != null) header("Origin", origin) }
                .post("{}".toRequestBody("application/json".toMediaType())).build()
            client.newCall(request).execute().use { it.code }
        }
        assertEquals(403, logout(null))
        assertEquals(403, logout("https://attacker.example"))
        assertNotEquals(JSONObject.NULL, (transport.request("auth/session/") as JSONObject).get("user"))

        // And the transport's own write signs out.
        val out = transport.request("auth/logout/", "POST") as JSONObject
        assertEquals(JSONObject.NULL, out.get("user"))
        transport.clear()
    }
}
