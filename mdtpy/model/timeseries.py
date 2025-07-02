from __future__ import annotations

from typing import Any, Optional, Callable, cast, Generator, Iterator
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json

from .mdt import FilteredSubmodelServiceCollection, SubmodelServiceCollection, SubmodelService, ResourceNotFoundError
from .reference import ElementReferenceCollection
from .aas_model import LangStringTextType, DataTypeDefXsd, Property, SubmodelElementCollection, MultiLanguageProperty


@dataclass(frozen=True, unsafe_hash=True, slots=True)
class TIMESERIES_SEMANTIC_ID:
    TIMESERIES = "https://admin-shell.io/idta/TimeSeries/1/1"
    METADATA = "https://admin-shell.io/idta/TimeSeries/Metadata/1/1"
    INTERNAL_SEGMENT = 'https://admin-shell.io/idta/TimeSeries/Segments/InternalSegment/1/1'
    LINKED_SEGMENT = 'https://admin-shell.io/idta/TimeSeries/Segments/LinkedSegment/1/1'
    RECORDS = "https://admin-shell.io/idta/TimeSeries/Records/1/1"
    RECORD = "https://admin-shell.io/idta/TimeSeries/Record/1/1"


@dataclass(slots=True)
class Field:
    name: str
    type: DataTypeDefXsd
    
    @classmethod
    def from_element(cls, prop:Property) -> Field:
        assert prop.idShort is not None
        return Field(name=prop.idShort, type=DataTypeDefXsd.from_name(prop.valueType))


@dataclass(slots=True)
class RecordMetadata:
    fields: list[Field]
    
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> RecordMetadata:
        fields = [ Field.from_element(prop) for prop in smc.value if isinstance(prop, Property) ]
        return RecordMetadata(fields)

@dataclass(slots=True)
class FieldValue:
    field: Field
    value: Any
    
    @classmethod
    def from_element(cls, prop:Property) -> FieldValue:
        assert prop.idShort is not None
        return FieldValue(field=Field.from_element(prop), value=prop.value)


@dataclass(slots=True)
class Record:
    _values: list[FieldValue]
    
    @property
    def timestamp(self) -> datetime:
        return self._values[0].value
    
    def __len__(self):
        return len(self._values)
        
    def __iter__(self) -> Iterator[FieldValue]:
        return iter(self._values)
    
    def __getitem__(self, name:str) -> Any:
        for fv in self._values:
            if fv.field.name == name:
                return fv.value
        raise KeyError(f"Field {name} not found in record")
    
    def __contains__(self, name:str) -> bool:
        return any(fv for fv in self._values if fv.field.name == name)
    
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> Record:
        values = [ FieldValue.from_element(prop) for prop in smc.value if isinstance(prop, Property) ]
        return Record(_values=values)
    
    def __repr__(self) -> str:
        return str({fv.field.name:fv.value  for fv in self._values})


@dataclass(slots=True)
class Records:
    records: list[Record]
    
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> Records:
        records = [ Record.from_element(rec_smc) for rec_smc in smc.value if isinstance(rec_smc, SubmodelElementCollection) ]
        return Records(records=records)


class Segment(ABC):
    def __init__(self) -> None:
        self.idShort: str = ''
        self.Name: list[LangStringTextType] = []
        self.Description: list[LangStringTextType] = []
        self.RecordCount: int = 0
        self.StartTime: datetime = datetime.min
        self.EndTime: datetime = datetime.min
        self.Duration: timedelta = timedelta.min
        self.SamplingInterval: Optional[int] = None
        self.SamplingRate: Optional[int] = None
        self.State: str = ''
        self.LastUpdate: datetime = datetime.min
        
    @property
    @abstractmethod
    def records(self) -> Generator[Record, None, None]:
        pass
    
    def load_from_element(self, smc:SubmodelElementCollection) -> None:
        assert smc.idShort is not None
        self.idShort = smc.idShort
        
        for prop in smc.value:
            if isinstance(prop, Property) or isinstance(prop, MultiLanguageProperty):
                assert prop.idShort is not None
                setattr(self, prop.idShort, prop.value)
                
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> Segment:
        semantic_id = smc.semanticId.keys[0].value if smc.semanticId else None
        if semantic_id == TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT:
            segment = InternalSegment()
        elif semantic_id == TIMESERIES_SEMANTIC_ID.LINKED_SEGMENT:
            segment = LinkedSegment()
        else:
            raise ValueError(f"Unknown segment type: {smc.idShort}")
        segment.load_from_element(smc)
        return segment

class InternalSegment(Segment):
    def __init__(self) -> None:
        super().__init__()
        self._records = Records(records=[])
        
    @property
    def records(self) -> Generator[Record, None, None]:
        for record in self._records.records:
            yield record
    
    def load_from_element(self, smc:SubmodelElementCollection) -> None:
        super().load_from_element(smc)
        for records_smc in smc.value:
            if isinstance(records_smc, SubmodelElementCollection) and records_smc.idShort == 'Records':
                self._records = Records.from_element(records_smc)
                break

class LinkedSegment(Segment):
    def __init__(self) -> None:
        super().__init__()
        
    @property
    def records(self) -> Generator[Record, None, None]:
        raise NotImplementedError("LinkedSegment does not support records")
    
    def load_from_element(self, smc:SubmodelElementCollection) -> None:
        super().load_from_element(smc)
        

class Segments:
    def __init__(self) -> None:
        self._segments: list[Segment] = []
        
    def load_from_element(self, smc:SubmodelElementCollection) -> None:
        self._segments = [Segment.from_element(segment_smc)
                                for segment_smc in smc.value 
                                    if isinstance(segment_smc, SubmodelElementCollection)]
        
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> Segments:
        segments = Segments()
        segments.load_from_element(smc)
        return segments
    
    def __len__(self) -> int:
        return len(self._segments)
    
    def __iter__(self) -> Iterator[Segment]:
        return iter(self._segments)
    
    def __getitem__(self, key:str) -> Segment:
        for seg in self._segments:
            if seg.idShort == key:
                return seg
        raise KeyError(f"Segment {key} not found")

   
class Metadata:
    def __init__(self) -> None:
        self.Name: list[LangStringTextType] = []
        self.Description: list[LangStringTextType] = []
        self.RecordMetadata: RecordMetadata = RecordMetadata(fields=[])
        
    def load_from_element(self, smc:SubmodelElementCollection) -> None:
        for elm in smc.value:
            if isinstance(elm, MultiLanguageProperty):
                if elm.idShort == 'Name':
                    self.Name = elm.value
                elif elm.idShort == 'Description':
                    self.Description = elm.value
            elif isinstance(elm, SubmodelElementCollection):
                if elm.idShort == 'RecordMetadata':
                    self.RecordMetadata = RecordMetadata.from_element(elm)
        
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> Metadata:
        metadata = Metadata()
        metadata.load_from_element(smc)
        return metadata
    
    def __repr__(self) -> str:
        return f'Metadata(Name={self.Name}, Description={self.Description}, RecordMetadata={self.RecordMetadata})'


class TimeSeries:
    def __init__(self) -> None:
        self.Metadata: Metadata = Metadata()
        self.Segments: Segments = Segments()
        
    def load_from_element(self, smc:SubmodelElementCollection) -> None:
        for elm in smc.value:
            if isinstance(elm, SubmodelElementCollection):
                if elm.idShort == 'Metadata':
                    self.Metadata = Metadata.from_element(elm)
                elif elm.idShort == 'Segments':
                    self.Segments = Segments.from_element(elm)
                    
    @classmethod
    def from_element(cls, smc:SubmodelElementCollection) -> TimeSeries:
        timeseries = TimeSeries()
        timeseries.load_from_element(smc)
        return timeseries
    

class TimeSeriesService(SubmodelService):
    pass
            
    
class TimeseriesSubmodelServiceCollection(FilteredSubmodelServiceCollection):
    def __init__(self, sm_coll:SubmodelServiceCollection) -> None:
        super().__init__(sm_coll, filter=lambda svc: svc.semanticId == TIMESERIES_SEMANTIC_ID.TIMESERIES)
        
    def __getitem__(self, key:str) -> TimeSeriesService:
        found = self.base_collection[key]
        if self.filter(found):
            return cast(TimeSeriesService, found)
        else:
            raise ResourceNotFoundError.create("TimeSeriesService", f'idShort={key}')