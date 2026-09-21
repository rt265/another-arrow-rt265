"""信息栏、开始界面与结算覆盖层的布局、文案与绘制冒烟测试。"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, ui
from another_arrow_rt265.levels import Level
from another_arrow_rt265.session import GameStatus, Session

AREA = pygame.Rect(0, 0, 640, 640)

CLEARABLE_LEVEL: Level = (
    ".^.",
    "...",
    "...",
)


def _session() -> Session:
    """创建一个只有一关（因此也是最后一关）的会话。"""
    return Session(AREA, levels=(CLEARABLE_LEVEL,))


def _surface() -> pygame.Surface:
    return pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))


# ---------------------------------------------------------------- 布局


def test_board_area_sits_below_the_hud_within_the_window() -> None:
    area = ui.board_area()
    assert area.top >= config.HUD_HEIGHT
    assert area.left >= 0
    assert area.right <= config.WINDOW_WIDTH
    assert area.bottom <= config.WINDOW_HEIGHT


def test_restart_button_is_inside_the_hud() -> None:
    hud = ui.hud_rect()
    button = ui.restart_button_rect()
    assert hud.contains(button)
    assert button.right <= config.WINDOW_WIDTH - config.HUD_PADDING
    # 按钮不应该盖住棋盘。
    assert not button.colliderect(ui.board_area())


def test_overlay_button_is_centered_inside_the_card() -> None:
    card = ui.overlay_card_rect()
    button = ui.overlay_button_rect()
    assert card.contains(button)
    assert button.centerx == card.centerx
    assert card.centerx == config.WINDOW_WIDTH // 2
    assert card.centery == config.WINDOW_HEIGHT // 2


def test_hud_chips_stay_inside_the_hud_and_clear_of_the_button() -> None:
    hud = ui.hud_rect()
    level, arrows, mistakes = ui.hud_chip_rects()
    button = ui.restart_button_rect()

    for chip in (level, arrows, mistakes):
        assert hud.contains(chip)
        assert not chip.colliderect(button)
        assert not chip.colliderect(ui.board_area())

    # 三块卡片按“关卡 → 剩余箭头 → 失误”从左到右排开，彼此不重叠。
    assert level.right < arrows.left
    assert arrows.right < mistakes.left


def test_start_button_is_centered_and_above_the_rules_panel() -> None:
    button = ui.start_button_rect()
    panel = ui.rules_panel_rect()

    assert button.centerx == config.WINDOW_WIDTH // 2
    assert 0 <= button.left and button.right <= config.WINDOW_WIDTH
    # 主按钮位于画面中上部，且不压到下方的“玩法”卡片。
    assert button.centery < config.WINDOW_HEIGHT * 0.6
    assert button.bottom < panel.top


def test_start_screen_content_fits_inside_the_window() -> None:
    panel = ui.rules_panel_rect()

    assert panel.left >= 0
    assert panel.right <= config.WINDOW_WIDTH
    assert panel.bottom <= config.WINDOW_HEIGHT


# ---------------------------------------------------------------- 文案


def test_overlay_button_text_follows_the_status() -> None:
    session = _session()

    session.status = GameStatus.LEVEL_CLEARED
    assert ui.overlay_button_text(session) == "回到主界面"  # 只有一关，通关即通关全部
    session.status = GameStatus.FAILED
    assert ui.overlay_button_text(session) == "重试本关"


def test_overlay_button_text_has_next_level_on_multi_level_session() -> None:
    session = Session(AREA, levels=(CLEARABLE_LEVEL, CLEARABLE_LEVEL))
    session.status = GameStatus.LEVEL_CLEARED
    assert ui.overlay_button_text(session) == "下一关"


# ---------------------------------------------------------------- 绘制


def test_draw_hud_renders_without_error() -> None:
    surface = _surface()
    ui.draw_hud(surface, _session())
    ui.draw_hud(surface, _session(), mouse=ui.restart_button_rect().center)


@pytest.mark.parametrize("status", list(GameStatus))
def test_draw_ui_renders_in_every_state(status: GameStatus) -> None:
    surface = _surface()
    session = _session()
    session.status = status

    ui.draw_ui(surface, session)
    ui.draw_ui(surface, session, mouse=ui.overlay_button_rect().center)


def test_overlay_paints_a_shade_over_the_whole_window() -> None:
    surface = _surface()
    session = _session()
    ui.draw_hud(surface, session)
    before = surface.get_at((4, config.WINDOW_HEIGHT // 2))[:3]

    session.status = GameStatus.FAILED
    ui.draw_ui(surface, session)
    after = surface.get_at((4, config.WINDOW_HEIGHT // 2))[:3]

    assert before != after, "结算覆盖层应该把整屏压暗（含信息栏之外的区域）"


def test_draw_start_screen_renders_without_error() -> None:
    surface = _surface()
    session = _session()

    ui.draw_start_screen(surface, session)
    ui.draw_start_screen(surface, session, mouse=ui.start_button_rect().center)


def test_draw_start_screen_covers_the_whole_window() -> None:
    surface = _surface()
    surface.fill((255, 0, 255))

    ui.draw_start_screen(surface, _session())

    assert surface.get_at((2, 2))[:3] != (255, 0, 255)
    assert surface.get_at((config.WINDOW_WIDTH - 3, 2))[:3] != (255, 0, 255)
    assert surface.get_at((2, config.WINDOW_HEIGHT - 3))[:3] != (255, 0, 255), (
        "开始界面应该连背景一起画，不留未覆盖的角落"
    )


def test_draw_background_paints_a_top_to_bottom_gradient() -> None:
    surface = _surface()
    ui.draw_background(surface)

    top = surface.get_at((4, 4))[:3]
    bottom = surface.get_at((4, config.WINDOW_HEIGHT - 4))[:3]
    assert sum(top) > sum(bottom), "背景应当自上而下由亮转暗"
