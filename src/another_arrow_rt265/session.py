"""关卡会话：把关卡、棋盘、失误次数与结算状态串成一条规则链。

本模块是“游戏规则”的单一来源，只依赖 :class:`~another_arrow_rt265.board.Board`
与 :mod:`another_arrow_rt265.config`，不涉及任何绘制，因此可以在没有窗口的
环境下用固定 ``dt`` 完整地测试通关、失败与重新开始。

一次会话包含五件事：

- **棋盘**：交给 ``Board`` 处理点击、碰撞与动画；
- **失误次数**：点击被阻挡的箭头时扣减，扣到 0 即本关失败（教程里那次演示撞墙除外）；
- **关卡进度**：棋盘清空（且飞出动画播完）后进入通关结算，再进入下一关；
- **单关计时**：每关各有一个计时器，只在“还在解谜”时走字，并记住本关的最佳用时；
- **新手教程**：第 1 关附带一段边玩边学的教程（见 :mod:`another_arrow_rt265.tutorial`），
  进度由本模块在点击与每帧刷新时推进，画什么则交给 ``ui``。
"""

from __future__ import annotations

from enum import Enum

import pygame

from another_arrow_rt265 import config
from another_arrow_rt265.board import Board, ClickResult
from another_arrow_rt265.levels import LEVELS, Level
from another_arrow_rt265.tutorial import Tutorial


class GameStatus(Enum):
    """一次关卡会话的进行状态。"""

    PLAYING = "playing"
    """正在进行中，可以点击棋盘。"""

    LEVEL_CLEARED = "level_cleared"
    """本关箭头已全部清除，正在等待玩家进入下一关。"""

    FAILED = "failed"
    """失误次数已耗尽，正在等待玩家重试。"""


class Session:
    """按顺序游玩若干关卡的会话。"""

    def __init__(
        self,
        area: pygame.Rect,
        levels: tuple[Level, ...] = LEVELS,
        max_mistakes: int = config.MAX_MISTAKES,
        level_index: int = 0,
    ) -> None:
        """创建会话并载入首个关卡。

        Args:
            area: 可供棋盘使用的屏幕区域。
            levels: 关卡列表，至少包含一关。
            max_mistakes: 每一关允许的失误次数，必须为正数。
            level_index: 起始关卡序号，越界时自动取模。

        Raises:
            ValueError: 关卡列表为空或失误次数不是正数时抛出。
        """
        if not levels:
            msg = "关卡列表不能为空"
            raise ValueError(msg)
        if max_mistakes <= 0:
            msg = "失误次数必须为正数"
            raise ValueError(msg)

        self.levels = levels
        self.area = area
        self.max_mistakes = max_mistakes
        self.status = GameStatus.PLAYING
        self._cleared_pause = 0.0
        # 最佳用时按“关卡序号”记录，不随重开本关或回到主界面清空。
        self._best_times: dict[int, float] = {}
        # 教程在本局会话里只教一次：走完或被跳过后，重开本关也不会再弹。
        self._tutorial_seen = False
        self._load(level_index % len(levels))

    # ------------------------------------------------------------ 只读状态

    @property
    def board(self) -> Board:
        """当前关卡的棋盘。"""
        return self._board

    @property
    def total_levels(self) -> int:
        """内置关卡总数。"""
        return len(self.levels)

    @property
    def level_number(self) -> int:
        """当前关卡的序号（从 1 开始，供界面显示）。"""
        return self.level_index + 1

    @property
    def is_last_level(self) -> bool:
        """当前是否已经是最后一关。"""
        return self.level_index == len(self.levels) - 1

    @property
    def arrows_left(self) -> int:
        """当前关卡剩余的箭头数量。"""
        return self._board.remaining

    @property
    def mistakes_left(self) -> int:
        """当前关卡剩余的失误次数。"""
        return self._mistakes_left

    @property
    def is_playing(self) -> bool:
        """是否处于可点击棋盘的进行状态。"""
        return self.status is GameStatus.PLAYING

    @property
    def cleared_all_levels(self) -> bool:
        """是否已经通关最后一关。"""
        return self.status is GameStatus.LEVEL_CLEARED and self.is_last_level

    @property
    def elapsed(self) -> float:
        """本关已经用掉的时间（秒），重置只发生在 :meth:`_load` 里。

        计时器只统计“还在解谜”的时间：清空棋盘的瞬间就停表，之后的飞出动画、
        结算停顿都不再计入；本关失败时也在那一次点击处停下。
        """
        return self._elapsed

    @property
    def best_time(self) -> float | None:
        """本关的最佳用时（秒）；本次会话里还没通关过本关则返回 ``None``。

        成绩按关卡序号记在会话上，因此重开本关、回到主界面、通关一轮再重来，
        都不会把已经跑出来的成绩抹掉。
        """
        return self._best_times.get(self.level_index)

    @property
    def is_new_record(self) -> bool:
        """刚刚这次通关是否刷新了本关的最佳用时（第一次通关也算刷新）。"""
        return self._new_record

    @property
    def tutorial(self) -> Tutorial | None:
        """当前关卡的教程进度；非教程关卡、或本局已经教过（走完 / 跳过）时为 ``None``。"""
        return self._tutorial

    # ------------------------------------------------------------ 规则

    def click(self, position: tuple[int, int]) -> ClickResult | None:
        """把一次鼠标点击转交给棋盘，并结算失误次数。

        Returns:
            棋盘的处理结果；会话已经结算（通关 / 失败）时不处理点击并返回
            ``None``，避免玩家在结算界面上继续改动棋盘。

        Note:
            箭头飞出棋盘是**立即**生效的（见 ``Board.handle_click``），
            因此“清空棋盘”的判定会早于飞出动画结束，真正的结算推迟到
            :meth:`update` 里动画播完之后。
        """
        if not self.is_playing:
            return None

        result = self._board.handle_click(position)
        if result is ClickResult.BLOCKED and not self._is_collision_demo():
            self._mistakes_left -= 1
            if self._mistakes_left <= 0:
                self.status = GameStatus.FAILED
        if self._tutorial is not None:
            self._tutorial.note_click(result)
            self._sync_tutorial()
        return result

    def _is_collision_demo(self) -> bool:
        """这次撞墙是不是教程正在演示的那一次（演示只讲道理，不扣失误）。

        必须在 ``note_click()`` **之前**问：演示那一次点击会同时把碰撞那一步记完，
        问晚了就变成“真扣”。演示本身依然会触发棋盘的晃动 / 火花 / 挡路提示，
        玩家看得到碰撞，也不会因为还在学而丢一条命。
        """
        return self._tutorial is not None and self._tutorial.collision_demo_pending

    def update(self, dt: float) -> None:
        """推进棋盘动画、本关计时与结算计时，``dt`` 为上一帧耗时（秒）。"""
        self._board.update(dt)
        self._sync_tutorial()
        if not self.is_playing:
            return

        if self._board.is_cleared:
            self._settle(dt)
            return

        # 棋盘还没清空：正常走表，并让结算停顿重新计时。
        self._elapsed += dt
        self._cleared_pause = 0.0

    def _settle(self, dt: float) -> None:
        """棋盘清空后：等飞出动画播完，再停顿一下弹出结算。

        这段时间不再计入 :attr:`elapsed`——最后一步点击落下的瞬间，
        本关的用时就已经定下来了。
        """
        if self._board.flying:
            self._cleared_pause = 0.0
            return

        self._cleared_pause += dt
        if self._cleared_pause >= config.LEVEL_CLEARED_DELAY:
            self._finish()

    def _finish(self) -> None:
        """结算本关通关，并把用时记入本关的最佳成绩。"""
        self.status = GameStatus.LEVEL_CLEARED
        previous = self._best_times.get(self.level_index)
        self._new_record = previous is None or self._elapsed < previous
        if self._new_record:
            self._best_times[self.level_index] = self._elapsed

    # ------------------------------------------------------------ 关卡流转

    def restart_level(self) -> None:
        """让当前关卡恢复到初始状态（箭头布局与失误次数都会重置）。"""
        self._load(self.level_index)

    def advance(self) -> None:
        """进入下一关；已经是最后一关时从头开始新的一轮。"""
        next_index = self.level_index + 1
        self._load(0 if next_index >= len(self.levels) else next_index)

    def load_level(self, level_index: int) -> None:
        """跳到指定关卡（越界时取模）并重置失误次数。"""
        self._load(level_index % len(self.levels))

    def skip_tutorial(self) -> None:
        """跳过教程：本局会话内不再显示（重开本关、回到第 1 关都不会再弹）。"""
        self._dismiss_tutorial()

    def _dismiss_tutorial(self) -> None:
        """收起教程，并记下“本局已经教过”（之后重开本关也不会再弹）。"""
        self._tutorial_seen = True
        self._tutorial = None

    def _load(self, level_index: int) -> None:
        """载入关卡并重置与本关绑定的所有状态（包括计时器与教程）。

        “重置”指重新数一次本次挑战的用时；:attr:`best_time` 属于关卡的历史成绩，
        因此不会被清掉。教程只在第 1 关且本局还没教过时出现，失败重开会重新教
        （失败说明还没学会），走完或被跳过之后再回到第 1 关就不再打扰。
        """
        self.level_index = level_index
        self._board = Board(self.levels[level_index], self.area)
        self._mistakes_left = self.max_mistakes
        self.status = GameStatus.PLAYING
        self._cleared_pause = 0.0
        self._elapsed = 0.0
        self._new_record = False
        show_tutorial = not self._tutorial_seen and self._needs_tutorial(level_index)
        self._tutorial = Tutorial() if show_tutorial else None

    def _needs_tutorial(self, level_index: int) -> bool:
        """``level_index`` 是不是“教程关”。

        只有**内置关卡列表**的第 1 关带教程：教程是给首次上手的玩家准备的引导，
        而“演示撞墙不扣失误”是对规则的一处放宽——自定义关卡（测试、以后的自制
        关卡）即使也排在序号 0，也不应该被悄悄塞进教程、更不该继承这处放宽。
        """
        return level_index == config.TUTORIAL_LEVEL_INDEX and self.levels == LEVELS

    def _sync_tutorial(self) -> None:
        """按棋盘状态推进教程；教学完成或本关目标已达成时收起教程。

        收起（并记为“本局教过了”）的条件有两个：三步都走完，或棋盘已经清空——
        后者是为了兜住“玩家一路只点畅通箭头、从没撞过墙”的情况，此时本关已经通关，
        没必要继续教下去。本关失败不收起教程，重开本关会从第一步重新教一遍。
        """
        if self._tutorial is None:
            return
        self._tutorial.sync(self._board)
        if self._tutorial.is_finished or self._board.is_cleared:
            self._dismiss_tutorial()
