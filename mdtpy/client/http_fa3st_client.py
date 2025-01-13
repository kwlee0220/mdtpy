from __future__ import annotations

from typing import Optional, Any
from dataclasses import dataclass

import base64
import requests
import json

from ..model import MDTException, ResourceNotFoundError, InternalError
from .http_client import to_exception, parse_none_response
from ..impl import json_deserializer

@dataclass(frozen=True, slots=True)
class Message:
    messageType: str
    text: str
    code: str
    timestamp: str
    

class HttpFa3stClient:
    """
    A client class for FA3ST API that handles HTTP requests and responses.
    -------
    to_base64_string(id: str) -> str
        Encodes the given string ID to a base64 string.
    parse_none_response(resp: requests.Response) -> None
        Parses a response that is expected to have no content.
    parse_response(result_cls, resp: requests.Response)
        Parses the HTTP response based on the status code and expected result class.
    to_exception(resp: requests.Response) -> MDTException
        Converts an HTTP response to an appropriate exception based on the response content.
    """
    def to_base64_string(self, id:str) -> str:
        return base64.b64encode(id.encode('UTF-8')).decode('ascii')
    
    def parse_none_response(self, resp:requests.Response) -> None:
        return parse_none_response(resp)
        
    def parse_response(self, result_cls, resp:requests.Response):
        if resp.status_code == 204:
            return None
        elif resp.status_code >= 200 and resp.status_code < 300:
            if result_cls == bytes:
                content_type = resp.headers['content-type']
                content = resp.content
                return content_type, content
            
            resp_json = json.loads(resp.text)
            if 'result' in resp_json:
                resp_json = resp_json['result'][0]
            return json_deserializer.read_resource(resp_json)
        else:
            raise to_exception(resp)

    def to_exception(self, resp:requests.Response) -> MDTException:
        json_obj = resp.json()
        message = Message(**json_obj['messages'][0])
        if message.text.startswith("Resource not found"):
            details = message.text[41:-1]
            return ResourceNotFoundError.create("ModelRef", details)
        elif message.text.startswith('error parsing body'):
            return InternalError('JSON parsing failed')
        else:
            return MDTException(message.text)