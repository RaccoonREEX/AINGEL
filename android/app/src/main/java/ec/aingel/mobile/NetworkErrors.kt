package ec.aingel.mobile

import okhttp3.Headers.Companion.headersOf
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.io.InterruptedIOException
import java.net.ConnectException
import java.net.NoRouteToHostException
import java.net.SocketException
import java.net.UnknownHostException
import java.security.cert.CertPathValidatorException
import java.security.cert.CertificateException
import javax.net.ssl.SSLException

/**
 * Stable, client-side error codes for transport and HTTP failures. They are safe to log and to show
 * as a short technical code: they never contain server bodies, tokens, URLs or personal data.
 * Server-provided snake_case codes (e.g. `credentials_invalid`) keep flowing through unchanged.
 */
internal object NetworkError {
    const val CSRF_FAILED = "csrf_failed"
    const val TLS_FAILED = "tls_failed"
    const val SERVER_HTML_ERROR = "server_html_error"
    const val RATE_LIMITED = "rate_limited"
    const val REDIRECT_UNEXPECTED = "redirect_unexpected"
    const val HTTPS_REQUIRED = "https_required"
    const val NETWORK_UNAVAILABLE = "network_unavailable"
    const val TIMEOUT = "timeout"
    const val DNS_FAILED = "dns_failed"
    const val SERVER_UNREACHABLE = "server_unreachable"
    /** Pre-existing generic code (kept: UI maps it to the connection message). */
    const val SERVER_UNAVAILABLE = "server_unavailable"
    const val SERVER_ERROR = "server_error"
    const val NOT_FOUND = "not_found"
    const val VALIDATION_FAILED = "validation_failed"
    const val PERMISSION_DENIED = "permission_denied"
    const val AUTHENTICATION_REQUIRED = "authentication_required"
    const val PAYLOAD_TOO_LARGE = "payload_too_large"
    const val RESPONSE_INVALID = "response_invalid"
    const val REQUEST_INVALID = "request_invalid"
    const val REQUEST_CANCELLED = "request_cancelled"
}

private val TOP_LEVEL_CODE = Regex("[a-z][a-z0-9_]*")
/** Nested field errors must look like a backend code (contain `_`) so echoed values are never surfaced. */
private val FIELD_CODE = Regex("[a-z][a-z0-9]*(_[a-z0-9]+)+")

private fun topLevelCode(message: String): String? = message.takeIf { it.length <= 80 && it.matches(TOP_LEVEL_CODE) }

/** Maps the bounded set of Django REST framework default messages; anything else must already be a code. */
private fun detailCode(message: String): String? = when {
    message.contains("CSRF") -> NetworkError.CSRF_FAILED
    message.contains("Authentication credentials were not provided") || message.contains("Incorrect authentication credentials") -> NetworkError.AUTHENTICATION_REQUIRED
    message.startsWith("You do not have permission") -> NetworkError.PERMISSION_DENIED
    message.startsWith("Request was throttled") -> NetworkError.RATE_LIMITED
    message == "Not found." -> NetworkError.NOT_FOUND
    else -> topLevelCode(message)
}

private fun firstFieldCode(value: Any?, depth: Int = 0): String? {
    if (depth > 3) return null
    return when (value) {
        is String -> value.takeIf { it.length <= 80 && it.matches(FIELD_CODE) }
        is JSONArray -> (0 until minOf(value.length(), 20)).firstNotNullOfOrNull { firstFieldCode(value.opt(it), depth + 1) }
        is JSONObject -> value.keys().asSequence().take(20).firstNotNullOfOrNull { firstFieldCode(value.opt(it), depth + 1) }
        else -> null
    }
}

/** Safe error code from a parsed JSON error body, or null when the body carries no recognisable code. */
internal fun apiErrorCode(result: Any?): String? = when (result) {
    is JSONArray -> result.opt(0).let { first -> if (first is String) detailCode(first) else firstFieldCode(first) }
    is JSONObject -> {
        val error = result.opt("error") as? String
        val detail = result.opt("detail") as? String
        error?.let(::detailCode) ?: detail?.let(::detailCode) ?: firstFieldCode(result)
    }
    else -> null
}

private fun statusCode(status: Int): String = when {
    status in 300..399 -> NetworkError.REDIRECT_UNEXPECTED
    status == 400 -> NetworkError.VALIDATION_FAILED
    status == 401 -> NetworkError.AUTHENTICATION_REQUIRED
    status == 403 -> NetworkError.PERMISSION_DENIED
    status == 404 -> NetworkError.NOT_FOUND
    status == 408 -> NetworkError.TIMEOUT
    status == 413 -> NetworkError.PAYLOAD_TOO_LARGE
    status == 429 -> NetworkError.RATE_LIMITED
    status == 502 || status == 503 || status == 504 -> NetworkError.SERVER_UNAVAILABLE
    status in 500..599 -> NetworkError.SERVER_ERROR
    else -> NetworkError.REQUEST_INVALID
}

/** Seconds from a `Retry-After` header (delta-seconds or HTTP-date), bounded to one day. */
internal fun retryAfterSeconds(value: String?, nowMillis: Long = System.currentTimeMillis()): Long? {
    val raw = value?.trim()?.takeIf { it.isNotEmpty() } ?: return null
    val seconds = raw.toLongOrNull() ?: headersOf("Retry-After", raw).getDate("Retry-After")?.let { date ->
        ((date.time - nowMillis + 999) / 1000).coerceAtLeast(0)
    } ?: return null
    return seconds.takeIf { it >= 0 }?.coerceAtMost(86_400)
}

private fun isHtml(contentType: String?, body: String): Boolean =
    contentType?.lowercase()?.let { "html" in it || "xml" in it } == true || body.trimStart().startsWith("<")

private fun isJsonType(contentType: String?): Boolean = contentType?.lowercase()?.substringBefore(';')?.trim()
    ?.let { it == "application/json" || it.endsWith("+json") } == true

/**
 * Decodes an API response or throws a safe [ApiFailure]. HTML (proxy/Django error pages, captive portals)
 * and redirects are never parsed as JSON and their text is never surfaced.
 *
 * @param requestScheme scheme of the request URL, used to identify http→https upgrade redirects.
 */
internal fun decodeApiResponse(
    status: Int,
    contentType: String?,
    body: String?,
    location: String? = null,
    retryAfter: String? = null,
    requestScheme: String = "https",
): Any {
    val retry = if (status == 429 || status == 503) retryAfterSeconds(retryAfter) else null
    if (status in 300..399) {
        val upgrade = requestScheme == "http" && location?.trim()?.startsWith("https://", ignoreCase = true) == true
        throw ApiFailure(if (upgrade) NetworkError.HTTPS_REQUIRED else NetworkError.REDIRECT_UNEXPECTED, status)
    }
    val text = body.orEmpty()
    val success = status in 200..299
    if (success && (status == 204 || status == 205) && text.isBlank()) return JSONObject()
    val trimmed = text.trimStart()
    val looksJson = trimmed.startsWith("{") || trimmed.startsWith("[")
    val parsed: Any? = if (looksJson && (isJsonType(contentType) || !isHtml(contentType, text))) {
        try { if (trimmed.startsWith("[")) JSONArray(text) else JSONObject(text) } catch (_: Exception) { null }
    } else null
    if (success) return parsed ?: throw ApiFailure(if (isHtml(contentType, text)) NetworkError.SERVER_HTML_ERROR else NetworkError.RESPONSE_INVALID, status)
    if (parsed == null && isHtml(contentType, text)) {
        val code = when {
            status == 403 && text.contains("CSRF") -> NetworkError.CSRF_FAILED
            status == 404 -> NetworkError.NOT_FOUND
            status == 413 -> NetworkError.PAYLOAD_TOO_LARGE
            status == 429 -> NetworkError.RATE_LIMITED
            else -> NetworkError.SERVER_HTML_ERROR
        }
        throw ApiFailure(code, status, retry)
    }
    throw ApiFailure(apiErrorCode(parsed) ?: statusCode(status), status, retry)
}

private fun Throwable.causes(): Sequence<Throwable> = generateSequence(this) { it.cause.takeIf { cause -> cause !== it } }.take(8)

/**
 * Maps OkHttp transport failures to stable codes.
 * @param online result of a connectivity check, or null when it is unknown.
 */
internal fun failureForIOException(error: IOException, online: Boolean?): ApiFailure {
    val chain = error.causes().toList()
    val code = when {
        chain.any { it is SSLException || it is CertPathValidatorException || it is CertificateException } -> NetworkError.TLS_FAILED
        chain.any { it is InterruptedIOException && (it is java.net.SocketTimeoutException || it.message == "timeout") } -> NetworkError.TIMEOUT
        error.message == "Canceled" -> NetworkError.REQUEST_CANCELLED
        online == false -> NetworkError.NETWORK_UNAVAILABLE
        chain.any { it is UnknownHostException } -> NetworkError.DNS_FAILED
        chain.any { it is SocketException && it.message.orEmpty().let { m -> "ENETUNREACH" in m || "Network is unreachable" in m } } -> NetworkError.NETWORK_UNAVAILABLE
        chain.any { it is ConnectException || it is NoRouteToHostException } -> NetworkError.SERVER_UNREACHABLE
        else -> NetworkError.SERVER_UNAVAILABLE
    }
    return ApiFailure(code)
}

/** Short technical code safe to show to users for support, e.g. `csrf_failed·403`. */
fun ApiFailure.debugCode(): String = if (status > 0) "$code·$status" else code

/** User-facing message for the network codes above, or null for codes the caller maps itself. */
fun networkErrorMessage(code: String): Int? = when (code) {
    NetworkError.CSRF_FAILED -> R.string.net_error_csrf_failed
    NetworkError.TLS_FAILED -> R.string.net_error_tls_failed
    NetworkError.SERVER_HTML_ERROR -> R.string.net_error_server_html_error
    NetworkError.RATE_LIMITED -> R.string.net_error_rate_limited
    NetworkError.REDIRECT_UNEXPECTED -> R.string.net_error_redirect_unexpected
    NetworkError.HTTPS_REQUIRED -> R.string.net_error_https_required
    NetworkError.NETWORK_UNAVAILABLE -> R.string.net_error_network_unavailable
    NetworkError.TIMEOUT -> R.string.net_error_timeout
    NetworkError.DNS_FAILED -> R.string.net_error_dns_failed
    NetworkError.SERVER_UNREACHABLE -> R.string.net_error_server_unreachable
    NetworkError.SERVER_ERROR -> R.string.net_error_server_error
    NetworkError.NOT_FOUND -> R.string.net_error_not_found
    NetworkError.VALIDATION_FAILED -> R.string.net_error_validation_failed
    NetworkError.PAYLOAD_TOO_LARGE -> R.string.net_error_payload_too_large
    NetworkError.RESPONSE_INVALID -> R.string.net_error_response_invalid
    else -> null
}
