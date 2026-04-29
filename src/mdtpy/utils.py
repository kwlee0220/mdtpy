from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar, cast

import json
from datetime import date, datetime, timedelta

from basyx.aas import model
from dateutil.relativedelta import relativedelta

T = TypeVar('T')


# --------------------------------------------------------------------------- #
# JSON 직렬화 헬퍼
# --------------------------------------------------------------------------- #

def json_serializer(obj: Any) -> Any:
    """
    `json.dumps`의 `default` 인자로 사용할 수 있는 직렬화 콜백.

    `datetime`/`date`만 ISO 8601 문자열로 변환한다. 그 외의 타입에 대해서는
    `TypeError`를 발생시켜 호출자가 인식하지 못하는 객체를 알아챌 수 있게 한다.

    Args:
        obj (Any): 직렬화 대상 객체.
    Returns:
        Any: ISO 8601 문자열 (datetime/date인 경우).
    Raises:
        TypeError: 지원하지 않는 타입인 경우.
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def json_dumps(obj: Any) -> str:
    """`json_serializer`를 적용한 `json.dumps` 단축 함수."""
    return json.dumps(obj, default=json_serializer)


class JsonSerializable(Generic[T]):
    """
    JSON 직렬화 가능 클래스의 mixin/추상 베이스.

    하위 타입은 `from_json_object`와 `to_json_object`를 구현해야 한다.
    `from_json` / `to_json`은 dict ↔ JSON 문자열 변환을 자동 수행한다.

    Note:
        `from_json_object`와 `to_json_object`는 본문이 `...`인 stub이므로
        직접 호출 시 `None`이 반환된다. 반드시 서브클래스에서 override한다.
    """

    @classmethod
    def from_json_object(cls, data: Any) -> T:
        """JSON 객체(dict 등)에서 인스턴스를 만든다 (서브클래스에서 구현)."""
        ...

    def to_json_object(self) -> Any:
        """현재 인스턴스를 JSON 직렬화 가능한 객체로 변환한다 (서브클래스 구현)."""
        ...

    @classmethod
    def from_json(cls, json_str: str) -> T:
        """JSON 문자열을 파싱해 `from_json_object`를 호출한다."""
        json_obj = json.loads(json_str)
        return cls.from_json_object(json_obj)

    def to_json(self) -> str:
        """`to_json_object`의 결과를 JSON 문자열로 직렬화한다."""
        return json.dumps(self.to_json_object())


# --------------------------------------------------------------------------- #
# datetime / timedelta ↔ ISO 8601
# --------------------------------------------------------------------------- #

def datetime_to_iso8601(dt: datetime) -> str:
    """`datetime`을 ISO 8601 문자열로 변환한다."""
    return dt.isoformat()


def iso8601_to_datetime(iso8601: str) -> datetime:
    """
    ISO 8601 datetime 문자열을 `datetime` 객체로 파싱한다.

    Python 3.10의 `datetime.fromisoformat`은 분수 초가 3자리 또는 6자리일
    때만 허용하므로, 입력의 분수 부분이 짧으면 `0`으로 패딩한다.

    Args:
        iso8601 (str): ISO 8601 형식 문자열.
    Returns:
        datetime: 파싱된 datetime.
    """
    # 밀리초 부분이 3자리가 아닌 경우 처리
    if '.' in iso8601:
        base, ms = iso8601.split('.')
        ms = ms.ljust(3, '0')
        iso8601 = f"{base}.{ms}"
    return datetime.fromisoformat(iso8601)


def timedelta_to_iso8601(delta: timedelta) -> str:
    """`timedelta`를 ISO 8601 duration 문자열(`PnDTnHnMnS`)로 변환한다."""
    return second_to_iso8601(delta.total_seconds())


def second_to_iso8601(total_seconds: float) -> str:
    """
    초 단위 실수를 ISO 8601 duration 문자열로 변환한다.

    예:
        - 0초 → `"PT0S"`
        - 90초 → `"PT1M30S"`
        - 1일 1시간 → `"P1DT1H"`
        - 0.5초 → `"PT0.500S"` (밀리초까지 표기)

    Args:
        total_seconds (float): 변환할 총 초 (음수가 아닌 값을 가정).
    Returns:
        str: `P[nD]T[nH][nM][nS]` 형식의 duration.
    """
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, remainder = divmod(remainder, 60)
    seconds, milliseconds = divmod(remainder, 1)

    parts = []
    if days > 0:
        parts.append(f"{int(days)}D")
    if hours > 0 or minutes > 0 or seconds > 0 or milliseconds > 0 or (not parts):
        time_part = "T"
        if hours > 0:
            time_part += f"{int(hours)}H"
        if minutes > 0:
            time_part += f"{int(minutes)}M"
        if seconds > 0 or milliseconds > 0 or (not parts and time_part == "T"):
            seconds_str = f"{int(seconds)}"
            if milliseconds > 0:
                seconds_str += f".{int(milliseconds * 1000):03d}"
            time_part += f"{seconds_str}S"
        parts.append(time_part)

    return "P" + "".join(parts)


def iso8601_to_timedelta(iso8601: str) -> timedelta:
    """
    ISO 8601 duration 문자열을 `timedelta`로 변환한다.

    내부적으로 `isodate.parse_duration`을 사용한다 (월/년 단위는 timedelta로
    환산할 수 없으므로 입력은 일/시/분/초 범위로 한정해야 한다).
    """
    import isodate
    return isodate.parse_duration(iso8601)


# --------------------------------------------------------------------------- #
# 일반 헬퍼
# --------------------------------------------------------------------------- #

def to_nonnull(value: Optional[T]) -> T:
    """
    `value`가 None이 아님을 단언하고 그대로 반환한다.

    Optional을 좁혀야 하는 곳에서 짧게 쓰기 위한 헬퍼. `python -O`에서는 assert가
    제거되므로 None인 경우 후속 코드에서 다른 형태로 깨질 수 있다.

    Args:
        value (Optional[T]): 검사할 값.
    Returns:
        T: 동일한 값 (None이 아님).
    Raises:
        AssertionError: `value`가 None인 경우.
    """
    assert value is not None
    return value


# --------------------------------------------------------------------------- #
# SubmodelElement → Python 값 변환
# --------------------------------------------------------------------------- #

def to_str(sme: model.SubmodelElement) -> Optional[str]:
    """`Property` SME의 값을 문자열로 변환한다 (값이 None이면 None)."""
    value = cast(model.Property, sme).value
    return str(value) if value is not None else None


def to_int(sme: model.SubmodelElement) -> Optional[int]:
    """`Property` SME의 값을 `model.datatypes.Int`로 변환한다."""
    value = cast(model.Property, sme).value
    return model.datatypes.Int(value) if value is not None else None


def to_datetime(sme: model.SubmodelElement) -> Optional[datetime]:
    """`Property` SME의 값을 `datetime`으로 반환한다 (서버가 이미 datetime 형태로 채운다고 가정)."""
    return sme.value if sme.value is not None else None  # type: ignore


def to_duration(sme: model.SubmodelElement) -> Optional[relativedelta]:
    """`Property` SME의 값을 `relativedelta`로 반환한다."""
    return sme.value if sme.value is not None else None  # type: ignore


def to_mlstr(mlp: model.SubmodelElement) -> Optional[str]:
    """
    `MultiLanguageProperty`의 값에서 첫 번째 언어의 텍스트를 반환한다.

    값이 None이거나 빈 매핑이면 None을 반환한다. 서버 응답은 일반적으로
    한 개의 언어만 채워서 보낸다고 가정하고 단순 추출한다.
    """
    try:
        if mlt := mlp.value:  # type: ignore
            tup = next(iter(mlt.items()))
            return tup[1] if tup is not None else None
        else:
            return None
    except StopIteration:
        return None


# --------------------------------------------------------------------------- #
# relativedelta ↔ timedelta
# --------------------------------------------------------------------------- #

def relativedelta_to_timedelta(rd: relativedelta, base: datetime) -> timedelta:
    """
    `relativedelta`를 주어진 기준 시각(`base`)에 적용해 `timedelta`로 환산한다.

    `relativedelta`는 월/년 같이 길이가 가변적인 단위를 가질 수 있어 `base`가
    없으면 `timedelta`로 변환할 수 없다.
    """
    return (base + rd) - base if rd else timedelta(seconds=0)


# 과거 오타(`relativedelta_to_timedelata`)와의 호환을 위한 별칭. 신규 코드는
# `relativedelta_to_timedelta`를 사용한다.
relativedelta_to_timedelata = relativedelta_to_timedelta


def relativedelta_to_seconds(rd: relativedelta, base: datetime) -> float:
    """`relativedelta_to_timedelta`의 결과를 총 초로 반환한다."""
    return relativedelta_to_timedelta(rd, base).total_seconds()


def timedelta_to_relativedelta(td: timedelta) -> relativedelta:
    """`timedelta`를 동일한 길이의 `relativedelta`로 변환한다."""
    return relativedelta(
        days=td.days,
        seconds=td.seconds,
        microseconds=td.microseconds,
    )
