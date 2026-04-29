"""
mdtpy.timeseries 모듈의 클래스에 대한 단위 테스트.

대상:
    - TIMESERIES_SEMANTIC_ID (semantic_id 상수)
    - Metadata / Record / Records
    - Segment(추상) / InternalSegment / LinkedSegment
    - Segments (semantic_id 기반 분류)
    - TimeSeries
    - TimeSeriesService.timeseries()

`ExternalSegment`는 생성자에서 `segment_smc.value`(SubmodelElementCollection
attribute)를 접근하지만 시그니처는 `CollectionValueType`(dict)로 표시되어 있어
간단히 테스트하기 어렵다. 본 파일은 이 케이스를 건너뛴다.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from mdtpy.descriptor import (
    SEMANTIC_ID_TIME_SERIES_SUBMODEL,
    MDTSubmodelDescriptor,
)
from mdtpy.reference import DefaultElementReference
from mdtpy.timeseries import (
    InternalSegment,
    LinkedSegment,
    Metadata,
    Record,
    Records,
    Segments,
    TIMESERIES_SEMANTIC_ID,
    TimeSeries,
    TimeSeriesService,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_segment_dict(**overrides):
    """Segment 베이스 클래스가 읽는 표준 키를 채운 dict."""
    base = {
        'Name': {'en': 'Seg'},
        'Description': {'en': 'desc'},
        'RecordCount': 0,
        'StartTime': None,
        'EndTime': None,
        'Duration': None,
        'SamplingInterval': None,
        'SamplingRate': None,
        'State': None,
        'LastUpdate': None,
    }
    base.update(overrides)
    return base


def make_seg_ref(semantic_id_uri: str, value: dict, id_short: str = "Seg"):
    """semantic_id에 따라 분기되는 to_segment를 통과시키기 위한 mock reference."""
    ref = MagicMock(spec=DefaultElementReference)
    sem_id = MagicMock()
    sem_id.key = [MagicMock(value=semantic_id_uri)]
    ref.semantic_id = sem_id
    ref.read_value.return_value = value
    ref.id_short = id_short
    return ref


# --------------------------------------------------------------------------- #
# TIMESERIES_SEMANTIC_ID
# --------------------------------------------------------------------------- #

class TestSemanticIdConstants:
    def test_constants_match_idta_uris(self):
        assert TIMESERIES_SEMANTIC_ID.TIMESERIES.startswith("https://admin-shell.io/")
        assert "InternalSegment" in TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT
        assert "LinkedSegment" in TIMESERIES_SEMANTIC_ID.LINKED_SEGMENT
        assert "ExternalSegment" in TIMESERIES_SEMANTIC_ID.EXTERNAL_SEGMENT


# --------------------------------------------------------------------------- #
# Record / Records
# --------------------------------------------------------------------------- #

class TestRecord:
    def test_first_field_is_treated_as_timestamp(self):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        rec = Record("r1", {'Timestamp': ts, 'Value': 42})
        assert rec.id == "r1"
        assert rec.timestamp == ts

    def test_fields_property_returns_full_dict(self):
        rec = Record("r1", {'Timestamp': None, 'A': 1, 'B': 2})
        assert rec.fields == {'Timestamp': None, 'A': 1, 'B': 2}

    def test_repr_contains_id(self):
        rec = Record("r-99", {'Timestamp': None, 'X': 1})
        assert "r-99" in repr(rec)


class TestRecords:
    def test_len_matches_input_dict(self):
        recs = Records({
            'rec0': {'Timestamp': None, 'A': 1},
            'rec1': {'Timestamp': None, 'A': 2},
        })
        assert len(recs) == 2

    def test_iter_yields_record_instances_in_order(self):
        recs = Records({
            'rec0': {'Timestamp': None, 'V': 'a'},
            'rec1': {'Timestamp': None, 'V': 'b'},
        })
        ids = [r.id for r in recs]
        assert ids == ['rec0', 'rec1']
        assert all(isinstance(r, Record) for r in recs)


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #

class TestMetadata:
    def test_constructs_from_metadata_dict(self):
        md = Metadata({
            'Name': {'en': 'My Series', 'ko': '시리즈'},
            'Description': {'en': 'description'},
            'Record': {'Timestamp': None, 'Voltage': 0.0},
        })
        assert md.name == {'en': 'My Series', 'ko': '시리즈'}
        assert md.description == {'en': 'description'}
        assert isinstance(md.record, Record)

    def test_description_can_be_none(self):
        md = Metadata({
            'Name': {'en': 'X'},
            'Description': None,
            'Record': {'Timestamp': None, 'A': 0},
        })
        assert md.description is None


# --------------------------------------------------------------------------- #
# Segment 베이스 properties
# --------------------------------------------------------------------------- #

class TestSegmentProperties:
    """`InternalSegment`는 `Segment`를 상속하므로 베이스 properties도 함께 검증."""

    def test_all_metadata_properties_are_passed_through(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        update = datetime(2024, 1, 1, 23)
        seg = InternalSegment(make_segment_dict(
            Name={'en': 'A'},
            Description={'en': 'd'},
            RecordCount=10,
            StartTime=start,
            EndTime=end,
            Duration='PT1H',
            SamplingInterval=100,
            SamplingRate=10,
            State='OK',
            LastUpdate=update,
            Records={},
        ))
        assert seg.name == {'en': 'A'}
        assert seg.description == {'en': 'd'}
        assert seg.record_count == 10
        assert seg.start_time == start
        assert seg.end_time == end
        assert seg.duration == 'PT1H'
        assert seg.sampling_interval == 100
        assert seg.sampling_rate == 10
        assert seg.state == 'OK'
        assert seg.last_update == update


# --------------------------------------------------------------------------- #
# InternalSegment / LinkedSegment
# --------------------------------------------------------------------------- #

class TestInternalSegment:
    def test_records_property_returns_records_collection(self):
        seg = InternalSegment(make_segment_dict(
            Records={
                'r0': {'Timestamp': None, 'V': 1},
                'r1': {'Timestamp': None, 'V': 2},
            },
        ))
        assert isinstance(seg.records, Records)
        assert len(seg.records) == 2

    def test_records_as_pandas_returns_dataframe(self):
        seg = InternalSegment(make_segment_dict(
            Records={
                'r0': {'Timestamp': None, 'V': 1.0},
                'r1': {'Timestamp': None, 'V': 2.0},
            },
        ))
        df = seg.records_as_pandas()
        assert isinstance(df, pd.DataFrame)
        assert list(df['V']) == [1.0, 2.0]

    def test_missing_records_raises_assertion(self):
        with pytest.raises(AssertionError, match="Records is missing"):
            InternalSegment(make_segment_dict())  # 'Records' 키 없음


class TestLinkedSegment:
    def test_constructor_requires_endpoint_and_query(self):
        seg = LinkedSegment(make_segment_dict(
            Endpoint='http://srv/data',
            Query='SELECT 1',
        ))
        # 베이스 properties 동작 + 인스턴스 정상 생성 확인
        assert seg.record_count == 0

    def test_missing_endpoint_raises_assertion(self):
        with pytest.raises(AssertionError, match="Endpoint is missing"):
            LinkedSegment(make_segment_dict(Query='SELECT 1'))

    def test_missing_query_raises_assertion(self):
        with pytest.raises(AssertionError, match="Query is missing"):
            LinkedSegment(make_segment_dict(Endpoint='http://srv'))

    def test_records_as_pandas_raises_not_implemented(self):
        seg = LinkedSegment(make_segment_dict(
            Endpoint='http://x', Query='q',
        ))
        with pytest.raises(NotImplementedError):
            seg.records_as_pandas()


# --------------------------------------------------------------------------- #
# Segments — semantic_id 기반 분류
# --------------------------------------------------------------------------- #

class TestSegments:
    def test_internal_segment_dispatch(self):
        seg_value = make_segment_dict(Records={})
        ref = make_seg_ref(
            TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT, seg_value, id_short='Internal',
        )
        coll = Segments({'Internal': ref})
        assert isinstance(coll['Internal'], InternalSegment)

    def test_linked_segment_dispatch(self):
        seg_value = make_segment_dict(Endpoint='http://x', Query='q')
        ref = make_seg_ref(
            TIMESERIES_SEMANTIC_ID.LINKED_SEGMENT, seg_value, id_short='Linked',
        )
        coll = Segments({'Linked': ref})
        assert isinstance(coll['Linked'], LinkedSegment)

    def test_unknown_semantic_id_raises_value_error(self):
        ref = make_seg_ref('https://unknown/segment', make_segment_dict(), id_short='X')
        with pytest.raises(ValueError, match="Unknown segment type"):
            Segments({'X': ref})

    def test_supports_mapping_protocol(self):
        ref = make_seg_ref(
            TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT,
            make_segment_dict(Records={}),
            id_short='S',
        )
        coll = Segments({'S': ref})

        assert len(coll) == 1
        assert 'S' in coll
        assert 'X' not in coll
        assert list(coll.keys()) == ['S']
        assert list(coll.values()) == [coll['S']]
        assert list(iter(coll)) == [coll['S']]

    def test_keyed_by_id_short(self):
        """입력 dict 키와 무관하게 segment의 id_short가 키로 쓰인다 (회귀 가드)."""
        ref = make_seg_ref(
            TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT,
            make_segment_dict(Records={}),
            id_short='RealName',
        )
        coll = Segments({'IgnoredKey': ref})
        assert 'RealName' in coll
        assert 'IgnoredKey' not in coll


# --------------------------------------------------------------------------- #
# TimeSeries (단순 컨테이너)
# --------------------------------------------------------------------------- #

class TestTimeSeries:
    def test_holds_metadata_and_segments(self):
        md = Metadata({
            'Name': {'en': 'X'},
            'Description': None,
            'Record': {'Timestamp': None, 'A': 0},
        })
        ref = make_seg_ref(
            TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT,
            make_segment_dict(Records={}),
            id_short='S',
        )
        segs = Segments({'S': ref})
        ts = TimeSeries(md, segs)
        assert ts.metadata is md
        assert ts.segments is segs


# --------------------------------------------------------------------------- #
# TimeSeriesService.timeseries()
# --------------------------------------------------------------------------- #

class TestTimeSeriesService:
    def _make_sm_desc(self):
        return MDTSubmodelDescriptor(
            id='sm-ts',
            id_short='TS',
            semantic_id=SEMANTIC_ID_TIME_SERIES_SUBMODEL,
            endpoint='http://srv/sm',
        )

    def test_timeseries_assembles_metadata_and_segments(self):
        svc = TimeSeriesService('inst-1', self._make_sm_desc())

        # element_reference('Metadata').read_value() → Metadata dict
        meta_ref = MagicMock()
        meta_ref.read_value.return_value = {
            'Name': {'en': 'My TS'},
            'Description': None,
            'Record': {'Timestamp': None, 'V': 0},
        }

        # element_reference('Segments') → root segments ref (pathes 호출됨)
        segs_root_ref = MagicMock()
        segs_root_ref.pathes.return_value = ['Segments.Seg1']

        # element_reference('Segments.Seg1') → 개별 segment ref
        seg1_ref = make_seg_ref(
            TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT,
            make_segment_dict(Records={}),
            id_short='Seg1',
        )

        def _element_reference(path):
            if path == 'Metadata':
                return meta_ref
            if path == 'Segments':
                return segs_root_ref
            if path == 'Segments.Seg1':
                return seg1_ref
            raise AssertionError(f"unexpected path: {path}")

        with patch.object(svc, 'element_reference', side_effect=_element_reference):
            ts = svc.timeseries()

        assert isinstance(ts, TimeSeries)
        assert ts.metadata.name == {'en': 'My TS'}
        assert 'Seg1' in ts.segments
        assert isinstance(ts.segments['Seg1'], InternalSegment)

    def test_only_direct_children_of_segments_are_collected(self):
        """깊이 2(`Segments.<name>`) 경로만 segment 후보로 사용된다."""
        svc = TimeSeriesService('inst-1', self._make_sm_desc())

        meta_ref = MagicMock()
        meta_ref.read_value.return_value = {
            'Name': {'en': 'X'},
            'Description': None,
            'Record': {'Timestamp': None, 'V': 0},
        }
        segs_root_ref = MagicMock()
        # 깊이 2가 아닌 경로(루트, 깊이 3 이상)는 무시되어야 한다
        segs_root_ref.pathes.return_value = [
            'Segments',                   # 깊이 1 — 무시
            'Segments.Seg1',              # 깊이 2 — 채택
            'Segments.Seg1.Records',      # 깊이 3 — 무시
        ]
        seg1_ref = make_seg_ref(
            TIMESERIES_SEMANTIC_ID.INTERNAL_SEGMENT,
            make_segment_dict(Records={}),
            id_short='Seg1',
        )

        def _element_reference(path):
            if path == 'Metadata':
                return meta_ref
            if path == 'Segments':
                return segs_root_ref
            if path == 'Segments.Seg1':
                return seg1_ref
            raise AssertionError(f"unexpected path: {path}")

        with patch.object(svc, 'element_reference', side_effect=_element_reference):
            ts = svc.timeseries()

        assert list(ts.segments.keys()) == ['Seg1']
