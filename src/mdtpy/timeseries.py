from __future__ import annotations

from typing import cast, Iterator, Generator, Any, Optional
from abc import ABC, abstractmethod
from collections.abc import KeysView, ValuesView, ItemsView, Mapping
from dataclasses import dataclass

from datetime import datetime
import pandas as pd

from basyx.aas import model

from .value import CollectionValueType, MultiLanguagePropertyValue
from .reference import DefaultElementReference
from .descriptor import MDTSubmodelDescriptor
from .submodel import SubmodelService


@dataclass(frozen=True, unsafe_hash=True, slots=True)
class TIMESERIES_SEMANTIC_ID:
    """
    AAS TimeSeries 표준에서 사용되는 semantic_id 상수.

    Note:
        값은 IEC 63278 / IDTA TimeSeries Submodel 표준에서 정의된 URI다.
    """
    TIMESERIES = "https://admin-shell.io/idta/TimeSeries/1/1"
    METADATA = "https://admin-shell.io/idta/TimeSeries/Metadata/1/1"
    INTERNAL_SEGMENT = "https://admin-shell.io/idta/TimeSeries/Segments/InternalSegment/1/1"
    LINKED_SEGMENT = "https://admin-shell.io/idta/TimeSeries/Segments/LinkedSegment/1/1"
    EXTERNAL_SEGMENT = "https://admin-shell.io/idta/TimeSeries/Segments/ExternalSegment/1/1"
    RECORDS = "https://admin-shell.io/idta/TimeSeries/Records/1/1"
    RECORD = "https://admin-shell.io/idta/TimeSeries/Record/1/1"


class Metadata:
    """
    TimeSeries 서브모델의 Metadata 영역.

    Attributes:
        name (MultiLanguagePropertyValue): 시계열 이름 (다국어).
        description (Optional[MultiLanguagePropertyValue]): 다국어 설명.
        record (Record): 레코드 스키마(필드 정의).
    """

    def __init__(self, metadata_value: CollectionValueType) -> None:
        self.__name = cast(MultiLanguagePropertyValue, metadata_value['Name'])
        self.__description = cast(
            Optional[MultiLanguagePropertyValue], metadata_value['Description']
        )
        self.__record = Record(
            "rec0", cast(CollectionValueType, metadata_value['Record'])
        )

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
    """
    시계열 레코드 한 개. 첫 필드는 timestamp로 간주된다.

    Attributes:
        id (str): 레코드 식별자.
        timestamp (Optional[datetime]): 첫 번째 필드 값(Timestamp 컨벤션).
        fields (dict[str, Any | None]): 레코드의 모든 필드.
    """

    def __init__(self, id: str, record: CollectionValueType) -> None:
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
    def fields(self) -> dict[str, Any | None]:
        return self.__fields

    def __repr__(self) -> str:
        return f'Record(id={self.id}, fields={self.fields})'


class Records:
    """
    레코드 collection. `len()`과 iteration을 지원한다.
    """

    def __init__(self, records: CollectionValueType) -> None:
        self.__records = records

    def __len__(self) -> int:
        return len(self.__records)

    def __iter__(self) -> Generator[Record, None, None]:
        return (
            Record(id, cast(CollectionValueType, rec))
            for id, rec in self.__records.items()
        )


class Segment(ABC):
    """
    TimeSeries 세그먼트 추상 베이스.

    공통 메타데이터(이름/설명/레코드 수/시작·종료 시각/샘플링 정보 등)는 모두
    Submodel의 `Segment` SMC에서 읽어온다. 구체 타입에 따라 records 접근 방식이
    다르다 (`InternalSegment.records_as_pandas`만 데이터를 직접 제공).

    Concrete subclasses:
        - `InternalSegment`: 인라인 레코드, pandas 변환 가능
        - `LinkedSegment`: 외부 endpoint+query 참조 (조회 미구현)
        - `ExternalSegment`: 외부 File/Blob 참조 (조회 미구현)
    """

    def __init__(self, segment: CollectionValueType) -> None:
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
    def records_as_pandas(self) -> pd.DataFrame:
        """레코드를 pandas DataFrame으로 반환한다 (서브클래스가 구현)."""
        ...


class InternalSegment(Segment):
    """
    레코드를 인라인으로 가지는 세그먼트. `records_as_pandas`로 변환 가능.
    """

    def __init__(self, segment: CollectionValueType) -> None:
        super().__init__(segment)
        records = segment.get('Records')
        assert records is not None, "Records is missing in InternalSegment"
        self.__records = Records(cast(CollectionValueType, records))

    @property
    def records(self) -> Records:
        return self.__records

    def records_as_pandas(self) -> pd.DataFrame:
        """레코드를 pandas DataFrame으로 변환한다."""
        return pd.DataFrame([record.fields for record in self.__records])


class LinkedSegment(Segment):
    """
    외부 endpoint + query로 데이터에 접근하는 세그먼트.

    현재 구현은 endpoint/query 메타데이터만 보관하며 실제 조회는 지원하지 않는다.
    """

    def __init__(self, segment_value: CollectionValueType) -> None:
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
    """
    외부 File 또는 Blob 참조를 가지는 세그먼트.

    Note:
        현 구현은 생성자에서 `segment_smc.value`를 순회하므로 호출자는
        `CollectionValueType`(dict)이 아니라 basyx `SubmodelElementCollection`
        SME 자체를 넘겨야 한다. 다른 세그먼트 타입과 시그니처가 다른 점에 주의.
    """

    def __init__(self, segment_smc: CollectionValueType) -> None:
        super().__init__(segment_smc)

        for sme in segment_smc.value:  # type: ignore[union-attr]
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
    """
    이름(id_short) → `Segment` 매핑. dict-like (Mapping 인터페이스).

    각 segment는 `DefaultElementReference`의 `semantic_id`를 보고 적절한
    `Segment` 서브클래스로 인스턴스화된다.
    """

    def __init__(self, segs_dict: Mapping[str, DefaultElementReference]) -> None:
        def to_segment(seg_ref: DefaultElementReference) -> Segment:
            assert (semantic_id := seg_ref.semantic_id) is not None
            values = cast(CollectionValueType, seg_ref.read_value())
            match semantic_id.key[0].value:
                case TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT:
                    return InternalSegment(values)
                case TIMESERIES_SEMANTIC_ID.LINKED_SEGMENT:
                    return LinkedSegment(values)
                case TIMESERIES_SEMANTIC_ID.EXTERNAL_SEGMENT:
                    return ExternalSegment(values)
                case _:
                    raise ValueError(f"Unknown segment type: {seg_ref.id_short}")

        self.__segments = {
            str(seg_ref.id_short): to_segment(seg_ref)
            for seg_name, seg_ref in segs_dict.items()
        }

    def __len__(self) -> int:
        return len(self.__segments)

    def __iter__(self) -> Iterator[Segment]:
        return iter(self.__segments.values())

    def __getitem__(self, key: str) -> Segment:
        return self.__segments[key]

    def __contains__(self, key: str) -> bool:
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
    """
    Metadata + Segments 묶음. `TimeSeriesService.timeseries()`의 반환 타입.

    Attributes:
        metadata (Metadata): 시계열 메타데이터.
        segments (Segments): 세그먼트 collection.
    """

    def __init__(self, metadata: Metadata, segments: Segments) -> None:
        self.__metadata = metadata
        self.__segments = segments

    @property
    def metadata(self) -> Metadata:
        return self.__metadata

    @property
    def segments(self) -> Segments:
        return self.__segments


class TimeSeriesService(SubmodelService):
    """
    TimeSeries 서브모델 전용 서비스.

    `SubmodelService`를 상속하면서 `timeseries()` 메서드로 Metadata + Segments
    트리를 한 번에 읽어와 `TimeSeries` 객체로 반환한다.
    """

    def __init__(self, instance_id: str, sm_desc: MDTSubmodelDescriptor) -> None:
        super().__init__(instance_id, sm_desc)

    def timeseries(self) -> TimeSeries:
        """
        TimeSeries 서브모델의 Metadata와 모든 Segments를 읽어 객체화한다.

        - `Metadata` SMC를 한 번 읽어 `Metadata` 객체로 변환.
        - `Segments` SMC의 직속 자식만(`Segments.<name>` 깊이 2 경로) 추려서
          각 세그먼트의 semantic_id에 따라 `InternalSegment`/`LinkedSegment`/
          `ExternalSegment`로 인스턴스화.

        Returns:
            TimeSeries: Metadata + Segments 묶음.
        """
        metadata_value = self.element_reference('Metadata').read_value()
        metadata = Metadata(cast(CollectionValueType, metadata_value))

        segs_ref = cast(DefaultElementReference, self.element_reference('Segments'))
        # 직속 segment 경로(`Segments.<name>`, 깊이 2)만 골라낸다.
        path_pairs = {
            path2[1]: '.'.join(path2)
            for path2 in (path.split('.') for path in segs_ref.pathes())
            if len(path2) == 2
        }
        segs_dict: dict[str, DefaultElementReference] = {
            seg_name: cast(DefaultElementReference, self.element_reference(seg_ref_str))
            for seg_name, seg_ref_str in path_pairs.items()
        }

        segments = Segments(segs_dict)
        return TimeSeries(metadata, segments)
