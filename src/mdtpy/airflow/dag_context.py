"""Airflow task 실행 시점의 런타임 어댑터를 정의한다.

`DagContext`는 Invocation이 task 본문을 실행할 때 필요한 런타임 기능
(submodel 조회, reference 해석, task 간 출력 값 전달)을 추상화한다.
구현체는 두 가지이다.

- `LocalDagContext`: task 출력을 프로세스 내 클래스 변수에 보관하여 단일 프로세스
  안에서 DAG 흐름을 검증한다.
- `AirflowDagContext`: 실제 Airflow 런타임에서 XCom과 Variable을 사용한다.
  task 출력은 `@type`/`value` JSON 형태로 직렬화하여 XCom에 저장한다.
  `airflow.sdk` import를 메서드 호출 시점으로 지연시켜, 본 서브패키지를
  사용하는 쪽이 항상 Airflow를 설치하지 않아도 되도록 한다.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, cast
from abc import ABC, abstractmethod

import logging
logger = logging.getLogger(__name__)

from .types import TaskOutput
from .. import (
    connect, SubmodelService, ElementReference, ElementValue, MDTInstanceManager, reference
)
from ..value import parse_json_node as parse_value_json_node

__all__ = ['DagContext', 'LocalDagContext', 'AirflowDagContext']


def _check_task_output(output:TaskOutput) -> None:
    """`output`이 유효한 `TaskOutput`(`ElementValue`)인지 검증한다."""
    if not isinstance(output, ElementValue):
        raise TypeError(f"Unsupported TaskOutput type: {type(output)}")

def _to_task_output_json_node(output:TaskOutput) -> dict[str, Any]:
    """`TaskOutput`을 XCom에 저장할 수 있는 JSON 직렬화 형태로 변환한다."""
    _check_task_output(output)
    return output.to_json_node()

def _parse_task_output_json_node(jnode:dict[str, Any]) -> TaskOutput:
    """XCom에서 조회한 JSON 직렬화 형태를 `TaskOutput`으로 복원한다."""
    return cast(TaskOutput, parse_value_json_node(jnode))


class DagContext(ABC):
    """Invocation이 task 본문을 실행할 때 사용하는 런타임 컨텍스트의 추상 베이스이다.

    여섯 멤버(`task_id`, `mdt_manager`, `get_submodel`, `resolve_reference`,
    `get_task_output`, `set_task_outputs`) 모두 `@abstractmethod`이므로, 하나라도
    구현하지 않은 서브클래스는 인스턴스화할 수 없다.
    """

    @property
    @abstractmethod
    def task_id(self) -> str:
        """현재 실행 중인 task의 식별자를 반환한다."""
        ...

    @property
    @abstractmethod
    def mdt_manager(self) -> MDTInstanceManager:
        """현재 실행 중인 task가 접속하는 MDT Instance Manager를 반환한다."""
        ...

    @abstractmethod
    def get_submodel(self, instance:str, submodel_idshort:str) -> SubmodelService:
        """주어진 instance의 submodel을 idShort로 조회하여 반환한다."""
        ...

    @abstractmethod
    def resolve_reference(self, ref_string:str) -> ElementReference:
        """reference 문자열을 `ElementReference`로 해석한다."""
        ...

    @abstractmethod
    def get_task_output(self, task_id:str, arg_id:str) -> TaskOutput:
        """주어진 task가 남긴 출력 중 `arg_id`에 해당하는 값을 조회한다.
        만일 `arg_id`가 존재하지 않으면 `KeyError`를 발생시킨다.
        """
        ...

    @abstractmethod
    def set_task_outputs(self, outputs:Mapping[str, TaskOutput]) -> None:
        """현재 task의 출력 인자 값들을 후속 task가 참조할 수 있도록 저장한다."""
        ...


class LocalDagContext(DagContext):
    """Airflow 없이 동작하는 in-process `DagContext` 구현이다.

    task 출력을 클래스 변수 `__TASK_OUTPUT`에 보관하므로, 동일 프로세스 내에서
    생성된 인스턴스들 사이에 출력 상태가 공유된다. 여러 DAG를 검증하는 테스트는
    인스턴스 간 상태 누수를 막기 위해 이 클래스 변수를 명시적으로 초기화해야 한다.
    """

    __TASK_OUTPUT = dict[str, Mapping[str, TaskOutput]]()

    def __init__(self, task_id:str, mdt_inst_url:str) -> None:
        """task_id와 MDT Instance Manager URL로 컨텍스트를 초기화하고 매니저에 접속한다."""
        self.__task_id = task_id
        self.mdt_manager_url = mdt_inst_url
        self.__mdt_manager:MDTInstanceManager = connect(mdt_inst_url)

    @property
    def task_id(self) -> str:
        return self.__task_id

    @property
    def mdt_manager(self) -> MDTInstanceManager:
        return self.__mdt_manager

    def get_submodel(self, instance:str, submodel_idshort:str) -> SubmodelService:
        return self.mdt_manager.instances[instance].submodel_services[submodel_idshort]

    def resolve_reference(self, ref_string:str) -> ElementReference:
        return reference(ref_string)

    def get_task_output(self, task_id:str, arg_id:str) -> TaskOutput:
        task_outputs = LocalDagContext.__TASK_OUTPUT.get(task_id)
        if task_outputs is None:
            raise KeyError(f"Task output for '{task_id}' is not found")
        if arg_id not in task_outputs:
            raise KeyError(f"Task output argument '{arg_id}' is not found in task '{task_id}'")

        logger.info(f"Fetching task output for {task_id}[{arg_id}] from {task_outputs}")
        return task_outputs[arg_id]

    def set_task_outputs(self, outputs:Mapping[str, TaskOutput]) -> None:
        # AirflowDagContext와 동일하게 TaskOutput(ElementValue) 계약을 강제한다.
        for output in outputs.values():
            _check_task_output(output)
        LocalDagContext.__TASK_OUTPUT[self.task_id] = outputs

    def __repr__(self) -> str:
        return f"LocalDagContext(task_id={self.task_id}, arguments={LocalDagContext.__TASK_OUTPUT})"


class AirflowDagContext(DagContext):
    """실제 Airflow 런타임에서 동작하는 `DagContext` 구현이다.

    task 출력은 XCom(`'task_output'` 키)으로 주고받고, 매니저 URL은 Airflow
    `Variable`에서 읽는다. XCom은 JSON 직렬화 가능한 값만 허용하므로 `ElementValue`는
    `@type`/`value` JSON 형태(`to_json_node()`)로 저장하고 조회 시 `parse_json_node()`로
    복원한다. `airflow.sdk` import는 메서드 호출 시점으로 지연시켜,
    본 컨텍스트를 사용하지 않는 호출자는 Airflow 설치 없이도 모듈을 import할 수 있다.
    """

    def __init__(self, mdt_manager_url:Optional[str]=None) -> None:
        """MDT Instance Manager URL로 컨텍스트를 초기화하고 매니저에 접속한다.

        `mdt_manager_url`이 `None`이면 Airflow `Variable`에서 `mdt_manager_url`을 읽는다.
        """
        from airflow.sdk import Variable

        self.__mdt_manager_url = mdt_manager_url if mdt_manager_url is not None \
                                                else Variable.get("mdt_manager_url")
        self.__mdt_manager:MDTInstanceManager = connect(self.__mdt_manager_url)

    @property
    def mdt_manager(self) -> MDTInstanceManager:
        """AirflowDagContext 인스턴스 생성 시점이 아니라, 실제 task 실행 시점에 접속한다."""
        if self.__mdt_manager is None:
            self.__mdt_manager = connect(self.__mdt_manager_url)
        return self.__mdt_manager

    @property
    def task_id(self) -> str:
        return self.task_instance.task_id

    def get_submodel(self, instance:str, submodel_idshort:str) -> SubmodelService:
        return self.mdt_manager.instances[instance].submodel_services[submodel_idshort]

    def resolve_reference(self, ref_string:str) -> ElementReference:
        return self.mdt_manager.resolve_reference(ref_string)

    @property
    def task_instance(self) -> Any:
        """현재 Airflow 실행 컨텍스트에서 task instance(`ti`)를 가져온다.

        반환 타입은 Airflow의 TaskInstance이나, Airflow 미설치 환경에서도 타입 해석이
        가능해야 하므로 `Any`로 선언한다.
        """
        from airflow.sdk import get_current_context
        ctx = get_current_context()
        if ctx is None:
            raise RuntimeError("Airflow context is not available.")
        return ctx['ti']

    def get_task_output(self, task_id:str, arg_id:str) -> TaskOutput:
        ti = self.task_instance
        logger.info(f'taskInstance: {ti}, task_id: {task_id}, argument: {arg_id}')

        output_args = ti.xcom_pull(task_ids=task_id, key='task_output')
        if output_args is None:
            raise KeyError(f"Task output for '{task_id}' is not found")
        if arg_id not in output_args:
            raise KeyError(f"Task output argument '{arg_id}' is not found in task '{task_id}'")

        logger.info(f"Fetching task output for {task_id}[{arg_id}] from {output_args}")
        # XCom에는 `@type`/`value` JSON 형태로 저장되어 있으므로 `ElementValue`로 복원한다.
        jnode = output_args[arg_id]
        return _parse_task_output_json_node(jnode)

    def set_task_outputs(self, outputs:Mapping[str, TaskOutput]) -> None:
        ti = self.task_instance
        logger.info(f"Setting task output: {ti.task_id} = {outputs}")
        # XCom은 JSON 직렬화 가능한 값만 허용하므로 `@type`/`value` JSON 형태로 변환하여 저장한다.
        jnodes = { arg_id: _to_task_output_json_node(output) for arg_id, output in outputs.items() }
        ti.xcom_push(key='task_output', value=jnodes)

    def __repr__(self) -> str:
        # task 실행 컨텍스트 밖(DAG 파싱, 디버깅 등)에서도 안전하도록 부수효과 없는 정보만 담는다.
        return f"AirflowDagContext(mdt_manager_url={self.__mdt_manager_url})"
