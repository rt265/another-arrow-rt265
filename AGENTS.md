# Repo Guide

本项目是一个 Python 小游戏项目，预期复现微信小游戏“一箭又一箭”的核心玩法

## Project Structure

项目使用 Pygame-ce 作为游戏库，UV 作为管理器，Ruff 作为静态检查器，ty 作为类型检查器，Nuitka 作为二进制程序打包器。

```
.
├─docs # 相关文档
├─src
│  └─another_arrow_rt265 # 源代码
│     └─assets # 静态资源
├─tests # 测试
└─pyproject.toml 项目信息与依赖
```

## Log notice

Agent 需要将本轮对话做出的改动汇总为 Markdown 文档，存储在 `docs/agents` 目录下，供后继 Agent 查阅。

后继 Agent 首先阅读 `docs/agents` 的 `basic-info.md`，获取当前工作的总体状态，其次再阅读分文档。

## UI Copy Notice

**界面不写多余的说明文字**：

- 除非用户明确要求，任何界面都不要加解释性文案——包括说明卡片、提示行、
  页脚小字这类“告诉玩家这个界面是干什么的 / 有什么后果”的文字。
  菜单页只放控件（按钮、开关）与必要读数（版本、关卡数这类事实性信息）。
- **用户删除文案是有意为之**：不要凭“变更记录 / 测试 / 记忆里写过”就把它加回去。
  发现“文档说该有、代码里没有”时，先当成产品决定，改文档与测试，而不是改代码。
- 对应的产品规则测试：`tests/test_ui.py::test_start_screen_keeps_no_rule_text`、
  `test_settings_page_keeps_no_explanatory_text`。

## Copyright Notice

- 不得使用参考游戏的任何资源
- 所有第三方素材合规性由开发者处理，Agent 只需要调用资源
