"""pytest 全局配置。

测试只需要离屏渲染，不依赖真实的显示器与声卡，因此统一把 SDL 切到 dummy
驱动。环境变量必须在导入 pygame 之前设置，所以放在 conftest 里。
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from collections.abc import Iterator

import pytest

from another_arrow_rt265 import viewport


@pytest.fixture(autouse=True)
def _design_viewport() -> Iterator[None]:
    """让每个用例都从“窗口 = 设计尺寸（720×720）”开始。

    视口是模块级的当前状态（见 :mod:`another_arrow_rt265.viewport`）：某个用例把
    窗口改成别的尺寸之后必须还原，否则会污染后面的用例。于是在这里统一收尾——
    用例内部可以随便改，改完不用自己复位。
    """
    yield
    viewport.reset()
