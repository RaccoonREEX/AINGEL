package ec.aingel.mobile

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.net.Uri
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.exifinterface.media.ExifInterface
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

fun jpeg(bitmap: Bitmap): ByteArray {
    val scale = minOf(1f, 1280f / maxOf(bitmap.width, bitmap.height))
    val resized = Bitmap.createScaledBitmap(bitmap, maxOf(1, (bitmap.width * scale).toInt()), maxOf(1, (bitmap.height * scale).toInt()), true)
    return try { ByteArrayOutputStream().use { resized.compress(Bitmap.CompressFormat.JPEG, 88, it); it.toByteArray() } }
        finally { if (resized !== bitmap) resized.recycle() }
}

fun readPhoto(context: Context, uri: Uri): ByteArray {
    val bytes = context.contentResolver.openInputStream(uri)?.use { input ->
        ByteArrayOutputStream().use { output ->
            val buffer = ByteArray(8192)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                if (output.size() + count > 8 * 1024 * 1024) throw ApiFailure("image_too_large")
                output.write(buffer, 0, count)
            }
            output.toByteArray()
        }
    } ?: throw ApiFailure("image_invalid")
    if (bytes.size > 8 * 1024 * 1024) throw ApiFailure("image_too_large")
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
    if (bounds.outWidth <= 0 || bounds.outHeight <= 0 || bounds.outWidth.toLong() * bounds.outHeight > 24_000_000) throw ApiFailure("image_invalid")
    val options = BitmapFactory.Options().apply { inSampleSize = maxOf(1, maxOf(bounds.outWidth, bounds.outHeight) / 1280) }
    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options) ?: throw ApiFailure("image_invalid")
    val orientation = try { ExifInterface(ByteArrayInputStream(bytes)).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL) } catch (_: Exception) { ExifInterface.ORIENTATION_NORMAL }
    val corrected = orientPhoto(bitmap, orientation)
    return try { jpeg(corrected) } finally { if (corrected !== bitmap) corrected.recycle(); bitmap.recycle() }
}

fun orientPhoto(bitmap: Bitmap, orientation: Int): Bitmap {
    val matrix = Matrix().apply {
        when (orientation) {
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> setScale(-1f, 1f)
            ExifInterface.ORIENTATION_ROTATE_180 -> setRotate(180f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> setScale(1f, -1f)
            ExifInterface.ORIENTATION_TRANSPOSE -> { setRotate(90f); postScale(-1f, 1f) }
            ExifInterface.ORIENTATION_ROTATE_90 -> setRotate(90f)
            ExifInterface.ORIENTATION_TRANSVERSE -> { setRotate(-90f); postScale(-1f, 1f) }
            ExifInterface.ORIENTATION_ROTATE_270 -> setRotate(-90f)
        }
    }
    return if (matrix.isIdentity) bitmap else Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
}

fun syntheticPhoto(): ByteArray {
    val bitmap = Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap); canvas.drawColor(Color.WHITE)
    val paint = Paint().apply { color = Color.BLUE }; canvas.drawRect(60f, 150f, 230f, 320f, paint)
    paint.color = Color.RED; canvas.drawCircle(460f, 230f, 80f, paint)
    return jpeg(bitmap).also { bitmap.recycle() }
}

@Composable fun CameraCapture(front: Boolean, onPhoto: (ByteArray) -> Unit, onCancel: () -> Unit, onError: () -> Unit) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val preview = remember { PreviewView(context) }
    val capture = remember { ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build() }
    var provider by remember { mutableStateOf<ProcessCameraProvider?>(null) }
    var ready by remember { mutableStateOf(false) }
    var taking by remember { mutableStateOf(false) }
    DisposableEffect(owner, front) {
        var disposed = false
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            if (!disposed) try {
                provider = future.get()
                val stream = Preview.Builder().build().apply { setSurfaceProvider(preview.surfaceProvider) }
                provider?.bindToLifecycle(owner, if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA, stream, capture)
                ready = true
            } catch (_: Exception) { onError() }
        }, ContextCompat.getMainExecutor(context))
        onDispose { disposed = true; provider?.unbind(capture); provider?.unbindAll() }
    }
    Column {
        Text(stringResource(R.string.camera_active))
        AndroidView(factory = { preview }, modifier = Modifier.fillMaxWidth().height(320.dp))
        Button(enabled = ready && !taking, onClick = {
            taking = true
            capture.takePicture(ContextCompat.getMainExecutor(context), object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    try {
                        val bitmap = image.toBitmap()
                        val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(image.imageInfo.rotationDegrees.toFloat()) }, true)
                        onPhoto(jpeg(rotated))
                        if (rotated !== bitmap) rotated.recycle()
                        bitmap.recycle()
                    } catch (_: Exception) { onError() }
                    finally { image.close(); taking = false }
                }
                override fun onError(exception: ImageCaptureException) { taking = false; onError() }
            })
        }) { Text(stringResource(R.string.capture)) }
        TextButton(onClick = onCancel) { Text(stringResource(R.string.cancel)) }
    }
}
