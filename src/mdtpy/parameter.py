from __future__ import annotations

from typing import cast, Optional, Mapping, Iterator

from .descriptor import MDTParameterDescriptor
from .reference import DefaultElementReference


class MDTParameter(DefaultElementReference):
  def __init__(self, descriptor: MDTParameterDescriptor):
    super().__init__(ref_string=descriptor.reference, endpoint=cast(str, descriptor.endpoint)) 
    self.descriptor = descriptor

  @property
  def id(self) -> str:
    """
    파라미터 식별자를 반환한다.

    Returns:
      str: 파라미터 식별자.
    """
    return self.descriptor.id

  @property
  def name(self) -> Optional[str]:
    """
    파라미터 이름을 반환한다.

    Returns:
      Optional[str]: 파라미터 이름.
    """
    return self.descriptor.name


class MDTParameterCollection(Mapping[str, MDTParameter]):
  def __init__(self, parameters: list[MDTParameter]):
    self.__param_dict = { param.id:param for param in parameters }

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

  def __contains__(self, param_id: str) -> bool:
    """
    주어진 식별자의 파라미터 존재 여부를 반환한다.

    Args:
      param_id (str): 파라미터 식별자.
    Returns:
      bool: 파라미터 존재 여부.
    """
    return param_id in self.__param_dict

  def __getitem__(self, param_id: str) -> MDTParameter:
    """
    주어진 식별자의 파라미터를 반환한다.

    Args:
      param_id (str): 파라미터 식별자.
    Returns:
      MDTParameter: 파라미터 객체.
    """
    return self.__param_dict[param_id]