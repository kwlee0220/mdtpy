from __future__ import annotations

from typing import TypeVar, Iterator, Any, Mapping, Iterable

import datetime
from urllib import parse

from basyx.aas import model

from .reference import ElementReference, DefaultElementReference
from .descriptor import MDTSubmodelDescriptor
from .aas_misc import ProtocolInformation, Endpoint, OperationVariable, OperationResult, OperationRequest, OperationHandle
from .exceptions import InvalidResourceStateError, ResourceNotFoundError
from .basyx import serde as basyx_serde
from . import fa3st


class SubmodelService:
  def __init__(self, instance_id:str, sm_desc:MDTSubmodelDescriptor) -> None:
    self.__instance_id = instance_id
    self.__descriptor = sm_desc

  @property
  def instance_id(self) -> str:
    """
    MDTInstance의 식별자를 반환한다.

    Returns:
      str: MDTInstance의 식별자.
    """
    return self.__instance_id
  
  @property
  def id(self) -> str:
    """
    Submodel의 식별자를 반환한다.

    Returns:
      str: Submodel의 식별자.
    """
    return self.__descriptor.id
  
  @property
  def id_short(self) -> str:
    """
    Submodel의 ID Short를 반환한다.

    Returns:
      str: Submodel의 ID Short.
    """
    return self.__descriptor.id_short

  @property
  def semantic_id_str(self) -> str:
    """
    Submodel의 Semantic ID를 반환한다.

    Returns:
      str: Submodel의 Semantic ID.
    """
    return self.__descriptor.semantic_id

  @property
  def service_endpoint(self) -> str|None:
    """
    Submodel의 Service Endpoint를 반환한다.

    Returns:
      str|None: Submodel의 Service Endpoint.
    """
    return self.__descriptor.endpoint
      
  @property
  def endpoint(self) -> Endpoint:
    """
    Submodel의 Endpoint를 반환한다.

    Returns:
      Endpoint: Submodel의 Endpoint.
    """
    return Endpoint(interface="SUBMODEL",
                    protocolInformation=ProtocolInformation(href=self.service_endpoint,
                                                            endpointProtocol="HTTP",
                                                            endpointProtocolVersion="1.1"))

  def is_information_model(self) -> bool:
    """
    Submodel가 Information Model인지 여부를 반환한다.

    Returns:
      bool: Submodel가 Information Model인지 여부.
    """
    return self.__descriptor.is_information_model()

  def is_data(self) -> bool:
    """
    Submodel가 Data Model인지 여부를 반환한다.

    Returns:
      bool: Submodel가 Data Model인지 여부.
    """
    return self.__descriptor.is_data()

  def is_simulation(self) -> bool:
    """
    Submodel가 Simulation Model인지 여부를 반환한다.

    Returns:
      bool: Submodel가 Simulation Model인지 여부.
    """
    return self.__descriptor.is_simulation()

  def is_ai(self) -> bool:
    """
    Submodel가 AI Model인지 여부를 반환한다.

    Returns:
      bool: Submodel가 AI Model인지 여부.
    """
    return self.__descriptor.is_ai()

  def is_time_series(self) -> bool:
    """
    Submodel가 Time Series Model인지 여부를 반환한다.

    Returns:
      bool: Submodel가 Time Series Model인지 여부.
    """
    return self.__descriptor.is_time_series()
      
  def read(self) -> model.Submodel:
    """
    Submodel을 읽어온다.

    Returns:
      model.Submodel: Submodel.
    """
    if not self.__descriptor.endpoint:
        raise InvalidResourceStateError.create("SubmodelService", f"id={self.id}", "Endpoint is not set")
    # return fa3st.call_get(self.__descriptor.endpoint, deserializer=basyx_serde.from_dict) # type: ignore
    return fa3st.call_get(self.__descriptor.endpoint, deserializer=basyx_serde.from_json) # type: ignore
  
  def write(self, submodel:model.Submodel) -> None:
    """
    Submodel을 쓴다.

    Args:
      submodel (model.Submodel): 쓸 Submodel.
    """
    if not self.__descriptor.endpoint:
        raise InvalidResourceStateError.create("SubmodelService", f"id={self.id}", "Endpoint is not set")
    url = f"{self.__descriptor.endpoint}"
    json_str = basyx_serde.to_json(submodel)
    fa3st.call_put(url, json_str)

  @property
  def submodel_elements(self) -> SubmodelElementCollection:
    """
    Submodel의 모든 SubmodelElement 객체들의 목록을 반환한다.

    Returns:
      SubmodelElementCollection: Submodel의 모든 SubmodelElement 객체들의 목록.
    """
    return SubmodelElementCollection(self)

  def element_reference(self, path:str) -> ElementReference:
    """
    주어진 idShort 경로에 해당하는 SubmodelElement의 ElementReference를 반환한다.

    Args:
      path (str): idShort 경로.
    Returns:
      ElementReference: idShort 경로에 해당하는 SubmodelElement의 ElementReference.
    """
    ref_string = f'{self.instance_id}:{self.id_short}:{path}'
    return DefaultElementReference(ref_string=ref_string, endpoint=self.submodel_element_url(path))

  def invoke_operation_sync(self, op_path:str, input_op_variables:Iterable[OperationVariable],
                            inoutput_op_variables:Iterable[OperationVariable],
                            timeout:datetime.timedelta) -> OperationResult:
    """
    주어진 연산 경로에 해당하는 연산을 동기적으로 호출한다.

    Args:
      op_path (str): 연산 경로.
      input_op_variables (Iterable[OperationVariable]): 입력 연산 변수 목록.
      inoutput_op_variables (Iterable[OperationVariable]): 입출력 연산 변수 목록.
      timeout (datetime.timedelta): 타임아웃.
    Returns:
      OperationResult: 연산 결과.
    """
    url = self.submodel_element_url(op_path) + "/invoke"
    req = OperationRequest(input_arguments=input_op_variables,
                          inoutput_arguments=inoutput_op_variables,
                          client_timeout_duration=timeout)
    json_str = req.to_json()
    return fa3st.call_post(url, data=json_str, deserializer=OperationResult.from_json) # type: ignore
      
  def invoke_operation_async(self, path:str, input_arguments:list[OperationVariable],
                            input_output_arguments:list[OperationVariable],
                            timeout:datetime.timedelta) -> OperationHandle:
    """
    주어진 연산 경로에 해당하는 연산을 비동기적으로 호출한다.

    Args:
      path (str): 연산 경로.
      input_arguments (list[OperationVariable]): 입력 연산 변수 목록.
      input_output_arguments (list[OperationVariable]): 입출력 연산 변수 목록.
      timeout (datetime.timedelta): 타임아웃.
    Returns:
      OperationHandle: 연산 결과.
    """
    url = self.submodel_element_url(path) + "/invoke?async=true"
    req = OperationRequest(input_arguments=input_arguments,
                          inoutput_arguments=input_output_arguments,
                          client_timeout_duration=timeout)
    json_str = req.to_json()
    return fa3st.call_post(url, data=json_str, serde=OperationHandle.from_json) # type: ignore
  
  def get_operation_async_result(self, path:str, handle:OperationHandle) -> OperationResult:
    """
    주어진 연산 경로에 해당하는 연산의 비동기 결과를 반환한다.

    Args:
      path (str): 연산 경로.
      handle (OperationHandle): 연산 결과 핸들.
    Returns:
      OperationResult: 연산 결과.
    """
    url = self.submodel_element_url(path) + f"/operation-results/{handle.handle_id}"
    return fa3st.call_get(url, deserializer=OperationResult) # type: ignore

  def submodel_element_url(self, path:str) -> str:
    """
    SubmodelElement의 URL을 반환한다.

    Args:
      path (str): idShort 경로.
    Returns:
      str: SubmodelElement의 URL.
    """
    url_prefix = f"{self.__descriptor.endpoint}/submodel-elements"
    return f'{url_prefix}/{parse.quote(path)}' if path else url_prefix


T = TypeVar('T', bound=SubmodelService)
class SubmodelServiceCollection(Mapping[str, T]):
  def __init__(self, instance, sm_desc_dict: Mapping[str, MDTSubmodelDescriptor]):
    op_desc_dict = instance.operation_descriptors
    self.services = dict[str, T]()
    for sm_desc in sm_desc_dict.values():
      if sm_desc.is_data() or sm_desc.is_information_model():
        self.services[sm_desc.id_short] = SubmodelService(instance.id, sm_desc)  # type: ignore
      elif sm_desc.is_simulation() or sm_desc.is_ai():
        if sm_desc.id_short in op_desc_dict:
          op_desc = op_desc_dict[sm_desc.id_short]
          from .operation import OperationSubmodelService
          self.services[sm_desc.id_short] = OperationSubmodelService(instance.id, sm_desc, op_desc)  # type: ignore
        else:
          raise ResourceNotFoundError.create("MDTInstance", f"Operation {instance.id}.{sm_desc.id} not found")
      elif sm_desc.is_time_series():
        from .timeseries import TimeSeriesService
        self.services[sm_desc.id_short] = TimeSeriesService(instance.id, sm_desc)  # type: ignore

  def __bool__(self) -> bool:
    """
    SubmodelService 목록이 비어있는지 여부를 반환한다.

    Returns:
      bool: SubmodelService 목록이 비어있는지 여부.
    """
    return len(self) > 0

  def __len__(self) -> int:
    """
    SubmodelService 목록에 포함된 SubmodelService 개수를 반환한다.

    Returns:
      int: SubmodelService 목록에 포함된 SubmodelService 개수.
    """
    return len(self.services)

  def __getitem__(self, id_short: str) -> T:
    """
    SubmodelService 목록에 포함된 SubmodelService 중에서 주어진 idShort에 해당하는 SubmodelService를 반환한다.

    Args:
      id_short (str): idShort.
    Returns:
      T: SubmodelService.
    """
    if id_short not in self.services:
      raise ResourceNotFoundError.create("SubmodelService", f"idShort={id_short}")
    return self.services[id_short]

  def __setitem__(self, id_short: str, value) -> None:
    raise NotImplementedError('SubmodelServiceCollection does not support set operation')

  def __iter__(self) -> Iterator[str]:
    """
    SubmodelService 목록을 순환하는 순환자를 반환한다.

    Returns:
      Iterator[str]: SubmodelService 목록을 순환하는 순환자.
    """
    return iter(self.services.keys())

  def __contains__(self, key: str) -> bool:
    """
    SubmodelService 목록에 주어진 idShort에 해당하는 SubmodelService가 포함되어 있는지 여부를 반환한다.

    Args:
      key (str): idShort.
    Returns:
      bool: SubmodelService 목록에 주어진 idShort에 해당하는 SubmodelService가 포함되어 있는지 여부.
    """
    return key in self.services

  def get_by_id(self, id: str) -> T:
    """
    SubmodelService 목록에 포함된 SubmodelService 중에서 주어진 id에 해당하는 SubmodelService를 반환한다.

    Args:
      id (str): id.
    Returns:
      T: SubmodelService.
    """
    for svc in self.services.values():
      if svc.id == id:
        return svc
    raise ResourceNotFoundError.create("SubmodelService", f"id={id}")

  def find_by_semantic_id(self, semantic_id: str) -> list[T]:
    return [svc for svc in self.services.values() if svc.semantic_id_str == semantic_id]


T = TypeVar('T', bound=SubmodelService)
class SubmodelServiceCollection2(Mapping[str, T]):
  def __init__(self, services: list[T]):
    self.__services = services

  def __bool__(self) -> bool:
    return len(self) > 0

  def __len__(self) -> int:
    return len(self.__services)

  def __getitem__(self, id_short: str) -> T:
    for svc in self.__services:
      if svc.id_short == id_short:
        return svc
    raise ResourceNotFoundError.create("SubmodelService", f"idShort={id_short}")

  def __setitem__(self, id_short: str, value) -> None:
    raise NotImplementedError('SubmodelServiceCollection does not support set operation')

  def __iter__(self) -> Iterator[T]:
    return iter(self.__services)

  def __contains__(self, key: str) -> bool:
    return any(svc.id == key for svc in self.__services)

  def get_by_id(self, id: str) -> T:
    for svc in self.__services:
      if svc.id == id:
        return svc
    raise ResourceNotFoundError.create("SubmodelService", f"id={id}")

  def find_by_semantic_id(self, semantic_id: str) -> list[T]:
    return [svc for svc in self.__services if svc.semantic_id_str == semantic_id]


class SubmodelElementCollection(Mapping[str, model.SubmodelElement]):
  def __init__(self, submodel_svc: SubmodelService):
    self.__submodel_svc = submodel_svc

  def element_reference(self, path: str) -> DefaultElementReference:
    ref_string = f'{self.__submodel_svc.instance_id}:{self.__submodel_svc.id_short}:{path}'
    return DefaultElementReference(ref_string=ref_string, endpoint=self.__submodel_svc.submodel_element_url(path))

  def __iter__(self) -> Iterator[str]:
    return iter(self.element_reference('').pathes())

  def __len__(self) -> int:
    return len(self.element_reference('').pathes())

  def __getitem__(self, path: str) -> model.SubmodelElement:
    return self.element_reference(path).read()

  def __setitem__(self, path: str, sme: model.SubmodelElement) -> None:
    try:
      self.element_reference(path).write(sme)
    except ResourceNotFoundError :
      self.element_reference(path).add(sme)

  def __delitem__(self, path: str) -> None:
    self.element_reference(path).remove()

  def __contains__(self, path: str) -> bool:
    return self.element_reference(path).exists()

  def get_value(self, path:str) -> Any:
    return self.element_reference(path).read_value()

  def update_value(self, path:str, value:Any) -> None:
    self.element_reference(path).update_value(value)

  def get_attachment(self, path: str) -> bytes|None:
    return self.element_reference(path).get_attachment()