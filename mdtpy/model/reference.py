from __future__ import annotations

from typing import Any
from abc import ABC, abstractmethod
from collections import OrderedDict

from .aas_model import SubmodelElement, Property
from .aas_service import MDTFile, SubmodelService
from .exceptions import ResourceNotFoundError
from .value import ElementValue


class ElementReference(ABC):
    @property
    @abstractmethod
    def submodel(self) -> SubmodelService: pass
    
    @property
    @abstractmethod
    def path(self) -> str: pass
    
    @abstractmethod
    def read(self) -> SubmodelElement: pass
    
    @abstractmethod
    def read_value(self) -> ElementValue: pass
    
    @abstractmethod
    def update(self, smev:ElementValue): pass
    
    @abstractmethod
    def update_with_string(self, json_str:str): pass
    
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
        return self._submodel_service.getSubmodelElementByPath(self._path)
    
    def read_value(self):
        from .value import to_value
        return to_value(self.read())
    
    def update(self, smev:ElementValue|dict[str,Any]):
        self._submodel_service.patchSubmodelElementValueByPath(self._path, smev)
    
    def update_with_string(self, value:str) -> None:
        match self.buffer:
            case Property():
                self._submodel_service.patchSubmodelElementValueByPath(self._path, value)
            case _:
                raise ValueError('UnsupportedOperation: update_with_string')
            
    def get_file_content(self) -> tuple[str, bytes]:
        return self._submodel_service.getFileContentByPath(self._path)
            
    def put_file(self, file:MDTFile) -> None:
        self._submodel_service.putFileByPath(self._path, file)

    def to_json_object(self) -> dict[str,str]:
        return {
            'referenceType': 'default',
            'instanceId': self._submodel_service.instance_id,
            'submodelIdShort': self._submodel_service.idShort,
            'idShortPath': self._path
        }
    
    def __repr__(self):
        return self._path
        
    @property
    def buffer(self) -> SubmodelElement:
        if not self.__buffer:
            self.__buffer = self._submodel_service.getSubmodelElementByPath(self.path)
        return self.__buffer
    
 
class ElementReferenceCollection:
    def __init__(self):
        self._references:OrderedDict[str,ElementReference] = OrderedDict()
            
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
    
    def __repr__(self):
        list_str = ', '.join([f"{key}={ref}" for key, ref in self._references.items()])
        return '{' + list_str + '}'
        
    def __getitem__(self, key:str) -> Any:
        if isinstance(key, str):
            return self.__assert_key(key).read()
        elif isinstance(key, int):
            return self.__assert_index(key).read()
        else:
            raise ValueError(f'Invalid ElementReference index: {key}')
        
    def __setitem__(self, key:str|int, value:str|ElementValue|MDTFile) -> None:
        ref = None
        if isinstance(key, str):
            ref = self.__assert_key(key)
        elif isinstance(key, int):
            ref = self.__assert_index(key)
        else:
            raise ValueError(f'Invalid ElementReference: key={key}')
        
        if isinstance(value, str):
            ref.update_with_string(value)
        elif isinstance(value, int|float|bool):
            ref.update_with_string(str(value))
        elif isinstance(value, ElementValue):
            ref.update(value)
        elif isinstance(value, MDTFile):
            ref.put_file(value)
        else:
            raise ValueError(f'Invalid ElementValue: {value}')
    
    def append(self, key:str, ref:ElementReference) -> ElementReferenceCollection:
        self._references[key] = ref
        return self
    
    def __call__(self, *args, **kwds):
        assert len(args) == 1
        
        key = args[0]
        if isinstance(key, str):
            return self.__assert_key(key)
        elif isinstance(key, int):
            return self.__assert_index(key)
        else:
            raise ValueError(f'Invalid ElementReference key: {key}')
        
    def __assert_key(self, key:str) -> ElementReference:
        try:
            return self._references[key]
        except KeyError:
            raise ResourceNotFoundError.create("ElementReference", f'key={key}')
        
    def __assert_index(self, index:int) -> ElementReference:
        ref_list = list(self._references.values())
        try:
            return ref_list[index]
        except Exception:
            raise ResourceNotFoundError.create("ElementReference", f'index={index}')
    