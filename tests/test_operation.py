"""
mdtpy.operation 모듈의 클래스/함수에 대한 단위 테스트.

대상:
    - AASOperationService          : Operation 타입 검증, OperationVariable 수집,
                                     invoke 성공/실패 흐름
    - OperationSubmodelService     : input_arg_descs/output_arg_desc_dict 구성, invoke 흐름,
                                     출력 ElementReference 업데이트
    - parse_argument_json_node     : 타입 태그에 따른 JSON 노드 변환

기본 노선: HTTP·SubmodelService 의존을 unittest.mock으로 차단.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from basyx.aas import model

from mdtpy.descriptor import (
    ArgumentDescriptor,
    MDTOperationDescriptor,
    MDTSubmodelDescriptor,
)
from mdtpy.exceptions import InvalidArgumentError, OperationError, ResourceNotFoundError
from mdtpy.operation import (
    AASOperationService,
    OperationSubmodelService,
    parse_argument_json_node,
)
from mdtpy.value import FileValue
from mdtpy.ref import ElementReference
from mdtpy.submodel import SubmodelService


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_arg_desc(
    id: str = "a1",
    id_short_path: str = "Inputs.a1",
    value_type: str = "xs:int",
    reference: str = "oparg:test:op:in:a1",
) -> ArgumentDescriptor:
    return ArgumentDescriptor(
        id=id,
        id_short_path=id_short_path,
        value_type=value_type,
        reference=reference,
    )


def make_op_desc(
    id: str = "op1",
    operation_type: str = "sync",
    input_args=None,
    output_args=None,
) -> MDTOperationDescriptor:
    return MDTOperationDescriptor(
        id=id,
        operation_type=operation_type,
        input_arguments=input_args if input_args is not None else [],
        output_arguments=output_args if output_args is not None else [],
    )


def make_sm_desc(
    id: str = "sm1",
    id_short: str = "Sim",
    endpoint: str = "http://srv/sm",
    semantic_id: str = "https://etri.re.kr/mdt/Submodel/Simulation/1/1",
) -> MDTSubmodelDescriptor:
    return MDTSubmodelDescriptor(
        id=id,
        id_short=id_short,
        semantic_id=semantic_id,
        endpoint=endpoint,
    )


def make_op_var(id_short: str) -> MagicMock:
    """OperationVariable.value (SubmodelElement) 자리 채울 mock."""
    sme = MagicMock(spec=model.SubmodelElement)
    sme.id_short = id_short
    return sme


# --------------------------------------------------------------------------- #
# AASOperationService
# --------------------------------------------------------------------------- #

class TestAASOperationServiceInit:
    def _submodel_svc_with_op(self, op):
        svc = MagicMock(spec=SubmodelService)
        # submodel_elements는 dict-like — mapping 형태로 충분
        svc.submodel_elements = {"OpPath": op}
        return svc

    def test_collects_input_inout_output_variables(self):
        op = MagicMock(spec=model.Operation)
        op.input_variable = [make_op_var("in1"), make_op_var("in2")]
        op.in_output_variable = [make_op_var("io1")]
        op.output_variable = [make_op_var("out1")]

        aas_op = AASOperationService(self._submodel_svc_with_op(op), "OpPath")
        assert len(aas_op.in_op_variables) == 2
        assert len(aas_op.inout_op_variables) == 1
        assert len(aas_op.out_op_variables) == 1

    def test_raises_value_error_when_path_is_not_an_operation(self):
        non_op = MagicMock(spec=model.SubmodelElement)
        svc = MagicMock(spec=SubmodelService)
        svc.submodel_elements = {"NotOp": non_op}
        with pytest.raises(ValueError, match="not an Operation"):
            AASOperationService(svc, "NotOp")

    def test_value_error_includes_path_and_actual_type(self):
        non_op = MagicMock(spec=model.Property)
        svc = MagicMock(spec=SubmodelService)
        svc.submodel_elements = {"X": non_op}
        with pytest.raises(ValueError) as excinfo:
            AASOperationService(svc, "X")
        assert "X" in str(excinfo.value)


class TestAASOperationServiceInvoke:
    def _make_service_with_vars(self, in_ids=("a",), out_ids=("r",), inout_ids=()):
        op = MagicMock(spec=model.Operation)
        op.input_variable = [make_op_var(x) for x in in_ids]
        op.in_output_variable = [make_op_var(x) for x in inout_ids]
        op.output_variable = [make_op_var(x) for x in out_ids]
        sm_svc = MagicMock(spec=SubmodelService)
        sm_svc.submodel_elements = {"OpPath": op}
        return AASOperationService(sm_svc, "OpPath"), sm_svc, op

    def _make_result(self, success=True, output_ids=(), inoutput_ids=(), messages=None):
        result = MagicMock()
        result.success = success
        result.messages = messages
        result.output_op_variables = (
            [MagicMock(value=make_op_var(i)) for i in output_ids] if output_ids else None
        )
        result.inoutput_op_variables = (
            [MagicMock(value=make_op_var(i)) for i in inoutput_ids] if inoutput_ids else None
        )
        return result

    def test_invoke_updates_input_variables_from_kwargs(self):
        aas_op, sm_svc, _op = self._make_service_with_vars(in_ids=("a",))
        sm_svc.invoke_operation_sync.return_value = self._make_result(success=True)

        with patch("mdtpy.operation.aas_operation.update_element_with_raw_value") as m_update, \
             patch("mdtpy.operation.aas_operation.get_value", return_value=None):
            aas_op.invoke(a=99)
            # 입력 OperationVariable의 value가 99로 갱신되어야 한다
            assert m_update.called
            updated_value_arg = m_update.call_args[0][1]
            assert updated_value_arg == 99

    def test_invoke_calls_submodel_invoke_operation_sync(self):
        aas_op, sm_svc, _op = self._make_service_with_vars(in_ids=("a",))
        sm_svc.invoke_operation_sync.return_value = self._make_result(success=True)

        with patch("mdtpy.operation.aas_operation.update_element_with_raw_value"), \
             patch("mdtpy.operation.aas_operation.get_value"):
            aas_op.invoke()

        # invoke_operation_sync가 op_path와 변수 목록으로 호출되어야 한다
        call = sm_svc.invoke_operation_sync.call_args
        assert call.args[0] == "OpPath"
        assert "timeout" in call.kwargs

    def test_invoke_returns_dict_keyed_by_id_short_for_outputs(self):
        aas_op, sm_svc, _ = self._make_service_with_vars(in_ids=(), out_ids=("r",))
        sm_svc.invoke_operation_sync.return_value = self._make_result(
            success=True, output_ids=("r",)
        )
        with patch("mdtpy.operation.aas_operation.get_value", return_value=123):
            output = aas_op.invoke()
        assert output == {"r": 123}

    def test_invoke_merges_output_and_inoutput_variables(self):
        aas_op, sm_svc, _ = self._make_service_with_vars()
        sm_svc.invoke_operation_sync.return_value = self._make_result(
            success=True, output_ids=("o",), inoutput_ids=("io",)
        )
        with patch("mdtpy.operation.aas_operation.get_value", side_effect=lambda v: f"val:{v.id_short}"):
            output = aas_op.invoke()
        assert output == {"o": "val:o", "io": "val:io"}

    def test_invoke_raises_operation_error_when_not_successful(self):
        aas_op, sm_svc, _ = self._make_service_with_vars()
        sm_svc.invoke_operation_sync.return_value = self._make_result(
            success=False, messages=["something bad"]
        )
        with pytest.raises(OperationError, match="something bad"):
            aas_op.invoke()

    def test_invoke_failure_without_messages_still_raises(self):
        aas_op, sm_svc, _ = self._make_service_with_vars()
        sm_svc.invoke_operation_sync.return_value = self._make_result(
            success=False, messages=None
        )
        with pytest.raises(OperationError, match="failed"):
            aas_op.invoke()


# --------------------------------------------------------------------------- #
# OperationSubmodelService
# --------------------------------------------------------------------------- #

class TestOperationSubmodelServiceInit:
    @patch("mdtpy.operation.mdt_operation.AASOperationService")
    def test_init_builds_arg_desc_structures_and_aas_service(self, mock_aas_cls):
        sm_desc = make_sm_desc()
        op_desc = make_op_desc(
            input_args=[make_arg_desc(id="x")],
            output_args=[make_arg_desc(id="y")],
        )
        svc = OperationSubmodelService("test-instance", sm_desc, op_desc)

        # 입력은 descriptor 리스트 그대로, 출력은 id→descriptor dict로 보관된다.
        assert svc.input_arg_descs == op_desc.input_arguments
        assert isinstance(svc.output_arg_desc_dict, dict)
        assert set(svc.output_arg_desc_dict) == {"y"}
        # AASOperationService는 'Operation' 경로로 생성되어야 한다.
        mock_aas_cls.assert_called_once_with(svc, "Operation")
        assert svc.op is mock_aas_cls.return_value

    @patch("mdtpy.operation.mdt_operation.AASOperationService")
    def test_operation_descriptor_is_property(self, mock_aas_cls):
        op_desc = make_op_desc(id="my-op")
        svc = OperationSubmodelService("inst", make_sm_desc(), op_desc)
        # @property이므로 호출이 아니라 attribute 접근
        assert svc.operation_descriptor is op_desc


class TestOperationSubmodelServiceInvoke:
    """`invoke` 메서드 전용 테스트.

    SubmodelService 상속 + AASOperationService 생성을 우회하기 위해
    `__new__`로 객체를 만든 뒤 필요한 속성만 직접 주입한다.

    invoke 계약 요약:
        - 선언된 입력 인자마다 kwargs 값이 있으면 그 값을, 없으면
          `reference(desc.reference)`로 만든 기본 참조를 op.invoke에 넘긴다.
        - 결과의 각 항목은 kwargs로 받은 ElementReference가 있으면 그 참조를,
          없으면 `output_arg_desc_dict`의 기본 출력 참조를 update_value()로 갱신한다.
    """

    def _bare_svc(self, input_descs=(), output_descs=()) -> OperationSubmodelService:
        svc = OperationSubmodelService.__new__(OperationSubmodelService)
        svc.input_arg_descs = list(input_descs)
        svc.output_arg_desc_dict = { d.id: d for d in output_descs }
        svc.op = MagicMock()
        svc.op.invoke.return_value = {}
        return svc

    @patch("mdtpy.operation.mdt_operation.reference")
    def test_invoke_passes_kwarg_and_default_reference_to_op_invoke(self, m_ref):
        """입력 'a'는 kwargs 값(1)으로, 'b'는 kwargs에 없으므로 reference(desc.reference)로 전달된다."""
        m_ref.side_effect = lambda ref_string: f"REF({ref_string})"
        descs = [make_arg_desc(id="a", reference="ref:a"),
                 make_arg_desc(id="b", reference="ref:b")]
        svc = self._bare_svc(input_descs=descs)

        svc.invoke(a=1)

        svc.op.invoke.assert_called_once_with(a=1, b="REF(ref:b)")

    def test_invoke_returns_op_invoke_result(self):
        svc = self._bare_svc()
        svc.op.invoke.return_value = {"out": 99}

        assert svc.invoke() == {"out": 99}

    def test_invoke_updates_kwargs_reference_with_result(self):
        """출력 자리에 ElementReference를 kwargs로 넣으면 결과 값으로 update_value된다."""
        svc = self._bare_svc()
        svc.op.invoke.return_value = {"out": 123}
        out_ref = MagicMock(spec=ElementReference)

        svc.invoke(out=out_ref)

        out_ref.update_value.assert_called_once_with(123)

    @patch("mdtpy.operation.mdt_operation.reference")
    def test_invoke_updates_default_output_reference_when_not_in_kwargs(self, m_ref):
        """kwargs로 출력을 넘기지 않으면 output_arg_desc_dict의 기본 참조가 갱신된다."""
        def_ref = MagicMock(spec=ElementReference)
        m_ref.return_value = def_ref
        svc = self._bare_svc(output_descs=[make_arg_desc(id="out", reference="ref:out")])
        svc.op.invoke.return_value = {"out": 99}

        svc.invoke()

        m_ref.assert_called_once_with("ref:out")
        def_ref.update_value.assert_called_once_with(99)

    @patch("mdtpy.operation.mdt_operation.reference")
    def test_invoke_reports_output_write_failure_separately_and_keeps_writing(self, m_ref):
        """연산 성공 후 출력 저장이 실패하면 OperationError 가 아니라 OutputWriteError 이고,
        나머지 출력은 계속 저장하며, 예외에 결과 전체를 담는다."""
        from mdtpy.exceptions import OutputWriteError, ResourceNotFoundError
        bad_ref = MagicMock(spec=ElementReference)
        bad_ref.update_value.side_effect = ResourceNotFoundError("no such target")
        good_ref = MagicMock(spec=ElementReference)
        svc = self._bare_svc(output_descs=[make_arg_desc(id="a", reference="ref:a"),
                                           make_arg_desc(id="b", reference="ref:b")])
        svc.op.invoke.return_value = {"a": 1, "b": 2}

        with pytest.raises(OutputWriteError) as info:
            svc.invoke(a=bad_ref, b=good_ref)

        assert info.value.outputs == {"a": 1, "b": 2}
        assert list(info.value.failures) == ["a"]
        assert isinstance(info.value.failures["a"], ResourceNotFoundError)
        good_ref.update_value.assert_called_once_with(2)

    def test_invoke_rejects_non_reference_for_output_only_arg(self):
        """출력 전용 인자에 ElementReference가 아닌 값을 주면 연산을 호출하지 않고 ValueError."""
        svc = self._bare_svc(output_descs=[make_arg_desc(id="out", reference="ref:out")])

        with pytest.raises(ValueError, match="out"):
            svc.invoke(out=42)
        svc.op.invoke.assert_not_called()

    @patch("mdtpy.operation.mdt_operation.reference")
    def test_invoke_updates_default_output_for_inout_arg_given_raw_value(self, m_ref):
        """입출력 인자에 원시값을 주면 입력으로 쓰이고, 결과는 기본 출력 참조에 갱신된다."""
        def_ref = MagicMock(spec=ElementReference)
        m_ref.return_value = def_ref
        svc = self._bare_svc(input_descs=[make_arg_desc(id="io", reference="ref:io:in")],
                             output_descs=[make_arg_desc(id="io", reference="ref:io:out")])
        svc.op.invoke.return_value = {"io": 99}

        svc.invoke(io=42)

        svc.op.invoke.assert_called_once_with(io=42)
        m_ref.assert_any_call("ref:io:out")
        def_ref.update_value.assert_called_once_with(99)

    def test_invoke_updates_any_kwargs_reference_present_in_result(self):
        """결과에 해당 id가 있으면 kwargs로 받은 ElementReference는 출력 선언 여부와
        무관하게 갱신된다."""
        svc = self._bare_svc()
        svc.op.invoke.return_value = {"foo": 1}
        ref = MagicMock(spec=ElementReference)

        svc.invoke(foo=ref)

        ref.update_value.assert_called_once_with(1)


# --------------------------------------------------------------------------- #
# parse_argument_json_node  (인자·값 JSON 노드 → 파이썬 객체)
# --------------------------------------------------------------------------- #

class TestParseArgumentJsonNode:
    @pytest.mark.parametrize("node", [42, 1.5, "param:inst1:Temp", None, [1, 2]])
    def test_non_dict_is_returned_as_is(self, node):
        # 참조 접두어로 시작하는 문자열도 변환하지 않는다(문자열 값과 구분할 수 없으므로).
        assert parse_argument_json_node(node) == node

    def test_dict_without_type_tag_is_returned_as_is(self):
        node = {"content_type": "image/png", "value": "a.png"}
        assert parse_argument_json_node(node) is node

    def test_model_type_becomes_submodel_element(self):
        node = {"modelType": "Property", "idShort": "p", "valueType": "xs:int", "value": "3"}
        sme = parse_argument_json_node(node)
        assert isinstance(sme, model.Property) and sme.value == 3

    def test_value_type_tag_becomes_element_value(self):
        node = FileValue(content_type="text/plain", value="a.txt").to_json_node()
        assert parse_argument_json_node(node) == FileValue(content_type="text/plain", value="a.txt")

    def test_ref_type_tag_delegates_to_manager(self):
        from mdtpy import instance as instance_mod
        fake_ref = object()
        mgr = MagicMock()
        mgr.from_reference_json.return_value = fake_ref
        instance_mod.mdt_manager = mgr  # conftest 가 테스트 후 원복한다.

        node = {"@type": "mdt:ref:element",
                "submodelReference": {"instanceId": "inst1", "submodelIdShort": "Data"},
                "elementPath": "A.B"}
        assert parse_argument_json_node(node) is fake_ref

    def test_unknown_type_tag_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown @type: mdt:unknown"):
            parse_argument_json_node({"@type": "mdt:unknown"})


# --------------------------------------------------------------------------- #
# InvalidArgumentError  (연산을 호출하기 전, 인자를 적용하지 못한 경우)
# --------------------------------------------------------------------------- #

class TestInvalidArgumentError:
    def _int_operation_service(self):
        """xs:int 입력 인자 'n' 하나를 가진 AASOperationService. 서브모델 서비스는 mock."""
        op = model.Operation("Op", input_variable=[model.Property("n", model.datatypes.Int, 1)])
        submodel_svc = MagicMock(spec=SubmodelService)
        submodel_svc.submodel_elements = {"Op": op}
        return AASOperationService(submodel_svc, "Op"), submodel_svc

    @pytest.mark.parametrize("bad_value", ["abc", {"a": 1}, [1, 2]])
    def test_wrong_typed_input_is_rejected_before_invoking(self, bad_value):
        svc, submodel_svc = self._int_operation_service()
        with pytest.raises(InvalidArgumentError) as info:
            svc.invoke(n=bad_value)
        assert info.value.argument_id == "n" and "'n'" in str(info.value)
        assert isinstance(info.value, ValueError)            # except ValueError 로도 잡힌다
        submodel_svc.invoke_operation_sync.assert_not_called()

    def test_remote_error_while_reading_input_reference_is_not_wrapped(self):
        svc, submodel_svc = self._int_operation_service()
        ref = MagicMock(spec=ElementReference)
        ref.read_value.side_effect = ResourceNotFoundError("input reference not found")
        with pytest.raises(ResourceNotFoundError):
            svc.invoke(n=ref)
        submodel_svc.invoke_operation_sync.assert_not_called()
