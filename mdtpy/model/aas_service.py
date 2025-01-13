from __future__ import annotations

from typing import Any
from abc import ABC, abstractmethod

from datetime import timedelta

from .aas_model import *


class AssetAdministrationShellService(ABC):
    """
    Class for manipulating an Asset Administration Shell Service.
    
    Methods:
        getAssetAdministrationShell() -> AssetAdministrationShell:
            Retrieve the Asset Administration Shell.
        putAssetAdministrationShell(aas: AssetAdministrationShell) -> AssetAdministrationShell:
            Update the Asset Administration Shell with the provided instance.
        getAssetInformation() -> AssetInformation:
            Retrieve the Asset Information.
        putAssetInformation(assetInfo: AssetInformation) -> AssetInformation:
            Update the Asset Information with the provided instance.
        getAllSubmodelReferences() -> list[Reference]:
            Retrieve all Submodel References.
        postSubmodelReference(ref: Reference) -> Reference:
            Add a new Submodel Reference.
        deleteSubmodelReference(submodelId: str) -> None:
            Delete the Submodel Reference identified by the given submodelId.
    """
    @abstractmethod
    def getAssetAdministrationShell(self) -> AssetAdministrationShell: pass
    @abstractmethod
    def putAssetAdministrationShell(self, aas:AssetAdministrationShell) -> AssetAdministrationShell: pass
    
    @abstractmethod
    def getAssetInformation(self) -> AssetInformation: pass
    @abstractmethod
    def putAssetInformation(self, assetInfo:AssetInformation) -> AssetInformation: pass
    
    @abstractmethod
    def getAllSubmodelReferences(self) -> list[Reference]: pass
    @abstractmethod
    def postSubmodelReference(self, ref:Reference) -> Reference: pass
    @abstractmethod
    def deleteSubmodelReference(self, submodelId:str) -> None: pass
    
    
class MDTFile:
    """
    A class to represent an AAS File SubmodelElement.
    
    Attributes:
    -----------
    file_path : pathlib.Path
        The path to the file.
    content_type : str, optional
        The MIME type of the file. If not provided, it will be guessed based on the file extension.
    value : str
        The name of the file.
        
    Methods:
    --------
    __init__(file_path: str, content_type: Optional[str] = None):
        Initializes the MDTFile with the given file path and optional content type.
    __repr__():
        Returns a string representation of the MDTFile instance.
    """
    
    def __init__(self, file_path:str, content_type:Optional[str]=None):
        from pathlib import Path
        import mimetypes
        
        self.file_path = Path(file_path)
        self.content_type = content_type if content_type else mimetypes.guess_type(file_path)[0]
        self.value = self.file_path.name
        
    def __repr__(self):
        return f"{self.file_path} ({self.content_type})"


class SubmodelService(ABC):
    """
    Interface class for handing a Submodel.
    
    Properties:
        id (str): Unique identifier for the submodel service.
        idShort (str): Short identifier for the submodel service.
        endpoint (Endpoint): Endpoint associated with the submodel service.
        
    Methods:
        getSubmodel() -> Submodel:
            Retrieve the submodel.
        getAllSubmodelElements() -> list[SubmodelElement]:
            Retrieve all elements of the submodel.
        putSubmodel(submodel: Submodel) -> Submodel:
            Update the submodel with the provided submodel object.
        getSubmodelElementByPath(path: str) -> SubmodelElement:
            Retrieve a SubmodelElement by its path.
        postSubmodelElement(element: SubmodelElement) -> SubmodelElement:
            Add a new SubmodelElement.
        postSubmodelElementByPath(path: str, element: SubmodelElement) -> SubmodelElement:
            Add a new SubmodelElement at the specified path.
        putSubmodelElementByPath(path: str, element: SubmodelElement) -> SubmodelElement:
            Update a SubmodelElement at the specified path.
        patchSubmodelElementValueByPath(path: str, element: ValueOnlySerializable | str) -> None:
            Partially update the value of a SubmodelElement at the specified path.
        deleteSubmodelElementByPath(path: str) -> None:
            Delete a SubmodelElement at the specified path.
        getFileContentByPath(path: str) -> tuple[str, bytes]:
            Retrieve the content of a file at the specified path.
        putFileByPath(path: str, file: MDTFile) -> None:
            Update a file at the specified path.
        deleteFileByPath(path: str) -> None:
            Delete a file at the specified path.
        invokeOperationSync(path: str, inputArguments: list[OperationVariable], 
                            inoutputArguments: list[OperationVariable], timeout: timedelta) -> OperationResult:
            Synchronously invoke an operation at the specified path.
        invokeOperationAsync(path: str, inputArguments: list[OperationVariable], 
                             inoutputArguments: list[OperationVariable], timeout: timedelta) -> OperationHandle:
            Asynchronously invoke an operation at the specified path.
        getOperationAsyncResult(handleId: OperationHandle) -> OperationResult:
            Retrieve the result of an asynchronous operation.
    """
    @property
    @abstractmethod
    def id(self) -> str: pass

    @property
    @abstractmethod
    def idShort(self) -> str: pass

    @property
    @abstractmethod
    def semanticId(self) -> str: pass

    @property
    @abstractmethod
    def endpoint(self) -> Endpoint: pass
    
    @property
    def service_url(self) -> str:
        return self.endpoint.protocolInformation.href
    
    @abstractmethod
    def getSubmodel(self) -> Submodel: pass
    
    @abstractmethod
    def getAllSubmodelElements(self) -> list[SubmodelElement]: pass
    
    @abstractmethod
    def putSubmodel(self, submodel:Submodel) -> Submodel: pass
    
    @abstractmethod
    def getSubmodelElementByPath(self, idShortPath:str) -> SubmodelElement: pass
    
    @abstractmethod
    def postSubmodelElement(self, element:SubmodelElement) -> SubmodelElement: pass
    
    @abstractmethod
    def postSubmodelElementByPath(self, idShortPath:str, element:SubmodelElement) -> SubmodelElement: pass
    
    @abstractmethod
    def putSubmodelElementByPath(self, idShortPath:str, element:SubmodelElement) -> SubmodelElement: pass
    
    @abstractmethod
    def patchSubmodelElementValueByPath(self, idShortPath:str, element:ValueOnlySerializable|str) -> None: pass
    
    @abstractmethod
    def deleteSubmodelElementByPath(self, idShortPath:str) -> None: pass
    
    @abstractmethod
    def getFileContentByPath(self, idShortPath:str) -> tuple[str, bytes]: pass
    
    @abstractmethod
    def putFileByPath(self, idShortPath:str, file:MDTFile) -> None: pass
    
    @abstractmethod
    def deleteFileByPath(self, idShortPath:str) -> None: pass
    
    @abstractmethod
    def invokeOperationSync(self, idShortPath:str, inputArguments:list[OperationVariable],
                            inoutputArguments:list[OperationVariable], timeout:timedelta) -> OperationResult: pass
    
    @abstractmethod
    def invokeOperationAsync(self, idShortPath:str, inputArguments:list[OperationVariable],
                            inoutputArguments:list[OperationVariable], timeout:timedelta) -> OperationHandle: pass
    
    @abstractmethod
    def getOperationAsyncResult(self, handleId:OperationHandle) -> OperationResult: pass