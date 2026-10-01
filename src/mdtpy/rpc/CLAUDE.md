# CLAUDE.md — `mdtpy.rpc` package

Guidance for Claude Code when working inside `src/mdtpy/rpc/`. See the repository-root
`CLAUDE.md` for project-wide conventions (Korean docstrings, English exceptions/logs,
import order, 100-char lines).

## What this package is

RESTful RPC clients for invoking **remote operations** over HTTP against an MDT operation
server. This is a separate transport from the AAS operation invocation in
`mdtpy.operation` (which goes through FA³ST `invoke_operation_sync`); the RPC package
talks to a dedicated operation endpoint using the `RpcRequestMessage` /
`RpcResponseMessage` wire protocol.

Structural facts:

- `rpc/` itself has **no `__init__.py`** — it is a PEP 420 namespace directory. All code
  lives in `rpc/restful/`; the import path is `from mdtpy.rpc.restful import ...`.
- **Not auto-imported** by `mdtpy/__init__.py`. Nothing here is re-exported at top level.
- No pytest coverage: the only executable exercise is the live-server sample
  `src/samples/sample_restful_async_rpc.py`. Changes here cannot be verified by
  `make test` — be correspondingly careful.

## Files (`rpc/restful/`)

- **`common.py`** — `DEFAULT_TIMEOUT` (30 s per HTTP request), `VERIFY_TLS` (False:
  self-signed certs), the `RpcArgument` union
  (`ElementValue | ElementReference | str | int | float | bool`), and
  `encode_argument_to_json_node()` (input-argument → JSON encoding, see below).
- **`rpc_state.py`** — `RpcState` enum: `RUNNING` / `COMPLETED` / `FAILED` / `CANCELLED`.
- **`rpc_request_message.py`** — `RpcRequestMessage` DTO (`inputs`, optional `outputs`,
  extra top-level fields preserved across JSON round-trip; `None` fields omitted).
- **`rpc_response_message.py`** — `RpcResponseMessage` frozen dataclass (state-dependent
  invariants enforced in `__post_init__`: `COMPLETED` requires `outputs`, `FAILED`
  requires `error`), the per-state factory classmethods, `parse_response_message()`
  (HTTP response → message, converting structured error bodies to
  `RestfulRemoteException`), and `parse_output_argument_json_node()` (output dispatch,
  see below).
- **`error.py`** — `RestfulErrorEntity` DTO + `RestfulRemoteException`,
  `RpcExecutionError`, `RpcCancelledError`. **Security invariant**: the server's `code`
  string (usually a remote exception class name) is *never* used to `import_module`/load
  a class — it is carried verbatim inside `RestfulRemoteException`. Keep it that way.
- **`restful_rpc_client.py`** — `RESTfulRpcClient`: single blocking POST to
  `operation_url`; `call()` returns outputs or raises by state.
- **`restful_async_rpc_client.py`** — `RESTfulAsyncRpcClient`: POST to
  `base_url + op_endpoint` starts a session (`RUNNING` + `session_endpoint`), then polls
  `GET {session_url}` every `poll_interval` (default 3 s) until terminal state — **the
  session endpoint itself, with no `/state` or other sub-path**; the server exposes no
  such route. `cancel()` sends `DELETE {session_url}` and may be called from another
  thread.

## Wire format

The response envelope is `{"status", "session_endpoint", "outputs", "error"}`, matching
Java `utils.rpc.restful.RpcResponseMessage` field-for-field. **`status`/`session_endpoint`
were once `state`/`sessionEndpoint` on both sides, and there is no alias** — the rename is
a hard break, so an mdtpy client and a Java peer must be upgraded together. A response
missing `status` raises `ValueError("'status' is null")`; a missing `session_endpoint`
stays `None` and surfaces later when the poll URL is built. Keep these names in lockstep
with the Java DTO.

The value encoding is the same `@type` polymorphic JSON as `mdtpy.value`
(`mdt:value:*`, Java `mdt.model.sm.value.ElementValues`-compatible). Output arguments are
dispatched by tag in `parse_output_argument_json_node()`:

| node shape | parsed as |
|---|---|
| non-dict scalar | returned as-is |
| `@type: mdt:value:*` | `ElementValue` via `parse_json_node` |
| `@type: mdt:ref:*` | `ElementReference` via `parse_reference_json_node` (**requires a connected global `mdt_manager`**) |
| no `@type`, has `modelType` | basyx `SubmodelElement` via `basyx_serde.from_dict` |
| plain dict | returned as-is |
| unknown `@type` | `ValueError` |

Input arguments (`encode_argument_to_json_node`): literals pass through JSON-native;
`ElementValue` → its `@type` JSON; `ElementReference` → the *referenced value's* `@type`
JSON, **except** when the referenced value is a `FileValue` — then the *reference itself*
(`mdt:ref:*` JSON) is sent so the server handles the file by reference rather than by
value. Preserve this File special case.

## Client semantics

- Both clients map terminal states identically: `COMPLETED` → outputs dict (empty dict if
  `None`), `FAILED` → `RpcExecutionError` with the remote cause as `__cause__`,
  `CANCELLED` → `RpcCancelledError`, anything else → `RuntimeError`.
- Async `call()` sleeps `poll_interval` **before** the first poll, and checks the
  `timeout` deadline (monotonic clock) each iteration → `TimeoutError`. A timeout does
  **not** cancel the server-side session; the operation keeps running remotely.
- Async start responses may only be `RUNNING` (with `session_endpoint`) or `FAILED`.
- `cancel()` reads the **HTTP status code**, not the body state: `200` + `CANCELLED` →
  `True`, `409 Conflict` (already terminal, or the operation refused the cancel) →
  `False`. The 409 check must stay **before** `parse_response_message()`, which turns
  every non-2xx response into an exception. Anything else — `404` for a session that
  never existed or was already reclaimed — propagates; 409 and 404 are different
  situations and must not be collapsed. A `200` carrying any state other than `CANCELLED`
  raises `RuntimeError`: the server expresses "could not cancel" as 409. Before `call()`,
  `session_url` is `None` and `cancel()` raises `RuntimeError`.
- The async call URL is `base_url + op_endpoint` concatenated **without** a separator —
  `op_endpoint` must start with `/` (the sample passes `"/operations/AddAndSleep"`).
- `RpcRequestMessage` stores the caller's `inputs`/`outputs` dicts **without copying**
  (documented behavior): mutating them after construction changes the message. The async
  client encodes arguments at `call()` time, not at construction.

## Known caveats (flagged, not yet fixed — don't paper over silently)

- In `encode_argument_to_json_node`, the `smev is not None` check is dead
  (`read_value()` returns `ElementValue`, never `None`).
