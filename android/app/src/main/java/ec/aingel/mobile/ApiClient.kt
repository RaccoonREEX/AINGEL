package ec.aingel.mobile

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.security.KeyStore
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class ApiFailure(val code: String, val status: Int = 0) : Exception(code)

fun validBackend(raw: String, debug: Boolean): String? {
    val url = raw.trim().toHttpUrlOrNull() ?: return null
    if (url.username.isNotEmpty() || url.password.isNotEmpty() || url.query != null || url.fragment != null || url.encodedPath != "/") return null
    if (url.scheme != "https" && !(debug && url.host in setOf("127.0.0.1", "localhost", "10.0.2.2"))) return null
    return url.toString()
}

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
    private val preferences = context.getSharedPreferences("aingel-config", Context.MODE_PRIVATE)
    private val cookies = DeviceCookies(context)
    var base: String = preferences.getString("backend", "http://127.0.0.1:8010/")!!
        private set
    var csrf: String = ""
        private set
    val client = OkHttpClient.Builder().cookieJar(cookies).connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(65, TimeUnit.SECONDS).callTimeout(75, TimeUnit.SECONDS).followRedirects(false).build()
    fun configure(raw: String) {
        val value = validBackend(raw, BuildConfig.DEBUG) ?: throw ApiFailure("backend_invalid")
        if (value != base) { clear(); base = value; preferences.edit().putString("backend", value).apply() }
    }
    fun clear() { cookies.clear(); csrf = "" }
    suspend fun request(path: String, method: String = "GET", data: JSONObject? = null): Any = withContext(Dispatchers.IO) {
        val body = if (method == "GET" || method == "HEAD") null else (data ?: JSONObject()).toString().toRequestBody("application/json".toMediaType())
        execute(Request.Builder().url(base + "api/v1/" + path).method(method, body).apply { if (method != "GET") header("X-CSRFToken", csrf) }.build())
    }
    suspend fun upload(path: String, image: ByteArray, values: Map<String, String>): JSONObject = uploadImages(path, listOf(image), values)
    suspend fun uploadImages(path: String, images: List<ByteArray>, values: Map<String, String>): JSONObject = withContext(Dispatchers.IO) {
        if (images.isEmpty() || images.size > 3 || images.sumOf { it.size.toLong() } > 5 * 1024 * 1024) throw ApiFailure("image_too_large")
        val body = MultipartBody.Builder().setType(MultipartBody.FORM).apply {
            images.forEachIndexed { index, image -> addFormDataPart("image", "capture-$index.jpg", image.toRequestBody("image/jpeg".toMediaType())) }
            values.forEach { (key, value) -> addFormDataPart(key, value) }
        }.build()
        execute(Request.Builder().url(base + "api/v1/" + path).header("X-CSRFToken", csrf).post(body).build()) as JSONObject
    }
    private fun execute(request: Request): Any {
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 204) return JSONObject()
                val raw = response.body?.string() ?: throw ApiFailure("server_unavailable")
                val result: Any = if (raw.trimStart().startsWith("[")) JSONArray(raw) else try { JSONObject(raw) } catch (_: Exception) { throw ApiFailure("server_unavailable", response.code) }
                if (!response.isSuccessful) {
                    val json = result as? JSONObject
                    val code = json?.optString("error")?.takeIf { it.isNotBlank() } ?: json?.optString("detail")?.takeIf { it.isNotBlank() } ?: "request_invalid"
                    throw ApiFailure(code, response.code)
                }
                (result as? JSONObject)?.optString("csrf")?.takeIf { it.isNotBlank() }?.let { csrf = it }
                return result
            }
        } catch (error: ApiFailure) { throw error }
        catch (_: Exception) { throw ApiFailure("server_unavailable") }
    }
}
