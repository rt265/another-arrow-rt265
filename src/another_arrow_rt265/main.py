"""可执行入口模块。"""

from __future__ import annotations

from another_arrow_rt265.game import Game


def main() -> None:
    """启动游戏窗口。"""
    Game().run()
