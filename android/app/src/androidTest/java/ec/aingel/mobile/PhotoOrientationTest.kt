package ec.aingel.mobile

import android.graphics.Bitmap
import android.graphics.Color
import androidx.exifinterface.media.ExifInterface
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PhotoOrientationTest {
    @Test fun rotateAndMirrorGalleryPhotosBeforeStrippingMetadata() {
        val original = Bitmap.createBitmap(2, 3, Bitmap.Config.ARGB_8888)
        original.eraseColor(Color.WHITE); original.setPixel(0, 0, Color.RED)
        val cases = listOf(
            Triple(ExifInterface.ORIENTATION_NORMAL, 2 to 3, 0 to 0),
            Triple(ExifInterface.ORIENTATION_FLIP_HORIZONTAL, 2 to 3, 1 to 0),
            Triple(ExifInterface.ORIENTATION_ROTATE_180, 2 to 3, 1 to 2),
            Triple(ExifInterface.ORIENTATION_FLIP_VERTICAL, 2 to 3, 0 to 2),
            Triple(ExifInterface.ORIENTATION_TRANSPOSE, 3 to 2, 0 to 0),
            Triple(ExifInterface.ORIENTATION_ROTATE_90, 3 to 2, 2 to 0),
            Triple(ExifInterface.ORIENTATION_TRANSVERSE, 3 to 2, 2 to 1),
            Triple(ExifInterface.ORIENTATION_ROTATE_270, 3 to 2, 0 to 1))
        cases.forEach { (orientation, size, red) ->
            val result = orientPhoto(original, orientation)
            assertEquals(size.first, result.width); assertEquals(size.second, result.height)
            assertEquals(Color.RED, result.getPixel(red.first, red.second))
            if (result !== original) result.recycle()
        }
        original.recycle()
    }
}
