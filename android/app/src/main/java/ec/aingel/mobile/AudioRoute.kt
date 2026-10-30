package ec.aingel.mobile

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager

/*
 * 5b · Where AINGEL's voice comes out and which microphone it listens with. The choice is a device type
 * (phone speaker / Bluetooth / wired) kept on this phone, so it survives reconnecting the headset.
 */
object AudioRoute {
    data class Device(val key: String, val label: String, val sub: String, val bluetooth: Boolean, val info: AudioDeviceInfo?)
    private const val PREFS = "aingel-audio"
    const val DEFAULT = "default"

    private val BT_OUT = setOf(AudioDeviceInfo.TYPE_BLUETOOTH_A2DP, AudioDeviceInfo.TYPE_BLUETOOTH_SCO, 26 /* BLE_HEADSET */, 27 /* BLE_SPEAKER */, 30 /* BLE_BROADCAST */)
    private val BT_IN = setOf(AudioDeviceInfo.TYPE_BLUETOOTH_SCO, 26 /* BLE_HEADSET */)
    private val WIRED = setOf(AudioDeviceInfo.TYPE_WIRED_HEADSET, AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_USB_HEADSET)

    /** Language of the labels; the app sets it from the profile (es-EC / en-US). */
    @Volatile var spanish: Boolean = java.util.Locale.getDefault().language != "en"
    @Suppress("UNUSED_PARAMETER") private fun es(context: Context) = spanish
    private fun t(context: Context, a: String, b: String) = if (es(context)) a else b

    /** Speaker of the phone plus every Bluetooth or wired output that is connected now. */
    fun outputs(context: Context): List<Device> {
        val am = context.getSystemService(AudioManager::class.java)
        val found = am.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
        val list = mutableListOf(Device(DEFAULT, t(context, "Altavoz del teléfono", "Phone speaker"), t(context, "Predeterminado del sistema", "System default"), false,
            found.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }))
        found.filter { it.type in BT_OUT || it.type in WIRED }.groupBy { it.productName.toString() to (it.type in BT_OUT) }.forEach { (key, devices) ->
            val bt = key.second; val d = devices.firstOrNull { it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP } ?: devices.first()
            list.add(Device((if (bt) "bt:" else "wired:") + key.first, key.first.ifBlank { t(context, if (bt) "Auriculares Bluetooth" else "Auriculares", if (bt) "Bluetooth headphones" else "Headphones") },
                t(context, "Conectados", "Connected"), bt, d))
        }
        return list
    }
    fun inputs(context: Context): List<Device> {
        val am = context.getSystemService(AudioManager::class.java)
        val found = am.getDevices(AudioManager.GET_DEVICES_INPUTS)
        val list = mutableListOf(Device(DEFAULT, t(context, "Micrófono del teléfono", "Phone microphone"), t(context, "Predeterminado del sistema", "System default"), false,
            found.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_MIC }))
        found.filter { it.type in BT_IN || it.type in WIRED }.distinctBy { it.productName.toString() }.forEach { d ->
            val bt = d.type in BT_IN
            list.add(Device((if (bt) "bt:" else "wired:") + d.productName, t(context, "Micrófono de los auriculares", "Headset microphone"), d.productName.toString().ifBlank { t(context, "Detectado", "Detected") }, bt, d))
        }
        return list
    }

    fun output(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("output", DEFAULT)!!
    fun input(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("input", DEFAULT)!!
    fun setOutput(context: Context, key: String) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("output", key).apply()
    fun setInput(context: Context, key: String) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("input", key).apply()

    /** The chosen output if it is connected now; otherwise the phone speaker. */
    fun outputDevice(context: Context): Device = outputs(context).let { all -> all.firstOrNull { it.key == output(context) } ?: all.first() }
    fun inputDevice(context: Context): Device = inputs(context).let { all -> all.firstOrNull { it.key == input(context) } ?: all.first() }
    fun outputLabel(context: Context) = outputDevice(context).label

    /**
     * Device AINGEL's voice must be played on, or null to let the system decide. «Altavoz del teléfono» forces the
     * built-in speaker only when something else is connected (otherwise the system already uses it).
     */
    fun speechTarget(context: Context): AudioDeviceInfo? {
        val all = outputs(context); val chosen = all.firstOrNull { it.key == output(context) } ?: all.first()
        return if (chosen.key == DEFAULT) chosen.info.takeIf { all.size > 1 } else chosen.info
    }
}
