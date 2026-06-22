# Getting Started with Grizabella

This guide walks through your first steps with Grizabella, whether you're
using it as a Python library, through the PySide6 UI, or via the MCP server.

## Using Grizabella as a Library (Python API)

```python
from uuid import uuid4

from grizabella.api import Grizabella
from grizabella.core.models import (
    EmbeddingDefinition,
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDataType,
    PropertyDefinition,
)

# 1. Open a Grizabella database. Passing a bare name ("default") resolves to
#    a per-user data directory; passing a Path uses it as-is.
with Grizabella(db_name_or_path="my_db", use_gpu=False) as client:

    # 2. Define an object type (like a table / node label).
    note_otd = ObjectTypeDefinition(
        name="Note",
        description="A simple text note.",
        properties=[
            PropertyDefinition(name="title",   data_type=PropertyDataType.TEXT, is_nullable=False),
            PropertyDefinition(name="content", data_type=PropertyDataType.TEXT),
        ],
    )
    client.create_object_type(note_otd)

    # 3. (Optional) Define an embedding over the 'content' property, with an
    #    optional cross-encoder reranker that will be applied to semantic
    #    searches automatically when a query_text is supplied.
    client.create_embedding_definition(EmbeddingDefinition(
        name="note_content_embedding",
        object_type_name="Note",
        source_property_name="content",
        embedding_model="huggingface/mixedbread-ai/mxbai-embed-large-v1",
        reranker_model="cross-encoder/ms-marco-MiniLM-L-6-v2",  # optional
    ))

    # 4. Upsert an ObjectInstance. Note the field is `properties`, not `data`.
    note = client.upsert_object(ObjectInstance(
        id=uuid4(),
        object_type_name="Note",
        properties={"title": "My First Note", "content": "Hello Grizabella!"},
    ))
    print(f"Stored note {note.id} (upserted at {note.upsert_date})")

    # 5. Retrieve by id + type.
    fetched = client.get_object_by_id(str(note.id), "Note")
    assert fetched is not None
    print(fetched.properties["title"])

    # 6. Semantic search. If the EmbeddingDefinition carries a reranker_model,
    #    or rerank=True + rerank_model is supplied, the top candidates are
    #    cross-encoded before the final top-`limit` are returned.
    hits = client.find_similar(
        embedding_name="note_content_embedding",
        query_text="a friendly greeting",
        limit=5,
        rerank=True,              # force-on; None auto-enables when a model is configured
        rerank_candidates=50,     # oversample before reranking
    )
    for hit in hits:
        print(hit.properties.get("title"))

    # 7. Bulk mode: defer embedding generation for high-throughput ingests.
    client.begin_bulk_addition()
    for _ in range(100):
        client.upsert_object(ObjectInstance(
            id=uuid4(),
            object_type_name="Note",
            properties={"title": "bulk", "content": "…"},
        ))
    client.finish_bulk_addition()  # all deferred embeddings computed here
```

Key things to remember:

* The `Grizabella` context manager calls `connect()` / `close()` for you.
  Multiple clients pointing at the same path share a single underlying
  `GrizabellaDBManager` via a reference-counted singleton factory.
* `ObjectInstance.properties` holds the actual data; `MemoryInstance` (the
  base) provides `id`, `weight`, and `upsert_date`. There is no separate
  `created_at` / `updated_at`.
* Property data types come from `PropertyDataType` (TEXT, INTEGER, FLOAT,
  BOOLEAN, DATETIME, BLOB, JSON, UUID) — there is no `DataType` enum.
* `use_gpu=True` routes both sentence-transformer embedding and cross-encoder
  reranking through CUDA when available.

See [Python API Detailed Guide](./python_api_detailed.md) for relations,
embeddings, and complex queries.

## Using the PySide6 UI

Launch with:

```bash
poetry run grizabella-ui
```

The **Connection View** lets you connect to the default Grizabella database
(under your user data directory) or pick/create one via "Browse". Once
connected, the main window exposes:

* **Schema editors** for Object Types and Relation Types — define names,
  properties, and allowed source/target types.
* **Embedding Definitions** for attaching vector (and optional reranker)
  models to object-type properties.
* **Object / Relation Explorers** to create, edit, and browse instances.
* A **Query** view for running semantic searches and complex queries.

See [PySide6 UI Guide](./pyside6_ui_guide.md) for a tour.

## Using the MCP Server

Grizabella's MCP server speaks the Model Context Protocol over **stdio**
(it is not an HTTP server). Clients spawn it as a subprocess:

```bash
poetry run grizabella-mcp --db-path /path/to/db
# optional: --use-gpu
```

Any MCP-compatible client can then connect over stdio. For example, in
Python:

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
            result = await session.call_tool(
                "find_similar_by_embedding",
                {
                    "args": {
                        "embedding_definition_name": "note_content_embedding",
                        "query_text": "a friendly greeting",
                        "limit": 5,
                        "rerank": True,
                    },
                },
            )
            print(result)

asyncio.run(main())
```

See [MCP Server API Guide](./mcp_server_api_guide.md) for the full tool
catalog (schema management, instance CRUD, semantic search, complex
queries, reranking).
