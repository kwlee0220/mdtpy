"""
mdtpy.parameter 모듈의 클래스에 대한 단위 테스트.

대상:
    - MDTParameter        : DefaultElementReference 상속, descriptor 검증, 속성 위임
    - MDTParameterCollection : 읽기 전용 Mapping, 중복 id 검출
"""
from __future__ import annotations

import pytest

from mdtpy.descriptor import MDTParameterDescriptor
from mdtpy.exceptions import MDTException
from mdtpy.parameter import MDTParameter, MDTParameterCollection
from mdtpy.reference import DefaultElementReference


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_param_desc(
    id: str = "p1",
    value_type: str = "xs:int",
    reference: str = "param:test:p1",
    name=None,
    endpoint="http://srv/params/p1",
) -> MDTParameterDescriptor:
    return MDTParameterDescriptor(
        id=id,
        value_type=value_type,
        reference=reference,
        name=name,
        endpoint=endpoint,
    )


# --------------------------------------------------------------------------- #
# MDTParameter
# --------------------------------------------------------------------------- #

class TestMDTParameter:
    def test_constructor_initializes_reference_endpoint_and_ref_string(self):
        desc = make_param_desc(
            id="p1",
            reference="param:test:p1",
            endpoint="http://srv/params/p1",
        )
        param = MDTParameter(desc)
        assert isinstance(param, DefaultElementReference)
        assert param.ref_string == "param:test:p1"
        assert param.endpoint == "http://srv/params/p1"

    def test_constructor_rejects_none_endpoint_with_value_error(self):
        desc = make_param_desc(id="p-bad", endpoint=None)
        with pytest.raises(ValueError, match="endpoint is None"):
            MDTParameter(desc)

    def test_value_error_message_includes_descriptor_id(self):
        desc = make_param_desc(id="explicit-id", endpoint=None)
        with pytest.raises(ValueError, match="explicit-id"):
            MDTParameter(desc)

    def test_descriptor_property_returns_original_object(self):
        desc = make_param_desc(id="p1")
        param = MDTParameter(desc)
        assert param.descriptor is desc

    def test_descriptor_property_is_read_only(self):
        """`@property`로 노출되므로 외부에서 재할당할 수 없어야 한다."""
        param = MDTParameter(make_param_desc())
        with pytest.raises(AttributeError):
            param.descriptor = make_param_desc(id="other")  # type: ignore[misc]

    def test_id_property_returns_descriptor_id(self):
        param = MDTParameter(make_param_desc(id="speed"))
        assert param.id == "speed"

    def test_name_property_returns_descriptor_name(self):
        param = MDTParameter(make_param_desc(id="p1", name="Speed Limit"))
        assert param.name == "Speed Limit"

    def test_name_property_returns_none_when_not_set(self):
        param = MDTParameter(make_param_desc(id="p1", name=None))
        assert param.name is None


# --------------------------------------------------------------------------- #
# MDTParameterCollection
# --------------------------------------------------------------------------- #

class TestMDTParameterCollection:
    def _make_param(self, id: str) -> MDTParameter:
        return MDTParameter(
            make_param_desc(
                id=id,
                reference=f"param:test:{id}",
                endpoint=f"http://srv/params/{id}",
            )
        )

    def test_empty_collection_has_zero_length(self):
        coll = MDTParameterCollection([])
        assert len(coll) == 0
        assert list(coll) == []

    def test_accepts_iterable_not_just_list(self):
        """`Iterable[MDTParameter]`를 받아야 하므로 generator도 허용된다."""
        params = (self._make_param(f"p{i}") for i in range(3))
        coll = MDTParameterCollection(params)
        assert len(coll) == 3

    def test_len_returns_number_of_parameters(self):
        coll = MDTParameterCollection([self._make_param("a"), self._make_param("b")])
        assert len(coll) == 2

    def test_iter_yields_keys_in_insertion_order(self):
        params = [self._make_param("c"), self._make_param("a"), self._make_param("b")]
        coll = MDTParameterCollection(params)
        assert list(coll) == ["c", "a", "b"]

    def test_getitem_returns_matching_parameter(self):
        p1 = self._make_param("p1")
        p2 = self._make_param("p2")
        coll = MDTParameterCollection([p1, p2])
        assert coll["p1"] is p1
        assert coll["p2"] is p2

    def test_getitem_unknown_id_raises_key_error(self):
        coll = MDTParameterCollection([self._make_param("p1")])
        with pytest.raises(KeyError):
            _ = coll["missing"]

    def test_contains_uses_default_mapping_implementation(self):
        """`Mapping`이 제공하는 기본 `__contains__`로 'x in coll'이 동작해야 한다."""
        coll = MDTParameterCollection([self._make_param("known")])
        assert "known" in coll
        assert "unknown" not in coll

    def test_keys_values_items_methods_inherited_from_mapping(self):
        p = self._make_param("p1")
        coll = MDTParameterCollection([p])
        assert list(coll.keys()) == ["p1"]
        assert list(coll.values()) == [p]
        assert list(coll.items()) == [("p1", p)]

    def test_get_method_returns_default_when_missing(self):
        coll = MDTParameterCollection([self._make_param("p1")])
        sentinel = object()
        assert coll.get("missing", sentinel) is sentinel

    def test_duplicate_id_raises_mdt_exception(self):
        p_first = self._make_param("dup")
        p_second = self._make_param("dup")
        with pytest.raises(MDTException, match="Duplicate"):
            MDTParameterCollection([p_first, p_second])

    def test_duplicate_detection_includes_id_in_message(self):
        with pytest.raises(MDTException, match="my-param-id"):
            MDTParameterCollection(
                [self._make_param("my-param-id"), self._make_param("my-param-id")]
            )

    def test_collection_does_not_expose_internal_dict(self):
        """`__param_dict`는 name-mangling되어 외부에서 직접 접근할 수 없어야 한다."""
        coll = MDTParameterCollection([self._make_param("p1")])
        assert not hasattr(coll, "param_dict")
        assert not hasattr(coll, "__param_dict")
