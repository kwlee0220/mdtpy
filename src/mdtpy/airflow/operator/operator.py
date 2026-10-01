"""Airflow task 본문으로 실행되는 `Operator`의 추상 베이스를 정의한다.

`Operator`는 `DagTaskArgument`로 기술된 입력 명세를 받아, task 실행 시점에
`DagContext`를 통해 실제 값을 해석하고 동작을 수행한다. 구체 구현들은
`set_element` / `operation_submodel` / `aas_operation` / `restful_async_rpc` /
`ai_model_call` / `python_script` 모듈에 각각 분리되어 있다.
"""

from __future__ import annotations

from typing import Optional

from abc import ABC, abstractmethod

from ..dag_task_argument import DagTaskArgument, ElementReferenceArgument
from ..dag_context import DagContext

__all__ = ['Operator', 'DagTaskInputArgument', 'DagTaskOutputArgument']

# 입력 인자는 세 가지 `DagTaskArgument`(task_output/reference/literal) 중 무엇이든 허용한다.
DagTaskInputArgument = DagTaskArgument

# 출력 인자의 경우에는 `ElementReferenceArgument`만 허용한다.
# 이는 연산 호출 결과가 저장될 SubmodelElement의 위치를 지정한다.
DagTaskOutputArgument = ElementReferenceArgument


class Operator(ABC):
    """Airflow task 본문으로 실행되는 동작의 추상 베이스이다."""

    @abstractmethod
    def run(self, context:Optional[DagContext]=None) -> None:
        """`context` 하에서 이 Operator를 실행한다.
        `context`가 `None`이면 기본 컨텍스트를 생성한다."""
        ...
