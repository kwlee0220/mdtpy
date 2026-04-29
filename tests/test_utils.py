"""
mdtpy.utils 모듈의 헬퍼 함수/클래스에 대한 단위 테스트.

대상:
    - json_serializer / json_dumps
    - JsonSerializable (서브클래스를 통한 동작 검증)
    - datetime ↔ ISO 8601, timedelta ↔ ISO 8601 duration
    - second_to_iso8601 (다양한 입력)
    - to_nonnull
    - SME → Python 변환 헬퍼: to_str / to_int / to_datetime / to_duration / to_mlstr
    - relativedelta ↔ timedelta 헬퍼 (오타 별칭 포함)
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from dateutil.relativedelta import relativedelta

from basyx.aas import model

from mdtpy.utils import (
    JsonSerializable,
    datetime_to_iso8601,
    iso8601_to_datetime,
    iso8601_to_timedelta,
    json_dumps,
    json_serializer,
    relativedelta_to_seconds,
    relativedelta_to_timedelata,
    relativedelta_to_timedelta,
    second_to_iso8601,
    timedelta_to_iso8601,
    timedelta_to_relativedelta,
    to_datetime,
    to_duration,
    to_int,
    to_mlstr,
    to_nonnull,
    to_str,
)


# --------------------------------------------------------------------------- #
# json_serializer / json_dumps
# --------------------------------------------------------------------------- #

class TestJsonSerializer:
    def test_datetime_serialized_as_isoformat(self):
        dt = datetime(2024, 1, 1, 12, 30, 45)
        assert json_serializer(dt) == "2024-01-01T12:30:45"

    def test_date_serialized_as_isoformat(self):
        d = date(2024, 1, 1)
        assert json_serializer(d) == "2024-01-01"

    @pytest.mark.parametrize("value", [object(), set([1, 2]), 3.14j])
    def test_unsupported_type_raises_type_error(self, value):
        with pytest.raises(TypeError, match="not JSON serializable"):
            json_serializer(value)


class TestJsonDumps:
    def test_includes_datetime_via_default(self):
        result = json_dumps({"created_at": datetime(2024, 1, 1, 0, 0, 0)})
        parsed = json.loads(result)
        assert parsed == {"created_at": "2024-01-01T00:00:00"}

    def test_passes_through_native_types(self):
        result = json_dumps({"x": 1, "y": "hello", "z": [True, None]})
        assert json.loads(result) == {"x": 1, "y": "hello", "z": [True, None]}


# --------------------------------------------------------------------------- #
# JsonSerializable
# --------------------------------------------------------------------------- #

class _Sample(JsonSerializable["_Sample"]):
    def __init__(self, x: int, y: str) -> None:
        self.x = x
        self.y = y

    @classmethod
    def from_json_object(cls, data):
        return cls(x=data["x"], y=data["y"])

    def to_json_object(self):
        return {"x": self.x, "y": self.y}

    def __eq__(self, other):
        return isinstance(other, _Sample) and self.x == other.x and self.y == other.y


class TestJsonSerializable:
    def test_subclass_roundtrip_via_json_string(self):
        original = _Sample(x=42, y="hello")
        json_str = original.to_json()
        restored = _Sample.from_json(json_str)
        assert restored == original

    def test_to_json_uses_to_json_object_output(self):
        s = _Sample(x=1, y="z")
        assert json.loads(s.to_json()) == {"x": 1, "y": "z"}


# --------------------------------------------------------------------------- #
# datetime ↔ ISO 8601
# --------------------------------------------------------------------------- #

class TestDatetimeIso8601:
    def test_datetime_to_iso8601_uses_isoformat(self):
        dt = datetime(2024, 6, 15, 9, 30, 0)
        assert datetime_to_iso8601(dt) == "2024-06-15T09:30:00"

    def test_iso8601_to_datetime_basic(self):
        assert iso8601_to_datetime("2024-06-15T09:30:00") == datetime(2024, 6, 15, 9, 30, 0)

    def test_iso8601_to_datetime_pads_short_milliseconds(self):
        """3자리 미만 분수 초는 0으로 패딩된 후 파싱되어야 한다."""
        # '.5' → '.500'으로 패딩
        result = iso8601_to_datetime("2024-06-15T09:30:00.5")
        assert result == datetime(2024, 6, 15, 9, 30, 0, microsecond=500000)

    def test_roundtrip(self):
        dt = datetime(2024, 6, 15, 9, 30, 0)
        assert iso8601_to_datetime(datetime_to_iso8601(dt)) == dt


# --------------------------------------------------------------------------- #
# second_to_iso8601 / timedelta ↔ ISO 8601
# --------------------------------------------------------------------------- #

class TestSecondToIso8601:
    def test_zero_returns_pt0s(self):
        assert second_to_iso8601(0) == "PT0S"

    def test_seconds_only(self):
        assert second_to_iso8601(45) == "PT45S"

    def test_minutes_and_seconds(self):
        assert second_to_iso8601(90) == "PT1M30S"

    def test_hours_minutes_seconds(self):
        assert second_to_iso8601(3661) == "PT1H1M1S"

    def test_days_only(self):
        assert second_to_iso8601(86400) == "P1D"

    def test_days_and_time(self):
        assert second_to_iso8601(86400 + 3600) == "P1DT1H"

    def test_sub_second_milliseconds(self):
        # 0.5초 = 500밀리초
        assert second_to_iso8601(0.5) == "PT0.500S"

    def test_complex_combination(self):
        # 1일 + 2시간 + 3분 + 4.5초
        td = timedelta(days=1, hours=2, minutes=3, seconds=4, milliseconds=500)
        assert second_to_iso8601(td.total_seconds()) == "P1DT2H3M4.500S"


class TestTimedeltaIso8601:
    def test_timedelta_to_iso8601_delegates_to_seconds(self):
        td = timedelta(hours=1, minutes=30)
        assert timedelta_to_iso8601(td) == "PT1H30M"

    def test_iso8601_to_timedelta_uses_isodate(self):
        assert iso8601_to_timedelta("PT1H30M") == timedelta(hours=1, minutes=30)

    def test_roundtrip_for_simple_durations(self):
        td = timedelta(days=2, hours=3, minutes=45)
        assert iso8601_to_timedelta(timedelta_to_iso8601(td)) == td


# --------------------------------------------------------------------------- #
# to_nonnull
# --------------------------------------------------------------------------- #

class TestToNonnull:
    @pytest.mark.parametrize("value", [0, "", False, [], {}, "x", 42])
    def test_returns_value_unchanged_when_not_none(self, value):
        assert to_nonnull(value) == value

    def test_none_raises_assertion(self):
        with pytest.raises(AssertionError):
            to_nonnull(None)


# --------------------------------------------------------------------------- #
# SubmodelElement → Python 변환
# --------------------------------------------------------------------------- #

class TestToStr:
    def test_returns_str_value(self):
        prop = MagicMock(spec=model.Property)
        prop.value = 42
        assert to_str(prop) == "42"

    def test_none_value_returns_none(self):
        prop = MagicMock(spec=model.Property)
        prop.value = None
        assert to_str(prop) is None


class TestToInt:
    def test_uses_basyx_int_constructor(self):
        prop = MagicMock(spec=model.Property)
        prop.value = "42"
        result = to_int(prop)
        # model.datatypes.Int은 int 호환 타입을 만든다
        assert int(result) == 42

    def test_none_value_returns_none(self):
        prop = MagicMock(spec=model.Property)
        prop.value = None
        assert to_int(prop) is None


class TestToDatetime:
    def test_returns_value_directly(self):
        prop = MagicMock()
        dt = datetime(2024, 1, 1)
        prop.value = dt
        assert to_datetime(prop) is dt

    def test_none_returns_none(self):
        prop = MagicMock()
        prop.value = None
        assert to_datetime(prop) is None


class TestToDuration:
    def test_returns_value_directly(self):
        prop = MagicMock()
        rd = relativedelta(hours=2)
        prop.value = rd
        assert to_duration(prop) is rd

    def test_none_returns_none(self):
        prop = MagicMock()
        prop.value = None
        assert to_duration(prop) is None


class TestToMlstr:
    def test_returns_first_language_text(self):
        mlp = MagicMock()
        mlp.value = {"en": "hello", "ko": "안녕"}
        assert to_mlstr(mlp) == "hello"

    def test_returns_none_when_value_is_none(self):
        mlp = MagicMock()
        mlp.value = None
        assert to_mlstr(mlp) is None

    def test_returns_none_when_value_is_empty_mapping(self):
        mlp = MagicMock()
        mlp.value = {}
        # 빈 dict는 falsy → 'None을 반환'
        assert to_mlstr(mlp) is None


# --------------------------------------------------------------------------- #
# relativedelta ↔ timedelta
# --------------------------------------------------------------------------- #

class TestRelativedeltaTimedelta:
    def test_simple_days_conversion(self):
        base = datetime(2024, 1, 1)
        rd = relativedelta(days=3)
        assert relativedelta_to_timedelta(rd, base) == timedelta(days=3)

    def test_month_handles_variable_length(self):
        """1월(31일) 기준 +1 month는 31일짜리 timedelta로 환산되어야 한다."""
        jan1 = datetime(2024, 1, 1)
        td = relativedelta_to_timedelta(relativedelta(months=1), jan1)
        assert td == timedelta(days=31)

    def test_zero_returns_zero_timedelta(self):
        # falsy relativedelta는 timedelta(0)
        assert relativedelta_to_timedelta(relativedelta(), datetime(2024, 1, 1)) == timedelta(0)

    def test_typo_alias_still_works(self):
        """`relativedelta_to_timedelata` 오타 이름은 호환성 별칭으로 살아 있다."""
        assert relativedelta_to_timedelata is relativedelta_to_timedelta

    def test_to_seconds_returns_total_seconds(self):
        base = datetime(2024, 1, 1)
        secs = relativedelta_to_seconds(relativedelta(hours=2, minutes=30), base)
        assert secs == 9000.0


class TestTimedeltaToRelativedelta:
    def test_preserves_days_seconds_microseconds(self):
        td = timedelta(days=2, seconds=30, microseconds=500)
        rd = timedelta_to_relativedelta(td)
        assert rd.days == 2
        assert rd.seconds == 30
        assert rd.microseconds == 500
