"""pytest 全局配置。

测试只需要离屏渲染，不依赖真实的显示器与声卡，因此统一把 SDL 切到 dummy
驱动。环境变量必须在导入 pygame 之前设置，所以放在 conftest 里。
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
