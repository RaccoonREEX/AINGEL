package ec.aingel.mobile

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.io.InterruptedIOException
import java.net.ConnectException
import java.net.SocketException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.security.cert.CertPathValidatorException
import javax.net.ssl.SSLHandshakeException
import javax.net.ssl.SSLPeerUnverifiedException

class NetworkErrorsTest {
    private fun failure(block: () -> Any): ApiFailure = try { block(); fail("Expected ApiFailure"); throw AssertionError() } catch (e: ApiFailure) { e }

    @Test fun transportExceptionsMapToStableCodes() {
        val certificate = SSLHandshakeException("handshake").apply { initCause(CertPathValidatorException("Trust anchor for certification path not found.")) }
        assertEquals("tls_failed", failureForIOException(certificate, null).code)
        assertEquals("tls_failed", failureForIOException(SSLPeerUnverifiedException("Hostname not verified"), true).code)
        assertEquals("tls_failed", failureForIOException(IOException("wrapped", CertPathValidatorException("expired")), true).code)
        assertEquals("timeout", failureForIOException(SocketTimeoutException("Read timed out"), true).code)
        assertEquals("timeout", failureForIOException(InterruptedIOException("timeout"), null).code)
        assertEquals("dns_failed", failureForIOException(UnknownHostException("Unable to resolve host"), null).code)
        assertEquals("network_unavailable", failureForIOException(UnknownHostException("Unable to resolve host"), false).code)
        assertEquals("network_unavailable", failureForIOException(ConnectException("failed"), false).code)
        assertEquals("network_unavailable", failureForIOException(SocketException("connect failed: ENETUNREACH (Network is unreachable)"), null).code)
        assertEquals("server_unreachable", failureForIOException(ConnectException("Failed to connect"), true).code)
        assertEquals("server_unavailable", failureForIOException(IOException("unexpected end of stream"), true).code)
        assertEquals("request_cancelled", failureForIOException(IOException("Canceled"), true).code)
        // The exception message is the code only, never the underlying (possibly host-revealing) text.
        assertEquals("dns_failed", failureForIOException(UnknownHostException("private.example"), null).message)
    }

    @Test fun redirectsAreNeverFollowedOrParsed() {
        val moved = failure { decodeApiResponse(301, "text/html", null, "https://elsewhere.example/api/v1/x/") }
        assertEquals("redirect_unexpected", moved.code); assertEquals(301, moved.status)
        val upgrade = failure { decodeApiResponse(308, null, null, "https://aingel.example/api/v1/x/", requestScheme = "http") }
        assertEquals("https_required", upgrade.code); assertEquals(308, upgrade.status)
        assertEquals("redirect_unexpected", failure { decodeApiResponse(302, null, "", null, requestScheme = "https") }.code)
    }

    @Test fun htmlErrorPagesMapToSafeCodes() {
        val page = "<html><body><h1>502 Bad Gateway</h1><p>nginx</p></body></html>"
        val gateway = failure { decodeApiResponse(502, "text/html; charset=utf-8", page) }
        assertEquals("server_html_error", gateway.code); assertEquals(502, gateway.status)
        assertFalse(gateway.message.orEmpty().contains("nginx"))
        val csrf = "<h1>Forbidden <span>(403)</span></h1><p>CSRF verification failed. Request aborted.</p>"
        assertEquals("csrf_failed", failure { decodeApiResponse(403, "text/html", csrf) }.code)
        assertEquals("server_html_error", failure { decodeApiResponse(403, "text/html", "<h1>Forbidden</h1>") }.code)
        assertEquals("not_found", failure { decodeApiResponse(404, "text/html", "<h1>Not Found</h1>") }.code)
        assertEquals("payload_too_large", failure { decodeApiResponse(413, "text/html", "<h1>413</h1>") }.code)
        // A captive portal answering 200 with HTML is not a successful API call.
        assertEquals("server_html_error", failure { decodeApiResponse(200, "text/html", "<!doctype html><title>Login</title>") }.code)
        // HTML without a content type is still recognised.
        assertEquals("server_html_error", failure { decodeApiResponse(503, null, "  <html>maintenance</html>") }.code)
    }

    @Test fun jsonErrorsKeepServerCodesAndFallBackByStatus() {
        assertEquals("credentials_invalid", failure { decodeApiResponse(400, "application/json", "{\"error\":\"credentials_invalid\"}") }.code)
        assertEquals("face_too_many", failure { decodeApiResponse(400, "application/json", "[\"face_too_many\"]") }.code)
        assertEquals("object_prompt_invalid", failure { decodeApiResponse(400, "application/json", "{\"object\":[\"object_prompt_invalid\"]}") }.code)
        assertEquals("validation_failed", failure { decodeApiResponse(400, "application/json", "{\"username\":[\"This field is required.\"]}") }.code)
        // Echoed single-word values are never mistaken for a code.
        assertEquals("validation_failed", failure { decodeApiResponse(400, "application/json", "{\"username\":[\"maria\"]}") }.code)
        val notAuthenticated = failure { decodeApiResponse(403, "application/json", "{\"detail\":\"Authentication credentials were not provided.\"}") }
        assertEquals("authentication_required", notAuthenticated.code); assertEquals(403, notAuthenticated.status)
        assertEquals("authentication_required", failure { decodeApiResponse(401, "application/json", "{}") }.code)
        assertEquals("permission_denied", failure { decodeApiResponse(403, "application/json", "{\"detail\":\"You do not have permission to perform this action.\"}") }.code)
        assertEquals("meta_access_denied", failure { decodeApiResponse(403, "application/json", "{\"error\":\"meta_access_denied\"}") }.code)
        assertEquals("csrf_failed", failure { decodeApiResponse(403, "application/json", "{\"detail\":\"CSRF Failed: Origin checking failed - https://x.example does not match any trusted origins.\"}") }.code)
        assertEquals("not_found", failure { decodeApiResponse(404, "application/json", "{\"detail\":\"Not found.\"}") }.code)
        assertEquals("companion_source_not_found", failure { decodeApiResponse(404, "application/json", "{\"error\":\"companion_source_not_found\"}") }.code)
        assertEquals("server_error", failure { decodeApiResponse(500, "application/json", "{\"detail\":\"A server error occurred.\"}") }.code)
        assertEquals("model_unavailable", failure { decodeApiResponse(503, "application/json", "{\"error\":\"model_unavailable\"}") }.code)
        assertEquals("server_unavailable", failure { decodeApiResponse(502, null, "") }.code)
        assertEquals("request_invalid", failure { decodeApiResponse(405, "application/json", "{\"detail\":\"Method \\\"PUT\\\" not allowed.\"}") }.code)
    }

    @Test fun rateLimitsCarryRetryAfter() {
        val throttled = failure { decodeApiResponse(429, "application/json", "{\"detail\":\"Request was throttled. Expected available in 30 seconds.\"}", retryAfter = "30") }
        assertEquals("rate_limited", throttled.code); assertEquals(429, throttled.status); assertEquals(30L, throttled.retryAfterSeconds)
        val login = failure { decodeApiResponse(429, "application/json", "{\"error\":\"auth_rate_limited\"}") }
        assertEquals("auth_rate_limited", login.code); assertNull(login.retryAfterSeconds)
        assertEquals("rate_limited", failure { decodeApiResponse(429, "text/html", "<h1>429</h1>", retryAfter = "abc") }.code)
        val now = 1_700_000_000_000L
        assertEquals(120L, retryAfterSeconds("Tue, 14 Nov 2023 22:15:20 GMT", now))
        assertEquals(86_400L, retryAfterSeconds("999999999", now))
        assertNull(retryAfterSeconds("-5", now)); assertNull(retryAfterSeconds(null, now)); assertNull(retryAfterSeconds("soon", now))
    }

    @Test fun successfulResponsesDecode() {
        assertEquals("t", (decodeApiResponse(200, "application/json", "{\"csrf\":\"t\"}") as JSONObject).getString("csrf"))
        assertEquals(1, (decodeApiResponse(200, null, "[1]") as JSONArray).length())
        assertEquals(0, (decodeApiResponse(204, null, "") as JSONObject).length())
        assertEquals("response_invalid", failure { decodeApiResponse(200, "text/plain", "ok") }.code)
        assertEquals("response_invalid", failure { decodeApiResponse(200, "application/json", "{broken") }.code)
        assertEquals("response_invalid", failure { decodeApiResponse(200, "application/json", "") }.code)
    }

    @Test fun debugCodeAndMessagesAreSafe() {
        assertEquals("csrf_failed·403", ApiFailure("csrf_failed", 403).debugCode())
        assertEquals("timeout", ApiFailure("timeout").debugCode())
        listOf("csrf_failed", "tls_failed", "server_html_error", "rate_limited", "redirect_unexpected", "https_required",
            "network_unavailable", "timeout", "dns_failed", "server_unreachable", "server_error", "not_found",
            "validation_failed", "payload_too_large", "response_invalid").forEach { assertNotNull(it, networkErrorMessage(it)) }
        // Codes the app already maps itself are left to the existing mapping.
        listOf("server_unavailable", "authentication_required", "permission_denied", "credentials_invalid").forEach { assertNull(it, networkErrorMessage(it)) }
    }

    @Test fun savedBackendsMigrateToThePublicDefault() {
        // Fresh install.
        assertEquals(SavedBackend(DEFAULT_BACKEND, false, false), resolveSavedBackend(null, migrated = false, debug = false))
        // Development loopback from before the public default: moved once and its session discarded.
        listOf("http://127.0.0.1:8010/", "http://localhost:8010/", "http://10.0.2.2:8010/").forEach {
            assertEquals(SavedBackend(DEFAULT_BACKEND, true, true), resolveSavedBackend(it, migrated = false, debug = true))
        }
        // A deliberate loopback chosen after migration stays in debug builds, never in release builds.
        assertEquals(SavedBackend("http://127.0.0.1:8010/", false, false), resolveSavedBackend("http://127.0.0.1:8010/", migrated = true, debug = true))
        assertEquals(SavedBackend(DEFAULT_BACKEND, true, true), resolveSavedBackend("http://127.0.0.1:8010/", migrated = true, debug = false))
        // Plain-http LAN or malformed values are never used.
        assertEquals(SavedBackend(DEFAULT_BACKEND, true, true), resolveSavedBackend("http://192.168.1.20:8010/", migrated = false, debug = true))
        assertEquals(SavedBackend(DEFAULT_BACKEND, true, true), resolveSavedBackend("not a url", migrated = true, debug = true))
        // Custom HTTPS backends are preserved (and normalised).
        assertEquals(SavedBackend("https://custom.example/", false, false), resolveSavedBackend("https://custom.example/", migrated = true, debug = false))
        assertEquals(SavedBackend("https://custom.example/", false, true), resolveSavedBackend("https://CUSTOM.example", migrated = true, debug = false))
        assertEquals(SavedBackend(DEFAULT_BACKEND, false, false), resolveSavedBackend(DEFAULT_BACKEND, migrated = false, debug = false))
    }
}
