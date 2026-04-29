"""
mdtpy.aas_misc 모듈의 dataclass에 대한 단위 테스트.

대상:
    - SecurityTypeEnum / SecurityAttributeObject
    - ProtocolInformation / Endpoint
    - OperationVariable      : from_dict/to_dict (basyx_serde에 위임)
    - OperationResult        : from_dict / from_json
    - OperationHandle        : from_json (handleId 매핑)
    - OperationRequest       : to_json (ISO 8601 timeout, inoutputArguments 제외 동작)
"""
from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest

from mdtpy.aas_misc import (
    Endpoint,
    OperationHandle,
    OperationRequest,
    OperationResult,
    OperationVariable,
    ProtocolInformation,
    SecurityAttributeObject,
    SecurityTypeEnum,
)


# --------------------------------------------------------------------------- #
# SecurityTypeEnum / SecurityAttributeObject
# --------------------------------------------------------------------------- #

class TestSecurityTypeEnum:
    def test_member_names_exist(self):
        assert {m.name for m in SecurityTypeEnum} == {"NONE", "RFC_TLSA", "W3C_DID"}

    def test_members_are_distinct(self):
        values = [m.value for m in SecurityTypeEnum]
        assert len(values) == len(set(values))


class TestSecurityAttributeObject:
    def test_construction_stores_fields(self):
        sa = SecurityAttributeObject(type=SecurityTypeEnum.NONE, key="k", value="v")
        assert sa.type is SecurityTypeEnum.NONE
        assert sa.key == "k"
        assert sa.value == "v"


# --------------------------------------------------------------------------- #
# ProtocolInformation / Endpoint
# --------------------------------------------------------------------------- #

class TestProtocolInformation:
    def test_required_only_uses_defaults(self):
        pi = ProtocolInformation(href="http://srv/x")
        assert pi.href == "http://srv/x"
        assert pi.endpointProtocol is None
        assert pi.endpointProtocolVersion is None
        assert pi.subprotocol is None
        assert pi.subprotocolBody is None
        assert pi.subprotocolBody_encoding is None
        assert pi.securityAttributes == []

    def test_default_security_attributes_is_independent_per_instance(self):
        """`default_factory=list` 동작 회귀 가드 (인스턴스 간 list 공유 방지)."""
        pi1 = ProtocolInformation(href="http://a")
        pi2 = ProtocolInformation(href="http://b")
        pi1.securityAttributes.append(
            SecurityAttributeObject(type=SecurityTypeEnum.NONE, key="k", value="v")
        )
        assert pi2.securityAttributes == []

    def test_full_construction(self):
        sa = SecurityAttributeObject(type=SecurityTypeEnum.W3C_DID, key="k", value="v")
        pi = ProtocolInformation(
            href="http://srv",
            endpointProtocol="HTTP",
            endpointProtocolVersion="1.1",
            subprotocol="sub",
            subprotocolBody="body",
            subprotocolBody_encoding="utf-8",
            securityAttributes=[sa],
        )
        assert pi.endpointProtocol == "HTTP"
        assert pi.securityAttributes == [sa]


class TestEndpoint:
    def test_wraps_interface_and_protocol_information(self):
        pi = ProtocolInformation(href="http://x", endpointProtocol="HTTP")
        ep = Endpoint(interface="SUBMODEL", protocolInformation=pi)
        assert ep.interface == "SUBMODEL"
        assert ep.protocolInformation is pi


# --------------------------------------------------------------------------- #
# OperationVariable
# --------------------------------------------------------------------------- #

class TestOperationVariable:
    def test_construction_holds_submodel_element(self):
        sme = MagicMock()
        ov = OperationVariable(value=sme)
        assert ov.value is sme

    def test_from_dict_delegates_to_basyx_serde(self):
        """`from_dict`는 `basyx_serde.from_dict(data['value'])` 호출 결과를 감싼다."""
        sme_obj = MagicMock(name="SubmodelElement")
        with patch(
            "mdtpy.aas_misc.basyx_serde.from_dict", return_value=sme_obj
        ) as m_from_dict:
            ov = OperationVariable.from_dict({"value": {"key": "json"}})
        m_from_dict.assert_called_once_with({"key": "json"})
        assert ov.value is sme_obj

    def test_to_dict_delegates_to_basyx_serde(self):
        """`to_dict`는 `basyx_serde.to_json` 결과를 dict로 풀어 `value` 키에 담는다."""
        sme = MagicMock()
        with patch(
            "mdtpy.aas_misc.basyx_serde.to_json",
            return_value='{"id_short":"x","value":42}',
        ):
            result = OperationVariable(value=sme).to_dict()
        assert result == {"value": {"id_short": "x", "value": 42}}


# --------------------------------------------------------------------------- #
# OperationResult
# --------------------------------------------------------------------------- #

class TestOperationResult:
    def test_from_dict_minimal_success_response(self):
        """필수 필드만 있는 성공 응답 (output/inoutput 인자 없음)."""
        r = OperationResult.from_dict({
            "executionState": "Completed",
            "success": True,
        })
        assert r.success is True
        assert r.execution_state == "Completed"
        assert r.messages is None
        assert r.output_op_variables is None
        assert r.inoutput_op_variables is None

    def test_from_dict_with_messages(self):
        r = OperationResult.from_dict({
            "executionState": "Failed",
            "success": False,
            "messages": ["err1", "err2"],
        })
        assert r.success is False
        assert r.messages == ["err1", "err2"]

    def test_from_dict_parses_output_arguments_via_operation_variable(self):
        """`outputArguments`/`inoutputArguments`는 OperationVariable로 변환되어야 한다."""
        out_sme = MagicMock(name="output")
        inout_sme = MagicMock(name="inoutput")

        # basyx_serde.from_dict가 두 번 호출되며 각각 다른 SME를 반환
        with patch(
            "mdtpy.aas_misc.basyx_serde.from_dict",
            side_effect=[out_sme, inout_sme],
        ) as m_from_dict:
            r = OperationResult.from_dict({
                "executionState": "Completed",
                "success": True,
                "outputArguments": [{"value": {"o": 1}}],
                "inoutputArguments": [{"value": {"i": 2}}],
            })

        assert m_from_dict.call_count == 2
        assert r.output_op_variables is not None
        assert len(r.output_op_variables) == 1
        assert r.output_op_variables[0].value is out_sme
        assert r.inoutput_op_variables is not None
        assert r.inoutput_op_variables[0].value is inout_sme

    def test_from_json_parses_string_then_dict(self):
        with patch(
            "mdtpy.aas_misc.OperationResult.from_dict",
            return_value="sentinel",
        ) as m_from_dict:
            result = OperationResult.from_json('{"executionState": "X", "success": true}')
        m_from_dict.assert_called_once_with({"executionState": "X", "success": True})
        assert result == "sentinel"


# --------------------------------------------------------------------------- #
# OperationHandle
# --------------------------------------------------------------------------- #

class TestOperationHandle:
    def test_from_json_maps_handleId_camelcase(self):
        h = OperationHandle.from_json('{"handleId": "abc-123"}')
        assert h.handle_id == "abc-123"

    def test_from_json_missing_key_raises(self):
        with pytest.raises(KeyError):
            OperationHandle.from_json('{"other": "x"}')

    def test_construction_directly(self):
        h = OperationHandle(handle_id="zzz")
        assert h.handle_id == "zzz"


# --------------------------------------------------------------------------- #
# OperationRequest
# --------------------------------------------------------------------------- #

class TestOperationRequest:
    def _make_op_var(self, key="x", value=1):
        """to_dict이 호출되도록 OperationVariable을 mock한다."""
        ov = MagicMock(spec=OperationVariable)
        ov.to_dict.return_value = {"value": {key: value}}
        return ov

    def test_to_json_includes_input_arguments(self):
        ov1 = self._make_op_var("a", 1)
        ov2 = self._make_op_var("b", 2)
        req = OperationRequest(
            input_arguments=[ov1, ov2],
            inoutput_arguments=[],
            client_timeout_duration=datetime.timedelta(seconds=10),
        )
        body = json.loads(req.to_json())
        assert body["inputArguments"] == [{"value": {"a": 1}}, {"value": {"b": 2}}]

    def test_to_json_excludes_inoutput_arguments(self):
        """현재 fa3st 서버는 `inoutputArguments`를 인식하지 않으므로
        직렬화에서 제외되어야 한다 (회귀 가드)."""
        ov_in = self._make_op_var("i", 1)
        ov_inout = self._make_op_var("io", 2)
        req = OperationRequest(
            input_arguments=[ov_in],
            inoutput_arguments=[ov_inout],
            client_timeout_duration=datetime.timedelta(seconds=1),
        )
        body = json.loads(req.to_json())
        assert "inoutputArguments" not in body
        # inoutput 변수는 to_dict 호출도 일어나지 않아야 한다 (불필요한 비용 방지)
        ov_inout.to_dict.assert_not_called()

    def test_to_json_serializes_timeout_as_iso8601(self):
        req = OperationRequest(
            input_arguments=[],
            inoutput_arguments=[],
            client_timeout_duration=datetime.timedelta(minutes=5),
        )
        body = json.loads(req.to_json())
        # ISO 8601 duration은 'P'로 시작
        assert body["clientTimeoutDuration"].startswith("P")
