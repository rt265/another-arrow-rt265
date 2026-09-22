"""抗锯齿贴图（``sprites``）的测试。

这里测的是“边缘到底有没有过渡色”这件事本身：``pygame.draw`` 画出来的圆、
圆角矩形只会有“图形色 + 底色”两种颜色（硬边），而超采样贴图在斜边与圆角上
必然出现介于两者之间的像素。测试不看具体数值，只看颜色层级与几何位置，
因此换配色、改超采样倍数都不会误报。
"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, sprites

BACKGROUND = (0, 0, 0)
COLOR = (240, 240, 240)
SIZE = (48, 48)


def _canvas() -> pygame.Surface:
    surface = pygame.Surface(SIZE)
    surface.fill(BACKGROUND)
    return surface


def _pixel_at(surface: pygame.Surface, position: tuple[int, int]) -> config.Color:
    pixel = surface.get_at(position)
    return (int(pixel[0]), int(pixel[1]), int(pixel[2]))


def _colors(surface: pygame.Surface) -> set[config.Color]:
    return {
        _pixel_at(surface, (x, y))
        for x in range(surface.get_width())
        for y in range(surface.get_height())
        if _pixel_at(surface, (x, y)) != BACKGROUND
    }


def _fill(canvas: pygame.Surface, _factor: int) -> None:
    """把所有像素填成待测颜色（画布带透明通道，因此 alpha 要写满）。"""
    canvas.fill((*COLOR, 255))


def test_render_returns_a_surface_of_the_requested_size() -> None:
    sprite = sprites.render(SIZE, _fill)

    assert sprite.get_size() == SIZE
    assert sprite.get_flags() & pygame.SRCALPHA


def test_render_removes_the_stair_steps_of_a_rotated_square() -> None:
    """斜边是抗锯齿最直接的证据：硬边只有两种颜色，过渡色说明做了超采样。"""

    def painter(canvas: pygame.Surface, factor: int) -> None:
        pygame.draw.polygon(
            canvas,
            COLOR,
            [
                (2 * factor, 2 * factor),
                (SIZE[0] * factor - 2, 20 * factor),
                (2 * factor, 40 * factor),
            ],
        )

    hard = _canvas()
    painter(hard, 1)
    assert len(_colors(hard)) == 1, "对照组：直接画出来的斜边只有一种颜色"

    soft = _canvas()
    soft.blit(sprites.render(SIZE, painter), (0, 0))
    assert len(_colors(soft)) > 3, "斜边应当出现多档过渡色"


def test_circle_is_anti_aliased_and_keeps_a_solid_core() -> None:
    sprite = sprites.circle(12, COLOR)

    assert sprite.get_size() == (27, 27)
    assert sprite.get_at((13, 13))[:3] == COLOR, "圆心必须是实心色"
    assert sprite.get_at((0, 0))[3] == 0, "圆外的像素透明"

    surface = _canvas()
    surface.blit(sprite, (10, 10))
    assert len(_colors(surface)) > 3


def test_hollow_shapes_are_transparent_inside() -> None:
    """圆环与圆角描边只有一圈线，中间要透出底色（否则会盖住下面的内容）。"""
    surface = _canvas()
    surface.blit(sprites.circle(12, COLOR, 3), (10, 10))
    assert surface.get_at((23, 23))[:3] == BACKGROUND

    surface = _canvas()
    surface.blit(sprites.round_rect((40, 40), 12, COLOR, 3), (4, 4))
    assert surface.get_at((24, 24))[:3] == BACKGROUND


def test_round_rect_edges_are_anti_aliased() -> None:
    sprite = sprites.round_rect((40, 40), 14, COLOR)

    surface = _canvas()
    surface.blit(sprite, (4, 4))
    assert len(_colors(surface)) > 3, "圆角与斜边一样应当出现过渡色"

    # 圆角弧线上一定有“画到一半”的像素。
    partial = [
        alpha
        for x in range(8)
        for y in range(8)
        if 0 < (alpha := sprite.get_at((x, y))[3]) < 255
    ]
    assert partial, "圆角上应当有半透明的过渡像素"


def test_rounded_mask_has_a_transparent_corner_and_a_solid_middle() -> None:
    mask = sprites.rounded_mask((40, 40), 12)

    assert mask.get_at((20, 20))[:4] == (255, 255, 255, 255)
    assert mask.get_at((0, 0))[3] == 0
    assert any(
        0 < mask.get_at((x, y))[3] < 255 for x in range(12) for y in range(12)
    ), "圆角上应当有半透明的过渡"

    # 正是这张蒙版让 ``ui._gradient`` 的四角出现半透明像素。
    layer = pygame.Surface((40, 40), pygame.SRCALPHA)
    layer.fill((*config.COLOR_PANEL, 255))
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    assert layer.get_at((0, 0))[3] == 0
    assert layer.get_at((20, 20))[3] == 255


def test_sprites_are_cached_and_shared() -> None:
    """同样的参数只生成一张贴图：稳定状态下每帧只多一次 blit，而不是重画一遍。"""
    assert sprites.circle(9, COLOR) is sprites.circle(9, COLOR)
    assert sprites.circle(9, COLOR) is not sprites.circle(10, COLOR)
    assert sprites.round_rect((20, 20), 6, COLOR) is sprites.round_rect(
        (20, 20), 6, COLOR
    )


def test_cache_info_shows_the_callers_hit_the_cache() -> None:
    sprites.circle.cache_clear()
    for _ in range(5):
        sprites.blit_circle(_canvas(), (12, 12), 8, COLOR)

    info = sprites.circle.cache_info()
    assert info.misses == 1
    assert info.hits == 4


def test_blit_helpers_place_the_shape_at_the_center() -> None:
    surface = _canvas()
    sprites.blit_circle(surface, (20, 20), 6, COLOR)
    assert surface.get_at((20, 20))[:3] == COLOR

    surface = _canvas()
    sprites.blit_round_rect(surface, pygame.Rect(8, 8, 24, 24), 8, COLOR)
    assert surface.get_at((20, 20))[:3] == COLOR


def test_huge_sprites_use_a_smaller_supersample_factor() -> None:
    """整屏大的图形要降档：4 倍的画布会占上百 MB，得不偿失。"""
    small = sprites._supersample_factor((64, 64), sprites.SUPERSAMPLE)
    large = sprites._supersample_factor((1440, 900), sprites.SUPERSAMPLE)

    assert small == sprites.SUPERSAMPLE
    assert 1 <= large < sprites.SUPERSAMPLE


@pytest.mark.parametrize("size", [(64, 64), (600, 600)])
def test_a_degraded_factor_still_paints_the_shape(size: tuple[int, int]) -> None:
    """降档到 1 倍时也必须照常出图（只是没有过渡色），不能返回空贴图。

    大贴图允许有一两级的取整误差：SDL 的 ``smoothscale`` 在很大的表面上会有
    通道取整（实测 240 会变成 238），这在“面板描边”这种尺寸上肉眼看不出来。
    """
    sprite = sprites.render(size, _fill)

    assert sprite.get_size() == size
    middle = sprite.get_at((size[0] // 2, size[1] // 2))
    assert middle[3] >= 250, "降档后也必须是实心画出来的，而不是空白"
    assert all(abs(middle[index] - COLOR[index]) <= 2 for index in range(3))


@pytest.mark.parametrize("size", [(1, 1), (3, 1), (2, 2)])
def test_tiny_sizes_do_not_blow_up(size: tuple[int, int]) -> None:
    sprite = sprites.render(size, _fill)
    assert sprite.get_size() == size
