# mdtpy.airflow

Apache Airflow DAG에서 MDT 연산을 task 단위로 실행하기 위한 보조 모듈.

> **Note**: 이 서브패키지는 `mdtpy/__init__.py`에서 자동으로 import되지 않는다.
> 사용하려면 `from mdtpy.airflow import ...` 형태로 명시적으로 import한다.

## 개요

MDT 연산 하나를 Airflow task 하나의 본문으로 감싸고, task 사이에서 값을 주고받을 수 있게
해주는 세 가지 추상을 제공한다.

| 추상 | 구체 구현 | 역할 |
|---|---|---|
| `DagTaskArgument` | `task_output()`, `reference()`, `literal()` | 입력 값을 task 실행 시점에 어디서 얻을지 기술 |
| `Operator` | `SetElementOperator`, `OperationSubmodelOperator`, `AASOperationOperator`, `RestfulAsyncRpcOperator`, `RestfulRpcOperator`, `PythonScriptOperator` | task 본문 |
| `DagContext` | `LocalDagContext`, `AirflowDagContext` | 실행 환경 어댑터 — task 출력 저장/조회, MDT Instance Manager 접근, 참조 해석 |

연산자 객체는 입력(`inputs`)·출력(`outputs`) **명세**를 받아 만들어지고, task가 실행될 때
`run(context)`가 호출되면 `DagContext`를 통해 실제 값을 해석하여 동작한다.

이 패키지의 주 사용처는 `mdt-workflow`가 생성하는 Airflow DAG 파일이다.

## 설치

Airflow는 `mdtpy`의 런타임 의존성에 포함되지 않는다. Airflow에서 사용할 때만 별도로 설치한다.

```bash
pip install apache-airflow
```

`airflow.sdk`는 모듈 import 시점이 아니라 `AirflowDagContext`를 생성하거나 사용할 때 import된다.
따라서 Airflow가 설치되지 않은 환경에서도 `mdtpy.airflow`를 import하고 `LocalDagContext`로
DAG 흐름을 실행하거나 테스트할 수 있다.

## 빠른 시작

### Airflow 없이 실행 (단위 테스트 / DAG 디버깅)

```python
from mdtpy.airflow import LocalDagContext, reference, task_output, literal, sink
from mdtpy.airflow import SetElementOperator, OperationSubmodelOperator

MDT_MANAGER_URL = "http://localhost:12985/instance-manager"

# task 1: CycleTime 값을 읽어 task 출력('target')으로 남긴다.
SetElementOperator(
    inputs = { 'source': reference("param:heater:CycleTime") },
).run(LocalDagContext("get_heater_cycle_time", MDT_MANAGER_URL))

# task 2: task 1의 출력을 입력으로 받아 Operation submodel을 호출하고,
#         결과를 SubmodelElement에 기록한다.
OperationSubmodelOperator(
    instance = "innercase",
    submodel = "ProcessOptimization",
    inputs = {
        'HTCycleTime': task_output("get_heater_cycle_time", "target"),
        'Efficiency': literal(0.85),
    },
    outputs = { 'TotalThroughput': sink("param:innercase:CycleTime") },
).run(LocalDagContext("innercase_optimization", MDT_MANAGER_URL))
```

`LocalDagContext`는 생성자에서 task id를 받으므로 task마다 새로 만든다.

### Airflow DAG 안에서 실행

task 본문에서 연산자를 만들고 `run()`을 호출한다. `context`를 생략하면 `AirflowDagContext()`가
생성되며, 이때 MDT Instance Manager URL은 Airflow `Variable`의 `mdt_manager_url`에서 읽는다.

```python
from airflow.sdk import dag, task
from mdtpy.airflow import reference, task_output, literal, sink
from mdtpy.airflow.operator import SetElementOperator, OperationSubmodelOperator

@dag(dag_id="innercase", tags=["mdt"])
def _dag():
    @task(task_id="get_heater_cycle_time")
    def _t1() -> None:
        SetElementOperator(
            inputs = { 'source': reference("param:heater:CycleTime") },
        ).run()

    @task(task_id="innercase_optimization")
    def _t2() -> None:
        OperationSubmodelOperator(
            instance = "innercase",
            submodel = "ProcessOptimization",
            inputs = {
                'HTCycleTime': task_output("get_heater_cycle_time", "target"),
                'Efficiency': literal(0.85),
            },
            outputs = { 'TotalThroughput': sink("param:innercase:CycleTime") },
        ).run()

    _t1() >> _t2()

_dag()
```

`mdt-workflow`가 생성하는 DAG도 같은 형태다 (task 함수 이름 대신 `task_id`로 task를 식별한다).

## DagTaskArgument — 입력 값을 어디서 가져올지 기술

`inputs`는 **입력 이름 → `DagTaskArgument`** 매핑이며, 값은 아래 팩토리로 만든다. 각 팩토리는
같은 이름의 `DagTaskArgument` 구현을 감싼 짧은 헬퍼이고, task 실행 시점에 `get(context)`가
호출되어 값이 결정된다.

| 팩토리 | 구현 클래스 | 의미 | `get()`이 돌려주는 것 |
|---|---|---|---|
| `task_output(task_id, arg_id)` | `TaskOutputArgument` | 선행 task가 남긴 출력 값 | `ElementValue` |
| `reference(ref_string)` | `ElementReferenceArgument` | 참조 대상의 값을 읽어 전달 | `ElementValue`. 단, 대상이 File이면 `ElementReference` 자체, `timeseries:` 참조면 `SubmodelElement` |
| `literal(value)` | `LiteralArgument` | 고정 리터럴 | `ElementValue` |

```python
from mdtpy.airflow import task_output, reference, literal

prev_output = task_output("inspect_image", "Defect")
upper_image = reference("param:inspector:UpperImage")   # File이면 참조 그대로 전달
log_data = reference("timeseries:Welder:NozzleProductionLog#last=50s|Time,QuantityProduced")
threshold = literal(3.14)
```

- `reference()`가 File 대상에 대해 값 대신 참조를 돌려주는 것은 연산에 파일을 참조로 넘기기
  위해서다. 값이 필요한 연산자(`SetElementOperator`)는 참조를 받으면 다시 값으로 읽는다.
- `literal()`은 `ElementValue`는 그대로 두고, 그 외의 값은 `mdt_value()`로 감싼다. `mdt_value()`는
  스칼라(`str`/`bool`/`int`/`float`/`timedelta`)만 받으므로 다른 타입은 **생성 시점**에 `ValueError`가
  발생한다. 컬렉션·리스트·File·Range·DateTime 등 구조가 있는 값은 `ElementValue`로 만들어 넘긴다.

  ```python
  import mdtpy
  literal(mdtpy.value.parse_json_node({ ... }))   # mdt-workflow가 생성하는 DAG의 방식
  ```

### `sink()` — 결과를 기록할 위치

`outputs`는 **출력 이름 → 기록 위치(`ElementReference`)** 매핑이다. 기록 위치는 입력 명세가 아니라
실제 `ElementReference`여야 하므로 `sink(ref_string)`(= `mdtpy.reference(ref_string)`)로 만든다.

> **주의**: `reference()`는 **입력 명세**(`ElementReferenceArgument`)를, `sink()`는 **기록 위치**
> (`ElementReference`)를 만든다. `outputs`에 `reference()`를 쓰면 동작하지 않는다.

## Operator — task 본문

모든 연산자는 `run(context=None)`으로 실행되며, `context`가 `None`이면 `AirflowDagContext()`를
생성한다. 연산자 고유의 인자는 생성자 인자로 직접 받고, `inputs`/`outputs`는 항상 키워드 dict로 받는다.

| 연산자 | 생성자 | 무엇을 실행하는가 |
|---|---|---|
| `SetElementOperator` | `(inputs, outputs={})` | `inputs['source']` 값을 읽어 `outputs['target']`(선택)에 기록 — 연산 호출 없음 |
| `OperationSubmodelOperator` | `(instance, submodel, *, inputs, outputs={})` | MDT Operation submodel 호출 (등록정보 기반) |
| `AASOperationOperator` | `(instance, submodel, path, *, inputs, outputs={})` | submodel 내 AAS `Operation`을 idShort 경로로 직접 호출 |
| `RestfulAsyncRpcOperator` | `(base_url, op_endpoint, *, inputs, outputs={})` | 원격 연산을 비동기 RESTful RPC로 호출 (상태 폴링) |
| `RestfulRpcOperator` | `(op_url, *, timeout=None, inputs, outputs={})` | 원격 연산을 동기 RESTful RPC로 호출 (단일 POST) |
| `PythonScriptOperator` | `(script, *, inputs, outputs={})` | 인라인 Python script 실행 |

연산자마다 **어떤 결과가 후속 task로 전달되는지**가 다르다.

| 연산자 | task 출력으로 전달되는 값 |
|---|---|
| `SetElementOperator` | 읽은 값 하나, 항상 `'target'` 키 |
| `OperationSubmodelOperator` / `AASOperationOperator` / `RestfulAsyncRpcOperator` | 연산이 반환한 **모든** 결과 |
| `RestfulRpcOperator` | `outputs`에 **선언된 출력만** (선언했는데 반환되지 않으면 `KeyError`). 기록 위치가 `None`이면 기록 없이 전달만 한다 |
| `PythonScriptOperator` | script가 `outputs` dict에 넣은 **모든** 값. `outputs` 인자는 그중 무엇을 어디에 기록할지만 정한다 |

각 연산자의 상세 동작, 오류 조건, 예제는 [operator/README.md](operator/README.md)를 참고한다.

## DagContext — 실행 환경 어댑터

`DagContext`는 연산자가 실행 중에 쓰는 런타임 기능을 추상화한다. 여섯 멤버가 모두 추상이다.

| 멤버 | 역할 |
|---|---|
| `task_id` (property) | 현재 실행 중인 task id |
| `mdt_manager` (property) | 접속한 `MDTInstanceManager` |
| `get_submodel(instance, submodel_idshort)` | instance의 submodel 서비스 조회 |
| `resolve_reference(ref_string)` | 참조 문자열을 `ElementReference`로 해석 |
| `get_task_output(task_id, arg_id)` | 선행 task의 출력 조회. 없으면 `KeyError` |
| `set_task_outputs(outputs)` | 현재 task의 출력 저장. 값이 `ElementValue`가 아니면 `TypeError` |

### `LocalDagContext(task_id, mdt_inst_url)` — Airflow 없이 실행

- MDT Instance Manager URL은 **필수** 인자이며, Airflow에 전혀 의존하지 않는다.
- task 출력은 클래스 변수 `__TASK_OUTPUT`에 보관되므로, 같은 프로세스 안에서 만든 인스턴스끼리
  출력이 공유된다. 그래서 task를 순차적으로 실행하며 `task_output()`으로 값을 넘길 수 있다.
- `resolve_reference()`는 참조 문자열을 `mdtpy.reference()`로 감싸기만 하고 서버에 질의하지 않는다.

> **주의**: `__TASK_OUTPUT`은 같은 프로세스 안에서 계속 누적된다. 테스트마다 깨끗한 상태가
> 필요하면 `LocalDagContext._LocalDagContext__TASK_OUTPUT.clear()`로 명시적으로 초기화한다.

### `AirflowDagContext(mdt_manager_url=None)` — 실제 Airflow 환경

- `airflow.sdk`의 `Variable` / `get_current_context()` / XCom을 사용한다.
- `mdt_manager_url`을 생략하면 Airflow `Variable`의 `mdt_manager_url`을 읽는다.
- 생성자에서 `connect()`로 `MDTInstanceManager`를 만들지만, `connect()`는 URL을 담은 클라이언트
  객체만 만들 뿐 서버와 통신하지 않는다. 실제 통신은 submodel 조회나 참조 해석 시점에 일어난다.
- `task_id`는 현재 실행 컨텍스트의 task instance(`ti`)에서 얻는다.
- `resolve_reference()`는 `MDTInstanceManager.resolve_reference()`로 서버에 질의하여 해석한다.
- task 출력은 XCom의 `'task_output'` 키로 주고받는다 (`xcom_pull(task_ids=..., key='task_output')`).
  XCom은 JSON 직렬화 가능한 값만 허용하므로 `ElementValue`는 `@type`/`value` JSON 형태로
  직렬화되어 저장되고, 조회 시 자동으로 복원된다.

## 주의사항

- **`run()`의 기본 컨텍스트는 `AirflowDagContext`다.** Airflow 밖에서 실행할 때는
  `LocalDagContext`를 반드시 명시적으로 넘긴다.
- **task 출력은 `ElementValue`만 허용된다.** 두 컨텍스트 모두 그 외 타입은 `TypeError`로 거부한다.
- **연산자 클래스는 `from mdtpy.airflow import X` 또는 `from mdtpy.airflow.operator import X`로
  import한다.** `mdtpy.airflow.operator`를 속성으로 접근하면 패키지가 아니라 `operator/operator.py`
  모듈이 잡히므로, `import mdtpy.airflow.operator as op`나 `patch("mdtpy.airflow.operator.<모듈>....")`
  같은 문자열 경로는 의도한 대로 동작하지 않는다. 테스트에서는 하위 모듈을 직접 import하고
  (`from mdtpy.airflow.operator import restful_async_rpc`) `patch.object`를 쓴다.
- `PythonScriptOperator`의 `script`는 `exec()`로 실행되므로 DAG 작성자가 제공한 코드를 그대로
  신뢰한다. 외부 입력으로 script 본문을 조립하지 않는다.

## 패키지 구성

| 파일 | 내용 |
|---|---|
| `dag_task_argument.py` | `DagTaskArgument`와 세 구현, 팩토리 `task_output` / `reference` / `literal` / `sink` |
| `dag_context.py` | `DagContext`, `LocalDagContext`, `AirflowDagContext` |
| `operator/` | `Operator` ABC와 여섯 연산자 구현 ([operator/README.md](operator/README.md)) |
| `types.py` | 타입 alias `ArgumentValue`(= `ElementValue \| ElementReference \| SubmodelElement`), `TaskOutput`(= `ElementValue`) |
| `__init__.py` | 위 모듈들을 모두 re-export |

## 관련 문서

- [operator/README.md](operator/README.md) — 연산자별 상세 동작과 예제
- [../ref/README.md](../ref/README.md) — 참조 표현식과 `ElementReference`
- [../rpc/README.md](../rpc/README.md) — RESTful RPC 클라이언트 (동기/비동기)
- `src/samples/sample_python_script.py`, `src/samples/sample_inspector_simiulation.py`,
  `src/samples/sample_estimate_throughput.py` — `LocalDagContext`로 실행하는 예제
- `tests/test_airflow.py` — 단위 테스트 (Airflow 설치 없이 실행)
