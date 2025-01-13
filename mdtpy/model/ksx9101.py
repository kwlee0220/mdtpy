from __future__ import annotations

from typing import Optional, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .aas_model import DataTypeDefXsd, SubmodelElement, SubmodelElementList, SubmodelElementCollection, Property
from .aas_service import SubmodelService


@dataclass(slots=True)
class Equipment:
    EquipmentID: str
    EquipmentName: Optional[str] = field(default=None)
    
@dataclass(slots=True)
class EquipmentParameter:
    EquipmentID: str
    ParameterID: str
    ParameterType: DataTypeDefXsd
    ParameterName: Optional[str] = field(default=None)
    ParameterGrade: Optional[str] = field(default=None)
    ParameterUOMCode: Optional[str] = field(default=None)
    LSL: Optional[str] = field(default=None)
    USL: Optional[str] = field(default=None)
    PeriodicDataCollectionIndicator: bool = field(default=False)
    DataCollectionPeriod: Optional[str] = field(default=None)
    
    def fromAasModel(self, model:SubmodelElementCollection) -> None:
        props = {sme.idShort:sme for sme in model.value if isinstance(sme, Property) and sme.idShort}
        
        self.EquipmentID = self.get_string_value(props, 'EquipmentID')
        self.ParameterID = self.get_string_value(props, 'ParameterID')
        
        prop = props.get('ParameterType')
        self.ParameterType = DataTypeDefXsd.from_name(prop.value) if prop else DataTypeDefXsd.STRING
        
        self.ParameterName = self.get_optional_string_value(props, 'ParameterName')
        self.ParameterGrade = self.get_optional_string_value(props, 'ParameterGrade')
        self.ParameterUOMCode = self.get_optional_string_value(props, 'ParameterUOMCode')
        self.LSL = self.get_optional_string_value(props, 'LSL')
        self.USL = self.get_optional_string_value(props, 'USL')
        self.PeriodicDataCollectionIndicator = self.get_boolean_value(props, 'PeriodicDataCollectionIndicator')
        self.DataCollectionPeriod = self.get_optional_string_value(props, 'DataCollectionPeriod')
        
    def get_string_value(self, props:dict[str,Property], prop_name:str) -> str:
        prop = props.get(prop_name)
        if prop is None:
            raise ValueError(f'Property is not define: name={prop_name}')
        return str(prop.value)
        
    def get_optional_string_value(self, props:dict[str,Property], prop_name:str) -> Optional[str]:
        prop = props.get(prop_name)
        return str(prop.value) if prop else None
    
    def get_boolean_value(self, props:dict[str,Property], prop_name:str) -> bool:
        prop = props.get(prop_name)
        return bool(prop.value) if prop else False
    
@dataclass(slots=True)
class EquipmentParameterList:
    parameters: list[EquipmentParameter]
    

def as_string(sme:SubmodelElement) -> str:
    if sme and isinstance(sme, Property):
        return sme.value
    elif sme is None:
        return sme
    else:
        raise ValueError('Not Property: {sme}')
    
def as_boolean(sme:SubmodelElement, default:Optional[bool]=None) -> bool:
    if sme:
        if isinstance(sme, Property):
            if sme.valueType == 'xs:boolean':
                return bool(sme.value)
            else:
                raise ValueError(f"Not 'boolean' Property type: {sme.valueType}")
        else:
            raise ValueError(f"Not Property SubmodelElement: {sme.__class__}")
    elif default:
        return default
    else:
        raise ValueError('Empty Property')