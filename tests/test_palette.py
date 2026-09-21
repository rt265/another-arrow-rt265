"""彩色箭头配色的测试：取色规则、可读性与状态推导。"""

from __future__ import annotations

import pytest

from another_arrow_rt265 import config, palette

# 主题色实际会落在哪些底色上：棋盘格、棋盘底板（飞出动画会经过）与箭头自己的圆片。
BOARD_BACKGROUNDS = (config.COLOR_CELL, config.COLOR_BOARD)
# WCAG 对“非文本的大块图形”要求的对比度下限。
MIN_GRAPHIC_CONTRAST = 3.0


def _luminance(color: config.Color) -> float:
    """返回 WCAG 相对亮度（0.0 ~ 1.0），用于估算颜色之间的对比度。"""

    def channel(value: int) -> float:
        srgb = value / 255.0
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: config.Color, second: config.Color) -> float:
    """返回两个颜色的对比度，1.0 表示完全相同，数值越大越分明。"""
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _hue_order(color: config.Color) -> list[int]:
    """返回三个通道从大到小的下标，用来粗略判断色相有没有被改掉。"""
    return sorted(range(3), key=lambda index: color[index], reverse=True)


def _dominant_channel(color: config.Color) -> int:
    """返回最大的通道下标（颜色偏红 / 偏绿 / 偏蓝）。"""
    return max(range(3), key=lambda index: color[index])


def _between(color: config.Color, first: config.Color, second: config.Color) -> bool:
    """判断 ``color`` 的每个通道是否都落在另外两个颜色之间（混合的必然结果）。"""
    return all(
        min(first[index], second[index])
        <= color[index]
        <= max(first[index], second[index])
        for index in range(3)
    )


def test_palette_is_well_formed_and_has_enough_variety() -> None:
    assert len(config.ARROW_PALETTE) >= 4, "颜色太少，棋盘上看不出“彩色箭头”"
    assert len(set(config.ARROW_PALETTE)) == len(config.ARROW_PALETTE), "调色板有重复色"
    for color in config.ARROW_PALETTE:
        assert len(color) == 3
        assert all(isinstance(value, int) and 0 <= value <= 255 for value in color)


def test_neighbouring_arrows_never_share_a_color() -> None:
    """上下 / 左右相邻的格子必须取到不同颜色，否则会看成一大片同色。"""
    for row in range(12):
        for col in range(12):
            color = palette.theme_color(row, col)
            assert palette.theme_color(row + 1, col) != color
            assert palette.theme_color(row, col + 1) != color


def test_theme_color_only_depends_on_the_cell_position() -> None:
    """取色只跟行列有关：同一个格子每次取到的颜色都一样，且必定来自调色板。"""
    for row, col in ((0, 0), (1, 2), (4, 5), (7, 3)):
        color = palette.theme_color(row, col)
        assert color == palette.theme_color(row, col)
        assert color in config.ARROW_PALETTE


@pytest.mark.parametrize("theme", config.ARROW_PALETTE)
def test_every_theme_color_stands_out_on_the_board(
    theme: config.Color,
) -> None:
    """每个主题色都要在棋盘格、棋盘底板上醒目，并且在自家圆片上仍然看得清。"""
    for background in BOARD_BACKGROUNDS:
        assert _contrast(theme, background) >= MIN_GRAPHIC_CONTRAST
    assert _contrast(theme, palette.chip_color(theme)) >= MIN_GRAPHIC_CONTRAST


@pytest.mark.parametrize("theme", config.ARROW_PALETTE)
def test_chip_border_separates_the_chip_from_the_cell(theme: config.Color) -> None:
    """圆片描边要比圆片底色亮，好歹把箭头从同色系的棋盘格上勾出来。"""
    border = palette.chip_border_color(theme)
    assert _contrast(border, palette.chip_color(theme)) > 1.0
    assert _contrast(border, config.COLOR_CELL) >= 2.0


@pytest.mark.parametrize("theme", config.ARROW_PALETTE)
@pytest.mark.parametrize(
    ("selected", "blocked"),
    ((False, False), (True, False), (False, True)),
)
def test_arrow_stays_readable_in_every_state(
    theme: config.Color, selected: bool, blocked: bool
) -> None:
    """常态 / 选中 / 碰撞三种状态下，箭头与它自己的圆片都要分得开。"""
    chip = palette.chip_color(theme, selected=selected, blocked=blocked)
    glyph = palette.glyph_color(theme, selected=selected, blocked=blocked)
    assert _contrast(glyph, chip) >= MIN_GRAPHIC_CONTRAST


@pytest.mark.parametrize("theme", config.ARROW_PALETTE)
def test_glyph_keeps_its_hue_in_every_state(theme: config.Color) -> None:
    """状态变化只调明暗，不该把箭头的颜色身份换掉。

    选中色是“主题色 + 白”，色相完全保留；碰撞色染向偏白的警示色，颜色会被冲淡，
    因此只要求主色通道不变（绿箭头不会变成红箭头），不强求通道的完整排序。
    """
    assert _hue_order(palette.glyph_color(theme, selected=True)) == _hue_order(theme)
    assert _dominant_channel(palette.glyph_color(theme, blocked=True)) == (
        _dominant_channel(theme)
    )


@pytest.mark.parametrize("theme", config.ARROW_PALETTE)
def test_selected_and_blocked_glyphs_get_brighter(theme: config.Color) -> None:
    """选中是“点亮”，碰撞是“撞得发白”，两者都比常态更亮；碰撞还要向警示色靠。"""
    selected = palette.glyph_color(theme, selected=True)
    blocked = palette.glyph_color(theme, blocked=True)
    assert _luminance(selected) > _luminance(theme)
    assert _luminance(blocked) > _luminance(theme)

    assert selected != theme and blocked != theme
    assert _between(selected, theme, config.COLOR_ARROW_HIGHLIGHT)
    assert _between(blocked, theme, config.COLOR_ARROW_BLOCKED)


@pytest.mark.parametrize("theme", config.ARROW_PALETTE)
def test_selected_and_blocked_chips_are_brighter_than_the_normal_one(
    theme: config.Color,
) -> None:
    """选中 / 碰撞的圆片底色要比常态亮一点（状态本身仍由提示环强调）。"""
    normal = palette.chip_color(theme)
    selected = palette.chip_color(theme, selected=True)
    blocked = palette.chip_color(theme, blocked=True)
    assert normal != selected != blocked
    assert _luminance(selected) > _luminance(normal)
    assert _luminance(blocked) > _luminance(normal)


def test_mix_interpolates_and_clamps() -> None:
    start, end = (10, 20, 30), (110, 220, 255)
    assert palette.mix(start, end, 0.0) == start
    assert palette.mix(start, end, 1.0) == end

    middle = palette.mix(start, end, 0.5)
    assert all(
        abs(middle[index] - (start[index] + end[index]) / 2) <= 1 for index in range(3)
    )
    # 越界的比例会被夹住，调用方不必自己保证取值范围。
    assert palette.mix(start, end, -1.0) == start
    assert palette.mix(start, end, 2.0) == end
