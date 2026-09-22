"""抗锯齿贴图：矢量图形先在超采样画布上画，再平滑缩小。

``pygame.draw`` 画出来的圆、圆角矩形、多边形都是**硬边**的：一块画布上只会有“填充色”
与“底色”两种颜色，斜边与圆弧因此是台阶状的（实测见
``docs/agents/explore-12-window-resize-and-crispness.md``：一个 4× 放大的圆片描边、
箭头斜边都能直接看出锯齿）。项目里**没有位图素材**（``assets/`` 只有字体），所以
“素材低分辨率”真正指的就是这件事——窗口越大、格子越大，台阶越显眼。

这里的做法与 :func:`another_arrow_rt265.ui._glow_sprite` 一致：把图形先画在
``SUPERSAMPLE`` 倍的画布上（一个像素被摊成 4×4 个子像素），再用 ``smoothscale``
缩回目标尺寸，边缘便按覆盖率得到过渡色。贴图按绘制参数缓存，因此稳定状态下每帧只多一次
``blit``，比每帧现画一组带锯齿的图形还省。

约定：

- 这里进出的所有长度都是**屏幕像素**；设计尺寸下的长度请在调用方先用
  :func:`another_arrow_rt265.viewport.s` 换算（与 ``ui`` / ``board`` 的约定一致）；
- :func:`circle` / :func:`round_rect` 返回的是**共享的缓存对象**，调用方不要修改它
  （需要改整体透明度就先 ``.copy()`` 再 :meth:`pygame.Surface.set_alpha`）；
- 贴图很大时自动降一档超采样倍数（见 :data:`MAX_CANVAS_PIXELS`），既能保证小图形
  （图标、箭头圆片）拿到最好的效果，也不会为整屏面板分配上百 MB 的画布。
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Final

import pygame

#: 贴图颜色：允许带透明度（第 4 个分量），这样半透明的环也能走同一套缓存。
Color = tuple[int, int, int] | tuple[int, int, int, int]

#: 超采样倍数：边缘的一个像素被摊成 4×4 个子像素，缩放时按覆盖率得到过渡色。
SUPERSAMPLE: Final[int] = 4
#: 单张贴图的超采样画布像素上限。超采样代价按面积走：4× 的 900×700 面板要 4000 万
#: 个子像素（约 160MB 画布），而这块面板的斜边与圆角本来就长、2× 已经看不出台阶，
#: 所以超过上限就降一档倍数——小图形（图标 20px、圆片 100px）永远拿得到 4×。
MAX_CANVAS_PIXELS: Final[int] = 4_000_000
#: 贴图缓存的条目上限。键是“尺寸 + 颜色 + 线宽”这样的绘制参数：棋子尺寸跟着窗口
#: 缩放（量化到 1/16 档）+ 6 种主题色 + 3 种状态 + 4 个方向，实际用到的条目有限。
CACHE_SIZE: Final[int] = 192


def _supersample_factor(size: tuple[int, int], supersample: int) -> int:
    """返回这张贴图实际使用的超采样倍数（按面积降档，见 :data:`MAX_CANVAS_PIXELS`）。"""
    pixels = max(1, size[0]) * max(1, size[1])
    factor = max(1, int(supersample))
    while factor > 1 and pixels * factor * factor > MAX_CANVAS_PIXELS:
        factor -= 1
    return factor


def render(
    size: tuple[float, float],
    painter: Callable[[pygame.Surface, int], None],
    *,
    supersample: int = SUPERSAMPLE,
) -> pygame.Surface:
    """把 ``painter`` 画的图形变成一张 ``size`` 大小、带透明通道的抗锯齿贴图。

    Args:
        size: 目标尺寸（像素）。
        painter: ``painter(canvas, factor)``，在 ``factor`` 倍的画布上画图形；
            画布是一个带透明通道、边长为 ``size * factor`` 的新表面，图形要按
            ``factor`` 等比放大画上去（线宽、半径都要乘 ``factor``）。
        supersample: 期望的超采样倍数，很大时会按面积自动降档。

    Returns:
        一张 ``size`` 大小的新表面；缩放后边缘带过渡色，图形之外的像素透明。
    """
    width = max(1, round(size[0]))
    height = max(1, round(size[1]))
    factor = _supersample_factor((width, height), supersample)
    canvas = pygame.Surface((width * factor, height * factor), pygame.SRCALPHA)
    painter(canvas, factor)
    if factor == 1:
        return canvas
    return pygame.transform.smoothscale(canvas, (width, height))


def _span(radius: int) -> int:
    """返回半径 ``radius`` 的圆形贴图的边长（奇数，圆心落在正中间）。"""
    return 2 * max(1, radius) + 3


@functools.lru_cache(maxsize=CACHE_SIZE)
def circle(radius: int, color: Color, width: int = 0) -> pygame.Surface:
    """返回一张圆形贴图（``width`` > 0 时是圆环），边长 ``2 * radius + 3``。

    描边像 ``pygame.draw.circle`` 一样向圆心方向收，因此外沿始终是 ``radius``，
    贴图尺寸与 :func:`blit_circle` 的定位可以放心对齐。
    """
    radius = max(1, radius)
    stroke = max(0, width)
    span = _span(radius)

    def paint(canvas: pygame.Surface, factor: int) -> None:
        pygame.draw.circle(
            canvas,
            color,
            (canvas.get_width() / 2, canvas.get_height() / 2),
            radius * factor,
            width=stroke * factor,
        )

    return render((span, span), paint)


def blit_circle(
    surface: pygame.Surface,
    center: tuple[float, float],
    radius: float,
    color: Color,
    width: float = 0,
) -> None:
    """在 ``center`` 处画一个抗锯齿的圆（``width`` > 0 时是圆环）。

    ``center`` 允许是动画算出来的浮点坐标，这里取整到像素后再落笔；半径与线宽
    也一样先取整，免得浮点参数把缓存撑成无穷多份。
    """
    sprite = circle(round(radius), color, round(width))
    surface.blit(sprite, sprite.get_rect(center=(round(center[0]), round(center[1]))))


@functools.lru_cache(maxsize=CACHE_SIZE)
def round_rect(
    size: tuple[int, int],
    radius: int,
    color: Color,
    width: int = 0,
) -> pygame.Surface:
    """返回一张圆角矩形贴图（``width`` > 0 时是圆角描边）。

    描边向矩形内部收，圆角半径会被夹到“短边的一半”以内（与 ``pygame.draw.rect``
    的 ``border_radius`` 一致）。
    """
    width_px = max(1, size[0])
    height_px = max(1, size[1])
    radius_px = max(0, min(radius, min(width_px, height_px) // 2))
    stroke = max(0, width)

    def paint(canvas: pygame.Surface, factor: int) -> None:
        pygame.draw.rect(
            canvas,
            color,
            canvas.get_rect(),
            width=stroke * factor,
            border_radius=radius_px * factor,
        )

    return render((width_px, height_px), paint)


def blit_round_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    radius: float,
    color: Color,
    width: float = 0,
) -> None:
    """在 ``rect`` 处画一个抗锯齿的圆角矩形（``width`` > 0 时是圆角描边）。"""
    sprite = round_rect((rect.width, rect.height), round(radius), color, round(width))
    surface.blit(sprite, rect.topleft)


@functools.lru_cache(maxsize=CACHE_SIZE)
def rounded_mask(size: tuple[int, int], radius: int) -> pygame.Surface:
    """返回一张“白色圆角矩形”蒙版，用来把别的贴图抠出抗锯齿的圆角。

    与 ``pygame.draw.rect(border_radius=...)`` 直接画的硬边蒙版相比，这里的四角
    带过渡色，配合 :data:`pygame.BLEND_RGBA_MULT` 抠出来的圆角不再是阶梯（见
    :func:`another_arrow_rt265.ui._gradient`）。
    """
    return round_rect(size, radius, (255, 255, 255, 255))
