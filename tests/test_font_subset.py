"""字体产物：字形覆盖、字体名与体积。

字体曾是打包体积的大头（完整的静态字重每个约 16 MB，两个字重加起来比程序本身还大），
所以仓库里存的是**子集化后的字体**：只保留游戏真正会画出来的字，并把族名改成自己的
（OFL 1.1 下修改版不沿用上游族名），全部由 ``tools/subset_fonts.py`` 生成。

子集化换来了体积，代价是必须钉住一条约束：**改了界面文案就要重新子集化**，
否则新字在界面里会变成空白方块——本文件就是那条防线（`pygame` 不会报错，
只是静静地画不出字，所以只能靠测试拦住）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from fontTools.ttLib import TTFont

from another_arrow_rt265 import resources

REPO_ROOT = Path(__file__).resolve().parents[1]

#: 子集化后的字体上限：完整字重约 16 MB，真做过子集化就不可能这么大。
MAX_BUNDLED_FONT_BYTES = 500_000

#: 只出现在文档字符串里的字符：它们不该被算进游戏文本。
DOCSTRING_ONLY_CHARACTER = "龘"

#: 上游族名：改名后的字体仍要在名字表里标明自己是谁的子集。
UPSTREAM_FAMILY_NAME = "Noto Sans CJK SC"


def _load_subset_tool() -> ModuleType:
    """按路径加载 ``tools/subset_fonts.py``（它是开发脚本，不是包的一部分）。"""
    spec = importlib.util.spec_from_file_location(
        "subset_fonts", REPO_ROOT / "tools" / "subset_fonts.py"
    )
    assert spec is not None and spec.loader is not None, "找不到 tools/subset_fonts.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundled_characters(weight: resources.FontWeight) -> set[str]:
    """返回某个内置字重真正带有的字符（读 cmap，也就是 SDL_ttf 查字的那张表）。"""
    path = resources.font_path(weight)
    assert path is not None, f"内置的 {weight} 字体没找到"
    with TTFont(path, lazy=True) as font:
        cmap = font.getBestCmap()
    assert cmap is not None, "字体里没有可用的 cmap"
    return {chr(code) for code in cmap}


def _name_records(weight: resources.FontWeight) -> dict[int, str]:
    """返回字体名字表里“name ID → 文字”的映射。"""
    path = resources.font_path(weight)
    assert path is not None, f"内置的 {weight} 字体没找到"
    with TTFont(path, lazy=True) as font:
        return {record.nameID: record.toUnicode() for record in font["name"].names}


@pytest.fixture(scope="module")
def game_text() -> str:
    """游戏全部界面文字用到的字符（与子集化时用的是同一份口径）。"""
    return _load_subset_tool().collect_text()


def test_the_game_text_comes_from_the_ui(game_text: str) -> None:
    """导出的文本不是空的，抽查的字确实来自界面与教程。"""
    characters = set(game_text)

    assert set("一箭又一箭") <= characters, "标题没被收集到"
    assert set("剩余箭头失误") <= characters, "信息栏文案没被收集到"
    assert set("点击高亮的箭头") <= characters, "教程文案没被收集到"
    # 时间、关卡号这类字是 f-string 在运行时算出来的，字面量里看不到，所以整段带上。
    assert {chr(code) for code in range(0x20, 0x7F)} <= characters


def test_the_game_text_skips_docstrings(tmp_path: Path) -> None:
    """文档字符串与注释不是界面文案，不该把字形带进子集。"""
    module = tmp_path / "sample.py"
    module.write_text(
        f'"""{DOCSTRING_ONLY_CHARACTER} 模块说明。"""\n'
        "\n"
        "\n"
        "class Sample:\n"
        f'    """{DOCSTRING_ONLY_CHARACTER} 类说明。"""\n'
        "\n"
        "    count: int\n"
        f'    """{DOCSTRING_ONLY_CHARACTER} 属性说明。"""\n'
        "\n"
        "\n"
        "def f() -> str:\n"
        f'    """{DOCSTRING_ONLY_CHARACTER} 函数说明。"""\n'
        f"    # 注释里的 {DOCSTRING_ONLY_CHARACTER} 也不算\n"
        '    return "第 1 关"\n',
        encoding="utf-8",
    )

    text = _load_subset_tool().collect_text([module])

    assert set("第关") <= set(text)
    assert DOCSTRING_ONLY_CHARACTER not in text


@pytest.mark.parametrize("weight", resources.BUNDLED_WEIGHTS)
def test_bundled_font_covers_every_character_the_game_draws(
    game_text: str, weight: resources.FontWeight
) -> None:
    """内置字体的 cmap 必须覆盖游戏文本：少一个字，界面里就是一个空白方块。"""
    missing = sorted(set(game_text) - _bundled_characters(weight))

    assert not missing, (
        f"{resources.font_file_name(weight)} 缺 {len(missing)} 个字：{''.join(missing)}"
        "——改了界面文案后请重新跑 `uv run python tools/subset_fonts.py`"
    )


def test_the_coverage_check_notices_a_character_the_subset_dropped() -> None:
    """子集里确实没有的字必须被判成缺失，否则上面的覆盖检查是空转的。"""
    assert DOCSTRING_ONLY_CHARACTER not in _bundled_characters(resources.DEFAULT_WEIGHT)
    assert DOCSTRING_ONLY_CHARACTER not in _load_subset_tool().collect_text()


@pytest.mark.parametrize("weight", resources.BUNDLED_WEIGHTS)
def test_the_bundled_font_is_renamed_to_our_family(
    weight: resources.FontWeight,
) -> None:
    """OFL 1.1 下修改版不沿用上游族名：族名 / 子族名 / 全名 / PostScript 名都已换掉。"""
    names = _name_records(weight)

    assert names[1] == resources.FONT_FAMILY == "SHSSubset SC"
    assert names[2] == weight.value
    assert names[4] == f"{resources.FONT_FAMILY} {weight.value}"
    assert names[6] == resources.font_postscript_name(weight)
    assert names[1] != UPSTREAM_FAMILY_NAME


@pytest.mark.parametrize("weight", resources.BUNDLED_WEIGHTS)
def test_the_renamed_font_keeps_the_upstream_notices(
    weight: resources.FontWeight,
) -> None:
    """改名不能改掉别人的声明：版权（ID 0）、OFL 许可（ID 13/14）与出处备注都在。"""
    names = _name_records(weight)

    assert "Adobe" in names[0], "上游版权声明被改掉了"
    assert "SIL Open Font License" in names[13], "OFL 许可声明被改掉了"
    assert names[14] == "http://scripts.sil.org/OFL"
    assert UPSTREAM_FAMILY_NAME in names[3], "唯一标识里应标明子集的出处"


@pytest.mark.parametrize("weight", resources.BUNDLED_WEIGHTS)
def test_the_bundled_font_is_really_subsetted(weight: resources.FontWeight) -> None:
    """包内字体必须是子集化的产物（打包体积优化的成果，别再退回完整字重）。"""
    path = resources.font_path(weight)
    assert path is not None

    assert path.stat().st_size <= MAX_BUNDLED_FONT_BYTES
