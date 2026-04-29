from __future__ import annotations

from typing import TYPE_CHECKING, Union, Optional, TypedDict, cast
from collections.abc import Mapping

from datetime import timedelta
from pathlib import Path
from basyx.aas import model

from .utils import timedelta_to_relativedelta

if TYPE_CHECKING:
    from .reference import ElementReference


# --------------------------------------------------------------------------- #
# 타입 별칭
# --------------------------------------------------------------------------- #

ListValueType = list[Optional['ElementValueType']]
CollectionValueType = dict[str, Optional['ElementValueType']]

# Python 측에서 다루는 SubmodelElement 값의 표준 형태.
ElementValueType = Union[
    model.ValueDataType,
    'FileValue',
    'RangeValue',
    'MultiLanguagePropertyValue',
    ListValueType,
    CollectionValueType,
]

PropertyJsonValueType = Union[str, int, float, bool]
ListJsonValueType = list[Optional['ElementJsonValueType']]
CollectionJsonValueType = dict[str, Optional['ElementJsonValueType']]

# 서버 JSON wire 포맷에서 다루는 SubmodelElement 값의 형태.
ElementJsonValueType = Union[
    PropertyJsonValueType,
    'FileJsonValue',
    'RangeValue',
    'MultiLanguagePropertyValue',
    ListJsonValueType,
    CollectionJsonValueType,
]

# id_short → 값 매핑. Operation 입출력 인자 모음 등에 사용된다.
ElementValueDict = dict[str, Optional[ElementValueType]]


# --------------------------------------------------------------------------- #
# 합성 값 타입 (TypedDict)
# --------------------------------------------------------------------------- #

class FileValue(TypedDict):
    """File 형 SubmodelElement 값 (Python 측 표기, snake_case)."""
    content_type: str
    value: Optional[str]


class FileJsonValue(TypedDict):
    """File 형 SubmodelElement 값 (서버 wire 포맷, camelCase)."""
    contentType: str
    value: Optional[str]


class RangeValue(TypedDict):
    """Range 형 SubmodelElement 값 (min/max 쌍)."""
    min: Optional[model.ValueDataType]
    max: Optional[model.ValueDataType]


# 언어 코드 → 텍스트 매핑.
MultiLanguagePropertyValue = dict[str, str]
# 서버 wire 포맷: [{ lang: text }, ...] 형태의 리스트.
MultiLanguagePropertyJsonValue = list[dict[str, str]]


# --------------------------------------------------------------------------- #
# 헬퍼 함수
# --------------------------------------------------------------------------- #

def update_value_dict(
    target: ElementValueDict,
    new_values: Mapping[
        str,
        ElementValueType | 'ElementReference' | model.SubmodelElement | None,
    ],
) -> None:
    """
    `target` 값 매핑을 `new_values`로 덮어쓴다.

    `new_values`의 각 값은 다음 타입 중 하나를 받는다:
        - None                → target[key] = None
        - `ElementReference`  → 원격에서 read_value() 후 저장
        - `SubmodelElement`   → `get_value(sme)` 결과 저장
        - 그 외(원시 값)      → 그대로 저장

    `target`에 없는 키는 무시한다.

    Args:
        target (ElementValueDict): 갱신될 매핑.
        new_values: 새로운 값들의 매핑.
    """
    from .reference import ElementReference
    for key, new_value in new_values.items():
        if key not in target:
            continue
        if new_value is None:
            target[key] = None
        elif isinstance(new_value, ElementReference):
            target[key] = new_value.read_value()
        elif isinstance(new_value, model.SubmodelElement):
            target[key] = get_value(new_value)
        else:
            target[key] = new_value


def to_file_value(path: str, content_type: Optional[str] = None) -> FileValue:
    """
    파일 경로로부터 `FileValue` TypedDict를 만든다.

    `content_type`이 주어지지 않으면 Tika가 파일을 읽어 MIME type을
    추정한다 (Tika 서버 또는 로컬 모드 의존).

    Args:
        path (str): 파일 경로.
        content_type (Optional[str]): 명시적 MIME type.
            None이면 Tika로 자동 추정.
    Returns:
        FileValue: `{'content_type': str, 'value': <파일명>}`.
    """
    if content_type is None:
        from tika import parser
        parsed = parser.from_file(path)
        mime_type = parsed["metadata"]["Content-Type"]  # type: ignore
    else:
        mime_type = content_type
    return {'content_type': mime_type, 'value': Path(path).name}


def get_value(sme: model.SubmodelElement) -> Optional[ElementValueType]:
    """
    SubmodelElement 객체의 값을 Python 표준 표기로 반환한다.

    SME 타입별 반환 형태:
        - Property                       → ValueDataType (int/float/str/bool 등)
        - SubmodelElementCollection      → dict[id_short, value]
        - SubmodelElementList            → list[value]
        - File                           → FileValue {'content_type', 'value'}
        - Range                          → RangeValue {'min', 'max'}
        - MultiLanguageProperty          → MultiLanguagePropertyValue {lang: text}

    Args:
        sme (model.SubmodelElement): 값을 얻어올 SubmodelElement 객체.
    Returns:
        Optional[ElementValueType]: SubmodelElement 객체의 값.
    Raises:
        NotImplementedError: 지원되지 않는 SubmodelElement 타입인 경우.
    """
    assert sme is not None
    match sme:
        case model.Property():
            return sme.value
        case model.SubmodelElementCollection():
            return {str(member.id_short): get_value(member) for member in sme.value}
        case model.SubmodelElementList():
            return [get_value(member) for member in sme.value]
        case model.File():
            return {'content_type': sme.content_type, 'value': sme.value}
        case model.Range():
            return {'min': sme.min, 'max': sme.max}
        case model.MultiLanguageProperty():
            if sme.value is None:
                return None
            return {lang: text for lang, text in sme.value.items()}
        case _:
            raise NotImplementedError(f"Unknown SubmodelElement type: {type(sme)}")


def update_element_with_value(
    sme: model.SubmodelElement,
    value: Optional[ElementValueType],
) -> None:
    """
    SubmodelElement 객체의 값을 주어진 값으로 변경한다.

    `value`가 None이면 아무 일도 하지 않는다 (값을 명시적으로 None으로
    초기화하려면 호출자가 SME 종류별로 직접 설정해야 한다).

    SME 타입별 동작은 `get_value`의 역방향이며, 컨테이너형(SMC/SML)은
    재귀적으로 멤버를 갱신한다.

    Args:
        sme (model.SubmodelElement): 값을 변경할 SubmodelElement 객체.
        value (Optional[ElementValueType]): 변경할 값.
    Raises:
        NotImplementedError: 지원되지 않는 SubmodelElement 타입인 경우.
    """
    if value is None:
        return
    match sme:
        case model.Property():
            value = (
                timedelta_to_relativedelta(value)
                if value is not None and isinstance(value, timedelta)
                else value
            )
            sme.value = value
        case model.SubmodelElementCollection():
            assert isinstance(value, dict)
            for member in sme.value:
                member_value = value.get(str(member.id_short))
                if member_value is not None:
                    update_element_with_value(member, member_value)
        case model.SubmodelElementList():
            assert isinstance(value, list)
            for member, member_value in zip(sme.value, value):
                update_element_with_value(member, member_value)
        case model.File():
            assert isinstance(value, dict), f"FileValue must be a dict: {value}"
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


def from_json_object(
    value: Optional[ElementJsonValueType],
    proto: model.SubmodelElement,
) -> Optional[ElementValueType]:
    """
    서버 wire 포맷(JSON) 값을 Python 표준 ElementValueType으로 변환한다.

    `proto`는 매핑할 SubmodelElement 모델로, 변환에 필요한 메타데이터
    (Property의 value_type, SMC의 멤버 SME 등)를 제공한다.

    Args:
        value (Optional[ElementJsonValueType]): 서버에서 받은 JSON 값.
        proto (model.SubmodelElement): 매핑 기준이 되는 SubmodelElement.
    Returns:
        Optional[ElementValueType]: Python 표준 형태로 변환된 값.
    Raises:
        NotImplementedError: 지원되지 않는 SubmodelElement 타입인 경우.
    """
    if value is None:
        return None

    match proto:
        case model.Property():
            if isinstance(value, str):
                return cast(ElementValueType, model.datatypes.from_xsd(value, proto.value_type))
            else:
                return cast(model.ValueDataType, value)
        case model.SubmodelElementCollection():
            assert isinstance(value, dict)
            parsed_value = dict[str, Optional[ElementValueType]]()
            for member in proto.value:
                key = str(member.id_short)
                member_value = value.get(key)
                parsed_value[key] = (
                    from_json_object(member_value, member)
                    if member_value is not None
                    else None
                )
            return parsed_value
        case model.SubmodelElementList():
            assert isinstance(value, list)
            return [
                from_json_object(member_value, member)
                for member, member_value in zip(proto.value, value)
            ]
        case model.File():
            assert isinstance(value, dict)
            ct, v = value.get('contentType'), value.get('value')
            assert ct is not None, "contentType is required"
            return cast(FileValue, {'content_type': ct, 'value': v})
        case model.Range():
            assert isinstance(value, dict)
            min = cast(str, value.get('min'))
            min = model.datatypes.from_xsd(min, proto.value_type) if min is not None else None
            max = cast(str, value.get('max'))
            max = model.datatypes.from_xsd(max, proto.value_type) if max is not None else None
            return {'min': min, 'max': max}
        case model.MultiLanguageProperty():
            assert isinstance(value, list)  # MultiLanguagePropertyJsonValue
            value_list = cast(list[dict[str, str]], value)
            return cast(
                MultiLanguagePropertyValue,
                {lang: text for kv in value_list for lang, text in kv.items()},
            )
        case _:
            raise NotImplementedError(f"Unknown SubmodelElement type: {type(proto)}")


def to_json_object(
    value: Optional[ElementValueType],
    proto: model.SubmodelElement,
) -> Optional[ElementJsonValueType]:
    """
    Python 표준 ElementValueType 값을 서버 wire 포맷(JSON)으로 변환한다.

    `from_json_object`의 역방향. `proto`는 매핑할 SME 모델 (서버에 보낼
    값의 타입 정보 제공).

    Args:
        value (Optional[ElementValueType]): 변환할 Python 측 값.
        proto (model.SubmodelElement): 매핑 기준이 되는 SubmodelElement.
    Returns:
        Optional[ElementJsonValueType]: JSON 직렬화 가능한 값.
    Raises:
        NotImplementedError: 지원되지 않는 SubmodelElement 타입인 경우.
    """
    if value is None:
        return None

    match proto:
        case model.Property():
            assert isinstance(value, model.ValueDataType)
            return model.datatypes.xsd_repr(value)
        case model.SubmodelElementCollection():
            assert isinstance(value, dict)
            if proto.value is None:
                return None
            collection_json_value = dict[str, Optional[ElementJsonValueType]]()
            for member in proto.value:
                key = str(member.id_short)
                member_value = value.get(key)
                if member_value is not None:
                    collection_json_value[key] = to_json_object(member_value, member)
            return collection_json_value
        case model.SubmodelElementList():
            assert isinstance(value, list)
            return [
                to_json_object(member_value, member)
                for member, member_value in zip(proto.value, value)
            ]
        case model.File():
            assert isinstance(value, dict)
            return cast(
                FileJsonValue,
                {'contentType': value.get('content_type'), 'value': value.get('value')},
            )
        case model.Range():
            assert isinstance(value, dict)
            min = cast(Optional[model.ValueDataType], value.get('min'))
            min = model.datatypes.xsd_repr(min) if min is not None else None
            max = cast(Optional[model.ValueDataType], value.get('max'))
            max = model.datatypes.xsd_repr(max) if max is not None else None
            return {'min': min, 'max': max}
        case model.MultiLanguageProperty():
            assert isinstance(value, dict)
            return cast(MultiLanguagePropertyValue, {lang: text for lang, text in value.items()})
        case _:
            raise NotImplementedError(f"Unknown SubmodelElement type: {type(proto)}")
