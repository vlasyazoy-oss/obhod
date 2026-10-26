package org.obhod.app

import java.util.Locale

/**
 * Языки интерфейса: русский, английский и языки регионов — турецкий, персидский (справа налево), китайский.
 * Строки в коде, а не в res/values-*: экран строится программно и меняет язык без перезапуска.
 */
object I18n {
    val LANGS = linkedMapOf("ru" to "Русский", "en" to "English", "tr" to "Türkçe", "fa" to "فارسی", "zh" to "中文")

    @Volatile var lang = "ru"

    val rtl: Boolean get() = lang == "fa"

    fun systemDefault(): String = Locale.getDefault().language.let { if (it in LANGS) it else "en" }

    fun t(key: String, vararg args: Any): String {
        val s = STRINGS[key]?.let { it[lang] ?: it["en"] ?: it["ru"] } ?: key
        return if (args.isEmpty()) s else String.format(s, *args)
    }

    fun region(code: String) = t("region_$code")
    fun mode(code: String) = t("mode_$code")

    /** Названия стратегий в regions.json по-русски; переводим их по фразам. */
    fun strategy(name: String): String {
        val dict = PHRASES[lang] ?: return name
        var out = name
        for ((ru, tr) in dict) out = out.replace(ru, tr)
        return out
    }

    private val PHRASES = mapOf(
        "en" to listOf("разрез TLS-записи" to "TLS record split", "TLS-запись" to "TLS record", "TLS-записи" to "TLS record",
            "по SNI" to "at SNI", "с низким TTL" to "with low TTL", "OOB-байт" to "OOB byte",
            "цепочка с автопереключением" to "auto-switching chain"),
        "tr" to listOf("разрез TLS-записи" to "TLS kaydı bölme", "TLS-запись" to "TLS kaydı", "TLS-записи" to "TLS kaydı",
            "по SNI" to "SNI'de", "с низким TTL" to "düşük TTL ile", "OOB-байт" to "OOB baytı",
            "цепочка с автопереключением" to "otomatik geçişli zincir"),
        "fa" to listOf("разрез TLS-записи" to "برش رکورد TLS", "TLS-запись" to "رکورد TLS", "TLS-записи" to "رکورد TLS",
            "по SNI" to "در SNI", "с низким TTL" to "با TTL پایین", "OOB-байт" to "بایت OOB",
            "цепочка с автопереключением" to "زنجیره با تعویض خودکار"),
        "zh" to listOf("разрез TLS-записи" to "TLS 记录分割", "TLS-запись" to "TLS 记录", "TLS-записи" to "TLS 记录",
            "по SNI" to "按 SNI", "с низким TTL" to "低 TTL", "OOB-байт" to "OOB 字节",
            "цепочка с автопереключением" to "自动切换链"),
    )

    private fun s(ru: String, en: String, tr: String, fa: String, zh: String) = mapOf("ru" to ru, "en" to en, "tr" to tr, "fa" to fa, "zh" to zh)

    private val STRINGS: Map<String, Map<String, String>> = mapOf(
        "app_name" to s("Обход", "Obhod", "Obhod", "Obhod", "Obhod"),
        "tab_routing" to s("Маршрутизация", "Routing", "Yönlendirme", "مسیریابی", "路由"),
        "tab_home" to s("Главная", "Home", "Ana sayfa", "خانه", "主页"),
        "tab_settings" to s("Настройки", "Settings", "Ayarlar", "تنظیمات", "设置"),

        "no_key" to s("Ключа нет", "No key", "Anahtar yok", "کلیدی نیست", "没有密钥"),
        "no_key_hint" to s("Без ключа работает обход DPI. Ключ: vless://, hy2://, trojan://, ss:// или подписка",
            "DPI bypass works without a key. Key: vless://, hy2://, trojan://, ss:// or a subscription",
            "DPI atlatma anahtarsız çalışır. Anahtar: vless://, hy2://, trojan://, ss:// veya abonelik",
            "دور زدن DPI بدون کلید کار می‌کند. کلید: vless://، hy2://، trojan://، ss:// یا اشتراک",
            "无需密钥即可绕过 DPI。密钥：vless://、hy2://、trojan://、ss:// 或订阅"),
        "more" to s("ещё %d", "+%d more", "+%d daha", "%d مورد دیگر", "另有 %d 个"),
        "key_title" to s("Ключ", "Key", "Anahtar", "کلید", "密钥"),
        "paste" to s("Вставить ключ", "Paste key", "Anahtarı yapıştır", "چسباندن کلید", "粘贴密钥"),
        "delete" to s("Удалить", "Delete", "Sil", "حذف", "删除"),
        "delete_confirm" to s("Удалить ключ «%s»?", "Delete key “%s”?", "“%s” anahtarı silinsin mi?", "کلید «%s» حذف شود؟", "删除密钥“%s”？"),
        "cancel" to s("Отмена", "Cancel", "İptal", "لغو", "取消"),
        "clipboard_empty" to s("Буфер обмена пуст: скопируйте ключ или ссылку на подписку",
            "Clipboard is empty: copy a key or a subscription link", "Pano boş: bir anahtar veya abonelik bağlantısı kopyalayın",
            "کلیپ‌بورد خالی است: یک کلید یا پیوند اشتراک کپی کنید", "剪贴板为空：请复制密钥或订阅链接"),
        "sub_loading" to s("Скачиваю подписку…", "Downloading subscription…", "Abonelik indiriliyor…", "در حال دریافت اشتراک…", "正在下载订阅…"),
        "sub_failed" to s("Подписка не скачалась: %s", "Subscription failed: %s", "Abonelik indirilemedi: %s", "دریافت اشتراک ناموفق بود: %s", "订阅下载失败：%s"),
        "no_keys_found" to s("Не нашёл ключей в буфере обмена", "No keys found in the clipboard", "Panoda anahtar bulunamadı",
            "کلیدی در کلیپ‌بورد پیدا نشد", "剪贴板中未找到密钥"),

        "status_connected" to s("Подключено · %s", "Connected · %s", "Bağlandı · %s", "متصل · %s", "已连接 · %s"),
        "status_connecting" to s("Подключаюсь…", "Connecting…", "Bağlanıyor…", "در حال اتصال…", "正在连接…"),
        "status_idle" to s("Нажмите на эмблему, чтобы подключиться", "Tap the emblem to connect", "Bağlanmak için ambleme dokunun",
            "برای اتصال روی نشان بزنید", "点击徽标以连接"),
        "disconnect" to s("Отключить", "Disconnect", "Bağlantıyı kes", "قطع اتصال", "断开"),

        "region" to s("Регион", "Region", "Bölge", "منطقه", "地区"),
        "auto" to s("Авто: %s", "Auto: %s", "Otomatik: %s", "خودکار: %s", "自动：%s"),
        "region_ru" to s("Россия", "Russia", "Rusya", "روسیه", "俄罗斯"),
        "region_tr" to s("Турция", "Turkey", "Türkiye", "ترکیه", "土耳其"),
        "region_ir" to s("Иран", "Iran", "İran", "ایران", "伊朗"),
        "region_cn" to s("Китай", "China", "Çin", "چین", "中国"),
        "region_other" to s("Другая страна", "Other country", "Diğer ülke", "کشور دیگر", "其他国家"),
        "note_ir" to s("Обход DPI в Иране помогает частично: многие сервисы заблокированы по IP. Для надёжной работы нужен ключ.",
            "DPI bypass in Iran helps only partly: many services are blocked by IP. A key is needed for reliable access.",
            "İran'da DPI atlatma kısmen işe yarar: birçok hizmet IP ile engelli. Güvenilir erişim için anahtar gerekir.",
            "دور زدن DPI در ایران فقط تا حدی کمک می‌کند: بسیاری از سرویس‌ها با IP مسدود هستند. برای اتصال پایدار کلید لازم است.",
            "在伊朗绕过 DPI 只能部分有效：许多服务按 IP 封锁。稳定访问需要密钥。"),
        "note_cn" to s("В Китае заблокированы сами IP-адреса сервисов, локальный обход DPI не помогает. Нужен ключ (лучше VLESS+Reality или Hysteria2).",
            "In China the services' IP addresses themselves are blocked, local DPI bypass does not help. A key is needed (VLESS+Reality or Hysteria2 is best).",
            "Çin'de hizmetlerin IP adresleri engelli, yerel DPI atlatma işe yaramaz. Anahtar gerekir (en iyisi VLESS+Reality veya Hysteria2).",
            "در چین خود نشانی‌های IP سرویس‌ها مسدود است و دور زدن محلی DPI کمکی نمی‌کند. کلید لازم است (بهتر است VLESS+Reality یا Hysteria2).",
            "在中国，服务的 IP 地址本身被封锁，本地绕过 DPI 无效。需要密钥（最好是 VLESS+Reality 或 Hysteria2）。"),

        "mode" to s("Режим", "Mode", "Mod", "حالت", "模式"),
        "mode_dpi" to s("Обход DPI", "DPI bypass", "DPI atlatma", "دور زدن DPI", "绕过 DPI"),
        "mode_vpn" to s("VPN по ключу", "VPN by key", "Anahtarla VPN", "VPN با کلید", "密钥 VPN"),
        "mode_hybrid" to s("Гибрид", "Hybrid", "Hibrit", "ترکیبی", "混合"),
        "mode_dpi_desc" to s("сайты из списка через ByeDPI, остальное напрямую", "listed sites via ByeDPI, the rest direct",
            "listedeki siteler ByeDPI ile, gerisi doğrudan", "سایت‌های فهرست از ByeDPI، بقیه مستقیم", "列表中的网站经 ByeDPI，其余直连"),
        "mode_vpn_desc" to s("всё через сервер по ключу, кроме своей страны", "everything via the key's server except your own country",
            "kendi ülkeniz hariç her şey anahtarın sunucusu üzerinden", "همه چیز از سرور کلید، به‌جز کشور خودتان", "除本国外全部经密钥服务器"),
        "mode_hybrid_desc" to s("обход DPI для списка, ключ для заблокированного по IP", "DPI bypass for the list, key for IP-blocked sites",
            "liste için DPI atlatma, IP ile engellenenler için anahtar", "دور زدن DPI برای فهرست، کلید برای سایت‌های مسدود با IP",
            "列表使用绕过 DPI，按 IP 封锁的使用密钥"),

        "strategy" to s("Стратегия обхода DPI", "DPI bypass strategy", "DPI atlatma stratejisi", "راهبرد دور زدن DPI", "绕过 DPI 策略"),
        "strategy_none" to s("не нужна в этом регионе", "not needed in this region", "bu bölgede gerekmez", "در این منطقه لازم نیست", "该地区不需要"),
        "dpi_all" to s("Все сайты через обход DPI", "All sites via DPI bypass", "Tüm siteler DPI atlatma ile", "همه سایت‌ها از دور زدن DPI", "所有网站都绕过 DPI"),
        "dpi_all_sub" to s("Не только сайты из списка региона", "Not only the region's list", "Yalnızca bölge listesindekiler değil",
            "نه فقط سایت‌های فهرست منطقه", "不仅是地区列表中的网站"),
        "lan" to s("Локальная сеть напрямую", "Local network direct", "Yerel ağ doğrudan", "شبکه محلی مستقیم", "局域网直连"),
        "lan_sub" to s("Роутер, принтер и адреса 192.168.* всегда мимо VPN", "Router, printer and 192.168.* addresses always bypass the VPN",
            "Yönlendirici, yazıcı ve 192.168.* adresleri her zaman VPN dışında", "روتر، چاپگر و نشانی‌های ‎192.168.*‎ همیشه بیرون از VPN",
            "路由器、打印机和 192.168.* 地址始终不经 VPN"),

        "language" to s("Язык", "Language", "Dil", "زبان", "语言"),
        "log" to s("Журнал", "Log", "Günlük", "گزارش", "日志"),
        "log_sub" to s("Что делают sing-box и ByeDPI", "What sing-box and ByeDPI are doing", "sing-box ve ByeDPI ne yapıyor",
            "sing-box و ByeDPI چه می‌کنند", "sing-box 和 ByeDPI 的运行情况"),
        "battery" to s("Отключить оптимизацию батареи", "Disable battery optimization", "Pil optimizasyonunu kapat",
            "غیرفعال کردن بهینه‌سازی باتری", "关闭电池优化"),
        "battery_sub" to s("Чтобы Android не выключал VPN в фоне", "So Android does not stop the VPN in the background",
            "Android VPN'i arka planda kapatmasın diye", "تا اندروید VPN را در پس‌زمینه متوقف نکند", "防止 Android 在后台停止 VPN"),
        "vpn_settings" to s("Настройки VPN Android", "Android VPN settings", "Android VPN ayarları", "تنظیمات VPN اندروید", "Android VPN 设置"),
        "vpn_settings_sub" to s("Постоянная VPN и блокировка без VPN — держите выключенными для черновика",
            "Keep always-on VPN and blocking without VPN off for this draft",
            "Bu taslak için her zaman açık VPN ve VPN'siz engellemeyi kapalı tutun",
            "برای این نسخه آزمایشی VPN همیشه‌روشن و مسدودسازی بدون VPN را خاموش نگه دارید",
            "此草稿版本请关闭始终开启的 VPN 和无 VPN 时阻止连接"),
        "about" to s("О программе", "About", "Hakkında", "درباره", "关于"),
        "about_sub" to s("Обход %s · open source", "Obhod %s · open source", "Obhod %s · açık kaynak", "Obhod %s · متن‌باز", "Obhod %s · 开源"),
        "about_text" to s(
            "Обход %s\n\nОбход DPI без сервера (ByeDPI 0.17.3) и VPN по своему ключу (sing-box 1.14.4), туннель hev-socks5-tunnel 2.19.3.\n\nПрофили регионов: Россия, Турция, Иран, Китай.\n\nЧерновик: подписан отладочным ключом.",
            "Obhod %s\n\nDPI bypass without a server (ByeDPI 0.17.3) and VPN with your own key (sing-box 1.14.4), tunnel hev-socks5-tunnel 2.19.3.\n\nRegion profiles: Russia, Turkey, Iran, China.\n\nDraft build, signed with a debug key.",
            "Obhod %s\n\nSunucusuz DPI atlatma (ByeDPI 0.17.3) ve kendi anahtarınızla VPN (sing-box 1.14.4), tünel hev-socks5-tunnel 2.19.3.\n\nBölge profilleri: Rusya, Türkiye, İran, Çin.\n\nTaslak sürüm, hata ayıklama anahtarıyla imzalı.",
            "Obhod %s\n\nدور زدن DPI بدون سرور (ByeDPI 0.17.3) و VPN با کلید خودتان (sing-box 1.14.4)، تونل hev-socks5-tunnel 2.19.3.\n\nنمایه‌های منطقه: روسیه، ترکیه، ایران، چین.\n\nنسخه آزمایشی، امضاشده با کلید اشکال‌زدایی.",
            "Obhod %s\n\n无需服务器即可绕过 DPI（ByeDPI 0.17.3），以及使用你自己的密钥的 VPN（sing-box 1.14.4），隧道 hev-socks5-tunnel 2.19.3。\n\n地区配置：俄罗斯、土耳其、伊朗、中国。\n\n草稿版本，使用调试密钥签名。"),

        "err_need_key" to s("Для этого режима нужен ключ: вставьте ссылку vless://, hy2://, trojan://, ss:// или подписку.",
            "This mode needs a key: paste a vless://, hy2://, trojan://, ss:// link or a subscription.",
            "Bu mod anahtar gerektirir: vless://, hy2://, trojan://, ss:// bağlantısı veya abonelik yapıştırın.",
            "این حالت به کلید نیاز دارد: پیوند vless://، hy2://، trojan://، ss:// یا اشتراک را بچسبانید.",
            "此模式需要密钥：请粘贴 vless://、hy2://、trojan://、ss:// 链接或订阅。"),
        "err_vpn_denied" to s("Android не дал создать VPN: нет разрешения", "Android refused to create the VPN: no permission",
            "Android VPN oluşturmaya izin vermedi", "اندروید اجازه ساخت VPN را نداد", "Android 拒绝创建 VPN：没有权限"),
        "err_start" to s("Не удалось подключиться: %s", "Could not connect: %s", "Bağlanılamadı: %s", "اتصال ممکن نشد: %s", "无法连接：%s"),
    )
}
