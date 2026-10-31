package ec.aingel.mobile

import android.os.Build
import android.view.Display
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * Foldables and outer screens (AINGEL_Plegables v1.0.0, 6a–6e).
 * COVER: an outer screen (Flip 3/4/5/6, razr) or any small window — only AINGEL's orb, dark tone on pure black.
 * TWO_PANE: Fold inner screen, dual screens or a wide window — AINGEL on the left, options on the right, split in the
 * middle where the fold or hinge is, so nothing crosses it. Otherwise the normal phone layout.
 */
internal enum class WindowShape { PHONE, COVER, TWO_PANE }

internal fun windowShape(widthDp: Int, heightDp: Int, secondaryDisplay: Boolean): WindowShape {
    val short = minOf(widthDp, heightDp); val long = maxOf(widthDp, heightDp)
    return when {
        secondaryDisplay && short < 480 -> WindowShape.COVER
        short < 400 && long < 640 -> WindowShape.COVER
        widthDp >= 600 -> WindowShape.TWO_PANE
        else -> WindowShape.PHONE
    }
}

@Composable internal fun rememberWindowShape(): WindowShape {
    val size = LocalWindowInfo.current.containerSize
    val density = LocalDensity.current
    val activity = LocalActivity.current
    @Suppress("DEPRECATION")
    val display = if (Build.VERSION.SDK_INT >= 30) activity?.display else activity?.windowManager?.defaultDisplay
    return with(density) { windowShape(size.width.toDp().value.toInt(), size.height.toDp().value.toInt(), display != null && display.displayId != Display.DEFAULT_DISPLAY) }
}

/**
 * 6a–6c: AINGEL alone on pure black (AMOLED pixels off), about 60 % of the short side of the free area, away from the
 * cameras (safe area). No text or hands; tapping makes AINGEL listen and it answers aloud. [status] is read by TalkBack.
 */
@Composable internal fun CoverOrb(state: AingelOrbState, reduced: Boolean, status: String, level: () -> Float, onTap: () -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize().background(Color.Black).windowInsetsPadding(WindowInsets.safeDrawing)
        .clickable(remember { MutableInteractionSource() }, null, role = Role.Button, onClickLabel = status, onClick = onTap)
        .semantics { contentDescription = status; liveRegion = LiveRegionMode.Polite }, contentAlignment = Alignment.Center) {
        AingelOrb(state, minOf(maxWidth, maxHeight) * 0.6f, reducedMotion = reduced, dark = true, audioLevel = level)
    }
}

/** 6d / 6e right pane: the «Traducir con manos» (or «Ver con AINGEL») options as a list instead of the corner menu. */
@Composable internal fun ModeOptions(profile: HomeProfile, active: HomeMode?, seeSub: Boolean, onPick: (HomeMode) -> Unit, onSeeOutput: (Boolean) -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        T(stringResource(if (profile.deaf) R.string.ui_m_hands else R.string.ui_m_see_with).uppercase(), 12, FontWeight.SemiBold, Ui.Muted)
        profile.modes.forEach { mode ->
            val on = active == mode; val label = stringResource(mode.label)
            Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).clip(RoundedCornerShape(16.dp)).background(if (on) Ui.Selected else Color.White)
                .border(1.5.dp, if (on) Ui.Navy else Ui.Control, RoundedCornerShape(16.dp))
                .clickable(role = Role.Button, onClickLabel = label) { onPick(mode) }.semantics { selected = on }.padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                PathIcon(mode.icon, 20.dp)
                T(label, 15, FontWeight.SemiBold, Ui.Navy, modifier = Modifier.weight(1f))
            }
            if (mode == HomeMode.SEE && seeSub) Row(Modifier.padding(start = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val voice = stringResource(R.string.ui_m_see_voice); val text = stringResource(R.string.ui_m_see_text)
                Box(Modifier.size(44.dp).clip(CircleShape).background(Color.White).border(1.5.dp, Ui.Control, CircleShape)
                    .clickable(role = Role.Button, onClickLabel = voice) { onSeeOutput(true) }.semantics { contentDescription = voice }, contentAlignment = Alignment.Center) { PathIcon(SPEAKER_ICON, 18.dp, stroke = 1.9f) }
                Box(Modifier.size(44.dp).clip(CircleShape).background(Color.White).border(1.5.dp, Ui.Control, CircleShape)
                    .clickable(role = Role.Button, onClickLabel = text) { onSeeOutput(false) }.semantics { contentDescription = text }, contentAlignment = Alignment.Center) { T("Aa", 15, FontWeight.Bold, Ui.Navy) }
            }
        }
    }
}
