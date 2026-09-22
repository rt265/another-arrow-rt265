"""窗口缩放（``viewport``）的换算规则。

界面与棋盘的布局常量都是按设计尺寸（720×720）写的绝对值，这里钉住的是“把它们
等比映射到实际窗口”这件事本身的规则：缩放系数、居中留白、下限与量化。
"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, viewport


def test_the_design_size_maps_to_itself() -> None:
    """窗口就是设计尺寸时，视图不缩放也不偏移（改动前的一切逐像素保持）。"""
    view = viewport.Viewport.fit(config.WINDOW_SIZE)

    assert view.scale == 1.0
    assert view.origin == (0, 0)
    assert view.s(10) == 10
    assert view.x(32) == 32
    assert view.y(104) == 104
    assert view.rect(0, 0, 720, 720) == pygame.Rect(0, 0, 720, 720)


def test_a_bigger_window_scales_everything_up() -> None:
    view = viewport.Viewport.fit((1080, 1080))

    assert view.scale == 1.5
    assert view.origin == (0, 0)
    assert view.s(20) == 30
    assert view.rect(32, 128, 656, 44) == pygame.Rect(48, 192, 984, 66)
    assert view.point(360, 360) == (540, 540)


def test_a_wide_window_keeps_the_content_centred() -> None:
    """长宽比不一致时按较小的那一维缩放，多出来的部分留白（内容居中）。"""
    view = viewport.Viewport.fit((1440, 900))

    assert view.scale == 1.25
    assert view.origin == (270, 0)
    assert view.center() == (720, 450), "设计框的中心应当落在窗口中心"
    assert view.rect(0, 0, 720, 720).center == (720, 450)


def test_a_portrait_window_keeps_the_content_centred() -> None:
    view = viewport.Viewport.fit((900, 1440))

    assert view.scale == 1.25
    assert view.origin == (0, 270)
    assert view.center() == (450, 720)


def test_the_content_is_never_shrunk_below_the_design_size() -> None:
    """窗口比设计尺寸还小时不缩小内容（会裁掉一部分），避免界面小到不可读。"""
    view = viewport.Viewport.fit((400, 300))

    assert view.scale == config.MIN_SCALE == 1.0
    assert view.origin == (-160, -210), "内容仍然居中，超出窗口的部分被裁掉"


def test_the_scale_is_quantised_to_keep_caches_small() -> None:
    """缩放系数取整到固定步长：拖拽窗口时不会为每个中间尺寸各缓存一份贴图 / 字体。

    向下取整，因此设计框永远不会比窗口大，取整不会变成“多裁掉一条”。
    """
    view = viewport.Viewport.fit((1081, 1081))
    raw = 1081 / config.WINDOW_WIDTH

    assert view.scale == pytest.approx(1.5)
    assert view.scale <= raw
    assert raw - view.scale < config.SCALE_STEP
    assert (round(view.scale / config.SCALE_STEP) * config.SCALE_STEP) == view.scale
    assert 720 * view.scale <= 1081, "设计框要放得进窗口"


def test_adjacent_rects_stay_flush() -> None:
    """两个紧挨着的设计矩形映射之后仍然紧挨着，不能裂缝也不能重叠。

    信息栏那一行卡片是“算着排满”的，取整方式一旦把边界算歪就会露出缝隙，
    所以 :meth:`Viewport.rect` 对左右 / 上下边界分别取整。
    """
    view = viewport.Viewport.fit((1080, 900))
    left = view.rect(0, 0, 92, 72)
    right = view.rect(92, 0, 104, 72)

    assert left.right == right.left
    assert left.top == right.top
    assert left.bottom == right.bottom


def test_map_matches_rect() -> None:
    view = viewport.Viewport.fit((1000, 700))
    design = pygame.Rect(32, 104, 92, 72)

    assert view.map(design) == view.rect(32, 104, 92, 72)


def test_the_module_level_viewport_follows_set_and_reset() -> None:
    assert viewport.current() is viewport.DEFAULT
    assert viewport.s(10) == 10

    viewport.set_current(viewport.Viewport.fit((1440, 1440)))
    assert viewport.s(10) == 20
    assert viewport.x(config.HUD_PADDING) == 64

    viewport.reset()
    assert viewport.current() is viewport.DEFAULT
    assert viewport.rect(0, 0, 10, 10) == pygame.Rect(0, 0, 10, 10)
