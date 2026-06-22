# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Grizabella is a tri-layer memory framework for LLM solutions that unifies three storage engines behind a single Python API and an optional MCP server:

- **SQLite** — relational/metadata layer (authoritative store for object/relation properties)
- **LanceDB** — vector layer (embedding storage and ANN search)
- **Kuzu** — graph layer (relations, traversal). The `real_ladybug` dependency is a packaging shim; `kuzu` 0.10.1 is the actual engine used by `grizabella/db_layers/kuzu/`.

There is also a PySide6 desktop UI (`grizabella-ui`) and a TypeScript MCP client (`typescript/`) that talks to the Python MCP server — the TS package is an independent npm project with its own tests.

## Common commands

Environment is managed with **Poetry** (Python `>=3.12, <3.14`).

```bash
poetry install                             # install deps
poetry run pytest                          # full test suite
poetry run pytest tests/unit               # only unit tests
poetry run pytest tests/integration        # only integration tests
poetry run pytest tests/e2e                # only e2e (spawns MCP server subprocess)
poetry run pytest tests/unit/core/test_foo.py::test_bar   # single test
poetry run pytest -k "pattern"             # by keyword
poetry run pylint grizabella               # lint (ruff line-length is 240, see pyproject)
poetry run grizabella-mcp --db-path ./mydb # run the MCP server (optional --use-gpu)
poetry run grizabella-ui                   # launch PySide6 UI
poetry run mkdocs serve                    # serve docs locally
```

TypeScript client (`cd typescript/`):

```bash
pnpm install
pnpm build
pnpm test               # jest; also test:unit / test:integration / test:e2e
pnpm lint
```

## Architecture

### Layered structure

- `grizabella/api/client.py` — `Grizabella` public class. This is the only entry point library consumers (and the MCP server) should use. It delegates to `GrizabellaDBManager` via a factory.
- `grizabella/core/db_manager.py` — `GrizabellaDBManager` coordinates the three adapters. It composes three internal helpers from `_db_manager_helpers.py`: `_ConnectionHelper` (opens/owns adapters), `_SchemaManager` (object/relation/embedding type definitions), `_InstanceManager` (CRUD over instances). Schema and instance logic is split here — don't add new logic directly to `db_manager.py` if it belongs in one of the helpers.
- `grizabella/core/db_manager_factory.py` — reference-counted singleton factory keyed on the resolved DB path. Multiple `Grizabella(...)` clients pointing at the same path share one `GrizabellaDBManager`. Cleanup happens when the last reference drops; `cleanup_all_managers()` is called on MCP shutdown.
- `grizabella/core/query_engine.py` (`QueryPlanner` + `QueryExecutor`) — plans and executes `ComplexQuery` (defined in `query_models.py`). A query is decomposed into `PlannedStep`s tagged `sqlite_filter`, `lancedb_search`, or `kuzu_traversal`; the executor runs steps and intersects object-id sets across layers. When changing query semantics, updates usually span `query_models.py`, `query_engine.py`, and the adapter methods the steps call.
- `grizabella/core/models.py` — Pydantic v2 definitions (`PropertyDataType`, `ObjectTypeDefinition`, `RelationTypeDefinition`, `ObjectInstance`, `RelationInstance`, `EmbeddingDefinition`, plus `MemoryInstance` base with `id`, `weight`, `upsert_date`). These are the contract between every layer and the MCP surface — changes here ripple everywhere.
- `grizabella/core/connection_pool.py`, `resource_monitor.py` — background resource management; the MCP shutdown path touches these directly.

### DB layer adapters

`grizabella/db_layers/{sqlite,lancedb,kuzu}/` each expose an adapter plus, for SQLite and Kuzu, a `thread_safe_*_adapter.py` wrapper. The db_manager uses the thread-safe variants. All adapters inherit contracts from `db_layers/common/base_adapter.py`.

### MCP server

`grizabella/mcp/server.py` is a FastMCP app (~1000 lines) that wraps a single `Grizabella` instance and exposes its methods as MCP tools. `enhanced_server.py` is a smaller variant. Notable quirks:

- The server writes a fresh log file named `mcp-server-YYYYMMDD_HHMMSS.log` into the CWD on every startup (these accumulate in the repo root — they are not cleaned automatically).
- `shutdown_handler` (SIGINT/SIGTERM) bypasses async cleanup and directly clears `_db_manager_factory._instances` and `_connection_pool_manager` state — this was added because async cleanup during signal handling was hanging. Don't replace it with `await`-based cleanup without understanding why.
- `stdout` must stay clean of non-MCP output (it's the MCP transport). Logging is file-only by design; don't add `StreamHandler(sys.stdout)`.

### Tests

- `tests/unit/` mirrors `grizabella/` structure.
- `tests/integration/` tests talk to real SQLite/LanceDB/Kuzu backends on temp dirs.
- `tests/e2e/test_grizabella_mcp_e2e.py` spawns the MCP server as a subprocess via `poetry run python -m grizabella.mcp.server --db-path <tmp>` (see `tests/conftest.py::mcp_session`) and talks to it over stdio. Changes to the MCP entrypoint or CLI args must keep that invocation working.
- `pytest-asyncio` is configured as a dependency; `conftest.py` pins `anyio_backend` to `asyncio`.

### Bulk mode + GPU embeddings

`Grizabella.begin_bulk_addition()` / `finish_bulk_addition()` defer embedding generation so many objects can be upserted without recomputing vectors one-by-one. `use_gpu=True` routes sentence-transformers through CUDA. Both are load-bearing for the MCP server's ingestion paths — preserve them when refactoring the client.

## Conventions that are not obvious

- Do **not** bypass the factory by constructing `GrizabellaDBManager` directly except in tests that monkeypatch `grizabella.api.client.GrizabellaDBManager` (the client has a branch that detects a Mock and records the constructor call for test assertions — see `client.py` lines ~68–86).
- `db_paths.py` resolves `db_name_or_path` — a bare name (e.g. `"default"`) resolves into a per-user data dir, while a `Path` is used as-is. The MCP server's `--db-path` takes the latter form.
- Python package version lives in `pyproject.toml`; the TS client has its own independent version in `typescript/package.json`. Bump them separately.
- Ruff `line-length` is 240 — long lines in this codebase are intentional and not auto-wrapped.
