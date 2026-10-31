package ec.aingel.mobile

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.media.MediaMuxer
import androidx.camera.core.ImageProxy
import java.io.File
import java.nio.ByteBuffer

/**
 * Experimental continuous vision with video: the live camera is encoded to H.264 (hardware MediaCodec, ~10 fps,
 * one keyframe per second) and the last [keepSeconds] of encoded samples stay in a bounded ring (about 1 MB). [clip]
 * turns the latest window, starting at a keyframe, into a real MP4 (MediaMuxer), reads it and deletes the file at
 * once: nothing is kept, there is no continuous recording. Clips overlap because the ring is shared (e.g. 6 s every 4 s).
 * Not thread-confined: [feed] runs on the camera analyzer thread, [clip] on a coroutine; the ring is synchronized.
 */
internal class ClipRecorder(private val fps: Int = 10, private val bitrate: Int = 1_000_000, private val keepSeconds: Int = 8) {
    private class Sample(val data: ByteArray, val ptsUs: Long, val key: Boolean)

    private var codec: MediaCodec? = null
    private var format: MediaFormat? = null
    private var width = 0
    private var height = 0
    private var rotation = 0
    private var lastFedUs = Long.MIN_VALUE
    private val ring = ArrayDeque<Sample>()
    private val info = MediaCodec.BufferInfo()
    @Volatile var failed = false
        private set

    /** Encodes one camera frame (throttled to [fps]); the encoder starts with the first frame's size. */
    fun feed(image: ImageProxy) {
        feedFrame(image.width and 1.inv(), image.height and 1.inv(), image.imageInfo.rotationDegrees, image.imageInfo.timestamp / 1000) { copyPlanes(image, it) }
    }

    /**
     * The encoding path shared by the camera and by synthetic test frames: [fill] writes one YUV_420_888 frame into the
     * encoder's input image. [timeoutUs] lets a test wait for an input buffer; the camera never waits.
     */
    internal fun feedFrame(w: Int, h: Int, degrees: Int, ptsUs: Long, timeoutUs: Long = 0, fill: (android.media.Image) -> Unit) {
        if (failed) return
        if (lastFedUs != Long.MIN_VALUE && ptsUs - lastFedUs < 1_000_000L / fps) return
        try {
            val encoder = codec ?: start(w, h, degrees)
            val index = encoder.dequeueInputBuffer(timeoutUs)
            if (index >= 0) {
                val input = encoder.getInputImage(index)
                if (input == null) { encoder.queueInputBuffer(index, 0, 0, ptsUs, 0) } else {
                    fill(input)
                    encoder.queueInputBuffer(index, 0, width * height * 3 / 2, ptsUs, 0)
                    lastFedUs = ptsUs
                }
            }
            drain(encoder)
        } catch (_: Exception) { failed = true; close() }
    }

    private fun start(w: Int, h: Int, degrees: Int): MediaCodec {
        width = w; height = h; rotation = degrees
        val encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
        encoder.configure(MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, w, h).apply {
            setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
            setInteger(MediaFormat.KEY_BIT_RATE, bitrate)
            setInteger(MediaFormat.KEY_FRAME_RATE, fps)
            setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1)
        }, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
        encoder.start()
        codec = encoder
        return encoder
    }

    private fun drain(encoder: MediaCodec) {
        while (true) {
            val index = encoder.dequeueOutputBuffer(info, 0)
            when {
                index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> format = encoder.outputFormat
                index < 0 -> return
                else -> {
                    val buffer = encoder.getOutputBuffer(index)
                    if (buffer != null && info.size > 0 && info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0) {
                        val bytes = ByteArray(info.size)
                        buffer.position(info.offset); buffer.get(bytes)
                        synchronized(ring) {
                            ring.addLast(Sample(bytes, info.presentationTimeUs, info.flags and MediaCodec.BUFFER_FLAG_KEY_FRAME != 0))
                            val oldest = info.presentationTimeUs - keepSeconds * 1_000_000L
                            while (ring.isNotEmpty() && ring.first().ptsUs < oldest) ring.removeFirst()
                        }
                    }
                    encoder.releaseOutputBuffer(index, false)
                }
            }
        }
    }

    /** The latest [seconds] as an MP4 starting at a keyframe, or null while there are fewer than [minSeconds]. */
    fun clip(seconds: Double, minSeconds: Double, cacheDir: File): ByteArray? {
        val outputFormat = format ?: return null
        val samples = synchronized(ring) {
            val end = ring.lastOrNull()?.ptsUs ?: return null
            val from = end - (seconds * 1_000_000).toLong()
            val start = ring.indexOfFirst { it.key && it.ptsUs >= from }.takeIf { it >= 0 } ?: return null
            ring.drop(start)
        }
        val span = (samples.last().ptsUs - samples.first().ptsUs) / 1_000_000.0
        if (span < minSeconds) return null
        val file = File.createTempFile("aingel-clip", ".mp4", cacheDir)
        try {
            val muxer = MediaMuxer(file.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
            try {
                muxer.setOrientationHint(rotation)
                val track = muxer.addTrack(outputFormat)
                muxer.start()
                val base = samples.first().ptsUs
                val info = MediaCodec.BufferInfo()
                for (sample in samples) {
                    info.set(0, sample.data.size, sample.ptsUs - base, if (sample.key) MediaCodec.BUFFER_FLAG_KEY_FRAME else 0)
                    muxer.writeSampleData(track, ByteBuffer.wrap(sample.data), info)
                }
                muxer.stop()
            } finally { muxer.release() }
            return file.readBytes()
        } finally { file.delete() }  // the clip lives only in memory, for one upload
    }

    fun close() {
        try { codec?.stop() } catch (_: Exception) {}
        try { codec?.release() } catch (_: Exception) {}
        codec = null
        synchronized(ring) { ring.clear() }
    }

    /** YUV_420_888 camera planes into the encoder's YUV_420_888 input image, honouring both strides. */
    private fun copyPlanes(source: ImageProxy, target: android.media.Image) {
        for (p in 0 until 3) {
            val src = source.planes[p]; val dst = target.planes[p]
            val w = if (p == 0) width else width / 2; val h = if (p == 0) height else height / 2
            val s = src.buffer; val d = dst.buffer
            if (src.pixelStride == 1 && dst.pixelStride == 1) {
                val row = ByteArray(w)
                for (y in 0 until h) { s.position(y * src.rowStride); s.get(row, 0, w); d.position(y * dst.rowStride); d.put(row, 0, w) }
            } else for (y in 0 until h) for (x in 0 until w) {
                d.put(y * dst.rowStride + x * dst.pixelStride, s.get(y * src.rowStride + x * src.pixelStride))
            }
        }
    }
}
