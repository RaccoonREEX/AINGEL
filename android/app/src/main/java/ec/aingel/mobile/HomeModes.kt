package ec.aingel.mobile

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/*
 * 5a · Home with AINGEL in the centre and the top-right menu that unfolds downwards on the same screen.
 * Deaf profile: «Traducir con manos» (listen, see, write). Blind profile: «Ver con AINGEL» (describe, watch).
 */
internal enum class HomeMode(val label: Int, val icon: String) {
    HEAR(R.string.ui_m_hear, EAR), SEE(R.string.ui_m_see, EYE), WRITE(R.string.ui_m_write, KEYBOARD),
    DESCRIBE(R.string.ui_m_describe, EYE), WATCH(R.string.ui_m_watch, WATCH_EYE);
    val signs get() = this == HEAR || this == WRITE
    val camera get() = this == SEE || this == DESCRIBE
}

/** Which menu the account gets, from the presets chosen at sign-up (2c / 2d). */
internal data class HomeProfile(val deaf: Boolean, val blind: Boolean) {
    val modes get() = (if (deaf) listOf(HomeMode.HEAR, HomeMode.SEE, HomeMode.WRITE) else emptyList()) + (if (blind) listOf(HomeMode.DESCRIBE, HomeMode.WATCH) else emptyList())
}
internal fun homeProfile(prefs: JSONObject?) = HomeProfile(
    deaf = prefs?.optBoolean("hearing_assistance", true) != false,
    blind = prefs?.optBoolean("visual_assistance", true) != false,
)

private const val EYE = "M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12zM9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0"
private const val EAR = "M7 9a5 5 0 0 1 10 0c0 3-2.5 3.8-3.2 6.2A3 3 0 0 1 8.5 16M10 9.5a2 2 0 0 1 4 0"
private const val KEYBOARD = "M5.5 6h13A2.5 2.5 0 0 1 21 8.5v7a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 15.5v-7A2.5 2.5 0 0 1 5.5 6zM7 10h.01M11 10h.01M15 10h.01M8 14h8"
private const val WATCH_EYE = "$EYE M12 2v1.5M12 20.5V22M4 4l1 1M19 19l1 1M20 4l-1 1M5 19l-1 1"
private const val HAND_OPEN = "M8 13V5.5a1.3 1.3 0 0 1 2.6 0V11M10.6 10V4.3a1.3 1.3 0 0 1 2.6 0V10M13.2 10.2V5.3a1.3 1.3 0 0 1 2.6 0V11M15.8 11V7.8a1.3 1.3 0 0 1 2.6 0v5.4a6.6 6.6 0 0 1-6.6 6.6h-.5a6 6 0 0 1-4.7-2.3l-2.5-3.3a1.3 1.3 0 0 1 2-1.6L8 14.5"
internal const val SPEAKER_ICON = "M4 9.5v5h3.5L12 18.5v-13L7.5 9.5zM15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"
private const val CHEVRON = "M6 9l6 6 6-6"
internal const val ARROW_ICON = "M5 12h14M13 6l6 6-6 6"

@Composable internal fun PathIcon(d: String, size: Dp, color: Color = Ui.Navy, stroke: Float = 1.8f) {
    val path = remember(d) { PathParser().parsePathString(d).toPath() }
    Canvas(Modifier.size(size)) {
        val k = this.size.width / 24f
        drawContext.transform.scale(k, k, Offset.Zero)
        drawPath(path, color, style = Stroke(stroke, cap = StrokeCap.Round, join = StrokeJoin.Round))
    }
}

/** Scrim behind the open menu: white from the right edge, so the options read over the orb. */
@Composable internal fun MenuScrim(open: Boolean, onClose: () -> Unit) {
    val alpha by animateFloatAsState(if (open) 1f else 0f, tween(220), label = "scrim")
    if (alpha > 0f) Box(Modifier.fillMaxSize().graphicsLayer { this.alpha = alpha }
        .background(Brush.horizontalGradient(0f to Color.White.copy(alpha = 0f), .55f to Color.White.copy(alpha = .86f), 1f to Color.White.copy(alpha = .96f)))
        .clickable(remember { MutableInteractionSource() }, null, enabled = open, onClick = onClose))
}

/**
 * Top-right button and its options, unfolding downwards with a short stagger. The «Ver y traducir»
 * option first shows its two outputs: speaker (say it aloud) and Aa (large text).
 */
@Composable internal fun HomeMenu(profile: HomeProfile, open: Boolean, active: HomeMode?, seeSub: Boolean, reduced: Boolean,
                                  onToggle: () -> Unit, onPick: (HomeMode) -> Unit, onSeeOutput: (Boolean) -> Unit) {
    val main = stringResource(if (profile.deaf) R.string.ui_m_hands else R.string.ui_m_see_with)
    val lit = open || active != null
    Column(horizontalAlignment = Alignment.End) {
        val labelAlpha by animateFloatAsState(if (open) 1f else 0f, tween(200), label = "label")
        Row(Modifier.clip(RoundedCornerShape(28.dp)).clickable(role = Role.Button, onClickLabel = main, onClick = onToggle)
            .semantics { contentDescription = main; stateDescription = if (open) "expanded" else "collapsed" },
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            T(main, 13, FontWeight.SemiBold, Ui.Navy, maxLines = 1, modifier = Modifier.graphicsLayer { alpha = labelAlpha; translationX = (1 - labelAlpha) * 8.dp.toPx() })
            Box(Modifier.size(48.dp).clip(CircleShape).background(if (lit) Ui.Navy else Color.White).border(1.5.dp, if (lit) Ui.Navy else Ui.Control, CircleShape),
                contentAlignment = Alignment.Center) { PathIcon(if (profile.deaf) HAND_OPEN else EYE, 24.dp, if (lit) Color.White else Ui.Navy, 1.7f) }
        }
        profile.modes.forEachIndexed { i, mode ->
            val shown by animateFloatAsState(if (open) 1f else 0f, tween(if (reduced) 120 else 260, delayMillis = if (open) 40 + i * 45 else (profile.modes.size - 1 - i) * 25), label = "opt$i")
            if (shown > .01f) {
                val on = active == mode; val label = stringResource(mode.label)
                Row(Modifier.padding(top = (10 * shown).dp).graphicsLayer {
                    alpha = shown; transformOrigin = TransformOrigin(1f, .5f)
                    if (!reduced) { scaleX = .6f + .4f * shown; scaleY = .6f + .4f * shown; translationY = (1 - shown) * (-14 - i * 10).dp.toPx() }
                }.clip(RoundedCornerShape(24.dp)).clickable(enabled = open, role = Role.Button, onClickLabel = label) { onPick(mode) }.semantics { selected = on },
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    T(label, 13, FontWeight.SemiBold, Ui.Navy, maxLines = 1)
                    Box(Modifier.padding(end = 2.dp).size(44.dp).clip(CircleShape).background(if (on) Ui.Gold else Color.White).border(1.5.dp, if (on) Ui.Gold else Ui.Control, CircleShape),
                        contentAlignment = Alignment.Center) { PathIcon(mode.icon, 20.dp) }
                }
                if (mode == HomeMode.SEE && seeSub && open) Row(Modifier.padding(top = 8.dp, end = 2.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val voice = stringResource(R.string.ui_m_see_voice); val text = stringResource(R.string.ui_m_see_text)
                    Box(Modifier.size(40.dp).clip(CircleShape).background(Color.White).border(1.5.dp, Ui.Control, CircleShape)
                        .clickable(role = Role.Button, onClickLabel = voice) { onSeeOutput(true) }.semantics { contentDescription = voice }, contentAlignment = Alignment.Center) { PathIcon(SPEAKER_ICON, 18.dp, stroke = 1.9f) }
                    Box(Modifier.size(40.dp).clip(CircleShape).background(Color.White).border(1.5.dp, Ui.Control, CircleShape)
                        .clickable(role = Role.Button, onClickLabel = text) { onSeeOutput(false) }.semantics { contentDescription = text }, contentAlignment = Alignment.Center) { T("Aa", 15, FontWeight.Bold, Ui.Navy) }
                }
            }
        }
        val toggle = stringResource(R.string.ui_m_toggle)
        Box(Modifier.padding(top = 8.dp, end = 10.dp).size(28.dp, 22.dp).clip(RoundedCornerShape(50)).background(Ui.Selected)
            .clickable(role = Role.Button, onClickLabel = toggle, onClick = onToggle).semantics { contentDescription = toggle }, contentAlignment = Alignment.Center) {
            val turn by animateFloatAsState(if (open) 180f else 0f, tween(250), label = "chevron")
            Box(Modifier.rotate(turn)) { PathIcon(CHEVRON, 14.dp, stroke = 2.4f) }
        }
    }
}

/** Round stop button with its label, as in 5a («Terminar»). */
@Composable internal fun StopButton(onClick: () -> Unit) {
    val label = stringResource(R.string.ui_m_finish)
    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(Modifier.size(64.dp).clip(CircleShape).background(Ui.Navy).clickable(role = Role.Button, onClickLabel = label, onClick = onClick).semantics { contentDescription = label },
            contentAlignment = Alignment.Center) { Box(Modifier.size(18.dp).background(Color.White, RoundedCornerShape(4.dp))) }
        T(label, 13, color = Ui.Muted)
    }
}

/** Compact pictogram board for «Ver y traducir»: the person taps the signs they make (no recognition yet). */
@Composable internal fun SignBoard(spanish: Boolean, onPick: (String) -> Unit) {
    val label = { id: String -> signName(id, spanish).trim('¿', '?').replaceFirstChar { it.uppercase() } }
    SIGN_BOARD.chunked(4).forEach { row ->
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            row.forEach { id ->
                Column(Modifier.weight(1f).heightIn(min = 72.dp).clip(RoundedCornerShape(16.dp)).border(1.5.dp, Ui.Border, RoundedCornerShape(16.dp)).background(Color.White)
                    .clickable(role = Role.Button, onClickLabel = label(id)) { onPick(id) }.padding(vertical = 8.dp, horizontal = 2.dp),
                    horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp, Alignment.CenterVertically)) {
                    SIGN_PICTOGRAMS[id]?.let { PathIcon(it, 24.dp, stroke = 1.7f) }
                    T(label(id), 11, FontWeight.SemiBold, Ui.Navy, align = TextAlign.Center, maxLines = 1)
                }
            }
            repeat(4 - row.size) { Spacer(Modifier.weight(1f)) }
        }
        Spacer(Modifier.height(8.dp))
    }
}

/**
 * «Siguiente» card. The cared-for person cannot edit routines someone else organizes: tapping only shows,
 * for 3 s, who organizes it. Routines of the signed-in user still open «Hoy».
 */
@Composable internal fun NextCard(next: JSONObject, own: Boolean, onOpen: () -> Unit) {
    var toast by remember { mutableStateOf(false) }
    LaunchedEffect(toast) { if (toast) { kotlinx.coroutines.delay(3000); toast = false } }
    val who = next.optString("author_name").ifBlank { next.optString("author") }
    Box(Modifier.fillMaxWidth()) {
        val shown by animateFloatAsState(if (toast) 1f else 0f, tween(220), label = "toast")
        Column(Modifier.fillMaxWidth()) {
            if (shown > .01f) Box(Modifier.fillMaxWidth().padding(bottom = 10.dp).graphicsLayer { alpha = shown; translationY = (1 - shown) * 6.dp.toPx() }
                .clip(RoundedCornerShape(14.dp)).background(Ui.Navy).padding(horizontal = 14.dp, vertical = 12.dp).semantics { liveRegion = LiveRegionMode.Polite }) {
                T(stringResource(R.string.ui_m_readonly, who, who), 13, FontWeight.Medium, Color.White, lineHeight = 1.45f)
            }
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Ui.Subtle).clickable(role = Role.Button) { if (own) onOpen() else toast = true }
                .padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Overline(stringResource(R.string.ui_next) + " · " + hhmm(next.optString("at")))
                    T(next.optString("title"), 14, FontWeight.SemiBold, Ui.Navy, maxLines = 1)
                }
                Ring(done = false, next = true)
            }
        }
    }
}
