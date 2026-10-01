from __future__ import annotations

from typing import Any, Optional

from mdtpy.ref import ElementReference
from mdtpy.rpc.restful.common import RpcArgument


class RpcRequestMessage:
    """원격 연산(operation) 호출 요청 메시지를 표현하는 DTO.

    연산에 전달할 입력 인자들을 ``inputs`` 필드(입력 이름 → 값)로 담는다.
    ``inputs``/``outputs`` 이외의 최상위 필드는 추가 필드(extra fields)로 보존되어
    JSON 왕복(round-trip) 시 원래 위치(최상위)로 복원된다.
    JSON 직렬화 시 ``None`` 필드는 생략된다.
    """

    def __init__(self, inputs: dict[str, Any], outputs: Optional[dict[str, Any]] = None) -> None:
        """요청 메시지를 생성한다.

        전달된 ``inputs``/``outputs`` dict 는 복사하지 않고 그대로 보관하므로, 생성 후
        호출자가 원본 dict 를 변경하면 메시지 내용도 함께 바뀐다.

        :param inputs: 연산 입력 인자. (입력 이름 → 값, ``None`` 불가)
        :param outputs: 연산 출력 인자. (출력 이름 → 값, ``None`` 가능)
        :raises ValueError: ``inputs`` 가 ``None`` 인 경우.
        """
        if inputs is None:
            raise ValueError("'inputs' is null")

        self.__inputs = inputs
        self.__outputs = outputs
        self.__extra_fields: dict[str, Any] = {}

    @property
    def inputs(self) -> dict[str, RpcArgument]:
        """연산 입력 인자를 반환한다. (입력 이름 → 값)"""
        return self.__inputs

    @property
    def outputs(self) -> Optional[dict[str, ElementReference]]:
        """연산 출력 인자를 반환한다. (출력 이름 → 값) 출력이 없으면 ``None``."""
        return self.__outputs

    @property
    def extra_fields(self) -> dict[str, Any]:
        """``inputs``/``outputs`` 이외의 추가 필드를 반환한다. (필드 이름 → 값)"""
        return self.__extra_fields

    def put_extra_field(self, name: str, value: Any) -> None:
        """``inputs``/``outputs`` 이외의 추가 필드를 등록한다.

        :param name: 필드 이름.
        :param value: 필드 값.
        """
        self.__extra_fields[name] = value

    def to_json_object(self) -> dict[str, Any]:
        """요청 메시지를 JSON 직렬화용 dict 로 변환한다.

        ``None`` 인 ``outputs`` 는 생략하고, 추가 필드는 다시 최상위 필드로 펼친다.

        :return: JSON 직렬화용 dict.
        """
        obj: dict[str, Any] = {'inputs': self.__inputs}
        # NON_NULL: outputs 가 None 이면 직렬화에서 생략한다.
        if self.__outputs is not None:
            obj['outputs'] = self.__outputs
        # inputs/outputs 이외의 추가 필드를 최상위 필드로 펼친다.
        obj.update(self.__extra_fields)
        return obj

    @classmethod
    def from_json_object(cls, obj: dict[str, Any]) -> RpcRequestMessage:
        """JSON 역직렬화 dict 로부터 요청 메시지를 생성한다.

        ``inputs``/``outputs`` 로 바인딩되지 않은 최상위 필드는 추가 필드로 보존된다.

        :param obj: JSON 역직렬화 dict.
        :return: 생성된 요청 메시지.
        :raises ValueError: ``inputs`` 필드가 없는 경우.
        """
        inputs = obj.get('inputs')
        if inputs is None:
            raise ValueError("'inputs' is null")

        msg = cls(inputs, obj.get('outputs'))
        for name, value in obj.items():
            if name not in ('inputs', 'outputs'):
                msg.put_extra_field(name, value)
        return msg

    def __str__(self) -> str:
        return ", ".join(self.__inputs.keys())
