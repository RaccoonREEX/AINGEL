package ec.aingel.mobile

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlin.math.pow
import kotlin.math.sqrt

/** Same mapping as the web: noise gate 0.02, curve 0.65, clamp 0..1 (attack/release live in the orb). */
internal fun shapeLevel(rms: Float): Float = if (rms < 0.02f) 0f else (rms * 5).coerceAtMost(1f).pow(0.65f)

/** SpeechRecognizer reports loudness in dB (about -2..10); map it onto the RMS scale used by [shapeLevel]. */
/** Android's answer when a session starts right after another one closed (or another screen still holds the
 * microphone): trying again shortly works, so it is not «this phone cannot recognize speech». */
@SuppressLint("InlinedApi")  // compile-time int: before API 31 the recognizer never reports it, so the comparison is just false
internal fun transientRecognizerError(error: Int) = error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY ||
    error == SpeechRecognizer.ERROR_CLIENT || error == SpeechRecognizer.ERROR_SERVER_DISCONNECTED

internal fun recognizerLevel(rmsDb: Float): Float = shapeLevel(((rmsDb + 2f) / 12f).coerceIn(0f, 1f) * 0.2f)

internal fun pcmLevel(buffer: ShortArray, count: Int): Float {
    if (count <= 0) return 0f
    var sum = 0.0
    for (i in 0 until count) { val v = buffer[i] / 32768.0; sum += v * v }
    return shapeLevel(sqrt(sum / count).toFloat())
}

/**
 * Microphone input for the assistant. Uses the platform recogniser for text and its RMS callback for
 * the orb level, so the microphone is opened once. When no recogniser is installed, an AudioRecord
 * meter drives the orb and the screen asks the person to type. Nothing is recorded or stored.
 * The phone's on-device recogniser is preferred (Android 12+); otherwise the system's recogniser may send the voice
 * to its vendor, so it is used only when the signed-in account accepted that ([accepted], from its session payload).
 */
class VoiceInput(private val context: Context, private val accepted: () -> Boolean = { false }) {
    @Volatile private var level = 0f
    private var recognizer: SpeechRecognizer? = null
    private var session = 0
    private var meter: Thread? = null
    @Volatile private var metering = false
    companion object {
        /** The phone's on-device recogniser lacked the language (e.g. no es-EC pack): remembered for the whole app, so
         * no screen tries it again; the system's recogniser (and the account's acceptance) is used instead. */
        @Volatile private var deviceFailed = false
    }
    private val onDevice: Boolean get() = !deviceFailed && Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(context)
    val recognitionAvailable: Boolean get() = onDevice || SpeechRecognizer.isRecognitionAvailable(context)
    /** "device", "service" or "ask" ([recognitionMode]) for the account signed in now. */
    fun mode(): String = recognitionMode(onDevice, accepted())
    /** Listening would use the system's speech service, which this account has not accepted: ask first, or type. */
    fun needsAcceptance(): Boolean = mode() == "ask" && SpeechRecognizer.isRecognitionAvailable(context)
    fun level(): Float = level

    /** Headset chosen in Ajustes (5b): asked for as the communication device while listening (Android 12+). */
    private var routed = false
    private fun routeMicrophone() {
        if (android.os.Build.VERSION.SDK_INT < 31) return
        val device = AudioRoute.inputDevice(context).takeIf { it.key != AudioRoute.DEFAULT }?.info ?: return
        val am = context.getSystemService(android.media.AudioManager::class.java)
        routed = am.availableCommunicationDevices.firstOrNull { it.id == device.id || it.productName == device.productName && it.type == device.type }?.let { am.setCommunicationDevice(it) } == true
    }
    private fun releaseMicrophone() {
        if (routed && android.os.Build.VERSION.SDK_INT >= 31) context.getSystemService(android.media.AudioManager::class.java).clearCommunicationDevice()
        routed = false
    }

    /** Starts a session and returns its number, so a caller can later stop only its own ([stopIf]). */
    fun start(locale: String, onPartial: (String) -> Unit, onResult: (String) -> Unit, onFailure: (Int) -> Unit): Int {
        stop()
        val id = ++session
        listen(id, locale, onPartial, onResult, onFailure)
        return id
    }

    /**
     * One listening attempt within session [id]. If the on-device recogniser lacks the language it is not reported as a
     * failure: the same session goes on at once with the system's recogniser, which needs this account's acceptance
     * (ERROR_INSUFFICIENT_PERMISSIONS without it, so the screen offers it, or typing).
     */
    @SuppressLint("InlinedApi")  // the language errors exist from API 31, the only versions with an on-device recogniser
    private fun listen(id: Int, locale: String, onPartial: (String) -> Unit, onResult: (String) -> Unit, onFailure: (Int) -> Unit) {
        val mode = mode()
        // Callers ask first; never the vendor's service without this account's acceptance.
        if (mode == "ask" && SpeechRecognizer.isRecognitionAvailable(context)) { onFailure(SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS); return }
        routeMicrophone()
        if (!recognitionAvailable) { startMeter(); return }
        val device = mode == "device"
        val engine = if (device && Build.VERSION.SDK_INT >= 31) SpeechRecognizer.createOnDeviceSpeechRecognizer(context) else SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = engine
        engine.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) { level = recognizerLevel(rmsdB) }
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() { level = 0f }
            override fun onError(error: Int) {
                level = 0f
                android.util.Log.i("AINGEL-voice", "recognizer error=$error device=$device")  // the code only, never content
                // The on-device recogniser failing for any reason other than silence (a missing language pack is
                // reported in several ways) means the system's recogniser is used from now on, as before.
                if (device && error != SpeechRecognizer.ERROR_NO_MATCH && error != SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
                    deviceFailed = true
                    // Not the person's problem: retry right away with the system's recogniser (after this callback).
                    if (recognizer === engine) Handler(Looper.getMainLooper()).post {
                        if (session == id && recognizer === engine) { recognizer = null; engine.destroy(); listen(id, locale, onPartial, onResult, onFailure) }
                    }
                    return
                }
                if (recognizer === engine) onFailure(error)
            }
            override fun onResults(results: Bundle?) {
                level = 0f
                if (recognizer === engine) onResult(results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty())
            }
            override fun onPartialResults(partial: Bundle?) {
                partial?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let(onPartial)
            }
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        engine.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, locale)
            // Offline only with the on-device recogniser. Forcing it on the system's recogniser made it demand an offline
            // language pack the phone may not have (es-EC on the Flip 4: error 12), so voice stopped working.
            .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, device)
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1))
    }

    /** Stops the microphone only if session [id] is still the one listening (a newer one may have started). */
    fun stopIf(id: Int) { if (id == session) stop() }

    /** Ask the recogniser for its final result now (the person tapped to finish). */
    fun finish() { recognizer?.stopListening(); stopMeter() }

    fun stop() {
        releaseMicrophone()
        recognizer?.let { it.cancel(); it.destroy() }
        recognizer = null
        stopMeter()
        level = 0f
    }

    @SuppressLint("MissingPermission") // The caller requests RECORD_AUDIO right before starting.
    private fun startMeter() {
        val rate = 16000
        val size = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT).coerceAtLeast(2048)
        metering = true
        meter = Thread {
            val record = try { AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, size) } catch (_: Exception) { null }
            if (record == null || record.state != AudioRecord.STATE_INITIALIZED) { record?.release(); return@Thread }
            val buffer = ShortArray(1024)
            try {
                record.startRecording()
                while (metering) { val read = record.read(buffer, 0, buffer.size); if (read > 0) level = pcmLevel(buffer, read) }
            } finally { record.stop(); record.release(); level = 0f }
        }.apply { isDaemon = true; start() }
    }

    private fun stopMeter() { metering = false; meter = null }
}
