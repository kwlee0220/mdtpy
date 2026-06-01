# CLAUDE.md — mdtpy/airflow

This file provides guidance to Claude Code (claude.ai/code) when working with the `mdtpy.airflow` subpackage.

For repository-wide conventions and the broader architecture, see `../../../CLAUDE.md`. End-user usage is in `README.md` next to this file and in `doc/programming_guide.md`.

## What this package is

`mdtpy.airflow` is an **optional** subpackage that wraps MDT Operation invocation as Airflow task bodies. It is **not** auto-imported by `mdtpy/__init__.py` (the line is commented), so direct dependence on Airflow is avoided in the core library.

Three layered abstractions:

1. **`DagContext`** (`dag_context.py`) — runtime adapter. `LocalDagContext` keeps task outputs in a class-level dict for in-process testing; `AirflowDagContext` defers `airflow.sdk` import to method-call time and uses XCom (`'task_output'` key) + `Variable`.
2. **`ArgumentSpec`** (`argument_spec.py`) — describes how to obtain a value at task runtime. Three concrete specs and matching factory helpers (`task_output`, `reference`, `literal`).
3. **`Invocation`** (`invocation.py`) — task body. `SetElementInvocation` reads a `source` and optionally writes to `target`; `AASOperationTaskInvocation` calls a submodel `Operation`. Input/output specs are passed as an `InvocationArgumentSpecs` TypedDict (both `inputs` and `outputs` are `NotRequired`); the module-level helpers `get_input_argument_dict(specs)` / `get_output_argument_dict(specs)` read each key with a `{}` default.

The `__init__.py` re-exports the three submodules via `from .X import *`, so callers do `from mdtpy.airflow import LocalDagContext, AASOperationTaskInvocation, reference, task_output, ...`. Each submodule declares `__all__`, so `import *` only pulls the intended public names (the factories, the `*ArgumentSpec` / `*Invocation` / `*DagContext` classes, `InvocationArgumentSpecs`, the type aliases, and the two `get_*_argument_dict` helpers) — not their internal imports.

## Architecture quirks worth knowing

- **`AirflowDagContext` does deferred imports.** `from airflow.sdk import Variable` and `get_current_context()` are inside method bodies. Don't hoist them to the module top — that would force every `mdtpy.airflow` consumer to have Airflow installed.
- **`AASOperationTaskInvocation.run` merges inputs and outputs before calling `invoke`** (`get_input_argument_dict(...) | get_output_argument_dict(...)`, see `invocation.py`). The reason: `OperationSubmodelService.invoke` auto-updates any `ElementReference` passed in the kwargs whose key is in `output_arguments`. So putting an output reference in `argument_specs['outputs']` causes the operation result to be written back to that reference.
- **`SetElementInvocation` requires `source` in `inputs`** (raises `ValueError("Input argument 'source' is required")` otherwise) and treats `target` as the only meaningful key in `outputs`. Other keys are ignored.
- **`LocalDagContext.__TASK_OUTPUT` is a class variable**, so output state leaks across instances within the same process. Tests that exercise more than one DAG should reset it explicitly.
- **`DagContext` is fully abstract.** All five members — `task_id`, `get_submodel`, `resolve_reference`, `get_task_output_argument`, `set_task_output` — carry `@abstractmethod`, so a subclass that misses any of them cannot be instantiated.

## Known issues

These are real bugs/oversights that future work should be aware of:

- **`LocalDagContext.__init__` references `Variable.get(...)` without importing `Variable`** when `mdt_inst_url` is `None` (`dag_context.py:83`). Calling it with `mdt_inst_url=None` outside Airflow raises `NameError: name 'Variable' is not defined`. Either import `Variable` from `airflow.sdk` lazily (matching `AirflowDagContext`), or make `mdt_inst_url` required for `LocalDagContext`.
- **Unused imports** in `dag_context.py`: `Any`, `cached_property`. Safe to remove.
- **Commented-out `add_task_output_value` blocks** remain in `DagContext` / `LocalDagContext` / `AirflowDagContext`. These look like a half-finished migration; remove if no longer needed.

## Testing

There is currently **no pytest coverage** for this subpackage. If you add tests:

- Use `LocalDagContext` (no Airflow needed). Mock `connect()` / `MDTInstanceManager` to isolate from network.
- Reset `LocalDagContext._LocalDagContext__TASK_OUTPUT` between tests, or add a public `reset()` classmethod.
- Patch `mdtpy.airflow.dag_context.connect` to avoid real HTTP calls.

## Coding conventions

Follow the repo-wide rules in `../../../CLAUDE.md` (Korean docstrings, `Optional[X]`, 4-space indent, etc.). All files in this subpackage have been converted to 4-space indentation — keep new code 4-space and do not reintroduce the old 2-space style.
