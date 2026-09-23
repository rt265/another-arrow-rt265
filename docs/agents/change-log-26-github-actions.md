# 变更记录 26：重写 GitHub Actions 工作流

本轮是**构建基础设施**任务（不对应 `basic-info.md` 的 Priority 事项）：把上一轮提交的
`.github/workflows/` 推倒重写。游戏源码、测试、`pyproject.toml` **一行未改**。

## 1. 为什么要重写

上一轮那次提交的 CI 是半成品，四个硬伤：

| 问题 | 位置 | 后果 |
| --- | --- | --- |
| 文件被截断，末尾只剩一个孤立的 `release:` 键 | `build.yml` 第 71 行 | YAML 不合法，整个工作流直接起不来 |
| `uv run python -m nuitka -project`（少一个连字符） | 两个 build job | Nuitka 4.2 只认 `--project`，会当成未知选项 |
| `actions/checkout` 写成 `action/checkout`（缺 s） | `test.yml` | 无法解析该 action |
| 所有 checkout 都写死 `ref: main` | 两个工作流 | 在分支 / PR 上构建的其实是 main 的代码，构建结果与被测提交不一致 |

另外两个工作流都**没有**：PR 触发、并发取消、依赖缓存、产物上传、打包产物的冒烟验证，
`release` 任务只写了标题没有内容（等于发布功能不存在）。

## 2. 关于 Nuitka-Action 的结论（本轮用户提问）

用户提议用官方的 [`Nuitka/Nuitka-Action`](https://github.com/Nuitka/Nuitka-Action)。结论是
**技术上能跑，但与本项目的打包方式存在硬冲突，因此不采用**，只从它身上抄了两条做法。

先澄清它的能力（读 `action.yml` 得到，非猜测）：

- 它是 **composite action**（`runs: using: composite`），不是 Docker action，所以
  `windows-latest` / `ubuntu-latest` 都能用；
- 输入项几乎一一对应 Nuitka 选项，**并且有一个 `project` 输入**（注释就写着
  “Compile the project in the current directory by extracting configuration from it”）；
- 自带 `NUITKA_CACHE_DIR` + `actions/cache` 缓存，Linux 上还会装 ccache。

不采用的原因：

1. **`--project` 与它的必填输入互斥（硬冲突）。** `script-name` 是它的唯一必填项，最终以
   `--script-name`（`--main` 的别名）传给 Nuitka，而 Nuitka 自己明确规定二者不能共存。
   本机实测（`uv` 环境里钉的 Nuitka 4.2.1）：

   ```text
   $ uv run python -m nuitka --project --script-name=src/another_arrow_rt265/main.py
   FATAL: Error, with '--project' do not provide '--main', '--main-entry-point', or a positional main program.
          The entry points need to come from the project configuration.
   ```

   为排除“手工构造的参数不算数”的疑虑，又用**该 action 的真实通道**复现了一次
   （`NUITKA_WORKFLOW_INPUTS` JSON + `--github-workflow-options`，即 action.yml 里
   `Build with Nuitka` 那一步干的事），得到同一条报错。
   要用这个 action，就必须放弃 `--project`，把包名、入口、`include-package-data`、
   `output-folder-name`、`nofollow-import-to`、`windows-console-mode`、`standalone`
   全部搬回 workflow YAML —— 正是 `change-log-05` 特意避免的重复（pyproject 单一事实来源）。

2. **Nuitka 的来源不同。** 它用 pip 从 git 装 Nuitka，默认 `nuitka-version: main`（上游开发分支），
   **不读 `uv.lock`**；本项目本地与 CI 都是锁文件钉住的 4.2.1。编译器版本在本地与 CI 之间漂移，
   打包问题会变得难以复现。

3. **一个 job 里出现两套依赖管理。** 它把依赖装进 runner 的系统 Python
   （`pip install -r <action>/requirements.txt` 再装 git 版 nuitka），本项目依赖全由 uv 管；
   用 action 就得额外 `pip install pygame-ce uv-build`，还要保证 Nuitka 跑在同一解释器里。

从它身上抄走的两条（新工作流里已有）：

- **`NUITKA_CACHE_DIR` + `actions/cache`**：Nuitka 的编译缓存目录可以用这个环境变量指定
  （`nuitka/utils/AppDirs.py` 读它），缓存起来能跨运行省掉重复的 C 编译；
- **README 的 "Common traps"**：Linux 产物里的 `.libs` 是隐藏目录，`*` 通配或默认的
  `upload-artifact` 都会把它漏掉。我们的对策是**在产物目录里用 `zip -r .` 打包**，
  并且**上传的是打包好的 zip 而不是 dist 目录**，于是一并不需要 `include-hidden-files`。

## 3. 新工作流

`.github/workflows/test.yml`

| 项 | 值 |
| --- | --- |
| 触发 | `push`（所有分支）、`pull_request`、`workflow_dispatch` |
| 并发 | `tests-${{ github.ref }}`，新提交取消旧运行 |
| 权限 | `contents: read` |
| 任务 | `test`（`pytest -q` → `ruff check .` → `ruff format --check .` → `ty check`），`timeout-minutes: 10` |

四条命令与 `docs/dev/development-guide.md` 里本地跑的一致；`uv sync --locked` 保证 CI 用的就是
`uv.lock` 钉住的版本（锁文件过期会直接失败，而不是悄悄装一套新依赖）。

`.github/workflows/build.yml`

| 项 | 值 |
| --- | --- |
| 触发 | `push` 到 `main`、`push` `v*` 标签、`workflow_dispatch` |
| 任务 | `build`（矩阵 `windows-latest` / `ubuntu-latest`，`timeout-minutes: 25`）+ `release`（仅 `v*` 标签） |
| 打包 | `uv run python -m nuitka --project`，与本地完全同一条命令 |
| 冒烟 | Windows：`Start-Process` + `WaitForExit(8000)`；Linux：`timeout 8`，**要求退出码恰为 124**（即“活满 8 秒被超时杀掉”，提前退出即失败） |
| 附件 | 统一为 `another-arrow-<version tag>-<os>-<arch>.zip`（`-windows-x64` / `-linux-x64`）；非标签构建把版本位换成短提交号 |
| 发布 | `gh release create`（runner 自带 CLI，不引入第三方 action），带 `--generate-notes --verify-tag`；发布已存在时改为 `gh release upload --clobber`，重跑幂等 |

几个刻意的选择：

- **不引入第三方 action**：除了 actions/* 官方那几个与 `astral-sh/setup-uv`，发布用 GitHub 自带的
  `gh` CLI，少一个供应链依赖。
- **build 里不跑 pytest**：`test.yml` 在同一个标签推送上也跑，重复跑只是浪费；发布前请确认它是绿的
  （或给 main 配分支保护）。
- **SDLC 一致性**：`patchelf`（Linux standalone 要靠它改 rpath）与 `zip` 在 Linux 上显式安装，
  `assume-yes-for-downloads` 仍保留在 `pyproject.toml` 里作为兜底。
- **`--project` 一以贯之**：包名、入口、产物名与打包策略仍只在 `pyproject.toml` 声明一次，CI 不重复。

## 4. 验证

本地能验证的都验证了，用一个一次性脚本 `.preview/check_workflow_snippets.py`
（`.preview/` 已 gitignore）**把工作流里真正会跑的脚本片段抽出来执行**，而不是另抄一份：

```text
1) 逐片段语法检查      bash 片段过 `bash -n`，pwsh 片段过 PowerShell AST 解析 —— 14 段全过
2) 附件命名片段        refs/tags/v3.1  → file=another-arrow-v3.1-windows-x64.zip
                      refs/heads/main → file=another-arrow-abcdef1-linux-x64.zip
3) Windows 冒烟片段    对着本机真实产物跑：进程存活 8 秒后被脚本结束（[ok]）
4) 冒烟负例           产物目录不存在时按预期抛异常退出（[ok]）
5) Windows 打包片段    真的打一个 zip：82 项、含 another-arrow-rt265.exe、没有多一层目录（[ok]）
```

（脚本顺带发现两件本机环境的事：WSL bash 不继承 Windows 侧环境变量，所以片段里的环境变量要在
脚本开头以 `export` 注入；本机 pwsh 输出是 GBK，断言只能看 ASCII 部分。两处都只影响这个校验脚本。）

工作流 YAML 本身另用 `PyYAML` 解析并断言结构（触发条件、矩阵、步骤名单、
`Build with Nuitka` 的命令就是 `uv run python -m nuitka --project`、release 的 `if`/`needs`/权限）。

外部依赖的版本都核对过是真实存在的 tag：`actions/checkout@v7.0.1`、`actions/setup-python@v7.0.0`、
`astral-sh/setup-uv@v10.2.0`、`actions/upload-artifact@v7.0.1`、`actions/download-artifact@v8.0.1`、
`actions/cache@v5.0.5`（后一个出自 Nuitka-Action 的 action.yml 里对 v5.0.5 的引用）。

**未验证（本机条件所限）**：Linux 构建与 Linux 冒烟、以及 `release` 任务本身，都需要真实
GitHub runner 才能跑；标签命名与 `config.VERSION` 的一致性也仍靠人工（`tests/test_config.py`
钉住 `VERSION` 与 `pyproject.toml` 一致，但不管标签名）。

## 5. 同步改动

- `README.md` 的 Installation 一节：把两个平台的附件写成一个统一模式 `another-arrow-<version tag>-<os>-<arch>.zip`
  （原话是“当前仅提供 Windows x86_64 构建”，现在会同时产出两个平台的附件）。
- `docs/dev/development-guide.md` 的“打包与发布”：新增 CI 一节（触发方式、附件命名、冒烟口径）。
- `docs/agents/basic-info.md`：补一条 CI/发布的现状，便于后继 Agent 直接读到。

## 6. 追问：附件命名统一

用户随后要求把命名统一为 `another-arrow-<version tag>-<os>-<arch>.zip`。原先 Windows 是
`another-arrow-<tag>.zip`（不带平台名，只因为 README 当初只提供 Windows 构建），Linux 才带 `-linux-x64`
——两边不一致，多平台后也看不出下载的是哪一份。现在两个平台都带 `-<os>-<arch>`：

| 场景 | 附件名 |
| --- | --- |
| Windows，标签 `v3.1` | `another-arrow-v3.1-windows-x64.zip` |
| Linux，标签 `v3.1` | `another-arrow-v3.1-linux-x64.zip` |
| 非标签构建（commit `abcdef1`） | `another-arrow-abcdef1-<os>-<arch>.zip` |

实现上只动了**一个来源**：矩阵里的 `platform` / `asset_suffix` 两个字段换成 `os_name` + `arch`，
job 名、`Resolve asset name` 的 `echo`、`upload-artifact` 的 name 三处都从这两个字段拼出来，
不再存在“哪一份要带后缀”的分支。`README.md`、`docs/dev/development-guide.md`、
`docs/agents/basic-info.md` 与本文件的描述均已同步。

重新跑了一遍本地校验（`.preview/check_workflows.py` + `.preview/check_workflow_snippets.py`），
除命名断言改为新格式外其余用例不变，全部通过：

```text
2) 附件命名片段        refs/tags/v3.1  → file=another-arrow-v3.1-windows-x64.zip
                      refs/heads/main → file=another-arrow-abcdef1-linux-x64.zip
3) Windows 冒烟片段    产物启动后存活 8 秒，被脚本主动结束（[ok]）
5) Windows 打包片段    payload.zip 共 82 项，含 exe，且没有多余目录层（[ok]）
```

（未变的一个事实：非标签构建的版本位仍是短提交号而不是 `pyproject.toml` 的 `version`——
CI 不解析 pyproject，短提交号也更便于定位是哪次构建。）
