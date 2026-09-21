"""箭头方向的定义与转换。"""

from __future__ import annotations

from enum import Enum
from typing import Final


class Direction(Enum):
    """棋盘箭头的四种朝向。

    成员的值同时是关卡字符网格中用于表示该方向的符号。
    """

    UP = "^"
    RIGHT = ">"
    DOWN = "v"
    LEFT = "<"

    @property
    def delta(self) -> tuple[int, int]:
        """返回该方向在网格中的行列增量 ``(d_row, d_col)``。"""
        return _DELTAS[self]

    @property
    def angle(self) -> int:
        """返回绘制时相对“向上”箭头的顺时针旋转角度（度）。"""
        return _ANGLES[self]

    @property
    def vector(self) -> tuple[float, float]:
        """返回该方向在屏幕像素坐标下的单位向量 ``(dx, dy)``。

        与 :attr:`delta` 的区别是分量顺序为 ``(x, y)`` 且为浮点数，
        便于直接用于绘制与动画位移计算。
        """
        delta_row, delta_col = self.delta
        return (float(delta_col), float(delta_row))


# 屏幕坐标下 y 轴向下，因此“向下”对应行号增加。
_DELTAS: Final[dict[Direction, tuple[int, int]]] = {
    Direction.UP: (-1, 0),
    Direction.RIGHT: (0, 1),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
}

_ANGLES: Final[dict[Direction, int]] = {
    Direction.UP: 0,
    Direction.RIGHT: 90,
    Direction.DOWN: 180,
    Direction.LEFT: 270,
}


def from_symbol(symbol: str) -> Direction:
    """把关卡字符转换为对应的方向。

    Args:
        symbol: 关卡网格中的单个字符。

    Returns:
        该字符表示的方向。

    Raises:
        ValueError: 字符不是合法的箭头符号时抛出。
    """
    for direction in Direction:
        if direction.value == symbol:
            return direction
    msg = f"未知的箭头符号：{symbol!r}"
    raise ValueError(msg)
