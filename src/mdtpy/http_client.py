from __future__ import annotations

import requests

from .exceptions import MDTException, RemoteError, ResourceNotFoundError


def parse_none_response(resp:requests.Response) -> None:
    if resp.status_code >= 200 and resp.status_code < 300:
        return
    else:
        raise to_exception(resp)

def parse_response(resp:requests.Response, result_cls:type|None=None):
  if resp.status_code >= 200 and resp.status_code < 300:
    content_type = resp.headers['content-type']
    if content_type == 'application/json':
      json = resp.json()
      return result_cls.from_dict(json) if result_cls else json
    elif content_type.startswith('text/plain'):
      return resp.text
    else:
      raise MDTException(f"Unsupported content type: {content_type}")
  else:
    raise to_exception(resp)

def parse_list_response(resp:requests.Response, result_cls:type=None):
  if resp.status_code >= 200 and resp.status_code < 300:
    return [result_cls.from_dict(descElm) for descElm in resp.json()]
  else:
    raise to_exception(resp)

    
def to_exception(resp:requests.Response) -> MDTException:
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
      from .exceptions import ResourceNotFoundError
      raise ResourceNotFoundError(json_obj['message'])
    
    paths = code.split('.')
    
    from importlib import import_module
    moduleName = '.'.join(paths[:-1])
    module = import_module(moduleName)
    exception_cls = getattr(module, paths[-1])
    return exception_cls(json_obj['text'])
  else:
    return RemoteError(resp.text)
