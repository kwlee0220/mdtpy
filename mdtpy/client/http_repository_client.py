from __future__ import annotations

from typing import Any
from dataclasses import asdict

from datetime import timedelta
import requests

from ..model.aas_repository import *
from .http_client import to_base64_string, parse_list_response
from .http_service_client import *


class HttpAssetAdministrationShellRepositoryClient(AssetAdministrationShellRepository):
    def __init__(self, url:str) -> None:
        super().__init__()
        self.endpoint = url
        
    def to_service(self, aasId:str) -> HttpAssetAdministrationShellServiceClient:
        url = f"{self.endpoint}/{to_base64_string(aasId)}"
        return HttpAssetAdministrationShellServiceClient(url)

    def getAllAssetAdministrationShells(self) -> list[HttpAssetAdministrationShellServiceClient]: 
        url = f"{self.endpoint}"
        resp = requests.get(url)
        return [self.to_service(aas.id) for aas in parse_list_response(AssetAdministrationShell, resp)]
    
    def getAssetAdministrationShellById(self, aasId:str) -> HttpAssetAdministrationShellServiceClient:
        return self.to_service(aasId)
        
    def getAssetAdministrationShellByAssetId(self, assetId:str) -> list[HttpAssetAdministrationShellServiceClient]:
        url = f"{self.endpoint}/?assetId={assetId}"
        resp = requests.get(url)
        return [self.to_service(aas.id) for aas in parse_list_response(AssetAdministrationShell, resp)]
        
    def getAssetAdministrationShellByIdShort(self, idShort:str) -> list[HttpAssetAdministrationShellServiceClient]:
        url = f"{self.endpoint}/?idShort={idShort}"
        resp = requests.get(url)
        return [self.to_service(aas.id) for aas in parse_list_response(AssetAdministrationShell, resp)]
    
    def postAssetAdministrationShell(self, aas:AssetAdministrationShell) -> HttpAssetAdministrationShellServiceClient:
        url = f"{self.endpoint}"
        resp = requests.post(url, data=asdict(aas))
        return self.to_service(aas.id)
   
    def updateAssetAdministrationShellById(self, aas:AssetAdministrationShell) -> HttpAssetAdministrationShellServiceClient:
        url = f"{self.endpoint}/{to_base64_string(aas.id)}"
        resp = requests.put(url, data=asdict(aas))
        return self.to_service(aas.id)
    
    def deleteAssetAdministrationShellById(self, aasId:str) -> None:
        url = f"{self.endpoint}/{to_base64_string(aasId)}"
        resp = requests.delete(url)
        parse_none_response(resp)


class HttpSubmodelRepositoryClient(SubmodelRepository):
    def __init__(self, url:str) -> None:
        super().__init__()
        self.endpoint = url
        
    def get_submodel_url(self, submodel_id:str) -> str:
        return f"{self.endpoint}/{to_base64_string(submodel_id)}"
        
    def to_service(self, submodel_id:str) -> HttpSubmodelServiceClient:
        url = f"{self.endpoint}/{to_base64_string(submodel_id)}"
        return HttpSubmodelServiceClient(url)
        
    def getAllSubmodels(self) -> list[HttpSubmodelServiceClient]:
        url = f"{self.endpoint}"
        resp = requests.get(url)
        return [self.to_service(submodel.id) for submodel in parse_list_response(Submodel, resp)]
    
    def getSubmodelById(self, id:str) -> HttpSubmodelServiceClient:
        return self.to_service(id)
    
    def getAllSubmodelBySemanticId(self, semanticId:str) -> list[HttpSubmodelServiceClient]:
        url = f"{self.endpoint}/?semanticId={semanticId}"
        resp = requests.get(url)
        return [self.to_service(aas.id) for aas in parse_list_response(Submodel, resp)]
    
    def getAllSubmodelsByIdShort(self, idShort:str) -> list[HttpSubmodelServiceClient]:
        url = f"{self.endpoint}/?idShort={idShort}"
        resp = requests.get(url)
        return [self.to_service(submodel.id) for submodel in parse_list_response(Submodel, resp)]
    
    def postSubmodel(self, submodel:Submodel) -> HttpSubmodelServiceClient:
        url = f"{self.endpoint}"
        resp = requests.post(url, data=asdict(submodel))
        return self.to_service(submodel.id)
    
    def putSubmodelById(self, submodel:Submodel) -> HttpSubmodelServiceClient:
        url = f"{self.endpoint}/{to_base64_string(submodel.id)}"
        resp = requests.put(url, data=asdict(submodel))
        return self.to_service(submodel.id)
    
    def deleteSubmodelById(self, id:str) -> None:
        url = f"{self.endpoint}/{to_base64_string(id)}"
        resp = requests.delete(url)
        parse_none_response(resp)