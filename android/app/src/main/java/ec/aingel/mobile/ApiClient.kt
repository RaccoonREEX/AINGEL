package ec.aingel.mobile

import android.content.Context
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import kotlinx.coroutines.suspendCancellableCoroutine
import okhttp3.*
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.security.KeyStore
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.UUID
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class ApiFailure(val code: String, val status: Int = 0, val retryAfterSeconds: Long? = null) : Exception(code)

internal const val DEFAULT_BACKEND = "https://aingel.mapatechstudio.com/"

internal fun isLegacyLoopbackBackend(raw: String?): Boolean {
    val url = raw?.trim()?.toHttpUrlOrNull() ?: return false
    return url.scheme == "http" && url.host in setOf("127.0.0.1", "localhost", "10.0.2.2")
}

fun validBackend(raw: String, debug: Boolean): String? {
    val url = raw.trim().toHttpUrlOrNull() ?: return null
    if (url.username.isNotEmpty() || url.password.isNotEmpty() || url.query != null || url.fragment != null || url.encodedPath != "/") return null
    if (url.scheme != "https" && !(debug && url.host in setOf("127.0.0.1", "localhost", "10.0.2.2"))) return null
    return url.toString()
}

/** Result of reading the saved backend at start-up. */
internal data class SavedBackend(val base: String, val discardSession: Boolean, val persist: Boolean)

/**
 * Resolves the backend saved by an earlier install. Pre-public loopback builds are moved once to the
 * public default; a saved value that is not valid for this build type (e.g. plain http in release, or a
 * malformed value) is never used and falls back to the default, discarding its cookies.
 */
internal fun resolveSavedBackend(saved: String?, migrated: Boolean, debug: Boolean): SavedBackend {
    if (!migrated && isLegacyLoopbackBackend(saved)) return SavedBackend(DEFAULT_BACKEND, discardSession = true, persist = true)
    if (saved == null) return SavedBackend(DEFAULT_BACKEND, discardSession = false, persist = false)
    val valid = validBackend(saved, debug) ?: return SavedBackend(DEFAULT_BACKEND, discardSession = true, persist = true)
    return SavedBackend(valid, discardSession = false, persist = valid != saved)
}

/** Parse only bounded error codes; raw server text is never shown directly. */
fun safeApiError(result: Any): String = apiErrorCode(result) ?: NetworkError.REQUEST_INVALID

/** Deep vision answers can take about a minute (three model calls); other requests keep the defaults below. */
internal const val SLOW_READ_SECONDS = 180L

internal fun defaultHttpClientBuilder(): OkHttpClient.Builder = OkHttpClient.Builder()
    .connectTimeout(15, TimeUnit.SECONDS).readTimeout(65, TimeUnit.SECONDS).callTimeout(75, TimeUnit.SECONDS)

private class SecretStore(context: Context) {
    private val prefs = context.getSharedPreferences("aingel-session", Context.MODE_PRIVATE)
    private val alias = "AingelSessionAES"
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    @Synchronized fun write(value: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val encrypted = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        prefs.edit().putString("cookies", Base64.encodeToString(encrypted, Base64.NO_WRAP)).apply()
    }
    @Synchronized fun read(): String? {
        val value = prefs.getString("cookies", null) ?: return null
        return try {
            val bytes = Base64.decode(value, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12))) }
            String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), Charsets.UTF_8)
        } catch (_: Exception) {
            // A missing/invalid device key must discard the session, never fall back to plaintext.
            clear(); null
        }
    }
    fun clear() { prefs.edit().remove("cookies").apply() }
}

private class DeviceCookies(context: Context) : CookieJar {
    private val store = SecretStore(context)
    private var cookies = mutableListOf<Cookie>()
    init {
        val value = store.read()
        if (value != null) try {
            val array = JSONArray(value)
            for (i in 0 until array.length()) {
                val item = array.getJSONObject(i)
                val url = item.getString("url").toHttpUrlOrNull() ?: continue
                Cookie.parse(url, item.getString("value"))?.let { cookies.add(it) }
            }
        } catch (_: Exception) { clear() }
    }
    @Synchronized override fun saveFromResponse(url: HttpUrl, received: List<Cookie>) {
        for (cookie in received) {
            cookies.removeAll { it.name == cookie.name && it.domain == cookie.domain && it.path == cookie.path }
            if (cookie.expiresAt > System.currentTimeMillis()) cookies.add(cookie)
        }
        val array = JSONArray()
        for (cookie in cookies) array.put(JSONObject().put("url", "${if (cookie.secure) "https" else "http"}://${cookie.domain}/").put("value", cookie.toString()))
        store.write(array.toString())
    }
    @Synchronized override fun loadForRequest(url: HttpUrl): List<Cookie> = cookies.filter { it.expiresAt > System.currentTimeMillis() && it.matches(url) }
    @Synchronized fun clear() { cookies.clear(); store.clear() }
}

class ApiClient(context: Context) {
    private val appContext = context.applicationContext ?: context
    private val preferences = context.getSharedPreferences("aingel-config", Context.MODE_PRIVATE)
    private val cookies = DeviceCookies(context)
    private val gate = SessionCookieGate(cookies, cookies::clear)
    private fun initialBackend(): String {
        val saved = resolveSavedBackend(preferences.getString("backend", null),
            preferences.getBoolean("backend-default-migrated-v1", false), BuildConfig.DEBUG)
        if (saved.discardSession) gate.invalidate()
        preferences.edit().putBoolean("backend-default-migrated-v1", true).apply {
            if (saved.persist) putString("backend", saved.base)
        }.apply()
        return saved.base
    }
    private val transport = ApiTransport(gate, initialBackend(), online = ::online)

    val base: String get() = transport.base
    val csrf: String get() = transport.csrf
    val client: OkHttpClient get() = transport.client

    /** null when connectivity cannot be read (ACCESS_NETWORK_STATE not granted). */
    private fun online(): Boolean? = try {
        if (appContext.checkSelfPermission(android.Manifest.permission.ACCESS_NETWORK_STATE) != PackageManager.PERMISSION_GRANTED) null
        else {
            val manager = appContext.getSystemService(ConnectivityManager::class.java)
            val capabilities = manager?.activeNetwork?.let { manager.getNetworkCapabilities(it) }
            capabilities?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
        }
    } catch (_: Exception) { null }

    fun configure(raw: String) {
        val value = validBackend(raw, BuildConfig.DEBUG) ?: throw ApiFailure("backend_invalid")
        transport.reconfigure(value) { preferences.edit().putString("backend", value).apply() }
    }
    fun clear() = transport.clear()

    suspend fun request(path: String, method: String = "GET", data: JSONObject? = null): Any = transport.request(path, method, data)
    suspend fun upload(path: String, image: ByteArray, values: Map<String, String>): JSONObject = uploadImages(path, listOf(image), values)
    suspend fun uploadImages(path: String, images: List<ByteArray>, values: Map<String, String>): JSONObject = transport.uploadImages(path, images, values)
    /** A short burst of camera frames (experimental sign recognition): up to six, in order. */
    suspend fun uploadFrames(path: String, frames: List<ByteArray>, values: Map<String, String>): JSONObject = transport.uploadImages(path, frames, values, limit = 6)
    suspend fun uploadClip(path: String, clip: ByteArray, values: Map<String, String>): JSONObject = transport.uploadClip(path, clip, values)
    /** A multipart form without files: synthetic tests name a server fixture instead of sending media. */
    suspend fun uploadForm(path: String, values: Map<String, String>): JSONObject = transport.uploadForm(path, values)
    /** Deep vision (`vision/`): a new picture, or a follow-up about the session's picture when [image] is null. Its
     * deepest level makes three model calls, so it waits longer than other requests. */
    suspend fun vision(image: ByteArray?, values: Map<String, String>): JSONObject =
        if (image != null) transport.uploadImages(VISION_PATH, listOf(image), values, slow = true) else transport.uploadForm(VISION_PATH, values, slow = true)
    suspend fun signClip(profileId: String, clipId: String): ByteArray = transport.signClip(profileId, clipId)
}

/**
 * Context-free HTTP core of [ApiClient] (unit-testable on the JVM).
 *
 * Writes always carry `X-CSRFToken` and a same-origin `Origin` (Django checks Origin against the request
 * host / CSRF_TRUSTED_ORIGINS on HTTPS). A write without a token first bootstraps one from `auth/session/`,
 * and a write rejected with `csrf_failed` is retried exactly once after refreshing the token: Django rejects
 * CSRF failures before running the view, so the retry cannot duplicate a write.
 */
internal class ApiTransport(
    private val gate: SessionCookieGate,
    initialBase: String,
    builder: OkHttpClient.Builder = defaultHttpClientBuilder(),
    private val online: () -> Boolean? = { null },
) {
    private val stateLock = Any()
    @Volatile
    var base: String = initialBase
        private set
    @Volatile
    var csrf: String = ""
        private set
    @Volatile
    var client: OkHttpClient = builder.cookieJar(gate.cookieJar()).followRedirects(false).followSslRedirects(false).build()
        private set
    private data class SessionSnapshot(val base: String, val csrf: String, val client: OkHttpClient, val generation: Long)
    private fun snapshot() = synchronized(stateLock) { SessionSnapshot(base, csrf, client, gate.generation()) }

    fun reconfigure(value: String, persist: () -> Unit) {
        synchronized(stateLock) {
            if (value != base) { clearLocked(); base = value; persist() }
        }
    }
    private fun clearLocked() {
        gate.invalidate()
        csrf = ""
        client = client.newBuilder().cookieJar(gate.cookieJar()).build()
    }
    fun clear() = synchronized(stateLock) { clearLocked() }

    private fun Request.Builder.csrfHeaders(session: SessionSnapshot) = apply {
        header("X-CSRFToken", session.csrf)
        header("Origin", session.base.removeSuffix("/"))
    }

    suspend fun request(path: String, method: String = "GET", data: JSONObject? = null): Any {
        val unsafe = method != "GET" && method != "HEAD"
        val body = if (!unsafe) null else (data ?: JSONObject()).toString().toRequestBody("application/json".toMediaType())
        return send(unsafe) { session ->
            Request.Builder().url(session.base + "api/v1/" + path).method(method, body).apply { if (unsafe) csrfHeaders(session) }.build()
        }
    }

    suspend fun uploadForm(path: String, values: Map<String, String>, slow: Boolean = false): JSONObject {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM).apply { values.forEach { (key, value) -> addFormDataPart(key, value) } }.build()
        val result = send(unsafe = true, slow = slow) { session ->
            Request.Builder().url(session.base + "api/v1/" + path).csrfHeaders(session).post(body).build()
        }
        return result as? JSONObject ?: throw ApiFailure(NetworkError.RESPONSE_INVALID)
    }

    suspend fun uploadImages(path: String, images: List<ByteArray>, values: Map<String, String>, limit: Int = 3, slow: Boolean = false): JSONObject {
        if (images.isEmpty() || images.size > limit || images.sumOf { it.size.toLong() } > 5 * 1024 * 1024) throw ApiFailure("image_too_large")
        val body = MultipartBody.Builder().setType(MultipartBody.FORM).apply {
            images.forEachIndexed { index, image -> addFormDataPart("image", "capture-$index.jpg", image.toRequestBody("image/jpeg".toMediaType())) }
            values.forEach { (key, value) -> addFormDataPart(key, value) }
        }.build()
        val result = send(unsafe = true, slow = slow) { session ->
            Request.Builder().url(session.base + "api/v1/" + path).csrfHeaders(session).post(body).build()
        }
        return result as? JSONObject ?: throw ApiFailure(NetworkError.RESPONSE_INVALID)
    }

    /** One short MP4 clip (experimental continuous vision); the fields go first so the server can reject early. */
    suspend fun uploadClip(path: String, clip: ByteArray, values: Map<String, String>): JSONObject {
        if (clip.isEmpty() || clip.size > 8 * 1024 * 1024) throw ApiFailure("clip_too_large")
        val body = MultipartBody.Builder().setType(MultipartBody.FORM).apply {
            values.forEach { (key, value) -> addFormDataPart(key, value) }
            addFormDataPart("clip", "clip.mp4", clip.toRequestBody("video/mp4".toMediaType()))
        }.build()
        val result = send(unsafe = true) { session ->
            Request.Builder().url(session.base + "api/v1/" + path).csrfHeaders(session).post(body).build()
        }
        return result as? JSONObject ?: throw ApiFailure(NetworkError.RESPONSE_INVALID)
    }

    /** Fetches `auth/session/`, which stores the current CSRF token from its JSON `csrf` field. */
    private suspend fun refreshCsrf() {
        val session = snapshot()
        execute(session, Request.Builder().url(session.base + "api/v1/auth/session/").get().build())
    }

    private suspend fun send(unsafe: Boolean, slow: Boolean = false, build: (SessionSnapshot) -> Request): Any {
        // Same cookies and connections, longer waits: only the read and whole-call timeouts change.
        fun SessionSnapshot.timed() = if (!slow) this else copy(client = client.newBuilder()
            .readTimeout(SLOW_READ_SECONDS, TimeUnit.SECONDS).callTimeout(SLOW_READ_SECONDS + 15, TimeUnit.SECONDS).build())
        if (!unsafe) return snapshot().timed().let { execute(it, build(it)) }
        if (csrf.isBlank()) refreshCsrf()
        val first = snapshot()
        return try {
            execute(first.timed(), build(first))
        } catch (failure: ApiFailure) {
            if (failure.code != NetworkError.CSRF_FAILED) throw failure
            refreshCsrf()
            val retry = snapshot()
            if (retry.generation != first.generation) throw ApiFailure("session_changed")
            execute(retry.timed(), build(retry))
        }
    }

    suspend fun signClip(profileId: String, clipId: String): ByteArray {
        val validProfile = try { UUID.fromString(profileId).toString() == profileId.lowercase() } catch (_: Exception) { false }
        if (!validProfile || !validSignClipId(clipId)) throw ApiFailure("sign_clip_invalid")
        val session = snapshot()
        val request = Request.Builder().url(session.base + "api/v1/profiles/$profileId/signs/clips/$clipId/").get().build()
        return suspendCancellableCoroutine { continuation ->
            val call = session.client.newCall(request)
            continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    if (continuation.isActive) continuation.resumeWithException(ApiFailure("sign_clip_unavailable"))
                }
                override fun onResponse(call: Call, response: Response) {
                    try {
                        val bytes = response.use {
                            if (!it.isSuccessful) throw ApiFailure("sign_clip_unavailable", it.code)
                            val body = it.body ?: throw ApiFailure("sign_clip_unavailable")
                            if (body.contentType()?.type != "video" || body.contentType()?.subtype != "mp4") throw ApiFailure("sign_clip_invalid")
                            val limit = 20 * 1024 * 1024
                            if (body.contentLength() > limit) throw ApiFailure("sign_clip_invalid")
                            val result = ByteArrayOutputStream()
                            body.byteStream().use { input ->
                                val buffer = ByteArray(8192)
                                while (true) {
                                    val count = input.read(buffer)
                                    if (count < 0) break
                                    if (result.size() + count > limit) throw ApiFailure("sign_clip_invalid")
                                    result.write(buffer, 0, count)
                                }
                            }
                            if (result.size() == 0) throw ApiFailure("sign_clip_invalid")
                            synchronized(stateLock) { if (!gate.isCurrent(session.generation)) throw ApiFailure("session_changed") }
                            result.toByteArray()
                        }
                        if (continuation.isActive) continuation.resume(bytes)
                    } catch (error: Exception) {
                        if (continuation.isActive) continuation.resumeWithException(if (error is ApiFailure) error else ApiFailure("sign_clip_unavailable"))
                    }
                }
            })
        }
    }

    private suspend fun execute(session: SessionSnapshot, request: Request): Any = suspendCancellableCoroutine { continuation ->
        val call = session.client.newCall(request)
        continuation.invokeOnCancellation { call.cancel() }
        call.enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                if (continuation.isActive) continuation.resumeWithException(failureForIOException(e, online()))
            }
            override fun onResponse(call: Call, response: Response) {
                try {
                    val result = response.use { readResponse(session, it) }
                    if (continuation.isActive) continuation.resume(result)
                } catch (error: Exception) {
                    if (continuation.isActive) continuation.resumeWithException(when (error) {
                        is ApiFailure -> error
                        is IOException -> failureForIOException(error, online())
                        else -> ApiFailure(NetworkError.RESPONSE_INVALID, response.code)
                    })
                }
            }
        })
    }

    private fun readResponse(session: SessionSnapshot, response: Response): Any {
        // Redirect bodies are never read; error bodies are decoded only into bounded codes.
        val body = if (response.code in 300..399) null else response.body?.string()
        val result = decodeApiResponse(response.code, response.header("Content-Type"), body,
            response.header("Location"), response.header("Retry-After"), response.request.url.scheme)
        synchronized(stateLock) {
            if (!gate.isCurrent(session.generation)) throw ApiFailure("session_changed")
            (result as? JSONObject)?.optString("csrf")?.takeIf { it.isNotBlank() }?.let { csrf = it }
        }
        return result
    }
}
