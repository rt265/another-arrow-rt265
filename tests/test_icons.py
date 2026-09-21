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


@pytest.mark.parametrize("icon", list(icons.Icon))
def test_every_icon_paints_something(icon: icons.Icon) -> None:
    assert _painted_pixels(_render(icon)) > 0


@pytest.mark.parametrize("icon", list(icons.Icon))
def test_every_icon_uses_the_requested_color(icon: icons.Icon) -> None:
    surface = _render(icon)
    colors = {
        surface.get_at((x, y))[:3]
        for x in range(SURFACE_SIZE)
        for y in range(SURFACE_SIZE)
        if surface.get_at((x, y))[:3] != BACKGROUND
    }
    assert colors == {COLOR}


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
