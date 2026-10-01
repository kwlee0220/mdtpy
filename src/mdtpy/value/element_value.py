from __future__ import annotations

import json
import mimetypes
from typing import Any, Optional, cast
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import timedelta
from pathlib import Path

from basyx.aas import model
from basyx.aas.model.datatypes import Integer, Float, Boolean, String, Duration

from ..utils import timedelta_to_relativedelta
from .types import (
    RawElementValueType, ElementJsonValueType, CollectionValueType, ListValueType,
    RawMLPropertyValue, FileJsonValue, PropertyJsonValue,
)
from .codec import (
    FIELD_TYPE, FIELD_VALUE, TYPE_FILE, TYPE_RANGE, TYPE_MLPROP, TYPE_COLLECTION, TYPE_LIST,
    _XSD_TO_MDT_TYPE, _XSD_TO_VTYPE_NAME, _xsd_name_of, _encode_scalar, _decode_scalar,
)


def mdt_value(value: PropertyJsonValue) -> PropertyValue:
    """원시 Python 표현으로부터 PropertyValue 객체를 생성한다.

    Args:
        value (PropertyJsonValue): 원시 Python 스칼라 값
            (str / bool / int / float / timedelta).
    Returns:
        PropertyValue: 생성된 PropertyValue 객체.
    Raises:
        ValueError: 지원되지 않는 값 타입인 경우.
    """
    match value:
        case str():
            return PropertyValue(value, String)
        case bool():
            return PropertyValue(value, Boolean)
        case int():
            return PropertyValue(value, Integer)
        case float():
            return PropertyValue(value, Float)
        case timedelta():
            return PropertyValue(timedelta_to_relativedelta(value), Duration)
        case _:
            raise ValueError(f"unsupported property value type: {type(value)}")


# --------------------------------------------------------------------------- #
# 값 클래스 (ElementValue 계층)
# --------------------------------------------------------------------------- #

class ElementValue(ABC):
    """SubmodelElement 값을 표현하는 클래스 계층의 추상 베이스.

    `get_value` / `read_value` 는 SME 종류에 따라 이 클래스의 서브클래스 객체를 반환한다.
    원시 Python 표현(스칼라/dict/list)이 필요하면 :meth:`to_raw_object` 로 변환한다.
    """

    @abstractmethod
    def to_json_node(self) -> dict[str, Any]:
        """``@type``/``value`` 형태의 polymorphic JSON 객체(dict)로 직렬화하여 반환한다.

        반환된 dict 는 값에 대한 JSON 표현(``value``)과 값의 종류를 식별하는 타입
        정보(``@type``)를 함께 담는다. :func:`parse_json_node` 로 역변환할 수 있다.
        """
        ...

    def to_json_string(self) -> str:
        """:meth:`to_json_node` 결과를 JSON 문자열로 직렬화하여 반환한다."""
        return json.dumps(self.to_json_node(), ensure_ascii=False)

    @abstractmethod
    def to_raw_json_node(self) -> Optional[ElementJsonValueType]:
        """타입 태그(``@type``) 없는 bare wire JSON 값으로 직렬화하여 반환한다.

        :meth:`to_json_node` 와 달리 값의 종류를 식별하는 메타데이터를 담지 않는
        범용 bare-wire 표현이다. 스칼라는 XSD 문자열 표현으로 인코딩하며,
        컨테이너(collection/list)의 멤버도 동일하게 중첩 직렬화한다.
        :func:`mdtpy.value.from_raw_json_node` 로 역변환할 수 있다.

        Note:
            현재 MDTInstanceManager 의 참조 값 경로는 이 형식이 아니라 ``@type``
            polymorphic 형식(:meth:`to_json_node`/:meth:`to_json_string`)을 사용한다.
        """
        ...

    @abstractmethod
    def to_raw_object(self) -> Optional[RawElementValueType]:
        """클래스 래퍼를 제거한 원시 Python 표현으로 (재귀적으로) 변환하여 반환한다.

        :func:`mdtpy.value.from_raw_object` 로 역변환할 수 있다.
        """
        ...

    @abstractmethod
    def apply_to(self, element: model.SubmodelElement) -> None:
        """이 값 객체를 ``element`` 에 적용한다.

        Args:
            element (model.SubmodelElement): 값을 적용할 SubmodelElement.
        Raises:
            ValueError: ``element`` 의 종류가 이 값 객체와 호환되지 않는 경우.
        """
        ...


class PropertyValue(ElementValue):
    """Property 형 SubmodelElement 값. 스칼라 값을 :attr:`value` 로 보유한다.

    :attr:`value_type` 는 값의 XSD 데이터 타입(basyx ``model.datatypes`` 의 타입 객체)으로,
    JSON 직렬화 시 ``@type`` 결정에 사용하는 필수 인자다. ``None`` 을 전달하면
    :meth:`to_json_node` 시점에 값의 런타임 타입으로부터 추론한다.
    """
    def __init__(self, value: Optional[model.ValueDataType],
                 value_type: model.base.DataTypeDefXsd) -> None:
        self.value = value
        self.value_type = value_type

    def to_raw_object(self) -> Optional[RawElementValueType]:
        return _decode_scalar(self.value, _xsd_name_of(self.value, self.value_type)) \
                if self.value is not None else None

    def apply_to(self, element: model.SubmodelElement) -> None:
        if not isinstance(element, model.Property):
            raise ValueError(
                f"PropertyValue can only be applied to Property: got {type(element).__name__}")

        raw = self.to_raw_object()
        if raw is None:
            # None은 기존 값의 타입으로 변환하지 않고 그대로 기록하여 값을 지운다.
            element.value = None
        elif isinstance(element.value, int):
            element.value = int(raw)  # type: ignore[assignment]
        elif isinstance(element.value, float):
            element.value = float(raw)  # type: ignore[assignment]
        elif isinstance(element.value, bool):
            element.value = bool(raw)  # type: ignore[assignment]
        elif isinstance(element.value, str):
            element.value = str(raw)  # type: ignore[assignment]
        elif isinstance(raw, timedelta):
            element.value = timedelta_to_relativedelta(raw)
        else:
            element.value = raw

    def to_json_node(self) -> dict[str, Any]:
        xsd_name = _xsd_name_of(self.value, self.value_type)
        mtype = _XSD_TO_MDT_TYPE.get(xsd_name)
        if mtype is None:
            raise ValueError(f"unsupported property value type: {xsd_name}")
        return {FIELD_TYPE: mtype, FIELD_VALUE: _encode_scalar(self.value, xsd_name)}

    def to_raw_json_node(self) -> Optional[ElementJsonValueType]:
        if self.value is None:
            return None
        return model.datatypes.xsd_repr(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PropertyValue) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"PropertyValue({self.value!r})"


class FileValue(ElementValue):
    """File 형 SubmodelElement 값. MIME 타입(:attr:`content_type`)과
    파일명(:attr:`value`)을 보유한다."""

    def __init__(self, content_type: str, value: Optional[str]) -> None:
        self.content_type = content_type
        self.value = value

    @classmethod
    def from_file_path(cls, path: str, content_type: Optional[str] = None) -> FileValue:
        """파일 경로로부터 FileValue 객체를 생성한다.

        Args:
            path (str): 파일 경로.
            content_type (Optional[str]): 파일의 MIME 타입. None이면 추론한다.
        Returns:
            FileValue: 생성된 FileValue 객체.
        """
        if content_type is None:
            guessed, _ = mimetypes.guess_type(path)
            mime_type = guessed or "application/octet-stream"
        else:
            mime_type = content_type
        return FileValue(content_type=mime_type, value=Path(path).name)

    def to_raw_object(self) -> CollectionValueType:
        return {'content_type': self.content_type, 'value': self.value}

    def apply_to(self, element: model.SubmodelElement) -> None:
        if not isinstance(element, model.File):
            raise ValueError(
                f"FileValue can only be applied to File: got {type(element).__name__}")
        assert self.content_type is not None, "content_type is required"
        element.content_type = cast(model.ContentType, self.content_type)
        element.value = cast(Optional[model.PathType], self.value)

    def to_json_node(self) -> dict[str, Any]:
        return {FIELD_TYPE: TYPE_FILE,
                FIELD_VALUE: {'contentType': self.content_type, 'value': self.value}}

    def to_raw_json_node(self) -> Optional[ElementJsonValueType]:
        return cast(FileJsonValue, {'contentType': self.content_type, 'value': self.value})

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, FileValue)
                and self.content_type == other.content_type
                and self.value == other.value)

    def __hash__(self) -> int:
        return hash((self.content_type, self.value))

    def __repr__(self) -> str:
        return f"FileValue(content_type={self.content_type!r}, value={self.value!r})"


class RangeValue(ElementValue):
    """Range 형 SubmodelElement 값. 최소(:attr:`min`)/최대(:attr:`max`) 쌍을 보유한다.

    :attr:`value_type` 는 min/max 의 XSD 데이터 타입(basyx ``model.datatypes`` 의 타입 객체)으로,
    JSON 직렬화 시 ``vtype`` 결정에 사용하는 필수 인자다. ``None`` 을 전달하면
    직렬화 시점에 min/max 값으로부터 추론한다.
    """

    def __init__(self, min: Optional[model.ValueDataType],
                 max: Optional[model.ValueDataType],
                 value_type: model.base.DataTypeDefXsd) -> None:
        self.min = min
        self.max = max
        self.value_type = value_type

    def to_raw_object(self) -> CollectionValueType:
        return {'min': self.min, 'max': self.max}

    def apply_to(self, element: model.SubmodelElement) -> None:
        if not isinstance(element, model.Range):
            raise ValueError(
                f"RangeValue can only be applied to Range: got {type(element).__name__}")
        element.min = cast(Optional[model.ValueDataType], self.min)
        element.max = cast(Optional[model.ValueDataType], self.max)

    def to_json_node(self) -> dict[str, Any]:
        ref_value = self.min if self.min is not None else self.max
        xsd_name = _xsd_name_of(ref_value, self.value_type)
        vname = _XSD_TO_VTYPE_NAME.get(xsd_name, 'STRING')
        return {FIELD_TYPE: TYPE_RANGE,
                FIELD_VALUE: {'vtype': vname,
                              'min': _encode_scalar(self.min, xsd_name),
                              'max': _encode_scalar(self.max, xsd_name)}}

    def to_raw_json_node(self) -> Optional[ElementJsonValueType]:
        min = model.datatypes.xsd_repr(self.min) if self.min is not None else None
        max = model.datatypes.xsd_repr(self.max) if self.max is not None else None
        return {'min': min, 'max': max}

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RangeValue) and self.min == other.min and self.max == other.max

    def __hash__(self) -> int:
        return hash((self.min, self.max))

    def __repr__(self) -> str:
        return f"RangeValue(min={self.min!r}, max={self.max!r})"


class MLPropertyValue(ElementValue, Sequence[dict[str, str]]):
    """MultiLanguageProperty 형 SubmodelElement 값.

    ``[{언어코드: 텍스트}, ...]`` 형태의 단일-엔트리 dict 리스트로 값을 보유한다
    (예: ``[{"en": "Ampere Values"}, {"kr": "전류량"}]``). ``@type``/bare-wire/raw-object
    표현 모두 이 리스트 형태를 그대로 사용하며, basyx SME 변환 시에만 dict-like
    ``MultiLanguageTextType`` 과 상호 변환한다.
    """

    def __init__(self, mappings: list[dict[str, str]]) -> None:
        self.__value = list(mappings)

    def to_raw_object(self) -> RawMLPropertyValue:
        return self.__value

    def apply_to(self, element: model.SubmodelElement) -> None:
        if not isinstance(element, model.MultiLanguageProperty):
            raise ValueError(
                f"MLPropertyValue can only be applied to MultiLanguageProperty: "
                f"got {type(element).__name__}")
        # 단일-엔트리 dict 리스트를 평탄한 {언어: 텍스트} dict 로 합쳐 적용한다.
        element.value = model.MultiLanguageTextType(
            {lang: text for entry in self.__value for lang, text in entry.items()})

    def to_json_node(self) -> dict[str, str|list[dict[str, str]]]:
        return { FIELD_TYPE: TYPE_MLPROP, FIELD_VALUE: self.__value }

    def to_raw_json_node(self) -> Optional[ElementJsonValueType]:
        return cast(RawMLPropertyValue, self.__value)

    def __getitem__(self, index):  # type: ignore[override]
        return self.__value[index]

    def __len__(self) -> int:
        return len(self.__value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MLPropertyValue):
            return self.__value == other.__value
        if isinstance(other, list):
            return self.__value == other
        return NotImplemented

    def __repr__(self) -> str:
        return f"MLPropertyValue({self.__value!r})"


class ElementCollectionValue(ElementValue, Mapping[str, Optional['ElementValue']]):
    """SubmodelElementCollection 형 값. id_short → 멤버 값(ElementValue) 매핑(Mapping)이다."""

    def __init__(self, members: Mapping[str, Optional[ElementValue]]) -> None:
        self.__members: dict[str, Optional[ElementValue]] = dict(members)

    def to_raw_object(self) -> CollectionValueType:
        return {key: (member.to_raw_object() if member is not None else None)
                for key, member in self.__members.items()}

    def apply_to(self, element: model.SubmodelElement) -> None:
        if not isinstance(element, model.SubmodelElementCollection):
            raise ValueError(
                f"ElementCollectionValue can only be applied to SubmodelElementCollection: "
                f"got {type(element).__name__}")
        # id_short 로 대응되는 멤버 값을 찾아 재귀적으로 적용한다.
        for member in element.value:
            member_value = self.__members.get(str(member.id_short))
            if member_value is not None:
                member_value.apply_to(member)

    def to_json_node(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            key: (member.to_json_node() if member is not None else None)
            for key, member in self.__members.items()
        }
        return {FIELD_TYPE: TYPE_COLLECTION, FIELD_VALUE: fields}

    def to_raw_json_node(self) -> Optional[ElementJsonValueType]:
        # 값이 있는(None 이 아닌) 멤버만 포함하여 wire 포맷 dict 로 직렬화한다.
        return {key: member.to_raw_json_node()
                for key, member in self.__members.items() if member is not None}

    def __getitem__(self, key: str) -> Optional[ElementValue]:
        return self.__members[key]

    def __iter__(self):
        return iter(self.__members)

    def __len__(self) -> int:
        return len(self.__members)

    def __repr__(self) -> str:
        return f"ElementCollectionValue({self.__members!r})"


class ElementListValue(ElementValue, Sequence['ElementValue']):
    """SubmodelElementList 형 값. 멤버 값(ElementValue)의 순차열(Sequence)이다.

    컬렉션(ElementCollectionValue)과 달리 멤버는 ``None`` 이 될 수 없다.
    """

    def __init__(self, members: Sequence[ElementValue]) -> None:
        self.__members: list[ElementValue] = list(members)

    def to_raw_object(self) -> ListValueType:
        return [member.to_raw_object() for member in self.__members]

    def apply_to(self, element: model.SubmodelElement) -> None:
        if not isinstance(element, model.SubmodelElementList):
            raise ValueError(
                f"ElementListValue can only be applied to SubmodelElementList: "
                f"got {type(element).__name__}")
        # 순서대로 짝지어 재귀적으로 적용한다.
        for member, member_value in zip(element.value, self.__members):
            member_value.apply_to(member)

    def to_json_node(self) -> dict[str, Any]:
        elements = [member.to_json_node() for member in self.__members]
        return {FIELD_TYPE: TYPE_LIST, FIELD_VALUE: elements}

    def to_raw_json_node(self) ->  Optional[ElementJsonValueType]:
        return [ member.to_raw_json_node() for member in self.__members]

    def __getitem__(self, index):  # type: ignore[override]
        return self.__members[index]

    def __len__(self) -> int:
        return len(self.__members)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ElementListValue):
            return self.__members == other.__members
        if isinstance(other, list):
            return self.__members == other
        return NotImplemented

    def __repr__(self) -> str:
        return f"ElementListValue({self.__members!r})"
