"""특정 instance의 submodel `Operation`을 호출하는 `OperationSubmodelOperator`를 정의한다."""

from __future__ import annotations

from typing import Mapping, Optional

import logging

from ... import ElementReference, OperationSubmodelService
from ..dag_context import DagContext, AirflowDagContext
from .operator import Operator, DagTaskInputArgument

logger = logging.getLogger(__name__)

__all__ = ['OperationSubmodelOperator']


class OperationSubmodelOperator(Operator):
    """특정 instance의 submodel `Operation`을 호출하는 `Operator`이다.

    `run`은 입력 명세와 출력 명세를 병합하여 `invoke`에 넘긴다. 출력 명세를 함께
    전달하는 이유는, `OperationSubmodelService.invoke`가 kwargs로 받은
    `ElementReference` 중 출력 인자에 해당하는 것에 연산 결과를 자동으로 기록하기
    때문이다.
    """

    def __init__(self, instance: str, submodel: str, *,
                inputs: Mapping[str, DagTaskInputArgument],
                outputs: Mapping[str, ElementReference] = {}) -> None:
        self.instance = instance
        self.submodel = submodel
        self.inputs = inputs
        self.outputs = outputs

    def run(self, context:Optional[DagContext]=None) -> None:
        """대상 submodel이 Operation submodel인지 확인한 뒤 인자를 해석하여 호출한다."""
        logger.info(f"Invoking operation {self.instance}:{self.submodel} "
                    f"with inputs {self.inputs} and outputs {self.outputs}")
        if context is None:
            context = AirflowDagContext()

        submodel = context.get_submodel(self.instance, self.submodel)
        # 조회된 Submodel이 OperationSubmodelService가 아니면 예외를 발생시킨다.
        if not isinstance(submodel, OperationSubmodelService):
            raise ValueError(f"Submodel {self.instance}:{self.submodel} is not an operation submodel")

        # 입력 인자와 출력 인자를 병합하여 kwargs로 전달한다.
        # 출력 인자는 연산 결과를 기록할 ElementReference이다.
        in_args = { arg_id: arg.get(context) for arg_id, arg in self.inputs.items() }
        args = { **in_args, **self.outputs }

        # submodel.invoke는 출력 인자에 해당하는 ElementReference에 연산 결과를 자동으로 기록한다.
        out_arg_values = submodel.invoke(**args)
        context.set_task_outputs(out_arg_values)

    def __repr__(self) -> str:
        return ( f"{self.__class__.__name__}(task={self.instance}:{self.submodel}, "
                 f"inputs={self.inputs}, "
                 f"outputs={self.outputs})" )
