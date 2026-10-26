package org.obhod.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.VpnService
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import hev.htproxy.TProxyService
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * VPN: TUN (VpnService) → hev-socks5-tunnel → SOCKS sing-box → напрямую / ByeDPI / сервер по ключу.
 * Само приложение исключено из VPN, поэтому соединения sing-box и ByeDPI идут мимо туннеля.
 */
class ObhodVpnService : VpnService() {
    private var tun: ParcelFileDescriptor? = null
    private lateinit var engine: Engine

    // Запуск и остановка строго по очереди и не в главном потоке: остановка ждёт процессы движков
    private val worker = Executors.newSingleThreadExecutor()

    override fun onCreate() {
        super.onCreate()
        engine = Engine(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) {
            // Android перезапускает службу сам после гибели процесса. VPN без экрана и без ведома пользователя
            // перехватывал бы весь трафик телефона — поэтому такой перезапуск не поднимает VPN.
            Log.write("obhod", "служба перезапущена системой — VPN не поднимаю, подключитесь заново")
            stopSelf()
            return START_NOT_STICKY
        }
        if (intent.action == ACTION_STOP) {
            worker.execute { stopVpn() }
            return START_NOT_STICKY
        }
        startForegroundCompat(I18n.t("status_connecting"))
        worker.execute { startVpn() }
        return START_NOT_STICKY
    }

    private fun startVpn() {
        val store = Store(this)
        try {
            Status.set(Status.State.CONNECTING)
            if (tun != null) runCatching { TProxyService.TProxyStopService() } // переподключение с новыми настройками
            val region = store.currentRegion()
            val mode = store.effectiveMode()
            val key = store.currentKey()?.getJSONObject("outbound")
            val config = Config.build(region, mode, key, store.dpiAll)
            val strategy = if (mode != "vpn") store.strategy() else null
            engine.start(config.toString(2), strategy?.let { Config.byedpiArgs(it) })

            val builder = Builder()
                .setSession("Обход")
                .setMtu(8500)
                .addAddress("172.19.0.1", 30)
                .addDnsServer(Config.TUN_DNS)
                .addRoute("0.0.0.0", 0)
                .addDisallowedApplication(packageName)
            tun?.close()
            tun = builder.establish() ?: throw Engine.EngineError(I18n.t("err_vpn_denied"))

            val yaml = File(filesDir, "tunnel.yml").apply { writeText(Config.tunnelYaml()) }
            TProxyService.TProxyStartService(yaml.path, tun!!.fd)

            val text = "${I18n.region(store.regionCode())} · ${I18n.mode(mode)}"
            Log.write("obhod", "подключено: ${region.getString("name")}, ${Config.MODES[mode]}")
            startForegroundCompat(I18n.t("status_connected", text))
            Status.set(Status.State.CONNECTED, text)
        } catch (e: Exception) {
            Log.write("ошибка", e.message ?: e.toString())
            val shown = when ((e as? Config.ConfigError)?.code) {
                "need_key" -> I18n.t("err_need_key")
                "dpi_unsupported" -> I18n.t("note_${store.regionCode()}")
                else -> I18n.t("err_start", e.message ?: e.toString())
            }
            Status.set(Status.State.ERROR, shown)
            stopVpn()
        }
    }

    /** Порядок важен: сначала туннель (перестаёт писать в TUN), потом движки, потом сам TUN. Повторный вызов безопасен. */
    private fun stopVpn() {
        runCatching { TProxyService.TProxyStopService() }
        runCatching { engine.stop() }
        runCatching { tun?.close() }
        tun = null
        if (Status.state != Status.State.ERROR) Status.set(Status.State.DISCONNECTED)
        Log.write("obhod", "отключено")
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    // VPN отключили в настройках Android или включили другой VPN
    override fun onRevoke() {
        worker.execute { stopVpn() }
    }

    override fun onDestroy() {
        // Служба уничтожается — TUN закрываем в любом случае, чтобы не оставить телефон без сети
        if (tun != null) runCatching { worker.submit { stopVpn() }.get(8, TimeUnit.SECONDS) }
        worker.shutdown()
        super.onDestroy()
    }

    private fun startForegroundCompat(text: String) {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "Обход", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, ObhodVpnService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_lock_lock)
            .setContentTitle(I18n.t("app_name"))
            .setContentText(text)
            .setContentIntent(open)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(null, I18n.t("disconnect"), stop).build())
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIFICATION_ID, n)
        }
    }

    companion object {
        const val ACTION_STOP = "org.obhod.app.STOP"
        private const val CHANNEL = "vpn"
        private const val NOTIFICATION_ID = 1
    }
}

/** Состояние подключения для экрана; слушатели вызываются в главном потоке. */
object Status {
    enum class State { DISCONNECTED, CONNECTING, CONNECTED, ERROR }

    @Volatile var state = State.DISCONNECTED
        private set
    @Volatile var text = ""
        private set
    var listener: (() -> Unit)? = null
    private val main = Handler(Looper.getMainLooper())

    fun set(s: State, t: String = "") {
        state = s
        text = t
        main.post { listener?.invoke() }
    }
}
