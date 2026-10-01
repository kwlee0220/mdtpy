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
        if context is None:
            context = AirflowDagContext()

        in_args = { arg_id: arg.get(context) for arg_id, arg in self.inputs.items() }
        rpc_client = RESTfulAsyncRpcClient(base_url=self.base_url, op_endpoint=self.op_endpoint,
                                            inputs=in_args)
        results = rpc_client.call()
        for arg_id, arg_value in results.items():
            if not isinstance(arg_value, ElementValue):
                arg_value = mdt_value(arg_value)
                results[arg_id] = arg_value
            if arg_id in self.outputs:
                self.outputs[arg_id].update_value(arg_value)

        context.set_task_outputs(results)
