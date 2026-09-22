# Repo Guide

本项目是一个 Python 小游戏项目，预期复现微信小游戏“一箭又一箭”的核心玩法

## Project Structure

项目使用 Pygame-ce 作为游戏库，UV 作为管理器，Ruff 作为静态检查器，ty 作为类型检查器，Nuitka 作为二进制程序打包器。

```
.
├─docs # 相关文档
├─src
│  └─another_arrow_rt265 # 源代码
│     └─assets # 静态资源（随程序打包的字体等）
├─tests # 测试
└─pyproject.toml 项目信息与依赖
```

## Log notice

Agent 需要将本轮对话做出的改动汇总为 Markdown 文档，存储在 `docs/agents` 目录下，供后继 Agent 查阅。

## Copyright Notice

- 不得使用参考游戏的任何资源
- 如果（需要）引入第三方来源的素材，请在[THIRD-PARTY](THIRD-PARTY.md)中说明
