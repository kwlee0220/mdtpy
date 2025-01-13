from __future__ import annotations

from typing import Optional, Any
from abc import ABC, abstractmethod
from .aas_model import *


def to_value(sme:SubmodelElement) -> ElementValue:
    if isinstance(sme, Property):
        return PropertyValue(sme.value)
    elif isinstance(sme, SubmodelElementCollection):
        return ElementValueCollection({ element.idShort:to_value(element) for element in sme.value })
    elif isinstance(sme, SubmodelElementList):
        return ElementValueList([to_value(element) for element in sme.value ])
    elif isinstance(sme, File):
        value:dict[str,str] = { 'contentType': sme.contentType }
        if sme.value:
            value['value'] = sme.value
        return FileValue(content_type=sme.contentType, value=sme.value)
    elif isinstance(sme, Range):
        json_obj:dict[str,str] = sme.serializeValue()
        json_obj.pop('idShort')
        return RangeValue(**json_obj)
        
class ElementValue(ABC):
    @abstractmethod
    def to_json_object(self): Any

class ElementValueCollection(ElementValue):
    def __init__(self, elements:dict[str,ElementValue]):
        super().__init__()
        self.elements = elements
        
    def to_json_object(self) -> dict[str,Any]:
        return { name:smev.to_json_object() for name, smev in self.elements.items()}


class ElementValueList(ElementValue):
    def __init__(self, elements:list[ElementValue]):
        super().__init__()
        self.elements = elements
        
    def to_json_object(self) -> list[Any]:
        return [smev.to_json_object() for smev in self.elements]


class DataElementValue(ElementValue): pass

class PropertyValue(DataElementValue):
    def __init__(self, value:str):
        super().__init__()
        self.value = value
        
    def to_json_object(self) -> str:
        return self.value
    
    def __repr__(self):
        return self.value

 
class FileValue(DataElementValue):
    def __init__(self, content_type:str, value:Optional[str]=None):
        super().__init__()
        self.contentType = content_type
        self.value = value
        
    def to_json_object(self) -> dict[str,str]:
        serialized:dict[str,str] = { 'contentType': self.contentType }
        if self.value:
            serialized['value'] = self.value
        return serialized
    
    def __repr__(self):
        return f"{self.value} ({self.contentType})"

 
class RangeValue(DataElementValue):
    def __init__(self, min:Optional[str]=None, max:Optional[str]=None):
        super().__init__()
        self.min = min
        self.max = max
        
    def to_json_object(self) -> dict[str,str]:
        return {'min': self.min, 'max': self.max}


class MultiLanguagePropertyValue(ElementValue):
    def __init__(self, lang_texts:list[LangStringTextType]):
        super().__init__()
        self.lang_texts = lang_texts
        
    def to_json_object(self) -> dict[str, dict[str,str]]:
        return [ self.__serialize_text(tt) for tt in self.lang_texts ]
    
    def __serialize_text(self, text_type:LangStringTextType) -> dict[str,str]:
        return { 'language': text_type.language, 'text': text_type.text }