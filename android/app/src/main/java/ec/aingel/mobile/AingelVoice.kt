package ec.aingel.mobile

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.MediaPlayer
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.io.File
import java.util.Locale
import java.util.concurrent.atomic.AtomicLong

/**
 * AINGEL's voice (system TTS) sent to the output chosen in Ajustes (5b). The platform TTS plays in the engine's
 * own process, so to honour a specific device the phrase is synthesised to a private cache file and played here
 * with setPreferredDevice; with no choice to honour, TTS speaks directly. Platform TTS exposes no samples, so the
 * orb level follows the spoken word ranges, or a gentle pulse while a routed file plays.
 */
class AingelVoice(context: Context, private val onReady: (Boolean) -> Unit = {}) {
    private val app = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    @Volatile var ready = false; private set
    private val pulseAt = AtomicLong(0)
    @Volatile private var pulse = 0f
    private val done = mutableMapOf<String, () -> Unit>()
    private val routes = mutableMapOf<String, AudioDeviceInfo>()
    private var player: MediaPlayer? = null

    init {
        tts = TextToSpeech(app) { status ->
            ready = status == TextToSpeech.SUCCESS
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(id: String?) { if (id?.startsWith("file-") != true) { pulse = .55f; pulseAt.set(System.nanoTime()) } }
                override fun onRangeStart(id: String?, start: Int, end: Int, frame: Int) {
                    if (id?.startsWith("file-") == true) return
                    pulse = (.45f + (end - start) * .06f).coerceAtMost(.95f); pulseAt.set(System.nanoTime())
                }
                override fun onDone(id: String?) { if (id?.startsWith("file-") == true) main.post { play(id) } else finished(id) }
                @Deprecated("Required override") override fun onError(id: String?) = finished(id)
                override fun onStop(id: String?, interrupted: Boolean) = finished(id)
            })
            main.post { onReady(ready) }
        }
    }

    fun level(): Float {
        val at = pulseAt.get(); if (at == 0L) return 0f
        val age = (System.nanoTime() - at) / 1e9f
        return pulse * (1 - age / .32f).coerceAtLeast(0f)
    }
    fun available(locale: Locale) = ready && (tts?.isLanguageAvailable(locale) ?: -1) >= 0

    /** Speaks [text] on the chosen output; [onDone] runs on the main thread. */
    fun speak(text: String, locale: Locale, rate: Float, onDone: (() -> Unit)? = null) {
        stop()
        val engine = tts ?: return
        engine.language = locale; engine.setSpeechRate(rate)
        val target = if (Build.VERSION.SDK_INT >= 28) AudioRoute.speechTarget(app) else null
        val id = (if (target != null) "file-" else "aingel-") + System.nanoTime()
        if (onDone != null) synchronized(done) { done[id] = onDone }
        if (target == null) { engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, id); return }
        synchronized(routes) { routes[id] = target }
        engine.synthesizeToFile(text, null, File(app.cacheDir, "$id.wav"), id)
    }

    private fun play(id: String) {
        val file = File(app.cacheDir, "$id.wav")
        val device = synchronized(routes) { routes.remove(id) }
        if (!file.exists() || device == null) { finished(id); return }
        try {
            player?.release()
            player = MediaPlayer().apply {
                setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                setDataSource(file.path); prepare()
                if (Build.VERSION.SDK_INT >= 28) setPreferredDevice(device)
                setOnCompletionListener { file.delete(); release(); if (player === it) player = null; finished(id) }
                start()
            }
            tickPulse()
        } catch (_: Exception) { file.delete(); finished(id) }
    }
    private fun tickPulse() {
        val p = player ?: return
        if (!try { p.isPlaying } catch (_: Exception) { false }) return
        pulse = .5f + (System.nanoTime() % 7) * .05f; pulseAt.set(System.nanoTime())
        main.postDelayed(::tickPulse, 180)
    }
    private fun finished(id: String?) {
        pulseAt.set(0)
        val callback = synchronized(done) { done.remove(id) }
        if (callback != null) main.post(callback)
    }

    fun stop() {
        synchronized(done) { done.clear() }
        tts?.stop()
        player?.let { try { it.stop() } catch (_: Exception) {}; it.release() }; player = null
        pulseAt.set(0)
    }
    fun shutdown() { stop(); tts?.shutdown(); tts = null; ready = false }
}
