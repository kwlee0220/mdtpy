from __future__ import annotations

from typing import Any, Optional
from http import HTTPStatus
import logging
import time

import requests

from mdtpy.ref import ElementReference

from .rpc_request_message import RpcRequestMessage
from .rpc_response_message import RpcResponseMessage, parse_response_message
from .rpc_state import RpcState
from .common import DEFAULT_TIMEOUT, VERIFY_TLS, RpcArgument, encode_argument_to_json_node
from .error import RpcExecutionError, RpcCancelledError
from mdtpy.value import ElementValue

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 3.0  # 세션 상태 폴링 주기 (초)
    

class RESTfulAsyncRpcClient:
    """원격 연산(operation)을 비동기 방식의 HTTP로 호출하는 클라이언트.

    연산을 시작시키는 최초 POST 요청으로 세션을 얻고(``RUNNING``), 이후 주기적 폴링으로 세션 상태를
    조회하여 완료를 기다린다. 연산 상태에 따라 다음과 같이 동작한다.

    * ``COMPLETED`` - 연산 출력을 결과로 반환한다.
    * ``FAILED`` - 복원된 원인 예외를 ``__cause__`` 로 갖는 :class:`RpcExecutionError` 를 던진다.
    * ``CANCELLED`` - :class:`RpcCancelledError` 를 던진다.
    """

    def __init__(self, *, base_url: str, op_endpoint: str,
                 inputs: dict[str, Optional[RpcArgument]],
                 outputs: Optional[dict[str, ElementReference]] = None,
                 poll_interval: float = DEFAULT_POLL_INTERVAL,
                 timeout: Optional[float] = None,
                 request_timeout: float = DEFAULT_TIMEOUT,
                 verify_tls: bool = VERIFY_TLS) -> None:
        """클라이언트를 생성한다.

        :param base_url: 연산 서버의 기본 URL. 연산 호출 URL과 세션 상태 조회 URL의 접두어로 사용된다.
        :param op_endpoint: 연산 엔드포인트. 최종 호출 URL은 ``base_url + op_endpoint`` 로
            단순 연결되므로 ``op_endpoint`` 는 ``/`` 로 시작해야 한다.
            (예: ``"/operations/AddAndSleep"``)
        :param inputs: 연산 입력 인자. (입력 이름 → 값, 필수) 값으로는 ``ElementValue`` /
            ``ElementReference`` / 리터럴(str/int/float/bool)을 받는다.
        :param outputs: 연산 출력 인자. (출력 이름 → ``ElementReference``) 생략하면 출력
            인자 없이 호출한다.
        :param poll_interval: 세션 상태 폴링 주기(초). (기본값 3초)
        :param timeout: 연산 완료를 기다리는 전체 제한 시간(초). ``None`` 이면 무제한.
        :param request_timeout: 개별 HTTP 요청의 응답 대기 제한 시간(초).
        :param verify_tls: TLS 인증서 검증 여부.
        :raises ValueError: ``base_url`` 또는 ``op_endpoint`` 가 비어 있는 경우.
        """
        if not base_url:
            raise ValueError("base_url is not specified")
        if not op_endpoint:
            raise ValueError("op_endpoint is not specified")

        self.base_url = base_url
        self.op_endpoint = op_endpoint
        self.inputs = inputs
        self.outputs = outputs
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.request_timeout = request_timeout
        self.verify_tls = verify_tls
        self.__session_url: Optional[str] = None  # 연산 세션 URL. 연산 시작 전에는 None.

    @property
    def session_url(self) -> Optional[str]:
        """연산 시작 후 할당된 세션 URL을 반환한다. 시작 전이면 ``None``."""
        return self.__session_url

    def call(self) -> dict[str, Any]:
        """연산을 호출하고 완료될 때까지 폴링하여 결과 출력을 반환한다.

        연산 시작 후 ``poll_interval`` 만큼 대기한 뒤 첫 폴링을 수행한다.

        Note:
            ``timeout`` 초과 시 :class:`TimeoutError` 를 던지지만 서버 측 세션은
            취소되지 않고 계속 실행된다. 중단이 필요하면 별도로 :meth:`cancel` 을
            호출해야 한다.

        :return: 연산 출력. (출력 이름 → 값)
        :raises RpcExecutionError: 원격 연산이 ``FAILED`` 상태로 종료된 경우.
        :raises RpcCancelledError: 원격 연산이 ``CANCELLED`` 상태로 종료된 경우.
        :raises TimeoutError: 제한 시간 내에 연산이 완료되지 않은 경우.
        :raises RuntimeError: 예상치 못한 연산 상태가 반환된 경우.
        :raises RestfulRemoteException: HTTP 에러 응답이 구조화된 에러 본문
            (``code``/``message``)을 담은 경우.
        :raises requests.HTTPError: 그 외 HTTP 통신 자체가 실패한 경우.
        """
        deadline = None if self.timeout is None else time.monotonic() + self.timeout
        self.__start()

        while True:
            time.sleep(self.poll_interval)
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"rpc timed out: session={self.__session_url}")

            resp = self.__poll()
            if resp.state == RpcState.RUNNING:
                logger.info("rpc is running, session=%s", self.__session_url)
                continue
            elif resp.state == RpcState.COMPLETED:
                logger.info("rpc is completed, session=%s, outputs=%s",
                            self.__session_url, resp.outputs)
                return resp.outputs if resp.outputs is not None else {}
            elif resp.state == RpcState.FAILED:
                cause = resp.to_exception()
                raise RpcExecutionError(f"rpc failed: {cause}") from cause
            elif resp.state == RpcState.CANCELLED:
                raise RpcCancelledError(f"rpc is cancelled: session={self.__session_url}")
            else:
                raise RuntimeError(f"unexpected rpc state: {resp.state}")

    def cancel(self) -> bool:
        """수행 중인 연산의 취소를 요청한다.

        다른 스레드에서 :meth:`call` 진행 중에 호출할 수 있다.

        프로토콜 규약에 따라 취소가 확정되면 ``200 OK`` 와 함께 ``CANCELLED`` 상태가 오고,
        대상 세션이 이미 종료 상태여서 취소가 허용되지 않으면 ``409 Conflict`` 가 온다.
        후자는 취소할 대상이 없다는 뜻이므로 예외 대신 ``False`` 를 반환한다.

        세션이 존재하지 않거나 보존 기간이 지나 회수된 경우(``404 Not Found``)는 취소 거부와
        구분되는 상황이므로 예외가 그대로 전파된다.

        :return: 취소가 확정되었으면 ``True``, 이미 종료되어 취소할 수 없으면 ``False``.
        :raises RuntimeError: 아직 연산이 시작되지 않았거나 예상치 못한 상태가 반환된 경우.
        :raises RestfulRemoteException: 세션이 존재하지 않는 등 취소 요청 자체가 실패한 경우.
        :raises requests.HTTPError: 그 외 HTTP 통신 자체가 실패한 경우.
        """
        if self.__session_url is None:
            raise RuntimeError("rpc is not started yet")

        http_resp = requests.delete(self.__session_url, timeout=self.request_timeout,
                                    verify=self.verify_tls)
        if http_resp.status_code == HTTPStatus.CONFLICT:
            # 대상 세션이 이미 종료 상태여서 취소가 허용되지 않는 경우.
            logger.info("rpc is already finished, cannot cancel: session=%s", self.__session_url)
            return False

        # 취소가 확정된 응답은 CANCELLED만 가능하다. 그 외의 종료 상태는 409로 전달된다.
        resp = parse_response_message(http_resp)
        if resp.state != RpcState.CANCELLED:
            raise RuntimeError(f"unexpected rpc state: {resp.state}")
        return True

    def __start(self) -> None:
        """폴링을 시작하기 전에 연산을 호출하여 세션을 확보한다."""
        logger.info("calling rpc: %s, inputs=%s", self.op_endpoint, self.inputs)

        inputs = { name:encode_argument_to_json_node(arg) for name, arg in self.inputs.items() }
        outputs = { name:arg.to_json_node() for name, arg in self.outputs.items() } if self.outputs is not None else None

        request_msg = RpcRequestMessage(inputs, outputs)
        op_url = self.base_url + self.op_endpoint
        http_resp = requests.post(op_url, json=request_msg.to_json_object(),
                                    timeout=self.request_timeout, verify=self.verify_tls)
        resp = parse_response_message(http_resp)
        # 비동기 연산 시작 응답은 RUNNING 또는 FAILED 만 가능하다.
        if resp.state == RpcState.RUNNING:
            assert resp.session_endpoint is not None
            self.__session_url = self.base_url + resp.session_endpoint
        elif resp.state == RpcState.FAILED:
            cause = resp.to_exception()
            raise RpcExecutionError(f"operation failed: {cause}") from cause
        else:
            raise RuntimeError(f"unexpected state: {resp.state}")

    def __poll(self) -> RpcResponseMessage:
        """세션 상태를 한 번 조회한다."""
        http_resp = requests.get(self.__session_url,
                                       timeout=self.request_timeout,
                                       verify=self.verify_tls)
        return parse_response_message(http_resp)
