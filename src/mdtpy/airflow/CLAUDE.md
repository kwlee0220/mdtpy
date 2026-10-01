# CLAUDE.md — mdtpy/airflow

This file provides guidance to Claude Code (claude.ai/code) when working with the `mdtpy.airflow` subpackage.

For repository-wide conventions and the broader architecture, see `../../../CLAUDE.md`. End-user usage is in `README.md` next to this file and in `doc/programming_guide.md`.

## What this package is

`mdtpy.airflow` is an **optional** subpackage that wraps MDT Operation invocation as Airflow task bodies. It is **not** auto-imported by `mdtpy/__init__.py`, so direct dependence on Airflow is avoided in the core library.

Four modules (one of them, `operator/`, is now a package) / three layered abstractions:

1. **`DagContext`** (`dag_context.py`) — runtime adapter. `LocalDagContext(task_id, mdt_inst_url)` keeps task outputs in a class-level dict for in-process testing, takes `mdt_inst_url` as a **required** argument, connects eagerly, and never imports Airflow. `AirflowDagContext(mdt_manager_url=None)` defers `airflow.sdk` import to method-call time, connects **lazily** (first `mdt_manager` access, i.e. at task-run time, not construction), and uses XCom (`'task_output'` key) + `Variable` (URL falls back to the `mdt_manager_url` Variable). Task outputs pushed to XCom are serialized to the `@type`/`value` polymorphic JSON form via the module-level helpers `_to_task_output_json_node` (push) / `_parse_task_output_json_node` (pull), because XCom only accepts JSON-serializable values.
2. **`DagTaskArgument`** (`dag_task_argument.py`) — describes how to obtain an input value at task runtime; `get(context) -> ArgumentValue` (= `ElementValue | ElementReference`). Three concrete specs + matching factory helpers: `task_output()` → `TaskOutputArgument` (reads `context.get_task_output(...)` → `ElementValue`), `reference()` → `ElementReferenceArgument` (resolves the ref and **reads its value**, returning the value — but returns the `ElementReference` **itself** when the value is a `FileValue`, so File inputs can be passed by reference), `literal()` → `LiteralArgument` (wraps a raw scalar with `mdt_value()` → `ElementValue`; unsupported types raise `ValueError` at construction, i.e. DAG-definition time). So `get()` returns an `ElementValue` for `task_output`/`literal` and (for `reference`) an `ElementValue` normally or an `ElementReference` for File targets.
3. **`Operator`** (`operator/` package) — task body; `run(context=None)` (defaults to `AirflowDagContext()`). The `Operator` ABC plus the type aliases (`DagTaskInputArgument = DagTaskArgument`, `DagTaskOutputArgument = ElementReferenceArgument`) live in `operator/operator.py`; each concrete operator is in its own module and re-exported from `operator/__init__.py` (so `from mdtpy.airflow.operator import ...` and `from mdtpy.airflow import ...` both work): `CopyElementOperator(source, target=None)` (`set_element.py`, reads `source` and optionally writes to `target`; owns the `_to_element_value` helper), `OperationSubmodelOperator(instance, submodel, inputs, outputs)` (`operation_submodel.py`, calls a submodel `Operation`), `AASOperationOperator(instance, submodel, op_idshort_path, inputs, outputs)` (`aas_operation.py`, calls an AAS `Operation` by idShort path), `RestfulAsyncRpcOperator(base_url, op_endpoint, inputs, outputs)` (`restful_async_rpc.py`, invokes over RESTful async RPC). Constructor args are passed **directly** (not via a dict).

`types.py` holds `ArgumentValue = ElementValue | ElementReference` and `TaskOutput = ElementValue`.

The `__init__.py` re-exports the modules via `from .X import *`. Callers do `from mdtpy.airflow import LocalDagContext, OperationSubmodelOperator, reference, task_output, ...`.

## Architecture quirks worth knowing

- **`AirflowDagContext` does deferred imports.** `from airflow.sdk import Variable` and `get_current_context()` are inside method bodies. Don't hoist them to the module top — that would force every `mdtpy.airflow` consumer to have Airflow installed.
- **Two different `reference()` functions.** The airflow `reference(ref_string)` builds an `ElementReferenceArgument` (an **input spec** whose `get()` reads the referenced value and returns it — or returns the `ElementReference` itself when that value is a `FileValue`). A **write target** (`CopyElementOperator.target`, `OperationSubmodelOperator.outputs` values) must be an actual `ElementReference` — build those with `mdtpy.reference(...)` (i.e. `mdtpy.ref.reference`), not the airflow one.
- **`OperationSubmodelOperator.run` merges materialized inputs and output destinations before calling `invoke`** (`{**in_args, **outputs}`). `inputs` values are `DagTaskArgument`s resolved to values; `outputs` values are `ElementReference`s. `OperationSubmodelService.invoke` auto-writes each result to the `ElementReference` passed for that id, so putting a ref in `outputs` causes the operation result to be written back to it.
- **`CopyElementOperator` requires `source` at construction** (raises `ValueError("Input argument 'source' is required")` if `None`). It stores the read value under the `'target'` key in task output — downstream tasks reference it with `task_output(task_id, 'target')`.
- **`LocalDagContext.__TASK_OUTPUT` is a class variable**, so output state leaks across instances within the same process. Tests that exercise more than one DAG should reset it explicitly.
- **`DagContext` is fully abstract — six members**: `task_id`, `mdt_manager`, `get_submodel`, `resolve_reference`, `get_task_output`, `set_task_outputs`. `mdt_manager` is a `@property @abstractmethod`, so a subclass must override it **at class level** (an instance attribute set in `__init__` does NOT satisfy it — that mistake makes the class un-instantiable).
- **`resolve_reference` asymmetry is intentional.** `LocalDagContext` wraps the string lazily via `mdtpy.ref.reference()` (no HTTP at resolve time); `AirflowDagContext` uses `MDTInstanceManager.resolve_reference()`, which queries the manager for the `service_url` eagerly.
- **`TaskOutput` is `ElementValue`.** Both contexts' `set_task_outputs` reject a non-`ElementValue` value with `TypeError` via the shared `_check_task_output` helper (Airflow through `_to_task_output_json_node`, Local directly), so the contract is enforced uniformly.
- **Missing task-output lookups raise `KeyError`** with a message naming the task/argument (both contexts) — not `assert`, so behavior survives `python -O`.
- **`AirflowDagContext.__repr__` is side-effect-free** (only shows `mdt_manager_url`). Don't add `get_current_context()`/XCom calls back into it — it must be safe outside a running task (DAG parsing, debuggers).

## File-input handling

The value-vs-reference decision lives in `ElementReferenceArgument.get()`: it reads the referenced value and returns it, **except** when the value is a `FileValue` — then it returns the `ElementReference` itself. So `OperationSubmodelOperator` (which passes each `arg.get(context)` straight into `invoke()`) hands File inputs to the operation by reference and everything else by value. `CopyElementOperator` always wants a value, so it wraps the result in `_to_element_value` (which re-reads a File reference into its `FileValue`). Note a File `source` in `CopyElementOperator` is therefore read twice (once in `get()` to detect the File, once in `_to_element_value`); an uncommon path, but not free.

## Known issues

None currently.

## Testing

Unit tests live in `tests/test_airflow.py` (run with `make test`; no Airflow install needed). Patterns used there, for extending coverage:

- `LocalDagContext` is created with `mdtpy.airflow.dag_context.connect` patched (no real HTTP).
- An autouse fixture resets `LocalDagContext._LocalDagContext__TASK_OUTPUT` around each test.
- `AirflowDagContext` is built via `object.__new__` (bypassing the `airflow.sdk` import in `__init__`) and its `task_instance` property is patched with a mock TaskInstance whose `xcom_push`/`xcom_pull` round-trip through `json.dumps`/`json.loads` to reproduce XCom's JSON-serializability constraint. The name-mangled private URL attribute is `ctx._AirflowDagContext__mdt_manager_url`.

## Coding conventions

Follow the repo-wide rules in `../../../CLAUDE.md` (Korean docstrings, `Optional[X]`, 4-space indent, etc.).
