"""
mdtpy.airflow 서브패키지 단위 테스트.

Airflow 설치 없이 동작한다: `LocalDagContext`는 `connect()`를 patch하여 생성하고,
`AirflowDagContext`는 `task_instance` property를 mock TaskInstance로 대체한다.
XCom 경로 테스트는 push/pull 사이에 `json.dumps`/`json.loads`를 강제로 끼워
XCom의 JSON 직렬화 제약을 재현한다.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from mdtpy.airflow import (
    OperationSubmodelOperator,
    AirflowDagContext,
    LocalDagContext,
    SetElementOperator,
    literal,
    reference,
    task_output,
)
from mdtpy.airflow.dag_context import DagContext
from mdtpy.operation import OperationSubmodelService
from mdtpy.ref import BaseElementReference, ElementReference
from mdtpy.value import FileValue, PropertyValue, mdt_value

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
        ref_obj.read_value.return_value = mdt_value(42)
        context.resolve_reference.return_value = ref_obj
        spec = reference("param:inst1:Temperature")
        assert spec.get(context) == mdt_value(42)
        context.resolve_reference.assert_called_once_with("param:inst1:Temperature")

    def test_reference_returns_reference_for_file(self):
        # 대상이 File이면 get()은 값 대신 참조 자체를 반환한다(파일은 참조로 전달).
        context = MagicMock()
        ref_obj = MagicMock(spec=ElementReference)
        ref_obj.read_value.return_value = MagicMock(spec=FileValue)
        context.resolve_reference.return_value = ref_obj
        spec = reference("param:inst1:UpperImage")
        assert spec.get(context) is ref_obj


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


# --------------------------------------------------------------------------- #
# Operator  (task 본문)
# --------------------------------------------------------------------------- #

class TestCopyElementOperator:
    def test_requires_source_at_construction(self):
        # source가 None이면 DAG 정의(생성) 시점에 실패한다.
        with pytest.raises(ValueError, match="'source' is required"):
            SetElementOperator(None)

    def test_literal_source_stored_as_task_output(self):
        context = MagicMock()
        SetElementOperator(literal(3)).run(context)
        context.set_task_outputs.assert_called_once_with({"target": mdt_value(3)})

    def test_reference_source_read_and_written_to_target(self):
        src_ref = MagicMock(spec=ElementReference)
        src_ref.read_value.return_value = mdt_value(5)
        target = MagicMock(spec=ElementReference)
        context = MagicMock()
        context.resolve_reference.return_value = src_ref

        SetElementOperator(reference("param:i:Src"), target=target).run(context)

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
