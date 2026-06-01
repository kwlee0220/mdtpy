"""task 실행 시점에 인자 값을 얻는 방법을 기술하는 `ArgumentSpec`들을 정의한다.

각 `ArgumentSpec`은 "값을 어떻게 구할지"에 대한 명세이며, 실제 값은 task 실행
시점에 `DagContext`를 받아 `get()`을 호출할 때 결정된다. 세 가지 구현이 있다.

- `TaskOutputArgumentSpec`: 선행 task가 남긴 출력 값을 참조한다.
- `ElementReferenceArgumentSpec`: reference 문자열을 `ElementReference`로 해석한다.
- `LiteralArgumentSpec`: 고정된 리터럴 값을 그대로 사용한다.

각 구현에는 동일 이름의 팩토리 헬퍼(`task_output`, `reference`, `literal`)가 있어
호출부에서 간결하게 명세를 생성할 수 있다.
"""

from __future__ import annotations

from typing import Optional

from abc import ABC, abstractmethod

from ..reference import ElementReference
from ..value import ElementValueType
from .dag_context import DagContext


__all__ = ['task_output', 'reference', 'literal', 'ArgumentSpec',
           'TaskOutputArgumentSpec', 'ElementReferenceArgumentSpec', 'LiteralArgumentSpec']


def task_output(task_id:str, argument:str) -> TaskOutputArgumentSpec:
    """`task_id` task의 출력 인자 `argument`를 참조하는 명세를 생성한다."""
    return TaskOutputArgumentSpec(task_id, argument)

def reference(ref_string:str) -> ElementReferenceArgumentSpec:
    """reference 문자열을 가리키는 명세를 생성한다."""
    return ElementReferenceArgumentSpec(ref_string)

def literal(value:ElementValueType) -> LiteralArgumentSpec:
    """고정된 리터럴 값을 담는 명세를 생성한다."""
    return LiteralArgumentSpec(value)


class ArgumentSpec(ABC):
    """task 실행 시점에 인자 값을 얻는 방법을 기술하는 추상 베이스이다."""

    @abstractmethod
    def get(self, context:DagContext) -> ElementReference|Optional[ElementValueType]:
        """`context`를 사용하여 이 명세가 가리키는 값(또는 `ElementReference`)을 구한다."""
        ...


class TaskOutputArgumentSpec(ArgumentSpec):
    """선행 task가 남긴 출력 인자 값을 참조하는 명세이다."""

    def __init__(self, task_id:str, argument:str) -> None:
        self.task_id = task_id
        self.argument = argument

    def get(self, context:DagContext) -> Optional[ElementValueType]:
        """`context`에서 `task_id` task의 출력 인자 `argument` 값을 조회한다."""
        return context.get_task_output_argument(self.task_id, self.argument)

    def __repr__(self) -> str:
        return f"task_output({self.task_id}[{self.argument}])"


class ElementReferenceArgumentSpec(ArgumentSpec):
    """reference 문자열을 `ElementReference`로 해석하는 명세이다."""

    def __init__(self, ref_string:str) -> None:
        self.ref_string = ref_string

    def get(self, context:DagContext) -> ElementReference:
        """`context`를 사용하여 reference 문자열을 `ElementReference`로 해석한다."""
        return context.resolve_reference(self.ref_string)

    def __repr__(self) -> str:
        return f"reference({self.ref_string})"


class LiteralArgumentSpec(ArgumentSpec):
    """고정된 리터럴 값을 그대로 제공하는 명세이다."""

    def __init__(self, value:ElementValueType) -> None:
        self.value = value

    def get(self, context:DagContext) -> ElementValueType:
        """`context`와 무관하게 보관된 리터럴 값을 반환한다."""
        return self.value

    def __repr__(self) -> str:
        return f"literal({self.value})"
