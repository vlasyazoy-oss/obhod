"""Обход — черновой клиент: обход DPI как у Zapret плюс VPN по своему ключу как у Hiddify.

    py app.py           обычный запуск (на macOS: python3 app.py)
    py app.py --tray    свёрнутым в трей (так запускает автозапуск); на macOS — свёрнутым в Dock
"""
import ctypes
import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from urllib.parse import urlsplit
from tkinter import filedialog, messagebox, ttk

from core import autostart, autotest, config as cfg, emblem, keys, qr, region as reg, sysproxy, tray
from core.engine import DATA, Engine, EngineError, Log, missing_bins
from core.fetch import FetchError, fetch
from core.osinfo import MAC, font, mono
from core.paths import BIN, launch_command
from core.state import State
from core.subscription import CertError, trusted_context
from core.version import VERSION

MIXED_PORT = 2080
DPI_PORT = 1080
EMBLEM_W = 280
MUTEX_NAME = "Local\\ObhodSingleInstance"

# Палитра от эмблемы: тёмный фон с оттенком сливового, синий флага как акцент
BG, CARD, FG, MUTED = "#16151b", "#221f29", "#ecebf0", "#9d98a6"
ACCENT, ACCENT_HI, OK, BAD = "#2f53b5", "#3a62cc", "#3ecf8e", "#ff6b6b"


def is_admin():
    if MAC:
        return os.geteuid() == 0
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def flush_dns():
    """Очистить кэш DNS Windows (как ipconfig /flushdns, без прав администратора). Иначе программы ещё
    несколько минут ходят на подменённые провайдером адреса, полученные до включения TUN."""
    if MAC:
        try:
            subprocess.run(["dscacheutil", "-flushcache"], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
        return
    try:
        ctypes.windll.dnsapi.DnsFlushResolverCache()
    except (AttributeError, OSError):
        pass


def already_running(wait=0.0):
    """Второй экземпляр подрался бы с первым за порты и системный прокси.

    wait — сколько секунд ждать, пока прежний экземпляр закроется (перезапуск от администратора).
    """
    if MAC:
        return _locked_by_other()
    k32 = ctypes.windll.kernel32
    deadline = time.time() + wait
    while True:
        handle = k32.CreateMutexW(None, False, MUTEX_NAME)
        if k32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
            return False
        k32.CloseHandle(handle)
        if time.time() >= deadline:
            return True
        time.sleep(0.2)


_lock_file = None


def _locked_by_other():
    """macOS: замок на data/obhod.lock держит первый экземпляр, пока он работает (снимается и при сбое)."""
    global _lock_file
    import fcntl
    os.makedirs(DATA, exist_ok=True)
    _lock_file = open(os.path.join(DATA, "obhod.lock"), "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


def relaunch_as_admin():
    """Запускает эту же программу с повышением прав (окно UAC). True, если пользователь согласился."""
    exe, args = launch_command("--elevated")
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, os.path.dirname(exe), 1)
    return rc > 32


class App:
    def __init__(self, root, start_hidden=False):
        self.root = root
        self.q = queue.Queue()
        self.log = Log(on_line=lambda line: self.q.put(("log", line)))
        self.engine = Engine(self.log)
        self.state = State.load()
        self.regions = cfg.load_regions()
        self.detected, self.detected_how = reg.detect_offline()
        self.busy = False
        self._phase = 0.0
        self._reconnect_pending = False

        root.title("Обход — администратор" if is_admin() else "Обход")
        # Размеры в «логических» пикселях: при масштабе Windows 125–150 % окно не должно сжиматься.
        # На Mac Tk сам учитывает Retina, а дюйм у него 72 точки — там множитель не нужен
        self.k = 1.0 if MAC else root.winfo_fpixels("1i") / 96
        height = min(self.px(820), root.winfo_screenheight() - self.px(70))
        root.geometry(f"{self.px(480)}x{height}")
        root.minsize(self.px(440), min(self.px(600), height))
        root.configure(bg=BG)
        icon = os.path.join(DATA, "icon.png")
        if not os.path.exists(icon):
            os.makedirs(DATA, exist_ok=True)
            emblem.write_png(icon, 64)
        self._icon = tk.PhotoImage(file=icon)
        root.iconphoto(True, self._icon)
        self.tray = None
        self._tray_state = None
        if tray.available():
            post = lambda kind: (lambda: self.q.put((kind, None)))
            self.tray = tray.Tray(on_show=post("show"), on_toggle=post("toggle"), on_quit=post("quit"))
            self.tray.start()
        self._style()
        self._build()
        self._refresh_all()
        root.protocol("WM_DELETE_WINDOW", self.close_window)
        root.after(100, self._poll)

        if sysproxy.restore():
            self.log.write("obhod", "системный прокси остался после прошлого сбоя — вернул прежние настройки")
        if missing_bins():
            self.log.write("obhod", "нет движков: " + ", ".join(missing_bins()))
            root.after(300, self.ensure_engines)
        if not qr.available() or (not self.tray and not MAC):
            self.log.write("obhod", "трей или QR выключены: нет библиотек. Установите их: pip install -r requirements.txt")
        autostart.refresh()
        if MAC:
            # Cmd+Q и «Завершить» в Dock: сначала вернуть системный прокси, иначе интернет пропадёт
            root.createcommand("tk::mac::Quit", self.quit)
            if self.state.tun:
                self.state.tun = False  # TUN на macOS пока нет
                self.state.save()
        elif self.state.tun and not is_admin():
            root.after(400, self._offer_elevation)
        if start_hidden and self.tray:
            root.withdraw()
        elif start_hidden and MAC:
            root.iconify()
        if self.state.connect_on_start:
            root.after(500, self.toggle)

    # ---------- вид ----------
    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=CARD, font=font(10))
        s.configure("Card.TFrame", background=CARD)
        s.configure("Card.TLabel", background=CARD, foreground=FG)
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=font(9))
        s.configure("H.TLabel", background=BG, foreground=FG, font=font(16, bold=True))
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=font(9))
        s.configure("TButton", background=CARD, foreground=FG, borderwidth=0, padding=(10, 6))
        s.map("TButton", background=[("active", "#2a2e37"), ("disabled", CARD)], foreground=[("disabled", MUTED)])
        s.configure("Accent.TButton", background=ACCENT, foreground="white")
        s.map("Accent.TButton", background=[("active", ACCENT_HI)])
        for w in ("TRadiobutton", "TCheckbutton"):
            s.configure(w, background=CARD, foreground=FG, indicatorbackground="#3d3947", indicatorforeground=FG,
                        indicatormargin=(0, 0, 6, 0), upperbordercolor="#4a4555", lowerbordercolor="#4a4555")
            s.map(w, foreground=[("disabled", MUTED)], background=[("active", CARD)],
                  indicatorbackground=[("selected", ACCENT), ("active", "#2a2733")])
        s.configure("TCombobox", arrowcolor=FG, background=CARD, foreground=FG, bordercolor="#3a3644",
                    lightcolor=CARD, darkcolor=CARD, padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", BG)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", BG)], selectforeground=[("readonly", FG)])
        self.root.option_add("*TCombobox*Listbox.background", CARD)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        s.configure("Vertical.TScrollbar", background=CARD, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED,
                    lightcolor=CARD, darkcolor=CARD)

    def _card(self, parent, title):
        f = ttk.Frame(parent, style="Card.TFrame", padding=12)
        f.pack(fill="x", pady=(0, 10))
        ttk.Label(f, text=title, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        return f

    def _build(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer)
        head.pack(fill="x", pady=(0, 8))
        ttk.Label(head, text="Обход", style="H.TLabel").pack(side="left")
        ttk.Label(head, text=f"версия {VERSION}", style="Sub.TLabel").pack(side="left", padx=8, pady=(6, 0))

        # Эмблема — она же кнопка подключения
        mid = ttk.Frame(outer)
        mid.pack(pady=(0, 10))
        self.canvas = tk.Canvas(mid, width=self.px(EMBLEM_W), height=self.px(EMBLEM_W * emblem.H / emblem.W), bg=BG,
                                highlightthickness=0, cursor="hand2")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.toggle())
        self.status = ttk.Label(mid, text="", style="Sub.TLabel", font=font(10, bold=True))
        self.status.pack(pady=(8, 0))

        # Всё, что ниже эмблемы, прокручивается: на ноутбуках с масштабом 150 % окно не помещается целиком
        wrap = ttk.Frame(outer)
        wrap.pack(fill="both", expand=True)
        scroll = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(wrap, orient="vertical", command=scroll.yview)
        scroll.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(scroll)
        inner = scroll.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda e: scroll.itemconfigure(inner, width=e.width - self.px(6)))
        # Windows шлёт колесо шагами по 120, macOS — мелкими значениями (1, 2, 3…)
        self.root.bind_all("<MouseWheel>",
                           lambda e: scroll.yview_scroll(-(e.delta if MAC else e.delta // 120), "units"))

        # Регион
        c = self._card(body, "РЕГИОН")
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x")
        self.region_var = tk.StringVar()
        self.region_box = ttk.Combobox(row, textvariable=self.region_var, state="readonly", width=28)
        self.region_box.pack(side="left")
        self.region_box.bind("<<ComboboxSelected>>", self._on_region)
        ttk.Button(row, text="По IP", command=self._detect_ip).pack(side="right")
        self.region_hint = ttk.Label(c, style="Muted.TLabel", wraplength=self.px(410), justify="left")
        self.region_hint.pack(anchor="w", pady=(6, 0))

        # Режим
        c = self._card(body, "РЕЖИМ")
        self.mode_var = tk.StringVar()
        self.mode_buttons = {}
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x")
        for code, title in cfg.MODES.items():
            b = ttk.Radiobutton(row, text=title, value=code, variable=self.mode_var, command=self._on_mode)
            b.pack(side="left", padx=(0, 14))
            self.mode_buttons[code] = b
        self.mode_hint = ttk.Label(c, style="Muted.TLabel", wraplength=self.px(410), justify="left")
        self.mode_hint.pack(anchor="w", pady=(6, 0))

        # Ключи
        c = self._card(body, "КЛЮЧИ И ПОДПИСКИ")
        self.key_list = tk.Listbox(c, height=3, bg=BG, fg=FG, selectbackground=ACCENT, borderwidth=0,
                                   highlightthickness=0, activestyle="none", font=font(10))
        self.key_list.pack(fill="x")
        self.key_list.bind("<<ListboxSelect>>", self._on_key_select)
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="Вставить", style="Accent.TButton", command=self.paste_key).pack(side="left")
        self.qr_buttons = [ttk.Button(row, text="QR с экрана", command=self.scan_screen),
                           ttk.Button(row, text="QR из файла", command=self.scan_file)]
        for b in self.qr_buttons:
            b.pack(side="left", padx=(6, 0))
            if not qr.available():
                b.state(["disabled"])
        ttk.Button(row, text="Удалить", command=self.delete_key).pack(side="right")

        # Стратегия
        c = self._card(body, "ОБХОД DPI (SING-BOX)" if MAC else "ОБХОД DPI (BYEDPI)")
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x")
        self.strat_var = tk.StringVar()
        self.strat_box = ttk.Combobox(row, textvariable=self.strat_var, state="readonly", width=30)
        self.strat_box.pack(side="left")
        self.strat_box.bind("<<ComboboxSelected>>", self._on_strategy)
        self.autotest_btn = ttk.Button(row, text="Автоподбор", command=self.run_autotest)
        self.autotest_btn.pack(side="right")
        self.tun_var = tk.BooleanVar()
        self.dpi_all_var = tk.BooleanVar()
        ttk.Checkbutton(c, text="Все сайты через обход DPI, не только из списка", variable=self.dpi_all_var,
                        command=self._on_options).pack(anchor="w", pady=(8, 0))
        tun = ttk.Checkbutton(c, text="TUN: пока только в Windows-версии" if MAC else
                              "TUN: весь трафик системы (нужны права администратора)",
                              variable=self.tun_var, command=self._on_options)
        tun.pack(anchor="w")
        if MAC:
            tun.state(["disabled"])

        # Запуск
        c = self._card(body, "ЗАПУСК")
        self.autostart_var = tk.BooleanVar()
        self.connect_on_start_var = tk.BooleanVar()
        ttk.Checkbutton(c, text="Запускать при входе в macOS (свёрнутым в Dock)" if MAC else
                        "Запускать вместе с Windows (свёрнутым в трей)", variable=self.autostart_var,
                        command=self._on_autostart).pack(anchor="w")
        ttk.Checkbutton(c, text="Подключаться сразу после запуска", variable=self.connect_on_start_var,
                        command=self._on_options).pack(anchor="w")

        # Журнал
        self.log_box = tk.Text(body, height=6, bg=CARD, fg=MUTED, borderwidth=0, font=mono(8), wrap="word")
        self.log_box.pack(fill="x")
        self.log_box.configure(state="disabled")

    def px(self, n):
        return round(n * self.k)

    # ---------- состояние ----------
    def region_code(self):
        return self.detected if self.state.region == "auto" else self.state.region

    def region(self):
        return self.regions[self.region_code()]

    def mode(self):
        r = self.region()
        """Выбор пользователя, если он выполним; иначе режим по умолчанию для региона."""
        m = self.state.mode or cfg.default_mode(r, bool(self.state.keys))
        if m in ("dpi", "hybrid") and not r["dpi_supported"]:
            m = "vpn"
        if m in ("vpn", "hybrid") and not self.state.keys and r["dpi_supported"]:
            m = "dpi"  # ключей не осталось — без ключа работает только обход DPI
        return m

    def strategies(self):
        """ByeDPI из профиля региона на Windows, встроенная фрагментация sing-box на macOS."""
        return cfg.strategies(self.region())

    def strategy(self):
        wanted = self.state.strategies.get(self.region_code())
        options = self.strategies()
        for s in options:
            if s["id"] == wanted:
                return s
        return options[0] if options else None

    def _refresh_all(self):
        codes = ["auto", *self.regions]
        self._region_codes = codes
        labels = [f"Авто: {self.regions[self.detected]['name']}"] + [self.regions[c]["name"] for c in self.regions]
        self.region_box["values"] = labels
        self.region_box.current(codes.index(self.state.region) if self.state.region in codes else 0)
        r = self.region()
        hint = f"Определено: {self.detected_how}." if self.state.region == "auto" else ""
        if r.get("dpi_note"):
            hint += (" " if hint else "") + r["dpi_note"]
        self.region_hint.configure(text=hint)

        self.mode_var.set(self.mode())
        for code, b in self.mode_buttons.items():
            b.state(["!disabled"] if code == "vpn" or r["dpi_supported"] else ["disabled"])
        self.mode_hint.configure(text={
            "dpi": ("Сайты из списка региона идут с фрагментацией TLS (sing-box), остальное напрямую. "
                    "Сервер не нужен." if MAC else
                    "Сайты из списка региона идут через локальный ByeDPI, остальное напрямую. Сервер не нужен."),
            "vpn": "Весь трафик идёт через сервер по ключу, кроме сайтов своей страны и локальной сети.",
            "hybrid": "Обход DPI для сайтов из списка, ключ для заблокированного по IP, остальное напрямую.",
        }[self.mode()])

        self.key_list.delete(0, "end")
        for k in self.state.keys:
            self.key_list.insert("end", f"  {k['name']}   ·  {k['outbound']['type']}")
        if self.state.keys:
            self.key_list.selection_set(min(self.state.selected_key, len(self.state.keys) - 1))

        strategies = self.strategies()
        self.strat_box["values"] = [s["name"] for s in strategies] or ["— не нужен в этом регионе —"]
        cur = self.strategy()
        self.strat_box.current(strategies.index(cur) if cur else 0)
        self.autotest_btn.state(["!disabled"] if strategies and not self.busy else ["disabled"])
        self.tun_var.set(self.state.tun)
        self.dpi_all_var.set(self.state.dpi_all)
        self.autostart_var.set(autostart.is_enabled())
        self.connect_on_start_var.set(self.state.connect_on_start)
        self._draw_button()

    def _draw_button(self):
        """Глаза закрыты — отключено, открыты — подключено, бегают — идёт работа. То же на значке в трее."""
        on = self.engine.running
        look = math.sin(self._phase) if self.busy else 0.0
        emblem.draw(self.canvas, 0, 0, self.px(EMBLEM_W), eyes_open=on or self.busy, look=look)
        if on and not self.busy:
            how = "TUN" if self.state.tun else f"системный прокси 127.0.0.1:{MIXED_PORT}"
            self.status.configure(text=f"Подключено · {cfg.MODES[self.mode()]} · {how}", foreground=OK)
        elif not self.busy:
            self.status.configure(text="Нажмите на эмблему, чтобы подключиться", foreground=MUTED)
        if self.tray and not self.busy and self._tray_state != on:
            self._tray_state = on
            self.tray.set_state(on, f"подключено, {cfg.MODES[self.mode()]}" if on else "не подключено")

    # ---------- события ----------
    def _on_region(self, _=None):
        self.state.region = self._region_codes[self.region_box.current()]
        self.state.mode = ""
        self._changed()

    def _on_mode(self):
        self.state.mode = self.mode_var.get()
        self._changed()

    def _on_strategy(self, _=None):
        options = self.strategies()
        if options:
            self.state.strategies[self.region_code()] = options[self.strat_box.current()]["id"]
        self._changed()

    def _on_options(self):
        if self.tun_var.get() and not is_admin():
            self.tun_var.set(False)
            if messagebox.askyesno("Обход", "Для режима TUN нужны права администратора.\n\n"
                                            "Перезапустить Обход от имени администратора?", parent=self.root):
                self.state.tun = True
                self.state.save()
                if relaunch_as_admin():
                    self.quit()
                    return
                self.state.tun = False
                self.state.save()
                self.log.write("obhod", "перезапуск от администратора отменён — TUN выключен")
            return
        reconnect = self.state.tun != self.tun_var.get() or self.state.dpi_all != self.dpi_all_var.get()
        self.state.tun = self.tun_var.get()
        self.state.dpi_all = self.dpi_all_var.get()
        self.state.connect_on_start = self.connect_on_start_var.get()
        self._changed(reconnect)

    def _offer_elevation(self):
        """TUN включён в настройках, а запустили без прав администратора: предложить перезапуск сразу."""
        if messagebox.askyesno("Обход", "Включён режим TUN, для него нужны права администратора.\n\n"
                                        "Перезапустить Обход от имени администратора?\n"
                                        "«Нет» — выключить TUN и работать через системный прокси.", parent=self.root):
            if relaunch_as_admin():
                self.quit()
                return
        self.state.tun = False
        self.state.save()
        self.log.write("obhod", "TUN выключен: нет прав администратора")
        self._refresh_all()

    def _on_autostart(self):
        try:
            if self.autostart_var.get():
                autostart.enable()
                self.log.write("obhod", "автозапуск включён: " + autostart.command())
            else:
                autostart.disable()
                self.log.write("obhod", "автозапуск выключен")
        except OSError as e:
            self.log.write("ошибка", f"не удалось изменить автозапуск: {e}")
        self._refresh_all()

    def _on_key_select(self, _=None):
        sel = self.key_list.curselection()
        if sel:
            self.state.selected_key = sel[0]
            self._changed()

    def _changed(self, reconnect=True):
        self.state.save()
        self._refresh_all()
        if reconnect and self.busy:
            # Подключение уже идёт (первое или переподключение): когда оно закончится, переподключимся один раз
            # с последними настройками. Раньше здесь стартовал второй поток, и движки двух потоков путались.
            self._reconnect_pending = True
            return
        if reconnect and self.engine.running:
            self.log.write("obhod", "настройки изменились — переподключаюсь")
            self._in_thread(self._connect)

    def _detect_ip(self):
        def work():
            code, how = reg.detect_online()
            self.q.put(("detected", (code, how)))
        self._in_thread(work, busy=False)

    # ---------- ключи ----------
    def paste_key(self):
        """Текст из буфера — ключ, подписка или JSON; если в буфере картинка — ищем на ней QR."""
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            text = ""
        if text:
            self._import_texts([text])
            return
        texts = qr.from_clipboard() if qr.available() else None
        if texts is None:
            self.log.write("obhod", "в буфере обмена нет ни текста, ни картинки")
        else:
            self._import_texts(texts, source="картинке из буфера")

    def scan_screen(self):
        """Прячем окно, снимаем все мониторы, ищем QR."""
        self.root.withdraw()

        def grab():
            try:
                texts = qr.from_screen()
                if not texts:
                    # окна под нашим могут ещё перерисовываться после withdraw — снимаем второй раз
                    self.root.after(600)
                    texts = qr.from_screen()
            finally:
                self.root.deiconify()
            self._import_texts(texts, source="экране")
        self.root.after(300, lambda: self._guard(grab))

    def scan_file(self):
        path = filedialog.askopenfilename(title="Картинка с QR-кодом ключа", filetypes=[
            ("Картинки", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("Все файлы", "*.*")])
        if path:
            self._guard(lambda: self._import_texts(qr.from_file(path), source=os.path.basename(path)))

    def _guard(self, fn):
        try:
            fn()
        except (qr.QRError, OSError, ValueError) as e:
            self.log.write("ошибка", str(e))

    def _import_texts(self, texts, source=""):
        if source and not texts:
            self.log.write("obhod", f"на {source} не нашёл QR-кода")
            return
        if source:
            self.log.write("obhod", f"QR-кодов на {source}: {len(texts)}")
        for text in texts:
            text = text.strip()
            if text.startswith(("http://", "https://")):
                self._fetch_sub(text)
            else:
                self._add_keys(*keys.parse_many(text))

    def _fetch_sub(self, url, pinned=None):
        """Скачать подписку в фоне. Сертификат не подтвердился — спросить пользователя в главном потоке."""
        pinned = pinned or self.state.trusted_certs.get(urlsplit(url).hostname or "")
        self.log.write("obhod", "скачиваю подписку…")

        def work():
            try:
                found, errors, _ = keys.fetch_subscription(url, pinned=pinned)
            except CertError as e:
                self.q.put(("cert", (url, e)))
                return
            self._add_keys(found, errors, sub=url)
        self._in_thread(work, busy=False)

    def _ask_cert(self, url, e):
        """Сертификат сервера подписки не подтверждён: объяснить и дать решить. «Да» запоминает отпечаток —
        подписка с другого (подменённого) сертификата снова вызовет этот вопрос."""
        self.log.write("obhod", f"сертификат {e.host} не подтверждён: {e.reason}")
        if not e.fingerprint:
            messagebox.showerror("Обход", f"Не удалось проверить сервер подписки {e.host}: {e.reason}.", parent=self.root)
            return
        text = (f"Сервер подписки {e.host} не подтвердил свою подлинность:\n{e.reason.rstrip('.')}.\n\n"
                "Так бывает, если у сервера самоподписанный сертификат или если сеть подменяет сертификаты "
                "(корпоративный фильтр, антивирус).\n\n"
                f"Отпечаток сертификата (SHA-256):\n{e.fingerprint}\n\n"
                "Доверяйте, только если уверены в сервере — например, отпечаток совпадает с указанным в панели "
                "вашего VPN. В подменённой подписке могут оказаться чужие ключи, и трафик уйдёт на чужой сервер.\n\n"
                "Доверять этому сертификату и скачать подписку?")
        if messagebox.askyesno("Обход — сертификат не подтверждён", text, icon="warning", default="no", parent=self.root):
            self.state.trusted_certs[e.host] = e.fingerprint
            self.state.save()
            self.log.write("obhod", f"доверяю сертификату {e.host}: {e.fingerprint[:23]}…")
            self._fetch_sub(url, pinned=e.fingerprint)
        else:
            self.log.write("obhod", "подписка не загружена: сертификат не подтверждён")

    def _add_keys(self, found, errors, sub=""):
        for e in errors:
            self.log.write("obhod", "не разобрал ключ: " + e)
        self.q.put(("keys", [{"name": k.name, "uri": k.uri, "outbound": k.outbound, "sub": sub} for k in found]))

    def delete_key(self):
        sel = self.key_list.curselection()
        if sel:
            del self.state.keys[sel[0]]
            self.state.selected_key = 0
            self._changed()

    # ---------- движки ----------
    def ensure_engines(self, then=None):
        """Нет sing-box или ByeDPI — спрашиваем и скачиваем с GitHub. then() — что сделать после."""
        missing = missing_bins()
        if not missing:
            return True
        if self.root.state() == "withdrawn":
            self.root.deiconify()
        if not messagebox.askyesno("Обход", "Для работы нужны движки: " + ", ".join(missing) + ".\n\n"
                                   "Скачать их с официальных страниц GitHub (sing-box и ByeDPI, около 35 МБ)?\n"
                                   f"Они будут лежать в {BIN}", parent=self.root):
            self.log.write("obhod", f"без движков подключиться нельзя. Можно положить их в {BIN} вручную")
            return False

        def work():
            fetch(log=lambda m: self.log.write("загрузка", m))
            self.log.write("obhod", "движки на месте")
            if then:
                then()
        self._in_thread(work)
        return False

    # ---------- подключение ----------
    def toggle(self):
        if self.busy:
            return
        if missing_bins():
            self.ensure_engines(then=self._connect)
            return
        self._in_thread(self._disconnect if self.engine.running else self._connect)

    def _connect(self):
        if self.state.tun and not is_admin():
            raise cfg.ConfigError("TUN включён, но Обход запущен без прав администратора. "
                                  "Снимите галочку TUN или включите её снова — Обход предложит перезапуск.")
        r = self.region()
        key = self.state.current_key()
        strategy = self.strategy()
        conf = cfg.build(r, self.mode(), key["outbound"] if key else None, mixed_port=MIXED_PORT,
                         dpi_port=DPI_PORT, tun=self.state.tun, dpi_all=self.state.dpi_all,
                         singbox_dpi=strategy.get("singbox") if strategy else None)
        self.engine.start(conf, strategy, DPI_PORT)
        if not self.state.tun:
            sysproxy.enable(MIXED_PORT)
        flush_dns()
        self.log.write("obhod", f"подключено: {r['name']}, {cfg.MODES[self.mode()]}")

    def _disconnect(self):
        self.engine.stop()
        sysproxy.restore()
        flush_dns()
        self.log.write("obhod", "отключено")

    def run_autotest(self):
        was_running = self.engine.running

        def work():
            if was_running:
                self._disconnect()
            r = self.region()
            say = lambda m: self.log.write("тест", m)
            say(f"автоподбор для региона «{r['name']}»")
            blocked = autotest.baseline(r, say)
            if not blocked:
                say("все тестовые сайты открываются напрямую — проверяю стратегии на полном списке")
            results = autotest.run(r, say, urls=blocked or None)
            if results and results[0][1] > 0:
                best = results[0][0]
                self.state.strategies[self.region_code()] = best["id"]
                say(f"выбрана: {best['name']}")
            else:
                say("ни одна стратегия не помогла. Нужен ключ (режим «VPN по ключу» или «Гибрид»).")
            self.state.save()
            if was_running:
                self._connect()
        self._in_thread(work)

    # ---------- служебное ----------
    def _in_thread(self, fn, busy=True):
        if busy:
            self.busy = True
            self._refresh_all()
            self.status.configure(text="Работаю…", foreground=MUTED)

        def run():
            try:
                fn()
            except (cfg.ConfigError, EngineError, FetchError, keys.KeyParseError, OSError, ValueError) as e:
                self.log.write("ошибка", str(e))
                self.q.put(("error", str(e)))
            finally:
                if busy:
                    self.q.put(("done", None))
        threading.Thread(target=run, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", data + "\n")
                    if int(self.log_box.index("end-1c").split(".")[0]) > 400:
                        self.log_box.delete("1.0", "100.0")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif kind == "keys":
                    if data:
                        self.state.keys.extend(data)
                        self.state.selected_key = len(self.state.keys) - len(data)
                        self.log.write("obhod", f"добавлено ключей: {len(data)}")
                        self._changed()
                elif kind == "cert":
                    self._ask_cert(*data)
                elif kind == "detected":
                    self.detected, self.detected_how = data
                    self.state.region = "auto"
                    self._changed()
                elif kind == "done":
                    self.busy = False
                    self._refresh_all()
                    if self._reconnect_pending:
                        self._reconnect_pending = False
                        self._changed()
                elif kind == "error":
                    self.status.configure(text=data[:90], foreground=BAD)
                    if self.tray and not self.root.winfo_viewable():
                        self.tray.notify(data[:200])
                elif kind == "show":
                    self.root.deiconify()
                    self.root.lift()
                    self.root.focus_force()
                elif kind == "toggle":
                    self.toggle()
                elif kind == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        if not self.busy and self.engine.procs and not self.engine.running:
            self.log.write("obhod", "движок остановился сам — снимаю системный прокси")
            self.engine.stop()
            sysproxy.restore()
            self._refresh_all()
        if self.busy:
            self._phase += 0.35
            self._draw_button()
        self.root.after(80 if self.busy else 150, self._poll)

    def close_window(self):
        """Крестик прячет окно в трей, как у Hiddify; выход — из меню значка. На Mac — сворачивает в Dock
        (выход — Cmd+Q). Без трея на Windows — обычный выход."""
        if not self.tray:
            if MAC:
                self.root.iconify()
            else:
                self.quit()
            return
        self.root.withdraw()
        if not self.state.tray_hint_shown:
            self.tray.notify("Обход работает в трее. Выход — правой кнопкой по значку.")
            self.state.tray_hint_shown = True
            self.state.save()

    def quit(self):
        self.engine.stop()
        sysproxy.restore()
        if self.tray:
            self.tray.stop()
        self.root.destroy()


def selftest():
    """Obhod.exe --selftest: без окон скачать движки, подключиться в режиме «Обход DPI» на отдельных портах
    (системный прокси не трогается), открыть тестовые сайты, отключиться. Отчёт — data/selftest.txt."""
    report = []
    say = report.append
    ok = False
    try:
        say(f"Обход {VERSION} selftest, {time.strftime('%Y-%m-%d %H:%M:%S')}")
        ctx = trusted_context()
        say("проверка сертификатов подписок: " + ("хранилище системы (truststore)" if type(ctx).__module__.startswith("truststore")
                                                  else "встроенная в Python"))
        say(f"движки: {BIN}\nнастройки: {DATA}")
        fetch(log=say)
        code, how = reg.detect_offline()
        region = cfg.load_regions()[code]
        say(f"регион: {region['name']} ({how})")
        if not region["dpi_supported"]:
            say("в этом регионе обход DPI не работает — проверяю только запуск движков")
        options = cfg.strategies(region)
        strategy = options[0] if options else None
        mode = "dpi" if region["dpi_supported"] else None
        engine = Engine(Log())
        if mode:
            conf = cfg.build(region, mode, mixed_port=2181, dpi_port=1181, singbox_dpi=strategy.get("singbox"))
            engine.start(conf, strategy, 1181)
            say(f"подключено: {strategy['name']}")
            results = []
            for url in region["test_urls"] + ["https://example.com/"]:
                good = autotest.probe(url, 2181, timeout=12)  # SOCKS5 в mixed-inbound sing-box, имя резолвит он сам
                results.append(good)
                say(f"{'✓' if good else '✗'} {url}")
            engine.stop()
            ok = all(results)
        say("ИТОГ: " + ("всё работает" if ok else "есть проблемы, смотрите ✗"))
    except Exception as e:  # отчёт должен записаться при любой ошибке
        say(f"ОШИБКА: {e}")
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "selftest.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    if already_running(wait=8 if "--elevated" in sys.argv else 0):
        if MAC:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Обход", "Обход уже запущен — его окно в Dock.")
            root.destroy()
            return
        ctypes.windll.user32.MessageBoxW(None, "Обход уже запущен — его значок в трее, рядом с часами.", "Обход", 0x40)
        return
    root = tk.Tk()
    App(root, start_hidden="--tray" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
