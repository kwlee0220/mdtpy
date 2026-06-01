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
(390+ tests). `src/samples/sample_*.py` 스크립트들은 **실서버 대상 사용 예제 /
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
rm -rf dist/           # 이전 산출물 정리
uv build               # sdist + wheel을 dist/에 생성
```

빌드 결과는 다음으로 검증한다.

```bash
uv run --with twine twine check dist/*          # 메타데이터/README 렌더링 검사
unzip -l dist/mdtpy-*.whl                        # samples 제외, mdtpy 패키지만 포함되는지 확인
```

## PyPI 등록

### 1. 사전 준비

- [PyPI](https://pypi.org) 계정을 생성하고, *Account settings → API tokens* 에서
  API 토큰(`pypi-...`)을 발급받는다. 사전 검증용으로는
  [TestPyPI](https://test.pypi.org)에도 별도 가입을 권장한다.
- 새 릴리스마다 `pyproject.toml`의 `version`을 올린다. PyPI는 이미 업로드된
  버전의 재업로드를 거부한다.

### 2. (권장) TestPyPI 업로드 및 검증

```bash
uv run --with twine twine upload --repository testpypi dist/*
uv run --with mdtpy --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ python -c "import mdtpy"
```

### 3. PyPI 정식 업로드

```bash
uv run --with twine twine upload dist/*
```

- 사용자명에 `__token__`, 비밀번호에 API 토큰을 입력한다. 자동화 시에는
  `TWINE_USERNAME=__token__`, `TWINE_PASSWORD=pypi-...` 환경변수나 `~/.pypirc`를
  사용한다.

### 4. 설치 확인

```bash
pip install mdtpy      # 새 환경에서 설치 검증
```
