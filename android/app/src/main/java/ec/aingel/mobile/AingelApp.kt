package ec.aingel.mobile

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.util.Base64
import android.view.WindowManager
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.selection.selectable
import androidx.compose.ui.semantics.Role
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import java.time.ZoneId
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

@Composable private fun Input(label: Int, value: String, change: (String) -> Unit, secret: Boolean = false, enabled: Boolean = true) {
    OutlinedTextField(value, change, label = { Text(stringResource(label)) }, modifier = Modifier.fillMaxWidth(),
        visualTransformation = if (secret) PasswordVisualTransformation() else VisualTransformation.None,
        singleLine = true, enabled = enabled)
}
@Composable private fun Action(label: Int, enabled: Boolean = true, action: () -> Unit) {
    Button(onClick = action, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text(stringResource(label)) }
}
@Composable private fun Check(label: Int, value: Boolean, change: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth()) { Checkbox(value, change); Text(stringResource(label), Modifier.padding(top = 12.dp)) }
}

private val Muted = Color(0xFF5A6780)

@Composable fun AingelApp(model: AingelViewModel) {
    val s by model.state.collectAsStateWithLifecycle()
    var screen by rememberSaveable { mutableStateOf("home") }
    var signsFrom by rememberSaveable { mutableStateOf("home") }  // the sign translator returns where it was opened from
    var focus by remember { mutableStateOf(false) }
    val prefs = s.profile?.optJSONObject("preferences")
    val contrast = prefs?.optBoolean("high_contrast") == true
    val largeText = prefs?.optBoolean("large_text") == true
    val typography = Typography().let { type -> if (largeText) type.copy(
        bodyLarge = type.bodyLarge.copy(fontSize = type.bodyLarge.fontSize * 1.3f),
        bodyMedium = type.bodyMedium.copy(fontSize = type.bodyMedium.fontSize * 1.3f),
        labelLarge = type.labelLarge.copy(fontSize = type.labelLarge.fontSize * 1.2f)) else type }
    val context = LocalContext.current
    val shape = rememberWindowShape()  // outer screens show only AINGEL (AINGEL_Plegables 6a–6c)
    DisposableEffect(context) {
        val activity = context as? Activity
        val window = activity?.window
        // Screens hold personal data, so capture is blocked. Debug builds started with the explicit
        // QA extra (adb shell am start ... --ez aingel_qa_screenshots true) allow screenshots for design review.
        val qa = BuildConfig.DEBUG && activity?.intent?.getBooleanExtra("aingel_qa_screenshots", false) == true
        if (!qa) window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose { window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
    }
    SideEffect { Ui.highContrast(contrast) }
    // A new session (or the end of setup) always starts on the assistant, not on the last tab used.
    LaunchedEffect(s.username) { if (s.username == null) screen = "home" }
    fun navigate(target: String) { if (screen != target) { if (target == "signs") signsFrom = screen; model.resetScreen(); focus = false; screen = target } }
    BackHandler(s.username != null && s.profile != null && screen != "home") { navigate(if (screen in setOf("today", "remember", "circle", "more")) "home" else if (screen == "signs") signsFrom else "more") }
    MaterialTheme(colorScheme = lightColorScheme(primary = Ui.Navy, onPrimary = Color.White, background = Color.White,
        surface = Color.White, onSurface = Ui.Text, outline = Ui.Control, secondaryContainer = Ui.Selected, error = Color(0xFF8B2630)),
        typography = typography, shapes = Shapes(small = RoundedCornerShape(10.dp), medium = RoundedCornerShape(14.dp), large = RoundedCornerShape(16.dp))) {
        CompositionLocalProvider(LocalTextScale provides if (largeText) 1.15f else 1f) {
            val signedIn = s.username != null && s.profile != null
            val cover = signedIn && shape == WindowShape.COVER
            Scaffold(containerColor = if (cover) Color.Black else Color.White, contentWindowInsets = WindowInsets.safeDrawing, bottomBar = {
                if (signedIn && !focus && !cover) {
                    val tabs = listOf("home" to stringResource(R.string.nav_aingel), "today" to stringResource(R.string.nav_today),
                        "remember" to stringResource(R.string.nav_remember), "circle" to stringResource(R.string.nav_circle), "more" to stringResource(R.string.nav_more))
                        .filter { it.first != "remember" || prefs?.optBoolean("memory_assistance", true) != false }
                    TabBar(tabs, if (screen in setOf("home", "today", "remember", "circle")) screen else if (screen == "signs" && signsFrom == "home") "home" else "more", ::navigate)
                }
            }) { padding ->
                Box(Modifier.fillMaxSize().padding(padding)) {
                    when {
                        s.username == null -> AccessFlow(model, s)
                        screen == "security" -> Legacy(R.string.security, s, { navigate(if (s.profile == null) "home" else "more") }) { SecurityScreen(model, s) }
                        s.profile == null -> SetupFlow(model, s)
                        else -> key(screen, s.profile!!.optString("id")) {
                            when (if (cover) "home" else screen) {
                                "home" -> HomeScreen(model, s, onToday = { navigate("today") }, onSigns = { navigate("signs") }, onFocus = { focus = it })
                                "signs" -> SignTranslatorScreen(model, s) { navigate(signsFrom) }
                                "today" -> TodayScreen(model, s)
                                "more" -> MoreScreen(model, s, ::navigate)
                                "sound" -> SoundSettingsScreen(model, s) { navigate("more") }
                                "remember" -> Legacy(R.string.nav_remember, s, null) { MemoryScreen(model, s) }
                                "circle" -> Legacy(R.string.circle, s, null) {
                                    CircleScreen(model, s)
                                    HorizontalDivider(color = Ui.Divider)
                                    Text(stringResource(R.string.setup_invited), style = MaterialTheme.typography.titleMedium, color = Ui.Navy)
                                    AcceptInvitation(model, s.busy)
                                }
                                "profiles" -> Legacy(R.string.switch_profile, s, { navigate("more") }) {
                                    s.profiles.forEach { profile -> OutlinedButton(onClick = { model.select(profile); navigate("home") }, enabled = !s.busy,
                                        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text(profile.optString("display_name")) } }
                                }
                                "ask" -> Legacy(R.string.ui_more_tools, s, { navigate("more") }) { AskScreen(model, s) }
                                "messages" -> Legacy(R.string.messages, s, { navigate("more") }) { MessagesScreen(model, s) }
                                "settings" -> Legacy(R.string.settings, s, { navigate("more") }) { SettingsScreen(model, s) }
                                "see" -> Legacy(R.string.see, s, { navigate("more") }) { SeeScreen(model, s) }
                                "faces" -> Legacy(R.string.faces, s, { navigate("more") }) { FacesScreen(model, s) }
                                "hear" -> Legacy(R.string.hear, s, { navigate("more") }) { HearScreen(model, s) }
                                "aac" -> Legacy(R.string.aac, s, { navigate("more") }) { AacScreen(model) }
                            }
                        }
                    }
                }
            }
        }
    }
}

/** Screens outside the redesigned set keep their controls, under the new header (back + 26/600 title). */
@Composable private fun Legacy(title: Int, s: MobileState, onBack: (() -> Unit)?, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 22.dp, end = 22.dp, top = 14.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (onBack != null) TextButton(onClick = onBack, modifier = Modifier.offset(x = (-12).dp)) { T("‹", 26, color = Ui.Navy) }
            T(stringResource(title), 26, FontWeight.SemiBold, Ui.Navy, lineHeight = 1.2f)
        }
        if (s.busy) { LinearProgressIndicator(Modifier.fillMaxWidth(), color = Ui.Navy, trackColor = Ui.Divider); Text(stringResource(R.string.loading), color = Muted, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
        if (s.error != null) Text(stringResource(errorMessage(s.error!!)), color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        content()
    }
}

internal fun errorMessage(error: String): Int = when (error) {
    "device_permission_denied" -> R.string.permissions
    "permission_denied", "self_enrollment_requires_membership" -> R.string.access_denied
    "credentials_invalid" -> R.string.credentials_error
    "registration_invalid" -> R.string.registration_error
    "session_expired", "authentication_required", "mfa_challenge_expired" -> R.string.session_error
    "auth_rate_limited", "mfa_rate_limited", "throttled" -> R.string.rate_error
    "mfa_code_invalid" -> R.string.mfa_error
    "server_unavailable", "transcription_unavailable" -> R.string.connection_error
    "backend_invalid" -> R.string.backend_error
    "care_circle_full" -> R.string.circle_full_error
    "image_required", "face_enrollment_invalid" -> R.string.image_required_error
    "image_too_large", "face_images_too_large" -> R.string.image_size_error
    "face_duplicate_photo" -> R.string.face_duplicate_error
    "face_photo_blurry" -> R.string.face_blurry_error
    "face_single_clear_face_required" -> R.string.face_clear_error
    "face_photos_inconsistent" -> R.string.face_inconsistent_error
    "face_models_not_installed", "face_processing_failed" -> R.string.face_processing_error
    "voice_unavailable" -> R.string.voice_error
    "knowledge_not_installed", "knowledge_index_invalid" -> R.string.knowledge_unavailable
    "knowledge_query_invalid" -> R.string.knowledge_query_error
    "browser_unavailable" -> R.string.browser_error
    "companion_input_invalid" -> R.string.companion_input_error
    "companion_response_invalid" -> R.string.companion_response_error
    "camera_unavailable", "microphone_unavailable" -> R.string.device_error
    "private_test_consent_required" -> R.string.private_test_missing_consent
    "privacy_review_required" -> R.string.private_test_server_denied
    // Network and server failures (NetworkErrors.kt): specific messages instead of a generic «failed».
    else -> networkErrorMessage(error) ?: R.string.failed
}

@Composable private fun AcceptInvitation(model: AingelViewModel, busy: Boolean) {
    var code by remember { mutableStateOf("") }
    Input(R.string.invite_code, code, { code = it }); Action(R.string.accept, !busy && code.isNotBlank()) { model.acceptInvite(code); code = "" }
}
@Composable private fun AskScreen(model: AingelViewModel, s: MobileState) {
    var entity by remember { mutableStateOf("") }
    var supportVisible by remember { mutableStateOf(false) }
    var companionTopic by remember { mutableStateOf<CompanionTopic?>(null) }
    val preferredName = s.communication?.optString("preferred_name")?.takeIf { it.isNotBlank() } ?: s.profile!!.optString("display_name")
    val greeting = stringResource(R.string.greeting_name, preferredName) + " " + stringResource(when (s.communication?.optString("addressing")) {
        "formal" -> R.string.greeting_formal
        "informal" -> R.string.greeting_informal
        else -> R.string.greeting_neutral
    }) + if (s.communication?.optString("sentence_length") == "standard") " " + stringResource(R.string.greeting_extra) else ""
    Text(greeting); Action(R.string.read) { model.speak(greeting) }
    Action(R.string.need_support) { supportVisible = true }
    if (supportVisible) {
        val support = stringResource(supportMessageResource(s.communication?.optString("distress")))
        Text(support); Action(R.string.read) { model.speak(support) }
    }
    Input(R.string.entity, entity, { entity = it }); Action(R.string.remember, !s.busy && entity.isNotBlank()) { model.ask("search_memory", entity) }
    Action(R.string.today, !s.busy) { model.ask("get_routines") }; Action(R.string.messages, !s.busy) { model.ask("get_care_messages") }
    s.result?.let { result ->
        if (result.optString("tool") == "search_memory") {
            val evidence = result.optJSONObject("evidence")
            val text = if (evidence == null) stringResource(R.string.no_evidence) else stringResource(R.string.last_reported) + ": " + evidence.optString("location") + " · " + evidence.optString("observed_at")
            Text(text); Action(R.string.read) { model.speak(text) }
        } else result.optJSONArray("items")?.rows()?.let { items ->
            var index by remember(result) { mutableIntStateOf(0) }
            val oneStep = s.communication?.optString("interaction", "one_step") != "standard"
            if (items.isEmpty()) Text(stringResource(R.string.empty))
            val shown = if (oneStep) items.drop(index).take(1) else items
            shown.forEach { item ->
                val text = item.optString("title", item.optString("body")) + " " + item.optString("at") + " " + item.optString("instructions")
                Text(text); Action(R.string.read) { model.speak(text) }
            }
            if (oneStep && items.size > 1) {
                Text(stringResource(R.string.item_number, index + 1, items.size))
                Action(R.string.previous_item, index > 0) { index-- }
                Action(R.string.next_item, index < items.lastIndex) { index++ }
            }
        }
    }
    HealthResourcesScreen(model, s) { model.clearCompanion(); companionTopic = it }
    CompanionScreen(model, s, companionTopic) { model.clearCompanion(); companionTopic = null }
}

internal fun supportMessageResource(preference: String?): Int =
    if (preference == "contact_caregiver") R.string.support_contact else R.string.support_quiet

internal fun verifiedMedlinePlusUrl(raw: String): String? {
    val url = raw.toHttpUrlOrNull() ?: return null
    return if (url.scheme == "https" && url.host == "medlineplus.gov" && url.port == 443 && url.username.isEmpty() && url.password.isEmpty()) url.toString() else null
}

@Composable private fun HealthResourcesScreen(model: AingelViewModel, s: MobileState, selectTopic: (CompanionTopic) -> Unit) {
    var query by remember { mutableStateOf("") }
    val uriHandler = LocalUriHandler.current
    HorizontalDivider()
    Text(stringResource(R.string.knowledge_title), style = MaterialTheme.typography.titleLarge)
    Text(stringResource(R.string.knowledge_intro))
    Input(R.string.knowledge_search, query, { query = it.take(100) })
    Action(R.string.knowledge_search_action, !s.busy && query.isNotBlank()) { model.searchResources(query) }
    s.knowledge?.let { items ->
        var index by remember(items) { mutableIntStateOf(0) }
        val oneStep = s.communication?.optString("interaction", "one_step") != "standard"
        if (items.isEmpty()) Text(stringResource(R.string.knowledge_none))
        (if (oneStep) items.drop(index).take(1) else items).forEach { item ->
            val title = item.optString("title")
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.knowledge_source, item.optString("source")))
            Text(stringResource(R.string.knowledge_date, item.optString("downloaded_at").take(10)))
            val summary = item.optString("summary")
            var showSummary by remember(item) { mutableStateOf(false) }
            if (summary.isNotBlank()) {
                Action(if (showSummary) R.string.knowledge_hide_summary else R.string.knowledge_read_summary) { showSummary = !showSummary }
                if (showSummary) { Text(summary); Action(R.string.read) { model.speak(summary) } }
            }
            val language = item.optString("lang")
            if (title.isNotBlank() && language in setOf("es", "en")) Action(R.string.companion_use_topic, !s.busy) { selectTopic(CompanionTopic(title, language)) }
            val url = verifiedMedlinePlusUrl(item.optString("url"))
            if (url != null) Action(R.string.knowledge_open) {
                try { uriHandler.openUri(url) } catch (_: Exception) { model.reportError("browser_unavailable") }
            }
        }
        if (oneStep && items.size > 1) {
            Text(stringResource(R.string.item_number, index + 1, items.size))
            Action(R.string.previous_resource, index > 0) { index-- }
            Action(R.string.next_resource, index < items.lastIndex) { index++ }
        }
    }
}

@Composable private fun CompanionScreen(model: AingelViewModel, s: MobileState, topic: CompanionTopic?, clearTopic: () -> Unit) {
    var question by remember { mutableStateOf("") }
    var confirmed by remember { mutableStateOf(false) }
    val uriHandler = LocalUriHandler.current
    LaunchedEffect(question, topic) { confirmed = false; model.clearCompanion() }
    HorizontalDivider()
    Text(stringResource(R.string.companion_title), style = MaterialTheme.typography.titleLarge)
    Text(stringResource(R.string.companion_intro))
    topic?.let {
        Text(stringResource(R.string.companion_topic, it.title))
        Action(R.string.companion_remove_topic, !s.busy) { clearTopic() }
    }
    Input(R.string.companion_question, question, {
        val edited = it.take(1000)
        if (edited != question) { model.clearCompanion(); confirmed = false; question = edited }
    }, enabled = !s.busy)
    Check(R.string.companion_confirm, confirmed) { if (!s.busy) confirmed = it }
    Action(R.string.companion_submit, !s.busy && confirmed && question.isNotBlank()) { model.askCompanion(question, topic); confirmed = false }
    s.companion?.let { result ->
        Text(stringResource(if (result.optString("mode") == "meta") R.string.companion_meta else R.string.companion_mock))
        val answer = result.optString("text")
        Text(answer); Action(R.string.read) { model.speak(answer) }
        result.optJSONObject("source")?.let { source ->
            Text(source.optString("title"))
            Text(stringResource(R.string.knowledge_source, source.optString("source")))
            Text(stringResource(R.string.knowledge_date, source.optString("downloaded_at").take(10)))
            verifiedMedlinePlusUrl(source.optString("url"))?.let { url ->
                Action(R.string.knowledge_open) { try { uriHandler.openUri(url) } catch (_: Exception) { model.reportError("browser_unavailable") } }
            }
        }
    }
}
@Composable private fun MemoryScreen(model: AingelViewModel, s: MobileState) {
    LaunchedEffect(Unit) { model.loadRows("memories") }
    var entity by remember { mutableStateOf("") }; var location by remember { mutableStateOf("") }; var confirmed by remember { mutableStateOf(false) }
    if (s.profile?.optString("role") == "owner") {
        Input(R.string.entity, entity, { entity = it }); Input(R.string.location, location, { location = it })
        Check(R.string.confirmed, confirmed) { confirmed = it }
        Action(R.string.add, !s.busy && confirmed && entity.isNotBlank() && location.isNotBlank()) { model.addMemory(entity, location); confirmed = false; entity = ""; location = "" }
    }
    s.rows.forEach { row ->
        HorizontalDivider(); val text = row.optString("entity") + ": " + row.optString("location") + " · " + row.optString("observed_at")
        Text(text); Action(R.string.read) { model.speak(text) }
        if (s.profile?.optString("role") == "owner") Action(R.string.delete, !s.busy) { model.deleteMemory(row.getString("id")) }
    }
}
@Composable private fun MessagesScreen(model: AingelViewModel, s: MobileState) {
    LaunchedEffect(Unit) { model.loadRows("messages") }
    var body by remember { mutableStateOf("") }; Input(R.string.body, body, { body = it })
    Action(R.string.send, !s.busy && body.isNotBlank()) { model.message(body); body = "" }
    s.rows.forEach { Text(it.optString("author") + ": " + it.optString("body")); val text = it.optString("body"); Action(R.string.read) { model.speak(text) } }
}
@Composable private fun SettingsScreen(model: AingelViewModel, s: MobileState) {
    val profile = s.profile!!
    var name by remember { mutableStateOf(profile.optString("display_name")) }; var allergies by remember { mutableStateOf(profile.optString("allergies")) }
    var notes by remember { mutableStateOf(profile.optString("support_notes")) }
    var large by remember { mutableStateOf(profile.optJSONObject("preferences")?.optBoolean("large_text") == true) }
    var contrast by remember { mutableStateOf(profile.optJSONObject("preferences")?.optBoolean("high_contrast") == true) }
    var voice by remember { mutableStateOf(profile.optJSONObject("preferences")?.optBoolean("voice_output") == true) }
    Text(stringResource(R.string.permission_note)); Input(R.string.name, name, { name = it }); Input(R.string.allergies, allergies, { allergies = it }); Input(R.string.notes, notes, { notes = it })
    Check(R.string.large_text, large) { large = it }; Check(R.string.high_contrast, contrast) { contrast = it }; Check(R.string.voice_output, voice) { voice = it }
    Action(R.string.save, !s.busy && profile.optJSONObject("permissions")?.optBoolean("configure") == true) {
        val updated = JSONObject(profile.optJSONObject("preferences")?.toString() ?: "{}").put("large_text", large).put("high_contrast", contrast).put("voice_output", voice)
        model.savePreferences(name, allergies, notes, updated)
    }
    if (profile.optString("role") == "owner") {
        val consents = profile.optJSONObject("consents")
        var camera by remember(profile.optString("id"), consents?.toString()) { mutableStateOf(consents?.optBoolean("camera") == true) }
        var microphone by remember(profile.optString("id"), consents?.toString()) { mutableStateOf(consents?.optBoolean("microphone") == true) }
        var meta by remember(profile.optString("id"), consents?.toString()) { mutableStateOf(consents?.optBoolean("meta_data") == true) }
        Text(stringResource(R.string.private_test_title))
        Text(stringResource(R.string.private_test_explanation))
        Check(R.string.ui_auth_camera, camera) { camera = it }
        Check(R.string.ui_auth_mic, microphone) { microphone = it }
        Check(R.string.ui_auth_meta, meta) { meta = it }
        Action(R.string.private_test_save_consent, !s.busy) { model.saveMediaConsents(camera, microphone, meta) }
        Text(stringResource(R.string.private_test_declaration))
        Check(R.string.private_test_enable, s.privateTestProfileId == profile.optString("id")) { model.setPrivateTest(it) }
    }
}
@Composable private fun CircleScreen(model: AingelViewModel, s: MobileState) {
    LaunchedEffect(Unit) { model.loadCircle() }
    var username by remember { mutableStateOf("") }; var relationship by remember { mutableStateOf("") }; var memories by remember { mutableStateOf(false) }
    Text(stringResource(R.string.care_status))
    if (s.profile?.optString("role") == "owner") {
        Input(R.string.username, username, { username = it }); Input(R.string.relationship, relationship, { relationship = it })
        Check(R.string.memory_access, memories) { memories = it }
        Action(R.string.invite, !s.busy && username.isNotBlank() && relationship.isNotBlank()) { model.invite(username, relationship, memories); username = "" }
        s.inviteCode?.let { Text(stringResource(R.string.invite_code)); Text(it) }
    }
    s.circle?.optJSONArray("members")?.rows()?.forEach { member ->
        Text(member.optString("username") + " · " + member.optString("relationship"))
        if (s.profile?.optString("role") == "owner" || member.optString("username") == s.username) Action(R.string.remove, !s.busy) { model.revokeMember(member.getString("id")) }
    }
    s.circle?.optJSONArray("pending")?.rows()?.forEach { Text(it.optString("username") + " · " + it.optString("expires_at")) }
}

@Composable private fun PhotoInput(model: AingelViewModel, s: MobileState, front: Boolean = false) {
    val context = LocalContext.current; val scope = rememberCoroutineScope()
    var camera by remember { mutableStateOf(false) }
    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            try { val bytes = withContext(Dispatchers.IO) { readPhoto(context, uri) }; model.setImage(bytes) }
            catch (_: Exception) { model.reportError("image_invalid") }
        }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { allowed -> if (allowed) camera = true else model.reportError("device_permission_denied") }
    if (camera) CameraCapture(front, { model.setImage(it); camera = false }, { camera = false }, { camera = false; model.reportError("camera_unavailable") })
    else {
        Action(R.string.camera, !s.busy) {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) camera = true else permission.launch(Manifest.permission.CAMERA)
        }
        Action(R.string.gallery, !s.busy) { gallery.launch("image/*") }
    }
    s.image?.let { bytes ->
        val bitmap = remember(bytes) { BitmapFactory.decodeByteArray(bytes, 0, bytes.size) }
        if (bitmap != null) Image(bitmap.asImageBitmap(), stringResource(R.string.preview), Modifier.fillMaxWidth().heightIn(max = 260.dp))
    }
}
@Composable private fun SeeScreen(model: AingelViewModel, s: MobileState) {
    var objectName by remember { mutableStateOf("") }
    // Real photos use the sign-up authorization; only the included shapes image is a synthetic test.
    val shapes = remember { syntheticPhoto() }
    val fixture = s.image?.contentEquals(shapes) == true
    Text(stringResource(if (s.privateTestProfileId != null) R.string.private_test_active else R.string.synthetic_only)); PhotoInput(model, s)
    Action(R.string.fixture, !s.busy) { model.setImage(shapes) }
    Action(R.string.describe, !s.busy && s.image != null) { model.analyze(fixture) }
    Input(R.string.object_prompt, objectName, { objectName = it })
    Action(R.string.locate, !s.busy && s.image != null && objectName.isNotBlank()) { model.analyze(fixture, objectName) }
    s.result?.let { result ->
        val description = result.optString("text")
        if (description.isNotBlank()) { Text(description); Action(R.string.read) { model.speak(description) } }
        result.optJSONArray("matches")?.let { matches ->
            if (matches.length() == 0) Text(stringResource(R.string.no_matches))
            matches.rows().forEach { Text(it.optString("label", objectName) + " · " + it.optString("confidence")) }
            s.image?.let { AnnotatedPhoto(it, result) }
        }
    }
    Action(R.string.stop) { model.stopSpeech() }
}
@Composable private fun AnnotatedPhoto(bytes: ByteArray, result: JSONObject) {
    val image = remember(bytes) { BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap() } ?: return
    val overlays = remember(result) {
        result.optJSONArray("matches")?.rows()?.mapNotNull { item ->
            val box = item.optJSONArray("box") ?: return@mapNotNull null
            if (box.length() != 4) return@mapNotNull null
            val bounds = (0..3).map { box.optDouble(it).toFloat() }
            if (bounds.any { !it.isFinite() || it !in 0f..1f } || bounds[2] <= bounds[0] || bounds[3] <= bounds[1]) return@mapNotNull null
            val mask = try {
                val data = Base64.decode(item.getString("mask_png").substringAfter(','), Base64.DEFAULT)
                BitmapFactory.decodeByteArray(data, 0, data.size)?.asImageBitmap()
            } catch (_: Exception) { null }
            bounds to mask
        } ?: emptyList()
    }
    Box {
        Image(image, stringResource(R.string.preview), Modifier.fillMaxWidth().aspectRatio(image.width.toFloat() / image.height))
        Canvas(Modifier.matchParentSize()) {
            overlays.forEach { (bounds, mask) ->
                val left = bounds[0] * size.width; val top = bounds[1] * size.height
                val width = (bounds[2] - bounds[0]) * size.width; val height = (bounds[3] - bounds[1]) * size.height
                if (mask != null) drawImage(mask, dstOffset = IntOffset(left.toInt(), top.toInt()), dstSize = IntSize(maxOf(1, width.toInt()), maxOf(1, height.toInt())))
                drawRect(Color(0xFF135D9D), Offset(left, top), Size(width, height), style = Stroke(3.dp.toPx()))
            }
        }
    }
}
@Composable private fun FacesScreen(model: AingelViewModel, s: MobileState) {
    LaunchedEffect(Unit) { model.loadFaces() }
    var consent by remember { mutableStateOf(false) }; var ownConsent by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    Text(stringResource(R.string.face_intro))
    val enabled = s.faces?.optBoolean("enabled") == true
    val owner = s.profile?.optString("role") == "owner"
    if (owner) {
        if (!enabled) { Input(R.string.password, password, { password = it }, true); Check(R.string.face_consent, consent) { consent = it }
            Action(R.string.enable, !s.busy && consent && password.isNotEmpty()) { model.faceConsent(true, password); password = ""; consent = false }
        } else Action(R.string.disable, !s.busy) { model.faceConsent(false) }
    }
    if (enabled) {
        s.faces?.optJSONArray("enrollments")?.rows()?.forEach { Text(it.optString("display_name") + " · " + it.optString("relationship") + " · " + stringResource(R.string.expires) + " " + it.optString("expires_at")) }
        PhotoInput(model, s, !owner)
        if (s.faces?.optBoolean("can_enroll") == true) {
            Text(stringResource(R.string.face_samples) + " · " + s.enrollmentPhotos.size)
            Action(R.string.keep_photo, !s.busy && s.image != null && s.enrollmentPhotos.size < 2) { model.keepEnrollmentPhoto() }
            Action(R.string.clear_photos, !s.busy) { model.clearEnrollmentPhotos() }
            Input(R.string.name, name, { name = it }); Check(R.string.own_consent, ownConsent) { ownConsent = it }
            Action(R.string.enroll, !s.busy && ownConsent && (s.image != null || s.enrollmentPhotos.isNotEmpty()) && name.isNotBlank()) { model.enrollFace(name); ownConsent = false }
            Action(R.string.delete, !s.busy) { model.deleteFace() }
        }
        if (owner) {
            Check(R.string.face_consent, consent) { consent = it }
            Action(R.string.recognize, !s.busy && consent && s.image != null) { model.recognizeFaces(); consent = false }
            val faces = s.result?.optJSONArray("faces")
            if (faces != null) {
                if (faces.length() == 0) Text(stringResource(R.string.no_faces))
                faces.rows().forEach { face ->
                    val candidate = face.optJSONObject("candidate")
                    val text = if (candidate == null) stringResource(R.string.unknown) else stringResource(R.string.possible) + " " + candidate.optString("display_name") + ", " + candidate.optString("relationship")
                    Text(text); Action(R.string.read) { model.speak(text) }
                }
            }
        }
    }
}
@Composable private fun SecurityScreen(model: AingelViewModel, s: MobileState) {
    LaunchedEffect(Unit) { model.loadMfa() }
    DisposableEffect(Unit) { onDispose { model.hideRecovery() } }
    var password by remember { mutableStateOf("") }; var code by remember { mutableStateOf("") }
    Text(stringResource(R.string.mfa_intro)); Text(stringResource(if (s.mfaEnabled) R.string.mfa_on else R.string.mfa_off))
    if (s.recovery.isNotEmpty()) {
        Text(stringResource(R.string.recovery)); s.recovery.forEach { Text(it) }; Action(R.string.close) { model.hideRecovery() }
    } else if (s.mfaSetup != null) {
        val setup = s.mfaSetup!!
        val bitmap = remember(setup) { try { val bytes = Base64.decode(setup.getString("qr_png").substringAfter(','), Base64.DEFAULT); BitmapFactory.decodeByteArray(bytes, 0, bytes.size) } catch (_: Exception) { null } }
        if (bitmap != null) Image(bitmap.asImageBitmap(), stringResource(R.string.qr), Modifier.size(230.dp).background(Color.White))
        Text(setup.optString("secret")); Input(R.string.code, code, { code = it })
        Action(R.string.enable, !s.busy && code.length == 6) { model.enableMfa(code); code = "" }; Action(R.string.cancel) { model.hideRecovery() }
    } else {
        Input(R.string.password, password, { password = it }, true)
        if (s.mfaEnabled) {
            Input(R.string.code, code, { code = it })
            Action(R.string.disable, !s.busy && password.isNotEmpty() && code.isNotBlank()) { model.disableMfa(password, code); password = ""; code = "" }
        } else Action(R.string.setup, !s.busy && password.isNotEmpty()) { model.setupMfa(password); password = "" }
    }
}
@Composable private fun HearScreen(model: AingelViewModel, s: MobileState) {
    val context = LocalContext.current
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { allowed -> if (allowed) model.startCaptions() else model.reportError("device_permission_denied") }
    DisposableEffect(Unit) { onDispose { model.stopCaptions() } }
    val language = when (s.communication?.optString("sign_language")) {
        "lsec" -> R.string.sign_lsec
        "asl" -> R.string.sign_asl
        "other" -> R.string.sign_other
        "none" -> R.string.sign_none
        else -> R.string.sign_unavailable
    }
    Text(stringResource(R.string.sign_selected, stringResource(language)))
    Text(stringResource(R.string.sign_not_ready))
    if (supportsSignCatalog(s.communication?.optString("sign_language"))) {
        Text(stringResource(when (s.signStatus) {
            "listening" -> R.string.sign_listening
            "searching" -> R.string.sign_searching
            "available" -> R.string.sign_available
            "unavailable" -> R.string.sign_no_match
            "error" -> R.string.sign_lookup_error
            else -> R.string.sign_waiting
        }))
        s.signText?.let { Text(it) }
        if (s.signStatus == "available" && s.signVideo != null && s.signMetadata != null) {
            val clip = s.signMetadata!!
            Text(stringResource(R.string.sign_credit, clip.optString("source").take(200), clip.optString("attribution").take(500)))
            Text(stringResource(R.string.sign_license, clip.optString("license").take(200)))
            key(s.signVideo!!) { SignVideo(s.signVideo!!) }
        }
    } else Text(stringResource(R.string.sign_unsupported))
    Text(stringResource(R.string.mic_intro))
    Text(stringResource(when (s.captionStatus) { "recording" -> R.string.recording; "connecting" -> R.string.connecting; "finishing" -> R.string.finishing; else -> R.string.idle }))
    Action(R.string.start, s.captionStatus == "idle") {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) model.startCaptions() else permission.launch(Manifest.permission.RECORD_AUDIO)
    }
    Action(R.string.stop, s.captionStatus != "idle") { model.finishCaptions() }
    s.captions.forEach { Text(it.text, style = if (it.final) MaterialTheme.typography.bodyLarge else MaterialTheme.typography.bodyMedium) }
}
@Composable private fun AacScreen(model: AingelViewModel) {
    listOf(R.string.need_help, R.string.need_water, R.string.need_bathroom, R.string.pain, R.string.yes, R.string.no).forEach { label ->
        val text = stringResource(label); Action(label) { model.speak(text) }
    }
    Action(R.string.stop) { model.stopSpeech() }
}
