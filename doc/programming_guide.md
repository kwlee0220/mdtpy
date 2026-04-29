# mdtpy Programming Guide

이 문서는 AI 코딩 에이전트(Claude, Cursor 등)가 mdtpy 라이브러리를 활용하여
MDT(Manufacturing Digital Twin) 플랫폼 응용 프로그램을 작성할 때 참고할 수 있는 API 활용 가이드이다.

## 1. MDT 플랫폼 접속

모든 응용 프로그램은 `mdtpy.connect()`로 MDT Instance Manager에 접속하는 것으로 시작한다.

```python
import mdtpy

manager = mdtpy.connect("http://localhost:12985/instance-manager")
```

`manager`는 `MDTInstanceManager` 객체로, 이후 모든 인스턴스 접근의 시작점이다.
`mdtpy.connect()`는 모듈-수준 전역(`mdtpy.instance.mdt_manager`)도 함께 설정하므로,
`LazyElementReference` 같은 지연 해석 객체가 동일 매니저를 참조할 수 있다.

## 2. 인스턴스 접근 및 제어

### 인스턴스 가져오기

```python
instance = manager.instances['test']  # ID로 접근 (dict-like)
```

`manager.instances`는 `MDTInstanceCollection`으로 `Mapping`-유사 인터페이스를 제공한다:

```python
'test' in manager.instances              # __contains__ (200/404 분기)
len(manager.instances)                   # 등록된 인스턴스 개수
for inst in manager.instances:           # iteration
    print(inst.id)
list(manager.instances.find('id like %twin%'))   # 서버 측 필터링
```

**Note**: `bool(manager.instances)`는 컬렉션의 truthy 검사로 항상 `True`를 반환한다 (HTTP 호출 없음).
**비어있는지 확인하려면 `len(manager.instances) == 0`을 명시적으로 사용한다.**
또한 `__contains__`/`__getitem__`은 200/404 외의 상태 코드(5xx 등)에 대해 `MDTException`을 발생시키므로
서버 일시 장애가 "없는 인스턴스"로 둔갑하지 않는다.

### 인스턴스 등록 / 제거

```python
# 디렉토리를 zip 번들로 만들어 업로드
manager.instances.add('new-inst', port=9000, inst_dir='/path/to/bundle')

# 단일 제거 (ID URL-encoded)
del manager.instances['some-id']
manager.instances.remove('some-id')   # __delitem__과 동일

# 모두 제거
manager.instances.remove_all()
```

`add()`는 `inst_dir`이 디렉토리가 아니면 `ValueError`를 발생시키며, 임시 zip 파일은 자동 정리된다.

### 인스턴스 상태 확인 및 시작/중지

```python
if not instance.is_running():
    instance.start()          # 시작 완료까지 blocking
    assert instance.is_running()

instance.stop()               # 중지 완료까지 blocking
instance.start(nowait=True)   # 비동기 시작 (blocking 없음)
```

인스턴스 상태: `STOPPED`, `STARTING`, `RUNNING`, `STOPPING`, `FAILED`.

`start()`/`stop()`은 PUT 요청 후 즉시 디스크립터를 갱신하고 상태를 검증한다.
잘못된 전이(예: `STOPPED` 상태에서 `start()` 후 `STOPPED`로 응답이 온 경우)는
즉시 `InvalidResourceStateError`로 실패한다. 폴링 중 `STOPPING → FAILED`처럼
`STOPPED`가 아닌 종료 상태가 되어도 무한 대기하지 않고 정상 종료된 뒤 호출자가
최종 상태를 검증한다.

```python
# 디스크립터를 강제로 다시 읽어오기 (캐시 무효화)
instance.reload_descriptor()
```

### 인스턴스 주요 속성

```python
instance.id                    # 인스턴스 ID
instance.aas_id                # AAS 식별자
instance.aas_id_short          # Optional[str]
instance.global_asset_id       # Optional[str]
instance.asset_type            # Optional[MDTAssetType]
instance.asset_kind            # Optional[AssetKind]
instance.base_endpoint         # Optional[str]
instance.status                # MDTInstanceStatus enum
instance.descriptor            # InstanceDescriptor (전체 메타데이터)
instance.parameters            # MDTParameterCollection
instance.submodel_descriptors  # dict[str, MDTSubmodelDescriptor]
instance.operation_descriptors # dict[str, MDTOperationDescriptor]
instance.submodel_services     # SubmodelServiceCollection[SubmodelService]
instance.operations            # SubmodelServiceCollection[OperationSubmodelService]
instance.timeseries            # SubmodelServiceCollection[TimeSeriesService]
```

`parameters` / `submodel_descriptors` / `operation_descriptors` 속성은 인스턴스가
`RUNNING` 상태가 아니면 `InvalidResourceStateError`를 발생시킨다.

## 3. 파라미터 읽기/쓰기

파라미터는 인스턴스의 주요 데이터 값을 나타내며, `ElementReference`를 확장한 `MDTParameter` 객체로 접근한다.

`MDTParameterCollection`은 읽기 전용 `Mapping[str, MDTParameter]`이며, 동일한 ID가
중복으로 등록되면 생성 시점에 `MDTException("Duplicate MDTParameter id: ...")`을 발생시킨다.

### 단순 값 (Property)

```python
parameters = instance.parameters

status = parameters['Status']
print(status.id)           # 파라미터 ID
print(status.name)         # Optional[str] (사람이 읽는 이름)
print(status.model_type)   # SubmodelElement 타입 (예: Property)
print(status.value_type)   # 값 타입 (예: xs:string)

# 값 읽기
v = status.read_value()    # -> Python 값 (str, int, float 등)
print(v)                   # 'IDLE'

# 값 쓰기
status.update_value('Running')
```

### 복합 값 (SubmodelElementCollection)

Collection 타입 파라미터의 값은 `dict`로 반환된다.

```python
production = parameters['NozzleProduction']
v = production.read_value()
# v = {'QuantityProduced': 100, 'QuantityDefect': 2, ...}

v['QuantityProduced'] = v['QuantityProduced'] + 10
production.update_value(v)
```

### 파일 첨부 (File 타입 파라미터)

```python
param = instance.parameters['UpperImage']

# 파일 업로드
param.put_attachment('/path/to/image.jpg', 'image/jpg')
# content_type 생략 가능: param.put_attachment('/path/to/image.jpg')
# content_type 미지정 시 Tika가 자동 추정한다.

# 파일 다운로드
data: bytes = param.get_attachment()

# 파일 삭제
param.delete_attachment()
```

## 4. Reference 해석

MDT 플랫폼의 참조 문자열(reference string)을 통해 SubmodelElement에 직접 접근할 수 있다.
`resolve_reference()`는 다음 형식을 지원한다:

| 형식 | 의미 |
|---|---|
| `param:<instance>:<parameter>` | 파라미터 직접 참조 (서버 호출 없음, 로컬 lookup) |
| `oparg:<instance>:<operation>:in\|out:<argument>` | Operation 인자 참조 (로컬 lookup) |
| 그 외 | 서버 `/references/$url`에 위임하여 엔드포인트 조회 |

```python
# 일반 경로 (서버에 위임)
ref = manager.resolve_reference('test:Data:DataInfo.Equipment.EquipmentParameterValues[0].ParameterValue')

# 파라미터 참조 (로컬 매핑)
ref = manager.resolve_reference('param:test:SleepTime')

# Operation 인자 참조 (로컬 매핑)
in_arg = manager.resolve_reference('oparg:test:AddAndSleep:in:IncAmount')
out_arg = manager.resolve_reference('oparg:test:AddAndSleep:out:Output')
```

형식 위반 시 `ValueError`, 존재하지 않는 인스턴스/파라미터/오퍼레이션이면 `ResourceNotFoundError`,
서버 측 오류면 `MDTException`이 발생한다.

반환되는 `DefaultElementReference` 계열 객체는 다음 속성/메서드를 제공한다:

```python
ref.ref_string     # 참조 문자열
ref.model_type     # SubmodelElement 타입 (type 객체)
ref.id_short       # ID Short
ref.value_type     # 값 타입 (Property인 경우)

ref.read()         # -> model.SubmodelElement (전체 AAS 객체)
ref.read_value()   # -> Python 값
ref.update_value(new_value)

# File 타입인 경우
ref.put_attachment(file_path, content_type)
ref.get_attachment()  # -> Optional[bytes]
ref.delete_attachment()
```

`LazyElementReference`는 전역 `mdt_manager`를 통해 지연 해석되는 참조이다:

```python
from mdtpy import reference
lazy_ref = reference('param:inspector:UpperImage')  # 실제 접근 시점에 해석
```

## 5. Submodel 서비스

서브모델은 인스턴스의 데이터, 시뮬레이션, AI 모델 등을 제공하는 서비스 단위이다.

```python
svc = instance.submodel_services['Data']

# 서브모델 전체 읽기
sm = svc.read()  # -> basyx model.Submodel 객체

# 개별 SubmodelElement 접근 (점 경로와 인덱스 사용)
sme = svc.submodel_elements['DataInfo.Equipment.EquipmentParameters[0].ParameterID']
print(sme.id_short, sme.value)

# 값 읽기/쓰기
svc.submodel_elements.get_value('path.to.element')
svc.submodel_elements.update_value('path.to.element', new_value)

# ElementReference 획득
ref = svc.element_reference('path.to.element')
```

### `submodel_elements`의 경로 캐싱

`SubmodelElementCollection`은 `__iter__`/`__len__`/`__contains__`가 공유하는 경로 목록 캐시를
가진다. 첫 호출에서 한 번 페치하고 이후 메모리에서 사용하므로 같은 collection을 반복적으로
순회·검색해도 추가 HTTP 호출이 발생하지 않는다.

```python
elements = svc.submodel_elements

len(elements)          # 1회 GET (이후 캐시)
for path in elements:  # 추가 HTTP 없음
    ...
'X' in elements        # 메모리 검색 (HTTP 없음)

# 외부 변경을 반영하려면 명시적 무효화
elements.refresh()
```

`__setitem__`/`__delitem__`은 자동으로 캐시를 무효화한다.

### 서브모델 타입 확인

```python
svc.is_information_model()   # 정보 모델
svc.is_data()                # 데이터 모델
svc.is_simulation()          # 시뮬레이션 모델
svc.is_ai()                  # AI 모델
svc.is_time_series()         # 시계열 모델
```

서브모델 분류는 `MDTSubmodelDescriptor.semantic_id`로 결정되며,
`SubmodelServiceCollection`은 이 값에 따라 적절한 서비스 클래스를 인스턴스화한다.
- Data / InformationModel → `SubmodelService`
- Simulation / AI → `OperationSubmodelService` (operation descriptor 필요)
- TimeSeries → `TimeSeriesService`
- 그 외 semantic_id → 무시(컬렉션에 포함되지 않음)

## 6. Operation 호출

Operation은 AI, 시뮬레이션 등의 연산을 원격 실행하는 기능이다.

`ArgumentList`(input/output)는 동일한 ID가 중복으로 정의되면 생성 시점에
`MDTException("Duplicate Argument id: ...")`을 발생시킨다.

### 기본 호출

```python
op = instance.operations['AddAndSleep']

# invoke()에 키워드 인자로 전달
# - 값을 직접 전달하거나
# - MDTParameter/Argument 등 ElementReference 객체를 전달할 수 있다
result = op.invoke(IncAmount=20)
# result: dict[str, ElementValueType] (예: {'Output': 42})
print(result)
```

### 결과를 인스턴스에 반영

```python
# 출력 인자의 값을 업데이트
op.output_arguments['Output'].update_value(result['Output'])

# 입력 인자의 값을 업데이트 (다음 호출에 반영)
op.input_arguments['Data'].update_value(result['Output'])
```

### ElementReference를 인자로 전달

파라미터나 Argument 객체를 직접 인자로 전달하면, 해당 참조의 현재 값이 자동으로 사용된다.
출력 인자 자리에 `ElementReference`를 넣으면, `invoke()`가 결과 값을 해당 reference로 자동 갱신한다.

```python
data = instance.parameters['Data']
sleep_time = op.input_arguments['SleepTime']

# Output=data: invoke 후 data.update_value(result['Output'])이 자동 실행
result = op.invoke(Data=data, IncAmount=7, SleepTime=sleep_time, Output=data)
op.output_arguments.update_value(result)  # 모든 출력 인자를 한번에 업데이트
```

### 인자 인덱스 접근

`ArgumentList`는 ID(str) 또는 위치(int) 둘 다로 인자에 접근할 수 있다.

```python
op.input_arguments['IncAmount']   # ID로
op.input_arguments[0]             # 정의 순서대로
```

### 복합 워크플로우 예제

여러 Operation을 순차적으로 호출하여 파이프라인을 구성하는 패턴:

```python
manager = mdtpy.connect(url="http://localhost:12985/instance-manager")
inspector = manager.instances['inspector']

# Operation 획득
inspection = inspector.operations['ThicknessInspection']
update = inspector.operations['UpdateDefectList']
simulate = inspector.operations['ProcessSimulation']

# 파라미터 및 출력 인자 참조 획득
upper_image = inspector.parameters['UpperImage']
defect_list = inspector.parameters['DefectList']
cycle_time = inspector.parameters['CycleTime']
defect = inspection.output_arguments['Defect']

# 이미지 업로드 후 순차 호출
upper_image.put_attachment('/path/to/image.jpg')

inspection.invoke(UpperImage=upper_image, Defect=defect)
update.invoke(DefectList=defect_list, Defect=defect, UpdatedDefectList=defect_list)
simulate.invoke(DefectList=defect_list, AverageCycleTime=cycle_time)
```

## 7. 시계열 데이터

`TimeSeriesService`를 통해 시계열 데이터에 접근한다.

```python
ts_collection = instance.timeseries
print(len(ts_collection))

# 시계열 서비스 접근
ts_svc = ts_collection['WelderAmpereLog']
ts = ts_svc.timeseries()  # -> TimeSeries 객체

# 메타데이터
print(ts.metadata)         # name, description, record schema

# 세그먼트 접근
print(ts.segments.keys())  # 세그먼트 이름 목록
seg = ts.segments['Tail']
print(seg.name)
print(seg.record_count)
print(seg.start_time)
print(seg.end_time)

# pandas DataFrame으로 변환
df = seg.records_as_pandas()
print(df)
```

### 세그먼트 타입

- `InternalSegment`: 내부 저장 데이터 (records 직접 접근, pandas 변환 가능)
- `LinkedSegment`: 외부 링크 참조
- `ExternalSegment`: 외부 파일/Blob 데이터

## 8. Airflow DAG 통합

`mdtpy.airflow` 모듈은 Apache Airflow DAG에서 MDT Operation을 호출하기 위한 도구를 제공한다.
(`mdtpy/__init__.py`에서 자동 import되지 않으므로 필요 시 명시적으로 import한다.)

```python
import mdtpy
from mdtpy.airflow import LocalDagContext, reference, task_output
from mdtpy.airflow import AASOperationTaskInvocation, SetElementInvocation

MDT_MANAGER_URL = "http://localhost:12985/instance-manager"
manager = mdtpy.connect(url=MDT_MANAGER_URL)

# Operation 호출 태스크 정의
dag_context = LocalDagContext("inspect_image", MDT_MANAGER_URL)
AASOperationTaskInvocation(
    instance="inspector",
    submodel="ThicknessInspection",
    argument_specs={
        'inputs': {
            "UpperImage": reference("param:inspector:UpperImage")
        }
    }
).run(dag_context)
```

### 태스크 간 데이터 전달

`task_output()`으로 이전 태스크의 출력 인자를 참조할 수 있다:

```python
# 이전 태스크 'inspect_image'의 출력 'Defect'를 입력으로 사용
dag_context = LocalDagContext("update_defect_list", MDT_MANAGER_URL)
AASOperationTaskInvocation(
    instance="inspector",
    submodel="UpdateDefectList",
    argument_specs={
        'inputs': {
            'Defect': task_output("inspect_image", "Defect"),
            'DefectList': reference("param:inspector:DefectList"),
        },
        'outputs': {
            'UpdatedDefectList': reference("param:inspector:DefectList")
        }
    }
).run(dag_context)
```

### 값 읽기 태스크

`SetElementInvocation`으로 파라미터 값을 읽어오는 태스크를 정의할 수 있다:

```python
dag_context = LocalDagContext("get_heater_cycle_time", MDT_MANAGER_URL)
SetElementInvocation(
    argument_specs={
        'inputs': {
            "source": reference("param:heater:CycleTime")
        }
    }
).run(dag_context)
```

## 9. BaSyx 직렬화/역직렬화

AAS 객체의 JSON 직렬화를 위한 유틸리티:

```python
import mdtpy

# JSON 문자열 -> AAS 객체
with open('output.json', 'r') as f:
    obj = mdtpy.basyx.serde.from_json(f.read())

# dict -> AAS 객체
obj = mdtpy.basyx.serde.from_dict(data_dict)

# AAS 객체 -> JSON 문자열
json_str = mdtpy.basyx.serde.to_json(obj)
```

## 10. 예외 처리

모든 MDT 관련 예외는 `MDTException`을 상속한다:

```python
from mdtpy import (
    MDTException,
    ResourceNotFoundError,
    ResourceAlreadyExistsError,
    InvalidResourceStateError,
    OperationError,
    TimeoutError,
    MDTInstanceConnectionError,
)

try:
    instance = manager.instances['nonexistent']
except ResourceNotFoundError as e:
    print(f"인스턴스를 찾을 수 없음: {e}")

try:
    instance.start()
except InvalidResourceStateError as e:
    print(f"잘못된 상태: {e}")

try:
    result = op.invoke(Data=data)
except OperationError as e:
    print(f"Operation 실행 실패: {e}")
except TimeoutError as e:
    print(f"타임아웃: {e}")

try:
    inst = mdtpy.connect("http://unreachable")
    _ = inst.instances['x']
except MDTInstanceConnectionError as e:
    print(f"연결 실패: {e}")
```

서버가 200/404 외의 상태(5xx 등)로 응답할 때는 `MDTException` 하위 타입(`RemoteError` 등)이
직접 발생하므로, 인스턴스 존재 여부 확인 시 try/except로 분리해 처리하는 것이 안전하다.

## 11. 유틸리티 함수

### SubmodelElement에서 Python 타입으로 변환

```python
from mdtpy import to_str, to_int, to_datetime, to_duration

value_str = to_str(sme)         # -> str | None
value_int = to_int(sme)         # -> int | None
value_dt = to_datetime(sme)     # -> datetime | None
value_dur = to_duration(sme)    # -> relativedelta | None
```

### ISO 8601 날짜/시간 변환

```python
from mdtpy.utils import datetime_to_iso8601, iso8601_to_datetime
from mdtpy.utils import timedelta_to_iso8601, iso8601_to_timedelta

iso_str = datetime_to_iso8601(datetime.now())     # -> '2024-01-01T12:00:00'
dt = iso8601_to_datetime('2024-01-01T12:00:00')   # -> datetime

iso_dur = timedelta_to_iso8601(timedelta(hours=1))   # -> 'PT1H'
td = iso8601_to_timedelta('PT1H30M')                 # -> timedelta
```

## 12. 값 타입 체계

mdtpy에서 지원하는 AAS SubmodelElement 값 타입:

| SubmodelElement 타입 | Python 값 타입 | 비고 |
|---|---|---|
| Property | `str`, `int`, `float`, `bool`, `datetime` 등 | `value_type`에 따라 결정 |
| SubmodelElementCollection | `dict[str, ElementValueType]` | 중첩 가능 |
| SubmodelElementList | `list[ElementValueType]` | 인덱스 접근: `path[0]` |
| File | `FileValue` (`{content_type, value}`) | 첨부파일은 별도 API |
| Range | `RangeValue` (`{min, max}`) | |
| MultiLanguageProperty | `dict[str, str]` | `{'ko': '값', 'en': 'value'}` |

서버 wire 포맷(camelCase)은 `FileJsonValue`(`{contentType, value}`),
`MultiLanguagePropertyJsonValue`(`list[dict[str, str]]`)으로 별도 정의되어 있으며,
`from_json_object()` / `to_json_object()` 함수가 두 표현 사이를 변환한다.

## 13. HTTP 호출 정책

mdtpy는 두 종류의 HTTP 클라이언트를 사용한다:

- **`mdtpy.instance` 내부 헬퍼** (`_get`/`_put`/`_post`/`_delete`): MDT Instance Manager와의
  통신. `DEFAULT_TIMEOUT = 30`초가 기본 적용되며, 호출자가 명시한 `timeout`은 그대로 보존된다.
- **`mdtpy.fa3st`의 `call_*`**: 개별 인스턴스(FA³ST)와의 통신. 모듈 상수
  `DEFAULT_TIMEOUT = 30.0`초, `VERIFY_TLS = False`(self-signed 인증서 호환)가 일괄 적용된다.

자체 서명된 인증서를 사용하지 않는 환경이라면 `mdtpy.fa3st.VERIFY_TLS = True`로 변경하여
SSL 검증을 활성화할 수 있다.

연결 실패는 모두 `MDTInstanceConnectionError`로 래핑되어 노출된다.

## 요약: 일반적인 응용 프로그램 패턴

```python
import mdtpy

# 1. 플랫폼 접속
manager = mdtpy.connect("http://localhost:12985/instance-manager")

# 2. 인스턴스 접근 및 시작
instance = manager.instances['my_twin']
if not instance.is_running():
    instance.start()

# 3. 파라미터 읽기/쓰기
param = instance.parameters['MyParam']
value = param.read_value()
param.update_value(new_value)

# 4. Operation 호출
op = instance.operations['MyOperation']
result = op.invoke(Input1=param, Input2=42)
op.output_arguments.update_value(result)

# 5. 시계열 데이터 분석
ts = instance.timeseries['MyTimeSeries'].timeseries()
df = ts.segments['Latest'].records_as_pandas()
```
