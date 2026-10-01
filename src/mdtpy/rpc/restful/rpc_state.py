from __future__ import annotations

from enum import Enum


class RpcState(Enum):
    """원격 연산(operation)의 수행 상태.

    ``RpcResponseMessage`` 에 담겨 클라이언트에 전달되며, 비동기 수행 중에는 ``RUNNING``,
    종료 시에는 ``COMPLETED``/``FAILED``/``CANCELLED`` 중 하나가 된다.
    """
    RUNNING = "RUNNING"      # 연산이 수행 중이다. (아직 종료되지 않음)
    COMPLETED = "COMPLETED"  # 연산이 성공적으로 완료되었다. (출력이 함께 제공됨)
    FAILED = "FAILED"        # 연산이 실패로 종료되었다. (실패 정보가 함께 제공됨)
    CANCELLED = "CANCELLED"  # 연산이 취소되어 종료되었다.
