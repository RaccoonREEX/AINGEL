package ec.aingel.mobile

import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl

/** Ignore cookies from calls which belong to a closed or reconfigured session. */
internal class SessionCookieGate(private val delegate: CookieJar, private val clearDelegate: () -> Unit) {
    private var generation = 0L

    @Synchronized fun generation(): Long = generation
    @Synchronized fun isCurrent(value: Long): Boolean = value == generation

    @Synchronized fun invalidate() {
        generation++
        clearDelegate()
    }

    @Synchronized fun cookieJar(): CookieJar {
        val expected = generation
        return object : CookieJar {
            override fun loadForRequest(url: HttpUrl): List<Cookie> = synchronized(this@SessionCookieGate) {
                if (expected == generation) delegate.loadForRequest(url) else emptyList()
            }
            override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) = synchronized(this@SessionCookieGate) {
                if (expected == generation) delegate.saveFromResponse(url, cookies)
            }
        }
    }
}
