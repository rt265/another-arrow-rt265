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

# ------------------------------------------------------------------ 棋盘
BOARD_MARGIN: Final[int] = 48
MAX_CELL_SIZE: Final[int] = 112
CELL_GAP: Final[int] = 6
BOARD_RADIUS: Final[int] = 24
CELL_RADIUS: Final[int] = 12

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
COLOR_BACKGROUND: Final[Color] = (17, 21, 31)
COLOR_BOARD: Final[Color] = (28, 34, 48)
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
