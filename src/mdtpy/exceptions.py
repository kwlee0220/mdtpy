from __future__ import annotations

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


class InternalError(MDTException):
    """라이브러리 내부 일관성 위반 등 예상치 못한 실패."""

    def __init__(self, details: str) -> None:
        super().__init__(details)


class TimeoutError(MDTException):
    """원격 작업이 시간 내에 완료되지 않은 경우. (`builtins.TimeoutError`와 별개)"""

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
