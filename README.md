# mdtpy

MDT(Manufacturing Digital Twin) 플랫폼을 위한 Python 클라이언트 라이브러리.
MDT Instance Manager와 개별 FA³ST 인스턴스에 HTTP REST로 접근하여, 제조 현장의
디지털 트윈(설비/공정)을 조회·제어하고, 파라미터 값을 읽고 쓰고, AI/시뮬레이션
연산을 호출하고, 시계열 데이터를 pandas로 가져오는 API를 제공한다.

Asset Administration Shell(AAS) 표준을 기반으로 하며, 내부적으로
[`basyx-python-sdk`](https://pypi.org/project/basyx-python-sdk/)를 사용해 AAS 모델
(`Property`, `SubmodelElementCollection`, `File`, `Operation`, TimeSeries 등)을 다룬다.

## 요구 사항

- Python 3.10 이상

## 설치

```bash
pip install mdtpy
```

저장소에서 직접 개발하는 경우:

```bash
uv sync                  # 런타임 의존성
make install-dev         # 개발 의존성(pytest)까지 함께 설치
```

## 빠른 시작

```python
import mdtpy
from mdtpy import mdt_value

# 1. MDT Instance Manager에 접속 (반드시 가장 먼저 호출)
manager = mdtpy.connect("http://localhost:12985/instance-manager")

# 2. 트윈(인스턴스) 가져오기 / 시작
inst = manager.instances['Welder']
if not inst.is_running():
    inst.start()                        # RUNNING이 될 때까지 대기

# 3. 파라미터 값 읽기
status = inst.parameters['Status']
v = status.read_value()                 # -> PropertyValue('IDLE')  ※ ElementValue 래퍼
print(v.to_raw_object())                # -> 'IDLE'  (원시 Python 값)

# 4. 파라미터 값 쓰기
status.update_value(mdt_value('Running'))    # ElementValue 로 쓰기
status.update_with_raw_value('Running')      # 원시 값으로 쓰기

# 5. 연산(AI/시뮬레이션) 호출
op = inst.operations['TotalQuantityPrediction']
results = op.invoke(NozzleProduction=inst.parameters['NozzleProduction'])
# results: 출력 인자 id -> ElementValue. 출력 값은 서버에도 자동 반영된다.

# 6. 시계열 데이터 → pandas DataFrame
ts = inst.timeseries['WelderAmpereLog'].timeseries()
df = ts.segments['Tail'].records_as_pandas()
```

상세 사용법과 전체 예제는 [`doc/programming_guide.md`](doc/programming_guide.md)와
[`src/samples/`](src/samples/)의 샘플 프로그램을 참조한다.

## 핵심 개념

| 개념 | 설명 |
|---|---|
| `MDTInstance` | 설비(Machine) 또는 공정(Process) 하나에 대응하는 디지털 트윈. `STOPPED → STARTING → RUNNING → STOPPING` 생명주기를 갖는다. 파라미터 **값**·서브모델·연산은 트윈이 `RUNNING`일 때만 접근 가능하다. |
| `MDTParameter` | 트윈에 정의된 이름 있는 값 슬롯 (`inst.parameters['Status']`). 그 자체가 `ElementReference`라서 읽기/쓰기/첨부파일 메서드를 모두 갖는다. |
| `ElementValue` | 플랫폼에서 읽어온 모든 값의 래퍼 (`PropertyValue`, `FileValue`, `ElementCollectionValue`, ...). 원시 값이 필요하면 `.to_raw_object()`로 벗긴다. |
| `ElementReference` | 플랫폼 내 임의 요소를 가리키는 문자열 기반 포인터. `mdtpy.reference("param:Welder:Status")` 형태로 생성한다. |
| Operation | 트윈에 부착된 AI 추론/시뮬레이션 호출 (`inst.operations['ThicknessInspection']`). `invoke(**kwargs)`로 호출하며 출력 인자는 서버에 자동 반영된다. |
| TimeSeries | 시계열 서브모델. `records_as_pandas()`로 DataFrame 변환을 지원한다. |

### 참조 문자열 형식

```python
from mdtpy import reference

reference("param:Welder:Status")                                  # 파라미터
reference("oparg:inspector:ThicknessInspection:out:Defect")       # 연산 인자 (in|out)
reference("test:Data:DataInfo.Equipment.EquipmentParameterValues[0].ParameterValue")  # 경로 직접 지정
reference("timeseries:Welder:NozzleProductionLog#last=7")         # 시계열 최근 N건
reference("timeseries:Welder:NozzleProductionLog#last=50s|Time,QuantityProduced")  # 기간+컬럼 선택
```

## 자주 쓰는 레시피

### 복합 값(컬렉션) 부분 수정

```python
p = inst.parameters['NozzleProduction']
raw = p.read_value().to_raw_object()      # {'QuantityProduced': 100, ...}
raw['QuantityProduced'] += 10
p.update_with_raw_value(raw)
```

### 파일(blob) 파라미터 — 이미지 업로드/다운로드

```python
img = inst.parameters['UpperImage']       # value_type == 'File'
img.put_attachment('/path/to/image.jpg')  # content_type 자동 추정
data: bytes = img.get_attachment()
img.delete_attachment()
```

### 연산 파이프라인 (검사 → 결함 목록 갱신 → 시뮬레이션)

```python
upper_image.put_attachment(image_path)
inspection.invoke(UpperImage=upper_image)
update.invoke(DefectList=defect_list, Defect=defect_ref, UpdatedDefectList=defect_list)
simulate.invoke(DefectList=defect_list, AverageCycleTime=cycle_time)
```

인자로 파라미터/참조를 넘기면 그 값이 읽혀 전달되고, 출력 인자 자리에 넘긴 참조에는
결과가 다시 기록되므로 연산 사이에 서버 상태가 자동으로 이어진다.
전체 예제: [`src/samples/sample_mdt_operations.py`](src/samples/sample_mdt_operations.py),
[`src/samples/sample_multi_ops.py`](src/samples/sample_multi_ops.py)

### 조건으로 인스턴스 검색

```python
for inst in manager.instances.find("parameter.id='CurrentLotNo'"):
    v = inst.parameters['CurrentLotNo'].read_value().to_raw_object()
    print(inst.id, v)
```

### 예외 처리

```python
from mdtpy import ResourceNotFoundError, InvalidResourceStateError, OperationError

try:
    inst.start()
except InvalidResourceStateError:
    pass          # 이미 RUNNING 등, 현재 상태에서 허용되지 않는 전이
```

## 주의 사항

- `read_value()`는 원시 값이 아니라 `ElementValue` 객체를 반환한다. 출력·비교·JSON
  직렬화 전에 반드시 `.to_raw_object()`로 변환한다.
- `update_value()`는 `ElementValue`를 받는다. 원시 값은 `mdt_value()`로 감싸거나
  `update_with_raw_value()`를 사용한다.
- `inst.parameters` 같은 속성 접근은 매번 HTTP 호출이다. 루프 안에서는 지역 변수에
  담아 재사용한다. 파라미터 값 읽기도 건당 원격 호출이므로, 다수 인스턴스×다수
  파라미터를 읽을 때는 스레드 병렬화나 상위 컬렉션 일괄 조회를 고려한다.
- `bool(manager.instances)`는 항상 `True`다. 비어 있는지는 `len(...) == 0`으로 확인한다.
- 트윈의 `status`(RUNNING 등)는 **트윈 프로세스의 상태**이며 실제 설비의 가동 상태와는
  무관하다. 설비 상태는 보통 `Status` 같은 파라미터로 표현된다.

## 주요 모듈

| 모듈 | 역할 |
|---|---|
| `mdtpy.instance` | `connect()`, `MDTInstanceManager`, `MDTInstance`, 인스턴스 컬렉션/폴러 |
| `mdtpy.parameter` | `MDTParameter`, `MDTParameterCollection` |
| `mdtpy.value` | `ElementValue` 계층과 변환 (`to_raw_object`, `mdt_value`, `get_value`, `parse_json_node` 등) |
| `mdtpy.ref` | `reference()` 팩토리, `ElementReference`/`BaseElementReference` |
| `mdtpy.operation` | `OperationSubmodelService`(고수준 `invoke`), `AASOperationService`(저수준) |
| `mdtpy.submodel` | `SubmodelService`, `SubmodelElementCollection` — AAS 원시 접근 |
| `mdtpy.timeseries` | `TimeSeriesService` (pandas 통합) |
| `mdtpy.descriptor` | 인스턴스/파라미터/연산/인자 디스크립터 dataclass |
| `mdtpy.exceptions` | `MDTException` 계층 |
| `mdtpy.airflow` | Apache Airflow DAG 통합 (선택, 자동 import 안 됨) — [`src/mdtpy/airflow/README.md`](src/mdtpy/airflow/README.md) |
| `mdtpy.rpc.restful` | 원격 operation 호출용 RESTful RPC 클라이언트 (선택) |
| `mdtpy.basyx.serde` | basyx 모델 객체 JSON 직렬화 래퍼 |

API 전체 레퍼런스 성격의 문서는 [`CLAUDE.md`](CLAUDE.md)(영문)를 참조한다.

## 개발

### 테스트

```bash
make test              # 전체 pytest suite (470+ tests, mock 기반 — 서버 불필요)
make test-cov          # 커버리지 포함
```

> **참고**: ROS2를 source한 셸에서는 시스템 `launch_pytest` 플러그인 충돌이 있어
> `Makefile`/`.env`가 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`을 주입한다. ROS가 없으면
> `uv run pytest`로도 충분하다.

`src/samples/sample_*.py`는 실서버 대상 사용 예제/스모크 테스트이며 pytest suite에
포함되지 않는다.

### 코드 스타일

- 코드 주석/docstring: 한국어 (평서문 "~한다") · 로깅/예외 메시지: 영어
- import 순서: `__future__` → `typing` → 표준 → 서드파티 → 로컬
- 타입 힌트: built-in 우선 (`list`/`dict`), `Optional[X]` 권장
- 들여쓰기 4-space, 라인 길이 100자 (신규 코드)

### 빌드

```bash
rm -rf dist/
uv build               # sdist + wheel 생성
uv run --with twine twine check dist/*     # 메타데이터/README 렌더링 검사
unzip -l dist/mdtpy-*.whl                  # samples 제외 여부 확인
```

### PyPI 등록

1. [PyPI](https://pypi.org) API 토큰(`pypi-...`)을 발급받는다. 사전 검증용으로
   [TestPyPI](https://test.pypi.org) 가입을 권장한다. 새 릴리스마다
   `pyproject.toml`의 `version`을 올린다 (동일 버전 재업로드 불가).
2. (권장) TestPyPI 업로드 및 검증:

   ```bash
   uv run --with twine twine upload --repository testpypi dist/*
   uv run --with mdtpy --index-url https://test.pypi.org/simple/ \
          --extra-index-url https://pypi.org/simple/ python -c "import mdtpy"
   ```

3. 정식 업로드: `uv run --with twine twine upload dist/*`
   (사용자명 `__token__`, 비밀번호에 API 토큰. 자동화 시 `TWINE_USERNAME`/`TWINE_PASSWORD`
   환경변수 또는 `~/.pypirc` 사용)
4. 설치 확인: `pip install mdtpy`
