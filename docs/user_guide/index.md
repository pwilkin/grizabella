# Introduction to Grizabella

Welcome to Grizabella, a powerful tri-layer memory framework designed to enhance Large Language Model (LLM) solutions by providing robust, multi-faceted data storage and retrieval capabilities.

## What is Grizabella?

Grizabella is engineered to serve as a comprehensive memory backbone for applications leveraging LLMs. It allows developers to seamlessly integrate structured, unstructured, and graph-based data, enabling LLMs to access and utilize a rich, context-aware knowledge base. This facilitates more intelligent, accurate, and personalized interactions.

## Key Features

Grizabella offers a suite of features to empower your LLM applications:

* **Versatile Data Storage:**
  * **SQLite Integration:** For robust relational data storage, ideal for structured metadata and transactional information.
  * **LanceDB Integration:** For efficient vector storage and similarity search, crucial for semantic retrieval and embedding-based lookups.
  * **Kuzu Integration:** For powerful graph database capabilities, enabling the modeling and querying of complex relationships between data entities.
* **Unified Python API:** A consistent and intuitive Python library (`grizabella`) for interacting with all three database layers, simplifying development and data management.
* **PySide6 User Interface:** A standalone desktop application (`grizabella-ui`) providing a visual way to manage schemas, explore data, and interact with the Grizabella framework.
* **MCP Server:** A Model Context Protocol (MCP) server (`grizabella-mcp`) allowing other applications or agents to interact with Grizabella's data and functionalities through a standardized protocol.

## Architecture Overview

Grizabella's power stems from its unique tri-layer architecture:

1. **Relational Layer (SQLite):** Forms the foundation for structured data. It stores object metadata, schema definitions, and other relational information, ensuring data integrity and providing a solid base for other layers.
2. **Vector Layer (LanceDB):** Handles high-dimensional vector embeddings. This layer is optimized for fast similarity searches, enabling semantic understanding and retrieval of unstructured or semi-structured data.
3. **Graph Layer (Kuzu):** Manages complex relationships between data entities. This layer allows for sophisticated graph-based queries and analysis, uncovering insights from interconnected data.

These three layers work in concert, managed by a central `DBManager`, to provide a holistic and flexible memory solution.

This guide will walk you through installing Grizabella, getting started with its core functionalities, and leveraging its advanced features to build next-generation LLM-powered applications.
