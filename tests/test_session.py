"""关卡会话（失误次数、通关判定、失败与重开）的测试。"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import config
from another_arrow_rt265.board import Arrow, ClickResult
from another_arrow_rt265.levels import LEVELS, Level
from another_arrow_rt265.session import GameStatus, Session

AREA = pygame.Rect(0, 0, 640, 640)

# 十字形关卡：四个箭头互相阻挡，点哪个都会消耗失误。
CROSS_LEVEL: Level = (
    ".v.",
    ">.<",
    ".^.",
)

# 一行两箭头：(0,0) 向右被 (0,1) 挡住，(0,1) 向下畅通。
PAIR_LEVEL: Level = (
    ">v.",
    "...",
    "...",
)


def _arrow(session: Session, row: int, col: int) -> Arrow:
    """取出指定格子的箭头，顺便断言它确实存在。"""
    arrow = session.board.arrow_at(row, col)
    assert arrow is not None
    return arrow


def _click(session: Session, arrow: Arrow) -> ClickResult | None:
    """点击某个箭头所在的格子中心。"""
    return session.click(session.board.cell_rect(arrow.row, arrow.col).center)


def _count_arrows(level: Level) -> int:
    """统计关卡中的箭头数量。"""
    return sum(1 for line in level for symbol in line if symbol != ".")


def _clear_board(session: Session) -> None:
    """反复点击“前方畅通”的箭头，直到棋盘清空。

    内置关卡保证总存在可清除的箭头，因此这里不做回溯搜索；一旦找不到可清除
    的箭头，说明关卡数据出现了死锁，直接断言失败。
    """
    for _ in range(200):
        if session.board.is_cleared:
            return
        for arrow in session.board.arrows:
            if session.board.is_path_clear(arrow):
                assert _click(session, arrow) is ClickResult.CLEARED
                break
        else:
            msg = "棋盘上已经没有可清除的箭头"
            raise AssertionError(msg)
    msg = "清空棋盘用光了步数上限"
    raise AssertionError(msg)


def _step_until_settled(session: Session) -> None:
    """按固定帧长推进，直到会话给出结算结果。"""
    for _ in range(config.FPS * 3):
        if not session.is_playing:
            return
        session.update(1.0 / config.FPS)
    msg = "会话始终没有进入结算状态"
    raise AssertionError(msg)


# ---------------------------------------------------------------- 初始状态


def test_session_starts_playing_on_the_first_level() -> None:
    session = Session(AREA)
    assert session.level_number == 1
    assert session.total_levels == len(LEVELS)
    assert session.status is GameStatus.PLAYING
    assert session.is_playing is True
    assert session.mistakes_left == config.MAX_MISTAKES
    assert session.arrows_left == _count_arrows(LEVELS[0])
    assert session.board.flying == []


def test_level_index_wraps_around() -> None:
    session = Session(AREA, level_index=len(LEVELS))
    assert session.level_number == 1


def test_invalid_configuration_raises_value_error() -> None:
    with pytest.raises(ValueError):
        Session(AREA, levels=(), max_mistakes=1)
    with pytest.raises(ValueError):
        Session(AREA, levels=(PAIR_LEVEL,), max_mistakes=0)


# ---------------------------------------------------------------- 失误与失败


def test_blocked_click_costs_one_mistake() -> None:
    session = Session(AREA, levels=(PAIR_LEVEL,))
    blocked = _arrow(session, 0, 0)

    assert _click(session, blocked) is ClickResult.BLOCKED
    assert session.mistakes_left == config.MAX_MISTAKES - 1
    assert session.status is GameStatus.PLAYING
    assert session.arrows_left == 2

    # 失误扣完之前可以一直重试，棋盘与箭头都不变。
    assert _click(session, blocked) is ClickResult.BLOCKED
    assert session.mistakes_left == config.MAX_MISTAKES - 2

    # 点空格子不算失误。
    assert session.click((0, 0)) is ClickResult.MISS
    assert session.mistakes_left == config.MAX_MISTAKES - 2


def test_running_out_of_mistakes_fails_the_level() -> None:
    session = Session(AREA, levels=(CROSS_LEVEL,), max_mistakes=2)
    blocked = _arrow(session, 0, 1)

    assert _click(session, blocked) is ClickResult.BLOCKED
    assert session.mistakes_left == 1
    assert session.status is GameStatus.PLAYING

    assert _click(session, blocked) is ClickResult.BLOCKED
    assert session.mistakes_left == 0
    assert session.status is GameStatus.FAILED
    assert session.is_playing is False

    # 失败后点击不再影响棋盘，箭头一个都没少。
    assert session.click((0, 0)) is None
    assert session.arrows_left == 4

    # 动画仍然可以继续推进，不会因为结算而卡住。
    session.update(config.BLOCKED_FLASH_SECONDS)
    assert session.board.blocked_flash is None


def test_retry_after_failure_restores_the_level() -> None:
    session = Session(AREA, levels=(CROSS_LEVEL,), max_mistakes=1)
    assert session.click(session.board.cell_rect(0, 1).center) is ClickResult.BLOCKED
    assert session.status is GameStatus.FAILED

    session.restart_level()
    assert session.status is GameStatus.PLAYING
    assert session.mistakes_left == 1
    assert session.arrows_left == 4


# ---------------------------------------------------------------- 通关与流转


def test_clearing_all_arrows_shows_the_result_and_advances() -> None:
    session = Session(AREA)

    _clear_board(session)
    assert session.arrows_left == 0
    # 逻辑上棋盘已经清空，但飞出动画还没播完，此时不应弹出结算。
    assert session.board.flying
    assert session.status is GameStatus.PLAYING

    _step_until_settled(session)
    assert session.status is GameStatus.LEVEL_CLEARED

    session.advance()
    assert session.level_number == 2
    assert session.status is GameStatus.PLAYING
    assert session.mistakes_left == session.max_mistakes
    assert session.arrows_left == _count_arrows(LEVELS[1])
    assert session.board.flying == []


def test_settled_session_ignores_clicks_and_stays_settled() -> None:
    session = Session(AREA)
    _clear_board(session)
    _step_until_settled(session)
    assert session.status is GameStatus.LEVEL_CLEARED

    assert session.click(session.board.cell_rect(0, 1).center) is None
    session.update(1.0)
    session.update(1.0)
    assert session.status is GameStatus.LEVEL_CLEARED


def test_clearing_the_last_level_starts_a_new_round() -> None:
    session = Session(AREA, levels=(PAIR_LEVEL, LEVELS[0]), level_index=1)
    assert session.is_last_level is True
    assert session.level_number == 2

    _clear_board(session)
    _step_until_settled(session)
    assert session.status is GameStatus.LEVEL_CLEARED
    assert session.cleared_all_levels is True

    session.advance()
    assert session.level_number == 1
    assert session.status is GameStatus.PLAYING
    assert session.mistakes_left == session.max_mistakes


@pytest.mark.parametrize("level_index", range(len(LEVELS)))
def test_built_in_levels_can_be_cleared(level_index: int) -> None:
    """内置关卡都能在不消耗失误的情况下通关（贪心顺序即可解开）。"""
    session = Session(AREA, level_index=level_index)
    _clear_board(session)
    assert session.mistakes_left == session.max_mistakes

    _step_until_settled(session)
    assert session.status is GameStatus.LEVEL_CLEARED


# ---------------------------------------------------------------- 重新开始


def test_restart_restores_layout_and_mistakes() -> None:
    session = Session(AREA, levels=(PAIR_LEVEL,), max_mistakes=3)
    layout = [(arrow.row, arrow.col, arrow.direction) for arrow in session.board]

    assert _click(session, _arrow(session, 0, 0)) is ClickResult.BLOCKED
    assert _click(session, _arrow(session, 0, 1)) is ClickResult.CLEARED
    assert session.mistakes_left == 2
    assert session.arrows_left == 1
    assert session.board.flying

    session.restart_level()
    assert [
        (arrow.row, arrow.col, arrow.direction) for arrow in session.board
    ] == layout
    assert session.arrows_left == 2
    assert session.mistakes_left == 3
    assert session.status is GameStatus.PLAYING
    assert session.board.flying == []
    assert session.board.selected is None
    assert session.board.blocked_flash is None


def test_load_level_switches_level_and_resets_mistakes() -> None:
    session = Session(AREA, levels=(PAIR_LEVEL, LEVELS[0]), max_mistakes=2)
    assert session.click(session.board.cell_rect(0, 0).center) is ClickResult.BLOCKED
    assert session.mistakes_left == 1

    session.load_level(-1)  # 取模后应回到最后一关
    assert session.level_number == 2
    assert session.mistakes_left == 2
    assert session.arrows_left == _count_arrows(LEVELS[0])
