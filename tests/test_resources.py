"""自带素材（两个静态字重字体 + 一套音频）的定位与使用测试。

界面文字不依赖系统字体是这一部分的核心承诺，因此这里既测“文件找得到”，
也测“``ui`` 真的用了它、而且真的用上了不同字重”，还测“找不到时不会崩”。
字体是**子集化并改过名**的（见 ``tools/subset_fonts.py``），字体文件内容层面的检查
（字形覆盖、名字表、版权声明）在 ``tests/test_font_subset.py``。
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pygame
import pytest

from another_arrow_rt265 import audio, resources, ui

REPO_ROOT = Path(__file__).resolve().parents[1]

FONT_FILE_NAMES = tuple(
    resources.font_file_name(weight) for weight in resources.BUNDLED_WEIGHTS
)

#: 随程序分发的全部音频（五个音效 + 一首背景音乐）的文件主名。
SOUND_FILE_STEMS = tuple(cue.value for cue in audio.Cue) + (audio.MUSIC,)


def _styles() -> list[ui._TextStyle]:
    """返回 ``ui`` 里声明的全部文字样式（模块级 ``_TEXT_*`` 常量）。"""
    return [
        value
        for name, value in vars(ui).items()
        if name.startswith("_TEXT_") and isinstance(value, ui._TextStyle)
    ]


@pytest.fixture(autouse=True)
def font_ready():
    """直接构造 ``pygame.font.Font`` 之前，字体子系统得先初始化。"""
    if not pygame.font.get_init():
        pygame.font.init()


@pytest.fixture
def fresh_caches():
    """清掉资源定位与字体缓存，避免测试之间互相污染。"""
    resources.asset_path.cache_clear()
    yield
    resources.asset_path.cache_clear()
    ui._font.cache_clear()


def _pixels(surface: pygame.Surface) -> bytes:
    """把一张 surface 拍成字节，用来判断“两处渲染是不是一模一样”。"""
    return pygame.image.tobytes(surface, "RGBA")


# ---------------------------------------------------------------- 定位


@pytest.mark.parametrize("weight", resources.BUNDLED_WEIGHTS)
def test_bundled_font_is_found(weight: resources.FontWeight) -> None:
    path = resources.font_path(weight)

    assert path is not None, f"包内 assets/fonts 的 {weight} 字体没有被找到"
    assert path.is_file()
    assert path.parent.name == resources.FONT_DIRECTORY
    assert path == resources.asset_path(*resources.font_parts(weight))


def test_font_file_names_follow_the_weight() -> None:
    """文件名写法只有一处定义：``SHSSubsetSC-<字重>.otf``。"""
    assert FONT_FILE_NAMES == (
        "SHSSubsetSC-Regular.otf",
        "SHSSubsetSC-Bold.otf",
    )
    assert resources.font_parts(resources.FontWeight.BOLD) == (
        "fonts",
        "SHSSubsetSC-Bold.otf",
    )


def test_only_two_weights_ship() -> None:
    """界面的字重层级只有两级（Regular / Bold），不再随程序分发 Light。"""
    assert resources.BUNDLED_WEIGHTS == (
        resources.FontWeight.REGULAR,
        resources.FontWeight.BOLD,
    )
    assert "LIGHT" not in resources.FontWeight.__members__


def test_missing_a_weight_is_a_regular_font_not_a_crash() -> None:
    """字重是逐个文件定位的，拿不到时返回 ``None`` 而不是报错（由 ``ui`` 降级）。"""
    assert resources.font_path(resources.FontWeight.BOLD) is not None
    assert resources.DEFAULT_WEIGHT == resources.FontWeight.REGULAR
    assert resources.font_path() == resources.font_path(resources.DEFAULT_WEIGHT)


@pytest.mark.parametrize("weight", resources.BUNDLED_WEIGHTS)
def test_bundled_assets_live_inside_the_package(weight: resources.FontWeight) -> None:
    """素材必须落在包内：uv_build 只把包内文件（与 .data 目录）放进 wheel，
    Nuitka 的 ``--project`` 又只接受与 wheel 内容一致的数据文件声明。"""
    path = resources.font_path(weight)
    assert path is not None

    assert path.is_relative_to(resources.PACKAGE_DIRECTORY)


def test_nuitka_options_declare_no_extra_data_files() -> None:
    """包内素材由 ``--include-package-data`` 自动携带；
    再写 ``include-data-dir`` 会被 ``--project`` 判为“多余的数据文件”而直接打包失败。"""
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    nuitka = pyproject["tool"]["nuitka"]

    assert "include-data-dir" not in nuitka
    assert "include-data-files" not in nuitka


def test_asset_path_returns_none_for_missing_files(fresh_caches, tmp_path) -> None:
    assert resources.asset_path("fonts", "不存在的字体.otf") is None


def test_assets_next_to_the_program_are_used_as_a_fallback(
    fresh_caches, tmp_path, monkeypatch
) -> None:
    """包目录里没有素材时（比如手工把 ``assets/`` 放在 exe 旁边），仍然找得到。"""
    monkeypatch.setattr(resources, "PACKAGE_DIRECTORY", tmp_path / "empty")
    packed = tmp_path / "dist"
    (packed / "assets" / "fonts").mkdir(parents=True)
    font = packed / "assets" / "fonts" / resources.font_file_name()
    font.write_bytes(b"packed")
    monkeypatch.setattr(resources, "executable_directory", lambda: packed)

    assert resources.font_path() == font


def test_bundled_license_ships_next_to_the_font() -> None:
    """OFL 要求分发字体时附带 License 正文，因此它必须和字体待在一起。"""
    license_file = resources.asset_path("fonts", "LICENSE")

    assert license_file is not None, "字体旁边的 LICENSE 缺失"
    text = license_file.read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in text


def test_the_bundled_font_names_are_ours_not_the_upstream_ones() -> None:
    """OFL 1.1 下修改版不沿用上游名：文件名与字体内部名称都是我们自己的。

    两者的写法只有一种约定：**文件名前缀 = 族名去掉空格 = PostScript 名的前缀**
    （名字表实际写了什么，由 ``test_font_subset.py`` 核对）。出处靠字体里的版权 /
    许可声明与 ``THIRD-PARTY.md`` 记，不再靠文件名。
    """
    assert resources.FONT_FAMILY == "SHSSubset SC"
    assert resources.FONT_STEM == "SHSSubsetSC"
    assert resources.FONT_STEM == resources.FONT_FAMILY.replace(" ", "")
    assert "Noto" not in resources.FONT_STEM
    assert resources.font_file_name(resources.FontWeight.BOLD) == "SHSSubsetSC-Bold.otf"
    assert (
        resources.font_postscript_name(resources.FontWeight.BOLD) == "SHSSubsetSC-Bold"
    )


# ---------------------------------------------------------------- 用字体


@pytest.mark.parametrize("weight", resources.BUNDLED_WEIGHTS)
def test_ui_draws_with_the_bundled_font(
    fresh_caches, weight: resources.FontWeight
) -> None:
    """``ui._font()`` 必须给出内置的那个字重，而不是系统里随便匹配到的那一个。"""
    path = resources.font_path(weight)
    assert path is not None
    expected = pygame.font.Font(str(path), 24)

    actual = ui._font(24, weight)

    assert actual.size("关卡 剩余箭头") == expected.size("关卡 剩余箭头")
    assert _pixels(actual.render("失误", True, (255, 255, 255))) == _pixels(
        expected.render("失误", True, (255, 255, 255))
    )


def test_the_bundled_weights_are_really_two_different_fonts(fresh_caches) -> None:
    """两个文件必须是两种字形：同一行字用两个字重渲染，结果不能一模一样。"""
    rendered = {
        weight: _pixels(
            ui._font(24, weight).render("一箭又一箭", True, (255, 255, 255))
        )
        for weight in resources.BUNDLED_WEIGHTS
    }

    assert len(set(rendered.values())) == len(resources.BUNDLED_WEIGHTS)


def test_ui_styles_use_every_bundled_weight() -> None:
    """确保打包的字体都被使用。

    样式是**角色**（标题 / 副标题 / 正文 / 标签…），不是字重表：去掉 Light 之后，
    副标题与正文恰好都是 20 号常规字重，两个常量因此可以一样，不再要求互不相同。
    """
    styles = _styles()

    assert styles, "样式表里一个样式都没有"
    assert {style.weight for style in styles} == set(resources.BUNDLED_WEIGHTS)


def test_cjk_text_is_not_rendered_as_placeholders(fresh_caches) -> None:
    """内置字体带中文字形：画出来必须和 pygame 默认字体（方块）不一样。"""
    bundled = ui._font(24).render("关卡", True, (255, 255, 255))
    default = pygame.font.Font(None, 24).render("关卡", True, (255, 255, 255))

    assert bundled.get_width() > default.get_width()
    assert _pixels(bundled) != _pixels(default)


def test_font_falls_back_when_the_bundled_file_is_missing(
    fresh_caches, monkeypatch
) -> None:
    """字体文件缺失时退回系统字体／pygame 内置字体，界面不能直接崩掉。"""
    monkeypatch.setattr(resources, "font_path", lambda *args: None)

    font = ui._font(20)

    assert isinstance(font, pygame.font.Font)
    assert font.render("关卡", True, (255, 255, 255)).get_width() > 0


def test_a_missing_weight_falls_back_to_the_regular_one(
    fresh_caches, monkeypatch
) -> None:
    """只少了某个字重的文件时降级用常规字重，而不是整块退到系统字体。"""
    real = resources.font_path
    monkeypatch.setattr(
        resources,
        "font_path",
        lambda weight=resources.DEFAULT_WEIGHT: (
            None if weight == resources.FontWeight.BOLD else real(weight)
        ),
    )

    text = "关卡"
    bold = ui._font(20, resources.FontWeight.BOLD).render(text, True, (255, 255, 255))
    regular = ui._font(20).render(text, True, (255, 255, 255))

    assert _pixels(bold) == _pixels(regular)


def test_font_objects_are_cached(fresh_caches) -> None:
    assert ui._font(17) is ui._font(17)
    assert ui._font(17) is not ui._font(18)
    assert ui._font(17) is not ui._font(17, resources.FontWeight.BOLD)


def test_font_sizes_stay_readable(fresh_caches) -> None:
    """换字体后行高不缩水：界面里用来排版的行高不能比默认字体还小。"""
    for style in _styles():
        assert style.font().get_height() >= style.size + 4, (
            f"字号 {style.size} 的行高异常"
        )


def test_assets_font_directory_holds_exactly_the_declared_fonts() -> None:
    """包内 ``assets/fonts`` 里只有声明且实际使用的字体。"""
    fonts_dir = (
        resources.PACKAGE_DIRECTORY
        / resources.ASSETS_DIRECTORY
        / resources.FONT_DIRECTORY
    )

    assert sorted(path.name for path in fonts_dir.glob("*.otf")) == sorted(
        FONT_FILE_NAMES
    )


# ---------------------------------------------------------------- 音频素材


@pytest.mark.parametrize("stem", SOUND_FILE_STEMS)
def test_bundled_sound_is_found(stem: str) -> None:
    path = resources.sound_path(stem)

    assert path is not None, f"包内 assets/sounds 的 {stem}.mp3 没有被找到"
    assert path.is_file()
    assert path.parent.name == resources.SOUND_DIRECTORY
    assert path == resources.asset_path(*resources.sound_parts(stem))


def test_sound_file_names_follow_the_directory_layout() -> None:
    """文件名写法只有一处定义：``assets/sounds/<名称>.mp3``。"""
    assert resources.SOUND_SUFFIX == ".mp3"
    assert resources.sound_file_name(audio.Cue.BUTTON) == "button.mp3"
    assert resources.sound_parts(audio.MUSIC) == ("sounds", "background.mp3")


@pytest.mark.parametrize("stem", SOUND_FILE_STEMS)
def test_bundled_sounds_live_inside_the_package(stem: str) -> None:
    """与字体同规矩：素材必须落在包内，否则 wheel / Nuitka 产物都带不上它。"""
    path = resources.sound_path(stem)
    assert path is not None

    assert path.is_relative_to(resources.PACKAGE_DIRECTORY)


def test_assets_sound_directory_holds_exactly_the_declared_sounds() -> None:
    """包内 ``assets/sounds`` 里只有声明且实际播放的音频（不多不少）。"""
    sounds_dir = (
        resources.PACKAGE_DIRECTORY
        / resources.ASSETS_DIRECTORY
        / resources.SOUND_DIRECTORY
    )

    assert sorted(path.stem for path in sounds_dir.iterdir()) == sorted(
        SOUND_FILE_STEMS
    )
