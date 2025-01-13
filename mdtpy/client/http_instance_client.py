from __future__ import annotations

from typing import Optional, Generator, cast
from collections.abc import Iterator

import requests

from mdtpy.model import MDTInstanceManager, MDTInstance, MDTInstanceCollection, InstanceDescriptor, InstanceSubmodelDescriptor, \
                        MDTInstanceStatus, SubmodelServiceCollection, OperationSubmodelServiceCollection, MDT_SEMANTIC_ID, \
                        InvalidResourceStateError, ResourceNotFoundError
                        
from .utils import StatusPoller
from .http_registry_client import HttpAssetAdministrationShellRegistryClient, HttpSubmodelRegistryClient
from .http_service_client import HttpAssetAdministrationShellServiceClient, HttpSubmodelServiceClient
from .http_repository_client import *
from .http_client import to_base64_string, parse_none_response, parse_response, parse_list_response, extract_href
    
    
def connect(host:str='localhost', port:int=12985, path:str='/instance-manager') -> HttpMDTManagerClient:
    endpoint = f"http://{host}:{port}{path}"
    return HttpMDTManagerClient(endpoint)


class HttpMDTManagerClient(MDTInstanceManager):
    def __init__(self, endpoint:str) -> None:
        super().__init__()
        
        self.endpoint = endpoint
        self._instances = HttpInstanceCollection(self, endpoint)
        self.endpoint_base = '/'.join(endpoint.split('/')[:-1])

    @property
    def instances(self) -> HttpInstanceCollection:
        return self._instances
        
    def getAssetAdministrationShellRegistry(self) -> HttpAssetAdministrationShellRegistryClient:
        return HttpAssetAdministrationShellRegistryClient(self.endpoint_base + "/shell-registry/shell-descriptors")
    
    def getSubmodelRegistry(self) -> HttpSubmodelRegistryClient:
        return HttpSubmodelRegistryClient(self.endpoint_base + "/shell-registry/submodel-descriptors")
        
    def getAssetAdministrationShellService(self, aasId:str) -> HttpAssetAdministrationShellServiceClient:
        eps = self.getAssetAdministrationShellRegistry() \
                    .getAssetAdministrationShellDescriptorById(aasId) \
                    .endpoints
        href = extract_href(eps)
        if href:
            return HttpAssetAdministrationShellServiceClient(href)
        else:
            raise InvalidResourceStateError.create("AssetAdministrationShell", f"id={aasId}")
        
    def getSubmodelService(self, submodelId:str, serviceClass=None) -> SubmodelService:
        eps = self.getSubmodelRegistry() \
                    .getSubmodelDescriptorById(submodelId) \
                    .endpoints
        href = extract_href(eps)
        if href:
            return serviceClass(href) if serviceClass else HttpSubmodelServiceClient(href)
        else:
            raise InvalidResourceStateError.create("Submodel", f"id={submodelId}")


class HttpInstanceCollection(MDTInstanceCollection):
    def __init__(self, inst_mgr:HttpMDTManagerClient, endpoint:str):
        self.url_prefix = f"{endpoint}/instances"
        self.instance_manager = inst_mgr
    
    def __bool__(self):
        resp = requests.get(self.url_prefix)
        return len(parse_list_response(InstanceDescriptor, resp)) > 0
    
    def __len__(self):
        resp = requests.get(self.url_prefix)
        return len(parse_list_response(InstanceDescriptor, resp))
        
    def __iter__(self) -> Iterator[HttpInstanceClient]:
        resp = requests.get(self.url_prefix)
        inst_desc_list = parse_list_response(InstanceDescriptor, resp)
        return iter(HttpInstanceClient(self, self.instance_manager, inst_desc) for inst_desc in inst_desc_list)
    
    def __contains__(self, key:str) -> bool:
        url = f'{self.url_prefix}/{key}'
        resp = requests.get(url)
        return resp.status_code == 200
        
    def __getitem__(self, key:str) -> HttpInstanceClient:
        url = f'{self.url_prefix}/{key}'
        resp = requests.get(url)
        inst_desc = parse_response(InstanceDescriptor, resp)
        return HttpInstanceClient(self.instance_manager, self.url_prefix, inst_desc)
    
    def __setitem__(self, key:str, value:HttpInstanceClient) -> None:
        raise NotImplementedError('HttpInstanceCollection does not support set operation')
    
    def __delitem__(self, key:str) -> None:
        url = f'{self.url_prefix}/{key}'
        resp = requests.delete(url)
        parse_none_response(resp)
    
    def find(self, condition:str) -> Generator[HttpInstanceClient, None, None]:
        resp = requests.get(self.url_prefix, params={'filter': f"{condition}"})
        inst_desc_list = parse_list_response(InstanceDescriptor, resp)
        return (HttpInstanceClient(self, inst_desc) for inst_desc in inst_desc_list)
    
    def add(self, id:str, port:int, inst_dir:str) -> HttpInstanceClient:
        import shutil
        shutil.make_archive(inst_dir, 'zip', inst_dir)
        zipped_file = f'{inst_dir}.zip'
        
        from requests_toolbelt.multipart.encoder import MultipartEncoder
        m = MultipartEncoder(
            fields = {
                'id': id,
                'port': str(port),
                'bundle': ('filename', open(zipped_file, 'rb'), 'application/zip')
            }
        )
        resp = requests.post(self.url_prefix, data=m, headers={'Content-Type': m.content_type}, verify=False)
        inst_desc = parse_response(InstanceDescriptor, resp)
        return HttpInstanceClient(self, inst_desc)
    
    def remove(self, id:str) -> None:
        url = f'{self.url_prefix}/{id}'
        resp = requests.delete(url)
        return parse_none_response(resp)
        
    def remove_all(self) -> None:
        url = f"{self.url_prefix}"
        resp = requests.delete(url)
        parse_none_response(resp)
    
    def __repr__(self):
        return 'HttpMDTInstances(url={self.url_prefix})'
    
    
class InstanceStartPoller(StatusPoller):
    def __init__(self, status_url:str, init_desc:Optional[InstanceDescriptor]=None,
                 poll_interval:float=1.0, timeout:Optional[float]=None) -> None:
        super().__init__(poll_interval=poll_interval, timeout=timeout)
        self.status_url = status_url
        self.desc = init_desc
        
    def check_done(self) -> bool:
        if self.desc.status == MDTInstanceStatus.STARTING.name:
            resp = requests.get(self.status_url)
            self.desc = parse_response(InstanceDescriptor, resp)
            return self.desc.status != MDTInstanceStatus.STARTING.name
        else:
            return True
    
class InstanceStopPoller(StatusPoller):
    def __init__(self, status_url:str, init_desc:Optional[InstanceDescriptor]=None,
                 poll_interval:float=1.0, timeout:Optional[float]=None) -> None:
        super().__init__(poll_interval=poll_interval, timeout=timeout)
        self.status_url = status_url
        self.desc = init_desc
        
    def check_done(self) -> bool:
        if self.desc.status == MDTInstanceStatus.STOPPING.name:
            resp = requests.get(self.status_url)
            self.desc = parse_response(InstanceDescriptor, resp)
            return self.desc.status != MDTInstanceStatus.STOPPING.name
        else:
            return True
    

class HttpInstanceClient(MDTInstance):
    def __init__(self, instance_manager:HttpMDTManagerClient, base_url:str, descriptor:InstanceDescriptor) -> None:
        super().__init__()
        
        self.instance_manager = instance_manager
        self.descriptor = descriptor
        self.base_url = base_url
        self._submodels = HttpSubmodelServiceCollection(self)
         
    @property
    def id(self) -> str:
        return self.descriptor.id
         
    @property
    def aasId(self) -> str:
        return self.descriptor.aasId
         
    @property
    def aasIdShort(self) -> Optional[str]:
        return self.descriptor.aasIdShort
    
    @property
    def status(self) -> MDTInstanceStatus:
        return MDTInstanceStatus[self.descriptor.status]
        
    @property
    def serviceEndpoint(self) -> Optional[str]:
        return self.descriptor.baseEndpoint
    
    @property
    def shell(self) -> HttpAssetAdministrationShellServiceClient:
        return self.instance_manager.getAssetAdministrationShellService(self.aasId)

    @property
    def submodels(self) -> HttpSubmodelServiceCollection:
        return self._submodels
        
    def start(self, nowait=False) -> None:
        url = f"{self.base_url}/{self.id}/start"
        resp = requests.put(url, data="")
        self.descriptor = parse_response(InstanceDescriptor, resp)
        if nowait:
            if self.descriptor.status != MDTInstanceStatus.STARTING.name and MDTInstanceStatus.RUNNING.name:
                raise InvalidResourceStateError.create(f"Failed to start MDTInstance: id={self.id}")
        else:
            poller = InstanceStartPoller(f"{self.base_url}/{self.id}", init_desc=self.descriptor)
            poller.wait_for_done()
            self.descriptor = poller.desc
            if self.descriptor.status != MDTInstanceStatus.RUNNING.name:
                raise InvalidResourceStateError.create(f"Failed to start MDTInstance: id={self.id}")
    
    def stop(self, nowait=False) -> None:
        url = f"{self.base_url}/{self.id}/stop"
        resp = requests.put(url, data="")
        self.descriptor = parse_response(InstanceDescriptor, resp)
        if nowait:
            if self.descriptor.status != MDTInstanceStatus.STOPPING.name and MDTInstanceStatus.STOPPED.name:
                raise InvalidResourceStateError.create(f"Failed to stop MDTInstance: id={self.id}")
        else:
            poller = InstanceStopPoller(f"{self.base_url}/{self.id}", init_desc=self.descriptor)
            poller.wait_for_done()
            self.descriptor = poller.desc
            if self.descriptor.status != MDTInstanceStatus.STOPPED.name:
                raise InvalidResourceStateError.create(f"Failed to stop MDTInstance: id={self.id}")
    
    @property
    def parameters(self) -> ElementReferenceCollection:
        for sm_svc in self.submodels:
            if sm_svc.semanticId == 'https://etri.re.kr/mdt/Submodel/Data/1/1':
                return cast(DataSubmodelServiceClient, sm_svc).parameters
        raise ResourceNotFoundError.create("Data Submodel", 'semanticId=https://etri.re.kr/mdt/Submodel/Data/1/1')
    
    @property
    def operations(self) -> OperationSubmodelServiceCollection:
        return OperationSubmodelServiceCollection(self.submodels)
        
    def __eq__(self, value: object) -> bool:
        if isinstance(value, MDTInstance):
            return self.id == value.id
        else:
            return False
    
    def __repr__(self) -> str:
        return f"MDTInstance[id={self.descriptor.id}, aas-id={self.descriptor.aasId}, " \
                f"aas-id-short={self.descriptor.aasIdShort}, status={self.status}]"


class HttpSubmodelServiceCollection(SubmodelServiceCollection):
    def __init__(self, instance:HttpInstanceClient) -> None:
        super().__init__()
        self.instance = instance

    def __iter__(self) -> Iterator[SubmodelService]:
        return iter(self.createSubmodelService(sm_desc) for sm_desc in self.instance.descriptor.submodels)
    
    def __bool__(self) -> bool:
        return bool(self.instance.descriptor.submodels)
    
    def __len__(self) -> int:
        return len(self.instance.descriptor.submodels)
          
    def __getitem__(self, key:str) -> SubmodelService:
        if isinstance(key, str):
            for sm_desc in self.instance.descriptor.submodels:
                if sm_desc.idShort == key:
                    return self.createSubmodelService(sm_desc)
            raise ResourceNotFoundError.create("Submodel", f'idShort={key}')
        else:
            raise ValueError(f'Invalid Submodel key: {key}')
        
    def __setitem__(self, key:str, value:SubmodelService) -> None:
        raise NotImplementedError('SubmodelServiceCollection does not support set operation')
    
    def __delitem__(self, key:str) -> None:
        raise NotImplementedError('SubmodelServiceCollection does not support delete operation')
    
    def find(self, **kwargs) -> Generator[SubmodelService, None, None]:
        matches:list[InstanceSubmodelDescriptor] = self.instance.descriptor.submodels
        for key, value in kwargs.items():
            match key:
                case 'idShort':
                    matches = [sm_desc for sm_desc in matches if sm_desc.idShort == value]
                case 'semanticId':
                    matches = [sm_desc for sm_desc in matches if sm_desc.semanticId == value]
        return (self.createSubmodelService(sm_desc) for sm_desc in matches)
    
    def __repr__(self):
        return 'SubmodelServiceCollection(instance={self.instance.descriptor.id})'
                
    def createSubmodelService(self, sm_desc:InstanceSubmodelDescriptor) -> SubmodelService:
        if not self.instance.descriptor.baseEndpoint:
            raise ValueError(f'MDTInstance is not ready: id={self.instance.descriptor.id}, state={self.instance.descriptor.status}')
        
        submodel_url = f'{self.instance.descriptor.baseEndpoint}/submodels/{to_base64_string(sm_desc.id)}'
        if sm_desc:
            if sm_desc.semanticId == MDT_SEMANTIC_ID.DATA:
                if self.instance.descriptor.assetType == 'Machine':
                    return DataSubmodelServiceClient(self.instance.descriptor.id, sm_desc, submodel_url, 'Equipment')
                elif self.instance.descriptor.assetType == 'Process':
                    return DataSubmodelServiceClient(submodel_url, sm_desc, 'Operation')
                else:
                    return DataSubmodelServiceClient(self.instance.descriptor.id, sm_desc, submodel_url, 'Equipment')
            elif sm_desc.semanticId == MDT_SEMANTIC_ID.AI:
                return AIServiceClient(self.instance.descriptor.id, sm_desc, submodel_url)
            elif sm_desc.semanticId == MDT_SEMANTIC_ID.SIMULATION:
                return SimulationServiceClient(self.instance.descriptor.id, sm_desc, submodel_url)
            elif sm_desc.semanticId == MDT_SEMANTIC_ID.INFORMATION_MODEL:
                return InformationModelServiceClient(self.instance.descriptor.id, sm_desc, submodel_url)
            else:
                return HttpSubmodelServiceClient(self.instance.descriptor.id, sm_desc, submodel_url)