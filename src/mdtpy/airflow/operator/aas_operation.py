"""submodel 내 AAS `Operation`을 idShort 경로로 지정해 호출하는 `AASOperationOperator`를 정의한다."""

from __future__ import annotations

from typing import Mapping, Optional

import logging

from ... import ElementReference
from ...operation.aas_operation import AASOperationService
from ..dag_context import DagContext, AirflowDagContext
from .operator import Operator, DagTaskInputArgument

logger = logging.getLogger(__name__)

__all__ = ['AASOperationOperator']


class AASOperationOperator(Operator):
    def __init__(self, instance: str, submodel: str, path: str, *,
                inputs: Mapping[str, DagTaskInputArgument],
                outputs: Mapping[str, ElementReference] = {}) -> None:
        self.instance = instance
        self.submodel = submodel
        self.path = path
        self.inputs = inputs
        self.outputs = outputs

    def run(self, context:Optional[DagContext]=None) -> None:
        """submodel 내 `path` 위치의 Operation을 인자를 해석하여 호출한다.

        submodel의 종류(Data/Simulation/AI 등)는 확인하지 않는다. AAS `Operation` 요소는 어느
        submodel에나 있을 수 있고(예: Data submodel의 로봇 이동 연산), 호출은 submodel 공통의
        invoke 경로를 쓰기 때문이다. Java `AASOperationTask`도 같은 방식으로 동작한다.
        `path`가 가리키는 요소가 `Operation`인지는 `AASOperationService`가 확인한다.
        """
        logger.info(f"Invoking operation {self.instance}:{self.submodel}:{self.path} "
                    f"with inputs {self.inputs} and outputs {self.outputs}")
        if context is None:
            context = AirflowDagContext()

        submodel_svc = context.get_submodel(self.instance, self.submodel)
        op_client = AASOperationService(submodel_svc, self.path)
        in_args = { arg_id: arg.get(context) for arg_id, arg in self.inputs.items() }
        results = op_client.invoke(**in_args)
        for arg_id, arg_value in results.items():
            if arg_id in self.outputs:
                self.outputs[arg_id].update_value(arg_value)

        context.set_task_outputs(results)

    def __repr__(self) -> str:
        return ( f"{self.__class__.__name__}(task={self.instance}:{self.submodel}, "
                 f"inputs={self.inputs}, "
                 f"outputs={self.outputs})" )
