from __future__ import annotations

from typing import Any, Optional, TypeVar
from abc import ABC, abstractmethod

import json

from basyx.aas import model

from ..value import ElementValue

E = TypeVar('E', bound=model.SubmodelElement)


class ElementReference(ABC):
    @property
    def ref_string(self) -> str:
        """참조 표현식 문자열. 구현 클래스가 override 하여 제공한다."""
        raise NotImplementedError(f"{type(self).__name__}.ref_string is not implemented")

    @property
    @abstractmethod
    def model_type(self) -> type[E]:
        """ElementReference가 가리키는 SubmodelElement 객체의 모델 타입을 반환한다.

        Returns:
            type[E]: ElementReference가 가리키는 SubmodelElement 객체의 모델 타입.
        """
        pass

    @abstractmethod
    def read(self) -> model.SubmodelElement:
        """ElementReference가 가리키는 SubmodelElement 객체를 반환한다.

        Returns:
            model.SubmodelElement: ElementReference가 가리키는 SubmodelElement 객체.
        """
        pass

    @abstractmethod
    def write(self, sme: model.SubmodelElement) -> None:
        """주어진 SubmodelElement를 이용해서 ElementReference가 가리키는 SubmodelElement 객체를 변경한다.

        Parameters:
            sme (model.SubmodelElement): 변경할 SubmodelElement 객체.
        """
        pass
  
    @abstractmethod
    def read_value(self) -> ElementValue:
        """ElementReference가 가리키는 SubmodelElement 객체의 값을 반환한다.

        Returns:
            ElementValue: ElementReference가 가리키는 SubmodelElement 객체의 값.
        """
        pass

    @abstractmethod
    def update_value(self, value: ElementValue) -> None:
        """ElementReference가 가리키는 SubmodelElement 객체의 값을 변경한다.

        Parameters:
            value (ElementValue): 변경할 값.
        """
        pass

    @abstractmethod
    def update_with_raw_value(self, raw_data: Any) -> None:
        """ElementReference가 가리키는 SubmodelElement 객체의 값을 raw Python 객체로 변경한다.

        Parameters:
            raw_data (Any): 변경할 raw Python 객체.
        """
        pass

    @abstractmethod
    def get_attachment(self) -> Optional[bytes]:
        """File 요소에 첨부된 파일의 바이트 내용을 반환한다.

        Returns:
            Optional[bytes]: 첨부 파일의 바이트 내용. 첨부가 없으면 None.
        """
        pass

    @abstractmethod
    def put_attachment(self, file_path:str, content_type:Optional[str]=None) -> None:
        """주어진 경로의 파일을 File 요소에 첨부한다.

        Args:
            file_path (str): 첨부할 파일 경로.
            content_type (Optional[str]): 첨부 파일의 MIME 타입. None 이면 추론한다.
        """
        pass

    @abstractmethod
    def put_attachment_with_bytes(self, file_name:str, content_type:str, file_bytes:bytes) -> None:
        """바이트 내용을 File 요소에 첨부한다.

        Args:
            file_name (str): 첨부 파일 이름.
            content_type (str): 첨부 파일의 MIME 타입.
            file_bytes (bytes): 첨부할 바이트 내용.
        """
        pass

    @abstractmethod
    def delete_attachment(self) -> None:
        """File 요소에 첨부된 파일을 삭제한다."""
        pass

    @abstractmethod
    def to_json_node(self) -> dict[str, Any]:
        """ElementReference를 polymorphic JSON 객체로 변환하여 반환한다.

        Returns:
            dict[str, Any]: ElementReference를 polymorphic JSON 객체로 변환한 결과.
        """
        pass

    @abstractmethod
    def to_json_string(self) -> str:
        """:meth:`to_json_node` 결과를 JSON 문자열로 직렬화하여 반환한다."""
        pass
