"""自定义模式：玩家调的参数，与按参数实时生成出来的关卡。

自定义模式让玩家自己挑**棋盘边长**与**箭头数量**，参数一动就重新生成一关
（见 :class:`CustomLevel`）。本模块只做“参数 → 关卡”这一件事，只依赖
:mod:`another_arrow_rt265.generator` 与 :mod:`another_arrow_rt265.levels`，
不碰 pygame，因此参数范围与生成行为可以脱离窗口单独测试。

**参数范围是实测定的。** 自定义模式每次改参数都要重新生成，所以范围必须落在
生成器又快又稳的区间里：

- **边长 4 ~ 16**：16x16 已经贴着默认 720x720 窗口下棋盘的可读上限
  （见 :func:`~another_arrow_rt265.generator.generate_level` 的尺寸说明），
  再大格子就只剩二十来个像素，四个方向分不出来；
- **箭头数量上限 = 格子数的一半**：逆向构造在密度超过一半之后开始频繁重试——
  实测 16x16 / 154 支（密度 0.60）单次要 319 ms，还会在 200 次重试后直接失败；
  卡到一半之后最慢也只有 3.5 ms。整段拖动（16x16 从 1 支拖到 128 支）共 198 ms，
  平均 1.5 ms/关，摊在拖动过程中看不出卡顿。

同一组参数永远得到同一关（见 :attr:`CustomLevel.level`），只有 :meth:`CustomLevel.reroll`
才会换出另一批：这样玩家调参数时看到的是“这组参数下的那一关”，而不是每动一下
都换一张无关的图；生成结果也因此能按参数缓存，把滑动条拖回去时不必重算。
"""

from __future__ import annotations

import functools
from typing import Final

from another_arrow_rt265.generator import LevelSpec, generate_solvable_level
from another_arrow_rt265.levels import Level

MIN_SIZE: Final[int] = 4
"""棋盘边长下限：比 4x4 更小的棋盘放不下“被挡住”的演示。"""

MAX_SIZE: Final[int] = 16
"""棋盘边长上限：默认窗口下再大就分不出箭头的朝向。"""

DEFAULT_SIZE: Final[int] = 8
"""默认棋盘边长（第一次打开自定义模式时看到的尺寸）。"""

MIN_ARROWS: Final[int] = 1
"""箭头数量下限：一支箭头毫无难度，但它是合法的，也方便做对照。"""

MAX_ARROWS_RATIO: Final[float] = 0.5
"""箭头数量上限占格子数的比例（见模块说明里的实测数据）。"""

DEFAULT_ARROWS_RATIO: Final[float] = 0.4
"""默认箭头数量占格子数的比例：离上限留一截，打开就能看出是一局解谜。"""

_MIN_BLOCKED_RATIO: Final[float] = 0.25
"""开局被挡箭头的下限按箭头数的比例给：一支要求都不提会生成“一路点下去”的关卡。"""

_SEED_MODULUS: Final[int] = 2**31
"""种子的取模上限（``random.Random`` 收任何整数，这里只是让它落在常见范围内）。"""


def max_arrows(size: int) -> int:
    """返回边长 ``size`` 的棋盘上允许的箭头数量上限。"""
    return max(MIN_ARROWS, round(size * size * MAX_ARROWS_RATIO))


def default_arrows(size: int) -> int:
    """返回边长 ``size`` 下的默认箭头数量。"""
    return min(
        max_arrows(size),
        max(MIN_ARROWS, round(size * size * DEFAULT_ARROWS_RATIO)),
    )


def clamp_size(size: float) -> int:
    """把棋盘边长夹到 ``[MIN_SIZE, MAX_SIZE]``（小数按四舍五入处理）。"""
    return min(MAX_SIZE, max(MIN_SIZE, round(size)))


def clamp_arrows(arrows: float, size: int) -> int:
    """把箭头数量夹到边长 ``size`` 下的合法区间 ``[MIN_ARROWS, max_arrows(size)]``。"""
    return min(max_arrows(size), max(MIN_ARROWS, round(arrows)))


def seed_for(size: int, arrows: int, batch: int) -> int:
    """返回“这组参数的第 ``batch`` 批”用的随机种子。

    种子是**算出来的、不是抽出来的**：同一个 ``(边长, 箭头数量, 批次)`` 永远得到
    同一关，因此 :attr:`CustomLevel.level` 是确定的、可以按参数缓存。
    """
    return (batch * 1_000_003 + size * 1_009 + arrows * 9_176) % _SEED_MODULUS


def spec_for(size: int, arrows: int, batch: int) -> LevelSpec:
    """把自定义模式的“参数 + 第几批”翻译成生成器认得的一份规格。

    这是两层之间唯一的口径：棋盘是方的（行数 = 列数），种子由
    :func:`seed_for` 算出来，开局被挡箭头的下限按箭头数的比例给——
    完全不给下限（0）会生成“一路点下去、不用想”的关卡。
    """
    return LevelSpec(
        rows=size,
        cols=size,
        arrows=arrows,
        min_blocked=round(arrows * _MIN_BLOCKED_RATIO),
        seed=seed_for(size, arrows, batch),
    )


@functools.lru_cache(maxsize=512)
def build_level(size: int, arrows: int, batch: int) -> Level:
    """按“参数 + 第几批”生成一关（与 :func:`seed_for` 一起构成确定性映射）。

    Args:
        size: 棋盘边长（行数与列数相同）。
        arrows: 箭头数量。
        batch: 第几批，见 :meth:`CustomLevel.reroll`。

    Returns:
        生成好且已验证可通关的关卡。

    Raises:
        GenerationError: 参数太苛刻、生成器重试用尽时抛出。参数是夹过的、
            范围经过实测（见模块说明），正常路径不会发生。
    """
    return generate_solvable_level(spec_for(size, arrows, batch))


class CustomLevel:
    """正在“捏”的那一关：两个参数 + 由它们生成出来的关卡。

    参数一律**夹过**（见 :func:`clamp_size` / :func:`clamp_arrows`），因此
    :attr:`level` 一定存在、一定是合法的：界面把滑动条的取值交给
    :meth:`change_size` / :meth:`change_arrows` 即可，不必自己判边界，
    也不用担心把箭头数量改到棋盘外面去。
    """

    def __init__(
        self,
        size: int = DEFAULT_SIZE,
        arrows: int | None = None,
        batch: int = 0,
    ) -> None:
        """设定初始参数并生成第一关。

        Args:
            size: 棋盘边长，越界时夹到 ``[MIN_SIZE, MAX_SIZE]``。
            arrows: 箭头数量；省略时按 :func:`default_arrows` 取。
            batch: 第几批（见 :meth:`reroll`），负数按 0 处理。
        """
        self._size = clamp_size(size)
        self._arrows = clamp_arrows(
            default_arrows(self._size) if arrows is None else arrows,
            self._size,
        )
        self._batch = max(0, batch)
        self._level = build_level(self._size, self._arrows, self._batch)

    @property
    def size(self) -> int:
        """棋盘边长（行数与列数相同）。"""
        return self._size

    @property
    def arrows(self) -> int:
        """箭头数量。"""
        return self._arrows

    @property
    def batch(self) -> int:
        """第几批：同一组参数的每一次“换一关”各算一批。"""
        return self._batch

    @property
    def max_arrows(self) -> int:
        """当前边长下的箭头数量上限（滑动条的量程）。"""
        return max_arrows(self._size)

    @property
    def level(self) -> Level:
        """当前参数生成出来的关卡。"""
        return self._level

    def change_size(self, size: float) -> bool:
        """改棋盘边长，返回参数**是否真的变了**。

        边长变小时原先的箭头数量可能超上限，这里会一并夹下来——这是同一次改动，
        因此只生成一关。
        """
        return self._apply(size=size)

    def change_arrows(self, arrows: float) -> bool:
        """改箭头数量，返回参数**是否真的变了**。"""
        return self._apply(arrows=arrows)

    def reroll(self) -> None:
        """换一批：参数不动，换出这一组参数下的另一关。"""
        self._batch += 1
        self._level = build_level(self._size, self._arrows, self._batch)

    def _apply(self, *, size: float | None = None, arrows: float | None = None) -> bool:
        """写入新参数：夹到合法区间，参数真的变了才重新生成。"""
        new_size = self._size if size is None else clamp_size(size)
        new_arrows = clamp_arrows(
            self._arrows if arrows is None else arrows,
            new_size,
        )
        if (new_size, new_arrows) == (self._size, self._arrows):
            return False
        self._size, self._arrows = new_size, new_arrows
        self._level = build_level(new_size, new_arrows, self._batch)
        return True
