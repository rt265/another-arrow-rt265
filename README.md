# Another Arrow

本项目为福州大学 2026 年软件工程课程的项目，配合 Agent 开发小游戏。

> [!note]
>
>  本项目仅为学习研究使用，不涉及任何商业用途，也不建议在生产环境中使用。

## Show Time

|主界面|游戏界面|成功界面|失败界面|辅助线功能|
|-|-|-|-|-|
|![](/docs/player/assets/main.png)| ![](/docs/player/assets/gameplay.png) | ![](/docs/player/assets/win.png) | ![](/docs/player/assets/fail.png) | ![](/docs/player/assets/auxiliary.png) |


## Installation

下载 [Releases](https://github.com/rt265/another-arrow-rt265/releases) 中的 `another-arrow-<version tag>.zip`，解压并运行 `another-arrow-rt265.exe`

当前仅提供 Windows x86_64 构建。

## Quick Start

```bash
git clone https://github.com/rt265/another-arrow-rt265.git
cd another-arrow-rt265
uv sync
uv run another-arrow-rt265
```

你的设备将自动打开游戏窗口。

## Documentation

- 对于玩家：[Player Guide](/docs/player/player-guide.md)
- 对于开发者：[Development Guide](/docs/dev/development-guide.md)
- 对于 Agent：[Basic Info for Agent](/docs/agents/basic-info.md)

```bash
uv run pytest -q
```

Lint：

```bash
ruff check .
```

Format:

```bash
ruff format --check .
```

Type Check:

```bash
ty check
```

## Build

使用 [Nuitka](https://nuitka.net/) 将项目打包为独立可执行目录。

```bash
uv run python -m nuitka --project
```

`--project` 会读取 `pyproject.toml`，自动识别包名、`[project.scripts]` 里的入口函数，
以及 `[tool.nuitka]` 中的打包选项，因此无需在命令行重复写包名与入口。

产物位置：

```text
build/nuitka/another-arrow-rt265.dist/
├─ another-arrow-rt265.exe   # 双击即可运行
├─ python313.dll             # 内嵌的 Python 运行时
└─ pygame/                   # pygame 扩展模块与 SDL2 等 DLL
```

首次打包需要 C 编译器，之后再打包会复用编译缓存。
调试打包结果时可以用 `SDL_VIDEODRIVER=dummy` 在无显示器环境下跑冒烟测试。

## Tech Stack

- Python 3.13
- Pygame-ce
- UV
- Ruff
- ty
- Nuitka

## Credits & License

本项目遵循 MIT Lincese 协议，详见 [LICENSE](LICENSE) 文件。

本项目使用了来自第三方的资源，详见 [THIRD-PARTY](THIRD-PARTY.md) 文件。

Copyright (c) 2026 rt265
