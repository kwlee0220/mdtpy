from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Any, cast

import json
from functools import cached_property

from basyx.aas import model

from mdtpy import fa3st
from mdtpy.value.element_value import FileValue
from ..basyx import serde as basyx_serde
from .reference import ElementReference
from ..value import ElementValue

if TYPE_CHECKING:
    from ..instance import MDTInstanceManager


class BaseElementReference(ElementReference):
    """FA³ST 인스턴스의 단일 SubmodelElement 를 전역 ``mdt_manager`` 를 통해 다루는
    ElementReference 구현체.

    참조 표현식(:attr:`ref_string`)만 보관한 채 생성된다. 읽기/쓰기 연산(:meth:`read`,
    :meth:`write`, :meth:`read_value`, :meth:`update_value`,
    :meth:`update_with_raw_value`)은 전역 ``mdt_manager`` 의 참조 기반 API 에
    위임하고, 요소 추가/삭제 및 첨부(:meth:`add`, :meth:`remove`,
    :meth:`put_attachment` 등)는 지연 해석된 :attr:`service_url` 로 FA³ST 인스턴스에
    직접 접근한다. 따라서 서버 접속 없이도 생성할 수 있으며,
    :attr:`prototype` / :attr:`service_url` / :attr:`mdt_manager` 는 최초 접근 시
    전역 ``mdt_manager`` 로 해석하여 한 번만 계산해 캐싱한다.
    """

    def __init__(self, ref_string: str, *, service_url: Optional[str] = None) -> None:
        """참조 표현식 문자열로 BaseElementReference 를 생성한다.

        Args:
            ref_string (str): 참조 표현식 문자열.
            service_url (Optional[str]): 대상 SubmodelElement 의 FA³ST 접근 URL. 미리
                알고 있으면 지정하고, None 이면 :attr:`service_url` 최초 접근 시 전역
                ``mdt_manager`` 로 지연 해석한다.
        """
        assert ref_string is not None, "ref_string is None"
        self.__ref_string = ref_string
        self.__service_url = service_url
        self.__json_node: Optional[dict[str, Any]] = None

    @property
    def ref_string(self) -> str:
        """참조 표현식 문자열을 반환한다.

        Returns:
            str: 참조 표현식 문자열.
        """
        return self.__ref_string

    @property
    def semantic_id(self) -> Optional[model.Reference]:
        """ElementReference가 가리키는 SubmodelElement 객체의 semanticId 값을 반환한다.

        Returns:
            Optional[model.Reference]: ElementReference가 가리키는 SubmodelElement 객체의 semanticId 값.
        """
        return self.prototype.semantic_id

    @property
    def model_type(self) -> type[model.SubmodelElement]:
        """ElementReference가 가리키는 SubmodelElement 객체의 모델 타입을 반환한다.

        Returns:
            type[model.SubmodelElement]: ElementReference가 가리키는 SubmodelElement 객체의 모델 타입.
        """
        return type(self.prototype)

    @property
    def value_type(self) -> Optional[str]:
        """ElementReference가 가리키는 SubmodelElement 객체의 값 타입을 반환한다.
        Property 타입의 SubmodelElement 객체의 경우에만 사용할 수 있고, 그 외의 경우에는 None을 반환한다.

        Returns:
            Optional[str]: ElementReference가 가리키는 SubmodelElement 객체의 값 타입.
        """
        match self.prototype:
            case model.Property():
                return model.datatypes.XSD_TYPE_NAMES[self.prototype.value_type]
            case model.SubmodelElementCollection():
                return 'SubmodelElementCollection'
            case model.SubmodelElementList():
                return 'SubmodelElementList'
            case model.File():
                return 'File'
            case model.MultiLanguageProperty():
                return 'MultiLanguageProperty'
            case model.Range():
                return 'Range'
            case _:
                raise RuntimeError(f"Unsupported SubmodelElement type: {type(self.prototype)}")
        
    def pathes(self) -> list[str]:
        """ElementReference가 가리키는 SubmodelElement 객체의 경로를 반환한다.

        Returns:
            list[str]: ElementReference가 가리키는 SubmodelElement 객체의 경로.
        """
        path_list = cast(str, fa3st.call_get(f"{self.service_url}/$path"))
        path_list = [ path.strip() for path in path_list[2:-2].split(',') ]
        return [ path[1:-1] for path in path_list ]

    def read(self) -> model.SubmodelElement:
        """ElementReference가 가리키는 SubmodelElement 객체를 반환한다.

        Returns:
            model.SubmodelElement: ElementReference가 가리키는 SubmodelElement 객체.
        """
        return self.mdt_manager.read_element_of_reference(self.__ref_string)

    def write(self, sme: model.SubmodelElement) -> None:
        """주어진 SubmodelElement를 이용해서 ElementReference가 가리키는 SubmodelElement 객체를 변경한다.

        Args:
            sme (model.SubmodelElement): 변경할 SubmodelElement 객체.
        """
        self.mdt_manager.write_element_of_reference(self.__ref_string, sme)

    def read_value(self) -> ElementValue:
        """ElementReference가 가리키는 SubmodelElement 객체의 값을 반환한다.

        Returns:
            ElementValue: ElementReference가 가리키는 SubmodelElement 객체의 값.
        """
        return self.mdt_manager.read_value_of_reference(self.__ref_string)

    def update_value(self, value: ElementValue) -> None:
        """ElementReference가 가리키는 SubmodelElement 객체의 값을 변경한다.

        Args:
            value (ElementValue): 변경할 값.
        """
        self.mdt_manager.update_value_of_reference(self.__ref_string, value)

    def update_with_raw_value(self, raw_data: Any) -> None:
        """ElementReference가 가리키는 SubmodelElement 객체의 값을 raw Python 객체로 변경한다.

        Args:
            raw_data (Any): 변경할 raw Python 객체.
        """
        self.mdt_manager.update_raw_object_of_reference(self.__ref_string, raw_data)

    def add(self, sme: model.SubmodelElement) -> None:
        """ElementReference가 가리키는 SubmodelElement 객체를 추가한다.

        Args:
            sme (model.SubmodelElement): 추가할 SubmodelElement 객체.
        Raises:
            RuntimeError: 대상 MDTInstance 가 실행 중이 아니어서 service_url 을 해석할 수
                없는 경우.
        """
        if self.service_url is None:
            raise RuntimeError(f"MDTInstance is not running: ref={self.ref_string}")
        fa3st.call_post(self.service_url, basyx_serde.to_json(sme))

    def remove(self) -> None:
        """ElementReference가 가리키는 SubmodelElement 객체를 삭제한다.

        Raises:
            RuntimeError: 대상 MDTInstance 가 실행 중이 아니어서 service_url 을 해석할 수
                없는 경우.
        """
        if self.service_url is None:
            raise RuntimeError(f"MDTInstance is not running: ref={self.ref_string}")
        fa3st.call_delete(self.service_url)

    def get_attachment(self) -> Optional[bytes]:
        """File 요소에 첨부된 파일의 바이트 내용을 반환한다.

        Returns:
            Optional[bytes]: 첨부 파일의 바이트 내용. 첨부가 없으면 None.
        """
        ret = fa3st.call_get_file(f'{self.service_url}/attachment')
        return ret[1] if ret else None

    def put_attachment(self, file_path:str, content_type:Optional[str]=None) -> None:
        """주어진 경로의 파일을 File 요소에 첨부한다.

        Args:
            file_path (str): 첨부할 파일 경로.
            content_type (Optional[str]): 첨부 파일의 MIME 타입. None 이면 추론한다.
        """
        file_value = FileValue.from_file_path(file_path, content_type=content_type)
        self.update_value(file_value)

        url = f'{self.service_url}/attachment'
        file_name = file_value.value
        content_type = file_value.content_type
        with open(file_path, 'rb') as f:
            files = {'content': (file_name, f, content_type)}
            data = {'fileName': file_name, 'contentType': content_type}
            fa3st.call_put_file(url, files, data)

    def put_attachment_with_bytes(self, file_name:str, content_type:str, file_bytes:bytes) -> None:
        """바이트 내용을 File 요소에 첨부한다.

        Args:
            file_name (str): 첨부 파일 이름.
            content_type (str): 첨부 파일의 MIME 타입.
            file_bytes (bytes): 첨부할 바이트 내용.
        """
        from io import BytesIO

        url = f'{self.service_url}/attachment'
        with BytesIO(file_bytes) as f:
            files = {'content': (file_name, f, content_type)}
            data = {'fileName': file_name, 'contentType': content_type}
            fa3st.call_put_file(url, files, data)

    def delete_attachment(self) -> None:
        """File 요소에 첨부된 파일을 삭제한다."""
        file_sme = cast(model.File, self.read())
        fa3st.call_delete(f'{self.service_url}/attachment')
        file_sme.value = None
        self.write(file_sme)

    def to_json_node(self) -> dict[str, Any]:
        """참조를 ``@type`` 필드를 가진 polymorphic JSON 객체(dict)로 직렬화하여 반환한다.

        ``ref_string`` 을 전역 ``mdt_manager`` 의 ``to_reference_json`` 로 해석하여 얻은
        JSON 문자열을 dict 로 변환해 반환하며, 결과는 한 번만 계산해 캐싱한다.

        Returns:
            dict[str, Any]: 참조의 JSON 표현.
        """
        if self.__json_node is None:
            json_str = self.mdt_manager.to_reference_json(self.__ref_string)
            self.__json_node = cast(dict[str, Any], json.loads(json_str))
        return self.__json_node

    def to_json_string(self) -> str:
        """참조를 ``@type`` 필드를 가진 polymorphic JSON 문자열로 직렬화하여 반환한다.

        ``ref_string`` 을 전역 ``mdt_manager`` 의 ``to_reference_json`` 로 해석하여 얻은
        JSON 문자열을 그대로 반환한다(:meth:`to_json_node` 와 달리 캐싱하지 않는다).

        Returns:
            str: 참조의 JSON 문자열 표현.
        """
        return self.mdt_manager.to_reference_json(self.__ref_string)

    @cached_property
    def prototype(self) -> model.SubmodelElement:
        """ElementReference가 가리키는 SubmodelElement 객체(프로토타입)를 반환한다.

        :meth:`read` 결과를 최초 접근 시 한 번만 읽어 캐싱한다.

        Returns:
            model.SubmodelElement: ElementReference가 가리키는 SubmodelElement 객체.
        """
        return self.read()

    @property
    def service_url(self) -> Optional[str]:
        """대상 SubmodelElement 의 FA³ST 접근 URL 을 반환한다.

        ``ref_string`` 을 전역 ``mdt_manager`` 에 질의(``get_reference_service_url``)하여
        대상 SubmodelElement 의 접근 URL 을 얻는다. 결과는 최초 접근 시 한 번만 계산해
        캐싱한다.

        Returns:
            Optional[str]: 대상 SubmodelElement 의 접근 URL. 대상 MDTInstance 가 실행 중이
            아니면 None 일 수 있다.
        """
        if self.__service_url is None:
            self.__service_url = self.mdt_manager.get_reference_service_url(self.__ref_string)
        return self.__service_url

    @cached_property
    def mdt_manager(self) -> MDTInstanceManager:
        """전역 ``mdt_manager`` 를 반환한다.

        Returns:
            MDTInstanceManager: 전역 MDTInstanceManager 객체.
        Raises:
            RuntimeError: ``mdtpy.connect()`` 가 아직 호출되지 않아 전역 ``mdt_manager``
                가 초기화되지 않은 경우.
        """
        from ..instance import mdt_manager
        if mdt_manager is None:
            raise RuntimeError("mdt_manager is not initialized")
        return mdt_manager
