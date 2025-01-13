from __future__ import annotations

from typing import Optional

import base64
import requests

from mdtpy.model import MDTException, RemoteError
from ..model.aas_model import Endpoint


def to_base64_string(src:str) -> str:
    return base64.urlsafe_b64encode(bytes(src, 'utf-8')).decode('ascii')

def parse_none_response(resp:requests.Response) -> None:
    if resp.status_code >= 200 and resp.status_code < 300:
        return
    else:
        raise to_exception(resp)
    
def parse_response(result_cls, resp:requests.Response):
    if resp.status_code >= 200 and resp.status_code < 300:
        return result_cls.from_json(resp.text)
    else:
        raise to_exception(resp)
    
def parse_list_response(result_cls, resp:requests.Response):
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
            raise RemoteError(json_obj['message'])
        elif code == 'java.lang.NullPointerException':
            raise RemoteError(f"code={json_obj['code']}, message={json_obj['message']}")
        elif code == 'org.springframework.web.servlet.resource.NoResourceFoundException':
            raise RemoteError(json_obj['text'])
        elif code == 'org.springframework.web.HttpRequestMethodNotSupportedException':
            raise RemoteError(json_obj['text'])
        paths = code.split('.')
        
        from importlib import import_module
        moduleName = '.'.join(paths[:-1])
        module = import_module(moduleName)
        exception_cls = getattr(module, paths[-1])
        return exception_cls(json_obj['text'])

def extract_href(endpoints:list[Endpoint]) -> Optional[str]:
    if len(endpoints) == 0:
        return None
    href = endpoints[0].protocolInformation.href
    if href == None or len(href) == 0:
        return None
    else:
        return href