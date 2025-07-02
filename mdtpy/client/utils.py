from __future__ import annotations

from typing import Optional
from abc import ABC, abstractmethod

import time
from datetime import timedelta, datetime

from mdtpy.model import Reference


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

def semantic_id_string(semantic_id:Optional[Reference]) -> str:
    """
    Reference 객체에서 semantic ID 부분을 추출한다.

    Args:
        semantic_id (Optional[Reference]): 시맨틱 ID Reference 객체

    Returns:
        str: Semantic ID 문자열. semantic_id가 None인 경우 None을 반환
    """
    if semantic_id:
        return semantic_id.keys[0].value
    else:
        return None

class StatusPoller(ABC):
    """
    Abstract base class for polling the status of an operation.
    Attributes:
        poll_interval (float): The interval in seconds between each poll.
        timeout (Optional[float]): The maximum time in seconds to wait for the operation to complete. If None, wait indefinitely.
    Methods:
        is_done() -> bool:
            Abstract method to check if the operation is done. Must be implemented by subclasses.
        wait_for_done() -> None:
            Waits for the operation to complete by repeatedly calling `check_done` at intervals specified by `poll_interval`.
            Raises:
                TimeoutError: If the operation does not complete within the specified timeout.
    """
    def __init__(self, poll_interval:float, timeout:Optional[float]=None):
        self.poll_interval = poll_interval
        self.timeout = timeout
        
    @abstractmethod
    def is_done(self) -> bool: pass
    
    def wait_for_done(self) -> None:
        # 타임아웃 (self.timeout)이 있는 경우 최종 제한 시간을 계산하고,    
        # 타임아웃이 없는 경우 due를 None으로 설정하여 무제한 대기하도록 한다.
        started = time.time()
        due = started + self.timeout if self.timeout else None
        # 다음 폴링 시간을 계산한다.
        next_wakeup = started + self.poll_interval
        
        while not self.is_done():
            now = time.time()
            
            # 타임 아웃까지 남은 시간이 일정 시간 이내인 경우에는 TimeoutError를 발생시킨다.
            # 그렇지 않은 경우는 다음 폴링 시간까지 대기한다.
            if due and (due - now) < 0.01:
                raise TimeoutError(f'timeout={self.timeout}')
            
            # 다음 폴링 시간까지 남은 시간이 짧으면 대기하지 않고 바로 다음 폴링 시도한다.
            sleep_time = next_wakeup - now
            if sleep_time > 0.001:
                time.sleep(sleep_time)
            next_wakeup += self.poll_interval