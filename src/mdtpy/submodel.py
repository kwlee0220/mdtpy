from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Iterator, Any, Mapping, Iterable, Optional

if TYPE_CHECKING:
    from .instance import MDTInstance

import datetime
from urllib import parse

from basyx.aas import model

from .ref import ElementReference, BaseElementReference
from .descriptor import MDTSubmodelDescriptor
from .aas_misc import (
    ProtocolInformation,
    Endpoint,
    OperationVariable,
    OperationResult,
    OperationRequest,
    OperationHandle,
)
from .exceptions import InvalidResourceStateError, ResourceNotFoundError
from .basyx import serde as basyx_serde
from . import fa3st


class SubmodelService:
    def __init__(self, instance_id: str, sm_desc: MDTSubmodelDescriptor) -> None:
        self.__instance_id = instance_id
        self.__descriptor = sm_desc

    @property
    def instance_id(self) -> str:
        """
        MDTInstance의 식별자를 반환한다.

        Returns:
            str: MDTInstance의 식별자.
        """
        return self.__instance_id

    @property
    def id(self) -> str:
        """
        Submodel의 식별자를 반환한다.

        Returns:
            str: Submodel의 식별자.
        """
        return self.__descriptor.id

    @property
    def id_short(self) -> str:
        """
        Submodel의 ID Short를 반환한다.

        Returns:
            str: Submodel의 ID Short.
        """
        return self.__descriptor.id_short

    @property
    def semantic_id_str(self) -> str:
        """
        Submodel의 Semantic ID를 반환한다.

        Returns:
            str: Submodel의 Semantic ID.
        """
        return self.__descriptor.semantic_id

    @property
    def service_endpoint(self) -> Optional[str]:
        """
        Submodel의 Service Endpoint를 반환한다.

        Returns:
            Optional[str]: Submodel의 Service Endpoint.
        """
        return self.__descriptor.endpoint

    @property
    def endpoint(self) -> Endpoint:
        """
        Submodel의 Endpoint를 반환한다.

        Returns:
            Endpoint: Submodel의 Endpoint.
        """
        return Endpoint(
            interface="SUBMODEL",
            protocolInformation=ProtocolInformation(
                href=self.service_endpoint,
                endpointProtocol="HTTP",
                endpointProtocolVersion="1.1",
            ),
        )

    def is_information_model(self) -> bool:
        """
        Submodel가 Information Model인지 여부를 반환한다.

        Returns:
            bool: Submodel가 Information Model인지 여부.
        """
        return self.__descriptor.is_information_model()

    def is_data(self) -> bool:
        """
        Submodel가 Data Model인지 여부를 반환한다.

        Returns:
            bool: Submodel가 Data Model인지 여부.
        """
        return self.__descriptor.is_data()

    def is_simulation(self) -> bool:
        """
        Submodel가 Simulation Model인지 여부를 반환한다.

        Returns:
            bool: Submodel가 Simulation Model인지 여부.
        """
        return self.__descriptor.is_simulation()

    def is_ai(self) -> bool:
        """
        Submodel가 AI Model인지 여부를 반환한다.

        Returns:
            bool: Submodel가 AI Model인지 여부.
        """
        return self.__descriptor.is_ai()

    def is_time_series(self) -> bool:
        """
        Submodel가 Time Series Model인지 여부를 반환한다.

        Returns:
            bool: Submodel가 Time Series Model인지 여부.
        """
        return self.__descriptor.is_time_series()

    def read(self) -> model.Submodel:
        """
        Submodel을 읽어온다.

        Returns:
            model.Submodel: Submodel.
        """
        if not self.__descriptor.endpoint:
            raise InvalidResourceStateError.create(
                "SubmodelService", f"id={self.id}", "Endpoint is not set"
            )
        return fa3st.call_get(  # type: ignore
            self.__descriptor.endpoint, deserializer=basyx_serde.from_json
        )

    def write(self, submodel: model.Submodel) -> None:
        """
        Submodel을 쓴다.

        Args:
            submodel (model.Submodel): 쓸 Submodel.
        """
        if not self.__descriptor.endpoint:
            raise InvalidResourceStateError.create(
                "SubmodelService", f"id={self.id}", "Endpoint is not set"
            )
        url = self.__descriptor.endpoint
        json_str = basyx_serde.to_json(submodel)
        fa3st.call_put(url, json_str)

    @property
    def submodel_elements(self) -> SubmodelElementCollection:
        """
        Submodel의 모든 SubmodelElement 객체들의 목록을 반환한다.

        Returns:
            SubmodelElementCollection: Submodel의 모든 SubmodelElement 객체들의 목록.
        """
        return SubmodelElementCollection(self)

    def element_reference(self, path: str) -> ElementReference:
        """
        주어진 idShort 경로에 해당하는 SubmodelElement의 ElementReference를 반환한다.

        Args:
            path (str): idShort 경로.
        Returns:
            ElementReference: idShort 경로에 해당하는 SubmodelElement의 ElementReference.
        """
        ref_string = f"{self.instance_id}:{self.id_short}:{path}"
        return BaseElementReference(ref_string)

    def invoke_operation_sync(
        self,
        op_path: str,
        input_op_variables: Iterable[OperationVariable],
        inoutput_op_variables: Iterable[OperationVariable],
        timeout: datetime.timedelta,
    ) -> OperationResult:
        """
        주어진 연산 경로에 해당하는 연산을 동기적으로 호출한다.

        Args:
            op_path (str): 연산 경로.
            input_op_variables (Iterable[OperationVariable]): 입력 연산 변수 목록.
            inoutput_op_variables (Iterable[OperationVariable]): 입출력 연산 변수 목록.
            timeout (datetime.timedelta): 타임아웃.
        Returns:
            OperationResult: 연산 결과.
        Raises:
            TimeoutError: timeout(+여유 시간) 안에 응답을 받지 못한 경우 (mdtpy.TimeoutError).
                연산이 서버에서 아직 실행 중이거나 이미 끝났을 수 있다.
        """
        url = self.submodel_element_url(op_path) + "/invoke"
        req = OperationRequest(
            input_arguments=input_op_variables,
            inoutput_arguments=inoutput_op_variables,
            client_timeout_duration=timeout,
        )
        json_str = req.to_json()
        # 서버는 연산이 끝난 뒤에 응답하므로, 응답 대기 제한은 연산 제한 시간보다 길어야 한다.
        # (연결 제한은 기본값을 쓴다.) 응답을 받지 못하면 연산의 성공 여부를 알 수 없으므로
        # mdtpy.TimeoutError 가 난다.
        http_timeout = (fa3st.DEFAULT_TIMEOUT, timeout.total_seconds() + fa3st.DEFAULT_TIMEOUT)
        return fa3st.call_post(  # type: ignore
            url, data=json_str, deserializer=OperationResult.from_json, timeout=http_timeout
        )

    def invoke_operation_async(
        self,
        op_path: str,
        input_op_variables: Iterable[OperationVariable],
        inoutput_op_variables: Iterable[OperationVariable],
        timeout: datetime.timedelta,
    ) -> OperationHandle:
        """
        주어진 연산 경로에 해당하는 연산을 비동기적으로 호출하고, 끝나기를 기다리지 않고 핸들을 반환한다.

        AAS API v3 의 `POST …/invoke-async` 를 쓴다. 서버는 `202 Accepted` 와 함께
        `Location: operation-status/<base64url(handleId)>` 를 돌려주며, 이 헤더에서 핸들을 꺼낸다.
        상태는 :meth:`get_operation_async_status`, 결과는 :meth:`get_operation_async_result` 로 조회한다.

        Args:
            op_path (str): 연산 경로.
            input_op_variables (Iterable[OperationVariable]): 입력 연산 변수 목록.
            inoutput_op_variables (Iterable[OperationVariable]): 입출력 연산 변수 목록.
            timeout (datetime.timedelta): 서버가 연산에 허용할 최대 실행 시간.
        Returns:
            OperationHandle: 비동기 연산 핸들.
        Raises:
            MDTException: 서버가 오류를 반환했거나 응답에 Location 헤더가 없는 경우.
        """
        url = self.submodel_element_url(op_path) + "/invoke-async"
        req = OperationRequest(
            input_arguments=input_op_variables,
            inoutput_arguments=inoutput_op_variables,
            client_timeout_duration=timeout,
        )
        status_url = fa3st.call_post_for_location(url, data=req.to_json())
        encoded_handle = parse.unquote(status_url.rstrip('/').rsplit('/', 1)[-1])
        return OperationHandle(handle_id=fa3st.decode_base64url(encoded_handle))

    def get_operation_async_status(self, path: str, handle: OperationHandle) -> OperationResult:
        """
        비동기 연산의 현재 상태를 반환한다.

        `GET …/operation-status/<base64url(handleId)>` 를 호출한다. 실행 중(`Initiated`, `Running`)이면
        서버가 상태만 돌려주므로 출력 변수는 None 이다. 끝났으면 서버가 `302` 로 결과 위치
        (`operation-results`)를 알려 주고, 그 결과(출력 변수 포함)를 받아 반환한다.

        Args:
            path (str): 연산 경로.
            handle (OperationHandle): 비동기 연산 핸들.
        Returns:
            OperationResult: 연산 상태. `execution_state` 로 진행 여부를 판단한다.
        """
        url = self.submodel_element_url(path) + f"/operation-status/{fa3st.encode_base64url(handle.handle_id)}"
        return fa3st.call_get(url, deserializer=OperationResult.from_json) # type: ignore

    def get_operation_async_result(self, path: str, handle: OperationHandle) -> OperationResult:
        """
        비동기 연산의 결과를 반환한다.

        `GET …/operation-results/<base64url(handleId)>` 를 호출한다. 서버에 저장된 결과를 그대로 돌려주므로,
        연산이 아직 실행 중이면 `execution_state` 가 실행 중 상태인 결과가 온다.

        Args:
            path (str): 연산 경로.
            handle (OperationHandle): 비동기 연산 핸들.
        Returns:
            OperationResult: 연산 결과.
        """
        url = self.submodel_element_url(path) + f"/operation-results/{fa3st.encode_base64url(handle.handle_id)}"
        return fa3st.call_get(url, deserializer=OperationResult.from_json) # type: ignore

    def submodel_element_url(self, path: str) -> str:
        """
        SubmodelElement의 URL을 반환한다.

        Args:
            path (str): idShort 경로.
        Returns:
            str: SubmodelElement의 URL.
        Raises:
            InvalidResourceStateError: Submodel의 endpoint가 설정되지 않은 경우.
        """
        if not self.__descriptor.endpoint:
            raise InvalidResourceStateError.create(
                "SubmodelService", f"id={self.id}", "Endpoint is not set"
            )
        url_prefix = f"{self.__descriptor.endpoint}/submodel-elements"
        return f'{url_prefix}/{parse.quote(path, safe="")}' if path else url_prefix


T = TypeVar('T', bound=SubmodelService)
class SubmodelServiceCollection(Mapping[str, T]):
    def __init__(
        self,
        instance: 'MDTInstance',
        sm_desc_dict: Mapping[str, MDTSubmodelDescriptor],
    ):
        """
        주어진 서브모델 디스크립터 목록으로부터 SubmodelService 컬렉션을 구성한다.

        semantic_id에 따라 다음과 같이 분기한다.
            - Data / InformationModel : SubmodelService
            - Simulation / AI         : OperationSubmodelService (operation
              descriptor가 instance에 등록되어 있어야 한다)
            - TimeSeries              : TimeSeriesService
            - 그 외                   : 무시

        Operation descriptor 페치는 simulation/AI 서브모델이 실제로 존재할 때
        한 번만 lazy하게 수행한다.

        Args:
            instance (MDTInstance): 컬렉션이 속한 MDTInstance.
            sm_desc_dict (Mapping[str, MDTSubmodelDescriptor]): id_short →
                Submodel descriptor 매핑.
        Raises:
            ResourceNotFoundError: simulation/AI 서브모델에 대응하는 operation
                descriptor가 등록되어 있지 않은 경우.
        """
        op_desc_dict: Optional[Mapping[str, Any]] = None
        self.__services: dict[str, T] = {}
        for sm_desc in sm_desc_dict.values():
            if sm_desc.is_data() or sm_desc.is_information_model():
                self.__services[sm_desc.id_short] = SubmodelService(  # type: ignore
                    instance.id, sm_desc
                )
            elif sm_desc.is_simulation() or sm_desc.is_ai():
                # simulation/AI 서브모델이 실제 있을 때에만 op descriptor 페치
                if op_desc_dict is None:
                    op_desc_dict = instance.operation_descriptors
                if sm_desc.id_short in op_desc_dict:
                    op_desc = op_desc_dict[sm_desc.id_short]
                    from .operation import OperationSubmodelService
                    self.__services[sm_desc.id_short] = OperationSubmodelService(  # type: ignore
                        instance.id, sm_desc, op_desc
                    )
                else:
                    raise ResourceNotFoundError.create(
                        "MDTInstance",
                        f"Operation {instance.id}.{sm_desc.id} not found",
                    )
            elif sm_desc.is_time_series():
                from .timeseries import TimeSeriesService
                self.__services[sm_desc.id_short] = TimeSeriesService(  # type: ignore
                    instance.id, sm_desc
                )

    @property
    def services(self) -> Mapping[str, T]:
        """
        내부 SubmodelService 매핑을 read-only 형태로 반환한다.

        Returns:
            Mapping[str, T]: id_short → SubmodelService 매핑.
        """
        return self.__services

    def __bool__(self) -> bool:
        """
        컬렉션에 포함된 SubmodelService가 하나라도 있는지 여부를 반환한다.

        Returns:
            bool: 비어있지 않으면 True.
        """
        return len(self) > 0

    def __len__(self) -> int:
        """
        SubmodelService 개수를 반환한다.

        Returns:
            int: SubmodelService 개수.
        """
        return len(self.__services)

    def __getitem__(self, id_short: str) -> T:
        """
        주어진 idShort에 해당하는 SubmodelService를 반환한다.

        Args:
            id_short (str): idShort.
        Returns:
            T: SubmodelService.
        Raises:
            ResourceNotFoundError: 해당 idShort의 SubmodelService가 없는 경우.
        """
        if id_short not in self.__services:
            raise ResourceNotFoundError.create("SubmodelService", f"idShort={id_short}")
        return self.__services[id_short]

    def __iter__(self) -> Iterator[str]:
        """
        idShort 키들을 순환하는 순환자를 반환한다.

        Returns:
            Iterator[str]: idShort 순환자.
        """
        return iter(self.__services.keys())

    def __contains__(self, key: str) -> bool:
        """
        주어진 idShort의 SubmodelService 존재 여부를 반환한다.

        Args:
            key (str): idShort.
        Returns:
            bool: 존재하면 True.
        """
        return key in self.__services

    def get(self, id_short: str, default: Optional[T] = None) -> Optional[T]:  # type: ignore[override]
        """
        주어진 idShort의 SubmodelService를 반환하고, 없으면 `default` 를 반환한다.

        `__getitem__` 이 `KeyError` 가 아니라 `ResourceNotFoundError` 를 내므로
        `Mapping` 의 기본 구현 대신 직접 구현한다.

        Args:
            id_short (str): idShort.
            default (Optional[T]): 없을 때 반환할 값.
        Returns:
            Optional[T]: SubmodelService 또는 `default`.
        """
        return self.__services.get(id_short, default)

    def get_by_id(self, id: str) -> T:
        """
        주어진 Submodel id(URI)에 해당하는 SubmodelService를 반환한다.

        Args:
            id (str): Submodel id (URI).
        Returns:
            T: SubmodelService.
        Raises:
            ResourceNotFoundError: 해당 id의 SubmodelService가 없는 경우.
        """
        for svc in self.__services.values():
            if svc.id == id:
                return svc
        raise ResourceNotFoundError.create("SubmodelService", f"id={id}")

    def find_by_semantic_id(self, semantic_id: str) -> list[T]:
        """
        주어진 semantic_id를 가진 SubmodelService를 모두 반환한다.

        Args:
            semantic_id (str): Submodel semantic_id.
        Returns:
            list[T]: 매칭되는 SubmodelService 목록 (없으면 빈 리스트).
        """
        return [svc for svc in self.__services.values() if svc.semantic_id_str == semantic_id]


class SubmodelElementCollection(Mapping[str, model.SubmodelElement]):
    def __init__(self, submodel_svc: SubmodelService):
        self.__submodel_svc = submodel_svc
        # idShort 경로 목록 캐시. __iter__/__len__/__contains__가 공유하며,
        # mutation(__setitem__/__delitem__) 발생 시 None으로 리셋한다.
        self.__pathes_cache: Optional[list[str]] = None

    def element_reference(self, path: str) -> BaseElementReference:
        ref_string = f'{self.__submodel_svc.instance_id}:{self.__submodel_svc.id_short}:{path}'
        return BaseElementReference(ref_string)

    def refresh(self) -> None:
        """경로 캐시를 무효화하여 다음 조회 시 서버에서 재페치하게 한다."""
        self.__pathes_cache = None

    def __pathes(self) -> list[str]:
        if self.__pathes_cache is None:
            self.__pathes_cache = self.element_reference('').pathes()
        return self.__pathes_cache

    def __iter__(self) -> Iterator[str]:
        return iter(self.__pathes())

    def __len__(self) -> int:
        return len(self.__pathes())

    def __getitem__(self, path: str) -> model.SubmodelElement:
        return self.element_reference(path).read()

    def __setitem__(self, path: str, sme: model.SubmodelElement) -> None:
        try:
            self.element_reference(path).write(sme)
        except ResourceNotFoundError:
            self.element_reference(path).add(sme)
        self.__pathes_cache = None

    def __delitem__(self, path: str) -> None:
        self.element_reference(path).remove()
        self.__pathes_cache = None

    def __contains__(self, path: str) -> bool:
        return path in self.__pathes()

    def get(self, path: str, default: Optional[model.SubmodelElement] = None
            ) -> Optional[model.SubmodelElement]:  # type: ignore[override]
        """
        주어진 경로의 SubmodelElement 를 읽어 반환하고, 없으면 `default` 를 반환한다.

        `__getitem__` 은 없는 경로에 `KeyError` 가 아니라 `ResourceNotFoundError`(서버 404)를 내므로
        `Mapping` 의 기본 구현 대신 직접 구현한다. 경로 목록을 따로 읽지 않고 요소를 한 번만 읽는다.

        Args:
            path (str): idShort 경로.
            default (Optional[model.SubmodelElement]): 없을 때 반환할 값.
        Returns:
            Optional[model.SubmodelElement]: SubmodelElement 또는 `default`.
        """
        try:
            return self[path]
        except ResourceNotFoundError:
            return default

    def get_value(self, path: str) -> Any:
        return self.element_reference(path).read_value()

    def update_value(self, path: str, value: Any) -> None:
        self.element_reference(path).update_value(value)

    def get_attachment(self, path: str, max_bytes: Optional[int] = None) -> Optional[bytes]:
        return self.element_reference(path).get_attachment(max_bytes=max_bytes)