"""Игра «Блоки»: падающие фигуры из четырёх квадратов, поле 10×20. Только правила, без окна — их проверяют тесты.

Фигуры выдаются «мешками» по семь (каждая ровно раз в случайном порядке), поворот — в квадрате фигуры
с небольшими сдвигами от стен. Очки: 100/300/500/800 за 1–4 линии, умноженные на уровень; +1 за клетку
ускоренного падения, +2 за клетку сброса. Уровень растёт каждые 10 линий.
"""
import random

W, H = 10, 20
SHAPES = {  # клетки в квадрате фигуры, строка за строкой
    "I": ["....", "####", "....", "...."],
    "O": ["##", "##"],
    "T": [".#.", "###", "..."],
    "S": [".##", "##.", "..."],
    "Z": ["##.", ".##", "..."],
    "J": ["#..", "###", "..."],
    "L": ["..#", "###", "..."],
}
KICKS = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)]
LINE_SCORE = {1: 100, 2: 300, 3: 500, 4: 800}


def cells(kind, rot):
    """Клетки фигуры (x, y) в её квадрате после rot поворотов по часовой."""
    rows = SHAPES[kind]
    n = len(rows)
    out = [(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "#"]
    for _ in range(rot % 4):
        out = [(n - 1 - y, x) for x, y in out]
    return out


class Game:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.board = [[None] * W for _ in range(H)]
        self.bag = []
        self.score = self.lines = 0
        self.over = False
        self.last_cleared = 0
        self.next = self._draw()
        self._spawn()

    @property
    def level(self):
        return 1 + self.lines // 10

    def interval(self):
        """Миллисекунды между шагами падения на текущем уровне."""
        return max(70, round(800 * 0.82 ** (self.level - 1)))

    def _draw(self):
        if not self.bag:
            self.bag = list(SHAPES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def _spawn(self):
        self.kind, self.next = self.next, self._draw()
        self.rot = 0
        self.x = (W - len(SHAPES[self.kind])) // 2
        self.y = -1 if self.kind == "I" else 0  # у I верхняя строка квадрата пустая
        if not self._fits(self.x, self.y, self.rot):
            self.over = True

    def piece(self, y=None):
        """Клетки текущей фигуры на поле."""
        y = self.y if y is None else y
        return [(self.x + cx, y + cy) for cx, cy in cells(self.kind, self.rot)]

    def _fits(self, x, y, rot):
        for cx, cy in cells(self.kind, rot):
            px, py = x + cx, y + cy
            if not 0 <= px < W or py >= H or (py >= 0 and self.board[py][px]):
                return False
        return True

    def move(self, dx):
        if not self.over and self._fits(self.x + dx, self.y, self.rot):
            self.x += dx
            return True
        return False

    def rotate(self, d=1):
        if self.over:
            return False
        rot = (self.rot + d) % 4
        for kx, ky in KICKS:
            if self._fits(self.x + kx, self.y + ky, rot):
                self.x, self.y, self.rot = self.x + kx, self.y + ky, rot
                return True
        return False

    def ghost_y(self):
        y = self.y
        while self._fits(self.x, y + 1, self.rot):
            y += 1
        return y

    def soft_drop(self):
        """Вниз на клетку (+1 очко). Упёрлась — фигура ложится. True, если сдвинулась."""
        if self.over:
            return False
        if self._fits(self.x, self.y + 1, self.rot):
            self.y += 1
            self.score += 1
            return True
        self._lock()
        return False

    def hard_drop(self):
        if self.over:
            return 0
        dist = self.ghost_y() - self.y
        self.y += dist
        self.score += 2 * dist
        self._lock()
        return dist

    def tick(self):
        """Шаг падения по таймеру. Возвращает число убранных линий (0, если фигура ещё падает)."""
        if self.over:
            return 0
        if self._fits(self.x, self.y + 1, self.rot):
            self.y += 1
            return 0
        return self._lock()

    def _lock(self):
        for px, py in self.piece():
            if py < 0:
                self.over = True  # фигура не поместилась на поле
                return 0
            self.board[py][px] = self.kind
        full = [y for y in range(H) if all(self.board[y])]
        for y in full:
            del self.board[y]
            self.board.insert(0, [None] * W)
        if full:
            self.score += LINE_SCORE[len(full)] * self.level
            self.lines += len(full)
        self.last_cleared = len(full)
        self._spawn()
        return len(full)
