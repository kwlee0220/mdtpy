from __future__ import annotations

from typing import Optional, Any, TypeVar
from enum import Enum

from ..model.aas_model import *


T = TypeVar("T")

def read_resource(json_obj:dict[str,Any]) -> Any:
    type =json_obj['modelType']
    if type == "Submodel":
        return read_submodel(json_obj)
    elif type == "AssetAdministrationShell":
        return read_aas(json_obj)
    else:
        return read_submodel_element(json_obj)
    
    
def read_dataclass(json_obj:dict[str,Any], data_cls:type[T]) -> T:
    return data_cls.from_dict(json_obj)
    
def read_optional_dataclass(json_obj:Optional[dict[str,Any]], data_cls:type[T]) -> Optional[T]:
    return data_cls.from_dict(json_obj) if json_obj else None

def read_dataclass_list(json_obj:Optional[dict[str,Any]], data_cls:type[T]) -> list[T]:
    if json_obj is None:
        return list()
    else:
        return [data_cls.from_dict(ref_obj) for ref_obj in json_obj]
    
def read_enum(json_obj:str, enum_type:Enum) -> Enum:
    for e in enum_type:
        if e.value == json_obj:
            return e
    return None


def read_submodel_element(json_obj:dict[str,Any]) -> SubmodelElement:
    fields = {
        'idShort': json_obj.get('idShort'),
        'category': json_obj.get('category'),
        'displayName': read_dataclass_list(json_obj.get('displayName'), LangStringNameType),
        'description': read_dataclass_list(json_obj.get('description'), LangStringTextType),
        'semanticId': read_optional_dataclass(json_obj.get('semanticId'), Reference),
        'supplementalSemanticIds': read_dataclass_list(json_obj.get('supplementalSemanticIds'), Reference),
        'qualifiers': read_dataclass_list(json_obj.get('qualifiers'), Qualifier),
        'extensions': read_dataclass_list(json_obj.get('extensions'), Extension),
        'embeddedDataSpecifications': read_dataclass_list(json_obj.get('embeddedDataSpecifications'), EmbeddedDataSpecification)
    }
    
    type = AasSubmodelElements(json_obj.pop('modelType'))
    if type == AasSubmodelElements.PROPERTY:
        fields['valueType'] = json_obj['valueType']
        fields['value']  = json_obj.get('value')
        fields['valueId']  = read_optional_dataclass(json_obj.get('valueId'), Reference)
        return Property(fields)
    elif type == AasSubmodelElements.SUBMODEL_ELEMENT_COLLECTION:
        fields['value']  = read_submodel_element_list(json_obj.get('value'))
        return SubmodelElementCollection(fields)
    elif type == AasSubmodelElements.SUBMODEL_ELEMENT_LIST:
        fields['orderRelevant'] = json_obj.get('orderRelevant', True)
        fields['semanticIdListElement']  = read_optional_dataclass(json_obj.get('semanticIdListElement'), Reference)
        # fields['typeValueListElement']  = read_dataclass_list(json_obj.get('typeValueListElement'), AasSubmodelElements)
        fields['typeValueListElement']  = read_enum(json_obj.get('typeValueListElement'), AasSubmodelElements)
        fields['valueTypeListElement']  = json_obj.get('typeValueListElement', [])
        fields['value']  = read_submodel_element_list(json_obj.get('value'))
        return SubmodelElementList(fields)
    elif type == AasSubmodelElements.FILE:
        fields['contentType'] = json_obj['contentType']
        fields['value']  = json_obj.get('value')
        return File(fields)
    elif type == AasSubmodelElements.MULTI_LANGUAGE_PROPERTY:
        fields['value']  = read_dataclass_list(json_obj.get('value'), LangStringTextType)
        fields['valueId']  = read_optional_dataclass(json_obj.get('valueId'), Reference)
        return MultiLanguageProperty(fields)
    elif type == AasSubmodelElements.OPERATION:
        fields['inputVariables']  = read_dataclass_list(json_obj.get('inputVariables'), OperationVariable)
        fields['outputVariables']  = read_dataclass_list(json_obj.get('outputVariables'), OperationVariable)
        fields['inOutputVariables']  = read_dataclass_list(json_obj.get('inOutputVariables'), OperationVariable)
        return Operation(fields)
    elif type == AasSubmodelElements.BASIC_EVENT_ELEMENT:
        fields['observed'] = read_dataclass(json_obj['observed'], Reference)
        fields['direction'] = read_dataclass(json_obj['direction'], Direction)
        fields['state'] = read_dataclass(json_obj['state'], StateOfEvent)
        fields['messageTopic'] = json_obj.get('messageTopic')
        fields['messageBroker'] = json_obj.get('messageBroker')
        fields['lastUpdate'] = json_obj.get('lastUpdate')
        fields['minInterval'] = json_obj.get('minInterval')
        fields['maxInterval'] = json_obj.get('maxInterval')
        return BasicEventElement(fields)
    else:
        raise ValueError(f"Unsupported SubmodelElement: type={type}")
   
def read_submodel_element_list(json_obj:dict[str,Any]) -> list[SubmodelElement]:
    return [read_submodel_element(sme_json) for sme_json in json_obj]
    

def read_aas(json_obj:dict[str,Any]) -> AssetAdministrationShell:
    fields = {
        'id': json_obj['id'],
        'idShort': json_obj.get('idShort'),
        'category': json_obj.get('category'),
        'displayName': read_dataclass_list(json_obj.get('displayName'), LangStringNameType),
        'description': read_dataclass_list(json_obj.get('description'), LangStringTextType),
        'administration': read_optional_dataclass(json_obj.get('administration'), AdministrativeInformation),
        'assetInformation': read_dataclass(json_obj['assetInformation'], AssetInformation),
        'derivedFrom': read_optional_dataclass(json_obj.get('derivedFrom'), Reference),
        'extensions': read_dataclass_list(json_obj.get('extensions'), Extension),
        'embeddedDataSpecification': read_dataclass_list(json_obj.get('embeddedDataSpecification'), EmbeddedDataSpecification),
        'submodels': read_dataclass_list(json_obj.get('submodels'), Reference)
    }
    return AssetAdministrationShell(fields)
    
    
def read_submodel(json_obj:dict[str,Any]) -> Submodel:
    fields = {
        'id': json_obj['id'],
        'idShort': json_obj.get('idShort'),
        'category': json_obj.get('category'),
        'displayName': read_dataclass_list(json_obj.get('displayName'), LangStringNameType),
        'description': read_dataclass_list(json_obj.get('description'), LangStringTextType),
        'administration': read_optional_dataclass(json_obj.get('administration'), AdministrativeInformation),
        'semanticId': read_optional_dataclass(json_obj.get('semanticId'), Reference),
        'supplementalSemanticIds': read_dataclass_list(json_obj.get('supplementalSemanticIds'), Reference),
        'qualifiers': read_dataclass_list(json_obj.get('qualifiers'), Qualifier),
        'extensions': read_dataclass_list(json_obj.get('extensions'), Extension),
        'embeddedDataSpecification': read_dataclass_list(json_obj.get('embeddedDataSpecification'), EmbeddedDataSpecification),
        'submodelElements': read_submodel_element_list(json_obj.get('submodelElements'))
    }
    return Submodel(fields)

        

        
