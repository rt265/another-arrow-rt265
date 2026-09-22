"""棋盘的数据结构与绘制。

本模块负责把关卡的字符网格转换为箭头布局，完成棋盘的绘制、鼠标命中判定，
以及箭头飞出前的碰撞检测与移除。此外还实现了点击相关的动画与提示：

- 清除箭头时播放“飞出棋盘”的动画（逻辑移除是瞬时的，动画只是视觉表现）；
- 被阻挡时箭头沿前进方向抖动、前方溅出火花，并高亮提示挡路的箭头；
- 被选中的箭头带一圈呼吸式描边；
- **辅助线**（可选功能，默认关闭）：打开后每个箭头都沿它当前的前进方向拉一条虚线，
  顶到棋盘边缘（表示这一箭点得动）或停在挡路箭头上（表示点不动），
  鼠标指着的那条会更亮；见 :meth:`Board.guide_line`。
  辅助线只读棋盘状态、不改判定，因此每帧重算就自动跟得上棋盘的变化。

每个箭头都有自己的主题色（见 :mod:`another_arrow_rt265.palette`）：颜色由格子的
位置决定，一关之内不会变；选中与碰撞状态只在主题色上提亮 / 染色，不换颜色身份。

棋盘上所有带弧线或斜边的图形都走 :mod:`another_arrow_rt265.sprites` 的超采样贴图
（底板与格子是圆角矩形，箭头是“圆片 + 描边 + 多边形”的一张合成贴图），因此边缘
不再有阶梯；只有轴对齐的虚线仍然直接画——那本来就没有锯齿。箭头贴图按
“格子尺寸 + 主题色 + 状态 + 朝向”缓存，选中环 / 碰撞环与火花这类每帧都在动的
部分才现画。

动画状态统一由 :meth:`Board.update` 推进，便于在无窗口环境下用固定 ``dt`` 测试。

棋盘上的长度常量（格子间隙、圆角、线宽、辅助线的虚线长短……）都是**设计尺寸**下的值，
绘制时按当前视口换算（见 :mod:`another_arrow_rt265.viewport`），因此窗口放大后
格子、圆片与线宽一起等比变大，而不是把原画面拉大。窗口尺寸变化时由
:meth:`Board.reshape` 就地重算格子尺寸，关卡进度不受影响。
"""

from __future__ import annotations

import functools
import math
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Final

import pygame

from another_arrow_rt265 import config, palette, sprites, viewport
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

# 箭头圆片的半径相对格子内边宽的比例；圆片、辅助线起点与挡路提示都按它对齐。
_CHIP_RADIUS_RATIO: Final[float] = 0.44

# 箭头贴图的缓存上限：格子尺寸（跟着窗口缩放）+ 主题色 + 状态 + 朝向，条目有限。
_ARROW_SPRITE_CACHE: Final[int] = 192

_EMPTY_CELL: Final[str] = "."

# 抖动、脉冲等周期动画统一使用的整圈弧度。
_TWO_PI: Final[float] = math.tau


@dataclass(frozen=True, slots=True)
class Arrow:
    """棋盘上的单个箭头。"""

    row: int
    col: int
    direction: Direction


@dataclass(slots=True)
class FlyingArrow:
    """已经离开网格、正在飞出棋盘可视区域的箭头。

    箭头在进入飞行的瞬间就已经从网格中移除，因此不再阻挡任何箭头，
    也点不到；这里保存的只是绘制飞出动画所需的像素坐标数据。
    """

    arrow: Arrow
    """被清除的箭头。"""
    origin: tuple[float, float]
    """飞行起点，即箭头原所在格子的中心像素坐标。"""
    distance: float
    """需要飞行的总像素距离，取“刚好完全离开棋盘可见区域”的距离。"""
    elapsed: float = 0.0
    """已经飞行的时间（秒）。"""

    @property
    def progress(self) -> float:
        """0.0 ~ 1.0 的飞行进度，已按 ``config.FLY_OUT_EASE_POWER`` 缓动。"""
        duration = max(config.FLY_OUT_SECONDS, 1e-6)
        linear = min(1.0, self.elapsed / duration)
        return linear**config.FLY_OUT_EASE_POWER

    @property
    def position(self) -> tuple[float, float]:
        """箭头当前的中心像素坐标。"""
        unit_x, unit_y = self.arrow.direction.vector
        travelled = self.distance * self.progress
        return (
            self.origin[0] + unit_x * travelled,
            self.origin[1] + unit_y * travelled,
        )

    @property
    def finished(self) -> bool:
        """飞行是否已经结束（箭头已完全飞出可见区域）。"""
        return self.elapsed >= config.FLY_OUT_SECONDS


@dataclass(frozen=True, slots=True)
class GuideLine:
    """一条辅助线：沿某个箭头的前进方向画出的一段路径提示。

    它只描述“从哪儿画到哪儿”，不参与任何判定：``blocker`` 为空表示前方畅通、
    ``end`` 落在棋盘边缘；否则 ``end`` 落在挡路箭头圆片的外沿，再往前就是撞上的地方。
    """

    arrow: Arrow
    """这条辅助线属于哪个箭头。"""
    start: tuple[float, float]
    """起点：箭头自己圆片外沿上、朝前进方向的那一点。"""
    end: tuple[float, float]
    """终点：棋盘边缘（畅通）或挡路箭头的外沿（被挡）。"""
    blocker: Arrow | None
    """挡在前进方向上的箭头，畅通时为 ``None``。"""

    @property
    def blocked(self) -> bool:
        """这条辅助线是否停在另一个箭头上（也就是这一箭当前点不动）。"""
        return self.blocker is not None


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
        self._layout(area)
        self.selected: Arrow | None = None
        self._blocked_flash: Arrow | None = None
        self._flash_remaining: float = 0.0
        self._flying: list[FlyingArrow] = []
        self._elapsed: float = 0.0

    def _layout(self, area: pygame.Rect) -> None:
        """按可用区域重算格子尺寸与棋盘位置（棋盘在 ``area`` 里居中）。

        格子尺寸受两个上限约束：``area`` 能放下多少，以及设计尺寸下的
        ``config.MAX_CELL_SIZE``。后一个上限跟着视口放大，所以窗口变大时格子确实
        会变大，不会“窗口变大了、棋盘还是原来那么大”。
        """
        self.cell_size: int = min(
            area.width // self.cols,
            area.height // self.rows,
            viewport.s(config.MAX_CELL_SIZE),
        )
        self.rect: pygame.Rect = pygame.Rect(
            0,
            0,
            self.cols * self.cell_size,
            self.rows * self.cell_size,
        )
        self.rect.center = area.center

    def reshape(self, area: pygame.Rect) -> None:
        """按新的可用区域重新摆放棋盘（窗口尺寸变化时由 ``Session.resize`` 调用）。

        只重算格子尺寸与位置，**不改动任何规则状态**：箭头布局、选中、碰撞提示与
        计时都保持原样，因此拖拽窗口不会打断玩家正在解的这一关。飞出动画保存的是
        像素坐标，缩放后不再成立，直接放弃（它只持续 0.32 秒，看不出中断）。
        """
        self._layout(area)
        self._flying.clear()

    @property
    def panel_rect(self) -> pygame.Rect:
        """棋盘底板的屏幕区域（格子外再留一圈间隙）。"""
        gap = viewport.s(config.CELL_GAP)
        return self.rect.inflate(2 * gap, 2 * gap)

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

    @property
    def flying(self) -> list[FlyingArrow]:
        """当前正在播放飞出动画的箭头（已经不在网格上）。"""
        return list(self._flying)

    @property
    def flash_progress(self) -> float:
        """碰撞提示的播放进度，0.0 表示刚开始、1.0 表示已结束。"""
        if self._blocked_flash is None:
            return 1.0
        return 1.0 - self._flash_remaining / config.BLOCKED_FLASH_SECONDS

    @property
    def shake_offset(self) -> tuple[float, float]:
        """碰撞提示造成的抖动位移（像素），没有提示时为零向量。

        位移由两部分叠加：沿箭头方向“撞出去再弹回来”的阻尼振荡，
        以及垂直于该方向的轻微晃动，两者都随提示进度衰减到 0。
        """
        if self._blocked_flash is None:
            return (0.0, 0.0)

        cell = self.cell_rect(self._blocked_flash.row, self._blocked_flash.col)
        unit_x, unit_y = self._blocked_flash.direction.vector
        progress = self.flash_progress
        # 振幅随进度衰减，保证抖动结束时箭头精确回到原位。
        amplitude = cell.width * config.BLOCKED_SHAKE_RATIO * (1.0 - progress) ** 2
        phase = _TWO_PI * config.BLOCKED_SHAKE_CYCLES * progress
        along = math.sin(phase)
        side = 0.4 * math.sin(2.0 * phase)
        return (
            (unit_x * along - unit_y * side) * amplitude,
            (unit_y * along + unit_x * side) * amplitude,
        )

    @property
    def blocker_hint(self) -> Arrow | None:
        """当前碰撞提示中挡在前进方向上的箭头，没有提示时返回 ``None``。

        阻挡者在提示期间可能已经被清掉，此时立即返回 ``None``，提示自动消失。
        """
        if self._blocked_flash is None:
            return None
        return self.blocking_arrow(self._blocked_flash)

    def cell_rect(self, row: int, col: int) -> pygame.Rect:
        """返回某个格子在屏幕上的矩形区域（已扣除格子间隙）。"""
        gap = viewport.s(config.CELL_GAP)
        inner_size = self.cell_size - 2 * gap
        return pygame.Rect(
            self.rect.left + col * self.cell_size + gap,
            self.rect.top + row * self.cell_size + gap,
            inner_size,
            inner_size,
        )

    def arrow_color(self, arrow: Arrow) -> config.Color:
        """返回 ``arrow`` 的主题色（与它所在格子绑定，整关不变）。"""
        return palette.theme_color(arrow.row, arrow.col)

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

    def guide_line(self, arrow: Arrow) -> GuideLine:
        """返回 ``arrow`` 的辅助线：沿它当前的前进方向画到“这一箭会停在哪”。

        终点有两种，正好对应 :meth:`handle_click` 的两种结果：

        - **前方畅通**：终点落在棋盘可见区域的边缘，也就是它飞出棋盘的那条边；
        - **前方被挡**：终点落在第一个挡路箭头圆片的外沿，线到此为止。

        几何全部由 :meth:`cell_rect` 与 :meth:`blocking_arrow` 推出来，因此辅助线
        与绘制、点击判定读的是同一份坐标；线本身只是视觉提示，不改变任何状态。
        """
        cell = self.cell_rect(arrow.row, arrow.col)
        radius = cell.width * _CHIP_RADIUS_RATIO
        margin = viewport.s(config.GUIDE_LINE_MARGIN)
        unit_x, unit_y = arrow.direction.vector
        center = (float(cell.centerx), float(cell.centery))
        start = _point_towards(
            center,
            (center[0] + unit_x, center[1] + unit_y),
            radius + margin,
        )

        blocker = self.blocking_arrow(arrow)
        if blocker is not None:
            target = self.cell_rect(blocker.row, blocker.col)
            end = _point_towards(target.center, center, radius + margin)
            return GuideLine(arrow, start, end, blocker)

        panel = self.panel_rect
        if unit_x > 0:
            distance = panel.right - center[0]
        elif unit_x < 0:
            distance = center[0] - panel.left
        elif unit_y > 0:
            distance = panel.bottom - center[1]
        else:
            distance = center[1] - panel.top
        end = (center[0] + unit_x * distance, center[1] + unit_y * distance)
        return GuideLine(arrow, start, end, None)

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

        前方畅通时会立即从网格移除该箭头（因此后续点击的阻挡判定全部按
        “已经移除”计算），同时为它排入一段飞出棋盘的动画。

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
        self._start_fly_out(arrow)
        return ClickResult.CLEARED

    def update(self, dt: float) -> None:
        """推进棋盘上的动画状态，``dt`` 为上一帧耗时（秒）。"""
        self._elapsed += dt
        self._update_flying(dt)

        if self._blocked_flash is None:
            return
        self._flash_remaining = max(0.0, self._flash_remaining - dt)
        if self._flash_remaining == 0.0:
            self._clear_flash()

    def _update_flying(self, dt: float) -> None:
        """推进所有飞出动画，并丢弃已经飞出可见区域的箭头。"""
        for flying in self._flying:
            flying.elapsed += dt
        self._flying = [flying for flying in self._flying if not flying.finished]

    def _start_fly_out(self, arrow: Arrow) -> None:
        """为刚被清除的 ``arrow`` 排入一段飞出动画。"""
        cell = self.cell_rect(arrow.row, arrow.col)
        self._flying.append(
            FlyingArrow(
                arrow=arrow,
                origin=(float(cell.centerx), float(cell.centery)),
                distance=self._fly_out_distance(arrow, cell),
            )
        )

    def _fly_out_distance(self, arrow: Arrow, cell: pygame.Rect) -> float:
        """计算箭头从 ``cell`` 起步、完全飞出棋盘可见区域所需的像素距离。"""
        panel = self.panel_rect
        unit_x, unit_y = arrow.direction.vector
        if unit_x > 0:
            return panel.right + cell.width - cell.centerx
        if unit_x < 0:
            return cell.centerx - (panel.left - cell.width)
        if unit_y > 0:
            return panel.bottom + cell.width - cell.centery
        return cell.centery - (panel.top - cell.width)

    def _start_flash(self, arrow: Arrow) -> None:
        """开始（或重新开始）对 ``arrow`` 的碰撞提示。"""
        self._blocked_flash = arrow
        self._flash_remaining = config.BLOCKED_FLASH_SECONDS

    def _clear_flash(self) -> None:
        """结束当前的碰撞提示。"""
        self._blocked_flash = None
        self._flash_remaining = 0.0

    def draw(
        self,
        surface: pygame.Surface,
        mouse: tuple[int, int] | None = None,
        *,
        show_guides: bool = False,
    ) -> None:
        """把棋盘底板、格子、箭头与飞出动画绘制到 ``surface`` 上。

        绘制顺序为：面板 → 格子 → 辅助线 → “被谁挡住”的提示 → 棋盘上的箭头 →
        飞行中的箭头，因此飞出动画始终显示在最上层，不会被面板或格子遮挡，
        辅助线则压在箭头下面（线穿过别的格子时不会盖住那些箭头）。

        Args:
            surface: 绘制目标。
            mouse: 鼠标位置。辅助线打开时，悬停的箭头会画得更亮；为 ``None`` 时
                所有线一视同仁。
            show_guides: 辅助线开关（右下角开关 / ``G`` 键），默认关闭。
                关着时**一条线都不画**，打开后所有箭头各画一条。
        """
        panel = self.panel_rect
        sprites.blit_round_rect(
            surface, panel, viewport.s(config.BOARD_RADIUS), config.COLOR_BOARD
        )
        # 底板描边：向外侧收的圆角描边同样走超采样贴图，四角不再是阶梯。
        sprites.blit_round_rect(
            surface,
            panel,
            viewport.s(config.BOARD_RADIUS),
            config.COLOR_BOARD_BORDER,
            viewport.s(2),
        )

        # 所有格子共用同一张圆角贴图（尺寸与配色都一样），每帧只是重复 blit。
        cell_radius = viewport.s(config.CELL_RADIUS)
        for row in range(self.rows):
            for col in range(self.cols):
                sprites.blit_round_rect(
                    surface, self.cell_rect(row, col), cell_radius, config.COLOR_CELL
                )

        self._draw_guides(surface, mouse, show_guides)
        self._draw_blocker_hint(surface)

        for arrow in self:
            self._draw_arrow(surface, arrow)

        for flying in self._flying:
            self._draw_flying_arrow(surface, flying)

    def _draw_arrow(self, surface: pygame.Surface, arrow: Arrow) -> None:
        """绘制棋盘上的单个箭头。

        - 圆片（底色 + 描边）与箭头图形是**一张缓存贴图**，见 :func:`_arrow_sprite`；
        - 被选中的箭头向白色提亮，并带一圈呼吸式中性描边；
        - 刚刚撞到其他箭头的箭头染向警示色，整体沿前进方向抖动，
          外圈是向外扩散的红环，前方另有三道火花线。

        只有随动画每帧变化的部分（选中环 / 碰撞环 / 火花）才现画，其余部分稳定状态
        下每帧只是一次 ``blit``。
        """
        cell = self.cell_rect(arrow.row, arrow.col)
        is_selected = arrow == self.selected
        is_blocked = arrow == self._blocked_flash
        theme = self.arrow_color(arrow)
        radius = cell.width * _CHIP_RADIUS_RATIO

        sprite = _arrow_sprite(
            cell.width,
            arrow.direction,
            palette.chip_color(theme, selected=is_selected, blocked=is_blocked),
            palette.chip_border_color(theme, selected=is_selected, blocked=is_blocked),
            palette.glyph_color(theme, selected=is_selected, blocked=is_blocked),
            viewport.s(2),
        )
        offset_x, offset_y = self.shake_offset if is_blocked else (0.0, 0.0)
        center = (cell.centerx + offset_x, cell.centery + offset_y)
        surface.blit(
            sprite, sprite.get_rect(center=(round(center[0]), round(center[1])))
        )

        if is_blocked:
            sprites.blit_circle(
                surface,
                center,
                radius * (1.0 + 0.35 * self.flash_progress),
                config.COLOR_BLOCKED_RING,
                viewport.s(3),
            )
        elif is_selected:
            pulse = math.sin(_TWO_PI * self._elapsed / config.SELECTION_PULSE_SECONDS)
            scale = config.SELECTION_RING_SCALE + config.SELECTION_PULSE_RATIO * pulse
            sprites.blit_circle(
                surface,
                center,
                radius * scale,
                config.COLOR_SELECTION_RING,
                viewport.s(3),
            )

        if is_blocked:
            _draw_impact_sparks(
                surface, center, cell.width, arrow.direction, self.flash_progress
            )

    def _draw_guides(
        self,
        surface: pygame.Surface,
        mouse: tuple[int, int] | None,
        show_guides: bool,
    ) -> None:
        """绘制辅助线：关着时一条都不画，打开后其余箭头淡一档、悬停那条最醒目。

        悬停的箭头由 ``mouse`` 现算（:meth:`hit_test`），所以点掉一个箭头之后，
        辅助线会立刻跟着消失，不需要另外维护“谁被指着”的状态。
        """
        if not show_guides:
            return
        hovered = self.hit_test(mouse) if mouse is not None else None
        for arrow in self:
            if arrow != hovered:
                self._draw_guide(surface, self.guide_line(arrow), dim=True)
        if hovered is not None:
            self._draw_guide(surface, self.guide_line(hovered), dim=False)

    def _draw_guide(
        self, surface: pygame.Surface, line: GuideLine, *, dim: bool
    ) -> None:
        """绘制一条辅助线：虚线 + 终点标记。

        颜色只有两种：畅通用绿色、被挡用红色；``dim`` 是“全部显示”里的淡色版。
        长度不足一个虚线段时直接跳过，免得在贴边的短线上堆出一个小墨点。
        """
        if math.dist(line.start, line.end) < viewport.s(config.GUIDE_LINE_DASH):
            return
        color = (
            config.GUIDE_LINE_COLOR_BLOCKED
            if line.blocked
            else config.GUIDE_LINE_COLOR_CLEAR
        )
        if dim:
            color = palette.mix(color, config.COLOR_CELL, config.GUIDE_LINE_DIM_MIX)
        _draw_dashed_line(
            surface,
            line.start,
            line.end,
            color,
            dash=config.GUIDE_LINE_DASH,
            gap=config.GUIDE_LINE_GAP,
            width=config.GUIDE_LINE_WIDTH,
        )
        _draw_guide_cap(surface, line, color)

    def _draw_flying_arrow(self, surface: pygame.Surface, flying: FlyingArrow) -> None:
        """绘制飞出动画：位置由 :class:`FlyingArrow` 给出，越接近飞出越透明。

        画的还是 :func:`_arrow_sprite` 那张贴图（常态配色），只是每帧复制一份调低
        整体透明度——缓存贴图不能就地改，否则会把棋盘上的箭头一起改透明。
        """
        size = self.cell_size - 2 * viewport.s(config.CELL_GAP)
        theme = self.arrow_color(flying.arrow)
        sprite = _arrow_sprite(
            size,
            flying.arrow.direction,
            palette.chip_color(theme),
            palette.chip_border_color(theme),
            palette.glyph_color(theme),
            viewport.s(2),
        )

        # 尾段快速淡出：前 60% 的行程几乎不透明，最后 40% 渐隐到全透明。
        layer = sprite.copy()
        layer.set_alpha(round(255 * (1.0 - flying.progress**3)))
        position = (round(flying.position[0]), round(flying.position[1]))
        surface.blit(layer, layer.get_rect(center=position))

    def _draw_blocker_hint(self, surface: pygame.Surface) -> None:
        """绘制“被谁挡住”的提示：指向阻挡者的虚线，以及阻挡者外圈的高亮环。

        提示颜色由棋盘格底色随提示进度渐变到 ``COLOR_BLOCKER_HINT``，
        因此提示开始时最醒目，之后自然淡回背景，不需要额外的透明通道。
        """
        blocked = self._blocked_flash
        if blocked is None:
            return
        blocker = self.blocking_arrow(blocked)
        if blocker is None:
            return

        color = palette.mix(
            config.COLOR_CELL, config.COLOR_BLOCKER_HINT, 1.0 - self.flash_progress
        )
        cell = self.cell_rect(blocked.row, blocked.col)
        target = self.cell_rect(blocker.row, blocker.col)
        radius = cell.width * _CHIP_RADIUS_RATIO
        near = viewport.s(4.0)
        far = viewport.s(6.0)

        _draw_dashed_line(
            surface,
            _point_towards(cell.center, target.center, radius + near),
            _point_towards(target.center, cell.center, radius + far),
            color,
            smooth=True,
        )
        sprites.blit_circle(surface, target.center, radius + near, color, viewport.s(3))


@functools.lru_cache(maxsize=_ARROW_SPRITE_CACHE)
def _arrow_sprite(
    cell_size: int,
    direction: Direction,
    chip: config.Color,
    border: config.Color,
    glyph: config.Color,
    border_width: int,
) -> pygame.Surface:
    """返回一个箭头的抗锯齿贴图：圆片底色 + 圆片描边 + 箭头图形。

    这三件东西在棋盘上会反复出现（同一尺寸 + 同一主题色 + 同一状态 + 同一朝向的
    箭头长得完全一样），因此按绘制参数缓存；而选中环、碰撞环与火花每帧都在动，
    不在这里画。贴图是**共享的缓存对象**，需要改透明度（飞出动画）就自己复制一份。
    """
    radius = round(cell_size * _CHIP_RADIUS_RATIO)
    span = 2 * radius + 3

    def paint(canvas: pygame.Surface, factor: int) -> None:
        center = (canvas.get_width() / 2, canvas.get_height() / 2)
        pygame.draw.circle(canvas, chip, center, radius * factor)
        pygame.draw.circle(
            canvas, border, center, radius * factor, width=border_width * factor
        )
        pygame.draw.polygon(
            canvas, glyph, _arrow_points(center, cell_size * factor, direction)
        )

    return sprites.render((span, span), paint)


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
    center: tuple[float, float],
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


def _draw_impact_sparks(
    surface: pygame.Surface,
    center: tuple[float, float],
    cell_size: int,
    direction: Direction,
    progress: float,
) -> None:
    """在被阻挡箭头的前方画出三道向外扩散的火花线。

    火花长度与偏移都随 ``progress``（0.0 → 1.0）收缩到贴住箭头边缘，
    与碰撞提示同时结束，不需要单独的状态。三道火花都是斜线，因此用抗锯齿的折线画。
    """
    envelope = 1.0 - progress
    if envelope <= 0.0:
        return

    unit_x, unit_y = direction.vector
    base_angle = math.atan2(unit_y, unit_x)
    radius = cell_size * _CHIP_RADIUS_RATIO
    width = viewport.s(2)
    for offset_angle in (-0.5, 0.0, 0.5):
        angle = base_angle + offset_angle
        cos_angle, sin_angle = math.cos(angle), math.sin(angle)
        inner = radius * 1.02
        outer = inner + cell_size * (0.06 + 0.14 * envelope)
        pygame.draw.aaline(
            surface,
            config.COLOR_BLOCKED_SPARK,
            (center[0] + cos_angle * inner, center[1] + sin_angle * inner),
            (center[0] + cos_angle * outer, center[1] + sin_angle * outer),
            width,
        )


def _draw_guide_cap(
    surface: pygame.Surface,
    line: GuideLine,
    color: config.Color,
) -> None:
    """在辅助线的终点画一个方向标记。

    畅通时是一个越过棋盘边缘、指向线外的小箭头（“这一箭从这里飞出去”）；
    被挡住时是一段垂直于前进方向的短横杠（“到此为止，前面有东西”）。
    标记的朝向完全由箭头的方向决定，所以辅助线本身就说明了“往哪走”。

    两个张开的箭羽是斜线，用抗锯齿折线画；被挡时的横杠与前进方向垂直、
    因此总是水平或垂直的，直接画就好（轴对齐的线本来就没有锯齿）。
    """
    unit_x, unit_y = line.arrow.direction.vector
    perpendicular_x, perpendicular_y = -unit_y, unit_x
    end_x, end_y = line.end
    width = viewport.s(config.GUIDE_LINE_WIDTH)

    if line.blocked:
        half = viewport.s(config.GUIDE_LINE_CAP) / 2.0
        pygame.draw.line(
            surface,
            color,
            (end_x - perpendicular_x * half, end_y - perpendicular_y * half),
            (end_x + perpendicular_x * half, end_y + perpendicular_y * half),
            width=width + 1,
        )
        return

    head = viewport.s(config.GUIDE_LINE_HEAD)
    tip = (end_x + unit_x * head, end_y + unit_y * head)
    for sign in (1.0, -1.0):
        barb = (
            tip[0] - unit_x * head + perpendicular_x * head * 0.55 * sign,
            tip[1] - unit_y * head + perpendicular_y * head * 0.55 * sign,
        )
        pygame.draw.aaline(surface, color, tip, barb, width)


def _draw_dashed_line(
    surface: pygame.Surface,
    start: tuple[float, float],
    end: tuple[float, float],
    color: config.Color,
    dash: float | None = None,
    gap: float | None = None,
    width: int | None = None,
    *,
    smooth: bool = False,
) -> None:
    """在两点之间画一条虚线（纯几何实现，不依赖字体）。

    ``start`` / ``end`` 是屏幕坐标；``dash`` / ``gap`` / ``width`` 是**设计长度**，
    省略时取 ``config`` 里的值，二者都在这里按当前视口换算。

    ``smooth`` 为真时每一段用抗锯齿折线画。辅助线**不开**这一档：它们是轴对齐的
    细线（水平 / 垂直的线本来就没有锯齿），保持硬边反而更利落，也让测试能按精确
    颜色数像素；斜向的“被谁挡住”提示线则用得上抗锯齿。
    """
    dash = viewport.s(config.GUIDE_LINE_DASH if dash is None else dash)
    gap = viewport.s(config.GUIDE_LINE_GAP if gap is None else gap)
    width = viewport.s(config.GUIDE_LINE_WIDTH if width is None else width)
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    length = math.hypot(delta_x, delta_y)
    if length <= 0.0:
        return

    unit_x, unit_y = delta_x / length, delta_y / length
    step = dash + gap
    travelled = 0.0
    while travelled < length:
        segment_end = min(travelled + dash, length)
        segment_start = (start[0] + unit_x * travelled, start[1] + unit_y * travelled)
        segment_stop = (
            start[0] + unit_x * segment_end,
            start[1] + unit_y * segment_end,
        )
        if smooth:
            pygame.draw.aaline(surface, color, segment_start, segment_stop, width)
        else:
            pygame.draw.line(surface, color, segment_start, segment_stop, width=width)
        travelled += step


def _point_towards(
    start: tuple[float, float],
    end: tuple[float, float],
    distance: float,
) -> tuple[float, float]:
    """返回从 ``start`` 朝 ``end`` 前进 ``distance`` 像素后的坐标。"""
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    length = math.hypot(delta_x, delta_y)
    if length <= 0.0:
        return start

    ratio = distance / length
    return (start[0] + delta_x * ratio, start[1] + delta_y * ratio)
