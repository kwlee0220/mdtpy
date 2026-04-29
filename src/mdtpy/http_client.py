from __future__ import annotations

import requests

from .exceptions import MDTException, RemoteError


def parse_none_response(resp: requests.Response) -> None:
    """
    응답 본문을 사용하지 않는 호출(204/200 등)을 검증한다.

    상태 코드가 2xx면 아무 일도 하지 않고, 그 외에는 응답 본문을
    `to_exception`으로 변환하여 발생시킨다.

    Args:
        resp (requests.Response): 검증할 HTTP 응답 객체.
    Raises:
        MDTException: 상태 코드가 2xx가 아닌 경우 (RemoteError,
            ResourceNotFoundError 등 하위 타입 포함).
    """
    if resp.status_code >= 200 and resp.status_code < 300:
        return
    else:
        raise to_exception(resp)


def parse_response(resp: requests.Response, result_cls: type | None = None):
    """
    2xx 응답 본문을 content-type에 맞게 파싱하여 반환한다.

    동작:
        - `application/json`인 경우:
            - `result_cls`가 지정되면 `result_cls.from_dict(json)`로 변환.
            - `result_cls`가 None이면 raw dict/list 그대로 반환.
        - `text/plain`(charset 파라미터 포함)인 경우: `resp.text` 반환.
        - 그 외 content-type: `MDTException` 발생.
        - 비-2xx 응답: `to_exception(resp)`로 변환된 예외 발생.

    Args:
        resp (requests.Response): 파싱할 HTTP 응답 객체.
        result_cls (type | None): JSON 본문을 변환할 타입. `from_dict`
            classmethod를 가진 dataclass/JSONWizard 등이어야 한다.
    Returns:
        파싱된 객체. result_cls가 주어지면 그 타입의 인스턴스, 아니면 dict
        또는 str.
    Raises:
        MDTException: 지원하지 않는 content-type이거나 비-2xx 응답인 경우.
    """
    if resp.status_code >= 200 and resp.status_code < 300:
        content_type = resp.headers['content-type']
        if content_type == 'application/json':
            json = resp.json()
            return result_cls.from_dict(json) if result_cls else json
        elif content_type.startswith('text/plain'):
            return resp.text
        else:
            raise MDTException(f"Unsupported content type: {content_type}")
    else:
        raise to_exception(resp)


def parse_list_response(resp: requests.Response, result_cls: type | None = None):
    """
    2xx 응답 본문이 JSON 배열일 때 각 원소를 `result_cls`로 변환하여 반환한다.

    Note:
        시그니처 상 `result_cls`의 기본값이 None이지만, 실제 호출 시
        반드시 `from_dict`를 가진 클래스를 전달해야 한다 (None을 넘기면
        AttributeError 발생).

    Args:
        resp (requests.Response): 파싱할 HTTP 응답 객체.
        result_cls (type): 각 원소를 변환할 타입. `from_dict` classmethod 필수.
    Returns:
        list: `result_cls` 인스턴스의 리스트.
    Raises:
        MDTException: 비-2xx 응답인 경우 (`to_exception`으로 변환).
    """
    if result_cls is None:
        raise ValueError("parse_list_response requires result_cls")
    if resp.status_code >= 200 and resp.status_code < 300:
        return [result_cls.from_dict(descElm) for descElm in resp.json()]
    else:
        raise to_exception(resp)


def to_exception(resp: requests.Response) -> MDTException:
    """
    서버 오류 응답을 적절한 `MDTException` 하위 타입으로 변환한다.

    분류 규칙(우선순위 순):
        1. `Content-Type`이 `text/*`로 시작하면 `resp.text`를 담은 RemoteError 반환
           (JSON 파싱 시도하지 않음).
        2. JSON 본문에 `messages` 키가 있으면 첫 메시지의 `text`로 RemoteError 반환.
        3. JSON 본문에 `code` 키가 있고 알려진 매핑에 해당하면:
           - `java.lang.IllegalArgumentException`,
             `java.lang.NullPointerException`,
             `java.lang.UnsupportedOperationException`,
             `org.springframework.*` 계열 → 직접 RemoteError raise.
           - `utils.InternalException`         → RemoteError 반환.
           - `mdt.model.ResourceNotFoundException` → ResourceNotFoundError raise.
        4. 위 모두에 해당하지 않으면 (알 수 없는 code 포함) `resp.text` 또는
           가능한 경우 본문 정보를 담은 RemoteError로 폴백.

    Note:
        분기에 따라 `raise`와 `return`이 섞여 있다. 호출자는 항상
        `raise to_exception(resp)` 형태로 사용하므로 두 경우 모두 동일한
        효과를 낸다.

        과거 구현은 알 수 없는 `code`를 모듈 경로로 해석하여 동적 import를
        시도했으나, 신뢰할 수 없는 서버가 임의 모듈을 로드시킬 수 있는
        보안 위험이 있어 제거했다. 이제 알 수 없는 code는 안전한 RemoteError
        폴백으로 처리한다.

    Args:
        resp (requests.Response): 변환할 (비-2xx) HTTP 응답 객체.
    Returns:
        MDTException: 분기에 따라 RemoteError 또는 ResourceNotFoundError 인스턴스.
    Raises:
        RemoteError / ResourceNotFoundError: 위 분기 일부는 함수 내부에서 직접 raise한다.
    """
    # 1. text/* 응답
    ctype = resp.headers.get('Content-Type', '')
    if ctype.startswith('text/'):
        return RemoteError(resp.text)

    try:
        json_obj = resp.json()
    except ValueError:
        # JSON 파싱 실패 시 raw 본문으로 폴백
        return RemoteError(resp.text)

    # 2. messages 키
    if isinstance(json_obj, dict) and 'messages' in json_obj:
        message = json_obj['messages'][0]
        return RemoteError(message['text'])

    # 3. code 키 (알려진 매핑만 처리)
    if isinstance(json_obj, dict) and 'code' in json_obj:
        code = json_obj['code']
        if code == 'java.lang.IllegalArgumentException':
            raise RemoteError(json_obj['message'])
        elif code == 'utils.InternalException':
            return RemoteError(json_obj['message'])
        elif code in (
            'java.lang.NullPointerException',
            'java.lang.UnsupportedOperationException',
        ):
            raise RemoteError(f"code={json_obj['code']}, message={json_obj['message']}")
        elif code in (
            'org.springframework.web.servlet.resource.NoResourceFoundException',
            'org.springframework.web.HttpRequestMethodNotSupportedException',
        ):
            raise RemoteError(json_obj['text'])
        elif code == 'mdt.model.ResourceNotFoundException':
            from .exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(json_obj['message'])
        # 알려지지 않은 code → 안전한 폴백 (동적 import 제거)
        message_text = json_obj.get('message') or json_obj.get('text') or resp.text
        return RemoteError(f"code={code}, message={message_text}")

    # 4. 그 외 폴백
    return RemoteError(resp.text)
