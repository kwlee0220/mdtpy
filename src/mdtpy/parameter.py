from __future__ import annotations

from typing import Iterable, Optional, Mapping, Iterator

from .descriptor import MDTParameterDescriptor
from .exceptions import MDTException, ResourceNotFoundError
from .ref import BaseElementReference


class MDTParameter(BaseElementReference):
    def __init__(self, descriptor: MDTParameterDescriptor) -> None:
        if descriptor.endpoint is None:
            raise ValueError(f"endpoint is None: parameter id={descriptor.id}")
        super().__init__(descriptor.reference)
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
    
    @property
    def value_type(self) -> str:
        """
        파라미터 값의 데이터 유형을 반환한다.

        Returns:
          str: 파라미터 값의 데이터 유형.
        """
        return self.__descriptor.value_type


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
        Raises:
          ResourceNotFoundError: 해당 식별자의 파라미터가 없는 경우. 메시지에 사용 가능한
            파라미터 식별자 목록을 담는다.
        """
        param = self.__param_dict.get(param_id)
        if param is None:
            raise ResourceNotFoundError.create(
                "MDTParameter", f"id={param_id}, available={list(self.__param_dict)}"
            )
        return param

    def __contains__(self, param_id: object) -> bool:
        """
        주어진 식별자의 파라미터 존재 여부를 반환한다.

        `__getitem__` 이 `KeyError` 가 아니라 `ResourceNotFoundError` 를 내므로
        `Mapping` 의 기본 구현 대신 직접 구현한다.

        Args:
          param_id (object): 파라미터 식별자.
        Returns:
          bool: 존재하면 True.
        """
        return param_id in self.__param_dict

    def get(self, param_id: str, default: Optional[MDTParameter] = None) -> Optional[MDTParameter]:  # type: ignore[override]
        """
        주어진 식별자의 파라미터를 반환하고, 없으면 `default` 를 반환한다.

        `__getitem__` 이 `KeyError` 가 아니라 `ResourceNotFoundError` 를 내므로
        `Mapping` 의 기본 구현 대신 직접 구현한다.

        Args:
          param_id (str): 파라미터 식별자.
          default (Optional[MDTParameter]): 파라미터가 없을 때 반환할 값.
        Returns:
          Optional[MDTParameter]: 파라미터 객체 또는 `default`.
        """
        return self.__param_dict.get(param_id, default)