"""第一关交互式教程：进度状态机、会话接线与提示条布局。

教程是“边玩边学”的：玩家跟着棋盘上的呼吸高亮点几下，就把
“点畅通箭头 → 点被挡住箭头 → 清空棋盘”三条规则都体验一遍。
本文件既测状态机（不依赖窗口），也测会话接线与提示条的绘制。
"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config, tutorial, ui
from another_arrow_rt265.board import Board, ClickResult
from another_arrow_rt265.levels import LEVELS
from another_arrow_rt265.session import GameStatus, Session
from another_arrow_rt265.tutorial import Tutorial, TutorialStep

AREA = pygame.Rect(0, 0, 640, 640)

# 第 1 关的 (0, 1) 是向上、前方畅通的箭头；(0, 2) 向下，被 (1, 2) 的“<”挡住。
FREE_CELL = (0, 1)
BLOCKED_CELL = (0, 2)


def _session(max_mistakes: int = config.MAX_MISTAKES) -> Session:
    """创建一份使用内置关卡、停在第 1 关（教程关）的会话。"""
    return Session(ui.board_area(), levels=LEVELS, max_mistakes=max_mistakes)


def _surface() -> pygame.Surface:
    return pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))


def _frame(session: Session) -> pygame.Surface:
    """按 ``Game._draw`` 的顺序画一帧游戏画面。"""
    surface = _surface()
    ui.draw_background(surface)
    session.board.draw(surface)
    ui.draw_ui(surface, session)
    return surface


def _step(session: Session) -> TutorialStep:
    """返回会话里教程当前要求做的步骤；教程不存在或已结束时直接断言失败。"""
    progress = session.tutorial
    assert progress is not None, "本关应该带教程"
    hint = progress.hint
    assert hint is not None, "教程不应该已经结束"
    return hint.step


def _click(session: Session, cell: tuple[int, int]) -> ClickResult:
    """点一下某个格子，并检查会话确实把它转交给了棋盘。"""
    result = session.click(session.board.cell_rect(*cell).center)
    assert result is not None
    return result


def _clear_board(board: Board) -> None:
    """依次清掉所有“前方畅通”的箭头，直到棋盘清空。"""
    while not board.is_cleared:
        for arrow in board.arrows:
            if board.is_path_clear(arrow):
                board.handle_click(board.cell_rect(arrow.row, arrow.col).center)
                break
        else:
            msg = "棋盘上已经没有可清除的箭头"
            raise AssertionError(msg)


# ---------------------------------------------------------------- 状态机


def test_tutorial_starts_on_the_first_step() -> None:
    hint = Tutorial().hint

    assert hint is not None
    assert hint.step is TutorialStep.CLEAR_FREE
    assert (hint.number, hint.total) == (1, 3)
    assert hint.progress == "1 / 3"
    assert hint.text


def test_clearing_an_arrow_advances_to_the_collision_step() -> None:
    progress = Tutorial()
    progress.note_click(ClickResult.CLEARED)

    assert progress.hint is not None
    assert progress.hint.step is TutorialStep.BLOCKED


def test_clicking_empty_space_teaches_nothing() -> None:
    progress = Tutorial()
    progress.note_click(ClickResult.MISS)

    assert progress.hint is not None
    assert progress.hint.step is TutorialStep.CLEAR_FREE


def test_collision_step_waits_for_the_tutorial_to_ask_for_it() -> None:
    """自己先撞墙不算完成第二步：那一次不扣失误的演示得由教程点名。"""
    progress = Tutorial()
    assert progress.collision_demo_pending is False, "第一步还没走完"

    progress.note_click(ClickResult.BLOCKED)
    assert progress.hint is not None
    assert progress.hint.step is TutorialStep.CLEAR_FREE, "还没学会飞出棋盘"

    progress.note_click(ClickResult.CLEARED)
    assert progress.hint is not None
    assert progress.hint.step is TutorialStep.BLOCKED, "现在才轮到演示碰撞"
    assert progress.collision_demo_pending is True

    progress.note_click(ClickResult.BLOCKED)
    assert progress.hint is not None
    assert progress.hint.step is TutorialStep.CLEAR_BOARD
    assert progress.collision_demo_pending is False, "演示只送一次"


def test_clearing_the_board_finishes_the_tutorial() -> None:
    board = Board((".^.",), AREA)
    progress = Tutorial()
    progress.note_click(ClickResult.CLEARED)
    progress.note_click(ClickResult.BLOCKED)
    assert not progress.is_finished

    board.handle_click(board.cell_rect(0, 1).center)
    progress.sync(board)

    assert progress.is_finished
    assert progress.hint is None
    assert progress.step is None


def test_suggested_arrow_is_clear_then_blocked() -> None:
    """前两步各指一支“对得上话”的箭头：先畅通的，再被挡住的。"""
    board = Board(LEVELS[0], AREA)
    progress = Tutorial()

    first = progress.suggested_arrow(board)
    assert first is not None
    assert board.is_path_clear(first), "第一步应当指向一支前方畅通的箭头"

    progress.note_click(ClickResult.CLEARED)
    second = progress.suggested_arrow(board)
    assert second is not None
    assert not board.is_path_clear(second), "第二步应当指向一支被挡住的箭头"
    assert second != first


def test_suggested_arrow_is_none_on_the_last_step() -> None:
    """最后一步只要求清空棋盘，不指定具体箭头。"""
    board = Board(LEVELS[0], AREA)
    progress = Tutorial()
    progress.note_click(ClickResult.CLEARED)
    progress.note_click(ClickResult.BLOCKED)

    assert progress.suggested_arrow(board) is None


# ---------------------------------------------------------------- 会话接线


def test_session_offers_the_tutorial_on_the_first_level() -> None:
    assert _step(_session()) is TutorialStep.CLEAR_FREE


def test_session_has_no_tutorial_on_later_levels() -> None:
    assert Session(ui.board_area(), levels=LEVELS, level_index=1).tutorial is None


def test_session_moves_the_tutorial_along_with_the_players_clicks() -> None:
    session = _session()

    assert _click(session, FREE_CELL) is ClickResult.CLEARED
    assert _step(session) is TutorialStep.BLOCKED

    assert _click(session, BLOCKED_CELL) is ClickResult.BLOCKED
    assert _step(session) is TutorialStep.CLEAR_BOARD


def test_the_demo_collision_does_not_cost_a_mistake() -> None:
    """教程演示“失误”时只讲道理：反馈照旧，但失误次数不动。"""
    session = _session(max_mistakes=1)
    _click(session, FREE_CELL)

    assert _click(session, BLOCKED_CELL) is ClickResult.BLOCKED
    assert session.mistakes_left == 1, "演示不该扣掉真实失误"
    assert session.status is GameStatus.PLAYING
    assert session.board.blocked_flash is not None, "碰撞反馈照常播放"
    assert session.tutorial is not None


def test_collisions_after_the_demo_cost_mistakes_again() -> None:
    """豁免只有那一次：演示之后撞墙就按真实规则扣失误（包括因此失败）。"""
    session = _session(max_mistakes=1)
    _click(session, FREE_CELL)
    _click(session, BLOCKED_CELL)  # 演示：免费

    assert _click(session, BLOCKED_CELL) is ClickResult.BLOCKED
    assert session.mistakes_left == 0
    assert session.status is GameStatus.FAILED


def test_collisions_before_the_demo_cost_mistakes() -> None:
    """还没轮到演示就自己撞墙，那是一次真实失误（教程也不会因此往前走）。"""
    session = _session()

    assert _click(session, BLOCKED_CELL) is ClickResult.BLOCKED
    assert session.mistakes_left == session.max_mistakes - 1
    assert _step(session) is TutorialStep.CLEAR_FREE


def test_skipping_the_tutorial_makes_collisions_count_again() -> None:
    session = _session()
    _click(session, FREE_CELL)
    session.skip_tutorial()

    assert _click(session, BLOCKED_CELL) is ClickResult.BLOCKED
    assert session.mistakes_left == session.max_mistakes - 1


def test_custom_level_sets_never_get_the_tutorial() -> None:
    """教程只挂在内置关卡列表的第 1 关：自定义关卡不继承“演示不扣失误”。"""
    custom = Session(ui.board_area(), levels=(LEVELS[0],))
    assert custom.tutorial is None

    assert _click(custom, BLOCKED_CELL) is ClickResult.BLOCKED
    assert custom.mistakes_left == custom.max_mistakes - 1


def test_session_drops_the_tutorial_once_the_board_is_cleared() -> None:
    session = _session()
    _click(session, FREE_CELL)
    _click(session, BLOCKED_CELL)

    _clear_board(session.board)
    for _ in range(config.FPS):
        session.update(1.0 / config.FPS)
        if session.status is not GameStatus.PLAYING:
            break

    assert session.status is GameStatus.LEVEL_CLEARED
    assert session.tutorial is None, "本关已经通关，教程应当收工"


def test_session_drops_the_tutorial_when_it_is_cleared_without_a_collision() -> None:
    """一路只点畅通箭头也能通关：本关目标达成即收起教程，不再挂着第二步。"""
    session = _session()

    _clear_board(session.board)
    session.update(1.0 / config.FPS)

    assert session.tutorial is None
    assert session.mistakes_left == session.max_mistakes


def test_tutorial_comes_back_after_a_failed_attempt() -> None:
    """失败不作数：连教程都还没走完就耗尽失误，重开本关会重新教一遍。"""
    session = _session(max_mistakes=1)

    assert _click(session, BLOCKED_CELL) is ClickResult.BLOCKED
    assert session.status is GameStatus.FAILED
    assert session.tutorial is not None

    session.restart_level()
    assert _step(session) is TutorialStep.CLEAR_FREE


def test_skipping_the_tutorial_keeps_it_hidden_for_the_rest_of_the_session() -> None:
    session = _session()
    session.skip_tutorial()
    assert session.tutorial is None

    session.restart_level()
    assert session.tutorial is None, "跳过之后重开本关不该再弹"

    session.load_level(1)
    session.load_level(0)
    assert session.tutorial is None, "再回到第 1 关也不该再弹"


def test_next_level_has_no_tutorial() -> None:
    session = _session()
    _click(session, FREE_CELL)
    _click(session, BLOCKED_CELL)
    _clear_board(session.board)
    for _ in range(config.FPS * 3):
        if not session.is_playing:
            break
        session.update(1.0 / config.FPS)

    session.advance()
    assert session.level_number == 2
    assert session.tutorial is None


# ---------------------------------------------------------------- 提示条布局


def test_tutorial_panel_sits_above_the_first_level_board() -> None:
    """提示条排在棋盘上方的空白带里：在窗口内，且不压住任何棋子。"""
    panel = ui.tutorial_panel_rect()
    board = Board(LEVELS[config.TUTORIAL_LEVEL_INDEX], ui.board_area())
    board_panel = board.rect.inflate(2 * config.CELL_GAP, 2 * config.CELL_GAP)

    assert panel.top >= config.HUD_HEIGHT
    assert panel.left >= 0
    assert panel.right <= config.WINDOW_WIDTH
    assert panel.bottom <= config.WINDOW_HEIGHT
    assert not panel.colliderect(board_panel), "提示条不能压住第 1 关的棋子"
    assert not panel.colliderect(ui.hud_rect())


def test_tutorial_skip_button_is_inside_the_panel() -> None:
    panel = ui.tutorial_panel_rect()
    skip = ui.tutorial_skip_button_rect()

    assert panel.contains(skip)
    assert skip.right <= panel.right
    assert skip.centery == panel.centery


@pytest.mark.parametrize("text", sorted(tutorial._TEXTS.values()))
def test_tutorial_text_fits_beside_the_skip_button(text: str) -> None:
    """指引文案一行放得下，不会顶到“跳过教程”上（加字前先看这里）。"""
    panel = ui.tutorial_panel_rect()
    skip = ui.tutorial_skip_button_rect()

    progress_label = ui._TEXT_PROGRESS.font().render(
        "1 / 3", True, config.COLOR_PRIMARY
    )
    text_left = (
        panel.left
        + ui._TUTORIAL_BAR_PADDING
        + progress_label.get_width()
        + 2 * ui._TUTORIAL_DIVIDER_GAP
    )
    label = ui._TEXT_RULE.font().render(text, True, config.COLOR_TEXT)

    assert text_left + label.get_width() <= skip.left, text


# ---------------------------------------------------------------- 绘制


def test_draw_tutorial_renders_every_step_without_error() -> None:
    surface = _surface()
    session = _session()

    ui.draw_tutorial(surface, session)
    ui.draw_tutorial(surface, session, mouse=ui.tutorial_skip_button_rect().center)

    _click(session, FREE_CELL)  # 第二步：多画一圈挡路提示
    ui.draw_tutorial(surface, session)

    _click(session, BLOCKED_CELL)  # 第三步：只留提示条
    ui.draw_tutorial(surface, session)

    session.skip_tutorial()
    ui.draw_tutorial(surface, session)  # 没有教程时直接返回


def test_draw_tutorial_paints_the_panel_over_the_board_frame() -> None:
    """同一关、只差教程：提示条所在的位置必须真的被画上东西。"""
    with_tutorial = _session()
    without = _session()
    without.skip_tutorial()

    first = _frame(with_tutorial)
    second = _frame(without)

    spot = ui.tutorial_panel_rect().center
    assert first.get_at(spot)[:3] != second.get_at(spot)[:3]


def test_draw_tutorial_keeps_quiet_on_the_result_screen() -> None:
    """结算卡片弹出后不再画教程，免得和结算信息抢注意力。"""
    session = _session()
    session.status = GameStatus.FAILED
    surface = _surface()

    ui.draw_tutorial(surface, session)

    assert surface.get_at(ui.tutorial_panel_rect().center)[:3] == (0, 0, 0)
