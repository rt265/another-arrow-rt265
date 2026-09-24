"""菜单页、信息栏与结算覆盖层的布局、文案与绘制冒烟测试。"""

from __future__ import annotations

import itertools
from dataclasses import replace

import pygame
import pytest

from another_arrow_rt265 import config, custom, icons, tutorial, ui, viewport
from another_arrow_rt265.board import Board
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

#: 几张菜单页：布局类测试逐张跑一遍，新页面加进来就自动被覆盖。
MENU_PAGES = (
    ui.start_page(3, 3),
    ui.about_page(3, 3),
    ui.settings_page(True, True),
    ui.settings_page(False, False),
    ui.custom_page(),
)


def _session() -> Session:
    """创建一个只有一关（因此也是最后一关）的会话。"""
    return Session(AREA, levels=(CLEARABLE_LEVEL,))


def _custom_session() -> Session:
    """创建一个“自定义模式”的会话：只有一关，而且是十字关卡（点哪都撞）。"""
    return Session(AREA, levels=(CROSS_LEVEL,), max_mistakes=1, is_custom=True)


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
    widest = ui._TEXT_VALUE.font().render(
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
    label = ui._TEXT_LABEL.font().render(
        config.GUIDE_TOGGLE_LABEL, True, config.COLOR_TEXT
    )

    assert pill.contains(track)
    assert track.centery == pill.centery
    assert label.get_width() + config.SWITCH_PADDING <= track.left - pill.left
    assert 2 * config.SWITCH_KNOB_RADIUS + 2 <= track.height, "滑块要放得进轨道"


def test_start_screen_hero_row_holds_both_modes() -> None:
    """首屏主按钮行是两个玩法入口：“关卡模式”（主按钮）+“自定义模式”，整行居中。

    事项 19 把“开始游戏”拆成了这两种玩法，它们是同一件事的两条路，
    因此同占主按钮那一行，而不是一个在主按钮位、另一个被挤到页脚。
    """
    levels = ui.start_button_rect()
    custom_mode = ui.custom_button_rect()
    footer = ui.settings_button_rect()

    assert levels.right < custom_mode.left, "两个入口不重叠"
    assert levels.left + custom_mode.right == config.WINDOW_WIDTH, "整行横向居中"
    # 整行仍然压在窗口中线上（与事项 25 的“首屏主按钮竖直居中”同一条口径）。
    assert levels.centery == config.WINDOW_HEIGHT // 2
    assert custom_mode.centery == levels.centery
    assert levels.size == custom_mode.size
    # 两个入口在中线上，下方不压到页脚的“设置 / 关于”。
    assert levels.bottom < footer.top


def test_start_screen_marks_the_level_mode_as_the_primary_button() -> None:
    """主按钮（金色）是“关卡模式”：自定义模式是另一条路，但不抢主按钮的强调色。"""
    page = ui.start_page(3, 3)
    hero = [
        button
        for button in page.buttons
        if button.placement is ui.MenuButtonPlacement.HERO
    ]

    assert [button.text for button in hero] == ["关卡模式", "自定义模式"]
    assert [button.action for button in hero] == ["start", "custom"]
    assert [button.primary for button in hero] == [True, False]


def test_start_screen_footer_holds_the_settings_and_about_buttons() -> None:
    """开始界面页脚是两个次要入口：设置与关于左右并排、整行居中，且不压主按钮。"""
    settings = ui.settings_button_rect()
    about = ui.about_button_rect()

    assert settings.right < about.left, "两个入口不重叠"
    assert settings.left + about.right == config.WINDOW_WIDTH, "整行居中"
    assert 0 <= settings.left and about.right <= config.WINDOW_WIDTH
    assert ui.start_button_rect().bottom < settings.top


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
    """菜单页的每一块内容（开关 / 卡片 / 提示行 / 按钮）都要落在窗口里且互不重叠。"""
    for page in MENU_PAGES:
        layout = ui.menu_layout(page)
        blocks = [*(rect for _, rect in layout.toggles), *layout.sections]
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


def test_menu_pages_put_their_footer_buttons_on_the_same_row() -> None:
    """各页的页脚按钮贴着同一条底线、整行居中：“设置 / 关于 / 返回”不会跳来跳去。"""
    rows: list[list[pygame.Rect]] = []
    for page in MENU_PAGES:
        rects = [
            rect
            for button, rect in ui.menu_layout(page).buttons
            if button.placement is ui.MenuButtonPlacement.FOOTER
        ]
        assert rects, page.title
        assert rects[0].left + rects[-1].right == config.WINDOW_WIDTH, page.title
        rows.append(rects)

    bottoms = {rect.bottom for rects in rows for rect in rects}
    assert len(bottoms) == 1, "各页的页脚按钮应该落在同一行"
    assert bottoms.pop() <= config.WINDOW_HEIGHT


def test_menu_page_buttons_come_from_the_page_description() -> None:
    """页面描述的开关 / 按钮与菜单页实际可点的区域一一对应（绘制与命中判定同源）。"""
    layout = ui.menu_layout(ui.start_page(3, 3))
    actions = {button.action for button, _ in layout.buttons}

    assert actions == {"start", "custom", "settings", "about"}
    assert ui.menu_layout(ui.about_page(3, 3)).buttons[0][0].action == "home"
    assert ui.menu_layout(ui.settings_page(True, False)).buttons[0][0].action == (
        "settings-back"
    )
    # 自定义模式的页脚从左到右是“返回 / 换一关 / 开始游戏”，开始游戏是主按钮。
    custom_buttons = ui.menu_layout(ui.custom_page()).buttons
    assert [button.action for button, _ in custom_buttons] == [
        "home",
        "custom-reroll",
        "custom-start",
    ]
    assert custom_buttons[-1][0].primary


def test_menu_page_text_fits_inside_its_section() -> None:
    """卡片的每一行都要放得下：卡片宽度是按最宽的一行定的，加字前先看这里。"""
    for page in (*MENU_PAGES, ui.about_page(99, 9)):
        for rect, section in zip(
            ui.menu_layout(page).sections, page.sections, strict=True
        ):
            caption = ui._TEXT_SECTION_TITLE.font().render(
                section.caption, True, config.COLOR_PRIMARY
            )
            assert caption.get_width() + 2 * ui._SECTION_PADDING <= rect.width

            for line in section.lines:
                label = ui._TEXT_RULE.font().render(line, True, config.COLOR_TEXT)
                # 正文比小标题多缩进 22px（圆点与间隙），两侧再各留一份卡片内边距。
                assert label.get_width() + 2 * ui._SECTION_PADDING + 22 <= rect.width, (
                    line
                )


# ---------------------------------------------------------------- 设置界面


def test_settings_page_has_one_switch_per_preference() -> None:
    """设置页就是两个开关（音乐 / 音效）：动作名与当前取值都如实来自入参。"""
    page = ui.settings_page(music_enabled=False, sound_enabled=True)

    assert [toggle.action for toggle in page.toggles] == [
        "toggle-music",
        "toggle-sound",
    ]
    assert [toggle.label for toggle in page.toggles] == ["背景音乐", "音效"]
    assert [toggle.enabled for toggle in page.toggles] == [False, True]
    assert [button.action for button in page.buttons] == ["settings-back"]


def test_settings_page_switch_states_reach_the_layout() -> None:
    """页面描述里的取值会原样传到布局结果里：绘制与命中判定读的是同一份。"""
    layout = ui.menu_layout(ui.settings_page(music_enabled=True, sound_enabled=False))
    music, sound = layout.toggles

    assert [(toggle.action, toggle.enabled) for toggle, _ in layout.toggles] == [
        ("toggle-music", True),
        ("toggle-sound", False),
    ]
    # 两行开关左对齐、宽度一致，并且按顺序自上而下排开。
    assert music[1].left == sound[1].left
    assert music[1].width == sound[1].width
    assert music[1].bottom < sound[1].top


def test_settings_switches_reuse_the_guide_toggle_component() -> None:
    """两处开关是同一个组件：轨道尺寸与滑块与右下角那颗开关完全一致。"""
    row = ui.menu_layout(ui.settings_page(True, True)).toggles[0][1]
    track = ui._switch_track_rect(row, ui._PAGE_TOGGLE_PADDING)

    assert track.size == ui._guide_toggle_track_rect().size
    assert track.centery == row.centery
    assert row.contains(track), "轨道要落在开关行里"


def test_settings_page_keeps_no_explanatory_text() -> None:
    """设置页只有开关与“返回”：界面不写多余的说明文字（用户 2026-09-22 明确要求）。

    这是与开始界面同一条产品规则（见 `test_start_screen_keeps_no_rule_text`）：
    讲玩法是第 1 关交互式教程的事，菜单页只放控件。用户删除文案是有意为之，
    不要凭“文档 / 变更记录里写过”把它加回来。
    """
    page = ui.settings_page(True, True)
    layout = ui.menu_layout(page)

    assert page.sections == ()
    assert page.hint is None
    assert layout.sections == ()
    assert layout.hint is None


@pytest.mark.parametrize("text", ["游戏中按 S 打开这一页", "设置关闭程序后恢复默认"])
def test_menu_page_hint_fits_inside_its_box(text: str) -> None:
    """提示行是居中画的，放不下就会溢出窗口：加字前先看这里。

    当前**没有**任何页面用到提示行（界面不写多余说明文字，见
    `test_settings_page_keeps_no_explanatory_text`），所以这里拿一个合成的页面
    把机制本身钉住：将来用户真的要求在某页加一行提示时，宽度有现成的判据。
    """
    page = ui.MenuPage(title="示例", subtitle="SAMPLE", hint=text)
    rect = ui.menu_layout(page).hint
    assert rect is not None

    label = ui._TEXT_HINT.font().render(text, True, config.COLOR_TEXT_MUTED)
    assert label.get_width() <= rect.width, text


def test_draw_settings_screen_renders_without_error() -> None:
    surface = _surface()
    row = ui.menu_layout(ui.settings_page(True, True)).toggles[0][1]

    ui.draw_settings_screen(surface, True, True)
    ui.draw_settings_screen(surface, False, False)
    ui.draw_settings_screen(surface, True, False, row.center)


def test_draw_settings_screen_shows_both_switch_positions() -> None:
    """两行开关各自跟着自己的取值：音乐开着时音效仍然可以是关的。"""
    music, sound = (
        rect for _, rect in ui.menu_layout(ui.settings_page(True, True)).toggles
    )

    on = _surface()
    ui.draw_settings_screen(on, True, False)
    off = _surface()
    ui.draw_settings_screen(off, False, True)

    assert _color_hits(on, config.SWITCH_TRACK_ON, music) > 0, "音乐开着时轨道是青绿色"
    assert _color_hits(on, config.SWITCH_TRACK_OFF, sound) > 0, "音效关着时轨道是暗灰"
    assert _color_hits(off, config.SWITCH_TRACK_ON, music) == 0
    assert _color_hits(off, config.SWITCH_TRACK_OFF, music) > 0
    assert pygame.image.tobytes(on, "RGB") != pygame.image.tobytes(off, "RGB")


def test_draw_settings_screen_covers_the_whole_window() -> None:
    surface = _surface()
    surface.fill((255, 0, 255))

    ui.draw_settings_screen(surface, True, True)

    assert surface.get_at((2, 2))[:3] != (255, 0, 255)
    assert surface.get_at((config.WINDOW_WIDTH - 3, 2))[:3] != (255, 0, 255)
    assert surface.get_at((2, config.WINDOW_HEIGHT - 3))[:3] != (255, 0, 255), (
        "设置界面应该连背景一起画，不留未覆盖的角落"
    )


# ---------------------------------------------------------------- 自定义模式


def _slider_rows(
    size: int = 8, arrows: int = 20, maximum: int = 32
) -> tuple[ui.SliderRow, ...]:
    """返回自定义模式两行滑动条的几何（量程上限可以直接指定，便于做对照）。"""
    return ui.custom_slider_rows(size, arrows, maximum)


def test_custom_page_only_holds_its_footer_buttons() -> None:
    """自定义页只有标题与页脚三个按钮：滑动条与实时预览另有自己的几何函数。"""
    page = ui.custom_page()
    layout = ui.menu_layout(page)

    assert page.sections == ()
    assert page.toggles == ()
    assert page.hint is None
    assert layout.sections == ()
    assert layout.hint is None
    assert [button.text for button, _ in layout.buttons] == [
        "返回",
        "换一关",
        "开始游戏",
    ]
    # 主按钮是“开始游戏”，因此 Enter / 空格进来就是开一局。
    assert page.default_action() == "custom-start"


def test_custom_slider_rows_follow_the_parameters() -> None:
    """两行滑动条把参数、量程与当前取值如实带出来，并且都落在窗口里、互不重叠。"""
    size_row, arrow_row = _slider_rows(size=10, arrows=40, maximum=50)

    assert (size_row.key, size_row.label) == ("size", "棋盘边长")
    assert (size_row.value, size_row.minimum, size_row.maximum) == (
        10,
        custom.MIN_SIZE,
        custom.MAX_SIZE,
    )
    assert (arrow_row.key, arrow_row.label) == ("arrows", "箭头数量")
    assert (arrow_row.value, arrow_row.minimum, arrow_row.maximum) == (
        40,
        custom.MIN_ARROWS,
        50,
    )
    for row in (size_row, arrow_row):
        assert 0 <= row.rect.left and row.rect.right <= config.WINDOW_WIDTH
        assert 0 <= row.rect.top and row.rect.bottom <= config.WINDOW_HEIGHT
        assert row.rect.contains(row.track), "轨道要落在那一行里面"
        assert row.track.centery == row.rect.centery
    assert size_row.rect.right < arrow_row.rect.left, "两行左右并排、不重叠"
    assert size_row.rect.width == arrow_row.rect.width


def test_custom_slider_track_ignores_the_readout_width() -> None:
    """读数位数变了（8 与 128）轨道也得纹丝不动：否则拖动时量程会跟着变来变去。"""
    narrow = _slider_rows(arrows=8, maximum=128)[1].track
    wide = _slider_rows(arrows=128, maximum=128)[1].track

    assert narrow == wide


def test_custom_slider_value_round_trips() -> None:
    """“点哪里取哪个值”与“取值画在哪儿”互逆，并且两端把量程夹得死死的。"""
    row = _slider_rows(arrows=20, maximum=50)[1]
    left, right = ui._slider_thumb_span(row)

    assert ui.slider_value(row, left) == row.minimum
    assert ui.slider_value(row, right) == row.maximum
    assert ui.slider_value(row, left - 500) == row.minimum, "拖到轨道外面也夹回量程"
    assert ui.slider_value(row, right + 500) == row.maximum

    for value in (1, 7, 20, 49, 50):
        moved = replace(row, value=value)
        thumb = ui._slider_thumb_x(moved)
        # 量程比像素还密时（128 档挤在一百多像素里）来回换算最多差一档。
        assert abs(ui.slider_value(moved, thumb) - value) <= 1

    # 取值越大滑块越靠右。
    positions = [ui._slider_thumb_x(replace(row, value=value)) for value in (1, 20, 50)]
    assert positions == sorted(positions)
    assert positions[0] < positions[-1]


def test_custom_preview_stays_clear_of_the_controls() -> None:
    """预览棋盘不压标题、两行滑动条与页脚按钮：预览区取的是中间那块留白。"""
    rows = [row.rect for row in _slider_rows()]
    footer = [rect for _, rect in ui.menu_layout(ui.custom_page()).buttons]
    subtitle = viewport.y(ui._CUSTOM_SUBTITLE_Y)

    for size in range(custom.MIN_SIZE, custom.MAX_SIZE + 1):
        settings = custom.CustomLevel(size, custom.default_arrows(size))
        panel = Board(settings.level, ui.custom_preview_area()).panel_rect

        assert panel.top >= subtitle, f"{size}x{size} 的预览压到了标题"
        assert panel.left >= 0 and panel.right <= config.WINDOW_WIDTH
        for rect in (*rows, *footer):
            assert not panel.colliderect(rect), f"{size}x{size} 的预览压到了控件"


def test_draw_custom_screen_renders_without_error() -> None:
    surface = _surface()

    for size in (custom.MIN_SIZE, custom.DEFAULT_SIZE, custom.MAX_SIZE):
        settings = custom.CustomLevel(size, custom.default_arrows(size))
        row = _slider_rows(settings.size, settings.arrows, settings.max_arrows)[0].rect
        ui.draw_custom_screen(surface, settings)
        ui.draw_custom_screen(surface, settings, row.center)


def test_draw_custom_screen_covers_the_whole_window() -> None:
    """自定义画面连背景一起画（预览棋盘由 ``Game`` 贴在中间那块留白上）。"""
    surface = _surface()
    surface.fill((255, 0, 255))

    ui.draw_custom_screen(surface, custom.CustomLevel())

    assert surface.get_at((2, 2))[:3] != (255, 0, 255)
    assert surface.get_at((config.WINDOW_WIDTH - 3, 2))[:3] != (255, 0, 255)
    assert surface.get_at((2, config.WINDOW_HEIGHT - 3))[:3] != (255, 0, 255), (
        "自定义画面应该连背景一起画，不留未覆盖的角落"
    )


def test_custom_slider_fill_follows_the_value() -> None:
    """滑过的那一段填主色：取值越大填得越长（“调到哪儿了”一眼看得出来）。"""
    row = _slider_rows(custom.MIN_SIZE, 1, 32)[0]
    small, large = _surface(), _surface()

    ui.draw_custom_screen(small, custom.CustomLevel(custom.MIN_SIZE, 1))
    ui.draw_custom_screen(large, custom.CustomLevel(custom.MAX_SIZE, 1))

    assert _color_hits(small, config.SLIDER_TRACK_FILL, row.rect) < _color_hits(
        large, config.SLIDER_TRACK_FILL, row.rect
    )
    # 没滑到的那一段仍然是底色（两档都还剩得下一点）。
    assert _color_hits(large, config.SLIDER_TRACK_REST, row.rect) > 0


def test_level_chip_reports_the_custom_level() -> None:
    """自定义关卡报“自定义”：它只有一关，报“1 / 1”是误导。"""
    assert ui.level_chip_text(_session()) == "1 / 1"
    assert ui.level_chip_text(_custom_session()) == "自定义"


def test_level_chip_has_room_for_the_custom_label() -> None:
    """信息栏第一段要放得下“自定义”（三个 24 号字 + 两侧留白）。"""
    level_chip = ui.hud_chip_rects()[0]
    label = ui._TEXT_VALUE.font().render("自定义", True, config.COLOR_PRIMARY)

    assert label.get_width() + 2 * ui._HUD_CHIP_PADDING <= level_chip.width


def test_custom_result_texts() -> None:
    """自定义关卡的结算文案不提“第 N 关 / 全部 N 关”：它本来就是唯一的一关。"""
    session = _custom_session()
    session.click(session.board.cell_rect(0, 1).center)
    assert session.status is GameStatus.FAILED

    assert ui._result_message(session) == "失误次数已用完，本关未通过"
    assert ui.overlay_button_text(session) == "重试本关"

    session.status = GameStatus.LEVEL_CLEARED
    assert ui._result_message(session) == "自定义关卡已通关"
    assert ui.overlay_button_text(session) == "再玩一次"


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

    assert _color_hits(on, config.SWITCH_TRACK_ON, pill) > 0, "打开后轨道是青绿色"
    assert _color_hits(off, config.SWITCH_TRACK_OFF, pill) > 0, "关着时轨道是暗灰"
    assert _color_hits(off, config.SWITCH_TRACK_ON, pill) == 0
    assert pygame.image.tobytes(on, "RGB") != pygame.image.tobytes(off, "RGB")


def test_draw_guide_toggle_highlights_on_hover() -> None:
    pill = ui.guide_toggle_rect()
    idle = _surface()
    ui.draw_guide_toggle(idle, False)
    hovered = _surface()
    ui.draw_guide_toggle(hovered, False, pill.center)

    assert pygame.image.tobytes(idle, "RGB") != pygame.image.tobytes(hovered, "RGB")


def test_guide_toggle_knob_edges_are_anti_aliased() -> None:
    """开关滑块与轨道之间要有过渡色：滑块是抗锯齿贴图画上去的，不是硬边圆。

    取样框取轨道内部一段（避开轨道自身的圆角）：硬边画法在这里只会出现
    “轨道色 + 滑块色”两种颜色。
    """
    surface = _surface()
    surface.fill(config.SWITCH_TRACK_OFF)
    ui.draw_guide_toggle(surface, False)

    box = ui._guide_toggle_track_rect().inflate(-12, -6)
    colors = {
        surface.get_at((x, y))[:3]
        for x in range(box.left, box.right)
        for y in range(box.top, box.bottom)
    }
    assert config.SWITCH_TRACK_OFF in colors
    assert config.SWITCH_KNOB_OFF in colors
    assert len(colors) > 2, "滑块边缘没有过渡色，说明又画成了硬边"


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
    """几张菜单页的内容不同，不能画出同一张图（防止画错页面）。"""
    session = _session()
    rendered = []
    for draw in (
        lambda surface: ui.draw_start_screen(surface, session),
        lambda surface: ui.draw_about_screen(surface, session),
        lambda surface: ui.draw_settings_screen(surface, True, True),
        lambda surface: ui.draw_custom_screen(surface, custom.CustomLevel()),
    ):
        surface = _surface()
        draw(surface)
        rendered.append(pygame.image.tobytes(surface, "RGB"))

    assert len(set(rendered)) == len(rendered)


def test_draw_background_paints_one_flat_color() -> None:
    """扁平化之后背景是一块纯色：四角与中心必须完全一致。

    原来这里是“竖直渐变 + 径向柔光”，层次改由“块与块的明度差 + 1px 描边”表达之后，
    背景不再参与制造立体感，这条测试就是那次改动的判据。
    """
    surface = _surface()
    ui.draw_background(surface)

    corners = (
        (2, 2),
        (config.WINDOW_WIDTH - 3, 2),
        (2, config.WINDOW_HEIGHT - 3),
        (config.WINDOW_WIDTH - 3, config.WINDOW_HEIGHT - 3),
        (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2),
    )
    for corner in corners:
        assert surface.get_at(corner)[:3] == config.COLOR_BACKGROUND, corner


# ---------------------------------------------------------------- 扁平化


def test_hud_is_one_bar_with_three_dividers() -> None:
    """信息栏是一条通栏：整条铺底色 + 底边一条横线，四段分区之间用竖线隔开。

    扁平化之前这里是四块各自带描边的卡片。现在栏内只有“一条底 + 三条线”，
    因此分区自身不再有边框，栏外也不会出现栏的底色。
    """
    surface = _surface()
    surface.fill(config.COLOR_BACKGROUND)
    ui.draw_hud(surface, _session())

    bar = ui.hud_rect()
    # 整条栏都铺上了底色。
    assert surface.get_at((bar.left + 1, bar.centery))[:3] == config.COLOR_PANEL
    assert surface.get_at((bar.right - 2, bar.top + 2))[:3] == config.COLOR_PANEL
    # 底边是一条描边色的横线，线下面立刻回到背景色。
    assert (
        surface.get_at((bar.centerx, bar.bottom - 1))[:3] == config.COLOR_PANEL_BORDER
    )
    assert surface.get_at((bar.centerx, bar.bottom))[:3] == config.COLOR_BACKGROUND

    dividers = ui.hud_dividers()
    sections = ui.hud_chip_rects()
    assert len(dividers) == len(sections) - 1
    for (x, top, bottom), (previous, current) in zip(
        dividers, itertools.pairwise(sections), strict=True
    ):
        assert previous.right < x < current.left, "分隔线落在相邻两段分区的空隙里"
        assert bar.top < top < bottom < bar.bottom
        assert surface.get_at((x, (top + bottom) // 2))[:3] == config.COLOR_PANEL_BORDER


def test_chrome_components_are_flat_without_shadow_or_gradient() -> None:
    """组件只有“纯色填充 + 1px 描边”：外侧没有投影，内部没有渐变。

    投影是扁平化删掉的第一件事——旧实现会在按钮外侧叠 4 层深色；
    渐变则会让同一行出现多种填充色。
    """
    surface = _surface()
    surface.fill(config.COLOR_BACKGROUND)
    ui.draw_hud(surface, _session())

    button = ui.restart_button_rect()
    # 1) 紧贴按钮外侧的像素必须正好是信息栏自己的底色。
    for point in (
        (button.left - 2, button.centery),
        (button.right + 1, button.centery),
        (button.centerx, button.top - 2),
        (button.centerx, button.bottom + 1),
    ):
        assert surface.get_at(point)[:3] == config.COLOR_PANEL, point

    # 2) 贴着上边缘、避开左右圆角与按钮文字的一条横线只有一种颜色。
    fills = {
        surface.get_at((x, button.top + 2))[:3]
        for x in range(button.left + 20, button.right - 20)
    }
    assert fills == {config.COLOR_BUTTON}


def test_buttons_share_one_corner_radius() -> None:
    """按钮不再按高度取一半做成胶囊，而是与其它组件同一档圆角。

    胶囊的两肩会鼓出来，因此“距左边缘 1/4 圆角、距上边缘 2/3 圆角”这个点
    落在统一圆角之内、却在胶囊之外。改回 ``rect.height // 2`` 时这条会报警。
    """
    surface = _surface()
    surface.fill(config.COLOR_BACKGROUND)
    ui.draw_hud(surface, _session())

    radius = viewport.s(config.UI_RADIUS)
    for button in (ui.restart_button_rect(), ui.hud_home_button_rect()):
        shoulder = (button.left + radius // 4, button.top + 2 * radius // 3)
        assert surface.get_at(shoulder)[:3] == config.COLOR_BUTTON, shoulder
        corner = (button.left + 1, button.top + 1)
        assert surface.get_at(corner)[:3] == config.COLOR_PANEL, "四角要被圆角切掉"


def test_menu_title_has_no_glow_copy() -> None:
    """菜单页标题只有一层文字，不再在下面垫一份半透明的金色副本。

    判据：标题所在的那几行只能是“文字色 ↔ 背景色”之间的过渡（各通道按同一比例变化），
    金色副本混进背景后红色分量会明显偏高，一眼就能分辨。
    """
    surface = _surface()
    ui.draw_start_screen(surface, _session())

    title = ui._TEXT_HERO.font().render(ui._GAME_TITLE, True, config.COLOR_TEXT)
    rect = title.get_rect(
        center=(config.WINDOW_WIDTH // 2, viewport.y(ui._PAGE_TITLE_Y))
    )
    back = config.COLOR_BACKGROUND
    text = config.COLOR_TEXT
    for y in range(rect.top, min(rect.bottom + 5, config.WINDOW_HEIGHT)):
        for x in range(rect.left, rect.right):
            pixel = surface.get_at((x, y))[:3]
            ratios = [
                (pixel[index] - back[index]) / (text[index] - back[index])
                for index in range(3)
            ]
            assert max(ratios) - min(ratios) <= 0.06, (x, y, pixel)


# ---------------------------------------------------------------- 窗口缩放

#: 窗口自由缩放后要逐一套一遍的窗口尺寸：设计尺寸、正方形放大、横幅、竖屏。
WINDOW_SIZES = ((720, 720), (1080, 1080), (1440, 900), (900, 1440))


@pytest.fixture(params=WINDOW_SIZES)
def window(request: pytest.FixtureRequest) -> viewport.Viewport:
    """把当前视口切到某个窗口尺寸（用例结束后由 ``conftest`` 复位）。

    布局常量都是按设计尺寸写的绝对值，这里的尺寸矩阵负责证明它们换个窗口仍然成立。
    """
    return viewport.set_current(viewport.Viewport.fit(request.param))


def test_hud_row_fills_the_design_box_at_any_window_size(
    window: viewport.Viewport,
) -> None:
    """信息栏整行仍然“左贴齐、右贴齐”，只是整行按视口等比放大。"""
    row = (ui.hud_home_button_rect(), *ui.hud_chip_rects(), ui.restart_button_rect())

    assert row[0].left == window.x(config.HUD_PADDING)
    assert row[-1].right == window.x(config.WINDOW_WIDTH - config.HUD_PADDING)
    for previous, current in itertools.pairwise(row):
        assert previous.right <= current.left
    assert all(ui.hud_rect().contains(rect) for rect in row)


def test_board_area_follows_the_window_size(window: viewport.Viewport) -> None:
    """棋盘可用区域等比缩放，并且始终留在设计框内（不会跑到留白上）。"""
    area = ui.board_area()
    top = config.HUD_HEIGHT + config.BOARD_TOP_GAP

    assert area.left == window.x(config.HUD_PADDING)
    assert area.top == window.y(top)
    assert area.width == window.s(config.WINDOW_WIDTH - 2 * config.HUD_PADDING)
    assert area.bottom == window.y(config.WINDOW_HEIGHT - config.BOARD_MARGIN)
    assert window.rect(0, 0, *config.WINDOW_SIZE).contains(area)


def test_menu_pages_stay_centred_and_inside_the_design_box(
    window: viewport.Viewport,
) -> None:
    """菜单页的各块仍然居中、不越界：排版算的是设计坐标，最后统一映射。"""
    box = window.rect(0, 0, *config.WINDOW_SIZE)

    for page in MENU_PAGES:
        layout = ui.menu_layout(page)
        blocks = [
            *(rect for _, rect in layout.toggles),
            *layout.sections,
            *(rect for _, rect in layout.buttons),
        ]
        if layout.hint is not None:
            blocks.append(layout.hint)
        for rect in blocks:
            assert box.contains(rect), page.title

    levels, custom_mode = ui.start_button_rect(), ui.custom_button_rect()
    # 主按钮行整行居中：两侧留白相等（取整可能差一个像素）。
    assert abs(levels.left - (window.size[0] - custom_mode.right)) <= 1
    assert levels.centery == window.center()[1]
    assert levels.right < custom_mode.left


def test_guide_toggle_never_covers_a_cell_at_any_window_size(
    window: viewport.Viewport,
) -> None:
    """“开关在棋盘外面”这条关系与窗口尺寸无关：两者按同一个系数缩放。"""
    toggle = ui.guide_toggle_rect()
    for index in range(len(LEVELS)):
        board = Session(ui.board_area(), level_index=index).board
        for row in range(board.rows):
            for col in range(board.cols):
                assert not toggle.colliderect(board.cell_rect(row, col)), (
                    f"第 {index + 1} 关的 ({row}, {col}) 被辅助线开关压住了"
                )


def test_custom_screen_keeps_its_layout_at_any_window_size(
    window: viewport.Viewport,
) -> None:
    """自定义模式的滑动条与预览也一起缩放：都在设计框里，且预览不压控件。"""
    box = window.rect(0, 0, *config.WINDOW_SIZE)
    settings = custom.CustomLevel(8, 26)
    rows = [row.rect for row in ui.custom_slider_rows(8, 26, 32)]
    footer = [rect for _, rect in ui.menu_layout(ui.custom_page()).buttons]
    panel = Board(settings.level, ui.custom_preview_area()).panel_rect

    assert box.contains(ui.custom_preview_area())
    for rect in (*rows, *footer):
        assert box.contains(rect)
        assert not panel.colliderect(rect), "预览棋盘不该压到滑动条或页脚按钮"


def test_text_is_rendered_at_the_scaled_size() -> None:
    """窗口放大后文字是**按更大的字号重新渲染**的，而不是把位图拉大（后者会糊）。"""
    base = ui._TEXT_BODY.font().render("窗口缩放", True, config.COLOR_TEXT)

    viewport.set_current(viewport.Viewport.fit((1440, 1440)))
    doubled = ui._TEXT_BODY.font().render("窗口缩放", True, config.COLOR_TEXT)

    assert doubled.get_height() > base.get_height()
    assert doubled.get_width() == pytest.approx(2 * base.get_width(), rel=0.15)


def test_a_window_smaller_than_the_design_keeps_the_full_size() -> None:
    """窗口小于设计尺寸时只裁掉多出来的部分，界面尺寸不变（不缩小到看不清）。"""
    design = (ui.hud_home_button_rect(), ui.restart_button_rect())

    viewport.set_current(viewport.Viewport.fit((560, 560)))

    assert viewport.current().scale == config.MIN_SCALE
    smaller = (ui.hud_home_button_rect(), ui.restart_button_rect())
    assert smaller[0].size == design[0].size
    assert smaller[1].size == design[1].size


def test_scaled_drawing_covers_the_whole_window(window: viewport.Viewport) -> None:
    """背景要铺满整个窗口（含留白），不能只在设计框里画一块。"""
    width, height = window.size
    surface = pygame.Surface(window.size)
    surface.fill((255, 0, 255))

    ui.draw_start_screen(surface, _session())

    corners = ((2, 2), (width - 3, 2), (2, height - 3), (width - 3, height - 3))
    for corner in corners:
        assert surface.get_at(corner)[:3] != (255, 0, 255), corner
