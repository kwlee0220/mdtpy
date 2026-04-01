from __future__ import annotations

from typing import Any, Optional
from abc import ABC, abstractmethod

import logging
from functools import cached_property

from ..instance import connect, MDTInstanceManager
from ..operation import SubmodelService, OperationSubmodelService
from ..reference import ElementReference
from ..value import ElementValueDict, ElementValueType


class DagContext(ABC):
  @property
  @abstractmethod
  def task_id(self) -> str: ...

  def get_submodel(self, instance:str, submodel_idshort:str) -> SubmodelService: ...
  def resolve_reference(self, ref_string:str) -> ElementReference: ...

  def get_task_output_argument(self, task_id:str, arg_id:str) -> Optional[ElementValueType]: ...
  def set_task_output(self, out_arg_values:ElementValueDict) -> None: ...
  # def add_task_output_value(self, task_id:str, arg_id:str, arg_value:Optional[ElementValueType]) -> None: ...


class LocalDagContext(DagContext):
  __TASK_OUTPUT = dict[str, ElementValueDict]()

  def __init__(self, task_id:str, mdt_inst_url:Optional[str]=None) -> None:
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
  #   task_outputs = LocalDagContext.__TASK_OUTPUT.get(task_id)
  #   if task_outputs is None:
  #     task_outputs = {}
  #   task_outputs[arg_id] = arg_value
  #   LocalDagContext.__TASK_OUTPUT[task_id] = task_outputs

  def __repr__(self) -> str:
    return f"LocalDagContext(task_id={self.task_id}, arguments={LocalDagContext.__TASK_OUTPUT})"


class AirflowDagContext(DagContext):
  def __init__(self, mdt_manager_url:Optional[str]=None) -> None:
    from airflow.sdk import Variable

    self.mdt_manager_url = mdt_manager_url if mdt_manager_url is not None else Variable.get("mdt_manager_url")
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
  #   ti = self.task_instance
  #   logging.info(f"Adding task output: {task_id}[{arg_id}]: {arg_value}")
  #   task_outputs = ti.xcom_pull(task_ids=task_id, key='task_output')
  #   if task_outputs is None:
  #     task_outputs = {}
  #   task_outputs[arg_id] = arg_value
  #   ti.xcom_push(key='task_output', value=task_outputs)

  def __repr__(self) -> str:
    ti = self.task_instance
    task_output = ti.xcom_pull(task_ids=ti.task_id, key='task_output')
    return f"AirflowDagContext(task_id={self.task_id}, task_output={task_output})"

