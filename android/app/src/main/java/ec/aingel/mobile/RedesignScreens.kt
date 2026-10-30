package ec.aingel.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.speech.SpeechRecognizer
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

private val Gutter = Modifier.padding(horizontal = 22.dp)

/* ─────────── 1e · 2d · 2e  Access ─────────── */

@Composable fun AccessFlow(model: AingelViewModel, s: MobileState) {
    var mode by rememberSaveable { mutableStateOf("welcome") }
    BackHandler(mode != "welcome" && !s.mfaRequired) { mode = "welcome" }
    when {
        s.mfaRequired -> MfaChallenge(model, s)
        mode == "login" -> LoginForm(model, s, { mode = "welcome" }) { mode = "register" }
        mode == "register" -> RegisterForm(model, s) { mode = "welcome" }
        else -> Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 28.dp, end = 28.dp, top = 40.dp, bottom = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally) {
            AingelOrb(AingelOrbState.IDLE, 232.dp)
            Spacer(Modifier.height(22.dp))
            T("AINGEL", 26, FontWeight.Medium, Ui.Navy, letterSpacing = 8.8.sp, modifier = Modifier.padding(start = 8.dp))
            Spacer(Modifier.height(12.dp))
            Box(Modifier.width(34.dp).height(3.dp).background(Ui.Gold, RoundedCornerShape(2.dp)))
            Spacer(Modifier.height(22.dp))
            T(stringResource(R.string.brand_tagline), 19, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center)
            Spacer(Modifier.height(10.dp))
            T(stringResource(R.string.ui_intro), 14, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.55f)
            Spacer(Modifier.weight(1f).heightIn(min = 28.dp))
            ErrorText(s)
            PrimaryButton(stringResource(R.string.sign_in)) { model.clearError(); mode = "login" }
            Spacer(Modifier.height(10.dp))
            OutlineButton(stringResource(R.string.register)) { model.clearError(); mode = "register" }
            Spacer(Modifier.height(18.dp))
            T(stringResource(R.string.ui_disclaimer), 11, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.5f)
        }
    }
}

@Composable private fun BackChevron(onBack: () -> Unit) {
    Box(Modifier.offset(x = (-10).dp).size(44.dp).clip(CircleShape).clickable(role = Role.Button, onClickLabel = stringResource(R.string.back), onClick = onBack),
        contentAlignment = Alignment.Center) { T("‹", 26, color = Ui.Navy) }
}

@Composable private fun ErrorText(s: MobileState) {
    s.error?.let { T(stringResource(errorMessage(it)), 13, color = Color(0xFF8B2630), modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp).semantics { liveRegion = LiveRegionMode.Polite }) }
}

@Composable private fun LoginForm(model: AingelViewModel, s: MobileState, onBack: () -> Unit, onRegister: () -> Unit) {
    var username by rememberSaveable { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    var forgot by remember { mutableStateOf(false) }; var server by remember { mutableStateOf(false) }; var backend by remember { mutableStateOf(model.api.base) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 24.dp, end = 24.dp, top = 14.dp, bottom = 18.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        BackChevron(onBack)
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            T(stringResource(R.string.sign_in), 26, FontWeight.SemiBold, Ui.Navy)
            T(stringResource(R.string.ui_login_sub), 14, color = Ui.Muted)
        }
        FieldInput(stringResource(R.string.ui_username), username, { username = it })
        FieldInput(stringResource(R.string.password), password, { password = it }, secret = true)
        LinkButton(stringResource(R.string.ui_forgot), Modifier.align(Alignment.End)) { forgot = !forgot }
        if (forgot) T(stringResource(R.string.ui_forgot_note), 12, color = Ui.Muted)
        Spacer(Modifier.weight(1f))
        ErrorText(s)
        PrimaryButton(if (s.busy) stringResource(R.string.loading) else stringResource(R.string.ui_enter), enabled = !s.busy && username.isNotBlank() && password.isNotEmpty()) {
            model.login(username.trim(), password); password = ""
        }
        LinkButton(stringResource(R.string.ui_no_account), Modifier.fillMaxWidth().height(50.dp), size = 14, onClick = onRegister)
        LinkButton(stringResource(R.string.backend), Modifier.align(Alignment.CenterHorizontally), size = 11, color = Ui.Muted) { server = !server }
        if (server) {
            FieldInput(stringResource(R.string.backend), backend, { backend = it }, fontSize = 14)
            OutlineButton(stringResource(R.string.save), enabled = !s.busy) { model.configureBackend(backend) }
        }
    }
}

@Composable private fun RegisterForm(model: AingelViewModel, s: MobileState, onBack: () -> Unit) {
    var name by rememberSaveable { mutableStateOf("") }; var username by rememberSaveable { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    var who by rememberSaveable { mutableStateOf("other") }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 24.dp, end = 24.dp, top = 14.dp, bottom = 18.dp), verticalArrangement = Arrangement.spacedBy(13.dp)) {
        BackChevron(onBack)
        T(stringResource(R.string.register), 26, FontWeight.SemiBold, Ui.Navy)
        FieldInput(stringResource(R.string.ui_your_name), name, { name = it.take(100) }, height = 50.dp, fontSize = 15)
        FieldInput(stringResource(R.string.ui_username), username, { username = it.take(150) }, height = 50.dp, fontSize = 15)
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            FieldInput(stringResource(R.string.password), password, { password = it.take(256) }, secret = true, height = 50.dp, fontSize = 15)
            T(stringResource(R.string.ui_password_min), 11, color = Ui.Muted)
        }
        T(stringResource(R.string.ui_who_for), 13, FontWeight.SemiBold, Ui.Navy, modifier = Modifier.padding(top = 2.dp))
        RadioCard(stringResource(R.string.ui_for_me), who == "me") { who = "me" }
        RadioCard(stringResource(R.string.ui_for_other), who == "other") { who = "other" }
        Spacer(Modifier.weight(1f))
        ErrorText(s)
        PrimaryButton(if (s.busy) stringResource(R.string.loading) else stringResource(R.string.setup_continue), enabled = !s.busy && username.isNotBlank() && password.length >= 10) {
            model.register(username.trim(), password, who, name); password = ""
        }
    }
}

@Composable private fun MfaChallenge(model: AingelViewModel, s: MobileState) {
    var code by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        BackChevron { model.logout() }
        T(stringResource(R.string.verify), 26, FontWeight.SemiBold, Ui.Navy)
        FieldInput(stringResource(R.string.code), code, { code = it.take(32) })
        Spacer(Modifier.weight(1f)); ErrorText(s)
        PrimaryButton(stringResource(R.string.verify), enabled = !s.busy && code.isNotBlank()) { model.verifyMfa(code); code = "" }
    }
}

/* ─────────── 2f · 2g · 2h  Setup ─────────── */

private data class Cond(val id: String, val title: Int, val levels: Int, val captions: Int)
private val CONDITIONS = listOf(Cond("vision", R.string.ui_cond_vision, R.array.ui_levels_vision, R.array.ui_full_vision),
    Cond("hearing", R.string.ui_cond_hearing, R.array.ui_levels_hearing, R.array.ui_full_hearing),
    Cond("autism", R.string.ui_cond_autism, R.array.ui_levels_autism, R.array.ui_full_autism),
    Cond("dementia", R.string.ui_cond_dementia, R.array.ui_levels_dementia, R.array.ui_full_dementia))

private val PRESET_LABELS = mapOf("visual_assistance" to R.string.ui_p_visual, "voice_output" to R.string.ui_p_voice_output, "voice_first" to R.string.ui_p_voice_first,
    "large_text" to R.string.ui_p_large, "high_contrast" to R.string.ui_p_contrast, "hearing_assistance" to R.string.ui_p_hearing, "text_first" to R.string.ui_p_text_first,
    "haptic_alerts" to R.string.ui_p_haptic, "sign_language" to R.string.ui_p_signs, "no_reading" to R.string.ui_p_no_reading, "easy_read" to R.string.ui_p_easy_read,
    "simple_instructions" to R.string.ui_p_simple, "reduced_motion" to R.string.ui_p_motion, "one_step" to R.string.ui_p_one_step, "routine_preview" to R.string.ui_p_preview,
    "memory_assistance" to R.string.ui_p_memory, "speech_pace_slow" to R.string.ui_p_slow, "can_configure" to R.string.ui_p_circle, "simplified_home" to R.string.ui_p_simple_home,
    "default" to R.string.ui_p_default)

@Composable fun SetupFlow(model: AingelViewModel, s: MobileState) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val (who, ownName) = model.signup
    var step by rememberSaveable { mutableIntStateOf(1) }
    var name by rememberSaveable { mutableStateOf(if (who == "me") ownName else "") }
    var preferred by rememberSaveable { mutableStateOf(if (who == "me") ownName.substringBefore(' ') else "") }
    var relationship by rememberSaveable { mutableStateOf("") }
    var locale by rememberSaveable { mutableStateOf("es-EC") }
    var timezone by rememberSaveable { mutableStateOf("America/Guayaquil") }
    val levels = remember { mutableStateMapOf<String, Int>() }
    val enabled = remember { mutableStateMapOf<String, Boolean>() }
    var signs by rememberSaveable { mutableStateOf(false) }
    var signLanguage by rememberSaveable { mutableStateOf("lsec") }
    var reads by rememberSaveable { mutableStateOf("yes") }
    var addressing by rememberSaveable { mutableStateOf("usted") }
    // Authorizations are given here, once (as on the web); the app never asks per action (backend care.consent).
    var allowCamera by rememberSaveable { mutableStateOf(false) }
    var allowMic by rememberSaveable { mutableStateOf(false) }
    var allowMeta by rememberSaveable { mutableStateOf(false) }
    var createdId by rememberSaveable { mutableStateOf<String?>(null) }
    var configured by rememberSaveable { mutableStateOf(false) }
    var act by remember { mutableStateOf(AingelOrbState.IDLE) }
    var working by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    var invite by remember { mutableStateOf(false) }
    BackHandler(step > 1 && !configured) { step-- }
    val answers = SetupAnswers(
        vision = levels["vision"].takeIf { enabled["vision"] == true }, hearing = levels["hearing"].takeIf { enabled["hearing"] == true },
        autism = levels["autism"].takeIf { enabled["autism"] == true }, dementia = levels["dementia"].takeIf { enabled["dementia"] == true },
        signs = signs, signLanguage = signLanguage, reads = reads, addressing = addressing)
    val keys = presetKeys(answers)
    val count = CONDITIONS.count { enabled[it.id] == true }
    val shown = preferred.trim().ifBlank { name.trim().substringBefore(' ') }.ifBlank { stringResource(R.string.ui_the_person) }
    val validZone = try { java.time.ZoneId.of(timezone.trim()); true } catch (_: Exception) { false }
    val reduced = enabled["autism"] == true

    fun activate() {
        working = true; failed = false
        scope.launch {
            try {
                val condLines = CONDITIONS.filter { enabled[it.id] == true }.joinToString("; ") {
                    context.getString(it.title) + ": " + context.resources.getStringArray(it.captions)[levels[it.id] ?: 0]
                }
                val pending = keys.filterNot { it in SUPPORTED_PRESETS }.joinToString("; ") { context.getString(PRESET_LABELS.getValue(it)) + " ($it)" }
                val notes = listOfNotNull(
                    condLines.takeIf { it.isNotBlank() }?.let { context.getString(R.string.ui_notes_conditions, it) },
                    relationship.trim().takeIf { who == "other" && it.isNotBlank() }?.let { context.getString(R.string.ui_notes_relationship, it) },
                    pending.takeIf { it.isNotBlank() }?.let { context.getString(R.string.ui_notes_pending, it) },
                    context.getString(R.string.ui_not_diagnosis)).joinToString("\n")
                val profile = JSONObject().put("display_name", name.trim()).put("locale", locale).put("timezone", timezone.trim())
                    .put("support_notes", notes).put("preferences", presetPreferences(answers))
                    .put("consents", JSONObject().put("camera", allowCamera).put("microphone", allowMic).put("meta_data", allowMeta))
                createdId = model.createConfiguredProfile(profile, answers, preferred, createdId)
                configured = true
                delay(2300); act = AingelOrbState.HAPPY
                delay(3100); act = AingelOrbState.IDLE
            } catch (_: Exception) { failed = true } finally { working = false }
        }
    }

    Column(Modifier.fillMaxSize()) {
        Column(Gutter.padding(top = 10.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                T(stringResource(R.string.setup_step, step, 4), 12, FontWeight.SemiBold, Ui.Muted)
                if (step == 2) T(stringResource(R.string.ui_selected_count, count), 12, FontWeight.SemiBold, Ui.Navy)
            }
            ProgressLine(step / 4f)
        }
        if (step == 4) {
            Column(Modifier.weight(1f).fillMaxWidth().padding(start = 22.dp, end = 22.dp, top = 28.dp, bottom = 16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                AingelOrb(act, 270.dp, configured = configured, reducedMotion = reduced)
                Spacer(Modifier.height(14.dp))
                T(stringResource(if (configured) R.string.ui_ready_title else R.string.ui_activate_title), 22, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                Spacer(Modifier.height(8.dp))
                T(if (configured) stringResource(when (addressing) { "usted" -> R.string.ui_greet_usted; "tu" -> R.string.ui_greet_tu; else -> R.string.ui_greet_neutral }, shown)
                  else stringResource(R.string.ui_activate_text, shown), 14, color = Ui.Muted, align = TextAlign.Center, lineHeight = 1.55f)
                if (failed) T(stringResource(R.string.failed), 13, color = Color(0xFF8B2630), align = TextAlign.Center, modifier = Modifier.padding(top = 10.dp))
                Spacer(Modifier.weight(1f))
                if (configured) PrimaryButton(stringResource(R.string.ui_home), height = 56.dp, enabled = !s.busy) { model.finishSetup() }
                else PrimaryButton(if (working) stringResource(R.string.loading) else stringResource(R.string.ui_activate), height = 56.dp, enabled = !working) { activate() }
                if (!configured) LinkButton(stringResource(R.string.back), Modifier.padding(top = 6.dp), color = Ui.Muted) { step = 3 }
            }
            return@Column
        }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 22.dp, end = 22.dp, top = 16.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            when (step) {
                1 -> {
                    Overline(stringResource(if (who == "me") R.string.ui_your_data else R.string.ui_person_you_care))
                    T(stringResource(R.string.ui_who_for), 22, FontWeight.SemiBold, Ui.Navy, lineHeight = 1.25f)
                    T(stringResource(R.string.ui_person_intro), 13, color = Ui.Muted)
                    FieldInput(stringResource(R.string.ui_person_name), name, { name = it.take(100) }, height = 52.dp, fontSize = 15)
                    FieldInput(stringResource(R.string.preferred_name), preferred, { preferred = it.take(100) }, height = 52.dp, fontSize = 15)
                    if (who == "other") FieldInput(stringResource(R.string.relationship), relationship, { relationship = it.take(60) }, height = 52.dp, fontSize = 15)
                    T(stringResource(R.string.ui_language), 13, FontWeight.SemiBold, Ui.Navy)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Choice(stringResource(R.string.setup_spanish), locale == "es-EC", Modifier.weight(1f)) { locale = "es-EC" }
                        Choice(stringResource(R.string.setup_english), locale == "en-US", Modifier.weight(1f)) { locale = "en-US" }
                    }
                    FieldInput(stringResource(R.string.setup_timezone), timezone, { timezone = it.take(80) }, height = 52.dp, fontSize = 15)
                    if (!validZone) T(stringResource(R.string.setup_timezone_error), 12, color = Color(0xFF8B2630))
                    LinkButton(stringResource(R.string.ui_have_invite)) { invite = !invite }
                    if (invite) InviteBox(model, s)
                }
                2 -> {
                    T(stringResource(R.string.ui_support_title, shown), 22, FontWeight.SemiBold, Ui.Navy, lineHeight = 1.25f)
                    T(stringResource(R.string.ui_support_sub), 13, color = Ui.Muted)
                    CONDITIONS.forEach { c ->
                        val on = enabled[c.id] == true
                        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).border(1.5.dp, if (on) Ui.Navy else Ui.Border, RoundedCornerShape(16.dp)).padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Row(Modifier.fillMaxWidth().heightIn(min = 24.dp).clickable(role = Role.Checkbox) { enabled[c.id] = !on; if (c.id !in levels) levels[c.id] = 0 },
                                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                Box(Modifier.size(24.dp).border(2.dp, if (on) Ui.Navy else Ui.RingPending, RoundedCornerShape(7.dp)).background(if (on) Ui.Navy else Color.White, RoundedCornerShape(7.dp)),
                                    contentAlignment = Alignment.Center) { if (on) T("✓", 13, FontWeight.Bold, Color.White) }
                                T(stringResource(c.title), 15, FontWeight.SemiBold, Ui.Navy)
                            }
                            if (on) {
                                val names = LocalContext.current.resources.getStringArray(c.levels)
                                val full = LocalContext.current.resources.getStringArray(c.captions)
                                Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                                    names.forEachIndexed { i, l -> Choice(l, levels[c.id] == i, Modifier.weight(1f), height = 40.dp, size = 11) { levels[c.id] = i } }
                                }
                                T(full[levels[c.id] ?: 0], 12, FontWeight.Medium, Ui.Blue)
                            }
                        }
                    }
                    T(stringResource(R.string.ui_not_diagnosis_long), 12, color = Ui.Muted)
                }
                3 -> {
                    T(stringResource(R.string.ui_comm_title, shown), 22, FontWeight.SemiBold, Ui.Navy)
                    Question(stringResource(R.string.ui_q_signs)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Choice(stringResource(R.string.yes), signs, Modifier.weight(1f), 48.dp) { signs = true }
                            Choice(stringResource(R.string.no), !signs, Modifier.weight(1f), 48.dp) { signs = false }
                        }
                    }
                    if (signs) {
                        Question(stringResource(R.string.ui_q_which_signs)) {
                            listOf("lsec" to R.string.ui_lsec, "asl" to R.string.ui_asl, "other" to R.string.ui_other_signs).forEach { (v, l) ->
                                Choice(stringResource(l), signLanguage == v, Modifier.fillMaxWidth(), start = true) { signLanguage = v }
                            }
                        }
                        Question(stringResource(R.string.ui_q_reads)) {
                            listOf("yes" to R.string.ui_reads_yes, "difficulty" to R.string.ui_reads_difficulty, "no" to R.string.ui_reads_no).forEach { (v, l) ->
                                Choice(stringResource(l), reads == v, Modifier.fillMaxWidth(), start = true) { reads = v }
                            }
                            T(stringResource(R.string.ui_reads_hint), 12, color = Ui.Muted)
                        }
                    }
                    Question(stringResource(R.string.ui_q_address)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            listOf("usted" to R.string.ui_usted, "tu" to R.string.ui_tu, "neutral" to R.string.ui_neutral).forEach { (v, l) ->
                                Choice(stringResource(l), addressing == v, Modifier.weight(1f), size = 13) { addressing = v }
                            }
                        }
                    }
                    Question(stringResource(R.string.ui_auth_title)) {
                        listOf(Triple(R.string.ui_auth_camera, R.string.ui_auth_camera_d, allowCamera) to { v: Boolean -> allowCamera = v },
                            Triple(R.string.ui_auth_mic, R.string.ui_auth_mic_d, allowMic) to { v: Boolean -> allowMic = v },
                            Triple(R.string.ui_auth_meta, R.string.ui_auth_meta_d, allowMeta) to { v: Boolean -> allowMeta = v }).forEach { (row, set) ->
                            Choice((if (row.third) "✓  " else "") + stringResource(row.first), row.third, Modifier.fillMaxWidth(), start = true) { set(!row.third) }
                            T(stringResource(row.second), 12, color = Ui.Muted, lineHeight = 1.45f)
                        }
                        T(stringResource(R.string.ui_auth_hint), 12, color = Ui.Muted, lineHeight = 1.45f)
                    }
                    PresetSummary(keys, count)
                }
            }
        }
        Column(Gutter.padding(top = 10.dp, bottom = 14.dp)) {
            PrimaryButton(stringResource(if (step == 3) R.string.ui_review_activate else R.string.setup_continue), enabled = !(step == 1 && (name.isBlank() || !validZone))) { step++ }
            if (step == 1) LinkButton(stringResource(R.string.logout), Modifier.align(Alignment.CenterHorizontally), size = 12, color = Ui.Muted) { model.logout() }
        }
    }
}

@Composable private fun Question(label: String, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) { T(label, 14, FontWeight.SemiBold, Ui.Navy); content() }
}

@Composable private fun PresetSummary(keys: List<String>, count: Int) {
    Column(Modifier.fillMaxWidth().padding(top = 8.dp).clip(RoundedCornerShape(16.dp)).background(Ui.Subtle).padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Overline(stringResource(R.string.ui_preset_title))
        T(when (count) { 0 -> stringResource(R.string.ui_preset_none); 1 -> stringResource(R.string.ui_preset_one); else -> stringResource(R.string.ui_preset_many, count) }, 15, FontWeight.SemiBold, Ui.Navy)
        keys.forEach { k ->
            Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Box(Modifier.padding(top = 6.dp)) { Dot(Ui.Gold, 6.dp) }
                Column {
                    T(stringResource(PRESET_LABELS.getValue(k)), 13, FontWeight.Medium)
                    T(k + if (k !in SUPPORTED_PRESETS) " · " + stringResource(R.string.ui_soon) else "", 10, color = Ui.Muted)
                }
            }
        }
    }
}

@Composable private fun InviteBox(model: AingelViewModel, s: MobileState) {
    var code by remember { mutableStateOf("") }
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Ui.Subtle).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        FieldInput(stringResource(R.string.invite_code), code, { code = it.take(100) }, fontSize = 14)
        PrimaryButton(stringResource(R.string.accept), height = 48.dp, enabled = !s.busy && code.isNotBlank()) { model.acceptInvite(code); code = "" }
    }
}

/* ─────────── 1i  Today ─────────── */

@Composable fun TodayScreen(model: AingelViewModel, s: MobileState) {
    LaunchedEffect(Unit) { model.loadRows("routines") }
    val profile = s.profile!!
    val zoneId = zone(profile.optString("timezone"))
    val canEdit = profile.optJSONObject("permissions")?.optBoolean("configure") == true
    val sum = summarizeToday(s.rows, zoneId)
    var adding by remember { mutableStateOf(false) }
    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 22.dp, end = 22.dp, top = 14.dp, bottom = 90.dp)) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                T(stringResource(R.string.nav_today), 26, FontWeight.SemiBold, Ui.Navy)
                T(longDate(profile.optString("locale", "es-EC"), zoneId) + if (sum.list.isNotEmpty()) " · ${sum.done} ${stringResource(R.string.ui_of)} ${sum.list.size}" else "", 13, color = Ui.Muted)
            }
            Spacer(Modifier.height(16.dp)); ProgressLine(if (sum.list.isEmpty()) 0f else sum.done / sum.list.size.toFloat(), gold = true, height = 6.dp); Spacer(Modifier.height(6.dp))
            ErrorText(s)
            if (sum.list.isEmpty() && !s.busy) T(stringResource(R.string.ui_no_routines_today), 14, color = Ui.Muted, modifier = Modifier.padding(vertical = 20.dp))
            sum.list.forEach { r ->
                val done = r.optBoolean("confirmed_today"); val isNext = r.optString("id") == sum.next?.optString("id")
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(if (isNext) Ui.Subtle else Color.Transparent)
                    .padding(horizontal = 12.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    T(hhmm(r.optString("at")), 14, FontWeight.SemiBold, Ui.Navy, modifier = Modifier.width(50.dp))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        T(r.optString("title"), 14, FontWeight.SemiBold, if (done) Ui.Muted else Ui.Text, maxLines = 1)
                        T(if (done) stringResource(R.string.ui_confirmed_by, r.optString("confirmation_actor")) else r.optString("instructions").ifBlank { " " }, 11, color = Ui.Muted, maxLines = 1)
                    }
                    Box(Modifier.size(44.dp).clip(CircleShape).clickable(enabled = canEdit && !s.busy, role = Role.Checkbox,
                        onClickLabel = stringResource(if (done) R.string.undo_done else R.string.done)) { model.confirmRoutine(r) }, contentAlignment = Alignment.Center) {
                        Ring(done, isNext)
                    }
                }
            }
            if (adding) { Spacer(Modifier.height(18.dp)); AddRoutine(model, s) { adding = false } }
            Spacer(Modifier.height(16.dp))
            T(stringResource(R.string.ui_reminders_note), 11, color = Ui.Muted, lineHeight = 1.5f)
        }
        if (canEdit && !adding) PrimaryButton(stringResource(R.string.ui_add_routine), Modifier.align(Alignment.BottomEnd).padding(end = 20.dp, bottom = 14.dp), 52.dp, shadow = true, fill = false) { adding = true }
    }
}

@Composable private fun AddRoutine(model: AingelViewModel, s: MobileState, onDone: () -> Unit) {
    var title by remember { mutableStateOf("") }; var at by remember { mutableStateOf("08:00") }; var instructions by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("other") }
    val categories = listOf("wake" to R.string.wake, "medicine" to R.string.medicine, "meal" to R.string.meal, "water" to R.string.water,
        "bathroom" to R.string.bathroom, "appointment" to R.string.appointment, "sleep" to R.string.sleep, "other" to R.string.other)
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).border(1.dp, Ui.Border, RoundedCornerShape(16.dp)).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        T(stringResource(R.string.ui_add_routine), 18, FontWeight.SemiBold, Ui.Navy)
        FieldInput(stringResource(R.string.title), title, { title = it.take(150) }, height = 50.dp, fontSize = 15)
        FieldInput(stringResource(R.string.at), at, { at = it.take(5) }, height = 50.dp, fontSize = 15, placeholder = "08:00")
        T(stringResource(R.string.ui_type), 13, FontWeight.SemiBold, Ui.Navy)
        categories.chunked(2).forEach { pair -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            pair.forEach { (v, l) -> Choice(stringResource(l), category == v, Modifier.weight(1f), 40.dp, 12) { category = v } }
        } }
        FieldInput(stringResource(R.string.instructions), instructions, { instructions = it.take(2000) }, height = 50.dp, fontSize = 15)
        T(stringResource(R.string.daily), 11, color = Ui.Muted)
        PrimaryButton(stringResource(R.string.add), height = 50.dp, enabled = !s.busy && title.isNotBlank() && Regex("([01]\\d|2[0-3]):[0-5]\\d").matches(at)) {
            model.addRoutine(title, at, category, instructions); onDone()
        }
        OutlineButton(stringResource(R.string.cancel), height = 46.dp, size = 14, onClick = onDone)
    }
}

/* ─────────── 1j  More ─────────── */

@Composable fun MoreScreen(model: AingelViewModel, s: MobileState, navigate: (String) -> Unit) {
    val prefs = s.profile?.optJSONObject("preferences")
    var support by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 22.dp, end = 22.dp, top = 14.dp, bottom = 16.dp)) {
        T(stringResource(R.string.nav_more), 26, FontWeight.SemiBold, Ui.Navy)
        Spacer(Modifier.height(20.dp)); Overline(stringResource(R.string.assistance_section)); Spacer(Modifier.height(6.dp))
        listOf(Triple("signs", R.string.ui_signs_title, R.string.ui_more_signs), Triple("see", R.string.see, R.string.ui_more_see), Triple("hear", R.string.hear, R.string.ui_more_hear), Triple("messages", R.string.messages, R.string.ui_more_messages),
            Triple("faces", R.string.faces, R.string.ui_more_faces), Triple("aac", R.string.aac, R.string.ui_more_aac), Triple("ask", R.string.ui_more_tools, R.string.ui_more_tools_d))
            .filter { (route, _, _) -> when (route) { "see" -> prefs?.optBoolean("visual_assistance", true) != false; "hear" -> prefs?.optBoolean("hearing_assistance", true) != false; else -> true } }
            .forEach { (route, title, desc) -> MoreRow(stringResource(title), stringResource(desc)) { navigate(route) } }
        Spacer(Modifier.height(20.dp)); Overline(stringResource(R.string.account_section)); Spacer(Modifier.height(6.dp))
        MoreRow(stringResource(R.string.settings)) { navigate("settings") }
        MoreRow(stringResource(R.string.ui_s_title), stringResource(R.string.ui_s_more)) { navigate("sound") }
        MoreRow(stringResource(R.string.security)) { navigate("security") }
        if (s.profiles.size > 1) MoreRow(stringResource(R.string.switch_profile), s.profile?.optString("display_name")) { navigate("profiles") }
        MoreRow(stringResource(R.string.logout)) { model.logout() }
        Spacer(Modifier.weight(1f).heightIn(min = 28.dp))
        if (support) {
            val text = stringResource(supportMessageResource(s.communication?.optString("distress")))
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Ui.Subtle).padding(16.dp).semantics { liveRegion = LiveRegionMode.Polite },
                verticalArrangement = Arrangement.spacedBy(10.dp)) {
                T(text, 17, FontWeight.Medium, Ui.Navy, lineHeight = 1.45f)
                OutlineButton(stringResource(R.string.read), height = 46.dp, size = 14) { model.speak(text) }
            }
            Spacer(Modifier.height(10.dp))
        }
        OutlineButton(stringResource(R.string.need_support), height = 52.dp, navyBorder = true, size = 15) { support = true }
        Spacer(Modifier.height(8.dp))
        T(stringResource(R.string.support_no_call), 11, color = Ui.Muted, align = TextAlign.Center, modifier = Modifier.fillMaxWidth())
    }
}

@Composable private fun MoreRow(title: String, desc: String? = null, onClick: () -> Unit) {
    Column {
        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onClick).padding(vertical = 13.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                T(title, 15, FontWeight.SemiBold, Ui.Navy); desc?.let { T(it, 12, color = Ui.Muted) }
            }
            T("›", 18, color = Ui.Disabled)
        }
        HorizontalDivider(color = Ui.Divider)
    }
}
