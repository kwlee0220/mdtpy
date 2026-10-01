from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass


class RestfulRemoteException(RuntimeError):
    """원격 서버에서 전달된 실패 정보를 보유하는 예외.

    보안상 원격 응답의 ``code`` 로 임의 클래스를 로딩·복원하지 않고,
    ``code``/``message`` 를 그대로 보유한 예외로 변환한다.
    """

    def __init__(self, error: RestfulErrorEntity) -> None:
        super().__init__(str(error))
        self.error = error

    @property
    def code(self) -> Optional[str]:
        """에러 코드 또는 원격 예외 클래스 이름을 반환한다."""
        return self.error.code

    @property
    def remote_message(self) -> Optional[str]:
        """원격 에러 상세 메시지를 반환한다."""
        return self.error.message


@dataclass(frozen=True)
class RestfulErrorEntity:
    """RESTful 서버의 구조화된 에러 응답을 표현하는 DTO.

    JSON 형태는 ``code`` 와 ``message`` 필드로 구성된다. ``code`` 에는 일반적으로 서버에서
    발생한 예외 클래스 이름이 담기지만, 클라이언트는 보안상(임의 클래스 로딩 회피) 이를 이용해
    예외를 복원하지 않고 ``code``/``message`` 를 보유한 ``RestfulRemoteException`` 으로 변환한다.
    """
    code: Optional[str] = None
    message: Optional[str] = None

    @classmethod
    def from_exception(cls, exc: BaseException) -> RestfulErrorEntity:
        """예외 객체로부터 에러 엔티티를 생성한다.

        ``code`` 에는 예외 클래스 이름이, ``message`` 에는 예외 메시지가 저장된다.
        """
        qualified = f"{type(exc).__module__}.{type(exc).__qualname__}"
        return cls(qualified, str(exc))

    @classmethod
    def of_message(cls, msg: str) -> RestfulErrorEntity:
        """메시지만 가진 에러 엔티티를 생성한다."""
        return cls(None, msg)

    def to_exception(self) -> RestfulRemoteException:
        """이 에러 엔티티를 클라이언트 측 예외 객체로 변환하여 반환한다.

        원격 응답의 ``code`` 로 임의 클래스를 로딩·복원하지 않고, 이 엔티티를 보유한
        ``RestfulRemoteException`` 을 반환한다. 예외를 던지지 않는다.
        """
        return RestfulRemoteException(self)

    def to_json_object(self) -> dict[str, Any]:
        """에러 엔티티를 JSON 직렬화용 dict 로 변환한다. (``None`` 필드는 생략)"""
        obj: dict[str, Any] = {}
        if self.code is not None:
            obj['code'] = self.code
        if self.message is not None:
            obj['message'] = self.message
        return obj

    @classmethod
    def from_json_object(cls, obj: dict[str, Any]) -> RestfulErrorEntity:
        """JSON 역직렬화 dict 로부터 에러 엔티티를 생성한다."""
        return cls(obj.get('code'), obj.get('message'))

    def __str__(self) -> str:
        if self.code is not None and self.message is not None:
            return f"{self.code} ({self.message})"
        elif self.message is not None:
            return self.message
        elif self.code is not None:
            return self.code
        else:
            raise RuntimeError("Both code and message are null")


class RpcExecutionError(RuntimeError):
    """원격 연산이 ``FAILED`` 상태로 종료된 경우 발생하는 예외.

    원격에서 복원된 원인 예외는 ``__cause__`` 에 연결된다.
    """


class RpcCancelledError(RuntimeError):
    """원격 연산이 ``CANCELLED`` 상태로 종료된 경우 발생하는 예외."""
