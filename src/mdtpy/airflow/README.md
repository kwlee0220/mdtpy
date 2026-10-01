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
| `DagTaskArgument` | `task_output()`, `reference()`, `literal()` | 입력 인자 값을 실행 시점에 어떻게 얻을지 기술 |
| `Operator` | `CopyElementOperator`, `OperationSubmodelOperator` | 태스크 본문 |

## 설치

런타임 의존성에 Airflow는 포함되지 않는다. Airflow에서 사용할 때만 별도로 설치한다:

```bash
pip install apache-airflow
```

`AirflowDagContext`는 import 시점이 아니라 사용 시점에 `airflow.sdk`를 import하므로,
Airflow 미설치 환경에서도 `LocalDagContext`로 단위 테스트를 돌릴 수 있다.

## DagTaskArgument — 입력 값을 어디서 가져올지 기술

각 헬퍼는 동일 이름의 `DagTaskArgument` 클래스를 감싼 짧은 팩토리이며, 태스크 실행
시점에 `get(context)`가 호출되어 값(`ElementValue`)을 산출한다. 단, `reference()`가
가리키는 대상이 File이면 값 대신 참조(`ElementReference`)를 반환하여, 연산에 파일을
참조로 전달할 수 있다.

```python
from mdtpy.airflow import task_output, reference, literal

# 1. task_output: 같은 DAG의 다른 태스크가 이전에 출력한 인자 값을 사용
prev_output = task_output("inspect_image", "Defect")

# 2. reference: MDT 참조 문자열의 값을 읽어 사용 (대상이 File이면 참조 그대로 전달)
upper_image = reference("param:inspector:UpperImage")

# 3. literal: 상수 값을 그대로 전달
#    (ElementValue가 아닌 raw 스칼라는 내부에서 mdt_value()로 감싸진다)
threshold = literal(3.14)
```

> **주의**: 여기서 `reference()`는 **입력 명세**(`DagTaskArgument`)를 만든다. 값을
> **기록할 위치**로 쓰는 `ElementReference`(아래 `CopyElementOperator.target`,
> `OperationSubmodelOperator.outputs`)는 `mdtpy.reference(...)`로 만든다.

## Operator — 태스크 본문

### `CopyElementOperator(source, target=None)`

`source` 입력의 값을 읽고, `target`이 주어지면 그 `ElementReference`에 값을 쓴 뒤,
어느 경우든 읽은 값을 `'target'` 키로 태스크 출력에 저장한다. `source`가 `None`이면
생성 시점에 `ValueError`가 발생한다.

```python
import mdtpy
from mdtpy.airflow import LocalDagContext, CopyElementOperator, reference

ctx = LocalDagContext("get_cycle_time", "http://localhost:12985/instance-manager")

# source만: 값을 읽어 태스크 출력('target' 키)으로 저장
CopyElementOperator(source=reference("param:heater:CycleTime")).run(ctx)

# target 지정: 읽은 값을 다른 ElementReference에도 기록 (target은 실제 ElementReference)
CopyElementOperator(
    source=reference("param:heater:CycleTime"),
    target=mdtpy.reference("param:other:CycleTime"),
).run(ctx)
```

### `OperationSubmodelOperator(instance, submodel, inputs, outputs)`

지정한 인스턴스의 Operation 서브모델을 호출한다. `inputs`는 인자 id를
`DagTaskArgument`에 매핑하고, `outputs`는 결과를 기록할 `ElementReference`에
매핑한다.

```python
import mdtpy
from mdtpy.airflow import (
    LocalDagContext, OperationSubmodelOperator, reference, task_output,
)

# 1) 첫 태스크: 이미지로 두께 검사 실행
ctx1 = LocalDagContext("inspect_image", "http://localhost:12985/instance-manager")
OperationSubmodelOperator(
    instance="inspector",
    submodel="ThicknessInspection",
    inputs={"UpperImage": reference("param:inspector:UpperImage")},
    outputs={},
).run(ctx1)

# 2) 두 번째 태스크: 첫 태스크의 'Defect' 출력을 받아 결함 목록 갱신
ctx2 = LocalDagContext("update_defect_list", "http://localhost:12985/instance-manager")
OperationSubmodelOperator(
    instance="inspector",
    submodel="UpdateDefectList",
    inputs={
        "Defect": task_output("inspect_image", "Defect"),
        "DefectList": reference("param:inspector:DefectList"),
    },
    outputs={
        "UpdatedDefectList": mdtpy.reference("param:inspector:DefectList"),
    },
).run(ctx2)
```

`outputs`의 `ElementReference`는 입력 인자와 함께 합쳐져 `invoke`에 전달된다
(`OperationSubmodelService.invoke`가 `ElementReference`인 출력 인자에 연산 결과를
자동으로 기록하는 동작에 의존).

## DagContext — 실행 환경 추상화

### `LocalDagContext` (단위 테스트 / DAG 디버깅)

태스크 출력은 클래스-레벨 dict(`__TASK_OUTPUT`)에 저장된다. 같은 프로세스 안에서
여러 태스크를 순차 실행할 때 사용하며, 생성자는 MDT Instance Manager URL을 반드시
받는다(Airflow에 의존하지 않는다).

```python
from mdtpy.airflow import LocalDagContext

ctx = LocalDagContext("my_task", "http://localhost:12985/instance-manager")
# ... operator.run(ctx) ...
```

> **주의**: `__TASK_OUTPUT`은 클래스 변수라 같은 프로세스 안에서 누적된다.
> 테스트마다 깨끗한 상태가 필요하면 명시적으로 초기화한다.

### `AirflowDagContext` (실제 Airflow 환경)

`airflow.sdk`의 `Variable`/`get_current_context()`/XCom을 사용한다. MDT 매니저 접속은
생성 시점이 아니라 첫 사용 시점(task 실행 중)에 지연 수행된다.

```python
from mdtpy.airflow import AirflowDagContext, OperationSubmodelOperator, reference

# Airflow `Variable`에 'mdt_manager_url'이 설정되어 있어야 한다 (없으면 인자로 전달)
def my_python_callable(**kwargs):
    OperationSubmodelOperator(
        instance="inspector",
        submodel="ThicknessInspection",
        inputs={"UpperImage": reference("param:inspector:UpperImage")},
        outputs={},
    ).run(AirflowDagContext())
```

XCom 키는 `'task_output'`을 사용한다 (`xcom_pull(task_ids=..., key='task_output')`).
XCom은 JSON 직렬화 가능한 값만 허용하므로, 태스크 출력의 `ElementValue`는
`@type`/`value` JSON 형태로 직렬화되어 저장되고 조회 시 자동으로 복원된다.
태스크 출력 값은 `ElementValue`여야 하며, 그 외 타입은 저장 시 `TypeError`가 발생한다.

## 작성 흐름 요약

1. 각 태스크마다 하나의 `Operator` 인스턴스를 만든다.
2. `CopyElementOperator`는 `source`(+ 선택 `target`)를, `OperationSubmodelOperator`는
   `inputs`/`outputs`를 지정한다.
3. 태스크 본문에서 `operator.run(context)`을 호출한다.
4. 다른 태스크가 같은 DAG에서 이 태스크의 출력을 받으려면
   `task_output(task_id, arg_id)`로 참조한다.
