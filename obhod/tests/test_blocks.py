"""Правила игры «Блоки»: фигуры, повороты, линии, очки, конец игры."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import blocks  # noqa: E402
from core.blocks import H, W, Game  # noqa: E402


class Pieces(unittest.TestCase):
    def test_every_shape_has_four_cells_in_every_rotation(self):
        for kind in blocks.SHAPES:
            for rot in range(4):
                self.assertEqual(len(set(blocks.cells(kind, rot))), 4, f"{kind} rot {rot}")

    def test_four_rotations_return_to_start(self):
        for kind in blocks.SHAPES:
            self.assertEqual(sorted(blocks.cells(kind, 4)), sorted(blocks.cells(kind, 0)))

    def test_bag_gives_each_shape_once_per_seven(self):
        g = Game(seed=1)
        seen = [g.kind, g.next]
        for _ in range(12):
            g._spawn()
            seen.append(g.next)
        self.assertEqual(sorted(seen[:7]), sorted(blocks.SHAPES))
        self.assertEqual(sorted(seen[7:14]), sorted(blocks.SHAPES))


class Moves(unittest.TestCase):
    def test_walls_stop_the_piece(self):
        g = Game(seed=2)
        for _ in range(W):
            g.move(-1)
        self.assertEqual(min(x for x, _ in g.piece()), 0)
        self.assertFalse(g.move(-1))
        for _ in range(W):
            g.move(1)
        self.assertEqual(max(x for x, _ in g.piece()), W - 1)

    def test_rotation_next_to_wall_kicks_inside(self):
        g = Game(seed=3)
        g.kind, g.rot, g.x, g.y = "I", 1, -2, 5  # вертикальная I у левой стены
        self.assertEqual(min(x for x, _ in g.piece()), 0)
        self.assertTrue(g.rotate(1))
        self.assertTrue(all(0 <= x < W for x, _ in g.piece()))

    def test_hard_drop_lands_on_floor_and_scores(self):
        g = Game(seed=4)
        kind = g.kind
        dist = g.hard_drop()
        self.assertGreater(dist, 10)
        self.assertEqual(g.score, 2 * dist)
        self.assertEqual(sum(cell == kind for row in g.board for cell in row), 4)
        self.assertTrue(any(g.board[H - 1]))

    def test_ghost_matches_hard_drop(self):
        g = Game(seed=5)
        ghost = g.piece(g.ghost_y())
        kind = g.kind
        g.hard_drop()
        self.assertTrue(all(g.board[y][x] == kind for x, y in ghost))


class Lines(unittest.TestCase):
    def fill_rows(self, g, rows, hole=0):
        for y in rows:
            g.board[y] = ["J"] * W
            g.board[y][hole] = None

    def test_tetris_clears_four_lines_for_800_times_level(self):
        g = Game(seed=6)
        self.fill_rows(g, range(H - 4, H), hole=0)
        g.kind, g.rot, g.x, g.y = "I", 1, -2, 0  # вертикальная I над дыркой
        g.hard_drop()
        self.assertEqual(g.last_cleared, 4)
        self.assertEqual(g.lines, 4)
        self.assertEqual(g.score - 2 * (H - 4), 800)
        self.assertTrue(all(cell is None for row in g.board for cell in row))

    def test_rows_above_fall_down(self):
        g = Game(seed=7)
        self.fill_rows(g, [H - 1], hole=3)
        g.board[H - 2][5] = "S"
        g.kind, g.rot, g.x, g.y = "I", 1, 1, 0  # клетки I в столбце 3
        g.hard_drop()
        self.assertEqual(g.last_cleared, 1)
        self.assertEqual(g.board[H - 1][5], "S")
        self.assertEqual(g.board[H - 1][3], "I")

    def test_level_and_speed_grow_every_ten_lines(self):
        g = Game(seed=8)
        self.assertEqual(g.level, 1)
        slow = g.interval()
        g.lines = 25
        self.assertEqual(g.level, 3)
        self.assertLess(g.interval(), slow)
        g.lines = 1000
        self.assertEqual(g.interval(), 70)


class GameOver(unittest.TestCase):
    def test_stack_to_the_top_ends_the_game(self):
        g = Game(seed=9)
        for _ in range(200):
            if g.over:
                break
            g.hard_drop()
        self.assertTrue(g.over)
        before = g.score
        self.assertEqual(g.hard_drop(), 0)
        self.assertFalse(g.move(1))
        self.assertEqual(g.score, before)


if __name__ == "__main__":
    unittest.main()
