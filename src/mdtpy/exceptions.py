from __future__ import annotations

    
class MDTException(Exception):
  def __init__(self, details:str) -> None:
    self.details = details
    super().__init__(details)
    
  def __str__(self) -> str:
    return repr(self)


class InternalError(MDTException):
  def __init__(self, details:str) -> None:
    super().__init__(details)


class TimeoutError(MDTException):
  def __init__(self, details:str) -> None:
    super().__init__(details)


class CancellationError(MDTException):
  def __init__(self, details:str) -> None:
    super().__init__(details)


class OperationError(MDTException):
  def __init__(self, details:str) -> None:
    super().__init__(details)


class RemoteError(MDTException):
  def __init__(self, details:str) -> None:
    super().__init__(details)

import requests
class MDTInstanceConnectionError(MDTException):
  """
  MDTInstance와의 연결 오류가 발생한 경우 발생하는 예외.
  """
  def __init__(self, details:str, cause:requests.exceptions.ConnectionError) -> None:
    super().__init__(details)
    self.cause = cause

  def __repr__(self) -> str:
    return f"{self.__class__.__name__}(details={self.details}, cause={self.cause})"

   
class ResourceAlreadyExistsError(MDTException):
  """
  리소스가 이미 존재하는 경우 발생하는 예외.
  """
  def __init__(self, details:str) -> None:
    super().__init__(details)
      
  @classmethod
  def create(cls, resource_type:str, id_spec:str):
    return ResourceAlreadyExistsError(f"Resource(type={resource_type}, {id_spec})")
    
    
class ResourceNotFoundError(MDTException):
  """
  리소스가 존재하지 않는 경우 발생하는 예외.
  """
  def __init__(self, details:str) -> None:
    super().__init__(details)
      
  @classmethod
  def create(cls, resource_type:str, id_spec:str):
    return ResourceNotFoundError(f"Resource(type={resource_type}, {id_spec})")
        
    
class InvalidResourceStateError(MDTException):
  """
  리소스의 상태가 유효하지 않은 경우 발생하는 예외.
  """
  def __init__(self, details:str) -> None:
    super().__init__(details)
      
  @classmethod
  def create(cls, resource_type:str, id_spec:str, status):
    return InvalidResourceStateError(f"Resource(type={resource_type}, {id_spec}), status={status}")