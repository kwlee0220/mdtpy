from __future__ import annotations

from typing import Any, Optional
import logging

import requests

from .rpc_request_message import RpcRequestMessage
from .rpc_response_message import parse_response_message
from .rpc_state import RpcState
from .common import DEFAULT_TIMEOUT, VERIFY_TLS
from .error import RpcExecutionError, RpcCancelledError

logger = logging.getLogger(__name__)


class RESTfulRpcClient:
    """원격 연산(operation)을 동기 방식의 HTTP로 호출하는 클라이언트.

    :meth:`call` 을 호출하면 응답이 도착할 때까지 블록하고, 연산 상태에 따라 출력을 반환하거나
    예외를 던진다.
    """

    def __init__(self, operation_url: str, inputs: Optional[dict[str, Any]] = None, *,
                 session: Optional[requests.Session] = None,
                 timeout: float = DEFAULT_TIMEOUT, verify_tls: bool = VERIFY_TLS) -> None:
        """클라이언트를 생성한다.

        :param operation_url: 연산 호출 URL. (필수)
        :param inputs: 연산 입력 인자. (입력 이름 → 값) 생략하면 빈 입력으로 호출한다.
        :param session: 재사용할 :class:`requests.Session`. 생략하면 내부적으로 생성한다.
        :param timeout: 응답 대기 제한 시간(초).
        :param verify_tls: TLS 인증서 검증 여부.
        :raises ValueError: ``operation_url`` 이 비어 있는 경우.
        """
        if not operation_url:
            raise ValueError("operation_url is not specified")

        self.operation_url = operation_url
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.__request_msg = RpcRequestMessage(inputs if inputs is not None else {})
        self.__session = session if session is not None else requests.Session()

    def call(self) -> dict[str, Any]:
        """연산을 동기적으로 호출하고 결과 출력을 반환한다.

        :return: 연산 출력. (출력 이름 → 값)
        :raises RpcExecutionError: 원격 연산이 ``FAILED`` 상태로 종료된 경우.
        :raises RpcCancelledError: 원격 연산이 ``CANCELLED`` 상태로 종료된 경우.
        :raises RuntimeError: 예상치 못한 연산 상태가 반환된 경우.
        :raises RestfulRemoteException: HTTP 에러 응답이 구조화된 에러 본문
            (``code``/``message``)을 담은 경우.
        :raises requests.HTTPError: 그 외 HTTP 통신 자체가 실패한 경우.
        """
        logger.info("calling operation: %s with inputs=%s",
                    self.operation_url, self.__request_msg.inputs)

        http_resp = self.__session.post(self.operation_url,
                                        json=self.__request_msg.to_json_object(),
                                        timeout=self.timeout, verify=self.verify_tls)
        resp = parse_response_message(http_resp)
        if resp.state == RpcState.COMPLETED:
            return resp.outputs if resp.outputs is not None else {}
        elif resp.state == RpcState.FAILED:
            cause = resp.to_exception()
            raise RpcExecutionError(f"operation failed: {cause}") from cause
        elif resp.state == RpcState.CANCELLED:
            raise RpcCancelledError("operation is cancelled")
        else:
            raise RuntimeError(f"unexpected state: {resp.state}")
