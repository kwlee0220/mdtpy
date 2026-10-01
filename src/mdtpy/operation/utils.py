from __future__ import annotations
import json
from typing import Any

from basyx.aas import model

from ..basyx import serde as basyx_serde
from ..value.element_value import ElementValue
from ..value import parse_json_node as parse_value_json_node
from ..ref import parse_reference_json_node
from ..ref.reference import ElementReference

from .aas_operation import ArgumentType


def parse_argument_json_node(arg_json_node: Any) -> ArgumentType:
    """연산 인자 하나에 해당하는 JSON 노드를 대응되는 파이썬 객체로 변환한다.

    노드의 타입 태그를 보고 적절한 파서로 분배한다.

    * ``dict`` 가 아닌 노드(스칼라 등)는 그대로 반환한다.
    * ``@type`` 이 ``mdt:value:`` 로 시작하면 :class:`~mdtpy.value.ElementValue` 로 변환한다
      (:func:`~mdtpy.value.parse_json_node`).
    * ``@type`` 이 ``mdt:ref:`` 로 시작하면 :class:`~mdtpy.ref.ElementReference` 로 변환한다
      (:func:`~mdtpy.ref.parse_reference_json_node`; 전역 ``mdt_manager`` 연결이 필요하다).
    * ``@type`` 이 없고 ``modelType`` 필드를 가지면 basyx 모델 직렬화 형식으로 보고
      :class:`~basyx.aas.model.SubmodelElement` 로 변환한다 (:func:`basyx_serde.from_dict`).
    * ``@type`` 도 ``modelType`` 도 없는 ``dict`` 는 그대로 반환한다.

    Args:
        arg_json_node (Any): 변환할 인자 JSON 노드.
    Returns:
        타입 태그에 따라 변환된 객체(``ElementValue`` / ``ElementReference`` /
        ``SubmodelElement``), 또는 변환 대상이 아닌 경우 입력 노드 그대로.
    Raises:
        ValueError: ``@type`` 이 있으나 ``mdt:value:`` / ``mdt:ref:`` 어느 접두어에도
            해당하지 않는 알 수 없는 타입인 경우.
    """

    # dict 형식이 아니면 int, float, str 등 스칼라 값이므로 그대로 반환한다.
    if not isinstance(arg_json_node, dict):
        return arg_json_node

    #
    # '@type' 필드의 존재 여부과 값에 따라 적절한 파서로 분배한다.
    #
    type_str = arg_json_node.get('@type')
    if type_str is None:
        type_str = arg_json_node.get('modelType')
        if type_str is None:
            # '@type' 도 'modelType' 도 없으면 raw 객체로 간주하고 그대로 반환한다.
            return arg_json_node
        else:
            # 'modelType' 이 있으면 basyx 모델 직렬화 형식으로 간주하고
            # SubmodelElement로 변환한다.
            return basyx_serde.from_dict(arg_json_node)
    else:
        # '@type' 이 있으면 mdtpy 형식으로 간주하고 접두어에 따라 분배한다.
        if type_str.startswith('mdt:value:'):
            return parse_value_json_node(arg_json_node)
        elif type_str.startswith('mdt:ref:'):
            return parse_reference_json_node(arg_json_node)
        else:
            raise ValueError(f"Unknown output type: {type_str}")


def to_argument_json_node(arg: ArgumentType) -> Any:
    """연산 인자 하나를 JSON 직렬화용 노드로 변환한다.

    Args:
        arg (ArgumentType): 변환할 연산 인자.
    Returns:
        JSON 직렬화용 노드(dict, list, str, int, float 등).
    Raises:
        ValueError: 알 수 없는 타입의 인자인 경우.
    """
    if isinstance(arg, ElementValue):
        return arg.to_json_node()
    elif isinstance(arg, ElementReference):
        return arg.to_json_node()
    elif isinstance(arg, model.SubmodelElement):
        return json.loads(basyx_serde.to_json(arg))
    elif isinstance(arg, (dict, list, str, int, float)):
        return arg
    else:
        raise ValueError(f"Unknown argument type: {type(arg).__name__}")
