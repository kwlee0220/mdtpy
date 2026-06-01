"""Airflow task 실행 시점의 런타임 어댑터를 정의한다.

`DagContext`는 Invocation이 task 본문을 실행할 때 필요한 런타임 기능
(submodel 조회, reference 해석, task 간 출력 값 전달)을 추상화한다.
구현체는 두 가지이다.

- `LocalDagContext`: task 출력을 프로세스 내 클래스 변수에 보관하여 Airflow
  없이 in-process 테스트를 수행한다.
- `AirflowDagContext`: 실제 Airflow 런타임에서 XCom과 Variable을 사용한다.
  `airflow.sdk` import를 메서드 호출 시점으로 지연시켜, 본 서브패키지를
  사용하는 쪽이 항상 Airflow를 설치하지 않아도 되도록 한다.
"""

from __future__ import annotations

from typing import Any, Optional
from abc import ABC, abstractmethod

import logging
from functools import cached_property

from ..instance import connect, MDTInstanceManager
from ..operation import SubmodelService, OperationSubmodelService
from ..reference import ElementReference
from ..value import ElementValueDict, ElementValueType


__all__ = ['DagContext', 'LocalDagContext', 'AirflowDagContext']


class DagContext(ABC):
    """Invocation이 task 본문을 실행할 때 사용하는 런타임 컨텍스트의 추상 베이스이다.

    서브클래스는 아래 메서드를 모두 구현해야 한다. `task_id`만 `@abstractmethod`로
    강제되며, 나머지는 본문이 `...`인 비추상 메서드이므로 Python이 미구현을 강제하지
    않는다.
    """

    @property
    @abstractmethod
    def task_id(self) -> str:
        """현재 실행 중인 task의 식별자를 반환한다."""
        ...

    @abstractmethod
    def get_submodel(self, instance:str, submodel_idshort:str) -> SubmodelService:
        """주어진 instance의 submodel을 idShort로 조회하여 반환한다."""
        ...

    @abstractmethod
    def resolve_reference(self, ref_string:str) -> ElementReference:
        """reference 문자열(`param:`/`oparg:` 등)을 `ElementReference`로 해석한다."""
        ...

    @abstractmethod
    def get_task_output_argument(self, task_id:str, arg_id:str) -> Optional[ElementValueType]:
        """주어진 task가 남긴 출력 중 `arg_id`에 해당하는 값을 조회한다."""
        ...

    @abstractmethod
    def set_task_output(self, out_arg_values:ElementValueDict) -> None:
        """현재 task의 출력 인자 값들을 후속 task가 참조할 수 있도록 저장한다."""
        ...
    # def add_task_output_value(self, task_id:str, arg_id:str, arg_value:Optional[ElementValueType]) -> None: ...


class LocalDagContext(DagContext):
    """Airflow 없이 동작하는 in-process `DagContext` 구현이다.

    task 출력을 클래스 변수 `__TASK_OUTPUT`에 보관하므로, 동일 프로세스 내에서
    생성된 인스턴스들 사이에 출력 상태가 공유된다. 여러 DAG를 검증하는 테스트는
    인스턴스 간 상태 누수를 막기 위해 이 클래스 변수를 명시적으로 초기화해야 한다.
    """

    __TASK_OUTPUT = dict[str, ElementValueDict]()

    def __init__(self, task_id:str, mdt_inst_url:Optional[str]=None) -> None:
        """task_id와 MDT Instance Manager URL로 컨텍스트를 초기화하고 매니저에 접속한다.

        `mdt_inst_url`이 `None`이면 Airflow `Variable`에서 `mdt_manager_url`을 읽는다.
        """
        self.__task_id = task_id
        self.mdt_manager_url = mdt_inst_url if mdt_inst_url is not None else Variable.get("mdt_manager_url")
        self.mdt_manager:MDTInstanceManager = connect(self.mdt_manager_url)

    @property
    def task_id(self) -> str:
        return self.__task_id

    def get_submodel(self, instance:str, submodel_idshort:str) -> SubmodelService:
        return self.mdt_manager.instances[instance].submodel_services[submodel_idshort]

    def resolve_reference(self, ref_string:str) -> ElementReference:
        return self.mdt_manager.resolve_reference(ref_string)

    def get_task_output_argument(self, task_id:str, arg_id:str) -> Optional[ElementValueType]:
        task_outputs = LocalDagContext.__TASK_OUTPUT.get(task_id)
        assert task_outputs is not None, f"Task output for {task_id} is not found"

        logging.info(f"Fetching task output for {task_id}[{arg_id}] from {task_outputs}")
        return task_outputs[arg_id]

    def set_task_output(self, out_arg_values:ElementValueDict) -> None:
        LocalDagContext.__TASK_OUTPUT[self.task_id] = out_arg_values

    # def add_task_output_value(self, task_id:str, arg_id:str, arg_value:Optional[ElementValueType]) -> None:
    #     task_outputs = LocalDagContext.__TASK_OUTPUT.get(task_id)
    #     if task_outputs is None:
    #         task_outputs = {}
    #     task_outputs[arg_id] = arg_value
    #     LocalDagContext.__TASK_OUTPUT[task_id] = task_outputs

    def __repr__(self) -> str:
        return f"LocalDagContext(task_id={self.task_id}, arguments={LocalDagContext.__TASK_OUTPUT})"


class AirflowDagContext(DagContext):
    """실제 Airflow 런타임에서 동작하는 `DagContext` 구현이다.

    task 출력은 XCom(`'task_output'` 키)으로 주고받고, 매니저 URL은 Airflow
    `Variable`에서 읽는다. `airflow.sdk` import는 메서드 호출 시점으로 지연시켜,
    본 컨텍스트를 사용하지 않는 호출자는 Airflow 설치 없이도 모듈을 import할 수 있다.
    """

    def __init__(self, mdt_manager_url:Optional[str]=None) -> None:
        """MDT Instance Manager URL로 컨텍스트를 초기화하고 매니저에 접속한다.

        `mdt_manager_url`이 `None`이면 Airflow `Variable`에서 `mdt_manager_url`을 읽는다.
        """
        from airflow.sdk import Variable

        self.mdt_manager_url = mdt_manager_url if mdt_manager_url is not None \
                                                else Variable.get("mdt_manager_url")
        self.mdt_manager:MDTInstanceManager = connect(self.mdt_manager_url)

    @property
    def task_id(self) -> str:
        return self.task_instance.task_id

    def get_submodel(self, instance:str, submodel_idshort:str) -> SubmodelService:
        return self.mdt_manager.instances[instance].submodel_services[submodel_idshort]

    def resolve_reference(self, ref_string:str) -> ElementReference:
        return self.mdt_manager.resolve_reference(ref_string)

    @property
    def task_instance(self) -> 'TaskInstance':
        """현재 Airflow 실행 컨텍스트에서 task instance(`ti`)를 가져온다."""
        from airflow.sdk import get_current_context
        ctx = get_current_context()
        assert ctx is not None, "Airflow context is not available"
        return ctx['ti']

    def get_task_output_argument(self, task_id:str, arg_id:str) -> Optional[ElementValueType]:
        ti = self.task_instance
        logging.info(f'taskInstance: {ti}, task_id: {task_id}, argument: {arg_id}')

        output_args = ti.xcom_pull(task_ids=task_id, key='task_output')
        assert output_args is not None, f"Task output for {task_id} is not found"

        logging.info(f"Fetching task output for {task_id}[{arg_id}] from {output_args}")
        return output_args[arg_id]

    def set_task_output(self, out_arg_values:ElementValueDict) -> None:
        ti = self.task_instance
        logging.info(f"Setting task output: {ti.task_id} = {out_arg_values}")
        ti.xcom_push(key='task_output', value=out_arg_values)

    # def add_task_output_value(self, task_id:str, arg_id:str, arg_value:Optional[ElementValueType]) -> None:
    #     ti = self.task_instance
    #     logging.info(f"Adding task output: {task_id}[{arg_id}]: {arg_value}")
    #     task_outputs = ti.xcom_pull(task_ids=task_id, key='task_output')
    #     if task_outputs is None:
    #         task_outputs = {}
    #     task_outputs[arg_id] = arg_value
    #     ti.xcom_push(key='task_output', value=task_outputs)

    def __repr__(self) -> str:
        ti = self.task_instance
        task_output = ti.xcom_pull(task_ids=ti.task_id, key='task_output')
        return f"AirflowDagContext(task_id={self.task_id}, task_output={task_output})"
