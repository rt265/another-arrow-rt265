"""开始界面、信息栏（HUD）与结算覆盖层的绘制。

本模块只负责“画”，不修改任何游戏状态：按钮位置由 :func:`start_button_rect`、
:func:`hud_home_button_rect`、:func:`restart_button_rect`、
:func:`overlay_button_rect` 与 :func:`overlay_home_button_rect` 暴露给
:class:`~another_arrow_rt265.game.Game` 做命中判定，因此以后调排版只需要改这一个文件。

窗口一共有三种画面：

- 开始界面：标题、方向箭头装饰、主按钮与“玩法”说明卡片；
- 进行中：左上角“回到主界面”、关卡 / 剩余箭头 / 用时 / 失误四块统计卡片，
  右侧“重新开始”按钮；
- 通关 / 失败：叠加遮罩与卡片（正文下方额外报一下本关用时），
  底部并排“回到主界面”与主按钮（下一关 / 重试本关 / 再来一轮）。

组件的视觉效果统一由 :func:`_draw_panel` / :func:`_draw_primary_button` /
:func:`_draw_secondary_button` 提供：圆角渐变底板 + 描边 + 柔和投影，配色取自
``config`` 的“界面”一节；按钮上的小图标来自 :mod:`another_arrow_rt265.icons`。
"""

from __future__ import annotations

import functools
import math
from typing import Final

import pygame

from another_arrow_rt265 import config, icons
from another_arrow_rt265.direction import Direction
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
_FONT_LABEL: Final[int] = 15
_FONT_CHIP_VALUE: Final[int] = 24
_FONT_BUTTON: Final[int] = 20
_FONT_TITLE: Final[int] = 36
_FONT_BODY: Final[int] = 20

_FONT_HERO: Final[int] = 68
_FONT_SUBTITLE: Final[int] = 20
_FONT_RULE_TITLE: Final[int] = 19
_FONT_RULE: Final[int] = 17

# 信息栏：左上角“回到主界面”图标按钮、四块统计卡片（关卡 / 剩余箭头 / 用时 /
# 失误）与右侧“重新开始”按钮。窗口宽度有限，四块卡片加两个按钮刚好铺满一行：
# 卡片宽度按“最宽的那行字 + 两侧留白”取（用时读数最长，居中排布时最占地方），
# 卡片之间的间隙统一取 10，改动任何一项宽度前先把 720 这行账重新算一遍。
_HUD_ICON_BUTTON_SIZE: Final[tuple[int, int]] = (48, 48)
_HUD_NAV_GAP: Final[int] = 12
_HUD_CHIP_HEIGHT: Final[int] = 72
_HUD_CHIP_WIDTHS: Final[tuple[int, int, int, int]] = (92, 104, 120, 100)
_HUD_CHIP_GAP: Final[int] = 10
_HUD_CHIP_RADIUS: Final[int] = 20
_HUD_CHIP_PADDING: Final[int] = 16
_HUD_CHIP_CAPTION_TOP: Final[int] = 11
_HUD_CHIP_VALUE_TOP: Final[int] = 34
# 统计卡片与右侧按钮之间的间隙（与卡片之间的间隙保持一致）。
_HUD_CHIP_BUTTON_GAP: Final[int] = 10

_MISTAKE_RADIUS: Final[int] = 7
_MISTAKE_SPACING: Final[int] = 22
_RESTART_BUTTON_SIZE: Final[tuple[int, int]] = (140, 46)

# 按钮上的小图标：尺寸与“图标与文字之间的间隙”。
_BUTTON_ICON_SIZE: Final[int] = 20
_BUTTON_ICON_GAP: Final[int] = 10

# 结算卡片：徽章 / 标题 / 正文 / 用时 / 底部按钮行自上而下排列。
# 底部并排放“回到主界面”与主按钮，两个按钮一起在卡片里居中。
_CARD_SIZE: Final[tuple[int, int]] = (460, 340)
_CARD_RADIUS: Final[int] = 30
_CARD_EMBLEM_TOP: Final[int] = 72
_CARD_TITLE_TOP: Final[int] = 140
_CARD_BODY_TOP: Final[int] = 184
# 用时单独占一行：它既是成绩也是“要不要再来一遍”的理由。
_CARD_TIME_TOP: Final[int] = 212
_OVERLAY_EMBLEM_RADIUS: Final[int] = 36
_OVERLAY_BUTTON_SIZE: Final[tuple[int, int]] = (196, 56)
_OVERLAY_BUTTON_GAP: Final[int] = 16
_OVERLAY_BUTTON_MARGIN: Final[int] = 34

# 开始界面：标题、方向箭头装饰、主按钮与“玩法”卡片。
_GAME_TITLE: Final[str] = "一箭又一箭"
_GAME_SUBTITLE: Final[str] = "ANOTHER ARROW"
_HERO_TITLE_Y: Final[int] = 140
_HERO_SUBTITLE_Y: Final[int] = 212
_HERO_GLOW_ALPHA: Final[int] = 80
_HERO_CHIP_SIZE: Final[int] = 52
_HERO_CHIP_GAP: Final[int] = 18
_HERO_CHIP_CENTER_Y: Final[int] = 272
_HERO_DIRECTIONS: Final[tuple[Direction, ...]] = (
    Direction.RIGHT,
    Direction.UP,
    Direction.LEFT,
    Direction.DOWN,
)
_START_BUTTON_SIZE: Final[tuple[int, int]] = (264, 64)
_START_BUTTON_CENTER_Y: Final[int] = 368
_START_HINT_Y: Final[int] = 428
_RULES_PANEL_SIZE: Final[tuple[int, int]] = (540, 158)
_RULES_PANEL_TOP: Final[int] = 468
_RULES_PADDING: Final[int] = 28
_RULES_LINE_HEIGHT: Final[int] = 30
_RULES: Final[tuple[str, ...]] = (
    "点击箭头，前方没有阻挡时它会飞出棋盘",
    "被挡住的箭头飞不出去，还会消耗一次失误",
    "清空棋盘上的全部箭头，即可进入下一关",
)

# 组件投影 / 光晕的默认扩散半径。
_SHADOW_SPREAD: Final[int] = 8
_GLOW_SPREAD: Final[int] = 7


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


def _mix(
    color_from: config.Color, color_to: config.Color, ratio: float
) -> config.Color:
    """按 ``ratio``（0.0 → ``color_from``，1.0 → ``color_to``）混合两个颜色。"""
    ratio = min(1.0, max(0.0, ratio))
    return (
        round(color_from[0] + (color_to[0] - color_from[0]) * ratio),
        round(color_from[1] + (color_to[1] - color_from[1]) * ratio),
        round(color_from[2] + (color_to[2] - color_from[2]) * ratio),
    )


@functools.lru_cache(maxsize=4)
def _glow_sprite(radius: int, color: config.Color, alpha: int) -> pygame.Surface:
    """生成一张径向渐变的光斑贴图。

    先在 48×48 的低分辨率画布上逐像素算出衰减，再平滑放大，因此既能得到
    柔和的无级过渡，又只需要算几千个像素；结果按参数缓存，不会每帧重算。
    """
    steps = 48
    tiny = pygame.Surface((steps, steps), pygame.SRCALPHA)
    half = steps / 2.0
    for x in range(steps):
        for y in range(steps):
            distance = math.hypot(x + 0.5 - half, y + 0.5 - half) / half
            if distance >= 1.0:
                continue
            tiny.set_at((x, y), (*color, round(alpha * (1.0 - distance) ** 2)))
    return pygame.transform.smoothscale(tiny, (2 * radius, 2 * radius))


@functools.lru_cache(maxsize=8)
def _background(size: tuple[int, int], glow_center: tuple[int, int]) -> pygame.Surface:
    """生成整屏背景：竖直渐变 + 一团柔光（按尺寸与光心缓存）。"""
    surface = pygame.Surface(size)
    last_row = max(1, size[1] - 1)
    for y in range(size[1]):
        pygame.draw.line(
            surface,
            _mix(
                config.COLOR_BACKGROUND_TOP,
                config.COLOR_BACKGROUND_BOTTOM,
                y / last_row,
            ),
            (0, y),
            (size[0], y),
        )

    radius = round(max(size) * 0.6)
    glow = _glow_sprite(radius, config.COLOR_BACKGROUND_GLOW, config.GLOW_ALPHA)
    surface.blit(glow, glow.get_rect(center=glow_center))
    return surface


def draw_background(
    surface: pygame.Surface, center: tuple[int, int] | None = None
) -> None:
    """把整屏背景画到 ``surface`` 上（棋盘 / 主按钮背后会亮起一团柔光）。

    Args:
        surface: 绘制目标。
        center: 柔光的中心像素坐标；``None`` 时取窗口正中。
    """
    size = surface.get_size()
    glow_center = (size[0] // 2, size[1] // 2) if center is None else center
    surface.blit(_background(size, glow_center), (0, 0))


@functools.lru_cache(maxsize=64)
def _gradient(
    size: tuple[int, int],
    top: config.Color,
    bottom: config.Color,
    radius: int,
) -> pygame.Surface:
    """生成一张带圆角遮罩的竖直渐变贴图。

    做法是先画满渐变，再用一张“圆角矩形”蒙版按 ``BLEND_RGBA_MULT`` 抠掉四角，
    于是圆角外侧的像素 alpha 变成 0，贴到任何背景上都不会露出直角。
    """
    layer = pygame.Surface(size, pygame.SRCALPHA)
    last_row = max(1, size[1] - 1)
    for y in range(size[1]):
        pygame.draw.line(layer, _mix(top, bottom, y / last_row), (0, y), (size[0], y))

    if radius > 0:
        mask = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(
            mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius
        )
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return layer


def _draw_shadow(
    surface: pygame.Surface,
    rect: pygame.Rect,
    radius: int,
    spread: int = _SHADOW_SPREAD,
    alpha: int = 110,
) -> None:
    """在 ``rect`` 下方画一圈柔和投影，让组件从背景里“浮”起来。

    由外向内叠几层同心圆角矩形，外层几乎透明、内层最深，近似出模糊的渐变。
    """
    layer = pygame.Surface(
        (rect.width + 2 * spread, rect.height + 2 * spread), pygame.SRCALPHA
    )
    rings = 4
    for step in range(rings, 0, -1):
        grow = spread * step / rings
        shade = round(alpha * (1.0 - step / rings) ** 0.6)
        pygame.draw.rect(
            layer,
            (*config.COLOR_SHADOW, shade),
            pygame.Rect(
                spread - grow,
                spread - grow + 3,
                rect.width + 2 * grow,
                rect.height + 2 * grow,
            ),
            border_radius=round(radius + grow),
        )
    surface.blit(layer, (rect.x - spread, rect.y - spread))


def _draw_glow(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: config.Color,
    radius: int,
    spread: int = _GLOW_SPREAD,
    alpha: int = 120,
) -> None:
    """在组件外侧画一圈强调色光晕（主按钮的悬停态使用）。"""
    layer = pygame.Surface(
        (rect.width + 2 * spread, rect.height + 2 * spread), pygame.SRCALPHA
    )
    for step in range(spread, 0, -2):
        shade = round(alpha * (1.0 - step / spread) ** 1.5)
        pygame.draw.rect(
            layer,
            (*color, shade),
            pygame.Rect(
                spread - step,
                spread - step,
                rect.width + 2 * step,
                rect.height + 2 * step,
            ),
            width=2,
            border_radius=radius + step,
        )
    surface.blit(layer, (rect.x - spread, rect.y - spread))


def _draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    top: config.Color,
    bottom: config.Color,
    *,
    radius: int,
    border: config.Color | None = None,
    border_width: int = 2,
    shadow: bool = True,
    shadow_spread: int = _SHADOW_SPREAD,
) -> None:
    """画一块圆角渐变面板（投影 + 渐变底 + 描边），是各种组件的公共外观。"""
    if shadow:
        _draw_shadow(surface, rect, radius, spread=shadow_spread)
    surface.blit(_gradient(rect.size, top, bottom, radius), rect.topleft)
    if border is not None:
        pygame.draw.rect(
            surface, border, rect, width=border_width, border_radius=radius
        )


def _draw_arrow_glyph(
    surface: pygame.Surface,
    center: tuple[int, int],
    size: float,
    direction: Direction,
    color: config.Color,
) -> None:
    """在 ``center`` 处画一个指向 ``direction`` 的小箭头（装饰用）。

    由一个三角箭头和一根短杆拼成——只画三角形会像播放键，加上杆之后
    才和棋盘上的箭头有一致的“方向感”。
    """
    unit_x, unit_y = direction.vector
    perpendicular_x, perpendicular_y = -unit_y, unit_x
    center_x, center_y = center

    tip = (center_x + unit_x * size * 0.66, center_y + unit_y * size * 0.66)
    head_base_x = center_x + unit_x * size * 0.05
    head_base_y = center_y + unit_y * size * 0.05
    half_width = size * 0.44
    pygame.draw.polygon(
        surface,
        color,
        (
            tip,
            (
                head_base_x + perpendicular_x * half_width,
                head_base_y + perpendicular_y * half_width,
            ),
            (
                head_base_x - perpendicular_x * half_width,
                head_base_y - perpendicular_y * half_width,
            ),
        ),
    )
    pygame.draw.line(
        surface,
        color,
        (center_x - unit_x * size * 0.58, center_y - unit_y * size * 0.58),
        (center_x + unit_x * size * 0.20, center_y + unit_y * size * 0.20),
        width=max(2, round(size * 0.28)),
    )


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


def hud_home_button_rect() -> pygame.Rect:
    """返回信息栏左上角“回到主界面”图标按钮的区域。"""
    width, height = _HUD_ICON_BUTTON_SIZE
    return pygame.Rect(
        config.HUD_PADDING,
        (config.HUD_HEIGHT - height) // 2,
        width,
        height,
    )


def hud_chip_rects() -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
    """返回信息栏四块统计卡片（关卡 / 剩余箭头 / 用时 / 失误）的区域。

    前三块从左往右排在“回到主界面”按钮之后，第四块贴住“重新开始”按钮左侧，
    因此按钮宽度变化时两端的间距仍然保持一致。
    """
    top = (config.HUD_HEIGHT - _HUD_CHIP_HEIGHT) // 2
    level = pygame.Rect(
        hud_home_button_rect().right + _HUD_NAV_GAP,
        top,
        _HUD_CHIP_WIDTHS[0],
        _HUD_CHIP_HEIGHT,
    )
    arrows = pygame.Rect(
        level.right + _HUD_CHIP_GAP, top, _HUD_CHIP_WIDTHS[1], _HUD_CHIP_HEIGHT
    )
    elapsed = pygame.Rect(
        arrows.right + _HUD_CHIP_GAP, top, _HUD_CHIP_WIDTHS[2], _HUD_CHIP_HEIGHT
    )
    mistakes = pygame.Rect(0, top, _HUD_CHIP_WIDTHS[3], _HUD_CHIP_HEIGHT)
    mistakes.right = restart_button_rect().left - _HUD_CHIP_BUTTON_GAP
    return (level, arrows, elapsed, mistakes)


def restart_button_rect() -> pygame.Rect:
    """返回信息栏上“重新开始”按钮的区域。"""
    width, height = _RESTART_BUTTON_SIZE
    return pygame.Rect(
        config.WINDOW_WIDTH - config.HUD_PADDING - width,
        (config.HUD_HEIGHT - height) // 2,
        width,
        height,
    )


def start_button_rect() -> pygame.Rect:
    """返回开始界面上“开始游戏”按钮的区域。"""
    rect = pygame.Rect((0, 0), _START_BUTTON_SIZE)
    rect.center = (config.WINDOW_WIDTH // 2, _START_BUTTON_CENTER_Y)
    return rect


def rules_panel_rect() -> pygame.Rect:
    """返回开始界面下方“玩法”说明卡片的区域。"""
    rect = pygame.Rect((0, 0), _RULES_PANEL_SIZE)
    rect.centerx = config.WINDOW_WIDTH // 2
    rect.top = _RULES_PANEL_TOP
    return rect


def overlay_card_rect() -> pygame.Rect:
    """返回结算卡片的区域（在窗口中居中）。"""
    card = pygame.Rect((0, 0), _CARD_SIZE)
    card.center = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2)
    return card


def overlay_home_button_rect() -> pygame.Rect:
    """返回结算界面“回到主界面”按钮的区域（在按钮行左侧）。"""
    return _overlay_button_row()[0]


def overlay_button_rect() -> pygame.Rect:
    """返回结算界面主按钮的区域（在按钮行右侧）。"""
    return _overlay_button_row()[1]


def _overlay_button_row() -> tuple[pygame.Rect, pygame.Rect]:
    """返回结算界面底部两个按钮的区域 ``(回到主界面, 主按钮)``。

    两个按钮等宽并排，整体在卡片里居中；绘制与命中判定共用这一份坐标。
    """
    card = overlay_card_rect()
    width, height = _OVERLAY_BUTTON_SIZE
    top = card.bottom - _OVERLAY_BUTTON_MARGIN - height
    row_width = 2 * width + _OVERLAY_BUTTON_GAP
    left = card.centerx - row_width // 2
    home = pygame.Rect(left, top, width, height)
    primary = pygame.Rect(left + width + _OVERLAY_BUTTON_GAP, top, width, height)
    return (home, primary)


def overlay_button_text(session: Session) -> str:
    """返回结算界面主按钮的文案，与 ``Session`` 的流转保持一致。

    “回到主界面”始终由旁边的次要按钮提供，因此最后一关通关时主按钮
    改为“再来一轮”，不重复同一个动作。
    """
    if session.status is GameStatus.FAILED:
        return "重试本关"
    return "再来一轮" if session.is_last_level else "下一关"


def overlay_primary_icon(session: Session) -> icons.Icon:
    """返回结算界面主按钮上的图标，与 :func:`overlay_button_text` 对应。"""
    if session.status is GameStatus.FAILED:
        return icons.Icon.RESTART
    return icons.Icon.RESTART if session.is_last_level else icons.Icon.NEXT


def elapsed_text(seconds: float) -> str:
    """把秒数格式化成 ``分:秒.十分位``（如 ``0:12.3``）。

    先把时间取整到十分之一秒再做进位，因此 ``59.96`` 秒显示为 ``1:00.0``
    而不是 ``0:60.0``；负数按 0 处理，避免把动画误差显示成负时间。
    """
    tenths = round(max(0.0, seconds) * 10)
    minutes, rest = divmod(tenths, 600)
    return f"{minutes}:{rest / 10:04.1f}"


def result_time_text(session: Session) -> str:
    """返回结算卡片上的用时文案。

    通关时额外报一下本关最佳成绩：刚刷新记录就说“新纪录”，否则和这一把的
    用时并排显示，让玩家知道差在哪里。
    """
    elapsed = elapsed_text(session.elapsed)
    if session.status is not GameStatus.LEVEL_CLEARED:
        return f"本关用时 {elapsed}"
    if session.is_new_record:
        return f"新纪录 · 用时 {elapsed}"
    best = session.best_time
    if best is None:
        return f"本关用时 {elapsed}"
    return f"本关用时 {elapsed} · 最佳 {elapsed_text(best)}"


def draw_ui(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """按会话状态绘制游戏画面（信息栏，结算时再加一层卡片）。

    Args:
        surface: 绘制目标。
        session: 当前会话，用于读取关卡号、剩余箭头、本关用时与失误次数。
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
    """绘制信息栏：回到主界面 / 四块统计卡片 / 重新开始按钮。"""
    level_rect, arrows_rect, elapsed_rect, mistakes_rect = hud_chip_rects()

    _draw_icon_button(surface, hud_home_button_rect(), icons.Icon.HOME, mouse)
    _draw_stat_chip(
        surface,
        level_rect,
        "关卡",
        f"{session.level_number} / {session.total_levels}",
        config.COLOR_PRIMARY,
    )
    _draw_stat_chip(
        surface,
        arrows_rect,
        "剩余箭头",
        str(session.arrows_left),
        config.COLOR_TEXT,
    )
    # 读秒时只有十分位在跳，右对齐能让它待在原地不动，不会每 0.1 秒抽一下。
    _draw_stat_chip(
        surface,
        elapsed_rect,
        "用时",
        elapsed_text(session.elapsed),
        config.COLOR_TIME,
        align_right=True,
    )
    _draw_mistake_chip(surface, mistakes_rect, session)

    _draw_secondary_button(
        surface, restart_button_rect(), "重新开始", mouse, icon=icons.Icon.RESTART
    )


def draw_overlay(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制结算界面：整屏遮罩 + 居中卡片（徽章 / 标题 / 文案 / 用时 / 底部按钮行）。"""
    surface.blit(_shade(surface.get_size()), (0, 0))

    cleared = session.status is GameStatus.LEVEL_CLEARED
    accent = config.COLOR_SUCCESS if cleared else config.COLOR_FAILURE
    card = overlay_card_rect()

    _draw_panel(
        surface,
        card,
        config.COLOR_CARD_TOP,
        config.COLOR_CARD_BOTTOM,
        radius=_CARD_RADIUS,
        border=accent,
        border_width=3,
        shadow_spread=12,
    )
    _draw_result_emblem(
        surface, (card.centerx, card.top + _CARD_EMBLEM_TOP), accent, cleared
    )

    title = _font(_FONT_TITLE).render(
        "关卡完成！" if cleared else "挑战失败", True, accent
    )
    surface.blit(
        title, title.get_rect(center=(card.centerx, card.top + _CARD_TITLE_TOP))
    )

    body = _font(_FONT_BODY).render(_result_message(session), True, config.COLOR_TEXT)
    surface.blit(body, body.get_rect(center=(card.centerx, card.top + _CARD_BODY_TOP)))

    # 刷新记录时这行改用主色（金），一眼就能看出“这把比之前快”。
    record = session.status is GameStatus.LEVEL_CLEARED and session.is_new_record
    timing = _font(_FONT_BODY).render(
        result_time_text(session),
        True,
        config.COLOR_PRIMARY if record else config.COLOR_TEXT_MUTED,
    )
    surface.blit(
        timing, timing.get_rect(center=(card.centerx, card.top + _CARD_TIME_TOP))
    )

    _draw_secondary_button(
        surface,
        overlay_home_button_rect(),
        "回到主界面",
        mouse,
        icon=icons.Icon.HOME,
    )
    _draw_primary_button(
        surface,
        overlay_button_rect(),
        overlay_button_text(session),
        accent,
        mouse,
        icon=overlay_primary_icon(session),
    )


def _draw_result_emblem(
    surface: pygame.Surface,
    center: tuple[int, int],
    accent: config.Color,
    cleared: bool,
) -> None:
    """画结算卡片顶部的圆形徽章：通关画勾、失败画叉。"""
    radius = _OVERLAY_EMBLEM_RADIUS
    pygame.draw.circle(
        surface, _mix(accent, config.COLOR_CARD_BOTTOM, 0.78), center, radius
    )
    pygame.draw.circle(surface, accent, center, radius, width=3)

    center_x, center_y = center
    if cleared:
        pygame.draw.lines(
            surface,
            accent,
            False,
            [
                (center_x - 13, center_y + 1),
                (center_x - 4, center_y + 10),
                (center_x + 14, center_y - 10),
            ],
            width=5,
        )
    else:
        pygame.draw.line(
            surface,
            accent,
            (center_x - 10, center_y - 10),
            (center_x + 10, center_y + 10),
            width=5,
        )
        pygame.draw.line(
            surface,
            accent,
            (center_x - 10, center_y + 10),
            (center_x + 10, center_y - 10),
            width=5,
        )


def draw_start_screen(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制开始界面（连背景一起画，因为它独占整屏）。

    Args:
        surface: 绘制目标。
        session: 当前会话，用于在页脚标注总关卡数与每关的失误次数上限。
        mouse: 鼠标位置，仅用于“开始游戏”按钮的悬停高亮。
    """
    draw_background(surface)
    _draw_hero_title(surface)
    _draw_arrow_row(surface)
    _draw_primary_button(
        surface,
        start_button_rect(),
        "开始游戏",
        config.COLOR_PRIMARY,
        mouse,
        icon=icons.Icon.NEXT,
    )

    panel = rules_panel_rect()
    _draw_rules_panel(surface, panel)


def _draw_hero_title(surface: pygame.Surface) -> None:
    """画开始界面的标题：金色柔光垫底 + 主色文字 + 拉开字距的英文副标题。"""
    center_x = config.WINDOW_WIDTH // 2

    glow = _font(_FONT_HERO).render(_GAME_TITLE, True, config.COLOR_PRIMARY)
    glow.set_alpha(_HERO_GLOW_ALPHA)
    surface.blit(glow, glow.get_rect(center=(center_x, _HERO_TITLE_Y + 4)))

    title = _font(_FONT_HERO).render(_GAME_TITLE, True, config.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(center_x, _HERO_TITLE_Y)))

    subtitle = _font(_FONT_SUBTITLE).render(
        " ".join(_GAME_SUBTITLE), True, config.COLOR_TEXT_MUTED
    )
    surface.blit(subtitle, subtitle.get_rect(center=(center_x, _HERO_SUBTITLE_Y)))


def _draw_arrow_row(surface: pygame.Surface) -> None:
    """在标题下方排一行四个方向的箭头圆牌，直观提示游戏主题。"""
    count = len(_HERO_DIRECTIONS)
    total = count * _HERO_CHIP_SIZE + (count - 1) * _HERO_CHIP_GAP
    left = (config.WINDOW_WIDTH - total) // 2
    top = _HERO_CHIP_CENTER_Y - _HERO_CHIP_SIZE // 2

    for index, direction in enumerate(_HERO_DIRECTIONS):
        rect = pygame.Rect(
            left + index * (_HERO_CHIP_SIZE + _HERO_CHIP_GAP),
            top,
            _HERO_CHIP_SIZE,
            _HERO_CHIP_SIZE,
        )
        _draw_panel(
            surface,
            rect,
            config.COLOR_PANEL,
            config.COLOR_PANEL_DEEP,
            radius=16,
            border=config.COLOR_PANEL_BORDER,
            shadow_spread=5,
        )
        _draw_arrow_glyph(
            surface,
            rect.center,
            _HERO_CHIP_SIZE * 0.34,
            direction,
            config.COLOR_PRIMARY,
        )


def _draw_rules_panel(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """画“玩法”卡片：一行小标题 + 三条带圆点的规则。"""
    _draw_panel(
        surface,
        rect,
        config.COLOR_PANEL,
        config.COLOR_PANEL_DEEP,
        radius=24,
        border=config.COLOR_PANEL_BORDER,
        shadow_spread=10,
    )

    title = _font(_FONT_RULE_TITLE).render("玩法", True, config.COLOR_PRIMARY)
    surface.blit(title, (rect.left + _RULES_PADDING, rect.top + 20))

    font = _font(_FONT_RULE)
    bullet_x = rect.left + _RULES_PADDING + 6
    text_x = rect.left + _RULES_PADDING + 22
    for index, rule in enumerate(_RULES):
        y = rect.top + 66 + index * _RULES_LINE_HEIGHT
        pygame.draw.circle(
            surface,
            config.COLOR_PRIMARY,
            (bullet_x, y + font.get_height() // 2),
            4,
        )
        surface.blit(font.render(rule, True, config.COLOR_TEXT), (text_x, y))


def _result_message(session: Session) -> str:
    """返回结算卡片的正文文案。"""
    if session.status is GameStatus.FAILED:
        return f"失误次数已用完，第 {session.level_number} 关未通过"
    if session.is_last_level:
        return f"全部 {session.total_levels} 关已通关"
    return f"剩余失误 {session.mistakes_left} 次"


def _draw_chip_frame(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """画统计卡片的底板（渐变 + 描边，信息栏里不需要投影）。"""
    _draw_panel(
        surface,
        rect,
        config.COLOR_PANEL,
        config.COLOR_PANEL_DEEP,
        radius=_HUD_CHIP_RADIUS,
        border=config.COLOR_PANEL_BORDER,
        shadow=False,
    )


def _draw_stat_chip(
    surface: pygame.Surface,
    rect: pygame.Rect,
    caption: str,
    value: str,
    value_color: config.Color,
    *,
    align_right: bool = False,
) -> None:
    """画一块“小标题 + 大数值”的统计卡片。

    ``align_right`` 让数值靠右对齐（计时器用：读秒时只有十分位在变，
    右对齐才能让它待在原地）。
    """
    _draw_chip_frame(surface, rect)
    surface.blit(
        _font(_FONT_LABEL).render(caption, True, config.COLOR_TEXT_MUTED),
        (rect.left + _HUD_CHIP_PADDING, rect.top + _HUD_CHIP_CAPTION_TOP),
    )
    label = _font(_FONT_CHIP_VALUE).render(value, True, value_color)
    left = (
        rect.right - _HUD_CHIP_PADDING - label.get_width()
        if align_right
        else rect.left + _HUD_CHIP_PADDING
    )
    surface.blit(label, (left, rect.top + _HUD_CHIP_VALUE_TOP))


def _draw_mistake_chip(
    surface: pygame.Surface, rect: pygame.Rect, session: Session
) -> None:
    """画“失误”卡片。

    剩余次数用亮红色实心圆表示，已用掉的画成暗色圆，因此“总共几次、
    还剩几次”都能一眼看清，不必去读数字。
    """
    _draw_chip_frame(surface, rect)
    surface.blit(
        _font(_FONT_LABEL).render("失误", True, config.COLOR_TEXT_MUTED),
        (rect.left + _HUD_CHIP_PADDING, rect.top + _HUD_CHIP_CAPTION_TOP),
    )

    center_y = rect.top + _HUD_CHIP_VALUE_TOP + 15
    # 圆点整组在卡片里居中，与前后的“剩余箭头 / 重新开始”对齐得好看一些。
    span = (session.max_mistakes - 1) * _MISTAKE_SPACING
    first_x = rect.centerx - span // 2
    for index in range(session.max_mistakes):
        center = (first_x + index * _MISTAKE_SPACING, center_y)
        color = (
            config.COLOR_MISTAKE
            if index < session.mistakes_left
            else config.COLOR_MISTAKE_SPENT
        )
        pygame.draw.circle(surface, color, center, _MISTAKE_RADIUS)


def _draw_secondary_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    mouse: tuple[int, int] | None = None,
    icon: icons.Icon | None = None,
) -> None:
    """画深色的次要按钮（重新开始 / 回到主界面），鼠标悬停时提亮。"""
    hovered = mouse is not None and rect.collidepoint(mouse)
    top = config.COLOR_BUTTON_TOP_HOVER if hovered else config.COLOR_BUTTON_TOP
    bottom = config.COLOR_BUTTON_BOTTOM_HOVER if hovered else config.COLOR_BUTTON_BOTTOM
    _draw_panel(
        surface,
        rect,
        top,
        bottom,
        radius=rect.height // 2,
        border=config.COLOR_BUTTON_BORDER,
        shadow_spread=6,
    )
    _draw_button_content(surface, rect, text, config.COLOR_BUTTON_TEXT, icon)


def _draw_icon_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    icon: icons.Icon,
    mouse: tuple[int, int] | None = None,
) -> None:
    """画一个只有图标的按钮（信息栏左上角的“回到主界面”）。

    图形本身没有文字，因此用方位（左上角）与描边强调色向“可点”靠拢：
    悬停时提亮，和旁边带文字的按钮保持同一套外观。
    """
    hovered = mouse is not None and rect.collidepoint(mouse)
    top = config.COLOR_BUTTON_TOP_HOVER if hovered else config.COLOR_BUTTON_TOP
    bottom = config.COLOR_BUTTON_BOTTOM_HOVER if hovered else config.COLOR_BUTTON_BOTTOM
    _draw_panel(
        surface,
        rect,
        top,
        bottom,
        radius=rect.height // 2,
        border=config.COLOR_BUTTON_BORDER,
        shadow_spread=6,
    )
    icons.draw_icon(
        surface,
        icon,
        rect.center,
        round(rect.width * 0.46),
        config.COLOR_BUTTON_TEXT,
    )


def _draw_primary_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    accent: config.Color,
    mouse: tuple[int, int] | None = None,
    icon: icons.Icon | None = None,
) -> None:
    """画填充强调色的主按钮，鼠标悬停时更亮并带一圈外发光。"""
    hovered = mouse is not None and rect.collidepoint(mouse)
    radius = rect.height // 2
    if hovered:
        _draw_glow(surface, rect, accent, radius)
    _draw_panel(
        surface,
        rect,
        _mix(accent, (255, 255, 255), 0.28 if hovered else 0.14),
        _mix(accent, (0, 0, 0), 0.10 if hovered else 0.26),
        radius=radius,
        border=_mix(accent, (255, 255, 255), 0.35),
        shadow_spread=8,
    )
    _draw_button_content(surface, rect, text, config.COLOR_ON_PRIMARY, icon)


def _draw_button_content(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    color: config.Color,
    icon: icons.Icon | None = None,
) -> None:
    """把“图标 + 文字”当成一个整体在按钮里居中。"""
    label = _font(_FONT_BUTTON).render(text, True, color)
    content_width = label.get_width()
    if icon is not None:
        content_width += _BUTTON_ICON_SIZE + _BUTTON_ICON_GAP

    left = rect.centerx - content_width // 2
    if icon is not None:
        icons.draw_icon(
            surface,
            icon,
            (left + _BUTTON_ICON_SIZE // 2, rect.centery),
            _BUTTON_ICON_SIZE,
            color,
        )
        left += _BUTTON_ICON_SIZE + _BUTTON_ICON_GAP
    surface.blit(label, (left, rect.centery - label.get_height() // 2))
