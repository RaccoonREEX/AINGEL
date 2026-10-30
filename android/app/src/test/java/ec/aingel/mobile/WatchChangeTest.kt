package ec.aingel.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class WatchChangeTest {
    private val w = 640
    private val h = 480

    /** A room: a gradient wall with a little sensor noise. */
    private fun room(seed: Int, brightness: Int = 0) = ByteArray(w * h) { i ->
        val x = i % w; val y = i / w
        (60 + x / 8 + y / 12 + brightness + Random(seed * 31 + i).nextInt(-6, 7)).coerceIn(0, 255).toByte()
    }

    /** Someone standing in the middle third of the frame. */
    private fun withPerson(frame: ByteArray) = frame.copyOf().also { f ->
        for (y in 120 until 480) for (x in 250 until 400) f[y * w + x] = 20
    }

    private fun grid(frame: ByteArray) = lumaGrid(frame, w, w, h)

    @Test fun gridHasOneAveragePerCell() {
        val g = lumaGrid(ByteArray(w * h) { 100 }, w, w, h)
        assertEquals(WatchChange.COLS * WatchChange.ROWS, g.size)
        assertTrue(g.all { it == 100 })
    }

    @Test fun sameRoomWithNoiseOrExposureDriftIsNotANewScene() {
        val before = grid(room(1))
        assertFalse(sceneChanged(before, grid(room(2))))
        assertFalse(sceneChanged(before, grid(room(3, brightness = 25))))  // auto-exposure
    }

    @Test fun someoneComingInOrTheLightsGoingOffIs() {
        val before = grid(room(1))
        assertTrue(sceneChanged(before, grid(withPerson(room(2)))))
        assertTrue(sceneChanged(before, grid(ByteArray(w * h) { 5 })))
        assertTrue(sceneChanged(IntArray(0), before))
    }

    @Test fun rowPaddingIsSkipped() {
        val stride = w + 64
        val padded = ByteArray(stride * h) { i -> if (i % stride >= w) 0 else 100 }
        assertTrue(lumaGrid(padded, stride, w, h).all { it == 100 })
    }
}
