package ec.aingel.mobile

import kotlin.math.abs

/**
 * On-device «did the scene change?» for continuous watching. The camera is looked at several times a second here,
 * for free; a photo goes to Meta only when the scene changed since the last one described.
 * A frame is reduced to a 16×12 grid of average brightness. Comparing grids ignores an overall exposure shift
 * (auto-exposure, a cloud) and counts the cells that changed on their own: someone coming in, the phone turning.
 */
internal object WatchChange {
    const val COLS = 16
    const val ROWS = 12
    /** A cell changed when its brightness moved this much (0–255) beyond the overall shift. */
    const val CELL_DIFF = 24
    /** Share of changed cells that counts as a new scene (about 15 of 192 cells: a person entering the frame). */
    const val CHANGED_SHARE = 0.08
    /** The whole picture got this much brighter or darker: lights on or off. */
    const val LIGHT_SHIFT = 40.0
}

/** Average brightness per grid cell of a luminance (Y) plane, sampling every 4th pixel. */
internal fun lumaGrid(y: ByteArray, rowStride: Int, width: Int, height: Int, cols: Int = WatchChange.COLS, rows: Int = WatchChange.ROWS): IntArray {
    val sums = LongArray(cols * rows)
    val counts = IntArray(cols * rows)
    var row = 0
    while (row < height) {
        val cellRow = row * rows / height
        var col = 0
        while (col < width) {
            val index = row * rowStride + col
            if (index < y.size) {
                val cell = cellRow * cols + col * cols / width
                sums[cell] += (y[index].toInt() and 0xFF).toLong(); counts[cell]++
            }
            col += 4
        }
        row += 4
    }
    return IntArray(cols * rows) { if (counts[it] == 0) 0 else (sums[it] / counts[it]).toInt() }
}

internal fun sceneChanged(before: IntArray, now: IntArray): Boolean {
    if (before.size != now.size || before.isEmpty()) return true
    val shift = now.average() - before.average()
    if (abs(shift) > WatchChange.LIGHT_SHIFT) return true
    val moved = before.indices.count { abs(now[it] - before[it] - shift) > WatchChange.CELL_DIFF }
    return moved >= before.size * WatchChange.CHANGED_SHARE
}
