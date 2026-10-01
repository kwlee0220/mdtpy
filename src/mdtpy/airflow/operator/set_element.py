"""`source`에서 값을 읽어 선택적으로 `target`에 기록하는 `SetElementOperator`를 정의한다."""

from __future__ import annotations

from typing import Optional, Mapping

from ... import ElementReference
from ..dag_task_argument import ArgumentValue
from ..dag_context import DagContext, AirflowDagContext
from ...value.element_value import ElementValue
from .operator import Operator, DagTaskInputArgument

__all__ = ['SetElementOperator']


def _to_element_value(arg:ArgumentValue) -> ElementValue:
    """`arg`가 ElementReference이면 값을 읽어 ElementValue로 변환한다."""
    if isinstance(arg, ElementReference):
        return arg.read_value()
    else:
        return arg


class SetElementOperator(Operator):
    """`source` 입력에서 값을 읽어 선택적으로 `target`에 기록하는 `Operator`이다.

    `inputs['source']`(필수)는 어떤 입력이든 될 수 있는 `DagTaskInputArgument`이며, 없으면
    생성 시점에 `ValueError`를 발생시킨다. `outputs['target']`(선택)은 값을 기록할
    `ElementReference`이며, `outputs`를 지정했는데 `'target'`이 없어도 `ValueError`를
    발생시킨다. `run`은 `source` 값을 읽어, `target`이 주어진 경우 그 참조에 기록하고,
    어느 경우든 읽은 값을 `'target'` 키로 task 출력에 저장한다.
    """

    def __init__(self, inputs: Mapping[str, DagTaskInputArgument],
                 outputs: Mapping[str, ElementReference] = {}) -> None:
        if 'source' not in inputs:
            raise ValueError("Input argument 'source' is required")
        if outputs and 'target' not in outputs:
            raise ValueError("Output argument 'target' is required if outputs are provided")

        self.inputs = inputs
        self.outputs = outputs

    def run(self, context:Optional[DagContext]=None) -> None:
        """`source` 값을 읽어 `target`(있는 경우)에 기록하고 task 출력으로 저장한다."""
        if context is None:
            context = AirflowDagContext()

        # 입력 인자 `source`를 해석하여 값을 읽는다.
        # SetElement는 항상 값이 필요하므로(File 참조도 값으로 읽음) `_to_element_value`만 쓴다.
        src = self.inputs['source'].get(context)
        v = _to_element_value(src)

        # `target`이 지정되어 있으면 값을 기록한다.
        if 'target' in self.outputs:
            self.outputs['target'].update_value(v)

        # task의 출력에도 `value`를 기록한다.
        context.set_task_outputs({'target': v})
