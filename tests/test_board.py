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


def test_arrow_chips_are_anti_aliased() -> None:
    """圆片与箭头图形的边缘要有过渡色（超采样贴图的效果，见 ``sprites``）。

    直接用 ``pygame.draw`` 画的话，一个格子里只会有“格子底 / 圆片 / 描边 / 箭头”
    这几种整块颜色（实测 3 种），圆弧与斜边全是台阶；抗锯齿之后必然多出几十种
    过渡色。这条测试把“素材低分辨率”是否被改回去钉住。
    """
    board = Board(LEVELS[2], AREA)
    arrow = next(iter(board))
    surface = _render(board)
    cell = board.cell_rect(arrow.row, arrow.col)

    colors = {
        _pixel_at(surface, (x, y))
        for x in range(cell.left, cell.right)
        for y in range(cell.top, cell.bottom)
    }
    assert len(colors) > 10, f"格子里只有 {len(colors)} 种颜色，边缘是硬边的"


# ---------------------------------------------------------------- 辅助线


def _panel(board: Board) -> pygame.Rect:
    """棋盘可见区域的边缘（与 ``Board.draw`` 画底板时用的是同一个矩形）。"""
    return board.rect.inflate(2 * config.CELL_GAP, 2 * config.CELL_GAP)


def _blank_surface() -> pygame.Surface:
    surface = pygame.Surface(AREA.size)
    surface.fill((0, 0, 0))
    return surface


def _color_hits(surface: pygame.Surface, color: config.Color, area: pygame.Rect) -> int:
    """数 ``area`` 里正好等于 ``color`` 的像素个数。

    辅助线是不带抗锯齿的纯几何绘制，颜色因此是精确值，直接数像素就能验证
    “画了 / 没画”，比只断言常量更接近玩家看到的东西。
    """
    return sum(
        1
        for x in range(area.left, area.right)
        for y in range(area.top, area.bottom)
        if _pixel_at(surface, (x, y)) == color
    )


def _dim(color: config.Color) -> config.Color:
    """“开关打开但没悬停”时的淡色版辅助线颜色（与 ``Board._draw_guide`` 同一套混色）。"""
    return palette.mix(color, config.COLOR_CELL, config.GUIDE_LINE_DIM_MIX)


def test_guide_line_runs_from_the_arrow_to_the_board_edge() -> None:
    """畅通的箭头：辅助线从圆片外沿一直拉到棋盘可见区域的边缘。"""
    board = Board(LEVELS[0], AREA)
    arrow = board.arrow_at(3, 0)  # '>'，右边三格都是空的
    assert arrow is not None
    assert board.is_path_clear(arrow)

    line = board.guide_line(arrow)
    cell = board.cell_rect(3, 0)
    radius = cell.width * 0.44

    assert line.arrow == arrow
    assert line.blocked is False
    assert line.blocker is None
    assert line.start == pytest.approx(
        (cell.centerx + radius + config.GUIDE_LINE_MARGIN, cell.centery)
    )
    assert line.end == pytest.approx((_panel(board).right, cell.centery))


def test_guide_line_stops_on_the_arrow_that_blocks_it() -> None:
    """被挡的箭头：辅助线停在挡路箭头的圆片外沿，不会穿过去。"""
    board = Board(LEVELS[0], AREA)
    blocked = board.arrow_at(0, 2)  # 'v'，正下方被 (1,2) 的 '<' 挡住
    blocker = board.arrow_at(1, 2)
    assert blocked is not None
    assert blocker is not None
    assert board.blocking_arrow(blocked) == blocker

    line = board.guide_line(blocked)
    cell = board.cell_rect(0, 2)
    target = board.cell_rect(1, 2)
    radius = cell.width * 0.44

    assert line.blocked is True
    assert line.blocker == blocker
    assert line.start[0] == pytest.approx(cell.centerx)
    assert line.end[0] == pytest.approx(cell.centerx)
    assert line.start[1] == pytest.approx(
        cell.centery + radius + config.GUIDE_LINE_MARGIN
    )
    assert line.end[1] == pytest.approx(
        target.centery - radius - config.GUIDE_LINE_MARGIN
    )
    # 线确实“顶到”了阻挡者：终点落在自己格子之外、挡路箭头中心之前。
    assert cell.bottom < line.end[1] < target.centery


@pytest.mark.parametrize("direction", list(Direction))
def test_guide_line_points_at_the_edge_the_arrow_faces(direction: Direction) -> None:
    """四种朝向：辅助线都朝箭头指的那条边走，终点落在棋盘边缘上。"""
    board = Board(("...", f".{direction.value}.", "..."), AREA)
    arrow = board.arrow_at(1, 1)
    assert arrow is not None

    line = board.guide_line(arrow)
    cell = board.cell_rect(1, 1)
    panel = _panel(board)

    assert line.blocked is False
    if direction in (Direction.LEFT, Direction.RIGHT):
        assert line.end[1] == pytest.approx(cell.centery)
        edge = panel.right if direction is Direction.RIGHT else panel.left
        assert line.end[0] == pytest.approx(edge)
    else:
        assert line.end[0] == pytest.approx(cell.centerx)
        edge = panel.bottom if direction is Direction.DOWN else panel.top
        assert line.end[1] == pytest.approx(edge)


def test_guide_line_follows_the_board_after_the_blocker_is_gone() -> None:
    """辅助线读的是“当下”的棋盘：挡路的箭头一清，线立刻通到边缘。"""
    board = Board(CHAIN_LEVEL, AREA)
    arrow = board.arrow_at(0, 0)
    blocker = board.arrow_at(0, 1)
    assert arrow is not None
    assert blocker is not None

    assert board.guide_line(arrow).blocker == blocker
    assert _click(board, blocker) is ClickResult.CLEARED

    line = board.guide_line(arrow)
    assert line.blocked is False
    assert line.end[0] == pytest.approx(_panel(board).right)


def test_guides_stay_hidden_until_the_switch_is_on() -> None:
    """辅助线是可选的：开关没打开时，连悬停的箭头也不画线。"""
    board = Board(EDGE_LEVEL, AREA)  # 单个朝下的箭头，正下方一路畅通
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    cell = board.cell_rect(0, 1)
    # 箭头正下方的一条窄带：辅助线的虚线就落在这里，而箭头圆片够不到。
    band = pygame.Rect(
        cell.centerx - 3, cell.bottom, 6, board.rect.bottom - cell.bottom
    )

    surface = _blank_surface()
    board.draw(surface, cell.center)
    assert _color_hits(surface, config.GUIDE_LINE_COLOR_CLEAR, band) == 0
    assert _color_hits(surface, _dim(config.GUIDE_LINE_COLOR_CLEAR), band) == 0

    # 打开开关之后同样的悬停位置就有线了（下面几条测试都建立在这一步上）。
    guides = _blank_surface()
    board.draw(guides, cell.center, show_guides=True)
    assert _color_hits(guides, config.GUIDE_LINE_COLOR_CLEAR, band) > 0


def test_hovering_an_arrow_paints_a_brighter_guide_line() -> None:
    """开关打开后：所有箭头都有线，而鼠标指着的那条用亮色画出来。"""
    board = Board(EDGE_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    cell = board.cell_rect(0, 1)
    band = pygame.Rect(
        cell.centerx - 3, cell.bottom, 6, board.rect.bottom - cell.bottom
    )
    bright = config.GUIDE_LINE_COLOR_CLEAR
    faint = _dim(bright)

    no_mouse = _blank_surface()
    board.draw(no_mouse, show_guides=True)
    assert _color_hits(no_mouse, faint, band) > 0, "开关打开后应当有线"
    assert _color_hits(no_mouse, bright, band) == 0, "没有悬停就没有亮色的那条"

    outside = _blank_surface()
    board.draw(outside, (0, 0), show_guides=True)
    assert _color_hits(outside, bright, band) == 0, "棋盘外不算悬停"

    hovered = _blank_surface()
    board.draw(hovered, cell.center, show_guides=True)
    assert _color_hits(hovered, bright, band) > 0
    assert _color_hits(hovered, faint, band) == 0, "同一支箭头只画一条线"


def test_hovering_a_blocked_arrow_paints_the_blocked_color() -> None:
    """被挡住的箭头用另一种颜色表示“这一箭点不动”。"""
    board = Board(CHAIN_LEVEL, AREA)
    arrow = board.arrow_at(0, 0)
    assert arrow is not None
    cell = board.cell_rect(0, 0)
    band = pygame.Rect(cell.right, cell.centery - 3, board.rect.right - cell.right, 6)

    surface = _blank_surface()
    board.draw(surface, cell.center, show_guides=True)

    assert _color_hits(surface, config.GUIDE_LINE_COLOR_BLOCKED, band) > 0
    assert _color_hits(surface, config.GUIDE_LINE_COLOR_CLEAR, band) == 0


def test_the_switch_paints_every_arrow_dimmed() -> None:
    """开关打开：畅通与被挡的箭头各有一条淡色辅助线，不会太抢眼。"""
    board = Board(LEVELS[0], AREA)
    region = board.rect
    clear = _dim(config.GUIDE_LINE_COLOR_CLEAR)
    blocked = _dim(config.GUIDE_LINE_COLOR_BLOCKED)

    idle = _blank_surface()
    board.draw(idle)
    assert _color_hits(idle, clear, region) == 0
    assert _color_hits(idle, blocked, region) == 0

    guides = _blank_surface()
    board.draw(guides, show_guides=True)
    assert _color_hits(guides, clear, region) > 0, "畅通的箭头应当有线"
    assert _color_hits(guides, blocked, region) > 0, "被挡的箭头也应当有线"
    # 没有悬停的箭头，所有线都用淡色版；亮色只留给鼠标指着的那一条。
    assert _color_hits(guides, config.GUIDE_LINE_COLOR_CLEAR, region) == 0
    assert _color_hits(guides, config.GUIDE_LINE_COLOR_BLOCKED, region) == 0


# ---------------------------------------------------------------- 窗口缩放


def test_reshape_moves_the_board_without_touching_the_arrows() -> None:
    """窗口变化只重算几何：格子的尺寸与位置变了，箭头布局一寸不动。"""
    board = Board(LEVELS[0], pygame.Rect(0, 0, 400, 400))
    before = [(arrow.row, arrow.col, arrow.direction) for arrow in board]
    before_cell = board.cell_size

    area = pygame.Rect(0, 0, 800, 800)
    board.reshape(area)

    assert [(arrow.row, arrow.col, arrow.direction) for arrow in board] == before
    assert board.rect.center == area.center
    assert board.cell_size > before_cell
    assert board.rect.size == (
        board.cols * board.cell_size,
        board.rows * board.cell_size,
    )


def test_reshape_keeps_the_selection_and_the_collision_hint() -> None:
    """缩放不打断玩家：选中与碰撞提示保留，新几何下点击仍然命中同一支箭头。"""
    board = Board(CROSS_LEVEL, AREA)
    arrow = board.arrow_at(0, 1)
    assert arrow is not None
    assert board.handle_click(board.cell_rect(0, 1).center) is ClickResult.BLOCKED

    board.reshape(AREA.inflate(-200, -200))

    assert board.blocked_flash == arrow
    assert board.selected == arrow
    assert board.hit_test(board.cell_rect(0, 1).center) == arrow


def test_reshape_drops_the_fly_out_animation() -> None:
    """飞出动画记的是像素坐标，缩放后不再成立，因此直接放弃（只有 0.32 秒）。"""
    board = Board(LEVELS[0], AREA)
    arrow = next(iter(board))
    assert board.handle_click(board.cell_rect(arrow.row, arrow.col).center) is (
        ClickResult.CLEARED
    )
    assert board.flying

    board.reshape(AREA)

    assert board.flying == []
