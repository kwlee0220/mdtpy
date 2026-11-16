"""
MDT Workflow Manager(mdt-workflow) 조회 클라이언트.

mdt-workflow 는 MDT Instance Manager 와 별개의 서버(기본 포트 12989)이며, 워크플로우 모델(태스크 구성)과
그 모델로 만든 워크플로우 실행(Airflow DAG run)을 관리한다. 이 모듈은 모델·실행 조회와 실행 시작·중지 API 를 감싼다.

```python
wf_manager = mdtpy.connect_workflow_manager("http://<host>:12989/workflow-manager")
for model in wf_manager.models():
    print(model['id'], model['name'])
for wf in wf_manager.workflows(model_id='InjectionProcessSimulation'):
    print(wf.name, wf.status)
wf = wf_manager.start_workflow('InjectionProcessSimulation', run_id='run-001')
```
"""
from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import quote

import requests
from dataclass_wizard import JSONWizard

from .http_client import to_exception
from .fa3st import _connection_error, _response_timeout


DEFAULT_TIMEOUT = 30


class WorkflowStatus(Enum):
    """워크플로우 실행과 그 태스크의 상태."""

    NOT_STARTED = "NOT_STARTED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class NodeTask(JSONWizard):
    """
    워크플로우 실행 안의 태스크 하나의 실행 상태.

    Attributes:
        task_id (str): 태스크 식별자 (워크플로우 모델의 태스크 id).
        status (WorkflowStatus): 태스크 상태.
        dependents (list[str]): 이 태스크가 끝나야 시작하는 태스크들의 id.
        start_time (Optional[str]): 시작 시각 (ISO 8601). 아직 시작 전이면 None.
        finish_time (Optional[str]): 종료 시각 (ISO 8601). 아직 끝나지 않았으면 None.
    """
    task_id: str
    status: WorkflowStatus
    dependents: list[str] = field(default_factory=list)
    start_time: Optional[str] = None
    finish_time: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Workflow(JSONWizard):
    """
    워크플로우 모델로 만든 워크플로우 실행 하나.

    Attributes:
        name (str): 워크플로우 실행 식별자 (`<dagId>__<dagRunId>` 형식).
        model_id (str): 이 실행을 만든 워크플로우 모델의 id.
        status (WorkflowStatus): 실행 상태.
        creation_time (Optional[str]): 생성 시각 (ISO 8601).
        start_time (Optional[str]): 시작 시각 (ISO 8601). 아직 시작 전이면 None.
        finish_time (Optional[str]): 종료 시각 (ISO 8601). 아직 끝나지 않았으면 None.
        tasks (list[NodeTask]): 태스크별 실행 상태.
    """
    name: str
    model_id: str
    status: WorkflowStatus
    creation_time: Optional[str] = None
    start_time: Optional[str] = None
    finish_time: Optional[str] = None
    tasks: list[NodeTask] = field(default_factory=list)


def _request(method: str, url: str, **kw) -> requests.Response:
    """HTTP 요청을 보낸다. 통신 실패는 mdtpy 예외로 바꾼다.

    Raises:
        MDTInstanceConnectionError: 연결에 실패해 요청이 서버에 닿지 않은 경우. 요청을 보낸 뒤 연결이
            끊긴 경우는 그 하위 타입인 ConnectionLostError(결과 확인 불가)다.
        TimeoutError: 요청은 보냈으나 제한 시간 안에 응답을 받지 못한 경우 (mdtpy.TimeoutError, 결과 확인 불가).
    """
    kw.setdefault('timeout', DEFAULT_TIMEOUT)
    try:
        return requests.request(method, url, **kw)
    except requests.exceptions.ConnectionError as e:
        raise _connection_error(url, e)
    except requests.exceptions.Timeout as e:
        raise _response_timeout(url, kw['timeout'], e)


def _get(url: str, **kw) -> requests.Response:
    return _request('GET', url, **kw)


def _json(resp: requests.Response) -> Any:
    """2xx 응답의 JSON 본문을 돌려준다. 그 밖의 응답은 `to_exception` 으로 변환해 발생시킨다."""
    if 200 <= resp.status_code < 300:
        return resp.json()
    raise to_exception(resp)


def _none(resp: requests.Response) -> None:
    """2xx 가 아닌 응답을 `to_exception` 으로 변환해 발생시킨다."""
    if not 200 <= resp.status_code < 300:
        raise to_exception(resp)


def _text(resp: requests.Response) -> str:
    """2xx 응답의 본문 문자열을 돌려준다. 그 밖의 응답은 `to_exception` 으로 변환해 발생시킨다."""
    if 200 <= resp.status_code < 300:
        return resp.text
    raise to_exception(resp)


class MDTWorkflowManager:
    """
    mdt-workflow 의 모델·실행 조회와 실행 시작·중지 API 클라이언트.

    모든 메소드는 호출할 때마다 HTTP 요청을 한 번 보낸다.

    Raises (모든 메소드 공통):
        ResourceNotFoundError: 주어진 id 의 모델·실행·태스크가 없는 경우.
        MDTException: 서버가 그 밖의 오류 응답을 돌려준 경우 (RemoteError 등).
        MDTInstanceConnectionError: 연결에 실패한 경우. 요청을 보낸 뒤 연결이 끊긴 경우는 그 하위 타입인
            ConnectionLostError(결과 확인 불가)다.
        TimeoutError: 응답을 제한 시간 안에 받지 못한 경우 (mdtpy.TimeoutError, 결과 확인 불가).
    """

    def __init__(self, url: str) -> None:
        """
        Args:
            url (str): Workflow Manager 접속 URL (예: `http://<host>:12989/workflow-manager`).
        """
        self.__url = url.rstrip('/')

    @property
    def url(self) -> str:
        """Workflow Manager 접속 URL 을 반환한다."""
        return self.__url

    def models(self) -> list[dict[str, Any]]:
        """
        등록된 모든 워크플로우 모델을 반환한다.

        모델의 태스크 구성(`taskDescriptors`)은 태스크 종류마다 형식이 다르므로 서버의 JSON 객체를
        그대로 돌려준다.

        Returns:
            list[dict]: 워크플로우 모델 목록. 각 모델은 `id`, `name`, `description`,
                `taskDescriptors`, `gui`(GUI 편집기의 화면 배치) 키를 가진다.
        """
        return _json(_get(f"{self.url}/models"))

    def get_model(self, model_id: str) -> dict[str, Any]:
        """
        주어진 id 의 워크플로우 모델을 반환한다.

        Args:
            model_id (str): 워크플로우 모델 id.
        Returns:
            dict: 워크플로우 모델 (`models()` 의 원소와 같은 형식).
        """
        return _json(_get(f"{self.url}/models/{quote(model_id, safe='')}"))

    def get_model_script(self, model_id: str) -> str:
        """
        주어진 id 의 워크플로우 모델을 변환한 Airflow DAG 스크립트(Python)를 반환한다.

        Args:
            model_id (str): 워크플로우 모델 id.
        Returns:
            str: Airflow DAG 스크립트.
        """
        return _text(_get(f"{self.url}/models/{quote(model_id, safe='')}/script"))

    def workflows(self, model_id: Optional[str] = None) -> list[Workflow]:
        """
        워크플로우 실행 목록을 반환한다.

        Args:
            model_id (Optional[str]): 주면 그 모델로 만든 실행만 반환한다.
        Returns:
            list[Workflow]: 워크플로우 실행 목록.
        """
        workflows = [Workflow.from_dict(wf) for wf in _json(_get(f"{self.url}/workflows"))]
        if model_id is not None:
            workflows = [wf for wf in workflows if wf.model_id == model_id]
        return workflows

    def get_workflow(self, workflow_id: str) -> Workflow:
        """
        주어진 식별자의 워크플로우 실행을 반환한다.

        Args:
            workflow_id (str): 워크플로우 실행 식별자 (`Workflow.name`).
        Returns:
            Workflow: 워크플로우 실행.
        """
        return Workflow.from_dict(_json(_get(f"{self.url}/workflows/{quote(workflow_id, safe='')}")))

    def get_task_log(self, workflow_id: str, task_id: str) -> str:
        """
        워크플로우 실행에서 한 태스크의 최신 시도 로그를 반환한다.

        Args:
            workflow_id (str): 워크플로우 실행 식별자 (`Workflow.name`).
            task_id (str): 태스크 id.
        Returns:
            str: 태스크 로그. 태스크가 아직 실행되지 않았으면 ResourceNotFoundError 가 발생한다.
        """
        url = f"{self.url}/workflows/{quote(workflow_id, safe='')}/log/{quote(task_id, safe='')}"
        return _text(_get(url))

    def start_workflow(self, model_id: str, run_id: Optional[str] = None) -> Workflow:
        """
        주어진 워크플로우 모델로 새 워크플로우 실행을 시작하고, 끝나기를 기다리지 않고 돌려준다.

        `run_id` 를 주면 그 식별자로 실행을 만든다. 같은 `run_id` 의 실행이 이미 있으면 새로 시작하지 않고
        그 실행을 돌려주므로, 응답을 받지 못한 시작 요청(ResultUnknownError)을 같은 `run_id` 로 다시 보내도
        실행은 하나만 생긴다. 실행 식별자(`Workflow.name`)는 `<model_id>__<run_id>` 다.

        Args:
            model_id (str): 워크플로우 모델 id.
            run_id (Optional[str]): 실행 식별자 (`[A-Za-z0-9._-]{1,200}`). None 이면 서버가 정한다.
        Returns:
            Workflow: 시작한 (또는 같은 run_id 로 이미 있던) 워크플로우 실행.
        Raises:
            ResourceNotFoundError: 모델이 없거나, Airflow 가 아직 그 모델의 DAG 를 읽지 않은 경우.
            RemoteError: run_id 형식이 맞지 않는 경우.
        """
        params = { 'runId': run_id } if run_id is not None else None
        resp = _request('POST', f"{self.url}/models/{quote(model_id, safe='')}/start", params=params)
        return Workflow.from_dict(_json(resp))

    def stop_workflow(self, workflow_id: str) -> None:
        """
        실행 중이거나 대기 중인 워크플로우 실행을 중지한다. 실행과 아직 실행 중인 태스크는 FAILED 가 된다.

        이미 끝난 실행에는 아무 일도 하지 않는다.

        Args:
            workflow_id (str): 워크플로우 실행 식별자 (`Workflow.name`).
        """
        _none(_request('PUT', f"{self.url}/workflows/{quote(workflow_id, safe='')}/stop"))

    def __repr__(self) -> str:
        return f"MDTWorkflowManager(url={self.url})"


def connect_workflow_manager(url: str) -> MDTWorkflowManager:
    """
    mdt-workflow 에 연결한다.

    `mdtpy.connect()` 와 달리 모듈 전역 상태를 바꾸지 않는다. 연결 시점에는 HTTP 요청을 보내지 않는다.

    Args:
        url (str): Workflow Manager 접속 URL (예: `http://<host>:12989/workflow-manager`).
    Returns:
        MDTWorkflowManager: Workflow Manager 클라이언트.
    """
    return MDTWorkflowManager(url)


__all__ = ['WorkflowStatus', 'NodeTask', 'Workflow', 'MDTWorkflowManager', 'connect_workflow_manager']
