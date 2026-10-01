from __future__ import annotations

from basyx.aas import model
from .. import ElementReference, ElementValue

__all__ = [ 'ArgumentValue', 'TaskOutput' ]

# 오퍼레이터 호출에 사용되는 인자 값의 타입을 정의한다.
ArgumentValue = ElementValue|ElementReference|model.SubmodelElement

# 오퍼레이터 호출로 반환되는 출력 값의 타입을 정의한다.
TaskOutput = ElementValue