from __future__ import annotations

from typing import Any, cast, Optional, Mapping

from collections.abc import Iterator, Collection
from dataclasses import dataclass
from dataclass_wizard import JSONWizard
import datetime
from basyx.aas import model

from mdtpy.basyx.serde import from_json

from .submodel import SubmodelService
from .descriptor import MDTOperationDescriptor, MDTSubmodelDescriptor, ArgumentDescriptor
from .reference import ElementReference, DefaultElementReference, ElementReferenceDict
from .value import update_element_with_value, ElementValueType, get_value, ElementValueDict, update_value_dict, ElementJsonValueType
from .aas_misc import OperationVariable
from .exceptions import OperationError


def get_argument_value(arg:ElementReference|ElementValueType|model.SubmodelElement) -> Optional[ElementValueType]:
  if isinstance(arg, ElementReference):
    return arg.read_value()
  elif isinstance(arg, model.SubmodelElement):
    return get_value(arg)
  else:
    return arg


class AASOperationService:
  def __init__(self, submodel_svc:SubmodelService, operation_path:str) -> None:
    self.__submodel_svc = submodel_svc
    self.__operation_path = operation_path
    operation = cast(model.Operation, submodel_svc.submodel_elements[operation_path])
    self.in_op_variables = [ OperationVariable(value=var) for var in operation.input_variable ]
    self.inout_op_variables = [ OperationVariable(value=var) for var in operation.in_output_variable ]
    self.out_op_variables = [ OperationVariable(value=var) for var in operation.output_variable ]

  def invoke(self, **kwargs: Any) -> ElementValueDict:
    """
    연산을 호출한다.
    
    Args:
      kwargs: Any: 연산 인자 값을 전달하는 keyword 기반 인자.
        - 연산 식별자를 키로하는 dictionary.
        - 연산 인자 값은 전달할 값을 지정하던 ElementReference 혹은 ElementValueType 형태로 지정한다.
    
    Returns:
      ElementValueDict: 연산 출력 인자 값 목록.
    Raises:
      OperationError: 연산 호출 실패 시 발생하는 예외.
    """
    # 인자로 전달된 값을 OperationVariable의 값으로 업데이트한다.
    for opv in self.in_op_variables + self.inout_op_variables:
      var_id = str(opv.value.id_short)
      if var_id in kwargs:
        value = get_argument_value(kwargs[var_id])
        update_element_with_value(opv.value, value)

    result = self.__submodel_svc.invoke_operation_sync(self.__operation_path, 
                                                      self.in_op_variables,
                                                      self.inout_op_variables,
                                                      timeout=datetime.timedelta(days=7))
    if result.success:
      output_values:ElementValueDict = {}
      if result.output_op_variables is not None: 
        for op_var in result.output_op_variables:
          output_values[str(op_var.value.id_short)] = get_value(op_var.value)
      if result.inoutput_op_variables is not None: 
        for op_var in result.inoutput_op_variables:
          output_values[str(op_var.value.id_short)] = get_value(op_var.value)
      return output_values
    else:
      if result.messages:
        raise OperationError(f'Operation {self.__operation_path} failed: {result.messages}')
      else:
        raise OperationError(f'Operation {self.__operation_path} failed')


class Argument(DefaultElementReference):
  def __init__(self, op_submodel_svc:OperationSubmodelService, desc:ArgumentDescriptor) -> None:
    super().__init__(ref_string=desc.reference,
                     endpoint=f'{op_submodel_svc.service_endpoint}/submodel-elements/{desc.id_short_path}')
    self.descriptor = desc

  @property
  def id(self) -> str:
    """
    인자 식별자를 반환한다.

    Returns:
      str: 인자 식별자.
    """
    return self.descriptor.id


class ArgumentList(ElementReferenceDict[Argument]):
  def __init__(self, op_submodel_svc:OperationSubmodelService, arg_desc_list:list[ArgumentDescriptor]):
    super().__init__({ desc.id:Argument(op_submodel_svc, desc) for desc in arg_desc_list })
    self.__arg_desc_list = arg_desc_list

  def __getitem__(self, arg_id: str|int) -> Argument:
    """
    주어진 식별자에 해당하는 인자를 반환한다.

    Args:
      arg_id: str|int: 인자 식별자.
    Returns:
      Argument: 인자 객체.
    """
    if isinstance(arg_id, int):
      return super().__getitem__(self.__arg_desc_list[arg_id].id)
    else:
      return super().__getitem__(arg_id)


class OperationSubmodelService(SubmodelService):
  def __init__(self, instance_id:str, sm_desc:MDTSubmodelDescriptor, op_desc:MDTOperationDescriptor) -> None:
    super().__init__(instance_id, sm_desc)
    self.__op_desc = op_desc
    self.input_arguments = ArgumentList(self, op_desc.input_arguments)
    self.output_arguments = ArgumentList(self, op_desc.output_arguments)
    self.op = AASOperationService(self, 'Operation')

  def operation_descriptor(self) -> MDTOperationDescriptor:
    """
    연산의 등록정보를 반환한다.

    Returns:
      MDTOperationDescriptor: 연산의 등록정보.
    """
    return self.__op_desc

  def invoke(self, **kwargs: Any) -> ElementValueDict:
    """
    연산을 호출한다.
    
    Args:
      kwargs: Any: 연산 인자 값을 전달하는 keyword 기반 인자.
        - 연산 식별자를 키로하는 dictionary.
        - 연산 인자 값은 전달할 값을 지정하던 ElementReference 혹은 ElementValueType 형태로 지정한다.
    
    Returns:
      ArgumentList: 연산 출력 인자 목록.
    """
    input_arg_values = self.input_arguments.read_value()
    update_value_dict(input_arg_values, kwargs)

    # 연산을 호출한다.
    result = self.op.invoke(**input_arg_values)

    # 결과 값 중에서 ElementReference 형태로 출력 인자로 제공된 경우에는
    # 해당 ElementReference 객체의 값을 갱신한다
    for arg_id, arg_value in result.items():
      if arg_id in kwargs and isinstance(kwargs[arg_id], ElementReference) \
          and arg_id in self.output_arguments:
        kwargs[arg_id].update_value(arg_value)

    return result

