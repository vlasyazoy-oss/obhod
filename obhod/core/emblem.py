"""Эмблема «Обхода»: синяя и сливовая полосы, белый шестиугольник, чёрная маска с глазами.

Геометрия задана в координатах исходного рисунка 1280×845. Отсюда рисуется кнопка на tk.Canvas
и растровая иконка окна (PNG без сторонних библиотек).
"""
import struct
import zlib

W, H = 1280, 845
BLUE, WHITE, PLUM, BLACK = "#22408a", "#ffffff", "#554452", "#000000"
DIM = {BLUE: "#2a3247", PLUM: "#3a3440", WHITE: "#c9ccd3", BLACK: "#15161a"}  # приглушённые цвета, когда отключено

LEFT = [(0, 0), (539, 0), (539, 182), (346, 278), (346, 567), (539, 663), (539, H), (0, H)]
RIGHT = [(725, 0), (W, 0), (W, H), (725, H), (725, 665), (922, 567), (922, 278), (725, 180)]
MASK = (497, 349, 772, 497)                       # чёрная повязка
EYE_L, EYE_R = (530, 423), (739, 423)             # центры белых вырезов
EYE_RX, EYE_RY = 58, 72
PUPIL_R = 34


def draw(canvas, x0, y0, width, *, eyes_open=True, look=0.0, dim=False, tag="emblem"):
    """Рисует эмблему шириной width. look от -1 до 1 сдвигает зрачки; dim — приглушённые цвета."""
    s = width / W
    col = (lambda c: DIM[c]) if dim else (lambda c: c)
    p = lambda pts: [v for x, y in pts for v in (x0 + x * s, y0 + y * s)]
    canvas.delete(tag)
    canvas.create_rectangle(x0, y0, x0 + W * s, y0 + H * s, fill=col(WHITE), width=0, tags=tag)
    canvas.create_polygon(p(LEFT), fill=col(BLUE), width=0, tags=tag)
    canvas.create_polygon(p(RIGHT), fill=col(PLUM), width=0, tags=tag)
    mx0, my0, mx1, my1 = MASK
    canvas.create_rectangle(x0 + mx0 * s, y0 + my0 * s, x0 + mx1 * s, y0 + my1 * s, fill=col(BLACK), width=0, tags=tag)
    for cx, cy in (EYE_L, EYE_R):
        if eyes_open:
            canvas.create_oval(x0 + (cx - EYE_RX) * s, y0 + (cy - EYE_RY) * s, x0 + (cx + EYE_RX) * s,
                               y0 + (cy + EYE_RY) * s, fill=WHITE, width=0, tags=tag)
            px = cx + look * 18 + (6 if cx < W / 2 else -6)  # чуть сведены, как на рисунке
            canvas.create_oval(x0 + (px - PUPIL_R) * s, y0 + (cy - PUPIL_R) * s, x0 + (px + PUPIL_R) * s,
                               y0 + (cy + PUPIL_R) * s, fill=BLACK, width=0, tags=tag)
        else:
            # закрытый глаз: белая дуга-щель
            canvas.create_arc(x0 + (cx - EYE_RX + 6) * s, y0 + (cy - 30) * s, x0 + (cx + EYE_RX - 6) * s,
                              y0 + (cy + 22) * s, start=200, extent=140, style="arc", outline=col(WHITE),
                              width=max(2, 9 * s), tags=tag)


def _inside(pts, x, y):
    hit = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def color_at(x, y, eyes_open=True):
    """Цвет точки исходного рисунка (для растровых иконок)."""
    mx0, my0, mx1, my1 = MASK
    if mx0 <= x <= mx1 and my0 <= y <= my1:
        for cx, cy in (EYE_L, EYE_R):
            if eyes_open:
                px = cx + (6 if cx < W / 2 else -6)
                if (x - px) ** 2 + (y - cy) ** 2 <= PUPIL_R ** 2:
                    return BLACK
                if ((x - cx) / EYE_RX) ** 2 + ((y - cy) / EYE_RY) ** 2 <= 1:
                    return WHITE
            else:
                # та же дуга-щель, что в draw(): нижняя часть эллипса вокруг (cx, cy - 4)
                d = ((x - cx) / (EYE_RX - 6)) ** 2 + ((y - cy + 4) / 26) ** 2
                if y > cy + 2 and 0.4 <= d <= 1.8:
                    return WHITE
        return BLACK
    if _inside(LEFT, x, y):
        return BLUE
    if _inside(RIGHT, x, y):
        return PLUM
    return WHITE


def rgb(size=64, crop=True, eyes_open=True):
    """Пиксели RGB построчно. crop — квадрат по центру (шестиугольник с маской), иначе весь флаг по ширине."""
    x0, y0, side = (300, H / 2 - 340, 680) if crop else (0, 0, W)
    out = bytearray()
    for j in range(size):
        for i in range(size):
            acc = [0, 0, 0]
            for dx, dy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)):  # 4 сэмпла на пиксель
                c = color_at(x0 + (i + dx) * side / size, y0 + (j + dy) * side / size, eyes_open)
                for k in range(3):
                    acc[k] += int(c[1 + 2 * k:3 + 2 * k], 16)
            out += bytes(v // 4 for v in acc)
    return bytes(out)


def write_png(path, size=64, crop=True, eyes_open=True):
    pixels = rgb(size, crop, eyes_open)
    rows = b"".join(b"\x00" + pixels[j * size * 3:(j + 1) * size * 3] for j in range(size))
    raw = zlib.compress(rows, 9)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
