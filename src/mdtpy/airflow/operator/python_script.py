"""Python script를 실행하는 `PythonScriptOperator`를 정의한다."""

from __future__ import annotations

from typing import Any, Mapping, Optional

import logging

from ... import ElementReference
from ...value.element_value import ElementValue, mdt_value
from ..dag_context import DagContext, AirflowDagContext
from .operator import Operator, DagTaskInputArgument

logger = logging.getLogger(__name__)

__all__ = ['PythonScriptOperator']


class PythonScriptOperator(Operator):
    """주어진 Python script를 실행하고, script가 정의한 변수를 출력으로 기록하는 Operator이다.

    script는 `inputs`라는 이름의 dict(입력 이름 → 해석된 입력 값)를 전역 변수로 받는다.
    script 실행이 끝나면 `outputs`에 선언된 각 이름과 같은 이름의 변수 값을 읽어 task 출력으로
    전달하고, 저장 위치(`ElementReference`)가 지정된 출력은 해당 SubmodelElement에도 기록한다.
    """

    def __init__(self, script: str, *,
                inputs: Mapping[str, DagTaskInputArgument],
                outputs: Mapping[str, Optional[ElementReference]] = {}) -> None:
        """Operator를 생성한다.

        :param script: 실행할 Python script.
        :param inputs: script 입력 인자 명세. (입력 이름 → `DagTaskArgument`)
        :param outputs: script 출력 명세. (출력 변수 이름 → 저장 위치 `ElementReference`)
            선언된 모든 출력은 task 출력으로 전달된다. 저장 위치가 `None`인 출력은
            SubmodelElement에 기록하지 않고 후속 task에만 전달된다.
        """
        self.script = script
        self.inputs = inputs
        self.outputs = outputs

    def run(self, context:Optional[DagContext]=None) -> None:
        """입력 인자를 해석하여 script를 실행하고, 결과를 task 출력과 (지정된 경우) 저장 위치에 기록한다.

        :raises KeyError: `outputs`에 선언된 변수를 script가 정의하지 않은 경우.
        """
        if context is None:
            context = AirflowDagContext()

        logger.info(f"Running script with inputs {self.inputs} and outputs {self.outputs}")

        in_args = { arg_id: arg.get(context) for arg_id, arg in self.inputs.items() }

        # globals와 locals를 하나의 dict로 사용한다. 둘을 분리하면 script 최상위가 클래스 본문처럼
        # 실행되어, script에서 정의한 이름(import, 변수)을 함수/lambda/generator 식 안에서 찾지 못한다.
        out_values = {}
        namespace:dict[str, Any] = {'inputs': in_args, 'outputs': out_values}
        exec(self.script, namespace)

        # 선언된 출력 변수를 script가 모두 정의했는지 확인한다.
        missing = [key for key in self.outputs if key not in out_values]
        if missing:
            raise KeyError(f"script did not define output variable(s): {missing}")

        # 일부 출력만 기록된 채로 실패하지 않도록, 모든 출력 값을 먼저 변환한 뒤에 기록한다.
        for key, value in out_values.items():
            ref = self.outputs.get(key)
            if ref is not None:
                if not isinstance(value, ElementValue):
                    value = mdt_value(value)
                ref.update_value(value)

        # 저장 위치 지정 여부와 관계없이, 선언된 모든 출력을 후속 task에 전달한다.
        context.set_task_outputs(out_values)

    def __repr__(self) -> str:
        return ( f"{self.__class__.__name__}(inputs={self.inputs}, "
                 f"outputs={self.outputs})" )
