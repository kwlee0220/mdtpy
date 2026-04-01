from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar
from dataclasses import dataclass

import base64
import requests
import json
from urllib import parse

from dataclass_wizard import JSONWizard

from .exceptions import RemoteError, MDTException, ResourceNotFoundError
from .utils import JsonSerializable

T = TypeVar('T')

@dataclass(frozen=True, slots=True)
class Message(JSONWizard):
  message_type: str
  text: str
  code: str
  timestamp: str
    
def encode_base64url(text:str) -> str:
  """
  Encodes the given string ID to a base64 string.
  """
  return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


def decode_base64url(text:str) -> str:
  """
  Decodes the given base64 string to a string.
  """
  padding = '=' * (-len(text) % 4)
  return base64.urlsafe_b64decode(text + padding).decode("utf-8")

def encode_url(text:str) -> str:
  return parse.quote(text)

def decode_url(text:str) -> str:
  return parse.unquote(text)

 
def read_none_response(resp:requests.Response) -> None:
  """
  Parses a response that is expected to have no content.
  """
  if resp.status_code >= 200 and resp.status_code < 300:
    return
  else:
    raise to_exception(resp)

  
def read_response(resp:requests.Response) -> str | None:
  """
  Parses the HTTP response based on the status code and expected result class.
  """
  if resp.status_code == 204:
    return None
  elif resp.status_code >= 200 and resp.status_code < 300:
    return resp.text
  else:
    raise to_exception(resp)
  
def read_file_response(resp:requests.Response) -> tuple[str, bytes]|None:
  if resp.status_code == 204:
    return None
  elif resp.status_code >= 200 and resp.status_code < 300:
    return resp.headers['content-type'], resp.content
  else:
    raise to_exception(resp)
    

def call_get(url:str, deserializer:Optional[Callable[[str], T]]=None) -> T|str|None:
  try:
    resp = requests.get(url, verify=False)
    resp_text = read_response(resp)
    return deserializer(resp_text) if deserializer and resp_text else resp_text
  except requests.exceptions.ConnectionError as e:
    from .exceptions import MDTInstanceConnectionError
    raise MDTInstanceConnectionError(f"Failed to connect to {url}", e)

def call_put(url:str, data:str, deserializer:Optional[Callable[[str], T]]=None) -> T|str|None:
  try:
    resp = requests.put(url, data=data, verify=False)
    resp_text = read_response(resp)
    return deserializer(resp_text) if deserializer and resp_text else resp_text
  except requests.exceptions.ConnectionError as e:
    from .exceptions import MDTInstanceConnectionError
    raise MDTInstanceConnectionError(f"Failed to connect to {url}", e)

def call_post(url:str, data:str, deserializer:Optional[Callable[[str], T]]=None) -> T|str|None:
  try:
    resp = requests.post(url, data=data, headers={'Content-Type': 'application/json'}, verify=False)
    resp_text = read_response(resp)
    return deserializer(resp_text) if deserializer and resp_text else resp_text
  except requests.exceptions.ConnectionError as e:
    from .exceptions import MDTInstanceConnectionError
    raise MDTInstanceConnectionError(f"Failed to connect to {url}", e)

def call_patch(url:str, json_str:str, deserializer:Optional[Callable[[str], T]]=None) -> T|str|None:
  try:
    resp = requests.patch(url, data=json_str, headers={'Content-Type': 'application/json'}, verify=False)
    resp_text = read_response(resp)
    return deserializer(resp_text) if deserializer and resp_text else resp_text
  except requests.exceptions.ConnectionError as e:
    from .exceptions import MDTInstanceConnectionError
    raise MDTInstanceConnectionError(f"Failed to connect to {url}", e)

def call_delete(url:str) -> None:
  try:
    resp = requests.delete(url, verify=False)
    read_none_response(resp)
  except requests.exceptions.ConnectionError as e:
    from .exceptions import MDTInstanceConnectionError
    raise MDTInstanceConnectionError(f"Failed to connect to {url}", e)


# def to_exception(resp:requests.Response) -> MDTException:
#   """
#   Converts an HTTP response to an appropriate exception based on the response content.
#   """
#   json_obj = resp.json()
#   message = Message.from_dict(json_obj['messages'][0])
#   if message.text.startswith("Resource not found"):
#       details = message.text[41:-1]
#       return ResourceNotFoundError.create("ModelRef", details)
#   elif message.text.startswith('error parsing body'):
#       return InternalError('JSON parsing failed')
#   else:
#       return MDTException(message.text)

def to_exception(resp:requests.Response) -> MDTException:
  ctype = resp.headers['Content-Type']
  if ctype.startswith('text/'):
    return RemoteError(resp.text)

  json_obj = resp.json()
  if 'messages' in json_obj:
    message = json_obj['messages'][0]
    return RemoteError(message['text'])
  elif 'code' in json_obj:
    code = json_obj['code']
    if code == 'java.lang.IllegalArgumentException':
      raise RemoteError(json_obj['message'])
    elif code == 'utils.InternalException':
      return RemoteError(json_obj['message'])
    elif code == 'java.lang.NullPointerException' \
        or code == 'java.lang.UnsupportedOperationException':
      raise RemoteError(f"code={json_obj['code']}, message={json_obj['message']}")
    elif code == 'org.springframework.web.servlet.resource.NoResourceFoundException':
      raise RemoteError(json_obj['text'])
    elif code == 'org.springframework.web.HttpRequestMethodNotSupportedException':
      raise RemoteError(json_obj['text'])
    
    elif code == 'mdt.model.ResourceNotFoundException':
      raise ResourceNotFoundError(json_obj['message'])
    
    paths = code.split('.')
    
    from importlib import import_module
    moduleName = '.'.join(paths[:-1])
    module = import_module(moduleName)
    exception_cls = getattr(module, paths[-1])
    return exception_cls(json_obj['text'])
  else:
    return RemoteError(resp.text)
