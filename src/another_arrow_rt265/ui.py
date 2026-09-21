"""信息栏（HUD）与结算覆盖层的绘制。

本模块只负责“画”，不修改任何游戏状态：按钮位置由 :func:`restart_button_rect`
与 :func:`overlay_button_rect` 暴露给 :class:`~another_arrow_rt265.game.Game`
做命中判定，因此以后调排版只需要改这一个文件。

界面上有三种状态，共用一个信息栏：

- 进行中：显示关卡号、剩余箭头数、剩余失误圆点与“重新开始”按钮；
- 通关：叠加遮罩与卡片，主按钮为“下一关”（最后一关则是“重新开始游戏”）；
- 失败：叠加遮罩与卡片，主按钮为“重试本关”。
"""

from __future__ import annotations

import functools
from typing import Final

import pygame

from another_arrow_rt265 import config
from another_arrow_rt265.session import GameStatus, Session

# 优先匹配系统自带的 CJK 字体，避免界面文字渲染成方块。
_FONT_CANDIDATES: Final[tuple[str, ...]] = (
    "microsoftyaheiui",
    "microsoftyahei",
    "msyh",
    "simhei",
    "simsun",
    "notosanscjksc",
    "notosanscjk",
    "pingfangsc",
    "heiti",
    "wenquanyimicrohei",
)

_FONT_CAPTION: Final[int] = 16
_FONT_VALUE: Final[int] = 28
_FONT_BUTTON: Final[int] = 20
_FONT_TITLE: Final[int] = 40
_FONT_BODY: Final[int] = 20

_HUD_CAPTION_TOP: Final[int] = 22
_HUD_VALUE_TOP: Final[int] = 44

_MISTAKE_RADIUS: Final[int] = 7
_MISTAKE_SPACING: Final[int] = 22
_RESTART_BUTTON_SIZE: Final[tuple[int, int]] = (140, 44)

_CARD_SIZE: Final[tuple[int, int]] = (440, 300)
_CARD_RADIUS: Final[int] = 28
_OVERLAY_BUTTON_SIZE: Final[tuple[int, int]] = (220, 52)
_OVERLAY_BUTTON_MARGIN: Final[int] = 32


@functools.cache
def _font(size: int) -> pygame.font.Font:
    """按字号取字体（带缓存）。

    优先使用系统的中文字体；一个都没找到时退回 pygame 内置字体，
    此时中文会显示为占位方块，但界面结构依旧完整。
    """
    if not pygame.font.get_init():
        pygame.font.init()
    path = pygame.font.match_font(list(_FONT_CANDIDATES))
    return pygame.font.Font(path, size) if path else pygame.font.Font(None, size)


@functools.lru_cache(maxsize=1)
def _shade(size: tuple[int, int]) -> pygame.Surface:
    """返回一张铺满窗口的半透明遮罩（只在尺寸变化时重建）。"""
    shade = pygame.Surface(size, pygame.SRCALPHA)
    shade.fill((*config.COLOR_OVERLAY, config.OVERLAY_ALPHA))
    return shade


def board_area() -> pygame.Rect:
    """返回棋盘可用的屏幕区域（位于信息栏下方、窗口留白之内）。"""
    top = config.HUD_HEIGHT + config.BOARD_TOP_GAP
    return pygame.Rect(
        config.HUD_PADDING,
        top,
        config.WINDOW_WIDTH - 2 * config.HUD_PADDING,
        config.WINDOW_HEIGHT - top - config.BOARD_MARGIN,
    )


def hud_rect() -> pygame.Rect:
    """返回顶部信息栏的区域。"""
    return pygame.Rect(0, 0, config.WINDOW_WIDTH, config.HUD_HEIGHT)


def restart_button_rect() -> pygame.Rect:
    """返回信息栏上“重新开始”按钮的区域。"""
    width, height = _RESTART_BUTTON_SIZE
    return pygame.Rect(
        config.WINDOW_WIDTH - config.HUD_PADDING - width,
        (config.HUD_HEIGHT - height) // 2,
        width,
        height,
    )


def overlay_card_rect() -> pygame.Rect:
    """返回结算卡片的区域（在窗口中居中）。"""
    card = pygame.Rect((0, 0), _CARD_SIZE)
    card.center = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2)
    return card


def overlay_button_rect() -> pygame.Rect:
    """返回结算界面主按钮的区域。"""
    card = overlay_card_rect()
    width, height = _OVERLAY_BUTTON_SIZE
    return pygame.Rect(
        card.centerx - width // 2,
        card.bottom - _OVERLAY_BUTTON_MARGIN - height,
        width,
        height,
    )


def overlay_button_text(session: Session) -> str:
    """返回结算界面主按钮的文案，与 ``Session`` 的流转保持一致。"""
    if session.status is GameStatus.FAILED:
        return "重试本关"
    return "重新开始游戏" if session.is_last_level else "下一关"


def draw_ui(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """按会话状态绘制整个界面（信息栏，结算时再加一层卡片）。

    Args:
        surface: 绘制目标。
        session: 当前会话，用于读取关卡号、剩余箭头与失误次数。
        mouse: 鼠标位置，仅用于按钮的悬停高亮；为 ``None`` 时不显示悬停效果。
    """
    draw_hud(surface, session, mouse)
    if session.status is not GameStatus.PLAYING:
        draw_overlay(surface, session, mouse)


def draw_hud(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制信息栏：关卡号、剩余箭头、剩余失误与重新开始按钮。"""
    caption = _font(_FONT_CAPTION).render(
        f"第 {session.level_number} 关 / 共 {session.total_levels} 关",
        True,
        config.COLOR_TEXT_MUTED,
    )
    surface.blit(caption, (config.HUD_PADDING, _HUD_CAPTION_TOP))

    remaining = _font(_FONT_VALUE).render(
        f"剩余箭头 {session.arrows_left}", True, config.COLOR_TEXT
    )
    surface.blit(remaining, (config.HUD_PADDING, _HUD_VALUE_TOP))

    _draw_mistakes(surface, session)
    _draw_button(surface, restart_button_rect(), "重新开始", mouse)


def draw_overlay(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制结算界面：整屏遮罩 + 居中卡片 + 主按钮。"""
    surface.blit(_shade(surface.get_size()), (0, 0))

    cleared = session.status is GameStatus.LEVEL_CLEARED
    accent = config.COLOR_SUCCESS if cleared else config.COLOR_FAILURE
    card = overlay_card_rect()
    pygame.draw.rect(surface, config.COLOR_CARD, card, border_radius=_CARD_RADIUS)
    pygame.draw.rect(surface, accent, card, width=3, border_radius=_CARD_RADIUS)

    title = _font(_FONT_TITLE).render(
        "关卡完成！" if cleared else "挑战失败", True, accent
    )
    surface.blit(title, title.get_rect(center=(card.centerx, card.top + 76)))

    body = _font(_FONT_BODY).render(_result_message(session), True, config.COLOR_TEXT)
    surface.blit(body, body.get_rect(center=(card.centerx, card.top + 136)))

    hint = _font(_FONT_CAPTION).render(
        f"按 Enter 或空格：{overlay_button_text(session)}",
        True,
        config.COLOR_TEXT_MUTED,
    )
    surface.blit(hint, hint.get_rect(center=(card.centerx, card.top + 176)))

    _draw_button(
        surface, overlay_button_rect(), overlay_button_text(session), mouse, accent
    )


def _result_message(session: Session) -> str:
    """返回结算卡片的正文文案。"""
    if session.status is GameStatus.FAILED:
        return f"失误次数已用完，第 {session.level_number} 关未通过"
    if session.is_last_level:
        return f"全部 {session.total_levels} 关已通关"
    return f"剩余失误 {session.mistakes_left} 次"


def _draw_mistakes(surface: pygame.Surface, session: Session) -> None:
    """在信息栏右侧（重新开始按钮左边）画出剩余失误次数。

    剩余次数用亮色实心圆表示，已用掉的画成暗色圆，因此“总共几次、
    还剩几次”都能一眼看清。
    """
    total = session.max_mistakes
    center_y = config.HUD_HEIGHT // 2
    dots_width = (total - 1) * _MISTAKE_SPACING + 2 * _MISTAKE_RADIUS
    first_x = restart_button_rect().left - 28 - dots_width + _MISTAKE_RADIUS

    label = _font(_FONT_CAPTION).render("失误", True, config.COLOR_TEXT_MUTED)
    surface.blit(
        label,
        (
            first_x - _MISTAKE_RADIUS - 12 - label.get_width(),
            center_y - label.get_height() // 2,
        ),
    )

    for index in range(total):
        center = (first_x + index * _MISTAKE_SPACING, center_y)
        color = (
            config.COLOR_MISTAKE
            if index < session.mistakes_left
            else config.COLOR_MISTAKE_SPENT
        )
        pygame.draw.circle(surface, color, center, _MISTAKE_RADIUS)


def _draw_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    mouse: tuple[int, int] | None = None,
    accent: config.Color | None = None,
) -> None:
    """画一个胶囊形按钮；鼠标悬停时提亮，``accent`` 为边框强调色。"""
    hovered = mouse is not None and rect.collidepoint(mouse)
    fill = config.COLOR_BUTTON_HOVER if hovered else config.COLOR_BUTTON
    radius = rect.height // 2
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    pygame.draw.rect(
        surface,
        config.COLOR_BUTTON_BORDER if accent is None else accent,
        rect,
        width=2,
        border_radius=radius,
    )
    label = _font(_FONT_BUTTON).render(text, True, config.COLOR_BUTTON_TEXT)
    surface.blit(label, label.get_rect(center=rect.center))
