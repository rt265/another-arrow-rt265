"""导出游戏文本，把随程序分发的字体子集化，并把字体改名。

打包体积的大头一度是字体：完整的 Noto Sans CJK SC 静态字重每个约 16 MB，
两个字重加起来 31.8 MB，比程序本身还大；而界面用到的字只有几百个。这个脚本做三件事：

1. **导出游戏文本**：扫描 ``src/another_arrow_rt265/*.py`` 里的字符串字面量
   （文档字符串与注释不算界面文案），把游戏会画出来的字收集起来，写到
   ``build/game-text.txt``（``build/`` 已 gitignore）；
2. **子集化字体**：以这批字为子集，用 fontTools 生成
   ``src/another_arrow_rt265/assets/fonts/SHSSubsetSC-<字重>.otf``（文件名与字重表分别由
   ``resources.font_file_name()`` 与 ``resources.BUNDLED_WEIGHTS`` 给出，不再另写一份）；
3. **改字体名**：把族名换成 :data:`resources.FONT_FAMILY`（``SHSSubset SC``）——
   OFL 1.1 下修改版不该继续用上游族名，否则会被当成上游原件；上游的版权、许可与
   设计者声明照旧保留（OFL 要求随分发保留）。产物文件名（``SHSSubsetSC-<字重>.otf``）
   与字体内部的名称同源，源字体则仍叫上游的名字。

除了字面量，还整段带上 ASCII 可打印字符：用时（``59.9``）、关卡号、版本号这些字是
``f-string`` 在运行时算出来的，字面量里看不到它们。

源字体（未子集化的完整 OTF）**不进仓库**，需要重新生成时先从上游下载：

    https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf
    https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf

放进 ``build/fonts-full/``（默认的 ``--source-directory``，文件名照上游写法），然后：

    uv run python tools/subset_fonts.py

本地还没有完整字重（比如刚克隆仓库、或换了机器）时，加 ``--download`` 让脚本自己从上游取：

    uv run python tools/subset_fonts.py --download

子集化后的字体仍然基于 Noto Sans CJK SC（OFL-1.1，允许修改与再分发，见
``THIRD-PARTY.md`` 的“是否修改”一栏），但族名已经换成 :data:`resources.FONT_FAMILY`。
``tests/test_font_subset.py`` 会检查“包内字体覆盖了游戏全部文字”与“字体名、版权声明各就各位”，
因此**改了界面文案却忘了重新子集化会直接测试失败**，而不是在玩家眼前变成空白方块。
"""

from __future__ import annotations

import argparse
import ast
import sys
import urllib.request
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Final

from fontTools import subset
from fontTools.ttLib import TTFont

from another_arrow_rt265 import resources

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY: Final[Path] = REPO_ROOT / "src" / "another_arrow_rt265"
FONT_DIRECTORY: Final[Path] = PACKAGE_DIRECTORY / "assets" / "fonts"

#: 完整字体（子集化的输入）默认放这里；``build/`` 已 gitignore，因此不会进仓库。
DEFAULT_SOURCE_DIRECTORY: Final[Path] = REPO_ROOT / "build" / "fonts-full"
#: 导出的游戏文本（子集化的输入字符表）默认写这里。
DEFAULT_TEXT_OUTPUT: Final[Path] = REPO_ROOT / "build" / "game-text.txt"

#: 上游族名与它的文件名前缀：源字体是 ``build/fonts-full/NotoSansCJKsc-<字重>.otf``，
#: 产物则是 :func:`resources.font_file_name`（``SHSSubsetSC-<字重>.otf``）。
SOURCE_FAMILY_NAME: Final[str] = "Noto Sans CJK SC"
SOURCE_FONT_STEM: Final[str] = "NotoSansCJKsc"
#: 源字体从上游哪里取（``--download`` 用；仅本机生成字体时联网）。
SOURCE_URL: Final[str] = (
    "https://github.com/notofonts/noto-cjk/raw/main"
    "/Sans/OTF/SimplifiedChinese/{file_name}"
)

#: 动态文字用到的字符：运行时算出来的数字、时间、英文都在这一段里。
ASCII_PRINTABLE: Final[str] = "".join(chr(code) for code in range(0x20, 0x7F))


def source_modules() -> tuple[Path, ...]:
    """列出可能写着界面文案的模块（包内全部 ``*.py``，按路径排序）。"""
    return tuple(sorted(PACKAGE_DIRECTORY.glob("*.py")))


def _documentation_ids(tree: ast.Module) -> set[int]:
    """返回语法树里“文档字符串”那些常量的 ``id()``。

    模块 / 类 / 函数的文档字符串与紧跟字段声明的**属性文档字符串**都是
    “只有一个字符串的表达式语句”——它们是文档，不是界面文案（注释不在语法树里，
    本来就不会被收集）。
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant):
            continue
        if isinstance(node.value.value, str):
            found.add(id(node.value))
    return found


def string_literals(tree: ast.Module) -> Iterator[str]:
    """逐个产出模块里的字符串字面量（跳过文档字符串）。"""
    documentation = _documentation_ids(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) not in documentation:
            yield node.value


def collect_text(modules: Iterable[Path] | None = None) -> str:
    """返回游戏全部界面文字用到的字（去重、按码位排序、去掉不可打印字符）。"""
    characters = set(ASCII_PRINTABLE)
    for module in source_modules() if modules is None else tuple(modules):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for literal in string_literals(tree):
            characters.update(literal)
    return "".join(
        sorted(character for character in characters if character.isprintable())
    )


def _record_text(font: TTFont, name_id: int) -> str | None:
    """取某个名字 ID 的文字（取不到返回 ``None``）。"""
    for record in font["name"].names:
        if record.nameID == name_id:
            return record.toUnicode()
    return None


def rename_font(font: TTFont, weight: resources.FontWeight) -> None:
    """把字体名换成自己的（保留上游的版权与许可声明）。

    OFL 1.1 允许修改与再分发，但修改版不该继续叫作上游族名（``Noto Sans CJK SC``）——
    那会让人以为拿到的是上游原件。所以只改“这是谁家的字体”那几个字段：
    族名 / 子族名 / 全名 / PostScript 名 / 唯一标识；版权（ID 0）、许可（ID 13 / 14）、
    商标、厂商与设计者（ID 7~12）一概不动。
    """
    table = font["name"]
    family = resources.FONT_FAMILY
    subfamily = weight.value
    postscript = resources.font_postscript_name(weight)
    # 版本号沿用上游的（ID 5 形如 ``Version 2.004;hotconv ...``）。
    version = (_record_text(font, 5) or "").split(";")[0]
    replacements = {
        1: family,
        2: subfamily,
        3: ";".join(
            part
            for part in (postscript, version, f"subset of {SOURCE_FAMILY_NAME}")
            if part
        ),
        4: f"{family} {subfamily}",
        6: postscript,
    }

    for record in list(table.names):
        text = replacements.get(record.nameID)
        if text is None:
            continue
        try:
            record.string = text.encode(record.getEncoding())
        except (UnicodeEncodeError, LookupError):
            # 这个平台 / 编码放不下新名字（理论上只有非 Unicode 的旧编码会这样）。
            table.names.remove(record)


def subset_font(
    source: Path, target: Path, text: str, weight: resources.FontWeight
) -> None:
    """把 ``source`` 子集化成 ``text`` 里出现过的字形并改名，写出到 ``target``。"""
    options = subset.Options()
    # 字体名（含版权与许可声明）必须跟着走：OFL 要求保留声明，测试也认名字表。
    # ``name_IDs`` 的字面量类型是 ``int``，但 fontTools 接受 ``"*"`` 表示“全部保留”。
    options.name_IDs = ["*"]  # ty: ignore[invalid-assignment]
    options.name_legacy = True
    # 数字签名对子集化后的字体无意义，留着只会白占体积。
    options.drop_tables = [*options.drop_tables, "DSIG"]

    font = subset.load_font(source, options)
    try:
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=text)
        subsetter.subset(font)
        rename_font(font, weight)
        target.parent.mkdir(parents=True, exist_ok=True)
        subset.save_font(font, target, options)
    finally:
        font.close()


def download_source(source: Path) -> None:
    """从上游下载完整字体到 ``source``（换机器 / 新克隆后没有源字体时用）。"""
    url = SOURCE_URL.format(file_name=source.name)
    print(f"下载源字体：{url}")
    with urllib.request.urlopen(url) as response:
        data = response.read()
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(data)
    print(f"  → {source}（{len(data) / 1e6:.1f} MB）")


def build_parser() -> argparse.ArgumentParser:
    """命令行入口的参数表。"""
    parser = argparse.ArgumentParser(
        description="导出游戏文本，并把包内字体子集化到这批字上。"
    )
    parser.add_argument(
        "--source-directory",
        type=Path,
        default=DEFAULT_SOURCE_DIRECTORY,
        help="完整字体（子集化的输入）所在目录，默认 %(default)s",
    )
    parser.add_argument(
        "--text-output",
        type=Path,
        default=DEFAULT_TEXT_OUTPUT,
        help="导出的游戏文本写到哪，默认 %(default)s",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="只导出游戏文本，不动字体文件",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="源字体不在 --source-directory 里时，先从上游下载",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """导出游戏文本、逐个字重子集化并改名，返回进程退出码。"""
    arguments = build_parser().parse_args(argv)

    text = collect_text()
    arguments.text_output.parent.mkdir(parents=True, exist_ok=True)
    arguments.text_output.write_text(text, encoding="utf-8")
    print(f"游戏文本：{len(text)} 个字符 → {arguments.text_output}")
    if arguments.export_only:
        return 0

    for weight in resources.BUNDLED_WEIGHTS:
        file_name = resources.font_file_name(weight)
        source_name = f"{SOURCE_FONT_STEM}-{weight.value}.otf"
        source = arguments.source_directory / source_name
        if not source.is_file():
            if not arguments.download:
                print(f"缺少源字体：{source}", file=sys.stderr)
                print(
                    f"完整字重不进仓库：把上游的 {source_name} 放到上面那个目录，"
                    "或者加 --download 让脚本自己取（下载地址见模块说明）。",
                    file=sys.stderr,
                )
                return 1
            download_source(source)

        target = FONT_DIRECTORY / file_name
        before = target.stat().st_size if target.is_file() else source.stat().st_size
        subset_font(source, target, text, weight)
        print(
            f"{file_name}：{before / 1e6:.2f} MB → {target.stat().st_size / 1e6:.2f} MB"
            f"（字体名 {resources.FONT_FAMILY} {weight.value}）"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
