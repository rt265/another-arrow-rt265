"""游戏主循环。

窗口由两个画面组成，切换逻辑集中在 :class:`Game` 里：

- **开始界面**（:class:`Scene.START`）：标题、玩法说明与“开始游戏”按钮；
- **游戏画面**（:class:`Scene.PLAYING`）：顶部信息栏（关卡 / 剩余箭头 / 失误 /
  重新开始按钮）+ 棋盘，通关或失败时在棋盘之上叠一张结算卡片。

点击棋盘上的箭头，畅通则飞出、被阻挡则扣一次失误（见 ``board`` / ``session``）；
失误耗尽弹出失败卡片，可重试本关；清空全部箭头弹出通关卡片，可进入下一关；
通关最后一关后回到开始界面。
"""

from __future__ import annotations

from enum import Enum

import pygame

from another_arrow_rt265 import config, ui
from another_arrow_rt265.session import GameStatus, Session


class Scene(Enum):
    """窗口当前显示的画面。"""

    START = "start"
    """开始界面：等待玩家点击“开始游戏”，此时不响应棋盘点击。"""

    PLAYING = "playing"
    """游戏画面：棋盘、信息栏与结算卡片（结算状态由 ``Session`` 决定）。"""


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
        self.scene = Scene.START
        self.session = Session(ui.board_area(), level_index=level_index)

    def run(self) -> None:
        """进入主循环，直到窗口被关闭。"""
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            self._handle_events()
            if self.scene is Scene.PLAYING:
                self.session.update(dt)
            self._draw()
        pygame.quit()

    def start(self) -> None:
        """离开开始界面，从第 1 关开始新的一局。"""
        self.session.load_level(0)
        self.scene = Scene.PLAYING

    def return_to_start(self) -> None:
        """返回开始界面，并让会话回到第 1 关的初始状态。"""
        self.session.load_level(0)
        self.scene = Scene.START

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
        """处理左键点击：先判当前画面的按钮，再落到棋盘。

        开始界面只响应“开始游戏”按钮；结算界面会盖住信息栏，因此只响应
        卡片上的主按钮；棋盘点击交给 :meth:`Session.click` 一律忽略。
        """
        if self.scene is Scene.START:
            if ui.start_button_rect().collidepoint(position):
                self.start()
            return

        if not self.session.is_playing:
            if ui.overlay_button_rect().collidepoint(position):
                self._run_primary_action()
            return

        if ui.restart_button_rect().collidepoint(position):
            self.session.restart_level()
            return

        self.session.click(position)

    def _handle_key(self, key: int) -> None:
        """处理按键：``Esc`` 退出，``Enter`` / 空格触发主按钮，``R`` 重开本关。

        ``R`` 与左右方向键只在游戏画面生效；开始界面只认 ``Esc`` 与主按钮快捷键。
        """
        if key == pygame.K_ESCAPE:
            self.running = False
            return
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._run_primary_action()
            return
        if self.scene is Scene.START:
            return

        if key == pygame.K_r:
            self.session.restart_level()
        elif key == pygame.K_LEFT:
            self.session.load_level(self.session.level_index - 1)
        elif key == pygame.K_RIGHT:
            self.session.load_level(self.session.level_index + 1)

    def _run_primary_action(self) -> None:
        """执行当前画面的主按钮动作（按钮点击与 Enter / 空格共用入口）。

        开始界面是“开始游戏”，游戏画面里进行中不作处理（避免误触丢进度），
        结算后则分别是“重试本关”“下一关”与“回到主界面”。
        """
        if self.scene is Scene.START:
            self.start()
        elif self.session.status is GameStatus.FAILED:
            self.session.restart_level()
        elif self.session.status is GameStatus.LEVEL_CLEARED:
            if self.session.is_last_level:
                self.return_to_start()
            else:
                self.session.advance()

    def _draw(self) -> None:
        if self.scene is Scene.START:
            ui.draw_start_screen(self.screen, self.session, pygame.mouse.get_pos())
        else:
            # 柔光跟着棋盘走，让棋盘看起来是画面的视觉中心。
            ui.draw_background(self.screen, self.session.board.rect.center)
            self.session.board.draw(self.screen)
            ui.draw_ui(self.screen, self.session, pygame.mouse.get_pos())
        pygame.display.flip()
