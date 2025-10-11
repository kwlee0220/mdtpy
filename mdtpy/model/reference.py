from __future__ import annotations

from typing import Any
from abc import ABC, abstractmethod
from collections import OrderedDict
import time

from .aas_model import SubmodelElement, Property, SubmodelElementCollection, SubmodelElementList
from .aas_service import MDTFile, SubmodelService
from .exceptions import ResourceNotFoundError
from .value import ElementValue, PropertyValue, ElementCollectionValue, ElementListValue, to_value


class ElementReference(ABC):
    @property
    @abstractmethod
    def submodel(self) -> SubmodelService: pass
    
    @property
    @abstractmethod
    def path(self) -> str: pass
    
    @abstractmethod
    def read(self) -> SubmodelElement: pass
    
    def read_value(self) -> Any:
        return self.read().read_value()
    
    @abstractmethod
    def update(self, sme:SubmodelElement) -> None: pass
    
    @abstractmethod
    def update_value(self, value:Any): pass
    
    @abstractmethod
    def update_with_string(self, json_str:str): pass
    
    @abstractmethod
    def get_element_value(self) -> ElementValue: pass
    
    @abstractmethod
    def get_file_content(self) -> tuple[str, bytes]: pass
    
    @abstractmethod
    def put_file(self, file:MDTFile) -> None: pass

    @abstractmethod
    def to_json_object(self) -> dict[str,str]: pass
        

class DefaultElementReference(ElementReference):
    __slots__ = ('_submodel_service', '_path', '__buffer', )
    
    def __init__(self, submodel_service:SubmodelService, path:str):
        self._submodel_service = submodel_service
        self._path = path
        self.__buffer:SubmodelElement = None
        
    @property
    def submodel(self) -> SubmodelService:
        return self._submodel_service
        
    @property
    def path(self) -> str:
        return self._path
    
    def read(self) -> SubmodelElement:
        self.__buffer = self._submodel_service.getSubmodelElementByPath(self._path)
        return self.__buffer

    def update(self, sme:SubmodelElement) -> None:
        self.__buffer = sme
        self._submodel_service.putSubmodelElementByPath(self._path, sme)
    
    def update_value(self, value:Any):
        if self.__buffer is None:
            self.__buffer = self._submodel_service.getSubmodelElementByPath(self._path)
        self.__buffer.update_value(value)
        smev = to_value(self.__buffer)
        self._submodel_service.patchSubmodelElementValueByPath(self._path, smev)
    
    def update_with_string(self, value:str) -> None:
        if self.__buffer is None:
            self.__buffer = self._submodel_service.getSubmodelElementByPath(self._path)
        self.__buffer.update_with_string(value)
        elm_value = self.__buffer.read_value()
        self._submodel_service.patchSubmodelElementValueByPath(self._path, elm_value)
            
    def get_file_content(self) -> tuple[str, bytes]:
        return self._submodel_service.getFileContentByPath(self._path)
            
    def put_file(self, file:MDTFile) -> None:
        self._submodel_service.putFileByPath(self._path, file)
        
    def get_element_value(self) -> ElementValue:
        if isinstance(self.__buffer, Property):
            return PropertyValue(self.__buffer.value)
        elif isinstance(self.__buffer, SubmodelElementList):
            return ListValue(self.__buffer.value)
        elif isinstance(self.__buffer, SubmodelElementCollection):
            return CollectionValue(self.__buffer.value)
        else:
            raise ValueError(f'UnsupportedElementValue: {self.__buffer}')

    def to_json_object(self) -> dict[str,str]:
        return {
            '@type': 'mdt:ref:element',
            'submodelReference': {
                'instanceId': self._submodel_service.instance_id,
                'submodelIdShort': self._submodel_service.idShort
            },
            'elementPath': self._path
        }
    
    def __repr__(self):
        return f'ref: {self._path}'
        
    @property
    def buffer(self) -> SubmodelElement:
        if not self.__buffer:
            self.__buffer = self._submodel_service.getSubmodelElementByPath(self.path)
        return self.__buffer
    

class ElementReferenceCollection:
    def __init__(self, references:dict[str,ElementReference]=OrderedDict(),
                    element_type:str="ElementReference"):
        self._references = references
        self._element_type = element_type

    def __iter__(self):
        return iter((key, ref) for key, ref in self._references.items())
    
    def __bool__(self):
        return len(self._references) > 0
    
    def __len__(self):
        return len(self._references)
    
    def keys(self) -> set[str]:
        return set(self._references.keys())
    
    def values(self) -> list[ElementReference]:
        return list(self._references.values())
    
    def __contains__(self, key) -> bool:
        return key in self._references
        
    def __getitem__(self, key:str|int) -> ElementReference:
        return self.__get_reference(key)
        
    def __setitem__(self, key:str|int, value:SubmodelElement|Any) -> None:
        ref = self.__get_reference(key)
        if isinstance(value, SubmodelElement):
            ref.update(value)
        else:
            ref.update_value(value)
            
    def __get_reference(self, key:str|int) -> ElementReference:
        if isinstance(key, str):
            try:
                return self._references[key]
            except KeyError:
                raise ResourceNotFoundError.create(self._element_type, f'key={key}')
        elif isinstance(key, int):
            ref_list = list(self._references.values())
            try:
                return ref_list[key]
            except Exception:
                raise ResourceNotFoundError.create(self._element_type, f'index={key}')
        else:
            raise ValueError(f'Invalid ElementReference key: {key}')
    
    def __repr__(self):
        list_str = ', '.join([f"{key}={ref}" for key, ref in self._references.items()])
        return 'ref_collection: {${list_str}}'