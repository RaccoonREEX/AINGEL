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
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

fun JSONArray.rows(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }
data class MobileState(
    val busy: Boolean = true, val error: String? = null, val username: String? = null, val mfaRequired: Boolean = false,
    val profiles: List<JSONObject> = emptyList(), val profile: JSONObject? = null, val communication: JSONObject? = null, val rows: List<JSONObject> = emptyList(), val knowledge: List<JSONObject>? = null,
    val result: JSONObject? = null, val companion: JSONObject? = null, val image: ByteArray? = null, val enrollmentPhotos: List<ByteArray> = emptyList(), val mfaSetup: JSONObject? = null, val recovery: List<String> = emptyList(),
    val mfaEnabled: Boolean = false, val circle: JSONObject? = null, val inviteCode: String? = null, val faces: JSONObject? = null,
    val captions: List<CaptionTurn> = emptyList(), val recording: Boolean = false, val captionStatus: String = "idle",
    val signStatus: String = "waiting", val signText: String? = null, val signMetadata: JSONObject? = null, val signVideo: ByteArray? = null
)

class AingelViewModel(app: Application) : AndroidViewModel(app) {
    val api = ApiClient(app)
    private val mutable = MutableStateFlow(MobileState())
    val state = mutable.asStateFlow()
    private var tts: TextToSpeech? = null
    private var voiceReady = false
    private val captionEpoch = AtomicLong(0)
    private val captionsActive = AtomicBoolean(false)
    private val signGuard = SignLookupGuard()
    private var signJob: Job? = null
    private var lastSignPhrase: SignPhrase? = null
    private var activeSpeechTurn: String? = null
    private val retiredSpeechTurns = mutableSetOf<String>()
    private val captionClient = CaptionClient(api, viewModelScope,
        onTurns = { turns ->
            val epoch = captionEpoch.get()
            viewModelScope.launch {
                if (captionsActive.get() && captionEpoch.get() == epoch) {
                    mutable.update { it.copy(captions = turns) }
                    updateSigns(turns.lastOrNull(), epoch)
                }
            }
        },
        onSpeechStart = { turnId ->
            val epoch = captionEpoch.get()
            viewModelScope.launch {
                if (captionsActive.get() && captionEpoch.get() == epoch) {
                    activeSpeechTurn?.let { retiredSpeechTurns.add(it) }
                    activeSpeechTurn = turnId
                    if (turnId != null) retiredSpeechTurns.remove(turnId)
                    invalidateSigns(if (supportsSignCatalog(mutable.value.communication?.optString("sign_language"))) "listening" else "unsupported")
                }
            }
        },
        onStatus = { status -> mutable.update { it.copy(recording = status == "recording", captionStatus = status) } },
        onError = { code -> mutable.update { it.copy(error = code, recording = false, captionStatus = "idle") } })
    private var activeOperation: Job? = null
    private var operationGeneration = 0L
    init {
        tts = TextToSpeech(app) { status -> voiceReady = status == TextToSpeech.SUCCESS }
        operation {
            val session = api.request("auth/session/") as JSONObject
            applySession(session)
        }
    }
    private fun operation(work: suspend () -> Unit): Job {
        val current = ++operationGeneration
        activeOperation?.cancel()
        val job = viewModelScope.launch {
            mutable.update { it.copy(busy = true, error = null) }
            try { work() }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: ApiFailure) {
                if (current == operationGeneration) {
                    if (failure.status == 403 && failure.code == "authentication_required") mutable.update { MobileState(busy = false, error = "session_expired") }
                    else mutable.update { it.copy(error = failure.code) }
                }
            } catch (_: Exception) {
                if (current == operationGeneration) mutable.update { it.copy(error = "request_invalid") }
            } finally {
                if (current == operationGeneration) mutable.update { it.copy(busy = false) }
            }
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
        val profile = profiles.find { p -> p.optString("id") == selected } ?: profiles.firstOrNull()
        mutable.update { it.copy(profiles = profiles, profile = profile, communication = null) }
        profile?.optString("id")?.takeIf { it.isNotBlank() }?.let { refreshCommunication(it) }
    }
    private suspend fun refreshCommunication(profileId: String) {
        val value = api.request("profiles/$profileId/communication/") as JSONObject
        mutable.update { if (it.profile?.optString("id") == profileId) it.copy(communication = value) else it }
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
    private fun cancelOperation() { operationGeneration++; activeOperation?.cancel(); activeOperation = null }
    fun select(profile: JSONObject) {
        cancelOperation(); stopCaptions()
        mutable.update { it.copy(busy = false, profile = profile, communication = null, rows = emptyList(), knowledge = null, result = null, companion = null, image = null, enrollmentPhotos = emptyList(), faces = null, circle = null) }
        operation { refreshCommunication(profile.getString("id")) }
    }
    fun resetScreen() { cancelOperation(); stopCaptions(); tts?.stop(); mutable.update { it.copy(busy = false, rows = emptyList(), knowledge = null, result = null, companion = null, image = null, enrollmentPhotos = emptyList(), error = null, mfaSetup = null, recovery = emptyList(), inviteCode = null) } }
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
    fun searchResources(query: String) = operation {
        val profile = mutable.value.profile ?: throw ApiFailure("profile_required")
        val profileId = profile.getString("id")
        val language = if (profile.optString("locale") == "en-US") "en" else "es"
        mutable.update { it.copy(knowledge = null) }
        val resources = (api.request("profiles/$profileId/resources/search/", "POST", JSONObject().put("q", query.trim()).put("lang", language)) as JSONArray).rows()
        mutable.update { if (it.profile?.optString("id") == profileId) it.copy(knowledge = resources) else it }
    }
    fun clearCompanion() { mutable.update { it.copy(companion = null) } }
    internal fun askCompanion(text: String, topic: CompanionTopic?) = operation {
        val profileId = mutable.value.profile?.optString("id")?.takeIf { it.isNotBlank() } ?: throw ApiFailure("profile_required")
        mutable.update { it.copy(companion = null) }
        val result = api.request("profiles/$profileId/companion/chat/", "POST", companionPayload(text, topic)) as JSONObject
        if (result.optString("mode") !in setOf("meta", "mock") || result.optString("text").isBlank()) throw ApiFailure("companion_response_invalid")
        mutable.update { if (it.profile?.optString("id") == profileId) it.copy(companion = result) else it }
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
        tts?.language = locale
        tts?.setSpeechRate(if (mutable.value.communication?.optString("pace") == "slow") 0.8f else 1.0f)
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "aingel-response")
    }
    fun stopSpeech() { tts?.stop() }
    private fun invalidateSigns(status: String) {
        signGuard.advance(); signJob?.cancel(); signJob = null
        mutable.update { it.copy(signStatus = status, signText = null, signMetadata = null, signVideo = null) }
    }
    private fun updateSigns(turn: CaptionTurn?, epoch: Long) {
        if (turn == null) return
        if (turn.id in retiredSpeechTurns) return
        if (activeSpeechTurn != null && turn.id != activeSpeechTurn) {
            activeSpeechTurn?.let { retiredSpeechTurns.add(it) }
        }
        activeSpeechTurn = turn.id
        val language = mutable.value.communication?.optString("sign_language")
        if (!supportsSignCatalog(language)) { invalidateSigns("unsupported"); return }
        if (!turn.final) { invalidateSigns("listening"); return }
        val phrase = eligibleSignPhrase(mutable.value.profile?.optString("id"), language, turn)
        if (phrase == null) { invalidateSigns("unavailable"); mutable.update { it.copy(signText = turn.text) }; return }
        if (phrase == lastSignPhrase) return
        lastSignPhrase = phrase
        invalidateSigns("searching")
        mutable.update { it.copy(signText = phrase.text) }
        val token = signGuard.advance()
        signJob = viewModelScope.launch {
            try {
                val response = api.request("profiles/${phrase.profileId}/signs/lookup/", "POST", JSONObject().put("text", phrase.text).put("language", phrase.language)) as JSONObject
                if (!signGuard.isCurrent(token) || captionEpoch.get() != epoch || mutable.value.profile?.optString("id") != phrase.profileId || mutable.value.communication?.optString("sign_language") != phrase.language) return@launch
                if (response.opt("available") !is Boolean) throw ApiFailure("sign_catalog_invalid")
                if (!response.getBoolean("available")) { mutable.update { it.copy(signStatus = "unavailable") }; return@launch }
                val clip = response.optJSONObject("clip") ?: throw ApiFailure("sign_clip_invalid")
                if (clip.optString("language") != phrase.language || listOf("source", "attribution", "license").any { clip.optString(it).isBlank() }) throw ApiFailure("sign_clip_invalid")
                val video = api.signClip(phrase.profileId, clip.optString("id"))
                if (signGuard.isCurrent(token) && captionEpoch.get() == epoch && mutable.value.profile?.optString("id") == phrase.profileId && mutable.value.communication?.optString("sign_language") == phrase.language) {
                    mutable.update { it.copy(signStatus = "available", signMetadata = clip, signVideo = video) }
                }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) {
                if (signGuard.isCurrent(token) && captionEpoch.get() == epoch) mutable.update { it.copy(signStatus = "error", signMetadata = null, signVideo = null) }
            }
        }
    }
    fun startCaptions() {
        captionEpoch.incrementAndGet(); captionsActive.set(true); retiredSpeechTurns.clear(); activeSpeechTurn = null; lastSignPhrase = null
        invalidateSigns(if (supportsSignCatalog(mutable.value.communication?.optString("sign_language"))) "waiting" else "unsupported")
        mutable.update { it.copy(captions = emptyList(), error = null) }
        captionClient.start(mutable.value.profile?.optString("locale") ?: "es-EC")
    }
    fun stopCaptions() {
        captionsActive.set(false); captionEpoch.incrementAndGet(); captionClient.close()
        retiredSpeechTurns.clear(); activeSpeechTurn = null; lastSignPhrase = null
        invalidateSigns("waiting"); mutable.update { it.copy(captions = emptyList()) }
    }
    fun finishCaptions() { captionClient.stop() }
    override fun onCleared() { stopCaptions(); tts?.shutdown(); super.onCleared() }
}
