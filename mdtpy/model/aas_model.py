from typing import Optional, Any, TypeVar, cast, Protocol, runtime_checkable

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from enum import Enum, auto

from datetime import timedelta
import json
from .datatype_def_xsd import from_xsd_to_python, from_python_to_xsd
        

class DataTypeDefXsd(Enum):
    ANY_URI = ("xs:anyURI")
    BASE64BINARY = ("xs:base64Binary")
    BOOLEAN = ("xs:boolean")
    BYTE = ("xs:byte")
    DATE = ("xs:date")
    DATE_TIME = ("xs:dateTime")
    DECIMAL = ("xs:decimal")
    DOUBLE = ("xs:double")
    DURATION = ("xs:duration")
    GDAY = ("xs:gDay")
    GMONTH = ("xs:gMonth")
    GMONTH_DAY = ("xs:gMonthDay")
    GYEAR = ("xs:gYear")
    GYEAR_MONTH = ("xs:gYearMonth")
    FLOAT = ("xs:float")
    HEX_BINARY = ("xs:hexBinary")
    INT = ("xs:int")
    INTEGER = ("xs:integer")
    LONG = ("xs:long")
    NEGATIVE_INTEGER = ("xs:negativeInteger")
    NON_NEGATIVE_INTEGER = ("xs:nonNegativeInteger")
    NON_POSITIVE_INTEGER = ("xs:nonPositiveInteger")
    POSITIVE_INTEGER = ("xs:positiveInteger")
    SHORT = ("xs:short")
    STRING = ("xs:string")
    TIME = ("xs:time")
    UNSIGNED_BYTE = ("xs:unsignedByte")
    UNSIGNED_INT = ("xs:unsignedInt")
    UNSIGNED_LONG = ("xs:unsignedLong")
    UNSIGNED_SHORT = ("xs:unsignedShort")
    
    @staticmethod
    def from_name(name:str) -> 'DataTypeDefXsd':
        try:
            return DataTypeDefXsd(name)
        except Exception:
            return DataTypeDefXsd[name]
    

class KeyTypes(Enum):
    ANNOTATED_RELATIONSHIP_ELEMENT = "AnnotatedRelationshipElement"
    ASSET_ADMINISTRATION_SHELL = "AssetAdministrationShell"
    BASIC_EVENT_ELEMENT = "BasicEventElement"
    BLOB = "Blob"
    CAPABILITY = "Capability"
    CONCEPT_DESCRIPTION = "ConceptDescription"
    DATA_ELEMENT = "DataElement"
    ENTITY = "Entity"
    EVENT_ELEMENT = "EventElement"
    FILE = "File"
    FRAGMENT_REFERENCE = "FragmentReference"
    GLOBAL_REFERENCE = "GlobalReference"
    IDENTIFIABLE = "Identifiable"
    MULTI_LANGUAGE_PROPERTY = "MultiLanguageProperty"
    OPERATION = "Operation"
    PROPERTY = "Property"
    RANGE = "Range"
    REFERABLE = "Referable"
    REFERENCE_ELEMENT = "ReferenceElement"
    RELATIONSHIP_ELEMENT = "RelationshipElement"
    SUBMODEL = "Submodel"
    SUBMODEL_ELEMENT = "SubmodelElement"
    SUBMODEL_ELEMENT_COLLECTION = "SubmodelElementCollection"
    SUBMODEL_ELEMENT_LIST = "SubmodelElementList"

@dataclass_json
@dataclass(slots=True)
class Key:
    type: KeyTypes
    value: str
    
class ReferenceTypes(Enum):
    EXTERNAL_REFERENCE = "ExternalReference"
    MODEL_REFERENCE = "ModelReference"

@dataclass_json
@dataclass(slots=True)
class Reference:
    type: ReferenceTypes
    keys: list[Key]
    referredSemanticId: Optional['Reference'] = field(default=None)

@dataclass_json
@dataclass(slots=True)
class AdministrativeInformation:
    version: Optional[str] = field(default=None)
    revision: Optional[str] = field(default=None)
    creator: Optional[Reference] = field(default=None)
    templateId: Optional[str] = field(default=None)
    
class AssetKind(Enum):
    INSTANCE = "Instance"
    NOT_APPLICABLE = "NotApplicable"
    TYPE = "Type"
    
class SecurityTypeEnum(Enum):
    NONE = auto()
    RFC_TLSA = auto()
    W3C_DID = auto()

@dataclass(slots=True)
class SecurityAttributeObject:
    type: SecurityTypeEnum
    key: str
    value: str

@dataclass(kw_only=True, slots=True)
class SpecificAssetId:
    name: str
    value: str
    externalSubjectId: Reference
    semanticId: Optional[Reference]
    supplementalSemanticIds: list[Reference] = field(default_factory=list)
    
@dataclass(slots=True)
class ProtocolInformation:
    href: str
    endpointProtocol: Optional[str] = field(default=None)
    endpointProtocolVersion: Optional[str] = field(default=None)
    subprotocol: Optional[str] = field(default=None)
    subprotocolBody: Optional[str] = field(default=None)
    subprotocolBody_encoding: Optional[str] = field(default=None)
    securityAttributes: list[SecurityAttributeObject] = field(default_factory=list)

@dataclass_json
@dataclass(slots=True)
class Endpoint:
    interface: str
    protocolInformation: ProtocolInformation
    
@dataclass(slots=True)
class DataSpecificationContent: pass

@dataclass_json
@dataclass(slots=True)
class EmbeddedDataSpecification:
    dataSpecification: Reference
    dataSpecificationContent: DataSpecificationContent
    
class QualifierKind(Enum):
    ConceptQualifier = auto()
    TEMPLATE_QUALIFIER = auto()
    VALUE_QUALIFIER = auto()


class HasSemantics(ABC):
    @property
    @abstractmethod
    def semanticId(self) -> Optional[Reference]: pass
    
    @property
    @abstractmethod
    def supplementalSemanticIds(self) -> list[Reference]: pass


@dataclass_json
@dataclass
class Extension(HasSemantics):
    name: str
    valueType: Optional[str] = field(default=None)
    value: Optional[str] = field(default=None)
    refersTo: Optional[Reference] = field(default=None)
    
class HasExtensions(ABC):
    @property
    @abstractmethod
    def extensions(self) -> list[Extension]: pass

@dataclass_json
@dataclass(slots=True)
class AbstractLangString(HasExtensions):
    language: Optional[str] = field(default=None)
    text: Optional[str] = field(default=None)
    extensions: list[Extension] = field(default_factory=list)
    
    def to_json_obj(self) -> dict[str,Any]:
        json_obj = dict()
        if self.language: json_obj['language'] = self.language
        if self.text: json_obj['text'] = self.text
        if self.extensions: json_obj['extensions'] = [e.to_dict() for e in self.extensions]
        return json_obj
    
    def __repr__(self) -> str:
        return f"{self.language}:{self.text}"

class LangStringNameType(AbstractLangString): pass
class LangStringTextType(AbstractLangString): pass


class Referable(HasExtensions,ABC):
    @property
    @abstractmethod
    def category(self) -> Optional[str]: pass
    
    @property
    @abstractmethod
    def idShort(self) -> Optional[str]: pass
    
    @property
    @abstractmethod
    def displayName(self) -> list[LangStringNameType] : pass
    
    @property
    @abstractmethod
    def description(self) -> list[LangStringTextType] : pass
    

class Identifiable(Referable, ABC):
    @property
    @abstractmethod
    def id(self) -> str: pass
    
    @property
    @abstractmethod
    def administration(self) -> Optional[AdministrativeInformation]: pass
    
class ModellingKind(Enum):
    INSTANCE = "Instance"
    TEMPLATE = "Template"

@dataclass(kw_only=True, slots=True)
class HasKind:
    kind: Optional[ModellingKind]


class HasDataSpecification(ABC):
    @property
    @abstractmethod
    def embeddedDataSpecifications(self) -> list[EmbeddedDataSpecification]: pass


@dataclass_json
@dataclass(kw_only=True, slots=True)
class Qualifier(HasSemantics):
    semanticId: Optional[Reference] = field(default=None)
    supplementalSemanticIds: list[Reference] = field(default_factory=list)
    kind: Optional[str] = field(default=None)
    type: Optional[str] = field(default=None)
    valueType: str
    value: Optional[str] = field(default=None)
    valueId: Optional[Reference] = field(default=None)
    embeddedDataSpecification: list[EmbeddedDataSpecification] = field(default_factory=list)

class Qualifiable(ABC):
    @property
    @abstractmethod
    def qualifiers(self) -> list[Qualifier]: pass
    
    
@dataclass_json
@dataclass(kw_only=True, slots=True)
class AssetInformation:
    assetKind: AssetKind
    globalAssetId: Optional[str] = field(default=None)
    specificAssetId: Optional[SpecificAssetId] = field(default=None)
    
@dataclass_json
@dataclass(kw_only=True, slots=True)
class Resource:
    path: str
    contentType: Optional[str] = field(default=None)
    

class AssetAdministrationShell(Identifiable, HasDataSpecification):
    __slots__ = ('fields')
    
    def __init__(self, fields:dict[str,Any]) -> None:
        self.fields = fields
    
    @property
    def id(self) -> str:
        return self.fields['id']
        
    @property
    def administration(self) -> Optional[AdministrativeInformation]:
        return self.fields.get('administration')
    
    @property
    def idShort(self) -> Optional[str]:
        return self.fields.get('idShort')
        
    @property
    def category(self) -> Optional[str]:
        return self.fields.get('category')
    
    @property
    def displayName(self) -> list[LangStringNameType]:
        return self.fields['displayName']
    
    @property
    def description(self) -> list[LangStringTextType]:
        return self.fields['description']
    
    @property
    def assetInformation(self) -> AssetInformation:
        return self.fields['assetInformation']
        
    @property
    def extensions(self) -> list[Extension]:
        return self.fields['extensions']
        
    @property
    def embeddedDataSpecifications(self) -> list[EmbeddedDataSpecification]:
        return self.fields['embeddedDataSpecifications']
        
    @property
    def derivedFrom(self) -> Optional[Reference]:
        return self.fields.get('derivedFrom')
    
    @property
    def submodels(self) -> list[Reference]:
        return self.fields['submodels']


class Submodel(Identifiable, HasDataSpecification, HasSemantics, Qualifiable, HasKind):
    __slots__ = ('fields')
    
    def __init__(self, fields:dict[str,Any]) -> None:
        self.fields = fields
    
    @property
    def id(self) -> str:
        return self.fields['id']
        
    @property
    def administration(self) -> Optional[AdministrativeInformation]:
        return self.fields.get('administration')
    
    @property
    def idShort(self) -> Optional[str]:
        return self.fields.get('idShort')
        
    @property
    def category(self) -> Optional[str]:
        return self.fields.get('category')
    
    @property
    def displayName(self) -> list[LangStringNameType]:
        return self.fields['displayName']
    
    @property
    def description(self) -> list[LangStringTextType]:
        return self.fields['description']
    
    @property
    def kind(self) -> Optional[ModellingKind]:
        return self.fields.get('kind')
    
    @property
    def semanticId(self) -> Optional[Reference]:
        return self.fields.get('semanticId')
    
    @property
    def supplementalSemanticIds(self) -> list[Reference]:
        return self.fields['supplementalSemanticIds']
        
    @property
    def qualifiers(self) -> list[Qualifier]:
        return self.fields['qualifiers']
        
    @property
    def extensions(self) -> list[Extension]:
        return self.fields['extensions']
        
    @property
    def embeddedDataSpecifications(self) -> list[EmbeddedDataSpecification]:
        return self.fields['embeddedDataSpecifications']
        
    @property
    def submodelElements(self) -> list['SubmodelElement']:
        return self.fields['submodelElements']
    
    def __repr__(self) -> str:
        idShortStr = f", idShort={self.idShort}" if self.idShort else ""
        kindStr = f", kind={self.kind}" if self.kind else ""
        submodelElementIds = ','.join([sme.idShort for sme in self.submodelElements if sme.idShort])
        return f"Submodel[id={self.id}{idShortStr}{kindStr}, elements={submodelElementIds}]"
    
    
class AasSubmodelElements(Enum):
    ANNOTATED_RELATIONSHIP_ELEMENT = "AnnotatedRelationshipElement"
    BASIC_EVENT_ELEMENT = "BasicEventElement"
    BLOB = "Blob"
    CAPABILITY = "Capability"
    DATA_ELEMENT = "DataElement"
    ENTITY = "Entity"
    EVENT_ELEMENT = "EventElement"
    FILE = "File"
    MULTI_LANGUAGE_PROPERTY = "MultiLanguageProperty"
    OPERATION = "Operation"
    PROPERTY = "Property"
    RANGE = "Range"
    REFERENCE_ELEMENT = "ReferenceElement"
    RELATIONSHIP_ELEMENT = "RelationshipElement"
    SUBMODEL_ELEMENT = "SubmodelElement"
    SUBMODEL_ELEMENT_COLLECTION = "SubmodelElementCollection"
    SUBMODEL_ELEMENT_LIST = "SubmodelElementList"


class SubmodelElement(Referable, HasSemantics, Qualifiable, HasDataSpecification):
    __slots__ = ('fields')
    
    def __init__(self, fields:dict[str,Any]) -> None:
        self.fields = fields
    
    @property
    def idShort(self) -> Optional[str]:
        return self.fields.get('idShort')
    
    @property
    def modelType(self) -> str:
        return str(self.fields.get('modelType'))
    
    @property
    def category(self) -> Optional[str]:
        return self.fields.get('category')
    
    @property
    def displayName(self) -> list[LangStringNameType]:
        return self.fields['displayName']
    
    @property
    def description(self) -> list[LangStringTextType]:
        return self.fields.get('description', [])
    
    @description.setter
    def description(self, value:Optional[str]):
        if value:
            self.fields['description'] = value
        else:
            self.fields.pop('description')
    
    @property
    def semanticId(self) -> Optional[Reference]:
        return self.fields.get('semanticId')
    
    @property
    def supplementalSemanticIds(self) -> list[Reference]:
        objs = self.fields.get('supplementalSemanticIds')
        return objs if objs else []
        
    @property
    def qualifiers(self) -> list[Qualifier]:
        objs = self.fields.get('qualifiers')
        return objs if objs else []
        
    @property
    def extensions(self) -> list[Extension]:
        objs = self.fields.get('extensions')
        return objs if objs else []

    @property
    def embeddedDataSpecifications(self) -> list[EmbeddedDataSpecification]:
        objs = self.fields.get('embeddedDataSpecification')
        return objs if objs else []

    @property
    @abstractmethod
    def value(self) -> Any:
        pass
    
    @abstractmethod
    def read_value(self) -> Any:
        """Read the value of this submodel element.
        
        Returns:
            Any: The value of this submodel element.
        """
        pass
    
    @abstractmethod
    def update_value(self, value:Any) -> None:
        pass
    
    def to_json_obj(self, modelType:Optional[str]=None) -> dict[str,Any]:
        json_obj = dict()
        json_obj['modelType'] = modelType if modelType else self.__class__.__name__.split('.')[-1]
        if self.idShort:
            json_obj['idShort'] = self.idShort
        if self.category:
            json_obj['category'] = self.category
        if self.displayName:
            json_obj['displayName'] = [n.to_json_obj() for n in self.displayName]
        if self.description:
            json_obj['description'] = [n.to_json_obj() for n in self.description]
        if self.semanticId:
            json_obj['semanticId'] = self.semanticId.to_dict()
        if self.supplementalSemanticIds:
            json_obj['supplementalSemanticIds'] = [n.to_dict() for n in self.supplementalSemanticIds]
        if self.qualifiers:
            json_obj['qualifiers'] = [n.to_dict() for n in self.qualifiers]
        if self.extensions:
            json_obj['extensions'] = [n.to_dict() for n in self.extensions]
        if self.embeddedDataSpecifications:
            json_obj['embeddedDataSpecifications'] = [n.to_dict() for n in self.embeddedDataSpecifications]
        return json_obj
    
    
SubmodelElementT = TypeVar("SubmodelElementT", bound=SubmodelElement)

@runtime_checkable
class ValueOnlySerializable(Protocol):
    def serializeValue(self) -> dict[str,Any]: ...


class Property(SubmodelElement):
    def __init__(self, fields:dict[str,Any]) -> None:
        super().__init__(fields)
        
    @property
    def valueType(self) -> str:
        return self.fields['valueType']
    
    @property
    def value(self) -> Optional[str]:
        return self.fields['value']
    
    @value.setter
    def value(self, value:Optional[str]):
        self.fields['value'] = value
    
    @property
    def valueId(self) -> Optional[Reference]:
        return self.fields.get('valueId')
    
    def read_value(self) -> Any:
        return from_xsd_to_python(self.valueType, self.value)
        
    def update_value(self, value:Optional[Any]) -> None:
        self.value = from_python_to_xsd(self.valueType, value)

    def to_json_obj(self) -> dict[str,Any]:
        json_obj = super().to_json_obj()
        json_obj['modelType'] = 'Property'
        json_obj['valueType'] = self.valueType
        if self.value: json_obj['value'] = self.value
        if self.valueId: json_obj['valueId'] = self.valueId.to_dict()
        return json_obj
        
    def serializeValue(self) -> dict[str,Any]:
        assert self.idShort
        return {self.idShort: self.value}
    
    def __repr__(self) -> str:
        return f"Property(idShort={self.idShort}, type={self.valueType}, value={self.value})"
    
class File(SubmodelElement):
    def __init__(self, fields:dict[str,Any]) -> None:
        super().__init__(fields)
        
    @property
    def value(self) -> str:
        return self.fields['value']
    
    @property
    def contentType(self) -> str:
        return self.fields['contentType']
    
    def read_value(self) -> dict[str,str]:
        return {'contentType': self.contentType, 'value': self.value}
        
    def update_value(self, value:dict[str,str]) -> None:
        self.value = value['value']
        self.contentType = value['contentType']

    def to_json_obj(self) -> dict[str,Any]:
        json_obj = super().to_json_obj()
        json_obj['contentType'] = self.contentType
        if self.value: json_obj['value'] = self.value
        return json_obj
        
    def serializeValue(self) -> dict[str,Any]:
        assert self.idShort
        return {'contentType': self.contentType, 'value': self.value}
    
    def __repr__(self) -> str:
        return f"File(idShort={self.idShort}, value={self.value} ({self.value}))"
    
    
class Range(SubmodelElement):
    def __init__(self, fields:dict[str,str]) -> None:
        super().__init__(fields)
        
    @property
    def min(self) -> str:
        return self.fields['min']
        
    @property
    def max(self) -> str:
        return self.fields['max']
    
    def read_value(self) -> dict[str,str]:
        return {'min': self.min, 'max': self.max}
        
    def update_value(self, value:dict[str,str]) -> None:
        self.min = value['min']
        self.max = value['max']
    
    def to_json_obj(self) -> dict[str,Any]:
        json_obj = super().to_json_obj()
        if self.min: json_obj['min'] = self.min
        if self.max: json_obj['max'] = self.max
        return json_obj
        
    def serializeValue(self) -> dict[str,str]:
        assert self.idShort
        
        serialized:dict[str,str] = dict()
        if self.min: serialized['min'] = self.min
        if self.max: serialized['max'] = self.max
        return serialized
    
    def __repr__(self) -> str:
        min_str = f', min={self.min}' if self.min else ''
        max_str = f', max={self.max}' if self.max else ''
        return f"Range(idShort={self.idShort}{min_str}{max_str})"
    

class SubmodelElementCollection(SubmodelElement):
    def __init__(self, fields:dict[str,Any]) -> None:
        super().__init__(fields)
        self._fields = { sme.idShort: sme for sme in fields['value'] }
    
    @property
    def value(self) -> list[SubmodelElement]:
        return self.fields['value']
    
    def __getitem__(self, key:str) -> SubmodelElement:
        return self._fields[key]
    
    def get(self, id_short:str, cls:type[SubmodelElementT]=SubmodelElement) -> Optional[SubmodelElementT]:
        for sme in self.fields['value']:
            if sme.idShort == id_short:
                return cast(cls, sme)
            
    def read_value(self) -> dict[str | None, Any]:
        return { field.idShort: field.read_value() for field in self.value }
    
    def update_value(self, value:dict[str,Any]) -> None:
        for field in self.value:
            if field.idShort in value:
                field.update_value(value[field.idShort])
        
    def serializeValue(self) -> dict[str,Any]:
        serialized:dict[str,Any] = dict()
        for sme in self.value:
            if isinstance(sme, ValueOnlySerializable):
                serialized = serialized | sme.serializeValue()
        return serialized
    
    def to_json_obj(self) -> dict[str,Any]:
        json_obj = super().to_json_obj()
        json_obj['value'] = [sme.to_json_obj() for sme in self.value]
        return json_obj
    

class SubmodelElementList(SubmodelElement):
    def __init__(self, fields:dict[str,Any]) -> None:
        super().__init__(fields)
        
    @property
    def orderRelevant(self) -> Optional[bool]:
        return self.fields.get('orderRelevant')
    
    @property
    def semanticIdListElement(self) -> list[Reference]:
        return self.fields['semanticIdListElement']
                
    @property
    def typeValueListElement(self) -> list[AasSubmodelElements]:
        return self.fields['typeValueListElement']
    
    @property
    def valueTypeListElement(self) -> list[str]:
        return self.fields['valueTypeListElement']
    
    @property
    def value(self) -> list[SubmodelElement]:
        return self.fields['value']
            
    def read_value(self) -> list[Any]:
        return [ sme.read_value() for sme in self.value ]
    
    def update_value(self, value:list[Any]) -> None:
        for sme, v in zip(self.fields['value'], value):
            sme.update_value(v)

@dataclass_json
@dataclass(slots=True)
class OperationVariable:
    value: SubmodelElement
    
@dataclass_json
@dataclass(slots=True)
class OperationResult:
    outputArguments: list[OperationVariable]   
    inputOutputArguments: list[OperationVariable] 

@dataclass_json
@dataclass(slots=True)
class OperationHandle:
    handleId: str
    
@dataclass_json
@dataclass(slots=True)
class OperationRequest:
    inoutputArguments: list[OperationVariable]
    inputArguments: list[OperationVariable]
    clientTimeoutDuration: timedelta
    

class Operation(SubmodelElement):
    def __init__(self, fields:dict[str,Any]) -> None:
        super().__init__(fields)
        
    @property
    def inputVariables(self) -> list[OperationVariable]:
        return self.fields['inputVariables']
    
    @property
    def outputVariables(self) -> list[OperationVariable]:
        return self.fields['outputVariables']
    
    @property
    def inOutputVariables(self) -> list[OperationVariable]:
        return self.fields['inOutputVariables']
    

class EventElement(SubmodelElement, ABC): pass

class Direction(Enum):
    INPUT = "Input"
    OUTPUT = "Output"
    
class StateOfEvent(Enum):
    OFF = "Off"
    ON = "On"
    
class BasicEventElement(EventElement):
    def __init__(self, fields:dict[str,Any]) -> None:
        super().__init__(fields)
        
    @property
    def observed(self) -> Reference:
        return self.fields['observed']
        
    @property
    def direction(self) -> Direction:
        return self.fields['direction']
        
    @property
    def state(self) -> StateOfEvent:
        return self.fields['state']
        
    @property
    def messageTopic(self) -> Optional[str]:
        return self.fields.get('messageTopic')
        
    @property
    def messageBroker(self) -> Optional[Reference]:
        return self.fields.get('messageBroker')
        
    @property
    def lastUpdate(self) -> Optional[str]:
        return self.fields.get('lastUpdate')
        
    @property
    def minInterval(self) -> Optional[str]:
        return self.fields.get('minInterval')
        
    @property
    def maxInterval(self) -> Optional[str]:
        return self.fields.get('maxInterval')
    

class MultiLanguageProperty(SubmodelElement):
    def __init__(self, fields:dict[str,Any]) -> None:
        super().__init__(fields)
    
    @property
    def value(self) -> list[LangStringTextType]:
        return self.fields['value']
    
    @property
    def valueId(self) -> Optional[Reference]:
        return self.fields.get('valueId')
