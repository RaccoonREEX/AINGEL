package ec.aingel.mobile

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * 6b · Galaxy Z Flip outer screen while «Vigilancia continua» runs: when the phone is closed, AINGEL stays visible
 * there — only the dark orb on black, over the lock screen, no text and no personal data. It speaks with the
 * descriptions, and a tap repeats the last one. It closes when the phone is opened or watching stops.
 * Opened by WatchService on the outer display (Android lets a background service do it with «Mostrar sobre otras apps»).
 */
class WatchCoverActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (android.os.Build.VERSION.SDK_INT >= 27) { setShowWhenLocked(true); setTurnScreenOn(true) }
        // Pure black around a small orb: on AMOLED almost every pixel is off while it stays visible.
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContent {
            val status by WatchState.status.collectAsStateWithLifecycle()
            LaunchedEffect(status.running) { if (!status.running) finish() }
            val state = when { status.speaking -> AingelOrbState.SPEAKING; status.looking -> AingelOrbState.THINKING; else -> AingelOrbState.IDLE }
            CoverOrb(state, reduced = false, status = status.line.ifBlank { stringResource(R.string.ui_m_watch) }, level = { if (status.speaking) .45f else 0f }) {
                WatchService.repeat(this)
            }
        }
    }

    // Opening the phone (or turning the screen off) leaves the outer screen: the normal app takes over.
    override fun onStop() { super.onStop(); if (!isChangingConfigurations) finish() }
}
