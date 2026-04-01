from __future__ import annotations

from typing import cast, Iterator, Generator, Any, Optional
from abc import ABC, abstractmethod
from collections.abc import KeysView, ValuesView, ItemsView
from collections import UserDict
from dataclasses import dataclass

from datetime import datetime
from basyx.aas.model.base import Referable
from dateutil.relativedelta import relativedelta
import pandas as pd

from basyx.aas import model

import mdtpy
from .value import ElementValueType, CollectionValueType, MultiLanguagePropertyValue
from .reference import ElementReference
from . import utils


@dataclass(frozen=True, unsafe_hash=True, slots=True)
class TIMESERIES_SEMANTIC_ID:
    TIMESERIES = "https://admin-shell.io/idta/TimeSeries/1/1"
    METADATA = "https://admin-shell.io/idta/TimeSeries/Metadata/1/1"
    INTERNAL_SEGMENT = 'https://admin-shell.io/idta/TimeSeries/Segments/InternalSegment/1/1'
    LINKED_SEGMENT = 'https://admin-shell.io/idta/TimeSeries/Segments/LinkedSegment/1/1'
    EXTERNAL_SEGMENT = 'https://admin-shell.io/idta/TimeSeries/Segments/ExternalSegment/1/1'
    RECORDS = "https://admin-shell.io/idta/TimeSeries/Records/1/1"
    RECORD = "https://admin-shell.io/idta/TimeSeries/Record/1/1"


class Metadata:
  def __init__(self, metadata_value:CollectionValueType) -> None:
    self.__name = cast(MultiLanguagePropertyValue, metadata_value['Name'])
    self.__description = cast(Optional[MultiLanguagePropertyValue], metadata_value['Description'])
    self.__record = Record("rec0", cast(CollectionValueType, metadata_value['Record']))

  @property
  def name(self) -> MultiLanguagePropertyValue:
    return self.__name
  
  @property
  def description(self) -> Optional[MultiLanguagePropertyValue]:
    return self.__description
  
  @property
  def record(self) -> Record:
    return self.__record

  def __repr__(self) -> str:
    return f'Metadata(name={self.name}, fields={self.record.fields.keys()})'


class Record:
  def __init__(self, id:str, record:CollectionValueType) -> None:
    self.__id = id
    self.__fields = record

    first_field_key = next(iter(record.keys()))
    assert first_field_key is not None, f"Timestamp field is missing in record {record}"
    self.__timestamp = cast(Optional[datetime], record.get(first_field_key))

  @property
  def id(self) -> str:
    return self.__id
  
  @property
  def timestamp(self) -> Optional[datetime]:
    return self.__timestamp

  @property
  def fields(self) -> dict[str, Any|None]:
    return self.__fields
  
  def __repr__(self) -> str:
    return f'Record(id={self.id}, fields={self.fields})'


class Records:
  def __init__(self, records:CollectionValueType) -> None:
    self.__records = records
  
  def __len__(self):
    return len(self.__records)
      
  def __iter__(self) -> Generator[Record, None, None]:
    return (Record(id, cast(CollectionValueType, rec)) for id, rec in self.__records.items())


class Segment(ABC):
    def __init__(self, segment:CollectionValueType) -> None:
      self.__segment = segment

    @property
    def name(self) -> Optional[MultiLanguagePropertyValue]:
      return cast(Optional[MultiLanguagePropertyValue], self.__segment['Name'])
    
    @property
    def description(self) -> Optional[MultiLanguagePropertyValue]:
      return cast(Optional[MultiLanguagePropertyValue], self.__segment['Description'])
    
    @property
    def record_count(self) -> Optional[int]:
      return cast(Optional[int], self.__segment['RecordCount'])
    
    @property
    def start_time(self) -> Optional[datetime]:
      return cast(Optional[datetime], self.__segment['StartTime'])
    
    @property
    def end_time(self) -> Optional[datetime]:
      return cast(Optional[datetime], self.__segment['EndTime'])
    
    @property
    def duration(self) -> Optional[str]:
      return cast(Optional[str], self.__segment['Duration'])
    
    @property
    def sampling_interval(self) -> Optional[int]:
      return cast(Optional[int], self.__segment['SamplingInterval'])
    
    @property
    def sampling_rate(self) -> Optional[int]:
      return cast(Optional[int], self.__segment['SamplingRate'])
    
    @property
    def state(self) -> Optional[str]:
      return cast(Optional[str], self.__segment['State']) 
    
    @property
    def last_update(self) -> Optional[datetime]:
      return cast(Optional[datetime], self.__segment['LastUpdate'])

    @abstractmethod
    def records_as_pandas(self) -> pd.DataFrame: ...
    

class InternalSegment(Segment):
  def __init__(self, segment:CollectionValueType) -> None:
    super().__init__(segment)
    records = segment.get('Records')
    assert records is not None, f"Records is missing in InternalSegment"
    self.__records = Records(cast(CollectionValueType, records))

  @property
  def records(self) -> Records:
    return self.__records

  def records_as_pandas(self) -> pd.DataFrame:
    return pd.DataFrame([record.fields for record in self.__records])


class LinkedSegment(Segment):
  def __init__(self, segment_value:CollectionValueType) -> None:
    super().__init__(segment_value)

    endpoint = segment_value.get('Endpoint')
    assert endpoint is not None, f"Endpoint is missing in segment {segment_value}"
    self.__endpoint = cast(str, endpoint)
    query = segment_value.get('Query')
    assert query is not None, f"Query is missing in segment {segment_value}"
    self.__query = cast(str, query)

  def records_as_pandas(self) -> pd.DataFrame:
    raise NotImplementedError("LinkedSegment does not support records_as_pandas")

class ExternalSegment(Segment):
  def __init__(self, segment_smc:CollectionValueType) -> None:
    super().__init__(segment_smc)

    for sme in segment_smc.value:
      if sme.id_short == 'File':
        self.__file = cast(model.File, sme)
      elif sme.id_short == 'Blob':
        self.__blob = cast(model.Blob, sme)

  @property
  def file(self) -> model.File:
    return self.__file
  
  @property
  def blob(self) -> model.Blob:
    return self.__blob

  def records_as_pandas(self) -> pd.DataFrame:
    raise NotImplementedError("ExternalSegment does not support records_as_pandas")
        

class Segments:
    def __init__(self, segs_dict:dict[str, ElementReference]) -> None:
      def to_segment(seg_ref:ElementReference) -> Segment:
        assert (semantic_id := seg_ref.semantic_id) is not None
        values = seg_ref.read_value()
        match semantic_id.key[0].value:
          case TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT:
            return InternalSegment(values)
          case TIMESERIES_SEMANTIC_ID.LINKED_SEGMENT:
            return LinkedSegment(values)
          case TIMESERIES_SEMANTIC_ID.EXTERNAL_SEGMENT:
            return ExternalSegment(values)
          case _:
            raise ValueError(f"Unknown segment type: {seg_ref.id_short}")

      self.__segments = { str(seg_ref.id_short):to_segment(seg_ref) for seg_name, seg_ref in segs_dict.items() }
    
    def __len__(self) -> int:
        return len(self.__segments)
    
    def __iter__(self) -> Iterator[Segment]:
        return iter(self.__segments.values())
    
    def __getitem__(self, key:str) -> Segment:
        return self.__segments[key]
    
    def __contains__(self, key:str) -> bool:
        return key in self.__segments

    def keys(self) -> KeysView[str]:
        return self.__segments.keys()
    
    def values(self) -> ValuesView[Segment]:
        return self.__segments.values()
    
    def items(self) -> ItemsView[str, Segment]:
        return self.__segments.items()
    
    def __repr__(self) -> str:
        return f'Segments({self.__segments})'


class TimeSeries:
  def __init__(self, metadata:Metadata, segments:Segments) -> None:
    self.__metadata = metadata
    self.__segments = segments

  @property
  def metadata(self) -> Metadata:
    return self.__metadata
  
  @property
  def segments(self) -> Segments:
    return self.__segments


from .descriptor import MDTSubmodelDescriptor
from .submodel import SubmodelService
class TimeSeriesService(SubmodelService):
  def __init__(self, instance_id:str, sm_desc:MDTSubmodelDescriptor) -> None:
    super().__init__(instance_id, sm_desc)

  def timeseries(self) -> TimeSeries:
    def to_segment_name(path:str) -> Optional[str]:
      path_entry_list = path.split('.')
      if len(path_entry_list) == 2:
        return path_entry_list[1]
      return None

    metadata_value = self.element_reference('Metadata').read_value()
    metadata = Metadata(metadata_value)

    segs_ref = self.element_reference('Segments')
    segs_value = segs_ref.read_value()
    
    segs_dict = { path2[1]:'.'.join(path2) for path2 in ( path.split('.') for path in segs_ref.pathes() ) if len(path2) == 2}
    segs_dict = { seg_name:self.element_reference(seg_ref_str) for seg_name, seg_ref_str in segs_dict.items() }
    
    segments = Segments(segs_dict)
    return TimeSeries(metadata, segments)