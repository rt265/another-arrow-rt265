"""自带素材（字体）的定位与使用测试。

界面文字不依赖系统字体是这一部分的核心承诺，因此这里既测“文件找得到”，
也测“``ui`` 真的用了它”，还测“找不到时不会崩”。
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pygame
import pytest

from another_arrow_rt265 import resources, ui

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_bundled_font_is_found() -> None:
    path = resources.font_path()

    assert path is not None, "包内 assets/fonts 的字体没有被找到"
    assert path.is_file()
    assert path.parent.name == "fonts"
    assert path == resources.asset_path(*resources.FONT_PARTS)


def test_bundled_assets_live_inside_the_package() -> None:
    """素材必须落在包内：uv_build 只把包内文件（与 .data 目录）放进 wheel，
    Nuitka 的 ``--project`` 又只接受与 wheel 内容一致的数据文件声明。"""
    path = resources.font_path()
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
    font = packed / "assets" / "fonts" / resources.FONT_PARTS[-1]
    font.write_bytes(b"packed")
    monkeypatch.setattr(resources, "executable_directory", lambda: packed)

    assert resources.asset_path(*resources.FONT_PARTS) == font


def test_bundled_license_ships_next_to_the_font() -> None:
    """OFL 要求分发字体时附带 License 正文，因此它必须和字体待在一起。"""
    license_file = resources.asset_path("fonts", "LICENSE")

    assert license_file is not None, "字体旁边的 LICENSE 缺失"
    text = license_file.read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in text


def test_the_bundled_file_really_is_the_declared_font() -> None:
    """字体文件与 ``THIRD-PARTY.md`` 里声明的是同一个：名字对得上。"""
    path = resources.font_path()
    assert path is not None

    # 字体名表是 UTF-16BE，直接按位找 "Noto Sans CJK SC" 的编码。
    assert "Noto Sans CJK SC".encode("utf-16-be") in path.read_bytes()


def test_third_party_notice_mentions_the_bundled_font() -> None:
    """引了第三方素材就得在 THIRD-PARTY.md 里点名（AGENTS.md 的要求）。"""
    notice = (REPO_ROOT / "THIRD-PARTY.md").read_text(encoding="utf-8")

    assert resources.FONT_PARTS[-1] in notice
    assert "SIL OPEN FONT LICENSE" in notice


# ---------------------------------------------------------------- 用字体


def test_ui_draws_with_the_bundled_font(fresh_caches) -> None:
    """``ui._font()`` 必须给出内置字体，而不是系统里随便匹配到的那一个。"""
    path = resources.font_path()
    assert path is not None
    expected = pygame.font.Font(str(path), 24)

    actual = ui._font(24)

    assert actual.size("关卡 剩余箭头") == expected.size("关卡 剩余箭头")
    assert _pixels(actual.render("失误", True, (255, 255, 255))) == _pixels(
        expected.render("失误", True, (255, 255, 255))
    )


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
    monkeypatch.setattr(resources, "font_path", lambda: None)

    font = ui._font(20)

    assert isinstance(font, pygame.font.Font)
    assert font.render("关卡", True, (255, 255, 255)).get_width() > 0


def test_font_objects_are_cached(fresh_caches) -> None:
    assert ui._font(17) is ui._font(17)
    assert ui._font(17) is not ui._font(18)


def test_font_sizes_stay_readable(fresh_caches) -> None:
    """换字体后行高不缩水：界面里用来排版的行高不能比默认字体还小。"""
    for size in (15, 17, 20, 24, 36, 68):
        assert ui._font(size).get_height() >= size + 4, f"字号 {size} 的行高异常"


def test_assets_font_directory_holds_exactly_the_declared_font() -> None:
    """包内 ``assets/fonts`` 里只有声明过的那一个字体，不留没用上（也没声明）的文件。"""
    fonts_dir = resources.PACKAGE_DIRECTORY / resources.ASSETS_DIRECTORY / "fonts"

    assert (fonts_dir / resources.FONT_PARTS[-1]).is_file()
    assert [p.name for p in fonts_dir.glob("*.otf")] == [resources.FONT_PARTS[-1]]
