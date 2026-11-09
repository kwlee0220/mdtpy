from __future__ import annotations

from collections.abc import Callable
from typing import Optional, TypeVar
from dataclasses import dataclass

import base64
from urllib.parse import urljoin

import requests
import urllib3

from dataclass_wizard import JSONWizard

from .exceptions import (
    MDTException,
    MDTInstanceConnectionError,
    ConnectionLostError,
    FileTooLargeError,
    TimeoutError as MDTTimeoutError,
)
from .http_client import to_exception as _to_exception_common

T = TypeVar('T')


# 모든 HTTP 호출의 기본 타임아웃(초). 명시적 timeout이 주어지지 않았을 때 사용한다.
DEFAULT_TIMEOUT: float = 30.0

# requests 의 timeout 인자: 초 하나, 또는 (연결 제한, 응답 대기 제한) 튜플.
Timeout = float | tuple[float, float]


def _connection_error(url: str, cause: requests.exceptions.ConnectionError) -> MDTInstanceConnectionError:
    """연결 오류를 요청이 서버에 닿았는지에 따라 나눈다.

    연결 자체에 실패했으면(연결 거부, 이름 해석 실패, 연결 시간 초과, TLS 실패) 요청이 서버에 닿지 않은
    것이므로 `MDTInstanceConnectionError` 를 돌려준다. 연결된 뒤 응답을 받다가 끊겼으면 요청이 처리됐을 수
    있으므로 `ConnectionLostError`(결과 확인 불가)를 돌려준다. 판단할 수 없는 경우도 보수적으로 뒤쪽으로 본다.
    """
    reason = cause.args[0] if cause.args else None
    if isinstance(reason, urllib3.exceptions.MaxRetryError):
        reason = reason.reason
    not_sent = (isinstance(cause, (requests.exceptions.ConnectTimeout, requests.exceptions.SSLError))
                or isinstance(reason, (urllib3.exceptions.NewConnectionError,
                                       urllib3.exceptions.ConnectTimeoutError)))
    if not_sent:
        return MDTInstanceConnectionError(f"Failed to connect to {url}", cause)
    return ConnectionLostError(f"Connection to {url} was lost after the request was sent; "
                               f"the request may have been processed", cause)


def _response_timeout(url: str, timeout: Timeout, cause: Exception) -> MDTTimeoutError:
    """요청은 보냈으나 제한 시간 안에 응답을 받지 못한 경우의 예외를 만든다.

    연결 실패와 달리 서버가 요청을 받아 처리 중이거나 이미 처리했을 수 있으므로,
    그 요청의 결과를 알 수 없다는 뜻으로 쓴다.
    """
    error = MDTTimeoutError(f"No response from {url} within timeout={timeout}; "
                            f"the request may still be in progress on the server")
    error.__cause__ = cause
    return error

# 사내 self-signed 인증서를 쓰는 환경 호환을 위해 SSL 검증을 끈다.
# 외부 네트워크 호출에서는 True로 변경할 것을 권장.
VERIFY_TLS: bool = False

# JSON 본문을 보내는 요청에 사용하는 공통 헤더.
JSON_HEADERS: dict[str, str] = {'Content-Type': 'application/json'}


@dataclass(frozen=True, slots=True)
class Message(JSONWizard):
    """
    FA³ST 서버가 응답 본문 `messages` 배열에 담는 단위 메시지.

    Attributes:
        message_type (str): 메시지 종류 (예: "Error").
        text (str): 사람이 읽는 메시지 본문.
        code (str): 메시지 코드.
        timestamp (str): 메시지 발생 시각.
    """
    message_type: str
    text: str
    code: str
    timestamp: str


def encode_base64url(text: str) -> str:
    """
    문자열을 URL-safe Base64로 인코딩하여 반환한다.

    AAS / Submodel ID 같이 `/`, `:` 등 URL 예약 문자를 포함할 수 있는
    식별자를 경로 세그먼트에 안전하게 넣을 때 사용한다.

    Args:
        text (str): 인코딩할 원본 문자열 (UTF-8로 해석된다).
    Returns:
        str: URL-safe Base64 문자열 (ASCII).
    """
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


def decode_base64url(text: str) -> str:
    """
    `encode_base64url`로 인코딩된 문자열을 원본으로 복원한다.

    표준 Base64는 길이가 4의 배수여야 하므로, 부족한 만큼 `=` 패딩을
    내부적으로 보충한 뒤 디코딩한다.

    Args:
        text (str): URL-safe Base64 문자열 (패딩 유무 무관).
    Returns:
        str: UTF-8로 해석된 원본 문자열.
    """
    padding = '=' * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding).decode("utf-8")


def read_none_response(resp: requests.Response) -> None:
    """
    응답 본문을 사용하지 않는 호출(204 No Content 등)을 검증한다.

    상태 코드가 2xx면 아무 일도 하지 않고, 그 외에는 `to_exception`으로
    응답을 변환하여 발생시킨다.

    Args:
        resp (requests.Response): 검증할 HTTP 응답 객체.
    Raises:
        MDTException: 비-2xx 응답인 경우 (RemoteError 등 하위 타입 포함).
    """
    if resp.status_code >= 200 and resp.status_code < 300:
        return
    else:
        raise to_exception(resp)


def read_response(resp: requests.Response) -> Optional[str]:
    """
    응답 본문을 텍스트로 읽어 반환한다.

    동작:
        - 204 No Content: `None` 반환.
        - 그 외 2xx: `resp.text` 반환.
        - 비-2xx: `to_exception(resp)`로 변환된 예외를 발생.

    Args:
        resp (requests.Response): 읽을 HTTP 응답 객체.
    Returns:
        Optional[str]: 응답 본문 텍스트, 또는 204인 경우 None.
    Raises:
        MDTException: 비-2xx 응답인 경우.
    """
    if resp.status_code == 204:
        return None
    elif resp.status_code >= 200 and resp.status_code < 300:
        return resp.text
    else:
        raise to_exception(resp)


def read_file_response(resp: requests.Response) -> Optional[tuple[str, bytes]]:
    """
    파일/바이너리 응답을 (Content-Type, bytes) 튜플로 반환한다.

    동작:
        - 204 No Content: `None` 반환.
        - 그 외 2xx: `(resp.headers['Content-Type'], resp.content)` 반환.
        - 비-2xx: `to_exception(resp)`로 변환된 예외 발생.

    Args:
        resp (requests.Response): 읽을 HTTP 응답 객체.
    Returns:
        Optional[tuple[str, bytes]]: (Content-Type, 본문 바이트), 또는 None.
    Raises:
        MDTException: 비-2xx 응답인 경우.
    """
    if resp.status_code == 204:
        return None
    elif resp.status_code >= 200 and resp.status_code < 300:
        return resp.headers['Content-Type'], resp.content
    else:
        raise to_exception(resp)


def _request(
    method: str,
    url: str,
    *,
    data: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    deserializer: Optional[Callable[[str], T]] = None,
    timeout: Timeout = DEFAULT_TIMEOUT,
) -> Optional[T | str]:
    """
    공통 HTTP 호출 헬퍼.

    `requests.request(method, url, ...)`로 단일 요청을 보내고, 2xx 응답
    본문을 (선택적으로 deserialize하여) 반환한다. `verify`는 모듈-수준 상수
    `VERIFY_TLS`로 적용되고, `timeout`은 주지 않으면 `DEFAULT_TIMEOUT`이다.

    Args:
        method (str): HTTP 메서드 ("GET"/"PUT"/"POST"/"PATCH"/"DELETE").
        url (str): 요청 URL.
        data (Optional[str]): 요청 본문.
        headers (Optional[dict[str, str]]): 추가 헤더.
        deserializer (Optional[Callable[[str], T]]): 응답 텍스트 변환 함수.
            응답이 비어있으면(빈 문자열/None) 호출되지 않는다.
    Returns:
        Optional[T | str]: deserialize된 객체, 응답 텍스트, 또는 None(204).
    Raises:
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        TimeoutError: 요청은 보냈으나 timeout 안에 응답을 받지 못한 경우 (mdtpy.TimeoutError).
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    try:
        resp = requests.request(
            method, url,
            data=data,
            headers=headers,
            verify=VERIFY_TLS,
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError as e:
        raise _connection_error(url, e)
    except requests.exceptions.Timeout as e:
        raise _response_timeout(url, timeout, e)
    resp_text = read_response(resp)
    return deserializer(resp_text) if deserializer and resp_text else resp_text


def call_get(
    url: str,
    deserializer: Optional[Callable[[str], T]] = None,
) -> Optional[T | str]:
    """
    GET 요청을 보내고 응답 본문을 (선택적으로 deserialize하여) 반환한다.

    Args:
        url (str): 요청할 URL.
        deserializer (Optional[Callable[[str], T]]): 응답 텍스트를 변환할 함수.
            None이면 텍스트 그대로 반환한다. 응답이 비어있으면(빈 문자열/None)
            deserializer는 호출되지 않는다.
    Returns:
        Optional[T | str]: deserialize된 객체, 응답 텍스트, 또는 None(204).
    Raises:
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    return _request("GET", url, deserializer=deserializer)


def call_put(
    url: str,
    data: str,
    deserializer: Optional[Callable[[str], T]] = None,
) -> Optional[T | str]:
    """
    PUT 요청을 보내고 응답 본문을 (선택적으로 deserialize하여) 반환한다.

    Args:
        url (str): 요청할 URL.
        data (str): 요청 본문.
        deserializer (Optional[Callable[[str], T]]): 응답 변환 함수. 빈 응답에는
            호출되지 않는다.
    Returns:
        Optional[T | str]: deserialize된 객체, 응답 텍스트, 또는 None(204).
    Raises:
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    return _request("PUT", url, data=data, deserializer=deserializer)


# max_bytes 를 줄 때 응답 본문을 나눠 읽는 단위(바이트).
_FILE_CHUNK_SIZE = 64 * 1024


def call_get_file(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: Optional[int] = None,
) -> Optional[tuple[str, bytes]]:
    """
    바이너리/파일 응답을 받는 GET 요청을 보낸다. 첨부파일 다운로드에 사용한다.

    `call_get`(텍스트 본문)과 달리 응답을 `(Content-Type, bytes)` 튜플로 반환한다.
    `verify`는 모듈 상수(`VERIFY_TLS`)로 적용된다.

    `max_bytes` 를 주면 본문을 한꺼번에 받지 않고 나눠 읽는다. 응답 헤더의 Content-Length 가 상한을
    넘으면 본문을 읽지 않고, Content-Length 가 없으면 상한을 넘는 순간 읽기를 멈춘다. 어느 경우든
    `FileTooLargeError` 를 내며, 파일 전체를 메모리에 올리지 않는다.

    Args:
        url (str): 요청할 URL.
        timeout (float): 요청 타임아웃(초).
        max_bytes (Optional[int]): 내려받을 파일의 최대 크기(바이트). None 이면 제한하지 않는다.
    Returns:
        Optional[tuple[str, bytes]]: (Content-Type, 본문 바이트), 또는 None(204).
    Raises:
        FileTooLargeError: `max_bytes` 를 넘는 파일인 경우.
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    try:
        resp = requests.get(url, verify=VERIFY_TLS, timeout=timeout, stream=max_bytes is not None)
    except requests.exceptions.ConnectionError as e:
        raise _connection_error(url, e)
    except requests.exceptions.Timeout as e:
        raise _response_timeout(url, timeout, e)
    if max_bytes is None:
        return read_file_response(resp)

    try:
        if resp.status_code == 204 or not (200 <= resp.status_code < 300):
            return read_file_response(resp)     # 204 는 None, 오류 응답은 예외 (본문이 작다)
        content_type = resp.headers['Content-Type']
        length = resp.headers.get('Content-Length')
        if length is not None and length.isdigit() and int(length) > max_bytes:
            raise FileTooLargeError(url, int(length), max_bytes, content_type)

        body = bytearray()
        for chunk in resp.iter_content(chunk_size=_FILE_CHUNK_SIZE):
            body += chunk
            if len(body) > max_bytes:
                raise FileTooLargeError(url, None, max_bytes, content_type)
        return content_type, bytes(body)
    finally:
        # 상한을 넘어 읽기를 멈춘 경우에도 연결을 정리한다.
        resp.close()


def call_put_file(
    url: str,
    files: dict,
    data: Optional[dict[str, str]] = None,
    timeout: float = 60.0,
) -> None:
    """
    multipart/form-data 형식의 PUT 요청을 보낸다. 첨부파일 업로드에 사용한다.

    `call_put`(문자열 본문)과 달리 `files`/폼필드 `data`를 함께 전송한다.
    `verify`는 모듈 상수(`VERIFY_TLS`)로 적용되며, 응답 본문은 사용하지 않는다.

    Args:
        url (str): 요청할 URL.
        files (dict): `requests`의 multipart 업로드용 `files` 딕셔너리.
        data (Optional[dict[str, str]]): 함께 보낼 폼필드.
        timeout (float): 요청 타임아웃(초). 업로드 특성상 기본값을 크게 둔다.
    Raises:
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    try:
        resp = requests.put(url, files=files, data=data, verify=VERIFY_TLS, timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        raise _connection_error(url, e)
    except requests.exceptions.Timeout as e:
        raise _response_timeout(url, timeout, e)
    read_none_response(resp)


def call_post(
    url: str,
    data: str,
    deserializer: Optional[Callable[[str], T]] = None,
    timeout: Timeout = DEFAULT_TIMEOUT,
) -> Optional[T | str]:
    """
    POST 요청(본문은 application/json)을 보내고 응답 본문을 반환한다.

    Args:
        url (str): 요청할 URL.
        data (str): 요청 본문 (JSON 문자열).
        deserializer (Optional[Callable[[str], T]]): 응답 변환 함수. 빈 응답에는
            호출되지 않는다.
        timeout (Timeout): 요청 타임아웃(초, 또는 (연결, 응답 대기) 튜플).
            서버가 처리를 끝낸 뒤에 응답하는 요청(동기 연산 호출 등)은 처리 시간보다 길게 준다.
    Returns:
        Optional[T | str]: deserialize된 객체, 응답 텍스트, 또는 None(204).
    Raises:
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        TimeoutError: 요청은 보냈으나 timeout 안에 응답을 받지 못한 경우 (mdtpy.TimeoutError).
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    return _request("POST", url, data=data, headers=JSON_HEADERS, deserializer=deserializer,
                    timeout=timeout)


def call_post_for_location(
    url: str,
    data: str,
    timeout: Timeout = DEFAULT_TIMEOUT,
) -> str:
    """
    POST 요청(본문은 application/json)을 보내고, 응답의 Location 헤더를 절대 URL 로 반환한다.

    비동기 연산 시작(`…/invoke-async`)처럼 서버가 `202 Accepted` 와 함께 후속 조회 위치를 Location 헤더로
    알려 주는 요청에 쓴다. 상대 경로로 온 Location 은 요청 URL 을 기준으로 절대 URL 로 바꾼다.

    Args:
        url (str): 요청할 URL.
        data (str): 요청 본문 (JSON 문자열).
        timeout (Timeout): 요청 타임아웃(초, 또는 (연결, 응답 대기) 튜플).
    Returns:
        str: Location 헤더가 가리키는 절대 URL.
    Raises:
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        TimeoutError: 요청은 보냈으나 timeout 안에 응답을 받지 못한 경우 (mdtpy.TimeoutError).
        MDTException: 비-2xx 응답이거나, 응답에 Location 헤더가 없는 경우.
    """
    try:
        resp = requests.request("POST", url, data=data, headers=JSON_HEADERS, verify=VERIFY_TLS,
                                timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        raise _connection_error(url, e)
    except requests.exceptions.Timeout as e:
        raise _response_timeout(url, timeout, e)
    read_none_response(resp)
    location = resp.headers.get('Location')
    if not location:
        raise MDTException(f"No Location header in the response: url={url}, status={resp.status_code}")
    return urljoin(url, location)


def call_patch(
    url: str,
    json_str: str,
    deserializer: Optional[Callable[[str], T]] = None,
) -> Optional[T | str]:
    """
    PATCH 요청(본문은 application/json)을 보내고 응답 본문을 반환한다.

    Args:
        url (str): 요청할 URL.
        json_str (str): 요청 본문 (JSON 문자열).
        deserializer (Optional[Callable[[str], T]]): 응답 변환 함수. 빈 응답에는
            호출되지 않는다.
    Returns:
        Optional[T | str]: deserialize된 객체, 응답 텍스트, 또는 None(204).
    Raises:
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    return _request("PATCH", url, data=json_str, headers=JSON_HEADERS, deserializer=deserializer)


def call_delete(url: str) -> None:
    """
    DELETE 요청을 보낸다. 응답 본문은 사용하지 않는다.

    Args:
        url (str): 요청할 URL.
    Raises:
        MDTInstanceConnectionError: 연결 실패 시. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    try:
        resp = requests.delete(url, verify=VERIFY_TLS, timeout=DEFAULT_TIMEOUT)
    except requests.exceptions.ConnectionError as e:
        raise _connection_error(url, e)
    except requests.exceptions.Timeout as e:
        raise _response_timeout(url, DEFAULT_TIMEOUT, e)
    read_none_response(resp)


def to_exception(resp: requests.Response) -> MDTException:
    """
    서버 오류 응답을 적절한 `MDTException` 하위 타입으로 변환한다.

    `http_client.to_exception`에 위임하여 두 모듈의 분류 로직을 일치시킨다.
    구체적인 분기 규칙은 `http_client.to_exception`의 docstring 참조.

    Args:
        resp (requests.Response): 변환할 (비-2xx) HTTP 응답 객체.
    Returns:
        MDTException: 분기에 따라 적절한 하위 타입의 인스턴스.
    Raises:
        RemoteError / ResourceNotFoundError: 위임된 분기 일부는 함수 내부에서
            직접 raise한다.
    """
    return _to_exception_common(resp)
