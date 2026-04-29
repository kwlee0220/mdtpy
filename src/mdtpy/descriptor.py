from __future__ import annotations

from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from dataclass_wizard import JSONWizard


class MDTInstanceStatus(Enum):
    """MDTInstance의 생명주기 상태."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class MDTAssetType(Enum):
    """MDTInstance가 표현하는 자산 종류.

    Note:
        값이 PascalCase인 것은 서버 응답에 사용되는 표기를 그대로 따른 것이다.
    """

    Machine = "Machine"
    Process = "Process"
    Line = "Line"
    Factory = "Factory"


class AssetKind(Enum):
    """AAS Asset Kind (instance / type / not-applicable)."""

    INSTANCE = "INSTANCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    TYPE = "TYPE"


@dataclass(frozen=True, slots=True)
class InstanceDescriptor(JSONWizard):
    """
    MDTInstance 등록정보.

    Attributes:
        id (str): MDTInstance의 고유 식별자.
        status (MDTInstanceStatus): MDTInstance의 현재 상태.
        aas_id (str): 연결된 AAS의 ID(URI).
        base_endpoint (Optional[str]): MDTInstance의 베이스 엔드포인트.
        aas_id_short (Optional[str]): 연결된 AAS의 idShort.
        global_asset_id (Optional[str]): 전역 자산 식별자.
        asset_type (Optional[MDTAssetType]): 자산 종류.
        asset_kind (Optional[AssetKind]): AAS Asset Kind.
    """
    id: str
    status: MDTInstanceStatus
    aas_id: str
    base_endpoint: Optional[str] = field(default=None, hash=False, compare=False)
    aas_id_short: Optional[str] = field(default=None, hash=False, compare=False)
    global_asset_id: Optional[str] = field(default=None, hash=False, compare=False)
    asset_type: Optional[MDTAssetType] = field(default=None, hash=False, compare=False)
    asset_kind: Optional[AssetKind] = field(default=None, hash=False, compare=False)


@dataclass(frozen=True, slots=True)
class MDTParameterDescriptor(JSONWizard):
    """
    MDTParameter 등록정보.

    Attributes:
        id (str): 파라미터 식별자.
        value_type (str): 파라미터 값 타입 (XSD 데이터 타입 문자열).
        reference (str): 파라미터 참조 문자열 (`param:<instance>:<param>` 형태).
        name (Optional[str]): 사람이 읽는 파라미터 이름.
        endpoint (Optional[str]): 파라미터 접근 엔드포인트 URL.
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
SEMANTIC_ID_TIME_SERIES_SUBMODEL = "https://admin-shell.io/idta/TimeSeries/1/1"


@dataclass(frozen=True, slots=True)
class MDTSubmodelDescriptor(JSONWizard):
    """
    MDTSubmodel 등록정보.

    semantic_id 값에 따라 InformationModel / Data / Simulation / AI / TimeSeries
    중 하나로 분류된다. 분류는 `is_*()` 메서드로 확인한다.

    Attributes:
        id (str): 서브모델 식별자(URI).
        id_short (str): 서브모델 idShort.
        semantic_id (str): 서브모델 semantic id (URI).
        endpoint (Optional[str]): 서브모델 접근 엔드포인트 URL.
    """
    id: str
    id_short: str
    semantic_id: str
    endpoint: Optional[str]

    def is_information_model(self) -> bool:
        """semantic_id가 Information Model에 해당하면 True를 반환한다."""
        return self.semantic_id == SEMANTIC_ID_INFOR_MODEL_SUBMODEL

    def is_data(self) -> bool:
        """semantic_id가 Data Model에 해당하면 True를 반환한다."""
        return self.semantic_id == SEMANTIC_ID_DATA_SUBMODEL

    def is_simulation(self) -> bool:
        """semantic_id가 Simulation Model에 해당하면 True를 반환한다."""
        return self.semantic_id == SEMANTIC_ID_SIMULATION_SUBMODEL

    def is_ai(self) -> bool:
        """semantic_id가 AI Model에 해당하면 True를 반환한다."""
        return self.semantic_id == SEMANTIC_ID_AI_SUBMODEL

    def is_time_series(self) -> bool:
        """semantic_id가 Time Series Model에 해당하면 True를 반환한다."""
        return self.semantic_id == SEMANTIC_ID_TIME_SERIES_SUBMODEL


@dataclass(frozen=True, slots=True)
class ArgumentDescriptor(JSONWizard):
    """
    Operation 인자(input / inout / output) 등록정보.

    Attributes:
        id (str): 인자 식별자.
        id_short_path (str): 서브모델 내 인자의 idShort 경로
            (예: `Inputs.Speed`, `Out.Result[0]`).
        value_type (str): 인자 값 타입 (XSD 데이터 타입 문자열).
        reference (str): 인자 참조 문자열
            (`oparg:<instance>:<op>:in|out:<arg>` 형태).
    """
    id: str
    id_short_path: str
    value_type: str
    reference: str


@dataclass(frozen=True, slots=True)
class MDTOperationDescriptor(JSONWizard):
    """
    MDTOperation 등록정보.

    Attributes:
        id (str): 연산 식별자.
        operation_type (str): 연산 타입 (예: "sync", "async").
        input_arguments (list[ArgumentDescriptor]): 입력 인자 목록.
        output_arguments (list[ArgumentDescriptor]): 출력 인자 목록.
    """
    id: str
    operation_type: str
    input_arguments: list[ArgumentDescriptor]
    output_arguments: list[ArgumentDescriptor]
