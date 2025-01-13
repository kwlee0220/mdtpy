from __future__ import annotations

from typing import Any, Optional
from dataclasses import asdict, dataclass, field
from enum import Enum

from datetime import timedelta
import time
import requests
import json
from dataclasses_json import dataclass_json
from urllib import parse
import urllib3
urllib3.disable_warnings()

from .http_client import to_base64_string, parse_none_response, parse_response
from .http_fa3st_client import HttpFa3stClient
from mdtpy.model import InstanceSubmodelDescriptor, ElementReferenceCollection, ElementReference, DefaultElementReference, \
                        AssetAdministrationShell, AssetAdministrationShellService, Endpoint, \
                        Submodel, SubmodelElement, SubmodelElementList, \
                        OperationVariable, OperationResult, OperationRequest, OperationHandle, \
                        AssetInformation, Reference, ProtocolInformation, \
                        SubmodelService, InformationModelService, DataService, OperationService, AIService, SimulationService, \
                        MDTFile, TwinComposition, ElementValue, \
                        OperationError, CancellationError


class HttpAssetAdministrationShellServiceClient(HttpFa3stClient, AssetAdministrationShellService):
    def __init__(self, url:str) -> None:
        super().__init__()
        self.base_url = url
        
    def getAssetAdministrationShell(self) -> AssetAdministrationShell:
        url = f"{self.base_url}"
        resp = requests.get(url, verify=False)
        return self.parse_response(AssetAdministrationShell, resp)
    
    def putAssetAdministrationShell(self, aas:AssetAdministrationShell) -> AssetAdministrationShell:
        url = f"{self.base_url}"
        resp = requests.put(url, data=asdict(aas), verify=False)
        return self.parse_response(AssetAdministrationShell, resp)
    
    def getAssetInformation(self) -> AssetInformation:
        url = f"{self.base_url}/asset-information"
        resp = requests.get(url, verify=False)
        return self.parse_response(AssetInformation, resp)
        
    def putAssetInformation(self, assetInfo:AssetInformation) -> AssetInformation:
        url = f"{self.base_url}/asset-information"
        resp = requests.put(url, data=asdict(assetInfo), verify=False)
        return self.parse_response(AssetInformation, resp)
    
    def getAllSubmodelReferences(self) -> list[Reference]:
        url = f"{self.base_url}/submodels"
        resp = requests.get(url, verify=False)
        return self.parse_response(Reference, resp)
    
    def postSubmodelReference(self, ref:Reference) -> Reference:
        url = f"{self.base_url}/submodels"
        resp = requests.post(url, data=asdict(ref), verify=False)
        return self.parse_response(Reference, resp)
    
    def deleteSubmodelReference(self, submodelId:str) -> None:
        url = f"{self.base_url}/submodels/{self.to_base64_string(submodelId)}"
        resp = requests.delete(url, verify=False)
        parse_none_response(resp)
    
    
class HttpSubmodelServiceClient(HttpFa3stClient, SubmodelService):
    def __init__(self, instance_id:str, sm_desc:InstanceSubmodelDescriptor, url:str) -> None:
        super().__init__()
        self.instance_id = instance_id
        self._endpoint = url
        self.sm_desc = sm_desc
        self.base_url = url
    
    @property
    def id(self) -> str:
        return self.sm_desc.id
    
    @property
    def idShort(self) -> str:
        return self.sm_desc.idShort
    
    @property
    def semanticId(self) -> Reference:
        return self.sm_desc.semanticId
        
    @property
    def endpoint(self) -> Endpoint:
        return Endpoint(interface="SUBMODEL",
                        protocolInformation=ProtocolInformation(href=self._endpoint, endpointProtocol="HTTP",
                                                                endpointProtocolVersion="1.1"))
        
    def getSubmodel(self) -> Submodel:
        url = f"{self.base_url}"
        resp = requests.get(url, verify=False)
        return self.parse_response(Submodel, resp)
    
    def putSubmodel(self, submodel:Submodel) -> Submodel:
        url = f"{self.base_url}"
        resp = requests.put(url, data=asdict(submodel), verify=False)
        return self.parse_response(Submodel, resp)
    
    def getSubmodelElementByPath(self, path:str) -> SubmodelElement:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}"
        resp = requests.get(url, verify=False)
        return self.parse_response(SubmodelElement, resp)
    
    def getAllSubmodelElements(self) -> list[SubmodelElement]:
        url = f"{self.base_url}/submodel-elements"
        resp = requests.get(url, verify=False)
        return self.parse_list_response(SubmodelElement, resp)
    
    def postSubmodelElement(self, element:SubmodelElement) -> SubmodelElement:
        url = f"{self.base_url}/submodel-elements"
        resp = requests.post(url, data=asdict(element), verify=False)
        return self.parse_response(SubmodelElement, resp)
    
    def postSubmodelElementByPath(self, path:str, element:SubmodelElement) -> SubmodelElement:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}"
        resp = requests.post(url, data=asdict(element), verify=False)
        return self.parse_response(SubmodelElement, resp)
    
    def putSubmodelElementByPath(self, path:str, element:SubmodelElement) -> SubmodelElement:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}"
        dict_obj = element.to_json_obj()
        req_body = json.dumps(dict_obj, ensure_ascii=False)
        
        resp = requests.put(url, data=req_body, verify=False)
        return self.parse_response(SubmodelElement, resp)
    
    def patchSubmodelElementValueByPath(self, path:str, value:ElementValue|str|dict[str,Any]) -> None:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}/$value"
        if isinstance(value, ElementValue):
            req_body = json.dumps(value.to_json_object(), ensure_ascii=False)
        elif isinstance(value, str):
            req_body = value
        elif isinstance(value, dict):
            req_body = json.dumps(value, ensure_ascii=False)
        else:
            raise ValueError(f'Invalid ElementValue: {value}')
        resp = requests.patch(url, data=req_body, verify=False)
        self.parse_none_response(resp)
        
    def deleteSubmodelElementByPath(self, path:str) -> None:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}"
        resp = requests.delete(url, verify=False)
        self.parse_none_response(resp)
        
    def getFileContentByPath(self, path:str) -> tuple[str, bytes]:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}/attachment"
        resp = requests.get(url, verify=False)
        return self.parse_response(bytes, resp)
    
    def putFileByPath(self, path:str, file:MDTFile) -> None:
        from pathlib import Path
        from requests_toolbelt.multipart.encoder import MultipartEncoder
        
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}/attachment"
        file_path = Path(file.file_path)
        m = MultipartEncoder(
            fields={
                'fileName': file_path.name,
                'contentType': file.content_type,
                'content': ('filename', open(file_path, 'rb'), file.content_type)
            }
        )
        requests.put(url, data=m, headers={'Content-Type': m.content_type}, verify=False)
        
    def deleteFileByPath(self, path:str) -> None:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}/attachment"
        requests.delete(url, verify=False)
        
    def invokeOperationSync(self, path:str, inputArguments:list[OperationVariable],
                            inoutputArguments:list[OperationVariable], timeout:timedelta) -> OperationResult:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}/invoke"
        req = OperationRequest(inoutputArguments=inoutputArguments, inputArguments=inputArguments,
                               clientTimeoutDuration=timeout)
        resp = requests.post(url, data=asdict(req), verify=False)
        return self.parse_response(OperationResult, resp)
        
    def invokeOperationAsync(self, path:str, inputArguments:list[OperationVariable],
                            inoutputArguments:list[OperationVariable], timeout:timedelta) -> OperationHandle:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}/invoke?async=true"
        req = OperationRequest(inoutputArguments=inoutputArguments, inputArguments=inputArguments,
                               clientTimeoutDuration=timeout)
        resp = requests.post(url, data=asdict(req), verify=False)
        return self.parse_response(OperationHandle, resp)
    
    def getOperationAsyncResult(self, path:str, handle:OperationHandle) -> OperationResult:
        url = f"{self.base_url}/submodel-elements/{parse.quote(path)}/operation-results/{handle.handleId}"
        resp = requests.get(url, verify=False)
        return self.parse_response(OperationResult, resp)
    
        
class InformationModelServiceClient(HttpSubmodelServiceClient, InformationModelService): 
    def __init__(self, instance_id:str, sm_desc:InstanceSubmodelDescriptor, url:str) -> None:
        super().__init__(instance_id, sm_desc, url)

    @property
    def twinComposition(self) -> TwinComposition:
        element = self.getSubmodelElementByPath('TwinComposition')
        return TwinComposition.from_element(element)
    

class DataSubmodelServiceClient(HttpSubmodelServiceClient, DataService):
    def __init__(self, instance_id:str, sm_desc:InstanceSubmodelDescriptor, url:str, asset_type:str) -> None:
        super().__init__(instance_id=instance_id, sm_desc=sm_desc, url=url)
        self._asset_type = asset_type
        
        self._parameters = ElementReferenceCollection()
        pvalues = self.getSubmodelElementByPath(f'DataInfo.{asset_type}.{asset_type}ParameterValues')
        if not isinstance(pvalues, SubmodelElementList):
            raise ValueError(f'Unexpected SubmodelElement type (not SubmodelElementList): {pvalues.__class__}')
        for index, param in enumerate(pvalues.value):
            key:str = next(field.value for field in param.value if field.idShort == 'ParameterID')
            path = f'DataInfo.{asset_type}.{asset_type}ParameterValues[{index}].ParameterValue'
            self._parameters.append(key, DefaultElementReference(self, path))
            
    @property
    def asset_type(self) -> str:
        return self._asset_type
        
    @property
    def parameters(self) -> ElementReferenceCollection:
        return self._parameters


@dataclass_json
@dataclass(frozen=True, unsafe_hash=True, slots=True)
class OperationArgument:
    name: str
    reference: ElementReference

    
@dataclass_json
@dataclass(slots=True)
class OperationRequestBody:
    parameters: list[OperationArgument] = field(default_factory=lambda: [])
    outputNames: set[str] = field(default_factory=lambda: set())
    

class OperationStatus(Enum):
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'
    
@dataclass_json
@dataclass
class OperationResponse:
    session: str
    status: OperationStatus
    outputValueString: Optional[str] = field(default=None)
    message: Optional[str] = field(default=None)

class OperationServiceClient(HttpSubmodelServiceClient, OperationService):
    def __init__(self, instance_id:str, sm_desc:InstanceSubmodelDescriptor, url:str, op_type:str) -> None:
        super().__init__(instance_id=instance_id, sm_desc=sm_desc, url=url)
        
        self.idshort = self.idShort
        self._inputs = ElementReferenceCollection()
        input_list = self.getSubmodelElementByPath(f'{op_type}Info.Inputs')
        if not isinstance(input_list, SubmodelElementList):
            raise ValueError(f'Unexpected SubmodelElement type (not SubmodelElementList): {input_list.__class__}')
        for index, arg in enumerate(input_list.value):
            key:str = next(field.value for field in arg.value if field.idShort == 'InputID')
            path = f'{op_type}Info.Inputs[{index}].InputValue'
            self._inputs.append(key, DefaultElementReference(self, path))
        
        self._outputs = ElementReferenceCollection()
        output_list = self.getSubmodelElementByPath(f'{op_type}Info.Outputs')
        if not isinstance(output_list, SubmodelElementList):
            raise ValueError(f'Unexpected SubmodelElement type (not SubmodelElementList): {output_list.__class__}')
        for index, arg in enumerate(output_list.value):
            key:str = next(field.value for field in arg.value if field.idShort == 'OutputID')
            path = f'{op_type}Info.Outputs[{index}].OutputValue'
            self._outputs.append(key, DefaultElementReference(self, path))
        
    @property
    def inputs(self) -> ElementReferenceCollection:
        return self._inputs
        
    @property
    def outputs(self) -> ElementReferenceCollection:
        return self._outputs
    
    def __call__(self, server:str, op_id:Optional[str]=None, sync:bool=False, poll_interval:float=1, timeout:Optional[float]=None, **kwargs) -> None:
        if not op_id:
            op_id = f'{self.instance_id}/{self.idshort}'
        op_id_encoded = to_base64_string(op_id)
        
        sync_call = 'sync' if sync else 'async'
        url = f"{server}/operations/{op_id_encoded}/{sync_call}"
        
        in_args = { key[3:]:ref for key, ref in kwargs.items() if key.startswith('in_') }
        out_args = { key[4:]:ref for key, ref in kwargs.items() if key.startswith('out_') }
        
        body = OperationRequestBody()
        body.parameters = [ OperationArgument(key, ref.to_json_object()) for key, ref in (in_args | out_args).items() ]
        body.outputNames = { key for key, _ in out_args.items() }
        
        body_json = json.dumps(body.to_dict())
        resp = requests.post(url, data=body_json)
        op_resp:OperationResponse = parse_response(OperationResponse, resp)
        
        if op_resp.status == OperationStatus.RUNNING and sync_call == 'async':
            status_url = f"{server}/sessions/{to_base64_string(op_resp.session)}"
            op_resp = self.wait_for_finished(status_url, poll_interval, timeout)
            
        match op_resp.status:
            case OperationStatus.COMPLETED:
                return
            case OperationStatus.FAILED:
                raise OperationError(op_resp.message)
            case OperationStatus.CANCELLED:
                raise CancellationError()
    
    def wait_for_finished(self, status_url:str, poll_interval:float=1.0, timeout:Optional[float]=None) -> OperationResponse:
        started = time.time()
        due = started + timeout if timeout else None
        next_wakeup = started + poll_interval
        
        while True:
            resp = requests.get(url=status_url)
            op_resp = parse_response(OperationResponse, resp)
            if op_resp.status != OperationStatus.RUNNING:
                return op_resp
            
            now = time.time()
            if due and due - now < 0.01:
                raise TimeoutError(f'timeout={timeout}')
            
            sleep_time = next_wakeup - now
            if sleep_time > 0.001:
                time.sleep(sleep_time)
            next_wakeup += poll_interval

class AIServiceClient(OperationServiceClient, AIService):
    def __init__(self, instance_id:str, sm_desc:InstanceSubmodelDescriptor, url:str) -> None:
        super().__init__(instance_id, sm_desc, url, 'AI')
        
class SimulationServiceClient(OperationServiceClient, SimulationService): 
    def __init__(self, instance_id:str, sm_desc:InstanceSubmodelDescriptor, url:str) -> None:
        super().__init__(instance_id, sm_desc, url, 'Simulation')