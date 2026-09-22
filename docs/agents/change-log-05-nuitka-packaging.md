# 变更记录 05：跑通 Nuitka 打包流程

本轮不对应 `basic-info.md` 的 Priority 事项，是用户新增的**交付/构建基础设施**任务：把游戏打成
可以脱离 Python 环境运行的可执行程序。目标是“先跑通”，因此只做**能验证的最短路径**，不做体积
激进裁剪，也不改动任何游戏逻辑。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `pyproject.toml` | `[dependency-groups].dev` 新增 `uv-build>=0.12.13,<0.13.0`；**新增** `[tool.nuitka]` 一节，集中存放打包选项 |
| `README.md` | 新增 `## Build` 一节：打包命令、`--project` 的作用、产物结构、编译器与缓存说明 |
| `.preview/capture_dist.ps1` | **新增**：启动打包产物 → 校验窗口创建 → 截图 → 关窗并校验退出码（本地验证脚本，`.preview/` 已 gitignore） |

游戏源码（`src/another_arrow_rt265/**`）**一行未改**，也**没有新增测试**：打包属于构建配置，
验收方式是“产物能跑起来”，而不是单元测试。

## 关键设计

### 用 `--project` 而不是手写一长串参数

Nuitka 4.2 支持 `--project`：从当前目录的 `pyproject.toml` 里推断构建配置。它会调用 `uv_build`
后端生成一次 wheel，再解析 `METADATA` / `entry_points.txt` / `RECORD`，得到：

```text
--project-name=another-arrow-rt265
--main-entry-point=another-arrow-rt265=another_arrow_rt265:main
--output-filename=another-arrow-rt265
--output-folder-name=another-arrow-rt265
--include-package=another_arrow_rt265
--include-package-data=another_arrow_rt265
```

再叠加 `[tool.nuitka]` 里的选项。这样带来的直接好处是**单一事实来源**：包名、GUI 入口函数
都只在 `pyproject.toml` 里写一次，以后重命名包或改入口不会漏改打包命令。反过来说，命令行的
全部内容就只有一句：

```bash
uv run python -m nuitka --project
```

### `uv-build` 是 `--project` 的硬依赖

`nuitka/options/UvBuild.py` 内部会执行 `nuitka/tools/general/extract_uv_config/__main__.py`，
该脚本第一步就是 `import uv_build`，缺失时直接 `sys.exit`。而这个模块**不是** `uv` 命令行自带的
——`uv` 可执行文件在 PATH 里也没用。因此必须把它装进环境，本轮选择放进 `dev` 依赖组，版本范围
与 `[build-system].requires` 保持一致（`>=0.12.13,<0.13.0`），避免两处解析出不同版本。

### `[tool.nuitka]` 里放了什么、为什么

| 选项 | 原因 |
| --- | --- |
| `standalone = true` | 生成独立目录，目标机器不需要装 Python。相比 `--onefile` 启动更快（不用每次解压到临时目录），也方便直接看产物内容 |
| `output-dir = "build/nuitka"` | 产物统一落在 `build/` 下，该目录早已在 `.gitignore` 中，不污染仓库根目录 |
| `assume-yes-for-downloads = true` | 首次打包 Nuitka 需要下载 `depends.exe`（用于检测 DLL 依赖），CI 或一键构建时不能卡在交互确认上 |
| `windows-console-mode = "disable"` | 游戏是 GUI 程序，否则双击运行会额外弹出一个黑色控制台窗口 |
| `nofollow-import-to` | `pygame` 的 `packager_imports()` 函数体里写了 `import numpy` / `import OpenGL.GL`（该函数永不执行，但静态分析会跟进去），项目也没用 `pytest` / `ruff` / `ty`，显式排除可以消掉一批“找不到模块”的告警 |

试过再删掉的一项：`enable-plugin = "anti-bloat"`。Nuitka 4.2 会提示
`Plugin is defined as always enabled, no need to enable it.`——该体积优化插件已默认启用，
写出来只会多一条告警，于是删掉，只在配置里留了一行注释说明。

### 为什么不做激进体积裁剪

首次产物 71 个文件、31.71 MB，其中明显“多余”的有 `libcrypto-3-x64.dll`（7.62 MB）、
`_hashlib.pyd`、`_socket.pyd`、`select.pyd` 等——它们来自 Nuitka 对标准库的隐式包含，
与游戏逻辑无关。本轮**没有**用 `nofollow-import-to` 排除它们：这些模块是否会在某个动态路径上
被间接用到（`random` / `subprocess` / `uuid` 等）很难穷举，而冒烟测试只能覆盖“点箭头 + 关窗”
这一条主路径，一旦漏掉就是运行时才崩。本轮目标是先跑通，裁剪留作后续事项（见文末）。

## 验证

打包命令：

```bash
uv run python -m nuitka --project
```

构建环境与结果：

```text
Nuitka 4.2.1 / Python 3.13.15 / Windows 11 x86_64
C 编译器：cl 14.5（MSVC，自动探测成功，不需要 MinGW）
Backend C linking with 39 files
Successfully created 'build\nuitka\another-arrow-rt265.dist\another-arrow-rt265.exe'
```

产物结构（关键部分）：

```text
build/nuitka/another-arrow-rt265.dist/
├─ another-arrow-rt265.exe      6.91 MB   ← 冻结的主程序（含全部纯 Python 字节码）
├─ python313.dll                5.87 MB   ← 内嵌 Python 运行时
├─ vcruntime140*.dll
└─ pygame/
   ├─ base.pyd / font.pyd / draw.pyd / ...  ← 全部扩展模块
   ├─ SDL2.dll / SDL2_image.dll / SDL2_ttf.dll / SDL2_mixer.dll
   └─ freesansbold.ttf / pygame_icon.bmp    ← Nuitka 自动补的 pygame 包数据
```

DLL 依赖由 Nuitka 的 `dll-files` 插件接管（日志：`Found 16 files DLLs from pygame installation`），
SDL2 系列 DLL 全部就地复制到 `pygame/` 下，无需手工 `--include-dlls`。

运行验证用 `.preview/capture_dist.ps1` 自动完成，结果：

```text
Screenshot: title='Another Arrow' rect=736 x 759
Saved: .preview\dist_window.png
OK: 关窗正常退出，码 = 0
```

即：进程能正常创建窗口并跑主循环（不是启动即崩），关窗后走 `pygame.QUIT` 正常退出（码 0）。
截图人工确认了两件在打包后**最容易出问题**的事：

1. `pygame.font.match_font()` 仍能找到系统中文字体——HUD 的“失误”“重新开始”是正常汉字而不是方块；
2. 箭头、棋盘、圆角等绘制与源码运行时一致，SDL2 渲染链路完整。

回归（确认改 `pyproject.toml` 没有破坏既有流程）：

```bash
uv run pytest -q              # 65 passed
uv run ruff check .           # All checks passed
uv run ruff format --check .  # 17 files already formatted
uv run ty check               # All checks passed
```

## 已知限制与后续事项

- **`assets/` 不会自动进包**。`--project` 只会加 `--include-package-data=another_arrow_rt265`，
  而仓库的 `assets/` 在项目根目录、不在包内（目前是空目录，还没有影响）。一旦开始放图片/音效，
  需要补 `[tool.nuitka]` 的 `include-data-dir = ["assets=assets"]`，并让代码用
  “exe 同级目录”而非当前工作目录去定位资源。
- **体积**：31.71 MB 里约 1/4 是与游戏无关的标准库隐式依赖（`libcrypto-3-x64.dll` 等）。
  后续可以逐个 `nofollow-import-to` 试删，每删一个都要重跑一次产物冒烟。
- **单文件分发**：如有需要可尝试在命令后追加 `--onefile` 生成单个 exe，但启动时会解压到临时
  目录、更慢，且**本轮未验证**。
- `--project` 每次都会调 `uv_build` 构建一次 wheel 来提取配置，比纯命令行参数略慢，属可接受开销。
- 首次打包的中间产物在 `build/nuitka/another-arrow-rt265.build/`，删除后下次打包会重新编译
  （`clcache` 命中时会快很多）。
