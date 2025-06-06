# Grizabella Example Scripts

This directory contains example Python scripts demonstrating various functionalities of the Grizabella library. These scripts are intended to help users understand how to define schemas, manage data, and perform queries using the Grizabella API.

## Prerequisites

Before running these examples, ensure you have:

1. **Grizabella Installed**: The Grizabella library must be installed in your Python environment. If you are working from the project root, you can typically install it (and dependencies for examples) using Poetry:

    ```bash
    poetry install
    ```

2. **Python Environment Activated**: If you are using a virtual environment (recommended), make sure it's activated.

## Running the Examples

You can run each example script from the root directory of the Grizabella project using `poetry run python` or directly with `python` if Grizabella is in your system's Python path.

### 1. `basic_usage.py`

* **Description**: This script demonstrates the fundamental operations in Grizabella:
  * Connecting to a Grizabella database instance (a temporary one is created for the example).
  * Defining `ObjectTypeDefinition`s (e.g., "Author", "Book") with various `PropertyDefinition`s.
  * Defining a `RelationTypeDefinition` (e.g., "WRITTEN_BY") to link "Book" and "Author" objects.
  * Creating `ObjectInstance`s for authors and books.
  * Creating `RelationInstance`s to connect books to their authors.
  * Performing simple queries using `client.find_objects()` to retrieve all books and books by a specific author (by querying relations and then fetching related objects).
  * Illustrates the use of the `Grizabella` client as a context manager.

* **How to Run**:

    ```bash
    poetry run python examples/basic_usage.py
    ```

    Alternatively, from the `examples/` directory:

    ```bash
    poetry run python basic_usage.py
    ```

### 2. `embedding_search_example.py`

* **Description**: This script showcases Grizabella's embedding capabilities:
  * Defining an `ObjectTypeDefinition` (e.g., "Article") with a text property (e.g., "abstract") intended for embedding.
  * Defining an `EmbeddingDefinition` that specifies which property of the "Article" object type should be embedded (Grizabella uses a default Sentence Transformer model if not specified otherwise).
  * Upserting several "Article" `ObjectInstance`s with sample abstracts. Embeddings are generated automatically upon insertion if an `EmbeddingDefinition` is configured.
  * Performing a semantic similarity search using `client._db_manager.find_similar_objects_by_embedding()` with a query text against the "abstract" embeddings.
  * Printing the similar articles found, including their similarity scores.
  * Demonstrates retrieving full object data versus raw results (IDs and scores).

* **How to Run**:

    ```bash
    poetry run python examples/embedding_search_example.py
    ```

    Alternatively, from the `examples/` directory:

    ```bash
    poetry run python embedding_search_example.py
    ```

* **Note**: This example relies on Grizabella's default embedding model (likely a local Sentence Transformer). Ensure any dependencies for this model are met.

### 3. `complex_query_example.py`

* **Description**: This script demonstrates the construction and execution of more sophisticated queries using Grizabella's `ComplexQuery` capabilities:
  * Setting up a schema with two `ObjectTypeDefinition`s ("Researcher", "Paper"), an `EmbeddingDefinition` on "Paper.summary", and a `RelationTypeDefinition` ("AUTHORED") linking researchers to papers.
  * Populating the database with a small dataset of researchers, papers, and their authorship relations.
  * Constructing a `ComplexQuery` object. The example query aims to find researchers in a specific field of study who have authored papers semantically similar to a given topic. This involves:
    * A `QueryComponent` with a `RelationalFilter` on the "Researcher" object type.
    * Another `QueryComponent` with an `EmbeddingSearchClause` on the "Paper" object type.
    * The Grizabella Query Engine is expected to process these components and their implicit relationships (e.g., via the "AUTHORED" relation) to produce the final set of results.
  * Executing the query using `client.execute_complex_query()`.
  * Printing the `ObjectInstance`s from the `QueryResult`.
  * Includes comments explaining the logic and assumptions about how the complex query is processed.

* **How to Run**:

    ```bash
    poetry run python examples/complex_query_example.py
    ```

    Alternatively, from the `examples/` directory:

    ```bash
    poetry run python complex_query_example.py
    ```

* **Note**: The `ComplexQuery` functionality and how multiple `QueryComponent`s are combined is dependent on the Grizabella Query Engine's implementation. This example illustrates one way to structure such a query based on the defined models. The placeholder vector in the embedding search clause should be replaced with a real query vector in practical applications.

---

These examples should provide a good starting point for learning how to use Grizabella. Refer to the Grizabella documentation for more detailed API information and advanced features.
