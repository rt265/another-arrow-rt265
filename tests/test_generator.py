"""关卡生成器与可通关性验证的测试。

这里既验证“生成出来的关卡一定可通关”，也把求解器的结论与游戏自身的规则
（``Board.handle_click``）对齐：求解器说能按某个顺序清完，那么照着点就真的清得完。
"""

from __future__ import annotations

import random

import pygame
import pytest

from another_arrow_rt265 import generator
from another_arrow_rt265.board import Board, ClickResult
from another_arrow_rt265.generator import LevelSpec
from another_arrow_rt265.levels import (
    LEVEL_SPECS,
    LEVELS,
    TUTORIAL_LEVEL_SPEC,
    Level,
)

AREA = pygame.Rect(0, 0, 640, 640)

# 同一行上互相瞄准：谁都飞不出去，是典型的死局。
DEADLOCK_LEVEL: Level = (">..<",)

# 四个箭头互相阻挡，同样是死局。
CROSS_DEADLOCK: Level = (
    ".v.",
    ">.<",
    ".^.",
)

# 必须先清掉挡路的那支，才能清掉第一支。
CHAIN_LEVEL: Level = (
    ">v.",
    "...",
    "...",
)

# 属性测试用的规格：多种尺寸、密度与种子。
PROPERTY_SPECS: tuple[LevelSpec, ...] = tuple(
    LevelSpec(rows=rows, cols=cols, arrows=arrows, min_blocked=blocked, seed=seed)
    for seed in range(8)
    for rows, cols, arrows, blocked in (
        (4, 4, 6, 2),
        (5, 5, 12, 4),
        (6, 6, 20, 6),
        (7, 5, 16, 4),
        (8, 8, 24, 6),
    )
)


# ---------------------------------------------------------------- 生成


@pytest.mark.parametrize("spec", PROPERTY_SPECS)
def test_generated_levels_always_match_the_spec_and_can_be_cleared(
    spec: LevelSpec,
) -> None:
    level = generator.generate_solvable_level(spec)
    assert generator.verify_level(level, spec) == ()


def test_generate_level_only_places_arrows_with_a_clear_path() -> None:
    """逆向构造的每一步都合法：摆放时前方没有箭头，因此倒着清一定清得完。"""
    rng = random.Random(2026)
    for _ in range(50):
        level = generator.generate_level(6, 6, 18, rng=rng)
        assert level is not None
        assert sum(1 for line in level for symbol in line if symbol != ".") == 18
        assert generator.is_solvable(level)


def test_generate_level_returns_none_when_it_cannot_place_them_all() -> None:
    """摆不下时宁愿返回 ``None``，也不返回一支少一支的“半成品”。

    1x1 的棋盘只有一个格子，放不下第二支箭头。
    """
    assert generator.generate_level(1, 1, 2, rng=random.Random(0)) is None

    solo = generator.generate_level(1, 1, 1, rng=random.Random(0))
    assert solo is not None
    assert generator.is_solvable(solo)


def test_generation_is_reproducible() -> None:
    """同一个规格（含种子）永远得到同一关，内置关卡才不会每次启动都变样。"""
    spec = LevelSpec(rows=5, cols=5, arrows=12, min_blocked=5, seed=7)
    assert generator.generate_solvable_level(spec) == generator.generate_solvable_level(
        spec
    )


def test_different_seeds_give_different_levels() -> None:
    levels = {
        generator.generate_solvable_level(
            LevelSpec(rows=6, cols=6, arrows=16, min_blocked=7, seed=seed)
        )
        for seed in range(4)
    }
    assert len(levels) == 4


def test_generation_fails_loudly_when_the_spec_is_impossible() -> None:
    """1x1 棋盘上不可能有“被挡住的箭头”：生成器必须报错，而不是交出不合格的关卡。"""
    with pytest.raises(generator.GenerationError):
        generator.generate_solvable_level(
            LevelSpec(rows=1, cols=1, arrows=1, min_blocked=1)
        )


@pytest.mark.parametrize(
    ("rows", "cols", "arrows", "min_blocked"),
    [
        (0, 4, 1, 0),
        (4, 0, 1, 0),
        (2, 2, 0, 0),
        (2, 2, 5, 0),
        (2, 2, 2, 3),
    ],
)
def test_invalid_specs_are_rejected(
    rows: int,
    cols: int,
    arrows: int,
    min_blocked: int,
) -> None:
    with pytest.raises(ValueError):
        LevelSpec(rows=rows, cols=cols, arrows=arrows, min_blocked=min_blocked)


# ---------------------------------------------------------------- 求解与验证


def test_solver_reports_deadlocks() -> None:
    assert generator.solve(DEADLOCK_LEVEL) is None
    assert generator.solve(CROSS_DEADLOCK) is None
    assert generator.is_solvable(DEADLOCK_LEVEL) is False


def test_solver_finds_the_order_that_clears_the_chain() -> None:
    """贪心先清“现在能清”的那支，自然就得到正确的顺序。"""
    assert generator.solve(CHAIN_LEVEL) == ((0, 1), (0, 0))


def test_solver_rejects_malformed_levels() -> None:
    with pytest.raises(ValueError):
        generator.solve(())
    with pytest.raises(ValueError):
        generator.solve(("..", "."))
    with pytest.raises(ValueError):
        generator.solve(("?..",))


def test_solver_order_is_accepted_by_the_board() -> None:
    """求解器的结论必须和游戏规则一致：照它的顺序点，每一步都应当真的清掉。"""
    for level in LEVELS:
        order = generator.solve(level)
        assert order is not None

        board = Board(level, AREA)
        for row, col in order:
            result = board.handle_click(board.cell_rect(row, col).center)
            assert result is ClickResult.CLEARED
        assert board.is_cleared


def test_blocked_arrow_count_agrees_with_the_board() -> None:
    for level in LEVELS:
        board = Board(level, AREA)
        expected = sum(1 for arrow in board if not board.is_path_clear(arrow))
        assert generator.blocked_arrow_count(level) == expected


def test_verify_level_reports_every_kind_of_problem() -> None:
    """校验器要把不合格的原因说清楚，而不是只给一个“不合格”。"""
    size_spec = LevelSpec(rows=4, cols=4, arrows=3, min_blocked=0)
    assert any(
        "尺寸" in problem for problem in generator.verify_level((">..",), size_spec)
    )

    count_spec = LevelSpec(rows=4, cols=4, arrows=3, min_blocked=0)
    assert any(
        "箭头数量" in problem
        for problem in generator.verify_level(
            (".>..", "....", "....", "...."), count_spec
        )
    )

    blocked_spec = LevelSpec(rows=4, cols=4, arrows=1, min_blocked=1)
    assert any(
        "被挡住" in problem
        for problem in generator.verify_level(
            (".>..", "....", "....", "...."), blocked_spec
        )
    )

    deadlock_spec = LevelSpec(rows=4, cols=4, arrows=2, min_blocked=0)
    assert any(
        "死局" in problem
        for problem in generator.verify_level(
            (">..<", "....", "....", "...."), deadlock_spec
        )
    )


# ---------------------------------------------------------------- 内置关卡


def test_built_in_levels_match_their_specs() -> None:
    """内置关卡 = 1 关手写教程 + 每行规格一关，逐关都必须通过验证。"""
    specs = (TUTORIAL_LEVEL_SPEC, *LEVEL_SPECS)
    assert len(LEVELS) == len(specs) >= 3, "题目要求至少 3 个可通关的关卡"

    for level, spec in zip(LEVELS, specs, strict=True):
        assert generator.verify_level(level, spec) == ()


def test_every_built_in_level_has_something_to_think_about() -> None:
    """每关开局都至少有一支被挡住的箭头，否则整关只是“无脑点一遍”。"""
    for index, level in enumerate(LEVELS, start=1):
        assert generator.blocked_arrow_count(level) > 0, f"第 {index} 关没有阻挡关系"
