"""菜单页（开始 / 关于）、信息栏（HUD）与结算覆盖层的绘制。

本模块只负责“画”，不修改任何游戏状态：按钮位置由 :func:`start_button_rect`、
:func:`hud_home_button_rect`、:func:`restart_button_rect`、
:func:`overlay_button_rect` 与 :func:`overlay_home_button_rect` 暴露给
:class:`~another_arrow_rt265.game.Game` 做命中判定，因此以后调排版只需要改这一个文件。

**布局常量一律按设计尺寸（720×720）写成绝对值**，再由 :mod:`another_arrow_rt265.viewport`
换算到当前窗口：几何函数（:func:`board_area`、:func:`menu_layout` …）**返回屏幕坐标**；
绘制里遇到设计长度（半径、留白、行距、字号……）时用 :func:`another_arrow_rt265.viewport.s`
现算，而 `rect.height // 2` 这类由矩形派生的值本身就是像素，不要再换算一次。

窗口一共有四类画面：

- 菜单页：大标题 + 副标题 +（可选）方向箭头装饰 +（可选）主按钮+ 若干开关行
  + 若干说明卡片 + 提示行 + 页脚按钮。开始界面、关于界面与设置界面都是菜单页，
  只是内容不同；
- 进行中：一条整宽信息栏（左侧“回到主界面”、中间四段统计分区、右侧“重新开始”
  按钮，分区之间用 1px 竖直分隔线隔开，见 :func:`draw_hud`），加上右下角
  “辅助线”开关（见 :func:`draw_guide_toggle`）；
- 教程（只在第 1 关）：棋盘上方的引导提示条 + 待点击箭头的呼吸高亮，
  叠加在“进行中”画面上（见 :func:`draw_tutorial`）；
- 通关 / 失败：叠加遮罩与卡片（正文下方额外报一下本关用时），
  底部并排“回到主界面”与主按钮（下一关 / 重试本关 / 再来一轮）。

菜单页的“接口”是 :class:`MenuPage`：页面用数据描述自己有哪些开关行、说明卡片与按钮，
排版、绘制与命中判定都由 :func:`menu_layout` 统一算出来；开关与按钮不直接绑定行为，
只声明一个动作名，由 :meth:`~another_arrow_rt265.game.Game._run_action` 分发。
因此**新增一个界面（关卡选择……）只需要写一个 :class:`MenuPage` 常量，
再在动作表里补一行**，不必再写一遍排版、绘制与事件分发代码。

组件的视觉效果统一由 :func:`_draw_panel` / :func:`_draw_primary_button` /
:func:`_draw_secondary_button` 提供：**纯色圆角底板 + 1px 描边**。扁平化之后不再有渐变、
投影与外发光，层次全部靠“块与块的明度差 + 描边”表达，配色取自 ``config`` 的“界面”一节；
按钮上的小图标来自 :mod:`another_arrow_rt265.icons`。

带弧线与斜边的图形（圆角面板与按钮、圆点、徽章、装饰箭头）都走
:mod:`another_arrow_rt265.sprites` 的超采样贴图：先在 4 倍画布上画、再缩回目标尺寸，
边缘因此带过渡色。``pygame.draw`` 的直接调用只剩下三类：轴对齐的线（分隔线——
本来就没有锯齿）、整屏背景与整条信息栏这种整块填色，以及棋盘上那些功能性的提示环。
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from enum import Enum
from typing import Final

import pygame

from another_arrow_rt265 import config, icons, resources, sprites, tutorial, viewport
from another_arrow_rt265.direction import Direction
from another_arrow_rt265.session import GameStatus, Session

# 界面文字统一使用随程序分发的 Noto Sans CJK SC（见 resources.font_path()），
# 下面这份名单只是“字体文件缺失”时的兜底：按名字匹配系统自带的 CJK 字体，
# 免得退化成方块字。
_FONT_CANDIDATES: Final[tuple[str, ...]] = (
    "microsoftyaheiui",
    "microsoftyahei",
    "msyh",
    "simhei",
    "simsun",
    "notosanscjksc",
    "notosanscjk",
    "pingfangsc",
    "heiti",
    "wenquanyimicrohei",
)


@dataclass(frozen=True)
class _TextStyle:
    """一处界面文字的样式：**字号 + 字重**，两件事各管一层信息。

    字号分层级（标题 / 数值 / 正文 / 标签），字重强调重点（见下表的取舍）。
    想改某处文字的“轻重”，先想清楚它在界面里是主角还是配角，再动这里的表。
    """

    size: int
    weight: resources.FontWeight = resources.DEFAULT_WEIGHT

    def font(self) -> pygame.font.Font:
        """返回这个样式对应的字体对象（按“实际字号 + 字重”缓存，见 :func:`_font`）。

        这里的 ``size`` 是**设计字号**：实际字号要乘上当前视口，因此窗口放大后文字是
        照着更大的字号重新渲染的，而不是把原来的字位图拉大（后者一定会糊）。
        """
        return _font(viewport.s(self.size), self.weight)


# 界面文字的字号与字重一览。共用同一套字重的文字写在同一行，读的时候按“角色”找：
# Bold 负责“标题 / 数值 / 按钮 / 卡片小标题”，Regular 负责“正文与标签”，
# Light 只用在**弱化的次要文字**上（英文副标题、页脚提示）——它们本来就该退到背景里。
_TEXT_HERO: Final[_TextStyle] = _TextStyle(68, resources.FontWeight.BOLD)
_TEXT_SUBTITLE: Final[_TextStyle] = _TextStyle(20, resources.FontWeight.LIGHT)
_TEXT_TITLE: Final[_TextStyle] = _TextStyle(36, resources.FontWeight.BOLD)
_TEXT_BODY: Final[_TextStyle] = _TextStyle(20)
_TEXT_BUTTON: Final[_TextStyle] = _TextStyle(20, resources.FontWeight.BOLD)
_TEXT_SECTION_TITLE: Final[_TextStyle] = _TextStyle(19, resources.FontWeight.BOLD)
_TEXT_RULE: Final[_TextStyle] = _TextStyle(17)
_TEXT_HINT: Final[_TextStyle] = _TextStyle(16, resources.FontWeight.LIGHT)
_TEXT_LABEL: Final[_TextStyle] = _TextStyle(15)
_TEXT_PROGRESS: Final[_TextStyle] = _TextStyle(15, resources.FontWeight.BOLD)
_TEXT_VALUE: Final[_TextStyle] = _TextStyle(24, resources.FontWeight.BOLD)

# 信息栏：一整条铺满设计框宽度的纯色栏，内部从左到右是“回到主界面”图标按钮、
# 四段统计分区（关卡 / 剩余箭头 / 用时 / 失误）、右侧“重新开始”按钮，分区之间用
# 1px 竖直分隔线隔开。窗口宽度有限，整行则好铺满一行，改动任何一项宽度前
# 先把下面这行 720 的账重新算一遍：
#   32 + 48 + 12 + 92 + (8+1+8) + 92 + (8+1+8) + 122 + (8+1+8) + 89 + 10 + 140 + 32
# 分区宽度按“最宽的那行字 + 两侧留白”取：用时读数最长（“99:59.9”），
# “剩余箭头”四个字则决定了第二段的下限。
_HUD_ICON_BUTTON_SIZE: Final[tuple[int, int]] = (48, 48)
_HUD_NAV_GAP: Final[int] = 12
_HUD_CHIP_HEIGHT: Final[int] = 72
# 最后一段只用于起手，它的实际宽度由“重新开始按钮的左边”倒推（见 hud_chip_rects）。
_HUD_CHIP_WIDTHS: Final[tuple[int, int, int, int]] = (92, 92, 122, 89)
# 分区之间的 1px 分隔线及其两侧留白：相邻两段分区之间共占 2 * 8 + 1 = 17。
_HUD_DIVIDER_GAP: Final[int] = 8
_HUD_DIVIDER_WIDTH: Final[int] = 1
# 分隔线上下各内缩多少：让它看起来是“把这一栏分开”，而不是“把这一栏切断”。
_HUD_DIVIDER_INSET: Final[int] = 6
# 相邻两段统计分区之间的水平间距（分隔线就落在它正中间）。
_HUD_DIVIDER_SPAN: Final[int] = 2 * _HUD_DIVIDER_GAP + _HUD_DIVIDER_WIDTH
_HUD_CHIP_PADDING: Final[int] = 14
_HUD_CHIP_CAPTION_TOP: Final[int] = 11
_HUD_CHIP_VALUE_TOP: Final[int] = 34
# 统计分区与右侧按钮之间的间隙（这里不画分隔线，只留一个近距离）。
_HUD_CHIP_BUTTON_GAP: Final[int] = 10

_MISTAKE_RADIUS: Final[int] = 7
_MISTAKE_SPACING: Final[int] = 22
_RESTART_BUTTON_SIZE: Final[tuple[int, int]] = (140, 46)

# 按钮上的小图标：尺寸与“图标与文字之间的间隙”。
_BUTTON_ICON_SIZE: Final[int] = 20
_BUTTON_ICON_GAP: Final[int] = 10

# 结算卡片：徽章 / 标题 / 正文 / 用时 / 底部按钮行自上而下排列。
# 底部并排放“回到主界面”与主按钮，两个按钮一起在卡片里居中。
_CARD_SIZE: Final[tuple[int, int]] = (460, 340)
_CARD_EMBLEM_TOP: Final[int] = 72
_CARD_TITLE_TOP: Final[int] = 140
_CARD_BODY_TOP: Final[int] = 184
# 用时单独占一行：它既是成绩也是“要不要再来一遍”的理由。
_CARD_TIME_TOP: Final[int] = 212
_OVERLAY_EMBLEM_RADIUS: Final[int] = 36
_OVERLAY_BUTTON_SIZE: Final[tuple[int, int]] = (196, 56)
_OVERLAY_BUTTON_GAP: Final[int] = 16
_OVERLAY_BUTTON_MARGIN: Final[int] = 34

# 菜单页（开始 / 关于 / 设置，以及后续新增的同类页面）：自上而下依次是
# 大标题 → 副标题 →（可选）方向箭头装饰 →（可选）主按钮 → 开关行 → 说明卡片
# → 提示行 → 页脚按钮。页脚按钮贴着页面底部排，因此各页面的“返回 / 次要入口”
# 总在同一条线上。
_GAME_TITLE: Final[str] = "一箭又一箭"
_GAME_SUBTITLE: Final[str] = "ANOTHER ARROW"
_PAGE_TITLE_Y: Final[int] = 126
_PAGE_SUBTITLE_Y: Final[int] = 194
# 方向箭头装饰的中心（只出现在开始界面）。
_PAGE_DECORATION_Y: Final[int] = 248
# 主按钮行的中心：排在标题装饰与说明卡片之间。
_PAGE_HERO_BUTTON_Y: Final[int] = 340
# 说明卡片的起点：有主按钮时排在按钮下方，否则直接从副标题底下开始。
_PAGE_SECTIONS_TOP: Final[int] = 420
_PAGE_SECTIONS_TOP_PLAIN: Final[int] = 272
_PAGE_SECTION_GAP: Final[int] = 18
_PAGE_HINT_GAP: Final[int] = 8
_PAGE_FOOTER_MARGIN: Final[int] = 32
_MENU_BUTTON_GAP: Final[int] = 16
_HERO_BUTTON_SIZE: Final[tuple[int, int]] = (264, 64)
_FOOTER_BUTTON_SIZE: Final[tuple[int, int]] = (196, 56)

_HERO_CHIP_SIZE: Final[int] = 52
_HERO_CHIP_GAP: Final[int] = 18
_HERO_DIRECTIONS: Final[tuple[Direction, ...]] = (
    Direction.RIGHT,
    Direction.UP,
    Direction.LEFT,
    Direction.DOWN,
)

# 说明卡片：一行小标题 + 若干行带圆点的正文。高度按正文行数推出来——
# 小标题占 66px，之后每行 30px，行文字本身按 24px 算（17 号字的高度），
# 最后留 8px 底边距，于是三行正文刚好是 158px，与旧的“玩法”卡片一样高。
# 宽度则按“最宽的正文放得下”倒推：最宽的一行是关于界面的仓库地址（拉丁字母），
# 17 号 Regular 量到 474px，加上圆点缩进 22 与两侧内边距 28×2 共需 552px。
# 原来的 540 是按可变字体的拉丁字宽定的，换成静态字重后拉丁字形宽了一点（453 → 474），
# 因此留到 576（两侧各 72px 外边距）。
_SECTION_WIDTH: Final[int] = 576
_SECTION_PADDING: Final[int] = 28
_SECTION_CAPTION_TOP: Final[int] = 20
_SECTION_FIRST_LINE_TOP: Final[int] = 66
_SECTION_LINE_HEIGHT: Final[int] = 30
_SECTION_TEXT_HEIGHT: Final[int] = 24
_SECTION_BOTTOM_PADDING: Final[int] = 8

# 设置界面里的开关行：与说明卡片同宽的一条圆角栏（左边文字 + 右边滑动开关），
# 但矮一截，因为行里只有一行字；文字缩进与卡片的小标题对齐，
# 因此“开关行 + 卡片”竖着排下来左边缘是齐的。
_PAGE_TOGGLE_HEIGHT: Final[int] = 72
_PAGE_TOGGLE_PADDING: Final[int] = _SECTION_PADDING

# 教程提示条（只出现在第 1 关）：左侧是“第几步 / 共几步”，中间一句话指引，
# 右侧是“跳过教程”；同时给待点击的箭头套一圈呼吸高亮，把“点哪里”直接画出来。
_TUTORIAL_BAR_PADDING: Final[int] = 14
_TUTORIAL_DIVIDER_GAP: Final[int] = 12
_TUTORIAL_SKIP_MARGIN: Final[int] = 10
_TUTORIAL_RING_WIDTH: Final[int] = 3
# 高亮环呼吸时的透明度区间（最淡 / 最亮）与阻挡提示环的透明度。
_TUTORIAL_RING_ALPHA: Final[tuple[int, int]] = (110, 200)
_TUTORIAL_BLOCKER_ALPHA: Final[int] = 150
_TUTORIAL_BLOCKER_GROW: Final[int] = 4
_TUTORIAL_BLOCKER_WIDTH: Final[int] = 2

# 小贴图的缓存上限：装饰箭头与结算徽章的绘制参数（尺寸 + 颜色 + 状态）就那么几种。
_SMALL_SPRITE_CACHE: Final[int] = 64


# ---------------------------------------------------------------- 菜单页描述
# 下面这组数据结构是“新增界面”的接口：界面用它们描述自己有什么内容，
# 排版与绘制交给 :func:`menu_layout` 与 :func:`draw_menu_page`。


@dataclass(frozen=True)
class MenuSection:
    """菜单页上的一块说明卡片：一行小标题 + 若干行正文。"""

    caption: str
    lines: tuple[str, ...]

    @property
    def height(self) -> int:
        """卡片高度：按正文行数自适应，保证文字上下留白一致。"""
        return (
            _SECTION_FIRST_LINE_TOP
            + max(0, len(self.lines) - 1) * _SECTION_LINE_HEIGHT
            + _SECTION_TEXT_HEIGHT
            + _SECTION_BOTTOM_PADDING
        )


class MenuButtonPlacement(Enum):
    """按钮在菜单页上的位置。"""

    HERO = "hero"
    """主按钮：方向箭头装饰下方、开关行与说明卡片之前。"""

    FOOTER = "footer"
    """页脚按钮：整页内容的最后一行，整排居中并贴住页面底部留白。"""


@dataclass(frozen=True)
class MenuButton:
    """菜单页上的一个按钮。

    ``action`` 是交给 ``Game`` 分发的动作名：``ui`` 只声明“这个按钮长什么样、
    点了要做哪个动作”，具体做什么由
    :meth:`~another_arrow_rt265.game.Game._run_action` 决定，因此新增页面不必改动
    绘制与事件分发代码。
    """

    action: str
    text: str
    icon: icons.Icon
    primary: bool = False
    placement: MenuButtonPlacement = MenuButtonPlacement.FOOTER


@dataclass(frozen=True)
class MenuToggle:
    """菜单页上的一个开关行：左边文字、右边滑动开关（组件见 :func:`_draw_switch_row`）。

    与 :class:`MenuButton` 一样只声明“做什么 + 长什么样”：``action`` 交给
    ``Game._run_action`` 分发，``enabled`` 只是**当前取值**（决定开关画成开还是关）。
    因此页面描述是“内容 + 当前状态”，状态一变就重新生成一个页面——参见
    :func:`settings_page` 的入参。
    """

    action: str
    label: str
    enabled: bool


@dataclass(frozen=True)
class MenuPage:
    """一个菜单页的内容描述（排版由 :func:`menu_layout` 统一算出来）。"""

    title: str
    subtitle: str
    sections: tuple[MenuSection, ...] = ()
    toggles: tuple[MenuToggle, ...] = ()
    buttons: tuple[MenuButton, ...] = ()
    decorations: bool = False
    hint: str | None = None

    def default_action(self) -> str | None:
        """返回按下 Enter / 空格时触发的动作：主按钮优先，其次是第一个按钮。"""
        for button in self.buttons:
            if button.primary:
                return button.action
        return self.buttons[0].action if self.buttons else None


@dataclass(frozen=True)
class MenuLayout:
    """一个菜单页算好的骨架坐标（绘制与命中判定共用同一份结果）。"""

    sections: tuple[pygame.Rect, ...]
    toggles: tuple[tuple[MenuToggle, pygame.Rect], ...]
    hint: pygame.Rect | None
    buttons: tuple[tuple[MenuButton, pygame.Rect], ...]


@functools.cache
def start_page(total_levels: int, max_mistakes: int) -> MenuPage:
    """返回开始界面的页面描述。

    开始界面刻意不放任何文字说明：规则改由第 1 关的交互式教程边玩边教
    （见 :func:`draw_tutorial`），屏幕只留标题、方向箭头装饰与三个入口
    （主按钮“开始游戏” + 页脚的“设置 / 关于”）。

    Args:
        total_levels: 关卡总数。开始界面不展示这个数字（关卡进度只在信息栏里出现），
            入参先与 :func:`about_page` 保持同形，以后要加提示行时直接可用。
        max_mistakes: 每关的失误次数上限，同上。
    """
    return MenuPage(
        title=_GAME_TITLE,
        subtitle=_GAME_SUBTITLE,
        buttons=(
            MenuButton(
                "start",
                "开始游戏",
                icons.Icon.NEXT,
                primary=True,
                placement=MenuButtonPlacement.HERO,
            ),
            MenuButton("settings", "设置", icons.Icon.SETTINGS),
            MenuButton("about", "关于", icons.Icon.INFO),
        ),
        decorations=True,
    )


@functools.cache
def about_page(total_levels: int, max_mistakes: int) -> MenuPage:
    """返回“关于”界面的页面描述。

    这里只放制作信息：玩法说明由第 1 关的交互式教程承担，关卡数与失误上限只在信息栏
    里出现，因此下面两个入参目前不参与内容，只为与 :func:`start_page` 同形而保留。

    Args:
        total_levels: 关卡总数（仅为入参同形，当前不展示）。
        max_mistakes: 每关的失误次数上限（同上）。
    """
    return MenuPage(
        title="关于",
        subtitle="ABOUT",
        sections=(
            MenuSection(
                "制作信息",
                (
                    f"版本 {config.VERSION}",
                    "使用 Pygame-ce 制作，和 DeepSeek V4.1 Flash 辅助开发",
                    "MIT License, Copyright (c) 2026 rt265",
                    "GitHub Repo: https://github.com/rt265/another-arrow-rt265",
                ),
            ),
        ),
        buttons=(MenuButton("home", "返回主界面", icons.Icon.HOME),),
    )


@functools.cache
def settings_page(music_enabled: bool, sound_enabled: bool) -> MenuPage:
    """返回“设置”界面的页面描述。

    两个开关的**当前取值属于页面内容**（它决定开关画成开还是关），因此从入参传进来，
    由 ``functools.cache`` 给四种组合各留一份。

    Args:
        music_enabled: 背景音乐当前是否打开。
        sound_enabled: 音效当前是否打开。
    """
    return MenuPage(
        title="设置",
        subtitle="SETTINGS",
        toggles=(
            MenuToggle("toggle-music", "背景音乐", music_enabled),
            MenuToggle("toggle-sound", "音效", sound_enabled),
        ),
        buttons=(MenuButton("settings-back", "返回", icons.Icon.BACK),),
    )


def _weight_fallbacks(
    weight: resources.FontWeight,
) -> tuple[resources.FontWeight, ...]:
    """返回字重的降级顺序：想要的那个 → 常规字重。"""
    if weight == resources.DEFAULT_WEIGHT:
        return (resources.DEFAULT_WEIGHT,)
    return (weight, resources.DEFAULT_WEIGHT)


@functools.lru_cache(maxsize=96)
def _font(
    size: int, weight: resources.FontWeight = resources.DEFAULT_WEIGHT
) -> pygame.font.Font:
    """按“字号 + 字重”取字体（带缓存）。

    优先使用随程序分发的静态字重（``assets/fonts/NotoSansCJKsc-<字重>.otf``，见
    :func:`resources.font_path`）；这个字重的文件缺失时先退回常规字重，再退回系统
    的中文字体；再没有就退回 pygame 内置字体，此时中文会显示为占位方块，但界面结构依旧完整。

    缓存有上限（而不是 ``functools.cache``）
    """
    if not pygame.font.get_init():
        pygame.font.init()
    for candidate in _weight_fallbacks(weight):
        bundled = resources.font_path(candidate)
        if bundled is not None:
            return pygame.font.Font(str(bundled), size)
    system = pygame.font.match_font(list(_FONT_CANDIDATES))
    font = pygame.font.Font(system or None, size)
    # 系统字体没有静态字重可选，Bold 只能用合成加粗近似（兜底路径，正常跑不到这里）。
    font.set_bold(weight == resources.FontWeight.BOLD)
    return font


@functools.lru_cache(maxsize=1)
def _shade(size: tuple[int, int]) -> pygame.Surface:
    """返回一张铺满窗口的半透明遮罩（只在尺寸变化时重建）。"""
    shade = pygame.Surface(size, pygame.SRCALPHA)
    shade.fill((*config.COLOR_OVERLAY, config.OVERLAY_ALPHA))
    return shade


def _mix(
    color_from: config.Color, color_to: config.Color, ratio: float
) -> config.Color:
    """按 ``ratio``（0.0 → ``color_from``，1.0 → ``color_to``）混合两个颜色。"""
    ratio = min(1.0, max(0.0, ratio))
    return (
        round(color_from[0] + (color_to[0] - color_from[0]) * ratio),
        round(color_from[1] + (color_to[1] - color_from[1]) * ratio),
        round(color_from[2] + (color_to[2] - color_from[2]) * ratio),
    )


def draw_background(surface: pygame.Surface) -> None:
    """把整屏背景铺成一块纯色（扁平化：不再有竖直渐变与径向柔光）。

    Args:
        surface: 绘制目标；会把它**整个**填满，包括非等比窗口两侧的留白。
    """
    surface.fill(config.COLOR_BACKGROUND)


def _draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill: config.Color,
    *,
    radius: int,
    border: config.Color | None = None,
    border_width: int | None = None,
) -> None:
    """画一块圆角纯色面板（填充 + 可选描边），是各种组件的公共外观。

    扁平化之后面板只剩“一层纯色 + 一圈细描边”：没有渐变、投影与外发光，
    块与块之间的层次全靠 ``fill`` 与背景的明度差表达。所有长度都是**屏幕尺寸**：
    调用方遇到 ``config`` 里的设计常量时先过一遍
    :func:`another_arrow_rt265.viewport.s`，而来自 ``rect`` 的值直接用；
    ``border_width`` 省略时取 :data:`config.UI_BORDER_WIDTH` 并按当前视口换算。

    圆角与描边的抗锯齿由 :mod:`another_arrow_rt265.sprites` 的超采样贴图提供，
    因此一个像素宽的描边也不会出现阶梯。
    """
    sprites.blit_round_rect(surface, rect, radius, fill)
    if border is not None:
        width = (
            viewport.s(config.UI_BORDER_WIDTH) if border_width is None else border_width
        )
        sprites.blit_round_rect(surface, rect, radius, border, width)


def _draw_arrow_glyph(
    surface: pygame.Surface,
    center: tuple[int, int],
    size: float,
    direction: Direction,
    color: config.Color,
) -> None:
    """在 ``center`` 处画一个指向 ``direction`` 的小箭头（装饰用）。

    形状见 :func:`_paint_arrow_glyph`；这里贴的是按“尺寸 + 方向 + 颜色”缓存的
    抗锯齿贴图（开始界面那四个方向圆牌每帧都一样，没必要每帧重画）。
    """
    sprite = _arrow_glyph_sprite(round(size), direction, color)
    surface.blit(sprite, sprite.get_rect(center=(round(center[0]), round(center[1]))))


@functools.lru_cache(maxsize=_SMALL_SPRITE_CACHE)
def _arrow_glyph_sprite(
    size: int, direction: Direction, color: config.Color
) -> pygame.Surface:
    """返回一张装饰箭头的抗锯齿贴图（正方形，箭头居中）。"""
    # 图形的最大外延：箭头尖端 0.66×size，再加上杆的半线宽（≈0.14×size），留一点余量。
    span = 2 * round(size * 0.82) + 3

    def paint(canvas: pygame.Surface, factor: int) -> None:
        _paint_arrow_glyph(
            canvas,
            (canvas.get_width() / 2, canvas.get_height() / 2),
            size * factor,
            direction,
            color,
        )

    return sprites.render((span, span), paint)


def _paint_arrow_glyph(
    surface: pygame.Surface,
    center: tuple[float, float],
    size: float,
    direction: Direction,
    color: config.Color,
) -> None:
    """把装饰箭头画到 ``surface`` 上（尺寸单位由调用方决定）。

    由一个三角箭头和一根短杆拼成——只画三角形会像播放键，加上杆之后
    才和棋盘上的箭头有一致的“方向感”。
    """
    unit_x, unit_y = direction.vector
    perpendicular_x, perpendicular_y = -unit_y, unit_x
    center_x, center_y = center

    tip = (center_x + unit_x * size * 0.66, center_y + unit_y * size * 0.66)
    head_base_x = center_x + unit_x * size * 0.05
    head_base_y = center_y + unit_y * size * 0.05
    half_width = size * 0.44
    pygame.draw.polygon(
        surface,
        color,
        (
            tip,
            (
                head_base_x + perpendicular_x * half_width,
                head_base_y + perpendicular_y * half_width,
            ),
            (
                head_base_x - perpendicular_x * half_width,
                head_base_y - perpendicular_y * half_width,
            ),
        ),
    )
    pygame.draw.line(
        surface,
        color,
        (center_x - unit_x * size * 0.58, center_y - unit_y * size * 0.58),
        (center_x + unit_x * size * 0.20, center_y + unit_y * size * 0.20),
        width=max(2, round(size * 0.28)),
    )


def board_area() -> pygame.Rect:
    """返回棋盘可用的屏幕区域（位于信息栏下方、窗口留白之内）。"""
    top = config.HUD_HEIGHT + config.BOARD_TOP_GAP
    return viewport.rect(
        config.HUD_PADDING,
        top,
        config.WINDOW_WIDTH - 2 * config.HUD_PADDING,
        config.WINDOW_HEIGHT - top - config.BOARD_MARGIN,
    )


def hud_rect() -> pygame.Rect:
    """返回顶部信息栏的区域（扁平化之后它同时就是那条通栏底的区域）。"""
    return viewport.rect(0, 0, config.WINDOW_WIDTH, config.HUD_HEIGHT)


def _hud_home_button() -> pygame.Rect:
    """设计坐标下信息栏左上角“回到主界面”按钮的区域。"""
    width, height = _HUD_ICON_BUTTON_SIZE
    return pygame.Rect(
        config.HUD_PADDING,
        (config.HUD_HEIGHT - height) // 2,
        width,
        height,
    )


def hud_home_button_rect() -> pygame.Rect:
    """返回信息栏左上角“回到主界面”图标按钮的区域（屏幕坐标）。"""
    return viewport.map(_hud_home_button())


def _hud_sections() -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
    """设计坐标下信息栏四段统计分区（关卡 / 剩余箭头 / 用时 / 失误）的区域。

    前三段从左往右排在“回到主界面”按钮之后，末段贴住“重新开始”按钮左侧，
    因此按钮宽度变化时两端的间距仍然保持一致；段与段之间留出 ``_HUD_DIVIDER_SPAN``
    的宽度给竖直分隔线。整行在设计坐标里算出来，最后统一映射到屏幕，
    所以“整行恰好填满两侧留白”在任何窗口尺寸下都成立。
    """
    top = (config.HUD_HEIGHT - _HUD_CHIP_HEIGHT) // 2
    level = pygame.Rect(
        _hud_home_button().right + _HUD_NAV_GAP,
        top,
        _HUD_CHIP_WIDTHS[0],
        _HUD_CHIP_HEIGHT,
    )
    arrows = pygame.Rect(
        level.right + _HUD_DIVIDER_SPAN, top, _HUD_CHIP_WIDTHS[1], _HUD_CHIP_HEIGHT
    )
    elapsed = pygame.Rect(
        arrows.right + _HUD_DIVIDER_SPAN, top, _HUD_CHIP_WIDTHS[2], _HUD_CHIP_HEIGHT
    )
    mistakes = pygame.Rect(0, top, _HUD_CHIP_WIDTHS[3], _HUD_CHIP_HEIGHT)
    mistakes.right = _restart_button().left - _HUD_CHIP_BUTTON_GAP
    return (level, arrows, elapsed, mistakes)


def hud_chip_rects() -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
    """返回信息栏四段统计分区的区域（屏幕坐标）。

    四段按“关卡 → 剩余箭头 → 用时 → 失误”从左到右排开，
    扁平化之前它们是四块独立卡片，现在是同一条信息栏里的四个分区。
    """
    level, arrows, elapsed, mistakes = _hud_sections()
    return (
        viewport.map(level),
        viewport.map(arrows),
        viewport.map(elapsed),
        viewport.map(mistakes),
    )


def hud_dividers() -> tuple[tuple[int, int, int], ...]:
    """返回信息栏内三条竖直分隔线的线段 ``(x, top, bottom)``（屏幕坐标）。

    每条线落在相邻两段统计分区的正中间，竖直方向按分区高度上下各内缩
    ``_HUD_DIVIDER_INSET``，看起来是“把这一栏分成四格”而不是“把这一栏切断”。
    绘制（:func:`draw_hud`）与测试共用这一份坐标。
    """
    level, arrows, elapsed, mistakes = _hud_sections()
    segments: list[tuple[int, int, int]] = []
    for previous, current in ((level, arrows), (arrows, elapsed), (elapsed, mistakes)):
        midpoint = (previous.right + current.left) // 2
        segments.append(
            (
                viewport.x(midpoint),
                viewport.y(previous.top + _HUD_DIVIDER_INSET),
                viewport.y(previous.bottom - _HUD_DIVIDER_INSET),
            )
        )
    return tuple(segments)


def _restart_button() -> pygame.Rect:
    """设计坐标下信息栏“重新开始”按钮的区域。"""
    width, height = _RESTART_BUTTON_SIZE
    return pygame.Rect(
        config.WINDOW_WIDTH - config.HUD_PADDING - width,
        (config.HUD_HEIGHT - height) // 2,
        width,
        height,
    )


def restart_button_rect() -> pygame.Rect:
    """返回信息栏上“重新开始”按钮的区域。"""
    return viewport.map(_restart_button())


def guide_toggle_rect() -> pygame.Rect:
    """返回右下角“辅助线”开关的区域。

    它贴在窗口右下角，是游戏画面上唯一一个“与关卡进度无关、随时可点”的控件。
    位置受一条硬约束：**不能盖住任何格子**——最大的棋盘（6x6）最后一排格子
    一直铺到设计坐标的 y=674，因此底边只留 ``config.GUIDE_TOGGLE_MARGIN`` 里的 8px，
    横向则照常用 24px。窗口缩放时格子与开关按同一个系数放大，
    所以这条“开关在棋盘外面”的关系不会变（``tests/test_ui.py`` 逐关逐格核对）。
    """
    width, height = config.GUIDE_TOGGLE_SIZE
    right_margin, bottom_margin = config.GUIDE_TOGGLE_MARGIN
    return viewport.rect(
        config.WINDOW_WIDTH - right_margin - width,
        config.WINDOW_HEIGHT - bottom_margin - height,
        width,
        height,
    )


def _switch_track_rect(row: pygame.Rect, padding: int) -> pygame.Rect:
    """返回滑动开关轨道的区域（贴在 ``row`` 右侧、垂直居中）。"""
    width, height = viewport.scaled(config.SWITCH_TRACK_SIZE)
    return pygame.Rect(
        row.right - viewport.s(padding) - width,
        row.centery - height // 2,
        width,
        height,
    )


def _guide_toggle_track_rect() -> pygame.Rect:
    """返回右下角“辅助线”开关轨道的区域。"""
    return _switch_track_rect(guide_toggle_rect(), config.SWITCH_PADDING)


def start_button_rect() -> pygame.Rect:
    """返回开始界面上“开始游戏”按钮的区域。"""
    return viewport.map(_hero_row_rects(1)[0])


def _home_footer_rects() -> tuple[pygame.Rect, pygame.Rect]:
    """开始界面页脚的两个入口 ``(设置, 关于)``（设计坐标）。

    开始界面是唯一一个有**两个**页脚按钮的页面：主入口“开始游戏”占着主按钮的位置，
    两个次要入口（设置 / 关于）并排贴底，回到主界面时不会找不到它们。
    """
    settings, about = _footer_row_rects(2)
    return (settings, about)


def settings_button_rect() -> pygame.Rect:
    """返回开始界面页脚“设置”按钮的区域。"""
    return viewport.map(_home_footer_rects()[0])


def about_button_rect() -> pygame.Rect:
    """返回开始界面页脚“关于”按钮的区域。"""
    return viewport.map(_home_footer_rects()[1])


def about_back_button_rect() -> pygame.Rect:
    """返回“关于”界面页脚“返回主界面”按钮的区域。"""
    return viewport.map(_footer_row_rects(1)[0])


def settings_back_button_rect() -> pygame.Rect:
    """返回“设置”界面页脚“返回”按钮的区域。"""
    return viewport.map(_footer_row_rects(1)[0])


def _stack_sections(
    sections: tuple[MenuSection, ...], top: int
) -> tuple[pygame.Rect, ...]:
    """把说明卡片自上而下排开，返回它们的区域（设计坐标）。"""
    left = (config.WINDOW_WIDTH - _SECTION_WIDTH) // 2
    rects: list[pygame.Rect] = []
    cursor = top
    for index, section in enumerate(sections):
        cursor += _PAGE_SECTION_GAP if index else 0
        rect = pygame.Rect(left, cursor, _SECTION_WIDTH, section.height)
        rects.append(rect)
        cursor = rect.bottom
    return tuple(rects)


def _stack_toggles(
    toggles: tuple[MenuToggle, ...], top: int
) -> tuple[pygame.Rect, ...]:
    """把开关行自上而下排开，返回它们的区域（设计坐标）。

    与 :func:`_stack_sections` 同一套排法（宽度、间距、起点都一样），只是行高固定，
    因此“开关行 + 说明卡片”竖着排下来是一条整齐的栏。
    """
    left = (config.WINDOW_WIDTH - _SECTION_WIDTH) // 2
    rects: list[pygame.Rect] = []
    cursor = top
    for index, _ in enumerate(toggles):
        cursor += _PAGE_SECTION_GAP if index else 0
        rect = pygame.Rect(left, cursor, _SECTION_WIDTH, _PAGE_TOGGLE_HEIGHT)
        rects.append(rect)
        cursor = rect.bottom
    return tuple(rects)


def _hero_row_rects(count: int) -> tuple[pygame.Rect, ...]:
    """返回主按钮行的区域（居中排在标题装饰下方，设计坐标）。"""
    width, height = _HERO_BUTTON_SIZE
    left = _row_left(count, width)
    top = _PAGE_HERO_BUTTON_Y - height // 2
    return tuple(
        pygame.Rect(left + index * (width + _MENU_BUTTON_GAP), top, width, height)
        for index in range(count)
    )


def _footer_row_rects(count: int) -> tuple[pygame.Rect, ...]:
    """返回页脚按钮行的区域（居中，并与页面底部留白对齐，设计坐标）。"""
    width, height = _FOOTER_BUTTON_SIZE
    left = _row_left(count, width)
    top = config.WINDOW_HEIGHT - _PAGE_FOOTER_MARGIN - height
    return tuple(
        pygame.Rect(left + index * (width + _MENU_BUTTON_GAP), top, width, height)
        for index in range(count)
    )


def _row_left(count: int, width: int) -> int:
    """返回 ``count`` 个宽 ``width`` 的按钮横向居中时的左边界（设计坐标）。"""
    row_width = count * width + max(0, count - 1) * _MENU_BUTTON_GAP
    return (config.WINDOW_WIDTH - row_width) // 2


def menu_layout(page: MenuPage) -> MenuLayout:
    """算出一个菜单页的骨架坐标：说明卡片、提示行与按钮。

    整个页面先在**设计坐标**里排好（各块之间的间距都是设计值），最后统一按当前
    视口映射到屏幕，因此窗口缩放时各块之间的比例与相对位置不会变。

    绘制（:func:`draw_menu_page`）与命中判定（``Game._handle_menu_click``）都读
    这一份结果，因此开关 / 按钮画在哪里就能点在哪里，不会两边各算一遍而错位。
    """
    hero = tuple(b for b in page.buttons if b.placement is MenuButtonPlacement.HERO)
    footer = tuple(b for b in page.buttons if b.placement is MenuButtonPlacement.FOOTER)

    top = _PAGE_SECTIONS_TOP if hero else _PAGE_SECTIONS_TOP_PLAIN
    toggle_rects = _stack_toggles(page.toggles, top)
    sections_top = toggle_rects[-1].bottom + _PAGE_SECTION_GAP if toggle_rects else top
    sections = _stack_sections(page.sections, sections_top)
    hint = None
    if page.hint is not None:
        bottom = sections[-1].bottom if sections else sections_top
        hint = pygame.Rect(
            (config.WINDOW_WIDTH - _SECTION_WIDTH) // 2,
            bottom + _PAGE_HINT_GAP,
            _SECTION_WIDTH,
            _SECTION_TEXT_HEIGHT,
        )

    hero_rects = _hero_row_rects(len(hero))
    footer_rects = _footer_row_rects(len(footer))
    buttons: list[tuple[MenuButton, pygame.Rect]] = []
    hero_index = footer_index = 0
    for button in page.buttons:
        if button.placement is MenuButtonPlacement.HERO:
            buttons.append((button, viewport.map(hero_rects[hero_index])))
            hero_index += 1
        else:
            buttons.append((button, viewport.map(footer_rects[footer_index])))
            footer_index += 1
    return MenuLayout(
        sections=tuple(viewport.map(rect) for rect in sections),
        toggles=tuple(
            (toggle, viewport.map(rect))
            for toggle, rect in zip(page.toggles, toggle_rects, strict=True)
        ),
        hint=None if hint is None else viewport.map(hint),
        buttons=tuple(buttons),
    )


def _overlay_card() -> pygame.Rect:
    """设计坐标下结算卡片的区域（在设计框里居中）。"""
    card = pygame.Rect((0, 0), _CARD_SIZE)
    card.center = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2)
    return card


def overlay_card_rect() -> pygame.Rect:
    """返回结算卡片的区域（在窗口中居中，屏幕坐标）。"""
    return viewport.map(_overlay_card())


def tutorial_panel_rect() -> pygame.Rect:
    """返回教程提示条的区域（第 1 关棋盘上方的空白带）。

    第 1 关是 4x4 的小棋盘，格子尺寸被 ``config.MAX_CELL_SIZE`` 顶住，于是
    棋盘的上下各留出一段空白；提示条放在上侧那条里，既不遮挡棋子，也不必把
    棋盘缩小（第 1 关的棋盘位置因此和正式关卡完全一致）。窗口缩放时提示条与格子
    按同一个系数变化，这条关系不变；``tests/test_tutorial.py`` 会把“提示条不压到
    第 1 关棋盘”钉住。
    """
    area = board_area()
    return pygame.Rect(
        area.left, area.top, area.width, viewport.s(config.TUTORIAL_BAR_HEIGHT)
    )


def tutorial_skip_button_rect() -> pygame.Rect:
    """返回教程提示条右侧“跳过教程”按钮的区域。"""
    panel = tutorial_panel_rect()
    width, height = viewport.scaled(config.TUTORIAL_SKIP_SIZE)
    return pygame.Rect(
        panel.right - viewport.s(_TUTORIAL_SKIP_MARGIN) - width,
        panel.centery - height // 2,
        width,
        height,
    )


def overlay_home_button_rect() -> pygame.Rect:
    """返回结算界面“回到主界面”按钮的区域（在按钮行左侧）。"""
    return _overlay_button_row()[0]


def overlay_button_rect() -> pygame.Rect:
    """返回结算界面主按钮的区域（在按钮行右侧）。"""
    return _overlay_button_row()[1]


def _overlay_button_row() -> tuple[pygame.Rect, pygame.Rect]:
    """返回结算界面底部两个按钮的区域 ``(回到主界面, 主按钮)``。

    两个按钮等宽并排，整体在卡片里居中；绘制与命中判定共用这一份坐标。
    """
    card = overlay_card_rect()
    width, height = viewport.scaled(_OVERLAY_BUTTON_SIZE)
    gap = viewport.s(_OVERLAY_BUTTON_GAP)
    top = card.bottom - viewport.s(_OVERLAY_BUTTON_MARGIN) - height
    row_width = 2 * width + gap
    left = card.centerx - row_width // 2
    home = pygame.Rect(left, top, width, height)
    primary = pygame.Rect(left + width + gap, top, width, height)
    return (home, primary)


def overlay_button_text(session: Session) -> str:
    """返回结算界面主按钮的文案，与 ``Session`` 的流转保持一致。

    “回到主界面”始终由旁边的次要按钮提供，因此最后一关通关时主按钮
    改为“再来一轮”，不重复同一个动作。
    """
    if session.status is GameStatus.FAILED:
        return "重试本关"
    return "再来一轮" if session.is_last_level else "下一关"


def overlay_primary_icon(session: Session) -> icons.Icon:
    """返回结算界面主按钮上的图标，与 :func:`overlay_button_text` 对应。"""
    if session.status is GameStatus.FAILED:
        return icons.Icon.RESTART
    return icons.Icon.RESTART if session.is_last_level else icons.Icon.NEXT


def elapsed_text(seconds: float) -> str:
    """把秒数格式化成 ``分:秒.十分位``（如 ``0:12.3``）。

    先把时间取整到十分之一秒再做进位，因此 ``59.96`` 秒显示为 ``1:00.0``
    而不是 ``0:60.0``；负数按 0 处理，避免把动画误差显示成负时间。
    """
    tenths = round(max(0.0, seconds) * 10)
    minutes, rest = divmod(tenths, 600)
    return f"{minutes}:{rest / 10:04.1f}"


def result_time_text(session: Session) -> str:
    """返回结算卡片上的用时文案。

    通关时额外报一下本关最佳成绩：刚刷新记录就说“新纪录”，否则和这一把的
    用时并排显示，让玩家知道差在哪里。
    """
    elapsed = elapsed_text(session.elapsed)
    if session.status is not GameStatus.LEVEL_CLEARED:
        return f"本关用时 {elapsed}"
    if session.is_new_record:
        return f"新纪录 · 用时 {elapsed}"
    best = session.best_time
    if best is None:
        return f"本关用时 {elapsed}"
    return f"本关用时 {elapsed} · 最佳 {elapsed_text(best)}"


def draw_ui(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
    *,
    show_guides: bool = False,
) -> None:
    """按会话状态绘制游戏画面（信息栏、辅助线开关，结算时再加一层卡片）。

    Args:
        surface: 绘制目标。
        session: 当前会话，用于读取关卡号、剩余箭头、本关用时与失误次数。
        mouse: 鼠标位置，用于按钮与开关的悬停高亮；为 ``None`` 时不显示悬停效果。
        show_guides: 辅助线开关的状态，决定右下角开关画成“开”还是“关”。
    """
    draw_hud(surface, session, mouse)
    draw_guide_toggle(surface, show_guides, mouse)
    draw_tutorial(surface, session, mouse)
    if session.status is not GameStatus.PLAYING:
        draw_overlay(surface, session, mouse)


def _draw_hud_bar(surface: pygame.Surface) -> None:
    """铺满整条信息栏，并画上底边与三段竖直分隔线。

    背景是一条通栏的纯色块，底部一条 1px 描边把它与棋盘区分开；
    中间的分隔线直接用 ``pygame.draw.line``：轴对齐的直线本来就没有锯齿。
    """
    bar = hud_rect()
    surface.fill(config.COLOR_PANEL, bar)
    pygame.draw.line(
        surface,
        config.COLOR_PANEL_BORDER,
        (bar.left, bar.bottom - 1),
        (bar.right - 1, bar.bottom - 1),
    )
    for x, top, bottom in hud_dividers():
        pygame.draw.line(surface, config.COLOR_PANEL_BORDER, (x, top), (x, bottom))


def draw_hud(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制信息栏：一条通栏 + 回到主界面 / 四段统计分区 / 重新开始按钮。

    扁平化之后信息栏不再是四块各自带描边的卡片，而是**一条通栏**：先铺满整条栏，
    再用三条 1px 竖直分隔线把中间切成四格。分区只是排版上的概念，不再各自带边框，
    因此整条栏看上去只有一层底色。
    """
    _draw_hud_bar(surface)
    level_rect, arrows_rect, elapsed_rect, mistakes_rect = hud_chip_rects()

    _draw_icon_button(surface, hud_home_button_rect(), icons.Icon.HOME, mouse)
    _draw_stat_chip(
        surface,
        level_rect,
        "关卡",
        f"{session.level_number} / {session.total_levels}",
        config.COLOR_PRIMARY,
    )
    _draw_stat_chip(
        surface,
        arrows_rect,
        "剩余箭头",
        str(session.arrows_left),
        config.COLOR_TEXT,
    )
    # 读秒时只有十分位在跳，右对齐能让它待在原地不动，不会每 0.1 秒抽一下。
    _draw_stat_chip(
        surface,
        elapsed_rect,
        "用时",
        elapsed_text(session.elapsed),
        config.COLOR_TIME,
        align_right=True,
    )
    _draw_mistake_chip(surface, mistakes_rect, session)

    _draw_secondary_button(
        surface, restart_button_rect(), "重新开始", mouse, icon=icons.Icon.RESTART
    )


def _draw_switch_row(
    surface: pygame.Surface,
    row: pygame.Rect,
    label: str,
    enabled: bool,
    mouse: tuple[int, int] | None = None,
    *,
    style: _TextStyle = _TEXT_BUTTON,
    padding: int = config.SWITCH_PADDING,
) -> None:
    """画一行“左边文字 + 右边滑动开关”。

    这是“开关”这个组件的**唯一定义**：右下角的“辅助线”开关与“设置”界面里的
    “背景音乐 / 音效”两行都走它，因此轨道尺寸、滑块半径、开 / 关配色只有一份，
    不会两边各画一套（两处只有字号的差别，由 ``style`` 传进来）。

    开关必须**自己说明自己当前的档位**：关着时轨道是暗灰、文字也是灰的；打开后轨道
    换成强调色的青绿、文字提亮，悬停时整块提亮（与旁边的按钮同一套外观）。

    Args:
        surface: 绘制目标。
        row: 整行（或整块胶囊）的区域。
        label: 左侧文字。
        enabled: 当前是开还是关。
        mouse: 鼠标位置，仅用于悬停高亮。
        style: 左侧文字的字号与字重。
        padding: 文字与轨道的左右留白（设计长度）。
    """
    hovered = mouse is not None and row.collidepoint(mouse)
    lit = hovered or enabled

    _draw_panel(
        surface,
        row,
        config.COLOR_BUTTON_HOVER if lit else config.COLOR_BUTTON,
        radius=viewport.s(config.UI_RADIUS),
        border=config.COLOR_BUTTON_BORDER,
    )

    text = style.font().render(
        label, True, config.COLOR_TEXT if enabled else config.COLOR_TEXT_MUTED
    )
    surface.blit(
        text, (row.left + viewport.s(padding), row.centery - text.get_height() // 2)
    )

    # 轨道与滑块保持“胶囊 + 正圆”：它们是开关语义，不受统一圆角约束。
    track = _switch_track_rect(row, padding)
    sprites.blit_round_rect(
        surface,
        track,
        track.height // 2,
        config.SWITCH_TRACK_ON if enabled else config.SWITCH_TRACK_OFF,
    )
    # 滑块靠向哪一侧就是“开 / 关”的第二个信号（颜色之外再给一层冗余表达）。
    radius = viewport.s(config.SWITCH_KNOB_RADIUS)
    margin = (track.height - 2 * radius) // 2
    knob_x = track.right - radius - margin if enabled else track.left + radius + margin
    sprites.blit_circle(
        surface,
        (knob_x, track.centery),
        radius,
        config.SWITCH_KNOB_ON if enabled else config.SWITCH_KNOB_OFF,
    )


def draw_guide_toggle(
    surface: pygame.Surface,
    enabled: bool,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制右下角的“辅助线”开关（与设置里的开关同一个组件，只是小一号）。

    辅助线是可选功能，因此开关必须自己说明当前档位；具体画法见
    :func:`_draw_switch_row`。

    Args:
        surface: 绘制目标。
        enabled: 辅助线当前是否打开。
        mouse: 鼠标位置，仅用于悬停高亮。
    """
    _draw_switch_row(
        surface,
        guide_toggle_rect(),
        config.GUIDE_TOGGLE_LABEL,
        enabled,
        mouse,
        style=_TEXT_LABEL,
    )


def draw_tutorial(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制第 1 关的交互式教程：待点击箭头的高亮 + 顶部提示条。

    只有 :attr:`Session.tutorial` 有进度、且本关仍在进行中时才画：结算卡片弹出后
    提示条自动让位（已经在结算了，不必再教怎么点）。

    Args:
        surface: 绘制目标。
        session: 当前会话，教程进度与棋盘都从它读取。
        mouse: 鼠标位置，仅用于“跳过教程”按钮的悬停高亮。
    """
    progress = session.tutorial
    if progress is None or not session.is_playing:
        return
    hint = progress.hint
    if hint is None:
        return

    _draw_tutorial_highlight(surface, session, hint)

    panel = tutorial_panel_rect()
    _draw_panel(
        surface,
        panel,
        config.COLOR_PANEL,
        radius=viewport.s(config.UI_RADIUS),
        border=config.COLOR_PRIMARY,
    )

    # 左侧进度读数 → 竖分隔线 → 指引文案 → 右侧“跳过教程”，一行排开。
    progress_label = _TEXT_PROGRESS.font().render(
        hint.progress, True, config.COLOR_PRIMARY
    )
    surface.blit(
        progress_label,
        progress_label.get_rect(
            midleft=(panel.left + viewport.s(_TUTORIAL_BAR_PADDING), panel.centery)
        ),
    )
    divider_x = (
        panel.left
        + viewport.s(_TUTORIAL_BAR_PADDING)
        + progress_label.get_width()
        + viewport.s(_TUTORIAL_DIVIDER_GAP)
    )
    pygame.draw.line(
        surface,
        config.COLOR_PANEL_BORDER,
        (divider_x, panel.top + viewport.s(10)),
        (divider_x, panel.bottom - viewport.s(10)),
    )
    text = _TEXT_RULE.font().render(hint.text, True, config.COLOR_TEXT)
    surface.blit(
        text,
        text.get_rect(
            midleft=(divider_x + viewport.s(_TUTORIAL_DIVIDER_GAP), panel.centery)
        ),
    )
    _draw_compact_button(surface, tutorial_skip_button_rect(), "跳过教程", mouse)


def _draw_tutorial_highlight(
    surface: pygame.Surface,
    session: Session,
    hint: tutorial.TutorialHint,
) -> None:
    """给教程当前指向的箭头套一圈呼吸高亮，“点哪里”直接画在棋盘上。

    “点击被挡住的箭头”这一步会额外把挡路的箭头圈出来（细一档的红环），
    于是“谁挡住了谁”也从文字变成了看得见的图形。
    """
    progress = session.tutorial
    if progress is None:
        return
    board = session.board
    arrow = progress.suggested_arrow(board)
    if arrow is None:
        return

    pulse = 0.5 + 0.5 * math.sin(_tutorial_phase() * math.tau)
    grow = config.TUTORIAL_RING_GROW + 2 * pulse
    faint, bright = _TUTORIAL_RING_ALPHA
    alpha = round(faint + (bright - faint) * pulse)
    _draw_cell_ring(
        surface,
        board.cell_rect(arrow.row, arrow.col),
        grow,
        (*config.COLOR_PRIMARY, alpha),
        width=_TUTORIAL_RING_WIDTH,
    )

    if hint.step is tutorial.TutorialStep.BLOCKED:
        blocker = board.blocking_arrow(arrow)
        if blocker is not None:
            _draw_cell_ring(
                surface,
                board.cell_rect(blocker.row, blocker.col),
                _TUTORIAL_BLOCKER_GROW,
                (*config.COLOR_BLOCKER_HINT, _TUTORIAL_BLOCKER_ALPHA),
                width=_TUTORIAL_BLOCKER_WIDTH,
            )


def _tutorial_phase() -> float:
    """返回当前时刻在呼吸周期里的相位（0.0 ~ 1.0），只用于视觉提示。

    高亮环是纯装饰，不参与任何判定，因此直接读时钟，不必让棋盘再维护一份计时。
    """
    period = max(config.TUTORIAL_PULSE_SECONDS, 1e-6)
    return pygame.time.get_ticks() / 1000.0 % period / period


def _draw_cell_ring(
    surface: pygame.Surface,
    cell: pygame.Rect,
    grow: float,
    color: tuple[int, int, int, int],
    *,
    width: int,
) -> None:
    """在格子外围画一圈半透明描边（``color`` 的第 4 个分量是透明度）。

    ``grow`` 与 ``width`` 都是**设计长度**（含呼吸动画算出的小数），在这里按当前视口
    换算，因为要叠加到已经是像素尺寸的 ``cell`` 上。

    环本身贴的是抗锯齿的圆角描边；呼吸时半径会连续变化（每档差一个像素），
    按半径缓存就够用，而透明度是逐帧变化的，改的是贴图**副本**的整体 alpha。
    """
    grow_px = viewport.s(grow)
    rect = cell.inflate(2 * grow_px, 2 * grow_px)
    sprite = sprites.round_rect(
        rect.size,
        viewport.s(config.CELL_RADIUS) + grow_px,
        (*color[:3], 255),
        viewport.s(width),
    )
    if color[3] < 255:
        sprite = sprite.copy()
        sprite.set_alpha(color[3])
    surface.blit(sprite, rect.topleft)


def draw_overlay(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制结算界面：整屏遮罩 + 居中卡片（徽章 / 标题 / 文案 / 用时 / 底部按钮行）。"""
    surface.blit(_shade(surface.get_size()), (0, 0))

    cleared = session.status is GameStatus.LEVEL_CLEARED
    accent = config.COLOR_SUCCESS if cleared else config.COLOR_FAILURE
    card = overlay_card_rect()

    _draw_panel(
        surface,
        card,
        config.COLOR_PANEL,
        radius=viewport.s(config.UI_RADIUS),
        border=accent,
    )
    _draw_result_emblem(
        surface,
        (card.centerx, card.top + viewport.s(_CARD_EMBLEM_TOP)),
        accent,
        cleared,
    )
    title = _TEXT_TITLE.font().render(
        "关卡完成！" if cleared else "挑战失败", True, accent
    )
    surface.blit(
        title,
        title.get_rect(center=(card.centerx, card.top + viewport.s(_CARD_TITLE_TOP))),
    )

    body = _TEXT_BODY.font().render(_result_message(session), True, config.COLOR_TEXT)
    surface.blit(
        body,
        body.get_rect(center=(card.centerx, card.top + viewport.s(_CARD_BODY_TOP))),
    )

    # 刷新记录时这行改用主色（金），一眼就能看出“这把比之前快”。
    record = session.status is GameStatus.LEVEL_CLEARED and session.is_new_record
    timing = _TEXT_BODY.font().render(
        result_time_text(session),
        True,
        config.COLOR_PRIMARY if record else config.COLOR_TEXT_MUTED,
    )
    surface.blit(
        timing,
        timing.get_rect(center=(card.centerx, card.top + viewport.s(_CARD_TIME_TOP))),
    )

    _draw_secondary_button(
        surface,
        overlay_home_button_rect(),
        "回到主界面",
        mouse,
        icon=icons.Icon.HOME,
    )
    _draw_primary_button(
        surface,
        overlay_button_rect(),
        overlay_button_text(session),
        accent,
        mouse,
        icon=overlay_primary_icon(session),
    )


def _draw_result_emblem(
    surface: pygame.Surface,
    center: tuple[int, int],
    accent: config.Color,
    cleared: bool,
) -> None:
    """画结算卡片顶部的圆形徽章：通关画勾、失败画叉。

    底色圆、描边环与勾/叉一起画在一张缓存贴图里（见 :func:`_result_emblem_sprite`）：
    勾与叉都是斜线，贴图能把它们的阶梯一次性去掉，而拼接处也不会多出一条缝。
    """
    sprite = _result_emblem_sprite(viewport.s(_OVERLAY_EMBLEM_RADIUS), accent, cleared)
    surface.blit(sprite, sprite.get_rect(center=(round(center[0]), round(center[1]))))


@functools.lru_cache(maxsize=_SMALL_SPRITE_CACHE)
def _result_emblem_sprite(
    radius: int, accent: config.Color, cleared: bool
) -> pygame.Surface:
    """返回结算徽章的抗锯齿贴图（半径 ``radius``，图形居中）。"""
    span = 2 * radius + 3

    def paint(canvas: pygame.Surface, factor: int) -> None:
        center = (canvas.get_width() / 2, canvas.get_height() / 2)
        pygame.draw.circle(
            canvas,
            _mix(accent, config.COLOR_PANEL, 0.78),
            center,
            radius * factor,
        )
        pygame.draw.circle(
            canvas, accent, center, radius * factor, width=viewport.s(3) * factor
        )

        center_x, center_y = center
        stroke = viewport.s(5) * factor
        if cleared:
            pygame.draw.lines(
                canvas,
                accent,
                False,
                [
                    (
                        center_x - viewport.s(13) * factor,
                        center_y + viewport.s(1) * factor,
                    ),
                    (
                        center_x - viewport.s(4) * factor,
                        center_y + viewport.s(10) * factor,
                    ),
                    (
                        center_x + viewport.s(14) * factor,
                        center_y - viewport.s(10) * factor,
                    ),
                ],
                width=stroke,
            )
        else:
            pygame.draw.line(
                canvas,
                accent,
                (
                    center_x - viewport.s(10) * factor,
                    center_y - viewport.s(10) * factor,
                ),
                (
                    center_x + viewport.s(10) * factor,
                    center_y + viewport.s(10) * factor,
                ),
                width=stroke,
            )
            pygame.draw.line(
                canvas,
                accent,
                (
                    center_x - viewport.s(10) * factor,
                    center_y + viewport.s(10) * factor,
                ),
                (
                    center_x + viewport.s(10) * factor,
                    center_y - viewport.s(10) * factor,
                ),
                width=stroke,
            )

    return sprites.render((span, span), paint)


def draw_menu_page(
    surface: pygame.Surface,
    page: MenuPage,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制一个菜单页（连背景一起画，因为它独占整屏）。

    Args:
        surface: 绘制目标。
        page: 页面内容描述，排版由 :func:`menu_layout` 统一算出来。
        mouse: 鼠标位置，仅用于按钮的悬停高亮；为 ``None`` 时不显示悬停效果。
    """
    draw_background(surface)
    _draw_page_title(surface, page)
    if page.decorations:
        _draw_arrow_row(surface)

    layout = menu_layout(page)
    for toggle, rect in layout.toggles:
        _draw_menu_toggle(surface, rect, toggle, mouse)
    for rect, section in zip(layout.sections, page.sections, strict=True):
        _draw_section_panel(surface, rect, section)
    if layout.hint is not None and page.hint is not None:
        hint = _TEXT_HINT.font().render(page.hint, True, config.COLOR_TEXT_MUTED)
        surface.blit(hint, hint.get_rect(center=layout.hint.center))
    for button, rect in layout.buttons:
        _draw_menu_button(surface, button, rect, mouse)


def draw_start_screen(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制开始界面（页面内容见 :func:`start_page`）。

    Args:
        surface: 绘制目标。
        session: 当前会话；页面内容目前与它无关（关卡总数与失误上限只在信息栏里
            出现），入参先与其它画面保持同形。
        mouse: 鼠标位置，仅用于按钮的悬停高亮。
    """
    draw_menu_page(
        surface, start_page(session.total_levels, session.max_mistakes), mouse
    )


def draw_settings_screen(
    surface: pygame.Surface,
    music_enabled: bool,
    sound_enabled: bool,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制“设置”界面（页面内容见 :func:`settings_page`）。

    Args:
        surface: 绘制目标。
        music_enabled: 背景音乐开关的当前状态。
        sound_enabled: 音效开关的当前状态。
        mouse: 鼠标位置，仅用于开关行的悬停高亮。
    """
    draw_menu_page(surface, settings_page(music_enabled, sound_enabled), mouse)


def draw_about_screen(
    surface: pygame.Surface,
    session: Session,
    mouse: tuple[int, int] | None = None,
) -> None:
    """绘制“关于”界面（页面内容见 :func:`about_page`）。

    Args:
        surface: 绘制目标。
        session: 当前会话，关卡总数与失误上限的文案与开始界面同源。
        mouse: 鼠标位置，仅用于按钮的悬停高亮。
    """
    draw_menu_page(
        surface, about_page(session.total_levels, session.max_mistakes), mouse
    )


def _draw_page_title(surface: pygame.Surface, page: MenuPage) -> None:
    """画菜单页的标题：主色文字 + 拉开字距的英文副标题。

    扁平化之前标题下面垫了一份半透明的金色副本当光晕，现在只留一层文字：
    标题本身已经是全屏最大的字号，不需要再额外强调。
    """
    center_x = viewport.center()[0]

    title = _TEXT_HERO.font().render(page.title, True, config.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(center_x, viewport.y(_PAGE_TITLE_Y))))

    subtitle = _TEXT_SUBTITLE.font().render(
        " ".join(page.subtitle), True, config.COLOR_TEXT_MUTED
    )
    surface.blit(
        subtitle,
        subtitle.get_rect(center=(center_x, viewport.y(_PAGE_SUBTITLE_Y))),
    )


def _draw_arrow_row(surface: pygame.Surface) -> None:
    """在标题下方排一行四个方向的箭头圆牌，直观提示游戏主题。"""
    count = len(_HERO_DIRECTIONS)
    total = count * _HERO_CHIP_SIZE + (count - 1) * _HERO_CHIP_GAP
    left = (config.WINDOW_WIDTH - total) // 2
    top = _PAGE_DECORATION_Y - _HERO_CHIP_SIZE // 2

    for index, direction in enumerate(_HERO_DIRECTIONS):
        rect = viewport.map(
            pygame.Rect(
                left + index * (_HERO_CHIP_SIZE + _HERO_CHIP_GAP),
                top,
                _HERO_CHIP_SIZE,
                _HERO_CHIP_SIZE,
            )
        )
        _draw_panel(
            surface,
            rect,
            config.COLOR_PANEL,
            radius=viewport.s(config.UI_RADIUS),
            border=config.COLOR_PANEL_BORDER,
        )
        _draw_arrow_glyph(
            surface,
            rect.center,
            viewport.s(_HERO_CHIP_SIZE * 0.34),
            direction,
            config.COLOR_PRIMARY,
        )


def _draw_section_panel(
    surface: pygame.Surface, rect: pygame.Rect, section: MenuSection
) -> None:
    """画一块说明卡片：一行小标题 + 若干行带圆点的正文。"""
    _draw_panel(
        surface,
        rect,
        config.COLOR_PANEL,
        radius=viewport.s(config.UI_RADIUS),
        border=config.COLOR_PANEL_BORDER,
    )

    caption = _TEXT_SECTION_TITLE.font().render(
        section.caption, True, config.COLOR_PRIMARY
    )
    surface.blit(
        caption,
        (
            rect.left + viewport.s(_SECTION_PADDING),
            rect.top + viewport.s(_SECTION_CAPTION_TOP),
        ),
    )

    font = _TEXT_RULE.font()
    bullet_x = rect.left + viewport.s(_SECTION_PADDING + 6)
    text_x = rect.left + viewport.s(_SECTION_PADDING + 22)
    for index, line in enumerate(section.lines):
        y = rect.top + viewport.s(
            _SECTION_FIRST_LINE_TOP + index * _SECTION_LINE_HEIGHT
        )
        sprites.blit_circle(
            surface,
            (bullet_x, y + font.get_height() // 2),
            viewport.s(4),
            config.COLOR_PRIMARY,
        )
        surface.blit(font.render(line, True, config.COLOR_TEXT), (text_x, y))


def _draw_menu_button(
    surface: pygame.Surface,
    button: MenuButton,
    rect: pygame.Rect,
    mouse: tuple[int, int] | None = None,
) -> None:
    """画菜单按钮：样式由 :attr:`MenuButton.primary` 决定。"""
    if button.primary:
        _draw_primary_button(
            surface, rect, button.text, config.COLOR_PRIMARY, mouse, icon=button.icon
        )
    else:
        _draw_secondary_button(surface, rect, button.text, mouse, icon=button.icon)


def _draw_menu_toggle(
    surface: pygame.Surface,
    rect: pygame.Rect,
    toggle: MenuToggle,
    mouse: tuple[int, int] | None = None,
) -> None:
    """画菜单页上的一个开关行（文字大一些，与卡片正文同一套排版）。"""
    _draw_switch_row(
        surface,
        rect,
        toggle.label,
        toggle.enabled,
        mouse,
        style=_TEXT_BUTTON,
        padding=_PAGE_TOGGLE_PADDING,
    )


def _result_message(session: Session) -> str:
    """返回结算卡片的正文文案。"""
    if session.status is GameStatus.FAILED:
        return f"失误次数已用完，第 {session.level_number} 关未通过"
    if session.is_last_level:
        return f"全部 {session.total_levels} 关已通关"
    return f"剩余失误 {session.mistakes_left} 次"


def _draw_stat_chip(
    surface: pygame.Surface,
    rect: pygame.Rect,
    caption: str,
    value: str,
    value_color: config.Color,
    *,
    align_right: bool = False,
) -> None:
    """画一段“小标题 + 大数值”的统计分区。

    底板由整条信息栏统一提供（见 :func:`_draw_hud_bar`），这里只负责文字，
    因此分区之间不会有描边相互挤压的观感。

    ``align_right`` 让数值靠右对齐（计时器用：读秒时只有十分位在变，
    右对齐才能让它待在原地）。
    """
    surface.blit(
        _TEXT_LABEL.font().render(caption, True, config.COLOR_TEXT_MUTED),
        (
            rect.left + viewport.s(_HUD_CHIP_PADDING),
            rect.top + viewport.s(_HUD_CHIP_CAPTION_TOP),
        ),
    )
    label = _TEXT_VALUE.font().render(value, True, value_color)
    left = (
        rect.right - viewport.s(_HUD_CHIP_PADDING) - label.get_width()
        if align_right
        else rect.left + viewport.s(_HUD_CHIP_PADDING)
    )
    surface.blit(label, (left, rect.top + viewport.s(_HUD_CHIP_VALUE_TOP)))


def _draw_mistake_chip(
    surface: pygame.Surface, rect: pygame.Rect, session: Session
) -> None:
    """画“失误”分区。

    剩余次数用亮红色实心圆表示，已用掉的画成暗色圆，因此“总共几次、
    还剩几次”都能一眼看清，不必去读数字。
    """
    surface.blit(
        _TEXT_LABEL.font().render("失误", True, config.COLOR_TEXT_MUTED),
        (
            rect.left + viewport.s(_HUD_CHIP_PADDING),
            rect.top + viewport.s(_HUD_CHIP_CAPTION_TOP),
        ),
    )

    center_y = rect.top + viewport.s(_HUD_CHIP_VALUE_TOP + 15)
    # 圆点整组在卡片里居中，与前后的“剩余箭头 / 重新开始”对齐得好看一些。
    spacing = viewport.s(_MISTAKE_SPACING)
    span = (session.max_mistakes - 1) * spacing
    first_x = rect.centerx - span // 2
    for index in range(session.max_mistakes):
        center = (first_x + index * spacing, center_y)
        color = (
            config.COLOR_MISTAKE
            if index < session.mistakes_left
            else config.COLOR_MISTAKE_SPENT
        )
        sprites.blit_circle(surface, center, viewport.s(_MISTAKE_RADIUS), color)


def _draw_secondary_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    mouse: tuple[int, int] | None = None,
    icon: icons.Icon | None = None,
) -> None:
    """画深色的次要按钮（重新开始 / 回到主界面），鼠标悬停时提亮。"""
    hovered = mouse is not None and rect.collidepoint(mouse)
    _draw_panel(
        surface,
        rect,
        config.COLOR_BUTTON_HOVER if hovered else config.COLOR_BUTTON,
        radius=viewport.s(config.UI_RADIUS),
        border=config.COLOR_BUTTON_BORDER,
    )
    _draw_button_content(surface, rect, text, config.COLOR_BUTTON_TEXT, icon)


def _draw_icon_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    icon: icons.Icon,
    mouse: tuple[int, int] | None = None,
) -> None:
    """画一个只有图标的按钮（信息栏左上角的“回到主界面”）。

    图形本身没有文字，因此用方位（左上角）与描边强调色向“可点”靠拢：
    悬停时提亮，和旁边带文字的按钮保持同一套外观。
    """
    hovered = mouse is not None and rect.collidepoint(mouse)
    _draw_panel(
        surface,
        rect,
        config.COLOR_BUTTON_HOVER if hovered else config.COLOR_BUTTON,
        radius=viewport.s(config.UI_RADIUS),
        border=config.COLOR_BUTTON_BORDER,
    )
    icons.draw_icon(
        surface,
        icon,
        rect.center,
        round(rect.width * 0.46),
        config.COLOR_BUTTON_TEXT,
    )


def _draw_primary_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    accent: config.Color,
    mouse: tuple[int, int] | None = None,
    icon: icons.Icon | None = None,
) -> None:
    """画填充强调色的主按钮，鼠标悬停时只把填充色提亮一档。

    扁平化之前悬停还会在按钮外侧加一圈外发光，现在那层光晕改成了纯粹的色差：
    同一块形状只换颜色，悬停前后占的面积完全一致。
    """
    hovered = mouse is not None and rect.collidepoint(mouse)
    _draw_panel(
        surface,
        rect,
        _mix(accent, (255, 255, 255), 0.18) if hovered else accent,
        radius=viewport.s(config.UI_RADIUS),
        border=_mix(accent, (0, 0, 0), 0.28),
    )
    _draw_button_content(surface, rect, text, config.COLOR_ON_PRIMARY, icon)


def _draw_compact_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    mouse: tuple[int, int] | None = None,
) -> None:
    """画一个小尺寸的次要按钮（教程提示条上的“跳过教程”）。

    它是贴在提示条上的附属操作，字号也降一档，不抢主按钮的戏。
    """
    hovered = mouse is not None and rect.collidepoint(mouse)
    _draw_panel(
        surface,
        rect,
        config.COLOR_BUTTON_HOVER if hovered else config.COLOR_BUTTON,
        radius=viewport.s(config.UI_RADIUS),
        border=config.COLOR_BUTTON_BORDER,
    )
    _draw_button_content(
        surface, rect, text, config.COLOR_BUTTON_TEXT, style=_TEXT_LABEL
    )


def _draw_button_content(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    color: config.Color,
    icon: icons.Icon | None = None,
    style: _TextStyle = _TEXT_BUTTON,
) -> None:
    """把“图标 + 文字”当成一个整体在按钮里居中。"""
    label = style.font().render(text, True, color)
    icon_size = viewport.s(_BUTTON_ICON_SIZE)
    icon_gap = viewport.s(_BUTTON_ICON_GAP)
    content_width = label.get_width()
    if icon is not None:
        content_width += icon_size + icon_gap

    left = rect.centerx - content_width // 2
    if icon is not None:
        icons.draw_icon(
            surface,
            icon,
            (left + icon_size // 2, rect.centery),
            icon_size,
            color,
        )
        left += icon_size + icon_gap
    surface.blit(label, (left, rect.centery - label.get_height() // 2))
