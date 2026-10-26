"""
mdtpy.airflow 서브패키지 단위 테스트.

Airflow 설치 없이 동작한다: `LocalDagContext`는 `connect()`를 patch하여 생성하고,
`AirflowDagContext`는 `task_instance` property를 mock TaskInstance로 대체한다.
XCom 경로 테스트는 push/pull 사이에 `json.dumps`/`json.loads`를 강제로 끼워
XCom의 JSON 직렬화 제약을 재현한다.
"""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from basyx.aas import model

from mdtpy.aas_misc import OperationVariable
from mdtpy.airflow import (
    AASOperationOperator,
    OperationSubmodelOperator,
    AirflowDagContext,
    LocalDagContext,
    PythonScriptOperator,
    RestfulAsyncRpcOperator,
    SetElementOperator,
    literal,
    reference,
    task_output,
)
from mdtpy.airflow.dag_context import DagContext
from mdtpy.airflow.operator import restful_async_rpc as restful_async_rpc_module
from mdtpy.operation import OperationSubmodelService
from mdtpy.ref import BaseElementReference, ElementReference
from mdtpy.submodel import SubmodelService
from mdtpy.value import ElementCollectionValue, ElementListValue, FileValue, PropertyValue, mdt_value

MANAGER_URL = "http://localhost:12985/instance-manager"


@pytest.fixture(autouse=True)
def _reset_local_task_output():
    """LocalDagContext의 클래스-수준 task 출력 저장소를 테스트마다 초기화한다."""
    storage = LocalDagContext._LocalDagContext__TASK_OUTPUT
    saved = dict(storage)
    storage.clear()
    try:
        yield
    finally:
        storage.clear()
        storage.update(saved)


@pytest.fixture
def local_ctx():
    """connect()를 patch하여 네트워크 없이 LocalDagContext를 생성한다."""
    with patch("mdtpy.airflow.dag_context.connect") as m_connect:
        m_connect.return_value = MagicMock(name="mdt_manager")
        yield LocalDagContext("task1", MANAGER_URL)


def _make_airflow_ctx(store: dict):
    """__init__(airflow import + connect)을 우회하여 AirflowDagContext를 만들고,
    JSON 직렬화를 강제하는 mock TaskInstance를 함께 반환한다."""
    ctx = object.__new__(AirflowDagContext)
    ti = MagicMock()
    ti.task_id = "task1"
    ti.xcom_push.side_effect = lambda key, value: store.__setitem__(key, json.dumps(value))
    ti.xcom_pull.side_effect = \
        lambda task_ids, key: json.loads(store[key]) if key in store else None
    return ctx, ti


# --------------------------------------------------------------------------- #
# DagTaskArgument  (값을 어떻게 구할지에 대한 명세)
# --------------------------------------------------------------------------- #

class TestDagTaskArgument:
    @pytest.mark.parametrize("raw", [3.14, 3, True, "abc"])
    def test_literal_wraps_raw_scalar(self, raw):
        # raw 스칼라는 명세 생성 시점에 mdt_value()로 감싸진다.
        spec = literal(raw)
        value = spec.get(MagicMock())
        assert isinstance(value, PropertyValue)
        assert value == mdt_value(raw)

    def test_literal_passes_element_value_through(self):
        ev = mdt_value(7)
        assert literal(ev).get(MagicMock()) is ev

    def test_literal_rejects_unsupported_type_at_construction(self):
        # task 실행 시점이 아니라 DAG 정의 시점에 실패해야 한다.
        with pytest.raises(ValueError, match="unsupported property value type"):
            literal(object())

    def test_task_output_delegates_to_context(self):
        context = MagicMock()
        context.get_task_output.return_value = mdt_value(1)
        spec = task_output("prev_task", "Defect")
        assert spec.get(context) == mdt_value(1)
        context.get_task_output.assert_called_once_with("prev_task", "Defect")

    def test_reference_returns_value_for_non_file(self):
        # 대상이 File이 아니면 get()은 참조의 값을 읽어 반환한다.
        context = MagicMock()
        ref_obj = MagicMock(spec=ElementReference)
        ref_obj.ref_string = "param:inst1:Temperature"
        ref_obj.read_value.return_value = mdt_value(42)
        context.resolve_reference.return_value = ref_obj
        spec = reference("param:inst1:Temperature")
        assert spec.get(context) == mdt_value(42)
        context.resolve_reference.assert_called_once_with("param:inst1:Temperature")

    def test_reference_returns_reference_for_file(self):
        # 대상이 File이면 get()은 값 대신 참조 자체를 반환한다(파일은 참조로 전달).
        context = MagicMock()
        ref_obj = MagicMock(spec=ElementReference)
        ref_obj.ref_string = "param:inst1:UpperImage"
        ref_obj.read_value.return_value = MagicMock(spec=FileValue)
        context.resolve_reference.return_value = ref_obj
        spec = reference("param:inst1:UpperImage")
        assert spec.get(context) is ref_obj

    def test_reference_returns_element_for_timeseries(self):
        # 'timeseries:' 참조는 ElementValue가 아니라 SubmodelElement 자체를 반환한다.
        context = MagicMock()
        ref_obj = MagicMock(spec=ElementReference)
        ref_obj.ref_string = "timeseries:inst1:WelderAmpereLog"
        context.resolve_reference.return_value = ref_obj
        spec = reference("timeseries:inst1:WelderAmpereLog")
        assert spec.get(context) is ref_obj.read.return_value
        ref_obj.read_value.assert_not_called()


# --------------------------------------------------------------------------- #
# DagContext  (런타임 어댑터)
# --------------------------------------------------------------------------- #

class TestDagContext:
    def test_fully_abstract(self):
        # 여섯 멤버 모두 @abstractmethod이므로 직접 인스턴스화할 수 없다.
        with pytest.raises(TypeError):
            DagContext()


class TestLocalDagContext:
    def test_task_id_and_manager_url(self, local_ctx):
        assert local_ctx.task_id == "task1"
        assert local_ctx.mdt_manager_url == MANAGER_URL

    def test_mdt_manager_returns_connected_manager(self, local_ctx):
        # connect() 결과가 mdt_manager property로 노출된다.
        assert local_ctx.mdt_manager is not None

    def test_set_then_get_task_output(self, local_ctx):
        local_ctx.set_task_outputs({"Defect": mdt_value(3)})
        assert local_ctx.get_task_output("task1", "Defect") == mdt_value(3)

    def test_non_element_value_output_raises_type_error(self, local_ctx):
        # AirflowDagContext와 동일하게 ElementValue가 아닌 출력은 거부한다.
        with pytest.raises(TypeError, match="Unsupported TaskOutput type"):
            local_ctx.set_task_outputs({"Empty": None})

    def test_output_shared_across_instances(self, local_ctx):
        # 클래스 변수에 보관되므로 같은 프로세스의 다른 인스턴스에서도 조회된다.
        local_ctx.set_task_outputs({"Defect": mdt_value(3)})
        with patch("mdtpy.airflow.dag_context.connect"):
            other = LocalDagContext("task2", MANAGER_URL)
        assert other.get_task_output("task1", "Defect") == mdt_value(3)

    def test_missing_task_raises_keyerror(self, local_ctx):
        with pytest.raises(KeyError, match="no_such_task"):
            local_ctx.get_task_output("no_such_task", "Defect")

    def test_missing_argument_raises_keyerror(self, local_ctx):
        local_ctx.set_task_outputs({"Defect": mdt_value(3)})
        with pytest.raises(KeyError, match="no_such_arg"):
            local_ctx.get_task_output("task1", "no_such_arg")

    def test_resolve_reference_returns_lazy_reference(self, local_ctx):
        # 생성 시 HTTP 없이 BaseElementReference로 감싸기만 한다.
        ref = local_ctx.resolve_reference("param:inst1:Temperature")
        assert isinstance(ref, BaseElementReference)
        assert ref.ref_string == "param:inst1:Temperature"


class TestAirflowDagContext:
    def test_task_output_roundtrip_through_json(self):
        # ElementValue가 @type/value JSON으로 직렬화되어 XCom을 왕복해야 한다.
        store = {}
        ctx, ti = _make_airflow_ctx(store)
        outputs = {"Defect": mdt_value(3), "Score": mdt_value(0.97)}
        with patch.object(AirflowDagContext, "task_instance",
                          new_callable=PropertyMock, return_value=ti):
            ctx.set_task_outputs(outputs)
            for arg_id, orig in outputs.items():
                restored = ctx.get_task_output("task1", arg_id)
                assert restored == orig

    def test_pushed_value_is_json_serializable(self):
        store = {}
        ctx, ti = _make_airflow_ctx(store)
        with patch.object(AirflowDagContext, "task_instance",
                          new_callable=PropertyMock, return_value=ti):
            ctx.set_task_outputs({"Defect": mdt_value(3)})
        # mock이 json.dumps를 통과시켰으므로 @type 태그가 포함된 JSON이어야 한다.
        assert json.loads(store["task_output"]) \
            == {"Defect": {"@type": "mdt:value:integer", "value": 3}}

    def test_non_element_value_output_raises_type_error(self):
        # TaskOutput은 ElementValue만 허용한다 — None 등은 직렬화 단계에서 거부된다.
        store = {}
        ctx, ti = _make_airflow_ctx(store)
        with patch.object(AirflowDagContext, "task_instance",
                          new_callable=PropertyMock, return_value=ti):
            with pytest.raises(TypeError, match="Unsupported TaskOutput type"):
                ctx.set_task_outputs({"Empty": None})

    def test_missing_task_output_raises_keyerror(self):
        ctx, ti = _make_airflow_ctx({})
        with patch.object(AirflowDagContext, "task_instance",
                          new_callable=PropertyMock, return_value=ti):
            with pytest.raises(KeyError, match="task1"):
                ctx.get_task_output("task1", "Defect")

    def test_missing_argument_raises_keyerror(self):
        store = {}
        ctx, ti = _make_airflow_ctx(store)
        with patch.object(AirflowDagContext, "task_instance",
                          new_callable=PropertyMock, return_value=ti):
            ctx.set_task_outputs({"Defect": mdt_value(3)})
            with pytest.raises(KeyError, match="no_such_arg"):
                ctx.get_task_output("task1", "no_such_arg")

    def test_repr_has_no_side_effects(self):
        # task 실행 컨텍스트/Airflow 없이도 repr이 동작해야 한다
        # (task_instance에 접근하면 airflow import로 실패하므로, 성공 자체가 검증이다).
        ctx = object.__new__(AirflowDagContext)
        ctx._AirflowDagContext__mdt_manager_url = MANAGER_URL
        assert MANAGER_URL in repr(ctx)

    @staticmethod
    def _fake_airflow_sdk(variable_url: str = MANAGER_URL):
        """Airflow 미설치 환경에서 생성자의 `from airflow.sdk import Variable`을 대신할 가짜 모듈."""
        fake_sdk = MagicMock()
        fake_sdk.Variable.get.return_value = variable_url
        return fake_sdk, patch.dict(sys.modules, {"airflow": MagicMock(sdk=fake_sdk), "airflow.sdk": fake_sdk})

    def test_constructor_reads_url_from_variable_and_connects(self):
        # URL을 주지 않으면 Airflow Variable 'mdt_manager_url'을 읽고, 생성 시점에 connect()한다.
        fake_sdk, fake_modules = self._fake_airflow_sdk()
        with fake_modules, patch("mdtpy.airflow.dag_context.connect") as m_connect:
            ctx = AirflowDagContext()

        fake_sdk.Variable.get.assert_called_once_with("mdt_manager_url")
        m_connect.assert_called_once_with(MANAGER_URL)
        assert ctx.mdt_manager is m_connect.return_value

    def test_constructor_uses_given_url_without_variable(self):
        other_url = "http://other:12985/instance-manager"
        fake_sdk, fake_modules = self._fake_airflow_sdk()
        with fake_modules, patch("mdtpy.airflow.dag_context.connect") as m_connect:
            ctx = AirflowDagContext(other_url)

        fake_sdk.Variable.get.assert_not_called()
        m_connect.assert_called_once_with(other_url)
        assert ctx.mdt_manager is m_connect.return_value


# --------------------------------------------------------------------------- #
# Operator  (task 본문)
# --------------------------------------------------------------------------- #

class TestSetElementOperator:
    def test_requires_source_at_construction(self):
        # 'source' 입력이 없으면 DAG 정의(생성) 시점에 실패한다.
        with pytest.raises(ValueError, match="'source' is required"):
            SetElementOperator(inputs={})

    def test_outputs_without_target_rejected_at_construction(self):
        # outputs를 지정했다면 'target'이 반드시 있어야 한다.
        with pytest.raises(ValueError, match="'target' is required"):
            SetElementOperator(inputs={"source": literal(3)},
                               outputs={"dest": MagicMock(spec=ElementReference)})

    def test_literal_source_stored_as_task_output(self):
        context = MagicMock()
        SetElementOperator(inputs={"source": literal(3)}).run(context)
        context.set_task_outputs.assert_called_once_with({"target": mdt_value(3)})

    def test_reference_source_read_and_written_to_target(self):
        src_ref = MagicMock(spec=ElementReference)
        src_ref.ref_string = "param:i:Src"
        src_ref.read_value.return_value = mdt_value(5)
        target = MagicMock(spec=ElementReference)
        context = MagicMock()
        context.resolve_reference.return_value = src_ref

        SetElementOperator(inputs={"source": reference("param:i:Src")},
                           outputs={"target": target}).run(context)

        src_ref.read_value.assert_called_once()
        target.update_value.assert_called_once_with(mdt_value(5))
        context.set_task_outputs.assert_called_once_with({"target": mdt_value(5)})


class TestOperationSubmodelOperator:
    def test_rejects_non_operation_submodel(self):
        context = MagicMock()
        context.get_submodel.return_value = MagicMock()  # OperationSubmodelService가 아님
        op = OperationSubmodelOperator("inst1", "Data", inputs={}, outputs={})
        with pytest.raises(ValueError, match="not an operation submodel"):
            op.run(context)

    def test_invoke_merges_inputs_and_outputs_and_stores_result(self):
        submodel = MagicMock(spec=OperationSubmodelService)
        submodel.invoke.return_value = {"B": mdt_value(2)}
        out_ref = MagicMock(spec=ElementReference)
        context = MagicMock()
        context.get_submodel.return_value = submodel

        OperationSubmodelOperator(
            "inst1", "Simulation",
            inputs={"A": literal(1)},
            outputs={"B": out_ref},
        ).run(context)

        context.get_submodel.assert_called_once_with("inst1", "Simulation")
        # 입력은 값으로, 출력 대상은 ElementReference로 병합되어 invoke에 전달된다.
        submodel.invoke.assert_called_once_with(A=mdt_value(1), B=out_ref)
        context.set_task_outputs.assert_called_once_with({"B": mdt_value(2)})


class TestAASOperationOperator:
    @staticmethod
    def _data_submodel(operation):
        """`Operations.Op` 위치에 주어진 요소를 갖는 일반(Data) submodel 서비스."""
        submodel = MagicMock(spec=SubmodelService)  # OperationSubmodelService가 아님
        submodel.submodel_elements = {"Operations.Op": operation}
        return submodel

    def test_invokes_operation_in_data_submodel(self):
        # AAS Operation 요소는 Data submodel 안에도 있을 수 있다 (예: 로봇 이동 연산).
        # submodel 종류와 관계없이 호출되어야 한다 — Java AASOperationTask와 같은 동작.
        operation = model.Operation("Op",
                                    input_variable=[model.Property("X", model.datatypes.Int)],
                                    output_variable=[model.Property("Y", model.datatypes.Int)])
        submodel = self._data_submodel(operation)
        result = MagicMock(success=True, inoutput_op_variables=None,
                           output_op_variables=[OperationVariable(value=model.Property("Y", model.datatypes.Int, 7))])
        submodel.invoke_operation_sync.return_value = result
        out_ref = MagicMock(spec=ElementReference)
        context = MagicMock()
        context.get_submodel.return_value = submodel

        AASOperationOperator("panda01", "Data", "Operations.Op",
                             inputs={"X": literal(3)}, outputs={"Y": out_ref}).run(context)

        context.get_submodel.assert_called_once_with("panda01", "Data")
        path, in_vars, _ = submodel.invoke_operation_sync.call_args.args[:3]
        assert path == "Operations.Op"
        assert [(v.value.id_short, v.value.value) for v in in_vars] == [("X", 3)]
        out_ref.update_value.assert_called_once_with(mdt_value(7))
        context.set_task_outputs.assert_called_once_with({"Y": mdt_value(7)})

    def test_rejects_path_that_is_not_an_operation(self):
        submodel = self._data_submodel(model.Property("Op", model.datatypes.Int))
        context = MagicMock()
        context.get_submodel.return_value = submodel
        with pytest.raises(ValueError, match="not an Operation"):
            AASOperationOperator("panda01", "Data", "Operations.Op", inputs={}).run(context)


class TestPythonScriptOperator:
    def test_raw_output_converted_for_record_and_task_output(self, local_ctx):
        # 원시 값은 mdt_value()로 변환되어 저장 위치와 task 출력 양쪽에 같은 값으로 전달된다.
        out_ref = MagicMock(spec=ElementReference)
        PythonScriptOperator("outputs['answer'] = 42",
                             inputs={}, outputs={"answer": out_ref}).run(local_ctx)

        out_ref.update_value.assert_called_once_with(mdt_value(42))
        assert local_ctx.get_task_output("task1", "answer") == mdt_value(42)

    def test_inputs_visible_in_script(self):
        context = MagicMock()
        PythonScriptOperator("outputs['doubled'] = inputs['x'].to_raw_object() * 2",
                             inputs={"x": literal(21)}).run(context)

        context.set_task_outputs.assert_called_once_with({"doubled": mdt_value(42)})

    def test_dict_and_list_outputs_converted(self):
        # dict/list 출력은 ElementCollectionValue/ElementListValue로 변환된다. 예를 들어 계산한
        # 자세를 dict로 내면 후속 AASOperationTask가 SMC 입력(TargetPose 등)으로 받을 수 있다.
        context = MagicMock()
        script = ("outputs['pose'] = {'Position': {'x': 0.42, 'y': -0.1, 'z': 0.64}}\n"
                  "outputs['dims'] = [0.05, 0.05]")
        PythonScriptOperator(script, inputs={}).run(context)

        outputs = context.set_task_outputs.call_args.args[0]
        assert isinstance(outputs["pose"], ElementCollectionValue)
        assert outputs["pose"].to_raw_object() == {"Position": {"x": 0.42, "y": -0.1, "z": 0.64}}
        assert isinstance(outputs["dims"], ElementListValue)
        assert outputs["dims"].to_raw_object() == [0.05, 0.05]

    def test_all_script_outputs_passed_but_only_targets_recorded(self):
        # script가 outputs dict에 넣은 값은 모두 후속 task에 전달되고, 저장 위치가 지정된 값만 기록된다.
        out_ref = MagicMock(spec=ElementReference)
        context = MagicMock()
        PythonScriptOperator("outputs['answer'] = 42\noutputs['extra'] = 'x'",
                             inputs={}, outputs={"answer": out_ref}).run(context)

        out_ref.update_value.assert_called_once_with(mdt_value(42))
        context.set_task_outputs.assert_called_once_with({"answer": mdt_value(42), "extra": mdt_value("x")})

    def test_none_target_has_no_effect(self):
        # 저장 위치가 None인 항목은 이전 버전 호환을 위해 허용되며 아무 효과가 없다.
        context = MagicMock()
        PythonScriptOperator("outputs['answer'] = 42",
                             inputs={}, outputs={"answer": None}).run(context)

        context.set_task_outputs.assert_called_once_with({"answer": mdt_value(42)})

    def test_missing_target_output_skipped(self):
        # 저장 위치가 지정됐더라도 script가 그 값을 넣지 않았으면 기록하지 않는다.
        out_ref = MagicMock(spec=ElementReference)
        context = MagicMock()
        PythonScriptOperator("answer = 42",   # 변수 대입만으로는 출력되지 않는다.
                             inputs={}, outputs={"answer": out_ref}).run(context)

        out_ref.update_value.assert_not_called()
        context.set_task_outputs.assert_called_once_with({})

    def test_conversion_failure_records_nothing(self):
        # 모든 출력이 전달 대상이므로, 저장 위치가 없는 출력의 변환이 실패해도 앞쪽 출력은 기록되지 않는다.
        first_ref = MagicMock(spec=ElementReference)
        context = MagicMock()
        # list/dict는 변환되므로(test_dict_and_list_outputs_converted) 변환할 수 없는 값으로 object()를 쓴다.
        op = PythonScriptOperator("outputs['first'] = 1\noutputs['second'] = object()",
                                  inputs={}, outputs={"first": first_ref})
        with pytest.raises(ValueError, match="unsupported property value type"):
            op.run(context)

        first_ref.update_value.assert_not_called()
        context.set_task_outputs.assert_not_called()


class TestRestfulAsyncRpcOperator:
    # 'mdtpy.airflow.operator.restful_async_rpc...' 문자열 경로로 patch하면, mdtpy.airflow의
    # star import가 'operator' 속성을 operator.py 모듈로 덮어써서 해석에 실패한다. 모듈 객체를 직접 patch한다.
    @staticmethod
    def _patch_client():
        return patch.object(restful_async_rpc_module, "RESTfulAsyncRpcClient")

    def test_client_receives_resolved_inputs(self):
        context = MagicMock()
        with self._patch_client() as m_client:
            m_client.return_value.call.return_value = {}
            RestfulAsyncRpcOperator("http://op-server", "/ops/sim",
                                    inputs={"A": literal(1)}).run(context)

        m_client.assert_called_once_with(base_url="http://op-server", op_endpoint="/ops/sim",
                                         inputs={"A": mdt_value(1)})

    def test_raw_result_converted_for_record_and_task_output(self):
        out_ref = MagicMock(spec=ElementReference)
        context = MagicMock()
        with self._patch_client() as m_client:
            m_client.return_value.call.return_value = {"B": 2}
            RestfulAsyncRpcOperator("http://op-server", "/ops/sim",
                                    inputs={}, outputs={"B": out_ref}).run(context)

        out_ref.update_value.assert_called_once_with(mdt_value(2))
        context.set_task_outputs.assert_called_once_with({"B": mdt_value(2)})

    def test_undeclared_results_still_passed(self):
        # 이 operator는 연산이 반환한 모든 결과를 후속 task에 전달한다. 기록은 선언된 출력만 한다.
        out_ref = MagicMock(spec=ElementReference)
        context = MagicMock()
        with self._patch_client() as m_client:
            m_client.return_value.call.return_value = {"B": mdt_value(2), "C": mdt_value(3)}
            RestfulAsyncRpcOperator("http://op-server", "/ops/sim",
                                    inputs={}, outputs={"B": out_ref}).run(context)

        out_ref.update_value.assert_called_once_with(mdt_value(2))
        context.set_task_outputs.assert_called_once_with({"B": mdt_value(2), "C": mdt_value(3)})

    def test_conversion_failure_records_nothing(self):
        # 뒤쪽 결과의 변환이 실패하면 앞쪽 결과도 기록되지 않는다.
        first_ref = MagicMock(spec=ElementReference)
        second_ref = MagicMock(spec=ElementReference)
        context = MagicMock()
        op = RestfulAsyncRpcOperator("http://op-server", "/ops/sim", inputs={},
                                     outputs={"first": first_ref, "second": second_ref})
        with self._patch_client() as m_client:
            m_client.return_value.call.return_value = {"first": 1, "second": [1, 2]}
            with pytest.raises(ValueError, match="unsupported property value type"):
                op.run(context)

        first_ref.update_value.assert_not_called()
        second_ref.update_value.assert_not_called()
        context.set_task_outputs.assert_not_called()
