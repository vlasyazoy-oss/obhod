package org.obhod.app

import android.Manifest
import android.app.Activity
import android.app.Dialog
import android.content.ClipboardManager
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.net.VpnService
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.WindowInsets
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Три вкладки внизу, как у Hiddify: «Маршрутизация», «Главная», «Настройки».
 * Экран строится кодом, поэтому смена языка — просто пересборка экрана, без перезапуска.
 */
class MainActivity : Activity() {
    private lateinit var store: Store
    private lateinit var pages: FrameLayout
    private val tabs = mutableListOf<Tab>()
    private var subpage: View? = null
    private var current = 1

    private lateinit var emblem: EmblemView
    private lateinit var status: TextView
    private lateinit var keyName: TextView
    private lateinit var keyInfo: TextView
    private lateinit var regionValue: TextView
    private lateinit var modeValue: TextView
    private lateinit var strategyValue: TextView
    private lateinit var dpiAll: Switch
    private var logView: TextView? = null
    private var refreshing = false

    private class Tab(val pill: FrameLayout, val label: TextView, val page: View)

    private fun t(key: String, vararg args: Any) = I18n.t(key, *args)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = Store(this)
        I18n.lang = store.lang
        edgeToEdge()
        rebuild()
        (application as ObhodApp).takeCrash()?.let { Log.write("сбой", "прошлый запуск завершился сбоем: $it") }
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2)
        }
    }

    override fun onResume() {
        super.onResume()
        Status.listener = { refresh() }
        Log.listener = { line -> logView?.let { it.append((if (it.text.isEmpty()) "" else "\n") + line) } }
        refresh()
    }

    override fun onPause() {
        Status.listener = null
        Log.listener = null
        super.onPause()
    }

    @Deprecated("Activity API")
    override fun onBackPressed() {
        when {
            subpage != null -> closeSubpage()
            current != 1 -> select(1)
            else -> @Suppress("DEPRECATION") super.onBackPressed()
        }
    }

    /**
     * Android 15 рисует приложения «от края до края»: без отступов вкладки уходили под кнопки навигации Android,
     * а заголовок — под строку состояния. Рисуем сами под системными панелями и отступаем на их высоту.
     */
    @Suppress("DEPRECATION")
    private fun edgeToEdge() {
        if (Build.VERSION.SDK_INT >= 30) window.setDecorFitsSystemWindows(false)
        else window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT
    }

    private fun rebuild() {
        tabs.clear()
        subpage = null
        logView = null
        setContentView(buildUi())
        window.decorView.layoutDirection = if (I18n.rtl) View.LAYOUT_DIRECTION_RTL else View.LAYOUT_DIRECTION_LTR
        select(current)
    }

    // ---------- строительные блоки ----------
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun text(s: String = "", size: Float = 15f, color: Int = FG, bold: Boolean = false) = TextView(this).apply {
        text = s
        textSize = size
        setTextColor(color)
        textAlignment = View.TEXT_ALIGNMENT_VIEW_START
        if (bold) typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    }

    private fun rounded(color: Int, radius: Int) = GradientDrawable().apply { setColor(color); cornerRadius = dp(radius).toFloat() }

    private fun ripple(content: android.graphics.drawable.Drawable? = null, radius: Int = 0) =
        RippleDrawable(ColorStateList.valueOf(RIPPLE), content, if (radius > 0) rounded(Color.WHITE, radius) else null)

    private fun vertical(padH: Int = 0, padV: Int = 0) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(padH), dp(padV), dp(padH), dp(padV))
    }

    private fun title(s: String) = text(s, 26f).apply { setPadding(dp(20), dp(18), dp(20), dp(10)) }

    private fun row(icon: IconView.Kind, title: String, subtitle: String? = null, trailing: View? = null,
                    onClick: (() -> Unit)? = null): Pair<LinearLayout, TextView?> {
        val r = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(20), dp(14), dp(20), dp(14))
            if (onClick != null) {
                background = ripple()
                setOnClickListener { onClick() }
            }
        }
        r.addView(IconView(this, icon, FG), LinearLayout.LayoutParams(dp(26), dp(26)).apply { marginEnd = dp(20) })
        val texts = vertical()
        texts.addView(text(title, 17f))
        val sub = subtitle?.let { text(it, 14f, MUTED).also { t -> texts.addView(t) } }
        r.addView(texts, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        trailing?.let { r.addView(it) }
        return r to sub
    }

    private fun switch(checked: Boolean, onChange: (Boolean) -> Unit) = Switch(this).apply {
        isChecked = checked
        val states = arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf())
        thumbTintList = ColorStateList(states, intArrayOf(Color.WHITE, MUTED))
        trackTintList = ColorStateList(states, intArrayOf(ACCENT, LINE))
        setOnCheckedChangeListener { _, v -> if (!refreshing) onChange(v) }
    }

    /** Окно в стиле приложения: тёмная карточка, синие отметки. Без items — подтверждение с кнопкой okLabel. */
    private fun sheet(title: String, items: List<String> = emptyList(), selected: Int = -1, okLabel: String? = null,
                      onPick: (Int) -> Unit) {
        val d = Dialog(this)
        val box = vertical(8, 8).apply { background = rounded(SHEET, 24) }
        box.addView(text(title, 20f, FG, bold = true).apply { setPadding(dp(16), dp(14), dp(16), dp(10)) })
        val list = vertical()
        items.forEachIndexed { i, label ->
            val r = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(16), dp(13), dp(16), dp(13))
                background = ripple(if (i == selected) rounded(SELECTED, 14) else null, 14)
                setOnClickListener { d.dismiss(); onPick(i) }
            }
            val dot = View(this).apply {
                background = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    if (i == selected) { setColor(ACCENT_HI); setStroke(dp(5), SELECTED) } else setStroke(dp(2), MUTED)
                }
            }
            r.addView(dot, LinearLayout.LayoutParams(dp(20), dp(20)).apply { marginEnd = dp(16) })
            r.addView(text(label, 16f, FG).apply { maxLines = 2; ellipsize = TextUtils.TruncateAt.END },
                LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
            list.addView(r, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { bottomMargin = dp(2) })
        }
        box.addView(ScrollView(this).apply { addView(list) }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT, 1f))
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.END; setPadding(0, dp(8), dp(8), dp(6)) }
        fun button(label: String, primary: Boolean, action: () -> Unit) = text(label, 15f, if (primary) Color.WHITE else ACCENT_TEXT, bold = true).apply {
            setPadding(dp(18), dp(10), dp(18), dp(10))
            background = ripple(if (primary) rounded(BAD_BG, 20) else null, 20)
            setOnClickListener { d.dismiss(); action() }
        }
        buttons.addView(button(t("cancel"), false) {})
        if (okLabel != null) {
            buttons.addView(button(okLabel, true) { onPick(-1) }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginStart = dp(8) })
        }
        box.addView(buttons)
        d.setContentView(box)
        d.window?.apply {
            setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
            setLayout((resources.displayMetrics.widthPixels * 0.9).toInt(), WRAP_CONTENT)
            decorView.layoutDirection = if (I18n.rtl) View.LAYOUT_DIRECTION_RTL else View.LAYOUT_DIRECTION_LTR
        }
        d.show()
    }

    // ---------- экран ----------
    private fun buildUi(): View {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG) }
        pages = FrameLayout(this)
        root.addView(pages, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))

        val nav = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setBackgroundColor(NAV)
            setPadding(dp(8), dp(12), dp(8), dp(14))
        }
        val pageViews = listOf(routingPage(), homePage(), settingsPage())
        listOf(IconView.Kind.ROUTE to "tab_routing", IconView.Kind.POWER to "tab_home", IconView.Kind.GEAR to "tab_settings")
            .forEachIndexed { i, (kind, key) ->
                val box = vertical().apply { gravity = Gravity.CENTER_HORIZONTAL; setOnClickListener { select(i) } }
                val pill = FrameLayout(this)
                pill.addView(IconView(this, kind, FG), FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
                box.addView(pill, LinearLayout.LayoutParams(dp(64), dp(32)).apply { gravity = Gravity.CENTER_HORIZONTAL })
                val lbl = text(t(key), 12f, MUTED).apply {
                    gravity = Gravity.CENTER
                    textAlignment = View.TEXT_ALIGNMENT_CENTER
                    setPadding(0, dp(4), 0, 0)
                    maxLines = 1
                    ellipsize = TextUtils.TruncateAt.END
                }
                box.addView(lbl, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
                nav.addView(box, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
                pages.addView(pageViews[i], FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
                tabs += Tab(pill, lbl, pageViews[i])
            }
        root.addView(nav, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))

        // Отступы на высоту строки состояния и кнопок навигации Android
        root.setOnApplyWindowInsetsListener { _, insets ->
            val (top, bottom) = if (Build.VERSION.SDK_INT >= 30) {
                insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout()).let { it.top to it.bottom }
            } else {
                @Suppress("DEPRECATION") (insets.systemWindowInsetTop to insets.systemWindowInsetBottom)
            }
            pages.setPadding(0, top, 0, 0)
            nav.setPadding(dp(8), dp(12), dp(8), dp(14) + bottom)
            insets
        }
        return root
    }

    private fun select(i: Int) {
        closeSubpage()
        current = i
        tabs.forEachIndexed { j, tab ->
            val on = i == j
            tab.page.visibility = if (on) View.VISIBLE else View.GONE
            tab.pill.background = if (on) rounded(PILL, 16) else null
            tab.label.setTextColor(if (on) FG else MUTED)
            tab.label.typeface = if (on) Typeface.create("sans-serif-medium", Typeface.NORMAL) else Typeface.DEFAULT
        }
        refresh()
    }

    private fun scroll(content: View) = ScrollView(this).apply { isFillViewport = true; addView(content) }

    private fun homePage(): View {
        val col = vertical(16, 8)
        col.addView(text(t("app_name"), 22f, FG, bold = true).apply { setPadding(dp(4), dp(8), 0, dp(10)) })

        val card = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = ripple(rounded(CARD, 16), 16)
            setOnClickListener { pickKey() }
        }
        card.addView(IconView(this, IconView.Kind.KEY, FG), LinearLayout.LayoutParams(dp(24), dp(24)).apply { marginEnd = dp(14) })
        val texts = vertical()
        keyName = text("", 17f, FG, bold = true).apply { maxLines = 1; ellipsize = TextUtils.TruncateAt.END }
        keyInfo = text("", 13f, MUTED)
        texts.addView(keyName)
        texts.addView(keyInfo)
        card.addView(texts, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        card.addView(text("▾", 18f, MUTED))
        col.addView(card, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))

        val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(10), 0, dp(6)) }
        actions.addView(pill(IconView.Kind.PASTE, t("paste"), ACCENT) { pasteKey() }, LinearLayout.LayoutParams(0, dp(44), 1f))
        actions.addView(pill(IconView.Kind.TRASH, t("delete"), CARD) { deleteKey() },
            LinearLayout.LayoutParams(WRAP_CONTENT, dp(44)).apply { marginStart = dp(10) })
        col.addView(actions)

        emblem = EmblemView(this).apply { setOnClickListener { toggle() } }
        col.addView(emblem, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(18) })
        status = text("", 14f, MUTED).apply {
            gravity = Gravity.CENTER
            textAlignment = View.TEXT_ALIGNMENT_CENTER
            setPadding(dp(8), dp(12), dp(8), dp(12))
        }
        col.addView(status, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        return scroll(col)
    }

    private fun pill(icon: IconView.Kind, label: String, bg: Int, onClick: () -> Unit) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER
        setPadding(dp(16), 0, dp(16), 0)
        background = ripple(rounded(bg, 22), 22)
        setOnClickListener { onClick() }
        addView(IconView(this@MainActivity, icon, Color.WHITE), LinearLayout.LayoutParams(dp(20), dp(20)).apply { marginEnd = dp(8) })
        addView(text(label, 15f, Color.WHITE, bold = true))
    }

    private fun routingPage(): View {
        val col = vertical()
        col.addView(title(t("tab_routing")))
        val (r1, v1) = row(IconView.Kind.GLOBE, t("region"), "", onClick = { pickRegion() })
        regionValue = v1!!
        col.addView(r1)
        val (r2, v2) = row(IconView.Kind.SWAP, t("mode"), "", onClick = { pickMode() })
        modeValue = v2!!
        col.addView(r2)
        val (r3, v3) = row(IconView.Kind.TUNE, t("strategy"), "", onClick = { pickStrategy() })
        strategyValue = v3!!
        col.addView(r3)
        dpiAll = switch(store.dpiAll) { store.dpiAll = it; changed() }
        col.addView(row(IconView.Kind.LAYERS, t("dpi_all"), t("dpi_all_sub"), dpiAll).first)
        col.addView(row(IconView.Kind.SHIELD, t("lan"), t("lan_sub")).first)
        return scroll(col)
    }

    private fun settingsPage(): View {
        val col = vertical()
        col.addView(title(t("tab_settings")))
        col.addView(row(IconView.Kind.GLOBE, t("language"), I18n.LANGS.getValue(I18n.lang)) { pickLanguage() }.first)
        col.addView(row(IconView.Kind.LOG, t("log"), t("log_sub")) { openLog() }.first)
        col.addView(row(IconView.Kind.BATTERY, t("battery"), t("battery_sub")) { openBatterySettings() }.first)
        col.addView(row(IconView.Kind.SHIELD, t("vpn_settings"), t("vpn_settings_sub")) {
            startActivity(Intent(Settings.ACTION_VPN_SETTINGS))
        }.first)
        col.addView(row(IconView.Kind.INFO, t("about"), t("about_sub", versionName())) { openAbout() }.first)
        return scroll(col)
    }

    // ---------- подстраницы ----------
    private fun openSubpage(name: String, content: View) {
        closeSubpage()
        val page = vertical().apply { setBackgroundColor(BG); isClickable = true }
        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(14), dp(20), dp(10))
        }
        head.addView(IconView(this, IconView.Kind.BACK, FG).apply {
            if (I18n.rtl) scaleX = -1f // стрелка «назад» в RTL смотрит вправо
            background = ripple(null, 22)
            setOnClickListener { closeSubpage() }
        }, LinearLayout.LayoutParams(dp(44), dp(44)))
        head.addView(text(name, 24f).apply { setPadding(dp(12), 0, dp(12), 0) })
        page.addView(head)
        page.addView(content, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))
        pages.addView(page, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        subpage = page
    }

    private fun closeSubpage() {
        subpage?.let { pages.removeView(it) }
        subpage = null
        logView = null
    }

    private fun openLog() {
        val tv = text(Log.all().joinToString("\n"), 11f, MUTED).apply {
            typeface = Typeface.MONOSPACE
            textDirection = View.TEXT_DIRECTION_LTR // журнал техничный, всегда слева направо
            setTextIsSelectable(true)
            setPadding(dp(16), dp(8), dp(16), dp(16))
        }
        openSubpage(t("log"), scroll(tv))
        logView = tv
    }

    private fun openAbout() {
        val col = vertical(20, 8)
        col.addView(EmblemView(this).apply { eyesOpen = true }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        col.addView(text(t("about_text", versionName()), 15f).apply { setPadding(0, dp(18), 0, 0) })
        openSubpage(t("about"), scroll(col))
    }

    private fun openBatterySettings() {
        runCatching { startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
            .onFailure { startActivity(Intent(Settings.ACTION_SETTINGS)) }
    }

    private fun versionName(): String = packageManager.getPackageInfo(packageName, 0).versionName ?: ""

    // ---------- выбор из списков ----------
    private fun regionCodes() = listOf("auto") + store.regions.keys().asSequence().toList()

    private fun regionLabel(code: String) =
        if (code == "auto") t("auto", I18n.region(Region.detect(this).first)) else I18n.region(code)

    private fun pickRegion() {
        val codes = regionCodes()
        sheet(t("region"), codes.map { (FLAGS[it] ?: "") + "  " + regionLabel(it) }, codes.indexOf(store.region)) {
            if (codes[it] != store.region) { store.region = codes[it]; store.mode = ""; changed() }
        }
    }

    private fun pickMode() {
        val r = store.currentRegion()
        val codes = Config.MODES.keys.filter { it == "vpn" || r.getBoolean("dpi_supported") }
        sheet(t("mode"), codes.map { I18n.mode(it) }, codes.indexOf(store.effectiveMode())) {
            store.mode = codes[it]
            changed()
        }
    }

    private fun pickStrategy() {
        val list = store.currentRegion().getJSONArray("strategies")
        if (list.length() == 0) return
        val items = (0 until list.length()).map { list.getJSONObject(it) }
        val cur = items.indexOfFirst { it.getString("id") == store.strategy()?.getString("id") }
        sheet(t("strategy"), items.map { I18n.strategy(it.getString("name")) }, cur) {
            store.setStrategyId(store.regionCode(), items[it].getString("id"))
            changed()
        }
    }

    private fun pickLanguage() {
        val codes = I18n.LANGS.keys.toList()
        sheet(t("language"), codes.map { I18n.LANGS.getValue(it) }, codes.indexOf(I18n.lang)) {
            store.lang = codes[it]
            I18n.lang = codes[it]
            current = 2
            rebuild()
        }
    }

    private fun pickKey() {
        val keys = store.keys
        if (keys.length() == 0) { pasteKey(); return }
        val items = (0 until keys.length()).map { keys.getJSONObject(it) }
        sheet(t("key_title"), items.map { "${it.getString("name")}  ·  ${it.getJSONObject("outbound").getString("type")}" }, store.selectedKey) {
            store.selectedKey = it
            changed()
        }
    }

    private fun deleteKey() {
        val key = store.currentKey() ?: return
        sheet(t("delete_confirm", key.getString("name")), okLabel = t("delete")) {
            store.deleteKey(store.selectedKey)
            changed()
        }
    }

    // ---------- обновление ----------
    private fun refresh() {
        if (!::status.isInitialized) return
        refreshing = true
        val code = store.regionCode()
        val r = store.currentRegion()
        val mode = store.effectiveMode()

        val key: JSONObject? = store.currentKey()
        val count = store.keys.length()
        keyName.text = key?.getString("name") ?: t("no_key")
        keyInfo.text = if (key == null) t("no_key_hint")
        else "${key.getJSONObject("outbound").getString("type")} · ${key.getJSONObject("outbound").optString("server")}" +
            if (count > 1) " · " + t("more", count - 1) else ""

        val note = if (r.optString("dpi_note").isNotEmpty()) "\n" + t("note_$code") else ""
        regionValue.text = regionLabel(store.region) + note
        modeValue.text = I18n.mode(mode) + " — " + t("mode_${mode}_desc")
        strategyValue.text = store.strategy()?.let { I18n.strategy(it.getString("name")) } ?: t("strategy_none")
        dpiAll.isChecked = store.dpiAll

        emblem.eyesOpen = Status.state == Status.State.CONNECTED
        emblem.busy = Status.state == Status.State.CONNECTING
        status.text = when (Status.state) {
            Status.State.CONNECTED -> t("status_connected", Status.text)
            Status.State.CONNECTING -> t("status_connecting")
            Status.State.ERROR -> Status.text
            Status.State.DISCONNECTED -> t("status_idle")
        }
        status.setTextColor(when (Status.state) {
            Status.State.CONNECTED -> OK
            Status.State.ERROR -> BAD
            else -> MUTED
        })
        refreshing = false
    }

    private fun changed() {
        refresh()
        if (Status.state == Status.State.CONNECTED) {
            Log.write("obhod", "настройки изменились — переподключаюсь")
            startService(Intent(this, ObhodVpnService::class.java))
        }
    }

    // ---------- ключи ----------
    private fun pasteKey() {
        val clip = getSystemService(ClipboardManager::class.java).primaryClip
        val text = clip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()?.trim().orEmpty()
        if (text.isEmpty()) {
            status.text = t("clipboard_empty")
            return
        }
        if (text.startsWith("http://") || text.startsWith("https://")) {
            Log.write("obhod", "скачиваю подписку…")
            status.text = t("sub_loading")
            Thread {
                try {
                    val conn = URL(text).openConnection() as HttpURLConnection
                    conn.setRequestProperty("User-Agent", "obhod/0.1")
                    conn.connectTimeout = 15000
                    conn.readTimeout = 15000
                    val body = conn.inputStream.bufferedReader().use { it.readText() }
                    runOnUiThread { addKeys(body) }
                } catch (e: Exception) {
                    Log.write("ошибка", "подписка не скачалась: ${e.message}")
                    runOnUiThread { status.text = t("sub_failed", e.message ?: "") }
                }
            }.start()
        } else {
            addKeys(text)
        }
    }

    private fun addKeys(text: String) {
        val (found, errors) = Keys.parseMany(text)
        errors.forEach { Log.write("obhod", "не разобрал ключ: $it") }
        store.addKeys(found)
        if (found.isNotEmpty()) Log.write("obhod", "добавлено ключей: ${found.size}")
        changed()
        if (found.isEmpty()) status.text = t("no_keys_found")
    }

    // ---------- подключение ----------
    private fun toggle() {
        when (Status.state) {
            Status.State.CONNECTED, Status.State.CONNECTING ->
                startService(Intent(this, ObhodVpnService::class.java).setAction(ObhodVpnService.ACTION_STOP))
            else -> {
                val ask = VpnService.prepare(this) // системный запрос разрешения на VPN, один раз
                if (ask != null) startActivityForResult(ask, REQUEST_VPN) else startVpn()
            }
        }
    }

    private fun startVpn() {
        Status.set(Status.State.CONNECTING)
        startForegroundService(Intent(this, ObhodVpnService::class.java))
    }

    @Deprecated("Activity API")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_VPN) {
            if (resultCode == RESULT_OK) startVpn() else Log.write("obhod", "разрешение на VPN не дано")
        }
    }

    companion object {
        private const val REQUEST_VPN = 1
        val BG = Color.parseColor("#16151b")
        val NAV = Color.parseColor("#1d1b23")
        val CARD = Color.parseColor("#221f29")
        val SHEET = Color.parseColor("#24212c")
        val SELECTED = Color.parseColor("#2c3352")
        val PILL = Color.parseColor("#33304a")
        val LINE = Color.parseColor("#3d3947")
        val RIPPLE = Color.parseColor("#33ffffff")
        val FG = Color.parseColor("#ecebf0")
        val MUTED = Color.parseColor("#9d98a6")
        val ACCENT = Color.parseColor("#2f53b5")
        val ACCENT_HI = Color.parseColor("#6f8ff0")
        val ACCENT_TEXT = Color.parseColor("#8fa8ff")
        val BAD_BG = Color.parseColor("#b3364a")
        val OK = Color.parseColor("#3ecf8e")
        val BAD = Color.parseColor("#ff6b6b")
        private val FLAGS = mapOf("ru" to "🇷🇺", "tr" to "🇹🇷", "ir" to "🇮🇷", "cn" to "🇨🇳", "other" to "🌐", "auto" to "📍")
    }
}
