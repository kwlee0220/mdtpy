from __future__ import annotations

from typing import Any, Dict
import json

from basyx.aas.adapter.json.json_deserialization import AASFromJsonDecoder
from basyx.aas.adapter.json.json_serialization import AASToJsonEncoder


class _MDTFromJsonDecoder(AASFromJsonDecoder):
  """FA³ST 서버 응답을 basyx 모델로 역직렬화하는 디코더.

  FA³ST는 SubmodelElementList의 자식 요소를 idShort=""(빈 문자열)로 직렬화하지만,
  AAS 메타모델에서 리스트 자식은 idShort를 가질 수 없다. basyx의 validate_id_short가
  빈 문자열을 ValueError로 거부하고, 이 ValueError는 basyx의 failsafe 처리에서도
  잡히지 않으므로, 역직렬화 전에 빈 idShort 항목을 제거한다.
  """
  @classmethod
  def _amend_abstract_attributes(cls, obj: object, dct: Dict[str, object]) -> None:
    if dct.get('idShort') == '':
      dct = {k: v for k, v in dct.items() if k != 'idShort'}
    super()._amend_abstract_attributes(obj, dct)


def from_json(json_str:str) -> Any:
  return json.loads(json_str, cls=_MDTFromJsonDecoder)

def from_dict(data:dict) -> Any:
  json_str = json.dumps(data)
  return json.loads(json_str, cls=_MDTFromJsonDecoder)

def to_json(obj:Any) -> str:
  return json.dumps(obj, cls=AASToJsonEncoder)