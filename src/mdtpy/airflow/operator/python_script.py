"""Python script를 실행하는 `PythonScriptOperator`를 정의한다."""

from __future__ import annotations

from typing import Any, Mapping, Optional

import logging

from ... import ElementReference
from ...value.element_value import ElementValue, to_element_value
from ..dag_context import DagContext, AirflowDagContext
from .operator import Operator, DagTaskInputArgument

logger = logging.getLogger(__name__)

__all__ = ['PythonScriptOperator']


class PythonScriptOperator(Operator):
    """주어진 Python script를 실행하고, script가 `outputs` dict에 넣은 값을 task 출력으로 전달하는 Operator이다.

    script는 두 개의 dict를 전역 변수로 받는다. `inputs`는 입력 이름 → 해석된 입력 값이고,
    `outputs`는 빈 dict로, script가 `outputs['<출력 이름>'] = 값` 형태로 출력 값을 넣는다.
    script 실행이 끝나면 `outputs` dict에 들어 있는 모든 값을 task 출력으로 전달하고, 그중 operator의
    `outputs` 인자에 저장 위치(`ElementReference`)가 지정된 값은 해당 SubmodelElement에도 기록한다.
    """

    def __init__(self, script: str, *,
                inputs: Mapping[str, DagTaskInputArgument],
                outputs: Mapping[str, Optional[ElementReference]] = {}) -> None:
        """Operator를 생성한다.

        :param script: 실행할 Python script.
        :param inputs: script 입력 인자 명세. (입력 이름 → `DagTaskArgument`)
        :param outputs: 저장 위치 명세. (출력 이름 → 저장 위치 `ElementReference`)
            task 출력으로 전달되는 값은 이 명세와 무관하게 script가 `outputs` dict에 넣은 모든 값이며,
            이 명세는 그중 어떤 값을 어디에 기록할지만 정한다. script가 넣지 않은 이름은 기록하지 않고
            넘어간다. 저장 위치가 `None`인 항목은 아무 효과가 없다(이전 버전과의 호환을 위해 허용).
        """
        self.script = script
        self.inputs = inputs
        self.outputs = outputs

    def run(self, context:Optional[DagContext]=None) -> None:
        """입력 인자를 해석하여 script를 실행하고, 결과를 task 출력과 (지정된 경우) 저장 위치에 기록한다.

        script가 `outputs` dict에 넣은 모든 값이 task 출력으로 전달된다. 저장 위치가 지정됐더라도
        script가 그 값을 넣지 않았으면 해당 저장 위치는 갱신하지 않는다.
        `ElementValue`가 아닌 출력 값은 `to_element_value()`로 변환된다. 스칼라는 `PropertyValue`가 되고,
        dict는 `ElementCollectionValue`, list/tuple은 `ElementListValue`로 멤버까지 재귀적으로 변환된다.

        :raises ValueError: 출력 값을 `to_element_value()`로 변환할 수 없는 경우. 변환은 기록 전에 모두
            수행되므로, 이때는 어떤 저장 위치도 갱신되지 않는다.
        """
        if context is None:
            context = AirflowDagContext()

        logger.info(f"Running script with inputs {self.inputs} and outputs {self.outputs}")

        in_args = { arg_id: arg.get(context) for arg_id, arg in self.inputs.items() }

        # globals와 locals를 하나의 dict로 사용한다. 둘을 분리하면 script 최상위가 클래스 본문처럼
        # 실행되어, script에서 정의한 이름(import, 변수)을 함수/lambda/generator 식 안에서 찾지 못한다.
        # 스크립트 수행 중 'out_values'에 등록되는 값이 최종 출력으로 사용된다.
        out_values = {}
        namespace:dict[str, Any] = {'inputs': in_args, 'outputs': out_values}
        exec(self.script, namespace)

        # script가 outputs dict에 넣은 값은 모두 task 출력이 된다. operator의 `outputs`는 그중
        # 어떤 값을 어디에 기록할지만 정한다.
        # 일부 출력만 기록된 채로 실패하지 않도록, 모든 출력 값을 먼저 변환한 뒤에 기록한다.
        task_outputs:dict[str, ElementValue] = {
            key: to_element_value(value) for key, value in out_values.items()
        }

        # 저장 위치가 지정됐더라도 script가 그 값을 넣지 않았으면 기록하지 않고 넘어간다.
        for key, ref in self.outputs.items():
            if ref is not None and key in task_outputs:
                ref.update_value(task_outputs[key])

        # 저장 위치 지정 여부와 관계없이, script가 넣은 모든 출력을 후속 task에 전달한다.
        context.set_task_outputs(task_outputs)

    def __repr__(self) -> str:
        return ( f"{self.__class__.__name__}(inputs={self.inputs}, "
                 f"outputs={self.outputs})" )
