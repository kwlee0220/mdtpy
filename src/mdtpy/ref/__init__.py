from __future__ import annotations

from typing import Any

import json

from .reference import ElementReference
from .base_reference import BaseElementReference


# 참조 serde 자유 함수(parse_reference_json_node/parse_reference_json_string)는
# wildcard export(__all__)에서 제외한다. `mdtpy.ref.parse_reference_json_node` 처럼
# 모듈 한정으로 사용한다.
__all__ = [
    'reference',
    'ElementReference',
    'parse_reference_json_node',
    'parse_reference_json_string',
    'BaseElementReference',
]

def reference(ref_string:str) -> ElementReference:
    """reference 문자열을 `ElementReference`로 해석한다."""
    return BaseElementReference(ref_string)

def parse_reference_json_node(jnode: dict[str, Any]) -> ElementReference:
    return parse_reference_json_string(json.dumps(jnode))

def parse_reference_json_string(json_str: str) -> ElementReference:
    from ..instance import mdt_manager
    if mdt_manager is None:
        raise RuntimeError("mdt_manager is not initialized (parse_reference_json_string)")
    return mdt_manager.from_reference_json(json_str)
