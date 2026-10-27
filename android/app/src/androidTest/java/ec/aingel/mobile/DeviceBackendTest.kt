package ec.aingel.mobile

import android.content.Context
import android.content.ContextWrapper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.nio.ByteBuffer
import java.time.Instant
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

@RunWith(AndroidJUnit4::class)
class DeviceBackendTest {
    @Test fun nativeSessionCareMemoryAndMfaRoundTrip() = runBlocking {
        val suffix = UUID.randomUUID().toString().replace("-", "").take(12)
        val context = object : ContextWrapper(InstrumentationRegistry.getInstrumentation().targetContext) {
            override fun getSharedPreferences(name: String, mode: Int) = super.getSharedPreferences("test-$suffix-$name", mode)
        }
        val api = ApiClient(context)
        val username = "aingel.mobile.test.$suffix"
        val password = "Synthetic-Test!" + UUID.randomUUID().toString()
        api.request("auth/session/")
        val credentials = JSONObject().put("username", username).put("password", password)
        val registration = api.request("auth/register/", "POST", credentials) as JSONObject
        assertEquals(username, registration.getJSONObject("user").getString("username"))
        val profile = api.request("profiles/", "POST", JSONObject().put("display_name", "Synthetic Android test").put("locale", "es-EC")) as JSONObject
        val path = "profiles/${profile.getString("id")}/"
        api.request(path + "routines/", "POST", JSONObject().put("title", "Synthetic sleep routine").put("category", "sleep").put("at", "22:00")
            .put("weekdays", JSONArray((0..6).toList())).put("instructions", "Synthetic test only").put("active", true))
        val routines = api.request(path + "routines/") as JSONArray
        assertEquals(1, routines.length())
        val routineId = routines.getJSONObject(0).getString("id")
        api.request(path + "routines/$routineId/confirm/", "POST")
        assertTrue((api.request(path + "routines/") as JSONArray).getJSONObject(0).getBoolean("confirmed_today"))
        val query = JSONObject().put("tool", "search_memory").put("entity", "synthetic keys")
        assertEquals("no_evidence", (api.request(path + "ask/", "POST", query) as JSONObject).getString("answer_code"))
        api.request(path + "memories/", "POST", JSONObject().put("entity", "synthetic keys").put("location", "synthetic desk")
            .put("observed_at", Instant.now().toString()).put("confirmed", true))
        assertEquals("synthetic desk", (api.request(path + "ask/", "POST", query) as JSONObject).getJSONObject("evidence").getString("location"))

        // A second native client must recover the same cookie through device AES-GCM.
        val restored = ApiClient(context)
        assertEquals(username, (restored.request("auth/session/") as JSONObject).getJSONObject("user").getString("username"))
        val ciphertext = context.getSharedPreferences("aingel-session", Context.MODE_PRIVATE).getString("cookies", "")!!
        assertFalse(ciphertext.contains("sessionid")); assertFalse(ciphertext.contains(username))

        val setup = restored.request("auth/mfa/setup/", "POST", JSONObject().put("password", password)) as JSONObject
        val enabled = restored.request("auth/mfa/enable/", "POST", JSONObject().put("code", totp(setup.getString("secret")))) as JSONObject
        val recovery = enabled.getJSONArray("recovery_codes")
        assertEquals(8, recovery.length())
        restored.request("auth/logout/", "POST")
        val challenge = restored.request("auth/login/", "POST", credentials) as JSONObject
        assertTrue(challenge.getBoolean("mfa_required")); assertTrue(challenge.isNull("user"))
        try { restored.request("profiles/"); fail("Password alone must not authenticate") } catch (failure: ApiFailure) { assertEquals(403, failure.status) }
        val verified = restored.request("auth/mfa/verify/", "POST", JSONObject().put("code", recovery.getString(0))) as JSONObject
        assertEquals(username, verified.getJSONObject("user").getString("username"))
        restored.request("auth/logout/", "POST"); restored.request("auth/login/", "POST", credentials)
        try { restored.request("auth/mfa/verify/", "POST", JSONObject().put("code", recovery.getString(0))); fail("Recovery code must be one-use") }
        catch (failure: ApiFailure) { assertEquals(400, failure.status) }
        restored.request("auth/mfa/verify/", "POST", JSONObject().put("code", recovery.getString(1)))
        restored.request("auth/mfa/disable/", "POST", JSONObject().put("password", password).put("code", recovery.getString(2)))
        assertFalse((restored.request("auth/mfa/status/") as JSONObject).getBoolean("enabled"))
        restored.request("auth/logout/", "POST"); restored.clear()
    }

    private fun totp(base32: String): String {
        val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        var accumulator = 0; var bits = 0; val decoded = ArrayList<Byte>()
        for (character in base32) {
            val value = alphabet.indexOf(character); require(value >= 0)
            accumulator = (accumulator shl 5) or value; bits += 5
            if (bits >= 8) { bits -= 8; decoded.add((accumulator shr bits).toByte()) }
        }
        val mac = Mac.getInstance("HmacSHA1").apply { init(SecretKeySpec(decoded.toByteArray(), "HmacSHA1")) }
        val digest = mac.doFinal(ByteBuffer.allocate(8).putLong(System.currentTimeMillis() / 30000).array())
        val offset = digest.last().toInt() and 15
        val binary = ((digest[offset].toInt() and 127) shl 24) or ((digest[offset + 1].toInt() and 255) shl 16) or
            ((digest[offset + 2].toInt() and 255) shl 8) or (digest[offset + 3].toInt() and 255)
        return (binary % 1000000).toString().padStart(6, '0')
    }
}
