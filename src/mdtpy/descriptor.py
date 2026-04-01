from __future__ import annotations

from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from dataclass_wizard import JSONWizard


class MDTInstanceStatus(Enum):
  STOPPED = "STOPPED"
  STARTING = "STARTING"
  RUNNING = "RUNNING"
  STOPPING = "STOPPING"
  FAILED = "FAILED"

class MDTAssetType(Enum):
  Machine = "Machine"
  Process = "Process"
  Line = "Line"
  Factory = "Factory"

class AssetKind(Enum):
  INSTANCE = "INSTANCE"
  NOT_APPLICABLE = "NOT_APPLICABLE"
  TYPE = "TYPE"


@dataclass(frozen=True, slots=True)
class InstanceDescriptor(JSONWizard):
  """
  MDTInstance Descriptor

  Attributes:
  ----------
    id: str
      The unique identifier of the MDTInstance.
    status: MDTInstanceStatus
      The Status of the MDTInstance.
    base_endpoint: Optional[str]
      The Base Endpoint of the MDTInstance.
    aas_id: str
      The AAS ID of the MDTInstance.
    aas_idshort: Optional[str]
      The AAS ID Short of the MDTInstance.
    global_asset_id: Optional[str]
      The Global Asset ID of the MDTInstance.
    asset_type: Optional[MDTAssetType]
      The Asset Type of the MDTInstance.
    asset_kind: Optional[AssetKind]
      The Asset Kind of the MDTInstance.
  """
  id: str
  status: MDTInstanceStatus
  aas_id: str
  base_endpoint: Optional[str] = field(default=None, hash=False, compare=False)
  aas_id_short: Optional[str] = field(default=None, hash=False, compare=False)
  global_asset_id: Optional[str] = field(default=None, hash=False, compare=False)
  asset_type: MDTAssetType|None = field(default=None, hash=False, compare=False)
  asset_kind: AssetKind|None = field(default=None, hash=False, compare=False)

@dataclass(frozen=True, slots=True)
class MDTParameterDescriptor(JSONWizard):
  """
  MDTParameter Descriptor

  Attributes:
  ----------
    id: str
      파라미터 식별자.
    value_type: str
      파라미터 값 타입.
    reference: str
      파라미터 참조 문자열.
    name: Optional[str]
      파라미터 이름.
    endpoint: Optional[str]
      파라미터 접속 엔드포인트.
  """
  id: str
  value_type: str
  reference: str
  name: Optional[str] = None
  endpoint: Optional[str] = None


SEMANTIC_ID_INFOR_MODEL_SUBMODEL = "https://etri.re.kr/mdt/Submodel/InformationModel/1/1"
SEMANTIC_ID_AI_SUBMODEL = "https://etri.re.kr/mdt/Submodel/AI/1/1"
SEMANTIC_ID_SIMULATION_SUBMODEL = "https://etri.re.kr/mdt/Submodel/Simulation/1/1"
SEMANTIC_ID_DATA_SUBMODEL = "https://etri.re.kr/mdt/Submodel/Data/1/1"
SEMANTIC_ID_TIME_SERIES_SUBMODEL = 'https://admin-shell.io/idta/TimeSeries/1/1'

@dataclass(frozen=True, slots=True)
class MDTSubmodelDescriptor(JSONWizard):
  """
  MDTSubmodel Descriptor

  Attributes:
  ----------
    id: str
      서브모델 식별자.
    id_short: str
      서브모델 ID Short.
    semantic_id: str
      서브모델 Semantic ID.
    endpoint: Optional[str]
      서브모델 접속 엔드포인트.
  """
  id: str
  id_short: str
  semantic_id: str
  endpoint: Optional[str]

  def is_information_model(self) -> bool:
    return self.semantic_id == SEMANTIC_ID_INFOR_MODEL_SUBMODEL

  def is_data(self) -> bool:
    return self.semantic_id == SEMANTIC_ID_DATA_SUBMODEL

  def is_simulation(self) -> bool:
    return self.semantic_id == SEMANTIC_ID_SIMULATION_SUBMODEL

  def is_ai(self) -> bool:
    return self.semantic_id == SEMANTIC_ID_AI_SUBMODEL

  def is_time_series(self) -> bool:
    return self.semantic_id == SEMANTIC_ID_TIME_SERIES_SUBMODEL


@dataclass(frozen=True, slots=True)
class ArgumentDescriptor(JSONWizard):
  """
  Argument Descriptor

  Attributes:
  ----------
    id: str
      인자 식별자.
    id_short_path: str
      인자 ID Short 경로.
    value_type: str
      인자 값 타입.
    reference: str
      인자 참조 문자열.
  """
  id: str
  id_short_path: str
  value_type: str
  reference: str


@dataclass(frozen=True, slots=True)
class MDTOperationDescriptor(JSONWizard):
  """
  MDTOperation Descriptor

  Attributes:
  ----------
    id: str
      연산 식별자.
    operation_type: str
      연산 타입.
    input_arguments: list[ArgumentDescriptor]
      연산 입력 인자 목록.
    output_arguments: list[ArgumentDescriptor]
      연산 출력 인자 목록.
  """
  id: str
  operation_type: str
  input_arguments: list[ArgumentDescriptor]
  output_arguments: list[ArgumentDescriptor]
