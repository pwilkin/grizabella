# Grizabella

A tri-layer memory framework for LLM solutions.

[![Docs](https://img.shields.io/badge/docs-passing-brightgreen)](https://pwilkin.github.io/grizabella/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

Grizabella is a sophisticated memory layer designed for Large Language Model (LLM) solutions. It provides a unified interface to manage and query data across relational, vector, and graph databases, enabling complex memory and knowledge retrieval for AI applications.

## Key Features

* **Tri-layer Storage:** Integrates SQLite (relational), LanceDB (vector), and LadybugDB (graph) for comprehensive data management.
* **Unified Python API:** Offers a simple and consistent Python interface to interact with all three database layers.
* **Complex Query Engine:** Allows for sophisticated queries that can span across the different data storage paradigms.
* **GPU Acceleration:** Optional GPU support for faster embedding generation using Sentence Transformers.
* **Bulk Processing:** Efficient bulk addition mode for high-throughput data ingestion.
* **PySide6 UI:** Includes an optional desktop application for visualizing and managing data.
* **MCP Server:** Can operate as a Model Context Protocol (MCP) server, allowing other tools to leverage its memory capabilities.

## Quick Links

* [User Guide](./docs/user_guide/)
* [API Reference](./docs/api_reference/build/html/)
* [Examples](./examples/)
* [MCP Server Startup](./scripts/README.md)

## Quick Installation

For production use (once published):

```bash
pip install grizabella
```

For development:

```bash
git clone https://github.com/pwilkin/grizabella.git
cd grizabella
poetry install
```

## Basic Usage Snippet

```python
from grizabella import Grizabella

# Initialize Grizabella (connects to default in-memory databases)
gz = Grizabella()

# Define an object type (implicitly creates a table/node type)
gz.create_object_type("document", {"text": str, "source": str})

# Add an object
doc1 = gz.add_object(
    object_type="document",
    data={"text": "This is the first document.", "source": "manual"},
    vector_data={"text": "This is the first document."} # Data for embedding
)

print(f"Added document with ID: {doc1.id}")

# Bulk addition with GPU support
with Grizabella(use_gpu=True) as gz:
    gz.begin_bulk_addition()
    for i in range(100):
        gz.upsert_object(obj_instance) # Define obj_instance beforehand
    gz.finish_bulk_addition()

# Further operations (querying, adding relations, etc.) would go here.
```

## Maintenance

The vector store compacts itself: after 64 writes to a table, or once writes have
been quiet for five minutes, its fragments are merged and versions older than ten
minutes are removed. A vector index (IVF_FLAT, exact squared-L2 distances) is
built once a table passes 50,000 rows; below that a flat scan is exact and takes
a few milliseconds. `GRIZABELLA_LANCEDB_COMPACT_AFTER_WRITES`,
`GRIZABELLA_LANCEDB_MAINTENANCE_INTERVAL_S` (0 turns the background pass off),
`GRIZABELLA_LANCEDB_MAINTENANCE_IDLE_S`, `GRIZABELLA_LANCEDB_CLEANUP_OLDER_THAN_S`
and `GRIZABELLA_LANCEDB_INDEX_MIN_ROWS` change those numbers.

`grizabella-maintain` works on a database no engine has open:

```bash
grizabella-maintain --db-path ./mydb stats          # rows, fragments, versions, sizes; graph vs SQLite counts
grizabella-maintain --db-path ./mydb compact        # compact every vector table, keep only the latest version
grizabella-maintain --db-path ./mydb rebuild-graph  # recreate the graph tier from SQLite
```

`rebuild-graph` is the way across a LadybugDB storage-format change: SQLite holds
every object and relation, so the graph can be recreated from it. The old graph
files are moved into `graph-backup-<time>/`, not deleted.

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` (to be added) for guidelines on how to contribute to Grizabella.

## License

Grizabella is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
