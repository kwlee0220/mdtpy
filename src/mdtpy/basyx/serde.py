from __future__ import annotations

from typing import Any
import json

from basyx.aas.adapter.json.json_deserialization import AASFromJsonDecoder
from basyx.aas.adapter.json.json_serialization import AASToJsonEncoder


def from_json(json_str:str) -> Any:
  return json.loads(json_str, cls=AASFromJsonDecoder)
  
def from_dict(data:dict) -> Any:
  json_str = json.dumps(data)
  return json.loads(json_str, cls=AASFromJsonDecoder)

def to_json(obj:Any) -> str:
  return json.dumps(obj, cls=AASToJsonEncoder)