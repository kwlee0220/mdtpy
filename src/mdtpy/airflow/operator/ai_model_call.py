"""AI 모델 연산을 동기 방식의 RESTful RPC로 호출하는 `AIModelCallOperator`를 정의한다."""

from __future__ import annotations

from typing import Mapping, Optional

import logging

from ... import ElementReference
from ...rpc.restful.common import encode_argument_to_json_node
from ...rpc.restful.restful_rpc_client import RESTfulRpcClient
from ...value.element_value import ElementValue, mdt_value
from ..dag_context import DagContext, AirflowDagContext
from .operator import Operator, DagTaskInputArgument

logger = logging.getLogger(__name__)

__all__ = ['AIModelCallOperator']


class AIModelCallOperator(Operator):
    """AI 모델 연산을 동기 방식의 RESTful RPC로 호출하는 Operator이다.

    `RestfulAsyncRpcOperator`와 달리 연산 상태를 폴링하지 않는다. 단일 POST 요청이
    연산이 종료될 때까지 블록하고 그 응답에 출력이 실려온다. 그래서 `base_url` +
    `op_endpoint`로 나누지 않고 AI 모델 URL 전체를 `model_url`로 받는다.
    """

    def __init__(self, model_url: str, *,
                timeout: Optional[float] = None,
                inputs: Mapping[str, DagTaskInputArgument],
                outputs: Mapping[str, Optional[ElementReference]] = {}) -> None:
        """Operator를 생성한다.

        :param model_url: AI 모델 URL. (필수)
        :param timeout: 응답 대기 제한 시간(초). `None`이면 제한 없이 대기한다.
            동기 호출은 단일 응답이 연산 종료 시점까지 지연되고 AI 모델 추론은 수 분
            이상 걸릴 수 있어서, 기본값을 제한 없음으로 둔다.
        :param inputs: 연산 입력 인자 명세. (입력 이름 → `DagTaskArgument`)
        :param outputs: 연산 출력 명세. (출력 이름 → 저장 위치 `ElementReference`)
            선언된 출력만 task 출력으로 전달되며, 연산이 반환했더라도 선언되지 않은 출력은
            무시된다. 저장 위치가 `None`인 출력은 SubmodelElement에 기록하지 않고 후속
            task에만 전달된다.
        :raises ValueError: `model_url`이 비어 있는 경우. (`RESTfulRpcClient`가 발생시킨다)
        """
        self.model_url = model_url
        self.timeout = timeout
        self.inputs = inputs
        self.outputs = outputs

    def run(self, context:Optional[DagContext]=None) -> None:
        """입력 인자를 해석하여 연산을 호출하고, 결과를 task 출력과 (지정된 경우) 저장 위치에 기록한다.

        :raises KeyError: `outputs`에 선언된 출력을 연산이 반환하지 않은 경우.
        """
        if context is None:
            context = AirflowDagContext()

        logger.info(f"Calling AI model operation {self.model_url} "
                    f"with inputs {self.inputs} and outputs {self.outputs}")

        # RESTfulAsyncRpcClient는 입력을 내부에서 인코딩하지만 RESTfulRpcClient는 JSON-ready
        # 값을 요구하기 때문에, ElementValue 등을 여기서 JSON 노드로 변환해서 넘긴다.
        in_args = { arg_id: encode_argument_to_json_node(arg.get(context))
                    for arg_id, arg in self.inputs.items() }
        rpc_client = RESTfulRpcClient(self.model_url, inputs=in_args, timeout=self.timeout)
        results = rpc_client.call()

        # 선언된 출력을 연산이 모두 반환했는지 확인한다.
        missing = [key for key in self.outputs if key not in results]
        if missing:
            raise KeyError(f"AI model operation did not return output(s): {missing}")

        # 일부 출력만 기록된 채로 실패하지 않도록, 모든 출력 값을 먼저 변환한 뒤에 기록한다.
        # 출력이 ElementValue가 아닌 경우(예: JSON 리터럴)에는 ElementValue로 변환한다.
        out_values = {}
        for key in self.outputs:
            value = results[key]
            out_values[key] = value if isinstance(value, ElementValue) else mdt_value(value)
        for key, value in out_values.items():
            ref = self.outputs[key]
            if ref is not None:
                ref.update_value(value)

        # 저장 위치 지정 여부와 관계없이, 선언된 모든 출력을 후속 task에 전달한다.
        context.set_task_outputs(out_values)

    def __repr__(self) -> str:
        return ( f"{self.__class__.__name__}(model_url={self.model_url}, "
                 f"inputs={self.inputs}, "
                 f"outputs={self.outputs})" )
