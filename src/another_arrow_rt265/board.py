"""棋盘的数据结构与绘制。

本模块负责把关卡的字符网格转换为箭头布局，完成棋盘的绘制、鼠标命中判定，
以及箭头飞出前的碰撞检测与移除。箭头的飞出动画与关卡结算将在后续事项中实现。
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Final

import pygame

from another_arrow_rt265 import config
from another_arrow_rt265.direction import Direction, from_symbol
from another_arrow_rt265.levels import Level

# 以“向上”为基准的单位箭头形状，坐标原点位于格子中心，取值范围约 [-0.42, 0.42]。
_ARROW_SHAPE: Final[tuple[tuple[float, float], ...]] = (
    (0.00, -0.42),
    (0.34, -0.06),
    (0.13, -0.06),
    (0.13, 0.40),
    (-0.13, 0.40),
    (-0.13, -0.06),
    (-0.34, -0.06),
)

_EMPTY_CELL: Final[str] = "."


@dataclass(frozen=True, slots=True)
class Arrow:
    """棋盘上的单个箭头。"""

    row: int
    col: int
    direction: Direction


class ClickResult(Enum):
    """一次鼠标点击的处理结果。"""

    MISS = "miss"
    """没有点中任何箭头。"""

    CLEARED = "cleared"
    """点中的箭头前方无阻挡，已飞出棋盘。"""

    BLOCKED = "blocked"
    """点中的箭头前方有其他箭头阻挡，无法飞出。"""


class Board:
    """一块按网格摆放箭头的棋盘。"""

    def __init__(self, level: Level, area: pygame.Rect) -> None:
        """在 ``area`` 区域中居中创建棋盘。

        Args:
            level: 关卡的字符网格。
            area: 可供棋盘使用的屏幕区域，棋盘会按需缩放并居中。

        Raises:
            ValueError: 关卡为空、非矩形或包含未知符号时抛出。
        """
        self._cells: list[list[Arrow | None]] = _parse_level(level)
        self.rows: int = len(self._cells)
        self.cols: int = len(self._cells[0])
        self.cell_size: int = min(
            area.width // self.cols,
            area.height // self.rows,
            config.MAX_CELL_SIZE,
        )
        self.rect: pygame.Rect = pygame.Rect(
            0,
            0,
            self.cols * self.cell_size,
            self.rows * self.cell_size,
        )
        self.rect.center = area.center
        self.selected: Arrow | None = None
        self._blocked_flash: Arrow | None = None
        self._flash_remaining: float = 0.0

    def __iter__(self) -> Iterator[Arrow]:
        """按行优先顺序遍历棋盘上仍在场的箭头。"""
        for row_cells in self._cells:
            for arrow in row_cells:
                if arrow is not None:
                    yield arrow

    @property
    def arrows(self) -> list[Arrow]:
        """当前棋盘上的全部箭头。"""
        return list(self)

    @property
    def remaining(self) -> int:
        """当前棋盘上剩余的箭头数量。"""
        return sum(1 for _ in self)

    @property
    def is_cleared(self) -> bool:
        """棋盘上的箭头是否已经全部清除。"""
        return self.remaining == 0

    @property
    def blocked_flash(self) -> Arrow | None:
        """当前正在显示碰撞提示的箭头，没有则返回 ``None``。"""
        return self._blocked_flash

    def cell_rect(self, row: int, col: int) -> pygame.Rect:
        """返回某个格子在屏幕上的矩形区域（已扣除格子间隙）。"""
        inner_size = self.cell_size - 2 * config.CELL_GAP
        return pygame.Rect(
            self.rect.left + col * self.cell_size + config.CELL_GAP,
            self.rect.top + row * self.cell_size + config.CELL_GAP,
            inner_size,
            inner_size,
        )

    def arrow_at(self, row: int, col: int) -> Arrow | None:
        """返回指定格子中的箭头，空格子或越界返回 ``None``。"""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self._cells[row][col]
        return None

    def hit_test(self, position: tuple[int, int]) -> Arrow | None:
        """判断屏幕坐标命中了哪个箭头，未命中箭头时返回 ``None``。"""
        if not self.rect.collidepoint(position):
            return None
        col = (position[0] - self.rect.left) // self.cell_size
        row = (position[1] - self.rect.top) // self.cell_size
        return self.arrow_at(int(row), int(col))

    def blocking_arrow(self, arrow: Arrow) -> Arrow | None:
        """返回第一个阻挡 ``arrow`` 的箭头，前方畅通时返回 ``None``。

        检查方式是沿 ``arrow.direction`` 逐格前进，直到离开棋盘或遇到其他箭头。
        """
        delta_row, delta_col = arrow.direction.delta
        row = arrow.row + delta_row
        col = arrow.col + delta_col
        while 0 <= row < self.rows and 0 <= col < self.cols:
            occupant = self._cells[row][col]
            if occupant is not None:
                return occupant
            row += delta_row
            col += delta_col
        return None

    def is_path_clear(self, arrow: Arrow) -> bool:
        """判断 ``arrow`` 前进方向上是否不存在其他箭头。"""
        return self.blocking_arrow(arrow) is None

    def remove(self, arrow: Arrow) -> bool:
        """把 ``arrow`` 从棋盘上移除，成功返回 ``True``。

        移除会同时清理该箭头的选中状态与碰撞提示。
        """
        if self.arrow_at(arrow.row, arrow.col) != arrow:
            return False
        self._cells[arrow.row][arrow.col] = None
        if self.selected == arrow:
            self.selected = None
        if self._blocked_flash == arrow:
            self._clear_flash()
        return True

    def handle_click(self, position: tuple[int, int]) -> ClickResult:
        """处理一次鼠标左键点击：更新选中状态并尝试移除箭头。

        Returns:
            本次点击的结果，见 :class:`ClickResult`。
        """
        arrow = self.hit_test(position)
        if arrow is None:
            self.selected = None
            return ClickResult.MISS

        if not self.is_path_clear(arrow):
            self.selected = arrow
            self._start_flash(arrow)
            return ClickResult.BLOCKED

        self.remove(arrow)
        return ClickResult.CLEARED

    def update(self, dt: float) -> None:
        """推进棋盘上计时类反馈的状态，``dt`` 为上一帧耗时（秒）。"""
        if self._blocked_flash is None:
            return
        self._flash_remaining = max(0.0, self._flash_remaining - dt)
        if self._flash_remaining == 0.0:
            self._clear_flash()

    def _start_flash(self, arrow: Arrow) -> None:
        """开始（或重新开始）对 ``arrow`` 的碰撞提示。"""
        self._blocked_flash = arrow
        self._flash_remaining = config.BLOCKED_FLASH_SECONDS

    def _clear_flash(self) -> None:
        """结束当前的碰撞提示。"""
        self._blocked_flash = None
        self._flash_remaining = 0.0

    def draw(self, surface: pygame.Surface) -> None:
        """把棋盘底板、格子和箭头绘制到 ``surface`` 上。"""
        panel = self.rect.inflate(2 * config.CELL_GAP, 2 * config.CELL_GAP)
        pygame.draw.rect(
            surface, config.COLOR_BOARD, panel, border_radius=config.BOARD_RADIUS
        )

        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.cell_rect(row, col)
                pygame.draw.rect(
                    surface,
                    config.COLOR_CELL,
                    cell,
                    border_radius=config.CELL_RADIUS,
                )

        for arrow in self:
            self._draw_arrow(surface, arrow)

    def _draw_arrow(self, surface: pygame.Surface, arrow: Arrow) -> None:
        """绘制单个箭头。

        被选中的箭头使用高亮配色并带一圈金色描边；
        刚刚撞到其他箭头的箭头使用警示配色，并带一圈向外扩散的红环。
        """
        cell = self.cell_rect(arrow.row, arrow.col)
        center = cell.center
        is_selected = arrow == self.selected

        if arrow == self._blocked_flash:
            chip_color = config.COLOR_CHIP_BLOCKED
            arrow_color = config.COLOR_ARROW_BLOCKED
        elif is_selected:
            chip_color = config.COLOR_CHIP_SELECTED
            arrow_color = config.COLOR_ARROW_SELECTED
        else:
            chip_color = config.COLOR_CHIP
            arrow_color = config.COLOR_ARROW

        radius = int(cell.width * 0.44)
        pygame.draw.circle(surface, chip_color, center, radius)
        if arrow == self._blocked_flash:
            progress = 1.0 - self._flash_remaining / config.BLOCKED_FLASH_SECONDS
            pygame.draw.circle(
                surface,
                config.COLOR_BLOCKED_RING,
                center,
                int(radius * (1.0 + 0.45 * progress)),
                width=3,
            )
        elif is_selected:
            pygame.draw.circle(
                surface,
                config.COLOR_SELECTION_RING,
                center,
                radius,
                width=3,
            )

        pygame.draw.polygon(
            surface,
            arrow_color,
            _arrow_points(center, cell.width, arrow.direction),
        )


def _parse_level(level: Level) -> list[list[Arrow | None]]:
    """把关卡的字符网格转换为二维箭头数组。

    Args:
        level: 关卡的字符网格。

    Returns:
        与关卡等大的二维列表，空格子为 ``None``。

    Raises:
        ValueError: 关卡为空、各行长度不一致或包含未知符号时抛出。
    """
    if not level:
        msg = "关卡不能为空"
        raise ValueError(msg)

    width = len(level[0])
    if width == 0:
        msg = "关卡的列数不能为 0"
        raise ValueError(msg)

    cells: list[list[Arrow | None]] = []
    for row_index, line in enumerate(level):
        if len(line) != width:
            msg = f"关卡第 {row_index + 1} 行的长度与首行不一致"
            raise ValueError(msg)

        row_cells: list[Arrow | None] = []
        for col_index, symbol in enumerate(line):
            if symbol == _EMPTY_CELL:
                row_cells.append(None)
                continue
            try:
                direction = from_symbol(symbol)
            except ValueError as error:
                msg = f"关卡第 {row_index + 1} 行第 {col_index + 1} 列的符号非法：{symbol!r}"
                raise ValueError(msg) from error
            row_cells.append(Arrow(row_index, col_index, direction))
        cells.append(row_cells)

    return cells


def _arrow_points(
    center: tuple[int, int],
    size: int,
    direction: Direction,
) -> list[tuple[int, int]]:
    """计算箭头多边形在屏幕坐标下的顶点。"""
    radians = math.radians(direction.angle)
    cos_angle, sin_angle = math.cos(radians), math.sin(radians)
    center_x, center_y = center

    points: list[tuple[int, int]] = []
    for x, y in _ARROW_SHAPE:
        rotated_x = x * cos_angle - y * sin_angle
        rotated_y = x * sin_angle + y * cos_angle
        points.append(
            (round(center_x + rotated_x * size), round(center_y + rotated_y * size))
        )
    return points
