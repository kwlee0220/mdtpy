from __future__ import annotations

from typing import Any, Optional, cast
from datetime import datetime, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from basyx.aas import model


# --------------------------------------------------------------------------- #
# polymorphic JSON (@type / value) 상수 및 스칼라 코덱
#
# Java 측 mdt.model.sm.value.ElementValues 의 직렬화 포맷과 호환된다.
# 각 ElementValue 는 {"@type": <식별자>, "value": <값 표현>} 형태로 직렬화되며,
# 컨테이너(collection/list)의 멤버도 동일한 polymorphic 형태로 중첩 직렬화된다.
# --------------------------------------------------------------------------- #

FIELD_TYPE = '@type'
FIELD_VALUE = 'value'

# Property 직렬화 식별자 ----------------------------------------------------------
TYPE_STRING = 'mdt:value:string'
TYPE_INTEGER = 'mdt:value:integer'
TYPE_LONG = 'mdt:value:long'
TYPE_SHORT = 'mdt:value:short'
TYPE_FLOAT = 'mdt:value:float'
TYPE_DOUBLE = 'mdt:value:double'
TYPE_BOOLEAN = 'mdt:value:boolean'
TYPE_DATETIME = 'mdt:value:dateTime'
TYPE_DURATION = 'mdt:value:duration'
TYPE_DECIMAL = 'mdt:value:decimal'
# 컨테이너/기타 직렬화 식별자 ----------------------------------------------------
TYPE_COLLECTION = 'mdt:value:collection'
TYPE_LIST = 'mdt:value:list'
TYPE_FILE = 'mdt:value:file'
TYPE_RANGE = 'mdt:value:range'
TYPE_MLPROP = 'mdt:value:mlprop'

# XSD 타입명 → Property 직렬화 식별자.
_XSD_TO_MDT_TYPE: dict[str, str] = {
    'xs:string': TYPE_STRING,
    'xs:int': TYPE_INTEGER,
    'xs:integer': TYPE_INTEGER,
    'xs:long': TYPE_LONG,
    'xs:short': TYPE_SHORT,
    'xs:float': TYPE_FLOAT,
    'xs:double': TYPE_DOUBLE,
    'xs:boolean': TYPE_BOOLEAN,
    'xs:dateTime': TYPE_DATETIME,
    'xs:duration': TYPE_DURATION,
    'xs:decimal': TYPE_DECIMAL,
}
# Property 직렬화 식별자 → XSD 타입명. (역방향, 대표 XSD 타입 1개로 매핑)
_MDT_TYPE_TO_XSD: dict[str, str] = {
    TYPE_STRING: 'xs:string',
    TYPE_INTEGER: 'xs:int',
    TYPE_LONG: 'xs:long',
    TYPE_SHORT: 'xs:short',
    TYPE_FLOAT: 'xs:float',
    TYPE_DOUBLE: 'xs:double',
    TYPE_BOOLEAN: 'xs:boolean',
    TYPE_DATETIME: 'xs:dateTime',
    TYPE_DURATION: 'xs:duration',
    TYPE_DECIMAL: 'xs:decimal',
}
# Range 의 vtype 필드에 사용되는 데이터 타입 이름(AAS4J DataTypeDefXsd enum 이름) ↔ XSD 타입명.
_XSD_TO_VTYPE_NAME: dict[str, str] = {
    'xs:string': 'STRING', 'xs:boolean': 'BOOLEAN', 'xs:short': 'SHORT', 'xs:int': 'INT',
    'xs:long': 'LONG', 'xs:float': 'FLOAT', 'xs:double': 'DOUBLE', 'xs:dateTime': 'DATE_TIME',
    'xs:duration': 'DURATION', 'xs:decimal': 'DECIMAL', 'xs:date': 'DATE', 'xs:time': 'TIME',
}
_VTYPE_NAME_TO_XSD: dict[str, str] = {name: xsd for xsd, name in _XSD_TO_VTYPE_NAME.items()}

# 값을 JSON native 가 아니라 XSD 문자열로 인코딩하는 XSD 타입 집합. (그 외는 native JSON 으로 인코딩)
_STRING_ENCODED_XSD = {'xs:dateTime', 'xs:duration', 'xs:decimal', 'xs:date', 'xs:time'}


def _infer_xsd_name(value: Any) -> str:
    """값의 런타임 타입으로부터 XSD 타입명(``xs:*``)을 추론한다.

    ``value_type`` 정보 없이 생성된 :class:`PropertyValue`/:class:`RangeValue` 의
    직렬화에 사용한다.
    """
    # basyx 데이터 타입(또는 그 서브타입)이면 정확한 XSD 타입명을 얻는다.
    name = model.datatypes.XSD_TYPE_NAMES.get(type(value))
    if name is not None:
        return name
    # Python 기본 타입에 대한 추론. (bool 은 int 의 서브클래스이므로 먼저 검사한다)
    if isinstance(value, bool):
        return 'xs:boolean'
    if isinstance(value, int):
        return 'xs:int'
    if isinstance(value, float):
        return 'xs:double'
    if isinstance(value, str):
        return 'xs:string'
    if isinstance(value, datetime):
        return 'xs:dateTime'
    if isinstance(value, (relativedelta, timedelta)):
        return 'xs:duration'
    if isinstance(value, Decimal):
        return 'xs:decimal'
    raise ValueError(f"cannot infer XSD type for value: {value!r} ({type(value)})")


def _xsd_name_of(value: Optional[model.ValueDataType], value_type: Optional[Any]) -> str:
    """``value_type`` 가 있으면 그로부터, 없으면 ``value`` 로부터 XSD 타입명을 결정한다."""
    if value_type is not None:
        name = model.datatypes.XSD_TYPE_NAMES.get(value_type)
        if name is not None:
            return name
    if value is not None:
        return _infer_xsd_name(value)
    # value/value_type 모두로부터 결정할 수 없으면 문자열로 간주한다.
    return 'xs:string'


def _encode_scalar(value: Optional[model.ValueDataType], xsd_name: str) -> Any:
    """스칼라 값을 XSD 타입에 맞는 JSON 표현으로 인코딩한다.

    dateTime/duration/decimal 등은 XSD 문자열로, 그 외(string/number/boolean)는
    JSON native 값으로 인코딩한다.
    """
    if value is None:
        return None
    if xsd_name in _STRING_ENCODED_XSD:
        return model.datatypes.xsd_repr(value)
    return value


def _decode_scalar(jvalue: Any, xsd_name: str) -> Optional[model.ValueDataType]:
    """JSON 표현을 XSD 타입에 맞는 Python 스칼라 값으로 디코딩한다."""
    if jvalue is None:
        return None
    btype = model.datatypes.XSD_TYPE_CLASSES.get(xsd_name)
    if isinstance(jvalue, str) and btype is not None:
        return cast(model.ValueDataType, model.datatypes.from_xsd(jvalue, btype))
    return cast(model.ValueDataType, jvalue)
