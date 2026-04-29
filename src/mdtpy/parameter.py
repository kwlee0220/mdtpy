from __future__ import annotations

from typing import Iterable, Optional, Mapping, Iterator

from .descriptor import MDTParameterDescriptor
from .exceptions import MDTException
from .reference import DefaultElementReference


class MDTParameter(DefaultElementReference):
  def __init__(self, descriptor: MDTParameterDescriptor):
    if descriptor.endpoint is None:
      raise ValueError(f"MDTParameterDescriptor.endpoint is None: id={descriptor.id}")
    super().__init__(ref_string=descriptor.reference, endpoint=descriptor.endpoint)
    self.__descriptor = descriptor

  @property
  def descriptor(self) -> MDTParameterDescriptor:
    """
    파라미터 등록정보를 반환한다.

    Returns:
      MDTParameterDescriptor: 파라미터 등록정보.
    """
    return self.__descriptor

  @property
  def id(self) -> str:
    """
    파라미터 식별자를 반환한다.

    Returns:
      str: 파라미터 식별자.
    """
    return self.__descriptor.id

  @property
  def name(self) -> Optional[str]:
    """
    파라미터 이름을 반환한다.

    Returns:
      Optional[str]: 파라미터 이름.
    """
    return self.__descriptor.name


class MDTParameterCollection(Mapping[str, MDTParameter]):
  def __init__(self, parameters: Iterable[MDTParameter]):
    self.__param_dict: dict[str, MDTParameter] = {}
    for param in parameters:
      if param.id in self.__param_dict:
        raise MDTException(f"Duplicate MDTParameter id: {param.id}")
      self.__param_dict[param.id] = param

  def __len__(self) -> int:
    """
    파라미터 개수를 반환한다.

    Returns:
      int: 파라미터 개수.
    """
    return len(self.__param_dict)

  def __iter__(self) -> Iterator[str]:
    """
    전체 파라미터 목록을 순환하는 순환자를 반환한다.

    Returns:
      Iterator[str]: 파라미터 순환자.
    """
    return iter(self.__param_dict.keys())

  def __getitem__(self, param_id: str) -> MDTParameter:
    """
    주어진 식별자의 파라미터를 반환한다.

    Args:
      param_id (str): 파라미터 식별자.
    Returns:
      MDTParameter: 파라미터 객체.
    """
    return self.__param_dict[param_id]