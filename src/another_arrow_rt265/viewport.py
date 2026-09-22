"""窗口缩放：把“设计尺寸”等比映射到实际窗口。

界面与棋盘的**所有布局常量都按设计尺寸**（``config.WINDOW_SIZE``，720×720）**写成绝对值**，
运行时再由 :class:`Viewport` 换算到当前窗口：先乘 ``scale``，再平移到 ``origin``。

这样做与“渲染一张 720² 的画面再拉伸铺满窗口”有本质区别：几何按目标尺寸重算、文字按目标
字号重新渲染，**网格与字形都是照着最终像素重画的**，因此窗口放大的同时画面不会变糊
（后者放大后插值一定糊，这正是事项 12 要修的两件事之一）。

窗口长宽比与设计尺寸不一致时（不拉伸，保持等比），多出来的部分留白：背景仍然铺满整窗，
界面元素整体居中。窗口缩到比设计尺寸还小时**不缩小内容**（``config.MIN_SCALE``）——
设计尺寸下的字号与格子尺寸是这套界面的下限，再小就不是“缩放”而是“重新排版”了，
超出窗口的部分会被裁掉。

约定（``ui`` / ``board`` 都遵守）：

- **几何函数**（:func:`another_arrow_rt265.ui.board_area`、``Board.cell_rect`` …）返回的是
  **屏幕坐标**；
- 绘制里的**设计常量**（半径、留白、线宽、字号……）在遇到像素之前先用 :func:`s` / :func:`x`
  / :func:`y` 换算；而由 ``rect`` 直接派生的值（例如 ``rect.height // 2``）本来就是像素，
  **不要**再换算一次。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pygame

from another_arrow_rt265 import config


@dataclass(frozen=True, slots=True)
class Viewport:
    """一次“设计尺寸 → 窗口像素”的映射。"""

    size: tuple[int, int]
    """实际窗口尺寸（像素）。"""
    scale: float = 1.0
    """等比缩放系数，且**不会小于** ``config.MIN_SCALE``。"""
    origin: tuple[int, int] = (0, 0)
    """设计框左上角落在窗口里的位置；非等比窗口下就是留白。"""

    @classmethod
    def fit(
        cls,
        size: tuple[int, int],
        *,
        design: tuple[int, int] = config.WINDOW_SIZE,
        min_scale: float = config.MIN_SCALE,
        step: float = config.SCALE_STEP,
    ) -> Viewport:
        """按窗口尺寸算出视口：等比缩放、居中留白。

        Args:
            size: 窗口尺寸（像素），非正值会被夹到 1。
            design: 设计尺寸，所有布局常量都是按它写的。
            min_scale: 缩放系数下限（默认 1.0，即不把界面缩小）。
            step: 缩放系数的量化步长；拖拽窗口时中间尺寸无穷多，量化之后贴图与字体
                的缓存不会随每个中间尺寸各长一份（``1/16`` 的步长在视觉上看不出来）。
                取值向下取整（而不是四舍五入），于是设计框永远不会比窗口大，
                不会出现“为了取整而多裁掉几个像素”。
        """
        width, height = max(1, int(size[0])), max(1, int(size[1]))
        raw = min(width / design[0], height / design[1])
        # k/16 这类步长的倍数是二进制精确的，量化之后不会积累浮点误差。
        steps = int(raw / step + 1e-9)
        scale = max(min_scale, steps * step)
        box = (round(design[0] * scale), round(design[1] * scale))
        origin = ((width - box[0]) // 2, (height - box[1]) // 2)
        return cls((width, height), scale, origin)

    def s(self, value: float) -> int:
        """把一个设计长度换算成像素长度（字号、半径、线宽、留白）。"""
        return round(value * self.scale)

    def scaled(self, size: tuple[float, float]) -> tuple[int, int]:
        """把一个设计尺寸（宽、高）换算成像素尺寸。"""
        return (self.s(size[0]), self.s(size[1]))

    def x(self, value: float) -> int:
        """把一个设计横坐标换算成屏幕横坐标。"""
        return self.origin[0] + self.s(value)

    def y(self, value: float) -> int:
        """把一个设计纵坐标换算成屏幕纵坐标。"""
        return self.origin[1] + self.s(value)

    def point(self, x: float, y: float) -> tuple[int, int]:
        """把一个设计坐标点换算成屏幕坐标点。"""
        return (self.x(x), self.y(y))

    def rect(self, x: float, y: float, width: float, height: float) -> pygame.Rect:
        """把设计坐标下的矩形换算成屏幕矩形。

        两个方向都按**左右 / 上下边界分别取整**，因此相邻矩形仍然严丝合缝
        （先算宽再取整会在拼排时留下一两个像素的缝）。
        """
        left, top = self.x(x), self.y(y)
        return pygame.Rect(
            left, top, self.x(x + width) - left, self.y(y + height) - top
        )

    def map(self, rect: pygame.Rect) -> pygame.Rect:
        """把一个设计坐标下的矩形换算成屏幕矩形。"""
        return self.rect(rect.left, rect.top, rect.width, rect.height)

    def center(self) -> tuple[int, int]:
        """设计框的中心在屏幕上的位置（标题、结算卡片这类居中元素用）。"""
        return (
            self.x(config.WINDOW_WIDTH / 2),
            self.y(config.WINDOW_HEIGHT / 2),
        )


#: 尚未改变窗口尺寸时的视口：缩放 1.0、不留白，几何与过去逐像素相同。
DEFAULT: Final[Viewport] = Viewport(config.WINDOW_SIZE)

_current: Viewport = DEFAULT


def current() -> Viewport:
    """返回当前视口（窗口尺寸变化时由 :func:`another_arrow_rt265.game.Game` 更新）。"""
    return _current


def set_current(view: Viewport) -> Viewport:
    """设置当前视口，并把它原样返回（方便 ``self.view = viewport.set_current(...)``）。"""
    global _current
    _current = view
    return view


def reset() -> None:
    """把视口恢复成默认值（测试用，避免上一个用例的窗口尺寸泄漏到下一个）。"""
    set_current(DEFAULT)


def s(value: float) -> int:
    """当前视口下，设计长度 → 像素长度。"""
    return _current.s(value)


def scaled(value: tuple[float, float]) -> tuple[int, int]:
    """当前视口下，设计尺寸 → 像素尺寸。"""
    return _current.scaled(value)


def x(value: float) -> int:
    """当前视口下，设计横坐标 → 屏幕横坐标。"""
    return _current.x(value)


def y(value: float) -> int:
    """当前视口下，设计纵坐标 → 屏幕纵坐标。"""
    return _current.y(value)


def point(x_value: float, y_value: float) -> tuple[int, int]:
    """当前视口下，设计坐标点 → 屏幕坐标点。"""
    return _current.point(x_value, y_value)


def rect(x_value: float, y_value: float, width: float, height: float) -> pygame.Rect:
    """当前视口下，设计矩形 → 屏幕矩形。"""
    return _current.rect(x_value, y_value, width, height)


def map(rect_value: pygame.Rect) -> pygame.Rect:
    """当前视口下，设计矩形 → 屏幕矩形。"""
    return _current.map(rect_value)


def center() -> tuple[int, int]:
    """当前视口下，设计框中心的屏幕坐标。"""
    return _current.center()
