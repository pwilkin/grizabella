# Grizabella MCP Server API Guide

This guide documents the Grizabella Model Context Protocol (MCP) server — how
to launch it, how to connect, and the full list of tools it exposes.

## Transport

The Grizabella MCP server speaks **stdio** (the standard MCP subprocess
transport). It is **not** an HTTP server — there is no listening port, no
`curl` endpoint, and no REST/JSON-RPC URL. MCP clients spawn the server as a
child process and exchange framed JSON messages over its stdin/stdout.

## Launching the Server

```bash
poetry run grizabella-mcp --db-path /path/to/db
# optional:
poetry run grizabella-mcp --db-path /path/to/db --use-gpu
```

CLI flags:

- `--db-path PATH` — path to the Grizabella database directory. Overrides the
  `GRIZABELLA_DB_PATH` environment variable.
- `--use-gpu` — route the embedding model and the optional cross-encoder
  reranker through CUDA.

Resolution order for the database path: `--db-path` CLI arg →
`GRIZABELLA_DB_PATH` env var → default `grizabella_mcp_db` (resolved as a
Grizabella-managed instance under `~/.grizabella/db_instances/`). If the
target does not exist the server creates it.

The server writes a fresh log file named `mcp-server-YYYYMMDD_HHMMSS.log`
into the working directory at startup. `stdout` is reserved for the MCP
transport, so logging is file-only by design.

## Connecting from Python

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(
        command="poetry",
        args=["run", "grizabella-mcp", "--db-path", "/tmp/my_db"],
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([t.name for t in tools.tools])

asyncio.run(main())
```

All tool calls go through `session.call_tool("<tool_name>", {...args...})`.
Results are returned as MCP `TextContent` items whose payload is a
JSON-encoded Pydantic model (or list/bool) — deserialize with
`json.loads(...)` and (where applicable) round-trip through
`Model.model_validate(...)`.

## Error Handling

Every tool catches `GrizabellaException` and re-raises it with an `"MCP: ..."`
prefix so errors surface on the MCP client side with a descriptive message.
Unknown failures are wrapped as `Exception` with the same prefix. Check the
server log file for tracebacks.

---

## Schema Management

### `create_object_type`

**Args:** `object_type_def` — an `ObjectTypeDefinition` dict
(`name`, `description?`, `properties[]`).
**Property fields:** `name`, `data_type` (one of `TEXT`, `INTEGER`, `FLOAT`,
`BOOLEAN`, `DATETIME`, `BLOB`, `JSON`, `UUID`), `is_primary_key?`,
`is_nullable?`, `is_indexed?`, `is_unique?`, `description?`.
**Returns:** `null`.

```json
{
  "object_type_def": {
    "name": "Document",
    "description": "A text document.",
    "properties": [
      {"name": "title", "data_type": "TEXT", "is_indexed": true},
      {"name": "content", "data_type": "TEXT"}
    ]
  }
}
```

### `list_object_types`

**Args:** none. **Returns:** `ObjectTypeDefinition[]`.

### `get_object_type`

**Args:** `type_name`. **Returns:** `ObjectTypeDefinition | null`.

### `delete_object_type`

**Args:** `type_name`. **Returns:** `null`.

### `create_relation_type`

**Args:** `relation_type_def` — a `RelationTypeDefinition`
(`name`, `description?`, `source_object_type_names[]`,
`target_object_type_names[]`, `properties?`).
**Returns:** `null`.

### `list_relation_types`

**Args:** none. **Returns:** `RelationTypeDefinition[]`.

### `get_relation_type`

**Args:** `type_name`. **Returns:** `RelationTypeDefinition | null`.

### `delete_relation_type`

**Args:** `type_name`. **Returns:** `null`.

### `create_embedding_definition`

**Args:** `embedding_def` — an `EmbeddingDefinition` with:

- `name` (snake_case), `object_type_name`, `source_property_name`
- `embedding_model` (e.g. `"huggingface/mixedbread-ai/mxbai-embed-large-v1"`)
- `dimensions?` (inferred if omitted)
- `description?`
- `reranker_model?` — cross-encoder identifier (e.g.
  `"cross-encoder/ms-marco-MiniLM-L-6-v2"`). When set, semantic searches
  against this definition can post-process top-K vector hits with a
  cross-encoder. See the reranker-aware tools below.
- `rerank_candidate_multiplier?` (default `5`) — oversample factor: the
  vector search pulls `limit * multiplier` hits before the cross-encoder
  cuts them back down to `limit`.

**Returns:** `null`.

---

## Object Instance Management

### `upsert_object`

**Args:** `obj` — an `ObjectInstance` (`id?`, `weight?`, `upsert_date?`,
`object_type_name`, `properties`).
**Returns:** the stored `ObjectInstance` (populated `id`, `upsert_date`).

### `get_object_by_id`

**Args:** `object_id` (UUID string), `type_name`.
**Returns:** `ObjectInstance | null`.

### `delete_object`

**Args:** `object_id` (UUID string), `type_name`.
**Returns:** `true` on delete, `false` when not found.

### `find_objects`

**Args:** `type_name`, `filter_criteria?` (dict of exact matches),
`limit?`.
**Returns:** `ObjectInstance[]`.

### `begin_bulk_addition` / `finish_bulk_addition`

Toggle a bulk ingestion mode in which embedding generation is deferred until
`finish_bulk_addition` is called. Useful for high-throughput loads.
**Args:** none. **Returns:** status string.

---

## Relation Instance Management

### `add_relation`

**Args:** `relation` — a `RelationInstance` (`id?`, `weight?`,
`relation_type_name`, `source_object_instance_id`,
`target_object_instance_id`, `properties?`).
**Returns:** the stored `RelationInstance`.

### `get_relation`

Looks up relations of a given type between a specific source and target.
**Args:** `from_object_id`, `to_object_id`, `relation_type_name` (all
strings). **Returns:** `RelationInstanceList` with a `relations` array —
multiple parallel relations of the same type can exist between the same
pair.

### `delete_relation`

**Args:** `relation_type_name`, `relation_id` (UUID string of the specific
relation).
**Returns:** `true` if the row was actually removed, `false` otherwise.

> Note: earlier versions of this doc described `delete_relation` as taking
> `from_object_id`/`to_object_id`. That was incorrect — the tool deletes a
> single relation identified by its own UUID. Use `get_relation` to find the
> relation's id first if you only have the endpoints.

### `get_outgoing_relations`

**Args:** `args` object with `object_id` (UUID string), `type_name`, and
optional `relation_type_name` filter. **Returns:** `RelationInstance[]`.

### `get_incoming_relations`

Same signature as `get_outgoing_relations`, but traverses in the reverse
direction.

### `find_relations`

More general relation lookup. Filters on any combination of
`relation_type_name`, `source_object_id`, `target_object_id`, `query` (a
properties dict), and `limit`. Returns `RelationInstanceList`.

---

## Semantic Search

### `find_similar_by_embedding`

Text-first semantic search with optional cross-encoder reranking.

**Args:** a single `args` object containing:

- `embedding_definition_name` (string, required)
- `query_text` (string, required)
- `limit` (int, default `5`)
- `filter_condition` (string, optional) — a LanceDB WHERE clause applied
  before the ANN step (e.g. `"object_instance_id != 'abc…'"`)
- `rerank` (bool, optional):
  - `null` / omitted — auto-enable if a reranker is configured on the
    `EmbeddingDefinition` or if `rerank_model` is supplied.
  - `true` / `false` — force-enable or force-disable.
- `rerank_model` (string, optional) — cross-encoder model override.
- `rerank_candidates` (int, optional) — how many vector hits to fetch
  before reranking. Defaults to
  `limit * EmbeddingDefinition.rerank_candidate_multiplier`.

**Returns:** `ObjectInstance[]` ordered by vector distance (ascending) or,
when reranking ran, by rerank score (descending).

```json
{
  "args": {
    "embedding_definition_name": "doc_content_embed",
    "query_text": "state machine optimizations",
    "limit": 5,
    "rerank": true,
    "rerank_candidates": 50
  }
}
```

### `search_similar_objects`

**Status:** currently raises `NotImplementedError`. This tool is retained so
that the MCP schema matches the Python client surface; use
`find_similar_by_embedding` (text query) or `execute_complex_query` with an
`EmbeddingSearchClause` (pre-computed vector) instead.

### `get_embedding_vector_for_text`

**Args:** an object with `text_to_embed` (string) and
`embedding_definition_name` (string).
**Returns:** `{ "vector": [<floats>] }` — useful when you want to build a
`ComplexQuery` programmatically.

### `execute_complex_query`

**Args:** `query` — a `ComplexQuery` consisting of:

- `description?` (string)
- `components[]` — each a `QueryComponent`:
  - `object_type_name` (string)
  - `relational_filters?` — array of `RelationalFilter`
    (`property_name`, `operator` ∈ `==, !=, >, <, >=, <=, LIKE, IN, CONTAINS, STARTSWITH, ENDSWITH`,
    `value`).
  - `embedding_searches?` — array of `EmbeddingSearchClause`:
    - `embedding_definition_name` (string)
    - `similar_to_payload` (float[]) — the precomputed query vector
    - `threshold?`, `limit?`, `is_l2_distance?`
    - `rerank_query_text?` — raw text of the query; required to enable the
      cross-encoder reranker for this clause
    - `rerank?` / `rerank_model?` / `rerank_candidates?` — same semantics
      as `find_similar_by_embedding`
  - `graph_traversals?` — array of `GraphTraversalClause`:
    - `relation_type_name`, `direction` (`"outgoing"` | `"incoming"`),
      `target_object_type_name`, `target_object_id?`,
      `target_object_properties?`

**Returns:** `QueryResult` with `object_instances[]` and `errors[]`.

**Reranking inside a complex query.** When `rerank_query_text` is supplied
on an `EmbeddingSearchClause` and a reranker is configured (or
`rerank_model` is provided per-call), the lancedb step oversamples and
re-scores with the cross-encoder before handing ids to the next step.
Threshold filtering on the clause is skipped in that case (units change
from cosine distance to rerank score).

---

## Notes on Return Shapes

- Tools whose Python return type is a Pydantic model (`ObjectInstance`,
  `RelationInstance`, `ObjectTypeDefinition`, etc.) are serialized as JSON
  text and arrive as `TextContent` blocks. Round-trip via
  `Model.model_validate(json.loads(content.text))`.
- `get_outgoing_relations` / `get_incoming_relations` / `find_relations`
  return a `RelationInstanceList` wrapper with a `relations` field — look
  inside it rather than expecting a bare array.
- `begin_bulk_addition` / `finish_bulk_addition` return human-readable
  status strings, not structured data.
