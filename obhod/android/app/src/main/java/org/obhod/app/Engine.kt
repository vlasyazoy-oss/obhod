package org.obhod.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import java.io.File
import java.io.IOException
import java.util.ArrayDeque

/**
 * sing-box и ByeDPI как отдельные процессы. Бинарники лежат в APK как libsingbox.so и libbyedpi.so:
 * запускать исполняемые файлы Android разрешает только из nativeLibraryDir.
 */
class Engine(private val context: Context) {
    class EngineError(message: String) : RuntimeException(message)

    private val procs = linkedMapOf<String, Process>()
    private val libDir get() = File(context.applicationInfo.nativeLibraryDir)

    val running: Boolean get() = procs.values.any { it.isAlive }

    fun start(config: String, byedpiArgs: List<String>?) {
        stop()
        val dir = context.filesDir
        val conf = File(dir, "config.json").apply { writeText(config) }
        if (byedpiArgs != null) {
            Log.write("obhod", "ByeDPI: ${byedpiArgs.drop(4).joinToString(" ")}")
            procs["byedpi"] = spawn(listOf(File(libDir, "libbyedpi.so").path) + byedpiArgs, "byedpi")
        }
        procs["sing-box"] = spawn(listOf(File(libDir, "libsingbox.so").path, "run", "-c", conf.path, "-D", dir.path), "sing-box")
        Thread.sleep(800)
        val dead = procs.filterValues { !it.isAlive }.keys
        if (dead.isNotEmpty()) {
            stop()
            throw EngineError("движок завершился сразу после запуска: ${dead.joinToString()} (подробности в журнале)")
        }
    }

    private fun spawn(cmd: List<String>, source: String): Process {
        val p = ProcessBuilder(cmd).directory(context.filesDir).redirectErrorStream(true).start()
        pump(p) { Log.write(source, it) }
        return p
    }

    fun stop() {
        for (name in listOf("sing-box", "byedpi")) {
            procs.remove(name)?.let { p ->
                p.destroy()
                if (!p.waitFor(3, java.util.concurrent.TimeUnit.SECONDS)) p.destroyForcibly()
            }
        }
    }

    companion object {
        private val ANSI = Regex("\u001b\\[[0-9;]*m")

        /** Читает вывод процесса в фоне построчно, без цветовых кодов. */
        fun pump(p: Process, onLine: (String) -> Unit): Thread = Thread {
            try {
                p.inputStream.bufferedReader().forEachLine { onLine(it.replace(ANSI, "")) }
            } catch (e: IOException) {
                // Process.destroy() закрывает поток вывода, и чтение падает с «Stream closed». Это нормальная остановка;
                // необработанное исключение в любом потоке Android убило бы всё приложение.
            }
        }.apply { isDaemon = true; start() }
    }
}

/** Журнал на 500 строк в памяти и подписчики в главном потоке. */
object Log {
    private val lines = ArrayDeque<String>()
    private val main = Handler(Looper.getMainLooper())
    var listener: ((String) -> Unit)? = null

    @Synchronized
    fun write(source: String, text: String) {
        val line = "${java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.ROOT).format(java.util.Date())} [$source] ${text.trimEnd()}"
        lines.addLast(line)
        while (lines.size > 500) lines.removeFirst()
        main.post { listener?.invoke(line) }
    }

    @Synchronized
    fun all(): List<String> = lines.toList()
}
