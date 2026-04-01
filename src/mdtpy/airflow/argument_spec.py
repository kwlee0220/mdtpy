from __future__ import annotations

from typing import Any, Optional

from abc import ABC, abstractmethod

from ..reference import ElementReference, ElementValueType
from .dag_context import DagContext


def task_output(task_id:str, argument:str) -> TaskOutputArgumentSpec:
  return TaskOutputArgumentSpec(task_id, argument)

def reference(ref_string:str) -> ElementReferenceArgumentSpec:
  return ElementReferenceArgumentSpec(ref_string)

def literal(literal:ElementValueType) -> LiteralArgumentSpec:
  return LiteralArgumentSpec(literal)


class ArgumentSpec(ABC):
  @abstractmethod
  def get(self, context:DagContext) -> ElementReference|Optional[ElementValueType]: ...


class TaskOutputArgumentSpec(ArgumentSpec):
  def __init__(self, task_id:str, argument:str) -> None:
    self.task_id = task_id
    self.argument = argument

  def get(self, context:DagContext) -> ElementReference|Optional[ElementValueType]:
    return context.get_task_output_argument(self.task_id, self.argument)

  def __repr__(self) -> str:
    return f"task_output({self.task_id}[{self.argument}])"


class ElementReferenceArgumentSpec(ArgumentSpec):
  def __init__(self, ref_string:str) -> None:
    self.ref_string = ref_string

  def get(self, context:DagContext) -> ElementReference:
    return context.resolve_reference(self.ref_string)

  def __repr__(self) -> str:
    return f"reference({self.ref_string})"


class LiteralArgumentSpec(ArgumentSpec):
  def __init__(self, value:ElementValueType) -> None:
    self.value = value

  def get(self, context:DagContext) -> ElementReference|Optional[ElementValueType]:
    return self.value

  def __repr__(self) -> str:
    return f"literal({self.value})"