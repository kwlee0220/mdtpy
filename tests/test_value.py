"""
mdtpy.value 모듈의 헬퍼 함수에 대한 단위 테스트.

대상 함수:
    - update_value_dict
    - to_file_value
    - get_value
    - update_element_with_value
    - from_json_object
    - to_json_object

basyx의 SubmodelElement는 `MagicMock(spec=...)`으로 mock하여 match 패턴
(isinstance 기반)을 통과시키고, 직접 인스턴스 생성 비용을 피한다.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from basyx.aas import model

from mdtpy.reference import ElementReference
from mdtpy.value import (
    FileJsonValue,
    FileValue,
    RangeValue,
    from_json_object,
    get_value,
    to_file_value,
    to_json_object,
    update_element_with_value,
    update_value_dict,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_property(value=None, value_type=None, id_short="prop"):
    p = MagicMock(spec=model.Property)
    p.value = value
    p.value_type = value_type
    p.id_short = id_short
    return p


def make_smc(members):
    smc = MagicMock(spec=model.SubmodelElementCollection)
    smc.value = members
    return smc


def make_sml(members):
    sml = MagicMock(spec=model.SubmodelElementList)
    sml.value = members
    return sml


def make_file(content_type=None, value=None):
    f = MagicMock(spec=model.File)
    f.content_type = content_type
    f.value = value
    return f


def make_range(min_val=None, max_val=None, value_type=None):
    r = MagicMock(spec=model.Range)
    r.min = min_val
    r.max = max_val
    r.value_type = value_type
    return r


def make_mlp(value=None, id_short="mlp"):
    m = MagicMock(spec=model.MultiLanguageProperty)
    m.value = value
    m.id_short = id_short
    return m


# --------------------------------------------------------------------------- #
# update_value_dict
# --------------------------------------------------------------------------- #

class TestUpdateValueDict:
    def test_overwrites_existing_keys_with_raw_values(self):
        target = {"a": 0, "b": 0}
        update_value_dict(target, {"a": 1, "b": 2})
        assert target == {"a": 1, "b": 2}

    def test_skips_keys_not_in_target(self):
        target = {"a": 0}
        update_value_dict(target, {"a": 1, "missing": 99})
        assert target == {"a": 1}
        assert "missing" not in target

    def test_none_value_sets_target_to_none(self):
        target = {"a": "x"}
        update_value_dict(target, {"a": None})
        assert target["a"] is None

    def test_element_reference_is_resolved_via_read_value(self):
        ref = MagicMock(spec=ElementReference)
        ref.read_value.return_value = 42
        target = {"a": 0}
        update_value_dict(target, {"a": ref})
        assert target["a"] == 42
        ref.read_value.assert_called_once()

    def test_submodel_element_is_resolved_via_get_value(self):
        prop = make_property(value=99)
        target = {"a": 0}
        update_value_dict(target, {"a": prop})
        assert target["a"] == 99


# --------------------------------------------------------------------------- #
# to_file_value
# --------------------------------------------------------------------------- #

class TestToFileValue:
    def test_uses_explicit_content_type_without_tika(self, tmp_path):
        """`content_type`이 주어지면 Tika를 호출하지 않고 그대로 사용한다."""
        f = tmp_path / "image.jpg"
        f.write_bytes(b"")
        result = to_file_value(str(f), content_type="image/jpeg")
        assert result == {"content_type": "image/jpeg", "value": "image.jpg"}

    def test_value_field_is_basename_only(self, tmp_path):
        f = tmp_path / "deep" / "nested" / "x.txt"
        f.parent.mkdir(parents=True)
        f.write_text("data")
        result = to_file_value(str(f), content_type="text/plain")
        assert result["value"] == "x.txt"


# --------------------------------------------------------------------------- #
# get_value
# --------------------------------------------------------------------------- #

class TestGetValue:
    def test_property_returns_inner_value(self):
        assert get_value(make_property(value=42)) == 42

    def test_submodel_element_collection_returns_dict(self):
        a = make_property(value=1, id_short="a")
        b = make_property(value=2, id_short="b")
        smc = make_smc([a, b])
        assert get_value(smc) == {"a": 1, "b": 2}

    def test_submodel_element_list_returns_list_in_order(self):
        a = make_property(value="x")
        b = make_property(value="y")
        sml = make_sml([a, b])
        assert get_value(sml) == ["x", "y"]

    def test_file_returns_file_value_dict(self):
        f = make_file(content_type="image/png", value="img.png")
        assert get_value(f) == {"content_type": "image/png", "value": "img.png"}

    def test_range_returns_range_value_dict(self):
        r = make_range(min_val=0, max_val=10)
        assert get_value(r) == {"min": 0, "max": 10}

    def test_multilang_property_returns_dict_of_lang_to_text(self):
        # MultiLanguageProperty.value behaves like a Mapping {lang: text}
        mlp = make_mlp(value={"en": "hello", "ko": "안녕"})
        assert get_value(mlp) == {"en": "hello", "ko": "안녕"}

    def test_multilang_property_with_none_value_returns_none(self):
        assert get_value(make_mlp(value=None)) is None

    def test_unknown_sme_type_raises_not_implemented(self):
        unknown = MagicMock(spec=model.SubmodelElement)
        with pytest.raises(NotImplementedError, match="Unknown SubmodelElement type"):
            get_value(unknown)


# --------------------------------------------------------------------------- #
# update_element_with_value
# --------------------------------------------------------------------------- #

class TestUpdateElementWithValue:
    def test_none_value_is_noop(self):
        prop = make_property(value="initial")
        update_element_with_value(prop, None)
        assert prop.value == "initial"

    def test_property_assigns_value_directly(self):
        prop = make_property()
        update_element_with_value(prop, 123)
        assert prop.value == 123

    def test_property_converts_timedelta_to_relativedelta(self):
        """timedelta는 `timedelta_to_relativedelta`로 변환되어야 한다."""
        prop = make_property()
        with patch(
            "mdtpy.value.timedelta_to_relativedelta",
            return_value="converted",
        ) as m_conv:
            update_element_with_value(prop, timedelta(seconds=5))
        m_conv.assert_called_once()
        assert prop.value == "converted"

    def test_smc_recurses_into_members(self):
        a = make_property(id_short="a")
        b = make_property(id_short="b")
        smc = make_smc([a, b])
        update_element_with_value(smc, {"a": 1, "b": 2})
        assert a.value == 1
        assert b.value == 2

    def test_smc_skips_members_without_matching_value(self):
        """value dict에 없는 member는 갱신하지 않는다."""
        a = make_property(id_short="a", value="orig-a")
        b = make_property(id_short="b", value="orig-b")
        smc = make_smc([a, b])
        update_element_with_value(smc, {"a": "new-a"})  # 'b' 누락
        assert a.value == "new-a"
        assert b.value == "orig-b"

    def test_sml_zips_values_by_position(self):
        a = make_property()
        b = make_property()
        sml = make_sml([a, b])
        update_element_with_value(sml, [10, 20])
        assert a.value == 10
        assert b.value == 20

    def test_file_assigns_content_type_and_value(self):
        f = make_file()
        update_element_with_value(
            f, {"content_type": "image/png", "value": "x.png"}
        )
        assert f.content_type == "image/png"
        assert f.value == "x.png"

    def test_range_assigns_min_and_max(self):
        r = make_range()
        update_element_with_value(r, {"min": 0, "max": 100})
        assert r.min == 0
        assert r.max == 100

    def test_unknown_sme_type_raises_not_implemented(self):
        unknown = MagicMock(spec=model.SubmodelElement)
        with pytest.raises(NotImplementedError, match="Unknown SubmodelElement type"):
            update_element_with_value(unknown, "x")


# --------------------------------------------------------------------------- #
# from_json_object  (서버 wire 포맷 → Python 표준)
# --------------------------------------------------------------------------- #

class TestFromJsonObject:
    def test_none_value_returns_none(self):
        assert from_json_object(None, make_property()) is None

    def test_property_string_value_uses_xsd_parse(self):
        proto = make_property(value_type="xs:int")
        with patch(
            "mdtpy.value.model.datatypes.from_xsd",
            return_value=42,
        ) as m_from_xsd:
            result = from_json_object("42", proto)
        m_from_xsd.assert_called_once_with("42", "xs:int")
        assert result == 42

    def test_property_non_string_value_passes_through(self):
        proto = make_property(value_type="xs:int")
        # 이미 native 값인 경우 from_xsd를 거치지 않는다
        assert from_json_object(42, proto) == 42

    def test_submodel_element_collection_parses_each_member(self):
        a = make_property(id_short="a", value_type="xs:int")
        b = make_property(id_short="b", value_type="xs:int")
        proto = make_smc([a, b])
        with patch(
            "mdtpy.value.model.datatypes.from_xsd",
            side_effect=lambda v, t: int(v),
        ):
            result = from_json_object({"a": "1", "b": "2"}, proto)
        assert result == {"a": 1, "b": 2}

    def test_submodel_element_list_zips_with_proto_value(self):
        a = make_property(value_type="xs:int")
        b = make_property(value_type="xs:int")
        proto = make_sml([a, b])
        with patch(
            "mdtpy.value.model.datatypes.from_xsd",
            side_effect=lambda v, t: int(v),
        ):
            result = from_json_object(["10", "20"], proto)
        assert result == [10, 20]

    def test_file_maps_content_type_camelcase_to_snake_case(self):
        proto = make_file()
        result = from_json_object(
            {"contentType": "image/png", "value": "x.png"}, proto
        )
        assert result == {"content_type": "image/png", "value": "x.png"}

    def test_range_parses_min_and_max_via_xsd(self):
        proto = make_range(value_type="xs:int")
        with patch(
            "mdtpy.value.model.datatypes.from_xsd",
            side_effect=lambda v, t: int(v),
        ):
            result = from_json_object({"min": "0", "max": "10"}, proto)
        assert result == {"min": 0, "max": 10}

    def test_multilang_property_collapses_list_of_dicts_to_single_dict(self):
        proto = make_mlp()
        result = from_json_object(
            [{"en": "hello"}, {"ko": "안녕"}], proto,
        )
        assert result == {"en": "hello", "ko": "안녕"}

    def test_unknown_proto_type_raises(self):
        unknown = MagicMock(spec=model.SubmodelElement)
        with pytest.raises(NotImplementedError):
            from_json_object("anything", unknown)


# --------------------------------------------------------------------------- #
# to_json_object  (Python 표준 → 서버 wire 포맷)
# --------------------------------------------------------------------------- #

class TestToJsonObject:
    def test_none_value_returns_none(self):
        assert to_json_object(None, make_property()) is None

    def test_property_uses_xsd_repr(self):
        proto = make_property()
        # Property의 isinstance(value, model.ValueDataType)는 native int에 대해 True
        with patch(
            "mdtpy.value.model.datatypes.xsd_repr",
            return_value="42",
        ) as m_repr:
            result = to_json_object(42, proto)
        m_repr.assert_called_once_with(42)
        assert result == "42"

    def test_file_maps_snake_case_to_camelcase(self):
        proto = make_file()
        result = to_json_object(
            {"content_type": "image/png", "value": "x.png"}, proto,
        )
        assert result == {"contentType": "image/png", "value": "x.png"}

    def test_range_serializes_min_max_via_xsd_repr(self):
        proto = make_range()
        with patch(
            "mdtpy.value.model.datatypes.xsd_repr",
            side_effect=lambda v: str(v),
        ):
            result = to_json_object({"min": 0, "max": 10}, proto)
        assert result == {"min": "0", "max": "10"}

    def test_multilang_property_returns_lang_text_dict(self):
        proto = make_mlp()
        result = to_json_object({"en": "hello"}, proto)
        assert result == {"en": "hello"}

    def test_unknown_proto_type_raises(self):
        unknown = MagicMock(spec=model.SubmodelElement)
        with pytest.raises(NotImplementedError):
            to_json_object("x", unknown)
