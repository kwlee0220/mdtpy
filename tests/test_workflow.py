"""
mdtpy.workflow 모듈(MDT Workflow Manager 조회 클라이언트)의 단위 테스트.

HTTP I/O는 unittest.mock으로 가짜 처리하여 외부 서버 의존성 없이 구동된다.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

import mdtpy
from mdtpy.workflow import (
    MDTWorkflowManager,
    Workflow,
    WorkflowStatus,
    connect_workflow_manager,
)
from mdtpy.exceptions import (
    ConnectionLostError,
    MDTInstanceConnectionError,
    RemoteError,
    ResourceNotFoundError,
    ResultUnknownError,
)


URL = "http://wf.example.com:12989/workflow-manager"

WORKFLOW_JSON = {
    "name": "wf_model__manual__2026-11-15T10:00:00+00:00",
    "modelId": "wf_model",
    "status": "RUNNING",
    "creationTime": "2026-11-15T10:00:00",
    "startTime": "2026-11-15T10:00:01",
    "tasks": [
        { "taskId": "a", "status": "COMPLETED", "dependents": ["b"],
          "startTime": "2026-11-15T10:00:01", "finishTime": "2026-11-15T10:00:05" },
        { "taskId": "b", "status": "RUNNING", "startTime": "2026-11-15T10:00:06" },
    ],
}


def _resp(status: int = 200, json_body=None, text: str = "", ctype: str = "application/json"):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = { "Content-Type": ctype, "content-type": ctype }
    resp.json.return_value = json_body
    resp.text = text
    return resp


@pytest.fixture
def mock_get():
    with patch("mdtpy.workflow.requests.request") as m:
        yield m


def test_connect_strips_trailing_slash_and_sends_no_request(mock_get):
    wm = connect_workflow_manager(URL + "/")
    assert wm.url == URL
    mock_get.assert_not_called()


def test_exported_from_package():
    assert mdtpy.connect_workflow_manager is connect_workflow_manager
    assert mdtpy.WorkflowStatus is WorkflowStatus


def test_models_returns_raw_json(mock_get):
    models = [{ "id": "m1", "name": "모델", "taskDescriptors": [] }]
    mock_get.return_value = _resp(json_body=models)
    assert MDTWorkflowManager(URL).models() == models
    mock_get.assert_called_once_with("GET", f"{URL}/models", timeout=30)


def test_get_model_quotes_id(mock_get):
    mock_get.return_value = _resp(json_body={ "id": "a/b" })
    MDTWorkflowManager(URL).get_model("a/b")
    mock_get.assert_called_once_with("GET", f"{URL}/models/a%2Fb", timeout=30)


def test_get_model_not_found(mock_get):
    mock_get.return_value = _resp(404, json_body={ "code": "mdt.model.ResourceNotFoundException",
                                                   "message": "WorkflowModel(id=x)" })
    with pytest.raises(ResourceNotFoundError, match="WorkflowModel"):
        MDTWorkflowManager(URL).get_model("x")


def test_get_model_script_returns_text(mock_get):
    mock_get.return_value = _resp(text="from airflow import DAG", ctype="text/x-python")
    assert MDTWorkflowManager(URL).get_model_script("m1") == "from airflow import DAG"
    mock_get.assert_called_once_with("GET", f"{URL}/models/m1/script", timeout=30)


def test_workflow_from_json():
    wf = Workflow.from_dict(WORKFLOW_JSON)
    assert wf.model_id == "wf_model" and wf.status is WorkflowStatus.RUNNING
    assert wf.finish_time is None
    assert [(t.task_id, t.status, t.dependents) for t in wf.tasks] == [
        ("a", WorkflowStatus.COMPLETED, ["b"]), ("b", WorkflowStatus.RUNNING, []),
    ]
    assert wf.to_dict()["modelId"] == "wf_model"


def test_workflows_filters_by_model(mock_get):
    other = { **WORKFLOW_JSON, "name": "other__run", "modelId": "other", "tasks": [] }
    mock_get.return_value = _resp(json_body=[WORKFLOW_JSON, other])
    wm = MDTWorkflowManager(URL)
    assert [wf.name for wf in wm.workflows()] == [WORKFLOW_JSON["name"], "other__run"]
    assert [wf.name for wf in wm.workflows(model_id="other")] == ["other__run"]
    mock_get.assert_called_with("GET", f"{URL}/workflows", timeout=30)


def test_get_workflow_quotes_id(mock_get):
    mock_get.return_value = _resp(json_body=WORKFLOW_JSON)
    wf = MDTWorkflowManager(URL).get_workflow(WORKFLOW_JSON["name"])
    assert wf.name == WORKFLOW_JSON["name"]
    called_url = mock_get.call_args.args[1]
    assert called_url == f"{URL}/workflows/wf_model__manual__2026-11-15T10%3A00%3A00%2B00%3A00"


def test_get_workflow_bad_id_is_remote_error(mock_get):
    mock_get.return_value = _resp(400, json_body={ "code": "java.lang.IllegalArgumentException",
                                                   "message": "invalid Airflow task id: x" })
    with pytest.raises(RemoteError, match="invalid Airflow task id"):
        MDTWorkflowManager(URL).get_workflow("x")


def test_get_task_log(mock_get):
    mock_get.return_value = _resp(text="line1\nline2", ctype="text/plain")
    assert MDTWorkflowManager(URL).get_task_log("w__r", "t 1") == "line1\nline2"
    mock_get.assert_called_once_with("GET", f"{URL}/workflows/w__r/log/t%201", timeout=30)


def test_start_workflow_with_run_id(mock_get):
    mock_get.return_value = _resp(json_body=WORKFLOW_JSON)
    wf = MDTWorkflowManager(URL).start_workflow("wf_model", run_id="run-1")
    assert wf.model_id == "wf_model"
    mock_get.assert_called_once_with("POST", f"{URL}/models/wf_model/start",
                                     params={ "runId": "run-1" }, timeout=30)


def test_start_workflow_without_run_id(mock_get):
    mock_get.return_value = _resp(json_body=WORKFLOW_JSON)
    MDTWorkflowManager(URL).start_workflow("wf model")
    mock_get.assert_called_once_with("POST", f"{URL}/models/wf%20model/start", params=None, timeout=30)


def test_start_workflow_unknown_model(mock_get):
    mock_get.return_value = _resp(404, json_body={ "code": "mdt.model.ResourceNotFoundException",
                                                   "message": "Airflow DAG: x" })
    with pytest.raises(ResourceNotFoundError):
        MDTWorkflowManager(URL).start_workflow("x")


def test_stop_workflow(mock_get):
    mock_get.return_value = _resp(204)
    assert MDTWorkflowManager(URL).stop_workflow("m__r") is None
    mock_get.assert_called_once_with("PUT", f"{URL}/workflows/m__r/stop", timeout=30)


def test_stop_workflow_not_found(mock_get):
    mock_get.return_value = _resp(404, json_body={ "code": "mdt.model.ResourceNotFoundException",
                                                   "message": "Workflow(m__r)" })
    with pytest.raises(ResourceNotFoundError):
        MDTWorkflowManager(URL).stop_workflow("m__r")


def test_connect_failure_is_not_result_unknown(mock_get):
    # 연결 자체에 실패하면 요청이 서버에 닿지 않았으므로 결과 확인 불가가 아니다.
    mock_get.side_effect = requests.exceptions.ConnectTimeout("connect timeout")
    with pytest.raises(MDTInstanceConnectionError) as info:
        MDTWorkflowManager(URL).models()
    assert not isinstance(info.value, ResultUnknownError)


def test_connection_lost_is_result_unknown(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("reset by peer")
    with pytest.raises(ConnectionLostError):
        MDTWorkflowManager(URL).start_workflow("m", run_id="r")


def test_read_timeout_is_result_unknown(mock_get):
    mock_get.side_effect = requests.exceptions.ReadTimeout("slow")
    with pytest.raises(ResultUnknownError):
        MDTWorkflowManager(URL).start_workflow("m", run_id="r")
