from __future__ import annotations

from typing import Any, Union, Optional, TypedDict, NotRequired, cast
from collections.abc import Mapping

from datetime import timedelta
from pathlib import Path
from basyx.aas import model

from .utils import timedelta_to_relativedelta

ListValueType = list[Optional['ElementValueType']]
CollectionValueType = dict[str, Optional['ElementValueType']]
ElementValueType = Union[model.ValueDataType, 'FileValue', 'RangeValue', 'MultiLanguagePropertyValue',
                        ListValueType, CollectionValueType]

PropertyJsonValueType = Union[str,int,float,bool]
ListJsonValueType = list[Optional['ElementJsonValueType']]
CollectionJsonValueType = dict[str, Optional['ElementJsonValueType']]
ElementJsonValueType = Union[PropertyJsonValueType, 'FileJsonValue', 'RangeValue', 'MultiLanguagePropertyValue',
                            ListJsonValueType, CollectionJsonValueType]

ElementValueDict = dict[str, Optional[ElementValueType]]


def update_value_dict(target:ElementValueDict,
                      new_values:Mapping[str, ElementValueType|'ElementReference'|model.SubmodelElement|None]) -> None:
  from .reference import ElementReference
  for key, new_value in new_values.items():
    if key not in target:
      continue
    if new_value is None:
      target[key] = None
    elif isinstance(new_value, ElementReference):
      target[key] = new_value.read_value()
    elif isinstance(new_value, model.SubmodelElement):
      target[key] = get_value(new_value)
    else:
      target[key] = new_value

def to_file_value(path:str, content_type:Optional[str]=None) -> FileValue:
  if content_type is None:
    from tika import parser
    parsed = parser.from_file(path)
    mime_type = parsed["metadata"]["Content-Type"] # type: ignore
  else:
    mime_type = content_type
  return { 'content_type': mime_type, 'value': Path(path).name }

class FileValue(TypedDict):
  content_type: str
  value: Optional[str]
class FileJsonValue(TypedDict):
  contentType: str
  value: Optional[str]

class RangeValue(TypedDict):
  min: Optional[model.ValueDataType]
  max: Optional[model.ValueDataType]

MultiLanguagePropertyValue = dict[str,str]
MultiLanguagePropertyJsonValue = list[dict[str,str]]


def get_value(sme:model.SubmodelElement) -> Optional[ElementValueType]:
  """SubmodelElement 객체의 값을 반환한다.

  Args:
    sme (model.SubmodelElement): 값을 얻어올 SubmodelElement 객체.

  Returns:
    Optional[ElementValueType]: SubmodelElement 객체의 값.
  Raises:
    NotImplementedError: SubmodelElement 객체의 타입이 지원되지 않는 경우.
  """
  assert sme is not None
  match sme:
    case model.Property():
      return sme.value
    case model.SubmodelElementCollection():
      return { str(member.id_short):get_value(member) for member in sme.value }
    case model.SubmodelElementList():
      return [ get_value(member) for member in sme.value ]
    case model.File():
      return { 'content_type': sme.content_type, 'value': sme.value }
    case model.Range():
      return { 'min': sme.min, 'max': sme.max }
    case model.MultiLanguageProperty():
      if sme.value is None:
        return None
      return { lang:text for lang, text in sme.value.items() }
    case _:
      raise NotImplementedError(f"Unknown SubmodelElement type: {type(sme)}")


def update_element_with_value(sme:model.SubmodelElement, value:Optional[ElementValueType]) -> None:
  """SubmodelElement 객체의 값을 변경한다.

  Args:
    sme (model.SubmodelElement): 값을 변경할 SubmodelElement 객체.
    value (Optional[ElementValueType]): 변경할 값.
  Raises:
    NotImplementedError: SubmodelElement 객체의 타입이 지원되지 않는 경우.
  """
  if value is None:
    return
  match sme:
    case model.Property():
      value = timedelta_to_relativedelta(value) if value is not None and isinstance(value, timedelta) else value
      sme.value = value
    case model.SubmodelElementCollection():
      assert isinstance(value, dict)
      for member in sme.value:
        member_value = value.get(str(member.id_short))
        if member_value is not None:
          update_element_with_value(member, member_value)
    case model.SubmodelElementList():
      assert isinstance(value, list)
      for member, member_value in zip[tuple[model.SubmodelElement,ElementValueType]](sme.value, value):
        update_element_with_value(member, member_value)
    case model.File():
      assert isinstance(value, dict), f"FileValue must be a dict: {value}"
      sme.content_type = cast(model.ContentType, value.get('content_type'))
      assert sme.content_type is not None, "content_type is required"
      sme.value = cast(Optional[model.PathType], value.get('value'))
    case model.Range():
      assert isinstance(value, dict), f"RangeValue must be a dict: {value}"
      sme.min = cast(Optional[model.ValueDataType], value.get('min'))
      sme.max = cast(Optional[model.ValueDataType], value.get('max'))
    case model.MultiLanguageProperty():
      assert isinstance(value, dict), f"MultiLanguagePropertyValue must be a dict: {value}"
      sme.value = model.MultiLanguageTextType(cast(dict[str, str], value))
    case _:
      raise NotImplementedError(f"Unknown SubmodelElement type: {type(sme)}")


def from_json_object(value:Optional[ElementJsonValueType], proto:model.SubmodelElement) -> Optional[ElementValueType]:
  """Json 객체를 ElementValueType 객체로 변환한다.

  Args:
    value (Optional[JsonElementValueType]): 변환할 Json 객체.
    proto (model.SubmodelElement): 변환할 SubmodelElement 객체.

  Returns:
    Optional[ElementValueType]: 변환된 ElementValueType 객체.
  Raises:
    NotImplementedError: SubmodelElement 객체의 타입이 지원되지 않는 경우.
  """
  if value is None:
    return None

  match proto:
    case model.Property():
      if isinstance(value, str):
        return cast(ElementValueType, model.datatypes.from_xsd(value, proto.value_type))
      else:
        return cast(model.ValueDataType, value)
    case model.SubmodelElementCollection():
      assert isinstance(value, dict)
      parsed_value = dict[str, Optional[ElementValueType]]()
      for member in proto.value:
        key = str(member.id_short)
        member_value = value.get(key)
        parsed_value[key] = from_json_object(member_value, member) if member_value is not None else None
      return parsed_value
    case model.SubmodelElementList():
      assert isinstance(value, list)
      return [
        from_json_object(member_value, member)
        for member, member_value in zip(proto.value, value)
      ]
    case model.File():
      assert isinstance(value, dict)
      ct, v = value.get('contentType'), value.get('value')
      assert ct is not None, "contentType is required"
      return cast(FileValue, { 'content_type': ct, 'value': v })
    case model.Range():
      assert isinstance(value, dict)
      min = cast(str, value.get('min'))
      min = model.datatypes.from_xsd(min, proto.value_type) if min is not None else None
      max = cast(str, value.get('max'))
      max = model.datatypes.from_xsd(max, proto.value_type) if max is not None else None
      return { 'min': min, 'max': max }
    case model.MultiLanguageProperty():
      assert isinstance(value, list)  # MultiLanguagePropertyJsonValue
      value_list = cast(list[dict[str, str]], value)
      return cast(MultiLanguagePropertyValue,
                  { lang:text for kv in value_list for lang, text in kv.items() })
    case _:
      raise NotImplementedError(f"Unknown SubmodelElement type: {type(proto)}")

def to_json_object(value:Optional[ElementValueType], proto:model.SubmodelElement) -> Optional[ElementJsonValueType]:
  if value is None:
    return None

  match proto:
    case model.Property():
      assert isinstance(value, model.ValueDataType)
      return model.datatypes.xsd_repr(value)
    case model.SubmodelElementCollection():
      assert isinstance(value, dict)
      if proto.value is None:
        return None
      collection_json_value = dict[str, Optional[ElementJsonValueType]]()
      for member in proto.value:
        key = str(member.id_short)
        member_value = value.get(key)
        if member_value is not None:
          collection_json_value[key] = to_json_object(member_value, member)
      return collection_json_value
    case model.SubmodelElementList():
      assert isinstance(value, list)
      return [ to_json_object(member_value, member) for member, member_value in zip[tuple[model.SubmodelElement,ElementValueType]](proto.value, value) ]
    case model.File():
      assert isinstance(value, dict)
      return cast(FileJsonValue, { 'contentType': value.get('content_type'), 'value': value.get('value') })
    case model.Range():
      assert isinstance(value, dict)
      min = cast(Optional[model.ValueDataType], value.get('min'))
      min = model.datatypes.xsd_repr(min) if min is not None else None
      max = cast(Optional[model.ValueDataType], value.get('max'))
      max = model.datatypes.xsd_repr(max) if max is not None else None
      return { 'min': min, 'max': max }
    case model.MultiLanguageProperty():
      assert isinstance(value, dict)
      return cast(MultiLanguagePropertyValue, { lang:text for lang, text in value.items() })
    case _:
      raise NotImplementedError(f"Unknown SubmodelElement type: {type(proto)}")