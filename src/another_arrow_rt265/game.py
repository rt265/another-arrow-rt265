"""游戏主循环。

窗口由五个画面组成，切换逻辑集中在 :class:`Game` 里：

- **开始界面**（:class:`Scene.START`）：标题、方向箭头装饰与两个玩法入口——
  “关卡模式”（内置关卡）与“自定义模式”；页脚是“设置 / 关于”；
- **关于界面**（:class:`Scene.ABOUT`）：制作信息，页脚按钮回主界面；
- **设置界面**（:class:`Scene.SETTINGS`）：音乐 / 音效两个开关，页脚“返回”回到打开它的画面；
- **自定义模式**（:class:`Scene.CUSTOM`）：两行滑动条调棋盘边长与箭头数量，
  中间那块棋盘是**实时预览**（参数一动就重新生成，见
  :mod:`another_arrow_rt265.custom`），页脚是“返回 / 换一关 / 开始游戏”；
- **游戏画面**（:class:`Scene.PLAYING`）：顶部信息栏（回到主界面 / 关卡 /
  剩余箭头 / 用时 / 失误 / 重新开始）+ 棋盘，通关或失败时在棋盘之上叠一张
  结算卡片；第 1 关还会在棋盘上方挂一条可交互的教程提示
  （进度见 :mod:`another_arrow_rt265.tutorial`），玩家跟着高亮箭头点几下
  就能学会全部规则，不必先在首屏读一段文字说明。

点击棋盘上的箭头，畅通则飞出、被阻挡则扣一次失误（见 ``board`` / ``session``）；
失误耗尽弹出失败卡片，可重试本关；清空全部箭头弹出通关卡片，可进入下一关。
信息栏左上角与结算卡片上都提供“回到主界面”，随时可以退回标题画面。
**自定义模式是另一份关卡列表**：它只有一关，因此通关卡片的主按钮是“再玩一次”；
两种模式各有自己的会话（见 :meth:`start` / :meth:`start_custom`），
互不串场。

**辅助线**（事项 11）是一个可选功能，默认关闭：右下角有一颗常驻开关（``G`` 键同效），
打开后每个箭头都沿当前的前进方向拉一条虚线——顶到棋盘边缘说明点得动，
停在另一个箭头上说明点不动（见 :meth:`~another_arrow_rt265.board.Board.guide_line`），
鼠标指着的那条更亮。开关存在 :attr:`Game.show_guides` 上，属于窗口而非关卡，
重开本关 / 换关都不会把它关掉；它会一直摆在棋盘外面（不盖任何格子），
棋盘点击、倒计时与失误判定都不受影响。

两个菜单页的内容在 :mod:`another_arrow_rt265.ui` 里用
:class:`~another_arrow_rt265.ui.MenuPage` 描述（有哪些说明卡片、有哪些按钮、
按钮对应哪个动作），本模块只负责“接线”：把按钮的 ``action`` 名分发到
:meth:`Game._run_action` 的动作表，并在按下 Enter / 空格时触发页面的默认按钮。
**新增一个界面时，写一个 ``MenuPage``、加一个 ``Scene`` 成员、再往动作表里补一行即可。**

**窗口可以自由缩放**（拖边、最大化）：几何按 :mod:`another_arrow_rt265.viewport` 把
720×720 的设计尺寸等比映射到当前窗口并居中，文字与图形都是照着目标尺寸重画的；
窗口尺寸变化由 :meth:`Game._sync_window_size` 每帧核对后接管——换视口、让会话把棋盘
重新摆到新的可用区域，**关卡进度、失误、计时与教程进度都不受影响**。

**音频**（事项 16）由 :class:`~another_arrow_rt265.audio.Audio` 统一播放：窗口一打开就
循环放背景音乐，操作与规则事件各配一声音效（按钮、箭头飞出、撞墙、通关、失败）。
声音是**旁白而不是规则**：本模块只负责“看见了什么就响哪一声”，
:mod:`another_arrow_rt265.session` / :mod:`another_arrow_rt265.board` 对音频一无所知，
所以没有声卡时（headless、CI）整套逻辑照常跑，只是安静一点。

**设置界面**（事项 17）也只是一张菜单页：两个开关（背景音乐 / 音效）由
:meth:`Game.toggle_music` / :meth:`Game.toggle_sound` 改 :attr:`Game.audio` 上的开关位，
页面描述则按当前取值重新生成（见 :meth:`Game._menu_page`）。它可以从开始界面的页脚按钮
或游戏中的 ``S`` 键打开，并且**记得自己是从哪儿来的**：除了回开始界面，它还能回游戏，
回去时关卡进度、失误、计时与教程进度都不变（见 :meth:`show_settings` /
:meth:`leave_settings`）。

**自定义模式**（事项 19）把参数放在 :attr:`Game.custom`（一个
:class:`~another_arrow_rt265.custom.CustomLevel`）上，画面上的两行滑动条只声明
“改哪个参数”（:class:`~another_arrow_rt265.ui.SliderRow`），取值由
:meth:`Game._set_custom_parameter` 写回：参数真的变了才重建预览棋盘
（:meth:`_rebuild_custom_preview`），因此拖动滑动条时“生成”与“预览刷新”都只发生
在取值跨过一档的那一帧。预览用的是一块**真正的**
:class:`~another_arrow_rt265.board.Board`（:attr:`Game.custom_board`），
所以参数区里看到的箭头与进场后完全一致；它只负责画，点击一律不落到它身上。
“开始游戏”把当前参数生成的关卡交给一个**只含这一关**的会话
（:meth:`start_custom`），于是规则层不必知道“自定义”这回事，
只有信息栏与结算文案按 :attr:`~another_arrow_rt265.session.Session.is_custom`
换个说法（见 ``ui.level_chip_text`` / ``ui.overlay_button_text``）。
"""

from __future__ import annotations

from enum import Enum

import pygame

from another_arrow_rt265 import audio, config, custom, ui, viewport
from another_arrow_rt265.board import Board, ClickResult
from another_arrow_rt265.session import GameStatus, Session


class Scene(Enum):
    """窗口当前显示的画面。"""

    START = "start"
    """开始界面：等待玩家挑一种玩法（关卡模式 / 自定义模式），此时不响应棋盘点击。"""

    ABOUT = "about"
    """关于界面：制作信息，只有一个“返回主界面”按钮。"""

    SETTINGS = "settings"
    """设置界面：音乐 / 音效两个开关，页脚“返回”回到打开它的那个画面。"""

    CUSTOM = "custom"
    """自定义模式：两行滑动条调参数，中间实时预览生成出来的关卡。"""

    PLAYING = "playing"
    """游戏画面：棋盘、信息栏与结算卡片（结算状态由 ``Session`` 决定）。"""


class Game:
    """承载关卡流程的 pygame 应用，负责事件分发与画面刷新。"""

    def __init__(
        self, level_index: int = 0, *, audio_player: audio.Audio | None = None
    ) -> None:
        """初始化窗口并创建会话。

        Args:
            level_index: 起始关卡序号，越界时会自动取模。
            audio_player: 音频播放器；不传就新建一个真实的（测试可以塞一个只记账不发声的
                替身，用来断言“这个动作应该响哪一声”）。
        """
        pygame.init()
        # 窗口可以自由缩放（拖边、最大化）：界面几何全部按当前视口重算，
        # 见 `_sync_window_size()` 与 `viewport` 模块。
        self.screen = pygame.display.set_mode(config.WINDOW_SIZE, pygame.RESIZABLE)
        pygame.display.set_caption(config.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = Scene.START
        # 设置界面是从哪儿打开的（见 `show_settings` / `leave_settings`）：
        # 从开始界面进去就回开始界面，从游戏里进去就回游戏，**不碰会话**，
        # 因此中途进去调一下声音不会丢掉正在解的这一关。
        self._return_scene = Scene.START
        # 背景音乐从窗口打开放到程序退出：它不区分画面，也不再重播（start_music 幂等）。
        self.audio = audio.Audio() if audio_player is None else audio_player
        self.audio.start_music()
        # 辅助线开关（右下角的开关与 G 键共用）。默认关闭：它是可选功能，
        # 而不是“默认替玩家把答案标出来”。它是窗口级的显示偏好，而不是关卡状态：
        # 存在这里就不会因为重开本关、进入下一关而被重置。
        self.show_guides = False
        # 视口是窗口尺寸到“设计尺寸”的映射（等比 + 居中留白），界面与棋盘都读它；
        # 窗口尺寸变化时由 `_sync_window_size()` 重建，会话则只换棋盘几何、不丢进度。
        self.viewport = viewport.set_current(viewport.Viewport.fit(config.WINDOW_SIZE))
        self.session = Session(ui.board_area(), level_index=level_index)
        # 自定义模式（事项 19）：参数与实时预览都留在窗口上，因此回主界面、
        # 进设置、开一局再回来，调好的参数还是那副样子。
        self.custom = custom.CustomLevel()
        # 预览用的是一块**真正的棋盘**：画法与游戏里完全同源，参数一变就换一块
        # （见 `_rebuild_custom_preview`）。它只参与绘制，不接任何点击。
        self.custom_board = Board(self.custom.level, ui.custom_preview_area())
        # 正在拖的那一行滑动条（参数名），没在拖时为 None；见 `_handle_drag`。
        self._dragging_slider: str | None = None
        # 上一次看到的会话状态：用它把“状态变了”翻成一声通关 / 失败音效，
        # 因此不论状态是在点击里还是在刷新里翻的，都不会漏掉或多放。
        self._last_status = self.session.status

    def run(self) -> None:
        """进入主循环，直到窗口被关闭。"""
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            self._sync_window_size()
            self._handle_events()
            self._update(dt)
            self._draw()
        pygame.quit()

    def _sync_window_size(self) -> bool:
        """按当前窗口尺寸刷新视口与会话，窗口没变时什么也不做。

        每帧比一次窗口尺寸，而不是只听 ``VIDEORESIZE``：拖边、最大化、以及
        系统改缩放比例都会改变窗口尺寸，从“当前尺寸”反推最稳，也不会因为事件
        丢失或重复而算错。

        Returns:
            本次调用是否真的换了尺寸。
        """
        surface = pygame.display.get_surface()
        if surface is None:  # pragma: no cover - 只会在窗口被销毁后发生
            return False
        self.screen = surface
        if surface.get_size() == self.viewport.size:
            return False

        self.viewport = viewport.set_current(viewport.Viewport.fit(surface.get_size()))
        # 只换棋盘几何：关卡、失误、计时与教程进度都不重置。
        self.session.resize(ui.board_area())
        # 自定义模式的预览也是一块棋盘，同样跟着窗口换尺寸。
        self.custom_board.reshape(ui.custom_preview_area())
        return True

    def _update(self, dt: float) -> None:
        """推进当前画面，``dt`` 为上一帧耗时（秒）。

        只有游戏画面会让会话前进，因此在开始界面停留多久都不会计入
        关卡用时（计时器只是 :attr:`session` 的一部分状态）。
        通关 / 失败是在刷新里定下来的（飞出动画播完后的结算停顿），因此每帧
        核对一次状态变化，把结算音效补上。
        """
        if self.scene is Scene.PLAYING:
            self.session.update(dt)
            self._sync_audio_status()

    def _sync_audio_status(self) -> None:
        """会话状态变化时放一声音效（点击之后与每帧刷新后各核对一次）。

        只认“变了没有”，因此不用担心同一次结算被响两遍；重新开一关（状态回到
        ``PLAYING``）是安静地翻过去，不会放出任何声音。
        """
        status = self.session.status
        if status is self._last_status:
            return
        self._last_status = status
        if status is GameStatus.LEVEL_CLEARED:
            self.audio.play(audio.Cue.LEVEL_CLEARED)
        elif status is GameStatus.FAILED:
            self.audio.play(audio.Cue.LEVEL_FAILED)

    def start(self) -> None:
        """离开开始界面，从第 1 关开始新的一局（第 1 关带交互式教程）。

        从“自定义模式”回来时会**重建会话**：自定义关卡是另一份关卡列表，不重建的话
        关卡模式会接着玩刚才捏出来的那一关（见 :meth:`start_custom`）。因此
        切模式会重新开一局，本关的最佳成绩也从头记起。
        """
        if self.session.is_custom:
            self._swap_session(Session(self.session.area))
        self.session.load_level(0)
        self.scene = Scene.PLAYING

    def return_to_start(self) -> None:
        """返回开始界面，并让会话回到第 1 关的初始状态。"""
        self.session.load_level(0)
        self.scene = Scene.START

    def show_about(self) -> None:
        """切到“关于”界面（返回主界面走 :meth:`return_to_start`）。"""
        self.scene = Scene.ABOUT

    def show_custom(self) -> None:
        """切到“自定义模式”界面：参数与预览都保持上次离开时的样子。

        它和设置界面不一样，**不记“从哪儿来”**：参数页是开始界面的一个入口，
        页脚的“返回”就是回主界面（动作表里的 ``home``），不存在“回游戏”这回事。
        """
        self.scene = Scene.CUSTOM

    def start_custom(self) -> None:
        """用当前参数生成的那一关开一局（自定义模式只有这一关）。

        自定义模式与关卡模式各拿一个会话：这里把会话换成“只含这一关”的新会话，
        因此规则层不需要认识“自定义”这个概念，它看到的只是一份只有一关的关卡列表；
        界面要换个说法时读 :attr:`~another_arrow_rt265.session.Session.is_custom`。
        """
        self._swap_session(
            Session(
                self.session.area,
                levels=(self.custom.level,),
                max_mistakes=self.session.max_mistakes,
                is_custom=True,
            )
        )
        self.scene = Scene.PLAYING

    def reroll_custom(self) -> None:
        """自定义模式的“换一关”：参数不动，让同一组参数换出另一关。"""
        self.custom.reroll()
        self._rebuild_custom_preview()

    def _swap_session(self, session: Session) -> None:
        """换一个会话（切模式时用），并把音频的“状态变化”基准一起挪过去。

        不挪的话新会话的第一帧就会被当成一次状态变化——虽然它落到“进行中”上、
        不会真的出声，但基准对不上总归是个隐患（见 :meth:`_sync_audio_status`）。
        """
        self.session = session
        self._last_status = session.status

    def show_settings(self) -> None:
        """打开“设置”界面（记下是从哪个画面进来的，返回时回到原处）。

        已经在设置界面里就什么也不做，因此“进 / 出”不会因为重复触发而错乱。
        """
        if self.scene is Scene.SETTINGS:
            return
        self._return_scene = self.scene
        self.scene = Scene.SETTINGS

    def leave_settings(self) -> None:
        """关闭“设置”界面，回到打开它的那个画面。

        与会话无关：从游戏里进来时，关卡、失误、计时与教程进度都原封不动地留着
        （设置界面不是“开始”画面，不会走 :meth:`return_to_start` 那条重置路径）。
        关卡计时也只在进行中的画面上走字，因此进来翻开关不会计时。
        """
        if self.scene is not Scene.SETTINGS:
            return
        self.scene = self._return_scene

    def toggle_music(self) -> None:
        """开关背景音乐（关掉立刻停，打开立刻从头续上）。"""
        self.audio.music_enabled = not self.audio.music_enabled

    def toggle_sound(self) -> None:
        """开关音效（静音是在播放层拦下的，界面代码不必到处判断）。"""
        self.audio.sound_enabled = not self.audio.sound_enabled

    def _menu_page(self) -> ui.MenuPage:
        """返回当前菜单页的页面描述（只在开始 / 关于 / 设置 / 自定义这类画面上调用）。

        关卡总数与失误上限取自会话，所以“关于”界面里的数字与开始界面页脚
        提示行是同一个口径；设置界面的入参则是两个开关的**当前状态**，
        因此状态一变，页面描述（也就是开关画成开还是关）跟着变。
        自定义模式的页面描述不带参数——它的两行滑动条与实时预览另有几何函数
        （见 :mod:`another_arrow_rt265.ui`）。
        """
        if self.scene is Scene.ABOUT:
            return ui.about_page(self.session.total_levels, self.session.max_mistakes)
        if self.scene is Scene.SETTINGS:
            return ui.settings_page(self.audio.music_enabled, self.audio.sound_enabled)
        if self.scene is Scene.CUSTOM:
            return ui.custom_page()
        return ui.start_page(self.session.total_levels, self.session.max_mistakes)

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type in (pygame.VIDEORESIZE, pygame.WINDOWRESIZED):
                # 尺寸从窗口现读（事件自带的 w/h 在部分平台上不可靠），
                # 真正做事的是 `_sync_window_size()`。
                self._sync_window_size()
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 用事件自带坐标而不是 pygame.mouse.get_pos()，避免鼠标在
                # 事件入队后又被移动而导致点击落到别的格子上。
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEMOTION:
                # 只有按住某一行滑动条时才有意义（见 `_handle_drag`）。
                self._handle_drag(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                # 松开左键就是一次拖动的结尾，不论松开时鼠标在哪里。
                self._dragging_slider = None

    def _handle_click(self, position: tuple[int, int]) -> None:
        """处理左键点击：菜单页按声明的按钮命中，游戏画面先判按钮再落到棋盘。

        菜单页上的按钮来自 :class:`~another_arrow_rt265.ui.MenuPage` 的描述，
        因此新增界面时这里不必再改；自定义模式先判两行滑动条，再交给页脚按钮
        （见 :meth:`_handle_custom_click`）；游戏画面左上角与结算卡片左下角都有
        “回到主界面”；右下角的“辅助线”开关先于棋盘判定（它摆在棋盘外面，
        但万一以后调布局压到了棋盘，也应当是开关优先）；结算界面其余区域不响应
        棋盘点击；第 1 关的教程提示条只让“跳过教程”生效，条上的其他位置吃掉点击，
        免得漏到棋盘上。

        音效跟着“结果”而不是“位置”走：碰到按钮就响按钮声，碰到棋盘则由
        :meth:`_click_board` 按棋盘的答复选声（另见 :meth:`_sync_audio_status`）。
        滑动条是唯一**不发声**的控件：拖动是一串连续操作，每跨一档就响一声会变成噪声。
        """
        if self.scene is Scene.CUSTOM:
            self._handle_custom_click(position)
            return
        if self.scene is not Scene.PLAYING:
            self._handle_menu_click(position)
            return

        if not self.session.is_playing:
            if ui.overlay_home_button_rect().collidepoint(position):
                self.audio.play(audio.Cue.BUTTON)
                self.return_to_start()
            elif ui.overlay_button_rect().collidepoint(position):
                self._run_primary_action()
            return

        if ui.hud_home_button_rect().collidepoint(position):
            self.audio.play(audio.Cue.BUTTON)
            self.return_to_start()
        elif ui.restart_button_rect().collidepoint(position):
            self.audio.play(audio.Cue.BUTTON)
            self.session.restart_level()
        elif ui.guide_toggle_rect().collidepoint(position):
            self.audio.play(audio.Cue.BUTTON)
            self.show_guides = not self.show_guides
        elif (
            self.session.tutorial is not None
            and ui.tutorial_panel_rect().collidepoint(position)
        ):
            if ui.tutorial_skip_button_rect().collidepoint(position):
                self.audio.play(audio.Cue.BUTTON)
                self.session.skip_tutorial()
        else:
            self._click_board(position)

    def _click_board(self, position: tuple[int, int]) -> None:
        """把点击交给棋盘，并按棋盘的回答放出对应的音效。

        飞出与撞墙的声音都由 :class:`~another_arrow_rt265.board.ClickResult` 决定：
        点空不响（MISS），因此“拉一下空气”不会每次都给玩家一顿噪声。
        """
        result = self.session.click(position)
        if result is ClickResult.CLEARED:
            self.audio.play(audio.Cue.ARROW_FLY)
        elif result is ClickResult.BLOCKED:
            self.audio.play(audio.Cue.ARROW_COLLIDE)
        self._sync_audio_status()

    def _handle_menu_click(self, position: tuple[int, int]) -> None:
        """把点击派给当前菜单页上声明过的开关与按钮。

        开关行排在按钮之前：两者在页面上不重叠，但“点了开关就只切开关”这条语义
        应当写在前面（以后调排版压到一起时也不会变成点开关却退出了页面）。
        绘制与命中判定共用 :func:`ui.menu_layout` 的同一份坐标。
        """
        layout = ui.menu_layout(self._menu_page())
        for toggle, rect in layout.toggles:
            if rect.collidepoint(position):
                self._run_action(toggle.action)
                return
        for button, rect in layout.buttons:
            if rect.collidepoint(position):
                self._run_action(button.action)
                return

    # ------------------------------------------------------------ 自定义模式

    def _custom_sliders(self) -> tuple[ui.SliderRow, ...]:
        """当前参数下两行滑动条的几何（绘制与命中判定共用同一份坐标）。"""
        return ui.custom_slider_rows(
            self.custom.size, self.custom.arrows, self.custom.max_arrows
        )

    def _handle_custom_click(self, position: tuple[int, int]) -> None:
        """自定义模式：先判两行参数滑动条，剩下的交给页脚按钮。

        按下滑动条就顺手记下“正在拖它”（见 :meth:`_handle_drag`），因此按住不放
        一直拖着也能连续调节；点在滑动条之外的空白处什么也不发生（既不落到预览
        棋盘上，也不出声），预览本身**不接受点击**——它是看结果的，不是玩的。

        滑动条不发声（拖动是一串连续操作，每跨一档响一声会变成噪声），
        页脚按钮照旧由 :meth:`_run_action` 负责响声。
        """
        for row in self._custom_sliders():
            if row.rect.collidepoint(position):
                self._dragging_slider = row.key
                self._set_custom_parameter(row.key, ui.slider_value(row, position[0]))
                return
        self._handle_menu_click(position)

    def _handle_drag(self, position: tuple[int, int]) -> None:
        """拖动滑动条：按住不放时鼠标移到哪儿，参数就跟到哪儿。

        没在拖（或已经离开自定义模式）时什么都不做，因此普通的鼠标移动不会
        误改参数；松手由 ``MOUSEBUTTONUP`` 收尾（见 :meth:`_handle_events`）。
        """
        if self._dragging_slider is None or self.scene is not Scene.CUSTOM:
            return
        for row in self._custom_sliders():
            if row.key == self._dragging_slider:
                self._set_custom_parameter(row.key, ui.slider_value(row, position[0]))
                return

    def _set_custom_parameter(self, key: str, value: int) -> None:
        """把滑动条的新取值写回自定义参数，参数真的变了才重建预览棋盘。

        参数名就是控件声明的 ``key``（见
        :class:`~another_arrow_rt265.ui.SliderRow`）；夹边界与“值没变就不重算”
        都由 :class:`~another_arrow_rt265.custom.CustomLevel` 负责，
        因此拖到量程外、点在滑块当前位置上都不会有空转。

        Raises:
            KeyError: 参数名没有登记（通常是滑动条写错了 ``key``）。
        """
        if key == "size":
            changed = self.custom.change_size(value)
        elif key == "arrows":
            changed = self.custom.change_arrows(value)
        else:
            msg = f"未注册的自定义参数：{key}"
            raise KeyError(msg)
        if changed:
            self._rebuild_custom_preview()

    def _rebuild_custom_preview(self) -> None:
        """按新的关卡重建预览棋盘。

        预览是一块真棋盘（箭头、配色、格子几何全部与游戏里同源），换取代价是
        “参数一变就换一块对象”——它没有需要延续的动画，重新建比就地改关卡简单得多。
        """
        self.custom_board = Board(self.custom.level, ui.custom_preview_area())

    def _handle_key(self, key: int) -> None:
        """处理按键：``Esc`` 退出，``Enter`` / 空格触发主按钮，``H`` 回主界面。

        ``H`` 与 ``S`` 在任何画面上都生效（``S`` 是设置界面的开关：开着就关上、
        关着就打开）；``R``、``G`` 与左右方向键只在游戏画面生效，免得在开始界面或
        自定义模式里误触改掉进度、开关或参数（``G`` 与右下角那颗开关是同一个开关）。
        这些快捷键等价于按了某个按钮，因此同样响一声音效；``Esc`` 除外（它只是关窗口），
        以及在游戏进行中按 Enter / 空格——那下什么也没发生，不该给反馈。
        """
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._run_primary_action()
        elif key == pygame.K_h:
            self.audio.play(audio.Cue.BUTTON)
            self.return_to_start()
        elif key == pygame.K_s:
            self._toggle_settings()
        elif self.scene is Scene.PLAYING:
            if key == pygame.K_r:
                self.audio.play(audio.Cue.BUTTON)
                self.session.restart_level()
            elif key == pygame.K_g:
                self.audio.play(audio.Cue.BUTTON)
                self.show_guides = not self.show_guides
            elif key == pygame.K_LEFT:
                self.audio.play(audio.Cue.BUTTON)
                self.session.load_level(self.session.level_index - 1)
            elif key == pygame.K_RIGHT:
                self.audio.play(audio.Cue.BUTTON)
                self.session.load_level(self.session.level_index + 1)

    def _toggle_settings(self) -> None:
        """``S`` 键：在“设置 / 来处”两个画面之间切换（与页脚按钮同一条路径）。"""
        self.audio.play(audio.Cue.BUTTON)
        if self.scene is Scene.SETTINGS:
            self.leave_settings()
        else:
            self.show_settings()

    def _run_primary_action(self) -> None:
        """执行当前画面的主按钮动作（按钮点击与 Enter / 空格共用入口）。

        菜单页取 :meth:`ui.MenuPage.default_action`（主按钮优先），因此新增页面
        只要声明了按钮就自动获得 Enter / 空格支持（音效也由 :meth:`_run_action`
        一并包办）；游戏画面里进行中不作处理（避免误触丢进度），结算后则分别是
        “重试本关”与“下一关”（最后一关回到第 1 关重开一轮）。想回主界面走旁边的
        “回到主界面”按钮或 ``H`` 键，不共用这个入口。
        """
        if self.scene is Scene.PLAYING:
            if self.session.status is GameStatus.FAILED:
                self.audio.play(audio.Cue.BUTTON)
                self.session.restart_level()
            elif self.session.status is GameStatus.LEVEL_CLEARED:
                self.audio.play(audio.Cue.BUTTON)
                self.session.advance()
            return

        action = self._menu_page().default_action()
        if action is not None:
            self._run_action(action)

    def _run_action(self, action: str) -> None:
        """执行菜单动作（分发前先放一声音效——菜单上的开关与按钮都点得动）。

        这是界面与逻辑之间唯一的接口：``ui`` 里的开关与按钮只声明动作名，具体做什么
        都在这个表里（开关的“切换”也只是一个动作：状态存在窗口上，不在页面上）。
        新增一个界面时，把它的开关 / 按钮动作补到这里即可。

        Raises:
            KeyError: 动作名没有登记（通常是按钮写错了 ``action``）。
        """
        actions = {
            "start": self.start,
            "about": self.show_about,
            "home": self.return_to_start,
            "settings": self.show_settings,
            "settings-back": self.leave_settings,
            "toggle-music": self.toggle_music,
            "toggle-sound": self.toggle_sound,
            "custom": self.show_custom,
            "custom-start": self.start_custom,
            "custom-reroll": self.reroll_custom,
        }
        handler = actions.get(action)
        if handler is None:
            msg = f"未注册的菜单动作：{action}"
            raise KeyError(msg)
        self.audio.play(audio.Cue.BUTTON)
        handler()

    def _draw(self) -> None:
        mouse = pygame.mouse.get_pos()
        if self.scene is Scene.PLAYING:
            ui.draw_background(self.screen)
            # 鼠标位置交给棋盘：辅助线打开时，指着的那条会更亮。
            self.session.board.draw(self.screen, mouse, show_guides=self.show_guides)
            ui.draw_ui(self.screen, self.session, mouse, show_guides=self.show_guides)
        elif self.scene is Scene.ABOUT:
            ui.draw_about_screen(self.screen, self.session, mouse)
        elif self.scene is Scene.SETTINGS:
            ui.draw_settings_screen(
                self.screen,
                self.audio.music_enabled,
                self.audio.sound_enabled,
                mouse,
            )
        elif self.scene is Scene.CUSTOM:
            # 先画背景、标题、滑动条与页脚按钮，再把预览棋盘贴到中间那块留白上
            # （两者不重叠，见 `ui.custom_preview_area`）。
            ui.draw_custom_screen(self.screen, self.custom, mouse)
            self.custom_board.draw(self.screen)
        else:
            ui.draw_start_screen(self.screen, self.session, mouse)
        pygame.display.flip()
