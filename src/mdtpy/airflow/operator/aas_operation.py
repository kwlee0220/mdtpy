"""submodel 내 AAS `Operation`을 idShort 경로로 지정해 호출하는 `AASOperationOperator`를 정의한다."""

from __future__ import annotations

from typing import Mapping, Optional

import logging

from ... import ElementReference, OperationSubmodelService
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
        """대상 submodel이 Operation submodel인지 확인한 뒤 인자를 해석하여 호출한다."""
        logger.info(f"Invoking operation {self.instance}:{self.submodel}:{self.path} "
                    f"with inputs {self.inputs} and outputs {self.outputs}")
        if context is None:
            context = AirflowDagContext()

        submodel_svc = context.get_submodel(self.instance, self.submodel)
        # 조회된 Submodel이 OperationSubmodelService가 아니면 예외를 발생시킨다.
        if not isinstance(submodel_svc, OperationSubmodelService):
            raise ValueError(f"Submodel {self.instance}:{self.submodel} is not an operation submodel")

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
