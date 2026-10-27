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
    private val onTurns: (List<CaptionTurn>) -> Unit, private val onStatus: (String) -> Unit,
    private val onError: (String) -> Unit) {
    private var socket: WebSocket? = null
    private var recorder: AudioRecord? = null
    private var recordingJob: Job? = null
    private val running = AtomicBoolean(false)
    private var turns = emptyList<CaptionTurn>()
    private var generation = 0

    fun start(locale: String) {
        close(); val current = ++generation
        turns = emptyList(); onTurns(turns); onStatus("connecting")
        val request = Request.Builder().url(api.base.replaceFirst("http", "ws") + "ws/captions/")
            .header("Origin", api.base.trimEnd('/')).build()
        socket = api.client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                if (current != generation) { webSocket.cancel(); return }
                webSocket.send(JSONObject().put("type", "start").put("locale", locale).put("synthetic", true).toString())
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (current != generation) return
                try {
                    val event = JSONObject(text)
                    when (event.optString("type")) {
                        "ready" -> record(webSocket, current)
                        "error" -> { onError(event.optString("code", "transcription_unavailable")); close() }
                        "closed" -> close()
                        else -> { turns = reduceCaption(turns, event); onTurns(turns) }
                    }
                } catch (_: Exception) { onError("transcription_unavailable"); close() }
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (current == generation) { onError("transcription_unavailable"); close() }
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { if (current == generation) close() }
        })
    }

    @Suppress("MissingPermission")
    private fun record(webSocket: WebSocket, current: Int) {
        if (!running.compareAndSet(false, true)) return
        recordingJob = scope.launch(Dispatchers.IO) {
            var audio: AudioRecord? = null
            try {
                val minimum = AudioRecord.getMinBufferSize(24000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
                if (minimum <= 0) throw IllegalStateException()
                audio = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, 24000, AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT, maxOf(minimum * 2, 7680))
                if (audio.state != AudioRecord.STATE_INITIALIZED) throw IllegalStateException()
                recorder = audio; audio.startRecording(); onStatus("recording")
                val buffer = ByteArray(3840)
                val deadline = System.currentTimeMillis() + 9 * 60 * 1000
                while (isActive && running.get() && current == generation && System.currentTimeMillis() < deadline) {
                    val count = audio.read(buffer, 0, buffer.size)
                    if (count <= 0 || !webSocket.send(buffer.toByteString(0, count))) throw IllegalStateException()
                    if (webSocket.queueSize() > 96000) throw IllegalStateException()
                }
                if (current == generation) stop()
            } catch (_: Exception) {
                if (running.get() && current == generation) { onError("microphone_unavailable"); close() }
            } finally {
                try { audio?.stop() } catch (_: Exception) { }
                audio?.release()
                if (recorder === audio) recorder = null
            }
        }
    }
    fun stop() {
        if (socket == null) return
        val current = generation
        running.set(false)
        try { recorder?.stop() } catch (_: Exception) { }
        recordingJob?.cancel()
        socket?.send("{\"type\":\"stop\"}")
        onStatus("finishing")
        scope.launch { delay(31000); if (!running.get() && current == generation) close() }
    }
    fun close() {
        ++generation; running.set(false)
        try { recorder?.stop() } catch (_: Exception) { }
        recordingJob?.cancel(); recordingJob = null
        socket?.cancel(); socket = null; onStatus("idle")
    }
}
