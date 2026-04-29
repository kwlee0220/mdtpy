"""
mdtpy.operation 모듈의 클래스/함수에 대한 단위 테스트.

대상:
    - get_argument_value           : 분기별 분배
    - AASOperationService          : Operation 타입 검증, OperationVariable 수집,
                                     invoke 성공/실패 흐름
    - Argument                     : id_short_path URL 인코딩, descriptor 위임
    - ArgumentList                 : 중복 검출, str/int 인덱싱
    - OperationSubmodelService     : input/output_arguments 구성, invoke 흐름,
                                     출력 ElementReference 업데이트

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
from mdtpy.exceptions import MDTException, OperationError
from mdtpy.operation import (
    AASOperationService,
    Argument,
    ArgumentList,
    OperationSubmodelService,
    get_argument_value,
)
from mdtpy.reference import DefaultElementReference, ElementReference
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


def make_op_svc_mock(service_endpoint: str = "http://srv/sm") -> MagicMock:
    """`Argument`/`ArgumentList`가 사용하는 op_submodel_svc 자리의 mock."""
    op_svc = MagicMock()
    op_svc.service_endpoint = service_endpoint
    return op_svc


# --------------------------------------------------------------------------- #
# get_argument_value
# --------------------------------------------------------------------------- #

class TestGetArgumentValue:
    def test_element_reference_branch_calls_read_value(self):
        ref = MagicMock(spec=ElementReference)
        ref.read_value.return_value = 42
        assert get_argument_value(ref) == 42
        ref.read_value.assert_called_once_with()

    def test_submodel_element_branch_calls_get_value(self):
        sme = MagicMock(spec=model.SubmodelElement)
        with patch("mdtpy.operation.get_value", return_value="parsed") as m_get_value:
            assert get_argument_value(sme) == "parsed"
            m_get_value.assert_called_once_with(sme)

    @pytest.mark.parametrize("value", [42, 3.14, "text", True, None, [1, 2], {"k": "v"}])
    def test_raw_value_passthrough(self, value):
        assert get_argument_value(value) == value


# --------------------------------------------------------------------------- #
# Argument
# --------------------------------------------------------------------------- #

class TestArgument:
    def test_endpoint_url_encodes_id_short_path(self):
        op_svc = make_op_svc_mock("http://srv/sm")
        # path에 슬래시·대괄호·공백 등 예약 문자가 포함된 경우
        desc = make_arg_desc(id_short_path="Out.Result[0]/sub item")
        arg = Argument(op_svc, desc)
        prefix = "http://srv/sm/submodel-elements/"
        assert arg.endpoint.startswith(prefix)
        suffix = arg.endpoint[len(prefix):]
        for ch in "/[] ":
            assert ch not in suffix, f"suffix에 인코딩되지 않은 {ch!r} 가 남아있음: {suffix}"

    def test_constructor_passes_reference_to_parent(self):
        op_svc = make_op_svc_mock()
        desc = make_arg_desc(reference="oparg:i:op:in:a1")
        arg = Argument(op_svc, desc)
        assert isinstance(arg, DefaultElementReference)
        assert arg.ref_string == "oparg:i:op:in:a1"

    def test_descriptor_property_returns_original_object(self):
        op_svc = make_op_svc_mock()
        desc = make_arg_desc(id="x")
        arg = Argument(op_svc, desc)
        assert arg.descriptor is desc

    def test_descriptor_is_read_only(self):
        arg = Argument(make_op_svc_mock(), make_arg_desc())
        with pytest.raises(AttributeError):
            arg.descriptor = make_arg_desc(id="other")  # type: ignore[misc]

    def test_id_property_delegates_to_descriptor(self):
        arg = Argument(make_op_svc_mock(), make_arg_desc(id="speed"))
        assert arg.id == "speed"


# --------------------------------------------------------------------------- #
# ArgumentList
# --------------------------------------------------------------------------- #

class TestArgumentList:
    def test_construction_creates_arguments_for_each_descriptor(self):
        op_svc = make_op_svc_mock()
        descs = [make_arg_desc(id="a"), make_arg_desc(id="b")]
        coll = ArgumentList(op_svc, descs)
        assert len(coll) == 2
        assert isinstance(coll["a"], Argument)
        assert coll["a"].id == "a"
        assert coll["b"].id == "b"

    def test_getitem_by_int_index_uses_insertion_order(self):
        op_svc = make_op_svc_mock()
        descs = [make_arg_desc(id="x"), make_arg_desc(id="y"), make_arg_desc(id="z")]
        coll = ArgumentList(op_svc, descs)
        assert coll[0].id == "x"
        assert coll[1].id == "y"
        assert coll[2].id == "z"

    def test_getitem_by_int_index_out_of_range_raises(self):
        op_svc = make_op_svc_mock()
        coll = ArgumentList(op_svc, [make_arg_desc(id="a")])
        with pytest.raises(IndexError):
            _ = coll[5]

    def test_getitem_by_str_unknown_raises_key_error(self):
        op_svc = make_op_svc_mock()
        coll = ArgumentList(op_svc, [make_arg_desc(id="a")])
        with pytest.raises(KeyError):
            _ = coll["missing"]

    def test_duplicate_id_raises_mdt_exception(self):
        op_svc = make_op_svc_mock()
        with pytest.raises(MDTException, match="Duplicate Argument"):
            ArgumentList(op_svc, [make_arg_desc(id="dup"), make_arg_desc(id="dup")])

    def test_duplicate_message_contains_id(self):
        op_svc = make_op_svc_mock()
        with pytest.raises(MDTException, match="conflicting-id"):
            ArgumentList(
                op_svc,
                [make_arg_desc(id="conflicting-id"), make_arg_desc(id="conflicting-id")],
            )

    def test_empty_descriptor_list_yields_empty_collection(self):
        coll = ArgumentList(make_op_svc_mock(), [])
        assert len(coll) == 0


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

        with patch("mdtpy.operation.update_element_with_value") as m_update, \
             patch("mdtpy.operation.get_value", return_value=None):
            aas_op.invoke(a=99)
            # 입력 OperationVariable의 value가 99로 갱신되어야 한다
            assert m_update.called
            updated_value_arg = m_update.call_args[0][1]
            assert updated_value_arg == 99

    def test_invoke_calls_submodel_invoke_operation_sync(self):
        aas_op, sm_svc, _op = self._make_service_with_vars(in_ids=("a",))
        sm_svc.invoke_operation_sync.return_value = self._make_result(success=True)

        with patch("mdtpy.operation.update_element_with_value"), \
             patch("mdtpy.operation.get_value"):
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
        with patch("mdtpy.operation.get_value", return_value=123):
            output = aas_op.invoke()
        assert output == {"r": 123}

    def test_invoke_merges_output_and_inoutput_variables(self):
        aas_op, sm_svc, _ = self._make_service_with_vars()
        sm_svc.invoke_operation_sync.return_value = self._make_result(
            success=True, output_ids=("o",), inoutput_ids=("io",)
        )
        with patch("mdtpy.operation.get_value", side_effect=lambda v: f"val:{v.id_short}"):
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
    @patch("mdtpy.operation.AASOperationService")
    def test_init_creates_argument_lists_and_aas_service(self, mock_aas_cls):
        sm_desc = make_sm_desc()
        op_desc = make_op_desc(
            input_args=[make_arg_desc(id="x")],
            output_args=[make_arg_desc(id="y")],
        )
        svc = OperationSubmodelService("test-instance", sm_desc, op_desc)

        # input/output arguments는 ArgumentList로 노출되어야 한다
        assert "x" in svc.input_arguments
        assert "y" in svc.output_arguments
        # AASOperationService는 'Operation' 경로로 생성되어야 한다
        mock_aas_cls.assert_called_once_with(svc, "Operation")
        assert svc.op is mock_aas_cls.return_value

    @patch("mdtpy.operation.AASOperationService")
    def test_operation_descriptor_is_property(self, mock_aas_cls):
        op_desc = make_op_desc(id="my-op")
        svc = OperationSubmodelService("inst", make_sm_desc(), op_desc)
        # @property이므로 호출이 아니라 attribute 접근
        assert svc.operation_descriptor is op_desc


class TestOperationSubmodelServiceInvoke:
    """`invoke` 메서드 전용 테스트.

    SubmodelService 상속 + AASOperationService 생성을 우회하기 위해
    `__new__`로 객체를 만든 뒤 필요한 속성만 직접 주입한다.
    """

    def _bare_svc(self) -> OperationSubmodelService:
        svc = OperationSubmodelService.__new__(OperationSubmodelService)
        svc.input_arguments = MagicMock()
        svc.output_arguments = MagicMock()
        svc.op = MagicMock()
        return svc

    def test_invoke_reads_input_args_and_calls_op_invoke(self):
        svc = self._bare_svc()
        svc.input_arguments.read_value.return_value = {"a": 1, "b": 2}
        svc.output_arguments.__contains__.return_value = False
        svc.op.invoke.return_value = {}

        with patch("mdtpy.operation.update_value_dict") as m_update_dict:
            svc.invoke()

        # 입력 인자 값이 서버에서 한 번 read되고
        svc.input_arguments.read_value.assert_called_once()
        # update_value_dict가 kwargs와 합쳐주고
        m_update_dict.assert_called_once()
        # op.invoke에 그 값들이 그대로 전달된다
        svc.op.invoke.assert_called_once_with(a=1, b=2)

    def test_invoke_returns_op_invoke_result(self):
        svc = self._bare_svc()
        svc.input_arguments.read_value.return_value = {}
        svc.output_arguments.__contains__.return_value = False
        svc.op.invoke.return_value = {"out": 99}

        with patch("mdtpy.operation.update_value_dict"):
            result = svc.invoke()

        assert result == {"out": 99}

    def test_invoke_updates_output_element_reference_when_provided(self):
        """출력 인자 자리에 ElementReference를 kwargs로 넣으면, 결과 값으로
        해당 reference의 update_value()가 호출되어야 한다."""
        svc = self._bare_svc()
        svc.input_arguments.read_value.return_value = {}
        svc.output_arguments.__contains__.return_value = True
        svc.op.invoke.return_value = {"out": 123}

        out_ref = MagicMock(spec=ElementReference)

        with patch("mdtpy.operation.update_value_dict"):
            svc.invoke(out=out_ref)

        out_ref.update_value.assert_called_once_with(123)

    def test_invoke_does_not_update_non_reference_kwargs(self):
        """ElementReference가 아닌 일반 값은 update_value 호출 대상이 아님."""
        svc = self._bare_svc()
        svc.input_arguments.read_value.return_value = {}
        svc.output_arguments.__contains__.return_value = True
        svc.op.invoke.return_value = {"out": 99}

        with patch("mdtpy.operation.update_value_dict"):
            # 그냥 정수값을 kwargs로 — 업데이트 호출 없이 통과해야 한다
            result = svc.invoke(out=42)

        assert result == {"out": 99}

    def test_invoke_skips_update_when_arg_id_not_in_output_arguments(self):
        """결과 키가 output_arguments에 없는 경우(입력 인자가 잘못 ref로 들어온 경우)
        update_value를 호출하지 않는다."""
        svc = self._bare_svc()
        svc.input_arguments.read_value.return_value = {}
        # output_arguments에 'foo'가 없다고 가정
        svc.output_arguments.__contains__.return_value = False
        svc.op.invoke.return_value = {"foo": 1}

        ref = MagicMock(spec=ElementReference)
        with patch("mdtpy.operation.update_value_dict"):
            svc.invoke(foo=ref)

        ref.update_value.assert_not_called()
