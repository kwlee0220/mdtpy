from __future__ import annotations

from collections.abc import Callable
from typing import Optional, TypeVar
from dataclasses import dataclass

import base64
import requests

from dataclass_wizard import JSONWizard

from .exceptions import (
    MDTException,
    MDTInstanceConnectionError,
)
from .http_client import to_exception as _to_exception_common

T = TypeVar('T')


# 모든 HTTP 호출의 기본 타임아웃(초). 명시적 timeout이 주어지지 않았을 때 사용한다.
DEFAULT_TIMEOUT: float = 30.0

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
) -> Optional[T | str]:
    """
    공통 HTTP 호출 헬퍼.

    `requests.request(method, url, ...)`로 단일 요청을 보내고, 2xx 응답
    본문을 (선택적으로 deserialize하여) 반환한다. `verify`/`timeout`은
    모듈-수준 상수(`VERIFY_TLS`, `DEFAULT_TIMEOUT`)로 일괄 적용된다.

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
        MDTInstanceConnectionError: 연결 실패 시.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    try:
        resp = requests.request(
            method, url,
            data=data,
            headers=headers,
            verify=VERIFY_TLS,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.exceptions.ConnectionError as e:
        raise MDTInstanceConnectionError(f"Failed to connect to {url}", e)
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
        MDTInstanceConnectionError: 연결 실패 시.
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
        MDTInstanceConnectionError: 연결 실패 시.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    return _request("PUT", url, data=data, deserializer=deserializer)


def call_post(
    url: str,
    data: str,
    deserializer: Optional[Callable[[str], T]] = None,
) -> Optional[T | str]:
    """
    POST 요청(본문은 application/json)을 보내고 응답 본문을 반환한다.

    Args:
        url (str): 요청할 URL.
        data (str): 요청 본문 (JSON 문자열).
        deserializer (Optional[Callable[[str], T]]): 응답 변환 함수. 빈 응답에는
            호출되지 않는다.
    Returns:
        Optional[T | str]: deserialize된 객체, 응답 텍스트, 또는 None(204).
    Raises:
        MDTInstanceConnectionError: 연결 실패 시.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    return _request("POST", url, data=data, headers=JSON_HEADERS, deserializer=deserializer)


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
        MDTInstanceConnectionError: 연결 실패 시.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    return _request("PATCH", url, data=json_str, headers=JSON_HEADERS, deserializer=deserializer)


def call_delete(url: str) -> None:
    """
    DELETE 요청을 보낸다. 응답 본문은 사용하지 않는다.

    Args:
        url (str): 요청할 URL.
    Raises:
        MDTInstanceConnectionError: 연결 실패 시.
        MDTException: 비-2xx 응답에서 발생하는 서버 측 오류.
    """
    try:
        resp = requests.delete(url, verify=VERIFY_TLS, timeout=DEFAULT_TIMEOUT)
    except requests.exceptions.ConnectionError as e:
        raise MDTInstanceConnectionError(f"Failed to connect to {url}", e)
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
