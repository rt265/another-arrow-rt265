"""定位随程序分发的静态资源（``assets/``）。

程序**自带**全部素材：一套字体（Noto Sans CJK SC 的三个**静态字重**：Light / Regular /
Bold）与一套音频（背景音乐 + 五个音效）。字体不碰运气去匹配系统字体，音频不依赖
用户机器上装了什么。素材放在**包内**（``src/another_arrow_rt265/assets/``）：
打包工具会把包内文件原样搬走，而本文件就在它们旁边，所以 :data:`PACKAGE_DIRECTORY`
永远是第一个候选——源码运行、``uv build`` 出的 wheel、Nuitka 打出的 exe 三种形态下
位置相同（已用探针在产物里核实过）。

其余候选只是为了能兜住手工部署：

- 可执行文件同级目录（把 ``assets/`` 丢在 exe 旁边也能用）；
- 源码树的 ``src`` 与仓库根（历史上素材曾放在仓库根，留作兼容）；
- 当前工作目录。

:func:`asset_path` 按上述顺序逐个试，返回**第一个真实存在**的文件；一个都没有时返回
``None``，由调用方决定兜底策略（例如退回系统字体）。

本模块不依赖 pygame，可以直接测。
"""

from __future__ import annotations

import functools
import sys
from enum import StrEnum
from pathlib import Path
from typing import Final

#: 资源根目录名（与包内结构 ``assets/`` 保持一致）。
ASSETS_DIRECTORY: Final[str] = "assets"

#: 字体所在子目录与文件名前缀：``assets/fonts/NotoSansCJKsc-<字重>.otf``。
FONT_DIRECTORY: Final[str] = "fonts"
FONT_STEM: Final[str] = "NotoSansCJKsc"

#: 音频所在子目录与后缀：``assets/sounds/<名称>.mp3``（名称含义见 ``audio.Cue``）。
SOUND_DIRECTORY: Final[str] = "sounds"
SOUND_SUFFIX: Final[str] = ".mp3"

#: 本文件所在目录，也就是包目录（素材默认就放在它的 ``assets/`` 下）。
PACKAGE_DIRECTORY: Final[Path] = Path(__file__).resolve().parent


class FontWeight(StrEnum):
    """随程序分发的静态字重。

    Noto Sans CJK SC 有可变字重（``-VF.otf``）与七个静态字重两套发行版。这里用
    **静态字重**：SDL_ttf 只会渲染可变字体的默认实例，选不了轴上的值，想要调整字体粗细
    就只能使用静态字重。
    """

    LIGHT = "Light"
    REGULAR = "Regular"
    BOLD = "Bold"


#: 随程序打包的字重（按由轻到重排列，也就是界面上的层级顺序）。
BUNDLED_WEIGHTS: Final[tuple[FontWeight, ...]] = (
    FontWeight.LIGHT,
    FontWeight.REGULAR,
    FontWeight.BOLD,
)

#: 常规字重：正文与绝大多数标签用它，也是某个字重缺文件时的兜底。
DEFAULT_WEIGHT: Final[FontWeight] = FontWeight.REGULAR

# 从本文件向上找几层：包目录 → src → 仓库根。
_SOURCE_TREE_DEPTH: Final[int] = 2


def executable_directory() -> Path:
    """返回可执行文件所在目录。

    Nuitka 的产物里 ``sys.executable`` 指向可执行文件本身（standalone 的 dist 目录、
    onefile 则是用户手上那个 exe 的路径），因此“把 ``assets/`` 放在程序旁边”这种手工
    部署方式也能生效。
    """
    return Path(sys.executable).resolve().parent


def _search_roots() -> tuple[Path, ...]:
    """按优先级列出可能存放 ``assets/`` 的目录（去重且保持顺序）。"""
    roots = [
        PACKAGE_DIRECTORY,
        executable_directory(),
        *PACKAGE_DIRECTORY.parents[:_SOURCE_TREE_DEPTH],
        Path.cwd(),
    ]
    return tuple(dict.fromkeys(roots))


@functools.cache
def asset_path(*parts: str) -> Path | None:
    """在候选目录里查找 ``assets/<parts...>``，返回第一个存在的文件，找不到返回 ``None``。"""
    for root in _search_roots():
        candidate = root.joinpath(ASSETS_DIRECTORY, *parts)
        if candidate.is_file():
            return candidate
    return None


def font_file_name(weight: FontWeight = DEFAULT_WEIGHT) -> str:
    """返回某个字重的字体文件名（例如 ``NotoSansCJKsc-Light.otf``）。"""
    return f"{FONT_STEM}-{weight.value}.otf"


def font_parts(weight: FontWeight = DEFAULT_WEIGHT) -> tuple[str, ...]:
    """返回某个字重在 ``assets/`` 下的相对路径片段。"""
    return (FONT_DIRECTORY, font_file_name(weight))


def font_path(weight: FontWeight = DEFAULT_WEIGHT) -> Path | None:
    """返回某个字重的字体文件路径（找不到时为 ``None``，由调用方兜底）。"""
    return asset_path(*font_parts(weight))


def sound_file_name(name: str) -> str:
    """返回音频文件名（例如 ``background.mp3``）；``name`` 是 ``audio.Cue`` 的值。"""
    return f"{name}{SOUND_SUFFIX}"


def sound_parts(name: str) -> tuple[str, ...]:
    """返回音频在 ``assets/`` 下的相对路径片段。"""
    return (SOUND_DIRECTORY, sound_file_name(name))


def sound_path(name: str) -> Path | None:
    """返回音频文件路径（找不到时为 ``None``，由 :class:`audio.Audio` 静默跳过）。"""
    return asset_path(*sound_parts(name))
