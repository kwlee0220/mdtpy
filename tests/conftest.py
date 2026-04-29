"""
mdtpy 테스트 공용 설정 / fixture.

instance.py가 모듈-수준 전역(`mdt_inst_url`, `mdt_manager`)을 갖고 있어
테스트 간 누수가 일어나지 않도록 매 테스트마다 초기화한다.
"""
from __future__ import annotations

import pytest

import mdtpy.instance as instance_mod


@pytest.fixture(autouse=True)
def _reset_module_globals():
    """각 테스트 종료 후 instance 모듈의 전역 상태를 원복한다."""
    saved_url = instance_mod.mdt_inst_url
    saved_manager = instance_mod.mdt_manager
    try:
        yield
    finally:
        instance_mod.mdt_inst_url = saved_url
        instance_mod.mdt_manager = saved_manager
