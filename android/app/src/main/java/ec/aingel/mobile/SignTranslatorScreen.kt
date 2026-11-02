package ec.aingel.mobile

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private enum class SignMode(val label: Int) {
    VOICE_TO_SIGN(R.string.ui_signs_mode_v2s), TEXT_TO_SIGN(R.string.ui_signs_mode_t2s), SIGN_TO_VOICE(R.string.ui_signs_mode_s2v), SIGN_TO_TEXT(R.string.ui_signs_mode_s2t);
    val signsOut get() = this == VOICE_TO_SIGN || this == TEXT_TO_SIGN
}
/** Orb expression while a sign plays, as in the catalogue. */
private val EXPRESSION = mapOf("hola" to AingelOrbState.HAPPY, "gracias" to AingelOrbState.HAPPY, "bien" to AingelOrbState.HAPPY, "si" to AingelOrbState.HAPPY,
    "jugar" to AingelOrbState.HAPPY, "hija" to AingelOrbState.HAPPY, "mal" to AingelOrbState.RETRYING, "dolor" to AingelOrbState.RETRYING,
    "dormir" to AingelOrbState.THINKING, "pregunta" to AingelOrbState.CONFUSED)
private val SPEEDS = listOf(HANDS_SPEED, 1f, .75f, .5f)
private val EXAMPLES = listOf("Mañana quiero ir al parque con mi hija", "¿Tienes hambre?", "Me llamo Rosa", "Necesito mi medicina, por favor", "¿Dónde está el baño?")
private const val MIC_PATH = "M9 3h6v11H9zM5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"
private const val SPEAKER_PATH = "M4 9.5v5h3.5L12 18.5v-13L7.5 9.5zM15.5 9a4.5 4.5 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11"
private const val TEXT_PATH = "M5 6h14M12 6v13M9 19h6"
private const val ARROW_PATH = "M5 12h14M13 6l6 6-6 6"
private const val CHEVRON_PATH = "M6 9l6 6 6-6"

@Composable private fun StrokeIcon(d: String, size: Dp, color: Color = Ui.Navy) {
    val path = remember(d) { PathParser().parsePathString(d).toPath() }
    Canvas(Modifier.size(size)) {
        val k = this.size.width / 24f
        drawContext.transform.scale(k, k, Offset.Zero)
        drawPath(path, color, style = Stroke(1.8f, cap = StrokeCap.Round, join = StrokeJoin.Round))
    }
}
@Composable private fun Pictogram(id: String, size: Dp, color: Color = Ui.Navy) = SIGN_PICTOGRAMS[id]?.let { StrokeIcon(it, size, color) }

@Composable private fun ModeIcons(mode: SignMode, tint: Color) = Row(Modifier.width(76.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp, Alignment.CenterHorizontally)) {
    when (mode) {
        SignMode.VOICE_TO_SIGN -> { StrokeIcon(MIC_PATH, 20.dp, tint); StrokeIcon(ARROW_PATH, 14.dp, tint); HandGlyph(20.dp, tint) }
        SignMode.TEXT_TO_SIGN -> { StrokeIcon(TEXT_PATH, 20.dp, tint); StrokeIcon(ARROW_PATH, 14.dp, tint); HandGlyph(20.dp, tint) }
        SignMode.SIGN_TO_VOICE -> { HandGlyph(20.dp, tint); StrokeIcon(ARROW_PATH, 14.dp, tint); StrokeIcon(SPEAKER_PATH, 20.dp, tint) }
        SignMode.SIGN_TO_TEXT -> { HandGlyph(20.dp, tint); StrokeIcon(ARROW_PATH, 14.dp, tint); StrokeIcon(TEXT_PATH, 20.dp, tint) }
    }
}

/**
 * Sign translator: AINGEL signs with its floating hands (signs catalogue v1.5.0, AINGEL design pending LSEC
 * validation). Voice or text → signs uses the catalogue's sentence rule; signs → voice / text uses a pictogram
 * board because no automatic recognition exists yet. The mode is chosen from the "Traducir" button under the orb.
 */
@Composable fun SignTranslatorScreen(model: AingelViewModel, s: MobileState, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val profile = s.profile!!
    val spanish = profile.optString("locale", "es-EC") != "en-US"
    val reduced = profile.optJSONObject("preferences")?.optBoolean("reduced_motion") == true
    val voice = remember { VoiceInput(context) { model.state.value.speechService } }
    var speechAsk by remember { mutableStateOf<(() -> Unit)?>(null) }  // listening that waits for this account's decision
    var mode by remember { mutableStateOf(SignMode.VOICE_TO_SIGN) }
    var menu by remember { mutableStateOf(false) }
    var seq by remember { mutableStateOf<List<String>>(emptyList()) }
    var built by remember { mutableStateOf<List<Pair<String, WordKind>>>(emptyList()) }
    var byMeaning by remember { mutableStateOf(false) }  // signs chosen by Meta from the meaning, not word by word
    var playKey by remember { mutableIntStateOf(0) }
    var current by remember { mutableIntStateOf(-1) }
    var speed by remember { mutableFloatStateOf(HANDS_SPEED) }
    // 3D hands (OpenGL); the 2D signer takes over without OpenGL ES 3 (and in instrumented tests, with animation off).
    var hands3d by remember { mutableStateOf(OrbAnimation.enabled) }
    var heard by remember { mutableStateOf("") }
    var typed by remember { mutableStateOf("") }
    var orb by remember { mutableStateOf(AingelOrbState.IDLE) }
    var listening by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf("") }
    var camera by remember { mutableStateOf(false) }
    val message = remember { mutableStateListOf<String>() }
    var text by remember { mutableStateOf("") }
    var signCapture by remember { mutableStateOf<androidx.camera.core.ImageCapture?>(null) }
    var recognizing by remember { mutableStateOf(false) }
    var recognizedNote by remember { mutableStateOf<String?>(null) }
    var shown by remember { mutableStateOf(false) }
    var moodJob by remember { mutableStateOf<Job?>(null) }
    val str = { id: Int -> context.getString(id) }
    val name = { id: String -> signName(id, spanish) }
    // Board and message labels: capitalised, without the question marks of «¿pregunta?».
    val label = { id: String -> name(id).trim('¿', '?').replaceFirstChar { it.uppercase() } }
    DisposableEffect(Unit) { onDispose { voice.stop(); model.stopSpeech() } }
    BackHandler { voice.stop(); model.stopSpeech(); onBack() }
    LaunchedEffect(mode) {
        if (mode.signsOut) camera = false
        voice.stop(); listening = false; seq = emptyList(); built = emptyList(); byMeaning = false; heard = ""; result = ""; orb = AingelOrbState.IDLE
    }

    fun settle(state: AingelOrbState, ms: Long) { moodJob?.cancel(); orb = state; moodJob = scope.launch { delay(ms); orb = AingelOrbState.IDLE } }
    var blocked by remember { mutableStateOf<SignPlan.Blocked?>(null) }
    LaunchedEffect(Unit) { model.loadSignRegistry() }
    /** Animates [ids] only if all are validated in LSEC, or the person chose illustrations (returns false otherwise). */
    fun sign(ids: List<String>): Boolean {
        moodJob?.cancel(); orb = AingelOrbState.IDLE
        val plan = model.signPlan(ids)
        if (plan is SignPlan.Blocked) { seq = emptyList(); blocked = plan; return false }
        blocked = null; seq = ids; current = -1; playKey++
        return true
    }
    fun onSign(i: Int) {
        current = i
        // Expression of the sign being made; happy once the phrase is signed ("Entendido").
        if (i >= 0) { moodJob?.cancel(); orb = EXPRESSION[seq.getOrNull(i)] ?: AingelOrbState.IDLE } else settle(AingelOrbState.HAPPY, 2200)
    }
    fun interpret(value: String) {
        heard = value; built = emptyList(); byMeaning = false; seq = emptyList(); result = "thinking"
        moodJob?.cancel(); orb = AingelOrbState.THINKING
        scope.launch {
            // By meaning first (Meta); the word-by-word rule when Meta is not available.
            val meant = model.signsFor(value)
            if (heard != value) return@launch  // a newer sentence came in meanwhile
            if (!meant.isNullOrEmpty()) { byMeaning = true; result = if (sign(meant)) "signing" else "not-validated"; return@launch }
            val b = buildSentence(value)
            built = b?.words ?: emptyList()
            if (b == null) { result = "unsupported"; settle(AingelOrbState.CONFUSED, 3500); return@launch }
            result = if (sign(b.seq)) "signing" else "not-validated"
        }
    }
    fun micBlocked() = !mayStart(model.state.value.consent, Capture.MICROPHONE) || voice.needsAcceptance()
    fun listen() {
        if (listening) { if (voice.recognitionAvailable) voice.finish() else { voice.stop(); listening = false; result = "unavailable" }; return }
        if (micBlocked()) return
        seq = emptyList(); built = emptyList(); byMeaning = false; result = ""; heard = ""; model.stopSpeech()
        listening = true; orb = AingelOrbState.LISTENING
        fun begin(tries: Int) {
            if (micBlocked()) { listening = false; orb = AingelOrbState.IDLE; return }
            voice.start(profile.optString("locale", "es-EC"), onPartial = { heard = it }, onResult = { said ->
                voice.stop(); listening = false
                if (said.isBlank()) { result = "no-speech"; settle(AingelOrbState.CONFUSED, 3000) } else interpret(said)
            }, onFailure = { error ->
                voice.stop()
                // The phone's own recogniser lacked the language: the system's one needs this account's acceptance first.
                if (error == android.speech.SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS && voice.needsAcceptance()) {
                    listening = false; orb = AingelOrbState.IDLE; speechAsk = { listen() }
                }
                // Right after leaving home the microphone may still be closing: try again before giving up.
                else if (transientRecognizerError(error) && tries < 3 && listening) scope.launch { delay(600); if (listening) begin(tries + 1) }
                else {
                    listening = false
                    result = if (error == android.speech.SpeechRecognizer.ERROR_NO_MATCH || error == android.speech.SpeechRecognizer.ERROR_SPEECH_TIMEOUT) "no-speech" else "unavailable"
                    settle(AingelOrbState.CONFUSED, 3000)
                }
            })
        }
        begin(0)
    }
    fun withSpeech(start: () -> Unit) { if (voice.needsAcceptance()) speechAsk = start else start() }
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> if (ok) withSpeech { listen() } else result = "mic-denied" }
    val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> camera = ok; if (!ok) result = "camera-denied" }
    // The person's own grants (care.consent), separate from Android's permission: checked fresh before opening, reread
    // while open; a refusal closes the camera or microphone here, and opening them again needs a new grant.
    RefreshConsentWhile(model, listening || camera)
    LaunchedEffect(s.consent, s.speechService) {
        if (camera && !mayStart(s.consent, Capture.CAMERA)) { camera = false; result = "camera-stopped" }
        if (listening && micBlocked()) { voice.stop(); listening = false; orb = AingelOrbState.IDLE; result = "mic-stopped" }
    }
    fun say(value: String) { if (value.isNotBlank() && model.speak(value) { orb = AingelOrbState.IDLE }) orb = AingelOrbState.SPEAKING }
    fun add(id: String) { message.add(id); sign(listOf(id)); text = message.joinToString(" ") { label(it) } }
    /** Experimental: AINGEL tries to recognize the signs made in front of the camera and adds them to the message. */
    fun recognize() {
        val use = signCapture ?: return
        recognizing = true; recognizedNote = null; orb = AingelOrbState.THINKING
        scope.launch {
            recognizedNote = try {
                val result = model.recognizeSigns(use.signFrames(context))
                val ids = recognizedSigns(result)
                when {
                    result.optString("mode") == "mock" -> str(R.string.ui_signs_recognize_mock)
                    ids.isEmpty() -> str(R.string.ui_signs_recognize_none)
                    else -> { message.addAll(ids); text = message.joinToString(" ") { label(it) }; str(R.string.ui_signs_recognize_done) }
                }
            } catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
            catch (e: ApiFailure) {
                if (stopsCapture(e.code)) { camera = false; str(R.string.capture_camera_stopped) } else str(R.string.ui_signs_recognize_failed)
            } catch (_: Exception) { str(R.string.ui_signs_recognize_failed) }
            recognizing = false; orb = AingelOrbState.IDLE
        }
    }

    val status = when {
        listening -> str(R.string.ui_st_listening)
        orb == AingelOrbState.SPEAKING -> str(R.string.ui_signs_saying)
        result == "mic-denied" -> str(R.string.ui_mic_denied)
        result == "camera-denied" -> str(R.string.ui_camera_denied)
        result == "mic-consent" -> str(R.string.capture_microphone_not_authorized)
        result == "camera-consent" -> str(R.string.capture_camera_not_authorized)
        result == "mic-stopped" -> str(R.string.capture_microphone_stopped)
        result == "camera-stopped" -> str(R.string.capture_camera_stopped)
        mode.signsOut && result == "not-validated" -> blocked?.takeIf { it.partial }?.let { context.getString(R.string.ui_signs_partial, it.validated, it.total) }
            ?: str(R.string.ui_signs_unavailable_lsec)
        mode.signsOut -> str(when (result) {
            "signing" -> if (current >= 0) R.string.ui_signs_signing else R.string.ui_signs_done
            "thinking" -> R.string.ui_signs_thinking; "unsupported" -> R.string.ui_signs_none_found; "no-speech" -> R.string.ui_signs_no_speech; "unavailable" -> R.string.ui_signs_voice_unavailable
            else -> if (mode == SignMode.VOICE_TO_SIGN) R.string.ui_signs_tap_mic else R.string.ui_signs_type_prompt })
        camera -> str(R.string.ui_signs_camera_open)
        else -> str(R.string.ui_signs_build)
    }
    // Stage proportions from the catalogue (orb 300 px, r 87 → r ≈ 0.29 × orb; hands span ≈ 6 r).
    val r = 44.dp; val orbSize = r / 0.29f; val stageW = r * 6; val stageH = r * 5.3f; val cy = r * 2

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 22.dp, end = 22.dp, top = 6.dp, bottom = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        LinkButton("‹ " + stringResource(R.string.ui_home), color = Ui.Muted) { voice.stop(); model.stopSpeech(); onBack() }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.size(44.dp).background(Ui.Selected, RoundedCornerShape(50)), contentAlignment = Alignment.Center) { HandGlyph(26.dp, Ui.Navy) }
            T(stringResource(R.string.ui_signs_title), 24, FontWeight.SemiBold, Ui.Navy)
        }
        // Stage: orb + hands, status, signs and controls.
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Color.White).border(1.dp, Ui.Border, RoundedCornerShape(24.dp)).padding(vertical = 14.dp, horizontal = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Box(Modifier.size(stageW, stageH)) {
                Box(Modifier.offset(x = (stageW - orbSize) / 2, y = cy - orbSize / 2)) {
                    OrbWithCamera(if (listening) AingelOrbState.LISTENING else orb, orbSize, reduced, vision = camera && !mode.signsOut, front = true,
                        level = if (listening) voice::level else if (orb == AingelOrbState.SPEAKING) model::speechLevel else { { 0f } },
                        onCapture = { signCapture = it }, onCameraError = { camera = false; result = "camera-denied" })
                }
                if (hands3d) AingelHands3D(stageW, stageH, stageW / 2, cy, r, seq, playKey, speed, reduced, ::onSign) { hands3d = false }
                else AingelSigner(stageW, stageH, stageW / 2, cy, r, seq, playKey, speed, reduced, ::onSign)
            }
            T(status, 17, FontWeight.Medium, Ui.Navy, align = TextAlign.Center, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            // On the board the controls stay put, so tapping a sign never moves the board.
            if (seq.isNotEmpty() || !mode.signsOut) {
                if (mode.signsOut) FlowRowCompat(seq.mapIndexed { i, id -> i to id }, gap = 6.dp) { (i, id) ->
                    val on = i == current
                    Box(Modifier.clip(RoundedCornerShape(50)).background(if (on) Ui.Navy else Color.White).border(1.5.dp, if (on) Ui.Navy else Ui.Control, RoundedCornerShape(50))
                        .padding(horizontal = 11.dp, vertical = 6.dp)) { T(name(id), 13, FontWeight.SemiBold, if (on) Color.White else Ui.Navy) }
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val repeat = stringResource(R.string.ui_repeat)
                    Box(Modifier.size(44.dp).clip(CircleShape).border(1.5.dp, Ui.Control, CircleShape).clickable(role = Role.Button, onClickLabel = repeat, enabled = seq.isNotEmpty()) { sign(seq) }
                        .semantics { contentDescription = repeat }, contentAlignment = Alignment.Center) { T("↻", 18, FontWeight.SemiBold, Ui.Navy) }
                    val speedLabel = stringResource(R.string.ui_signs_speed)
                    Box(Modifier.heightIn(min = 44.dp).widthIn(min = 56.dp).clip(RoundedCornerShape(12.dp)).border(1.5.dp, Ui.Control, RoundedCornerShape(12.dp))
                        .clickable(role = Role.Button, onClickLabel = speedLabel) { speed = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.size] }
                        .semantics { contentDescription = "$speedLabel $speed×" }, contentAlignment = Alignment.Center) {
                        T((if (speed == 1f) "1" else speed.toString().removePrefix("0")) + "×", 13, FontWeight.SemiBold, Ui.Navy)
                    }
                }
                val signState by model.state.collectAsState()
                DesignBadge(signState.illustrativeSigns, signState.validatedSigns.size)
                IllustrativeSwitch(model, signState.illustrativeSigns)
                if (!mode.signsOut && blocked != null) T(stringResource(R.string.ui_signs_board_unvalidated), 13, color = Ui.Muted, align = TextAlign.Center)
            }
        }
        // "Traducir" button with AINGEL's eyes: unfolds the four modes downwards.
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            val translate = stringResource(R.string.ui_signs_translate)
            Row(Modifier.fillMaxWidth().heightIn(min = 64.dp).clip(RoundedCornerShape(50)).background(Color.White).border(1.5.dp, Ui.Navy, RoundedCornerShape(50))
                .clickable(role = Role.Button, onClickLabel = translate) { menu = !menu }.semantics { stateDescription = if (menu) "expanded" else "collapsed" }
                .padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Box(Modifier.size(40.dp).clip(CircleShape).background(Ui.Navy), contentAlignment = Alignment.Center) {
                    Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) { repeat(2) { Box(Modifier.size(6.dp, 14.dp).background(if (menu) Ui.Gold else Color.White, RoundedCornerShape(3.dp))) } }
                }
                Column(Modifier.weight(1f)) {
                    T(translate.uppercase(), 11, FontWeight.SemiBold, Ui.Muted, letterSpacing = 1.3.sp)
                    T(stringResource(mode.label), 16, FontWeight.SemiBold, Ui.Navy, maxLines = 1)
                }
                Box(Modifier.rotate(if (menu) 180f else 0f)) { StrokeIcon(CHEVRON_PATH, 22.dp) }
            }
            AnimatedVisibility(menu, enter = if (reduced) fadeIn() else expandVertically() + fadeIn(), exit = if (reduced) fadeOut() else shrinkVertically() + fadeOut()) {
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Color.White).border(1.dp, Ui.Border, RoundedCornerShape(22.dp)).padding(8.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    SignMode.entries.forEach { m ->
                        val on = mode == m; val tint = if (on) Color.White else Ui.Navy
                        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).clip(RoundedCornerShape(16.dp)).background(if (on) Ui.Navy else Color.Transparent)
                            .selectable(on, role = Role.RadioButton) { mode = m; menu = false }.padding(horizontal = 10.dp),
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            ModeIcons(m, tint); T(stringResource(m.label), 15, FontWeight.SemiBold, tint)
                        }
                    }
                }
            }
        }

        when (mode) {
            SignMode.VOICE_TO_SIGN -> Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                MicButton(listening, str(if (listening) R.string.ui_hint_finish else R.string.ui_hint_talk)) {
                    if (listening) listen()
                    else scope.launch {
                        if (!model.captureAllowed(Capture.MICROPHONE)) { result = "mic-consent"; return@launch }
                        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) withSpeech { listen() }
                        else micPermission.launch(Manifest.permission.RECORD_AUDIO)
                    }
                }
                if (listening) T(stringResource(R.string.ui_mic_private), 11, color = Ui.Muted)
                if (heard.isNotBlank()) T(stringResource(R.string.ui_signs_heard) + ": " + heard, 14, color = Ui.Muted, align = TextAlign.Center)
            }
            SignMode.TEXT_TO_SIGN -> Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FieldInput(stringResource(R.string.ui_signs_type), typed, { typed = it.take(200) }, Modifier.weight(1f), height = 48.dp, fontSize = 15)
                    PrimaryButton(stringResource(R.string.ui_signs_sign), Modifier.widthIn(min = 96.dp), 48.dp, enabled = typed.isNotBlank(), fill = false) { interpret(typed.trim()) }
                }
                if (spanish) FlowRowCompat(EXAMPLES, gap = 6.dp) { x ->
                    Box(Modifier.clip(RoundedCornerShape(50)).background(Ui.Subtle).border(1.dp, Ui.Border, RoundedCornerShape(50))
                        .clickable(role = Role.Button) { typed = x; interpret(x) }.padding(horizontal = 12.dp, vertical = 8.dp)) { T(x, 12, FontWeight.Medium, Ui.Navy) }
                }
            }
            else -> Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (camera) PrimaryButton(stringResource(R.string.ui_signs_close_camera), height = 46.dp) { camera = false }
                else OutlineButton(stringResource(R.string.ui_signs_open_camera), height = 46.dp, size = 14) {
                    scope.launch {
                        if (!model.captureAllowed(Capture.CAMERA)) { result = "camera-consent"; return@launch }
                        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) camera = true
                        else cameraPermission.launch(Manifest.permission.CAMERA)
                    }
                }
                if (camera) {
                    PrimaryButton(stringResource(if (recognizing) R.string.ui_signs_recognizing else R.string.ui_signs_recognize), height = 46.dp,
                        enabled = signCapture != null && !recognizing) { recognize() }
                    T(stringResource(R.string.ui_signs_camera_private), 11, color = Ui.Muted, align = TextAlign.Center)
                }
                recognizedNote?.let { T(it, 12, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.4f, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
                T(stringResource(R.string.ui_signs_no_recognizer), 12, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.45f)
                SIGN_BOARD.chunked(4).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        row.forEach { id ->
                            Column(Modifier.weight(1f).heightIn(min = 78.dp).clip(RoundedCornerShape(16.dp)).border(1.5.dp, Ui.Border, RoundedCornerShape(16.dp)).background(Color.White)
                                .clickable(role = Role.Button, onClickLabel = label(id)) { add(id) }.padding(vertical = 10.dp, horizontal = 2.dp),
                                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp, Alignment.CenterVertically)) {
                                Pictogram(id, 26.dp); T(label(id), 11, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center, maxLines = 1)
                            }
                        }
                        repeat(4 - row.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
                if (message.isNotEmpty()) {
                    FlowRowCompat(message.mapIndexed { i, id -> i to id }) { (i, id) ->
                        Row(Modifier.clip(RoundedCornerShape(50)).border(1.5.dp, Ui.Border, RoundedCornerShape(50)).clickable(role = Role.Button, onClickLabel = context.getString(R.string.delete)) {
                            message.removeAt(i); text = message.joinToString(" ") { label(it) }
                        }.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Pictogram(id, 18.dp); T(label(id) + " ×", 13, FontWeight.SemiBold, Ui.Navy)
                        }
                    }
                    LinkButton("↻ " + stringResource(R.string.ui_signs_see_message), size = 13) { sign(message.toList()) }
                    LinkButton(stringResource(R.string.ui_conv_clear), size = 13, color = Ui.Muted) { message.clear(); text = "" }
                }
                if (mode == SignMode.SIGN_TO_VOICE) Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    PrimaryButton(stringResource(R.string.ui_signs_say), Modifier.weight(1f), 48.dp, enabled = text.isNotBlank()) { say(text) }
                    if (orb == AingelOrbState.SPEAKING) OutlineButton(stringResource(R.string.stop), Modifier.weight(1f), 48.dp, size = 14) { model.stopSpeech(); orb = AingelOrbState.IDLE }
                }
                if (mode == SignMode.SIGN_TO_TEXT) {
                    T(stringResource(R.string.ui_signs_text_label), 13, FontWeight.SemiBold, Ui.Navy, modifier = Modifier.fillMaxWidth())
                    BasicTextField(text, { text = it.take(300) }, Modifier.fillMaxWidth().heightIn(min = 90.dp).border(1.5.dp, Ui.Control, RoundedCornerShape(14.dp)).padding(14.dp)
                        .semantics { contentDescription = context.getString(R.string.ui_signs_text_label) }, textStyle = TextStyle(fontFamily = Ui.Font, fontSize = 16.sp, color = Ui.Text), cursorBrush = SolidColor(Ui.Blue))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        PrimaryButton(stringResource(R.string.ui_signs_show_large), Modifier.weight(1f), 48.dp, enabled = text.isNotBlank()) { shown = true }
                        OutlineButton(stringResource(R.string.read), Modifier.weight(1f), 48.dp, enabled = text.isNotBlank(), size = 14) { say(text) }
                    }
                }
            }
        }
        if (mode.signsOut && byMeaning && seq.isNotEmpty()) T(stringResource(R.string.ui_signs_by_meaning), 11, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.5f, modifier = Modifier.fillMaxWidth())
        if (mode.signsOut && built.isNotEmpty()) Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
            FlowRowCompat(built, gap = 6.dp) { (w, k) ->
                val (bg, fg) = when (k) { WordKind.SIGN -> Ui.Selected to Ui.Navy; WordKind.SPELL -> Color(0xFFFDF3DF) to Color(0xFF7A5410); WordKind.SKIP -> Ui.Subtle to Color(0xFF9AA6BA) }
                Box(Modifier.clip(RoundedCornerShape(8.dp)).background(bg).padding(horizontal = 10.dp, vertical = 5.dp)) {
                    androidx.compose.material3.Text(w, fontFamily = Ui.Font, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = fg,
                        textDecoration = if (k == WordKind.SKIP) TextDecoration.LineThrough else null)
                }
            }
            T(stringResource(R.string.ui_signs_legend), 11, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.5f)
        }
        T(stringResource(R.string.ui_signs_disclaimer), 11, color = Ui.Muted, lineHeight = 1.5f)
    }
    speechAsk?.let { pending ->
        SpeechServiceNotice(model, onAccepted = { speechAsk = null; pending() }, onType = { speechAsk = null; mode = SignMode.TEXT_TO_SIGN })
    }
    if (shown) Dialog(onDismissRequest = { shown = false }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Box(Modifier.fillMaxSize().background(Color.White).clickable(onClickLabel = context.getString(R.string.close)) { shown = false }.padding(24.dp), contentAlignment = Alignment.Center) {
            T(text, 40, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center, lineHeight = 1.25f)
        }
    }
}

/** Simple centred wrapping row of chips (avoids the experimental FlowRow API). */
@Composable private fun <T> FlowRowCompat(items: List<T>, gap: Dp = 8.dp, item: @Composable (T) -> Unit) {
    androidx.compose.ui.layout.Layout(content = { items.forEach { item(it) } }, modifier = Modifier.fillMaxWidth()) { measurables, constraints ->
        val g = gap.roundToPx()
        val placeables = measurables.map { it.measure(constraints.copy(minWidth = 0, minHeight = 0)) }
        val rows = mutableListOf(mutableListOf<androidx.compose.ui.layout.Placeable>())
        var width = 0
        placeables.forEach { p ->
            if (width > 0 && width + g + p.width > constraints.maxWidth) { rows.add(mutableListOf()); width = 0 }
            width += (if (width > 0) g else 0) + p.width; rows.last().add(p)
        }
        val height = rows.sumOf { r -> r.maxOfOrNull { it.height } ?: 0 } + g * (rows.size - 1)
        layout(constraints.maxWidth, height) {
            var y = 0
            rows.forEach { r ->
                val rowWidth = r.sumOf { it.width } + g * (r.size - 1); var x = (constraints.maxWidth - rowWidth) / 2
                r.forEach { it.placeRelative(x, y); x += it.width + g }
                y += (r.maxOfOrNull { it.height } ?: 0) + g
            }
        }
    }
}
