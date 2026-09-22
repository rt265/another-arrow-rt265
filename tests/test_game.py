"""窗口级测试：画面切换、事件分发、按钮点击与结算流转。

这些测试在 SDL 的 dummy 驱动下创建真实窗口（见 ``conftest.py``），
并通过 ``pygame.event.post()`` 投递鼠标与键盘事件，尽量贴近真实操作路径。
"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, ui, viewport
from another_arrow_rt265.audio import Audio, Cue
from another_arrow_rt265.board import Board, ClickResult
from another_arrow_rt265.game import Game, Scene
from another_arrow_rt265.levels import LEVELS
from another_arrow_rt265.session import GameStatus, Session


@pytest.fixture
def game() -> Game:
    """一个使用内置关卡、已经离开开始界面的窗口（停在第 1 关）。"""
    instance = Game()
    instance.start()
    return instance


def _post_click(game: Game, position: tuple[int, int]) -> None:
    """投递一次左键点击并立刻处理事件队列。"""
    pygame.event.post(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": position, "button": 1})
    )
    game._handle_events()


def _post_key(game: Game, key: int) -> None:
    """投递一次按键并立刻处理事件队列。"""
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": key}))
    game._handle_events()


def _clear_board(board: Board) -> None:
    """依次清掉所有“前方畅通”的箭头，直到棋盘清空。"""
    while not board.is_cleared:
        for arrow in board.arrows:
            if board.is_path_clear(arrow):
                assert board.handle_click(
                    board.cell_rect(arrow.row, arrow.col).center
                ) is (ClickResult.CLEARED)
                break
        else:
            msg = "棋盘上已经没有可清除的箭头"
            raise AssertionError(msg)


def _settle(session: Session) -> None:
    """按固定帧长推进，直到弹出结算界面。"""
    for _ in range(config.FPS * 3):
        if not session.is_playing:
            return
        session.update(1.0 / config.FPS)
    msg = "会话始终没有进入结算状态"
    raise AssertionError(msg)


def _waste_all_mistakes(session: Session) -> None:
    """反复点击同一个被阻挡的箭头，直到失误次数耗尽、本关失败。"""
    while session.is_playing:
        blocked = next(
            (
                arrow
                for arrow in session.board.arrows
                if not session.board.is_path_clear(arrow)
            ),
            None,
        )
        assert blocked is not None, "这一关没有可以制造失误的箭头"
        session.click(session.board.cell_rect(blocked.row, blocked.col).center)
    assert session.status is GameStatus.FAILED


def test_clicking_the_board_clears_a_free_arrow(game: Game) -> None:
    session = game.session
    initial = session.arrows_left

    _post_click(game, session.board.cell_rect(0, 1).center)
    assert session.arrows_left == initial - 1


def test_clicking_the_restart_button_restores_the_level(game: Game) -> None:
    session = game.session
    initial = session.arrows_left

    _post_click(game, session.board.cell_rect(0, 1).center)
    assert session.arrows_left == initial - 1

    _post_click(game, ui.restart_button_rect().center)
    assert session.arrows_left == initial
    assert session.mistakes_left == session.max_mistakes
    assert session.status is GameStatus.PLAYING
    assert session.board.flying == []


def test_clicking_empty_space_does_not_cost_a_mistake(game: Game) -> None:
    session = game.session
    _post_click(game, (10, config.WINDOW_HEIGHT // 2))
    assert session.mistakes_left == session.max_mistakes


def test_restart_key_restarts_the_level(game: Game) -> None:
    session = game.session
    initial = session.arrows_left

    _post_click(game, session.board.cell_rect(0, 1).center)
    _post_key(game, pygame.K_r)
    assert session.arrows_left == initial
    assert session.mistakes_left == session.max_mistakes


def test_overlay_button_click_advances_to_the_next_level(game: Game) -> None:
    session = game.session
    _clear_board(session.board)
    _settle(session)
    assert session.status is GameStatus.LEVEL_CLEARED

    _post_click(game, ui.overlay_button_rect().center)
    assert session.level_number == 2
    assert session.status is GameStatus.PLAYING
    assert session.mistakes_left == session.max_mistakes


def test_enter_advances_from_the_result_screen(game: Game) -> None:
    session = game.session
    _clear_board(session.board)
    _settle(session)

    _post_key(game, pygame.K_RETURN)
    assert session.level_number == 2
    assert session.status is GameStatus.PLAYING


def test_board_clicks_are_ignored_on_the_result_screen(game: Game) -> None:
    session = game.session
    _clear_board(session.board)
    _settle(session)
    assert session.arrows_left == 0

    _post_click(game, session.board.rect.center)
    assert session.level_number == 1
    assert session.status is GameStatus.LEVEL_CLEARED


def test_enter_does_nothing_while_playing(game: Game) -> None:
    session = game.session
    _post_key(game, pygame.K_RETURN)
    assert session.level_number == 1
    assert session.status is GameStatus.PLAYING


@pytest.mark.parametrize("key", [pygame.K_ESCAPE])
def test_escape_stops_the_loop(game: Game, key: int) -> None:
    _post_key(game, key)
    assert game.running is False


def test_quit_event_stops_the_loop(game: Game) -> None:
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    game._handle_events()
    assert game.running is False


def test_arrow_keys_switch_levels_for_development(game: Game) -> None:
    session = game.session
    _post_key(game, pygame.K_RIGHT)
    assert session.level_number == 2

    _post_key(game, pygame.K_LEFT)
    assert session.level_number == 1


# ---------------------------------------------------------------- 开始界面


def test_window_opens_on_the_start_screen() -> None:
    game = Game()
    assert game.scene is Scene.START
    assert game.session.level_number == 1
    assert game.session.status is GameStatus.PLAYING


def test_clicking_the_start_button_begins_the_game() -> None:
    game = Game()
    _post_click(game, ui.start_button_rect().center)
    assert game.scene is Scene.PLAYING


def test_enter_starts_the_game_from_the_start_screen() -> None:
    game = Game()
    _post_key(game, pygame.K_RETURN)
    assert game.scene is Scene.PLAYING


def test_start_screen_ignores_board_and_hud_clicks() -> None:
    game = Game()
    session = game.session
    initial = session.arrows_left

    _post_click(game, session.board.cell_rect(0, 1).center)
    _post_click(game, ui.restart_button_rect().center)

    assert game.scene is Scene.START
    assert session.arrows_left == initial
    assert session.mistakes_left == session.max_mistakes


def test_start_screen_ignores_in_game_shortcuts() -> None:
    game = Game()
    _post_key(game, pygame.K_r)
    _post_key(game, pygame.K_RIGHT)

    assert game.scene is Scene.START
    assert game.session.level_number == 1


def test_last_level_primary_button_starts_a_new_round() -> None:
    game = Game()
    game.start()
    session = game.session
    session.load_level(session.total_levels - 1)

    _clear_board(session.board)
    _settle(session)
    assert session.status is GameStatus.LEVEL_CLEARED
    assert ui.overlay_button_text(session) == "再来一轮"

    _post_click(game, ui.overlay_button_rect().center)
    assert game.scene is Scene.PLAYING
    assert session.level_number == 1
    assert session.mistakes_left == session.max_mistakes


# ---------------------------------------------------------------- 关于界面


def test_start_screen_footer_opens_the_about_screen() -> None:
    game = Game()
    _post_click(game, ui.about_button_rect().center)
    assert game.scene is Scene.ABOUT


def test_about_screen_back_button_returns_to_the_start_screen() -> None:
    game = Game()
    _post_click(game, ui.about_button_rect().center)
    _post_click(game, ui.about_back_button_rect().center)
    assert game.scene is Scene.START


def test_enter_returns_from_the_about_screen() -> None:
    game = Game()
    _post_click(game, ui.about_button_rect().center)
    _post_key(game, pygame.K_RETURN)
    assert game.scene is Scene.START


def test_h_key_returns_from_the_about_screen() -> None:
    game = Game()
    _post_click(game, ui.about_button_rect().center)
    _post_key(game, pygame.K_h)
    assert game.scene is Scene.START


def test_about_screen_ignores_board_and_in_game_shortcuts() -> None:
    game = Game()
    session = game.session
    initial = session.arrows_left

    _post_click(game, ui.about_button_rect().center)
    _post_click(game, session.board.cell_rect(0, 1).center)
    _post_key(game, pygame.K_r)
    _post_key(game, pygame.K_RIGHT)

    assert game.scene is Scene.ABOUT
    assert session.level_number == 1
    assert session.arrows_left == initial
    assert session.mistakes_left == session.max_mistakes


def test_draw_renders_the_about_screen_frame() -> None:
    game = Game()
    _post_click(game, ui.about_button_rect().center)
    game._draw()
    assert game.scene is Scene.ABOUT


def test_every_declared_menu_action_is_wired() -> None:
    """菜单页声明的动作都要登记在动作表里：加了按钮却忘了接线会在这里报错。"""
    game = Game()

    for page in (ui.start_page(3, 3), ui.about_page(3, 3)):
        for button in page.buttons:
            game._run_action(button.action)

    with pytest.raises(KeyError):
        game._run_action("unknown-action")


# ---------------------------------------------------------------- 第一关教程


def test_first_level_opens_with_the_interactive_tutorial(game: Game) -> None:
    """首屏不再用文字讲规则：第 1 关自带一段可交互的教程。"""
    progress = game.session.tutorial
    assert progress is not None
    assert progress.hint is not None
    assert progress.suggested_arrow(game.session.board) is not None


def test_later_levels_have_no_tutorial(game: Game) -> None:
    game.session.load_level(1)
    assert game.session.tutorial is None


def test_tutorial_panel_swallows_clicks_that_miss_the_skip_button(game: Game) -> None:
    """提示条上的空白处吃掉点击，不会漏到下面的棋盘上。"""
    session = game.session
    initial = session.arrows_left
    panel = ui.tutorial_panel_rect()

    _post_click(game, (panel.left + 12, panel.centery))

    assert session.arrows_left == initial
    assert session.mistakes_left == session.max_mistakes
    assert session.tutorial is not None


def test_skip_button_hands_the_board_back_to_the_player(game: Game) -> None:
    session = game.session
    initial = session.arrows_left

    _post_click(game, ui.tutorial_skip_button_rect().center)
    assert session.tutorial is None

    # 跳过之后棋盘照常响应，提示条不再拦点击。
    _post_click(game, session.board.cell_rect(0, 1).center)
    assert session.arrows_left == initial - 1


def test_clearing_the_first_level_ends_the_tutorial(game: Game) -> None:
    session = game.session
    _clear_board(session.board)
    _settle(session)

    assert session.status is GameStatus.LEVEL_CLEARED
    assert session.tutorial is None


def test_draw_renders_the_first_level_frame_with_the_tutorial(game: Game) -> None:
    assert game.session.tutorial is not None
    game._draw()


def test_tutorial_is_only_taught_once_per_session() -> None:
    """同一次会话里教过就不再重播，但新开一局（新窗口）会重新教。"""
    game = Game()
    game.start()
    game.session.skip_tutorial()

    _post_click(game, ui.hud_home_button_rect().center)
    assert game.scene is Scene.START

    game.start()
    assert game.session.tutorial is None, "同一次会话里教过就不再重播"

    fresh = Game()
    fresh.start()
    assert fresh.session.tutorial is not None, "新开一局应当重新走一遍教程"


# ---------------------------------------------------------------- 回到主界面


@pytest.mark.parametrize("level_index", range(len(LEVELS)))
def test_every_level_has_a_back_to_menu_button_in_the_hud(level_index: int) -> None:
    game = Game()
    game.start()
    session = game.session
    session.load_level(level_index)

    _post_click(game, ui.hud_home_button_rect().center)

    assert game.scene is Scene.START
    assert session.level_number == 1
    assert session.mistakes_left == session.max_mistakes
    assert session.status is GameStatus.PLAYING


def test_home_key_returns_to_the_start_screen(game: Game) -> None:
    _post_key(game, pygame.K_h)
    assert game.scene is Scene.START


def test_won_level_has_a_back_to_menu_button_on_the_result_screen() -> None:
    game = Game()
    game.start()
    session = game.session
    _clear_board(session.board)
    _settle(session)
    assert session.status is GameStatus.LEVEL_CLEARED

    _post_click(game, ui.overlay_home_button_rect().center)
    assert game.scene is Scene.START
    assert session.level_number == 1


def test_failed_level_has_a_back_to_menu_button_on_the_result_screen() -> None:
    game = Game()
    game.start()
    session = game.session
    session.load_level(2)
    _waste_all_mistakes(session)
    assert session.status is GameStatus.FAILED

    _post_click(game, ui.overlay_home_button_rect().center)
    assert game.scene is Scene.START
    assert session.level_number == 1
    assert session.mistakes_left == session.max_mistakes


def test_draw_renders_a_full_frame(game: Game) -> None:
    game._draw()
    game.session.status = GameStatus.LEVEL_CLEARED
    game._draw()


def test_draw_renders_the_start_screen_frame() -> None:
    game = Game()
    game._draw()
    assert game.scene is Scene.START


# ---------------------------------------------------------------- 关卡计时器


def test_timer_advances_with_the_game_loop(game: Game) -> None:
    assert game.session.elapsed == 0.0

    game._update(0.5)
    assert game.session.elapsed == pytest.approx(0.5)

    # 结算界面（通关或失败）已经没有“在解谜”的时间，不再走表。
    game.session.status = GameStatus.LEVEL_CLEARED
    game._update(1.0)
    assert game.session.elapsed == pytest.approx(0.5)


def test_timer_does_not_run_on_the_start_screen() -> None:
    game = Game()
    game._update(2.0)
    assert game.session.elapsed == 0.0, "开始界面不应该给关卡计时"

    game.start()
    game._update(0.25)
    assert game.session.elapsed == pytest.approx(0.25)

    # 回到主界面会把会话退回第 1 关的初始状态，计时器一并归零。
    game.return_to_start()
    game._update(1.0)
    assert game.session.elapsed == 0.0


# ---------------------------------------------------------------- 辅助线


def test_guides_start_switched_off() -> None:
    """辅助线是可选功能：新窗口默认关着，开始游戏、换关也不会自己打开。"""
    game = Game()
    assert game.show_guides is False

    game.start()
    game.session.load_level(len(LEVELS) - 1)
    assert game.show_guides is False


def test_guide_key_toggles_the_guides_mode(game: Game) -> None:
    """G 键与右下角的开关是同一个开关：按下就打开，再按就关回去。"""
    _post_key(game, pygame.K_g)
    assert game.show_guides is True

    _post_key(game, pygame.K_g)
    assert game.show_guides is False


def test_clicking_the_guide_switch_toggles_the_guides(game: Game) -> None:
    """点右下角那颗开关就能开关辅助线，且这一下不会落到棋盘上。"""
    session = game.session
    initial = session.arrows_left

    _post_click(game, ui.guide_toggle_rect().center)
    assert game.show_guides is True
    assert session.arrows_left == initial, "开关这一下不该动棋盘"
    assert session.mistakes_left == session.max_mistakes

    _post_click(game, ui.guide_toggle_rect().center)
    assert game.show_guides is False


def test_guide_switch_is_inert_on_the_result_screen(game: Game) -> None:
    """结算卡片弹出来之后，开关不再响应（与棋盘一样被结算层接管）。"""
    session = game.session
    _clear_board(session.board)
    _settle(session)
    assert session.status is GameStatus.LEVEL_CLEARED

    _post_click(game, ui.guide_toggle_rect().center)
    assert game.show_guides is False


def test_guide_switch_belongs_to_the_window_not_the_level(game: Game) -> None:
    """辅助线开关不会被重开本关、换关或回主界面重置。"""
    _post_key(game, pygame.K_g)

    _post_key(game, pygame.K_r)
    assert game.show_guides is True, "重开本关不应该关掉辅助线"

    game.session.load_level(1)
    assert game.show_guides is True

    game.return_to_start()
    assert game.show_guides is True


def test_guide_key_is_ignored_outside_the_board(game: Game) -> None:
    """菜单页上按 G 不改开关（与 R、方向键一样只在游戏画面生效）。"""
    _post_key(game, pygame.K_h)
    assert game.scene is Scene.START

    _post_key(game, pygame.K_g)
    assert game.show_guides is False


def test_draw_renders_a_frame_with_the_guides_switched_on(game: Game) -> None:
    """开着辅助线画一帧不应出错（悬停位置由真实鼠标坐标给出）。"""
    _post_key(game, pygame.K_g)
    game._draw()

    game.session.status = GameStatus.LEVEL_CLEARED
    game._draw()
    assert game.show_guides is True


# ---------------------------------------------------------------- 窗口缩放


def _resize_the_window(game: Game, size: tuple[int, int]) -> None:
    """把窗口改成 ``size`` 并让游戏跟上（dummy 驱动下 set_mode 就够了）。"""
    pygame.display.set_mode(size, pygame.RESIZABLE)
    assert game._sync_window_size() is True


def test_resizing_the_window_keeps_the_level_progress(game: Game) -> None:
    """拖窗口只换几何：关卡、失误、用时与进行状态都不受影响。"""
    session = game.session
    _post_click(game, session.board.cell_rect(0, 1).center)
    left = session.arrows_left
    cell_before = session.board.cell_size
    session.update(1.5)

    _resize_the_window(game, (1080, 1080))

    assert game.viewport.scale == pytest.approx(1.5)
    assert session.board.cell_size > cell_before
    assert session.arrows_left == left
    assert session.mistakes_left == session.max_mistakes
    assert session.elapsed == pytest.approx(1.5)
    assert session.status is GameStatus.PLAYING
    assert game.scene is Scene.PLAYING


def test_clicking_still_works_after_the_window_grows(game: Game) -> None:
    """缩放之后命中判定跟着换到新几何上：点格子中心仍然点得中。"""
    _resize_the_window(game, (1080, 1080))
    session = game.session
    before = session.arrows_left
    free = next(
        arrow for arrow in session.board.arrows if session.board.is_path_clear(arrow)
    )

    _post_click(game, session.board.cell_rect(free.row, free.col).center)

    assert session.arrows_left == before - 1


def test_a_resize_event_makes_the_game_follow_the_window(game: Game) -> None:
    """真实缩放进来的事件（拖边 / 最大化）也要走同一条路。"""
    pygame.display.set_mode((1008, 1008), pygame.RESIZABLE)
    pygame.event.post(
        pygame.event.Event(
            pygame.VIDEORESIZE, {"size": (1008, 1008), "w": 1008, "h": 1008}
        )
    )

    game._handle_events()

    assert game.viewport.scale == viewport.Viewport.fit((1008, 1008)).scale
    assert game.session.board.rect.center == ui.board_area().center


def test_the_same_window_size_does_not_restart_the_board(game: Game) -> None:
    """窗口尺寸没变时什么也不做（每帧都会核对一次，不能顺手把棋盘重建一遍）。"""
    board = game.session.board
    assert game._sync_window_size() is False
    assert game.session.board is board


def test_the_tutorial_bar_follows_the_window(game: Game) -> None:
    """第 1 关的教程提示条按同一个视口缩放，仍然留在窗口内。"""
    assert game.session.tutorial is not None

    _resize_the_window(game, (1080, 1080))

    panel = ui.tutorial_panel_rect()
    assert game.viewport.rect(0, 0, *config.WINDOW_SIZE).contains(panel)
    assert game.session.tutorial is not None


# ---------------------------------------------------------------- 音乐与音效


class _RecordingAudio(Audio):
    """只记账不发声的 :class:`Audio`：用来断言“这个动作应该响哪一声”。

    它是 ``Audio`` 的子类（而不是一个长得像的对象），这样把替身塞给 ``Game`` 时
    类型上没有歧义；故意不调用 ``super().__init__()``——真实现一构造就会去读素材。
    """

    def __init__(self) -> None:
        self.played: list[Cue] = []
        self.music_starts = 0

    def play(self, cue: Cue) -> bool:
        self.played.append(cue)
        return True

    def start_music(self) -> bool:
        self.music_starts += 1
        return True


@pytest.fixture
def silent() -> _RecordingAudio:
    """一份“只记账不发声”的音频替身。"""
    return _RecordingAudio()


@pytest.fixture
def sound_game(silent: _RecordingAudio) -> Game:
    """把上面那份替身装进窗口的、已经进入第 1 关的游戏。"""
    instance = Game(audio_player=silent)
    instance.start()
    return instance


def _run_until_result(game: Game) -> None:
    """按固定帧长推进主循环，直到会话进入结算状态。"""
    for _ in range(config.FPS * 3):
        if not game.session.is_playing:
            return
        game._update(1.0 / config.FPS)
    msg = "会话始终没有进入结算状态"
    raise AssertionError(msg)


def _blocked_arrow(session: Session) -> tuple[int, int]:
    """找一个点不动的箭头，返回它的格子中心（用来制造失误）。"""
    board = session.board
    arrow = next(arrow for arrow in board.arrows if not board.is_path_clear(arrow))
    return board.cell_rect(arrow.row, arrow.col).center


def test_the_window_starts_playing_the_music(silent: _RecordingAudio) -> None:
    Game(audio_player=silent)
    assert silent.music_starts == 1


def test_clearing_an_arrow_plays_the_fly_away_sound(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    _post_click(sound_game, sound_game.session.board.cell_rect(0, 1).center)
    assert silent.played == [Cue.ARROW_FLY]


def test_hitting_a_blocker_plays_the_collision_sound(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    session = sound_game.session
    session.load_level(1)
    _post_click(sound_game, _blocked_arrow(session))

    assert silent.played == [Cue.ARROW_COLLIDE]


def test_clicking_empty_space_is_silent(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    """点空既不扣失误也不该出声，否则每次擦过棋盘都是一顿噪声。"""
    _post_click(sound_game, (10, config.WINDOW_HEIGHT // 2))
    assert silent.played == []


def test_clearing_the_level_plays_the_victory_sound(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    session = sound_game.session
    session.load_level(1)
    while not session.board.is_cleared:
        board = session.board
        arrow = next(arrow for arrow in board.arrows if board.is_path_clear(arrow))
        _post_click(sound_game, board.cell_rect(arrow.row, arrow.col).center)
    _run_until_result(sound_game)

    assert session.status is GameStatus.LEVEL_CLEARED
    assert silent.played[-1] is Cue.LEVEL_CLEARED


def test_wasting_every_mistake_plays_the_failure_sound(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    session = sound_game.session
    session.load_level(1)
    for _ in range(session.max_mistakes):
        _post_click(sound_game, _blocked_arrow(session))

    assert session.status is GameStatus.FAILED
    assert silent.played[-1] is Cue.LEVEL_FAILED
    assert silent.played.count(Cue.LEVEL_FAILED) == 1, "失败只该响一声"


def test_a_new_level_does_not_replay_the_result_sounds(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    """重开 / 换关是“安静地翻过去”，不会把上一关的通关声再放一遍。"""
    session = sound_game.session
    session.load_level(1)
    for _ in range(session.max_mistakes):
        _post_click(sound_game, _blocked_arrow(session))
    assert session.status is GameStatus.FAILED

    _post_click(sound_game, ui.overlay_button_rect().center)
    assert session.status is GameStatus.PLAYING

    silent.played.clear()
    sound_game._update(1.0 / config.FPS)
    assert silent.played == []


def test_menu_buttons_play_the_click_sound(
    silent: _RecordingAudio,
) -> None:
    game = Game(audio_player=silent)
    _post_click(game, ui.start_button_rect().center)

    game.return_to_start()
    _post_click(game, ui.about_button_rect().center)

    assert silent.played == [Cue.BUTTON, Cue.BUTTON]


def test_enter_on_the_start_screen_plays_the_click_sound(
    silent: _RecordingAudio,
) -> None:
    game = Game(audio_player=silent)
    _post_key(game, pygame.K_RETURN)
    assert silent.played == [Cue.BUTTON]


def test_in_game_buttons_and_shortcuts_play_the_click_sound(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    session = sound_game.session

    _post_click(sound_game, ui.restart_button_rect().center)
    _post_click(sound_game, ui.guide_toggle_rect().center)
    _post_click(sound_game, ui.tutorial_skip_button_rect().center)
    _post_click(sound_game, ui.hud_home_button_rect().center)

    assert silent.played == [Cue.BUTTON] * 4
    assert sound_game.scene is Scene.START
    # 按钮那几下没有一次落到棋盘上。
    assert session.status is GameStatus.PLAYING


def test_result_screen_buttons_play_the_click_sound(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    session = sound_game.session
    session.load_level(1)
    while not session.board.is_cleared:
        board = session.board
        arrow = next(arrow for arrow in board.arrows if board.is_path_clear(arrow))
        _post_click(sound_game, board.cell_rect(arrow.row, arrow.col).center)
    _run_until_result(sound_game)

    silent.played.clear()
    _post_click(sound_game, ui.overlay_button_rect().center)
    assert session.level_number == 3
    assert silent.played == [Cue.BUTTON]


def test_enter_while_playing_is_silent(
    sound_game: Game, silent: _RecordingAudio
) -> None:
    """游戏进行中按 Enter 什么也没发生，那么就不该有反馈声。"""
    _post_key(sound_game, pygame.K_RETURN)
    assert silent.played == []
