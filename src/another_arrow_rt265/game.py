"""游戏主循环。

本轮把各部件串成一个可玩的关卡 Demo：

- 顶部信息栏显示关卡号、剩余箭头、剩余失误与“重新开始”按钮；
- 点击棋盘上的箭头，畅通则飞出、被阻挡则扣一次失误（见 ``board`` / ``session``）；
- 失误耗尽弹出失败卡片，可重试本关；清空全部箭头弹出通关卡片，可进入下一关。

按既定设计，本轮不做开始界面，启动后直接进入第 1 关。
"""

from __future__ import annotations

import pygame

from another_arrow_rt265 import config, ui
from another_arrow_rt265.session import GameStatus, Session


class Game:
    """承载关卡流程的 pygame 应用，负责事件分发与画面刷新。"""

    def __init__(self, level_index: int = 0) -> None:
        """初始化窗口并创建会话。

        Args:
            level_index: 起始关卡序号，越界时会自动取模。
        """
        pygame.init()
        self.screen = pygame.display.set_mode(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        )
        pygame.display.set_caption(config.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.session = Session(ui.board_area(), level_index=level_index)

    def run(self) -> None:
        """进入主循环，直到窗口被关闭。"""
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            self._handle_events()
            self.session.update(dt)
            self._draw()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 用事件自带坐标而不是 pygame.mouse.get_pos()，避免鼠标在
                # 事件入队后又被移动而导致点击落到别的格子上。
                self._handle_click(event.pos)

    def _handle_click(self, position: tuple[int, int]) -> None:
        """处理左键点击：先判按钮，再落到棋盘。

        结算界面会盖住信息栏，因此结算状态下只响应卡片上的主按钮；
        棋盘点击交给 :meth:`Session.click` 一律忽略。
        """
        if not self.session.is_playing:
            if ui.overlay_button_rect().collidepoint(position):
                self._run_primary_action()
            return

        if ui.restart_button_rect().collidepoint(position):
            self.session.restart_level()
            return

        self.session.click(position)

    def _handle_key(self, key: int) -> None:
        """处理按键：``Esc`` 退出，``R`` 重开本关，左右方向键开发期切关。"""
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._run_primary_action()
        elif key == pygame.K_r:
            self.session.restart_level()
        elif key == pygame.K_LEFT:
            self.session.load_level(self.session.level_index - 1)
        elif key == pygame.K_RIGHT:
            self.session.load_level(self.session.level_index + 1)

    def _run_primary_action(self) -> None:
        """执行结算界面主按钮的动作（按钮点击与 Enter / 空格共用入口）。

        进行中按 Enter / 空格不作处理，避免误触丢掉进度。
        """
        if self.session.status is GameStatus.FAILED:
            self.session.restart_level()
        elif self.session.status is GameStatus.LEVEL_CLEARED:
            self.session.advance()

    def _draw(self) -> None:
        self.screen.fill(config.COLOR_BACKGROUND)
        self.session.board.draw(self.screen)
        ui.draw_ui(self.screen, self.session, pygame.mouse.get_pos())
        pygame.display.flip()
