from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TypedDict, NotRequired

from abc import ABC, abstractmethod

from ..reference import ElementReference
from ..operation import OperationSubmodelService
from .argument_spec import ElementReferenceArgumentSpec, LiteralArgumentSpec, TaskOutputArgumentSpec
from .dag_context import DagContext, AirflowDagContext

InputArgumentSpecType = TaskOutputArgumentSpec | ElementReferenceArgumentSpec | LiteralArgumentSpec
OutputArgumentSpecType = ElementReferenceArgumentSpec


class InvocationArgumentSpecs(TypedDict):
  inputs: dict[str, InputArgumentSpecType]
  outputs: NotRequired[dict[str, OutputArgumentSpecType]]


class Invocation(ABC):
  @abstractmethod
  def run(self, context:Optional[DagContext]=None) -> None: ...


def get_output_argument_specs(argument_specs: InvocationArgumentSpecs) -> dict[str, OutputArgumentSpecType]:
  if 'outputs' in argument_specs:
    return argument_specs['outputs']
  return {}


class SetElementInvocation(Invocation):
  def __init__(self, argument_specs: InvocationArgumentSpecs) -> None:
    self.argument_specs = argument_specs

  def run(self, context:Optional[DagContext]=None) -> None:
    if context is None:
      context = AirflowDagContext()

    if 'source' not in self.argument_specs['inputs']:
      raise ValueError("Argument 'source' is required")

    src_arg = self.argument_specs['inputs']['source'].get(context)
    src_value = src_arg.read_value() if isinstance(src_arg, ElementReference) else src_arg

    output_arg_specs = get_output_argument_specs(self.argument_specs)
    if 'target' in output_arg_specs:
      output_arg_specs['target'].get(context).update_value(src_value)

    context.set_task_output({'target': src_value})

class AASOperationTaskInvocation(Invocation):
  def __init__(self, instance: str, submodel: str, argument_specs: InvocationArgumentSpecs) -> None:
    self.instance = instance
    self.submodel = submodel
    self.argument_specs = argument_specs

  def run(self, context:Optional[DagContext]=None) -> None:
    if context is None:
      context = AirflowDagContext()

    submodel = context.get_submodel(self.instance, self.submodel)
    if not isinstance(submodel, OperationSubmodelService):
      raise ValueError(f"Submodel {self.instance}:{self.submodel} is not an operation submodel")
      
    # 입력 인자 규격에서 인자로 변환하여 연산을 호출한다.
    arg_specs = self.argument_specs['inputs'] | get_output_argument_specs(self.argument_specs)
    args = { arg_id: arg.get(context) for arg_id, arg in arg_specs.items() }
    out_arg_values = submodel.invoke(**args)
    context.set_task_output(out_arg_values)

  def __repr__(self) -> str:
    return ( f"{self.__class__.__name__}(task={self.instance}:{self.submodel}, "
             f"inputs={self.argument_specs['inputs']}, "
             f"outputs={get_output_argument_specs(self.argument_specs)})" )


# def add_task_output_values(context:DagContext, out_arg_values:ElementValueDict,
#                           out_arg_specs_dict:dict[str, OutputArgumentSpecType]) -> None:
#   task_id = context.task_id
#   for arg_id, arg_value in out_arg_values.items():
#     if arg_id not in out_arg_specs_dict:
#       continue

#     out_arg_specs = out_arg_specs_dict[arg_id]
#     if isinstance(out_arg_specs, list):
#       for arg_spec in out_arg_specs:
#         if isinstance(arg_spec, OutputArgumentSpec):
#           context.add_task_output_value(task_id, arg_id, arg_value)
#           break
#     else:
#       if isinstance(out_arg_specs, OutputArgumentSpec):
#           context.add_task_output_value(task_id, arg_id, arg_value)
