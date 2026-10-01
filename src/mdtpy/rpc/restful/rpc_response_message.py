from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass

import requests

from mdtpy.operation import parse_argument_json_node
from .rpc_state import RpcState
from .error import RestfulErrorEntity, RestfulRemoteException


@dataclass(frozen=True)
class RpcResponseMessage:
    """원격 연산(operation) 호출에 대한 서버의 응답 메시지를 표현하는 DTO.

    응답은 연산의 수행 상태(:class:`RpcState`)에 따라 구성이 달라진다.

    * ``COMPLETED`` - ``outputs`` 에 연산 출력이 담긴다.
    * ``FAILED`` - ``error`` 에 실패 정보(:class:`RestfulErrorEntity`)가 담긴다.
    * ``RUNNING`` - 비동기 수행 중이며 ``session_endpoint`` 로 세션을 식별한다.
    * ``CANCELLED`` - 연산이 취소되었다.

    JSON 직렬화 시 ``None`` 필드는 생략된다.
    """
    state: RpcState
    session_endpoint: Optional[str] = None
    outputs: Optional[dict[str, Any]] = None
    error: Optional[RestfulErrorEntity] = None

    def __post_init__(self) -> None:
        """상태와 필드 구성의 정합성을 검사한다."""
        if self.state is None:
            raise ValueError("'state' is null")
        if self.state == RpcState.COMPLETED and self.outputs is None:
            raise ValueError("state is COMPLETED but 'outputs' is null")
        if self.state == RpcState.FAILED and self.error is None:
            raise ValueError("state is FAILED but 'error' is null")

    def to_exception(self) -> RestfulRemoteException:
        """실패 정보(:attr:`error`)로부터 복원된 예외 객체를 반환한다.

        :raises RuntimeError: 연산 상태가 ``FAILED`` 가 아니거나 실패 정보가 없는 경우.
        """
        if self.state != RpcState.FAILED:
            raise RuntimeError(f"state is not FAILED: {self.state}")
        if self.error is None:
            raise RuntimeError("error is null")
        return self.error.to_exception()

    # 상태별 응답 메시지 생성 팩토리 메소드 -----------------------------------------------

    @classmethod
    def running(cls, session_endpoint: Optional[str] = None) -> RpcResponseMessage:
        """비동기 수행 중(``RUNNING``) 상태의 응답 메시지를 생성한다."""
        return cls(RpcState.RUNNING, session_endpoint=session_endpoint)

    @classmethod
    def completed(cls, session_endpoint: Optional[str],
                  outputs: dict[str, Any]) -> RpcResponseMessage:
        """수행 완료(``COMPLETED``) 상태의 응답 메시지를 생성한다."""
        return cls(RpcState.COMPLETED, session_endpoint=session_endpoint, outputs=outputs)

    @classmethod
    def failed(cls, session_endpoint: Optional[str], cause: BaseException) -> RpcResponseMessage:
        """수행 실패(``FAILED``) 상태의 응답 메시지를 생성한다.

        ``cause`` 는 :class:`RestfulErrorEntity` 로 변환되어 저장된다.
        """
        return cls(RpcState.FAILED, session_endpoint=session_endpoint,
                   error=RestfulErrorEntity.from_exception(cause))

    @classmethod
    def cancelled(cls, session_endpoint: Optional[str] = None) -> RpcResponseMessage:
        """수행 취소(``CANCELLED``) 상태의 응답 메시지를 생성한다."""
        return cls(RpcState.CANCELLED, session_endpoint=session_endpoint)

    # JSON 직렬화/역직렬화 -------------------------------------------------------------

    def to_json_object(self) -> dict[str, Any]:
        """응답 메시지를 JSON 직렬화용 dict 로 변환한다. (``None`` 필드는 생략)"""
        obj: dict[str, Any] = {'status': self.state.value}
        if self.session_endpoint is not None:
            obj['session_endpoint'] = self.session_endpoint
        if self.outputs is not None:
            obj['outputs'] = self.outputs
        if self.error is not None:
            obj['error'] = self.error.to_json_object()
        return obj

    @classmethod
    def from_json_object(cls, obj: dict[str, Any]) -> RpcResponseMessage:
        """JSON 역직렬화 dict 로부터 응답 메시지를 생성한다.

        ``outputs`` 의 각 값은 :func:`~mdtpy.operation.parse_argument_json_node` 로 타입 태그에
        따라 변환된다. ``outputs`` 필드가 없으면 빈 dict 가 된다 (``None`` 이 아님).

        :param obj: JSON 역직렬화 dict.
        :return: 생성된 응답 메시지.
        :raises ValueError: ``status`` 필드가 없는 경우.
        """
        state = obj.get('status')
        if state is None:
            raise ValueError("'status' is null")

        error_obj = obj.get('error')
        error = RestfulErrorEntity.from_json_object(error_obj) if error_obj is not None else None

        out_args = { key:parse_argument_json_node(jnode)
                    for key, jnode in obj.get('outputs', {}).items() }

        return cls(RpcState(state),
                   session_endpoint=obj.get('session_endpoint'),
                   outputs=out_args,
                   error=error)

    def __str__(self) -> str:
        outputs_str = ", ".join(self.outputs.keys()) if self.outputs else ""
        error_str = str(self.error) if self.error is not None else ""
        return (f"[session={self.session_endpoint}] status={self.state.value}, "
                f"outputs={{{outputs_str}}}{error_str}")


def parse_response_message(http_resp: requests.Response) -> RpcResponseMessage:
    """HTTP 응답을 :class:`RpcResponseMessage` 로 변환한다.

    에러 응답 본문이 ``code``/``message`` 형태의 에러 엔티티이면 복원된 예외를 던지고,
    그 외의 HTTP 에러는 ``requests.HTTPError`` 를 던진다.
    """
    if not http_resp.ok:
        try:
            body = http_resp.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and ('code' in body or 'message' in body):
            raise RestfulErrorEntity.from_json_object(body).to_exception()
        http_resp.raise_for_status()
    return RpcResponseMessage.from_json_object(http_resp.json())
