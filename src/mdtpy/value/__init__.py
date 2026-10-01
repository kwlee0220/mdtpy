from __future__ import annotations

from typing import Optional, cast
from datetime import timedelta

from basyx.aas import model
from basyx.aas.model import datatypes

from ..utils import timedelta_to_relativedelta
from .types import (
    PropertyValueType, ListValueType, CollectionValueType, RawMLPropertyValue,
    RawElementValueType, PropertyJsonValue, ListJsonValueType, CollectionJsonValueType,
    ElementJsonValueType, MultiLanguagePropertyJsonValue, FileJsonValue,
)
from .element_value import (
    ElementValue, PropertyValue, FileValue, RangeValue, MLPropertyValue,
    ElementCollectionValue, ElementListValue, mdt_value,
)
from .factory import (
    get_value, from_raw_object, from_raw_json_node, parse_json_node, parse_json_string,
)


# --------------------------------------------------------------------------- #
# 헬퍼 함수
# --------------------------------------------------------------------------- #

def update_element_with_raw_value(
    sme: model.SubmodelElement,
    value: Optional[RawElementValueType],
) -> None:
    """
    SubmodelElement 객체의 값을 주어진 원시 Python 값으로 변경한다.

    `value`는 스칼라/dict/list 형태의 원시 Python 값이며, File/MLP 는 Python 측
    포맷(snake_case dict / 평탄 dict)을 그대로 받는다. SME 타입별 동작은 `get_value`
    의 역방향이며, 컨테이너형(SMC/SML)은 재귀적으로 멤버를 갱신한다.

    Property 값이 `timedelta`이면 relativedelta 로 변환하여 설정한다. `value`가 `None`
    이면, Property 는 값을 `None`으로 설정하지만 컨테이너/File/Range/MLP 는 `ValueError`
    를 발생시킨다.

    Args:
        sme (model.SubmodelElement): 값을 변경할 SubmodelElement 객체.
        value (Optional[RawElementValueType]): 변경할 원시 Python 값.
    Raises:
        ValueError: Property 가 아닌 SME 에 `None`을 전달한 경우.
        NotImplementedError: 지원되지 않는 SubmodelElement 타입인 경우.
    """
    if isinstance(sme, model.Property):
        match value:
            case None:
                sme.value = None
            case timedelta():
                sme.value = timedelta_to_relativedelta(value)
            case bool():
                # bool 은 int 의 하위 타입이므로 int/float 분기보다 먼저 처리한다.
                sme.value = value
            case str() if sme.value_type is not None:
                # "12.0" 같은 XSD 리터럴 문자열을 Property 가 선언한 value_type 으로 파싱한다.
                # (basyx 의 trivial_cast 는 str -> Float 를 거부하므로 from_xsd 로 파싱한다.)
                sme.value = datatypes.from_xsd(value, sme.value_type)
            case (int() | float()) if sme.value_type is not None:
                # JSON 전송 과정에서 float 12.0 이 int 12 로 뭉개진 경우에도
                # value_type(xs:float 등)에 맞춰 캐스팅한다.
                sme.value = sme.value_type(value)
            case _:
                sme.value = value
        return

    if value is None:
        raise ValueError("SubmodelElementCollection value cannot be None")
    match sme:
        case model.SubmodelElementCollection():
            assert isinstance(value, dict)
            for member in sme.value:
                member_value = value.get(str(member.id_short))
                update_element_with_raw_value(member, member_value)
        case model.SubmodelElementList():
            assert isinstance(value, list)
            for member, member_value in zip(sme.value, value):
                update_element_with_raw_value(member, member_value)
        case model.File():
            assert isinstance(value, dict), f"FileValue must be a dict like {{'content_type': str, 'value': str}}, got: {value}"
            sme.content_type = cast(model.ContentType, value.get('content_type'))
            assert sme.content_type is not None, "content_type is required"
            sme.value = cast(Optional[model.PathType], value.get('value'))
        case model.Range():
            assert isinstance(value, dict), f"RangeValue must be a dict: {value}"
            sme.min = cast(Optional[model.ValueDataType], value.get('min'))
            sme.max = cast(Optional[model.ValueDataType], value.get('max'))
        case model.MultiLanguageProperty():
            assert isinstance(value, dict), f"MultiLanguagePropertyValue must be a dict: {value}"
            sme.value = model.MultiLanguageTextType(cast(dict[str, str], value))
        case _:
            raise NotImplementedError(f"Unknown SubmodelElement type: {type(sme)}")
