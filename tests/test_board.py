"""棋盘与箭头摆放的测试。"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265.board import Board
from another_arrow_rt265.direction import Direction, from_symbol
from another_arrow_rt265.levels import LEVELS

AREA = pygame.Rect(0, 0, 640, 640)
ARROW_SYMBOLS = {"^", "v", "<", ">"}


def test_levels_are_rectangular_and_use_known_symbols() -> None:
    for index, level in enumerate(LEVELS, start=1):
        assert level, f"第 {index} 关为空"
        width = len(level[0])
        for line in level:
            assert len(line) == width, f"第 {index} 关各行长度不一致"
            assert set(line) <= ARROW_SYMBOLS | {"."}, f"第 {index} 关包含未知符号"


def test_arrows_are_placed_per_level() -> None:
    for level in LEVELS:
        board = Board(level, AREA)
        expected = [
            (row, col)
            for row, line in enumerate(level)
            for col, ch in enumerate(line)
            if ch != "."
        ]
        assert [(arrow.row, arrow.col) for arrow in board] == expected
        for (row, col), arrow in zip(expected, board, strict=True):
            assert arrow.direction is from_symbol(level[row][col])


def test_hit_test_matches_arrow_centers() -> None:
    board = Board(LEVELS[0], AREA)
    for arrow in board:
        center = board.cell_rect(arrow.row, arrow.col).center
        assert board.hit_test(center) == arrow


def test_hit_test_outside_board_returns_none() -> None:
    board = Board(LEVELS[0], AREA)
    assert board.hit_test((0, 0)) is None
    assert board.hit_test((AREA.right - 1, AREA.bottom - 1)) is None


def test_handle_click_updates_selection() -> None:
    board = Board(LEVELS[0], AREA)
    arrow = board.arrows[0]

    assert board.selected is None
    assert board.handle_click(board.cell_rect(arrow.row, arrow.col).center) == arrow
    assert board.selected == arrow

    empty_cell = next(
        (row, col)
        for row in range(board.rows)
        for col in range(board.cols)
        if board.arrow_at(row, col) is None
    )
    assert board.handle_click(board.cell_rect(*empty_cell).center) is None
    assert board.selected is None


def test_direction_delta_and_symbol_roundtrip() -> None:
    assert from_symbol("^") is Direction.UP
    assert Direction.UP.delta == (-1, 0)
    assert Direction.RIGHT.delta == (0, 1)
    assert Direction.DOWN.delta == (1, 0)
    assert Direction.LEFT.delta == (0, -1)

    with pytest.raises(ValueError):
        from_symbol("x")


def test_invalid_level_raises_value_error() -> None:
    with pytest.raises(ValueError):
        Board((), AREA)
    with pytest.raises(ValueError):
        Board(("^..", ".v"), AREA)
    with pytest.raises(ValueError):
        Board(("^..", ".x."), AREA)
