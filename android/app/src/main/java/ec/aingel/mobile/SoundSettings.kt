package ec.aingel.mobile

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * 5b · Voice control settings, kept on this phone. AINGEL answers to the chosen phrase while its home screen is
 * open; it does not identify who speaks (no voice biometrics), and it does not listen in the background.
 */
object VoiceControl {
    private const val PREFS = "aingel-voice"
    val WORDS = listOf("Hola AINGEL", "AINGEL")
    fun enabled(c: Context) = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("enabled", false)
    fun trained(c: Context) = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("trained", false)
    fun word(c: Context) = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("word", WORDS[0])!!
    fun set(c: Context, enabled: Boolean? = null, trained: Boolean? = null, word: String? = null) = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply {
        enabled?.let { putBoolean("enabled", it) }; trained?.let { putBoolean("trained", it) }; word?.let { putString("word", it) }
    }.apply()
    /** «AINGEL» as heard by dictation: aingel, ángel, angel, ainyel… */
    private val NAME = Regex("\\b(a[iy]n?[gjy]el|[áa]ngel|ain ?gel|ainyel|aijel|eingel)\\b", RegexOption.IGNORE_CASE)
    fun heard(text: String, word: String): Boolean {
        val t = java.text.Normalizer.normalize(text.lowercase(), java.text.Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")
        return NAME.containsMatchIn(t) && (word == WORDS[1] || Regex("\\b(hola|ola)\\b").containsMatchIn(t))
    }
    /** What was said after the name, e.g. «¿qué tengo hoy?» in «Hola AINGEL, ¿qué tengo hoy?». */
    fun afterPhrase(text: String): String {
        // Lowercase first: IGNORE_CASE alone does not fold «Á» (lowercasing keeps the same length here).
        val m = Regex("(?<!\\p{L})(a[iy]n?[gjy]el|[áa]ngel|ain ?gel|ainyel|aijel|eingel)(?!\\p{L})").find(text.lowercase()) ?: return ""
        return text.substring(m.range.last + 1).trim().trimStart(',', '.', ' ', ':').trim()
    }
}

private class Pick(val key: String, val label: String, val sub: String, val bluetooth: Boolean)

@Composable fun SoundSettingsScreen(model: AingelViewModel, s: MobileState, onBack: () -> Unit) {
    val context = LocalContext.current
    val spanish = s.profile?.optString("locale", "es-EC") != "en-US"
    LaunchedEffect(spanish) { AudioRoute.spanish = spanish }
    var outputs by remember { mutableStateOf(AudioRoute.outputs(context)) }
    var inputs by remember { mutableStateOf(AudioRoute.inputs(context)) }
    var output by remember { mutableStateOf(AudioRoute.output(context)) }
    var input by remember { mutableStateOf(AudioRoute.input(context)) }
    var vcOn by remember { mutableStateOf(VoiceControl.enabled(context)) }
    var word by remember { mutableStateOf(VoiceControl.word(context)) }
    var enrolling by remember { mutableStateOf(false) }
    var testing by remember { mutableStateOf(false) }
    // Devices appear and disappear as headsets connect.
    DisposableEffect(Unit) {
        val am = context.getSystemService(AudioManager::class.java)
        val callback = object : AudioDeviceCallback() {
            override fun onAudioDevicesAdded(added: Array<out AudioDeviceInfo>?) { outputs = AudioRoute.outputs(context); inputs = AudioRoute.inputs(context) }
            override fun onAudioDevicesRemoved(removed: Array<out AudioDeviceInfo>?) { outputs = AudioRoute.outputs(context); inputs = AudioRoute.inputs(context) }
        }
        am.registerAudioDeviceCallback(callback, null)
        onDispose { am.unregisterAudioDeviceCallback(callback); model.stopSpeech() }
    }
    val mic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> if (ok) enrolling = true }
    BackHandler(!enrolling) { onBack() }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 18.dp, end = 18.dp, top = 6.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(22.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            val back = stringResource(R.string.ui_back)
            Box(Modifier.size(44.dp).clip(CircleShape).clickable(role = Role.Button, onClickLabel = back, onClick = onBack).semantics { contentDescription = back }, contentAlignment = Alignment.Center) { T("‹", 24, color = Ui.Navy) }
            T(stringResource(R.string.ui_s_title), 20, FontWeight.SemiBold, Ui.Navy)
        }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Overline(stringResource(R.string.ui_s_voice))
            RadioList(outputs.map { Pick(it.key, it.label, it.sub, it.bluetooth) }, output, stringResource(R.string.ui_s_voice)) { output = it; AudioRoute.setOutput(context, it) }
            OutlineButton(stringResource(if (testing) R.string.ui_s_testing else R.string.ui_s_test), Modifier.width(170.dp), 44.dp, enabled = !testing, size = 14) {
                testing = model.speak(context.getString(R.string.ui_s_test_phrase)) { testing = false }
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Overline(stringResource(R.string.ui_s_mic))
            RadioList(inputs.map { Pick(it.key, it.label, it.sub, false) }, input, stringResource(R.string.ui_s_mic), mic = true) { input = it; AudioRoute.setInput(context, it) }
            if (inputs.size > 1) T(stringResource(R.string.ui_s_mic_note), 12, color = Ui.Muted, lineHeight = 1.45f)
        }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Overline(stringResource(R.string.ui_s_vc))
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).border(1.dp, Ui.Border, RoundedCornerShape(18.dp))) {
                val title = stringResource(R.string.ui_s_vc_allow)
                Row(Modifier.fillMaxWidth().heightIn(min = 68.dp).toggleable(vcOn, role = Role.Switch) { on ->
                    if (!on) { vcOn = false; VoiceControl.set(context, enabled = false) }
                    else if (VoiceControl.trained(context)) { vcOn = true; VoiceControl.set(context, enabled = true) }
                    else if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) enrolling = true
                    else mic.launch(Manifest.permission.RECORD_AUDIO)
                }.padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        T(title, 15, FontWeight.SemiBold, Ui.Navy)
                        T(stringResource(R.string.ui_s_vc_desc, word), 12, color = Ui.Muted, lineHeight = 1.45f)
                    }
                    val knob by animateFloatAsState(if (vcOn) 1f else 0f, tween(200), label = "knob")
                    Box(Modifier.size(52.dp, 32.dp).clip(RoundedCornerShape(50)).background(if (vcOn) Ui.Navy else Ui.RingPending).padding(3.dp)) {
                        Box(Modifier.size(26.dp).graphicsLayer { translationX = knob * 20.dp.toPx() }.clip(CircleShape).background(Color.White))
                    }
                }
                if (vcOn) {
                    HorizontalDivider(color = Ui.Divider)
                    Column(Modifier.padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        T(stringResource(R.string.ui_s_vc_word), 13, FontWeight.SemiBold, Ui.Navy)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            VoiceControl.WORDS.forEach { w ->
                                val on = word == w
                                Box(Modifier.weight(1f).height(48.dp).clip(RoundedCornerShape(14.dp)).background(if (on) Ui.Navy else Color.White).border(1.5.dp, if (on) Ui.Navy else Ui.Control, RoundedCornerShape(14.dp))
                                    .selectable(on, role = Role.RadioButton) { word = w; VoiceControl.set(context, word = w) }, contentAlignment = Alignment.Center) { T(w, 14, FontWeight.SemiBold, if (on) Color.White else Ui.Navy) }
                            }
                        }
                        LinkButton(stringResource(R.string.ui_s_vc_retrain), size = 13) { enrolling = true }
                        T(stringResource(R.string.ui_s_vc_note), 11, color = Ui.Muted, lineHeight = 1.45f)
                    }
                }
            }
        }
    }
    if (enrolling) WakeEnrollment(model, s, word, onCancel = { enrolling = false }, onDone = {
        enrolling = false; vcOn = true; VoiceControl.set(context, enabled = true, trained = true)
    })
}

@Composable private fun RadioList(items: List<Pick>, selected: String, group: String, mic: Boolean = false, onPick: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).border(1.dp, Ui.Border, RoundedCornerShape(18.dp)).semantics { contentDescription = group; selectableGroup() }) {
        val current = items.firstOrNull { it.key == selected }?.key ?: items.first().key
        items.forEachIndexed { i, d ->
            val on = d.key == current
            if (i > 0) HorizontalDivider(color = Ui.Divider)
            Row(Modifier.fillMaxWidth().heightIn(min = 60.dp).background(if (on) Color(0xFFF3F7FC) else Color.White).selectable(on, role = Role.RadioButton) { onPick(d.key) }
                .padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Box(Modifier.size(36.dp).clip(CircleShape).background(Ui.Selected), contentAlignment = Alignment.Center) {
                    PathIcon(when { mic -> MIC_PATH; d.bluetooth -> HEADPHONES_PATH; else -> PHONE_PATH }, 18.dp, stroke = 1.9f)
                }
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) { T(d.label, 15, FontWeight.SemiBold, Ui.Navy); T(d.sub, 12, color = Ui.Muted) }
                Box(Modifier.size(22.dp).clip(CircleShape).border(2.dp, if (on) Ui.Navy else Ui.RingPending, CircleShape), contentAlignment = Alignment.Center) {
                    if (on) Box(Modifier.size(10.dp).clip(CircleShape).background(Ui.Navy))
                }
            }
        }
    }
}
private const val MIC_PATH = "M9 3h6v11H9zM5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"
private const val HEADPHONES_PATH = "M4 15v-3a8 8 0 0 1 16 0v3M4.5 14h2A1.5 1.5 0 0 1 8 15.5v3A1.5 1.5 0 0 1 6.5 20h-2A1.5 1.5 0 0 1 3 18.5v-3A1.5 1.5 0 0 1 4.5 14zM17.5 14h2a1.5 1.5 0 0 1 1.5 1.5v3a1.5 1.5 0 0 1-1.5 1.5h-2a1.5 1.5 0 0 1-1.5-1.5v-3a1.5 1.5 0 0 1 1.5-1.5z"
private const val PHONE_PATH = "M9.5 2.5h5A2.5 2.5 0 0 1 17 5v14a2.5 2.5 0 0 1-2.5 2.5h-5A2.5 2.5 0 0 1 7 19V5a2.5 2.5 0 0 1 2.5-2.5zM11 18.5h2"

/**
 * First use of voice control: AINGEL comes closer, puts its 3D hands next to its ears («escuchando», an interface
 * gesture, not an LSEC sign) and asks the person to repeat the phrase three times after it.
 */
@Composable private fun WakeEnrollment(model: AingelViewModel, s: MobileState, word: String, onCancel: () -> Unit, onDone: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val voice = remember { VoiceInput(context) }
    val locale = s.profile?.optString("locale", "es-EC") ?: "es-EC"
    val name = s.communication?.optString("preferred_name")?.takeIf { it.isNotBlank() } ?: s.profile?.optString("display_name")?.substringBefore(' ').orEmpty()
    var step by remember { mutableIntStateOf(0) }
    var phase by remember { mutableStateOf("intro") }
    var note by remember { mutableStateOf("") }
    var playKey by remember { mutableIntStateOf(0) }
    var hands3d by remember { mutableStateOf(OrbAnimation.enabled) }
    var live by remember { mutableStateOf(true) }
    DisposableEffect(Unit) { onDispose { live = false; voice.stop(); model.stopSpeech() } }

    fun prompt(repeat: Boolean) {
        if (!live) return
        voice.stop()
        val text = if (step == 0 || repeat) context.getString(R.string.ui_e_prompt_first, name, word) else context.getString(if (step == 1) R.string.ui_e_prompt_again else R.string.ui_e_prompt_last, word)
        phase = "speaking"; playKey++
        val next = {
            if (live) {
                phase = "listening"; playKey++
                voice.start(locale, onPartial = { heard ->
                    if (phase == "listening" && VoiceControl.heard(heard, word)) {
                        voice.stop(); step++
                        if (step >= 3) { phase = "done"; model.speak(context.getString(R.string.ui_e_done_say, name)) }
                        else { phase = "heard"; scope.launch { delay(900); prompt(false) } }
                    }
                }, onResult = { heard ->
                    voice.stop()
                    if (phase == "listening") {
                        if (VoiceControl.heard(heard, word)) { step++; if (step >= 3) { phase = "done"; model.speak(context.getString(R.string.ui_e_done_say, name)) } else { phase = "heard"; scope.launch { delay(900); prompt(false) } } }
                        else { note = context.getString(R.string.ui_e_not_heard, word); scope.launch { delay(600); prompt(false) } }
                    }
                }, onFailure = { _ -> voice.stop(); if (phase == "listening") { note = context.getString(R.string.ui_e_not_heard, word); scope.launch { delay(600); prompt(false) } } })
            }
        }
        if (!model.speak(text) { next() }) next()
    }
    LaunchedEffect(Unit) { delay(1500); prompt(false) }

    Dialog(onDismissRequest = onCancel, properties = DialogProperties(usePlatformDefaultWidth = false, dismissOnClickOutside = false)) {
        Box(Modifier.fillMaxSize().background(Color.White)) {
            val grow by animateFloatAsState(if (phase == "intro") .72f else 1.12f, tween(1400), label = "grow")
            val orbState = when (phase) { "done" -> AingelOrbState.HAPPY; "speaking" -> AingelOrbState.SPEAKING; "listening" -> AingelOrbState.LISTENING; "heard" -> AingelOrbState.THINKING; else -> AingelOrbState.IDLE }
            val r = 80.dp; val w = 360.dp; val h = 430.dp; val cy = 236.dp
            Box(Modifier.align(Alignment.TopCenter).padding(top = 30.dp).size(w, h)) {
                Box(Modifier.offset(x = (w - 260.dp) / 2, y = cy - 130.dp).graphicsLayer { scaleX = grow; scaleY = grow; translationY = (1 - (grow - .72f) / .4f) * 40.dp.toPx() }) {
                    AingelOrb(orbState, 260.dp, audioLevel = if (phase == "listening") voice::level else if (phase == "speaking") model::speechLevel else { { 0f } })
                }
                val seq = if (phase == "intro" || phase == "done") emptyList() else listOf("listen_ear")
                if (hands3d) AingelHands3D(w, h, w / 2, cy, r, seq, playKey, onSign = { i -> if (i < 0 && phase in setOf("speaking", "listening", "heard")) playKey++ }) { hands3d = false }
            }
            Column(Modifier.fillMaxSize().padding(horizontal = 28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Row(Modifier.fillMaxWidth().padding(top = 14.dp), horizontalArrangement = Arrangement.End) {
                    if (phase != "done") LinkButton(stringResource(R.string.cancel), size = 15, color = Ui.Navy) { onCancel() }
                }
                Spacer(Modifier.height(400.dp))
                T(if (phase == "done") stringResource(R.string.ui_e_done_title) else stringResource(R.string.ui_e_say, word), 28, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center, lineHeight = 1.25f,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Assertive })
                Spacer(Modifier.height(14.dp))
                T(when (phase) { "done" -> stringResource(R.string.ui_e_done_sub, word); "speaking" -> stringResource(R.string.ui_e_listen_aingel); "listening" -> stringResource(R.string.ui_e_listening); "heard" -> stringResource(R.string.ui_e_good); else -> "" },
                    14, color = Ui.Muted, align = TextAlign.Center)
                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.semantics { contentDescription = "$step / 3" }) {
                    repeat(3) { i -> Box(Modifier.size(10.dp).clip(CircleShape).background(if (i < step) Ui.Gold else Ui.Control)) }
                }
                Spacer(Modifier.weight(1f))
                if (phase == "done") PrimaryButton(stringResource(R.string.ui_e_ready), Modifier.widthIn(min = 220.dp), 56.dp, fill = false) { onDone() }
                else OutlineButton(stringResource(R.string.ui_e_repeat), Modifier.width(240.dp), 48.dp, size = 14) { note = ""; prompt(true) }
                T(if (phase == "done") stringResource(R.string.ui_e_privacy) else note, 11, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.45f, modifier = Modifier.padding(top = 8.dp, bottom = 34.dp).heightIn(min = 15.dp))
            }
        }
    }
}
