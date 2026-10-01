# mdtpy.airflow.operator — Airflow task 본문 연산자 패키지

Airflow task 하나의 **본문(body)** 으로 실행되는 `Operator` 구현들을 모아둔 패키지다.
각 `Operator`는 "무엇을 실행할지"(연산 위치, script, AI 모델 URL 등)와 "입력 값을 어디서
가져올지"(`inputs`), "결과를 어디에 기록할지"(`outputs`)를 **DAG 정의 시점**에 명세로 받고,
**task 실행 시점**에 `run(context)`가 호출되면 `DagContext`를 통해 실제 값을 해석하여 동작한다.

```python
from mdtpy.airflow import OperationSubmodelOperator, reference, sink   # 상위 패키지에서도 노출된다
from mdtpy.airflow.operator import OperationSubmodelOperator           # 직접 import 도 가능
```

> **Note**: `mdtpy.airflow`는 `mdtpy/__init__.py`에서 자동 import 되지 않는다. 또한
> `Operator.run()`에 `context`를 넘기지 않으면 `AirflowDagContext()`가 생성되므로,
> Airflow 밖에서 실행할 때는 `LocalDagContext`를 명시적으로 전달해야 한다.

## 빠른 시작

```python
from mdtpy.airflow import LocalDagContext, reference, task_output, literal, sink
from mdtpy.airflow import SetElementOperator, OperationSubmodelOperator

MDT_MANAGER_URL = "http://localhost:12985/instance-manager"

# 1) CycleTime 값을 읽어 task 출력('target')으로 남긴다.
SetElementOperator(
    inputs = { 'source': reference("param:heater:CycleTime") }
).run(LocalDagContext("get_heater_cycle_time", MDT_MANAGER_URL))

# 2) 선행 task의 출력을 입력으로 받아 Operation submodel을 호출하고,
#    결과를 SubmodelElement에 기록한다.
OperationSubmodelOperator(
    instance = "innercase",
    submodel = "ProcessOptimization",
    inputs = {
        'HTCycleTime': task_output("get_heater_cycle_time", "target"),
        'Efficiency': literal(0.85),
    },
    outputs = {
        'TotalThroughput': sink("param:innercase:CycleTime"),
    }
).run(LocalDagContext("innercase_optimization", MDT_MANAGER_URL))
```

Airflow DAG 안에서는 task callable 본문에서 `run()`을 호출한다 (`context` 생략 시
`AirflowDagContext`가 사용된다).

```python
from airflow.sdk import dag, task
from mdtpy.airflow import OperationSubmodelOperator, reference, sink

@dag(schedule=None)
def innercase_dag():
    @task
    def process_optimization():
        OperationSubmodelOperator(
            instance = "innercase",
            submodel = "ProcessOptimization",
            inputs = { 'HTCycleTime': reference("param:heater:CycleTime") },
            outputs = { 'TotalThroughput': sink("param:innercase:CycleTime") },
        ).run()          # -> AirflowDagContext (XCom + Variable 사용)
    process_optimization()
innercase_dag()
```

## 공통 규약

### `inputs` — 입력 값을 어디서 가져올지

`inputs`는 **입력 이름 → `DagTaskArgument`** 매핑이며, 값은 `mdtpy.airflow`의 세 팩토리로 만든다.

| 팩토리 | 의미 | `get()`이 돌려주는 것 |
|---|---|---|
| `task_output(task_id, arg_id)` | 선행 task가 남긴 출력 값 | `ElementValue` |
| `reference(ref_string)` | 참조 대상의 **값을 읽어** 전달 | `ElementValue`, 단 File이면 `ElementReference` 자체, `timeseries:` 참조면 `SubmodelElement` |
| `literal(value)` | 고정 리터럴 (raw 스칼라는 `mdt_value()`로 감싸짐) | `ElementValue` |

### `outputs` — 결과를 어디에 기록할지

`outputs`는 **출력 이름 → 기록 위치(`ElementReference`)** 매핑이다. 기록 위치는 입력 명세가
아니라 실제 `ElementReference`여야 하므로 **`sink(ref_string)`**(= `mdtpy.reference(...)`)로 만든다.

> **주의**: 이름이 같은 두 함수가 있다. `reference()`는 **입력 명세**(`ElementReferenceArgument`)를,
> `sink()`는 **기록 위치**(`ElementReference`)를 만든다. `outputs`에 `reference()`를 쓰면 동작하지 않는다.

`outputs`를 생략하면 SubmodelElement에는 아무것도 기록하지 않고 task 출력만 남긴다.

### task 출력

모든 연산자는 마지막에 `context.set_task_outputs(...)`로 결과를 남기며, 후속 task는
`task_output(task_id, arg_id)`로 이를 참조한다. task 출력 값은 반드시 `ElementValue`이고
(그 외 타입은 `TypeError`), `AirflowDagContext`에서는 XCom(`'task_output'` 키)에
`@type`/`value` JSON 형태로 직렬화되어 저장된다.

## 연산자 한눈에 보기

| 연산자 | 무엇을 실행하는가 | 모듈 |
|---|---|---|
| `SetElementOperator` | 값 읽기 / 복사 (연산 호출 없음) | `set_element.py` |
| `OperationSubmodelOperator` | MDT Operation submodel 호출 (등록정보 기반) | `operation_submodel.py` |
| `AASOperationOperator` | submodel 내 AAS `Operation`을 idShort 경로로 직접 호출 | `aas_operation.py` |
| `RestfulAsyncRpcOperator` | 원격 연산을 비동기 RESTful RPC로 호출 (상태 폴링) | `restful_async_rpc.py` |
| `AIModelCallOperator` | AI 모델 연산을 동기 RESTful RPC로 호출 (단일 POST) | `ai_model_call.py` |
| `PythonScriptOperator` | 인라인 Python script 실행 | `python_script.py` |

동작 차이가 실제로 문제가 되는 두 지점:

| | 선언되지 않은 출력 | `outputs` 값에 `None` |
|---|---|---|
| `OperationSubmodelOperator` / `AASOperationOperator` / `RestfulAsyncRpcOperator` | 연산이 반환한 **모든** 결과가 task 출력으로 전달된다 | 허용되지 않음 (기록 시 오류) |
| `AIModelCallOperator` / `PythonScriptOperator` | **선언된 출력만** task 출력으로 전달된다 (나머지는 무시) | 허용됨 — 기록은 생략하고 후속 task에만 전달 |
| `SetElementOperator` | 출력 이름은 항상 `'target'` 하나 | 해당 없음 |

또한 `AIModelCallOperator` / `PythonScriptOperator`는 선언된 출력이 산출되지 않으면
`KeyError`를 발생시키며, 일부만 기록된 채 실패하지 않도록 **모든 출력 값을 먼저 변환한 뒤에** 기록한다.

---

## `SetElementOperator(inputs, outputs={})`

`source` 입력에서 값을 읽고, `target` 출력이 지정된 경우 그 위치에 기록한다. 연산 호출은 없다.
읽은 값은 언제나 `'target'` 키로 task 출력에 저장된다.

- `inputs`에 `'source'`가 없으면 **생성 시점**에 `ValueError`.
- `outputs`가 비어 있지 않은데 `'target'`이 없으면 **생성 시점**에 `ValueError`.
- `source`가 File 참조여도 값(`FileValue`)으로 읽는다 — 이 경로에서는 파일을 두 번 읽게 된다.

```python
# 읽기만: 후속 task에 값 전달용
SetElementOperator(
    inputs = { 'source': reference("param:heater:CycleTime") }
).run(ctx)

# 복사: 읽은 값을 다른 위치에도 기록
SetElementOperator(
    inputs = { 'source': reference("param:heater:CycleTime") },
    outputs = { 'target': sink("param:other:CycleTime") },
).run(ctx)

# 후속 task에서
task_output("get_heater_cycle_time", "target")
```

## `OperationSubmodelOperator(instance, submodel, *, inputs, outputs={})`

`instance`의 `submodel`(idShort)을 조회하여 MDT Operation submodel로 호출한다.
`inputs`를 해석한 값과 `outputs`의 `ElementReference`를 **하나의 kwargs로 병합**해
`OperationSubmodelService.invoke()`에 넘긴다 — `invoke()`가 출력 인자로 전달된 참조에
결과를 자동으로 기록하기 때문이다.

- 조회한 submodel이 `OperationSubmodelService`가 아니면 `ValueError`.
- 지정하지 않은 입력 인자는 연산 등록정보(descriptor)의 **기본 참조**로 채워진다.
- `outputs`에 참조를 주지 않은 출력 인자도 등록정보에 정의된 참조에 기록된다.
- 연산이 반환한 모든 출력이 task 출력으로 전달된다.

```python
OperationSubmodelOperator(
    instance = "inspector",
    submodel = "ProcessSimulation",
    inputs = { 'DefectList': task_output("update_defect_list", "UpdatedDefectList") },
    outputs = { 'AverageCycleTime': sink("param:inspector:CycleTime") },
).run(ctx)
```

## `AASOperationOperator(instance, submodel, path, *, inputs, outputs={})`

submodel 내부의 AAS `Operation` SubmodelElement를 **idShort 경로(`path`)** 로 직접 지정해
호출한다 (`AASOperationService`). 등록정보 기반의 기본 입력/출력 참조 보완이 없는, 더 낮은
수준의 호출이다.

- 조회한 submodel이 `OperationSubmodelService`가 아니면 `ValueError`.
- `path`가 가리키는 요소가 `model.Operation`이 아니면 `ValueError`.
- 반환된 결과 중 `outputs`에 선언된 것만 기록되고, **모든** 결과가 task 출력으로 전달된다.

```python
AASOperationOperator(
    instance = "test",
    submodel = "AddAndSleep",
    path = "Operation",
    inputs = {
        'Data': task_output("get_heater_cycle_time", "target"),
        'IncAmount': task_output("count_records", "Count"),
        'SleepTime': literal(3.5),
    },
    outputs = { 'Output': sink("param:test:Data") },
).run(ctx)
```

## `RestfulAsyncRpcOperator(base_url, op_endpoint, *, inputs, outputs={})`

원격 연산을 **비동기** RESTful RPC로 호출한다(`RESTfulAsyncRpcClient`). 최초 POST로 연산을
시작해 세션을 얻고, 이후 세션 상태를 주기적으로 폴링하여 종료를 기다린다 (기본 폴링 주기 3초,
전체 대기 시간 제한 없음).

- 최종 호출 URL은 `base_url + op_endpoint`로 단순 연결되므로 `op_endpoint`는 `/`로 시작해야 한다.
- `base_url` / `op_endpoint`가 비어 있으면 `ValueError`.
- 연산이 `FAILED`면 `RpcExecutionError`(원인 예외가 `__cause__`), `CANCELLED`면 `RpcCancelledError`.
- `ElementValue`가 아닌 결과 값은 `mdt_value()`로 감싸 변환한 뒤 기록/전달한다.
- 반환된 결과 중 `outputs`에 선언된 것만 기록되고, **모든** 결과가 task 출력으로 전달된다.

```python
RestfulAsyncRpcOperator(
    base_url = "http://localhost:12987",
    op_endpoint = "/api/v1/operations/UpdateDefectList",
    inputs = {
        'Defect': task_output("inspect_image", "Defect"),
        'DefectList': reference("param:inspector:DefectList"),
    },
    outputs = { 'UpdatedDefectList': sink("param:inspector:DefectList") },
).run(ctx)
```

시계열 데이터를 입력으로 넘길 때는 `timeseries:` 참조를 사용한다.

```python
inputs = {
    'TimeSeriesData':
        reference("timeseries:Welder:NozzleProductionLog#last=50s|Time,QuantityProduced"),
}
```

## `AIModelCallOperator(model_url, *, timeout=None, inputs, outputs={})`

AI 모델 연산을 **동기** RESTful RPC로 호출한다(`RESTfulRpcClient`). 상태 폴링 없이 단일 POST가
연산 종료 시점까지 블록하고, 그 응답에 출력이 실려온다. 그래서 `base_url` + `op_endpoint`로
나누지 않고 모델 URL 전체를 `model_url`로 받는다.

- `timeout`(초)은 응답 대기 제한이며 기본값은 **제한 없음**(`None`) — AI 모델 추론이 수 분
  이상 걸릴 수 있기 때문이다.
- `model_url`이 비어 있으면 `ValueError`.
- 입력은 `encode_argument_to_json_node()`로 JSON 노드로 변환되어 전송된다 (File 참조는 값 대신
  참조 자체가 전송된다).
- `outputs`에 선언한 출력을 연산이 반환하지 않으면 `KeyError`.
- 선언된 출력만 task 출력으로 전달되며, 기록 위치가 `None`인 출력은 후속 task에만 전달된다.

```python
AIModelCallOperator(
    "http://localhost:9000/api/v1/models/defect-detector",
    timeout = 600,                       # 생략하면 무제한 대기
    inputs = { 'UpperImage': reference("param:inspector:UpperImage") },
    outputs = {
        'Defect': sink("param:inspector:Defect"),   # 기록 + 후속 task 전달
        'Confidence': None,                         # 후속 task 전달만
    },
).run(ctx)
```

## `PythonScriptOperator(script, *, inputs, outputs={})`

인라인 Python script를 실행한다. script는 `inputs`라는 이름의 dict(입력 이름 → 해석된 입력 값)를
전역 변수로 받고, 실행이 끝나면 `outputs`에 선언된 **이름과 같은 변수**의 값이 출력으로 수집된다.

- `inputs[...]` 값은 raw 값이 아니라 `ElementValue`다 — 원시 값이 필요하면 `to_raw_object()`를 쓴다.
- script는 단일 namespace(globals=locals)에서 실행되므로, 최상위에서 정의한 이름과 `import`한
  모듈을 함수/lambda/generator 안에서도 사용할 수 있다.
- 선언된 출력 변수를 script가 정의하지 않으면 `KeyError`.
- `ElementValue`가 아닌 값은 `mdt_value()`로 감싸 변환된다.
- 선언된 출력만 task 출력으로 전달되며, 기록 위치가 `None`인 출력은 후속 task에만 전달된다.

```python
SCRIPT = """
cycle_times = { name: value.to_raw_object() for name, value in inputs.items() }

BottleneckProcess = max(cycle_times, key=lambda name: cycle_times[name])
BottleneckCycleTime = float(cycle_times[BottleneckProcess])
"""

PythonScriptOperator(
    SCRIPT,
    inputs = {
        'heater': reference("param:heater:CycleTime"),
        'trimmer': reference("param:trimmer:CycleTime"),
        'former': reference("param:former:CycleTime"),
    },
    outputs = {
        'BottleneckCycleTime': sink("param:test:Data"),   # 기록 + 후속 task 전달
        'BottleneckProcess': None,                        # 후속 task 전달만
    },
).run(ctx)
```

> **주의**: `script`는 `exec()`로 실행되므로 DAG 작성자가 제공한 코드를 그대로 신뢰한다.
> 외부 입력으로 script 본문을 조립하지 않는다.

## 주의사항

- **`run()`의 기본 컨텍스트는 `AirflowDagContext`다.** Airflow 밖(단위 테스트, 샘플 스크립트)에서는
  `LocalDagContext(task_id, mdt_manager_url)`를 반드시 넘긴다. `LocalDagContext`의 task 출력
  저장소는 **클래스 변수**이므로 같은 프로세스 안에서 상태가 누적된다.
- **`reference()`와 `sink()`를 혼동하지 않는다** (입력 명세 vs 기록 위치).
- **task 출력은 `ElementValue`만 허용된다.** XCom 경로에서는 `@type`/`value` JSON으로
  직렬화되므로 JSON 직렬화 불가능한 값은 전달할 수 없다.
- **연산자 객체는 DAG 정의 시점에 생성되고 `run()`은 task 실행 시점에 호출된다.** 생성자에서
  검증되는 오류(`SetElementOperator`의 `'source'` 누락, `literal()`의 미지원 타입 등)는 DAG
  파싱 단계에서 드러나고, 나머지(연산 호출 실패, 출력 누락 등)는 task 실행 중에 드러난다.
- 각 연산자는 `logger.info`로 호출 대상과 `inputs`/`outputs` 명세를 기록한다 (`RestfulAsyncRpcOperator`는
  클라이언트 쪽 로그만 남긴다). Airflow task 로그에서 인자 해석 결과를 확인할 때 유용하다.

## 패키지 구성

| 파일 | 내용 |
|---|---|
| `operator.py` | `Operator` ABC, 타입 alias `DagTaskInputArgument`(= `DagTaskArgument`) / `DagTaskOutputArgument`(= `ElementReferenceArgument`) |
| `set_element.py` | `SetElementOperator` |
| `operation_submodel.py` | `OperationSubmodelOperator` |
| `aas_operation.py` | `AASOperationOperator` |
| `restful_async_rpc.py` | `RestfulAsyncRpcOperator` |
| `ai_model_call.py` | `AIModelCallOperator` |
| `python_script.py` | `PythonScriptOperator` |
| `__init__.py` | 위 구현들을 모두 re-export |

## 관련 문서

- [../README.md](../README.md) — `mdtpy.airflow` 전체 (`DagContext`, `DagTaskArgument`)
- [../../ref/README.md](../../ref/README.md) — 참조 표현식과 `ElementReference`
- [../../rpc/README.md](../../rpc/README.md) — RESTful RPC 클라이언트 (동기/비동기)
- `src/samples/sample_python_script.py`, `src/samples/sample_inspector_simiulation.py` — 실행 가능한 예제
