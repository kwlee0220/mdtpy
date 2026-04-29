"""
mdtpy.descriptor 모듈의 enum과 dataclass에 대한 단위 테스트.

대상:
    - 열거형: MDTInstanceStatus, MDTAssetType, AssetKind
    - dataclass: InstanceDescriptor, MDTParameterDescriptor,
        MDTSubmodelDescriptor, ArgumentDescriptor, MDTOperationDescriptor
    - JSONWizard 라운드트립 (from_dict / to_dict)
    - MDTSubmodelDescriptor.is_*() 분류 메서드
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from mdtpy.descriptor import (
    SEMANTIC_ID_AI_SUBMODEL,
    SEMANTIC_ID_DATA_SUBMODEL,
    SEMANTIC_ID_INFOR_MODEL_SUBMODEL,
    SEMANTIC_ID_SIMULATION_SUBMODEL,
    SEMANTIC_ID_TIME_SERIES_SUBMODEL,
    ArgumentDescriptor,
    AssetKind,
    InstanceDescriptor,
    MDTAssetType,
    MDTInstanceStatus,
    MDTOperationDescriptor,
    MDTParameterDescriptor,
    MDTSubmodelDescriptor,
)


# --------------------------------------------------------------------------- #
# 열거형
# --------------------------------------------------------------------------- #

class TestMDTInstanceStatusEnum:
    @pytest.mark.parametrize(
        "name, value",
        [
            ("STOPPED", "STOPPED"),
            ("STARTING", "STARTING"),
            ("RUNNING", "RUNNING"),
            ("STOPPING", "STOPPING"),
            ("FAILED", "FAILED"),
        ],
    )
    def test_member_value_pairs(self, name, value):
        assert MDTInstanceStatus[name].value == value
        assert MDTInstanceStatus(value).name == name

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError):
            MDTInstanceStatus("UNKNOWN")

    def test_iteration_yields_all_five(self):
        assert len(list(MDTInstanceStatus)) == 5


class TestMDTAssetTypeEnum:
    @pytest.mark.parametrize(
        "name, value",
        [
            ("Machine", "Machine"),
            ("Process", "Process"),
            ("Line", "Line"),
            ("Factory", "Factory"),
        ],
    )
    def test_pascal_case_values_match_server_format(self, name, value):
        """`MDTAssetType` 값은 서버 응답 표기를 따라 PascalCase여야 한다."""
        assert MDTAssetType[name].value == value
        assert MDTAssetType(value).name == name


class TestAssetKindEnum:
    @pytest.mark.parametrize(
        "name, value",
        [
            ("INSTANCE", "INSTANCE"),
            ("NOT_APPLICABLE", "NOT_APPLICABLE"),
            ("TYPE", "TYPE"),
        ],
    )
    def test_member_value_pairs(self, name, value):
        assert AssetKind[name].value == value
        assert AssetKind(value).name == name


# --------------------------------------------------------------------------- #
# InstanceDescriptor
# --------------------------------------------------------------------------- #

class TestInstanceDescriptor:
    def test_required_fields_only(self):
        desc = InstanceDescriptor(
            id="i1",
            status=MDTInstanceStatus.STOPPED,
            aas_id="aas-1",
        )
        assert desc.id == "i1"
        assert desc.status == MDTInstanceStatus.STOPPED
        assert desc.aas_id == "aas-1"
        # Optional 필드는 모두 None 기본값
        assert desc.base_endpoint is None
        assert desc.aas_id_short is None
        assert desc.global_asset_id is None
        assert desc.asset_type is None
        assert desc.asset_kind is None

    def test_full_construction(self):
        desc = InstanceDescriptor(
            id="i1",
            status=MDTInstanceStatus.RUNNING,
            aas_id="aas-1",
            base_endpoint="http://srv/i1",
            aas_id_short="Short",
            global_asset_id="global-x",
            asset_type=MDTAssetType.Machine,
            asset_kind=AssetKind.INSTANCE,
        )
        assert desc.base_endpoint == "http://srv/i1"
        assert desc.asset_type == MDTAssetType.Machine
        assert desc.asset_kind == AssetKind.INSTANCE

    def test_is_frozen(self):
        desc = InstanceDescriptor(id="i1", status=MDTInstanceStatus.STOPPED, aas_id="aas")
        with pytest.raises(FrozenInstanceError):
            desc.id = "other"  # type: ignore[misc]

    def test_equality_ignores_compare_false_fields(self):
        """`hash=False, compare=False`로 표시된 필드는 동등성 비교에서 제외된다."""
        a = InstanceDescriptor(
            id="i1", status=MDTInstanceStatus.RUNNING, aas_id="aas-1",
            base_endpoint="http://a",
        )
        b = InstanceDescriptor(
            id="i1", status=MDTInstanceStatus.RUNNING, aas_id="aas-1",
            base_endpoint="http://b",   # 다르지만 비교 대상 아님
        )
        assert a == b

    def test_equality_uses_required_fields(self):
        a = InstanceDescriptor(id="i1", status=MDTInstanceStatus.RUNNING, aas_id="aas-1")
        b = InstanceDescriptor(id="i2", status=MDTInstanceStatus.RUNNING, aas_id="aas-1")
        assert a != b

    def test_jsonwizard_roundtrip(self):
        """`from_dict`/`to_dict` 라운드트립이 모든 필드를 보존해야 한다."""
        original = InstanceDescriptor(
            id="i1",
            status=MDTInstanceStatus.RUNNING,
            aas_id="aas-1",
            base_endpoint="http://srv/i1",
            aas_id_short="Short",
            global_asset_id="global-x",
            asset_type=MDTAssetType.Process,
            asset_kind=AssetKind.TYPE,
        )
        data = original.to_dict()
        restored = InstanceDescriptor.from_dict(data)
        assert restored == original
        # compare=False 필드도 값 자체는 보존되어야 한다
        assert restored.base_endpoint == "http://srv/i1"
        assert restored.asset_type == MDTAssetType.Process


# --------------------------------------------------------------------------- #
# MDTParameterDescriptor
# --------------------------------------------------------------------------- #

class TestMDTParameterDescriptor:
    def test_required_fields_with_optional_defaults(self):
        d = MDTParameterDescriptor(id="p1", value_type="xs:int", reference="param:i:p1")
        assert d.id == "p1"
        assert d.value_type == "xs:int"
        assert d.reference == "param:i:p1"
        assert d.name is None
        assert d.endpoint is None

    def test_full_construction(self):
        d = MDTParameterDescriptor(
            id="p1",
            value_type="xs:double",
            reference="param:i:p1",
            name="속도",
            endpoint="http://srv/p1",
        )
        assert d.name == "속도"
        assert d.endpoint == "http://srv/p1"

    def test_is_frozen(self):
        d = MDTParameterDescriptor(id="p1", value_type="xs:int", reference="r")
        with pytest.raises(FrozenInstanceError):
            d.id = "p2"  # type: ignore[misc]

    def test_jsonwizard_roundtrip(self):
        original = MDTParameterDescriptor(
            id="p1", value_type="xs:int", reference="r", name="n", endpoint="ep"
        )
        assert MDTParameterDescriptor.from_dict(original.to_dict()) == original


# --------------------------------------------------------------------------- #
# MDTSubmodelDescriptor
# --------------------------------------------------------------------------- #

class TestMDTSubmodelDescriptor:
    @pytest.mark.parametrize(
        "semantic_id, true_method",
        [
            (SEMANTIC_ID_INFOR_MODEL_SUBMODEL, "is_information_model"),
            (SEMANTIC_ID_DATA_SUBMODEL, "is_data"),
            (SEMANTIC_ID_SIMULATION_SUBMODEL, "is_simulation"),
            (SEMANTIC_ID_AI_SUBMODEL, "is_ai"),
            (SEMANTIC_ID_TIME_SERIES_SUBMODEL, "is_time_series"),
        ],
    )
    def test_classification_methods_match_semantic_id(self, semantic_id, true_method):
        """주어진 semantic_id에서는 정확히 한 분류 메서드만 True여야 한다."""
        d = MDTSubmodelDescriptor(
            id="sm", id_short="X", semantic_id=semantic_id, endpoint=None
        )
        all_methods = [
            "is_information_model",
            "is_data",
            "is_simulation",
            "is_ai",
            "is_time_series",
        ]
        for m in all_methods:
            expected = (m == true_method)
            assert getattr(d, m)() is expected, (
                f"{m}() for semantic_id={semantic_id} expected {expected}"
            )

    def test_unknown_semantic_id_returns_false_for_all(self):
        d = MDTSubmodelDescriptor(
            id="sm", id_short="X", semantic_id="https://unknown/sm", endpoint=None
        )
        assert not d.is_information_model()
        assert not d.is_data()
        assert not d.is_simulation()
        assert not d.is_ai()
        assert not d.is_time_series()

    def test_is_frozen(self):
        d = MDTSubmodelDescriptor(
            id="sm", id_short="X", semantic_id=SEMANTIC_ID_DATA_SUBMODEL,
            endpoint="http://x",
        )
        with pytest.raises(FrozenInstanceError):
            d.id = "other"  # type: ignore[misc]

    def test_jsonwizard_roundtrip(self):
        original = MDTSubmodelDescriptor(
            id="sm-1",
            id_short="Data",
            semantic_id=SEMANTIC_ID_DATA_SUBMODEL,
            endpoint="http://srv/sm",
        )
        assert MDTSubmodelDescriptor.from_dict(original.to_dict()) == original


# --------------------------------------------------------------------------- #
# ArgumentDescriptor
# --------------------------------------------------------------------------- #

class TestArgumentDescriptor:
    def test_construction_requires_all_four_fields(self):
        d = ArgumentDescriptor(
            id="a1", id_short_path="Inputs.a1", value_type="xs:int", reference="r"
        )
        assert d.id == "a1"
        assert d.id_short_path == "Inputs.a1"
        assert d.value_type == "xs:int"
        assert d.reference == "r"

    def test_is_frozen(self):
        d = ArgumentDescriptor(id="a", id_short_path="p", value_type="t", reference="r")
        with pytest.raises(FrozenInstanceError):
            d.id = "b"  # type: ignore[misc]

    def test_jsonwizard_roundtrip(self):
        original = ArgumentDescriptor(
            id="a1", id_short_path="In.a1", value_type="xs:int", reference="r"
        )
        assert ArgumentDescriptor.from_dict(original.to_dict()) == original


# --------------------------------------------------------------------------- #
# MDTOperationDescriptor
# --------------------------------------------------------------------------- #

class TestMDTOperationDescriptor:
    def _make_arg(self, id_):
        return ArgumentDescriptor(
            id=id_, id_short_path=f"In.{id_}", value_type="xs:int", reference="r"
        )

    def test_construction_with_argument_lists(self):
        op = MDTOperationDescriptor(
            id="op1",
            operation_type="sync",
            input_arguments=[self._make_arg("x"), self._make_arg("y")],
            output_arguments=[self._make_arg("r")],
        )
        assert op.id == "op1"
        assert op.operation_type == "sync"
        assert len(op.input_arguments) == 2
        assert len(op.output_arguments) == 1

    def test_empty_argument_lists_are_allowed(self):
        op = MDTOperationDescriptor(
            id="op1", operation_type="sync", input_arguments=[], output_arguments=[],
        )
        assert op.input_arguments == []
        assert op.output_arguments == []

    def test_is_frozen(self):
        op = MDTOperationDescriptor(
            id="op1", operation_type="sync", input_arguments=[], output_arguments=[],
        )
        with pytest.raises(FrozenInstanceError):
            op.id = "other"  # type: ignore[misc]

    def test_jsonwizard_roundtrip_with_nested_arguments(self):
        original = MDTOperationDescriptor(
            id="op1",
            operation_type="sync",
            input_arguments=[self._make_arg("x")],
            output_arguments=[self._make_arg("r")],
        )
        restored = MDTOperationDescriptor.from_dict(original.to_dict())
        assert restored == original
        assert restored.input_arguments[0].id == "x"
        assert restored.output_arguments[0].id == "r"
