"""关卡生成与可通关性验证。

手工画关卡有两个麻烦：关数堆不上去，而且很容易画出“死局”——例如同一行上两支
箭头面对面互相瞄准，谁都飞不出去（``tests/test_generator.py`` 里有现成的反例）。
本模块用算法解决这两件事：

- **逆向构造**（:func:`generate_level`）：逐支摆放箭头，每放一支都要求它的前进方向
  上还没有箭头。这样得到的关卡自带一份解：把摆放顺序倒过来清即可——清某支箭头时，
  比它晚摆的都已经清掉，比它早摆的按构造不在它的前进方向上。
- **贪心求解**（:func:`solve`）：不看构造过程，直接对任意关卡反复清掉“当前前方畅通”
  的箭头，清完即判定可通关，中途卡住即判定死局。因为清掉箭头只会减少阻挡，任何一支
  现在能清的箭头以后也一定能清，所以随便挑哪一支都不会错过解：只要能通关，贪心就一定
  清得完。

:func:`generate_solvable_level` 把两者串起来，按 :class:`LevelSpec` 生成关卡，再用
:func:`verify_level` 验证尺寸、箭头数量、开局被挡数量与可通关性；内置关卡
（见 :mod:`another_arrow_rt265.levels`）就是这么来的。本模块只依赖
:mod:`another_arrow_rt265.direction`，不碰 pygame，因此可以脱离窗口单独测试与运行。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from another_arrow_rt265.direction import Direction, from_symbol

if TYPE_CHECKING:
    from another_arrow_rt265.levels import Level

Position = tuple[int, int]
"""棋盘坐标 ``(行, 列)``。"""

Grid = list[list[Direction | None]]
"""方向网格，``None`` 表示空格子。"""

_EMPTY: Final[str] = "."
# 一个规格最多尝试多少次；逆向构造的失败率很低，跑满说明规格本身太苛刻。
_ATTEMPTS: Final[int] = 200


class GenerationError(RuntimeError):
    """按规格生成关卡失败（规格太苛刻，或者棋盘摆不下这么多箭头）。"""


@dataclass(frozen=True, slots=True)
class LevelSpec:
    """一关的生成规格：棋盘尺寸 + 箭头数量 + 难度下限 + 随机种子。

    用数据描述“想要一关什么样的”，:func:`generate_solvable_level` 负责把它变成
    真实关卡，:func:`verify_level` 负责检查关卡是否符合描述。
    """

    rows: int
    """棋盘行数。"""
    cols: int
    """棋盘列数。"""
    arrows: int
    """箭头数量。"""
    min_blocked: int = 0
    """开局（一支箭头都没清掉时）至少要有多少支箭头被挡住。

    逆向构造出的关卡总是有几支“现在就能点”的箭头，但不设下限时也可能生成
    “一路点下去、不用想”的关卡。要求一定数量的箭头互相阻挡，关卡才有解谜的成分。
    """
    seed: int = 0
    """生成用的随机种子：同一个规格（含种子）永远得到同一关。

    内置关卡靠它保持稳定——玩家每次打开游戏，第 2 关都应该是同一张图。
    """

    def __post_init__(self) -> None:
        """校验规格本身是否自洽。

        Raises:
            ValueError: 棋盘尺寸非正数、箭头数量超出格子数，或被挡箭头下限
                超出箭头数量时抛出。
        """
        if self.rows < 1 or self.cols < 1:
            msg = f"棋盘尺寸必须是正数：{self.rows}x{self.cols}"
            raise ValueError(msg)
        if not 1 <= self.arrows <= self.rows * self.cols:
            msg = f"箭头数量 {self.arrows} 超出了 {self.rows}x{self.cols} 棋盘的格子数"
            raise ValueError(msg)
        if not 0 <= self.min_blocked <= self.arrows:
            msg = f"被挡箭头的下限 {self.min_blocked} 超出了箭头数量 {self.arrows}"
            raise ValueError(msg)


def generate_level(
    rows: int, cols: int, arrows: int, *, rng: random.Random
) -> Level | None:
    """用逆向构造生成一个必定可通关的关卡。

    做法：把格子打乱后依次尝试摆一支箭头，方向必须满足“前进方向上还没有箭头”
    （也就是它此刻可以立刻飞出棋盘）。方向的随机权重取它到边界的格数：箭头越朝
    棋盘内部，后面的箭头越有机会落进它的前进方向把它挡住，关卡才需要动脑，
    而不是“每支箭头都能随手点掉”。

    Args:
        rows: 棋盘行数。
        cols: 棋盘列数。
        arrows: 期望的箭头数量。
        rng: 随机数发生器；想要可复现的关卡就传固定种子的 :class:`random.Random`。

    Returns:
        生成好的关卡；若这一轮随机顺序摆不下这么多箭头则返回 ``None``。
        棋盘越满越难摆：越到后面越难找到“前方没有箭头”的方向——实测密度在
        3/4 以下几乎不会失败，超过 3/4 后失败率迅速上升，塞满整块棋盘基本摆不出来。
        想要固定的箭头数量，请用 :func:`generate_solvable_level`，它会自动重试。
    """
    grid: Grid = [[None] * cols for _ in range(rows)]
    occupied: set[Position] = set()
    positions = [(row, col) for row in range(rows) for col in range(cols)]
    rng.shuffle(positions)

    for position in positions:
        if len(occupied) == arrows:
            break
        candidates: list[tuple[Direction, tuple[Position, ...]]] = []
        for direction in Direction:
            ray = _ray(rows, cols, position, direction)
            if all(cell not in occupied for cell in ray):
                candidates.append((direction, ray))
        if not candidates:
            continue
        direction = _pick_direction(rng, candidates)
        grid[position[0]][position[1]] = direction
        occupied.add(position)

    if len(occupied) < arrows:
        return None
    return _render(grid)


def solve(level: Level) -> tuple[Position, ...] | None:
    """贪心求一条通关路线。

    反复挑一支“前方没有其他箭头”的箭头清掉，全部清完即返回点击顺序
    （按 ``(行, 列)`` 排列）；中途再也没有可清除的箭头，说明这是死局，返回 ``None``。

    Args:
        level: 关卡的字符网格。

    Returns:
        通关所需的点击顺序；死局时返回 ``None``。
    """
    grid = _parse(level)
    rows, cols = len(grid), len(grid[0])
    remaining = {
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if grid[row][col] is not None
    }

    order: list[Position] = []
    while remaining:
        for position in sorted(remaining):
            if _blocker(grid, remaining, position) is None:
                remaining.discard(position)
                order.append(position)
                break
        else:
            return None
    return tuple(order)


def is_solvable(level: Level) -> bool:
    """判断关卡能否被清空（等价于 :func:`solve` 是否存在解）。"""
    return solve(level) is not None


def blocked_arrow_count(level: Level) -> int:
    """统计开局有多少支箭头的正前方已经有别的箭头（点下去就会撞墙的那些）。"""
    grid = _parse(level)
    occupied = {
        (row, col)
        for row, line in enumerate(grid)
        for col, direction in enumerate(line)
        if direction is not None
    }
    return sum(
        1 for position in occupied if _blocker(grid, occupied, position) is not None
    )


def verify_level(level: Level, spec: LevelSpec) -> tuple[str, ...]:
    """检查关卡是否符合规格、并且可以通关。

    Args:
        level: 待检查的关卡。
        spec: 期望的规格。

    Returns:
        所有不合格的原因；空元组表示关卡完全符合规格。
    """
    problems: list[str] = []
    if not level:
        return ("关卡是空的",)

    rows, cols = len(level), len(level[0])
    if (rows, cols) != (spec.rows, spec.cols):
        problems.append(f"棋盘尺寸是 {rows}x{cols}，规格要求 {spec.rows}x{spec.cols}")

    arrows = sum(1 for line in level for symbol in line if symbol != _EMPTY)
    if arrows != spec.arrows:
        problems.append(f"箭头数量是 {arrows}，规格要求 {spec.arrows}")

    if not problems:
        blocked = blocked_arrow_count(level)
        if blocked < spec.min_blocked:
            problems.append(
                f"开局只有 {blocked} 支箭头被挡住，少于要求的 {spec.min_blocked} 支"
            )

    if solve(level) is None:
        problems.append("关卡是死局：清到一半就再也没有可以清掉的箭头了")

    return tuple(problems)


def generate_solvable_level(spec: LevelSpec) -> Level:
    """按规格生成一关，并保证它符合规格且可以通关。

    Args:
        spec: 关卡规格。

    Returns:
        生成好的关卡。

    Raises:
        GenerationError: 尝试次数用尽仍拿不到合格关卡时抛出。逆向构造的失败
            主要来自“棋盘太满”（越到后面越难找到前方没有箭头的方向），
            或者 ``min_blocked`` 要得比该尺寸下能摆出的阻挡还多。
    """
    rng = random.Random(spec.seed)
    for _ in range(_ATTEMPTS):
        level = generate_level(spec.rows, spec.cols, spec.arrows, rng=rng)
        if level is not None and not verify_level(level, spec):
            return level

    msg = (
        f"生成 {spec.rows}x{spec.cols}、{spec.arrows} 支箭头"
        f"（至少 {spec.min_blocked} 支被挡）的关卡失败：尝试了 {_ATTEMPTS} 次"
    )
    raise GenerationError(msg)


def _pick_direction(
    rng: random.Random,
    candidates: list[tuple[Direction, tuple[Position, ...]]],
) -> Direction:
    """按“射线上有多少个格子”加权随机挑一个方向。

    权重全为 0 时（例如 1x1 的棋盘上，四个方向都立刻出界）退化为等概率挑选，
    因为 ``random.choices`` 不接受全零权重。
    """
    weights = [len(ray) for _, ray in candidates]
    directions = [direction for direction, _ in candidates]
    if sum(weights) == 0:
        return rng.choice(directions)
    return rng.choices(directions, weights=weights, k=1)[0]


def _ray(
    rows: int,
    cols: int,
    position: Position,
    direction: Direction,
) -> tuple[Position, ...]:
    """返回从 ``position`` 沿 ``direction`` 出发、直到离开棋盘的整条射线。"""
    delta_row, delta_col = direction.delta
    row = position[0] + delta_row
    col = position[1] + delta_col
    cells: list[Position] = []
    while 0 <= row < rows and 0 <= col < cols:
        cells.append((row, col))
        row += delta_row
        col += delta_col
    return tuple(cells)


def _blocker(
    grid: Grid, occupied: set[Position], position: Position
) -> Position | None:
    """返回 ``position`` 上箭头前进方向上的第一支箭头（限定在 ``occupied`` 内）。

    ``occupied`` 决定“哪些格子还算有箭头”：求解过程中它只会变小，因此同一个
    函数既能算开局的阻挡，也能算清掉若干箭头之后的阻挡。
    """
    direction = grid[position[0]][position[1]]
    if direction is None:
        return None
    for cell in _ray(len(grid), len(grid[0]), position, direction):
        if cell in occupied:
            return cell
    return None


def _parse(level: Level) -> Grid:
    """把关卡的字符网格转成方向网格。

    Raises:
        ValueError: 关卡为空、各行长度不一致或包含未知符号时抛出。
    """
    if not level:
        msg = "关卡不能为空"
        raise ValueError(msg)

    width = len(level[0])
    if width == 0:
        msg = "关卡的列数不能为 0"
        raise ValueError(msg)

    grid: Grid = []
    for row_index, line in enumerate(level):
        if len(line) != width:
            msg = f"关卡第 {row_index + 1} 行的长度与首行不一致"
            raise ValueError(msg)
        grid.append(
            [None if symbol == _EMPTY else from_symbol(symbol) for symbol in line]
        )
    return grid


def _render(grid: Grid) -> Level:
    """把方向网格还原成关卡的字符网格（:func:`_parse` 的逆操作）。"""
    return tuple(
        "".join(_EMPTY if direction is None else direction.value for direction in row)
        for row in grid
    )
