package ec.aingel.mobile

import androidx.compose.foundation.layout.size
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.viewinterop.AndroidView

/*
 * AINGEL's articulated 3D hands on Android, drawn natively with OpenGL ES 3 (Hands3D.kt) from the same
 * converted signs as the web. Same contract as AingelSigner; calls [onUnavailable] when OpenGL cannot start,
 * so the screen falls back to the 2D hands.
 */
/** Default pace of AINGEL's hands everywhere (1.5×, chosen on 29-10-2026); the translator lets the person slow it down. */
internal const val HANDS_SPEED = 1.5f

@Composable fun AingelHands3D(width: Dp, height: Dp, cx: Dp, cy: Dp, r: Dp, seq: List<String>, playKey: Int, speed: Float = HANDS_SPEED, reducedMotion: Boolean = false,
                              onSign: (Int) -> Unit = {}, onUnavailable: () -> Unit) {
    val signCallback by rememberUpdatedState(onSign)
    val unavailable by rememberUpdatedState(onUnavailable)
    val sequence by rememberUpdatedState(seq)
    var view by remember { mutableStateOf<Hands3DView?>(null) }
    AndroidView(factory = { context -> Hands3DView(context, { signCallback(it) }, { unavailable() }).also { view = it } },
        modifier = Modifier.size(width, height).clearAndSetSemantics { })
    LaunchedEffect(view, width, height, cx, cy, r) { view?.layout(width.value, height.value, cx.value, cy.value, r.value) }
    LaunchedEffect(view, speed, reducedMotion) { view?.setSpeed(speed * (if (reducedMotion) .6f else 1f)) }
    LaunchedEffect(view, playKey) { if (playKey > 0) view?.play(sequence) }
}
