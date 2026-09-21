"""窗口级测试：画面切换、事件分发、按钮点击与结算流转。

这些测试在 SDL 的 dummy 驱动下创建真实窗口（见 ``conftest.py``），
并通过 ``pygame.event.post()`` 投递鼠标与键盘事件，尽量贴近真实操作路径。
"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, ui
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
