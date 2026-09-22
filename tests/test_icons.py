"""图标绘制测试：每个图标都要真的画出东西、不越界，并且彼此不同。"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, icons

SURFACE_SIZE = 64
BACKGROUND = (0, 0, 0)
COLOR = config.COLOR_TEXT
# 描边会从图形中心向两侧各溢出半个线宽，因此允许图标超出外接框一点点。
BOX_TOLERANCE = 2


def _render(icon: icons.Icon, size: int = 24) -> pygame.Surface:
    """把图标画在纯黑画布中央，返回画布。"""
    surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
    surface.fill(BACKGROUND)
    icons.draw_icon(surface, icon, (SURFACE_SIZE // 2, SURFACE_SIZE // 2), size, COLOR)
    return surface


def _painted_pixels(surface: pygame.Surface) -> int:
    """统计被画过的像素数量。"""
    return sum(
        1
        for x in range(surface.get_width())
        for y in range(surface.get_height())
        if surface.get_at((x, y))[:3] != BACKGROUND
    )


def _painted_colors(surface: pygame.Surface) -> set[config.Color]:
    """收集被画过的像素颜色。"""
    return {
        (int(pixel[0]), int(pixel[1]), int(pixel[2]))
        for x in range(surface.get_width())
        for y in range(surface.get_height())
        if (pixel := surface.get_at((x, y)))[:3] != BACKGROUND
    }


def _is_a_blend_of_the_color(pixel: config.Color) -> bool:
    """判断像素是不是“背景色 → 图标色”之间的一档过渡色。

    图标走的是超采样贴图，边缘像素是图形色与背景色按覆盖率混合出来的，因此各个
    通道的比例（相对图标色）必须一致；用比例而不是具体色值来判定，将来换配色或
    换画布底色都不必改这里。
    """
    ratios = [pixel[index] / COLOR[index] for index in range(3) if COLOR[index] > 0]
    return max(ratios) - min(ratios) <= 0.05


@pytest.mark.parametrize("icon", list(icons.Icon))
def test_every_icon_paints_something(icon: icons.Icon) -> None:
    assert _painted_pixels(_render(icon)) > 0


@pytest.mark.parametrize("icon", list(icons.Icon))
def test_every_icon_uses_the_requested_color(icon: icons.Icon) -> None:
    """图标要么用请求的颜色画（图形内部），要么是它与底色的过渡色（抗锯齿边缘）。"""
    colors = _painted_colors(_render(icon))

    assert COLOR in colors, "图形内部应当正好是请求的颜色"
    unexpected = sorted(
        color for color in colors if not _is_a_blend_of_the_color(color)
    )
    assert unexpected == [], "只允许出现“图标色 → 背景色”之间的过渡色"


@pytest.mark.parametrize("icon", list(icons.Icon))
def test_every_icon_is_anti_aliased(icon: icons.Icon) -> None:
    """图标是超采样贴图，边缘因此要有过渡色。

    只有“图标色 + 背景色”两种颜色说明又画回了硬边（`pygame.draw` 的默认效果），
    这正是本轮要修的那个问题，因此这里把它钉住。
    """
    assert len(_painted_colors(_render(icon, size=32))) > 2


@pytest.mark.parametrize("icon", list(icons.Icon))
def test_every_icon_stays_inside_its_box(icon: icons.Icon) -> None:
    size = 24
    surface = _render(icon, size=size)
    margin = (SURFACE_SIZE - size) // 2 - BOX_TOLERANCE

    for x in range(SURFACE_SIZE):
        for y in range(SURFACE_SIZE):
            if (
                margin <= x < SURFACE_SIZE - margin
                and margin <= y < SURFACE_SIZE - margin
            ):
                continue
            assert surface.get_at((x, y))[:3] == BACKGROUND, f"{icon} 画到了图标框之外"


@pytest.mark.parametrize("icon", list(icons.Icon))
def test_icons_scale_with_their_size(icon: icons.Icon) -> None:
    small = _painted_pixels(_render(icon, size=16))
    large = _painted_pixels(_render(icon, size=32))
    assert large > small


def test_icons_are_visually_distinct() -> None:
    images = {icon: pygame.image.tobytes(_render(icon), "RGB") for icon in icons.Icon}
    assert len(set(images.values())) == len(images), "不同图标不应该画出同一张图"
