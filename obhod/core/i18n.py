"""Языки интерфейса: русский, английский и языки регионов — турецкий, персидский, китайский. Те же, что в Android-версии.

Язык выбирается в окне; пока не выбран — по языку Windows, а если такого нет среди наших — английский.
Отчёт самопроверки (--selftest) остаётся по-русски: его читаем мы, а не пользователь.
"""
import ctypes

LANGS = {"ru": "Русский", "en": "English", "tr": "Türkçe", "fa": "فارسی", "zh": "中文"}
_ORDER = tuple(LANGS)

lang = "ru"  # до set_lang(): тесты и отчёт самопроверки видят русские тексты, как раньше


def system_default():
    try:
        buf = ctypes.create_unicode_buffer(85)
        ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
        code = buf.value.split("-")[0].lower()
    except (AttributeError, OSError):
        code = ""
    return code if code in LANGS else "en"


def set_lang(code):
    global lang
    lang = code if code in LANGS else system_default()
    return lang


def t(key, *args):
    row = STRINGS.get(key)
    if row is None:
        return key
    s = row[_ORDER.index(lang)] or row[1]
    return s % args if args else s


def region(code):
    return t("region_" + code)


def mode(code):
    return t("mode_" + code)


def phrases(text, table):
    """Названия стратегий в regions.json и «откуда узнали регион» — по-русски; переводим по фразам."""
    for ru, *tr in table:
        text = text.replace(ru, tr[_ORDER.index(lang) - 1] if lang != "ru" else ru)
    return text


def strategy(name):
    return phrases(name, STRATEGY_PHRASES)


def how(text):
    return phrases(text, HOW_PHRASES)


#                ru                              en                         tr                             fa                           zh
STRATEGY_PHRASES = [
    ("цепочка с автопереключением", "auto-switching chain", "otomatik geçişli zincir", "زنجیره با تعویض خودکار", "自动切换链"),
    ("разрез TLS-записи", "TLS record split", "TLS kaydı bölme", "برش رکورد TLS", "TLS 记录分割"),
    ("TLS-запись", "TLS record", "TLS kaydı", "رکورد TLS", "TLS 记录"),
    ("TLS-записи", "TLS record", "TLS kaydı", "رکورد TLS", "TLS 记录"),
    ("по SNI", "at SNI", "SNI'de", "در SNI", "按 SNI"),
    ("с низким TTL", "with low TTL", "düşük TTL ile", "با TTL پایین", "低 TTL"),
    ("OOB-байт", "OOB byte", "OOB baytı", "بایت OOB", "OOB 字节"),
]
HOW_PHRASES = [
    ("часовой пояс", "time zone", "saat dilimi", "منطقه زمانی", "时区"),
    ("язык системы", "system language", "sistem dili", "زبان سیستم", "系统语言"),
    ("не удалось определить", "could not detect", "belirlenemedi", "تشخیص داده نشد", "无法确定"),
    ("IP-адрес, страна", "IP address, country", "IP adresi, ülke", "نشانی IP، کشور", "IP 地址，国家"),
]

STRINGS = {
    # --- окно ---
    "app": ("Обход", "Obhod", "Obhod", "Obhod", "Obhod"),
    "admin": ("администратор", "administrator", "yönetici", "مدیر", "管理员"),
    "version": ("версия %s", "version %s", "sürüm %s", "نسخه %s", "版本 %s"),
    "language": ("Язык", "Language", "Dil", "زبان", "语言"),
    "card_region": ("РЕГИОН", "REGION", "BÖLGE", "منطقه", "地区"),
    "card_mode": ("РЕЖИМ", "MODE", "MOD", "حالت", "模式"),
    "card_keys": ("КЛЮЧИ И ПОДПИСКИ", "KEYS AND SUBSCRIPTIONS", "ANAHTARLAR VE ABONELİKLER", "کلیدها و اشتراک‌ها", "密钥和订阅"),
    "card_dpi": ("ОБХОД DPI (BYEDPI)", "DPI BYPASS (BYEDPI)", "DPI ATLATMA (BYEDPI)", "دور زدن DPI ‏(ByeDPI)", "绕过 DPI（ByeDPI）"),
    "card_start": ("ЗАПУСК", "STARTUP", "BAŞLANGIÇ", "راه‌اندازی", "启动"),
    "by_ip": ("По IP", "By IP", "IP ile", "با IP", "按 IP"),
    "auto": ("Авто: %s", "Auto: %s", "Otomatik: %s", "خودکار: %s", "自动：%s"),
    "detected": ("Определено: %s.", "Detected by %s.", "Belirleme: %s.", "تشخیص: %s.", "检测依据：%s。"),
    "region_ru": ("Россия", "Russia", "Rusya", "روسیه", "俄罗斯"),
    "region_tr": ("Турция", "Turkey", "Türkiye", "ترکیه", "土耳其"),
    "region_ir": ("Иран", "Iran", "İran", "ایران", "伊朗"),
    "region_cn": ("Китай", "China", "Çin", "چین", "中国"),
    "region_other": ("Другая страна", "Other country", "Diğer ülke", "کشور دیگر", "其他国家"),
    "note_ir": ("Обход DPI в Иране помогает частично: многие сервисы заблокированы по IP. Для надёжной работы нужен ключ.",
                "DPI bypass in Iran helps only partly: many services are blocked by IP. A key is needed for reliable access.",
                "İran'da DPI atlatma kısmen işe yarar: birçok hizmet IP ile engelli. Güvenilir erişim için anahtar gerekir.",
                "دور زدن DPI در ایران فقط تا حدی کمک می‌کند: بسیاری از سرویس‌ها با IP مسدود هستند. برای اتصال پایدار کلید لازم است.",
                "在伊朗绕过 DPI 只能部分有效：许多服务按 IP 封锁。稳定访问需要密钥。"),
    "note_cn": ("В Китае заблокированы сами IP-адреса сервисов, локальный обход DPI не помогает. Нужен ключ (лучше VLESS+Reality или Hysteria2).",
                "In China the services' IP addresses themselves are blocked, local DPI bypass does not help. A key is needed (VLESS+Reality or Hysteria2 is best).",
                "Çin'de hizmetlerin IP adresleri engelli, yerel DPI atlatma işe yaramaz. Anahtar gerekir (en iyisi VLESS+Reality veya Hysteria2).",
                "در چین خود نشانی‌های IP سرویس‌ها مسدود است و دور زدن محلی DPI کمکی نمی‌کند. کلید لازم است (بهتر است VLESS+Reality یا Hysteria2).",
                "在中国，服务的 IP 地址本身被封锁，本地绕过 DPI 无效。需要密钥（最好是 VLESS+Reality 或 Hysteria2）。"),
    "mode_dpi": ("Обход DPI", "DPI bypass", "DPI atlatma", "دور زدن DPI", "绕过 DPI"),
    "mode_vpn": ("VPN по ключу", "VPN by key", "Anahtarla VPN", "VPN با کلید", "密钥 VPN"),
    "mode_hybrid": ("Гибрид", "Hybrid", "Hibrit", "ترکیبی", "混合"),
    "hint_dpi": ("Сайты из списка региона идут через локальный ByeDPI, остальное напрямую. Сервер не нужен.",
                 "Sites from the region's list go through local ByeDPI, everything else goes direct. No server needed.",
                 "Bölge listesindeki siteler yerel ByeDPI üzerinden, geri kalanı doğrudan gider. Sunucu gerekmez.",
                 "سایت‌های فهرست منطقه از ByeDPI محلی می‌روند و بقیه مستقیم. سرور لازم نیست.",
                 "地区列表中的网站经本地 ByeDPI，其余直连。无需服务器。"),
    "hint_vpn": ("Весь трафик идёт через сервер по ключу, кроме сайтов своей страны и локальной сети.",
                 "All traffic goes through the key's server, except sites of your own country and the local network.",
                 "Kendi ülkenizin siteleri ve yerel ağ hariç tüm trafik anahtarın sunucusundan geçer.",
                 "همه ترافیک از سرور کلید می‌رود، به‌جز سایت‌های کشور خودتان و شبکه محلی.",
                 "除本国网站和局域网外，所有流量都经密钥服务器。"),
    "hint_hybrid": ("Обход DPI для сайтов из списка, ключ для заблокированного по IP, остальное напрямую.",
                    "DPI bypass for listed sites, the key for what is blocked by IP, everything else direct.",
                    "Listedeki siteler için DPI atlatma, IP ile engellenenler için anahtar, gerisi doğrudan.",
                    "دور زدن DPI برای سایت‌های فهرست، کلید برای آنچه با IP مسدود است و بقیه مستقیم.",
                    "列表网站绕过 DPI，按 IP 封锁的走密钥，其余直连。"),
    "paste": ("Вставить", "Paste", "Yapıştır", "چسباندن", "粘贴"),
    "qr_screen": ("QR с экрана", "QR from screen", "Ekrandan QR", "QR از صفحه", "屏幕二维码"),
    "qr_file": ("QR из файла", "QR from file", "Dosyadan QR", "QR از فایل", "文件二维码"),
    "delete": ("Удалить", "Delete", "Sil", "حذف", "删除"),
    "autotest": ("Автоподбор", "Auto-select", "Otomatik seç", "انتخاب خودکار", "自动选择"),
    "strategy_none": ("— не нужен в этом регионе —", "— not needed in this region —", "— bu bölgede gerekmez —",
                      "— در این منطقه لازم نیست —", "— 该地区不需要 —"),
    "dpi_all": ("Все сайты через обход DPI, не только из списка", "All sites via DPI bypass, not only the listed ones",
                "Yalnızca listedekiler değil, tüm siteler DPI atlatma ile", "همه سایت‌ها از دور زدن DPI، نه فقط فهرست",
                "所有网站都绕过 DPI，不仅是列表中的"),
    "tun": ("TUN: весь трафик системы (нужны права администратора)", "TUN: all system traffic (needs administrator rights)",
            "TUN: tüm sistem trafiği (yönetici hakları gerekir)", "TUN: همه ترافیک سیستم (به دسترسی مدیر نیاز دارد)",
            "TUN：系统全部流量（需要管理员权限）"),
    "autostart": ("Запускать вместе с Windows (свёрнутым в трей)", "Start with Windows (minimized to tray)",
                  "Windows ile başlat (tepsiye küçültülmüş)", "اجرا همراه با ویندوز (کوچک‌شده در سینی)", "随 Windows 启动（最小化到托盘）"),
    "connect_on_start": ("Подключаться сразу после запуска", "Connect right after start", "Başladıktan hemen sonra bağlan",
                         "اتصال بلافاصله پس از اجرا", "启动后立即连接"),
    "status_connected": ("Подключено · %s · %s", "Connected · %s · %s", "Bağlandı · %s · %s", "متصل · %s · %s", "已连接 · %s · %s"),
    "sysproxy": ("системный прокси %s", "system proxy %s", "sistem proxy'si %s", "پروکسی سیستم %s", "系统代理 %s"),
    "status_idle": ("Нажмите на эмблему, чтобы подключиться", "Click the emblem to connect", "Bağlanmak için ambleme tıklayın",
                    "برای اتصال روی نشان کلیک کنید", "点击徽标以连接"),
    "working": ("Работаю…", "Working…", "Çalışıyor…", "در حال کار…", "处理中…"),
    "game": ("Блоки", "Blocks", "Bloklar", "بلوک‌ها", "方块"),

    # --- трей ---
    "tray_show": ("Показать окно", "Show window", "Pencereyi göster", "نمایش پنجره", "显示窗口"),
    "tray_connect": ("Подключить", "Connect", "Bağlan", "اتصال", "连接"),
    "tray_disconnect": ("Отключить", "Disconnect", "Bağlantıyı kes", "قطع اتصال", "断开"),
    "tray_quit": ("Выход", "Quit", "Çıkış", "خروج", "退出"),
    "tray_on": ("подключено, %s", "connected, %s", "bağlı, %s", "متصل، %s", "已连接，%s"),
    "tray_off": ("не подключено", "not connected", "bağlı değil", "متصل نیست", "未连接"),
    "tray_hint": ("Обход работает в трее. Выход — правой кнопкой по значку.",
                  "Obhod keeps running in the tray. To quit, right-click the icon.",
                  "Obhod tepside çalışmaya devam ediyor. Çıkmak için simgeye sağ tıklayın.",
                  "Obhod در سینی سیستم کار می‌کند. برای خروج روی نماد راست‌کلیک کنید.",
                  "Obhod 在托盘中继续运行。退出请右键单击图标。"),
    "already_running": ("Обход уже запущен — его значок в трее, рядом с часами.",
                        "Obhod is already running — its icon is in the tray, next to the clock.",
                        "Obhod zaten çalışıyor — simgesi saatin yanındaki tepside.",
                        "Obhod در حال اجراست — نماد آن در سینی کنار ساعت است.",
                        "Obhod 已在运行——图标在时钟旁的托盘中。"),

    # --- диалоги ---
    "tun_need_admin": ("Для режима TUN нужны права администратора.\n\nПерезапустить Обход от имени администратора?",
                       "TUN mode needs administrator rights.\n\nRestart Obhod as administrator?",
                       "TUN modu yönetici hakları gerektirir.\n\nObhod yönetici olarak yeniden başlatılsın mı?",
                       "حالت TUN به دسترسی مدیر نیاز دارد.\n\nObhod با دسترسی مدیر دوباره اجرا شود؟",
                       "TUN 模式需要管理员权限。\n\n以管理员身份重新启动 Obhod？"),
    "tun_offer": ("Включён режим TUN, для него нужны права администратора.\n\nПерезапустить Обход от имени администратора?\n"
                  "«Нет» — выключить TUN и работать через системный прокси.",
                  "TUN mode is on and needs administrator rights.\n\nRestart Obhod as administrator?\n"
                  "“No” turns TUN off and uses the system proxy.",
                  "TUN modu açık ve yönetici hakları gerektiriyor.\n\nObhod yönetici olarak yeniden başlatılsın mı?\n"
                  "“Hayır” TUN'u kapatır ve sistem proxy'sini kullanır.",
                  "حالت TUN روشن است و به دسترسی مدیر نیاز دارد.\n\nObhod با دسترسی مدیر دوباره اجرا شود؟\n"
                  "«خیر» TUN را خاموش می‌کند و از پروکسی سیستم استفاده می‌کند.",
                  "TUN 模式已开启，需要管理员权限。\n\n以管理员身份重新启动 Obhod？\n“否”将关闭 TUN 并使用系统代理。"),
    "engines_ask": ("Для работы нужны движки: %s.\n\nСкачать их с официальных страниц GitHub (sing-box и ByeDPI, около 35 МБ)?\n"
                    "Они будут лежать в %s",
                    "Obhod needs its engines: %s.\n\nDownload them from their official GitHub pages (sing-box and ByeDPI, about 35 MB)?\n"
                    "They will be stored in %s",
                    "Obhod'un motorlara ihtiyacı var: %s.\n\nResmi GitHub sayfalarından indirilsin mi (sing-box ve ByeDPI, yaklaşık 35 MB)?\n"
                    "Şuraya kaydedilecek: %s",
                    "Obhod به موتورها نیاز دارد: %s.\n\nاز صفحه‌های رسمی GitHub دریافت شوند؟ (sing-box و ByeDPI، حدود ۳۵ مگابایت)\n"
                    "محل ذخیره: %s",
                    "Obhod 需要引擎：%s。\n\n从官方 GitHub 页面下载吗（sing-box 和 ByeDPI，约 35 MB）？\n将保存在 %s"),
    "cert_title": ("Обход — сертификат не подтверждён", "Obhod — certificate not verified", "Obhod — sertifika doğrulanmadı",
                   "Obhod — گواهی تأیید نشد", "Obhod — 证书未验证"),
    "cert_fail": ("Не удалось проверить сервер подписки %s: %s.", "Could not verify the subscription server %s: %s.",
                  "Abonelik sunucusu %s doğrulanamadı: %s.", "سرور اشتراک %s بررسی نشد: %s.", "无法验证订阅服务器 %s：%s。"),
    "cert_text": (
        "Сервер подписки %s не подтвердил свою подлинность:\n%s.\n\n"
        "Так бывает, если у сервера самоподписанный сертификат или если сеть подменяет сертификаты "
        "(корпоративный фильтр, антивирус).\n\nОтпечаток сертификата (SHA-256):\n%s\n\n"
        "Доверяйте, только если уверены в сервере — например, отпечаток совпадает с указанным в панели "
        "вашего VPN. В подменённой подписке могут оказаться чужие ключи, и трафик уйдёт на чужой сервер.\n\n"
        "Доверять этому сертификату и скачать подписку?",
        "The subscription server %s did not prove its identity:\n%s.\n\n"
        "This happens when the server has a self-signed certificate or when the network replaces certificates "
        "(a corporate filter, an antivirus).\n\nCertificate fingerprint (SHA-256):\n%s\n\n"
        "Trust it only if you are sure about the server — for example, the fingerprint matches the one in your VPN panel. "
        "A forged subscription may contain someone else's keys, and your traffic would go to their server.\n\n"
        "Trust this certificate and download the subscription?",
        "Abonelik sunucusu %s kimliğini kanıtlamadı:\n%s.\n\n"
        "Sunucunun kendinden imzalı sertifikası varsa veya ağ sertifikaları değiştiriyorsa (kurumsal filtre, antivirüs) "
        "böyle olur.\n\nSertifika parmak izi (SHA-256):\n%s\n\n"
        "Yalnızca sunucudan eminseniz güvenin — örneğin parmak izi VPN panelinizdekiyle aynıysa. Sahte bir abonelikte "
        "başkasının anahtarları olabilir ve trafiğiniz onun sunucusuna gider.\n\n"
        "Bu sertifikaya güvenip abonelik indirilsin mi?",
        "سرور اشتراک %s هویت خود را ثابت نکرد:\n%s.\n\n"
        "این وقتی پیش می‌آید که سرور گواهی خودامضا داشته باشد یا شبکه گواهی‌ها را جایگزین کند (فیلتر سازمانی، آنتی‌ویروس)."
        "\n\nاثر انگشت گواهی (SHA-256):\n%s\n\n"
        "فقط اگر به سرور مطمئن هستید اعتماد کنید — مثلاً اگر اثر انگشت با پنل VPN شما یکی است. در اشتراک جعلی ممکن است "
        "کلیدهای دیگران باشد و ترافیک شما به سرور آن‌ها برود.\n\n"
        "به این گواهی اعتماد شود و اشتراک دریافت شود؟",
        "订阅服务器 %s 未能证明其身份：\n%s。\n\n"
        "当服务器使用自签名证书，或网络替换证书（企业过滤器、杀毒软件）时会出现这种情况。\n\n证书指纹（SHA-256）：\n%s\n\n"
        "只有在确信服务器可靠时才信任——例如指纹与 VPN 面板中显示的一致。伪造的订阅可能包含他人的密钥，你的流量会流向他人的服务器。\n\n"
        "信任此证书并下载订阅？"),
    "qr_dialog": ("Картинка с QR-кодом ключа", "Image with the key's QR code", "Anahtarın QR kodlu resmi",
                  "تصویر کد QR کلید", "含密钥二维码的图片"),
    "images": ("Картинки", "Images", "Resimler", "تصاویر", "图片"),
    "all_files": ("Все файлы", "All files", "Tüm dosyalar", "همه فایل‌ها", "所有文件"),

    # --- журнал ---
    "tag_error": ("ошибка", "error", "hata", "خطا", "错误"),
    "tag_test": ("тест", "test", "test", "آزمون", "测试"),
    "tag_download": ("загрузка", "download", "indirme", "دریافت", "下载"),
    "log_proxy_restored": ("системный прокси остался после прошлого сбоя — вернул прежние настройки",
                           "the system proxy was left over from a crash — restored the previous settings",
                           "sistem proxy'si önceki çökmeden kalmıştı — eski ayarlar geri yüklendi",
                           "پروکسی سیستم از خرابی قبلی مانده بود — تنظیمات قبلی برگردانده شد",
                           "系统代理在上次崩溃后残留——已恢复之前的设置"),
    "log_no_engines": ("нет движков: %s", "engines missing: %s", "motorlar eksik: %s", "موتورها موجود نیستند: %s", "缺少引擎：%s"),
    "log_no_libs": ("трей и QR выключены: нет библиотек. Установите: py -m pip install --user -r requirements.txt",
                    "tray and QR are off: libraries missing. Install: py -m pip install --user -r requirements.txt",
                    "tepsi ve QR kapalı: kütüphaneler eksik. Kurun: py -m pip install --user -r requirements.txt",
                    "سینی و QR خاموش است: کتابخانه‌ها نیستند. نصب: py -m pip install --user -r requirements.txt",
                    "托盘和二维码已关闭：缺少库。安装：py -m pip install --user -r requirements.txt"),
    "log_elev_cancelled": ("перезапуск от администратора отменён — TUN выключен", "restart as administrator cancelled — TUN is off",
                           "yönetici olarak yeniden başlatma iptal edildi — TUN kapalı", "اجرای دوباره با دسترسی مدیر لغو شد — TUN خاموش است",
                           "已取消以管理员身份重启——TUN 已关闭"),
    "log_tun_off": ("TUN выключен: нет прав администратора", "TUN is off: no administrator rights", "TUN kapalı: yönetici hakları yok",
                    "TUN خاموش است: دسترسی مدیر نیست", "TUN 已关闭：没有管理员权限"),
    "log_autostart_on": ("автозапуск включён: %s", "autostart on: %s", "otomatik başlatma açık: %s", "اجرای خودکار روشن: %s", "开机自启已开启：%s"),
    "log_autostart_off": ("автозапуск выключен", "autostart off", "otomatik başlatma kapalı", "اجرای خودکار خاموش", "开机自启已关闭"),
    "log_autostart_fail": ("не удалось изменить автозапуск: %s", "could not change autostart: %s", "otomatik başlatma değiştirilemedi: %s",
                           "تغییر اجرای خودکار ممکن نشد: %s", "无法更改开机自启：%s"),
    "log_clipboard_empty": ("в буфере обмена нет ни текста, ни картинки", "the clipboard has neither text nor an image",
                            "panoda metin de resim de yok", "در کلیپ‌بورد نه متن هست نه تصویر", "剪贴板中既没有文本也没有图片"),
    "src_clipboard": ("картинка из буфера", "clipboard image", "panodaki resim", "تصویر کلیپ‌بورد", "剪贴板图片"),
    "src_screen": ("экран", "screen", "ekran", "صفحه", "屏幕"),
    "log_qr_none": ("QR-код не найден: %s", "no QR code found: %s", "QR kodu bulunamadı: %s", "کد QR پیدا نشد: %s", "未找到二维码：%s"),
    "log_qr_found": ("QR-кодов (%s): %d", "QR codes (%s): %d", "QR kodları (%s): %d", "کدهای QR ‏(%s): %d", "二维码（%s）：%d"),
    "log_sub_loading": ("скачиваю подписку…", "downloading the subscription…", "abonelik indiriliyor…", "در حال دریافت اشتراک…", "正在下载订阅…"),
    "log_cert": ("сертификат %s не подтверждён: %s", "certificate of %s not verified: %s", "%s sertifikası doğrulanmadı: %s",
                 "گواهی %s تأیید نشد: %s", "%s 的证书未验证：%s"),
    "log_cert_trusted": ("доверяю сертификату %s: %s…", "trusting the certificate of %s: %s…", "%s sertifikasına güveniliyor: %s…",
                         "اعتماد به گواهی %s: %s…", "信任 %s 的证书：%s…"),
    "log_sub_rejected": ("подписка не загружена: сертификат не подтверждён", "subscription not loaded: certificate not verified",
                         "abonelik yüklenmedi: sertifika doğrulanmadı", "اشتراک بارگذاری نشد: گواهی تأیید نشد", "未加载订阅：证书未验证"),
    "log_bad_key": ("не разобрал ключ: %s", "could not parse a key: %s", "anahtar çözümlenemedi: %s", "کلید خوانده نشد: %s", "无法解析密钥：%s"),
    "log_keys_added": ("добавлено ключей: %d", "keys added: %d", "eklenen anahtar: %d", "کلیدهای افزوده: %d", "已添加密钥：%d"),
    "log_engines_manual": ("без движков подключиться нельзя. Можно положить их в %s вручную",
                           "cannot connect without engines. You can put them into %s manually",
                           "motorlar olmadan bağlanılamaz. Onları %s klasörüne elle koyabilirsiniz",
                           "بدون موتورها اتصال ممکن نیست. می‌توانید آن‌ها را دستی در %s بگذارید",
                           "没有引擎无法连接。可以手动放到 %s"),
    "log_engines_ready": ("движки на месте", "engines are in place", "motorlar hazır", "موتورها آماده‌اند", "引擎已就绪"),
    "log_reconnect": ("настройки изменились — переподключаюсь", "settings changed — reconnecting", "ayarlar değişti — yeniden bağlanıyor",
                      "تنظیمات تغییر کرد — اتصال دوباره", "设置已更改——正在重新连接"),
    "log_connected": ("подключено: %s, %s", "connected: %s, %s", "bağlandı: %s, %s", "متصل: %s، %s", "已连接：%s，%s"),
    "log_disconnected": ("отключено", "disconnected", "bağlantı kesildi", "قطع شد", "已断开"),
    "log_engine_died": ("движок остановился сам — снимаю системный прокси", "an engine stopped by itself — removing the system proxy",
                        "bir motor kendiliğinden durdu — sistem proxy'si kaldırılıyor", "یک موتور خودش متوقف شد — پروکسی سیستم برداشته می‌شود",
                        "引擎自行停止——正在移除系统代理"),
    "log_lang": ("язык интерфейса: %s", "interface language: %s", "arayüz dili: %s", "زبان رابط: %s", "界面语言：%s"),
    "test_region": ("автоподбор для региона «%s»", "auto-select for region “%s”", "“%s” bölgesi için otomatik seçim",
                    "انتخاب خودکار برای منطقه «%s»", "为地区“%s”自动选择"),
    "test_all_open": ("все тестовые сайты открываются напрямую — проверяю стратегии на полном списке",
                      "all test sites open directly — checking the strategies on the full list",
                      "tüm test siteleri doğrudan açılıyor — stratejiler tam listede deneniyor",
                      "همه سایت‌های آزمایشی مستقیم باز می‌شوند — راهبردها روی فهرست کامل بررسی می‌شوند",
                      "所有测试网站都能直接打开——正在用完整列表检查策略"),
    "test_chosen": ("выбрана: %s", "selected: %s", "seçildi: %s", "انتخاب شد: %s", "已选择：%s"),
    "test_none": ("ни одна стратегия не помогла. Нужен ключ (режим «VPN по ключу» или «Гибрид»).",
                  "no strategy helped. A key is needed (“VPN by key” or “Hybrid” mode).",
                  "hiçbir strateji işe yaramadı. Anahtar gerekir (“Anahtarla VPN” veya “Hibrit” modu).",
                  "هیچ راهبردی کمک نکرد. کلید لازم است (حالت «VPN با کلید» یا «ترکیبی»).",
                  "没有策略有效。需要密钥（“密钥 VPN”或“混合”模式）。"),
    "test_direct": ("напрямую %s: %s", "direct %s: %s", "doğrudan %s: %s", "مستقیم %s: %s", "直连 %s：%s"),
    "test_opened": ("открылся", "opened", "açıldı", "باز شد", "已打开"),
    "test_failed": ("не открылся", "did not open", "açılmadı", "باز نشد", "未打开"),
    "test_doh": ("имена резолвлю через DoH %s: DNS провайдера в этом регионе подменяет адреса",
                 "resolving names via DoH %s: the ISP's DNS in this region spoofs addresses",
                 "adlar DoH %s ile çözülüyor: bu bölgede sağlayıcının DNS'i adresleri değiştiriyor",
                 "نام‌ها از DoH %s خوانده می‌شوند: DNS ارائه‌دهنده در این منطقه نشانی‌ها را جعل می‌کند",
                 "通过 DoH %s 解析域名：该地区运营商的 DNS 会伪造地址"),
    "test_bad_args": ("ByeDPI не принял параметры", "ByeDPI rejected the parameters", "ByeDPI parametreleri kabul etmedi",
                      "ByeDPI پارامترها را نپذیرفت", "ByeDPI 拒绝了参数"),

    # --- ошибки из core ---
    "err_tun_admin": ("TUN включён, но Обход запущен без прав администратора. Снимите галочку TUN или включите её снова — "
                      "Обход предложит перезапуск.",
                      "TUN is on, but Obhod runs without administrator rights. Untick TUN, or tick it again and Obhod will offer a restart.",
                      "TUN açık ama Obhod yönetici hakları olmadan çalışıyor. TUN işaretini kaldırın ya da yeniden işaretleyin; "
                      "Obhod yeniden başlatmayı önerecek.",
                      "TUN روشن است اما Obhod بدون دسترسی مدیر اجرا شده. تیک TUN را بردارید یا دوباره بزنید تا Obhod اجرای دوباره را پیشنهاد کند.",
                      "TUN 已开启，但 Obhod 没有以管理员身份运行。取消勾选 TUN，或重新勾选，Obhod 会提示重启。"),
    "err_need_key": ("Для этого режима нужен ключ: вставьте ссылку vless://, hy2://, trojan://, ss:// или подписку.",
                     "This mode needs a key: paste a vless://, hy2://, trojan://, ss:// link or a subscription.",
                     "Bu mod anahtar gerektirir: vless://, hy2://, trojan://, ss:// bağlantısı veya abonelik yapıştırın.",
                     "این حالت به کلید نیاز دارد: پیوند vless://، hy2://، trojan://، ss:// یا اشتراک را بچسبانید.",
                     "此模式需要密钥：请粘贴 vless://、hy2://、trojan://、ss:// 链接或订阅。"),
    "err_no_dpi": ("В этом регионе обход DPI не работает, нужен ключ.", "DPI bypass does not work in this region, a key is needed.",
                   "Bu bölgede DPI atlatma çalışmaz, anahtar gerekir.", "در این منطقه دور زدن DPI کار نمی‌کند، کلید لازم است.",
                   "该地区绕过 DPI 无效，需要密钥。"),
    "err_config": ("sing-box отклонил конфиг: %s", "sing-box rejected the config: %s", "sing-box yapılandırmayı reddetti: %s",
                   "sing-box پیکربندی را رد کرد: %s", "sing-box 拒绝了配置：%s"),
    "err_no_engines": ("нет движков: %s. Запустите scripts/fetch_bins.py", "engines missing: %s. Run scripts/fetch_bins.py",
                       "motorlar eksik: %s. scripts/fetch_bins.py çalıştırın", "موتورها نیستند: %s. scripts/fetch_bins.py را اجرا کنید",
                       "缺少引擎：%s。请运行 scripts/fetch_bins.py"),
    "log_orphans": ("закрыл оставшиеся от прошлого запуска движки: %s", "closed engines left over from the last run: %s",
                    "önceki çalışmadan kalan motorlar kapatıldı: %s", "موتورهای مانده از اجرای قبلی بسته شدند: %s",
                    "已关闭上次运行残留的引擎：%s"),
    "err_no_strategy": ("не выбрана стратегия обхода DPI", "no DPI bypass strategy selected", "DPI atlatma stratejisi seçilmedi",
                        "راهبرد دور زدن DPI انتخاب نشده", "未选择绕过 DPI 策略"),
    "err_no_nic": ("не нашёл адрес сетевой карты для ByeDPI — TUN с обходом DPI не запустить",
                   "could not find the network card's address for ByeDPI — TUN with DPI bypass cannot start",
                   "ByeDPI için ağ kartı adresi bulunamadı — DPI atlatmalı TUN başlatılamıyor",
                   "نشانی کارت شبکه برای ByeDPI پیدا نشد — TUN با دور زدن DPI اجرا نمی‌شود",
                   "找不到供 ByeDPI 使用的网卡地址——无法启动带绕过 DPI 的 TUN"),
    "err_died": ("движок завершился сразу после запуска: %s (подробности в журнале)",
                 "an engine exited right after start: %s (details in the log)",
                 "motor başladıktan hemen sonra kapandı: %s (ayrıntılar günlükte)",
                 "موتور بلافاصله پس از اجرا بسته شد: %s (جزئیات در گزارش)",
                 "引擎启动后立即退出：%s（详见日志）"),
    "fetch_get": ("скачиваю %s…", "downloading %s…", "%s indiriliyor…", "در حال دریافت %s…", "正在下载 %s…"),
    "fetch_done": ("готово: %s", "done: %s", "tamam: %s", "انجام شد: %s", "完成：%s"),
    "err_fetch": ("не удалось скачать %s: %s. Если GitHub заблокирован, подключите обход другим способом или положите файл в %s вручную",
                  "could not download %s: %s. If GitHub is blocked, connect another way or put the file into %s manually",
                  "%s indirilemedi: %s. GitHub engelliyse başka bir yolla bağlanın veya dosyayı elle %s klasörüne koyun",
                  "دریافت %s ممکن نشد: %s. اگر GitHub مسدود است، از راه دیگری وصل شوید یا فایل را دستی در %s بگذارید",
                  "无法下载 %s：%s。如果 GitHub 被封锁，请用其他方式连接，或手动把文件放到 %s"),
    "err_not_in_archive": ("в архиве нет %s", "%s is not in the archive", "arşivde %s yok", "%s در بایگانی نیست", "压缩包中没有 %s"),
    "err_qr_libs": ("Для QR нужны библиотеки: py -m pip install --user -r requirements.txt",
                    "QR needs libraries: py -m pip install --user -r requirements.txt",
                    "QR için kütüphaneler gerekir: py -m pip install --user -r requirements.txt",
                    "QR به کتابخانه‌ها نیاز دارد: py -m pip install --user -r requirements.txt",
                    "二维码需要库：py -m pip install --user -r requirements.txt"),
    "err_key_port": ("в ключе нет порта", "the key has no port", "anahtarda port yok", "کلید پورت ندارد", "密钥中没有端口"),
    "err_key_host": ("в ключе нет адреса сервера", "the key has no server address", "anahtarda sunucu adresi yok",
                     "کلید نشانی سرور ندارد", "密钥中没有服务器地址"),
    "err_key_pbk": ("в Reality-ключе нет публичного ключа (pbk)", "the Reality key has no public key (pbk)",
                    "Reality anahtarında açık anahtar (pbk) yok", "کلید Reality کلید عمومی (pbk) ندارد", "Reality 密钥中没有公钥（pbk）"),
    "err_key_transport": ("транспорт «%s» пока не поддерживается (sing-box его не умеет)",
                          "transport “%s” is not supported yet (sing-box cannot do it)",
                          "“%s” aktarımı henüz desteklenmiyor (sing-box bunu yapamıyor)",
                          "ترابرد «%s» هنوز پشتیبانی نمی‌شود (sing-box آن را ندارد)",
                          "暂不支持传输“%s”（sing-box 不支持）"),
    "err_key_vmess": ("vmess-ключ не похож на base64 JSON", "the vmess key does not look like base64 JSON",
                      "vmess anahtarı base64 JSON'a benzemiyor", "کلید vmess شبیه base64 JSON نیست", "vmess 密钥不像 base64 JSON"),
    "err_key_ss_plugin": ("ss с плагином (obfs/v2ray-plugin) пока не поддерживается", "ss with a plugin (obfs/v2ray-plugin) is not supported yet",
                          "eklentili ss (obfs/v2ray-plugin) henüz desteklenmiyor", "ss با افزونه (obfs/v2ray-plugin) هنوز پشتیبانی نمی‌شود",
                          "暂不支持带插件的 ss（obfs/v2ray-plugin）"),
    "err_key_ss": ("в ss-ключе нет метода или пароля", "the ss key has no method or password", "ss anahtarında yöntem veya parola yok",
                   "کلید ss روش یا گذرواژه ندارد", "ss 密钥中没有加密方法或密码"),
    "err_key_format": ("неизвестный формат ключа: %s…", "unknown key format: %s…", "bilinmeyen anahtar biçimi: %s…",
                       "قالب کلید ناشناخته: %s…", "未知的密钥格式：%s…"),
    "err_cert_changed": ("отпечаток сертификата изменился с прошлого раза", "the certificate fingerprint has changed since last time",
                         "sertifika parmak izi geçen seferden beri değişti", "اثر انگشت گواهی از دفعه قبل تغییر کرده",
                         "证书指纹与上次不同"),
    "err_sub_redirect": ("подписка перенаправляет на %s — вставьте этот адрес", "the subscription redirects to %s — paste that address",
                         "abonelik %s adresine yönlendiriyor — bu adresi yapıştırın", "اشتراک به %s هدایت می‌کند — این نشانی را بچسبانید",
                         "订阅重定向到 %s——请粘贴该地址"),
    "err_sub_status": ("сервер подписки ответил %s %s", "the subscription server answered %s %s", "abonelik sunucusu %s %s yanıtı verdi",
                       "سرور اشتراک پاسخ داد %s %s", "订阅服务器返回 %s %s"),

    # --- игра «Блоки» ---
    "g_score": ("СЧЁТ", "SCORE", "PUAN", "امتیاز", "得分"),
    "g_best": ("Рекорд: %d", "Best: %d", "Rekor: %d", "رکورد: %d", "最高分：%d"),
    "g_level": ("Уровень %d", "Level %d", "Seviye %d", "مرحله %d", "第 %d 级"),
    "g_lines": ("Линий: %d", "Lines: %d", "Satır: %d", "خط‌ها: %d", "行数：%d"),
    "g_next": ("Дальше", "Next", "Sıradaki", "بعدی", "下一个"),
    "g_pause": ("Пауза", "Paused", "Duraklatıldı", "مکث", "已暂停"),
    "g_over": ("Игра окончена", "Game over", "Oyun bitti", "بازی تمام شد", "游戏结束"),
    "g_new_best": ("Новый рекорд!", "New best!", "Yeni rekor!", "رکورد تازه!", "新纪录！"),
    "g_again": ("R — заново", "R — play again", "R — yeniden oyna", "R — بازی دوباره", "R —— 再玩一次"),
    "g_keys": ("← → двигать   ↑ повернуть\n↓ вниз   Пробел — сбросить\nP — пауза   R — заново",
               "← → move   ↑ rotate\n↓ soft drop   Space — hard drop\nP — pause   R — restart",
               "← → taşı   ↑ döndür\n↓ hızlı indir   Boşluk — bırak\nP — duraklat   R — yeniden",
               "← → جابه‌جایی   ↑ چرخش\n↓ پایین   فاصله — رها کردن\nP — مکث   R — از نو",
               "← → 移动   ↑ 旋转\n↓ 加速下落   空格 —— 直接落下\nP —— 暂停   R —— 重新开始"),
}
