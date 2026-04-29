# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mdtpy** is a Python client library for the MDT (Manufacturing Digital Twin) framework. It provides a Python API to interact with MDT Instance Manager services via HTTP REST, built on the Asset Administration Shell (AAS) standard using `basyx-python-sdk`. End-user API surface and worked examples live in `doc/programming_guide.md`.

## Build & Development

- **Python:** 3.10+ (specified in `.python-version`)
- **Package manager:** uv
- **Install runtime deps:** `uv sync`
- **Install dev deps (pytest):** `make install-dev` (= `uv sync --group dev`)
- **Build:** `uv build`

Source layout uses `src/mdtpy/` with `src/` on the Python path (configured in `.vscode/settings.json`).

## Testing

The project has a proper pytest suite under `tests/` (390+ unit tests) plus sample / integration scripts under `src/samples/sample_*.py` that require a live MDT Instance Manager server.

```bash
make test                     # canonical: runs full pytest suite
make test-cov                 # with coverage report
uv run --env-file .env pytest tests/test_instance.py        # single file
uv run --env-file .env pytest tests/test_instance.py::TestMDTInstanceCollection::test_bool_is_always_true_without_http  # single test
```

**Why `make test` instead of `uv run pytest`:** if your shell has ROS2 sourced (`/opt/ros/humble/...`), the system `launch_pytest` plugin auto-loads from the system site-packages and crashes with `ModuleNotFoundError: yaml`. The `Makefile` and `.env` inject `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` to bypass this. Without ROS in the shell, plain `uv run pytest` works too.

`tests/conftest.py` automatically resets the `mdt_inst_url` / `mdt_manager` module globals in `mdtpy.instance` between tests — relevant when adding tests that exercise `mdtpy.connect()`.

The standalone scripts in `src/samples/sample_*.py` (e.g. `python src/samples/sample_reference.py`) are **end-to-end usage examples / smoke tests against a running server**, not part of the pytest suite. Don't model new unit tests after them.

## Coding Conventions

- 코드 주석(inline comments, docstring)은 한국어로 작성한다. 문장은 "~한다"(평서문) 형식을 사용한다.
- 로깅 메시지(`logger.info`, `logger.warning`, `logger.error` 등)는 영어로 작성한다.
- 예외 메시지(`ValueError`, `RuntimeError` 등)는 영어로 작성한다.
- Python 파일의 import 순서:
  1. `from __future__ import annotations` (항상 맨 처음)
  2. `from typing import ...` (다른 모든 import보다 우선)
  3. 표준 라이브러리 import
  4. 서드파티 라이브러리 import
  5. 로컬/프로젝트 import
- Type hint 는 built-in 우선: `tuple` / `list` / `dict` (대문자 generic 비권장),
  `Optional[X]` 권장 (`X | None` 비권장).
- 라인 길이 100자 제한 (신규 코드). 함수 호출/선언 인자는 한 줄로 이어 쓰고
  120자 초과 시에만 줄바꿈. **trailing comma 가급적 사용 금지** (Black 의
  magic trailing comma 동작에 의존하지 않음).
- 들여쓰기는 4-space (VSCode `editor.tabSize: 4`로 설정되어 있음).
- 콜론 뒤 공백: `param: type` (PEP 8).

## Architecture

### Connection flow

```
mdtpy.connect(url) → MDTInstanceManager → MDTInstance → services (parameters, submodels, operations, timeseries)
```

`mdtpy.connect()` also sets module-level globals `mdt_inst_url` / `mdt_manager` in `instance.py` so that `LazyElementReference` (created from an arbitrary `param:`/`oparg:` string before the manager exists) can resolve later.

### Two HTTP clients (manager-side vs instance-side)

The codebase has two separate HTTP layers, and confusing them is a common pitfall:

- **`instance.py`** speaks to the **MDT Instance Manager**. It exposes `_get` / `_put` / `_post` / `_delete` thin wrappers that apply `DEFAULT_TIMEOUT = 30` seconds. Used by `MDTInstanceManager`, `MDTInstanceCollection`, `MDTInstance`, and the `Status*Poller`s.
- **`fa3st.py`** speaks to **individual FA³ST instances** (the running submodel servers). It exposes `call_get` / `call_put` / `call_post` / `call_patch` / `call_delete` built on a single `_request` helper, with `DEFAULT_TIMEOUT = 30.0` and `VERIFY_TLS = False` (self-signed certs). Used by `submodel.py`, `reference.py`.

Both modules have their own `to_exception(resp)`, but `fa3st.to_exception` delegates to `http_client.to_exception` so the classification logic is single-sourced. Server `code` strings are NOT dynamically `import_module`-ed (this was removed for security); unknown codes fall back to `RemoteError`.

`MDTInstanceConnectionError` wraps `requests.exceptions.ConnectionError` everywhere.

### Key modules (`src/mdtpy/`)

- **`instance.py`** — `connect()`, `MDTInstanceManager`, `MDTInstance`, `MDTInstanceCollection`. Lifecycle (`STOPPED → STARTING → RUNNING → STOPPING → FAILED`) with two pollers: `InstanceStartPoller` (loops while `STARTING`), `InstanceStopPoller` (loops while `STOPPING`, terminates on any non-`STOPPING` state including `FAILED` — caller checks final state).
- **`reference.py`** — `ElementReference` (ABC), `DefaultElementReference` (HTTP-backed proxy on a single AAS SubmodelElement), `LazyElementReference` (resolves through the global `mdt_manager`).
- **`value.py`** — Bidirectional value mapping. `get_value` / `update_element_with_value` work between basyx SMEs and Python values (Property, SMC, SML, File, Range, MultiLanguageProperty). `from_json_object` / `to_json_object` convert between Python form (snake_case `FileValue`) and server wire form (camelCase `FileJsonValue`, list-of-dict MLP).
- **`descriptor.py`** — Frozen dataclass + `JSONWizard` descriptors. `MDTSubmodelDescriptor.is_*()` methods classify by `semantic_id` (`SEMANTIC_ID_INFOR_MODEL_SUBMODEL`, `_DATA_`, `_SIMULATION_`, `_AI_`, `_TIME_SERIES_`). The collection in `submodel.py` dispatches to different service classes based on this.
- **`submodel.py`** — `SubmodelService` + `SubmodelServiceCollection` (read-only `Mapping[str, T]`). `SubmodelElementCollection` caches the `__pathes()` list across `__iter__` / `__len__` / `__contains__`; mutations (`__setitem__` / `__delitem__`) invalidate the cache, and `refresh()` invalidates manually. `SubmodelServiceCollection` lazy-fetches `instance.operation_descriptors` only when a Simulation/AI submodel is encountered.
- **`operation.py`** — `OperationSubmodelService` (extends `SubmodelService`), `AASOperationService` (validates `model.Operation` at construction), `Argument` / `ArgumentList` (URL-encodes `id_short_path`, raises `MDTException` on duplicate IDs). `invoke()` flows: read input args → merge kwargs → call → auto-update output `ElementReference` kwargs.
- **`parameter.py`** — `MDTParameter(DefaultElementReference)`, `MDTParameterCollection(Mapping)` with duplicate-id detection.
- **`timeseries.py`** — `TimeSeriesService` with pandas DataFrame integration.
- **`aas_misc.py`** — Wire-format dataclasses (`OperationVariable`, `OperationResult`, `OperationHandle`, `OperationRequest`, `Endpoint`, `ProtocolInformation`). camelCase field names mirror server JSON. `OperationRequest.to_json` deliberately omits `inoutputArguments` (current FA³ST does not accept it).
- **`basyx/serde.py`** — `from_json` / `from_dict` / `to_json` wrapping basyx-python-sdk codecs.
- **`http_client.py`** — Manager-side response parsers (`parse_response`, `parse_list_response`, `parse_none_response`) + shared `to_exception(resp)`.
- **`exceptions.py`** — `MDTException` hierarchy (`RemoteError`, `ResourceNotFoundError`, `ResourceAlreadyExistsError`, `InvalidResourceStateError`, `OperationError`, `MDTInstanceConnectionError`, etc.).
- **`utils.py`** — ISO 8601 / timedelta / relativedelta helpers; `to_str` / `to_int` / `to_datetime` / `to_duration` SME→Python coercions.
- **`airflow/`** — Airflow DAG integration; **NOT auto-imported** by `mdtpy/__init__.py` (the import is commented). Callers must `from mdtpy.airflow import ...` explicitly.

### Important behavioral notes

- `MDTInstanceCollection.__bool__` always returns `True` (no HTTP). To check emptiness use `len(coll) == 0`.
- `MDTInstanceCollection.__contains__` / `__getitem__` distinguish `200` / `404` from other status codes; `5xx` raises `MDTException` rather than reporting "not found".
- `MDTInstance.start()` / `stop()` validate state immediately after the PUT (failing fast on bad transitions) before optionally polling. `nowait=True` skips the poll.
- All collection-style classes (`MDTParameterCollection`, `ArgumentList`, `MDTInstanceCollection`) URL-encode IDs with `quote(id, safe="")`. Don't drop the `safe=""` — paths can contain `/`.
- The `param:` / `oparg:` reference forms are resolved **locally** by `MDTInstanceManager.resolve_reference` without server round-trips; only unrecognized prefixes hit `/references/$url`.
