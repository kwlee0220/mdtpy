from __future__ import annotations

from typing import Any, Optional

import json

from basyx.aas import model

from mdtpy import value
from mdtpy.ref import ElementReference
from mdtpy.value import ElementValue, FileValue, PropertyJsonValue

DEFAULT_TIMEOUT = 30.0  # 개별 HTTP 요청의 응답 대기 제한 시간 (초)
VERIFY_TLS = False      # 자체 서명 인증서를 허용한다.

RpcArgumentLiteral = str | int | float | bool
RpcArgument = ElementValue | ElementReference | RpcArgumentLiteral


def encode_argument_to_json_node(value: Optional[RpcArgument]) -> Any:
    """연산 입력 인자를 JSON 직렬화 가능한 값으로 변환한다.

    인자 타입별 인코딩 방식:

    * ``None`` → ``None`` 그대로.
    * :class:`~mdtpy.ref.ElementReference` → 참조 값을 읽어(``read_value()``) 그 값의
      ``@type`` polymorphic JSON 으로 변환한다. 단, 읽은 값이 :class:`FileValue` 이면
      값 대신 **참조 자체**(``mdt:ref:*`` JSON)를 전송하여 서버가 파일을 참조로
      처리하게 한다.
    * :class:`~mdtpy.value.ElementValue` → ``@type`` polymorphic JSON.
    * 리터럴(str/int/float/bool) → JSON native 값 그대로.

    Args:
        value (Optional[RpcArgument]): 인코딩할 연산 입력 인자.
    Returns:
        Any: JSON 직렬화 가능한 값.
    Raises:
        TypeError: 지원하지 않는 타입의 인자가 주어진 경우.
    """
    if value is None:
        return None
    elif isinstance(value, ElementReference):
        smev = value.read_value()
        if isinstance(smev, FileValue):
            return value.to_json_node()
        else:
            return smev.to_json_node() if smev is not None else None
    elif isinstance(value, ElementValue):
        return value.to_json_node()
    elif isinstance(value, RpcArgumentLiteral):
        return value
    elif isinstance(value, model.SubmodelElement):
        from mdtpy.basyx import serde as basyx_serde
        return json.loads(basyx_serde.to_json(value))
    else:
        raise TypeError(f"unsupported argument type: {type(value)}")