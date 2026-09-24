# 变更记录 27：打包体积优化（两个字重 + 字体子集化）

对应 `docs/agents/basic-info.md` 中 Priority 第 18 条：**打包体积优化：去除 Light 字重，
仅作 Regular-Bold 两级变化；导出游戏文本，做字体子集化**。

是 `change-log-15-static-font-weights.md` 的收尾：那一轮把可变字体换成三个静态字重（Light /
Regular / Bold，共 47.5 MB），换来了真正的字重层级，但也把包体撑到了 **82.0 MB**——字体占了一
半以上，而界面用到的字其实只有 **254 个**。

这一轮做两件事：字重砍到**两个**（Regular / Bold），两个字体都用 fontTools **子集化**，
并把“游戏文本”导出成可复现的字符表。

| 指标 | 改动前 | 改动后 |
| --- | --- | --- |
| 自带字体 | 3 个，47.5 MB | 2 个，**296 KB** |
| Nuitka 产物 `build/nuitka/another-arrow-rt265.dist` | 82.0 MB / 81 文件 | **34.7 MB / 80 文件** |
| wheel（未压缩） | 49.8 MB | **2.66 MB** |

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `tools/subset_fonts.py` | **新增**：用 `ast` 扫包内模块的字符串字面量导出 `build/game-text.txt`，再用 fontTools 把完整字重子集化成包内字体；`--source-directory` / `--text-output` / `--export-only` 三个参数 |
| `src/another_arrow_rt265/assets/fonts/NotoSansCJKsc-Light.otf` | **删除**：字重层级只剩两级，Light 不再使用（省 15.6 MB） |
| `src/another_arrow_rt265/assets/fonts/NotoSansCJKsc-{Regular,Bold}.otf` | **替换为子集化产物**：各 16 MB → **148 KB / 150 KB**，字形轮廓与度量原样保留 |
| `src/another_arrow_rt265/resources.py` | `FontWeight` 去掉 `LIGHT`；`BUNDLED_WEIGHTS` 只剩 `(REGULAR, BOLD)`；模块 docstring 写明“两个字重 + 已子集化” |
| `src/another_arrow_rt265/ui.py` | `_TEXT_SUBTITLE`（20 Light）与 `_TEXT_HINT`（16 Light）改用常规字重；样式表注释改成“次要靠更小的字号 + 更暗的颜色” |
| `tests/test_font_subset.py` | **新增**：覆盖检查（读字体 cmap 逐字核对导出文本）、导出文本的可信度（跳过文档字符串、含整段 ASCII）、检测机制本身有效、内置字体确实被切过（≤ 500 KB） |
| `tests/test_resources.py` | 三个字重的参数化测试改成两个；新增 `test_only_two_weights_ship`；`test_ui_styles_use_every_bundled_weight` 去掉“样式必须互不相同”（副标题与正文现在同为 20 号常规） |
| `THIRD-PARTY.md` | “是否修改”由“未修改”改为“**是**：只分发两个字重，且做过子集化”，中英双语 |
| `AGENTS.md` / `docs/dev/development-guide.md` | 结构图加 `tools/`；素材一节改成“两个字重、已子集化、改文案要重跑脚本”；新增“加一句界面文案” |
| `docs/agents/basic-info.md` | 事项 18 标记完成，新增“字体与打包体积”一节 |
| `pyproject.toml` / `uv.lock` | dev 依赖新增 `fonttools`（子集化脚本用它；测试也用它读 cmap） |

## 关键设计

### 为什么砍掉 Light

界面的层级由**字号**与**字重**两层表达：字号决定“这是什么”，字重决定“该多用力看它”。
Light 原本只用在两处——英文副标题与页脚提示行，而这两处本来就靠着**更小的字号**与
`COLOR_TEXT_MUTED` 退到背景里；把字重从细改回常规之后，肉眼几乎看不出差别，
却要为此多背一份字体文件。于是层级定死为“常规正文 + Bold 强调”两级。

`_TEXT_SUBTITLE` 与 `_TEXT_BODY` 因此变成了完全相同的 `(20, Regular)`。`_TextStyle` 是
**角色**声明（标题 / 副标题 / 正文 / 标签…），不是字重表，所以两个角色取同一组数值是合理的；
`test_ui_styles_use_every_bundled_weight` 里那条“样式表里不能有完全相同的两项”随之删掉，
只保留“两个字重都被用上”。

### 导出游戏文本的口径：源码字面量 + 整段 ASCII

“游戏文本”由 `ast` 扫 `src/another_arrow_rt265/*.py` 得到，规则有两条：

1. **只认字符串字面量**：界面文案就是字面量，注释根本不在语法树里，天然被排除；
2. **跳过文档字符串**：模块 / 类 / 函数的 docstring 与**属性文档字符串**（紧跟字段声明的
   裸字符串，如 `LevelSpec.min_blocked` 下面那段）都是“只有一个字符串的表达式语句”，
   它们不是界面文案。第一版只跳过 docstring 的前三种，属性文档字符串里的换行与数百个
   汉字因此混进了字符集（`452` 个字，还带一个 `\n`），修好后是 `254` 个。

再整段带上 ASCII 可打印字符（`0x20`–`0x7E`）：用时（`59.9`）、关卡号、版本号都是 `f-string`
在运行时算出来的，字面量里看不到，整段带上就不必逐个推敲。最后滤掉不可打印字符，
`build/game-text.txt` 里就是一份可以直接喂给 `fontTools.subset` 的字符表。

### 子集化参数：保留名字表，丢掉签名

```python
# 字体名 / 版权 / 许可声明必须跟着走（OFL 要求，测试也认名字表）
options.name_IDs = ["*"]
options.name_legacy = True
# 数字签名对子集无意义
options.drop_tables = [*options.drop_tables, "DSIG"]
```

其余走 fontTools 默认（保留 hinting、保留默认 OpenType 特性集）。输出是**确定性**的
（`recalc_timestamp` 默认关闭，连跑两次哈希一致），所以字体进仓库不会每次生成都产生 diff。

结果：字形轮廓、度量、行高一个字节都没变——`ui._font(24, Regular)` 渲染同一行字仍是
`size=(690, 35)`、`ink=24150`，Bold 仍是 `(701, 35)` / `24535`，与 `change-log-15` 记录一致。
子集化只丢掉了用不到的字形。

### 完整字重不进仓库

`assets/fonts/` 里放的是**子集化产物**，完整字重（16 MB × 2）放在 `build/fonts-full/`
（`build/` 已 gitignore）。需要重新生成时先从上游下载（地址写在 `tools/subset_fonts.py` 的
模块 docstring 里），再跑：

```bash
uv run python tools/subset_fonts.py
```

脚本按 `resources.BUNDLED_WEIGHTS` 遍历，字重表只有一处定义——将来再加字重
（或再做一次全量替换）都不用改脚本。缺源字体时它打印下载提示并以码 1 退出，不会悄悄
用旧文件糊过去。

### 防线：改了文案忘了子集化必须失败

子集化的代价是“漏字”。漏字时 `pygame` 不报错，只是静静地画成空白方块，所以专门加了一条
测试：`tests/test_font_subset.py` 用同一个 `collect_text()` 收集字，再读**字体 cmap**
逐个核对（cmap 就是 SDL_ttf 查字用的那张表）。另外三条测试钉住这条检查本身不会空转：

- `test_the_game_text_comes_from_the_ui`：导出的文本里确实有标题 / 信息栏 / 教程文案与整段 ASCII；
- `test_the_game_text_skips_docstrings`：临时造一个模块，文档字符串（含属性文档字符串）
  与注释里的生僻字 `龘` 不能被收进来；
- `test_the_coverage_check_notices_a_character_the_subset_dropped`：`龘` 确实不在 cmap 里，
  说明「差集判缺失」这条路是通的；
- `test_the_bundled_font_is_really_subsetted`：每个内置字体 ≤ 500 KB，防止哪天有人把完整
  字重塞回来（完整字重约 16 MB）。

## 验证

```powershell
uv run pytest -q                      # 491 passed（上轮 486：新增 8 条，参数化少 3 项）
uv run ruff check . ; uv run ruff format --check . ; uv run ty check   # 全绿
uv run python tools/subset_fonts.py   # 游戏文本 254 字；16.44/17.00 MB → 0.08/0.08 MB
uv run python .preview/font_check.py  # Regular (690,35) ink=24150 / Bold (701,35) ink=24535
uv run python .preview/ui_frames.py   # 开始 / 游戏 / 结算 / 教程 / 辅助线 / 十关的截图，人工确认无缺字、排版未变
uv build --wheel                      # wheel 未压缩 2.66 MB，包内只有两个 .otf 子集
uv run python -m nuitka --project     # 产物 34.7 MB / 80 文件（原 82.0 MB / 81 文件）
& .preview/capture_dist.ps1           # 产物冒烟：标题 Another Arrow、截图中文正常、关窗退出码 0
```

脚本输出（脚本可重复执行，两次生成的字体哈希一致）：

```text
游戏文本：254 个字符 → build\game-text.txt
NotoSansCJKsc-Regular.otf：16.44 MB → 0.08 MB
NotoSansCJKsc-Bold.otf：17.00 MB → 0.08 MB
```

打包日志里数据文件只剩两个字体（外加音频），数量与包内一致：

```text
Nuitka-Options: Included data file 'another_arrow_rt265\assets\fonts\LICENSE' due to package 'another_arrow_rt265' package data.
Nuitka-Options: Included data file 'another_arrow_rt265\assets\fonts\NotoSansCJKsc-Bold.otf' due to package 'another_arrow_rt265' package data.
Nuitka-Options: Included data file 'another_arrow_rt265\assets\fonts\NotoSansCJKsc-Regular.otf' due to package 'another_arrow_rt265' package data.
```

产物截图（`.preview/dist_window.png`）里开始界面、副标题、页脚按钮的中文全部正常，
说明子集化字体在 exe 内一样被正确定位与渲染。

## 后续

- 剩下的 34.7 MB 是 Python 运行时与 pygame/SDL2，不是素材；真要再压只能动打包策略
  （例如排除未用的 pygame 子模块），与本轮无关。
- 新增界面文案时留意：**新字必须重新子集化**，否则测试先失败（见上文“防线”）。
- `README.md` 与 `docs/player/` 未提及字重，本轮无需同步。
