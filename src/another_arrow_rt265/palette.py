"""箭头配色。

棋盘上的箭头是彩色的，但颜色不是随手刷上去的——分配规则集中在这里，
:mod:`another_arrow_rt265.board` 只负责把这里算出来的颜色画到屏幕上。

规则有三条：

1. 每个箭头从 ``config.ARROW_PALETTE`` 里取一个**主题色**，取哪一个由它所在
   格子的位置决定（见 :func:`theme_color`）。位置是固定的，所以整关之内颜色稳定：
   别的箭头被清除、玩家重新开始本关，剩下的箭头都不会换色。
2. 主题色只决定“这个箭头长什么样”，不参与任何判定——点击、阻挡、计分都只看
   :class:`~another_arrow_rt265.board.Arrow` 的行列与方向。
3. 选中 / 碰撞这些状态**不换主题色**，而是由主题色推导出来（见 :func:`chip_color`
   与 :func:`glyph_color`）：圆片底色用压暗过的主题色，箭头本身在选中时提亮、
   在碰撞时染向警示色。这样箭头始终保留自己的颜色身份，状态变化靠亮度与提示环表达。
"""

from __future__ import annotations

from another_arrow_rt265 import config


def theme_color(row: int, col: int) -> config.Color:
    """返回 ``(row, col)`` 处箭头的主题色。

    取色下标是 ``行 × ARROW_PALETTE_ROW_STEP + 列`` 对调色板长度取模：横向相邻的
    格子下标相差 1、纵向相差 ``ARROW_PALETTE_ROW_STEP``，只要该步长不是调色板长度的
    倍数，左右与上下相邻的箭头就必然不同色（不容易看错成一整片）。
    """
    palette = config.ARROW_PALETTE
    return palette[(row * config.ARROW_PALETTE_ROW_STEP + col) % len(palette)]


def chip_color(
    theme: config.Color,
    *,
    selected: bool = False,
    blocked: bool = False,
) -> config.Color:
    """返回箭头圆片底色的颜色（常态 / 选中 / 碰撞）。

    常态与碰撞各自有一个深色基准（``COLOR_CHIP`` / ``COLOR_CHIP_BLOCKED``），
    这里把主题色按不同比例混进去：既让圆片带上箭头的颜色，又保持足够暗，
    衬得亮色箭头依然醒目。选中态不另设基准，而是在常态底色上再压一层主题色——
    圆片更亮、更饱和，箭头看起来像是被点亮了。
    """
    if blocked:
        return mix(config.COLOR_CHIP_BLOCKED, theme, config.ARROW_CHIP_BLOCKED_MIX)

    chip = mix(config.COLOR_CHIP, theme, config.ARROW_CHIP_MIX)
    if selected:
        return mix(chip, theme, config.ARROW_CHIP_SELECTED_MIX)
    return chip


def chip_border_color(
    theme: config.Color,
    *,
    selected: bool = False,
    blocked: bool = False,
) -> config.Color:
    """返回圆片描边的颜色：比圆片底色亮、比主题色暗，用来勾出圆片的轮廓。"""
    chip = chip_color(theme, selected=selected, blocked=blocked)
    return mix(chip, theme, config.ARROW_CHIP_BORDER_MIX)


def glyph_color(
    theme: config.Color,
    *,
    selected: bool = False,
    blocked: bool = False,
) -> config.Color:
    """返回箭头图形本身的颜色（常态 / 选中 / 碰撞）。

    常态直接用主题色；选中时向白色轻微提亮即可——选中主要靠中性色的呼吸环表达，
    箭头本身不必洗白；碰撞时向偏白的警示色染色，与红色的扩散环、火花线一起
    表达“撞上了”。
    """
    if blocked:
        return mix(theme, config.COLOR_ARROW_BLOCKED, config.ARROW_BLOCKED_MIX)
    if selected:
        return mix(theme, config.COLOR_ARROW_HIGHLIGHT, config.ARROW_SELECTED_MIX)
    return theme


def mix(
    color_from: config.Color,
    color_to: config.Color,
    ratio: float,
) -> config.Color:
    """按 ``ratio`` 混合两个颜色（0.0 → ``color_from``，1.0 → ``color_to``）。

    ``ratio`` 会被夹到 ``[0.0, 1.0]``，因此调用方不必自己保证取值范围。
    """
    ratio = min(1.0, max(0.0, ratio))
    return (
        round(color_from[0] + (color_to[0] - color_from[0]) * ratio),
        round(color_from[1] + (color_to[1] - color_from[1]) * ratio),
        round(color_from[2] + (color_to[2] - color_from[2]) * ratio),
    )
