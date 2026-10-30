package ec.aingel.mobile

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.os.Build
import android.os.PowerManager
import android.app.ActivityOptions
import android.hardware.display.DisplayManager
import android.view.Display
import android.os.SystemClock
import android.provider.Settings
import android.view.Gravity
import android.view.MotionEvent
import android.view.WindowManager
import android.widget.ImageView
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.Locale
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/** One ApiClient for the app and its services, so the signed-in session is shared. */
object Backend {
    @Volatile private var client: ApiClient? = null
    fun api(context: Context): ApiClient = client ?: synchronized(this) { client ?: ApiClient(context.applicationContext).also { client = it } }
}

/** What the home screen shows about continuous watching while the service runs. */
object WatchState {
    /** [speaking]: AINGEL is saying a description; [looking]: a photo is being described (the outer-screen orb follows both). */
    data class Status(val running: Boolean = false, val line: String = "", val mock: Boolean = false, val speaking: Boolean = false, val looking: Boolean = false)
    private val mutable = MutableStateFlow(Status())
    val status = mutable.asStateFlow()
    internal fun set(status: Status) { mutable.value = status }
    internal fun change(edit: (Status) -> Status) { mutable.value = edit(mutable.value) }
}

/**
 * 5a · «Vigilancia continua» for the blind profile: a camera foreground service that watches the rear camera live on
 * the phone (WatchChange) and describes aloud only when the scene changes, at most once every 4 s and never over its
 * own voice, with a permanent notification (last description, «Detener») and,
 * if the person allowed it, a floating AINGEL bubble. It keeps running with the screen locked.
 * Images go to the scene endpoint only; the server sends them to Meta only in its "meta" mode and with the
 * authorization given at sign-up (camera + Meta), and never stores them. In test mode nothing is analysed and it says so once.
 */
class WatchService : LifecycleService() {
    companion object {
        private const val CHANNEL = "aingel_watch"
        private const val NOTIFICATION = 7101
        private const val ACTION_STOP = "ec.aingel.mobile.WATCH_STOP"
        private const val ACTION_REPEAT = "ec.aingel.mobile.WATCH_REPEAT"
        /** Least time between two photos sent to be described, even if everything keeps changing. */
        const val MIN_GAP_MS = 4_000L
        /** Extra wait after a failed description, so a server outage is not hammered. */
        const val RETRY_MS = 6_000L
        /** How often the live view is reduced to a grid (cheap, on the phone). */
        const val LOOK_MS = 300L
        const val TICK_MS = 250L
        const val NAME_AGAIN_MS = 3 * 60_000L

        fun start(context: Context, profileId: String, locale: String, privateTest: Boolean = false) {
            val intent = Intent(context, WatchService::class.java).putExtra("profile", profileId).putExtra("locale", locale).putExtra("private_test", privateTest)
            ContextCompat.startForegroundService(context, intent)
        }
        /** Only when it runs: starting the service just to stop it would be pointless. */
        fun stop(context: Context) { if (WatchState.status.value.running) context.startService(Intent(context, WatchService::class.java).setAction(ACTION_STOP)) }
        /** Says the last description again (tap on the outer-screen orb). */
        fun repeat(context: Context) { if (WatchState.status.value.running) context.startService(Intent(context, WatchService::class.java).setAction(ACTION_REPEAT)) }
    }

    private var voice: AingelVoice? = null
    private var loop: Job? = null
    private var capture: ImageCapture? = null
    private var analysis: ImageAnalysis? = null
    private var analyzer: ExecutorService? = null
    /** Latest grid of the live view (WatchChange), written by the analyzer thread. */
    @Volatile private var latest: IntArray? = null
    /** AINGEL is speaking until then (cleared when the voice finishes; bounded if the engine never reports it). */
    @Volatile private var speakingUntil = 0L
    private var wake: PowerManager.WakeLock? = null
    private var bubble: ImageView? = null
    private var locale = "es-EC"
    private var privateTest = false
    private val spanish get() = locale != "en-US"
    private fun text(es: String, en: String) = if (spanish) es else en

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        if (intent?.action == ACTION_STOP) { stopSelf(); return START_NOT_STICKY }
        if (intent?.action == ACTION_REPEAT) { WatchState.status.value.line.takeIf { it.isNotBlank() }?.let { say(it) }; return START_NOT_STICKY }
        if (loop != null) return START_NOT_STICKY
        val profile = intent?.getStringExtra("profile")
        if (profile.isNullOrBlank()) { stopSelf(); return START_NOT_STICKY }
        locale = intent.getStringExtra("locale") ?: "es-EC"
        privateTest = intent.getBooleanExtra("private_test", false)
        val first = text("Te acompaño. Te avisaré de lo que vea.", "I'm with you. I'll tell you what I see.")
        val notification = notification(first)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) startForeground(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)
        else startForeground(NOTIFICATION, notification)
        WatchState.set(WatchState.Status(running = true, line = first))
        wake = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "aingel:watch").apply { setReferenceCounted(false); acquire(4 * 60 * 60 * 1000L) }
        // Same voice and output (Ajustes · Voz de AINGEL) as the app.
        voice = AingelVoice(this) { ok -> if (ok) say(text("Vigilancia continua activada. Te avisaré de lo que vea.", "Continuous watching is on. I'll tell you what I see.")) }
        showBubble()
        // Closing the phone (main display off, outer display on) shows AINGEL on the outer screen.
        getSystemService(DisplayManager::class.java).registerDisplayListener(folds, null)
        bindCamera()
        loop = lifecycleScope.launch { describeLoop(profile) }
        return START_NOT_STICKY
    }

    private fun bindCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                val provider = future.get()
                val use = ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build()
                val live = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
                val executor = Executors.newSingleThreadExecutor().also { analyzer = it }
                var looked = 0L
                live.setAnalyzer(executor) { image ->
                    try {
                        val now = SystemClock.elapsedRealtime()
                        if (now - looked >= LOOK_MS) {
                            looked = now
                            val plane = image.planes[0]
                            val bytes = ByteArray(plane.buffer.remaining()).also { plane.buffer.get(it) }
                            latest = lumaGrid(bytes, plane.rowStride, image.width, image.height)
                        }
                    } finally { image.close() }
                }
                // Only its own use cases: the app's camera keeps working; whichever became active last uses the camera.
                provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, use, live)
                capture = use; analysis = live
            } catch (e: Exception) {
                update(text("No se pudo abrir la cámara.", "Couldn't open the camera."), speak = true); stopSelf()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private suspend fun describeLoop(profile: String) {
        delay(1_500)  // camera opening and exposure settling
        var saidMock = false
        var described: IntArray? = null  // grid of the last scene sent to be described
        var sentAt = 0L
        val announced = mutableMapOf<String, Long>()  // family member id → when AINGEL last said who it is
        while (lifecycleScope.isActive) {
            val use = capture
            val grid = latest
            val now = SystemClock.elapsedRealtime()
            val seen = described
            if (use != null && grid != null && now >= speakingUntil && now - sentAt >= MIN_GAP_MS && (seen == null || sceneChanged(seen, grid))) {
                described = grid; sentAt = now
                WatchState.change { it.copy(looking = true) }
                try {
                    val fields = mutableMapOf("locale" to locale, "profile" to profile)
                    if (privateTest) { fields["private_test"] = "true"; fields["synthetic"] = "false" } else fields["family"] = "true"
                    val result = Backend.api(this).upload("scene/", use.jpegFrame(this), fields)
                    val mock = result.optString("mode") == "mock"
                    val clock = System.currentTimeMillis()
                    // Who it is is said when the person appears, not on every capture while they stay.
                    val recent = announced.filterValues { clock - it < NAME_AGAIN_MS }.keys
                    knownPeople(result, recent).forEach { (id, _) -> announced[id] = clock }
                    val line = withKnownPeople(result, result.optString("text"), recent).ifBlank { text("No pude describir la imagen.", "I couldn't describe the image.") }
                    if (mock) {
                        // Test server: nothing was analysed. Say it once, then keep the notification honest.
                        update(text("Modo de prueba: este servidor no analiza imágenes.", "Test mode: this server does not analyse images."), speak = !saidMock, mock = true); saidMock = true
                    } else update(line, speak = true)
                } catch (e: ApiFailure) {
                    if (e.code == "privacy_review_required") {
                        update(getString(R.string.private_test_server_denied), speak = true); stopSelf(); return
                    }
                    update(text("No pude describir ahora. Lo intento de nuevo.", "I couldn't describe right now. Trying again."), speak = false)
                    described = null; sentAt = now + RETRY_MS
                } catch (_: Exception) {
                    update(text("No pude describir ahora. Lo intento de nuevo.", "I couldn't describe right now. Trying again."), speak = false)
                    described = null; sentAt = now + RETRY_MS
                }
            }
            WatchState.change { it.copy(looking = false) }
            delay(TICK_MS)
        }
    }

    private var onCover = false
    private val folds = object : DisplayManager.DisplayListener {
        override fun onDisplayAdded(displayId: Int) = checkFold(displayId)
        override fun onDisplayRemoved(displayId: Int) {}
        override fun onDisplayChanged(displayId: Int) = checkFold(displayId)
    }
    private fun checkFold(displayId: Int) {
        val displays = getSystemService(DisplayManager::class.java)
        val main = displays.getDisplay(Display.DEFAULT_DISPLAY)
        val other = displays.getDisplay(displayId)?.takeIf { displayId != Display.DEFAULT_DISPLAY }
        val folded = main?.state == Display.STATE_OFF && other != null && other.state != Display.STATE_OFF
        if (folded && !onCover) { onCover = true; showOnCover(displayId) }
        else if (main?.state == Display.STATE_ON) onCover = false
    }
    /** Android lets a background service open a screen only with «Mostrar sobre otras apps»; without it, the notification stays. */
    private fun showOnCover(displayId: Int) {
        if (!Settings.canDrawOverlays(this)) return
        try {
            startActivity(Intent(this, WatchCoverActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                ActivityOptions.makeBasic().setLaunchDisplayId(displayId).toBundle())
        } catch (_: Exception) {}
    }

    private fun update(line: String, speak: Boolean, mock: Boolean = false) {
        WatchState.change { it.copy(running = true, line = line, mock = mock) }
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION, notification(line))
        if (speak) say(line)
    }
    private fun say(line: String) {
        val v = voice?.takeIf { it.ready } ?: return
        speakingUntil = SystemClock.elapsedRealtime() + 30_000
        WatchState.change { it.copy(speaking = true) }
        v.speak(line, Locale.forLanguageTag(locale), 1f) { speakingUntil = 0L; WatchState.change { it.copy(speaking = false) } }
    }

    private fun notification(line: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && manager.getNotificationChannel(CHANNEL) == null)
            manager.createNotificationChannel(NotificationChannel(CHANNEL, text("Vigilancia continua", "Continuous watching"), NotificationManager.IMPORTANCE_LOW).apply { setShowBadge(false) })
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, WatchService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_aingel)
            .setContentTitle(text("AINGEL · Vigilancia continua", "AINGEL · Continuous watching"))
            .setContentText(line).setStyle(NotificationCompat.BigTextStyle().bigText(line + "\n" + text("Salida: ", "Output: ") + AudioRoute.outputLabel(this)))
            .setOngoing(true).setOnlyAlertOnce(true).setSilent(true).setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC).setContentIntent(open)
            .addAction(0, text("Detener", "Stop"), stop)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }

    /** Floating AINGEL bubble (tap = back to the app), only if the person allowed «display over other apps». */
    @SuppressLint("ClickableViewAccessibility")
    private fun showBubble() {
        if (!Settings.canDrawOverlays(this) || bubble != null) return
        val size = (64 * resources.displayMetrics.density).toInt()
        val wm = getSystemService(WINDOW_SERVICE) as WindowManager
        val params = WindowManager.LayoutParams(size, size,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, PixelFormat.TRANSLUCENT).apply { gravity = Gravity.END or Gravity.CENTER_VERTICAL; x = (10 * resources.displayMetrics.density).toInt() }
        val view = ImageView(this).apply {
            setImageResource(R.drawable.ic_aingel); setBackgroundResource(R.drawable.watch_bubble); val p = size / 6; setPadding(p, p, p, p)
            contentDescription = text("Abrir AINGEL", "Open AINGEL"); elevation = 8 * resources.displayMetrics.density
            var downY = 0f; var startY = 0
            setOnTouchListener { _, e ->
                when (e.action) {
                    MotionEvent.ACTION_DOWN -> { downY = e.rawY; startY = params.y; true }
                    MotionEvent.ACTION_MOVE -> { params.y = startY + (e.rawY - downY).toInt(); wm.updateViewLayout(this, params); true }
                    MotionEvent.ACTION_UP -> { if (kotlin.math.abs(e.rawY - downY) < 12) startActivity(Intent(this@WatchService, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)); true }
                    else -> false
                }
            }
        }
        try { wm.addView(view, params); bubble = view } catch (_: Exception) {}
    }

    override fun onDestroy() {
        loop?.cancel(); loop = null
        try { getSystemService(DisplayManager::class.java).unregisterDisplayListener(folds) } catch (_: Exception) {}
        bubble?.let { try { (getSystemService(WINDOW_SERVICE) as WindowManager).removeView(it) } catch (_: Exception) {} }; bubble = null
        try { ProcessCameraProvider.getInstance(this).get().unbind(*listOfNotNull(capture, analysis).toTypedArray()) } catch (_: Exception) {}
        analyzer?.shutdown(); analyzer = null
        voice?.shutdown(); voice = null
        wake?.let { if (it.isHeld) it.release() }; wake = null
        WatchState.set(WatchState.Status())
        super.onDestroy()
    }
}
