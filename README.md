# Grizabella

A tri-layer memory framework for LLM solutions.

[![Docs](https://img.shields.io/badge/docs-passing-brightgreen)](https://pwilkin.github.io/grizabella/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

Grizabella is a sophisticated memory layer designed for Large Language Model (LLM) solutions. It provides a unified interface to manage and query data across relational, vector, and graph databases, enabling complex memory and knowledge retrieval for AI applications.

## Key Features

* **Tri-layer Storage:** Integrates SQLite (relational), LanceDB (vector), and Kuzu (graph) for comprehensive data management.
* **Unified Python API:** Offers a simple and consistent Python interface to interact with all three database layers.
* **Complex Query Engine:** Allows for sophisticated queries that can span across the different data storage paradigms.
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

# Further operations (querying, adding relations, etc.) would go here.
```

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` (to be added) for guidelines on how to contribute to Grizabella.

## License

Grizabella is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
