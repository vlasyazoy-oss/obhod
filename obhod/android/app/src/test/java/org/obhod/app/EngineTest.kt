package org.obhod.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Collections

class EngineTest {
    /** Остановка движка не должна ронять приложение: раньше чтение журнала падало с «Stream closed». */
    @Test fun destroyingProcessWhileReadingDoesNotThrow() {
        val uncaught = Collections.synchronizedList(mutableListOf<Throwable>())
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { _, e -> uncaught += e }
        try {
            val windows = System.getProperty("os.name").startsWith("Windows")
            val cmd = if (windows) listOf("ping", "-n", "30", "127.0.0.1") else listOf("ping", "-c", "30", "127.0.0.1")
            repeat(5) {
                val p = ProcessBuilder(cmd).redirectErrorStream(true).start()
                val lines = Collections.synchronizedList(mutableListOf<String>())
                val reader = Engine.pump(p) { lines += it }
                Thread.sleep(700)
                p.destroy()
                reader.join(5000)
                assertFalse("поток чтения должен завершиться", reader.isAlive)
                assertTrue("вывод процесса читался", lines.isNotEmpty())
            }
        } finally {
            Thread.setDefaultUncaughtExceptionHandler(previous)
        }
        assertTrue("необработанные исключения: $uncaught", uncaught.isEmpty())
    }
}
