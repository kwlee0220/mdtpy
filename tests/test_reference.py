from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mdtpy.ref import (
    BaseElementReference,
    parse_reference_json_node,
    parse_reference_json_string,
    reference,
)


# --------------------------------------------------------------------------- #
# reference()  (참조 표현식 → BaseElementReference)
# --------------------------------------------------------------------------- #

class TestReference:
    @pytest.mark.parametrize("ref_string", [
        "inst1:Data:DataInfo.Equipment.EquipmentParameterValues[0].ParameterValue",
        "timeseries:inst1:TS#last=5",
        "param:inst1:Temperature",
        "oparg:inst1:Simulation:in:Speed",
    ])
    def test_wraps_in_base_reference(self, ref_string):
        # reference() 는 접두어와 무관하게 BaseElementReference 로 감싸고 ref_string 을 보존한다.
        # 실제 해석은 사용 시점에 전역 mdt_manager 를 통해 지연 수행된다.
        ref = reference(ref_string)
        assert isinstance(ref, BaseElementReference)
        assert ref.ref_string == ref_string


# --------------------------------------------------------------------------- #
# parse_reference_json_node / parse_reference_json_string  (@type JSON → ElementReference)
#   서버(mdt_manager.from_reference_json)에 위임한다.
# --------------------------------------------------------------------------- #

class TestParseJson:
    def test_raises_without_connected_manager(self):
        from mdtpy import instance as instance_mod
        instance_mod.mdt_manager = None  # conftest 가 테스트 후 원복한다.
        with pytest.raises(RuntimeError, match="mdt_manager is not initialized"):
            parse_reference_json_node({"@type": "mdt:ref:element",
                                       "submodelReference": {"instanceId": "inst1",
                                                             "submodelIdShort": "Data"},
                                       "elementPath": "A.B"})

    def test_node_delegates_to_manager(self):
        from mdtpy import instance as instance_mod
        fake_ref = object()
        mgr = MagicMock()
        mgr.from_reference_json.return_value = fake_ref
        instance_mod.mdt_manager = mgr  # conftest 가 테스트 후 원복한다.

        node = {"@type": "mdt:ref:element",
                "submodelReference": {"instanceId": "inst1", "submodelIdShort": "Data"},
                "elementPath": "A.B"}
        assert parse_reference_json_node(node) is fake_ref
        mgr.from_reference_json.assert_called_once()

    def test_string_delegates_to_manager(self):
        from mdtpy import instance as instance_mod
        fake_ref = object()
        mgr = MagicMock()
        mgr.from_reference_json.return_value = fake_ref
        instance_mod.mdt_manager = mgr  # conftest 가 테스트 후 원복한다.

        json_str = '{"@type": "mdt:ref:element", "submodelReference": ' \
                   '{"instanceId": "inst1", "submodelIdShort": "Data"}, "elementPath": "A.B"}'
        assert parse_reference_json_string(json_str) is fake_ref
        mgr.from_reference_json.assert_called_once_with(json_str)
