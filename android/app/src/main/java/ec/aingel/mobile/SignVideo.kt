package ec.aingel.mobile

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.SurfaceTexture
import android.media.MediaDataSource
import android.media.MediaPlayer
import android.view.Surface
import android.view.TextureView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView

/** The reviewed video stays in memory and is never written to the device filesystem. */
internal class MemoryVideoSource(bytes: ByteArray) : MediaDataSource() {
    private var data: ByteArray? = bytes
    override fun getSize(): Long = data?.size?.toLong() ?: 0
    override fun readAt(position: Long, buffer: ByteArray, offset: Int, size: Int): Int {
        val bytes = data ?: return -1
        if (size == 0) return 0
        if (position < 0 || position >= bytes.size) return -1
        val count = minOf(size, bytes.size - position.toInt())
        System.arraycopy(bytes, position.toInt(), buffer, offset, count)
        return count
    }
    override fun close() { data = null }
}

@Composable internal fun SignVideo(bytes: ByteArray) {
    var surface by remember(bytes) { mutableStateOf<Surface?>(null) }
    var player by remember(bytes) { mutableStateOf<MediaPlayer?>(null) }
    var ready by remember(bytes) { mutableStateOf(false) }
    var playing by remember(bytes) { mutableStateOf(false) }
    var started by remember(bytes) { mutableStateOf(false) }
    var failed by remember(bytes) { mutableStateOf(false) }
    val label = stringResource(R.string.sign_video_description)
    DisposableEffect(bytes) {
        val data = MemoryVideoSource(bytes)
        val media = MediaPlayer()
        player = media
        try {
            media.setVolume(0f, 0f)
            media.setDataSource(data)
            media.setOnPreparedListener { ready = true }
            media.setOnCompletionListener { playing = false }
            media.setOnErrorListener { _, _, _ -> failed = true; playing = false; true }
            media.prepareAsync()
        } catch (_: Exception) { failed = true }
        onDispose {
            media.setOnPreparedListener(null); media.setOnCompletionListener(null); media.setOnErrorListener(null)
            media.release(); data.close(); player = null; ready = false
            surface?.release(); surface = null
        }
    }
    LaunchedEffect(ready, surface, player) {
        val media = player
        val output = surface
        if (media != null && output != null) try {
            media.setSurface(output)
            if (ready && !started) { media.start(); started = true; playing = true }
        } catch (_: Exception) { failed = true; playing = false }
    }
    AndroidView(factory = { context: Context ->
        TextureView(context).apply {
            surfaceTextureListener = object : TextureView.SurfaceTextureListener {
                @SuppressLint("Recycle")  // kept in [surface]; released in onSurfaceTextureDestroyed and onDispose
                override fun onSurfaceTextureAvailable(texture: SurfaceTexture, width: Int, height: Int) { surface = Surface(texture) }
                override fun onSurfaceTextureSizeChanged(texture: SurfaceTexture, width: Int, height: Int) = Unit
                override fun onSurfaceTextureDestroyed(texture: SurfaceTexture): Boolean { surface?.release(); surface = null; return true }
                override fun onSurfaceTextureUpdated(texture: SurfaceTexture) = Unit
            }
        }
    }, modifier = Modifier.fillMaxWidth().height(260.dp).background(Color.Black).semantics { contentDescription = label })
    if (failed) Text(stringResource(R.string.sign_video_error))
    Button(enabled = ready && !failed && surface != null, onClick = {
        try {
            val media = player ?: return@Button
            if (playing) { media.pause(); playing = false }
            else { if (started && media.currentPosition >= media.duration) media.seekTo(0); media.start(); started = true; playing = true }
        } catch (_: Exception) { failed = true; playing = false }
    }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(if (playing) R.string.sign_pause else R.string.sign_play)) }
}
