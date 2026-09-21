"""棋盘解析、点击命中与碰撞检测的测试。"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config
from another_arrow_rt265.board import Arrow, Board, ClickResult
from another_arrow_rt265.direction import Direction, from_symbol
from another_arrow_rt265.levels import LEVELS

AREA = pygame.Rect(0, 0, 640, 640)
ARROW_SYMBOLS = {"^", "v", "<", ">"}


def _click(board: Board, arrow: Arrow) -> ClickResult:
    """点击某个箭头所在的格子中心。"""
    return board.handle_click(board.cell_rect(arrow.row, arrow.col).center)


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


# 十字形棋盘：四个箭头互相瞄准，四个方向全被阻挡。
CROSS_LEVEL = (
    ".v.",
    ">.<",
    ".^.",
)

# 同一行上互相瞄准的两个箭头：彼此阻挡，形成死锁，只能靠外部手段解锁。
LINE_LEVEL = (
    ">..<",
    "....",
    "....",
    "....",
)

# 阻挡链：必须先清掉 (0,1) 才能清掉 (0,0)。
CHAIN_LEVEL = (
    ">v..",
    "....",
    "....",
    "....",
)

# 一行三箭头：(0,0) 前进方向上的最近阻挡是 (0,1)，而不是更远的 (0,3)。
NEAR_LEVEL = (">v.v",)

# 单个朝向边界的箭头，前方畅通。
EDGE_LEVEL = (
    ".v.",
    "...",
    "...",
)


def test_click_clears_arrow_when_path_is_clear() -> None:
    board = Board(LEVELS[0], AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    remaining = board.remaining

    assert _click(board, arrow) is ClickResult.CLEARED
    assert board.arrow_at(0, 1) is None
    assert arrow not in board.arrows
    assert board.remaining == remaining - 1
    assert board.selected is None


def test_blocked_arrow_stays_on_board_and_flashes() -> None:
    board = Board(CHAIN_LEVEL, AREA)
    blocked = board.arrow_at(0, 0)
    assert blocked is not None
    assert board.is_path_clear(blocked) is False
    assert board.blocking_arrow(blocked) == board.arrow_at(0, 1)

    assert _click(board, blocked) is ClickResult.BLOCKED
    assert board.arrow_at(0, 0) == blocked
    assert board.selected == blocked
    assert board.blocked_flash == blocked

    board.update(config.BLOCKED_FLASH_SECONDS / 2)
    assert board.blocked_flash == blocked

    board.update(config.BLOCKED_FLASH_SECONDS)
    assert board.blocked_flash is None
    assert board.arrow_at(0, 0) == blocked


def test_removing_blocker_opens_the_path() -> None:
    board = Board(CHAIN_LEVEL, AREA)
    blocker = board.arrow_at(0, 1)
    assert blocker is not None
    assert _click(board, blocker) is ClickResult.CLEARED

    blocked = board.arrow_at(0, 0)
    assert blocked is not None
    assert board.is_path_clear(blocked) is True
    assert _click(board, blocked) is ClickResult.CLEARED

    assert board.remaining == 0
    assert board.is_cleared is True


def test_all_four_directions_detect_blockers() -> None:
    board = Board(CROSS_LEVEL, AREA)
    down = board.arrow_at(0, 1)
    up = board.arrow_at(2, 1)
    right = board.arrow_at(1, 0)
    left = board.arrow_at(1, 2)
    assert down is not None and up is not None
    assert right is not None and left is not None

    assert board.blocking_arrow(down) == up
    assert board.blocking_arrow(up) == down
    assert board.blocking_arrow(right) == left
    assert board.blocking_arrow(left) == right

    for arrow in (down, up, right, left):
        assert _click(board, arrow) is ClickResult.BLOCKED
    assert board.remaining == 4


def test_blocking_arrow_returns_nearest_obstacle() -> None:
    board = Board(NEAR_LEVEL, AREA)
    arrow = board.arrow_at(0, 0)
    assert arrow is not None
    assert board.blocking_arrow(arrow) == board.arrow_at(0, 1)


def test_facing_arrows_block_each_other_across_distance() -> None:
    board = Board(LINE_LEVEL, AREA)
    left = board.arrow_at(0, 0)
    right = board.arrow_at(0, 3)
    assert left is not None and right is not None

    assert board.blocking_arrow(left) == right
    assert board.blocking_arrow(right) == left

    # 互相阻挡时双方都无法飞出。
    assert _click(board, left) is ClickResult.BLOCKED
    assert _click(board, right) is ClickResult.BLOCKED
    assert board.remaining == 2

    # 强制移除其中一个后，另一个即可飞出。
    assert board.remove(right) is True
    assert board.is_path_clear(left) is True
    assert _click(board, left) is ClickResult.CLEARED
    assert board.remaining == 0


def test_path_pointing_out_of_board_is_clear() -> None:
    board = Board(EDGE_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    assert board.is_path_clear(arrow) is True
    assert board.blocking_arrow(arrow) is None
    assert _click(board, arrow) is ClickResult.CLEARED
    assert board.remaining == 0


def test_handle_click_miss_clears_selection() -> None:
    board = Board(CROSS_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    assert _click(board, arrow) is ClickResult.BLOCKED
    assert board.selected == arrow

    assert board.handle_click((0, 0)) is ClickResult.MISS
    assert board.selected is None


def test_remove_rejects_stale_or_unknown_arrows() -> None:
    board = Board(CROSS_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None

    # 位置正确但方向不同：不视为同一个箭头。
    assert board.remove(Arrow(0, 1, Direction.UP)) is False
    # 越界坐标。
    assert board.remove(Arrow(9, 9, Direction.UP)) is False
    # 正常移除，且不能重复移除。
    assert board.remove(arrow) is True
    assert board.remove(arrow) is False
    assert board.remaining == 3


def test_removing_flashed_arrow_resets_flash() -> None:
    board = Board(CROSS_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    assert _click(board, arrow) is ClickResult.BLOCKED
    assert board.blocked_flash == arrow

    assert board.remove(arrow) is True
    assert board.blocked_flash is None

    # 提示结束后再次推进不会报错。
    board.update(config.BLOCKED_FLASH_SECONDS)
    assert board.blocked_flash is None


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
