from __future__ import annotations

from typing import Any, cast, TypeVar, Generic

import json
from datetime import datetime, timedelta, date

from basyx.aas import model

T = TypeVar('T')


def json_serializer(obj: Any) -> Any:
  if isinstance(obj, (datetime, date)):
    return obj.isoformat()
  raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
def json_dumps(obj: Any) -> str:
  return json.dumps(obj, default=json_serializer)


class JsonSerializable(Generic[T]):
  @classmethod
  def from_json_object(cls, data: Any) -> T: ...

  def to_json_object(self) -> Any: ...

  @classmethod
  def from_json(cls, json_str: str) -> T:
    json_obj = json.loads(json_str)
    return cls.from_json_object(json_obj)

  def to_json(self) -> str:
    return json.dumps(self.to_json_object())


def datetime_to_iso8601(dt: datetime) -> str:
    """Convert a datetime object to ISO8601 datetime string format."""
    return dt.isoformat()

def iso8601_to_datetime(iso8601: str) -> datetime:
    # 밀리초 부분이 3자리가 아닌 경우 처리
    if '.' in iso8601:
        base, ms = iso8601.split('.')
        # 밀리초 부분을 3자리로 맞춤
        ms = ms.ljust(3, '0')
        iso8601 = f"{base}.{ms}"
    return datetime.fromisoformat(iso8601)

def timedelta_to_iso8601(delta: timedelta) -> str:
    return second_to_iso8601(delta.total_seconds())

def second_to_iso8601(total_seconds: float) -> str:
    """Convert a timedelta object to ISO8601 duration string format."""
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
    import isodate
    return isodate.parse_duration(iso8601)

def to_nonnull(value: T|None) -> T:
  assert value is not None
  return value

from dateutil.relativedelta import relativedelta

def to_str(sme:model.SubmodelElement) -> str|None:
  value = cast(model.Property, sme).value
  return str(value) if value is not None else None
def to_int(sme:model.SubmodelElement) -> int|None:
  value = cast(model.Property, sme).value
  return model.datatypes.Int(value) if value is not None else None
def to_datetime(sme:model.SubmodelElement) -> datetime|None:
  return sme.value if sme.value is not None else None   # type: ignore
def to_duration(sme:model.SubmodelElement) -> relativedelta|None:
  return sme.value if sme.value is not None else None   # type: ignore
def to_mlstr(mlp: model.SubmodelElement) -> str|None:
  try:
    if mlt := mlp.value:    # type: ignore
      tup = next(iter(mlt.items()))
      return tup[1] if tup is not None else None
    else:
      return None
  except StopIteration:
    return None



from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

def relativedelta_to_timedelata(rd:relativedelta, base:datetime) -> timedelta:
  return (base + rd) - base if rd else timedelta(seconds=0)
def relativedelta_to_seconds(rd:relativedelta, base:datetime) -> float:
  return relativedelta_to_timedelata(rd, base).total_seconds()

def timedelta_to_relativedelta(td:timedelta) -> relativedelta:
  return relativedelta(days=td.days,
                        seconds=td.seconds,
                        microseconds=td.microseconds)