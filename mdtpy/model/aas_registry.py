from __future__ import annotations

from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dataclasses_json import dataclass_json
from .aas_model import *


@dataclass_json
@dataclass(slots=True)
class SubmodelDescriptor:
    id: str
    idShort: Optional[str] = field(default=None)
    semanticId: Optional[Reference] = field(default=None)
    administration: Optional[AdministrativeInformation] = field(default=None)
    endpoints: list[Endpoint] = field(default_factory=list)
    supplementalSemanticId: list[Reference] = field(default_factory=list)


@dataclass_json
@dataclass(slots=True)
class AssetAdministrationShellDescriptor:
    id: str
    assetKind: AssetKind
    # assetType: str
    idShort: Optional[str] = field(default=None)
    administration: Optional[AdministrativeInformation] = field(default=None)
    globalAssetId: Optional[str] = field(default=None)
    endpoints: list[Endpoint] = field(default_factory=list)
    specificAssetIds: list[SpecificAssetId] = field(default_factory=list)
    submodelDescriptors: list[SubmodelDescriptor] = field(default_factory=list)
        
        
class AssetAdministrationShellRegistry(ABC):
    @abstractmethod
    def getAllAssetAdministrationShellDescriptors(self) -> list[AssetAdministrationShellDescriptor]: pass
    
    @abstractmethod
    def getAllAssetAdministrationShellDescriptorsByIdShort(self, idShort:str) \
        -> list[AssetAdministrationShellDescriptor]: pass
    
    @abstractmethod
    def getAssetAdministrationShellDescriptorById(self, id:str) -> AssetAdministrationShellDescriptor: pass
    
    @abstractmethod
    def postAssetAdministrationShellDescriptor(self, descriptor:AssetAdministrationShellDescriptor) \
        -> AssetAdministrationShellDescriptor: pass
    
    @abstractmethod
    def putAssetAdministrationShellDescriptorById(self, descriptor:AssetAdministrationShellDescriptor) \
        -> AssetAdministrationShellDescriptor: pass
    
    @abstractmethod
    def deleteAssetAdministrationShellDescriptorById(self, id:str) -> None: pass

        
class SubmodelRegistry(ABC):
    @abstractmethod
    def getSubmodelDescriptorById(self, submodel_id:str) -> SubmodelDescriptor: pass
    
    @abstractmethod
    def getAllSubmodelDescriptorsByIdShort(self, idShort:str) -> list[SubmodelDescriptor]: pass
    
    @abstractmethod
    def getAllSubmodelDescriptors(self) -> list[SubmodelDescriptor]: pass
    
    @abstractmethod
    def postSubmodelDescriptor(self, submodel:SubmodelDescriptor) -> SubmodelDescriptor: pass
    
    @abstractmethod
    def putSubmodelDescriptorById(self, submodel:SubmodelDescriptor) -> SubmodelDescriptor: pass
    
    @abstractmethod
    def deleteSubmodelDescriptorById(self, submodelId:str) -> None: pass