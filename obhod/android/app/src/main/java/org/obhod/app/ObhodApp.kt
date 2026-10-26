package org.obhod.app

import android.app.Application
import java.io.File

/**
 * Сбой приложения записывается в files/crash.txt и показывается в журнале при следующем запуске:
 * так причину видно на телефоне без компьютера и adb.
 */
class ObhodApp : Application() {
    override fun onCreate() {
        super.onCreate()
        I18n.lang = Store(this).lang
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, e ->
            runCatching {
                File(filesDir, CRASH_FILE).writeText("поток ${thread.name}: ${e.stackTraceToString().take(4000)}")
            }
            previous?.uncaughtException(thread, e)
        }
    }

    /** Текст прошлого сбоя (один раз), или null. */
    fun takeCrash(): String? {
        val f = File(filesDir, CRASH_FILE)
        if (!f.exists()) return null
        return runCatching { f.readText() }.getOrNull().also { f.delete() }
    }

    companion object {
        private const val CRASH_FILE = "crash.txt"
    }
}
