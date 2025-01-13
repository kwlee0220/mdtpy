from __future__ import annotations

from typing import Optional
from abc import ABC, abstractmethod

import time

from mdtpy.model import Reference

def semantic_id_string(semantic_id:Optional[Reference]) -> str:
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
        check_done() -> bool:
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
    def check_done(self) -> bool: pass
    
    def wait_for_done(self) -> None:
        # If timeout is not None, calculate the time when the operation should be considered timed out,
        # and calculate the time when the next poll should occur.
        started = time.time()
        due = started + self.timeout if self.timeout else None
        next_wakeup = started + self.poll_interval
        
        while not self.check_done():
            now = time.time()
            
            # If due is less than 10 milliseconds away, raise a TimeoutError.
            # We assume that after sleep and wakeup elapse more than 10 milliseconds.
            if due and due - now < 0.01:
                raise TimeoutError(f'timeout={self.timeout}')
            
            sleep_time = next_wakeup - now
            if sleep_time > 0.001:
                time.sleep(sleep_time)
            next_wakeup += self.poll_interval