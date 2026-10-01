# mdtpy.rpc — RESTful RPC 클라이언트 패키지

MDT 연산 서버의 **원격 연산(operation)** 을 HTTP 로 호출하는 클라이언트를 제공한다.
동기 클라이언트(`RESTfulRpcClient`)와 세션 기반 비동기 클라이언트
(`RESTfulAsyncRpcClient`) 두 가지가 있으며, 값 인코딩은 `mdtpy.value` 의
`@type` polymorphic JSON 형식(Java `mdt.model.sm.value` 와 wire 호환)을 그대로 쓴다.

> **import 경로 주의**: 코드는 전부 `mdtpy.rpc.restful` 아래에 있고,
> `mdtpy/__init__.py` 가 자동 import 하지 않는다. 반드시 명시적으로 import 한다.
>
> ```python
> from mdtpy.rpc.restful import RESTfulRpcClient, RESTfulAsyncRpcClient
> ```

## 빠른 시작

### 비동기 클라이언트 (권장 — 세션 폴링, 취소/타임아웃 지원)

```python
import mdtpy
from mdtpy import reference
from mdtpy.rpc.restful import RESTfulAsyncRpcClient

manager = mdtpy.connect("http://localhost:12985/instance-manager")
data = manager.instances['test'].parameters['Data']

client = RESTfulAsyncRpcClient(
    base_url="http://localhost:12987/api/v1",
    op_endpoint="/operations/AddAndSleep",   # 반드시 '/' 로 시작
    inputs={
        "Data": data,          # ElementReference → 참조 값이 읽혀 전송된다
        "IncAmount": 3,        # 리터럴(str/int/float/bool)은 그대로 전송
        "SleepTime": 2.7,
    },
    poll_interval=3.0,         # 세션 상태 폴링 주기 (기본 3초)
    timeout=600.0,             # 전체 완료 대기 제한 (None 이면 무제한)
)
outputs = client.call()        # 완료까지 블록, dict[str, Any] 반환
data.update_with_raw_value(outputs['Output'])
```

출력 인자를 참조로 지정하면 서버가 결과를 해당 요소에 직접 쓰게 할 수 있다:

```python
client = RESTfulAsyncRpcClient(
    base_url=BASE_URL, op_endpoint="/operations/ThicknessInspection",
    inputs={"UpperImage": reference("param:inspector:UpperImage")},
    outputs={"Defect": reference("oparg:inspector:ThicknessInspection:out:Defect")},
)
outputs = client.call()
```

### 동기 클라이언트 (한 번의 POST 로 끝나는 짧은 연산)

```python
from mdtpy.rpc.restful import RESTfulRpcClient

client = RESTfulRpcClient("http://localhost:12987/api/v1/operations/Add",
                          inputs={"a": 1, "b": 2})
outputs = client.call()
```

## 활용 가이드

### 입력 인자로 넘길 수 있는 타입 (`RpcArgument`)

| 타입 | 전송 방식 |
|---|---|
| `str` / `int` / `float` / `bool` | JSON 리터럴 그대로 |
| `ElementValue` | `@type` polymorphic JSON |
| `ElementReference` (일반 요소) | 참조 값을 읽어(`read_value()`) `@type` JSON 으로 |
| `ElementReference` (**File 요소**) | 값이 아니라 **참조 자체**(`mdt:ref:*` JSON)를 전송 — 서버가 파일을 참조로 처리 |

### 출력(`outputs`) 의 타입

`call()` 이 반환하는 dict 의 값은 서버 응답의 타입 태그에 따라 자동 변환된다:

| 응답 노드 | 변환 결과 |
|---|---|
| 스칼라 | 그대로 (`int`/`str`/...) |
| `@type: mdt:value:*` | `ElementValue` — `ref.update_value(outputs[k])` 로 바로 쓸 수 있다 |
| `@type: mdt:ref:*` | `ElementReference` (전역 `mdt_manager` 연결 필요) |
| `modelType` 보유 | basyx `SubmodelElement` |

### 상태별 결과 처리

`call()` 은 종료 상태에 따라 다음과 같이 동작한다 — 호출 코드는 예외 처리로 분기한다:

```python
from mdtpy.rpc.restful import RpcExecutionError, RpcCancelledError

try:
    outputs = client.call()
except RpcExecutionError as e:      # 원격 연산 FAILED
    print("원격 실패 원인:", e.__cause__)   # RestfulRemoteException (code/message 보유)
except RpcCancelledError:           # 원격 연산 CANCELLED
    ...
except TimeoutError:                # (비동기) timeout 내 미완료
    ...
```

- `e.__cause__` 는 `RestfulRemoteException` 으로, 서버 측 예외 클래스 이름(`code`)과
  메시지(`remote_message`)를 보유한다. 보안상 `code` 로 예외 클래스를 동적으로
  복원하지 않는다.

### 취소

`cancel()` 은 다른 스레드에서 `call()` 진행 중에 호출할 수 있다:

```python
ok = client.cancel()   # True: 취소 확정 / False: 이미 종료되어 취소 불가
```

취소 결과는 **HTTP 상태 코드**로 구분한다. 본문의 상태값이 아니다.

| DELETE 응답 | `cancel()` |
|---|---|
| `200` + `CANCELLED` | `True` — 취소 확정 |
| `409 Conflict` | `False` — 이미 종료되었거나 연산이 취소를 거부함 |
| `404 Not Found` | `RestfulRemoteException` 전파 — 세션이 없거나 보존 기간이 지남 |

`409` 와 `404` 는 다른 상황이므로 뭉뚱그리지 않는다. 전자는 "취소할 것이 없다", 후자는
"그런 세션이 없다" 이다.

## 주의사항

- **`op_endpoint` 는 `/` 로 시작해야 한다** — 호출 URL 이 `base_url + op_endpoint`
  단순 연결로 만들어진다.
- **타임아웃은 클라이언트만 멈춘다**: 비동기 `call()` 의 `timeout` 초과 시
  `TimeoutError` 가 나지만 서버 측 세션은 계속 실행된다. 중단이 필요하면 별도로
  `cancel()` 을 호출해야 한다.
- `timeout`(전체 대기)과 `request_timeout`(개별 HTTP 요청, 기본 30초)은 다른
  파라미터다.
- `mdt:ref:*` 출력 파싱과 `ElementReference` 입력 인코딩은 **`mdtpy.connect()` 가
  선행**되어야 한다 (전역 `mdt_manager` 사용).
- 기본값으로 TLS 인증서를 검증하지 않는다(`verify_tls=False`, 자체 서명 인증서
  환경). 공개망에서는 `verify_tls=True` 를 지정한다.
- `session_url` 은 `call()` 로 연산을 시작하기 전에는 `None` 이고, 이 상태에서
  `cancel()` 을 호출하면 `RuntimeError` 가 발생한다.
- `inputs` dict 는 복사 없이 보관되며 실제 인코딩은 `call()` 시점에 수행된다 —
  클라이언트 생성 후 `call()` 전에 dict 를 수정하면 수정된 값이 전송된다.

## 패키지 구성 (`rpc/restful/`)

| 파일 | 내용 |
|---|---|
| `restful_rpc_client.py` | `RESTfulRpcClient` — 동기 호출 (블로킹 POST 1회) |
| `restful_async_rpc_client.py` | `RESTfulAsyncRpcClient` — 세션 시작 후 상태 폴링, `cancel()` 지원 |
| `rpc_request_message.py` | `RpcRequestMessage` DTO (`inputs`/`outputs` + 추가 필드 보존) |
| `rpc_response_message.py` | `RpcResponseMessage` DTO, `parse_response_message()`, 출력 인자 파서 |
| `rpc_state.py` | `RpcState` (`RUNNING`/`COMPLETED`/`FAILED`/`CANCELLED`) |
| `error.py` | `RestfulErrorEntity`, `RestfulRemoteException`, `RpcExecutionError`, `RpcCancelledError` |
| `common.py` | `DEFAULT_TIMEOUT`/`VERIFY_TLS`, `RpcArgument`, 입력 인자 인코더 |

실행 가능한 전체 예제: [`src/samples/sample_restful_async_rpc.py`](../../samples/sample_restful_async_rpc.py)
(실서버 필요). 값 모델은 [`mdtpy.value`](../value/README.md), 참조는
[`mdtpy.ref`](../ref/README.md) 참조.
