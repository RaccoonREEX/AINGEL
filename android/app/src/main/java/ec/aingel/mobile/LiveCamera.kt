package ec.aingel.mobile

import android.graphics.Bitmap
import android.graphics.Matrix
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Live camera preview for explicit, one-off captures (3a "AINGEL looks through its eyes" and the
 * sign translator). Bound to the screen's lifecycle and released as soon as it leaves composition;
 * nothing is recorded. [onReady] receives the capture use case once the camera is running.
 */
@Composable fun LiveCamera(front: Boolean, modifier: Modifier = Modifier, onReady: (ImageCapture) -> Unit = {}, onError: () -> Unit) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    // TextureView-backed preview so the orb drawn on top can cut transparent eyes into it.
    val preview = remember { PreviewView(context).apply { implementationMode = PreviewView.ImplementationMode.COMPATIBLE; scaleType = PreviewView.ScaleType.FILL_CENTER } }
    val capture = remember { ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build() }
    DisposableEffect(owner, front) {
        var disposed = false
        var provider: ProcessCameraProvider? = null
        var stream: Preview? = null
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            if (disposed) return@addListener
            try {
                provider = future.get()
                stream = Preview.Builder().build().apply { setSurfaceProvider(preview.surfaceProvider) }
                // Only this view's use cases: unbindAll() would also take the camera from continuous watching.
                provider?.bindToLifecycle(owner, if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA, stream!!, capture)
                onReady(capture)
            } catch (_: Exception) { onError() }
        }, ContextCompat.getMainExecutor(context))
        onDispose { disposed = true; provider?.unbind(capture); stream?.let { provider?.unbind(it) } }
    }
    AndroidView(factory = { preview }, modifier = modifier)
}

/** Full-frame JPEG from the running camera, kept in memory only. */
suspend fun ImageCapture.jpegFrame(context: android.content.Context): ByteArray = suspendCancellableCoroutine { continuation ->
    takePicture(ContextCompat.getMainExecutor(context), object : ImageCapture.OnImageCapturedCallback() {
        override fun onCaptureSuccess(image: ImageProxy) {
            try {
                val bitmap = image.toBitmap()
                val rotated: Bitmap = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(image.imageInfo.rotationDegrees.toFloat()) }, true)
                val bytes = jpeg(rotated)
                if (rotated !== bitmap) rotated.recycle()
                bitmap.recycle()
                if (continuation.isActive) continuation.resume(bytes)
            } catch (e: Exception) { if (continuation.isActive) continuation.resumeWithException(ApiFailure("camera_unavailable")) }
            finally { image.close() }
        }
        override fun onError(exception: ImageCaptureException) { if (continuation.isActive) continuation.resumeWithException(ApiFailure("camera_unavailable")) }
    })
}
