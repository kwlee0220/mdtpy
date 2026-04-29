# mdtpy

MDT(Manufacturing Digital Twin) 플랫폼을 위한 Python 클라이언트 라이브러리.
Asset Administration Shell(AAS) 표준을 기반으로 MDT Instance Manager 및 개별
FA³ST 인스턴스에 HTTP REST로 접근하는 API를 제공한다.

내부적으로 [`basyx-python-sdk`](https://pypi.org/project/basyx-python-sdk/)를
사용해 AAS 모델(`Property`, `SubmodelElementCollection`, `SubmodelElementList`,
`File`, `Range`, `MultiLanguageProperty`, `Operation`, `TimeSeries` 등)을 다룬다.

## 요구 사항

- Python 3.10 이상
- [uv](https://docs.astral.sh/uv/) (의존성/빌드 관리)

## 설치

```bash
uv sync                  # 런타임 의존성
make install-dev         # 개발 의존성(pytest)까지 함께 설치
```

소스 레이아웃은 `src/mdtpy/`이며, `src/`가 Python path에 등록되어 있다
(`.vscode/settings.json`).

## 빠른 시작

```python
import mdtpy

# 1. MDT Instance Manager에 접속
manager = mdtpy.connect("http://localhost:12985/instance-manager")

# 2. 인스턴스 가져오기 / 시작
instance = manager.instances['my_twin']
if not instance.is_running():
    instance.start()

# 3. 파라미터 읽기/쓰기
param = instance.parameters['Status']
print(param.read_value())
param.update_value('Running')

# 4. Operation 호출
op = instance.operations['Inspect']
result = op.invoke(Image=instance.parameters['UpperImage'])
op.output_arguments.update_value(result)

# 5. 시계열 데이터
ts = instance.timeseries['WelderAmpereLog'].timeseries()
df = ts.segments['Latest'].records_as_pandas()
```

상세 사용법은 [`doc/programming_guide.md`](doc/programming_guide.md) 참조.

## 주요 모듈

| 모듈 | 역할 |
|---|---|
| `mdtpy.instance` | `connect()`, `MDTInstanceManager`, `MDTInstance`, 컬렉션, 폴러 |
| `mdtpy.reference` | `ElementReference` 추상화 (`DefaultElementReference`, `LazyElementReference`) |
| `mdtpy.parameter` | `MDTParameter`, `MDTParameterCollection` |
| `mdtpy.submodel` | `SubmodelService`, `SubmodelServiceCollection`, `SubmodelElementCollection` |
| `mdtpy.operation` | `OperationSubmodelService`, `Argument`, `ArgumentList` |
| `mdtpy.timeseries` | `TimeSeriesService` (pandas 통합) |
| `mdtpy.value` | SME ↔ Python 값 ↔ 서버 wire JSON 변환 |
| `mdtpy.descriptor` | 불변 dataclass 디스크립터, semantic_id 기반 분류 |
| `mdtpy.aas_misc` | AAS wire 포맷 dataclass (`Endpoint`, `OperationVariable` 등) |
| `mdtpy.fa3st` | 개별 FA³ST 인스턴스용 HTTP 헬퍼 (`call_get`/`call_put`/...) |
| `mdtpy.http_client` | Instance Manager용 응답 파서, 공통 예외 변환 |
| `mdtpy.exceptions` | `MDTException` 계층 |
| `mdtpy.utils` | ISO 8601 / timedelta / SME→Python 변환 헬퍼 |
| `mdtpy.airflow` | Apache Airflow DAG 통합 (선택, 자동 import되지 않음) |
| `mdtpy.basyx.serde` | basyx-python-sdk 직렬화 래퍼 |

## 개발

### 테스트 실행

```bash
make test              # 전체 pytest suite
make test-cov          # 커버리지 보고서 포함
```

또는 직접 실행:

```bash
uv run --env-file .env pytest tests/test_instance.py
uv run --env-file .env pytest tests/test_instance.py::TestMDTInstanceCollection -v
```

> **참고**: ROS2(`/opt/ros/humble/...`)를 source한 셸에서는 시스템
> `launch_pytest` 플러그인이 자동 로드되어 `yaml` 누락으로 충돌한다. `Makefile`
> 과 `.env`가 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`을 주입하여 이를 우회한다.
> ROS가 source되지 않은 셸이라면 `uv run pytest`만으로도 충분하다.

`tests/` 폴더의 단위 테스트는 외부 서버 의존 없이 mock으로 동작한다
(300+ tests). `src/samples/sample_*.py` 스크립트들은 **실서버 대상 사용 예제 /
스모크 테스트**이므로 별도 환경에서 실행한다 (예: `python src/samples/sample_reference.py`).

### 코드 스타일

- 코드 주석/docstring: 한국어 (평서문 "~한다")
- 로깅/예외 메시지: 영어
- import 순서: `__future__` → `typing` → 표준 → 서드파티 → 로컬
- 타입 힌트: built-in 우선 (`list`/`dict`/`tuple`), `Optional[X]` 권장
- 들여쓰기: 4-space
- 라인 길이: 100자 (신규 코드)

자세한 규칙과 아키텍처는 [`CLAUDE.md`](CLAUDE.md) 참조.

## 빌드

```bash
uv build               # sdist + wheel을 dist/에 생성
```
