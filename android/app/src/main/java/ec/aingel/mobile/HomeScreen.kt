package ec.aingel.mobile

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.speech.SpeechRecognizer
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.ImageCapture
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.runtime.collectAsState
import kotlinx.coroutines.Job
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

private data class Card(val time: String?, val title: String, val meta: String)
private data class MemoryCard(val value: String, val meta: String)
/** "model" answers are the only ones whose text is sent back to Meta as conversation history. */
private enum class Origin { LOCAL, MODEL, MOCK, VISION, NOTICE }
private data class Answer(
    val text: String, val spoken: String, val cards: List<Card> = emptyList(), val memory: MemoryCard? = null, val source: String,
    val origin: Origin = Origin.LOCAL, val link: Pair<String, String>? = null, val excerpt: String? = null, val offerLocal: Boolean = false,
    /** Web pages Meta's search used for the answer (title to https URL). */
    val web: List<Pair<String, String>> = emptyList(),
    /** App feature the model asked this phone to run (name, arguments) instead of answering in words. */
    val action: Pair<String, JSONObject>? = null,
)
/** App features offered to the model as tools (backend assistance.conversation.APP_ACTIONS). */
private val APP_ACTIONS = listOf("describe_surroundings", "find_object", "start_continuous_watch", "stop_continuous_watch", "listen_and_sign", "open_sign_translator")
private data class Exchange(val id: Long, val question: String, val answer: Answer?)
private const val MAX_MODEL_PAIRS = 5

/** 3a eyes button: two pills; navy disc with gold pills when AINGEL is looking. */
@Composable fun EyesButton(on: Boolean, onClick: () -> Unit) {
    val label = stringResource(if (on) R.string.ui_eyes_off else R.string.ui_eyes_on)
    Box(Modifier.size(44.dp).clip(CircleShape).background(if (on) Ui.Navy else Color.White).border(1.5.dp, if (on) Ui.Navy else Ui.Control, CircleShape)
        .clickable(role = Role.Switch, onClickLabel = label, onClick = onClick).semantics { contentDescription = label; stateDescription = if (on) "on" else "off" },
        contentAlignment = Alignment.Center) {
        Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) { repeat(2) { Box(Modifier.size(6.dp, 14.dp).background(if (on) Ui.Gold else Ui.Navy, RoundedCornerShape(3.dp))) } }
    }
}

/** Hand pictogram button that opens the sign-language translator. */
@Composable fun HandButton(onClick: () -> Unit) {
    val label = stringResource(R.string.ui_signs_title)
    Box(Modifier.size(44.dp).clip(CircleShape).background(Color.White).border(1.5.dp, Ui.Control, CircleShape)
        .clickable(role = Role.Button, onClickLabel = label, onClick = onClick).semantics { contentDescription = label }, contentAlignment = Alignment.Center) {
        HandGlyph(22.dp, Ui.Navy)
    }
}

/** Orb, optionally looking through its eyes at the live camera (3a). */
@Composable fun OrbWithCamera(state: AingelOrbState, size: Dp, reduced: Boolean, vision: Boolean, front: Boolean, level: () -> Float,
                              onCapture: (ImageCapture) -> Unit = {}, onCameraError: () -> Unit = {}) {
    Box(Modifier.size(size), contentAlignment = Alignment.Center) {
        if (vision) LiveCamera(front, Modifier.matchParentSize().clip(CircleShape), onReady = onCapture, onError = onCameraError)
        // The white face plate is round, so the view stays clean on tinted cards.
        AingelOrb(state, size, if (vision) Modifier.clip(CircleShape) else Modifier, reducedMotion = reduced, vision = vision,
            background = if (vision) Color.White else null, audioLevel = level)
    }
}

@Composable fun HomeScreen(model: AingelViewModel, s: MobileState, onToday: () -> Unit, onSigns: () -> Unit, onFocus: (Boolean) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val profile = s.profile!!
    val zoneId = zone(profile.optString("timezone"))
    val prefs = profile.optJSONObject("preferences")
    val reduced = prefs?.optBoolean("reduced_motion") == true
    val voice = remember { VoiceInput(context) }
    var phase by remember { mutableStateOf(AingelOrbState.IDLE) }
    var transcript by remember { mutableStateOf("") }
    val thread = remember { mutableStateListOf<Exchange>() }
    var composerOpen by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf<String?>(null) }
    var draft by remember { mutableStateOf("") }
    var routines by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var settleJob by remember { mutableStateOf<Job?>(null) }
    // Authorizations (camera, microphone, sending to Meta) are given at sign-up; the server checks them.
    var autoRead by remember { mutableStateOf(true) }
    val shape = rememberWindowShape()  // phone, outer screen (orb only) or two panes (AINGEL_Plegables)
    // Listening only while AINGEL is on screen: hidden (Home, lock, folded) the microphone is released.
    val lifecycleState by LocalLifecycleOwner.current.lifecycle.currentStateFlow.collectAsState()
    val resumed = lifecycleState.isAtLeast(Lifecycle.State.RESUMED)
    var vision by remember { mutableStateOf(false) }
    var capture by remember { mutableStateOf<ImageCapture?>(null) }
    var seeking by remember { mutableStateOf("") }
    var nextId by remember { mutableLongStateOf(1L) }
    // Continuous voice conversation: after each answer AINGEL listens again, until 25 s pass with nobody speaking.
    var continuous by remember { mutableStateOf(false) }
    var silenceUntil by remember { mutableLongStateOf(0L) }
    // 5a · top-right menu and its modes.
    val homeKind = remember(prefs?.toString()) { homeProfile(prefs) }
    var menuOpen by remember { mutableStateOf(false) }
    var mode by remember { mutableStateOf<HomeMode?>(null) }
    var seeSub by remember { mutableStateOf(false) }
    var seeVoice by remember { mutableStateOf(true) }
    var signSeq by remember { mutableStateOf<List<String>>(emptyList()) }
    var signKey by remember { mutableIntStateOf(0) }
    var signing by remember { mutableStateOf(false) }
    var hands3d by remember { mutableStateOf(OrbAnimation.enabled) }
    var heard by remember { mutableStateOf("") }
    var said by remember { mutableStateOf("") }
    var typedSigns by remember { mutableStateOf("") }
    val message = remember { mutableStateListOf<String>() }
    var modeJob by remember { mutableStateOf<Job?>(null) }
    var signGuard by remember { mutableStateOf<Job?>(null) }  // reopens listening if the hands never report the end
    val watch by WatchState.status.collectAsState()
    val str = { id: Int -> context.getString(id) }
    val spanish = profile.optString("locale", "es-EC") != "en-US"
    LaunchedEffect(spanish) { AudioRoute.spanish = spanish }
    DisposableEffect(Unit) { onDispose { voice.stop(); model.stopSpeech(); onFocus(false) } }
    LaunchedEffect(phase, mode) { onFocus(phase == AingelOrbState.LISTENING || mode == HomeMode.HEAR) }
    LaunchedEffect(profile.optString("id")) {
        while (true) {
            routines = try { (model.profileRequest("routines/") as JSONArray).rows() } catch (_: Exception) { routines }
            delay(60_000)
        }
    }
    val today = summarizeToday(routines, zoneId)
    fun settle(state: AingelOrbState, ms: Long) { settleJob?.cancel(); phase = state; settleJob = scope.launch { delay(ms); phase = AingelOrbState.IDLE } }

    /** Local, evidence-based answers; none of this is sent to Meta. */
    suspend fun local(question: String): Answer? = when (intentOf(question)) {
        AskIntent.MEMORY -> {
            val entity = memoryEntity(question)
            when {
                entity.isBlank() -> str(R.string.ui_which_object).let { Answer(it, it, source = str(R.string.ui_src_memories)) }
                profile.optJSONObject("permissions")?.optBoolean("memories") != true -> str(R.string.access_denied).let { Answer(it, it, source = str(R.string.ui_src_permissions)) }
                else -> {
                    phase = AingelOrbState.SEARCHING
                    val ev = (model.profileRequest("ask/", "POST", JSONObject().put("tool", "search_memory").put("entity", entity)) as JSONObject).optJSONObject("evidence")
                    if (ev == null) context.getString(R.string.ui_no_memory, entity).let { Answer(it, it, source = str(R.string.ui_src_memories_none)) }
                    else {
                        val value = ev.optString("entity").replaceFirstChar { it.uppercase() } + ", " + ev.optString("location") + "."
                        Answer("", str(R.string.ui_memory_lead) + ": " + value, memory = MemoryCard(value,
                            timeOf(ev.optString("observed_at"), zoneId) + " · " + context.getString(R.string.ui_recorded_by, ev.optString("author"))), source = str(R.string.ui_src_memories))
                    }
                }
            }
        }
        AskIntent.ROUTINES -> {
            val items = (model.profileRequest("routines/") as JSONArray).rows(); routines = items
            val sum = summarizeToday(items, zoneId)
            if (sum.list.isEmpty()) str(R.string.ui_no_routines_today).let { Answer(it, it, source = str(R.string.ui_src_routines)) }
            else {
                val next = sum.next
                val after = next?.let { n -> sum.list.firstOrNull { !it.optBoolean("confirmed_today") && it.optString("at") > n.optString("at") } }
                val lead = context.getString(R.string.ui_routines_lead, sum.list.size, sum.done)
                val text = if (next == null) "$lead ${str(R.string.ui_routines_none_left)}" else lead + " " + context.getString(R.string.ui_routines_next, next.optString("title"), hhmm(next.optString("at"))) +
                    (after?.let { " " + context.getString(R.string.ui_routines_after, it.optString("title"), hhmm(it.optString("at"))) } ?: "")
                Answer(text, text, listOfNotNull(next, after).map { Card(hhmm(it.optString("at")), it.optString("title"), it.optString("instructions")) }, source = str(R.string.ui_src_routines))
            }
        }
        AskIntent.MESSAGES -> {
            val items = (model.profileRequest("messages/") as JSONArray).rows().sortedByDescending { it.optString("created_at") }
            if (items.isEmpty()) str(R.string.ui_no_messages).let { Answer(it, it, source = str(R.string.ui_src_messages)) }
            else context.getString(R.string.ui_last_message_from, items[0].optString("author"), items[0].optString("body")).let { text ->
                Answer(text, text, items.take(2).map { Card(timeOf(it.optString("created_at"), zoneId), it.optString("body"), it.optString("author")) }, source = str(R.string.ui_src_messages))
            }
        }
        AskIntent.SUPPORT -> str(supportMessageResource(s.communication?.optString("distress"))).let { Answer(it + " " + str(R.string.support_no_call), it, source = str(R.string.ui_src_support)) }
        AskIntent.UNKNOWN -> null
    }

    /** General questions: Muse Spark with MedlinePlus and, when needed, web search, under the sign-up authorization. */
    suspend fun general(question: String, history: List<Exchange>): Answer {
        val turns = JSONArray()
        val pairs = history.filter { it.answer?.origin == Origin.MODEL && it.question.isNotBlank() }.takeLast(MAX_MODEL_PAIRS)
            .map { it.question.take(1000) to it.answer!!.spoken.take(1000) }
        boundedHistory(pairs, question.take(1000)).forEach { (q, a) ->
            turns.put(JSONObject().put("role", "user").put("text", q))
            turns.put(JSONObject().put("role", "assistant").put("text", a))
        }
        turns.put(JSONObject().put("role", "user").put("text", question.take(1000)))
        return try {
            val reply = model.converse(turns, APP_ACTIONS)
            val retrieval = reply.optJSONObject("provenance")?.optString("retrieval") == "medlineplus"
            val searched = reply.optJSONObject("provenance")?.optString("retrieval") == "web"
            val action = reply.optJSONObject("action")?.let { a -> a.optString("name").takeIf { it in APP_ACTIONS }?.let { it to (a.optJSONObject("arguments") ?: JSONObject()) } }
            val src = reply.optJSONObject("source")
            val link = src?.let { it.optString("title") to it.optString("url") }
            val text = reply.optString("text")
            if (reply.optString("mode") == "mock") {
                val excerpt = reply.optString("excerpt").takeIf { it.isNotBlank() && it != "null" }
                Answer(text, listOfNotNull(text, excerpt).joinToString(" "), source = str(if (retrieval) R.string.ui_src_mock_medline else R.string.ui_src_mock),
                    origin = Origin.MOCK, link = link, excerpt = excerpt)
            } else {
                val web = (reply.optJSONArray("citations") ?: JSONArray()).rows().mapNotNull { c -> c.optString("url").takeIf { it.startsWith("https://") }?.let { c.optString("title").ifBlank { it } to it } }
                Answer(text, text, source = str(when { retrieval -> R.string.ui_src_model_medline; web.isNotEmpty() || searched -> R.string.ui_src_model_web; else -> R.string.ui_src_model }),
                    origin = Origin.MODEL, link = link, web = web, action = action)
            }
        } catch (e: ApiFailure) {
            val message = when {
                e.status == 429 -> str(R.string.ui_conv_throttled)
                e.code == "privacy_review_required" -> str(R.string.ui_conv_privacy_off)
                e.code == "synthetic_fixture_required" -> str(R.string.ui_conv_synthetic_pick)
                else -> str(R.string.ui_conv_offline)
            }
            Answer(message, message, source = str(R.string.ui_src_local), origin = Origin.NOTICE, offerLocal = true)
        }
    }

    var listenAgain: () -> Unit = {}  // set below, once startListening exists
    var runAction: (String, JSONObject, String) -> Unit = { _, _, _ -> }  // set below, once the modes exist
    fun reply(id: Long, answer: Answer?) {
        val index = thread.indexOfFirst { it.id == id }
        if (index >= 0) thread[index] = thread[index].copy(answer = answer)
        if (answer == null) { settle(AingelOrbState.CONFUSED, 3200); return }
        model.clearError()
        silenceUntil = 0L
        val next = { if (continuous) scope.launch { delay(350); if (continuous && phase == AingelOrbState.IDLE) listenAgain() } }
        // On an outer screen there is no text, so AINGEL always answers aloud.
        phase = if ((autoRead || shape == WindowShape.COVER) && model.speak(answer.spoken) { if (phase == AingelOrbState.SPEAKING) { phase = AingelOrbState.IDLE; next() } }) AingelOrbState.SPEAKING
            else { next(); AingelOrbState.IDLE }
    }

    fun ask(question: String) {
        settleJob?.cancel(); model.stopSpeech()
        val text = question.trim(); if (text.isEmpty()) return
        // Camera requests are AINGEL's own job: done at once, even without Meta.
        when (cameraCommandOf(text)) {
            CameraCommand.SEE -> { runAction("describe_surroundings", JSONObject(), text); return }
            CameraCommand.WATCH -> { runAction("start_continuous_watch", JSONObject(), text); return }
            CameraCommand.WATCH_STOP -> { runAction("stop_continuous_watch", JSONObject(), text); return }
            null -> {}
        }
        val id = nextId++
        val history = thread.toList()
        thread.add(Exchange(id, text, null)); notice = null; phase = AingelOrbState.THINKING
        scope.launch {
            val started = System.currentTimeMillis()
            val answer = try { local(text) ?: general(text, history) } catch (_: Exception) {
                notice = str(R.string.failed); thread.removeAll { it.id == id }; continuous = false; silenceUntil = 0L; settle(AingelOrbState.RETRYING, 2200); return@launch
            }
            delay((600 - (System.currentTimeMillis() - started)).coerceAtLeast(0))
            val action = answer.action
            if (action != null) { thread.removeAll { it.id == id }; runAction(action.first, action.second, text) } else reply(id, answer)
        }
    }

    /** Synthetic demo: a question the server wrote, answered with a fictitious profile; nothing typed or said is sent. */
    fun askFixture(fixture: String, question: String) {
        settleJob?.cancel(); model.stopSpeech()
        val id = nextId++
        thread.add(Exchange(id, question, null)); notice = null; phase = AingelOrbState.THINKING; composerOpen = true
        scope.launch {
            val answer = try {
                val reply = model.converseFixture(fixture)
                val text = reply.optString("text")
                if (reply.optString("mode") == "mock") Answer(text, text, source = str(R.string.ui_src_mock), origin = Origin.MOCK)
                else Answer(text, text, source = str(R.string.ui_src_synthetic), origin = Origin.MODEL)
            } catch (_: Exception) { str(R.string.ui_conv_offline).let { Answer(it, it, source = str(R.string.ui_src_local), origin = Origin.NOTICE) } }
            reply(id, answer)
        }
    }

    /** One-off capture of the full frame; sent only with the image consent and never stored. */
    fun look(objectName: String?, question: String? = null) {
        val use = capture ?: return
        val id = nextId++
        thread.add(Exchange(id, question ?: if (objectName == null) str(R.string.ui_vision_describe) else context.getString(R.string.ui_vision_find_q, objectName), null))
        composerOpen = true
        phase = if (objectName == null) AingelOrbState.THINKING else AingelOrbState.SEARCHING
        scope.launch {
            val caution = str(R.string.ui_vision_caution)
            val answer = try {
                val result = model.analyzeFrame(use.jpegFrame(context), objectName)
                val mock = result.optString("mode") == "mock"
                val text = if (objectName == null) withKnownPeople(result, result.optString("text")) else if (mock) str(R.string.ui_vision_mock) else {
                    val sides = (result.optJSONArray("matches") ?: JSONArray()).rows().map {
                        str(when (it.optString("horizontal")) { "left" -> R.string.ui_side_left; "right" -> R.string.ui_side_right; else -> R.string.ui_side_center })
                    }
                    if (sides.isEmpty()) context.getString(R.string.ui_vision_none, objectName) else context.getString(R.string.ui_vision_found, sides.size, objectName, sides.joinToString(", "))
                }
                Answer("$text $caution", text, origin = Origin.VISION,
                    source = if (mock) str(R.string.ui_src_vision_mock) else context.getString(R.string.ui_src_vision_meta, result.optString("model", "Meta")))
            } catch (e: ApiFailure) {
                str(if (e.code == "privacy_review_required") R.string.ui_vision_need_consent else R.string.ui_vision_failed).let { Answer(it, it, source = str(R.string.ui_src_local), origin = Origin.NOTICE) }
            } catch (_: Exception) { str(R.string.ui_vision_failed).let { Answer(it, it, source = str(R.string.ui_src_local), origin = Origin.NOTICE) } }
            reply(id, answer)
        }
    }

    /**
     * Listens for the person. Voice turns are continuous: each listening turn has a 25 s silence window
     * ([silenceUntil]); the recogniser stops after a few seconds of silence, so it restarts quietly inside the
     * window, and when the window passes AINGEL simply stops listening and says nothing.
     * [retry]: one more try if the recogniser is still busy (right after the wake phrase released it).
     */
    fun startListening(retry: Boolean = false, followUp: Boolean = false) {
        settleJob?.cancel(); model.stopSpeech(); notice = null; transcript = ""
        if (!followUp) continuous = true
        if (silenceUntil == 0L) silenceUntil = System.currentTimeMillis() + 25_000
        phase = AingelOrbState.LISTENING
        val silent = {
            if (continuous && System.currentTimeMillis() < silenceUntil) scope.launch { delay(250); if (continuous && phase == AingelOrbState.LISTENING) startListening(followUp = true) }
            else { continuous = false; silenceUntil = 0L; phase = AingelOrbState.IDLE }
        }
        voice.start(profile.optString("locale", "es-EC"), onPartial = { transcript = it }, onResult = { heard ->
            voice.stop()
            if (heard.isBlank()) silent() else { transcript = heard; silenceUntil = 0L; ask(heard) }
        }, onFailure = { error ->
            voice.stop()
            if (error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) silent()
            else if (retry && error in setOf(SpeechRecognizer.ERROR_RECOGNIZER_BUSY, SpeechRecognizer.ERROR_CLIENT, SpeechRecognizer.ERROR_SERVER_DISCONNECTED)) {
                scope.launch { delay(600); startListening(false) }
            }
            else { continuous = false; silenceUntil = 0L; phase = AingelOrbState.IDLE; composerOpen = true; notice = str(R.string.ui_voice_failed) }
        })
    }
    fun listenFollowUp() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) startListening(followUp = true)
        else continuous = false
    }
    listenAgain = ::listenFollowUp
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) startListening() else { phase = AingelOrbState.IDLE; composerOpen = true; notice = str(R.string.ui_mic_denied) }
    }
    val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) vision = true else notice = str(R.string.ui_camera_denied)
    }
    fun onMic() {
        when (phase) {
            // Tapping to finish ends the conversation's follow-up listening too, even if nothing was said.
            AingelOrbState.LISTENING -> if (voice.recognitionAvailable) { continuous = false; silenceUntil = 0L; voice.finish() } else {
                voice.stop(); phase = AingelOrbState.IDLE; composerOpen = true; notice = str(R.string.ui_voice_failed)
            }
            AingelOrbState.IDLE, AingelOrbState.HAPPY, AingelOrbState.CONFUSED ->
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) startListening()
                else micPermission.launch(Manifest.permission.RECORD_AUDIO)
            else -> { settleJob?.cancel(); voice.stop(); model.stopSpeech(); continuous = false; silenceUntil = 0L; phase = AingelOrbState.IDLE }
        }
    }
    fun endMode() {
        modeJob?.cancel(); voice.stop(); model.stopSpeech(); settleJob?.cancel()
        signGuard?.cancel(); mode = null; vision = false; capture = null; signSeq = emptyList(); signing = false; heard = ""; said = ""; typedSigns = ""; message.clear()
        phase = AingelOrbState.IDLE; notice = null
    }
    var onHandsDone: () -> Unit = {}  // set below, once «Escuchar y traducir» exists
    fun sign(seq: List<String>) {
        phase = AingelOrbState.IDLE; signSeq = seq; signing = seq.isNotEmpty(); signKey++
        signGuard?.cancel()
        if (mode == HomeMode.HEAR && signing) {
            // The microphone stays off until the whole phrase is signed: nothing heard meanwhile can cut it.
            voice.stop()
            signGuard = scope.launch { delay(4_000 + (seq.size * 1_600 / HANDS_SPEED).toLong()); if (signing) onHandsDone() }
        }
    }
    /** «Escuchar y traducir»: listens, signs what it heard with the 3D hands, then listens again until «Terminar». */
    fun hearListen(tries: Int = 0) {
        if (mode != HomeMode.HEAR || signing) return
        phase = AingelOrbState.LISTENING
        val again = { ms: Long -> modeJob?.cancel(); modeJob = scope.launch { delay(ms); hearListen() } }
        voice.start(profile.optString("locale", "es-EC"), onPartial = { heard = it }, onResult = { text ->
            voice.stop()
            if (mode == HomeMode.HEAR) {
                if (text.isBlank()) again(500)
                else {
                    heard = text; phase = AingelOrbState.THINKING
                    modeJob?.cancel(); modeJob = scope.launch {
                        // By meaning first (Meta); the word-by-word rule when Meta is not available.
                        val seq = model.signsFor(text) ?: buildSentence(text)?.seq
                        if (mode != HomeMode.HEAR) return@launch
                        if (seq.isNullOrEmpty()) again(500) else sign(seq)
                    }
                }
            }
        }, onFailure = { error ->
            voice.stop()
            if (mode == HomeMode.HEAR) {
                if (error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) again(400)
                else if (transientRecognizerError(error) && tries < 3) { modeJob?.cancel(); modeJob = scope.launch { delay(600); hearListen(tries + 1) } }
                else { phase = AingelOrbState.IDLE; notice = str(R.string.ui_voice_failed) }
            }
        })
    }
    fun onHandsSign(i: Int) {
        if (i >= 0) return
        signGuard?.cancel(); signing = false
        if (mode == HomeMode.HEAR) { modeJob?.cancel(); modeJob = scope.launch { delay(600); hearListen() } }
    }
    onHandsDone = { onHandsSign(-1) }
    /** «Ver y describir»: one frame from the rear camera, described aloud once. */
    fun describe() {
        val use = capture ?: return
        modeJob?.cancel()
        modeJob = scope.launch {
            phase = AingelOrbState.THINKING; said = ""
            val text = try {
                model.analyzeFrame(use.jpegFrame(context), null).let { withKnownPeople(it, it.optString("text")) }
            } catch (e: ApiFailure) { str(if (e.code == "privacy_review_required") R.string.ui_vision_need_consent else R.string.ui_vision_failed) }
            catch (_: Exception) { str(R.string.ui_vision_failed) }
            if (mode != HomeMode.DESCRIBE) return@launch
            said = text
            phase = if (model.speak("$text ${str(R.string.ui_vision_caution)}") { if (phase == AingelOrbState.SPEAKING) phase = AingelOrbState.IDLE }) AingelOrbState.SPEAKING else AingelOrbState.IDLE
        }
    }
    val modeMic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> if (ok) hearListen() else { phase = AingelOrbState.IDLE; notice = str(R.string.ui_mic_denied) } }
    val modeCamera = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> if (ok && mode?.camera == true) vision = true else if (!ok) notice = str(R.string.ui_camera_denied) }
    fun startMode(m: HomeMode, voiceOut: Boolean = true) {
        endMode(); mode = m; menuOpen = false; seeSub = false
        when (m) {
            HomeMode.HEAR -> if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) hearListen() else modeMic.launch(Manifest.permission.RECORD_AUDIO)
            HomeMode.WRITE -> sign(listOf("hola"))
            HomeMode.SEE, HomeMode.DESCRIBE -> {
                seeVoice = voiceOut
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) vision = true else modeCamera.launch(Manifest.permission.CAMERA)
            }
            HomeMode.WATCH -> {}
        }
    }
    fun pickMode(m: HomeMode) { if (m == HomeMode.SEE && mode != HomeMode.SEE) seeSub = !seeSub else if (mode == m) { endMode(); menuOpen = false } else startMode(m) }
    LaunchedEffect(capture, mode) { if (mode == HomeMode.DESCRIBE && capture != null && said.isEmpty()) { delay(1200); describe() } }
    fun beginWatch() {
        val privateTest = try { model.privateWatchEnabled() } catch (e: ApiFailure) { model.reportError(e.code); return }
        WatchService.start(context, profile.getString("id"), profile.optString("locale", "es-EC"), privateTest,
            s.communication?.optString("spontaneous")?.takeIf { it.isNotBlank() } ?: "normal")
        endMode(); (context as? Activity)?.moveTaskToBack(true)
    }
    val watchPermissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
        when {
            granted[Manifest.permission.CAMERA] == false -> notice = str(R.string.ui_camera_denied)
            granted[Manifest.permission.POST_NOTIFICATIONS] == false -> notice = str(R.string.ui_m_notifications_denied)
            else -> beginWatch()
        }
    }
    fun startWatch() {
        val needed = buildList {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) add(Manifest.permission.CAMERA)
            if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) add(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (needed.isEmpty()) beginWatch() else watchPermissions.launch(needed.toTypedArray())
    }
    BackHandler(mode != null || menuOpen) { if (menuOpen) { menuOpen = false; seeSub = false } else endMode() }
    // 5b · voice control: while home is open and idle, AINGEL listens for its phrase and then for the question.
    val wakeOn = remember { VoiceControl.enabled(context) && VoiceControl.trained(context) }
    val wakeWord = remember { VoiceControl.word(context) }
    val wakeIdle = wakeOn && resumed && mode == null && !menuOpen && phase == AingelOrbState.IDLE && thread.isEmpty() && !composerOpen &&
        ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
    LaunchedEffect(resumed) {
        if (resumed) { if (mode == HomeMode.HEAR && !signing && phase != AingelOrbState.LISTENING) hearListen(); return@LaunchedEffect }
        modeJob?.cancel(); voice.stop(); continuous = false; silenceUntil = 0L
        if (phase == AingelOrbState.LISTENING) phase = AingelOrbState.IDLE
    }
    LaunchedEffect(wakeIdle) {
        if (!wakeIdle) return@LaunchedEffect
        // Restarts run in this effect, so opening the menu, a mode or another screen ends them and frees the microphone.
        var waking = false; var mine = -1
        try {
            delay(800)
            fun wait() {
                waking = true
                // Waits for the whole utterance: «Hola AINGEL, ¿qué tengo hoy?» is answered at once; the phrase alone opens listening.
                mine = voice.start(profile.optString("locale", "es-EC"), onPartial = {}, onResult = { heard ->
                    waking = false; voice.stop()
                    if (VoiceControl.heard(heard, wakeWord)) {
                        val rest = VoiceControl.afterPhrase(heard)
                        if (rest.split(' ').count { it.isNotBlank() } >= 2) { transcript = rest; ask(rest) }
                        else scope.launch { delay(450); startListening(retry = true) }
                    } else launch { delay(300); wait() }
                }, onFailure = { _ -> waking = false; voice.stop(); launch { delay(600); wait() } })
            }
            wait()
            awaitCancellation()
        } finally { if (waking) voice.stopIf(mine) }  // never the session the person just opened with the mic
    }

    fun toggleVision() {
        if (vision) { vision = false; capture = null; return }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) vision = true
        else cameraPermission.launch(Manifest.permission.CAMERA)
    }
    fun clearConversation() { settleJob?.cancel(); voice.stop(); model.stopSpeech(); continuous = false; silenceUntil = 0L; thread.clear(); notice = null; phase = AingelOrbState.IDLE }
    /** A short local answer in the conversation (spoken unless the feature speaks for itself). */
    fun localReply(question: String, text: String, speak: Boolean = true) {
        val id = nextId++
        thread.add(Exchange(id, question, null)); composerOpen = true
        if (speak) reply(id, Answer(text, text, source = str(R.string.ui_src_local)))
        else { val i = thread.indexOfFirst { it.id == id }; if (i >= 0) thread[i] = thread[i].copy(answer = Answer(text, text, source = str(R.string.ui_src_local))); phase = AingelOrbState.IDLE }
    }
    /** Looks through the rear camera (the orb's eyes) and describes, or searches for [objectName]. */
    fun seeNow(question: String, objectName: String?) {
        // The outer screen faces the person, not the scene: the phone has to be opened to look.
        if (shape == WindowShape.COVER) { localReply(question, str(R.string.ui_cover_open_to_see)); return }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            cameraPermission.launch(Manifest.permission.CAMERA); localReply(question, str(R.string.ui_cmd_camera_permission)); return
        }
        vision = true; composerOpen = true
        scope.launch {
            phase = if (objectName == null) AingelOrbState.THINKING else AingelOrbState.SEARCHING
            var waited = 0
            while (capture == null && waited < 50) { delay(100); waited++ }
            if (capture == null) localReply(question, str(R.string.ui_camera_failed))
            else { delay(700); look(objectName, question) }  // a moment for exposure once the camera opens
        }
    }
    runAction = { name, args, question ->
        when (name) {
            "describe_surroundings" -> seeNow(question, null)
            "find_object" -> seeNow(question, args.optString("object_name").takeIf { it.isNotBlank() }?.take(80))
            "start_continuous_watch" -> { continuous = false; voice.stop(); localReply(question, str(R.string.ui_cmd_watch_on), speak = false); startWatch() }
            "stop_continuous_watch" -> when {
                watch.running -> { WatchService.stop(context); localReply(question, str(R.string.ui_cmd_watch_off)) }
                vision -> { vision = false; capture = null; localReply(question, str(R.string.ui_cmd_camera_off)) }  // «apaga la cámara»: the eyes
                else -> localReply(question, str(R.string.ui_cmd_watch_none))
            }
            "listen_and_sign" -> { clearConversation(); composerOpen = false; startMode(HomeMode.HEAR) }
            "open_sign_translator" -> { clearConversation(); composerOpen = false; onSigns() }
        }
    }
    val inConversation = thread.isNotEmpty() || composerOpen
    BackHandler(inConversation && phase != AingelOrbState.LISTENING) { clearConversation(); composerOpen = false }

    val status = stringResource(when (phase) {
        AingelOrbState.IDLE -> if (vision) R.string.ui_st_looking else R.string.ui_st_idle; AingelOrbState.LISTENING -> R.string.ui_st_listening; AingelOrbState.THINKING -> R.string.ui_st_thinking
        AingelOrbState.SEARCHING -> R.string.ui_st_searching; AingelOrbState.SPEAKING -> R.string.ui_st_speaking; AingelOrbState.RETRYING -> R.string.ui_st_retrying
        AingelOrbState.HAPPY -> R.string.ui_st_happy; AingelOrbState.CONFUSED -> R.string.ui_st_confused })
    val hint = stringResource(when (phase) {
        AingelOrbState.LISTENING -> R.string.ui_hint_finish; AingelOrbState.SPEAKING -> R.string.ui_hint_stop
        AingelOrbState.THINKING, AingelOrbState.SEARCHING, AingelOrbState.RETRYING -> R.string.ui_hint_wait
        else -> if (vision) R.string.ui_hint_point else R.string.ui_hint_talk })
    val busy = phase !in setOf(AingelOrbState.IDLE, AingelOrbState.HAPPY, AingelOrbState.CONFUSED)
    val level: () -> Float = when (phase) { AingelOrbState.LISTENING -> voice::level; AingelOrbState.SPEAKING -> model::speechLevel; else -> { { 0f } } }
    val name = s.communication?.optString("preferred_name")?.takeIf { it.isNotBlank() } ?: profile.optString("display_name").substringBefore(' ')
    val orb: @Composable (Dp) -> Unit = { size ->
        OrbWithCamera(phase, size, reduced, vision, front = mode == HomeMode.SEE, level = level, onCapture = { capture = it },
            onCameraError = { vision = false; capture = null; notice = str(R.string.ui_camera_failed) })
    }
    val visionPanel: @Composable () -> Unit = {
        if (vision) Column(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
            PrimaryButton(stringResource(R.string.ui_vision_describe), height = 46.dp, enabled = capture != null && !busy) { look(null) }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FieldInput(stringResource(R.string.ui_vision_object), seeking, { seeking = it.take(80) }, Modifier.weight(1f), height = 44.dp, fontSize = 14)
                OutlineButton(stringResource(R.string.ui_vision_find), Modifier.width(110.dp).padding(top = 26.dp), 44.dp, enabled = capture != null && !busy && seeking.isNotBlank(), size = 14) { look(seeking.trim()) }
            }
            T(stringResource(R.string.ui_camera_private), 11, color = Ui.Muted, align = TextAlign.Center)
        }
    }

    val menu = homeKind.modes.isNotEmpty()
    // While the corner menu is open the greeting hides, so nothing overlaps (5a); two panes list the options instead.
    val greeting: @Composable (Boolean) -> Unit = { corner ->
        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).padding(end = if (corner && menu) 56.dp else 0.dp).graphicsLayer { alpha = if (corner && menuOpen) 0f else 1f },
            horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                T(stringResource(R.string.home_hello, name), 22, FontWeight.SemiBold, Ui.Navy, lineHeight = 1.25f)
                T(longDate(profile.optString("locale", "es-EC"), zoneId), 13, color = Ui.Muted)
            }
            if (!menu) { HandButton { vision = false; onSigns() }; EyesButton(vision) { toggleVision() } }
        }
    }
    val stage: @Composable () -> Unit = {
        if (mode?.signs == true) BoxWithConstraints(Modifier.fillMaxWidth(), contentAlignment = Alignment.TopCenter) {
            // Hands around the orb: r ≈ 0.29 × orb, as in the catalogue stage.
            val orbSize = 250.dp; val r = orbSize * 0.288f; val w = minOf(maxWidth, 360.dp); val cy = orbSize / 2; val h = cy + r * 3.3f
            Box(Modifier.size(w, h)) {
                Box(Modifier.offset(x = (w - orbSize) / 2)) { orb(orbSize) }
                if (hands3d) AingelHands3D(w, h, w / 2, cy, r, signSeq, signKey, onSign = ::onHandsSign) { hands3d = false }
                else AingelSigner(w, h, w / 2, cy, r, signSeq, signKey, onSign = ::onHandsSign)
            }
        } else orb(250.dp)
    }
    val controls: @Composable ColumnScope.() -> Unit = {
        when (mode) {
            null -> {
                if (s.syntheticConversationProfileId == profile.optString("id")) {
                    Notice(stringResource(R.string.synthetic_conversation_active)); Spacer(Modifier.height(8.dp))
                    SyntheticQuestions(s.syntheticQuestions, busy) { id, q -> askFixture(id, q) }; Spacer(Modifier.height(10.dp))
                }
                T(status, 18, FontWeight.Medium, Ui.Navy, align = TextAlign.Center, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                if (!menu) visionPanel()
                Spacer(Modifier.height(18.dp))
                MicButton(busy, hint) { onMic() }
                Spacer(Modifier.height(8.dp)); T(hint, 13, color = Ui.Muted)
                if (!busy) LinkButton(stringResource(R.string.ui_prefer_type), size = 12, color = Ui.Muted) { composerOpen = true }
                if (wakeIdle) T(stringResource(R.string.ui_s_wake_hint, wakeWord), 12, color = Ui.Muted, align = TextAlign.Center)
                notice?.let { Spacer(Modifier.height(12.dp)); Notice(it) }
                if (watch.running) { Spacer(Modifier.height(16.dp)); WatchCard(watch) { WatchService.stop(context) } }
                Spacer(Modifier.weight(1f).heightIn(min = 16.dp))
                today.next?.let { next -> NextCard(next, own = next.optString("author") == s.username, onOpen = onToday) }
            }
            HomeMode.HEAR -> {
                T(stringResource(if (signing) R.string.ui_m_signing_mic_paused else if (phase == AingelOrbState.LISTENING) R.string.ui_st_listening else R.string.ui_st_idle), 18, FontWeight.Medium, Ui.Navy,
                    align = TextAlign.Center, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                if (heard.isNotBlank()) { Spacer(Modifier.height(6.dp)); T("«$heard»", 15, color = Ui.Muted, align = TextAlign.Center) }
                Spacer(Modifier.height(10.dp)); DesignBadge()
                notice?.let { Spacer(Modifier.height(12.dp)); Notice(it) }
                Spacer(Modifier.weight(1f).heightIn(min = 20.dp)); StopButton { endMode() }
            }
            HomeMode.WRITE -> {
                if (signing) T(stringResource(R.string.ui_m_signing), 18, FontWeight.Medium, Ui.Navy, align = TextAlign.Center, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                DesignBadge()
                Spacer(Modifier.weight(1f).heightIn(min = 20.dp))
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FieldInput(stringResource(R.string.ui_m_write_here), typedSigns, { typedSigns = it.take(200) }, Modifier.weight(1f), height = 52.dp)
                    val toSigns = stringResource(R.string.ui_m_to_signs)
                    Box(Modifier.size(52.dp).clip(RoundedCornerShape(16.dp)).background(if (typedSigns.isBlank()) Ui.Navy.copy(alpha = .45f) else Ui.Navy)
                        .clickable(enabled = typedSigns.isNotBlank(), role = Role.Button, onClickLabel = toSigns) { val typed = typedSigns; phase = AingelOrbState.THINKING; scope.launch { (model.signsFor(typed) ?: buildSentence(typed)?.seq)?.let { sign(it) } ?: run { phase = AingelOrbState.IDLE } } }
                        .semantics { contentDescription = toSigns }, contentAlignment = Alignment.Center) { PathIcon(ARROW_ICON, 20.dp, Color.White, 2f) }
                }
                LinkButton(stringResource(R.string.ui_m_finish), size = 14) { endMode() }
            }
            HomeMode.SEE -> {
                T(stringResource(R.string.ui_m_make_signs), 20, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center)
                Spacer(Modifier.height(4.dp)); T(stringResource(R.string.ui_m_no_recognizer), 12, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.45f)
                Spacer(Modifier.height(12.dp))
                SignBoard(spanish) { id -> message.add(id) }
                val text = message.joinToString(" ") { signName(it, spanish).trim('¿', '?') }.replaceFirstChar { it.uppercase() }
                if (message.isNotEmpty()) {
                    if (seeVoice) {
                        T("«$text»", 20, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center)
                        Spacer(Modifier.height(10.dp))
                        PrimaryButton(stringResource(R.string.ui_m_say), height = 48.dp) {
                            if (model.speak(text) { if (phase == AingelOrbState.SPEAKING) phase = AingelOrbState.IDLE }) phase = AingelOrbState.SPEAKING
                        }
                    } else T(text, 28, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center, lineHeight = 1.3f, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    LinkButton(stringResource(R.string.ui_m_clear), size = 13, color = Ui.Muted) { message.clear() }
                }
                Spacer(Modifier.height(14.dp)); StopButton { endMode() }
            }
            HomeMode.DESCRIBE -> {
                T(said.ifBlank { stringResource(R.string.ui_m_looking) }, 20, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center, lineHeight = 1.35f,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                if (said.isNotBlank()) { Spacer(Modifier.height(6.dp)); T(stringResource(R.string.ui_vision_caution), 12, color = Ui.Muted, align = TextAlign.Center) }
                Spacer(Modifier.height(10.dp))
                OutlineButton(stringResource(R.string.ui_m_describe_again), height = 46.dp, size = 14, enabled = capture != null && phase != AingelOrbState.THINKING) { describe() }
                Spacer(Modifier.weight(1f).heightIn(min = 16.dp)); StopButton { endMode() }
            }
            HomeMode.WATCH -> {
                T(stringResource(R.string.ui_m_watch), 20, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center)
                Spacer(Modifier.height(6.dp)); T(stringResource(R.string.ui_m_watch_intro), 14, color = Ui.Text, align = TextAlign.Center, lineHeight = 1.5f)
                Spacer(Modifier.height(6.dp)); T(stringResource(R.string.ui_vision_caution), 12, color = Ui.Muted, align = TextAlign.Center)
                Spacer(Modifier.height(8.dp)); T(stringResource(R.string.ui_m_watch_output, AudioRoute.outputLabel(context)), 12, color = Ui.Muted, align = TextAlign.Center)
                // Experimental: short video clips instead of photos (the server must allow it; otherwise it uses photos).
                var video by remember { mutableStateOf(WatchService.videoEnabled(context)) }
                Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Switch(video, { video = it; WatchService.setVideo(context, it) }, colors = SwitchDefaults.colors(checkedTrackColor = Ui.Navy),
                        modifier = Modifier.semantics { contentDescription = context.getString(R.string.watch_video) })
                    Spacer(Modifier.width(10.dp)); T(stringResource(R.string.watch_video), 13, FontWeight.Medium, Ui.Navy, modifier = Modifier.weight(1f))
                }
                if (video) T(stringResource(R.string.watch_video_note), 11, color = Ui.Muted, align = TextAlign.Center)
                PrimaryButton(stringResource(R.string.ui_m_watch_start), height = 52.dp) { startWatch() }
                if (!Settings.canDrawOverlays(context)) LinkButton(stringResource(R.string.ui_m_bubble), size = 13) {
                    // The person decides in the system screen; AINGEL never changes that permission itself.
                    try { context.startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + context.packageName))) } catch (_: Exception) {}
                }
                notice?.let { Spacer(Modifier.height(12.dp)); Notice(it) }
                Spacer(Modifier.weight(1f).heightIn(min = 16.dp)); LinkButton(stringResource(R.string.ui_m_finish), size = 14) { endMode() }
            }
        }
    }
    // 6a–6c · outer screen: only AINGEL; tapping makes it listen.
    if (shape == WindowShape.COVER) { CoverOrb(phase, reduced, status, level) { onMic() }; return }

    when {
        // The full-screen listening view is for the conversation; the 5a modes keep their own layout.
        phase == AingelOrbState.LISTENING && mode == null && thread.isEmpty() -> Column(Modifier.fillMaxSize().padding(start = 26.dp, end = 26.dp, top = 18.dp, bottom = 24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Row(Modifier.clip(RoundedCornerShape(50)).background(Ui.Selected).padding(horizontal = 14.dp, vertical = 8.dp).semantics { liveRegion = LiveRegionMode.Polite },
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) { Dot(Ui.Blue); T(status, 13, FontWeight.SemiBold, Ui.Blue) }
            Spacer(Modifier.height(34.dp))
            AingelOrb(phase, 290.dp, reducedMotion = reduced, audioLevel = level)
            Spacer(Modifier.height(26.dp))
            T((transcript.ifBlank { stringResource(R.string.ui_listening_placeholder) }) + "…", 23, FontWeight.Medium, Ui.Navy, align = TextAlign.Center)
            Spacer(Modifier.weight(1f))
            MicButton(true, hint) { onMic() }
            Spacer(Modifier.height(10.dp)); T(hint, 13, color = Ui.Muted)
            Spacer(Modifier.height(20.dp)); T(stringResource(R.string.ui_mic_private), 11, color = Ui.Muted, align = TextAlign.Center)
        }
        inConversation -> Column(Modifier.fillMaxSize().padding(start = 22.dp, end = 22.dp, top = 6.dp, bottom = 12.dp)) {
            val scroll = rememberScrollState()
            LaunchedEffect(thread.size, thread.lastOrNull()?.answer) { scroll.animateScrollTo(scroll.maxValue) }
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                LinkButton("‹ " + stringResource(R.string.ui_home), color = Ui.Muted) { clearConversation(); composerOpen = false }
                Spacer(Modifier.weight(1f))
                HandButton { vision = false; onSigns() }
                Spacer(Modifier.width(8.dp))
                EyesButton(vision) { toggleVision() }
            }
            if (s.syntheticConversationProfileId == profile.optString("id")) {
                Notice(stringResource(R.string.synthetic_conversation_active))
                SyntheticQuestions(s.syntheticQuestions, busy) { id, q -> askFixture(id, q) }
            }
            Column(Modifier.weight(1f).verticalScroll(scroll), horizontalAlignment = Alignment.CenterHorizontally) {
                orb(170.dp)
                Row(Modifier.semantics { liveRegion = LiveRegionMode.Polite }, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (busy) Dot(if (phase == AingelOrbState.SPEAKING) Ui.Gold else Ui.Blue)
                    T(status, 14, FontWeight.Medium, Ui.Navy)
                }
                visionPanel()
                thread.forEach { ex -> ExchangeView(ex, model, onSpeak = { phase = AingelOrbState.SPEAKING }, onStop = { phase = AingelOrbState.IDLE }, onAsk = { ask(it) }, phaseProvider = { phase }) }
                notice?.let { Spacer(Modifier.height(14.dp)); Notice(it) }
                if (phase == AingelOrbState.LISTENING) Row(Modifier.fillMaxWidth().padding(top = 16.dp).semantics { liveRegion = LiveRegionMode.Polite },
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Dot(Ui.Blue); T(transcript.ifBlank { stringResource(R.string.ui_listening_placeholder) } + "…", 15, FontWeight.Medium, Ui.Navy)
                }
            }
            Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Switch(autoRead, { autoRead = it; if (!it) model.stopSpeech() }, colors = SwitchDefaults.colors(checkedTrackColor = Ui.Navy),
                    modifier = Modifier.semantics { contentDescription = context.getString(R.string.ui_auto_read) })
                Spacer(Modifier.width(8.dp)); T(stringResource(R.string.ui_auto_read), 13, FontWeight.Medium, Ui.Navy, modifier = Modifier.weight(1f))
                if (thread.isNotEmpty()) LinkButton(stringResource(R.string.ui_conv_clear), size = 12, color = Ui.Muted) { clearConversation() }
            }
            Composer(draft, { draft = it }, stringResource(R.string.ui_composer), hint, busy, onSend = { val q = draft; draft = ""; continuous = false; voice.stop(); ask(q) }, onMic = ::onMic)
        }
        // 6d / 6e · two panes: AINGEL (and the hands) on one side, options on the other; the gap sits on the fold.
        shape == WindowShape.TWO_PANE -> Row(Modifier.fillMaxSize().padding(horizontal = 22.dp, vertical = 14.dp)) {
            Column(Modifier.weight(1f).fillMaxHeight(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { stage() }
            Spacer(Modifier.width(32.dp))
            Column(Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()), horizontalAlignment = Alignment.CenterHorizontally) {
                greeting(false)
                Spacer(Modifier.height(18.dp))
                if (menu) { ModeOptions(homeKind, mode, seeSub, onPick = ::pickMode, onSeeOutput = { voiceOut -> startMode(HomeMode.SEE, voiceOut) }); Spacer(Modifier.height(18.dp)) }
                controls()
            }
        }
        else -> Box(Modifier.fillMaxSize()) {
            val homeScroll = rememberScrollState()
            Column(Modifier.fillMaxSize().verticalScroll(homeScroll).padding(start = 22.dp, end = 22.dp, top = 14.dp, bottom = 14.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                greeting(true)
                Spacer(Modifier.height(18.dp))
                stage()
                Spacer(Modifier.height(6.dp))
                controls()
            }
            if (homeKind.modes.isNotEmpty()) {
                MenuScrim(menuOpen) { menuOpen = false; seeSub = false }
                // The button scrolls with the greeting, so it never covers the content below.
                Box(Modifier.align(Alignment.TopEnd).padding(top = 14.dp, end = 16.dp).graphicsLayer { translationY = -homeScroll.value.toFloat() }) {
                    HomeMenu(homeKind, menuOpen, mode, seeSub, reduced, onToggle = { menuOpen = !menuOpen; seeSub = false }, onPick = ::pickMode,
                        onSeeOutput = { voiceOut -> startMode(HomeMode.SEE, voiceOut) })
                }
            }
        }
    }
}

@Composable private fun DesignBadge() {
    Box(Modifier.clip(RoundedCornerShape(50)).background(Color(0xFFFDF3DF)).padding(horizontal = 10.dp, vertical = 4.dp)) {
        T(stringResource(R.string.ui_signs_design), 11, FontWeight.SemiBold, Color(0xFF7A5410), align = TextAlign.Center)
    }
}

/** Continuous watching is running in the background: last description and «Detener». */
@Composable private fun WatchCard(status: WatchState.Status, onStop: () -> Unit) {
    val context = LocalContext.current
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).border(1.dp, Ui.Border, RoundedCornerShape(22.dp)).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) { Dot(Color(0xFF3FB27F)); T(stringResource(R.string.ui_m_watch_running), 13, FontWeight.SemiBold, Ui.Navy) }
        T(status.line, 15, FontWeight.Medium, Ui.Text, lineHeight = 1.45f, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            T(stringResource(R.string.ui_m_watch_output, AudioRoute.outputLabel(context)), 12, color = Ui.Muted, modifier = Modifier.weight(1f))
            PrimaryButton(stringResource(R.string.ui_m_watch_stop), Modifier.width(120.dp), 40.dp, fill = false, onClick = onStop)
        }
    }
}

@Composable private fun ExchangeView(ex: Exchange, model: AingelViewModel, onSpeak: () -> Unit, onStop: () -> Unit, onAsk: (String) -> Unit, phaseProvider: () -> AingelOrbState) {
    val uri = LocalUriHandler.current
    Column(Modifier.fillMaxWidth().padding(top = 18.dp)) {
        if (ex.question.isNotBlank()) Box(Modifier.align(Alignment.End).clip(RoundedCornerShape(16.dp, 16.dp, 4.dp, 16.dp)).background(Ui.Selected).padding(horizontal = 14.dp, vertical = 10.dp)) {
            T(ex.question, 14, FontWeight.Medium, Ui.Navy)
        }
        ex.answer?.let { a ->
            Spacer(Modifier.height(12.dp))
            if (a.memory != null) Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).border(1.dp, Ui.Border, RoundedCornerShape(18.dp)).padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)) {
                T(stringResource(R.string.ui_memory_lead), 12, color = Ui.Muted)
                T(a.memory.value, 20, FontWeight.SemiBold, Ui.Navy, lineHeight = 1.35f)
                T(a.memory.meta, 12, color = Ui.Muted)
                HorizontalDivider(color = Ui.Divider)
                T(stringResource(R.string.ui_memory_note), 11, color = Ui.Muted, lineHeight = 1.5f)
            } else T(a.text, 17, color = Ui.Text, lineHeight = 1.55f, modifier = Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite })
            a.excerpt?.let { Spacer(Modifier.height(10.dp)); Box(Modifier.fillMaxWidth().background(Ui.Subtle, RoundedCornerShape(10.dp)).padding(12.dp)) { T("$it…", 14, lineHeight = 1.5f) } }
            a.cards.forEach { c ->
                Spacer(Modifier.height(10.dp))
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).border(1.dp, Ui.Border, RoundedCornerShape(14.dp)).padding(horizontal = 16.dp, vertical = 14.dp),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    c.time?.let { T(it, 18, FontWeight.SemiBold, Ui.Navy) }
                    Column { T(c.title, 14, FontWeight.SemiBold, maxLines = 2); if (c.meta.isNotBlank()) T(c.meta, 12, color = Ui.Muted, maxLines = 1) }
                }
            }
            if (a.offerLocal) Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(R.string.ui_suggest_today, R.string.ui_suggest_messages).forEach { id ->
                    val label = stringResource(id)
                    Box(Modifier.clip(RoundedCornerShape(50)).border(1.dp, Ui.Control, RoundedCornerShape(50)).clickable(role = Role.Button) { onAsk(label) }.padding(horizontal = 14.dp, vertical = 9.dp)) { T(label, 12, FontWeight.Medium, Ui.Navy) }
                }
            }
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(Modifier.clip(RoundedCornerShape(50)).background(if (a.origin == Origin.MODEL) Ui.Selected else Ui.Subtle).border(1.dp, Ui.Border, RoundedCornerShape(50)).padding(horizontal = 10.dp, vertical = 4.dp)) {
                    T(stringResource(when (a.origin) { Origin.MODEL -> R.string.ui_chip_meta; Origin.VISION -> R.string.ui_chip_image; else -> R.string.ui_source }), 12, FontWeight.SemiBold, Ui.Navy)
                }
                T(a.source, 12, color = Ui.Muted, modifier = Modifier.weight(1f))
            }
            a.link?.let { (title, url) ->
                LinkButton("$title · MedlinePlus", size = 12) { if (verifiedMedlinePlusUrl(url) != null) try { uri.openUri(url) } catch (_: Exception) {} }
            }
            a.web.take(3).forEach { (title, url) -> LinkButton(title.take(80), size = 12) { try { uri.openUri(url) } catch (_: Exception) {} } }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlineButton(stringResource(R.string.ui_repeat), Modifier.weight(1f), 46.dp, size = 14) {
                    if (model.speak(a.spoken) { if (phaseProvider() == AingelOrbState.SPEAKING) onStop() }) onSpeak()
                }
                PrimaryButton(stringResource(R.string.ui_stop_reading), Modifier.weight(1f), 46.dp) { model.stopSpeech(); onStop() }
            }
        }
    }
}

@Composable fun ConsentRow(text: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).clickable(role = Role.Checkbox) { onChange(!checked) }.padding(vertical = 4.dp),
        verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Checkbox(checked, null, colors = CheckboxDefaults.colors(checkedColor = Ui.Navy))
        T(text, 13, lineHeight = 1.45f, modifier = Modifier.padding(top = 12.dp).weight(1f))
    }
}


/** The server's example questions for the synthetic demo (the only content it sends to Meta). */
@Composable private fun SyntheticQuestions(questions: List<Pair<String, String>>, busy: Boolean, onPick: (String, String) -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = 6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        questions.forEach { (id, question) ->
            Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(50)).border(1.dp, Ui.Control, RoundedCornerShape(50))
                .clickable(enabled = !busy, role = Role.Button) { onPick(id, question) }.padding(horizontal = 14.dp, vertical = 9.dp)) {
                T(question, 13, FontWeight.Medium, Ui.Navy)
            }
        }
    }
}

@Composable private fun Notice(text: String) {
    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Ui.Subtle).border(1.dp, Ui.Border, RoundedCornerShape(12.dp)).padding(horizontal = 14.dp, vertical = 10.dp)
        .semantics { liveRegion = LiveRegionMode.Polite }) { T(text, 13, color = Ui.Navy, align = TextAlign.Center, modifier = Modifier.fillMaxWidth()) }
}

@Composable private fun Composer(value: String, onChange: (String) -> Unit, placeholder: String, hint: String, busy: Boolean, onSend: () -> Unit, onMic: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp).clip(RoundedCornerShape(50)).border(1.dp, Ui.Control, RoundedCornerShape(50)).background(Color.White)
        .padding(start = 20.dp, end = 6.dp, top = 6.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        BasicTextField(value, { onChange(it.take(1000)) }, Modifier.weight(1f).semantics { contentDescription = placeholder }, singleLine = true, cursorBrush = SolidColor(Ui.Blue),
            textStyle = TextStyle(fontFamily = Ui.Font, fontSize = 15.sp, color = Ui.Text),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send), keyboardActions = KeyboardActions(onSend = { onSend() })) { inner ->
            Box { if (value.isEmpty()) T(placeholder, 15, color = Ui.Placeholder, maxLines = 1); inner() }
        }
        if (value.isNotBlank()) Box(Modifier.size(48.dp).clip(CircleShape).background(Ui.Navy).clickable(role = Role.Button, onClickLabel = stringResource(R.string.send), onClick = onSend),
            contentAlignment = Alignment.Center) { T("→", 20, FontWeight.SemiBold, Color.White) }
        else MicButton(busy, hint, 48.dp, onMic)
    }
}

/** Hand pictogram (translator catalogue icon), drawn as strokes. */
@Composable fun HandGlyph(size: Dp, color: Color) {
    androidx.compose.foundation.Canvas(Modifier.size(size)) {
        val k = this.size.width / 24f
        val path = androidx.compose.ui.graphics.vector.PathParser().parsePathString(
            "M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10.5V4a1.5 1.5 0 0 1 3 0v6.5M14 10.5V5.5a1.5 1.5 0 0 1 3 0V13c0 4-2.5 7-6.5 7S5 17.5 4.5 15l-1-3a1.4 1.4 0 0 1 2.5-1.2L8 13").toPath()
        drawContext.transform.scale(k, k, androidx.compose.ui.geometry.Offset.Zero)
        drawPath(path, color, style = androidx.compose.ui.graphics.drawscope.Stroke(1.8f, cap = androidx.compose.ui.graphics.StrokeCap.Round, join = androidx.compose.ui.graphics.StrokeJoin.Round))
    }
}
