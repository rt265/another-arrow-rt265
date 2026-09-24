"""自定义模式：参数夹取、确定性生成与整段参数范围的可生成性。

本模块把两条承诺钉住：

1. **参数怎么乱来都行**——越界会被夹到合法区间，界面不必自己判边界；
2. **范围内每一组参数都生成得出来**——范围是照实测数据画的（见
   ``custom`` 模块说明），这条测试就是那份数据的守门人：哪天生成器变慢或变差，
   这里会先失败，而不是等玩家把滑动条拖到某个值上才崩。
"""

from __future__ import annotations

import pytest

from another_arrow_rt265 import custom
from another_arrow_rt265.generator import blocked_arrow_count, verify_level

#: 扫参数范围时逐组试的尺寸。全扫一遍要几百次生成，因此这里只挑有代表性的几档：
#: 下限、默认值、三个中间值（含奇数边长）与上限。
SWEEP_SIZES = (custom.MIN_SIZE, 5, 8, 12, 15, custom.MAX_SIZE)


def _arrow_counts(size: int) -> tuple[int, ...]:
    """返回某个尺寸下要逐组试的箭头数量：下限、默认值、上限。"""
    return (
        custom.MIN_ARROWS,
        custom.default_arrows(size),
        custom.max_arrows(size),
    )


def test_default_parameters_sit_near_the_middle_of_the_range() -> None:
    """默认参数是“打开就能用”的一档：8x8，四成密度，离上限留一截。"""
    settings = custom.CustomLevel()

    assert settings.size == custom.DEFAULT_SIZE
    assert settings.arrows == custom.default_arrows(custom.DEFAULT_SIZE)
    assert settings.arrows < custom.max_arrows(settings.size)
    assert len(settings.level) == settings.size
    assert all(len(line) == settings.size for line in settings.level)


@pytest.mark.parametrize("size", SWEEP_SIZES)
@pytest.mark.parametrize("batch", [0, 1])
def test_every_parameter_combination_generates_a_valid_level(
    size: int, batch: int
) -> None:
    """范围内每一组参数、每一批都要生成得出来，而且符合规格、可以通关。"""
    for arrows in range(custom.MIN_ARROWS, custom.max_arrows(size) + 1):
        settings = custom.CustomLevel(size, arrows, batch)

        assert (settings.size, settings.arrows) == (size, arrows)
        problems = verify_level(settings.level, custom.spec_for(size, arrows, batch))
        assert not problems, f"{size}x{size} / {arrows} 支：{'；'.join(problems)}"


def test_dense_boards_still_have_blocked_arrows() -> None:
    """箭头多的时候开局要真的有互相挡着的箭头，而不是“一路点下去”。"""
    size, arrows = 8, 24
    settings = custom.CustomLevel(size, arrows)

    assert blocked_arrow_count(settings.level) >= round(
        arrows * custom._MIN_BLOCKED_RATIO
    ), "一律可点的关卡不算解谜"


@pytest.mark.parametrize(
    ("size", "arrows", "expected_size", "expected_arrows"),
    [
        (1, 0, custom.MIN_SIZE, custom.MIN_ARROWS),
        (-3, -3, custom.MIN_SIZE, custom.MIN_ARROWS),
        (99, 10_000, custom.MAX_SIZE, custom.max_arrows(custom.MAX_SIZE)),
        (custom.MAX_SIZE + 1, 1, custom.MAX_SIZE, custom.MIN_ARROWS),
    ],
)
def test_parameters_are_clamped_into_the_range(
    size: int, arrows: int, expected_size: int, expected_arrows: int
) -> None:
    """越界的参数一律夹回合法区间，因此界面永远拿得到一关正常的关卡。"""
    settings = custom.CustomLevel(size, arrows)

    assert settings.size == expected_size
    assert settings.arrows == expected_arrows
    assert settings.max_arrows == custom.max_arrows(expected_size)


def test_arrows_come_down_when_the_board_shrinks() -> None:
    """缩小棋盘把箭头顶到上限之外时，箭头一起夹下来——这是同一次改动。"""
    settings = custom.CustomLevel(custom.MAX_SIZE, custom.max_arrows(custom.MAX_SIZE))

    assert settings.change_size(custom.MIN_SIZE) is True
    assert settings.arrows == custom.max_arrows(custom.MIN_SIZE)
    assert len(settings.level) == custom.MIN_SIZE


def test_setting_the_same_parameters_again_does_not_regenerate() -> None:
    """取值没变就不重新生成：拖着滑动条停在原地不该让预览跳一下。"""
    settings = custom.CustomLevel(8, 20)
    level = settings.level

    assert settings.change_size(8) is False
    assert settings.change_arrows(20) is False
    assert settings.level is level

    # 越界但夹回原值的取值同样算“没变”（滑动条拖到量程外不会白重算一关）。
    top = custom.CustomLevel(custom.MAX_SIZE, custom.max_arrows(custom.MAX_SIZE))
    assert top.change_size(custom.MAX_SIZE + 5) is False
    assert top.change_arrows(10_000) is False


def test_the_same_parameters_always_give_the_same_level() -> None:
    """参数（含第几批）决定关卡：同一组参数永远同一关，玩法可复现。"""
    settings = custom.CustomLevel(8, 20)

    assert custom.CustomLevel(8, 20).level == settings.level

    # 调走再调回来，拿到的还是原来那一关（生成结果按参数缓存）。
    settings.change_arrows(30)
    settings.change_arrows(20)
    assert settings.level == custom.CustomLevel(8, 20).level


def test_reroll_keeps_the_parameters_but_changes_the_level() -> None:
    """“换一关”只换一批：参数不该跟着动，关卡要真的是另一关。"""
    settings = custom.CustomLevel(8, 20)
    before = settings.level
    batch = settings.batch

    settings.reroll()

    assert (settings.size, settings.arrows) == (8, 20)
    assert settings.batch == batch + 1
    assert settings.level != before


def test_seeds_differ_between_parameters_and_batches() -> None:
    """种子是参数与批次的函数：任何一维不同都不该撞上同一个种子。"""
    seeds = {
        custom.seed_for(size, arrows, batch)
        for size in (8, 9)
        for arrows in (20, 21)
        for batch in (0, 1)
    }

    assert len(seeds) == 8
