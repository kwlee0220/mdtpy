# mdtpy.airflow

Apache Airflow DAG에서 MDT Operation을 호출하기 위한 보조 모듈.

> **Note**: 이 서브패키지는 `mdtpy/__init__.py`에서 자동으로 import되지 않는다.
> 사용하려면 `from mdtpy.airflow import ...` 형태로 명시적으로 import한다.

## 개요

MDT Operation을 Airflow 태스크 단위로 분해하고, XCom을 통해 태스크 사이로
값을 전달할 수 있게 해주는 세 가지 추상화를 제공한다:

| 추상 | 구체 구현 | 역할 |
|---|---|---|
| `DagContext` | `LocalDagContext`, `AirflowDagContext` | 태스크 출력 저장/조회와 MDT 매니저 접근 |
| `ArgumentSpec` | `task_output()`, `reference()`, `literal()` | 인자 값을 실행 시점에 어떻게 얻을지 기술 |
| `Invocation` | `SetElementInvocation`, `AASOperationTaskInvocation` | 태스크 본문 |

## 설치

런타임 의존성에 Airflow는 포함되지 않는다. Airflow에서 사용할 때만 별도로 설치한다:

```bash
pip install apache-airflow
```

`AirflowDagContext`는 import 시점이 아니라 사용 시점에 `airflow.sdk`를 import하므로,
Airflow 미설치 환경에서도 `LocalDagContext`로 단위 테스트를 돌릴 수 있다.

## ArgumentSpec — 값을 어디서 가져올지 기술

각 헬퍼는 동일 이름의 클래스를 감싼 짧은 팩토리이다.

```python
from mdtpy.airflow import task_output, reference, literal

# 1. task_output: 같은 DAG의 다른 태스크가 이전에 출력한 인자 값을 사용
prev_output = task_output("inspect_image", "Defect")

# 2. reference: MDT 참조 문자열을 매니저로 해석하여 ElementReference 획득
upper_image = reference("param:inspector:UpperImage")

# 3. literal: 상수 값을 그대로 전달
threshold = literal(3.14)
```

## Invocation — 태스크 본문

### `SetElementInvocation`

`source` 입력의 값을 읽고, 선택적으로 `target` 출력 reference에 그 값을 쓴 뒤,
태스크 출력으로도 등록한다.

```python
from mdtpy.airflow import LocalDagContext, SetElementInvocation, reference

ctx = LocalDagContext("get_cycle_time", "http://localhost:12985/instance-manager")
SetElementInvocation(
    argument_specs={
        'inputs': {
            'source': reference("param:heater:CycleTime"),
        },
        # 선택: target에 쓰면 해당 reference도 갱신된다
        # 'outputs': { 'target': reference("param:other:CycleTime") },
    }
).run(ctx)
```

`source` 키는 필수이다 (없으면 `ValueError`).

### `AASOperationTaskInvocation`

지정한 인스턴스의 Operation 서브모델을 호출한다.

```python
from mdtpy.airflow import (
    LocalDagContext, AASOperationTaskInvocation, reference, task_output,
)

# 1) 첫 태스크: 이미지로 두께 검사 실행
ctx1 = LocalDagContext("inspect_image", "http://localhost:12985/instance-manager")
AASOperationTaskInvocation(
    instance="inspector",
    submodel="ThicknessInspection",
    argument_specs={
        'inputs': {
            "UpperImage": reference("param:inspector:UpperImage"),
        },
    },
).run(ctx1)

# 2) 두 번째 태스크: 첫 태스크의 'Defect' 출력을 받아 결함 목록 갱신
ctx2 = LocalDagContext("update_defect_list", "http://localhost:12985/instance-manager")
AASOperationTaskInvocation(
    instance="inspector",
    submodel="UpdateDefectList",
    argument_specs={
        'inputs': {
            'Defect': task_output("inspect_image", "Defect"),
            'DefectList': reference("param:inspector:DefectList"),
        },
        'outputs': {
            'UpdatedDefectList': reference("param:inspector:DefectList"),
        },
    },
).run(ctx2)
```

`outputs`에 명시한 reference는 입력 인자에 함께 합쳐져 호출에 전달된다
(`Operation.invoke`가 `ElementReference`인 출력 인자를 자동으로 갱신하는 동작에 의존).

## DagContext — 실행 환경 추상화

### `LocalDagContext` (단위 테스트 / DAG 디버깅)

태스크 출력은 클래스-레벨 dict(`__TASK_OUTPUT`)에 저장된다. 같은 프로세스 안에서
여러 태스크를 순차 실행할 때 사용한다.

```python
from mdtpy.airflow import LocalDagContext

ctx = LocalDagContext("my_task", "http://localhost:12985/instance-manager")
# ... Invocation.run(ctx) ...
```

> **주의**: `__TASK_OUTPUT`은 클래스 변수라 같은 프로세스 안에서 누적된다.
> 테스트마다 깨끗한 상태가 필요하면 명시적으로 초기화한다.

### `AirflowDagContext` (실제 Airflow 환경)

`airflow.sdk`의 `Variable`/`get_current_context()`/XCom을 사용한다.

```python
from mdtpy.airflow import AirflowDagContext, AASOperationTaskInvocation, reference

# Airflow `Variable`에 'mdt_manager_url'이 설정되어 있어야 한다 (없으면 인자로 전달)
def my_python_callable(**kwargs):
    AASOperationTaskInvocation(
        instance="inspector",
        submodel="ThicknessInspection",
        argument_specs={'inputs': {"UpperImage": reference("param:inspector:UpperImage")}},
    ).run(AirflowDagContext())
```

XCom 키는 `'task_output'`을 사용한다 (`xcom_pull(task_ids=..., key='task_output')`).

## 작성 흐름 요약

1. 각 태스크마다 하나의 `Invocation` 인스턴스를 만든다.
2. `argument_specs['inputs']`에 입력 인자별 `ArgumentSpec`을 적는다.
3. 출력으로 reference에 값을 반영하려면 `argument_specs['outputs']`에 적는다.
4. 태스크 본문에서 `invocation.run(context)`을 호출한다.
5. 다른 태스크가 같은 DAG에서 이 태스크의 출력을 받으려면
   `task_output(task_id, arg_id)`로 참조한다.
