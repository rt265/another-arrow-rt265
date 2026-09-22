"""菜单页、信息栏与结算覆盖层的布局、文案与绘制冒烟测试。"""

from __future__ import annotations

import itertools

import pygame
import pytest

from another_arrow_rt265 import config, icons, tutorial, ui
from another_arrow_rt265.levels import LEVELS, Level
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


# ---------------------------------------------------------------- 辅助线开关


def _color_hits(surface: pygame.Surface, color: config.Color, area: pygame.Rect) -> int:
    """数区域里正好等于 ``color`` 的像素个数（开关是不带抗锯齿的纯几何绘制）。"""
    return sum(
        1
        for x in range(area.left, area.right)
        for y in range(area.top, area.bottom)
        if surface.get_at((x, y))[:3] == color
    )


def test_guide_toggle_sits_in_the_bottom_right_corner() -> None:
    """开关摆在窗口右下角，且不压信息栏、重新开始按钮与教程提示条。"""
    toggle = ui.guide_toggle_rect()

    assert toggle.centerx > config.WINDOW_WIDTH // 2
    assert toggle.centery > config.WINDOW_HEIGHT // 2
    assert config.WINDOW_WIDTH - toggle.right <= config.HUD_PADDING
    assert config.WINDOW_HEIGHT - toggle.bottom <= 16, "它要贴着底边：下面没地方了"
    assert not toggle.colliderect(ui.hud_rect())
    assert not toggle.colliderect(ui.restart_button_rect())
    assert not toggle.colliderect(ui.tutorial_panel_rect())


def test_guide_toggle_never_covers_a_cell() -> None:
    """开关必须落在棋盘外面：最大的棋盘（6x6）最后一排格子一直铺到 y=674。

    垂直留白因此只有 8px，这条测试对内置关卡逐一核对，以后调棋盘布局、
    调格子尺寸或改开关尺寸时都会第一时间报警。
    """
    toggle = ui.guide_toggle_rect()
    for index in range(len(LEVELS)):
        board = Session(ui.board_area(), level_index=index).board
        for row in range(board.rows):
            for col in range(board.cols):
                assert not toggle.colliderect(board.cell_rect(row, col)), (
                    f"第 {index + 1} 关的 ({row}, {col}) 被辅助线开关压住了"
                )


def test_guide_toggle_content_fits_inside_the_pill() -> None:
    """胶囊里“文字 + 轨道”排得下：加字或改宽度前先看这里。"""
    pill = ui.guide_toggle_rect()
    track = ui._guide_toggle_track_rect()
    label = ui._font(ui._FONT_LABEL).render(
        config.GUIDE_TOGGLE_LABEL, True, config.COLOR_TEXT
    )

    assert pill.contains(track)
    assert track.centery == pill.centery
    assert label.get_width() + config.GUIDE_TOGGLE_PADDING <= track.left - pill.left
    assert 2 * config.GUIDE_TOGGLE_KNOB_RADIUS + 2 <= track.height, "滑块要放得进轨道"


def test_start_button_is_centered_above_the_footer_button() -> None:
    button = ui.start_button_rect()
    footer = ui.about_button_rect()

    assert button.centerx == config.WINDOW_WIDTH // 2
    assert 0 <= button.left and button.right <= config.WINDOW_WIDTH
    # 主按钮位于画面中上部，且不压到页脚的“关于”。
    assert button.centery < config.WINDOW_HEIGHT * 0.6
    assert button.bottom < footer.top


def test_start_screen_keeps_no_rule_text() -> None:
    """首屏不再用文字讲规则：说明卡片与提示行都让给第 1 关的交互式教程。"""
    page = ui.start_page(3, 3)
    layout = ui.menu_layout(page)

    assert page.sections == ()
    assert page.hint is None
    assert layout.sections == ()
    assert layout.hint is None


def test_gameplay_help_lives_in_the_tutorial() -> None:
    """玩法说明不写在菜单页上（首屏与“关于”都没写），而是由第 1 关的教程承担。"""
    texts = " ".join(tutorial._TEXTS.values())

    assert "飞出棋盘" in texts
    assert "失误" in texts


def test_about_screen_only_lists_credits() -> None:
    """“关于”界面只放制作信息（版本 / 技术栈 / 许可 / 仓库），不重复玩法与操作说明。"""
    page = ui.about_page(3, 3)
    lines = [line for section in page.sections for line in section.lines]

    assert [section.caption for section in page.sections] == ["制作信息"]
    assert any(f"版本 {config.VERSION}" in line for line in lines)
    assert any("pygame-ce" in line.lower() for line in lines)
    assert any("MIT License" in line for line in lines)
    assert any("github.com" in line for line in lines)
    assert not any("辅助线" in line or "快捷键" in line for line in lines)


# ---------------------------------------------------------------- 菜单页


def test_menu_pages_stack_their_blocks_inside_the_window() -> None:
    """菜单页的每一块内容（卡片 / 提示行 / 按钮）都要落在窗口里且互不重叠。"""
    for page in (ui.start_page(3, 3), ui.about_page(3, 3)):
        layout = ui.menu_layout(page)
        blocks = list(layout.sections)
        if layout.hint is not None:
            blocks.append(layout.hint)
        blocks.extend(rect for _, rect in layout.buttons)

        for rect in blocks:
            assert rect.left >= 0 and rect.right <= config.WINDOW_WIDTH, page.title
            assert rect.top >= 0 and rect.bottom <= config.WINDOW_HEIGHT, page.title

        # 自上而下排开：相邻两块不能叠在一起（提示行贴着卡片、按钮贴着底部）。
        for previous, current in itertools.pairwise(
            sorted(blocks, key=lambda rect: (rect.top, rect.left))
        ):
            assert not previous.colliderect(current), f"{page.title} 上有内容重叠"


def test_menu_pages_share_the_same_footer_button_spot() -> None:
    """两个菜单页的页脚按钮落在同一位置，返回 / 次要入口不会跳来跳去。"""
    about = ui.about_button_rect()
    back = ui.about_back_button_rect()

    assert about == back
    assert about.centerx == config.WINDOW_WIDTH // 2
    assert about.bottom <= config.WINDOW_HEIGHT


def test_menu_page_buttons_come_from_the_page_description() -> None:
    """页面描述的按钮与菜单页实际可点的区域一一对应（绘制与命中判定同源）。"""
    layout = ui.menu_layout(ui.start_page(3, 3))
    actions = {button.action for button, _ in layout.buttons}

    assert actions == {"start", "about"}
    assert ui.menu_layout(ui.about_page(3, 3)).buttons[0][0].action == "home"


def test_menu_page_text_fits_inside_its_section() -> None:
    """卡片的每一行都要放得下：卡片宽度是按最宽的一行定的，加字前先看这里。"""
    for page in (ui.start_page(3, 3), ui.about_page(99, 9)):
        for rect, section in zip(
            ui.menu_layout(page).sections, page.sections, strict=True
        ):
            caption = ui._font(ui._FONT_RULE_TITLE).render(
                section.caption, True, config.COLOR_PRIMARY
            )
            assert caption.get_width() + 2 * ui._SECTION_PADDING <= rect.width

            for line in section.lines:
                label = ui._font(ui._FONT_RULE).render(line, True, config.COLOR_TEXT)
                # 正文比小标题多缩进 22px（圆点与间隙），两侧再各留一份卡片内边距。
                assert label.get_width() + 2 * ui._SECTION_PADDING + 22 <= rect.width, (
                    line
                )


# ---------------------------------------------------------------- 文案


def test_about_page_reports_the_version_but_not_the_session_numbers() -> None:
    """“关于”界面报版本号（跟着 ``config`` 走），但不再报关卡数与失误上限。"""
    lines = [
        line for section in ui.about_page(12, 5).sections for line in section.lines
    ]

    assert any(f"版本 {config.VERSION}" in line for line in lines)
    assert not any("共" in line and "关" in line for line in lines)


def test_menu_pages_pick_a_default_action_for_enter() -> None:
    """Enter / 空格触发页面的默认按钮：开始界面是“开始游戏”，关于界面是“返回”。"""
    assert ui.start_page(3, 3).default_action() == "start"
    assert ui.about_page(3, 3).default_action() == "home"


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


def test_draw_guide_toggle_shows_both_positions() -> None:
    """开关的“开 / 关”两档在画面上真的不一样：轨道换颜色，滑块也换边。"""
    pill = ui.guide_toggle_rect()

    on = _surface()
    ui.draw_guide_toggle(on, True)
    off = _surface()
    ui.draw_guide_toggle(off, False)

    assert _color_hits(on, config.GUIDE_TOGGLE_TRACK_ON, pill) > 0, "打开后轨道是青绿色"
    assert _color_hits(off, config.GUIDE_TOGGLE_TRACK_OFF, pill) > 0, "关着时轨道是暗灰"
    assert _color_hits(off, config.GUIDE_TOGGLE_TRACK_ON, pill) == 0
    assert pygame.image.tobytes(on, "RGB") != pygame.image.tobytes(off, "RGB")


def test_draw_guide_toggle_highlights_on_hover() -> None:
    pill = ui.guide_toggle_rect()
    idle = _surface()
    ui.draw_guide_toggle(idle, False)
    hovered = _surface()
    ui.draw_guide_toggle(hovered, False, pill.center)

    assert pygame.image.tobytes(idle, "RGB") != pygame.image.tobytes(hovered, "RGB")


@pytest.mark.parametrize("status", list(GameStatus))
def test_draw_ui_renders_in_every_state(status: GameStatus) -> None:
    surface = _surface()
    session = _session()
    session.status = status

    ui.draw_ui(surface, session)
    ui.draw_ui(surface, session, mouse=ui.overlay_button_rect().center)
    ui.draw_ui(surface, session, mouse=ui.overlay_home_button_rect().center)
    ui.draw_ui(surface, session, show_guides=True)
    ui.draw_ui(surface, session, ui.guide_toggle_rect().center, show_guides=True)


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


def test_draw_about_screen_renders_without_error() -> None:
    surface = _surface()
    session = _session()

    ui.draw_about_screen(surface, session)
    ui.draw_about_screen(surface, session, mouse=ui.about_back_button_rect().center)


def test_draw_about_screen_covers_the_whole_window() -> None:
    surface = _surface()
    surface.fill((255, 0, 255))

    ui.draw_about_screen(surface, _session())

    assert surface.get_at((2, 2))[:3] != (255, 0, 255), (
        "关于界面应该连背景一起画，不留未覆盖的角落"
    )


def test_menu_pages_are_visually_distinct() -> None:
    """两张菜单页的内容不同，不能画出同一张图（防止画错页面）。"""
    start = _surface()
    about = _surface()
    session = _session()

    ui.draw_start_screen(start, session)
    ui.draw_about_screen(about, session)

    assert pygame.image.tobytes(start, "RGB") != pygame.image.tobytes(about, "RGB")


def test_draw_background_paints_a_top_to_bottom_gradient() -> None:
    surface = _surface()
    ui.draw_background(surface)

    top = surface.get_at((4, 4))[:3]
    bottom = surface.get_at((4, config.WINDOW_HEIGHT - 4))[:3]
    assert sum(top) > sum(bottom), "背景应当自上而下由亮转暗"
