# CLAUDE.md — `mdtpy.value` package

Guidance for Claude Code when working inside `src/mdtpy/value/`. See the repository-root
`CLAUDE.md` for project-wide conventions (Korean docstrings, English exceptions/logs,
import order, 100-char lines).

## What this package is

The value model for SubmodelElements: the `ElementValue` ABC with 6 subclasses, plus the
conversions between an `ElementValue` and each of its external representations.
Serialization (`to_*`) lives as methods on `ElementValue`; **all deserialization /
construction entry points live in `factory.py`** and are re-exported from
`mdtpy.value` (and, via `from .value import *`, at `mdtpy` top level).

## Files

- **`types.py`** — type aliases only (`RawElementValueType`, `ElementJsonValueType`,
  `PropertyJsonValue`, `CollectionValueType`, `ListValueType`, `RawMLPropertyValue`,
  `MultiLanguagePropertyJsonValue`, `FileJsonValue` TypedDict, `PropertyValueType`).
  `ElementValue` is imported under `TYPE_CHECKING`.
- **`codec.py`** — `@type` wire constants (`FIELD_TYPE`/`FIELD_VALUE`, `TYPE_*`),
  XSD ↔ mdt-type ↔ vtype name maps, and the private scalar codec
  (`_encode_scalar` / `_decode_scalar` / `_infer_xsd_name` / `_xsd_name_of`).
  `_STRING_ENCODED_XSD` lists the XSD types that are encoded as XSD strings even in the
  `@type` form (dateTime, duration, decimal, date, time); everything else stays JSON-native.
- **`element_value.py`** — `ElementValue` ABC + `PropertyValue`, `FileValue`
  (incl. `FileValue.from_file_path` classmethod), `RangeValue`, `MLPropertyValue`
  (read-only `Sequence[dict[str, str]]` — a list of single-entry `{lang: text}` dicts),
  `ElementCollectionValue` (read-only `Mapping`),
  `ElementListValue` (read-only `Sequence`, members are **non-`None`**), and the
  `mdt_value()` scalar convenience factory (its `case bool()` must stay **before**
  `case int()` — `bool` is an `int` subclass).
- **`factory.py`** — `get_value(sme)`, `from_raw_object(value, proto)`,
  `from_raw_json_node(value, proto)`, `parse_json_node(jnode)`, `parse_json_string(s)`.
- **`__init__.py`** — `update_element_with_raw_value(sme, raw)` + re-exports.

## The four conversion pairs

| Representation | serialize (on `ElementValue`) | deserialize (in `factory.py`) | proto needed |
|---|---|---|---|
| raw Python object | `to_raw_object()` | `from_raw_object(value, proto)` | **SME** (type metadata; no XSD decoding — values already native) |
| bare wire JSON (no `@type`) | `to_raw_json_node()` | `from_raw_json_node(value, proto)` | **`ElementValue`** template (decodes XSD strings) |
| polymorphic `@type` JSON | `to_json_node()` / `to_json_string()` | `parse_json_node()` / `parse_json_string()` | none (self-describing) |
| basyx SME | `apply_to(sme)` writes into an SME | `get_value(sme)` reads from an SME | — |

Format differences you must keep straight (per kind):

- **File**: raw-object pair uses snake_case `content_type`; both JSON pairs use camelCase
  `contentType` (required — missing raises).
- **MLP**: all representations (raw-object, bare-wire, `@type`) use the same
  `[{lang: text}, ...]` list of single-entry dicts (e.g. `[{"en": "..."}, {"kr": "..."}]`,
  Java-compatible). Only the basyx SME side differs: `get_value`/`apply_to` convert to/from
  the dict-like `MultiLanguageTextType` (`{lang: text}`).
- **Scalars**: the `@type` pair keeps int/bool/float JSON-native (only
  `_STRING_ENCODED_XSD` types become strings); the bare-wire pair stringifies everything
  via `xsd_repr`.
- **`xs:integer` narrows to `xs:int`** on an `@type` round-trip
  (`_MDT_TYPE_TO_XSD` maps each mdt-type back to one representative XSD type). Equality
  ignores `value_type`, so this is tolerated.

**Which pair is live in production:** the `@type` pair — the manager `$value` reference
path (`read_value_of_reference` → `parse_json_string`, `update_value_of_reference` →
`to_json_string`) and the RPC package use it. The `$raw` endpoint uses plain
`json.dumps(..., default=json_serializer)`, *not* the bare-wire pair; the bare-wire and
raw-object pairs have no live production caller and are kept as converters exercised by
`tests/test_value.py`.

## Semantics to preserve

- `PropertyValue` / `RangeValue`: `value_type` is a **required** constructor arg; passing
  `None` defers to runtime-type inference at serialization time. `__eq__` compares
  values only (ignores `value_type`).
- **`None` handling** is deliberate and asymmetric by type:
  - `from_raw_object` / `from_raw_json_node`: `None` input is valid only with a
    Property(-Value) proto → `PropertyValue(None)`; other protos assert.
  - `PropertyValue(None).apply_to(sme)` **clears** the element's value (decided 2026-07;
    `test_property_value_none_clears_value`).
  - `update_element_with_raw_value(sme, None)`: Property → clears; any other SME kind →
    `ValueError`.
- `ElementListValue` members are non-`None`; `ElementCollectionValue` members are
  `Optional` (its `to_raw_json_node` skips `None` members, `to_raw_object` keeps them
  as `None` — intentional).
- Containers are read-only (`Mapping`/`Sequence`); partial updates go through a raw
  dict/list + `update_with_raw_value` on the reference side.

## Known caveats (flagged, not yet fixed — don't paper over silently)

- `MLPropertyValue.__init__` copies the input list (`list(mappings)`), but `to_raw_object()`
  / `to_raw_json_node()` / `to_json_node()` return the internal list itself — output
  aliasing hazard (a caller mutating the returned list mutates the value).
- Container-like classes compare equal to their plain-collection counterpart:
  `MLPropertyValue([{'en':'x'}]) == [{'en':'x'}]` and `ElementListValue.__eq__` accept plain
  lists. Tests rely on this.

## Testing notes

- `tests/test_value.py` covers all pairs incl. round-trips; SMEs are mocked with
  `MagicMock(spec=...)` so `match`/`isinstance` dispatch works without real basyx objects.
- Patch scalar decoding at `mdtpy.value.model.datatypes.from_xsd` (shared module object,
  works regardless of which submodule imported it).
- When adding a subclass or format: update **both** directions plus the `@type` constant
  maps in `codec.py`, and add a round-trip test — one-sided changes are exactly how the
  MLP asymmetry bug happened.
