from __future__ import annotations

from typing import Optional

import requests


class MDTException(Exception):
    """
    mdtpy의 모든 사용자 정의 예외의 베이스.

    하위 타입은 의미별로 분리되어 있으며 (`RemoteError`, `OperationError`,
    `ResourceNotFoundError` 등), `details` 속성에 사람이 읽는 본문을 보관한다.

    Attributes:
        details (str): 예외 본문 메시지.
    """

    def __init__(self, details: str) -> None:
        self.details = details
        super().__init__(details)

    def __str__(self) -> str:
        return repr(self)


class FileTooLargeError(MDTException):
    """
    내려받으려는 첨부파일이 지정한 크기 상한(`max_bytes`)을 넘는 경우.

    상한을 넘는 것이 확인되는 즉시 내려받기를 멈추므로 파일 전체를 메모리에 올리지 않는다.

    Attributes:
        url (str): 요청 URL.
        size (Optional[int]): 서버가 알려 준 파일 크기(바이트). 알려 주지 않았으면 None
            (이때는 상한까지 읽은 뒤 멈춘 것이다).
        limit (int): 크기 상한(바이트).
        content_type (Optional[str]): 응답의 Content-Type.
    """

    def __init__(self, url: str, size: Optional[int], limit: int, content_type: Optional[str]) -> None:
        self.url = url
        self.size = size
        self.limit = limit
        self.content_type = content_type
        size_text = f"{size} bytes" if size is not None else f"more than {limit} bytes"
        super().__init__(f"File too large: {size_text} (limit={limit} bytes, "
                         f"content_type={content_type}, url={url})")


class OutputWriteError(MDTException):
    """
    연산은 성공했으나, 그 출력 값을 저장 위치에 기록하지 못한 경우.

    연산을 다시 실행하면 두 번 실행된다. 결과는 `outputs` 에 그대로 있으므로, 실패한 출력만
    `failures` 를 보고 따로 기록한다. 기록에 성공한 출력은 이미 저장되어 있다.

    Attributes:
        outputs (dict): 연산 결과 전체 (출력 인자 id → ElementValue).
        failures (dict[str, Exception]): 기록에 실패한 출력 인자 id → 원인 예외.
    """

    def __init__(self, outputs: dict, failures: dict[str, Exception]) -> None:
        self.outputs = outputs
        self.failures = failures
        causes = ", ".join(f"{arg_id}: {type(e).__name__}: {e}" for arg_id, e in failures.items())
        super().__init__(f"Operation succeeded but failed to store outputs: {causes}")


class InternalError(MDTException):
    """라이브러리 내부 일관성 위반 등 예상치 못한 실패."""

    def __init__(self, details: str) -> None:
        super().__init__(details)


class ResultUnknownError(MDTException):
    """
    요청을 서버에 보냈으나 그 결과를 확인하지 못한 경우.

    응답 대기 시간을 넘겼거나(`TimeoutError`), 응답을 받는 도중 연결이 끊긴 경우(`ConnectionLostError`)다.
    서버는 요청을 이미 처리했거나 아직 처리 중일 수 있으므로, 상태를 바꾸는 요청(연산 실행 등)을
    그대로 다시 보내면 두 번 처리될 수 있다. 다시 보내기 전에 서버의 상태를 먼저 확인한다.
    """

    def __init__(self, details: str) -> None:
        super().__init__(details)


class TimeoutError(ResultUnknownError):
    """
    요청을 보냈으나 제한 시간 안에 응답을 받지 못한 경우. (`builtins.TimeoutError`와 별개)

    `ResultUnknownError` 의 하위 타입이다. 서버가 요청을 처리했는지는 알 수 없다.
    """

    def __init__(self, details: str) -> None:
        super().__init__(details)


class CancellationError(MDTException):
    """원격 작업이 명시적으로 취소된 경우."""

    def __init__(self, details: str) -> None:
        super().__init__(details)


class OperationError(MDTException):
    """AAS Operation 호출이 실패한 경우 (서버가 success=False로 응답)."""

    def __init__(self, details: str) -> None:
        super().__init__(details)


class RemoteError(MDTException):
    """
    서버가 비-2xx 응답을 반환했거나 알 수 없는 오류 코드로 실패한 경우.

    `http_client.to_exception` / `fa3st.to_exception`이 분류 결과를 본 타입의
    인스턴스로 만들거나 직접 raise한다.
    """

    def __init__(self, details: str) -> None:
        super().__init__(details)


class MDTInstanceConnectionError(MDTException):
    """
    MDTInstance(또는 Instance Manager)와의 HTTP 연결 자체에 실패한 경우.

    `requests.exceptions.ConnectionError`를 감싸서 호출자가 본 타입만으로
    연결 오류를 잡을 수 있도록 한다.

    Attributes:
        details (str): 예외 본문.
        cause (requests.exceptions.ConnectionError): 원본 connection error.
    """

    def __init__(
        self,
        details: str,
        cause: requests.exceptions.ConnectionError,
    ) -> None:
        super().__init__(details)
        self.cause = cause

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(details={self.details}, cause={self.cause})"


class ConnectionLostError(MDTInstanceConnectionError, ResultUnknownError):
    """
    연결은 됐으나 응답을 받는 도중 연결이 끊긴 경우.

    요청이 서버에 닿았을 수 있으므로 `ResultUnknownError` 이며, 연결 오류로 잡던 기존 코드를 위해
    `MDTInstanceConnectionError` 이기도 하다. 연결 자체에 실패해 요청이 서버에 닿지 않은 경우는
    `MDTInstanceConnectionError` 만 쓴다.
    """

    def __init__(self, details: str, cause: requests.exceptions.ConnectionError) -> None:
        MDTInstanceConnectionError.__init__(self, details, cause)


class ResourceAlreadyExistsError(MDTException):
    """
    이미 존재하는 식별자로 리소스를 생성하려고 시도한 경우.
    """

    def __init__(self, details: str) -> None:
        super().__init__(details)

    @classmethod
    def create(cls, resource_type: str, id_spec: str) -> ResourceAlreadyExistsError:
        """
        `Resource(type=..., id_spec=...)` 형태의 표준 메시지로 인스턴스를 만든다.

        Args:
            resource_type (str): 리소스 종류 (예: "MDTInstance").
            id_spec (str): 리소스 식별 정보 (예: "id=foo").
        Returns:
            ResourceAlreadyExistsError: 표준 메시지가 채워진 인스턴스.
        """
        return ResourceAlreadyExistsError(f"Resource(type={resource_type}, {id_spec})")


class ResourceNotFoundError(MDTException):
    """
    요청한 리소스가 존재하지 않는 경우 (서버가 404를 반환한 경우 포함).
    """

    def __init__(self, details: str) -> None:
        super().__init__(details)

    @classmethod
    def create(cls, resource_type: str, id_spec: str) -> ResourceNotFoundError:
        """
        `Resource(type=..., id_spec=...)` 형태의 표준 메시지로 인스턴스를 만든다.

        Args:
            resource_type (str): 리소스 종류 (예: "MDTInstance").
            id_spec (str): 리소스 식별 정보 (예: "id=foo").
        Returns:
            ResourceNotFoundError: 표준 메시지가 채워진 인스턴스.
        """
        return ResourceNotFoundError(f"Resource(type={resource_type}, {id_spec})")


class InvalidResourceStateError(MDTException):
    """
    리소스의 현재 상태에서 허용되지 않는 작업을 시도한 경우.

    예: STOPPED 상태에서 `parameters` 접근, RUNNING 상태에서 재시작 등.
    """

    def __init__(self, details: str) -> None:
        super().__init__(details)

    @classmethod
    def create(
        cls,
        resource_type: str,
        id_spec: str,
        status,
    ) -> InvalidResourceStateError:
        """
        `Resource(type=..., id_spec=...), status=<status>` 형태의 표준 메시지로
        인스턴스를 만든다.

        Args:
            resource_type (str): 리소스 종류.
            id_spec (str): 리소스 식별 정보.
            status: 현재 상태(`MDTInstanceStatus` 등) 또는 상태 설명 문자열.
        Returns:
            InvalidResourceStateError: 표준 메시지가 채워진 인스턴스.
        """
        return InvalidResourceStateError(
            f"Resource(type={resource_type}, {id_spec}), status={status}"
        )

__all__ = [
    "MDTException",
    "FileTooLargeError",
    "OutputWriteError",
    "InternalError",
    "ResultUnknownError",
    "TimeoutError",
    "ConnectionLostError",
    "CancellationError",
    "OperationError",
    "RemoteError",
    "MDTInstanceConnectionError",
    "ResourceAlreadyExistsError",
    "ResourceNotFoundError",
    "InvalidResourceStateError",
]