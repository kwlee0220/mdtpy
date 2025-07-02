from __future__ import annotations

from typing import Optional, Generator, Callable
from collections.abc import Iterator
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from dataclasses_json import dataclass_json

from .exceptions import ResourceNotFoundError
from .aas_model import SubmodelElementCollection
from .aas_service import AssetAdministrationShellService, SubmodelService
from .reference import ElementReferenceCollection
from .aas_registry import AssetAdministrationShellRegistry, SubmodelRegistry


@dataclass(frozen=True, unsafe_hash=True, slots=True)
class MDT_SEMANTIC_ID:
    INFORMATION_MODEL = "https://etri.re.kr/mdt/Submodel/InformationModel/1/1"
    DATA = "https://etri.re.kr/mdt/Submodel/Data/1/1"
    AI = "https://etri.re.kr/mdt/Submodel/AI/1/1"
    SIMULATION = "https://etri.re.kr/mdt/Submodel/Simulation/1/1"

class MDTInstanceStatus(Enum):
	STOPPED = 0
	STARTING = 1
	RUNNING = 2
	STOPPING = 3
	FAILED = 4


@dataclass_json
@dataclass(frozen=True, unsafe_hash=True, slots=True)
class InstanceSubmodelDescriptor:
    """
    InstanceSubmodelDescriptor is a data class that represents a Submodel descriptor contained in an MDTInstance.

    Attributes:
        id (str): The unique identifier for the MDTInstance.
        idShort (Optional[str]): A short identifier for the MDTInstance. Defaults to None.
        semanticId (Optional[str]): The semantic identifier for the MDTInstance. Defaults to None.
    """
    id: str
    idShort: Optional[str] = field(default=None)
    semanticId: Optional[str] = field(default=None)
    
@dataclass_json
@dataclass(frozen=True, unsafe_hash=True, slots=True)
class MDTParameterDescriptor:
    """
    A class to represent a parameter descriptor for an MDTInstance.

    Attributes:
    -----------
    name : str
        The name of the parameter.
    valueType : str
        The type of the parameter value.
    """
    name: str
    valueType: str
    
@dataclass_json
@dataclass(frozen=True, unsafe_hash=True, slots=True)
class NamedValueType:
    name: str
    valueType: str
    
@dataclass_json
@dataclass(frozen=True, unsafe_hash=True, slots=True)
class MDTOperationDescriptor:
    name: str
    operationType: str
    inputArguments: list[NamedValueType]
    outputArguments: list[NamedValueType]

@dataclass_json
@dataclass(frozen=True, unsafe_hash=True, slots=True)
class InstanceDescriptor:
    """
    A class used to represent an MDTInstance Descriptor.

    Attributes:
    ----------
    id : str
        The unique identifier for the MDTInstance.
    aasId : str
        The Asset Administration Shell (AAS) identifier.
    aasIdShort : Optional[str]
        The short identifier for the AAS.
    globalAssetId : Optional[str]
        The global asset identifier.
    assetType : Optional[str]
        The type of the asset.
    assetKind : Optional[str]
        The kind of the asset.
    submodels : list[InstanceSubmodelDescriptor]
        A list of submodel descriptors contained with the MDTInstance.
    parameters : list[MDTParameterDescriptor]
        A list of parameter descriptors for the MDTInstance
    operations : list[MDTOperationDescriptor]
        A list of operation descriptors for the MDTInstance
    """
    id: str
    aasId: str = field(hash=False, compare=False)
    aasIdShort: Optional[str] = field(hash=False, compare=False)
    globalAssetId: Optional[str] = field(hash=False, compare=False)
    assetType: Optional[str] = field(hash=False, compare=False)
    assetKind: Optional[str] = field(hash=False, compare=False)
    submodels: list[InstanceSubmodelDescriptor]
    parameters: list[MDTParameterDescriptor]
    operations: list[MDTOperationDescriptor]
    

@dataclass_json
@dataclass(frozen=True, unsafe_hash=True, slots=True)
class InstanceRuntimeInfo:
    """
    A class to represent the runtime information of an MDT instance.
    
    Attributes:
    ----------
    status : str
        The status of the MDT instance.
        The status can be one of the following values:
        - STOPPED
        - STARTING
        - RUNNING
        - STOPPING
        - FAILED
    baseEndpoint : Optional[str]
        The base endpoint URL for the MDT instance.
    """
    status: str = field(hash=False, compare=False)
    baseEndpoint: Optional[str] = None

@dataclass_json
@dataclass(frozen=True, unsafe_hash=True, slots=True)
class StatusResult:
    """
    A class to represent the status result of an MDT instance.

    Attributes:
    ----------
    id : str
        The unique identifier of the status result.
    status : MDTInstanceStatus
        The status of the MDT instance.
        The status can be one of the following values:
        - MDTInstanceStatus.STOPPED
        - MDTInstanceStatus.STARTING
        - MDTInstanceStatus.RUNNING
        - MDTInstanceStatus.STOPPING
        - MDTInstanceStatus.FAILED
    service_endpoint : str
        The service endpoint associated with the MDT instance.
    """
    id: str
    status: MDTInstanceStatus = field(hash=False, compare=False)
    service_endpoint: str = field(hash=False, compare=False)


class MDTInstanceManager(ABC):
    """
    A class for managing MDT instances in MDT Framework.
    
    Properties:
        instances (MDTInstanceCollection): Collection of MDT instances.
    Methods:
        getAssetAdministrationShellRegistry() -> AssetAdministrationShellRegistry:
            Method to get the Asset Administration Shell Registry.
        getSubmodelRegistry() -> SubmodelRegistry:
            Method to get the Submodel Registry.
        getAssetAdministrationShellService(aasId: str) -> AssetAdministrationShellService:
            Method to get the Asset Administration Shell Service for a given AAS ID.
        getSubmodelService(submodelId: str) -> SubmodelService:
            Method to get the Submodel Service for a given Submodel ID.
    """
    @property
    @abstractmethod
    def instances(self) -> MDTInstanceCollection: pass
    
    @abstractmethod
    def getAssetAdministrationShellRegistry(self) -> AssetAdministrationShellRegistry: pass
    @abstractmethod
    def getSubmodelRegistry(self) -> SubmodelRegistry: pass
    
    @abstractmethod
    def getAssetAdministrationShellService(self, aasId:str) -> AssetAdministrationShellService: pass
    @abstractmethod
    def getSubmodelService(self, submodelId:str) -> SubmodelService: pass
    

class MDTInstanceCollection(ABC):
    """
    Class for managing MDTInstance objects in the MDT Framework.
    
    Methods:
    --------
    __iter__() -> Iterator[MDTInstance]
        Return an iterator over MDTInstances.
    __contains__(key: str) -> bool
        Check if an MDTInstance exists in the collection.
    __getitem__(id: str) -> MDTInstance
        Get an MDTInstance by its id.
    __delitem__(id: str) -> None
        Delete an MDTInstance from the collection by its id.
    find(**kwargs) -> list[MDTInstance]
        Find MDTInstance based on given criteria.
    add(id: str, port: int, inst_dir: str) -> MDTInstance
        Add a new MDTInstance to the collection.
    __delitem__(id: str) -> None
        Delete an MDTInstance from the collection by its id.
    remove(id: str) -> None
        Remove an MDTInstance from the collection by its ID.
    remove_all() -> None
        Remove all MDTInstances from the collection.
    """
    @abstractmethod
    def __iter__(self) -> Iterator[MDTInstance]: pass
    
    @abstractmethod
    def __contains__(self, key:str) -> bool: pass
    
    @abstractmethod
    def __getitem__(self, id:str) -> MDTInstance: pass
    
    @abstractmethod
    def __delitem__(self, key:str) -> None: pass
    
    @abstractmethod
    def find(self, **kwargs) -> list[MDTInstance]: pass
    
    @abstractmethod
    def add(self, id:str, port:int, inst_dir:str) -> MDTInstance: pass
    
    def __delitem__(self, id:str) -> None:
        self.remove(id)
        
    @abstractmethod
    def remove(self, id:str) -> None: pass
    
    @abstractmethod
    def remove_all(self) -> None: pass


class SubmodelServiceCollection(ABC):
    @abstractmethod
    def __iter__(self) -> Iterator[SubmodelService]: pass
    
    @abstractmethod
    def __bool__(self) -> bool: pass
    
    @abstractmethod
    def __len__(self) -> int: pass
          
    @abstractmethod
    def __getitem__(self, key:str) -> SubmodelService: pass
        
    def __setitem__(self, key:str, value:SubmodelService) -> None:
        raise NotImplementedError('SubmodelServiceCollection does not support set operation')
    
    def __delitem__(self, key:str) -> None:
        raise NotImplementedError('SubmodelServiceCollection does not support delete operation')
    
    @abstractmethod
    def find(self, **kwargs) -> Generator[SubmodelService, None, None]: pass
        

class FilteredSubmodelServiceCollection(SubmodelServiceCollection):
    def __init__(self, base_collection:SubmodelServiceCollection, filter:Callable[[SubmodelService], bool]) -> None:
        super().__init__()
        self.base_collection = base_collection
        self.filter = filter

    def __iter__(self) -> Iterator[SubmodelService]:
        return (sm for sm in self.base_collection if self.filter(sm))
    
    def __bool__(self) -> bool:
        return any(sm for sm in self.base_collection if self.filter(sm))
    
    def __len__(self) -> int:
        return len([sm for sm in self.base_collection if self.filter(sm)])
          
    def __getitem__(self, key:str) -> SubmodelService:
        found = self.base_collection[key]
        if self.filter(found):
            return found
        else:
            raise ResourceNotFoundError.create("Submodel", f'idShort={key}')
        
    def __setitem__(self, key:str, value:SubmodelService) -> None:
        raise NotImplementedError('SubmodelCollection does not support set operation')
    
    def __delitem__(self, key:str) -> None:
        raise NotImplementedError('SubmodelCollection does not support delete operation')
    
    def find(self, **kwargs) -> Generator[SubmodelService, None, None]:
        return (sm for sm in self.base_collection.find(kwargs) if self.filter(sm))    
            
def is_operation_submodel(sm: SubmodelService) -> bool:
    return sm.semanticId == MDT_SEMANTIC_ID.AI or sm.semanticId == MDT_SEMANTIC_ID.SIMULATION
            
class OperationSubmodelServiceCollection(FilteredSubmodelServiceCollection):
    def __init__(self, sm_coll:SubmodelServiceCollection) -> None:
        super().__init__(sm_coll, filter=lambda svc: is_operation_submodel(svc))


class MDTInstance(ABC):
    """
    Class representing an MDTInstance.
    
    Properties:
        id (str): Unique identifier for the MDT instance.
        aasId (str): Asset Administration Shell (AAS) identifier.
        aasIdShort (str): Short identifier for the AAS.
        status (MDTInstanceStatus): Current status of the MDT instance.
        serviceEndpoint (Optional[str]): Service endpoint for the MDT instance.
        shell (AssetAdministrationShellService): Asset Administration Shell service for the MDT instance.
        submodels (SubmodelServiceCollection): Collection of submodels for the MDT instance.
        parameters (ElementReferenceCollection): Collection of parameters for the MDT instance.
        operations (SubmodelServiceCollection): Collection of operations for the MDT instance.
        
    Methods:
        start() -> StatusResult:
            Starts the MDT instance.
        stop() -> StatusResult:
            Stops the MDT instance.
        getAssetAdministrationShellService() -> AssetAdministrationShellService:
            Retrieves the Asset Administration Shell service for the MDT instance.
    """
    @property
    @abstractmethod
    def id(self) -> str: pass
    @property
    @abstractmethod
    def aasId(self) -> str: pass
    @property
    @abstractmethod
    def aasIdShort(self) -> str: pass
    
    @property
    @abstractmethod
    def status(self) -> MDTInstanceStatus: pass
    @property
    @abstractmethod
    def serviceEndpoint(self) -> Optional[str]: pass
    
    @abstractmethod
    def start(self) -> StatusResult: pass
    @abstractmethod
    def stop(self) -> StatusResult: pass
    
    @property
    @abstractmethod
    def parameters(self) -> ElementReferenceCollection: pass
    
    @property
    @abstractmethod
    def operations(self) -> SubmodelServiceCollection: pass
    
    @property
    @abstractmethod
    def shell(self) -> AssetAdministrationShellService: pass
    @property
    @abstractmethod
    def submodels(self) -> SubmodelServiceCollection: pass
        
        
class DataService(SubmodelService):
    """
    Class for handling a MDT Data Submodel.
    This class inherits from SubmodelService.
    
    Properties:
        asset_type (str): A string representing the type of asset.
            The asset_type is one of followings:
            - "Equipment"
            - "Operation"
        parameters (ElementReferenceCollection): A collection of element references
            that is defined by the parameters for the data service.
    """
    @property
    @abstractmethod
    def asset_type(self) -> str: pass
    
    @property
    @abstractmethod
    def parameters(self) -> ElementReferenceCollection: pass

class OperationService(SubmodelService):
    """
    Class for operation Submodel service.
    An operation service should be either an AIService or a SimulationService.
    This class inherits from SubmodelService.
    
    Properties:
        inputs (ElementReferenceCollection): a collection of input ElementReference.
        outputs (ElementReferenceCollection): a collection of output ElementReference.
    Methods:
        __call__(*args, **kwargs): An operation method.
    """
    @property
    @abstractmethod
    def inputs(self) -> ElementReferenceCollection: pass
    
    @property
    @abstractmethod
    def outputs(self) -> ElementReferenceCollection: pass
    
    @abstractmethod
    def __call__(self, *args, **kwargs): pass
    
    def __repr__(self):
        in_param_id_list_str = ", ".join(id for id, _ in self.inputs)
        out_param_id_list_str = ", ".join(id for id, _ in self.outputs)
        return f"{self.idShort}({in_param_id_list_str}) -> {out_param_id_list_str}"
    
class AIService(OperationService): pass
class SimulationService(OperationService): pass


@dataclass_json
@dataclass(kw_only=True)
class ComponentItem:
    """
    A class to represent a component item.
    Attributes:
    ----------
    ID : str
        The identifier of the component item.
    Reference : str
        The reference of the component item.
    Description : str
        The description of the component item.
    Methods:
    -------
    from_element(cls, smc: SubmodelElementCollection) -> ComponentItem:
        Creates a ComponentItem instance from a SubmodelElementCollection.
    """
    ID: str
    Reference: str
    Description: str
    
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> ComponentItem:
        fields = { prop.idShort:prop.value for prop in smc.value }
        return ComponentItem.from_dict(fields)

@dataclass_json
@dataclass(kw_only=True)
class CompositionDependency:
    """
    Represents a dependency between two components in a twin composition
    
    Attributes:
        SourceId (str): The identifier of the source component.
        TargetId (str): The identifier of the target component.
        DependencyType (str): The type of dependency between the source and target components.
        Description (str): A description of the dependency.
        
    Methods:
        from_element(cls, smc: SubmodelElementCollection) -> CompositionDependency:
            Creates an instance of CompositionDependency from a SubmodelElementCollection.
    """
    SourceId: str
    TargetId: str
    DependencyType: str
    Description: str
    
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> CompositionDependency:
        fields = { prop.idShort:prop.value for prop in smc.value }
        return CompositionDependency.from_dict(fields)

@dataclass_json
@dataclass(kw_only=True)
class TwinComposition:
    """
    A class to represent the composition of a twin.
    
    Attributes:
    -----------
    CompositionID : str
        The unique identifier for the composition.
    CompositionType : str
        The type of the composition.
    CompositionCreator : str
        The creator of the composition.
    CompositionDescription : str
        A description of the composition.
    ComponentItems : list[ComponentItem]
        A list of component items in the composition.
    CompositionDependencies : list[CompositionDependency]
        A list of dependencies for the composition.
        
    Methods:
    --------
    from_element(cls, smc: SubmodelElementCollection) -> CompositionDependency:
        Class method to create a TwinComposition instance from a SubmodelElementCollection object.
    """
    CompositionID: str
    CompositionType: str
    CompositionCreator: str
    CompositionDescription: str
    ComponentItems: list[ComponentItem]
    CompositionDependencies: list[CompositionDependency]
    
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> CompositionDependency:
        fields = { prop.idShort:prop.value for prop in smc.value }
        if 'ComponentItems' in fields:
            fields['ComponentItems'] = [ComponentItem.from_element(smc) for smc in fields['ComponentItems']]
        if 'CompositionDependencies' in fields:
            fields['CompositionDependencies'] = [CompositionDependency.from_element(smc) for smc in fields['CompositionDependencies']]
            
        return TwinComposition.from_dict(fields)

class InformationModelService(SubmodelService):
    @property
    @abstractmethod
    def twinComposition(self) -> TwinComposition: pass