from __future__ import annotations

from typing import Optional, Any
from abc import ABC, abstractmethod
from .aas_model import *


def to_value(sme:Optional[SubmodelElement]) -> Optional[ElementValue]:
    if sme is None:
        return None
    if isinstance(sme, Property):
        return PropertyValue(sme.value)
    elif isinstance(sme, SubmodelElementCollection):
        return ElementCollectionValue({ element.idShort:to_value(element) for element in sme.value })
    elif isinstance(sme, SubmodelElementList):
        return ElementListValue([to_value(element) for element in sme.value ])
    elif isinstance(sme, File):
        value:dict[str,str] = { 'contentType': sme.contentType }
        if sme.value:
            value['value'] = sme.value
        return FileValue(content_type=sme.contentType, value=sme.value)
    elif isinstance(sme, Range):
        json_obj:dict[str,str] = sme.serializeValue()
        json_obj.pop('idShort')
        return RangeValue(**json_obj)
    else:
        raise NotImplementedError(f"Unknown SubmodelElement type: {type(sme)}")


class ElementValue(ABC):
    @abstractmethod
    def to_json_object(self) -> Any:
        pass

class ElementCollectionValue(ElementValue):
    def __init__(self, elements:dict[str,ElementValue]):
        super().__init__()
        self.elements = elements
        
    def to_json_object(self) -> dict[str,Any]:
        return { name:smev.to_json_object() for name, smev in self.elements.items()}


class ElementListValue(ElementValue):
    def __init__(self, elements:list[ElementValue]):
        super().__init__()
        self.elements = elements
        
    def to_json_object(self) -> list[Any]:
        return [smev.to_json_object() for smev in self.elements]


class DataElementValue(ElementValue): pass

class PropertyValue(DataElementValue):
    def __init__(self, value:Optional[str]):
        super().__init__()
        self.value = value
        
    def to_json_object(self) -> Optional[str]:
        return self.value
    
    def __repr__(self):
        return str(self.value) if self.value else ''

 
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
        
    def to_json_object(self) -> dict[str,Optional[str]]:
        return {'min': self.min, 'max': self.max}


class MultiLanguagePropertyValue(ElementValue):
    def __init__(self, lang_texts:list[LangStringTextType]):
        super().__init__()
        self.lang_texts = lang_texts
        
    def to_json_object(self) -> dict[str, dict[str,str]]:
        return [ self.__serialize_text(tt) for tt in self.lang_texts ]
    
    def __serialize_text(self, text_type:LangStringTextType) -> dict[str,str]:
        return { 'language': text_type.language, 'text': text_type.text }