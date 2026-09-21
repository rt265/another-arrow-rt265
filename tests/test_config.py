"""配置常量的测试：界面显示的项目信息不能与项目元数据各说各话。"""

from __future__ import annotations

import tomllib
from pathlib import Path

from another_arrow_rt265 import config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_version_matches_pyproject() -> None:
    """“关于”界面显示的版本号取自 ``config``，必须与 pyproject.toml 一致。"""
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))

    assert config.VERSION == pyproject["project"]["version"]
