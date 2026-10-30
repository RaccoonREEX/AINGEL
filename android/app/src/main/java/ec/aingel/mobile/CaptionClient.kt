package ec.aingel.mobile

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.*
import okhttp3.*
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicBoolean

data class CaptionTurn(val id: String, val text: String, val final: Boolean)

fun reduceCaption(turns: List<CaptionTurn>, event: JSONObject): List<CaptionTurn> {
    if (event.optString("type") !in setOf("transcript", "speechComplete")) return turns
    val id = event.optString("turnId", "current")
    val existing = turns.find { it.id == id }
    if (existing?.final == true) return turns
    val text = event.optString("transcript").take(12000).ifBlank { existing?.text ?: "" }
    if (text.isBlank()) return turns
    val turn = CaptionTurn(id, text, event.optString("type") == "speechComplete" || event.optBoolean("final"))
    return (turns.filterNot { it.id == id } + turn).takeLast(100)
}

class CaptionClient(private val api: ApiClient, private val scope: CoroutineScope,
    private val onTurns: (List<CaptionTurn>) -> Unit, private val onSpeechStart: (String?) -> Unit, private val onStatus: (String) -> Unit,
    private val onError: (String) -> Unit) {
    private var socket: WebSocket? = null
    private var recorder: AudioRecord? = null
    private var recordingJob: Job? = null
    private val running = AtomicBoolean(false)
    private var turns = emptyList<CaptionTurn>()
    @Volatile private var generation = 0
    private var stopping = false

    @Synchronized
    /** [profileId]: the server checks its sign-up authorization (microphone + Meta). */
    fun start(locale: String, profileId: String, privateTest: Boolean = false) {
        close(); val current = ++generation; stopping = false
        turns = emptyList(); onTurns(turns); onStatus("connecting")
        val request = Request.Builder().url(api.base.replaceFirst("http", "ws") + "ws/captions/")
            .header("Origin", api.base.trimEnd('/')).build()
        socket = api.client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                synchronized(this@CaptionClient) {
                    if (current != generation) { webSocket.cancel(); return }
                    webSocket.send(captionStartPayload(locale, profileId, privateTest).toString())
                }
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                synchronized(this@CaptionClient) {
                    if (current != generation) return
                    try {
                        val event = JSONObject(text)
                        when (event.optString("type")) {
                            "ready" -> record(webSocket, current)
                            "error" -> { onError(event.optString("code", "transcription_unavailable")); close() }
                            "closed" -> close()
                            "speechStart" -> onSpeechStart(event.optString("turnId").ifBlank { null })
                            "transcript", "speechComplete" -> {
                                val updated = reduceCaption(turns, event)
                                if (updated != turns) { turns = updated; onTurns(turns) }
                            }
                        }
                    } catch (_: Exception) { onError("transcription_unavailable"); close() }
                }
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                synchronized(this@CaptionClient) {
                    if (current == generation) { onError("transcription_unavailable"); close() }
                }
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                synchronized(this@CaptionClient) { if (current == generation) close() }
            }
        })
    }

    @Suppress("MissingPermission")
    @Synchronized private fun record(webSocket: WebSocket, current: Int) {
        if (current != generation || stopping) return
        if (!running.compareAndSet(false, true)) return
        recordingJob = scope.launch(Dispatchers.IO) {
            var audio: AudioRecord? = null
            try {
                val minimum = AudioRecord.getMinBufferSize(24000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
                if (minimum <= 0) throw IllegalStateException()
                audio = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, 24000, AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT, maxOf(minimum * 2, 7680))
                if (audio.state != AudioRecord.STATE_INITIALIZED) throw IllegalStateException()
                synchronized(this@CaptionClient) {
                    // A permission result or socket callback may arrive after the screen
                    // was left. Never start recording for a cancelled session.
                    if (!isActive || !running.get() || stopping || current != generation) return@launch
                    recorder = audio; audio.startRecording(); onStatus("recording")
                }
                val buffer = ByteArray(3840)
                val deadline = System.currentTimeMillis() + 9 * 60 * 1000
                while (isActive && running.get() && current == generation && System.currentTimeMillis() < deadline) {
                    val count = audio.read(buffer, 0, buffer.size)
                    if (count <= 0 || !webSocket.send(buffer.toByteString(0, count))) throw IllegalStateException()
                    if (webSocket.queueSize() > 96000) throw IllegalStateException()
                }
                synchronized(this@CaptionClient) { if (current == generation) stop() }
            } catch (_: Exception) {
                synchronized(this@CaptionClient) {
                    if (running.get() && current == generation) { onError("microphone_unavailable"); close() }
                }
            } finally {
                try { audio?.stop() } catch (_: Exception) { }
                audio?.release()
                synchronized(this@CaptionClient) { if (recorder === audio) recorder = null }
            }
        }
    }
    @Synchronized fun stop() {
        if (socket == null || stopping) return
        stopping = true
        val current = generation
        running.set(false)
        try { recorder?.stop() } catch (_: Exception) { }
        recordingJob?.cancel()
        socket?.send("{\"type\":\"stop\"}")
        onStatus("finishing")
        scope.launch {
            delay(31000)
            synchronized(this@CaptionClient) { if (!running.get() && current == generation) close() }
        }
    }
    @Synchronized fun close() {
        ++generation; stopping = true; running.set(false)
        try { recorder?.stop() } catch (_: Exception) { }
        recordingJob?.cancel(); recordingJob = null
        socket?.cancel(); socket = null; onStatus("idle")
    }
}
