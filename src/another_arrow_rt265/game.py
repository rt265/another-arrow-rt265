"""游戏主循环。

当前阶段实现“窗口 + 棋盘 + 点击移除箭头”的可玩流程：
点击前方畅通的箭头会把箭头移出棋盘，撞到其他箭头时给出闪烁提示。
失误次数、结算界面与飞出动画将在后续事项中加入。
"""

from __future__ import annotations

import pygame

from another_arrow_rt265 import config
from another_arrow_rt265.board import Board
from another_arrow_rt265.levels import LEVELS


class Game:
    """承载关卡的 pygame 应用，负责事件分发与画面刷新。"""

    def __init__(self, level_index: int = 0) -> None:
        """初始化窗口并载入首个关卡。

        Args:
            level_index: 初始关卡序号，越界时会自动取模。
        """
        pygame.init()
        self.screen = pygame.display.set_mode(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        )
        pygame.display.set_caption(config.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.level_index = level_index % len(LEVELS)
        self.board = Board(LEVELS[self.level_index], _board_area())

    def run(self) -> None:
        """进入主循环，直到窗口被关闭。"""
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            self._handle_events()
            self.board.update(dt)
            self._draw()
        pygame.quit()

    def load_level(self, level_index: int) -> None:
        """切换到指定关卡并重置棋盘。"""
        self.level_index = level_index % len(LEVELS)
        self.board = Board(LEVELS[self.level_index], _board_area())

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.board.handle_click(pygame.mouse.get_pos())

    def _handle_key(self, key: int) -> None:
        """处理按键：``Esc`` 退出，左右方向键用于开发期切换关卡。"""
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_LEFT:
            self.load_level(self.level_index - 1)
        elif key == pygame.K_RIGHT:
            self.load_level(self.level_index + 1)

    def _draw(self) -> None:
        self.screen.fill(config.COLOR_BACKGROUND)
        self.board.draw(self.screen)
        pygame.display.flip()


def _board_area() -> pygame.Rect:
    """返回棋盘可用的屏幕区域。"""
    return pygame.Rect(
        config.BOARD_MARGIN,
        config.BOARD_MARGIN,
        config.WINDOW_WIDTH - 2 * config.BOARD_MARGIN,
        config.WINDOW_HEIGHT - 2 * config.BOARD_MARGIN,
    )
