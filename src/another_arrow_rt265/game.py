"""游戏主循环。

窗口由三个画面组成，切换逻辑集中在 :class:`Game` 里：

- **开始界面**（:class:`Scene.START`）：标题、玩法说明与“开始游戏”按钮，
  页脚是“关于”入口；
- **关于界面**（:class:`Scene.ABOUT`）：玩法、操作与制作信息，页脚按钮回主界面；
- **游戏画面**（:class:`Scene.PLAYING`）：顶部信息栏（回到主界面 / 关卡 /
  剩余箭头 / 用时 / 失误 / 重新开始）+ 棋盘，通关或失败时在棋盘之上叠一张
  结算卡片。

点击棋盘上的箭头，畅通则飞出、被阻挡则扣一次失误（见 ``board`` / ``session``）；
失误耗尽弹出失败卡片，可重试本关；清空全部箭头弹出通关卡片，可进入下一关。
信息栏左上角与结算卡片上都提供“回到主界面”，随时可以退回标题画面。

两个菜单页的内容在 :mod:`another_arrow_rt265.ui` 里用
:class:`~another_arrow_rt265.ui.MenuPage` 描述（有哪些说明卡片、有哪些按钮、
按钮对应哪个动作），本模块只负责“接线”：把按钮的 ``action`` 名分发到
:meth:`Game._run_action` 的动作表，并在按下 Enter / 空格时触发页面的默认按钮。
**新增一个界面时，写一个 ``MenuPage``、加一个 ``Scene`` 成员、再往动作表里补一行即可。**
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

    ABOUT = "about"
    """关于界面：玩法、操作与制作信息，只有一个“返回主界面”按钮。"""

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
            self._update(dt)
            self._draw()
        pygame.quit()

    def _update(self, dt: float) -> None:
        """推进当前画面，``dt`` 为上一帧耗时（秒）。

        只有游戏画面会让会话前进，因此在开始界面停留多久都不会计入
        关卡用时（计时器只是 :attr:`session` 的一部分状态）。
        """
        if self.scene is Scene.PLAYING:
            self.session.update(dt)

    def start(self) -> None:
        """离开开始界面，从第 1 关开始新的一局。"""
        self.session.load_level(0)
        self.scene = Scene.PLAYING

    def return_to_start(self) -> None:
        """返回开始界面，并让会话回到第 1 关的初始状态。"""
        self.session.load_level(0)
        self.scene = Scene.START

    def show_about(self) -> None:
        """切到“关于”界面（返回主界面走 :meth:`return_to_start`）。"""
        self.scene = Scene.ABOUT

    def _menu_page(self) -> ui.MenuPage:
        """返回当前菜单页的页面描述（只在开始 / 关于这类菜单画面上调用）。

        关卡总数与失误上限取自会话，所以“关于”界面里的数字与开始界面页脚
        提示行是同一个口径。
        """
        if self.scene is Scene.ABOUT:
            return ui.about_page(self.session.total_levels, self.session.max_mistakes)
        return ui.start_page(self.session.total_levels, self.session.max_mistakes)

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
        """处理左键点击：菜单页按声明的按钮命中，游戏画面先判按钮再落到棋盘。

        菜单页上的按钮来自 :class:`~another_arrow_rt265.ui.MenuPage` 的描述，
        因此新增界面时这里不必再改；游戏画面左上角与结算卡片左下角都有
        “回到主界面”；结算界面其余区域不响应棋盘点击。
        """
        if self.scene is not Scene.PLAYING:
            self._handle_menu_click(position)
            return

        if not self.session.is_playing:
            if ui.overlay_home_button_rect().collidepoint(position):
                self.return_to_start()
            elif ui.overlay_button_rect().collidepoint(position):
                self._run_primary_action()
            return

        if ui.hud_home_button_rect().collidepoint(position):
            self.return_to_start()
        elif ui.restart_button_rect().collidepoint(position):
            self.session.restart_level()
        else:
            self.session.click(position)

    def _handle_menu_click(self, position: tuple[int, int]) -> None:
        """把点击派给当前菜单页上声明过的按钮（绘制与命中判定共用同一份坐标）。"""
        for button, rect in ui.menu_layout(self._menu_page()).buttons:
            if rect.collidepoint(position):
                self._run_action(button.action)
                return

    def _handle_key(self, key: int) -> None:
        """处理按键：``Esc`` 退出，``Enter`` / 空格触发主按钮，``H`` 回主界面。

        ``H`` 在菜单页与游戏画面都生效；``R`` 与左右方向键只在游戏画面生效，
        免得在开始界面误触改掉进度。
        """
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._run_primary_action()
        elif key == pygame.K_h:
            self.return_to_start()
        elif self.scene is Scene.PLAYING:
            if key == pygame.K_r:
                self.session.restart_level()
            elif key == pygame.K_LEFT:
                self.session.load_level(self.session.level_index - 1)
            elif key == pygame.K_RIGHT:
                self.session.load_level(self.session.level_index + 1)

    def _run_primary_action(self) -> None:
        """执行当前画面的主按钮动作（按钮点击与 Enter / 空格共用入口）。

        菜单页取 :meth:`ui.MenuPage.default_action`（主按钮优先），因此新增页面
        只要声明了按钮就自动获得 Enter / 空格支持；游戏画面里进行中不作处理
        （避免误触丢进度），结算后则分别是“重试本关”与“下一关”（最后一关回到
        第 1 关重开一轮）。想回主界面走旁边的“回到主界面”按钮或 ``H`` 键，
        不共用这个入口。
        """
        if self.scene is Scene.PLAYING:
            if self.session.status is GameStatus.FAILED:
                self.session.restart_level()
            elif self.session.status is GameStatus.LEVEL_CLEARED:
                self.session.advance()
            return

        action = self._menu_page().default_action()
        if action is not None:
            self._run_action(action)

    def _run_action(self, action: str) -> None:
        """执行菜单动作。

        这是界面与逻辑之间唯一的接口：``ui`` 里的按钮只声明动作名，具体做什么
        都在这个表里。新增一个界面时，把它的按钮动作补到这里即可。

        Raises:
            KeyError: 动作名没有登记（通常是按钮写错了 ``action``）。
        """
        actions = {
            "start": self.start,
            "about": self.show_about,
            "home": self.return_to_start,
        }
        handler = actions.get(action)
        if handler is None:
            msg = f"未注册的菜单动作：{action}"
            raise KeyError(msg)
        handler()

    def _draw(self) -> None:
        mouse = pygame.mouse.get_pos()
        if self.scene is Scene.PLAYING:
            # 柔光跟着棋盘走，让棋盘看起来是画面的视觉中心。
            ui.draw_background(self.screen, self.session.board.rect.center)
            self.session.board.draw(self.screen)
            ui.draw_ui(self.screen, self.session, mouse)
        elif self.scene is Scene.ABOUT:
            ui.draw_about_screen(self.screen, self.session, mouse)
        else:
            ui.draw_start_screen(self.screen, self.session, mouse)
        pygame.display.flip()
