from __future__ import annotations

import os
import shutil
import tempfile
import time
from typing import Iterator, Generator, Optional
from abc import ABC, abstractmethod
from pathlib import Path

import requests
from urllib.parse import quote

from basyx.aas import model
from .basyx import serde as basyx_serde

from .submodel import SubmodelService, SubmodelServiceCollection
from .reference import DefaultElementReference
from .descriptor import (
    InstanceDescriptor,
    MDTParameterDescriptor,
    MDTSubmodelDescriptor,
    MDTOperationDescriptor,
    MDTAssetType,
    AssetKind,
    MDTInstanceStatus,
)
from .parameter import MDTParameterCollection, MDTParameter
from .timeseries import TimeSeriesService
from .operation import OperationSubmodelService
from .http_client import parse_response, parse_list_response, parse_none_response
from .exceptions import InvalidResourceStateError, ResourceNotFoundError


mdt_inst_url:Optional[str] = None
mdt_manager:Optional[MDTInstanceManager] = None


DEFAULT_TIMEOUT = 30

def _get(url, **kw):
    kw.setdefault('timeout', DEFAULT_TIMEOUT)
    return requests.get(url, **kw)

def _put(url, **kw):
    kw.setdefault('timeout', DEFAULT_TIMEOUT)
    return requests.put(url, **kw)

def _post(url, **kw):
    kw.setdefault('timeout', DEFAULT_TIMEOUT)
    return requests.post(url, **kw)

def _delete(url, **kw):
    kw.setdefault('timeout', DEFAULT_TIMEOUT)
    return requests.delete(url, **kw)

def connect(url: str) -> MDTInstanceManager:
    """
    MDT 플랫폼에 연결한다.

    Args:
        url (str): MDTInstanceManager 접속 URL.
    Returns:
        MDTInstanceManager: MDTInstanceManager 객체.
    """
    global mdt_inst_url, mdt_manager
    mdt_inst_url = url
    mdt_manager = MDTInstanceManager(url)
    return mdt_manager


class MDTInstanceManager:
    def __init__(self, mdt_inst_url: str):
        self.__inst_url = mdt_inst_url
        self.__instances = MDTInstanceCollection(mdt_inst_url)

    @property
    def url(self) -> str:
        """
        MDTInstanceManager 접속 URL을 반환한다.

        Returns:
            str: MDTInstanceManager 접속 URL.
        """
        return self.__inst_url

    @property
    def instances(self) -> MDTInstanceCollection:
        """
        MDTInstanceManager에 등록된 모든 MDTInstance 객체들의 목록을 반환한다.

        Returns:
            MDTInstanceCollection: MDTInstanceManager에 등록된 MDTInstance 객체들의 목록.
        """
        return self.__instances

    def resolve_reference(self, ref_string: str) -> DefaultElementReference:
        """
        주어진 참조 문자열을 해석하여 해당하는 ElementReference 객체를 반환한다.

        참조 문자열은 다음 형식 중 하나여야 한다.
            - "param:<instance_id>:<parameter_id>"
            - "oparg:<instance_id>:<operation_id>:in|out:<argument_id>"
            - 그 외: 서버에 위임하여 엔드포인트를 조회한다.

        Args:
            ref_string (str): 참조 문자열.
        Returns:
            DefaultElementReference: 참조 문자열에 해당하는 ElementReference 객체.
        Raises:
            ValueError: 참조 문자열의 형식이 유효하지 않은 경우.
            ResourceNotFoundError: 참조가 가리키는 MDTInstance, parameter,
                            operation, argument 등이 존재하지 않는 경우.
            MDTException: 서버가 오류 응답을 반환한 경우 (RemoteError 등 하위 타입 포함).
            requests.exceptions.RequestException: HTTP 통신 자체에 실패한 경우.
        """
        parts = ref_string.split(':')
        if not parts or not parts[0]:
            raise ValueError(f"Invalid reference: {ref_string}")
        match parts[0]:
            case 'param':
                if len(parts) != 3:
                    raise ValueError(f"Invalid parameter reference: {ref_string}")
                return self.instances[parts[1]].parameters[parts[2]]
            case 'oparg':
                if len(parts) != 5:
                    raise ValueError(f"Invalid operation argument reference: {ref_string}")
                op = self.instances[parts[1]].operations[parts[2]]
                match parts[3]:
                    case 'in':
                        return op.input_arguments[parts[4]]
                    case 'out':
                        return op.output_arguments[parts[4]]
                    case _:
                        raise ValueError(f"Invalid operation argument reference: {ref_string}")
            case _:
                url = f"{self.__inst_url}/references/$url?ref={quote(ref_string)}"
                resp = _get(url)
                return DefaultElementReference(
                    ref_string=ref_string,
                    endpoint=parse_response(resp),
                )


class MDTInstanceCollection:
    def __init__(self, mdt_inst_url: str) -> None:
        """
        MDTInstance 목록을 초기화한다.

        Args:
            mdt_inst_url (str): MDTInstanceManager의 접속 URL.
        """
        self.__inst_url = mdt_inst_url
        self.__url_prefix = f"{mdt_inst_url}/instances"

    def __bool__(self) -> bool:
        """
        MDTInstance 컬렉션 핸들은 서버 상태와 관계없이 항상 truthy다.

        `__len__`이 정의되어 있을 때 Python 기본 동작은 `__len__`을 통해
        bool을 결정하므로, HTTP 호출을 일으키지 않도록 명시적으로 True를 반환한다.
        실제 비어있는지 여부는 `len(collection) == 0`으로 확인한다.

        Returns:
            bool: 항상 True.
        """
        return True

    def __len__(self) -> int:
        """
        MDTInstance 개수를 반환한다.

        Returns:
            int: MDTInstance 개수.
        """
        resp = _get(self.__url_prefix)
        return len(parse_list_response(resp, InstanceDescriptor))
                
    def __iter__(self) -> Iterator[MDTInstance]:
        """
        MDTInstance 목록을 순환하는 순환자를 반환한다.

        Returns:
            Iterator[MDTInstance]: MDTInstance 순환자.
        """
        resp = _get(self.__url_prefix)
        inst_desc_list = parse_list_response(resp, InstanceDescriptor)
        return iter(MDTInstance(inst_desc, self.__inst_url) for inst_desc in inst_desc_list)
    
    def __contains__(self, instance_id:str) -> bool:
        """
        주어진 식별자에 해당하는 MDTInstance 존재 여부를 반환한다.

        Args:
            instance_id (str): MDTInstance 식별자.
        Returns:
            bool: MDTInstance 존재 여부.
        Raises:
            MDTException: 서버가 200/404 외의 오류 응답을 반환한 경우.
        """
        url = f'{self.__url_prefix}/{quote(instance_id, safe="")}'
        resp = _get(url)
        if resp.status_code == 404:
            return False
        parse_none_response(resp)
        return True

    def __getitem__(self, instance_id:str) -> MDTInstance:
        """
        주어진 식별자에 해당하는 MDTInstance를 반환한다.

        Args:
            instance_id (str): MDTInstance 식별자.
        Returns:
            MDTInstance: MDTInstance 객체.
        Raises:
            ResourceNotFoundError: MDTInstance 식별자에 해당하는 MDTInstance가 없는 경우.
            MDTException: 서버가 200/404 외의 오류 응답을 반환한 경우.
        """
        url = f'{self.__url_prefix}/{quote(instance_id, safe="")}'
        resp = _get(url)
        if resp.status_code == 404:
            raise ResourceNotFoundError.create("MDTInstance", f"id={instance_id}")

        inst_desc: InstanceDescriptor = parse_response(resp, InstanceDescriptor)  # type: ignore
        return MDTInstance(inst_desc, self.__inst_url)
        
    def find(self, condition:str) -> Generator[MDTInstance, None, None]:
        """
        MDTInstance 목록에 포함된 MDTInstance 중에서 주어진 조건에 맞는 것들을 반환한다.

        Args:
            condition (str): 조건.
        Returns:
            Generator[MDTInstance, None, None]: MDTInstance 생산자.
        """
        resp = _get(self.__url_prefix, params={'filter': f"{condition}"})
        inst_desc_list = parse_list_response(resp, InstanceDescriptor)
        return (MDTInstance(inst_desc, self.__inst_url) for inst_desc in inst_desc_list)
        
    def add(self, instance_id:str, port:int, inst_dir:str) -> MDTInstance:
        """
        MDTInstance 목록에 MDTInstance를 추가한다.

        Args:
            instance_id (str): 추가할 MDTInstance 식별자.
            port (int): 추가할 MDTInstance에 부여할 포트 번호.
            inst_dir (str): 추가할 MDTInstance의 디렉토리.
        Returns:
            MDTInstance: 추가된 MDTInstance 객체.
        Raises:
            ResourceAlreadyExistsError: 추가할 MDTInstance 식별자에 해당하는 MDTInstance가
                        이미 존재하는 경우.
        """
        src = Path(inst_dir)
        if not src.is_dir():
            raise ValueError(f"not a directory: {inst_dir}")

        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, src.name)
            zipped_file = shutil.make_archive(base, 'zip', root_dir=str(src))

            with open(zipped_file, 'rb') as f:
                files = {'bundle': (os.path.basename(zipped_file), f, 'application/zip')}
                data = {'id': instance_id, 'port': str(port)}
                resp = _post(self.__url_prefix, files=files, data=data, timeout=60)

        inst_desc: InstanceDescriptor = parse_response(resp, InstanceDescriptor)  # type: ignore
        return MDTInstance(inst_desc, self.__inst_url)
        
    def __delitem__(self, instance_id:str) -> None:
        """
        MDTInstance 목록에서 주어진 식별자에 해당하는 MDTInstance를 제거한다.

        Args:
            instance_id (str): 제거할 MDTInstance 식별자.
        Raises:
            ResourceNotFoundError: 제거할 MDTInstance 식별자에 해당하는 MDTInstance가 없는 경우.
        """
        url = f'{self.__url_prefix}/{quote(instance_id, safe="")}'
        resp = _delete(url)
        parse_none_response(resp)

    def remove(self, instance_id:str) -> None:
        """
        MDTInstance 목록에서 주어진 식별자에 해당하는 MDTInstance를 제거한다.

        Args:
            instance_id (str): 제거할 MDTInstance 식별자.
        Raises:
            ResourceNotFoundError: 제거할 MDTInstance 식별자에 해당하는 MDTInstance가 없는 경우.
        """
        del self[instance_id]
                
    def remove_all(self) -> None:
        """
        MDTInstance 목록에 포함된 모든 MDTInstance를 제거한다.
        """
        url = f"{self.__url_prefix}"
        resp = _delete(url)
        parse_none_response(resp)


class MDTInstance:
    def __init__(self, descriptor:InstanceDescriptor, mdt_inst_url: str) -> None:
        self.__descriptor = descriptor
        self.__instance_url = f"{mdt_inst_url}/instances/{quote(descriptor.id, safe='')}"

    @property
    def descriptor(self) -> InstanceDescriptor:
        """
        MDTInstance의 등록정보를 반환한다.

        Returns:
            InstanceDescriptor: MDTInstance의 등록정보.
        """
        return self.__descriptor

    @property
    def id(self) -> str:
        """
        MDTInstance 식별자를 반환한다.

        Returns:
            str: MDTInstance 식별자.
        """
        return self.__descriptor.id

    @property
    def aas_id(self) -> str:
        """
        MDTInstance의 AAS ID를 반환한다.

        Returns:
            str: MDTInstance의 AAS ID.
        """
        return self.__descriptor.aas_id

    @property
    def aas_id_short(self) -> Optional[str]:
        """
        MDTInstance의 AAS ID Short를 반환한다.

        Returns:
            Optional[str]: MDTInstance의 AAS ID Short.
        """
        return self.__descriptor.aas_id_short

    @property
    def global_asset_id(self) -> Optional[str]:
        """
        MDTInstance의 Global Asset ID를 반환한다.

        Returns:
            Optional[str]: MDTInstance의 Global Asset ID.
        """
        return self.__descriptor.global_asset_id

    @property
    def asset_type(self) -> Optional[MDTAssetType]:
        """
        MDTInstance의 Asset Type을 반환한다.

        Returns:
            Optional[MDTAssetType]: MDTInstance의 Asset Type.
        """
        return self.__descriptor.asset_type

    @property
    def asset_kind(self) -> Optional[AssetKind]:
        """
        MDTInstance의 Asset Kind을 반환한다.

        Returns:
            Optional[AssetKind]: MDTInstance의 Asset Kind.
        """
        return self.__descriptor.asset_kind

    @property
    def status(self) -> MDTInstanceStatus:
        """
        MDTInstance의 Status를 반환한다.

        Returns:
            MDTInstanceStatus: MDTInstance의 Status.
        """
        return self.__descriptor.status

    @property
    def base_endpoint(self) -> Optional[str]:
        """
        MDTInstance의 Base Endpoint를 반환한다.

        Returns:
            Optional[str]: MDTInstance의 Base Endpoint.
        """
        return self.__descriptor.base_endpoint

    def is_running(self) -> bool:
        """
        MDTInstance가 실행 중인지 여부를 반환한다.

        Returns:
            bool: MDTInstance가 실행 중인지 여부.
        """
        return self.status == MDTInstanceStatus.RUNNING

    @property
    def parameters(self) -> MDTParameterCollection:
        """
        MDTInstance에 정의된 모든 Parameter 객체들의 목록을 반환한다.

        Returns:
            MDTParameterCollection: 파라미터 목록
        """
        if not self.is_running():
            raise InvalidResourceStateError.create("MDTInstance", f"id={self.id}", self.status)

        url = f"{self.__instance_url}/model/parameters"
        resp = _get(url)
        desc_list = parse_list_response(resp, MDTParameterDescriptor)
        return MDTParameterCollection([MDTParameter(desc) for desc in desc_list])

    @property
    def submodel_descriptors(self) -> dict[str, MDTSubmodelDescriptor]:
        """
        MDTInstance에 정의된 모든 Submodel 객체들의 등록정보 목록을 반환한다.

        Returns:
            dict[str, MDTSubmodelDescriptor]: Submodel 등록정보 목록
        """
        if not self.is_running():
            raise InvalidResourceStateError.create("MDTInstance", f"id={self.id}", self.status)

        url = f"{self.__instance_url}/model/submodels"
        resp = _get(url)
        return { desc.id_short:desc for desc in parse_list_response(resp, MDTSubmodelDescriptor) }

    @property
    def operation_descriptors(self) -> dict[str, MDTOperationDescriptor]:
        """
        MDTInstance에 정의된 모든 Operation 객체들의 등록정보 목록을 반환한다.

        Returns:
            dict[str, MDTOperationDescriptor]: Operation 등록정보 목록
        """
        if not self.is_running():
            raise InvalidResourceStateError.create("MDTInstance", f"id={self.id}", self.status)

        url = f"{self.__instance_url}/model/operations"
        resp = _get(url)
        return { desc.id:desc for desc in parse_list_response(resp, MDTOperationDescriptor) }

    @property
    def submodel_services(self) -> SubmodelServiceCollection[SubmodelService]:
        """
        MDTInstance에 정의된 모든 Submodel 객체들의 Service 객체들의 목록을 반환한다.

        Returns:
            SubmodelServiceCollection[SubmodelService]: Submodel Service 목록
        """
        return SubmodelServiceCollection[SubmodelService](self, self.submodel_descriptors)

    @property
    def operations(self) -> SubmodelServiceCollection[OperationSubmodelService]:
        """
        MDTInstance에 정의된 모든 Operation 객체들의 Service 객체들의 목록을 반환한다.

        Returns:
            SubmodelServiceCollection[OperationSubmodelService]: Operation Service 목록
        """
        op_sm_desc_dict = {
            id: sm_desc
            for id, sm_desc in self.submodel_descriptors.items()
            if sm_desc.is_simulation() or sm_desc.is_ai()
        }
        return SubmodelServiceCollection[OperationSubmodelService](self, op_sm_desc_dict)

    @property
    def timeseries(self) -> SubmodelServiceCollection[TimeSeriesService]:
        """
        MDTInstance에 정의된 모든 TimeSeries 객체들의 Service 객체들의 목록을 반환한다.

        Returns:
            SubmodelServiceCollection[TimeSeriesService]: TimeSeries Service 목록
        """
        ts_sm_desc_dict = {
            id: sm_desc
            for id, sm_desc in self.submodel_descriptors.items()
            if sm_desc.is_time_series()
        }
        return SubmodelServiceCollection[TimeSeriesService](self, ts_sm_desc_dict)


    def start(self, nowait=False) -> InstanceDescriptor:
        """
        MDTInstance를 시작시킨다.

        Args:
            nowait: True인 경우, MDTInstance가 시작될 때까지 대기하지 않는다.
        Returns:
            InstanceDescriptor: MDTInstance의 등록정보.
        Raises:
            InvalidResourceStateError: MDTInstance의 상태를 STARTING 또는 RUNNING으로
                            변경할 수 없는 경우.
        """
        url = f"{self.__instance_url}/start"
        resp = _put(url, data="")
        parse_none_response(resp)

        # start 요청을 보내고 replay가 온 후에는 STARTING 또는 RUNNING 상태여야 한다.
        # 그렇지 않으면 예외를 발생시킨다.
        self.reload_descriptor()
        if self.__descriptor.status not in (MDTInstanceStatus.STARTING, MDTInstanceStatus.RUNNING):
            raise InvalidResourceStateError.create(
                "MDTInstance", f"id={self.id}", self.__descriptor.status
            )
        if not nowait:
            poller = InstanceStartPoller(f"{self.__instance_url}", init_desc=self.__descriptor)
            poller.wait_for_done()
            self.__descriptor = poller.desc
            if self.__descriptor.status != MDTInstanceStatus.RUNNING:
                raise InvalidResourceStateError.create(
                    "MDTInstance", f"id={self.id}", self.__descriptor.status
                )
            
        return self.descriptor
    

    def stop(self, nowait=False) -> InstanceDescriptor:
        """
        MDTInstance를 중지시킨다.

        Args:
            nowait: True인 경우, MDTInstance가 중지될 때까지 대기하지 않는다.
        Returns:
            InstanceDescriptor: MDTInstance의 등록정보.
        Raises:
            InvalidResourceStateError: MDTInstance의 상태를 STOPPING 또는 STOPPED로 변경할
                            수 없는 경우.
        """
        url = f"{self.__instance_url}/stop"
        resp = _put(url, data="")
        parse_none_response(resp)

        # stop 요청을 보내고 replay가 온 후에는 STOPPING 또는 STOPPED 상태여야 한다.
        # 그렇지 않으면 예외를 발생시킨다.
        self.reload_descriptor()
        if self.__descriptor.status not in (MDTInstanceStatus.STOPPING, MDTInstanceStatus.STOPPED):
            raise InvalidResourceStateError.create(
                "MDTInstance", f"id={self.id}", self.__descriptor.status
            )

        # nowait가 False인 경우, STOPPED 상태가 될 때까지 대기한다.
        if not nowait:
            poller = InstanceStopPoller(f"{self.__instance_url}", init_desc=self.__descriptor)
            poller.wait_for_done()
            self.__descriptor = poller.desc
            if self.__descriptor.status != MDTInstanceStatus.STOPPED:
                raise InvalidResourceStateError.create(
                    "MDTInstance", f"id={self.id}", self.__descriptor.status
                )
            
        return self.descriptor

    def read_asset_administration_shell(self) -> model.AssetAdministrationShell:
        import mdtpy.fa3st as fa3st
        aas_id_encoded = fa3st.encode_base64url(self.descriptor.aas_id)
        url = f"{self.descriptor.base_endpoint}/shells/{aas_id_encoded}"
        return fa3st.call_get(url, deserializer=basyx_serde.from_json) # type: ignore

    def reload_descriptor(self) -> InstanceDescriptor:
        """
        MDTInstance의 등록정보를 다시 읽어온다.

        Returns:
            InstanceDescriptor: MDTInstance의 등록정보.
        """
        resp = _get(self.__instance_url)
        self.__descriptor: InstanceDescriptor = parse_response(  # type: ignore
            resp, InstanceDescriptor
        )
        return self.__descriptor

    def __repr__(self) -> str:
        """
        MDTInstance의 문자열 표현을 반환한다.

        Returns:
            str: MDTInstance의 문자열 표현.
        """
        return f"MDTInstance({self.__descriptor})"


class StatusPoller(ABC):
    def __init__(self, poll_interval:float, timeout:Optional[float]=None) -> None:
        """
        StatusPoller를 초기화한다.

        Args:
            poll_interval: 폴링 간격.
            timeout: 타임아웃 (초).
        """
        self.poll_interval = poll_interval
        self.timeout = timeout
            
    @abstractmethod
    def is_done(self) -> bool:
        """
        작업이 완료되었는지 여부를 반환한다.

        Returns:
            bool: 작업이 완료되었는지 여부.
        """
        pass
    
    def wait_for_done(self) -> None:
        """
        작업이 완료될 때까지 대기한다.

        Raises:
            TimeoutError: 작업이 지정된 타임아웃 시간 내에 완료되지 않은 경우.
        """
        # 타임아웃 (self.timeout)이 있는 경우 최종 제한 시간을 계산하고,    
        # 타임아웃이 없는 경우 due를 None으로 설정하여 무제한 대기하도록 한다.
        started = time.time()
        due = started + self.timeout if self.timeout else None
        # 다음 폴링 시간을 계산한다.
        next_wakeup = started + self.poll_interval
        
        while not self.is_done():
            now = time.time()
            
            # 타임 아웃까지 남은 시간이 일정 시간 이내인 경우에는 TimeoutError를 발생시킨다.
            # 그렇지 않은 경우는 다음 폴링 시간까지 대기한다.
            if due and (due - now) < 0.01:
                raise TimeoutError(f'timeout={self.timeout}')
            
            # 다음 폴링 시간까지 남은 시간이 짧으면 대기하지 않고 바로 다음 폴링 시도한다.
            sleep_time = next_wakeup - now
            if sleep_time > 0.001:
                time.sleep(sleep_time)
            next_wakeup += self.poll_interval

class InstanceStartPoller(StatusPoller):
    def __init__(self, status_url:str, init_desc:InstanceDescriptor,
                                poll_interval:float=1.0, timeout:Optional[float]=None) -> None:
        super().__init__(poll_interval=poll_interval, timeout=timeout)
        self.status_url = status_url
        self.desc = init_desc
            
    def is_done(self) -> bool:
        """
        작업이 완료되었는지 여부를 반환한다.

        Returns:
            bool: 작업이 완료되었는지 여부.
        """
        if self.desc.status == MDTInstanceStatus.STARTING:
            resp = _get(self.status_url)
            self.desc: InstanceDescriptor = parse_response(  # type: ignore
                resp, InstanceDescriptor
            )
            return self.desc.status != MDTInstanceStatus.STARTING
        else:
            return True
        
class InstanceStopPoller(StatusPoller):
    def __init__(self, status_url:str, init_desc:InstanceDescriptor,
                                poll_interval:float=1.0, timeout:Optional[float]=None) -> None:
        super().__init__(poll_interval=poll_interval, timeout=timeout)
        self.status_url = status_url
        self.desc = init_desc
                
    def is_done(self) -> bool:
        """
        작업이 완료되었는지 여부를 반환한다.

        STOPPING 상태에서 벗어났는지 여부를 기준으로 한다.
        STOPPED가 아닌 다른 종료 상태(FAILED 등)가 되어도 폴링이 끝나도록 하기 위함이며,
        최종 상태가 STOPPED인지 여부 판정은 호출 측(stop())이 담당한다.

        Returns:
            bool: 작업이 완료되었는지 여부.
        """
        if self.desc.status == MDTInstanceStatus.STOPPING:
            resp = _get(self.status_url)
            self.desc: InstanceDescriptor = parse_response(  # type: ignore
                resp, InstanceDescriptor
            )
            return self.desc.status != MDTInstanceStatus.STOPPING
        else:
            return True