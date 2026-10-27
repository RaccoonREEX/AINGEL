package ec.aingel.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.ViewModelProvider

class MainActivity : ComponentActivity() {
    private lateinit var model: AingelViewModel
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        model = ViewModelProvider(this)[AingelViewModel::class.java]
        setContent { AingelApp(model) }
    }
    override fun onStop() {
        if (::model.isInitialized) model.stopCaptions()
        super.onStop()
    }
}
