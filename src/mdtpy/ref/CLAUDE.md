# CLAUDE.md — `mdtpy.ref` package

Guidance for Claude Code when working inside `src/mdtpy/ref/`. See the repository-root
`CLAUDE.md` for project-wide conventions (Korean docstrings, English exceptions/logs,
import order, 100-char lines).

## What this package is

The element-reference abstraction: a string expression (`ref_string`) that names a single
SubmodelElement inside an MDT instance, plus the operations to read/write that element and
its value **without holding the element itself**. Constructing a reference performs **no
HTTP**; everything remote is resolved lazily on first access.

## Files

- **`reference.py`** — `ElementReference` ABC. Abstract surface: `model_type`, `read`,
  `write`, `read_value`, `update_value`, `update_with_raw_value`, the four attachment ops
  (`get_attachment` / `put_attachment` / `put_attachment_with_bytes` / `delete_attachment`),
  and reference serde (`to_json_node` / `to_json_string`). `ref_string` is a non-abstract
  property that raises `NotImplementedError` unless overridden.
- **`base_reference.py`** — the single concrete implementation, `BaseElementReference`
  (details below).
- **`__init__.py`** — `reference(ref_string)` factory (thin wrapper: returns
  `BaseElementReference(ref_string)`, no parsing/dispatch) and the server-delegated
  reference serde free functions `parse_reference_json_node` / `parse_reference_json_string`
  (POST to the manager's `from_reference_json`; require a connected global `mdt_manager`,
  else `RuntimeError`). All of these plus `BaseElementReference` are in `__all__` and are
  therefore re-exported at top level via `from .ref import *` in `mdtpy/__init__.py`.

## `BaseElementReference` — the split you must not confuse

Operations go over **two different HTTP layers**:

| Path | Operations | Transport |
|---|---|---|
| **Manager-side** (global `mdt_manager`'s `*_of_reference` API, `instance.py` HTTP) | `read`, `write`, `read_value`, `update_value`, `update_with_raw_value`, `to_json_node`, `to_json_string` | manager REST endpoints (`/submodel-element?ref=`, `$value`, `$raw`, `/references/$json`) |
| **FA³ST-direct** (resolved `service_url`, `fa3st.py` HTTP) | `add`, `remove`, `pathes`, all four attachment ops | the running FA³ST instance itself |

Consequences:

- Manager-side ops work as long as `mdtpy.connect()` was called — even if you never knew
  the instance's own URL.
- FA³ST-direct ops need the target MDTInstance to be **running**: `service_url` resolves
  through `mdt_manager.get_reference_service_url()` and may be `None` for a stopped
  instance. `add` / `remove` explicitly raise `RuntimeError` in that case; the attachment
  ops currently do *not* guard and would build a `'None/attachment'` URL — keep the guard
  in mind if you touch them.

### Lazy, cached state

`prototype` (`cached_property`, = first `read()`), `service_url` (resolved once, then
cached), `mdt_manager` (`cached_property`; raises `RuntimeError` if `mdtpy.connect()` has
not been called), and the `to_json_node` result (cached in `__json_node`;
`to_json_string` deliberately re-queries and does **not** cache). Because of this caching,
a reference does not observe type/URL changes after first resolution — construct a fresh
reference if the instance was restarted elsewhere.

Derived read-only properties `semantic_id` / `model_type` / `value_type` all go through
`prototype`, so their first access triggers one manager-side `read`. `value_type` returns
the XSD type name for a `Property` and a class-name string
(`'SubmodelElementCollection'`, `'File'`, ...) for the other kinds.

## No batch-reference class anymore

There used to be an `ElementReferenceDict(UserDict, ElementReference)` batch class here, then
briefly an `ArgumentList(UserDict[str, Argument])` in `operation/`. Both were removed. Operation
argument groups are now plain `dict[str, Argument]` built by `build_argument_dict()` in
`operation/mdt_operation.py` (duplicate-id → `MDTException`). There is no dict-level batch value
op; callers index the dict and use each `Argument`'s own `BaseElementReference` value methods
(`op.output_arguments['Defect'].update_value(...)`). Output write-back on `invoke()` is done
per-argument inside `OperationSubmodelService.invoke`, not via a batch call.

## Subclasses elsewhere in the codebase

- `MDTParameter(BaseElementReference)` — `parameter.py` (built with `descriptor.reference`
  as `ref_string`).
- `Argument(BaseElementReference)` — `operation/mdt_operation.py`; grouped into a plain
  `dict[str, Argument]` by `build_argument_dict()`.
- `timeseries.py` consumes `BaseElementReference` for segment/metadata access.

Changing `BaseElementReference`'s constructor signature or lazy-resolution behavior ripples
into all of the above plus `tests/test_reference.py`.

## Testing notes

- `tests/conftest.py` resets the `mdt_inst_url` / `mdt_manager` module globals in
  `mdtpy.instance` between tests — rely on that instead of manual cleanup when a test
  needs a fake global manager.
- Mock the manager-side ops at `mdt_manager` level (e.g. a `MagicMock` assigned to
  `mdtpy.instance.mdt_manager`) and FA³ST-direct ops at `mdtpy.fa3st.call_*` level; they
  are separate layers and one mock does not cover the other.
- `read_value()` returns an `ElementValue`, never a raw scalar/dict — tests that feed
  references into other components must mock `read_value.return_value` as an
  `ElementValue`-like object (see `tests/test_timeseries.py` for the
  `read_value.return_value.to_raw_object.return_value` pattern).
