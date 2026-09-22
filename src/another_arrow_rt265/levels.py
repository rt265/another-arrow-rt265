"""内置关卡数据。

每个关卡使用等宽的字符网格描述，每行的字符含义为：

- ``.``：空格子；
- ``^`` / ``v`` / ``<`` / ``>``：对应方向的箭头。

网格的行数、列数由字符串数量与单行长度决定，因此关卡尺寸可以不同。

第 1 关是**手写固定**的教程关（见 :data:`TUTORIAL_LEVEL`）：交互式教程的文案与
演示都依赖它的具体布局，既要有前方畅通的箭头，也要有被挡住的箭头。

其余关卡不再手工绘制，而是按 :data:`LEVEL_SPECS` 里的“尺寸 + 箭头数量 + 开局
被挡数量 + 随机种子”，交给 :mod:`another_arrow_rt265.generator` 用逆向构造生成，
并在生成时用求解器验证一遍（见 :func:`~another_arrow_rt265.generator.verify_level`）。
因此**新增关卡只要加一行规格**：不必再手工画网格，也不会画出“同一条线上两支箭头
互相瞄准”的死局。
"""

from __future__ import annotations

from typing import Final

from another_arrow_rt265.generator import LevelSpec, generate_solvable_level

Level = tuple[str, ...]

TUTORIAL_LEVEL: Final[Level] = (
    ".^v.",
    "..<.",
    "...<",
    ">...",
)
"""教程关（第 1 关）：4x4、5 支箭头，其中 (0,2) 被 (1,2) 挡住。

教程的三步引导（点畅通的箭头 → 点被挡住的箭头 → 清空棋盘）就建立在这两块上，
所以这一关保持手写、不参与随机生成。
"""

TUTORIAL_LEVEL_SPEC: Final[LevelSpec] = LevelSpec(
    rows=4, cols=4, arrows=5, min_blocked=1
)
"""教程关的规格：测试用它验证手写关卡依旧可通关，也确实含有被挡住的箭头。"""

LEVEL_SPECS: Final[tuple[LevelSpec, ...]] = (
    # 第 2 关：4x4、6 支箭头，比教程关多一支，练习“先清挡路的”。
    LevelSpec(rows=4, cols=4, arrows=6, min_blocked=2, seed=0),
    # 第 3 关：5x5、10 支箭头，首次出现同一行 / 列上的长链阻挡。
    LevelSpec(rows=5, cols=5, arrows=10, min_blocked=4, seed=1),
    # 第 4 关：5x5、12 支箭头，箭头更密，可点的更少。
    LevelSpec(rows=5, cols=5, arrows=12, min_blocked=5, seed=2),
    # 第 5 关：6x6、16 支箭头，棋盘与箭头数量一起变大。
    LevelSpec(rows=6, cols=6, arrows=16, min_blocked=7, seed=3),
    # 第 6 关：6x6、20 支箭头，开局就有近一半箭头互相当路。
    LevelSpec(rows=6, cols=6, arrows=20, min_blocked=9, seed=4),
    # 第 7 关：7x7、25 支箭头，棋盘更大，开局被挡的更多。
    LevelSpec(rows=7, cols=7, arrows=25, min_blocked=12, seed=5),
    # 第 8 关：8x8、30 支箭头，棋盘更大，开局被挡的更多。
    LevelSpec(rows=8, cols=8, arrows=30, min_blocked=15, seed=6),
    # 第 9 关：8x8、40 支箭头，棋盘更大，开局被挡的更多。
    LevelSpec(rows=8, cols=8, arrows=40, min_blocked=20, seed=7),
    # 第 10 关：终极关卡！
    LevelSpec(rows=14, cols=14, arrows=100, min_blocked=40, seed=8),
)
"""第 2 关起的生成规格：一行一关，想加关卡就再添一行。"""

LEVELS: Final[tuple[Level, ...]] = (TUTORIAL_LEVEL,) + tuple(
    generate_solvable_level(spec) for spec in LEVEL_SPECS
)
"""内置关卡：第 1 关手写，其余按 :data:`LEVEL_SPECS` 生成。"""
