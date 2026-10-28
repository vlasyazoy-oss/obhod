"""Окно игры «Блоки»: поле слева, справа эмблема, счёт и следующая фигура.

Эмблема играет вместе с вами: зрачки следят за фигурой, на убранной линии глаза моргают, на паузе и после
проигрыша закрыты. Фигуры — оттенки цветов эмблемы: три синих, три сливовых и белый.
"""
import tkinter as tk

from . import blocks, emblem
from .i18n import t

BG, PANEL, GRID, FG, MUTED = "#16151b", "#221f29", "#1c1a22", "#ecebf0", "#9d98a6"
COLORS = {
    "I": "#ecebf0",  # белая полоса флага
    "O": "#3a62cc",
    "J": "#22408a",  # синий эмблемы
    "L": "#7d9be8",
    "T": "#8a6f86",
    "S": "#554452",  # сливовый эмблемы
    "Z": "#b9a3b5",
}
VK = {"P": 80, "R": 82, "X": 88, "Z": 90}  # коды клавиш: работают и в русской раскладке


def _shade(color, k):
    """Светлее (k > 0) или темнее (k < 0) — для объёма клеток."""
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    rgb = [round(c + (255 - c) * k) if k > 0 else round(c * (1 + k)) for c in rgb]
    return "#%02x%02x%02x" % tuple(rgb)


def cell(canvas, x, y, size, color, ghost=False, tag="cell"):
    gap = max(1, size // 14)
    x0, y0, x1, y1 = x + gap, y + gap, x + size - gap, y + size - gap
    if ghost:
        canvas.create_rectangle(x0, y0, x1, y1, outline=_shade(color, -0.25), width=max(1, size // 12), tags=tag)
        return
    edge = max(2, size // 8)
    canvas.create_rectangle(x0, y0, x1, y1, fill=color, width=0, tags=tag)
    canvas.create_rectangle(x0, y0, x1, y0 + edge, fill=_shade(color, 0.3), width=0, tags=tag)
    canvas.create_rectangle(x0, y1 - edge, x1, y1, fill=_shade(color, -0.3), width=0, tags=tag)


def draw_icon(canvas, x, y, size):
    """Значок кнопки в главном окне: «T» в цветах флага — синий, белый, сливовый, снизу белый."""
    for i, color in enumerate(("#3a62cc", "#ecebf0", "#8a6f86")):
        cell(canvas, x + i * size, y, size, color, tag="icon")
    cell(canvas, x + size, y + size, size, "#ecebf0", tag="icon")


class BlocksWindow:
    def __init__(self, root, k, best=0, on_best=lambda score: None):
        self.k = k
        self.best = best
        self.on_best = on_best
        self.c = round(26 * k)                       # размер клетки
        self.side = round(190 * k)                   # ширина правой панели
        self.win = tk.Toplevel(root, bg=BG)
        self.win.resizable(False, False)
        self.canvas = tk.Canvas(self.win, width=blocks.W * self.c + self.side + self.px(30),
                                height=blocks.H * self.c + self.px(24), bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.win.bind("<Key>", self._key)
        self.win.bind("<FocusOut>", lambda e: self._auto_pause())
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self._timer = None
        self._blink = 0
        self.new_game()
        self.relabel()
        self.show()

    def px(self, n):
        return round(n * self.k)

    # ---------- управление окном ----------
    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def relabel(self):
        self.win.title(f"{t('app')} — {t('game')}")
        self.render()

    def close(self):
        self._save_best()
        if self._timer:
            self.win.after_cancel(self._timer)
        self.win.destroy()

    # ---------- игра ----------
    def new_game(self):
        self._save_best()
        self.game = blocks.Game()
        self.paused = False
        self.new_best = False
        self._schedule()
        if hasattr(self, "canvas"):
            self.render()

    def _save_best(self):
        game = getattr(self, "game", None)
        if game and game.score > self.best:
            self.best = game.score
            self.new_best = True
            self.on_best(self.best)

    def _schedule(self):
        if self._timer:
            self.win.after_cancel(self._timer)
        self._timer = self.win.after(self.game.interval(), self._step)

    def _step(self):
        self._timer = None
        if self.paused or self.game.over:
            return
        if self.game.tick():
            self._blink = 3  # кадра с закрытыми глазами
        self._after_move()
        self._schedule()

    def _after_move(self):
        if self.game.over:
            self._save_best()
        self.render()

    def _auto_pause(self):
        """Ушли в другое окно — пауза, чтобы фигуры не падали без присмотра."""
        if self.game.over or self.paused or not self.alive():
            return
        try:
            focus = self.win.focus_get()
        except (KeyError, tk.TclError):
            focus = None
        if focus is None or focus.winfo_toplevel() is not self.win:
            self.paused = True
            self.render()

    def _key(self, e):
        g = self.game
        if e.keycode == VK["R"]:
            self.new_game()
            return
        if g.over:
            return
        if e.keycode == VK["P"] or e.keysym == "Escape":
            self.paused = not self.paused
            if not self.paused:
                self._schedule()
            self.render()
            return
        if self.paused:
            return
        if e.keysym == "Left":
            g.move(-1)
        elif e.keysym == "Right":
            g.move(1)
        elif e.keysym in ("Up",) or e.keycode == VK["X"]:
            g.rotate(1)
        elif e.keycode == VK["Z"]:
            g.rotate(-1)
        elif e.keysym == "Down":
            if not g.soft_drop() and g.last_cleared:
                self._blink = 3
            self._schedule()
        elif e.keysym == "space":
            g.hard_drop()
            if g.last_cleared:
                self._blink = 3
            self._schedule()
        else:
            return
        self._after_move()

    # ---------- рисование ----------
    def render(self):
        cv, g, c = self.canvas, self.game, self.c
        cv.delete("all")
        ox, oy = self.px(12), self.px(12)
        bw, bh = blocks.W * c, blocks.H * c
        cv.create_rectangle(ox - 2, oy - 2, ox + bw + 2, oy + bh + 2, fill=GRID, outline=PANEL, width=2)
        for x in range(1, blocks.W):
            cv.create_line(ox + x * c, oy, ox + x * c, oy + bh, fill=BG)
        for y in range(1, blocks.H):
            cv.create_line(ox, oy + y * c, ox + bw, oy + y * c, fill=BG)
        for y, row in enumerate(g.board):
            for x, kind in enumerate(row):
                if kind:
                    cell(cv, ox + x * c, oy + y * c, c, COLORS[kind])
        if not g.over:
            color = COLORS[g.kind]
            for x, y in g.piece(g.ghost_y()):
                if y >= 0:
                    cell(cv, ox + x * c, oy + y * c, c, color, ghost=True)
            for x, y in g.piece():
                if y >= 0:
                    cell(cv, ox + x * c, oy + y * c, c, color)

        # правая панель
        sx = ox + bw + self.px(18)
        sw = self.side - self.px(6)
        eyes = not (g.over or self.paused or self._blink)
        if self._blink:
            self._blink -= 1
            self.win.after(70, self.render)
        look = 0.0 if g.over else max(-1.0, min(1.0, (g.x + 1.5 - blocks.W / 2) / (blocks.W / 2)))
        emblem.draw(cv, sx, oy, sw, eyes_open=eyes, look=look, dim=g.over)
        y = oy + sw * emblem.H / emblem.W + self.px(16)
        font = lambda size, bold=False: ("Segoe UI Semibold" if bold else "Segoe UI", size)
        cv.create_text(sx, y, text=t("g_score"), anchor="nw", fill=MUTED, font=font(9))
        cv.create_text(sx, y + self.px(14), text=f"{g.score:,}".replace(",", " "), anchor="nw", fill=FG, font=font(24, True))
        y += self.px(58)
        cv.create_text(sx, y, text=t("g_best", max(self.best, g.score)), anchor="nw", fill=FG, font=font(10))
        cv.create_text(sx, y + self.px(20), text=t("g_level", g.level) + "    " + t("g_lines", g.lines), anchor="nw",
                       fill=MUTED, font=font(9))
        y += self.px(52)
        cv.create_text(sx, y, text=t("g_next"), anchor="nw", fill=MUTED, font=font(9))
        nc = round(c * 0.8)
        n_cells = blocks.cells(g.next, 0)
        nw = (max(x for x, _ in n_cells) + 1) * nc
        for x, yy in n_cells:
            cell(cv, sx + (sw - nw) / 2 + x * nc, y + self.px(22) + yy * nc, nc, COLORS[g.next])
        y += self.px(22) + 3 * nc
        cv.create_text(sx, oy + bh, text=t("g_keys"), anchor="sw", fill=MUTED, font=font(8), justify="left")

        if g.over or self.paused:
            cv.create_rectangle(ox, oy + bh / 2 - self.px(46), ox + bw, oy + bh / 2 + self.px(46), fill=PANEL, width=0)
            title = t("g_over") if g.over else t("g_pause")
            cv.create_text(ox + bw / 2, oy + bh / 2 - self.px(14), text=title, fill=FG, font=font(16, True))
            sub = (t("g_new_best") + "   " if g.over and self.new_best else "") + (t("g_again") if g.over else "P")
            cv.create_text(ox + bw / 2, oy + bh / 2 + self.px(18), text=sub, fill="#7d9be8" if self.new_best else MUTED,
                           font=font(10))
