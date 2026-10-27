package ec.aingel.mobile

import android.app.Application
import android.speech.tts.TextToSpeech
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.Locale

fun JSONArray.rows(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }
data class MobileState(
    val busy: Boolean = true, val error: String? = null, val username: String? = null, val mfaRequired: Boolean = false,
    val profiles: List<JSONObject> = emptyList(), val profile: JSONObject? = null, val rows: List<JSONObject> = emptyList(),
    val result: JSONObject? = null, val image: ByteArray? = null, val enrollmentPhotos: List<ByteArray> = emptyList(), val mfaSetup: JSONObject? = null, val recovery: List<String> = emptyList(),
    val mfaEnabled: Boolean = false, val circle: JSONObject? = null, val inviteCode: String? = null, val faces: JSONObject? = null,
    val captions: List<CaptionTurn> = emptyList(), val recording: Boolean = false, val captionStatus: String = "idle"
)

class AingelViewModel(app: Application) : AndroidViewModel(app) {
    val api = ApiClient(app)
    private val mutable = MutableStateFlow(MobileState())
    val state = mutable.asStateFlow()
    private var tts: TextToSpeech? = null
    private var voiceReady = false
    private val captionClient = CaptionClient(api, viewModelScope,
        onTurns = { turns -> mutable.update { it.copy(captions = turns) } },
        onStatus = { status -> mutable.update { it.copy(recording = status == "recording", captionStatus = status) } },
        onError = { code -> mutable.update { it.copy(error = code, recording = false, captionStatus = "idle") } })
    private var activeOperation: Job? = null
    init {
        tts = TextToSpeech(app) { status -> voiceReady = status == TextToSpeech.SUCCESS }
        operation {
            val session = api.request("auth/session/") as JSONObject
            applySession(session)
        }
    }
    private fun operation(work: suspend () -> Unit): Job {
        activeOperation?.cancel()
        val job = viewModelScope.launch {

        mutable.update { it.copy(busy = true, error = null) }
        try { work() }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (failure: ApiFailure) {
            if (failure.status == 403 && failure.code.contains("Authentication")) mutable.update { MobileState(busy = false, error = "session_expired") }
            else mutable.update { it.copy(error = failure.code) }
        } catch (_: Exception) { mutable.update { it.copy(error = "request_invalid") } }
        finally { mutable.update { it.copy(busy = false) } }
        }
        activeOperation = job
        return job
    }
    private suspend fun applySession(session: JSONObject) {
        val username = session.optJSONObject("user")?.optString("username")
        mutable.update { it.copy(username = username, mfaRequired = session.optBoolean("mfa_required")) }
        if (username != null) refreshProfiles()
    }
    private suspend fun refreshProfiles() {
        val profiles = (api.request("profiles/") as JSONArray).rows()
        val selected = mutable.value.profile?.optString("id")
        mutable.update { it.copy(profiles = profiles, profile = profiles.find { p -> p.optString("id") == selected } ?: profiles.firstOrNull()) }
    }
    fun configureBackend(value: String) = operation { api.configure(value); api.request("auth/session/"); mutable.update { MobileState(busy = false) } }
    fun login(username: String, password: String, register: Boolean = false) = operation {
        val response = api.request("auth/${if (register) "register" else "login"}/", "POST", JSONObject().put("username", username).put("password", password)) as JSONObject
        applySession(response)
    }
    fun verifyMfa(code: String) = operation { applySession(api.request("auth/mfa/verify/", "POST", JSONObject().put("code", code)) as JSONObject) }
    fun logout() = operation {
        stopCaptions(); tts?.stop()
        try { api.request("auth/logout/", "POST") }
        finally { api.clear(); mutable.value = MobileState(busy = false) }
        api.request("auth/session/")
    }
    fun select(profile: JSONObject) { activeOperation?.cancel(); stopCaptions(); mutable.update { it.copy(profile = profile, rows = emptyList(), result = null, image = null, enrollmentPhotos = emptyList(), faces = null, circle = null) } }
    fun resetScreen() { activeOperation?.cancel(); stopCaptions(); tts?.stop(); mutable.update { it.copy(rows = emptyList(), result = null, image = null, enrollmentPhotos = emptyList(), error = null, mfaSetup = null, recovery = emptyList(), inviteCode = null) } }
    fun clearError() { mutable.update { it.copy(error = null) } }
    fun reportError(code: String) { mutable.update { it.copy(error = code) } }
    fun createProfile(name: String) = operation { api.request("profiles/", "POST", JSONObject().put("display_name", name).put("locale", "es-EC")); refreshProfiles() }
    private fun path(suffix: String) = "profiles/${mutable.value.profile?.getString("id") ?: throw ApiFailure("profile_required")}/$suffix"
    fun loadRows(kind: String) = operation {
        val rows = (api.request(path("$kind/")) as JSONArray).rows(); mutable.update { it.copy(rows = rows) }
    }
    fun ask(tool: String, entity: String = "") = operation {
        val result = api.request(path("ask/"), "POST", JSONObject().put("tool", tool).put("entity", entity)) as JSONObject; mutable.update { it.copy(result = result) }
    }
    fun addMemory(entity: String, location: String) = operation {
        api.request(path("memories/"), "POST", JSONObject().put("entity", entity).put("location", location).put("observed_at", Instant.now().toString()).put("confirmed", true))
        val rows = (api.request(path("memories/")) as JSONArray).rows(); mutable.update { it.copy(rows = rows) }
    }
    fun deleteMemory(id: String) = operation { api.request(path("memories/$id/"), "DELETE"); val rows = (api.request(path("memories/")) as JSONArray).rows(); mutable.update { it.copy(rows = rows) } }
    fun message(body: String) = operation {
        api.request(path("messages/"), "POST", JSONObject().put("body", body).put("locale", mutable.value.profile?.optString("locale", "es-EC")))
        val rows = (api.request(path("messages/")) as JSONArray).rows(); mutable.update { it.copy(rows = rows) }
    }
    fun confirmRoutine(item: JSONObject) = operation {
        api.request(path("routines/${item.getString("id")}/confirm/"), if (item.optBoolean("confirmed_today")) "DELETE" else "POST")
        val rows = (api.request(path("routines/")) as JSONArray).rows(); mutable.update { it.copy(rows = rows) }
    }
    fun addRoutine(title: String, at: String, category: String, instructions: String) = operation {
        api.request(path("routines/"), "POST", JSONObject().put("title", title).put("at", at).put("category", category).put("instructions", instructions).put("weekdays", JSONArray((0..6).toList())).put("active", true))
        val rows = (api.request(path("routines/")) as JSONArray).rows(); mutable.update { it.copy(rows = rows) }
    }
    fun deleteRoutine(id: String) = operation {
        api.request(path("routines/$id/"), "DELETE")
        val rows = (api.request(path("routines/")) as JSONArray).rows(); mutable.update { it.copy(rows = rows) }
    }
    fun savePreferences(name: String, allergies: String, notes: String, preferences: JSONObject) = operation {
        api.request(path(""), "PATCH", JSONObject().put("display_name", name).put("allergies", allergies).put("support_notes", notes).put("preferences", preferences)); refreshProfiles()
    }
    fun loadCircle() = operation { val circle = api.request(path("circle/")) as JSONObject; mutable.update { it.copy(circle = circle) } }
    fun invite(username: String, relationship: String, memories: Boolean) = operation {
        val result = api.request(path("circle/"), "POST", JSONObject().put("username", username).put("relationship", relationship).put("can_configure", true).put("can_view_memories", memories)) as JSONObject
        val circle = api.request(path("circle/")) as JSONObject; mutable.update { it.copy(inviteCode = result.getString("code"), circle = circle) }; refreshProfiles()
    }
    fun acceptInvite(code: String) = operation { api.request("invites/accept/", "POST", JSONObject().put("code", code)); refreshProfiles() }
    fun revokeMember(id: String) = operation {
        val selected = mutable.value.profile?.optString("id")
        api.request(path("circle/$id/"), "DELETE"); refreshProfiles()
        val circle = if (mutable.value.profile?.optString("id") == selected) api.request(path("circle/")) as JSONObject else null
        mutable.update { it.copy(circle = circle) }
    }
    fun setImage(image: ByteArray) { mutable.update { it.copy(image = image, result = null) } }
    fun analyze(synthetic: Boolean, objectName: String? = null) = operation {
        val image = mutable.value.image ?: throw ApiFailure("image_required")
        val fields = mutableMapOf("locale" to (mutable.value.profile?.optString("locale") ?: "es-EC"), "synthetic" to synthetic.toString())
        if (objectName != null) fields["object_name"] = objectName
        val result = api.upload(if (objectName == null) "scene/" else "locate/", image, fields)
        mutable.update { it.copy(result = result) }
        if (result.has("text") && mutable.value.profile?.optJSONObject("preferences")?.optBoolean("voice_output") == true) speak(result.getString("text"))
    }
    fun loadFaces() = operation { val faces = api.request(path("faces/")) as JSONObject; mutable.update { it.copy(faces = faces) } }
    fun faceConsent(enabled: Boolean, password: String = "") = operation {
        api.request(path("faces/consent/"), "POST", JSONObject().put("enabled", enabled).put("consent", enabled).put("password", password))
        val faces = api.request(path("faces/")) as JSONObject; mutable.update { it.copy(faces = faces, result = null) }; refreshProfiles()
    }
    fun keepEnrollmentPhoto() {
        val current = mutable.value.image ?: return
        if (mutable.value.enrollmentPhotos.size >= 2) return
        mutable.update { it.copy(enrollmentPhotos = it.enrollmentPhotos + current, image = null) }
    }
    fun clearEnrollmentPhotos() { mutable.update { it.copy(enrollmentPhotos = emptyList(), image = null) } }
    fun enrollFace(name: String) = operation {
        val images = mutable.value.enrollmentPhotos + listOfNotNull(mutable.value.image)
        api.uploadImages(path("faces/"), images, mapOf("display_name" to name, "consent" to "true", "own_photo" to "true"))
        val faces = api.request(path("faces/")) as JSONObject; mutable.update { it.copy(faces = faces, image = null, enrollmentPhotos = emptyList()) }
    }
    fun recognizeFaces() = operation { val result = api.upload(path("faces/recognize/"), mutable.value.image ?: throw ApiFailure("image_required"), mapOf("consent" to "true")); mutable.update { it.copy(result = result) } }
    fun deleteFace() = operation { api.request(path("faces/"), "DELETE"); val faces = api.request(path("faces/")) as JSONObject; mutable.update { it.copy(faces = faces) } }
    fun loadMfa() = operation { val enabled = (api.request("auth/mfa/status/") as JSONObject).getBoolean("enabled"); mutable.update { it.copy(mfaEnabled = enabled) } }
    fun setupMfa(password: String) = operation { val setup = api.request("auth/mfa/setup/", "POST", JSONObject().put("password", password)) as JSONObject; mutable.update { it.copy(mfaSetup = setup) } }
    fun enableMfa(code: String) = operation {
        val result = api.request("auth/mfa/enable/", "POST", JSONObject().put("code", code)) as JSONObject
        val codes = result.getJSONArray("recovery_codes")
        mutable.update { it.copy(mfaEnabled = true, mfaSetup = null, recovery = (0 until codes.length()).map(codes::getString)) }
    }
    fun disableMfa(password: String, code: String) = operation {
        api.request("auth/mfa/disable/", "POST", JSONObject().put("password", password).put("code", code)); mutable.update { it.copy(mfaEnabled = false, recovery = emptyList()) }
    }
    fun hideRecovery() { mutable.update { it.copy(recovery = emptyList(), mfaSetup = null) } }
    fun speak(text: String) {
        val locale = Locale.forLanguageTag(mutable.value.profile?.optString("locale", "es-EC") ?: "es-EC")
        if (!voiceReady || (tts?.isLanguageAvailable(locale) ?: -1) < 0) { reportError("voice_unavailable"); return }
        tts?.language = locale; tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "aingel-response")
    }
    fun stopSpeech() { tts?.stop() }
    fun startCaptions() { mutable.update { it.copy(captions = emptyList(), error = null) }; captionClient.start(mutable.value.profile?.optString("locale") ?: "es-EC") }
    fun stopCaptions() { captionClient.close() }
    fun finishCaptions() { captionClient.stop() }
    override fun onCleared() { captionClient.close(); tts?.shutdown(); super.onCleared() }
}
