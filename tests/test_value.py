"""
mdtpy.value 모듈의 헬퍼 함수에 대한 단위 테스트.

대상 함수:
    - FileValue.from_file_path
    - get_value
    - update_element_with_raw_value
    - from_raw_json_node
    - from_raw_object

basyx의 SubmodelElement는 `MagicMock(spec=...)`으로 mock하여 match 패턴
(isinstance 기반)을 통과시키고, 직접 인스턴스 생성 비용을 피한다.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from basyx.aas import model

from mdtpy.value import (
    ElementCollectionValue,
    ElementListValue,
    ElementValue,
    FileJsonValue,
    FileValue,
    MLPropertyValue,
    PropertyValue,
    RangeValue,
    from_raw_json_node,
    from_raw_object,
    get_value,
    parse_json_node,
    parse_json_string,
    update_element_with_raw_value,
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
# FileValue.from_file_path
# --------------------------------------------------------------------------- #

class TestFromFilePath:
    def test_uses_explicit_content_type_without_tika(self, tmp_path):
        """`content_type`이 주어지면 Tika를 호출하지 않고 그대로 사용한다."""
        f = tmp_path / "image.jpg"
        f.write_bytes(b"")
        result = FileValue.from_file_path(str(f), content_type="image/jpeg")
        assert result == FileValue(content_type="image/jpeg", value="image.jpg")

    def test_value_field_is_basename_only(self, tmp_path):
        f = tmp_path / "deep" / "nested" / "x.txt"
        f.parent.mkdir(parents=True)
        f.write_text("data")
        result = FileValue.from_file_path(str(f), content_type="text/plain")
        assert result.value == "x.txt"


# --------------------------------------------------------------------------- #
# get_value
# --------------------------------------------------------------------------- #

class TestGetValue:
    def test_property_returns_property_value(self):
        assert get_value(make_property(value=42)) == PropertyValue(42, model.datatypes.Int)

    def test_submodel_element_collection_returns_collection_value(self):
        a = make_property(value=1, id_short="a")
        b = make_property(value=2, id_short="b")
        smc = make_smc([a, b])
        result = get_value(smc)
        assert isinstance(result, ElementCollectionValue)
        assert result == {"a": PropertyValue(1, model.datatypes.Int),
                          "b": PropertyValue(2, model.datatypes.Int)}

    def test_submodel_element_list_returns_list_in_order(self):
        a = make_property(value="x")
        b = make_property(value="y")
        sml = make_sml([a, b])
        result = get_value(sml)
        assert isinstance(result, ElementListValue)
        assert result == [PropertyValue("x", model.datatypes.String),
                          PropertyValue("y", model.datatypes.String)]

    def test_file_returns_file_value(self):
        f = make_file(content_type="image/png", value="img.png")
        assert get_value(f) == FileValue(content_type="image/png", value="img.png")

    def test_range_returns_range_value(self):
        r = make_range(min_val=0, max_val=10)
        assert get_value(r) == RangeValue(min=0, max=10, value_type=model.datatypes.Int)

    def test_multilang_property_returns_mlproperty_value(self):
        # sme.value(dict-like {lang: text})는 [{lang: text}, ...] 리스트로 변환된다.
        mlp = make_mlp(value={"en": "hello", "ko": "안녕"})
        result = get_value(mlp)
        assert isinstance(result, MLPropertyValue)
        assert result == [{"en": "hello"}, {"ko": "안녕"}]

    def test_multilang_property_with_none_value_raises(self):
        with pytest.raises(ValueError, match="MultiLanguageProperty value is None"):
            get_value(make_mlp(value=None))

    def test_unknown_sme_type_raises_not_implemented(self):
        unknown = MagicMock(spec=model.SubmodelElement)
        with pytest.raises(NotImplementedError, match="Unknown SubmodelElement type"):
            get_value(unknown)


# --------------------------------------------------------------------------- #
# update_element_with_raw_value
# --------------------------------------------------------------------------- #

class TestUpdateElementWithRawValue:
    def test_property_none_sets_value_to_none(self):
        prop = make_property(value="initial")
        update_element_with_raw_value(prop, None)
        assert prop.value is None

    def test_property_assigns_value_directly(self):
        prop = make_property()
        update_element_with_raw_value(prop, 123)
        assert prop.value == 123

    def test_property_converts_timedelta_to_relativedelta(self):
        """timedelta는 `timedelta_to_relativedelta`로 변환되어야 한다."""
        prop = make_property()
        with patch(
            "mdtpy.value.timedelta_to_relativedelta",
            return_value="converted",
        ) as m_conv:
            update_element_with_raw_value(prop, timedelta(seconds=5))
        m_conv.assert_called_once()
        assert prop.value == "converted"

    def test_smc_recurses_into_members(self):
        a = make_property(id_short="a")
        b = make_property(id_short="b")
        smc = make_smc([a, b])
        update_element_with_raw_value(smc, {"a": 1, "b": 2})
        assert a.value == 1
        assert b.value == 2

    def test_smc_sets_missing_members_to_none(self):
        """value dict에 없는 member 는 None 으로 갱신된다 (Property 멤버 기준)."""
        a = make_property(id_short="a", value="orig-a")
        b = make_property(id_short="b", value="orig-b")
        smc = make_smc([a, b])
        update_element_with_raw_value(smc, {"a": "new-a"})  # 'b' 누락
        assert a.value == "new-a"
        assert b.value is None

    def test_sml_zips_values_by_position(self):
        a = make_property()
        b = make_property()
        sml = make_sml([a, b])
        update_element_with_raw_value(sml, [10, 20])
        assert a.value == 10
        assert b.value == 20

    def test_file_assigns_content_type_and_value(self):
        f = make_file()
        update_element_with_raw_value(
            f, {"content_type": "image/png", "value": "x.png"}
        )
        assert f.content_type == "image/png"
        assert f.value == "x.png"

    def test_range_assigns_min_and_max(self):
        r = make_range()
        update_element_with_raw_value(r, {"min": 0, "max": 100})
        assert r.min == 0
        assert r.max == 100

    def test_unknown_sme_type_raises_not_implemented(self):
        unknown = MagicMock(spec=model.SubmodelElement)
        with pytest.raises(NotImplementedError, match="Unknown SubmodelElement type"):
            update_element_with_raw_value(unknown, "x")


# --------------------------------------------------------------------------- #
# ElementValue.apply_to  (ElementValue → basyx SME)
#
# 각 서브클래스는 (1) 먼저 SME 종류 호환성을 검사하고, (2) 값을 SME 에 기록한다.
# 컨테이너(SMC/SML)는 멤버마다 재귀적으로 apply_to 를 호출한다.
# --------------------------------------------------------------------------- #

class TestApplyTo:
    # -- PropertyValue --------------------------------------------------- #
    def test_property_value_applies_scalar(self):
        prop = make_property(value_type=model.datatypes.Int)
        PropertyValue(42, model.datatypes.Int).apply_to(prop)
        assert prop.value == 42

    def test_property_value_none_clears_value(self):
        # None 값을 적용하면 element 의 기존 값을 지운다.
        prop = make_property(value="initial", value_type=model.datatypes.String)
        PropertyValue(None, model.datatypes.String).apply_to(prop)
        assert prop.value is None

    def test_property_value_converts_timedelta_to_relativedelta(self):
        """timedelta 값은 `timedelta_to_relativedelta`로 변환되어 기록된다."""
        prop = make_property(value_type=model.datatypes.Duration)
        with patch(
            "mdtpy.value.element_value.timedelta_to_relativedelta",
            return_value="converted",
        ) as m_conv:
            PropertyValue(timedelta(seconds=5), model.datatypes.Duration).apply_to(prop)
        m_conv.assert_called_once()
        assert prop.value == "converted"

    def test_property_value_rejects_non_property(self):
        with pytest.raises(ValueError, match="PropertyValue can only be applied to Property"):
            PropertyValue(1, model.datatypes.Int).apply_to(make_file())

    # -- FileValue ------------------------------------------------------- #
    def test_file_value_applies(self):
        f = make_file()
        FileValue("image/png", "x.png").apply_to(f)
        assert f.content_type == "image/png"
        assert f.value == "x.png"

    def test_file_value_rejects_non_file(self):
        with pytest.raises(ValueError, match="FileValue can only be applied to File"):
            FileValue("image/png", "x.png").apply_to(make_property())

    # -- RangeValue ------------------------------------------------------ #
    def test_range_value_applies(self):
        r = make_range()
        RangeValue(0, 100, model.datatypes.Int).apply_to(r)
        assert r.min == 0
        assert r.max == 100

    def test_range_value_rejects_non_range(self):
        with pytest.raises(ValueError, match="RangeValue can only be applied to Range"):
            RangeValue(0, 100, model.datatypes.Int).apply_to(make_property())

    # -- MLPropertyValue ------------------------------------------------- #
    def test_mlproperty_value_applies(self):
        m = make_mlp()
        MLPropertyValue([{"en": "hi"}, {"ko": "안녕"}]).apply_to(m)
        assert dict(m.value) == {"en": "hi", "ko": "안녕"}

    def test_mlproperty_value_rejects_non_mlp(self):
        with pytest.raises(
            ValueError, match="MLPropertyValue can only be applied to MultiLanguageProperty"
        ):
            MLPropertyValue([{"en": "hi"}]).apply_to(make_property())

    # -- ElementCollectionValue ------------------------------------------ #
    def test_collection_recurses_into_members(self):
        a = make_property(id_short="a", value_type=model.datatypes.Int)
        b = make_property(id_short="b", value_type=model.datatypes.Int)
        smc = make_smc([a, b])
        ElementCollectionValue({
            "a": PropertyValue(1, model.datatypes.Int),
            "b": PropertyValue(2, model.datatypes.Int),
        }).apply_to(smc)
        assert a.value == 1
        assert b.value == 2

    def test_collection_skips_members_without_matching_value(self):
        a = make_property(id_short="a", value="orig-a", value_type=model.datatypes.String)
        b = make_property(id_short="b", value="orig-b", value_type=model.datatypes.String)
        smc = make_smc([a, b])
        ElementCollectionValue({
            "a": PropertyValue("new-a", model.datatypes.String),
        }).apply_to(smc)  # 'b' 누락
        assert a.value == "new-a"
        assert b.value == "orig-b"

    def test_collection_rejects_non_collection(self):
        with pytest.raises(
            ValueError, match="ElementCollectionValue can only be applied to SubmodelElementCollection"
        ):
            ElementCollectionValue({}).apply_to(make_property())

    def test_collection_member_type_mismatch_raises(self):
        """멤버 값과 SME 멤버의 종류가 다르면 해당 멤버의 apply_to 에서 ValueError."""
        a = make_property(id_short="a", value_type=model.datatypes.Int)
        smc = make_smc([a])
        with pytest.raises(ValueError, match="FileValue can only be applied to File"):
            ElementCollectionValue({"a": FileValue("t", "x")}).apply_to(smc)

    # -- ElementListValue ------------------------------------------------ #
    def test_list_zips_values_by_position(self):
        a = make_property(value_type=model.datatypes.Int)
        b = make_property(value_type=model.datatypes.Int)
        sml = make_sml([a, b])
        ElementListValue([
            PropertyValue(10, model.datatypes.Int),
            PropertyValue(20, model.datatypes.Int),
        ]).apply_to(sml)
        assert a.value == 10
        assert b.value == 20

    def test_list_rejects_non_list(self):
        with pytest.raises(
            ValueError, match="ElementListValue can only be applied to SubmodelElementList"
        ):
            ElementListValue([]).apply_to(make_property())


# --------------------------------------------------------------------------- #
# from_raw_json_node  (bare wire 포맷 → ElementValue)
# --------------------------------------------------------------------------- #

class TestFromJsonObject:
    def test_none_value_with_property_proto_returns_none_property(self):
        # value 가 None 이면 Property proto 에 대해서만 허용되며 값이 None 인 PropertyValue 를 반환한다.
        result = from_raw_json_node(None, PropertyValue(None, model.datatypes.Int))
        assert isinstance(result, PropertyValue) and result.value is None

    def test_property_string_value_uses_xsd_parse(self):
        proto = PropertyValue(None, model.datatypes.Int)
        with patch(
            "mdtpy.value.model.datatypes.from_xsd",
            return_value=42,
        ) as m_from_xsd:
            result = from_raw_json_node("42", proto)
        m_from_xsd.assert_called_once_with("42", model.datatypes.Int)
        assert result == PropertyValue(42, model.datatypes.Int)

    def test_property_non_string_value_passes_through(self):
        proto = PropertyValue(None, model.datatypes.Int)
        # 이미 native 값인 경우 from_xsd를 거치지 않는다
        assert from_raw_json_node(42, proto) == PropertyValue(42, model.datatypes.Int)

    def test_collection_parses_each_member(self):
        proto = ElementCollectionValue({
            "a": PropertyValue(None, model.datatypes.Int),
            "b": PropertyValue(None, model.datatypes.Int),
        })
        with patch(
            "mdtpy.value.model.datatypes.from_xsd",
            side_effect=lambda v, t: int(v),
        ):
            result = from_raw_json_node({"a": "1", "b": "2"}, proto)
        assert isinstance(result, ElementCollectionValue)
        assert result == {"a": PropertyValue(1, model.datatypes.Int),
                          "b": PropertyValue(2, model.datatypes.Int)}

    def test_list_zips_with_proto_members(self):
        proto = ElementListValue([
            PropertyValue(None, model.datatypes.Int),
            PropertyValue(None, model.datatypes.Int),
        ])
        with patch(
            "mdtpy.value.model.datatypes.from_xsd",
            side_effect=lambda v, t: int(v),
        ):
            result = from_raw_json_node(["10", "20"], proto)
        assert isinstance(result, ElementListValue)
        assert result == [PropertyValue(10, model.datatypes.Int),
                          PropertyValue(20, model.datatypes.Int)]

    def test_file_maps_content_type_camelcase_to_snake_case(self):
        proto = FileValue(content_type="application/octet-stream", value=None)
        result = from_raw_json_node(
            {"contentType": "image/png", "value": "x.png"}, proto
        )
        assert result == FileValue(content_type="image/png", value="x.png")

    def test_range_parses_min_and_max_via_xsd(self):
        proto = RangeValue(min=None, max=None, value_type=model.datatypes.Int)
        with patch(
            "mdtpy.value.model.datatypes.from_xsd",
            side_effect=lambda v, t: int(v),
        ):
            result = from_raw_json_node({"min": "0", "max": "10"}, proto)
        assert result == RangeValue(min=0, max=10, value_type=model.datatypes.Int)

    def test_multilang_property_reads_list(self):
        # to_raw_json_node 의 출력과 같은 [{lang: text}, ...] 리스트를 받는다.
        proto = MLPropertyValue([])
        result = from_raw_json_node([{"en": "hello"}, {"ko": "안녕"}], proto)
        assert isinstance(result, MLPropertyValue)
        assert result == [{"en": "hello"}, {"ko": "안녕"}]

    def test_multilang_property_round_trips(self):
        original = MLPropertyValue([{"en": "hello"}, {"ko": "안녕"}])
        wire = original.to_raw_json_node()
        assert from_raw_json_node(wire, MLPropertyValue([])) == original

    def test_unknown_proto_type_raises(self):
        unknown = MagicMock(spec=ElementValue)
        with pytest.raises(NotImplementedError):
            from_raw_json_node("anything", unknown)


# --------------------------------------------------------------------------- #
# from_raw_object  (원시 Python 값 → ElementValue, to_raw_object 의 역방향)
# --------------------------------------------------------------------------- #

class TestFromRawObject:
    def test_property_none_returns_none_property(self):
        # value 가 None 이면 Property proto 에 대해서만 허용되며 값이 None 인 PropertyValue 를 반환한다.
        result = from_raw_object(None, make_property())
        assert isinstance(result, PropertyValue) and result.value is None

    def test_property_wraps_native_without_from_xsd(self):
        proto = make_property(value_type=model.datatypes.Int)
        with patch("mdtpy.value.model.datatypes.from_xsd") as m_from_xsd:
            result = from_raw_object(3, proto)
        m_from_xsd.assert_not_called()
        assert result == PropertyValue(3, model.datatypes.Int)

    def test_file_reads_snake_case(self):
        proto = make_file()
        result = from_raw_object({"content_type": "image/png", "value": "x.png"}, proto)
        assert result == FileValue("image/png", "x.png")

    def test_file_camelcase_is_rejected(self):
        # from_raw_json_node 와 달리 camelCase(contentType)는 받지 않는다.
        proto = make_file()
        with pytest.raises(AssertionError, match="content_type is required"):
            from_raw_object({"contentType": "image/png", "value": "x.png"}, proto)

    def test_range_wraps_native_without_from_xsd(self):
        proto = make_range(value_type=model.datatypes.Int)
        with patch("mdtpy.value.model.datatypes.from_xsd") as m_from_xsd:
            result = from_raw_object({"min": 0, "max": 10}, proto)
        m_from_xsd.assert_not_called()
        assert result == RangeValue(0, 10, model.datatypes.Int)

    def test_mlp_reads_list(self):
        proto = make_mlp()
        result = from_raw_object([{"en": "hello"}, {"ko": "안녕"}], proto)
        assert result == MLPropertyValue([{"en": "hello"}, {"ko": "안녕"}])

    def test_collection_recurses_over_members(self):
        a = make_property(id_short="a", value_type=model.datatypes.Int)
        b = make_property(id_short="b", value_type=model.datatypes.Int)
        proto = make_smc([a, b])
        result = from_raw_object({"a": 1, "b": 2}, proto)
        assert isinstance(result, ElementCollectionValue)
        assert result == {"a": PropertyValue(1, model.datatypes.Int),
                          "b": PropertyValue(2, model.datatypes.Int)}

    def test_list_zips_with_proto_value(self):
        a = make_property(value_type=model.datatypes.Int)
        b = make_property(value_type=model.datatypes.Int)
        proto = make_sml([a, b])
        result = from_raw_object([10, 20], proto)
        assert isinstance(result, ElementListValue)
        assert result == [PropertyValue(10, model.datatypes.Int),
                          PropertyValue(20, model.datatypes.Int)]

    def test_unknown_proto_type_raises(self):
        unknown = MagicMock(spec=model.SubmodelElement)
        with pytest.raises(NotImplementedError):
            from_raw_object("x", unknown)

    def test_round_trips_with_to_raw(self):
        # ev.to_raw_object() 를 되돌리면 원래 ElementValue 와 같아진다 (스칼라/컨테이너).
        proto = make_smc([make_property(id_short="q", value_type=model.datatypes.Int)])
        ev = ElementCollectionValue({"q": PropertyValue(7, model.datatypes.Int)})
        assert from_raw_object(ev.to_raw_object(), proto) == ev


# --------------------------------------------------------------------------- #
# polymorphic JSON (@type/value) 직렬화/역직렬화
# --------------------------------------------------------------------------- #

from datetime import datetime
from decimal import Decimal


class TestToJsonNode:
    """ElementValue → @type/value JSON 직렬화."""

    def test_property_string(self):
        node = PropertyValue("IDLE", model.datatypes.String).to_json_node()
        assert node == {"@type": "mdt:value:string", "value": "IDLE"}

    def test_property_integer_inferred_when_value_type_none(self):
        # value_type 이 None 이면 런타임 타입으로부터 @type 을 추론한다.
        node = PropertyValue(42, None).to_json_node()
        assert node == {"@type": "mdt:value:integer", "value": 42}

    def test_property_long_uses_value_type(self):
        node = PropertyValue(42, model.datatypes.Long).to_json_node()
        assert node == {"@type": "mdt:value:long", "value": 42}

    def test_property_boolean(self):
        node = PropertyValue(True, model.datatypes.Boolean).to_json_node()
        assert node == {"@type": "mdt:value:boolean", "value": True}

    def test_property_datetime_is_xsd_string(self):
        dt = model.datatypes.from_xsd("2020-01-02T03:04:05", model.datatypes.DateTime)
        node = PropertyValue(dt, model.datatypes.DateTime).to_json_node()
        assert node == {"@type": "mdt:value:dateTime", "value": "2020-01-02T03:04:05"}

    def test_property_decimal_is_xsd_string(self):
        node = PropertyValue(Decimal("12.34"), model.datatypes.Decimal).to_json_node()
        assert node == {"@type": "mdt:value:decimal", "value": "12.34"}

    def test_file(self):
        node = FileValue("image/png", "img.png").to_json_node()
        assert node == {"@type": "mdt:value:file",
                        "value": {"contentType": "image/png", "value": "img.png"}}

    def test_range_with_vtype(self):
        node = RangeValue(0, 10, model.datatypes.Int).to_json_node()
        assert node == {"@type": "mdt:value:range",
                        "value": {"vtype": "INT", "min": 0, "max": 10}}

    def test_mlproperty_is_list_of_lang_maps(self):
        node = MLPropertyValue([{"en": "hello"}, {"ko": "안녕"}]).to_json_node()
        assert node == {"@type": "mdt:value:mlprop",
                        "value": [{"en": "hello"}, {"ko": "안녕"}]}

    def test_collection_members_are_nested_polymorphic(self):
        coll = ElementCollectionValue({"q": PropertyValue(100, model.datatypes.Int)})
        node = coll.to_json_node()
        assert node == {"@type": "mdt:value:collection",
                        "value": {"q": {"@type": "mdt:value:integer", "value": 100}}}

    def test_list_members_are_nested_polymorphic(self):
        lst = ElementListValue([PropertyValue(1, model.datatypes.Int)])
        node = lst.to_json_node()
        assert node == {"@type": "mdt:value:list",
                        "value": [{"@type": "mdt:value:integer", "value": 1}]}

    def test_unsupported_property_type_raises(self):
        # 지원하지 않는 XSD 타입(예: xs:date)은 ValueError 를 발생시킨다.
        from datetime import date
        with pytest.raises(ValueError, match="unsupported property value type"):
            PropertyValue(date(2020, 1, 1), model.datatypes.Date).to_json_node()


class TestToRawJsonNode:
    """ElementValue → 타입 태그 없는 bare wire JSON 직렬화 (@type 미포함)."""

    def test_property_is_xsd_string_repr(self):
        # to_json_node 와 달리 스칼라도 XSD 문자열로 인코딩한다.
        assert PropertyValue(42, model.datatypes.Int).to_raw_json_node() == "42"
        assert PropertyValue(True, model.datatypes.Boolean).to_raw_json_node() == "true"

    def test_property_none_returns_none(self):
        assert PropertyValue(None, model.datatypes.Int).to_raw_json_node() is None

    def test_file(self):
        node = FileValue("image/png", "img.png").to_raw_json_node()
        assert node == {"contentType": "image/png", "value": "img.png"}

    def test_range_omits_vtype(self):
        node = RangeValue(0, 10, model.datatypes.Int).to_raw_json_node()
        assert node == {"min": "0", "max": "10"}

    def test_mlproperty_is_list(self):
        node = MLPropertyValue([{"en": "hello"}, {"ko": "안녕"}]).to_raw_json_node()
        assert node == [{"en": "hello"}, {"ko": "안녕"}]

    def test_collection_skips_none_members(self):
        coll = ElementCollectionValue({
            "q": PropertyValue(100, model.datatypes.Int),
            "n": None,
        })
        assert coll.to_raw_json_node() == {"q": "100"}


class TestParseJsonNode:
    """@type/value JSON → ElementValue 역직렬화."""

    def test_property_string(self):
        ev = parse_json_node({"@type": "mdt:value:string", "value": "IDLE"})
        assert ev == PropertyValue("IDLE", model.datatypes.String)

    def test_property_integer(self):
        ev = parse_json_node({"@type": "mdt:value:integer", "value": 42})
        assert ev == PropertyValue(42, model.datatypes.Int)

    def test_property_datetime(self):
        ev = parse_json_node({"@type": "mdt:value:dateTime", "value": "2020-01-02T03:04:05"})
        assert ev == PropertyValue(datetime(2020, 1, 2, 3, 4, 5), model.datatypes.DateTime)

    def test_property_decimal(self):
        ev = parse_json_node({"@type": "mdt:value:decimal", "value": "12.34"})
        assert ev == PropertyValue(Decimal("12.34"), model.datatypes.Decimal)

    def test_file(self):
        ev = parse_json_node({"@type": "mdt:value:file",
                              "value": {"contentType": "image/png", "value": "img.png"}})
        assert ev == FileValue("image/png", "img.png")

    def test_range(self):
        ev = parse_json_node({"@type": "mdt:value:range",
                              "value": {"vtype": "INT", "min": 0, "max": 10}})
        assert ev == RangeValue(0, 10, model.datatypes.Int)

    def test_mlproperty(self):
        ev = parse_json_node({"@type": "mdt:value:mlprop",
                              "value": [{"en": "hello"}, {"ko": "안녕"}]})
        assert ev == MLPropertyValue([{"en": "hello"}, {"ko": "안녕"}])

    def test_collection(self):
        ev = parse_json_node({"@type": "mdt:value:collection",
                              "value": {"q": {"@type": "mdt:value:integer", "value": 100}}})
        assert ev == ElementCollectionValue({"q": PropertyValue(100, model.datatypes.Int)})

    def test_list(self):
        ev = parse_json_node({"@type": "mdt:value:list",
                              "value": [{"@type": "mdt:value:integer", "value": 1}]})
        assert ev == ElementListValue([PropertyValue(1, model.datatypes.Int)])

    def test_missing_type_field_raises(self):
        with pytest.raises(ValueError, match="@type"):
            parse_json_node({"value": 1})

    def test_unregistered_type_raises(self):
        with pytest.raises(ValueError, match="Unregistered ElementValue type"):
            parse_json_node({"@type": "mdt:value:bogus", "value": 1})

    def test_parse_json_string(self):
        ev = parse_json_string('{"@type": "mdt:value:integer", "value": 7}')
        assert ev == PropertyValue(7, model.datatypes.Int)


class TestJsonRoundTrip:
    """to_json_node → parse_json_node 왕복."""

    def test_nested_collection_round_trip(self):
        original = ElementCollectionValue({
            "list": ElementListValue([PropertyValue("a", model.datatypes.String)]),
            "file": FileValue("text/plain", "x.txt"),
            "range": RangeValue(0, 5, model.datatypes.Int),
        })
        assert parse_json_node(original.to_json_node()) == original
        assert parse_json_string(original.to_json_string()) == original
