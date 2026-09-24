# 变更记录 28：字体改名为 SHSSubset SC（OFL 1.1）

延续 `change-log-27-font-subset.md`（Priority 第 18 条）。第 27 轮把字体子集化到 296 KB，
但**沿用上游族名** `Noto Sans CJK SC`——OFL 1.1 允许修改与再分发，前提是修改版不再使用
上游的名称（上游版权声明里若声明了 Reserved Font Name，修改版更必须改名）。
本轮把子集化产物的名字换成自己的：**`SHSSubset SC`**（Regular / Bold）。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `tools/subset_fonts.py` | 新增第 3 步**改名**：`rename_font(font, weight)` 只改“这是谁家的字体”那几个字段（族名 / 子族名 / 全名 / PostScript 名 / 唯一标识），版权（ID 0）、OFL 许可（ID 13 / 14）、商标与厂商 / 设计者（ID 7~12）一概不动；`subset_font()` 多收一个 `weight`，改动完再落盘 |
| `src/another_arrow_rt265/resources.py` | 新增 `FONT_FAMILY = "SHSSubset SC"`（字体内部族名）与 `font_postscript_name(weight)`（`SHSSubsetSC-{Regular,Bold}`）；`FONT_STEM` 的注释写明“文件名沿用上游族名，只是标明出处” |
| `src/another_arrow_rt265/assets/fonts/NotoSansCJKsc-{Regular,Bold}.otf` | **重新生成**：内容（字形 / 度量）与上轮相同，名字表换成新名字 |
| `tests/test_resources.py` | `test_the_bundled_file_really_is_the_declared_font`（按位找 UTF-16BE 的 `Noto Sans CJK SC`）换成 `test_the_bundled_font_family_is_ours_not_the_upstream_one`（族名 / 文件前缀 / PostScript 名三者的约定） |
| `tests/test_font_subset.py` | 新增两条按字重参数化的名字表测试：族名 / 子族名 / 全名 / PostScript 名是自己的；版权、OFL 声明、出处备注还在 |
| `THIRD-PARTY.md` | 增加“名称 \| SHSSubset SC”一行（原来的“名称”已被改成“原始名称”），`是否修改` 补上“修改版不再沿用上游族名” |
| `docs/dev/development-guide.md` | 素材与“加一句界面文案”两节说明改名与文件名口径；`.preview/font_check.py` 那行改成“两个字重” |

## 关键设计

### 名字表里改什么、不改什么

子集化后的名字表只有 Windows Unicode（平台 3 / en-US）一组记录，因此就地改文字即可：

| ID | 字段 | 处理 |
| --- | --- | --- |
| 1 / 2 | 族名 / 子族名 | → `SHSSubset SC` / `Regular`、`Bold` |
| 4 | 全名 | → `SHSSubset SC Regular`、`SHSSubset SC Bold` |
| 6 | PostScript 名 | → `SHSSubsetSC-Regular`、`SHSSubsetSC-Bold` |
| 3 | 唯一标识 | → `SHSSubsetSC-Bold;Version 2.004;subset of Noto Sans CJK SC`（沿用上游版本号，并写明是谁的子集） |
| 0 | 版权 | **不动**（`© 2014-2021 Adobe (http://www.adobe.com/).`）：OFL 要求保留 |
| 5 / 7~14 | 版本 / 商标 / 厂商 / 设计者 / 网址 / OFL 声明与链接 | **不动**：都是上游的声明与出处信息 |

新名字的写法集中在 `resources.py` 一处声明（`FONT_FAMILY` + `font_postscript_name()`），
脚本、测试都从那里取，不再各写一份字符串。

### 文件名为什么不动

`assets/fonts/NotoSansCJKsc-{Regular,Bold}.otf` 里的 `NotoSansCJKsc` 是**文件的出处**，
不是字体名：一个文件叫“Noto Sans CJK SC 的哪个字重”，读的人才知道它从哪来；
字体内部叫什么，由名字表回答（现在是 `SHSSubset SC`）。两者职责不同，因此没有改文件名，
`resources.FONT_STEM`（文件名前缀）与 `resources.FONT_FAMILY`（族名）也分成了两个常量。

### 防线

- `test_the_bundled_font_is_renamed_to_our_family`：族名 == `resources.FONT_FAMILY` ==
  `SHSSubset SC`，且**不等于上游族名**；子族名、全名、PostScript 名逐一对齐；
- `test_the_renamed_font_keeps_the_upstream_notices`：改名不能顺手改掉别人的声明——
  版权（ID 0 含 `Adobe`）、OFL 许可（ID 13 含 `SIL Open Font License`）、许可链接（ID 14）、
  以及唯一标识里的“subset of Noto Sans CJK SC”都要在；
- `test_the_bundled_font_family_is_ours_not_the_upstream_one`（`test_resources.py`）：
  不读字体文件也能拦住“把族名改回上游”的手滑。

## 验证

```powershell
uv run pytest -q                      # 495 passed（上轮 491：+4 名字表测试，-1 旧的按位找名字）
uv run ruff check . ; uv run ruff format --check . ; uv run ty check   # 全绿
uv run python tools/subset_fonts.py   # 游戏文本 254 字；两个字重 0.08 MB → 0.08 MB（字体名 SHSSubset SC …）
uv run python .preview/font_check.py  # 度量与上轮一致：Regular (690,35) ink=24150 / Bold (701,35) ink=24535
uv run python .preview/ui_frames.py   # 界面截图人工确认无缺字、排版未变
uv run python -m nuitka --project     # 重打包，改名后的字体照常进产物
& .preview/capture_dist.ps1           # 产物冒烟：标题 Another Arrow、截图中文正常、关窗退出码 0
```

名字表实测（`fontTools` 读回来）：

```text
== NotoSansCJKsc-Regular.otf
  0 '© 2014-2021 Adobe (http://www.adobe.com/).'
  1 'SHSSubset SC'
  2 'Regular'
  3 'SHSSubsetSC-Regular;Version 2.004;subset of Noto Sans CJK SC'
  4 'SHSSubset SC Regular'
  6 'SHSSubsetSC-Regular'
 13 'This Font Software is licensed under the SIL Open Font License, Version 1.1. …'
```

产物里的副本同样带着新名字（`build/nuitka/another-arrow-rt265.dist/…/assets/fonts/`）：

```text
NotoSansCJKsc-Bold.otf -> SHSSubset SC / SHSSubsetSC-Bold (77060 B)
NotoSansCJKsc-Regular.otf -> SHSSubset SC / SHSSubsetSC-Regular (75144 B)
```

## 后续

- 若以后要换族名，改 `resources.FONT_FAMILY` 一处，再跑
  `uv run python tools/subset_fonts.py` 重新生成字体即可（文件名不受影响）。
- `assets/fonts/LICENSE` 的顶部声明（“This Font Software is based on Noto Sans CJK SC.”
  与 Noto Project Authors 版权）由开发者维护，本轮未改。

## 追记（同日）：文件名也改成 `SHSSubsetSC-*.otf`

开发者随后把包内的两个字体文件也改了名，本轮追认这个改动并修好受影响的代码与测试——
上面“文件名为什么不动”那一节的结论作废，历史记录（本文件与 `change-log-27` 里的
`NotoSansCJKsc-{Regular,Bold}.otf`）只反映当时的状态。

- `resources.FONT_STEM`：`NotoSansCJKsc` → **`SHSSubsetSC`**。现在的约定只有一条：
  **文件名前缀 = 族名去掉空格 = PostScript 名前缀**，`font_file_name()` 与
  `font_postscript_name()` 都从 `FONT_STEM` 派生，不再有“文件名说上游、名字表说自己”的两套写法。
- `tools/subset_fonts.py`：新增 `SOURCE_FONT_STEM = "NotoSansCJKsc"`——**源字体**（`build/fonts-full/`，
  上游的完整字重）仍用上游文件名，**产物**用 `resources.font_file_name()`，两边不再共用一份名字；
  缺源字体时的提示也直接给出它要的文件名。
- 测试：`test_font_file_names_follow_the_weight` 的期望改成 `SHSSubsetSC-*.otf`；
  `test_the_bundled_font_names_are_ours_not_the_upstream_ones` 改成钉住那条约定
  （`FONT_STEM == FONT_FAMILY.replace(" ", "")`、`"Noto" not in FONT_STEM`）。
  18 条测试（字体定位 / 使用 / 覆盖率 / 名字表 / 体积）随之恢复绿色。
- `ui._font()` 的 docstring、`docs/dev/development-guide.md`、`docs/agents/basic-info.md`
  里的字体路径一并改成新名字。

验证：`uv run pytest -q` → **495 passed**；`ruff check` / `ruff format --check` / `ty check` 全绿；
重跑 `uv run python tools/subset_fonts.py` 生成的两个文件与开发者手改名的完全一致
（`SHSSubsetSC-Regular.otf` 75,144 B、`SHSSubsetSC-Bold.otf` 77,060 B，脚本确定性输出）；
重打包产物与冒烟照常通过。
