"""Airflow task 본문으로 실행되는 `Invocation`들을 정의한다.

`Invocation`은 `ArgumentSpec`으로 기술된 입력/출력 명세를 받아, task 실행 시점에
`DagContext`를 통해 실제 값을 해석하고 동작을 수행한다. 두 가지 구현이 있다.

- `SetElementInvocation`: `source`에서 값을 읽어 선택적으로 `target`에 기록한다.
- `AASOperationTaskInvocation`: 특정 instance의 submodel `Operation`을 호출한다.

입력/출력 명세는 `InvocationArgumentSpecs`(TypedDict) 형태로 전달한다.
"""

from __future__ import annotations

from typing import Optional, TypedDict
from typing_extensions import NotRequired

from abc import ABC, abstractmethod

import logging
logger = logging.getLogger(__name__)

from ..reference import ElementReference
from ..operation import OperationSubmodelService
from .argument_spec import ElementReferenceArgumentSpec, LiteralArgumentSpec, TaskOutputArgumentSpec
from .dag_context import DagContext, AirflowDagContext

InputArgumentSpecType = TaskOutputArgumentSpec | ElementReferenceArgumentSpec | LiteralArgumentSpec
OutputArgumentSpecType = ElementReferenceArgumentSpec

__all__ = ['InvocationArgumentSpecs', 'Invocation', 'SetElementInvocation',
           'AASOperationTaskInvocation', 'get_input_argument_dict', 'get_output_argument_dict',
           'InputArgumentSpecType', 'OutputArgumentSpecType']


class InvocationArgumentSpecs(TypedDict):
    """Invocation의 입력/출력 인자 명세를 담는 형식이다.

    `inputs`는 필수이며, 각 인자 id를 입력 명세에 매핑한다. `outputs`는 선택이며,
    연산 결과를 기록할 `ElementReference` 명세를 인자 id에 매핑한다.
    """

    inputs: NotRequired[dict[str, InputArgumentSpecType]]
    outputs: NotRequired[dict[str, OutputArgumentSpecType]]

def get_input_argument_dict(argument_specs: InvocationArgumentSpecs) -> dict[str, InputArgumentSpecType]:
    """`argument_specs`에서 입력 명세 dict를 반환하며, 없으면 빈 dict를 반환한다."""
    return argument_specs.get('inputs', {})

def get_output_argument_dict(argument_specs: InvocationArgumentSpecs) -> dict[str, OutputArgumentSpecType]:
    """`argument_specs`에서 출력 명세 dict를 반환하며, 없으면 빈 dict를 반환한다."""
    return argument_specs.get('outputs', {})


class Invocation(ABC):
    """Airflow task 본문으로 실행되는 동작의 추상 베이스이다."""

    @abstractmethod
    def run(self, context:Optional[DagContext]=None) -> None:
        """`context` 하에서 이 Invocation을 실행한다. `context`가 `None`이면 기본 컨텍스트를 생성한다."""
        ...


class SetElementInvocation(Invocation):
    """`source` 입력에서 값을 읽어 선택적으로 `target` 출력에 기록하는 Invocation이다.

    `inputs`에는 반드시 `source` 키가 있어야 한다. `outputs`에 `target` 키가 있으면
    해당 `ElementReference`에 값을 기록하며, 어느 경우든 읽은 값은 `'target'` 키로
    task 출력에 저장된다. `source`/`target` 외의 키는 무시된다.
    """

    def __init__(self, argument_specs: InvocationArgumentSpecs) -> None:
        self.argument_specs = argument_specs

    def run(self, context:Optional[DagContext]=None) -> None:
        """`source` 값을 읽어 `target`(있는 경우)에 기록하고 task 출력으로 저장한다."""
        if context is None:
            context = AirflowDagContext()

        in_args = get_input_argument_dict(self.argument_specs)
        if 'source' not in in_args:
            raise ValueError("Input argument 'source' is required")

        src_args = in_args['source'].get(context)
        # `src_arg`가 `ElementReference`이면 값을 읽고, 아니면 그대로 사용한다.
        src_value = src_args.read_value() if isinstance(src_args, ElementReference) else src_args

        out_args = get_output_argument_dict(self.argument_specs)
        if 'target' in out_args:
            out_args['target'].get(context).update_value(src_value)

        # task의 출력에도 `src_value`를 기록한다.
        context.set_task_output({'target': src_value})


class AASOperationTaskInvocation(Invocation):
    """특정 instance의 submodel `Operation`을 호출하는 Invocation이다.

    `run`은 입력 명세와 출력 명세를 병합하여 `invoke`에 넘긴다. 출력 명세를 함께
    전달하는 이유는, `OperationSubmodelService.invoke`가 kwargs로 받은
    `ElementReference` 중 출력 인자에 해당하는 것에 연산 결과를 자동으로 기록하기
    때문이다.
    """

    def __init__(self, instance: str, submodel: str,
                 argument_specs: InvocationArgumentSpecs) -> None:
        self.instance = instance
        self.submodel = submodel
        self.argument_specs = argument_specs

    def run(self, context:Optional[DagContext]=None) -> None:
        """대상 submodel이 Operation submodel인지 확인한 뒤 인자를 해석하여 호출한다."""
        logger.info(f"Invoking operation {self.instance}:{self.submodel} "
                    f"with arguments {self.argument_specs}")
        if context is None:
            context = AirflowDagContext()

        submodel = context.get_submodel(self.instance, self.submodel)
        # 조회된 Submodel이 OperationSubmodelService가 아니면 예외를 발생시킨다.
        if not isinstance(submodel, OperationSubmodelService):
            raise ValueError(f"Submodel {self.instance}:{self.submodel} is not an operation submodel")

        # 입력 인자 규격에서 인자로 변환하여 연산을 호출한다.
        arg_list = get_input_argument_dict(self.argument_specs) | get_output_argument_dict(self.argument_specs)
        args = { arg_id: arg.get(context) for arg_id, arg in arg_list.items() }

        # submodel.invoke는 출력 인자에 해당하는 ElementReference에 연산 결과를 자동으로 기록한다.
        out_arg_values = submodel.invoke(**args)
        context.set_task_output(out_arg_values)

    def __repr__(self) -> str:
        return ( f"{self.__class__.__name__}(task={self.instance}:{self.submodel}, "
                 f"inputs={get_input_argument_dict(self.argument_specs)}, "
                 f"outputs={get_output_argument_dict(self.argument_specs)})" )
