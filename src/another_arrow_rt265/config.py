"""全局配置常量。

集中存放窗口尺寸、棋盘布局与配色等参数，后续调整视觉风格时只需修改此处。
"""

from __future__ import annotations

from typing import Final

Color = tuple[int, int, int]

# ------------------------------------------------------------------ 窗口
WINDOW_WIDTH: Final[int] = 720
WINDOW_HEIGHT: Final[int] = 720
WINDOW_TITLE: Final[str] = "Another Arrow"
FPS: Final[int] = 60

# ------------------------------------------------------------------ 布局
# 顶部信息栏（关卡 / 剩余箭头 / 失误 / 重新开始按钮）的高度。
HUD_HEIGHT: Final[int] = 104
# 信息栏内所有元素相对窗口左右边界的留白。
HUD_PADDING: Final[int] = 32
# 棋盘相对窗口左右边界与底部边界的留白。
BOARD_MARGIN: Final[int] = 40
# 棋盘与信息栏之间额外留出的间隙，避免最大的棋盘贴住信息栏。
BOARD_TOP_GAP: Final[int] = 24

# ------------------------------------------------------------------ 棋盘
MAX_CELL_SIZE: Final[int] = 112
CELL_GAP: Final[int] = 6
BOARD_RADIUS: Final[int] = 24
CELL_RADIUS: Final[int] = 12

# ------------------------------------------------------------------ 玩法
# 每一关允许的失误次数。
MAX_MISTAKES: Final[int] = 3
# 棋盘清空后、弹出通关结算前的停顿（秒），用于等最后一支箭头飞完。
LEVEL_CLEARED_DELAY: Final[float] = 0.18

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
# 选中箭头描边环的呼吸周期（秒）与半径变化幅度（相对半径）。
SELECTION_PULSE_SECONDS: Final[float] = 1.1
SELECTION_PULSE_RATIO: Final[float] = 0.06

# ------------------------------------------------------------------ 配色
# 窗口背景：自上而下的竖直渐变，外加棋盘 / 主按钮背后的一团柔光。
COLOR_BACKGROUND_TOP: Final[Color] = (30, 38, 58)
COLOR_BACKGROUND_BOTTOM: Final[Color] = (10, 13, 21)
COLOR_BACKGROUND_GLOW: Final[Color] = (62, 98, 170)
GLOW_ALPHA: Final[int] = 88

COLOR_BOARD: Final[Color] = (28, 34, 48)
# 棋盘底板的描边，避免深色棋盘在深色背景上“糊”成一片。
COLOR_BOARD_BORDER: Final[Color] = (50, 61, 88)
COLOR_CELL: Final[Color] = (40, 49, 68)
COLOR_CHIP: Final[Color] = (26, 32, 45)
COLOR_CHIP_SELECTED: Final[Color] = (52, 46, 30)
COLOR_CHIP_BLOCKED: Final[Color] = (58, 14, 20)
COLOR_ARROW: Final[Color] = (226, 232, 245)
COLOR_ARROW_SELECTED: Final[Color] = (255, 203, 92)
COLOR_ARROW_BLOCKED: Final[Color] = (255, 210, 210)
COLOR_SELECTION_RING: Final[Color] = (255, 203, 92)
COLOR_BLOCKED_RING: Final[Color] = (232, 64, 64)
# 碰撞时在箭头前方溅出的火花线与“被谁挡住”的提示环。
COLOR_BLOCKED_SPARK: Final[Color] = (255, 186, 100)
COLOR_BLOCKER_HINT: Final[Color] = (255, 122, 122)

# ------------------------------------------------------------------ 界面
# 信息栏文字、按钮与失误圆点。
COLOR_TEXT: Final[Color] = (233, 238, 248)
COLOR_TEXT_MUTED: Final[Color] = (128, 141, 168)
COLOR_MISTAKE: Final[Color] = (238, 92, 92)
COLOR_MISTAKE_SPENT: Final[Color] = (52, 60, 82)

# 组件外观：投影、面板底色（渐变两端）与描边色，
# 统计卡片、开始界面的“玩法”卡片以及各种按钮都由这几个色阶推出来。
COLOR_SHADOW: Final[Color] = (3, 5, 9)
COLOR_PANEL: Final[Color] = (36, 44, 63)
COLOR_PANEL_DEEP: Final[Color] = (25, 31, 45)
COLOR_PANEL_BORDER: Final[Color] = (62, 77, 108)

# 次要按钮（深色）的渐变两端与悬停态。
COLOR_BUTTON_TOP: Final[Color] = (54, 66, 92)
COLOR_BUTTON_BOTTOM: Final[Color] = (38, 47, 67)
COLOR_BUTTON_TOP_HOVER: Final[Color] = (70, 86, 118)
COLOR_BUTTON_BOTTOM_HOVER: Final[Color] = (49, 61, 86)
COLOR_BUTTON_BORDER: Final[Color] = (88, 106, 142)
COLOR_BUTTON_TEXT: Final[Color] = (233, 238, 248)

# 主按钮的强调色（金色），按钮上的文字用深色保证对比度。
COLOR_PRIMARY: Final[Color] = (255, 196, 74)
COLOR_ON_PRIMARY: Final[Color] = (38, 28, 8)

# 结算覆盖层：遮罩、卡片，以及通关 / 失败两种强调色。
COLOR_OVERLAY: Final[Color] = (8, 11, 18)
OVERLAY_ALPHA: Final[int] = 200
COLOR_CARD_TOP: Final[Color] = (40, 49, 70)
COLOR_CARD_BOTTOM: Final[Color] = (25, 31, 45)
COLOR_SUCCESS: Final[Color] = (108, 220, 156)
COLOR_FAILURE: Final[Color] = (238, 92, 92)
