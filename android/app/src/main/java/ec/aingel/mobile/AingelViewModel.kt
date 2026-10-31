package ec.aingel.mobile

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
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
    val signStatus: String = "waiting", val signText: String? = null, val signMetadata: JSONObject? = null, val signVideo: ByteArray? = null,
    val privateTestProfileId: String? = null, val syntheticConversationProfileId: String? = null,
    // The server's synthetic example questions (id to text in the app language), shown while the demo is on.
    val syntheticQuestions: List<Pair<String, String>> = emptyList(),
    // Age and consent policy (backend care.consent): the account's 18+ declaration, the current terms, and the
    // person's decisions for the selected profile.
    val adultDeclared: Boolean = true, val termsVersion: String = "", val consent: JSONObject? = null,
    val consentCode: JSONObject? = null, val purposes: JSONObject? = null, val openConsent: Boolean = false,
)

class AingelViewModel(app: Application) : AndroidViewModel(app) {
    val api = Backend.api(app)
    private val mutable = MutableStateFlow(MobileState())
    val state = mutable.asStateFlow()
    /** AINGEL's voice, routed to the output chosen in Ajustes (5b). */
    private val voice = AingelVoice(app)
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
    /** Who the new account is for and the name typed at sign-up; used to prefill the setup wizard. */
    var signup: Pair<String, String> = "other" to ""
        private set
    /** The orb follows AINGEL's voice (word ranges, or a pulse while a routed phrase plays). */
    fun speechLevel(): Float = voice.level()
    init {
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
                    if (failure.status in setOf(401, 403) && failure.code == "authentication_required") mutable.update { MobileState(busy = false, error = "session_expired") }
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
        val adult = session.optJSONObject("user")?.optBoolean("adult_declared", false) ?: true
        mutable.update { it.copy(username = username, mfaRequired = session.optBoolean("mfa_required"), adultDeclared = adult,
            termsVersion = session.optString("terms_version").ifBlank { it.termsVersion }) }
        if (username != null && adult) refreshProfiles()
    }
    private suspend fun refreshProfiles() {
        val profiles = (api.request("profiles/") as JSONArray).rows()
        val selected = mutable.value.profile?.optString("id")
        val profile = profiles.find { p -> p.optString("id") == selected } ?: profiles.firstOrNull()
        mutable.update {
            val sameProfile = profile?.optString("id") == it.profile?.optString("id")
            it.copy(profiles = profiles, profile = profile, communication = null,
                syntheticConversationProfileId = if (sameProfile) it.syntheticConversationProfileId else null)
        }
        profile?.optString("id")?.takeIf { it.isNotBlank() }?.let { refreshCommunication(it) }
    }
    private suspend fun refreshCommunication(profileId: String) {
        val value = api.request("profiles/$profileId/communication/") as JSONObject
        mutable.update { if (it.profile?.optString("id") == profileId) it.copy(communication = value) else it }
    }
    fun configureBackend(value: String) = operation { stopCaptions(); WatchService.stop(getApplication()); api.configure(value); api.request("auth/session/"); mutable.update { MobileState(busy = false) } }
    fun register(username: String, password: String, who: String, name: String) { signup = who to name.trim(); login(username, password, true) }
    fun login(username: String, password: String, register: Boolean = false) = operation {
        val body = JSONObject().put("username", username).put("password", password)
        // Registration carries the explicit 18+ declaration for the current terms; the server checks it.
        if (register) body.put("adult", true).put("terms_version", termsVersion())
        val response = api.request("auth/${if (register) "register" else "login"}/", "POST", body) as JSONObject
        applySession(response)
    }
    private suspend fun termsVersion(): String = mutable.value.termsVersion.ifBlank {
        (api.request("auth/session/") as JSONObject).optString("terms_version").also { v -> mutable.update { it.copy(termsVersion = v) } }
    }
    fun declareAdult() = operation {
        applySession(api.request("auth/adult/", "POST", JSONObject().put("adult", true).put("terms_version", termsVersion())) as JSONObject)
    }
    private fun localeQuery() = "?locale=" + (mutable.value.profile?.optString("locale")?.takeIf { it.isNotBlank() } ?: if (java.util.Locale.getDefault().language == "es") "es-EC" else "en-US")
    fun loadPurposes() = operation { val p = api.request("consent/purposes/" + localeQuery()) as JSONObject; mutable.update { it.copy(purposes = p) } }
    fun loadConsent() = operation { val c = api.request(path("consent/") + localeQuery()) as JSONObject; mutable.update { it.copy(consent = c) } }
    /** Only the person decides; the server refuses anyone else (consent_subject_only). */
    fun decideConsent(purpose: String, decision: String) = operation {
        val c = api.request(path("consent/") + localeQuery(), "POST", JSONObject().put("purpose", purpose).put("decision", decision)) as JSONObject
        mutable.update { it.copy(consent = c) }
    }
    fun createConsentCode() = operation { val code = api.request(path("consent/invite/"), "POST") as JSONObject; mutable.update { it.copy(consentCode = code) } }
    /** Profiles from before the policy: the owner says whose data this is (never inferred). */
    fun confirmSubject(forSelf: Boolean) = operation {
        val body = if (forSelf) JSONObject().put("for_self", true) else JSONObject().put("for_self", false).put("subject_adult", true)
        val c = api.request(path("consent/confirm-subject/"), "POST", body) as JSONObject
        mutable.update { it.copy(consent = c) }; refreshProfiles()
    }
    fun requestLegalReview() = operation { val c = api.request(path("consent/legal-review/"), "POST") as JSONObject; mutable.update { it.copy(consent = c) }; refreshProfiles() }
    fun redeemConsentCode(code: String) = operation {
        val linked = api.request("consent/redeem/", "POST", JSONObject().put("code", code)) as JSONObject
        refreshProfiles()
        val profile = mutable.value.profiles.find { it.optString("id") == linked.optString("profile") }
        mutable.update { it.copy(profile = profile ?: it.profile, consent = null, openConsent = true) }
    }
    fun consentOpened() { mutable.update { it.copy(openConsent = false) } }
    /** Saves communication preferences and keeps the app's copy current (watching reads «spontaneous» from it). */
    suspend fun saveCommunication(patch: JSONObject): JSONObject {
        val id = mutable.value.profile?.optString("id") ?: throw ApiFailure("profile_required")
        val saved = api.request("profiles/$id/communication/", "PATCH", patch) as JSONObject
        mutable.update { if (it.profile?.optString("id") == id) it.copy(communication = saved) else it }
        return saved
    }
    fun verifyMfa(code: String) = operation { applySession(api.request("auth/mfa/verify/", "POST", JSONObject().put("code", code)) as JSONObject) }
    fun logout() = operation {
        stopCaptions(); WatchService.stop(getApplication()); voice.stop()
        try { api.request("auth/logout/", "POST") }
        finally { api.clear(); mutable.value = MobileState(busy = false) }
        api.request("auth/session/")
    }
    private fun cancelOperation() { operationGeneration++; activeOperation?.cancel(); activeOperation = null }
    fun select(profile: JSONObject) {
        cancelOperation(); stopCaptions(); WatchService.stop(getApplication())
        mutable.update { it.copy(busy = false, profile = profile, privateTestProfileId = null, syntheticConversationProfileId = null, communication = null, rows = emptyList(), knowledge = null, result = null, companion = null, image = null, enrollmentPhotos = emptyList(), faces = null, circle = null) }
        operation { refreshCommunication(profile.getString("id")) }
    }
    fun resetScreen() { cancelOperation(); stopCaptions(); voice.stop(); mutable.update { it.copy(busy = false, rows = emptyList(), knowledge = null, result = null, companion = null, image = null, enrollmentPhotos = emptyList(), error = null, mfaSetup = null, recovery = emptyList(), inviteCode = null) } }
    fun clearError() { mutable.update { it.copy(error = null) } }
    fun reportError(code: String) { mutable.update { it.copy(error = code) } }
    /**
     * Creates the configured profile and its communication preferences without leaving the wizard,
     * so the activation animation can play; [finishSetup] then opens the home screen. A retry after a
     * failed communication save reuses the profile already created.
     */
    internal suspend fun createConfiguredProfile(profile: JSONObject, answers: SetupAnswers, preferredName: String, existingId: String?): String {
        val id = existingId ?: (api.request("profiles/", "POST", profile) as JSONObject).getString("id")
        val current = api.request("profiles/$id/communication/") as JSONObject
        api.request("profiles/$id/communication/", "PATCH", presetCommunication(current, answers, preferredName))
        return id
    }
    fun finishSetup() = operation { refreshProfiles() }
    /** Direct, non-blocking queries for the assistant screen (no global busy overlay). */
    suspend fun profileRequest(suffix: String, method: String = "GET", body: JSONObject? = null): Any = api.request(path(suffix), method, body)
    /** General conversation under the authorization given at sign-up (the server checks it, care.consent). */
    /** [actions]: app features the model may ask this phone to run (camera, watching, signs). */
    suspend fun converse(turns: JSONArray, actions: List<String> = emptyList()): JSONObject {
        val state = mutable.value
        if (state.privateTestProfileId != null) throw ApiFailure("privacy_review_required")
        val id = state.profile?.optString("id")?.takeIf { it.isNotBlank() } ?: throw ApiFailure("profile_required")
        // The synthetic demo never sends what was typed or said: only the server's questions (converseFixture).
        if (state.syntheticConversationProfileId == id) throw ApiFailure("synthetic_fixture_required")
        return api.request("profiles/$id/conversation/", "POST", conversationPayload(turns, actions)) as JSONObject
    }
    /** Synthetic demo: the server writes the question and answers it with a fictitious profile. */
    suspend fun converseFixture(fixture: String): JSONObject {
        val id = mutable.value.profile?.optString("id")?.takeIf { it.isNotBlank() } ?: throw ApiFailure("profile_required")
        return api.request("profiles/$id/conversation/", "POST", fixtureConversationPayload(fixture, appLocale())) as JSONObject
    }
    private fun appLocale() = if (getApplication<Application>().resources.configuration.locales[0].language == "es") "es-EC" else "en-US"
    /** One captured frame to scene description or object search; the image is not stored. */
    suspend fun analyzeFrame(image: ByteArray, objectName: String?): JSONObject {
        // The profile lets the server apply its sign-up authorization (camera + Meta).
        val fields = imageRequestFields(mutable.value.profile, mutable.value.privateTestProfileId)
        // Describing also says which enrolled family members are in front (matched on our server, not by Meta).
        if (objectName != null) fields["object_name"] = objectName else if (mutable.value.privateTestProfileId == null) fields["family"] = "true"
        return api.upload(if (objectName == null) "scene/" else "locate/", image, fields)
    }
    private val glossCache = object : LinkedHashMap<String, List<String>>(32, .75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, List<String>>?) = size > 64
    }
    /** Signs for [text] by meaning (Meta, backend assistance.gloss), or null to use the local rule (buildSentence):
     * test mode, no authorization from sign-up, no connection, slow answer or an unusable gloss. */
    suspend fun signsFor(text: String): List<String>? {
        if (mutable.value.privateTestProfileId != null) return null
        val key = text.trim().lowercase().take(300)
        if (key.isEmpty()) return null
        synchronized(glossCache) { glossCache[key] }?.let { return it }
        val seq = withTimeoutOrNull(6_000) {
            try {
                val reply = api.request(path("signs/gloss/"), "POST", JSONObject().put("text", text.trim().take(300)).put("vocabulary", JSONObject(GLOSS_VOCABULARY))) as JSONObject
                glossSeq(reply.optJSONArray("gloss"))
            } catch (e: CancellationException) { throw e } catch (_: Exception) { null }
        }
        if (seq != null) synchronized(glossCache) { glossCache[key] = seq }
        return seq
    }
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
        if (mutable.value.privateTestProfileId != null) throw ApiFailure("privacy_review_required")
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
    fun saveMediaConsents(camera: Boolean, microphone: Boolean, meta: Boolean) = operation {
        stopCaptions(); WatchService.stop(getApplication())
        mutable.update { it.copy(privateTestProfileId = null) }
        api.request(path(""), "PATCH", JSONObject().put("consents", JSONObject().put("camera", camera).put("microphone", microphone).put("meta_data", meta)))
        refreshProfiles()
    }
    fun setPrivateTest(enabled: Boolean) {
        stopCaptions(); WatchService.stop(getApplication())
        val profile = mutable.value.profile
        val id = profile?.optString("id").orEmpty()
        if (enabled && !(privateMediaAllowed(profile, id, "camera") || privateMediaAllowed(profile, id, "microphone"))) {
            mutable.update { it.copy(privateTestProfileId = null, error = "private_test_consent_required") }
        } else mutable.update { it.copy(privateTestProfileId = if (enabled) id else null,
            syntheticConversationProfileId = if (enabled) null else it.syntheticConversationProfileId, error = null) }
    }
    /** Session-only explicit declaration; it never classifies or filters the content. */
    fun setSyntheticConversation(enabled: Boolean) {
        if (enabled) { stopCaptions(); WatchService.stop(getApplication()) }
        val id = mutable.value.profile?.optString("id")?.takeIf { it.isNotBlank() }
        mutable.update { it.copy(syntheticConversationProfileId = if (enabled) id else null,
            privateTestProfileId = if (enabled) null else it.privateTestProfileId) }
        if (enabled) viewModelScope.launch {
            val language = appLocale()
            val questions = try {
                val catalog = api.request("synthetic/") as JSONObject
                if (!catalog.optBoolean("enabled")) emptyList()
                else (catalog.optJSONArray("questions") ?: JSONArray()).rows().map { it.getString("id") to it.optString(language) }
            } catch (_: Exception) { emptyList() }
            mutable.update { if (it.syntheticConversationProfileId == id) it.copy(syntheticQuestions = questions) else it }
        }
    }
    fun privateWatchEnabled(): Boolean {
        val current = mutable.value
        if (current.privateTestProfileId == null) return false
        if (!privateMediaAllowed(current.profile, current.privateTestProfileId, "camera")) throw ApiFailure("private_test_consent_required")
        return true
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
    /** [synthetic]: the shapes preview stands for the server fixture, so only fixture ids are sent ([objectName] is then
     * "red_circle" or "blue_square"); real photos need the person's own grants, which the server checks. */
    fun analyze(synthetic: Boolean, objectName: String? = null) = operation {
        val result = if (synthetic) {
            api.uploadForm(if (objectName == null) "scene/" else "locate/", fixtureImageFields(appLocale(), objectName ?: "shapes"))
        } else {
            val image = mutable.value.image ?: throw ApiFailure("image_required")
            val fields = imageRequestFields(mutable.value.profile, mutable.value.privateTestProfileId)
            if (objectName != null) fields["object_name"] = objectName
            api.upload(if (objectName == null) "scene/" else "locate/", image, fields)
        }
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
    fun speak(text: String) { speak(text, null) }
    /** Speaks [text]; returns false (and reports it) when no voice is available. [onDone] runs on the main thread. */
    fun speak(text: String, onDone: (() -> Unit)?): Boolean {
        val locale = Locale.forLanguageTag(mutable.value.profile?.optString("locale", "es-EC") ?: "es-EC")
        if (!voice.available(locale)) { reportError("voice_unavailable"); return false }
        voice.speak(text, locale, if (mutable.value.communication?.optString("pace") == "slow") 0.8f else 1.0f, onDone)
        return true
    }
    fun stopSpeech() = voice.stop()
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
        val state = mutable.value
        val privateTest = state.privateTestProfileId != null
        if (privateTest && !privateMediaAllowed(state.profile, state.privateTestProfileId, "microphone")) { reportError("private_test_consent_required"); return }
        captionEpoch.incrementAndGet(); captionsActive.set(true); retiredSpeechTurns.clear(); activeSpeechTurn = null; lastSignPhrase = null
        invalidateSigns(if (supportsSignCatalog(mutable.value.communication?.optString("sign_language"))) "waiting" else "unsupported")
        mutable.update { it.copy(captions = emptyList(), error = null) }
        captionClient.start(state.profile?.optString("locale") ?: "es-EC", state.profile?.optString("id").orEmpty(), privateTest)
    }
    fun stopCaptions() {
        captionsActive.set(false); captionEpoch.incrementAndGet(); captionClient.close()
        retiredSpeechTurns.clear(); activeSpeechTurn = null; lastSignPhrase = null
        invalidateSigns("waiting"); mutable.update { it.copy(captions = emptyList()) }
    }
    fun finishCaptions() { captionClient.stop() }
    override fun onCleared() { stopCaptions(); voice.shutdown(); super.onCleared() }
}
