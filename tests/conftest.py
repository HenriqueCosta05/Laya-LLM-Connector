from __future__ import annotations

from pathlib import Path

import pytest

from laya_connector.config import Config

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def make_cfg(tmp_path):
    def _make(**overrides) -> Config:
        return Config(root=tmp_path, **overrides)
    return _make


@pytest.fixture
def cfg(make_cfg) -> Config:
    return make_cfg()
