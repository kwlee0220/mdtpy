from __future__ import annotations

from typing import Optional, cast, TypeVar
from abc import ABC, abstractmethod
from collections import UserDict
from functools import cached_property

import requests
import json
from urllib.parse import quote

from basyx.aas import model

from . import fa3st
from .basyx import serde as basyx_serde
from .value import ElementValueType, from_json_object, to_json_object
from .http_client import parse_none_response
from .exceptions import ResourceNotFoundError


def reference(ref_string: str) -> LazyElementReference:
  return LazyElementReference(ref_string)

class ElementReference(ABC):
  @abstractmethod
  def read_json(self) -> str:
    """ElementReference가 가리키는 SubmodelElement 객체를 json 문자열로 반환한다.

    Returns:
        str: ElementReference가 가리키는 SubmodelElement 객체를 json 문자열로 반환한다.
    """
    pass

  @abstractmethod
  def write_json(self, json_str: str) -> None:
    """SubmodelElement JSON 문자열을 SubmodelElement 객체로 변환하여
    ElementReference가 가리키는 SubmodelElement 객체를 변경한다.

    Parameters:
        json_str (str): 저장할 json 문자열.
    """
    pass

  def read(self) -> model.SubmodelElement:
    """ElementReference가 가리키는 SubmodelElement 객체를 반환한다.

    Returns:
        model.SubmodelElement: ElementReference가 가리키는 SubmodelElement 객체.
    """
    return basyx_serde.from_json(self.read_json())

  def write(self, sme: model.SubmodelElement) -> None:
    """주어진 SubmodelElement를 이용해서 ElementReference가 가리키는 SubmodelElement 객체를 변경한다.

    Parameters:
        sme (model.SubmodelElement): 변경할 SubmodelElement 객체.
    """
    self.write_json(basyx_serde.to_json(sme))
  
  @abstractmethod
  def read_value(self) -> Optional[ElementValueType]:
    """ElementReference가 가리키는 SubmodelElement 객체의 값을 반환한다.

    Returns:
        Optional[ElementValueType]: ElementReference가 가리키는 SubmodelElement 객체의 값.
    """
    pass

  @abstractmethod
  def update_value(self, value: Optional[ElementValueType]) -> None:
    """ElementReference가 가리키는 SubmodelElement 객체의 값을 변경한다.

    Parameters:
        value (Optional[ElementValueType]): 변경할 값.
    """
    pass

  @abstractmethod
  def update_value_with_json_string(self, json_str: str) -> None:
    """ElementReference가 가리키는 SubmodelElement 객체의 값을 json 문자열로 변경한다.

    Parameters:
        json_str (str): 변경할 json 문자열.
    """
    pass


class DefaultElementReference(ElementReference):
  def __init__(self, ref_string: str, endpoint: str) -> None:
    assert ref_string is not None, f"ref_string is None for ElementReference"
    assert endpoint is not None, f"element_url is None for ElementReference[{ref_string}]"

    self.__ref_string = ref_string
    self.__endpoint = endpoint

  @property
  def ref_string(self) -> str:
    return self.__ref_string

  @property
  def endpoint(self) -> str:
    return self.__endpoint

  @cached_property
  def prototype(self) -> model.SubmodelElement:
    return cast(model.SubmodelElement, fa3st.call_get(self.endpoint,
                                                      deserializer=basyx_serde.from_json))

  @property
  def id_short(self) -> str:
    """ElementReference가 가리키는 SubmodelElement 객체의 idShort 값을 반환한다.

    Returns:
        str: ElementReference가 가리키는 SubmodelElement 객체의 idShort 값.
    """
    return str(self.prototype.id_short)

  @property
  def model_type(self) -> type[model.SubmodelElement]:
    """ElementReference가 가리키는 SubmodelElement 객체의 모델 타입을 반환한다.

    Returns:
        str: ElementReference가 가리키는 SubmodelElement 객체의 모델 타입.
    """
    return type(self.prototype)

  @property
  def value_type(self) -> Optional[str]:
    """ElementReference가 가리키는 SubmodelElement 객체의 값 타입을 반환한다.
    Property 타입의 SubmodelElement 객체의 경우에만 사용할 수 있고, 그 외의 경우에는 None을 반환한다.

    Returns:
        Optional[str]: ElementReference가 가리키는 SubmodelElement 객체의 값 타입.
    """
    if isinstance(self.prototype, model.Property):
      return model.datatypes.XSD_TYPE_NAMES[self.prototype.value_type]
    else:
      return None

  @property
  def semantic_id(self) -> Optional[model.Reference]:
    """ElementReference가 가리키는 SubmodelElement 객체의 semanticId 값을 반환한다.

    Returns:
        Optional[model.Reference]: ElementReference가 가리키는 SubmodelElement 객체의 semanticId 값.
    """
    return self.prototype.semantic_id

  def pathes(self) -> list[str]:
    """ElementReference가 가리키는 SubmodelElement 객체의 경로를 반환한다.

    Returns:
        list[str]: ElementReference가 가리키는 SubmodelElement 객체의 경로.
    """
    path_list = cast(str, fa3st.call_get(f"{self.endpoint}/$path"))
    path_list = [ path.strip() for path in path_list[2:-2].split(',') ]
    return [ path[1:-1] for path in path_list ]

  def exists(self) -> bool:
    """ElementReference가 가리키는 SubmodelElement 객체가 존재하는지 여부를 반환한다.

    Returns:
        bool: ElementReference가 가리키는 SubmodelElement 객체가 존재하는지 여부.
    """
    try:
      self.prototype
      return True
    except ResourceNotFoundError:
      return False

  def read_json(self) -> str:
    """ElementReference가 가리키는 SubmodelElement 객체를 json 문자열로 반환한다.

    Returns:
        str: ElementReference가 가리키는 SubmodelElement 객체를 json 문자열로 반환한다.
    """
    return str(fa3st.call_get(self.endpoint))

  def write_json(self, json_str: str) -> None:
    """SubmodelElement JSON 문자열을 SubmodelElement 객체로 변환하여
    ElementReference가 가리키는 SubmodelElement 객체를 변경한다.

    Parameters:
        json_str (str): 저장할 json 문자열.
    """
    fa3st.call_put(self.endpoint, json_str)

  def read(self) -> model.SubmodelElement:
    """ElementReference가 가리키는 SubmodelElement 객체를 반환한다.

    Returns:
        model.SubmodelElement: ElementReference가 가리키는 SubmodelElement 객체.
    """
    return cast(model.SubmodelElement, fa3st.call_get(self.endpoint,
                                                      deserializer=basyx_serde.from_json))

  def write(self, sme: model.SubmodelElement) -> None:
    """ElementReference가 가리키는 SubmodelElement 객체를 변경한다.

    Parameters:
        sme (model.SubmodelElement): 변경할 SubmodelElement 객체.
    """
    fa3st.call_put(self.endpoint, basyx_serde.to_json(sme))
  
  def read_value(self) -> Optional[ElementValueType]:
    """ElementReference가 가리키는 SubmodelElement 객체의 값을 반환한다.

    Returns:
        Optional[ElementValueType]: ElementReference가 가리키는 SubmodelElement 객체의 값.
    """
    json_str = cast(str, fa3st.call_get(f"{self.endpoint}/$value"))
    json_obj = json.loads(json_str)
    _, value = next(iter(json_obj.items()))
    return from_json_object(value, self.prototype)

  def update_value(self, value: Optional[ElementValueType]) -> None:
    """ElementReference가 가리키는 SubmodelElement 객체의 값을 변경한다.

    Parameters:
        value (Optional[ElementValueType]): 변경할 값.
    """
    value_json_str = json.dumps(to_json_object(value, self.prototype))
    fa3st.call_patch(f"{self.endpoint}/$value", value_json_str)

  def update_value_with_json_string(self, json_str: str) -> None:
    """ElementReference가 가리키는 SubmodelElement 객체의 값을 json 문자열로 변경한다.

    Parameters:
        json_str (str): 변경할 json 문자열.
    """
    resp = requests.put(f"{self.endpoint}/$value", json=json_str)
    parse_none_response(resp)

  def add(self, sme: model.SubmodelElement) -> None:
    """ElementReference가 가리키는 SubmodelElement 객체를 추가한다.

    Parameters:
        sme (model.SubmodelElement): 추가할 SubmodelElement 객체.
    """
    fa3st.call_post(self.endpoint, basyx_serde.to_json(sme))

  def remove(self) -> None:
    """ElementReference가 가리키는 SubmodelElement 객체를 삭제한다.

    Parameters:
        sme (model.SubmodelElement): 삭제할 SubmodelElement 객체.
    """
    fa3st.call_delete(self.endpoint)

  def get_attachment(self) -> Optional[bytes]:
    resp = requests.get(url=f'{self.endpoint}/attachment', verify=False)
    ret = fa3st.read_file_response(resp)
    return ret[1] if ret else None

  def put_attachment(self, file_path:str, content_type:Optional[str]=None) -> None:
    import os
    from .value import to_file_value
    from requests_toolbelt.multipart.encoder import MultipartEncoder

    file_value = to_file_value(file_path, content_type=content_type)
    self.update_value(file_value)
    
    url = f'{self.endpoint}/attachment'
    file_name = os.path.basename(file_path)
    content_type = file_value['content_type']
    m = MultipartEncoder(
      fields={
        'fileName': file_name,
        'contentType': content_type,
        'content': ('filename', open(file_path, 'rb'), content_type)
      }
    )
    requests.put(url, data=m, headers={'Content-Type': m.content_type}, verify=False)
      
  def delete_attachment(self) -> None:
    file_sme = (cast(model.File, self.prototype))
    requests.delete(f'{self.endpoint}/attachment', verify=False)
    file_sme.value = None
    self.write(file_sme)

  def __repr__(self) -> str:
    return self.ref_string


T = TypeVar('T', bound=ElementReference)
class ElementReferenceDict(UserDict[str,T], ElementReference):
  def __init__(self, ref_dict: dict[str,T]):
    super().__init__(ref_dict)

  def read(self) -> model.SubmodelElementCollection:
    raise NotImplementedError("ElementReferenceDict.read() is not implemented")

  def write(self, sme: model.SubmodelElementCollection) -> None:
    raise NotImplementedError("ElementReferenceDict.write() is not implemented")

  def read_json(self) -> str:
    raise NotImplementedError("ElementReferenceDict.read_json() is not implemented")

  def write_json(self, json_str: str) -> None:
    raise NotImplementedError("ElementReferenceDict.write_json() is not implemented")

  def read_value(self) -> dict[str, Optional[ElementValueType]]:
    return { k:ref.read_value() for k, ref in self.data.items() }

  def update_value(self, new_values:dict[str, Optional[ElementValueType]]) -> None:
    for k,v in new_values.items():
      if k in self.data:
        self.data[k].update_value(v)
      else:
        raise ResourceNotFoundError.create("ElementReference", f"key={k}")

  def update_value_with_json_string(self, json_str: str) -> None:
    json_obj = json.loads(json_str)
    assert isinstance(json_obj, dict), f"Invalid json object: {json_str}"

    for k, v in json_obj.items():
      if k in self.data:
        self.data[k].update_value_with_json_string(json.dumps(v))


class LazyElementReference(ElementReference):
  def __init__(self, ref_string: str) -> None:
    self.ref_string = ref_string

  @cached_property
  def reference(self) -> DefaultElementReference:
    from .instance import mdt_manager
    assert mdt_manager is not None, "MDTManager is not connected"
    return mdt_manager.resolve_reference(self.ref_string)

  def read_json(self) -> str:
    return self.reference.read_json()

  def write_json(self, json_str: str) -> None:
    self.reference.write_json(json_str)

  def read(self) -> model.SubmodelElement:
    return self.reference.read()

  def write(self, sme: model.SubmodelElement) -> None:
    self.reference.write(sme)

  def read_value(self) -> Optional[ElementValueType]:
    return self.reference.read_value()

  def update_value(self, value: Optional[ElementValueType]) -> None:
    self.reference.update_value(value)

  def update_value_with_json_string(self, json_str: str) -> None:
    self.reference.update_value_with_json_string(json_str)