"""Обход — черновой клиент: обход DPI как у Zapret плюс VPN по своему ключу как у Hiddify.

    py app.py           обычный запуск
    py app.py --tray    свёрнутым в трей (так запускает автозапуск Windows)
"""
import ctypes
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from urllib.parse import urlsplit
from tkinter import filedialog, messagebox, ttk

from core import autostart, autotest, blocks_ui, config as cfg, emblem, i18n, keys, qr, region as reg, sysproxy, tray
from core.engine import DATA, Engine, EngineError, Log, missing_bins
from core.fetch import FetchError, fetch
from core.i18n import t
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
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def flush_dns():
    """Очистить кэш DNS Windows (как ipconfig /flushdns, без прав администратора). Иначе программы ещё
    несколько минут ходят на подменённые провайдером адреса, полученные до включения TUN."""
    try:
        ctypes.windll.dnsapi.DnsFlushResolverCache()
    except (AttributeError, OSError):
        pass


def already_running(wait=0.0):
    """Второй экземпляр подрался бы с первым за порты и системный прокси.

    wait — сколько секунд ждать, пока прежний экземпляр закроется (перезапуск от администратора).
    """
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
        i18n.set_lang(self.state.lang)
        self.regions = cfg.load_regions()
        self.detected, self.detected_how = reg.detect_offline()
        self.busy = False
        self._phase = 0.0
        self._reconnect_pending = False
        self.game = None

        self._set_title()
        # Размеры в «логических» пикселях: при масштабе Windows 125–150 % окно не должно сжиматься
        self.k = root.winfo_fpixels("1i") / 96
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
            self.log.write("obhod", t("log_proxy_restored"))
        if missing_bins():
            self.log.write("obhod", t("log_no_engines", ", ".join(missing_bins())))
            root.after(300, self.ensure_engines)
        if not self.tray or not qr.available():
            self.log.write("obhod", t("log_no_libs"))
        autostart.refresh()
        if self.state.tun and not is_admin():
            root.after(400, self._offer_elevation)
        if start_hidden and self.tray:
            root.withdraw()
        if self.state.connect_on_start:
            root.after(500, self.toggle)

    # ---------- вид ----------
    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=CARD, font=("Segoe UI", 10))
        s.configure("Card.TFrame", background=CARD)
        s.configure("Card.TLabel", background=CARD, foreground=FG)
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 9))
        s.configure("H.TLabel", background=BG, foreground=FG, font=("Segoe UI Semibold", 16))
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
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

    def _set_title(self):
        self.root.title(f"{t('app')} — {t('admin')}" if is_admin() else t("app"))

    def _build(self):
        self.outer = outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer)
        head.pack(fill="x", pady=(0, 8))
        ttk.Label(head, text=t("app"), style="H.TLabel").pack(side="left")
        ttk.Label(head, text=t("version", VERSION), style="Sub.TLabel").pack(side="left", padx=8, pady=(6, 0))
        # Справа: язык и игра «Блоки»
        self.lang_var = tk.StringVar(value=i18n.LANGS[i18n.lang])
        lang_box = ttk.Combobox(head, textvariable=self.lang_var, values=list(i18n.LANGS.values()), state="readonly",
                                width=9)
        lang_box.pack(side="right", pady=(4, 0))
        lang_box.bind("<<ComboboxSelected>>", self._on_lang)
        game = tk.Canvas(head, width=self.px(80), height=self.px(26), bg=BG, highlightthickness=0, cursor="hand2")
        game.pack(side="right", padx=(0, 10), pady=(4, 0))
        blocks_ui.draw_icon(game, self.px(2), self.px(5), self.px(8))
        game.create_text(self.px(30), self.px(13), text=t("game"), anchor="w", fill=FG, font=("Segoe UI", 9))
        game.bind("<Button-1>", lambda e: self.open_game())

        # Эмблема — она же кнопка подключения
        mid = ttk.Frame(outer)
        mid.pack(pady=(0, 10))
        self.canvas = tk.Canvas(mid, width=self.px(EMBLEM_W), height=self.px(EMBLEM_W * emblem.H / emblem.W), bg=BG,
                                highlightthickness=0, cursor="hand2")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.toggle())
        self.status = ttk.Label(mid, text="", style="Sub.TLabel", font=("Segoe UI Semibold", 10))
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
        self.root.bind_all("<MouseWheel>", lambda e: scroll.yview_scroll(-e.delta // 120, "units"))

        # Регион
        c = self._card(body, t("card_region"))
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x")
        self.region_var = tk.StringVar()
        self.region_box = ttk.Combobox(row, textvariable=self.region_var, state="readonly", width=28)
        self.region_box.pack(side="left")
        self.region_box.bind("<<ComboboxSelected>>", self._on_region)
        ttk.Button(row, text=t("by_ip"), command=self._detect_ip).pack(side="right")
        self.region_hint = ttk.Label(c, style="Muted.TLabel", wraplength=self.px(410), justify="left")
        self.region_hint.pack(anchor="w", pady=(6, 0))

        # Режим
        c = self._card(body, t("card_mode"))
        self.mode_var = tk.StringVar()
        self.mode_buttons = {}
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x")
        for code in cfg.MODES:
            b = ttk.Radiobutton(row, text=i18n.mode(code), value=code, variable=self.mode_var, command=self._on_mode)
            b.pack(side="left", padx=(0, 14))
            self.mode_buttons[code] = b
        self.mode_hint = ttk.Label(c, style="Muted.TLabel", wraplength=self.px(410), justify="left")
        self.mode_hint.pack(anchor="w", pady=(6, 0))

        # Ключи
        c = self._card(body, t("card_keys"))
        self.key_list = tk.Listbox(c, height=3, bg=BG, fg=FG, selectbackground=ACCENT, borderwidth=0,
                                   highlightthickness=0, activestyle="none", font=("Segoe UI", 10))
        self.key_list.pack(fill="x")
        self.key_list.bind("<<ListboxSelect>>", self._on_key_select)
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text=t("paste"), style="Accent.TButton", command=self.paste_key).pack(side="left")
        self.qr_buttons = [ttk.Button(row, text=t("qr_screen"), command=self.scan_screen),
                           ttk.Button(row, text=t("qr_file"), command=self.scan_file)]
        for b in self.qr_buttons:
            b.pack(side="left", padx=(6, 0))
            if not qr.available():
                b.state(["disabled"])
        ttk.Button(row, text=t("delete"), command=self.delete_key).pack(side="right")

        # Стратегия
        c = self._card(body, t("card_dpi"))
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x")
        self.strat_var = tk.StringVar()
        self.strat_box = ttk.Combobox(row, textvariable=self.strat_var, state="readonly", width=30)
        self.strat_box.pack(side="left")
        self.strat_box.bind("<<ComboboxSelected>>", self._on_strategy)
        self.autotest_btn = ttk.Button(row, text=t("autotest"), command=self.run_autotest)
        self.autotest_btn.pack(side="right")
        self.tun_var = tk.BooleanVar()
        self.dpi_all_var = tk.BooleanVar()
        ttk.Checkbutton(c, text=t("dpi_all"), variable=self.dpi_all_var,
                        command=self._on_options).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(c, text=t("tun"), variable=self.tun_var,
                        command=self._on_options).pack(anchor="w")

        # Запуск
        c = self._card(body, t("card_start"))
        self.autostart_var = tk.BooleanVar()
        self.connect_on_start_var = tk.BooleanVar()
        ttk.Checkbutton(c, text=t("autostart"), variable=self.autostart_var,
                        command=self._on_autostart).pack(anchor="w")
        ttk.Checkbutton(c, text=t("connect_on_start"), variable=self.connect_on_start_var,
                        command=self._on_options).pack(anchor="w")

        # Журнал
        self.log_box = tk.Text(body, height=6, bg=CARD, fg=MUTED, borderwidth=0, font=("Consolas", 8), wrap="word")
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

    def strategy(self):
        r = self.region()
        wanted = self.state.strategies.get(self.region_code())
        for s in r["strategies"]:
            if s["id"] == wanted:
                return s
        return r["strategies"][0] if r["strategies"] else None

    def _refresh_all(self):
        codes = ["auto", *self.regions]
        self._region_codes = codes
        labels = [t("auto", i18n.region(self.detected))] + [i18n.region(c) for c in self.regions]
        self.region_box["values"] = labels
        self.region_box.current(codes.index(self.state.region) if self.state.region in codes else 0)
        r = self.region()
        hint = t("detected", i18n.how(self.detected_how)) if self.state.region == "auto" else ""
        if r.get("dpi_note"):
            hint += (" " if hint else "") + cfg.region_note(r)
        self.region_hint.configure(text=hint)

        self.mode_var.set(self.mode())
        for code, b in self.mode_buttons.items():
            b.state(["!disabled"] if code == "vpn" or r["dpi_supported"] else ["disabled"])
        self.mode_hint.configure(text=t("hint_" + self.mode()))

        self.key_list.delete(0, "end")
        for k in self.state.keys:
            self.key_list.insert("end", f"  {k['name']}   ·  {k['outbound']['type']}")
        if self.state.keys:
            self.key_list.selection_set(min(self.state.selected_key, len(self.state.keys) - 1))

        strategies = r["strategies"]
        self.strat_box["values"] = [i18n.strategy(s["name"]) for s in strategies] or [t("strategy_none")]
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
            how = "TUN" if self.state.tun else t("sysproxy", f"127.0.0.1:{MIXED_PORT}")
            self.status.configure(text=t("status_connected", i18n.mode(self.mode()), how), foreground=OK)
        elif not self.busy:
            self.status.configure(text=t("status_idle"), foreground=MUTED)
        tray_state = (on, i18n.lang)  # после смены языка подсказку и меню трея тоже обновляем
        if self.tray and not self.busy and self._tray_state != tray_state:
            self._tray_state = tray_state
            self.tray.set_state(on, t("tray_on", i18n.mode(self.mode())) if on else t("tray_off"))

    # ---------- события ----------
    def _on_region(self, _=None):
        self.state.region = self._region_codes[self.region_box.current()]
        self.state.mode = ""
        self._changed()

    def _on_lang(self, _=None):
        """Новый язык — окно собирается заново; журнал сохраняется."""
        code = next(c for c, name in i18n.LANGS.items() if name == self.lang_var.get())
        if code == i18n.lang:
            return
        self.state.lang = i18n.set_lang(code)
        self.state.save()
        log = self.log_box.get("1.0", "end-1c")
        self.outer.destroy()
        self._set_title()
        self._build()
        self.log_box.configure(state="normal")
        self.log_box.insert("end", log + ("\n" if log else ""))
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self._refresh_all()
        if self.game and self.game.alive():
            self.game.relabel()
        self.log.write("obhod", t("log_lang", i18n.LANGS[code]))

    def open_game(self):
        if self.game and self.game.alive():
            self.game.show()
            return
        self.game = blocks_ui.BlocksWindow(self.root, self.k, best=self.state.blocks_best, on_best=self._on_best)

    def _on_best(self, score):
        self.state.blocks_best = score
        self.state.save()

    def _on_mode(self):
        self.state.mode = self.mode_var.get()
        self._changed()

    def _on_strategy(self, _=None):
        r = self.region()
        if r["strategies"]:
            self.state.strategies[self.region_code()] = r["strategies"][self.strat_box.current()]["id"]
        self._changed()

    def _on_options(self):
        if self.tun_var.get() and not is_admin():
            self.tun_var.set(False)
            if messagebox.askyesno(t("app"), t("tun_need_admin"), parent=self.root):
                self.state.tun = True
                self.state.save()
                if relaunch_as_admin():
                    self.quit()
                    return
                self.state.tun = False
                self.state.save()
                self.log.write("obhod", t("log_elev_cancelled"))
            return
        reconnect = self.state.tun != self.tun_var.get() or self.state.dpi_all != self.dpi_all_var.get()
        self.state.tun = self.tun_var.get()
        self.state.dpi_all = self.dpi_all_var.get()
        self.state.connect_on_start = self.connect_on_start_var.get()
        self._changed(reconnect)

    def _offer_elevation(self):
        """TUN включён в настройках, а запустили без прав администратора: предложить перезапуск сразу."""
        if messagebox.askyesno(t("app"), t("tun_offer"), parent=self.root):
            if relaunch_as_admin():
                self.quit()
                return
        self.state.tun = False
        self.state.save()
        self.log.write("obhod", t("log_tun_off"))
        self._refresh_all()

    def _on_autostart(self):
        try:
            if self.autostart_var.get():
                autostart.enable()
                self.log.write("obhod", t("log_autostart_on", autostart.command()))
            else:
                autostart.disable()
                self.log.write("obhod", t("log_autostart_off"))
        except OSError as e:
            self.log.write(t("tag_error"), t("log_autostart_fail", e))
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
            self.log.write("obhod", t("log_reconnect"))
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
            self.log.write("obhod", t("log_clipboard_empty"))
        else:
            self._import_texts(texts, source=t("src_clipboard"))

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
            self._import_texts(texts, source=t("src_screen"))
        self.root.after(300, lambda: self._guard(grab))

    def scan_file(self):
        path = filedialog.askopenfilename(title=t("qr_dialog"), filetypes=[
            (t("images"), "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), (t("all_files"), "*.*")])
        if path:
            self._guard(lambda: self._import_texts(qr.from_file(path), source=os.path.basename(path)))

    def _guard(self, fn):
        try:
            fn()
        except (qr.QRError, OSError, ValueError) as e:
            self.log.write(t("tag_error"), str(e))

    def _import_texts(self, texts, source=""):
        if source and not texts:
            self.log.write("obhod", t("log_qr_none", source))
            return
        if source:
            self.log.write("obhod", t("log_qr_found", source, len(texts)))
        for text in texts:
            text = text.strip()
            if text.startswith(("http://", "https://")):
                self._fetch_sub(text)
            else:
                self._add_keys(*keys.parse_many(text))

    def _fetch_sub(self, url, pinned=None):
        """Скачать подписку в фоне. Сертификат не подтвердился — спросить пользователя в главном потоке."""
        pinned = pinned or self.state.trusted_certs.get(urlsplit(url).hostname or "")
        self.log.write("obhod", t("log_sub_loading"))

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
        self.log.write("obhod", t("log_cert", e.host, e.reason))
        if not e.fingerprint:
            messagebox.showerror(t("app"), t("cert_fail", e.host, e.reason), parent=self.root)
            return
        text = t("cert_text", e.host, e.reason.rstrip("."), e.fingerprint)
        if messagebox.askyesno(t("cert_title"), text, icon="warning", default="no", parent=self.root):
            self.state.trusted_certs[e.host] = e.fingerprint
            self.state.save()
            self.log.write("obhod", t("log_cert_trusted", e.host, e.fingerprint[:23]))
            self._fetch_sub(url, pinned=e.fingerprint)
        else:
            self.log.write("obhod", t("log_sub_rejected"))

    def _add_keys(self, found, errors, sub=""):
        for e in errors:
            self.log.write("obhod", t("log_bad_key", e))
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
        if not messagebox.askyesno(t("app"), t("engines_ask", ", ".join(missing), BIN), parent=self.root):
            self.log.write("obhod", t("log_engines_manual", BIN))
            return False

        def work():
            fetch(log=lambda m: self.log.write(t("tag_download"), m))
            self.log.write("obhod", t("log_engines_ready"))
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
            raise cfg.ConfigError(t("err_tun_admin"))
        r = self.region()
        key = self.state.current_key()
        conf = cfg.build(r, self.mode(), key["outbound"] if key else None, mixed_port=MIXED_PORT,
                         dpi_port=DPI_PORT, tun=self.state.tun, dpi_all=self.state.dpi_all)
        self.engine.start(conf, self.strategy(), DPI_PORT)
        if not self.state.tun:
            sysproxy.enable(MIXED_PORT)
        flush_dns()
        self.log.write("obhod", t("log_connected", i18n.region(self.region_code()), i18n.mode(self.mode())))

    def _disconnect(self):
        self.engine.stop()
        sysproxy.restore()
        flush_dns()
        self.log.write("obhod", t("log_disconnected"))

    def run_autotest(self):
        was_running = self.engine.running

        def work():
            if was_running:
                self._disconnect()
            r = self.region()
            say = lambda m: self.log.write(t("tag_test"), m)
            say(t("test_region", i18n.region(self.region_code())))
            blocked = autotest.baseline(r, say)
            if not blocked:
                say(t("test_all_open"))
            results = autotest.run(r, say, urls=blocked or None)
            if results and results[0][1] > 0:
                best = results[0][0]
                self.state.strategies[self.region_code()] = best["id"]
                say(t("test_chosen", i18n.strategy(best["name"])))
            else:
                say(t("test_none"))
            self.state.save()
            if was_running:
                self._connect()
        self._in_thread(work)

    # ---------- служебное ----------
    def _in_thread(self, fn, busy=True):
        if busy:
            self.busy = True
            self._refresh_all()
            self.status.configure(text=t("working"), foreground=MUTED)

        def run():
            try:
                fn()
            except (cfg.ConfigError, EngineError, FetchError, keys.KeyParseError, OSError, ValueError) as e:
                self.log.write(t("tag_error"), str(e))
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
                        self.log.write("obhod", t("log_keys_added", len(data)))
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
            self.log.write("obhod", t("log_engine_died"))
            self.engine.stop()
            sysproxy.restore()
            self._refresh_all()
        if self.busy:
            self._phase += 0.35
            self._draw_button()
        self.root.after(80 if self.busy else 150, self._poll)

    def close_window(self):
        """Крестик прячет окно в трей, как у Hiddify; выход — из меню значка. Без трея — обычный выход."""
        if not self.tray:
            self.quit()
            return
        self.root.withdraw()
        if not self.state.tray_hint_shown:
            self.tray.notify(t("tray_hint"))
            self.state.tray_hint_shown = True
            self.state.save()

    def quit(self):
        if self.game and self.game.alive():
            self.game.close()
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
        strategy = region["strategies"][0] if region["strategies"] else None
        mode = "dpi" if region["dpi_supported"] else None
        engine = Engine(Log())
        if mode:
            conf = cfg.build(region, mode, mixed_port=2181, dpi_port=1181)
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
        i18n.set_lang(State.load().lang)
        ctypes.windll.user32.MessageBoxW(None, t("already_running"), t("app"), 0x40)
        return
    root = tk.Tk()
    App(root, start_hidden="--tray" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
