from __future__ import annotations

import json
from typing import Any, Optional, cast
from collections.abc import Mapping

from basyx.aas import model

from .types import ElementJsonValueType, RawElementValueType, PropertyValueType
from .codec import (
    FIELD_TYPE, FIELD_VALUE, TYPE_COLLECTION, TYPE_LIST, TYPE_FILE, TYPE_RANGE, TYPE_MLPROP,
    _MDT_TYPE_TO_XSD, _VTYPE_NAME_TO_XSD, _decode_scalar,
)
from .element_value import (
    ElementValue, PropertyValue, FileValue, RangeValue, MLPropertyValue,
    ElementCollectionValue, ElementListValue,
)


# --------------------------------------------------------------------------- #
# ElementValue 생성(역직렬화) 팩토리.
#
# JSON / 원시 Python 값 / SME 를 :class:`ElementValue` 로 되돌리는 진입점을 한 곳에
# 모은다. 직렬화(ElementValue → 표현)는 각 ElementValue 의 to_* 메서드가 담당한다.
# --------------------------------------------------------------------------- #


def get_value(sme: model.SubmodelElement) -> ElementValue:
    """
    SubmodelElement 객체의 값을 :class:`ElementValue` 형태로 반환한다.

    SME 타입별 반환 형태:
        - Property                       → PropertyValue
        - SubmodelElementCollection      → ElementCollectionValue
        - SubmodelElementList            → ElementListValue
        - File                           → FileValue
        - Range                          → RangeValue
        - MultiLanguageProperty          → MLPropertyValue (값이 없으면 예외 발생)

    Args:
        sme (model.SubmodelElement): 값을 얻어올 SubmodelElement 객체.
    Returns:
        ElementValue: SubmodelElement 객체의 값.
    Raises:
        NotImplementedError: 지원되지 않는 SubmodelElement 타입인 경우.
    """
    assert sme is not None
    match sme:
        case model.Property():
            return PropertyValue(sme.value, sme.value_type)
        case model.SubmodelElementCollection():
            return ElementCollectionValue(
                {str(member.id_short): get_value(member) for member in sme.value}
            )
        case model.SubmodelElementList():
            return ElementListValue([get_value(member) for member in sme.value])
        case model.File():
            return FileValue(sme.content_type, sme.value)
        case model.Range():
            return RangeValue(sme.min, sme.max, sme.value_type)
        case model.MultiLanguageProperty():
            if sme.value is None:
                raise ValueError("MultiLanguageProperty value is None")
            value = [{lang: text} for lang, text in sme.value.items()]
            return MLPropertyValue(value)
        case _:
            raise NotImplementedError(f"Unknown SubmodelElement type: {type(sme)}")


def from_raw_object(
    value: Optional[RawElementValueType],
    proto: model.SubmodelElement,
) -> ElementValue:
    """원시 Python 값(스칼라/dict/list)을 :class:`ElementValue` 로 역직렬화한다.

    :meth:`ElementValue.to_raw_object` 의 역방향이다. `proto`는 변환에 필요한 타입
    메타데이터(Property의 value_type, SMC의 멤버 SME 등)를 제공하는 SubmodelElement 다.
    입력이 이미 native 타입이므로 XSD 문자열 디코딩은 거치지 않는다.

    ``value`` 가 ``None`` 인 경우는 ``proto`` 가 Property 일 때만 허용되며, 값이 ``None``
    인 :class:`PropertyValue` 를 반환한다. 그 외 타입의 ``proto`` 에는 ``None`` 을 전달할
    수 없다.

    Args:
        value (Optional[RawElementValueType]): 변환할 원시 Python 값.
        proto (model.SubmodelElement): 매핑 기준이 되는 SubmodelElement.
    Returns:
        ElementValue: 역직렬화된 ElementValue.
    Raises:
        NotImplementedError: 지원되지 않는 SubmodelElement 타입인 경우.
    """
    if isinstance(proto, model.Property):
        return PropertyValue(cast(model.ValueDataType, value), proto.value_type)
    assert value is not None, "value is required for non-Property"

    match proto:
        case model.SubmodelElementCollection():
            assert isinstance(value, dict)
            parsed_value = dict[str, Optional[ElementValue]]()
            for member in proto.value:
                key = str(member.id_short)
                member_value = value.get(key)
                parsed_value[key] = (
                    from_raw_object(member_value, member)
                    if member_value is not None
                    else None
                )
            return ElementCollectionValue(parsed_value)
        case model.SubmodelElementList():
            assert isinstance(value, list)
            return ElementListValue([
                from_raw_object(member_value, member)
                for member, member_value in zip(proto.value, value)
            ])
        case model.File():
            assert isinstance(value, dict)
            ct, v = value.get('content_type'), value.get('value')
            assert ct is not None, "content_type is required"
            return FileValue(cast(str, ct), cast(Optional[str], v))
        case model.Range():
            assert isinstance(value, dict)
            return RangeValue(cast(Optional[model.ValueDataType], value.get('min')),
                              cast(Optional[model.ValueDataType], value.get('max')),
                              proto.value_type)
        case model.MultiLanguageProperty():
            assert isinstance(value, list)
            return MLPropertyValue(cast(list[dict[str, str]], value))
        case _:
            raise NotImplementedError(f"Unknown SubmodelElement type: {type(proto)}")


def from_raw_json_node(
    value: Optional[ElementJsonValueType],
    proto: ElementValue,
) -> ElementValue:
    """bare wire 포맷(``@type`` 없는 JSON) 값을 :class:`ElementValue` 로 역직렬화한다.

    :meth:`ElementValue.to_raw_json_node` 의 역방향이다. `proto`는 변환의 기준이 되는
    :class:`ElementValue` 로, 필요한 타입 메타데이터(Property/Range 의 value_type,
    컬렉션/리스트의 멤버 구조 등)를 제공한다.

    ``value`` 가 ``None`` 인 경우는 ``proto`` 가 :class:`PropertyValue` 일 때만 허용되며,
    값이 ``None`` 인 :class:`PropertyValue` 를 반환한다. 그 외 타입의 ``proto`` 에는
    ``None`` 을 전달할 수 없다.

    Args:
        value (Optional[ElementJsonValueType]): bare wire 포맷의 JSON 값.
        proto (ElementValue): 매핑 기준이 되는 ElementValue.
    Returns:
        ElementValue: 역직렬화된 ElementValue.
    Raises:
        NotImplementedError: 지원되지 않는 ElementValue 타입인 경우.
    """
    if isinstance(proto, PropertyValue):
        if value is None:
            return PropertyValue(None, proto.value_type)
        else:
            if isinstance(value, str):
                return PropertyValue(
                    cast(model.ValueDataType, model.datatypes.from_xsd(value, proto.value_type)),
                    proto.value_type
                )
            else:
                return PropertyValue(cast(model.ValueDataType, value), proto.value_type)
    assert value is not None, "value is required for non-PropertyValue"

    match proto:
        case ElementCollectionValue():
            assert isinstance(value, dict)
            parsed_value = dict[str, Optional[ElementValue]]()
            for key, member_proto in proto.items():
                member_value = value.get(key)
                parsed_value[key] = (
                    from_raw_json_node(member_value, member_proto)
                    if member_value is not None and member_proto is not None
                    else None
                )
            return ElementCollectionValue(parsed_value)
        case ElementListValue():
            assert isinstance(value, list)
            return ElementListValue([
                from_raw_json_node(member_value, member_proto)
                for member_proto, member_value in zip(proto, value)
            ])
        case FileValue():
            assert isinstance(value, dict)
            ct, v = value.get('contentType'), value.get('value')
            assert ct is not None, "contentType is required"
            return FileValue(cast(str, ct), cast(Optional[str], v))
        case RangeValue():
            assert isinstance(value, dict)
            min = cast(str, value.get('min'))
            min = model.datatypes.from_xsd(min, proto.value_type) if min is not None else None
            max = cast(str, value.get('max'))
            max = model.datatypes.from_xsd(max, proto.value_type) if max is not None else None
            return RangeValue(cast(Optional[model.ValueDataType], min),
                              cast(Optional[model.ValueDataType], max),
                              proto.value_type)
        case MLPropertyValue():
            # [{언어: 텍스트}, ...] 단일-엔트리 dict 리스트.
            # (:meth:`MLPropertyValue.to_raw_json_node` 출력과 대칭)
            assert isinstance(value, list)
            return MLPropertyValue(cast(list[dict[str, str]], value))
        case _:
            raise NotImplementedError(f"Unknown ElementValue type: {type(proto)}")


def parse_json_node(jnode: Mapping[str, Any]) -> ElementValue:
    """``@type``/``value`` 형태의 polymorphic JSON 객체를 :class:`ElementValue` 로 역직렬화한다.

    Java 측 ``mdt.model.sm.value.ElementValues`` 직렬화 포맷과 호환되며, 값 스스로
    타입을 서술하므로 `proto` 가 필요 없다.

    :param jnode: ``@type`` 과 ``value`` 필드를 가진 JSON 객체(dict).
    :return: 역직렬화된 ElementValue.
    :raises ValueError: ``@type`` 필드가 없거나 등록되지 않은 타입인 경우.
    """
    mtype = jnode.get(FIELD_TYPE)
    if mtype is None:
        raise ValueError(f"'{FIELD_TYPE}' field is missing: json={jnode}")
    vnode = jnode.get(FIELD_VALUE)

    # Property 계열: @type 으로 XSD 타입을 판별하여 스칼라를 디코딩한다.
    xsd_name = _MDT_TYPE_TO_XSD.get(mtype)
    if xsd_name is not None:
        value_type: PropertyValueType = model.datatypes.XSD_TYPE_CLASSES.get(xsd_name)
        return PropertyValue(_decode_scalar(vnode, xsd_name), value_type)

    if mtype == TYPE_COLLECTION:
        assert isinstance(vnode, dict), f"collection value must be an object: {vnode}"
        members: dict[str, Optional[ElementValue]] = {
            key: (parse_json_node(field) if field is not None else None)
            for key, field in vnode.items()
        }
        return ElementCollectionValue(members)
    if mtype == TYPE_LIST:
        assert isinstance(vnode, list), f"list value must be an array: {vnode}"
        return ElementListValue([parse_json_node(elm) for elm in vnode])
    if mtype == TYPE_FILE:
        assert isinstance(vnode, dict), f"file value must be an object: {vnode}"
        ct = vnode.get('contentType')
        assert ct is not None, f"contentType is required: {vnode}"
        return FileValue(cast(str, ct), cast(Optional[str], vnode.get('value')))
    if mtype == TYPE_RANGE:
        assert isinstance(vnode, dict), f"range value must be an object: {vnode}"
        vname = vnode.get('vtype')
        rng_xsd = _VTYPE_NAME_TO_XSD.get(vname, vname) if vname is not None else 'xs:string'
        btype = model.datatypes.XSD_TYPE_CLASSES.get(rng_xsd)
        return RangeValue(_decode_scalar(vnode.get('min'), rng_xsd),
                          _decode_scalar(vnode.get('max'), rng_xsd), btype)
    if mtype == TYPE_MLPROP:
        assert isinstance(vnode, list), f"mlprop value must be an array: {vnode}"
        return MLPropertyValue(cast(list[dict[str, str]], vnode))

    raise ValueError(f"Unregistered ElementValue type: {mtype}")


def parse_json_string(json_str: str) -> ElementValue:
    """``@type``/``value`` 형태의 polymorphic JSON 문자열을 :class:`ElementValue` 로 역직렬화한다."""
    return parse_json_node(json.loads(json_str))
