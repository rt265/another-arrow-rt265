# Another Arrow

“一箭又一箭”（Another Arrow）是一款点击式箭头解谜游戏，玩家需要点击当前可以飞出棋盘的箭头，消除完毕即通关。

> [!note]
>
> 本项目为福州大学 2026 年软件工程课程的项目，配合 Agent 开发小游戏。
>
>  本项目仅为学习研究使用，不涉及任何商业用途，也不建议在生产环境中使用。

## Show Time

|主界面|游戏界面|成功界面|失败界面|辅助线功能|
|-|-|-|-|-|
|![主界面](/docs/player/assets/main.png)| ![游戏界面](/docs/player/assets/gameplay.png) | ![通关](/docs/player/assets/win.png) | ![失败](/docs/player/assets/fail.png) | ![辅助线](/docs/player/assets/auxiliary.png) |

在此获取实机录像：[Record](/docs/player/assets/record.mp4)

## Installation

从 [Releases](https://github.com/rt265/another-arrow-rt265/releases) 下载构建产物 `another-arrow-<tag>-<os>-<arch>.zip`：

- Windows 选择 `-windows-x64`，
- Linux 选择 `-linux-x64`。

解压后运行目录下的可执行文件（Linux 首次运行前可能需要 `chmod +x`）。

在 [Actions](https://github.com/rt265/another-arrow-rt265/actions) 的 `Build and Release` 下载实时构建版本，建议仅使用对应 `Test` 通过的版本。

或者从源码运行/打包。参见 [Development Guide](/docs/dev/development-guide.md)。

## Documentation

- 对于玩家：[Player Guide](/docs/player/player-guide.md)
- 对于开发者：[Development Guide](/docs/dev/development-guide.md)
- 对于 Agent：[Basic Info for Agent](/docs/agents/basic-info.md)

## Feedback

有 Bug？想要新功能？请提 [Issue](https://github.com/rt265/another-arrow-rt265/issues)！

## Dependencies

- Python 3.13
- Pygame-ce
- UV
- Ruff
- ty
- Nuitka
- Pytest

## Credits & License

本项目遵循 MIT Lincese 协议，详见 [LICENSE](LICENSE) 文件。

本项目使用了来自第三方的资源，详见 [THIRD-PARTY](THIRD-PARTY.md) 文件。

Copyright (c) 2026 rt265
