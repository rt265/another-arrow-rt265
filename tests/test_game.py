"""窗口级测试：事件分发、按钮点击与结算流转。

这些测试在 SDL 的 dummy 驱动下创建真实窗口（见 ``conftest.py``），
并通过 ``pygame.event.post()`` 投递鼠标与键盘事件，尽量贴近真实操作路径。
"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, ui
from another_arrow_rt265.board import Board, ClickResult
from another_arrow_rt265.game import Game
from another_arrow_rt265.session import GameStatus, Session


@pytest.fixture
def game() -> Game:
    """一个使用内置关卡、直接进入第 1 关的窗口。"""
    return Game()


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


def test_draw_renders_a_full_frame(game: Game) -> None:
    game._draw()
    game.session.status = GameStatus.LEVEL_CLEARED
    game._draw()
