"""一箭又一箭（Another Arrow）：点击式箭头解谜小游戏。"""

from __future__ import annotations

__all__ = ["main"]


def main() -> None:
    """启动游戏窗口（延迟导入，避免仅导入包时就加载 pygame）。"""
    from another_arrow_rt265.main import main as run

    run()
