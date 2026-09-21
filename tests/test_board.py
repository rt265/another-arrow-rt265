"""棋盘解析、点击命中与碰撞检测的测试。"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, palette
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


def test_direction_vector_matches_delta_in_screen_coordinates() -> None:
    for direction in Direction:
        delta_row, delta_col = direction.delta
        assert direction.vector == (float(delta_col), float(delta_row))


def test_invalid_level_raises_value_error() -> None:
    with pytest.raises(ValueError):
        Board((), AREA)
    with pytest.raises(ValueError):
        Board(("^..", ".v"), AREA)
    with pytest.raises(ValueError):
        Board(("^..", ".x."), AREA)


# ---------------------------------------------------------------- 动画与提示

# 三个箭头互不阻挡，用于验证“清空棋盘”与“动画仍在播放”可以并存。
FLY_LEVEL = (
    ">..",
    "..^",
    ".<.",
)

_PANEL_PADDING = 2 * config.CELL_GAP


def test_cleared_arrow_leaves_grid_before_animation_finishes() -> None:
    board = Board(CHAIN_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    origin = board.cell_rect(0, 1).center

    assert _click(board, arrow) is ClickResult.CLEARED

    # 网格里立即消失：不再阻挡后续点击，也点不到。
    assert board.arrow_at(0, 1) is None
    assert board.remaining == 1
    assert _click(board, arrow) is ClickResult.MISS
    assert board.remove(arrow) is False

    blocked = board.arrow_at(0, 0)
    assert blocked is not None
    assert board.is_path_clear(blocked) is True

    # 同时又留下了一段飞出动画。
    assert len(board.flying) == 1
    flying = board.flying[0]
    assert flying.arrow == arrow
    assert flying.position == pytest.approx(origin)
    assert flying.progress == 0.0
    assert flying.finished is False


def test_fly_out_animation_ends_after_configured_duration() -> None:
    board = Board(CHAIN_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    origin = board.cell_rect(0, 1).center
    assert _click(board, arrow) is ClickResult.CLEARED

    flying = board.flying[0]
    board.update(config.FLY_OUT_SECONDS / 2)

    # 飞出动画是缓入的：过了一半时间时才走了不到一半路程。
    assert flying.progress == pytest.approx(0.5**config.FLY_OUT_EASE_POWER)
    assert 0.0 < flying.progress < 0.5
    assert flying.position[1] > origin[1]  # (0,1) 是向下的箭头

    board.update(config.FLY_OUT_SECONDS / 2)
    panel = board.rect.inflate(_PANEL_PADDING, _PANEL_PADDING)
    assert flying.finished is True
    assert not panel.collidepoint(flying.position)
    assert board.flying == []


@pytest.mark.parametrize("direction", list(Direction))
def test_fly_out_always_exits_the_board(direction: Direction) -> None:
    board = Board(("." + direction.value + ".", "...", "..."), AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    origin_x, origin_y = board.cell_rect(0, 1).center
    assert _click(board, arrow) is ClickResult.CLEARED

    flying = board.flying[0]
    unit_x, unit_y = direction.vector
    board.update(config.FLY_OUT_SECONDS)

    offset_x = flying.position[0] - origin_x
    offset_y = flying.position[1] - origin_y
    assert (offset_x, offset_y) == pytest.approx(
        (unit_x * flying.distance, unit_y * flying.distance)
    )
    assert flying.distance > board.cell_size  # 至少飞出一格，确保完全消失
    assert not board.rect.collidepoint(flying.position)


def test_board_can_be_cleared_while_animations_are_playing() -> None:
    board = Board(FLY_LEVEL, AREA)
    for arrow in board.arrows:
        assert _click(board, arrow) is ClickResult.CLEARED

    assert board.is_cleared is True
    assert board.remaining == 0
    assert len(board.flying) == 3

    board.update(config.FLY_OUT_SECONDS * 0.5)
    assert len(board.flying) == 3  # 三个动画同时开始，因此同时结束

    board.update(config.FLY_OUT_SECONDS)
    assert board.flying == []


def test_shake_offset_pushes_along_direction_then_springs_back() -> None:
    board = Board(CHAIN_LEVEL, AREA)
    blocked = board.arrow_at(0, 0)  # 向右的箭头
    assert blocked is not None
    assert board.shake_offset == (0.0, 0.0)

    assert _click(board, blocked) is ClickResult.BLOCKED
    assert board.shake_offset == pytest.approx((0.0, 0.0))

    # 第一个四分之一周期：沿箭头方向被推出去。
    board.update(config.BLOCKED_FLASH_SECONDS * 0.125)
    pushed = board.shake_offset
    assert pushed[0] > 0.0
    assert pushed[1] == pytest.approx(0.0)

    # 第二个四分之一周期：弹回到原位之后（幅度也更小）。
    board.update(config.BLOCKED_FLASH_SECONDS * 0.25)
    spring_back = board.shake_offset
    assert spring_back[0] < 0.0
    assert abs(spring_back[0]) < abs(pushed[0])

    # 提示结束后精确归零，箭头不会停在偏移位置上。
    board.update(config.BLOCKED_FLASH_SECONDS)
    assert board.blocked_flash is None
    assert board.shake_offset == (0.0, 0.0)


def test_flash_progress_runs_from_zero_to_one() -> None:
    board = Board(CHAIN_LEVEL, AREA)
    blocked = board.arrow_at(0, 0)
    assert blocked is not None
    assert board.flash_progress == 1.0  # 没有提示时视为已结束

    assert _click(board, blocked) is ClickResult.BLOCKED
    assert board.flash_progress == 0.0

    board.update(config.BLOCKED_FLASH_SECONDS * 0.25)
    assert board.flash_progress == pytest.approx(0.25)

    board.update(config.BLOCKED_FLASH_SECONDS)
    assert board.flash_progress == 1.0


def test_blocker_hint_follows_the_current_blocker() -> None:
    board = Board(CHAIN_LEVEL, AREA)
    blocked = board.arrow_at(0, 0)
    blocker = board.arrow_at(0, 1)
    assert blocked is not None and blocker is not None
    assert board.blocker_hint is None

    assert _click(board, blocked) is ClickResult.BLOCKED
    assert board.blocker_hint == blocker

    # 阻挡者被清掉后，提示立即失效，不会继续指向已经不存在的箭头。
    assert _click(board, blocker) is ClickResult.CLEARED
    assert board.blocker_hint is None

    # 路径畅通后原来的箭头就可以飞出了。
    assert _click(board, blocked) is ClickResult.CLEARED
    assert board.remaining == 0


def test_removing_flashed_arrow_clears_animation_state() -> None:
    board = Board(CROSS_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    assert _click(board, arrow) is ClickResult.BLOCKED
    board.update(config.BLOCKED_FLASH_SECONDS * 0.125)
    assert board.shake_offset != (0.0, 0.0)

    assert board.remove(arrow) is True
    assert board.blocked_flash is None
    assert board.shake_offset == (0.0, 0.0)
    assert board.blocker_hint is None


def test_draw_handles_blocked_and_flying_arrows() -> None:
    """绘制冒烟测试：抖动、火花、虚线与飞出动画都能在同一帧内画完。"""
    board = Board(CHAIN_LEVEL, AREA)
    surface = pygame.Surface(AREA.size)

    blocked = board.arrow_at(0, 0)
    assert blocked is not None
    assert _click(board, blocked) is ClickResult.BLOCKED
    board.update(config.BLOCKED_FLASH_SECONDS * 0.125)
    board.draw(surface)

    cleared = board.arrow_at(0, 1)
    assert cleared is not None
    assert _click(board, cleared) is ClickResult.CLEARED
    board.update(config.FLY_OUT_SECONDS * 0.5)
    board.draw(surface)
    assert len(board.flying) == 1

    board.update(config.FLY_OUT_SECONDS)
    board.draw(surface)
    assert board.flying == []


# ---------------------------------------------------------------- 彩色箭头


def _render(board: Board) -> pygame.Surface:
    """把棋盘画在纯黑画布上——颜色测试看的就是“真正画出来的像素”。"""
    surface = pygame.Surface(AREA.size)
    surface.fill((0, 0, 0))
    board.draw(surface)
    return surface


def _pixel_at(surface: pygame.Surface, position: tuple[int, int]) -> config.Color:
    """读取某个像素的 RGB。"""
    pixel = surface.get_at(position)
    return (int(pixel[0]), int(pixel[1]), int(pixel[2]))


def _cell_center_pixel(
    board: Board, surface: pygame.Surface, arrow: Arrow
) -> config.Color:
    """取箭头所在格子中心的像素：那里一定落在箭头图形上，与朝向无关。"""
    return _pixel_at(surface, board.cell_rect(arrow.row, arrow.col).center)


def test_arrow_color_comes_from_the_palette_and_stays_stable() -> None:
    """颜色跟格子绑定：清掉别的箭头、重新构造本关，剩下的箭头都不会换色。"""
    board = Board(LEVELS[2], AREA)
    colors = {arrow: board.arrow_color(arrow) for arrow in board.arrows}
    assert len(set(colors.values())) > 1, "整个棋盘只有一种颜色，谈不上彩色箭头"
    for arrow, color in colors.items():
        assert color == palette.theme_color(arrow.row, arrow.col)
        assert color in config.ARROW_PALETTE

    cleared = [arrow for arrow in board.arrows if board.is_path_clear(arrow)]
    assert cleared, "第 3 关应当至少有一支可清除的箭头"
    for arrow in cleared:
        assert _click(board, arrow) is ClickResult.CLEARED

    assert board.remaining == len(colors) - len(cleared)
    for arrow in board:
        assert board.arrow_color(arrow) == colors[arrow]

    # 重新开始本关（重新构造棋盘）后，颜色布局完全一致。
    replay = Board(LEVELS[2], AREA)
    assert {(arrow.row, arrow.col): replay.arrow_color(arrow) for arrow in replay} == {
        (arrow.row, arrow.col): color for arrow, color in colors.items()
    }


def test_every_arrow_is_painted_in_its_own_theme_color() -> None:
    """每个箭头都用主题色画出来（取格子中心，那里一定落在箭头图形里）。"""
    level = LEVELS[2]
    board = Board(level, AREA)
    surface = _render(board)

    painted = {
        _cell_center_pixel(board, surface, arrow): board.arrow_color(arrow)
        for arrow in board
    }
    for pixel, color in painted.items():
        assert pixel == color
    assert len(set(painted.values())) > 1


def test_selected_and_blocked_colors_are_derived_from_the_theme() -> None:
    """选中 / 碰撞只在主题色上提亮与染色，箭头依旧保留自己的颜色身份。"""
    board = Board(CROSS_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    theme = board.arrow_color(arrow)
    assert _cell_center_pixel(board, _render(board), arrow) == theme

    # 碰撞：染向偏白的警示色（红色扩散环与火花另行说明“撞上了”）。
    assert _click(board, arrow) is ClickResult.BLOCKED
    assert _cell_center_pixel(board, _render(board), arrow) == palette.glyph_color(
        theme, blocked=True
    )

    # 提示结束后只剩选中态：向白色提亮，颜色依然来自主题色。
    board.update(config.BLOCKED_FLASH_SECONDS)
    assert board.blocked_flash is None and board.selected == arrow
    selected = palette.glyph_color(theme, selected=True)
    assert selected != theme
    assert _cell_center_pixel(board, _render(board), arrow) == selected


def test_flying_arrow_keeps_its_theme_color() -> None:
    """飞出动画画的是同一支箭头，自然也用它的主题色。"""
    board = Board(EDGE_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    assert _click(board, arrow) is ClickResult.CLEARED

    flying = board.flying[0]
    assert flying.progress == 0.0  # 动画刚开始，箭头完全不透明
    position = (round(flying.position[0]), round(flying.position[1]))
    assert _pixel_at(_render(board), position) == board.arrow_color(arrow)
