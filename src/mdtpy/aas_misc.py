from __future__ import annotations

from typing import Any, cast, Optional, Iterable
from enum import Enum, auto

import json
import datetime
from dataclasses import dataclass, field
from dataclass_wizard import JSONWizard

from basyx.aas import model
from .basyx import serde as basyx_serde
from . import utils

    
class SecurityTypeEnum(Enum):
  NONE = auto()
  RFC_TLSA = auto()
  W3C_DID = auto()

@dataclass(slots=True)
class SecurityAttributeObject(JSONWizard):
  type: SecurityTypeEnum
  key: str
  value: str

@dataclass(slots=True)
class ProtocolInformation:
  href: Optional[str]
  endpointProtocol: Optional[str] = field(default=None)
  endpointProtocolVersion: Optional[str] = field(default=None)
  subprotocol: Optional[str] = field(default=None)
  subprotocolBody: Optional[str] = field(default=None)
  subprotocolBody_encoding: Optional[str] = field(default=None)
  securityAttributes: list[SecurityAttributeObject] = field(default_factory=list)

@dataclass(slots=True)
class Endpoint:
  interface: str
  protocolInformation: ProtocolInformation

@dataclass(slots=True)
class OperationVariable:
  value: model.SubmodelElement

  @classmethod
  def from_dict(cls, data: dict) -> OperationVariable:
    return cls(value=basyx_serde.from_dict(data['value']))

  def to_dict(self) -> dict[str, Any]:
    return { 'value': json.loads(basyx_serde.to_json(self.value)) }

@dataclass(slots=True)
class OperationResult:
  messages: Optional[list[str]]
  execution_state: str
  success: bool
  output_op_variables: Optional[list[OperationVariable]]
  inoutput_op_variables: Optional[list[OperationVariable]]

  @classmethod
  def from_dict(cls, data: dict) -> OperationResult:
    output_arguments = data.get('outputArguments')
    if output_arguments:
      output_arguments = [OperationVariable.from_dict(arg) for arg in output_arguments]
    inoutput_arguments = data.get('inoutputArguments')
    if inoutput_arguments:
      inoutput_arguments = [OperationVariable.from_dict(arg) for arg in inoutput_arguments]

    return cls(messages = data.get('messages'),
              execution_state = data['executionState'],
              success = data['success'],
              output_op_variables=output_arguments, 
              inoutput_op_variables=inoutput_arguments)
  
  @classmethod
  def from_json(cls, json_str: str) -> OperationResult:
    return cls.from_dict(json.loads(json_str))

@dataclass(slots=True)
class OperationHandle:
  handle_id: str

  @classmethod
  def from_json(cls, json_str: str) -> OperationHandle:
    json_dict = json.loads(json_str)
    return cls(handle_id=json_dict['handleId'])
    
@dataclass(slots=True)
class OperationRequest:
  input_arguments: Iterable[OperationVariable]
  inoutput_arguments: Iterable[OperationVariable]
  client_timeout_duration: datetime.timedelta

  def to_json(self) -> str:
    in_opv_list = [ op_var.to_dict() for op_var in self.input_arguments ]
    inout_opv_list = [ op_var.to_dict() for op_var in self.inoutput_arguments ]
    return json.dumps({
      'inputArguments': in_opv_list,
      # 'inoutputArguments': inout_opv_list,
      'clientTimeoutDuration': utils.timedelta_to_iso8601(self.client_timeout_duration)
    })
