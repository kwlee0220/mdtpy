from __future__ import annotations

from abc import ABC, abstractmethod

from .aas_model import AssetAdministrationShell, Submodel
from .aas_service import AssetAdministrationShellService, SubmodelService
    
    
class AssetAdministrationShellRepository(ABC):
    @abstractmethod
    def getAllAssetAdministrationShells(self) -> list[AssetAdministrationShellService]: pass
    @abstractmethod
    def getAssetAdministrationShellById(self, aasId:str) -> AssetAdministrationShellService: pass
    @abstractmethod
    def getAssetAdministrationShellByAssetId(self, assetId:str) -> list[AssetAdministrationShellService]: pass
    @abstractmethod
    def getAssetAdministrationShellByIdShort(self, idShort:str) -> list[AssetAdministrationShellService]: pass
    
    @abstractmethod
    def postAssetAdministrationShell(self, aas:AssetAdministrationShell) -> AssetAdministrationShellService: pass
    @abstractmethod
    def updateAssetAdministrationShellById(self, aas:AssetAdministrationShell) -> AssetAdministrationShellService: pass
    @abstractmethod
    def deleteAssetAdministrationShellById(self, aasId:str) -> None: pass
    
    
class SubmodelRepository(ABC):
    @abstractmethod
    def getAllSubmodels(self) -> list[SubmodelService]: pass
    
    @abstractmethod
    def getSubmodelById(self, id:str) -> SubmodelService: pass
    
    @abstractmethod
    def getAllSubmodelBySemanticId(self, semanticId:str) -> list[SubmodelService]: pass
    
    @abstractmethod
    def getAllSubmodelsByIdShort(self, idShort:str) -> list[SubmodelService]: pass
    
    @abstractmethod
    def postSubmodel(self, submodel:Submodel) -> SubmodelService: pass
    
    @abstractmethod
    def putSubmodelById(self, submodel:Submodel) -> SubmodelService: pass
    
    @abstractmethod
    def deleteSubmodelById(self, id:str) -> None: pass