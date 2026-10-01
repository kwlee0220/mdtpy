# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and other LLM coding assistants
(Cursor, Codex, ...) when working with code in this repository — **and, just as importantly,
when writing applications that use the mdtpy API**. It is written so that an LLM can author
mdtpy-based application code from this file alone, without scanning the library source.

## Project Overview

**mdtpy** is a Python client library for the MDT (Manufacturing Digital Twin) platform.
It talks HTTP REST to an **MDT Instance Manager** (and, behind it, to individual FA³ST
AAS servers), and models everything on the Asset Administration Shell (AAS) standard via
`basyx-python-sdk`. Worked end-user examples live in `doc/programming_guide.md` and
`src/samples/sample_*.py`.

- Package: `mdtpy` (src layout: `src/mdtpy/`), Python ≥ 3.10, managed with `uv`.
- Version: see `pyproject.toml` (`0.2.9` at time of writing).

---

# Part 1 — Writing applications with the mdtpy API

## 1.1 Mental model

```
mdtpy.connect(url) ──► MDTInstanceManager
                          └─ .instances ──► MDTInstance (a "twin": machine or process)
                                              ├─ .parameters     ──► MDTParameter (named value slots)
                                              ├─ .operations     ──► OperationSubmodelService (AI/simulation calls)
                                              ├─ .timeseries     ──► TimeSeriesService (pandas integration)
                                              └─ .submodel_services ──► SubmodelService (raw AAS access)
```

Three cross-cutting concepts:

- **`ElementValue`** — every value read from the platform comes back wrapped in an
  `ElementValue` subclass (`PropertyValue`, `FileValue`, `ElementCollectionValue`, ...).
  Unwrap with `.to_raw_object()`. Writes take an `ElementValue` (`update_value`) or a raw
  Python object (`update_with_raw_value`).
- **`ElementReference`** — a string-addressable pointer to any SubmodelElement anywhere in
  the platform (`reference("param:Welder:Status")`). Parameters and operation arguments ARE
  references (subclasses of `BaseElementReference`), so anything that accepts a reference
  accepts them too.
- **Twin lifecycle** — an `MDTInstance` is a *digital twin process*, with status
  `STOPPED → STARTING → RUNNING → STOPPING` (+ `FAILED`). Parameter **values**, submodels,
  and operations are only accessible while the twin is `RUNNING`. Twin status is unrelated
  to the physical equipment's on/off state (that is typically a parameter like `Status`).

## 1.2 Quick start

```python
import mdtpy
from mdtpy import mdt_value

manager = mdtpy.connect("http://localhost:12985/instance-manager")

inst = manager.instances['Welder']
if not inst.is_running():
    inst.start()                      # blocks (polls) until RUNNING

# --- read a parameter value
status = inst.parameters['Status']
v = status.read_value()               # -> PropertyValue('IDLE')  (an ElementValue!)
print(v.to_raw_object())              # -> 'IDLE'  (raw Python value)

# --- write a parameter value
status.update_value(mdt_value('Running'))   # update_value takes an ElementValue
status.update_with_raw_value('Running')     # ...or write a raw value directly

# --- invoke an operation (AI / simulation)
op = inst.operations['TotalQuantityPrediction']
results = op.invoke(NozzleProduction=inst.parameters['NozzleProduction'])
# results: Mapping[str, ElementValue]; outputs are ALSO auto-written back server-side

# --- time series to pandas
ts = inst.timeseries['WelderAmpereLog'].timeseries()
df = ts.segments['Tail'].records_as_pandas()
```

## 1.3 Connecting — `mdtpy.connect`

```python
manager: MDTInstanceManager = mdtpy.connect("http://<host>:12985/instance-manager")
```

`connect()` also sets a **module-level global manager** that `reference()`,
`MDTParameter`, and operation `Argument`s resolve through. Consequences:

- Call `connect()` **once, before** creating/using any reference; otherwise value access
  raises `RuntimeError("mdt_manager is not initialized")`.
- References can be constructed *before* connecting (construction does no HTTP);
  only their first read/write resolves lazily.

## 1.4 Instances — `manager.instances`

`MDTInstanceCollection` is dict-like; **most accesses are HTTP calls**:

```python
inst = manager.instances['inspector']          # __getitem__ -> MDTInstance; 404 -> ResourceNotFoundError
'inspector' in manager.instances               # __contains__ -> bool
for inst in manager.instances: ...             # __iter__ (one HTTP call, lists all)
len(manager.instances)                         # HTTP; NB: bool(collection) is ALWAYS True — use len()==0
manager.instances.find("parameter.id='CurrentLotNo'")   # server-side filter -> generator
manager.instances.add('new_id', port, '/path/to/bundle_dir')  # zip-upload a new twin
manager.instances.remove('new_id')             # or: del manager.instances['new_id']
```

`find()` filter examples (server-side query language; values in single quotes):
`"instance.instanceId = 'test'"`, `"parameter.id='FurnaceRecipe'"`.
Note: user input interpolated into filter strings is not escaped by mdtpy — be careful.

`MDTInstance` — cheap descriptor-backed properties (no HTTP):
`id`, `aas_id`, `aas_id_short`, `global_asset_id`, `asset_type` (`MDTAssetType`, e.g.
Machine/Process), `status` (`MDTInstanceStatus`), `base_endpoint`, `is_running()`.
`status`/`base_endpoint` change over time — call `reload_descriptor()` for a fresh view;
do not cache them.

`MDTInstance` — service accessors (each property access = one HTTP call):

| Property | Returns | Requires RUNNING? |
|---|---|---|
| `parameters` | `MDTParameterCollection` (Mapping[str, MDTParameter]) | no (but value reads do) |
| `parameter_descriptors` | `dict[str, MDTParameterDescriptor]` | no |
| `operations` | `SubmodelServiceCollection[OperationSubmodelService]` | **yes** (`InvalidResourceStateError`) |
| `operation_descriptors` | `dict[str, MDTOperationDescriptor]` | no |
| `submodel_services` | `SubmodelServiceCollection[SubmodelService]` | **yes** |
| `submodel_descriptors` | `dict[str, MDTSubmodelDescriptor]` | **yes** |
| `timeseries` | `SubmodelServiceCollection[TimeSeriesService]` | **yes** |

Lifecycle: `inst.start()` / `inst.stop()` — idempotence is NOT built in: starting a
RUNNING instance raises `InvalidResourceStateError` (catch it, or guard with
`is_running()`). Both poll until the transition completes; pass `nowait=True` to skip
polling. `read_asset_administration_shell()` returns the basyx AAS object.

## 1.5 Parameters — `inst.parameters`

`MDTParameter` **is a** `BaseElementReference` (its ref string is `param:<instance>:<param>`),
plus descriptor accessors `id`, `name`, `value_type` (XSD type string, or
`"SubmodelElementCollection"`, `"File"`, ...).

```python
p = inst.parameters['NozzleProduction']
p.read()                    # -> basyx model.SubmodelElement (full element)
v = p.read_value()          # -> ElementValue (e.g. ElementCollectionValue)
raw = v.to_raw_object()     # -> dict, e.g. {'QuantityProduced': 100, ...}
raw['QuantityProduced'] += 10
p.update_with_raw_value(raw)             # partial raw update is fine
```

**File (blob) parameters** (`value_type == 'File'`): the value is only
`{content_type, filename}` metadata; the actual bytes go through attachment methods:

```python
img = inst.parameters['UpperImage']
img.put_attachment('/path/to/image.jpg')            # content_type auto-guessed
img.put_attachment('/path/to/image.jpg', 'image/jpeg')
data: bytes = img.get_attachment()
img.delete_attachment()
```

**Performance caution:** each `read_value()` is one HTTPS round trip (~0.1–0.2 s typical).
Reading N parameters over M instances sequentially costs N×M round trips. For bulk reads,
either parallelize per instance with threads (calls are blocking I/O), or read a whole
containing collection in one call, e.g.
`reference(f"{inst_id}:Data:DataInfo.Equipment.EquipmentParameterValues").read_value()`.

## 1.6 Values — the `ElementValue` hierarchy

`read_value()` / `get_value(sme)` NEVER return bare scalars; they return:

| Class | Wraps | `.to_raw_object()` |
|---|---|---|
| `PropertyValue(value, value_type)` | scalar Property | scalar (`1`, `'IDLE'`, ...) |
| `FileValue(content_type, value)` | File metadata | `{'content_type': ..., 'value': <filename>}` |
| `RangeValue(min, max, value_type)` | Range | `{'min': ..., 'max': ...}` |
| `MLPropertyValue(mappings)` | MultiLanguageProperty | `[{'en': '...'}, {'ko': '...'}]` |
| `ElementCollectionValue(members)` | SMC — a read-only `Mapping` | `{idShort: raw, ...}` (recursive) |
| `ElementListValue(members)` | SML — a read-only `Sequence` | `[raw, ...]` (recursive) |

Key conversions:

```python
from mdtpy import mdt_value, PropertyValue
mdt_value(3)          # PropertyValue for int (str/bool/int/float/timedelta supported)
v.to_raw_object()     # ElementValue -> raw Python (recursive unwrap)
v.to_json_string()    # polymorphic {"@type": "mdt:value:...", "value": ...} wire JSON
mdtpy.parse_json_string(s)   # inverse of to_json_string
mdtpy.get_value(sme)         # basyx SubmodelElement -> ElementValue
v.apply_to(sme)              # write ElementValue into a matching basyx SME
```

Rules of thumb:
- Display/compare/JSON-serialize → always `.to_raw_object()` first. `str(v)` gives
  `"PropertyValue('IDLE')"` (repr), and `json.dumps(v)` / `mdtpy.json_dumps(v)` raise
  `TypeError`.
- `update_value(x)` requires `x: ElementValue` (wrap raw scalars in `mdt_value(...)`).
- `update_with_raw_value(x)` takes raw Python values (scalar/dict/list), including
  partial dicts for collections.
- `ElementCollectionValue`/`ElementListValue` are **read-only**; to modify, get the raw
  object, mutate it, and write back with `update_with_raw_value`.

## 1.7 References — `mdtpy.reference`

`reference(ref_string) -> BaseElementReference` builds a lazy handle (no HTTP until used).
All resolution is server-side; the client treats ref strings opaquely.

Reference string grammar:

| Form | Meaning | Example |
|---|---|---|
| `<instance>:<submodel_idShort>:<idShort.path>` | any element by path (indexes allowed) | `test:Data:DataInfo.Equipment.EquipmentParameterValues[0].ParameterValue` |
| `param:<instance>:<param_id>` | a parameter | `param:Welder:Status` |
| `oparg:<instance>:<operation>:in\|out:<arg_id>` | an operation argument | `oparg:inspector:ThicknessInspection:out:Defect` |
| `timeseries:<instance>:<submodel>#last=<N>` | last N records of a time series | `timeseries:Welder:NozzleProductionLog#last=7` |
| `timeseries:...#last=<dur>\|<col1>,<col2>` | duration window + column projection | `timeseries:Welder:NozzleProductionLog#last=50s\|Time,QuantityProduced` |

API on every reference: `read()` / `write(sme)` (full basyx element),
`read_value()` / `update_value(ev)` / `update_with_raw_value(raw)`,
`get_attachment()` / `put_attachment(path, content_type=None)` /
`put_attachment_with_bytes(name, ctype, data)` / `delete_attachment()`,
`ref_string`, `model_type`, `value_type`.

Note: `timeseries:` references are typically used with `.read()` (the SubmodelElement is
passed to operations directly), not `.read_value()`.

## 1.8 Operations — `inst.operations`

Operations model AI inference / simulation calls attached to a twin. Two API levels:

**High level (recommended)** — `OperationSubmodelService.invoke(**kwargs)`:

```python
inspection = inspector.operations['ThicknessInspection']
results = inspection.invoke(UpperImage=inspector.parameters['UpperImage'])
# results: Mapping[str, ElementValue], keyed by output argument id
defect: ElementValue = results['Defect']
```

Argument passing (`ArgumentType`): each kwarg may be
- an `ElementReference` (incl. `MDTParameter`) — its value is read and sent; if passed for
  an **output** id, the result is written back into that reference;
- an `ElementValue` — sent as-is;
- a raw Python value (`IncAmount=7`, `SleepTime=2.5`);
- a basyx `model.SubmodelElement` (used for `timeseries:` data — see below).

Semantics to remember:
- **Omitted input args** default to the operation's registered input reference (the value
  currently stored on the server).
- **Every output** is auto-written server-side: to the reference you passed for that output
  id if any, else to the operation's registered default output reference. `invoke()` has
  side effects even if you ignore its return value.
- Failure raises `OperationError`. The sync call has a very long internal timeout (7 days).

Discovering an operation's signature:

```python
op_desc = inspection.operation_descriptor      # MDTOperationDescriptor
op_desc.input_arguments                        # list[ArgumentDescriptor]
op_desc.output_arguments                       # list[ArgumentDescriptor]
# ArgumentDescriptor: .id, .id_short_path, .value_type, .reference ('oparg:...' string)
inspection.input_arg_descs                     # same input list, cached on the service
inspection.output_arg_desc_dict                # dict[id, ArgumentDescriptor]
# read an argument's current value:
mdtpy.reference(arg_desc.reference).read_value()
```

Passing time-series data to an operation (pattern from `sample_mdt_operations.py`):

```python
ts_sme = reference("timeseries:Welder:NozzleProductionLog#last=7").read()
results = test.operations['CountRecords'].invoke(TimeSeriesData=ts_sme)
```

**Low level** — `AASOperationService(op_submodel, "Operation").invoke(**kwargs)`: same
argument handling but NO automatic write-back of outputs and no defaulting of omitted
inputs; you get the raw result mapping and store outputs yourself. Use when you need
explicit control (see `sample_aas_operation.py`).

**Chained pipeline pattern** (from `sample_multi_ops.py`): pass parameters/references
between operations; write-back keeps server state consistent between steps:

```python
upper_image.put_attachment(image_path)
inspection.invoke(UpperImage=upper_image)
update.invoke(DefectList=defect_list, Defect=defect_ref, UpdatedDefectList=defect_list)
simulate.invoke(DefectList=defect_list, AverageCycleTime=cycle_time)
```

## 1.9 Time series — `inst.timeseries`

```python
svc = inst.timeseries['WelderAmpereLog']       # TimeSeriesService
ts = svc.timeseries()                          # reads Metadata + Segments in one shot
ts.metadata                                    # Metadata (record schema etc.)
ts.segments.keys()                             # e.g. dict_keys(['Latest', 'Tail', ...])
seg = ts.segments['Tail']                      # InternalSegment | LinkedSegment | ExternalSegment
seg.name; seg.record_count
df = seg.records_as_pandas()                   # -> pandas.DataFrame (InternalSegment only)
```

`records_as_pandas()` raises `NotImplementedError` on `LinkedSegment`/`ExternalSegment`.
For windowed reads feeding an operation, prefer a `timeseries:...#last=...` reference.

## 1.10 Submodels (raw AAS access) — `inst.submodel_services`

For anything parameters don't cover, drop to submodel level:

```python
svc = inst.submodel_services['Data']           # SubmodelService
sm = svc.read()                                # full basyx model.Submodel
sme = svc.submodel_elements['DataInfo.Equipment.EquipmentParameters[0].ParameterID']
svc.submodel_elements[path] = new_sme          # write (adds if missing)
svc.submodel_elements.get_value(path)          # value shortcut
ref = svc.element_reference(path)              # -> BaseElementReference
```

Classification helpers on `SubmodelService` (driven by semantic id): `is_data()`,
`is_information_model()`, `is_simulation()`, `is_ai()`, `is_time_series()`.
Path convention for parameter values inside the `Data` submodel:
Machine twins → `DataInfo.Equipment.EquipmentParameterValues[i].ParameterValue`,
Process twins → `DataInfo.Operation.OperationParameterValues[i].ParameterValue`.

## 1.11 Exceptions

```
MDTException (all carry .details)
├── ResourceNotFoundError        # 404s: unknown instance/parameter/submodel/operation
├── ResourceAlreadyExistsError
├── InvalidResourceStateError    # op not allowed in current twin state (e.g. not RUNNING)
├── OperationError               # operation invocation returned failure
├── RemoteError                  # other server-side error
├── MDTInstanceConnectionError   # network-level failure (.cause = requests error)
├── TimeoutError                 # remote timeout — NB: shadows builtins.TimeoutError on import *
├── CancellationError
└── InternalError
```

Prefer these over generic `RuntimeError`/`ValueError` when writing mdtpy-based services.

## 1.12 Optional integrations (not auto-imported)

- **`mdtpy.airflow`** — Airflow DAG operators for orchestrating twin operations:
  `LocalDagContext` (no Airflow needed) / `AirflowDagContext`, operators
  `AASOperationOperator`, `OperationSubmodelOperator`, `RestfulAsyncRpcOperator`,
  `SetElementOperator`, and argument combinators `reference(...)`, `task_output(task, key)`,
  `sink(ref_string)`, `literal(x)`. Full pipeline example: `src/samples/sample_inspector_simiulation.py`.
  Details: `src/mdtpy/airflow/CLAUDE.md`, `src/mdtpy/airflow/README.md`.
- **`mdtpy.rpc.restful`** — direct RESTful RPC to an operation server:
  `RESTfulRpcClient` (sync) / `RESTfulAsyncRpcClient` (poll-based).
  `RESTfulAsyncRpcClient(base_url, op_endpoint, inputs, outputs=None).call() -> outputs dict`;
  inputs/outputs accept the same reference/raw-value mix as `invoke()`.
  Example: `src/samples/sample_restful_async_rpc.py`.

## 1.13 Serialization helpers

- `mdtpy.json_dumps(obj)` — `json.dumps` with datetime→ISO 8601 support. It does **NOT**
  serialize `ElementValue` objects; call `.to_raw_object()` first.
- `mdtpy.basyx.serde.to_json(x)` / `from_json(s)` — serialize basyx model objects
  (Submodel, SubmodelElement, AAS shells).
- Descriptors (`InstanceDescriptor` etc.) are `dataclass-wizard` `JSONWizard`s:
  `.to_dict()` / `.from_dict()`.

## 1.14 Gotchas checklist (things LLMs get wrong)

1. `read_value()` returns an `ElementValue`, never a bare scalar. Unwrap before display,
   comparison, or JSON serialization.
2. `update_value()` needs an `ElementValue`; raw values go to `update_with_raw_value()`.
3. `bool(manager.instances)` is always `True` — use `len(...) == 0`.
4. `inst.operations`, `submodel_descriptors`, `timeseries` raise
   `InvalidResourceStateError` when the twin isn't RUNNING.
5. `inst.start()` on an already-RUNNING twin raises — guard with `is_running()`.
6. `invoke()` writes outputs back to the server even if you drop the return value.
7. File parameter values are metadata; bytes go through `get_attachment()`/`put_attachment()`.
8. Every property access like `inst.parameters` is a fresh HTTP call — hold it in a local
   variable inside loops.
9. Call `mdtpy.connect()` before touching any `reference(...)` value method.
10. Old API names that NO LONGER EXIST: `mdtpy.Argument` (→ `ArgumentDescriptor` +
    `oparg:` references), `op.input_arguments`/`op.output_arguments` on the service
    (→ `input_arg_descs` / `output_arg_desc_dict`), `ElementReferenceDict`, subscript
    access on `FileValue` (→ `.content_type` attribute).

---

# Part 2 — Working on the mdtpy codebase itself

## Build & Development

- **Python:** 3.10+ (`.python-version`) · **Package manager:** uv
- Install runtime deps: `uv sync` · dev deps: `make install-dev` (= `uv sync --group dev`)
- Build: `uv build` (sdist+wheel into `dist/`; `samples` excluded from the wheel)

## Testing

```bash
make test                     # canonical: full pytest suite (470+ tests, mock-based)
make test-cov                 # with coverage
uv run --env-file .env pytest tests/test_instance.py               # single file
```

**Why `make test`:** shells with ROS2 sourced auto-load the system `launch_pytest` plugin
and crash (`ModuleNotFoundError: yaml`); the Makefile/.env inject
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Without ROS, plain `uv run pytest` works.

`tests/conftest.py` resets the `mdt_inst_url`/`mdt_manager` globals in `mdtpy.instance`
between tests. The `src/samples/sample_*.py` scripts are live-server smoke tests, NOT unit
tests — don't model new unit tests after them.

## Coding Conventions

- 코드 주석(inline comments, docstring)은 한국어로 작성한다. 문장은 "~한다"(평서문) 형식을 사용한다.
- 로깅/예외 메시지는 영어로 작성한다.
- Import 순서: `from __future__ import annotations` → `typing` → 표준 → 서드파티 → 로컬.
- Type hint는 built-in 우선 (`list`/`dict`/`tuple`), `Optional[X]` 권장 (`X | None` 비권장).
- 라인 길이 100자 (신규 코드), trailing comma 가급적 금지, 들여쓰기 4-space.

## Architecture notes (internals)

- **Two HTTP layers:** `instance.py` talks to the **Instance Manager** (also hosts the
  reference-based `*_of_reference` element/value endpoints that `BaseElementReference`
  delegates to). `fa3st.py` talks to **individual FA³ST instances** (used by `submodel.py`
  and attachment/add/remove ops on references); `VERIFY_TLS = False` (self-signed certs).
  Both share exception classification via `http_client.to_exception`.
- **Global manager singleton:** `mdtpy.connect()` sets `mdt_manager`/`mdt_inst_url` module
  globals in `instance.py`; `BaseElementReference` lazily resolves `service_url` /
  `prototype` / `mdt_manager` on first use, so references can be built offline.
- **`reference()` does no client-side parsing** — `param:`/`oparg:`/`timeseries:`/path
  forms are resolved server-side (`/references/$url`, `/references/$json`). The structured
  client-side reference classes and `ref/serde.py` were removed.
- **Value serde:** the manager `$value` path uses the polymorphic `@type` pair
  (`to_json_node`/`parse_json_node`); `$raw` uses plain `json.dumps(default=json_serializer)`.
  The bare-wire pair (`to_raw_json_node`/`from_raw_json_node`) currently has no production
  caller (kept for tests/compat). All value deserialization entry points live in
  `value/factory.py`.
- **`SubmodelServiceCollection`** dispatches by semantic id (Data/InfoModel →
  `SubmodelService`, Simulation/AI → `OperationSubmodelService`, TimeSeries →
  `TimeSeriesService`) and lazily fetches operation descriptors only when needed.
- **URL-encoding:** ids/ref-strings/paths are quoted with `quote(..., safe="")` where URLs
  are built — keep `safe=""`, encoded values may contain `/`.
- Module-level details: `src/mdtpy/ref/CLAUDE.md`, `src/mdtpy/value/CLAUDE.md`,
  `src/mdtpy/airflow/CLAUDE.md`.
