from __future__ import annotations

from typing import Any, Optional, Iterable
from enum import Enum, auto

import json
import datetime
from dataclasses import dataclass, field
from dataclass_wizard import JSONWizard

from basyx.aas import model
from .basyx import serde as basyx_serde
from . import utils


class SecurityTypeEnum(Enum):
    """AAS Endpoint의 보안 속성 종류."""

    NONE = auto()
    RFC_TLSA = auto()
    W3C_DID = auto()


@dataclass(slots=True)
class SecurityAttributeObject(JSONWizard):
    """
    AAS Endpoint에 부여되는 보안 속성 단위.

    Attributes:
        type (SecurityTypeEnum): 보안 속성 종류.
        key (str): 속성 키.
        value (str): 속성 값.
    """
    type: SecurityTypeEnum
    key: str
    value: str


@dataclass(slots=True)
class ProtocolInformation:
    """
    AAS Endpoint의 프로토콜 정보를 나타내는 wire 포맷.

    필드 이름이 camelCase인 것은 서버(JSON) 표기를 그대로 따른 것이다.

    Attributes:
        href (Optional[str]): 엔드포인트 URL.
        endpointProtocol (Optional[str]): 프로토콜 이름 (예: "HTTP").
        endpointProtocolVersion (Optional[str]): 프로토콜 버전 (예: "1.1").
        subprotocol (Optional[str]): 서브프로토콜 이름.
        subprotocolBody (Optional[str]): 서브프로토콜 본문.
        subprotocolBody_encoding (Optional[str]): 서브프로토콜 본문 인코딩.
        securityAttributes (list[SecurityAttributeObject]): 보안 속성 목록.
    """
    href: Optional[str]
    endpointProtocol: Optional[str] = field(default=None)
    endpointProtocolVersion: Optional[str] = field(default=None)
    subprotocol: Optional[str] = field(default=None)
    subprotocolBody: Optional[str] = field(default=None)
    subprotocolBody_encoding: Optional[str] = field(default=None)
    securityAttributes: list[SecurityAttributeObject] = field(default_factory=list)


@dataclass(slots=True)
class Endpoint:
    """
    AAS Endpoint (interface + protocolInformation 묶음).

    Attributes:
        interface (str): 인터페이스 식별자 (예: "SUBMODEL").
        protocolInformation (ProtocolInformation): 접속 프로토콜 정보.
    """
    interface: str
    protocolInformation: ProtocolInformation


@dataclass(slots=True)
class OperationVariable:
    """
    AAS Operation의 입력/출력/입출력 변수를 감싸는 컨테이너.

    내부적으로는 basyx의 `model.SubmodelElement`를 그대로 들고 있으며,
    JSON 변환은 `basyx_serde`에 위임한다.

    Attributes:
        value (model.SubmodelElement): 변수의 값을 담은 SubmodelElement.
    """
    value: model.SubmodelElement

    @classmethod
    def from_dict(cls, data: dict) -> OperationVariable:
        """
        JSON 객체에서 OperationVariable을 만든다.

        Args:
            data (dict): `{'value': <SubmodelElement JSON>}` 형식의 dict.
        Returns:
            OperationVariable: basyx로 역직렬화된 변수 객체.
        """
        return cls(value=basyx_serde.from_dict(data['value']))

    def to_dict(self) -> dict[str, Any]:
        """
        JSON 직렬화 가능한 dict로 변환한다.

        Returns:
            dict[str, Any]: `{'value': <SubmodelElement JSON dict>}`.
        """
        return {'value': json.loads(basyx_serde.to_json(self.value))}


@dataclass(slots=True)
class OperationResult:
    """
    AAS Operation 호출 결과.

    Attributes:
        messages (Optional[list[str]]): 서버가 반환한 메시지 목록.
        execution_state (str): 실행 상태 ("Completed", "Failed" 등).
        success (bool): 성공 여부.
        output_op_variables (Optional[list[OperationVariable]]): 출력 인자 변수.
        inoutput_op_variables (Optional[list[OperationVariable]]): 입출력 인자 변수.
    """
    messages: Optional[list[str]]
    execution_state: str
    success: bool
    output_op_variables: Optional[list[OperationVariable]]
    inoutput_op_variables: Optional[list[OperationVariable]]

    @classmethod
    def from_dict(cls, data: dict) -> OperationResult:
        """
        서버 JSON 응답에서 OperationResult를 구성한다.

        서버 키 `outputArguments` / `inoutputArguments`를 OperationVariable
        목록으로 변환한다.

        Args:
            data (dict): JSON으로 파싱된 응답 본문.
        Returns:
            OperationResult: 변환된 결과 객체.
        """
        output_arguments = data.get('outputArguments')
        if output_arguments:
            output_arguments = [OperationVariable.from_dict(arg) for arg in output_arguments]
        inoutput_arguments = data.get('inoutputArguments')
        if inoutput_arguments:
            inoutput_arguments = [OperationVariable.from_dict(arg) for arg in inoutput_arguments]

        return cls(
            messages=data.get('messages'),
            execution_state=data['executionState'],
            success=data['success'],
            output_op_variables=output_arguments,
            inoutput_op_variables=inoutput_arguments,
        )

    @classmethod
    def from_json(cls, json_str: str) -> OperationResult:
        """JSON 문자열로부터 OperationResult를 구성한다."""
        return cls.from_dict(json.loads(json_str))


@dataclass(slots=True)
class OperationHandle:
    """
    비동기 Operation 호출이 반환하는 핸들.

    Attributes:
        handle_id (str): 서버가 발급한 비동기 작업 식별자.
    """
    handle_id: str

    @classmethod
    def from_json(cls, json_str: str) -> OperationHandle:
        """
        JSON 문자열에서 OperationHandle을 만든다.

        서버는 `handleId` 키(camelCase)를 사용하므로 그에 맞춰 매핑한다.

        Args:
            json_str (str): `{"handleId": "..."}` 형식의 JSON.
        Returns:
            OperationHandle: 핸들 객체.
        """
        json_dict = json.loads(json_str)
        return cls(handle_id=json_dict['handleId'])


@dataclass(slots=True)
class OperationRequest:
    """
    AAS Operation 호출 요청 본문.

    Attributes:
        input_arguments (Iterable[OperationVariable]): 입력 인자 변수 목록.
        inoutput_arguments (Iterable[OperationVariable]): 입출력 인자 변수 목록.
        client_timeout_duration (datetime.timedelta): 클라이언트 측 타임아웃.
            JSON 직렬화 시 ISO 8601 duration 문자열로 변환된다.
    """
    input_arguments: Iterable[OperationVariable]
    inoutput_arguments: Iterable[OperationVariable]
    client_timeout_duration: datetime.timedelta

    def to_json(self) -> str:
        """
        요청 본문을 JSON 문자열로 직렬화한다.

        현재 fa3st 서버는 `inputArguments`만 인식하므로 `inoutputArguments`는
        직렬화에서 제외한다. (필요 시 아래 주석을 해제하여 포함시킬 수 있다.)

        Returns:
            str: JSON 문자열.
        """
        in_opv_list = [op_var.to_dict() for op_var in self.input_arguments]
        return json.dumps({
            'inputArguments': in_opv_list,
            # 'inoutputArguments': [op_var.to_dict() for op_var in self.inoutput_arguments],
            'clientTimeoutDuration': utils.timedelta_to_iso8601(self.client_timeout_duration),
        })
