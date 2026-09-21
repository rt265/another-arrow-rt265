"""界面图标的矢量绘制。

图标全部用几何图形现画，不引入字体或图片资源：这样既不必给打包配置增加
数据目录（``assets/`` 在包外，Nuitka 需要额外的 ``include-data-dir``），
也能在任意尺寸下保持清晰，线宽与颜色还可以直接跟着所在按钮走——按钮悬停、
主/次按钮配色变化时图标会一起变，不会出现“图标是位图、颜色对不上”的问题。

约定：每个图标都画在以 ``center`` 为中心、边长为 ``size`` 的正方形内，
内部坐标按 ``size`` 归一化，因此调用方只需要决定“图标画多大”。
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Final

import pygame

from another_arrow_rt265 import config

# 环形箭头的采样段数：段数越多弧越圆滑，24 段在按钮尺寸下已经看不出折线。
_ARC_STEPS: Final[int] = 24


class Icon(Enum):
    """界面上用到的图标。"""

    HOME = "home"
    """房子：回到主界面。"""

    RESTART = "restart"
    """环形箭头：重新开始本关。"""

    NEXT = "next"
    """右箭头：开始游戏 / 进入下一关。"""


def draw_icon(
    surface: pygame.Surface,
    icon: Icon,
    center: tuple[int, int],
    size: int,
    color: config.Color,
) -> None:
    """把 ``icon`` 以 ``center`` 为中心画到 ``surface`` 上，占据边长 ``size`` 的正方形。

    Args:
        surface: 绘制目标。
        icon: 要画的图标。
        center: 图标中心的像素坐标。
        size: 图标外接正方形的边长（像素），线宽会按它等比缩放。
        color: 图标颜色，通常取所在按钮的文字色。
    """
    if icon is Icon.HOME:
        _draw_home(surface, center, size, color)
    elif icon is Icon.RESTART:
        _draw_restart(surface, center, size, color)
    else:
        _draw_next(surface, center, size, color)


def _stroke_width(size: int) -> int:
    """线宽随图标尺寸轻微变化，小图标不至于糊成一团。"""
    return max(2, round(size * 0.11))


def _draw_home(
    surface: pygame.Surface, center: tuple[int, int], size: int, color: config.Color
) -> None:
    """房子：一个三角屋顶 + 屋身轮廓 + 一扇门。"""
    center_x, center_y = center
    half = size / 2.0
    stroke = _stroke_width(size)

    # 屋顶：左右两条斜线在正上方交于屋脊。
    pygame.draw.lines(
        surface,
        color,
        False,
        [
            (center_x - half, center_y - half * 0.05),
            (center_x, center_y - half * 0.95),
            (center_x + half, center_y - half * 0.05),
        ],
        width=stroke,
    )

    # 屋身：只画左右两条竖线和底边，顶边留给屋顶，避免出现双层横线。
    body_left = center_x - half * 0.72
    body_right = center_x + half * 0.72
    body_top = center_y - half * 0.05
    body_bottom = center_y + half * 0.95
    for x in (body_left, body_right):
        pygame.draw.line(surface, color, (x, body_top), (x, body_bottom), width=stroke)
    pygame.draw.line(
        surface,
        color,
        (body_left - stroke / 2.0, body_bottom),
        (body_right + stroke / 2.0, body_bottom),
        width=stroke,
    )

    # 门：坐在底边上的一扇小门，让房子不至于像一块空白方块。
    door_width = size * 0.26
    pygame.draw.rect(
        surface,
        color,
        pygame.Rect(
            round(center_x - door_width / 2.0),
            round(center_y + half * 0.24),
            round(door_width),
            round(body_bottom - (center_y + half * 0.24)),
        ),
        width=stroke,
    )


def _draw_restart(
    surface: pygame.Surface, center: tuple[int, int], size: int, color: config.Color
) -> None:
    """环形箭头：留一个缺口，并在弧的末端接上箭头（顺时针方向）。"""
    center_x, center_y = center
    stroke = _stroke_width(size)
    radius = size * 0.38
    start_angle = math.radians(-55.0)
    end_angle = math.radians(215.0)

    # 圆弧本身用折线采样：pygame.draw.arc 的角度约定与屏幕坐标相反，
    # 自己采样既能保证方向正确，也方便直接拿到端点接箭头。
    points: list[tuple[float, float]] = []
    for step in range(_ARC_STEPS + 1):
        angle = start_angle + (end_angle - start_angle) * step / _ARC_STEPS
        points.append(
            (center_x + math.cos(angle) * radius, center_y + math.sin(angle) * radius)
        )
    pygame.draw.lines(surface, color, False, points, width=stroke)

    # 箭头接在弧的末端，沿切线方向指出去（屏幕坐标下角度增大即顺时针）。
    tangent_x, tangent_y = -math.sin(end_angle), math.cos(end_angle)
    tip_x = points[-1][0] + tangent_x * size * 0.30
    tip_y = points[-1][1] + tangent_y * size * 0.30
    half_base = size * 0.24
    pygame.draw.polygon(
        surface,
        color,
        (
            (tip_x, tip_y),
            (
                points[-1][0] - tangent_y * half_base,
                points[-1][1] + tangent_x * half_base,
            ),
            (
                points[-1][0] + tangent_y * half_base,
                points[-1][1] - tangent_x * half_base,
            ),
        ),
    )


def _draw_next(
    surface: pygame.Surface, center: tuple[int, int], size: int, color: config.Color
) -> None:
    """右箭头：一根短杆 + 一个三角箭头，与开始界面上的装饰箭头同款。"""
    center_x, center_y = center
    half = size / 2.0
    stroke = _stroke_width(size)

    pygame.draw.line(
        surface,
        color,
        (center_x - half * 0.92, center_y),
        (center_x + half * 0.05, center_y),
        width=stroke,
    )
    pygame.draw.polygon(
        surface,
        color,
        (
            (center_x + half, center_y),
            (center_x - half * 0.05, center_y - half * 0.62),
            (center_x - half * 0.05, center_y + half * 0.62),
        ),
    )
