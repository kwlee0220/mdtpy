from __future__ import annotations

from dataclasses import asdict

import requests

from ..model.aas_registry import *
from .http_client import to_base64_string, parse_none_response, parse_response, parse_list_response


class HttpAssetAdministrationShellRegistryClient(AssetAdministrationShellRegistry):
    def __init__(self, endpoint:str) -> None:
        super().__init__()
        self.endpoint = endpoint
    
    def getAssetAdministrationShellDescriptorById(self, id:str) -> AssetAdministrationShellDescriptor:
        url = f"{self.endpoint}/{to_base64_string(id)}"
        resp = requests.get(url)
        return parse_response(AssetAdministrationShellDescriptor, resp)
        
    def getAllAssetAdministrationShellDescriptors(self) -> list[AssetAdministrationShellDescriptor]:
        url = f"{self.endpoint}"
        resp = requests.get(url)
        return parse_list_response(AssetAdministrationShellDescriptor, resp)
    
    def getAllAssetAdministrationShellDescriptorsByIdShort(self, idShort:str) \
        -> list[AssetAdministrationShellDescriptor]:
        url = f"{self.endpoint}/idShort={idShort}"
        resp = requests.get(url)
        return parse_list_response(AssetAdministrationShellDescriptor, resp)
    
    def postAssetAdministrationShellDescriptor(self, descriptor:AssetAdministrationShellDescriptor) \
        -> AssetAdministrationShellDescriptor:
        url = f"{self.endpoint}"
        resp = requests.post(url, data=asdict(descriptor))
        return parse_response(AssetAdministrationShellDescriptor, resp)
    
    def putAssetAdministrationShellDescriptorById(self, descriptor:AssetAdministrationShellDescriptor) \
        -> AssetAdministrationShellDescriptor:
        url = f"{self.endpoint}/{to_base64_string(descriptor.id)}"
        resp = requests.put(url, data=asdict(descriptor))
        return parse_response(AssetAdministrationShellDescriptor, resp)
    
    def deleteAssetAdministrationShellDescriptorById(self, id:str) -> None:
        url = f"{self.endpoint}/{to_base64_string(id)}"
        resp = requests.delete(url)
        return parse_none_response(resp)


class HttpSubmodelRegistryClient(SubmodelRegistry):
    def __init__(self, endpoint:str) -> None:
        super().__init__()
        self.endpoint = endpoint
        
    def getSubmodelDescriptorById(self, submodel_id:str) -> SubmodelDescriptor:
        url = f"{self.endpoint}/{to_base64_string(submodel_id)}"
        resp = requests.get(url)
        return parse_response(SubmodelDescriptor, resp)
    
    def getAllSubmodelDescriptorsByIdShort(self, idShort:str) -> list[SubmodelDescriptor]:
        url = f"{self.endpoint}/idShort={idShort}"
        resp = requests.get(url)
        return parse_list_response(SubmodelDescriptor, resp)
        
    def getAllSubmodelDescriptors(self) -> list[SubmodelDescriptor]:
        url = f"{self.endpoint}"
        resp = requests.get(url)
        return parse_list_response(SubmodelDescriptor, resp)
        
    def postSubmodelDescriptor(self, submodel:SubmodelDescriptor) -> SubmodelDescriptor:
        url = f"{self.endpoint}"
        resp = requests.post(url, data=asdict(submodel))
        return parse_response(SubmodelDescriptor, resp)
        
    def putSubmodelDescriptorById(self, submodel:SubmodelDescriptor) -> SubmodelDescriptor:
        url = f"{self.endpoint}/{to_base64_string(submodel.id)}"
        resp = requests.put(url, data=asdict(submodel))
        return parse_response(SubmodelDescriptor, resp)
        
    def removeSubmodelDescriptorById(self, submodelId:str) -> None:
        url = f"{self.endpoint}/{to_base64_string(submodelId)}"
        resp = requests.delete(url)
        return parse_none_response(resp)
        