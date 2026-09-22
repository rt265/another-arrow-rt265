# 变更记录 13：程序自带字体（不再依赖系统字体）

对应 `docs/agents/basic-info.md` 中 Priority 第 13 条：**UI 优化：优化图标、字体等素材的显示效果**
（本轮只做**字体**部分；图标仍是几何绘制，见文末“后续”）。

这一轮让界面文字用上**随程序分发**的字体（Noto Sans CJK SC，SIL OFL 1.1）：
以前 `ui._font()` 是用 `pygame.font.match_font()` 去猜系统里的中文字体，同一份代码在别人机器上
可能变成别的字体、甚至退化成方块字；现在字体文件跟着程序走，**源码运行、wheel、exe 三处一致**。

为让打包链接受这份字体，素材从仓库根目录搬进了**包内**（`src/another_arrow_rt265/assets/fonts/`）——
原因见下面的“为什么必须放进包内”，这不是审美选择，是 `uv_build` + Nuitka `--project` 的硬约束。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/assets/fonts/NotoSansCJKsc-VF.otf` | **新增**（由仓库根 `assets/fonts/` 移入）：Noto Sans CJK SC 可变字重，29.3 MB，原样使用、未做子集化或改名 |
| `src/another_arrow_rt265/assets/fonts/LICENSE` | **新增**（同上移入）：SIL OFL 1.1 全文，与字体同目录分发（OFL 的强制要求） |
| `src/another_arrow_rt265/resources.py` | **新增**：`ASSETS_DIRECTORY` / `FONT_PARTS` / `PACKAGE_DIRECTORY` / `executable_directory()` / `asset_path()` / `font_path()`，按“包目录 → 可执行文件同级目录 → 源码树 → cwd”找素材，找不到返回 `None` |
| `src/another_arrow_rt265/ui.py` | `_font()` 改为**优先**用 `resources.font_path()` 的字体，其次才是系统字体 `_FONT_CANDIDATES`，最后退回 pygame 内置字体；注释说明三者关系 |
| `pyproject.toml` | **删除** `include-data-dir`（包内素材由 `--include-package-data` 自动携带），并把“为什么不能写 `include-data-dir`”记在注释里 |
| `src/another_arrow_rt265/icons.py` | 模块 docstring 里“assets 在包外、要用 include-data-dir”的说法已过时，改写为“字体已随程序打包，图标仍走几何绘制” |
| `THIRD-PARTY.md` | 中英文两份声明都补上字体文件路径、License 全文位置与“原样打包未修改” |
| `AGENTS.md` | 结构图里 `assets # 静态资源` 从仓库根挪到 `src/another_arrow_rt265/` 下 |
| `tests/test_resources.py` | **新增** 14 项：定位（含“素材必须在包内”、程序目录兜底、找不到返回 `None`）、第三方声明与 `pyproject` 的一致性、`ui._font()` 用的确实是内置字体、中文不是方块、字体缺失时能兜底、字号缓存与行高 |
| `.preview/font_check.py` | **新增**：并排渲染“内置 / 系统 / pygame 默认”三种字体，肉眼对比 |
| `.preview/probe_resources.py` | **新增**：把资源定位搬进 Nuitka 产物里跑一遍的探针（见“验证”） |

## 关键设计

### 为什么必须放进包内

一开始按“素材放仓库根 `assets/` 在包外”的旧约定，在 `[tool.nuitka]` 里写了
`include-data-dir = ["assets=assets"]`，`uv run python -m nuitka --project` 直接失败：

```text
FATAL: Error, the expected data files from project configuration do not match the included data files.
Extra data files:
assets\fonts\LICENSE
assets\fonts\NotoSansCJKsc-VF.otf
```

Nuitka 的 `--project` 会先让 uv 构建一次 wheel、读 `RECORD` 里**非 Python 文件**作为“项目预期数据文件”，
再要求命令行声明的数据文件与之**完全相等**（`checkProjectExpectedDataFiles()`，多一个少一个都 `sysexit`）。
而 `uv_build` 的 wheel 只收三层内容：`module-root`（`src/<包>/`）下的文件、`.data` 目录、`.dist-info` ——
**仓库根的 `assets/` 无论怎么配都进不了 wheel**（试过 `source-include = ["assets/**"]`：它只影响 sdist，
wheel 里依旧没有）。于是“包外素材 + `--project`”这条路根本不成立。

把素材放进包内之后，一切自洽：wheel 自带字体（`uv build` 出来即可用），
`--project` 自动加上的 `--include-package-data=another_arrow_rt265` 会把它们按原路径搬进产物，
与 `resources.py` 的相对位置不变，预期数据文件与实际数据文件天然相等。

### 字体定位：包目录优先，其余是兜底

`resources.asset_path("fonts", "NotoSansCJKsc-VF.otf")` 依次尝试：

| 顺序 | 候选目录 | 覆盖场景 |
| --- | --- | --- |
| 1 | `PACKAGE_DIRECTORY`（`Path(__file__).parent`） | 源码运行 / wheel 安装 / Nuitka 产物（实测产物里 `__file__` = `<dist>/another_arrow_rt265/...`） |
| 2 | `executable_directory()`（`sys.executable` 所在目录） | 手工把 `assets/` 丢在 exe 旁边（standalone 的 dist 目录、onefile 的 exe 目录） |
| 3 | `src`、仓库根 | 兼容历史上把素材放在仓库根的做法 |
| 4 | `Path.cwd()` | 从别处启动、但 cwd 恰好是仓库根 |

第一条就命中 99% 的情况；优先级靠前的目录先命中，顺序由 `_search_roots()` 去重后固定下来。

### 字体兜底链

`ui._font(size)` 的顺序是**内置字体 → 系统 CJK 字体（`_FONT_CANDIDATES`）→ pygame 内置字体**：
字体文件万一没被打进去，界面依旧能看（最差是方块字），不会直接崩。
`tests/test_resources.py` 用 `monkeypatch` 把 `resources.font_path` 打成 `None` 来钉住这条兜底链。

### 许可合规

字体是第三方素材，因此按 `AGENTS.md` 的要求做了三件事：

1. `THIRD-PARTY.md` 中英文两份都登记了组件名、版本（2.004）、来源、License 与版权声明，
   并写明字体**原样分发、未修改**（OFL 要求派生作品不得使用保留字体名，我们没做派生）；
2. SIL OFL 1.1 全文随字体一起分发（`assets/fonts/LICENSE`），因此它也必须留在包内、
   跟着 wheel 与产物走；
3. `tests/test_resources.py` 里有两项测试把“字体文件确实是声明里那个”和“声明里确实提到它”钉住，
   避免以后换了字体却忘了改声明。

## 验证

```powershell
uv run pytest -q                     # 新增 tests/test_resources.py；另有 3 项既有失败见下
uv run ruff check . ; uv run ruff format --check . ; uv run ty check
uv run python .preview/font_check.py # 三种字体并排渲染，肉眼确认中文不是方块
uv run python -m nuitka --project    # 打包（现在能过 --project 的数据文件校验）
& .preview/capture_dist.ps1          # 产物冒烟：窗口标题 Another Arrow、关窗退出码 0
```

**打包产物的硬证据**（`.preview/probe_resources.py` 用同样的 `resources` / `ui` 代码编译成
standalone 产物后运行）：

```text
PACKAGE_DIRECTORY = ...\probe_resources.dist\another_arrow_rt265
font_path()  = ...\probe_resources.dist\another_arrow_rt265\assets\fonts\NotoSansCJKsc-VF.otf
exists = True
bundled render: (250, 35) ink = 8750     ← 中文有真实字形
pygame default: (78, 18) ink = 1404      ← 方块字，用来对照
```

`uv build --wheel` 的产物里也能看到 `another_arrow_rt265/assets/fonts/{LICENSE,NotoSansCJKsc-VF.otf}`，
也就是说 pip 安装的形态同样自带字体。

## 后续

- Priority 第 13 条的**图标**部分未动：图标仍是 `icons.py` 里的几何绘制，`THIRD-PARTY.md`
  因此只有字体这一项第三方素材。
- `tests/test_ui.py` 那 3 项失败已在 `change-log-14-about-page-tests.md` 里按**新意图**处理完
  （“关于”界面只放制作信息是预期行为，改的是测试）。
