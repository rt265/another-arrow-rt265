"""信息栏、开始界面与结算覆盖层的布局、文案与绘制冒烟测试。"""

from __future__ import annotations

import itertools

import pygame
import pytest

from another_arrow_rt265 import config, icons, ui
from another_arrow_rt265.levels import Level
from another_arrow_rt265.session import GameStatus, Session

AREA = pygame.Rect(0, 0, 640, 640)

CLEARABLE_LEVEL: Level = (
    ".^.",
    "...",
    "...",
)

# 十字形关卡：四个箭头互相阻挡，点哪个都会消耗失误。
CROSS_LEVEL: Level = (
    ".v.",
    ">.<",
    ".^.",
)


def _session() -> Session:
    """创建一个只有一关（因此也是最后一关）的会话。"""
    return Session(AREA, levels=(CLEARABLE_LEVEL,))


def _surface() -> pygame.Surface:
    return pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))


def _clear_level(session: Session, seconds: float) -> None:
    """让单箭头关卡在指定的用时时长（秒）后通关。"""
    session.update(seconds)
    assert session.click(session.board.cell_rect(0, 1).center) is not None
    for _ in range(config.FPS * 3):
        if not session.is_playing:
            break
        session.update(1.0 / config.FPS)
    assert session.status is GameStatus.LEVEL_CLEARED


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


def test_hud_home_button_is_inside_the_hud_and_clear_of_the_chips() -> None:
    hud = ui.hud_rect()
    home = ui.hud_home_button_rect()
    assert hud.contains(home)
    assert home.left == config.HUD_PADDING
    assert not home.colliderect(ui.restart_button_rect())
    for chip in ui.hud_chip_rects():
        assert not chip.colliderect(home)


def test_overlay_button_row_is_centered_inside_the_card() -> None:
    card = ui.overlay_card_rect()
    home = ui.overlay_home_button_rect()
    primary = ui.overlay_button_rect()

    for button in (home, primary):
        assert card.contains(button)

    # 两个按钮并排、不重叠，且这一行在卡片里水平居中。
    assert home.right < primary.left
    assert card.centerx - home.left == primary.right - card.centerx
    assert card.centerx == config.WINDOW_WIDTH // 2
    assert card.centery == config.WINDOW_HEIGHT // 2


def test_hud_chips_stay_inside_the_hud_and_clear_of_the_button() -> None:
    hud = ui.hud_rect()
    level, arrows, elapsed, mistakes = ui.hud_chip_rects()
    button = ui.restart_button_rect()

    for chip in (level, arrows, elapsed, mistakes):
        assert hud.contains(chip)
        assert not chip.colliderect(button)
        assert not chip.colliderect(ui.board_area())

    # 四块卡片按“关卡 → 剩余箭头 → 用时 → 失误”从左到右排开，彼此不重叠。
    assert level.right < arrows.left
    assert arrows.right < elapsed.left
    assert elapsed.right < mistakes.left


def test_hud_row_fills_the_window_exactly() -> None:
    """信息栏一行排满：左贴齐、右贴齐，中间不重叠也不溢出窗口。

    卡片总宽是靠手算排出来的（窗口宽度有限），任何一处改宽都可能把最后一块
    卡片挤出窗口，因此这里把“整行恰好落在两侧留白之间”钉住。
    """
    row = (ui.hud_home_button_rect(), *ui.hud_chip_rects(), ui.restart_button_rect())

    assert row[0].left == config.HUD_PADDING
    assert row[-1].right == config.WINDOW_WIDTH - config.HUD_PADDING
    for previous, current in itertools.pairwise(row):
        assert previous.right <= current.left


def test_timer_chip_has_room_for_a_long_time_reading() -> None:
    """计时读数会越走越长，卡片至少要放得下 100 分钟以内的读数。"""
    *_, elapsed, _ = ui.hud_chip_rects()
    widest = ui._font(ui._FONT_CHIP_VALUE).render(
        ui.elapsed_text(5999.9), True, config.COLOR_TIME
    )
    assert widest.get_width() + 2 * ui._HUD_CHIP_PADDING <= elapsed.width


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
    assert ui.overlay_button_text(session) == "再来一轮"  # 只有一关，通关即通关全部
    session.status = GameStatus.FAILED
    assert ui.overlay_button_text(session) == "重试本关"


def test_overlay_button_icon_follows_the_status() -> None:
    session = _session()
    session.status = GameStatus.FAILED
    assert ui.overlay_primary_icon(session) is icons.Icon.RESTART

    session.status = GameStatus.LEVEL_CLEARED
    assert ui.overlay_primary_icon(session) is icons.Icon.RESTART  # 再来一轮

    multi = Session(AREA, levels=(CLEARABLE_LEVEL, CLEARABLE_LEVEL))
    multi.status = GameStatus.LEVEL_CLEARED
    assert ui.overlay_primary_icon(multi) is icons.Icon.NEXT


def test_overlay_button_text_has_next_level_on_multi_level_session() -> None:
    session = Session(AREA, levels=(CLEARABLE_LEVEL, CLEARABLE_LEVEL))
    session.status = GameStatus.LEVEL_CLEARED
    assert ui.overlay_button_text(session) == "下一关"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0.0, "0:00.0"),
        (0.04, "0:00.0"),
        (12.34, "0:12.3"),
        (59.96, "1:00.0"),  # 先取整到十分位再进位，不出现 0:60.0
        (65.0, "1:05.0"),
        (3725.4, "62:05.4"),
    ],
)
def test_elapsed_text_formats_minutes_seconds_and_tenths(
    seconds: float, expected: str
) -> None:
    assert ui.elapsed_text(seconds) == expected


def test_elapsed_text_never_shows_a_negative_time() -> None:
    assert ui.elapsed_text(-3.0) == "0:00.0"


def test_result_time_text_on_failure() -> None:
    session = Session(AREA, levels=(CROSS_LEVEL,), max_mistakes=1)
    session.update(3.0)
    assert session.click(session.board.cell_rect(0, 1).center) is not None
    assert session.status is GameStatus.FAILED

    assert ui.result_time_text(session) == "本关用时 0:03.0"


def test_result_time_text_marks_a_new_record_and_remembers_the_best() -> None:
    session = Session(AREA, levels=(CLEARABLE_LEVEL,))

    _clear_level(session, 1.0)
    assert session.is_new_record is True
    assert ui.result_time_text(session) == "新纪录 · 用时 0:01.0"

    session.restart_level()
    _clear_level(session, 2.5)
    assert session.is_new_record is False
    assert ui.result_time_text(session) == "本关用时 0:02.5 · 最佳 0:01.0"


# ---------------------------------------------------------------- 绘制


def test_draw_hud_renders_without_error() -> None:
    surface = _surface()
    ui.draw_hud(surface, _session())
    ui.draw_hud(surface, _session(), mouse=ui.restart_button_rect().center)
    ui.draw_hud(surface, _session(), mouse=ui.hud_home_button_rect().center)


@pytest.mark.parametrize("status", list(GameStatus))
def test_draw_ui_renders_in_every_state(status: GameStatus) -> None:
    surface = _surface()
    session = _session()
    session.status = status

    ui.draw_ui(surface, session)
    ui.draw_ui(surface, session, mouse=ui.overlay_button_rect().center)
    ui.draw_ui(surface, session, mouse=ui.overlay_home_button_rect().center)


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
