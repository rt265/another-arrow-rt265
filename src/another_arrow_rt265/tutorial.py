"""第一关的“边玩边学”教程。

教程不另开画面，而是直接叠在第 1 关的棋盘上，把三个动作串成一条引导链：

1. 点击前方畅通的箭头——学会“飞出棋盘”；
2. 点击被挡住的箭头——学会“碰撞与失误”（这一次是演示，不扣真实失误）；
3. 清空棋盘——学会过关条件。

本模块只有状态机：不读棋盘内容、不做任何绘制。:class:`Tutorial` 记录“玩家做过
哪些动作”，``ui`` 读 :attr:`Tutorial.hint` 与 :meth:`Tutorial.suggested_arrow`
决定画什么（提示条文案 + 高亮哪支箭头），``session`` 负责在点击与每帧刷新时
把进度推给它，并按 :attr:`Tutorial.collision_demo_pending` 决定这一次撞墙
要不要真的扣失误。因此教程进度可以在没有窗口的环境下完整测试。

进度是**单调**的：三步各记一个“已完成”标记，``step`` 只取第一个还没完成的，
玩家怎么乱点都不会把教程顶回去。唯一的例外是“碰撞”那一步：它必须由教程点名
（``step`` 正好是它）才算完成——因为对应的那次撞墙是教程给的演示，不扣失误，
自然不能由玩家自己提前“用掉”。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Final

from another_arrow_rt265.board import Arrow, Board, ClickResult


class TutorialStep(Enum):
    """教程的三个步骤。"""

    CLEAR_FREE = "clear_free"
    """点击一支前方畅通的箭头。"""

    BLOCKED = "blocked"
    """点击一支被挡住的箭头，体验碰撞与失误（教程会先声明这次不扣失误）。"""

    CLEAR_BOARD = "clear_board"
    """清空棋盘上的全部箭头，完成本关。"""


# 步骤顺序即引导顺序；``Tutorial.step`` 取其中第一个还没完成的。
_STEPS: Final[tuple[TutorialStep, ...]] = (
    TutorialStep.CLEAR_FREE,
    TutorialStep.BLOCKED,
    TutorialStep.CLEAR_BOARD,
)

_TEXTS: Final[dict[TutorialStep, str]] = {
    TutorialStep.CLEAR_FREE: "点击高亮的箭头：前方没有阻挡，它会飞出棋盘",
    TutorialStep.BLOCKED: "再点这支被挡住的箭头：飞不出去，这次演示不扣失误",
    TutorialStep.CLEAR_BOARD: "继续点击清空棋盘即可过关；再撞墙就要扣失误了",
}


@dataclass(frozen=True, slots=True)
class TutorialHint:
    """当前步骤的提示：进度读数 + 一句话文案。"""

    step: TutorialStep
    """当前正在引导的步骤。"""

    number: int
    """第几步（从 1 开始）。"""

    total: int
    """教程共有几步。"""

    text: str
    """提示条上的文案。"""

    @property
    def progress(self) -> str:
        """提示条左侧的进度读数，如 ``1 / 3``。"""
        return f"{self.number} / {self.total}"


class Tutorial:
    """第一关的教程进度：只记录玩家完成过哪些动作。"""

    def __init__(self) -> None:
        self._done: set[TutorialStep] = set()

    def note_click(self, result: ClickResult) -> None:
        """记录一次棋盘点击的结果。

        只认“飞出棋盘”与“被挡住”两种结果：点在空格子上（``MISS``）不算学习进度。

        碰撞那一步多一个条件：只有教程正在引导它（``step`` 就是 ``BLOCKED``）时才算数。
        因为对应的那次撞墙是教程给的**演示**（:attr:`collision_demo_pending` 为真时
        不扣失误），不能让玩家提前自己“用掉”这个豁免。
        """
        if result is ClickResult.CLEARED:
            self._done.add(TutorialStep.CLEAR_FREE)
        elif result is ClickResult.BLOCKED and self.step is TutorialStep.BLOCKED:
            self._done.add(TutorialStep.BLOCKED)

    def sync(self, board: Board) -> None:
        """把板面状态并入进度：棋盘清空即完成最后一步。

        由 ``Session`` 在每次点击后与每帧刷新时调用，因此玩家无论点掉哪一支箭头
        都能被记上，不需要教程自己去监听棋盘。
        """
        if board.is_cleared:
            self._done.add(TutorialStep.CLEAR_BOARD)

    @property
    def step(self) -> TutorialStep | None:
        """当前要引导的步骤；三步都已完成时返回 ``None``。"""
        for step in _STEPS:
            if step not in self._done:
                return step
        return None

    @property
    def is_finished(self) -> bool:
        """三步是否都已完成。"""
        return self.step is None

    @property
    def collision_demo_pending(self) -> bool:
        """下一次撞墙是不是教程正在演示的那一次。

        为真时 ``Session`` 仍然播放碰撞反馈（晃动、火花、挡路提示环），但**不扣
        失误**：玩家还处在“看着教程学”的阶段，第一次撞墙应该只换来一条经验。
        这次点击同时也会完成碰撞那一步（见 :meth:`note_click`），因此豁免只送一次：
        演示结束后再撞墙，失误就按真实规则扣。
        """
        return self.step is TutorialStep.BLOCKED

    @property
    def hint(self) -> TutorialHint | None:
        """当前步骤的提示文案；教程已经结束时返回 ``None``。"""
        step = self.step
        if step is None:
            return None
        return TutorialHint(
            step=step,
            number=_STEPS.index(step) + 1,
            total=len(_STEPS),
            text=_TEXTS[step],
        )

    def suggested_arrow(self, board: Board) -> Arrow | None:
        """返回当前步骤希望玩家点击的箭头，没有合适的箭头时返回 ``None``。

        - 第一步挑一支前方畅通的箭头（必定存在：棋盘清空前总有可以飞出的箭头，
          否则本关就是死局）；
        - 第二步挑一支被挡住的箭头，用来演示碰撞；
        - 最后一步要求清空棋盘，不指定具体箭头。
        """
        step = self.step
        if step is TutorialStep.CLEAR_FREE:
            return _first(board, lambda arrow: board.is_path_clear(arrow))
        if step is TutorialStep.BLOCKED:
            return _first(board, lambda arrow: not board.is_path_clear(arrow))
        return None


def _first(board: Board, predicate: Callable[[Arrow], bool]) -> Arrow | None:
    """按行优先顺序返回棋盘上第一个满足 ``predicate`` 的箭头。"""
    return next((arrow for arrow in board if predicate(arrow)), None)
