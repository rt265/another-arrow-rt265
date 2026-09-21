"""关卡会话：把关卡、棋盘、失误次数与结算状态串成一条规则链。

本模块是“游戏规则”的单一来源，只依赖 :class:`~another_arrow_rt265.board.Board`
与 :mod:`another_arrow_rt265.config`，不涉及任何绘制，因此可以在没有窗口的
环境下用固定 ``dt`` 完整地测试通关、失败与重新开始。

一次会话包含三件事：

- **棋盘**：交给 ``Board`` 处理点击、碰撞与动画；
- **失误次数**：点击被阻挡的箭头时扣减，扣到 0 即本关失败；
- **关卡进度**：棋盘清空（且飞出动画播完）后进入通关结算，再进入下一关。
"""

from __future__ import annotations

from enum import Enum

import pygame

from another_arrow_rt265 import config
from another_arrow_rt265.board import Board, ClickResult
from another_arrow_rt265.levels import LEVELS, Level


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
        if result is ClickResult.BLOCKED:
            self._mistakes_left -= 1
            if self._mistakes_left <= 0:
                self.status = GameStatus.FAILED
        return result

    def update(self, dt: float) -> None:
        """推进棋盘动画与结算计时，``dt`` 为上一帧耗时（秒）。"""
        self._board.update(dt)
        if not self.is_playing:
            return

        if not self._board.is_cleared or self._board.flying:
            # 还没清空，或者最后一支箭头仍在飞出画面，重新计时。
            self._cleared_pause = 0.0
            return

        self._cleared_pause += dt
        if self._cleared_pause >= config.LEVEL_CLEARED_DELAY:
            self.status = GameStatus.LEVEL_CLEARED

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

    def _load(self, level_index: int) -> None:
        """载入关卡并重置与本关绑定的所有状态。"""
        self.level_index = level_index
        self._board = Board(self.levels[level_index], self.area)
        self._mistakes_left = self.max_mistakes
        self.status = GameStatus.PLAYING
        self._cleared_pause = 0.0
