from __future__ import annotations

from typing import Optional, TypedDict, TYPE_CHECKING, Union

from basyx.aas import model

if TYPE_CHECKING:
    from .element_value import ElementValue


# --------------------------------------------------------------------------- #
# 타입 별칭
# --------------------------------------------------------------------------- #

PropertyValueType = model.Type[model.datatypes.AnyXSDType]

# 원시(raw) Python 표현. ElementValue 래퍼를 제거한 형태로, 서버 wire 변환과
# 컨테이너 내부 표현에 사용된다.
ListValueType = list[Optional['RawElementValueType']]
CollectionValueType = dict[str, Optional['RawElementValueType']]

# [{언어코드: 텍스트}, ...] 형태의 단일-엔트리 dict 리스트.
RawMLPropertyValue = list[dict[str,str]]

RawElementValueType = Union[
    model.ValueDataType,
    RawMLPropertyValue,
    ListValueType,
    CollectionValueType,
]

# Python 측에서 다루는 SubmodelElement 값의 표준 형태.

PropertyJsonValue = Union[str, int, float, bool]
ListJsonValueType = list[Optional['ElementJsonValueType']]
CollectionJsonValueType = dict[str, Optional['ElementJsonValueType']]

# MLP wire 포맷: [{언어코드: 텍스트}, ...] 단일-엔트리 dict 리스트.
# (bare-wire 와 @type polymorphic 포맷 모두 동일한 이 형태를 사용한다)
MultiLanguagePropertyJsonValue = list[dict[str, str]]

# 서버 JSON wire 포맷에서 다루는 SubmodelElement 값의 형태.
ElementJsonValueType = Union[
    PropertyJsonValue,
    'FileJsonValue',
    MultiLanguagePropertyJsonValue,
    ListJsonValueType,
    CollectionJsonValueType,
]

class FileJsonValue(TypedDict):
    """File 형 SubmodelElement 값 (서버 wire 포맷, camelCase)."""
    contentType: str
    value: Optional[str]
