"""定位随程序分发的静态资源（``assets/``）。

程序**自带**一份字体，而不是碰运气去匹配系统字体。素材放在**包内**
（``src/another_arrow_rt265/assets/``）：打包工具会把包内文件原样搬走，而本文件就在它们
旁边，所以 :data:`PACKAGE_DIRECTORY` 永远是第一个候选——源码运行、``uv build`` 出的
wheel、Nuitka 打出的 exe 三种形态下位置相同（已用探针在产物里核实过）。

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
from pathlib import Path
from typing import Final

#: 资源根目录名（与包内结构 ``assets/`` 保持一致）。
ASSETS_DIRECTORY: Final[str] = "assets"

#: 随程序分发的字体：Noto Sans CJK SC（可变字重），SIL OFL 1.1，声明见 ``THIRD-PARTY.md``。
FONT_PARTS: Final[tuple[str, ...]] = ("fonts", "NotoSansCJKsc-VF.otf")

#: 本文件所在目录，也就是包目录（素材默认就放在它的 ``assets/`` 下）。
PACKAGE_DIRECTORY: Final[Path] = Path(__file__).resolve().parent

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


def font_path() -> Path | None:
    """返回随程序分发的字体文件路径（找不到时为 ``None``，由调用方兜底）。"""
    return asset_path(*FONT_PARTS)
