"""AAS Operation을 RESTful RPC 방식으로 호출하는 `RestfulAsyncRpcOperator`를 정의한다."""

from __future__ import annotations

from typing import Mapping, Optional

from ... import ElementReference
from ...rpc.restful.restful_async_rpc_client import RESTfulAsyncRpcClient
from ...value.element_value import ElementValue, mdt_value
from ..dag_context import DagContext, AirflowDagContext
from .operator import Operator, DagTaskInputArgument

__all__ = ['RestfulAsyncRpcOperator']


class RestfulAsyncRpcOperator(Operator):
    """AAS Operation을 RESTful RPC 방식으로 호출하는 Operator이다."""

    def __init__(self, base_url: str, op_endpoint: str, *,
                inputs: Mapping[str, DagTaskInputArgument],
                outputs: Mapping[str, ElementReference] = {}) -> None:
        self.base_url = base_url
        self.op_endpoint = op_endpoint
        self.inputs = inputs
        self.outputs = outputs

    def run(self, context:Optional[DagContext]=None) -> None:
        """입력 인자를 해석하여 연산을 호출하고, 결과를 task 출력과 (지정된 경우) 저장 위치에 기록한다.

        연산이 반환한 모든 결과가 task 출력으로 전달되며, 그중 `outputs`에 선언된 결과만 저장 위치에
        기록된다. `ElementValue`가 아닌 결과는 `mdt_value()`로 변환된다.

        :raises ValueError: 결과를 `mdt_value()`로 변환할 수 없는 경우. 변환은 기록 전에 모두
            수행되므로, 이때는 어떤 저장 위치도 갱신되지 않는다.
        """
        if context is None:
            context = AirflowDagContext()

        in_args = { arg_id: arg.get(context) for arg_id, arg in self.inputs.items() }
        rpc_client = RESTfulAsyncRpcClient(base_url=self.base_url, op_endpoint=self.op_endpoint,
                                            inputs=in_args)
        results = rpc_client.call()

        # 일부 결과만 기록된 채로 실패하지 않도록, 모든 결과를 먼저 변환한 뒤에 기록한다.
        out_values = { arg_id: value if isinstance(value, ElementValue) else mdt_value(value)
                       for arg_id, value in results.items() }
        for arg_id, value in out_values.items():
            if arg_id in self.outputs:
                self.outputs[arg_id].update_value(value)

        # 저장 위치 지정 여부와 관계없이, 변환된 모든 결과를 후속 task에 전달한다.
        context.set_task_outputs(out_values)
