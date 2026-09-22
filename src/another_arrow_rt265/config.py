"""全局配置常量。

集中存放窗口尺寸、棋盘布局与配色等参数，后续调整视觉风格时只需修改此处。
"""

from __future__ import annotations

from typing import Final

Color = tuple[int, int, int]

# ------------------------------------------------------------------ 窗口
# 初始窗口尺寸，同时也是整套界面的**设计尺寸**：`ui.py` / `board.py` 里的布局常量
# 全都按它写成绝对值，运行时再由 `viewport` 按实际窗口等比换算（见 viewport.py）。
WINDOW_WIDTH: Final[int] = 720
WINDOW_HEIGHT: Final[int] = 720
WINDOW_SIZE: Final[tuple[int, int]] = (WINDOW_WIDTH, WINDOW_HEIGHT)
WINDOW_TITLE: Final[str] = "Another Arrow"
FPS: Final[int] = 60
# 窗口可以自由缩放，但缩放系数有下限：窗口小于设计尺寸时不再把界面缩小，
# 设计尺寸下的字号与格子尺寸是这套界面的下限，再小就该重新排版而不是缩放了。
MIN_SCALE: Final[float] = 1.0
# 缩放系数的量化步长（1/16）：拖拽窗口会产生无穷多个中间尺寸，量化之后按尺寸缓存的
# 贴图 / 字体不会每个中间值各留一份，肉眼也看不出这一档的差别。
SCALE_STEP: Final[float] = 1 / 16

# ------------------------------------------------------------------ 项目
# 显示在“关于”界面上：与 pyproject.toml 的 version 保持一致（测试会钉住这一点）。
VERSION: Final[str] = "2.0.0"

# ------------------------------------------------------------------ 布局
# 顶部信息栏（关卡 / 剩余箭头 / 失误 / 重新开始按钮）的高度。
HUD_HEIGHT: Final[int] = 104
# 信息栏内所有元素相对窗口左右边界的留白。
HUD_PADDING: Final[int] = 32
# 棋盘相对窗口左右边界与底部边界的留白。
BOARD_MARGIN: Final[int] = 40
# 棋盘与信息栏之间额外留出的间隙，避免最大的棋盘贴住信息栏。
BOARD_TOP_GAP: Final[int] = 24

# 界面组件的统一圆角与描边宽度。扁平化之后所有面板 / 卡片 / 按钮共用同一档圆角，
# 形状上的差别只由尺寸决定（不再出现“卡片 20 / 说明卡片 24 / 按钮胶囊”这样的多套口径）。
# 唯一的例外是右下角“辅助线”开关的轨道与滑块：它们是开关语义，保持胶囊与正圆。
UI_RADIUS: Final[int] = 12
UI_BORDER_WIDTH: Final[int] = 1

# ------------------------------------------------------------------ 棋盘
# 以下都是**设计尺寸下的值**：窗口缩放时由 `viewport` 等比换算，因此窗口变大时
# 格子、间隙与圆角会一起变大（而不是“窗口大了、棋盘还是原来那么大”）。
MAX_CELL_SIZE: Final[int] = 112
# 相邻格子之间、以及格子与棋盘底板边缘之间的间隙：画出来就是“一块块分开的格子”。
CELL_GAP: Final[int] = 6
# 棋盘底板与格子也跟着界面统一圆角，免得棋盘成为整屏里形状最“另类”的一块。
BOARD_RADIUS: Final[int] = UI_RADIUS
CELL_RADIUS: Final[int] = UI_RADIUS

# 箭头在格子里的占比。两个比例都以**扣掉 CELL_GAP 之后的格子内边宽**为基准：
#
# - 圆片半径 = 内边宽 × ARROW_CHIP_RATIO；
# - 箭头图形的最外端 = 圆片半径 × ARROW_GLYPH_RATIO。
#
# 二者一起决定“箭头与格子边界之间留多少空”：圆片离格子边框
# ``内边宽 × (1/2 − ARROW_CHIP_RATIO)``，图形又比圆片外沿再往里收一点，
# 因此棋盘上不会出现“箭头顶到格子边框、相邻圆片几乎挨上”的观感。
# 数值取舍：0.44 / 0.95 是“填满格子”的旧观感（留白只有内边宽的 6%，图形几乎顶到圆片外沿）；
# 现在是 0.40 / 0.88——留白 10%，图形距边框另有约 2.4%。
# 实际格子的内边宽只有 80 ~ 100px（4x4 到 6x6），因此留白是 8 ~ 10px，
# 肉眼能看出“箭头没贴着边”，又不会小到看不清朝向。
ARROW_CHIP_RATIO: Final[float] = 0.40
ARROW_GLYPH_RATIO: Final[float] = 0.88

# ------------------------------------------------------------------ 玩法
# 每一关允许的失误次数。
MAX_MISTAKES: Final[int] = 3
# 棋盘清空后、弹出通关结算前的停顿（秒），用于等最后一支箭头飞完。
LEVEL_CLEARED_DELAY: Final[float] = 0.18

# ------------------------------------------------------------------ 教程
# 教程只在这一关（序号从 0 开始）上启用：它同时包含“前方畅通”与“被挡住”的箭头，
# 可以就地演示两条核心规则，因此不必在首屏先读一遍文字说明。
TUTORIAL_LEVEL_INDEX: Final[int] = 0
# 教程提示条的高度：排在棋盘上方的空白带里，不遮挡任何棋子。
TUTORIAL_BAR_HEIGHT: Final[int] = 44
# 提示条右侧“跳过教程”按钮的尺寸。
TUTORIAL_SKIP_SIZE: Final[tuple[int, int]] = (104, 30)
# 待点击箭头外围高亮环的呼吸周期（秒）与向外扩张的基准幅度（像素）。
TUTORIAL_PULSE_SECONDS: Final[float] = 1.2
TUTORIAL_RING_GROW: Final[int] = 5

# ------------------------------------------------------------------ 辅助线
# 辅助线是**可选**的：默认关闭，右下角有一颗常驻开关（`G` 键同效）。
# 打开后每个箭头都沿它当前的前进方向画一条虚线，终点就是“这一箭会停在哪”——
# 前方畅通时顶到棋盘边缘（箭头正是从那里飞出棋盘），被挡住时停在挡路箭头的圆片外沿。
# 颜色只表达“这一点击得动 / 点不动”，线本身不参与任何判定，也不改变箭头的颜色身份。
GUIDE_LINE_COLOR_CLEAR: Final[Color] = (110, 226, 178)
GUIDE_LINE_COLOR_BLOCKED: Final[Color] = (255, 132, 132)
# 没有悬停时（或悬停的是别的箭头）把线色混向格子底色，让常显的线淡下去，
# 只有鼠标指着的那条最醒目。与“被谁挡住”的提示一样，用混色而不是透明通道，
# 免得为每条线各开一张图层。
GUIDE_LINE_DIM_MIX: Final[float] = 0.55
GUIDE_LINE_WIDTH: Final[int] = 2
# 虚线的实线段与空白段长度（像素）。
GUIDE_LINE_DASH: Final[float] = 9.0
GUIDE_LINE_GAP: Final[float] = 7.0
# 终点方向标记的尺寸（箭头张开长度 / 横杠总长），以及线段离圆片外沿的留白。
GUIDE_LINE_HEAD: Final[float] = 11.0
GUIDE_LINE_CAP: Final[float] = 13.0
GUIDE_LINE_MARGIN: Final[float] = 5.0

# 右下角的开关：一块圆角栏（左边文字 + 右边滑动开关，见 :data:`UI_RADIUS`）。
# 垂直留白比水平留白紧得多——最大的棋盘（6x6）最后一排格子一直铺到 y=674，
# 开关必须在它下面落脚，所以底边只留 8px；右边缘按常规留白对齐。
GUIDE_TOGGLE_SIZE: Final[tuple[int, int]] = (122, 32)
GUIDE_TOGGLE_MARGIN: Final[tuple[int, int]] = (24, 8)
GUIDE_TOGGLE_LABEL: Final[str] = "辅助线"
# 开关内文字 / 轨道的留白，以及轨道的尺寸与滑块半径（轨道与滑块保持胶囊与正圆）。
GUIDE_TOGGLE_PADDING: Final[int] = 12
GUIDE_TOGGLE_TRACK_SIZE: Final[tuple[int, int]] = (36, 20)
GUIDE_TOGGLE_KNOB_RADIUS: Final[int] = 7
# 开关轨道与滑块的配色：打开后轨道取辅助线的“畅通”色，
# 因此“开关是绿的”与“棋盘上那些绿线”是同一件事的两种说法。
GUIDE_TOGGLE_TRACK_ON: Final[Color] = GUIDE_LINE_COLOR_CLEAR
GUIDE_TOGGLE_TRACK_OFF: Final[Color] = (52, 60, 82)
GUIDE_TOGGLE_KNOB_ON: Final[Color] = (240, 246, 255)
GUIDE_TOGGLE_KNOB_OFF: Final[Color] = (128, 141, 168)

# ------------------------------------------------------------------ 反馈
# 撞到其他箭头时的闪烁提示持续时间（秒）。
BLOCKED_FLASH_SECONDS: Final[float] = 0.45

# ------------------------------------------------------------------ 动画
# 箭头飞出棋盘的动画时长（秒）。
FLY_OUT_SECONDS: Final[float] = 0.32
# 飞出动画的缓动指数，越大越接近“被射出”（起步慢、后段快）。
FLY_OUT_EASE_POWER: Final[float] = 1.8
# 碰撞时箭头沿前进方向的最大抖动幅度（相对格宽）。
BLOCKED_SHAKE_RATIO: Final[float] = 0.12
# 碰撞抖动的往返次数，2.0 表示“撞出去再弹回来”一个来回。
BLOCKED_SHAKE_CYCLES: Final[float] = 2.0
# 选中箭头描边环的呼吸周期（秒）、相对圆片半径的基准倍数与呼吸幅度。
# 基准倍数大于 1，让描边环落在圆片外沿之外，与圆片自己的描边区分开。
SELECTION_PULSE_SECONDS: Final[float] = 1.1
SELECTION_RING_SCALE: Final[float] = 1.07
SELECTION_PULSE_RATIO: Final[float] = 0.06

# ------------------------------------------------------------------ 配色
# 窗口背景：扁平化的**单一纯色**。原来这里是“竖直渐变 + 一团径向柔光”，
# 扁平化之后画面的层次只由“块与块的明度差 + 1px 描边”表达，背景不再制造立体感。
COLOR_BACKGROUND: Final[Color] = (16, 20, 30)

COLOR_BOARD: Final[Color] = (28, 34, 48)
# 棋盘底板的描边，避免深色棋盘在深色背景上“糊”成一片。
COLOR_BOARD_BORDER: Final[Color] = (50, 61, 88)
COLOR_CELL: Final[Color] = (40, 49, 68)

# 箭头的圆片底色：常态与碰撞两种基准色。
# 它们只是“底色”，真正的颜色由基准色与箭头主题色混合得到（见 `palette.py`）；
# 选中态则在常态底色的基础上再混入主题色，同样见 `palette.py`。
COLOR_CHIP: Final[Color] = (26, 32, 45)
COLOR_CHIP_BLOCKED: Final[Color] = (58, 14, 20)
# 选中时箭头提亮的目标色，以及碰撞时箭头染向的警示色（偏白）。
COLOR_ARROW_HIGHLIGHT: Final[Color] = (255, 255, 255)
COLOR_ARROW_BLOCKED: Final[Color] = (255, 210, 210)
# 选中环用接近白色的颜色：箭头主题色是彩色的，金色描边会和琥珀色主题撞在一起。
COLOR_SELECTION_RING: Final[Color] = (238, 243, 252)
COLOR_BLOCKED_RING: Final[Color] = (232, 64, 64)
# 碰撞时在箭头前方溅出的火花线与“被谁挡住”的提示环。
COLOR_BLOCKED_SPARK: Final[Color] = (255, 186, 100)
COLOR_BLOCKER_HINT: Final[Color] = (255, 122, 122)

# ------------------------------------------------------------------ 彩色箭头
# 箭头主题色的调色板：每个箭头按“行 × ARROW_PALETTE_ROW_STEP + 列”从调色板取色，
# 因此颜色只跟格子位置有关，一关之内稳定不变——清除别的箭头、重新开始本关，
# 都不会让剩下的箭头换色。步长只要不是调色板长度的倍数，上下相邻的箭头就不会撞色。
# 颜色只是视觉上的区分，不参与任何判定。
ARROW_PALETTE: Final[tuple[Color, ...]] = (
    (255, 118, 118),  # 珊瑚红
    (255, 184, 86),  # 琥珀
    (104, 222, 150),  # 薄荷
    (92, 190, 255),  # 天蓝
    (176, 152, 255),  # 薰衣草
    (255, 140, 205),  # 樱粉
)
ARROW_PALETTE_ROW_STEP: Final[int] = 3

# 主题色在各状态下的用量：圆片底色取压暗过的主题色，箭头本身用主题色。
ARROW_CHIP_MIX: Final[float] = 0.22
# 选中时在常态圆片上再混入主题色的比例：圆片更亮、更饱和，箭头看起来“被点亮”了。
ARROW_CHIP_SELECTED_MIX: Final[float] = 0.30
ARROW_CHIP_BLOCKED_MIX: Final[float] = 0.30
# 圆片描边相对圆片底色的提亮程度。
ARROW_CHIP_BORDER_MIX: Final[float] = 0.55
# 选中时箭头向白色提亮的程度：轻微提亮即可，选中主要靠中性的呼吸环表达（环不能太淡）。
ARROW_SELECTED_MIX: Final[float] = 0.18
# 碰撞时箭头向警示白染色的程度：幅度大，看起来像“撞得发白”。
ARROW_BLOCKED_MIX: Final[float] = 0.55

# ------------------------------------------------------------------ 界面
# 信息栏文字、按钮与失误圆点。
COLOR_TEXT: Final[Color] = (233, 238, 248)
COLOR_TEXT_MUTED: Final[Color] = (128, 141, 168)
COLOR_MISTAKE: Final[Color] = (238, 92, 92)
COLOR_MISTAKE_SPENT: Final[Color] = (52, 60, 82)
# 关卡计时器的读数：偏冷的浅蓝，与金色关卡号、红色失误点区分开。
# 破纪录时改用主色（金）强调整一下，见 `ui.draw_overlay`。
COLOR_TIME: Final[Color] = (146, 202, 255)

# 组件外观：扁平化之后**一个角色只有一种颜色**——信息栏、统计分区、说明卡片、
# 装饰圆牌与结算卡片共用 COLOR_PANEL + COLOR_PANEL_BORDER，不再有“渐变两端 + 投影”。
COLOR_PANEL: Final[Color] = (36, 44, 63)
COLOR_PANEL_BORDER: Final[Color] = (62, 77, 108)

# 次要按钮（深色）：填充色与悬停态。悬停只换填充色，不做渐变 / 外发光 / 位移。
COLOR_BUTTON: Final[Color] = (54, 66, 92)
COLOR_BUTTON_HOVER: Final[Color] = (70, 86, 118)
COLOR_BUTTON_BORDER: Final[Color] = (88, 106, 142)
COLOR_BUTTON_TEXT: Final[Color] = (233, 238, 248)

# 主按钮的强调色（金色），按钮上的文字用深色保证对比度。
COLOR_PRIMARY: Final[Color] = (255, 196, 74)
COLOR_ON_PRIMARY: Final[Color] = (38, 28, 8)

# 结算覆盖层：遮罩、卡片，以及通关 / 失败两种强调色。
# 遮罩保留——它是“本关结束了”的功能反馈而不是装饰；卡片与其它面板共用 COLOR_PANEL。
COLOR_OVERLAY: Final[Color] = (8, 11, 18)
OVERLAY_ALPHA: Final[int] = 200
COLOR_SUCCESS: Final[Color] = (108, 220, 156)
COLOR_FAILURE: Final[Color] = (238, 92, 92)

# ------------------------------------------------------------------ 音频
# 两条音量分开：背景音乐是长时间循环的底噪，压低到“听得出有，但不抢注意力”；
# 音效是短促的操作反馈（点按钮、箭头飞出、撞墙、通关 / 失败），要能一耳朵听清，
# 所以留得比音乐高。素材随程序分发（`assets/sounds/`），见 `audio.py`。
MUSIC_VOLUME: Final[float] = 0.35
SOUND_VOLUME: Final[float] = 0.7
