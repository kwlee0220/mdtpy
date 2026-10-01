"""task 실행 시점에 인자 값을 얻는 방법을 기술하는 `DagTaskArgument`들을 정의한다.

각 `DagTaskArgument`은 "값을 어떻게 구할지"에 대한 명세이며, 실제 값은 task 실행
시점에 `DagContext`를 받아 `get()`을 호출할 때 결정된다. 세 가지 구현이 있다.

- `TaskOutputArgument`: 선행 task가 남긴 출력 값을 참조한다.
- `ElementReferenceArgument`: reference 문자열을 해석하여 그 값을 읽어 반환하되,
  값이 File이면 참조 자체를 반환한다(File 입력을 참조로 전달하기 위함).
- `LiteralArgument`: 고정된 리터럴 값을 그대로 사용한다.

각 구현에는 동일 이름의 팩토리 헬퍼(`task_output`, `reference`, `literal`)가 있어
호출부에서 간결하게 명세를 생성할 수 있다.
"""

from __future__ import annotations

from typing import Any

from abc import ABC, abstractmethod

import mdtpy
from ..ref.reference import ElementReference
from ..value.element_value import FileValue
from ..value.types import PropertyJsonValue

from .. import ElementValue, mdt_value
from .types import ArgumentValue
from .dag_context import DagContext

__all__ = ['task_output', 'reference', 'literal', 'sink',
           'DagTaskArgument', 'TaskOutputArgument', 'ElementReferenceArgument', 'LiteralArgument']


def task_output(task_id:str, argument:str) -> TaskOutputArgument:
    """`task_id` task의 출력 인자 `argument`를 참조하는 명세를 생성한다."""
    return TaskOutputArgument(task_id, argument)

def reference(ref_string:str) -> ElementReferenceArgument:
    """reference 문자열을 가리키는 명세를 생성한다."""
    return ElementReferenceArgument(ref_string)

def literal(value:Any) -> LiteralArgument:
    """고정된 리터럴 값을 담는 명세를 생성한다.

    `ElementValue`가 아닌 raw 스칼라 값(str/bool/int/float 등)은 `mdt_value()`로 감싼다.
    """
    return LiteralArgument(value)

def sink(ref_string:str) -> ElementReference:
    """reference 문자열을 가리키는 명세를 생성한다."""
    return mdtpy.reference(ref_string)


class DagTaskArgument(ABC):
    """task 실행 시점에 인자 값을 얻는 방법을 기술하는 추상 베이스이다."""

    @abstractmethod
    def get(self, context:DagContext) -> ArgumentValue:
        """`context`를 사용하여 이 명세가 가리키는 값(또는 `ElementReference`)을 구한다.
        대부분의 경우 `ElementValue`를 사용하지만 'File' 타입의 입력을 지원하기 위해
        `ElementReference`를 반환할 수 있다.
        """
        ...


class TaskOutputArgument(DagTaskArgument):
    """선행 task가 남긴 출력 인자 값을 참조하는 명세이다."""

    def __init__(self, task_id:str, arg_id:str) -> None:
        self.task_id = task_id
        self.arg_id = arg_id

    def get(self, context:DagContext) -> ArgumentValue:
        """`context`에서 `task_id` task의 출력 인자 `argument` 값을 조회한다."""
        return context.get_task_output(self.task_id, self.arg_id)

    def __repr__(self) -> str:
        return f"task_output({self.task_id}[{self.arg_id}])"


class ElementReferenceArgument(DagTaskArgument):
    """reference 문자열을 `ElementReference`로 해석하는 명세이다."""

    def __init__(self, ref_string:str) -> None:
        self.ref_string = ref_string

    def get(self, context:DagContext) -> ArgumentValue:
        """`context`를 사용하여 reference 문자열을 `ElementReference`로 해석해서
        그 값이 FileValue이면 참조 자체를 반환하고, 그렇지 않으면 값을 읽어 반환한다."""
        ref = context.resolve_reference(self.ref_string)

        # 'TimeSeries' 타입의 경우에는 ElementValue가 아니라 SubmodelElement 자체를 사용한다.
        if ref.ref_string.startswith("timeseries:"):
            return ref.read()
        else:
            val = ref.read_value()
            if isinstance(val, FileValue):
                return ref
            else:
                return val

    def __repr__(self) -> str:
        return f"reference({self.ref_string})"


class LiteralArgument(DagTaskArgument):
    """고정된 리터럴 값을 그대로 제공하는 명세이다.

    `ElementValue`가 아닌 raw 스칼라 값이 주어지면 `mdt_value()`로 감싸 보관하므로,
    `get()`은 항상 `ElementValue`를 반환한다.
    """

    def __init__(self, value:ElementValue|PropertyJsonValue) -> None:
        self.value = value if isinstance(value, ElementValue) else mdt_value(value)

    def get(self, context:DagContext) -> ElementValue:
        """`context`와 무관하게 보관된 리터럴 값을 반환한다."""
        return self.value

    def __repr__(self) -> str:
        return f"literal({self.value})"
