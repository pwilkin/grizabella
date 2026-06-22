# Troubleshooting & FAQ

This section provides solutions to common problems and answers to frequently asked questions about Grizabella.

## Troubleshooting

### Installation Issues

* **Common problems with `poetry install`:**
  * Ensure you have Poetry installed correctly. Refer to the official Poetry documentation.
  * Make sure your `pyproject.toml` file is not corrupted and all dependencies are resolvable.
  * Try running `poetry lock --no-update` and then `poetry install` if you suspect a lock file issue.
  * Check for network connectivity issues if packages fail to download.

* **Missing Arrow C++ libraries for `lancedb`:**
  * Grizabella uses `lancedb`, which in turn requires Apache Arrow C++ libraries.
  * On Debian/Ubuntu, install them using: `sudo apt-get install -y libarrow-dev`
  * On other systems, refer to the Apache Arrow installation guide for installing the C++ libraries.
  * Alternatively, you might be able to install a pre-built `pyarrow` wheel that includes these, but system-wide installation is often more reliable for `lancedb`.

* **Python version incompatibilities:**
  * Grizabella requires **Python >=3.12 and <3.14**. Older 3.x versions (including 3.11) are not supported.
  * Ensure your Poetry environment is configured to use a compatible Python version. You can specify this in your `pyproject.toml` or when creating the environment with `poetry env use <python_version>`.

### Connection Issues (UI/API)

* **"Cannot connect to database" / Default database not found:**
  * **Check Path:** Verify that the database path specified (or the default path `~/.grizabella/db_instances/default_db`) exists and is accessible.
  * **Permissions:** Ensure Grizabella has read/write permissions for the database directory and its files.
  * **Default Database:** If you haven't specified a custom path, Grizabella looks for a database under `~/.grizabella/db_instances/default_db`. It is created automatically by `Grizabella(create_if_not_exists=True)` (the default) — just make sure the parent directory `~/.grizabella` is writable.

### Schema Definition Errors

* **Common mistakes when defining `ObjectTypeDefinition`, `EmbeddingDefinition`, `RelationTypeDefinition`:**
  * **Referencing non-existent types:** Ensure that any `ObjectType` referenced in a `RelationTypeDefinition` (in `source_object_type_names` / `target_object_type_names`) or in an `EmbeddingDefinition` (as `object_type_name`) has already been defined.
  * **Incorrect property data types:** `PropertyDefinition.data_type` must be a `PropertyDataType` enum value (`TEXT`, `INTEGER`, `FLOAT`, `BOOLEAN`, `DATETIME`, `BLOB`, `JSON`, `UUID`). Bare Python types (`str`, `int`, etc.) and Pydantic models are not accepted.
  * **Naming conventions:** While not strictly errors, adhere to consistent naming for clarity — PascalCase for object types, UPPER_SNAKE_CASE for relation types, snake_case for embedding definitions.
  * **Embedding source property:** `EmbeddingDefinition.source_property_name` (singular) must name a property that exists on the referenced `ObjectTypeDefinition` and should be of type `TEXT`.
  * **Reranker model:** `EmbeddingDefinition.reranker_model` is optional — when set, semantic searches can post-process top-K results with a cross-encoder. If you misspell the model identifier, the reranker fails to load and the server logs a warning and falls back to plain vector ranking.

### Embedding Generation Failures

* **SentenceTransformer model download issues:**
  * **Network:** Check your internet connection. SentenceTransformer models are downloaded from Hugging Face Hub.
  * **Model name typo:** Verify the model identifier (e.g., `all-MiniLM-L6-v2`) is correct. A typo will prevent the model from being found.
  * **Firewall/Proxy:** If you are behind a corporate firewall or proxy, ensure it allows connections to Hugging Face.

* **Dimension mismatches:**
  * If you are using pre-computed embeddings or a custom model, ensure the embedding dimensions match what `lancedb` expects or what your downstream tasks require. The default models have specific output dimensions.

### Query Issues

* **Complex query JSON parsing errors (UI input):**
  * If inputting complex queries directly as JSON in the UI (if such a feature is available), ensure the JSON is well-formed. Validate it with a JSON linter.
  * Pay attention to quotes, commas, and brackets.

* **No results returned:**
  * **Check filters:** Ensure your query filters are not too restrictive or unintentionally excluding all data.
  * **Data existence:** Verify that data matching your query criteria actually exists in the database.
  * **Embedding similarity:** If performing a vector search, the query vector might not be similar enough to any stored embeddings. Try broadening the search or using a more general query.
  * **Case sensitivity:** Some text-based filters might be case-sensitive by default.

## FAQ (Frequently Asked Questions)

* **Q: How do I specify a custom database location?**
  * A: Pass `db_name_or_path=` when constructing `Grizabella`, or launch the MCP server with `--db-path /path/to/db`. The `GRIZABELLA_DB_PATH` environment variable is honored only by the MCP server. Bare names resolve to `~/.grizabella/db_instances/<name>`; absolute paths are used as-is.

* **Q: What embedding models are supported?**
  * A: Any model available through the LanceDB embedding registry — primarily Hugging Face sentence-transformers and ONNX models. The default `EmbeddingDefinition.embedding_model` is `huggingface/mixedbread-ai/mxbai-embed-large-v1`. Prefix the identifier with a provider name (e.g. `huggingface/...`) to force a specific registry provider; plain identifiers default to `huggingface`.

* **Q: What reranker models are supported?**
  * A: Any cross-encoder loadable by `sentence-transformers.CrossEncoder`. Common choices: `cross-encoder/ms-marco-MiniLM-L-6-v2` (fast, MS MARCO trained), `BAAI/bge-reranker-v2-m3` (multilingual, higher quality), `mixedbread-ai/mxbai-rerank-base-v1`. Set `reranker_model` on the `EmbeddingDefinition` to enable it by default for semantic searches, or pass `rerank_model=` per call. Reranking needs `query_text` — it cannot work from a pre-computed vector alone because cross-encoders score text pairs.

* **Q: Can I have multiple embedding definitions for the same object type?**
  * A: Yes. You can define multiple `EmbeddingDefinition`s for a single `ObjectType`. Each definition can use a different source property and/or a different embedding model, allowing for diverse semantic representations of your objects.

* **Q: How is data consistency maintained across the three layers (SQLite, LanceDB, LadybugDB)?**
  * A: The Grizabella API and its core `GrizabellaDBManager` orchestrate operations across the three layers. Object and relation metadata are persisted to SQLite (the authoritative store), vector embeddings to LanceDB, and graph edges to LadybugDB (the successor to Kuzu — still imported internally under the `kuzu` alias). When an object is upserted, updated, or deleted, the manager writes to each layer as needed based on the schema.

* **Q: Where can I report bugs or ask for help?**
  * A: Please open an issue on the GitHub repository: <https://github.com/pwilkin/grizabella/issues>.


## Connection Management Best Practices

### Resource Management

* **Always use context managers or proper cleanup:**
  * When using the Python API, use the `with` statement or explicitly call cleanup methods to ensure resources are properly released:
    ```python
    from grizabella.api.client import Grizabella
    
    # Recommended approach using context manager
    with Grizabella(db_name_or_path="my_db") as client:
        # Perform operations
        client.create_object_type(...)
        # Resources automatically cleaned up when exiting the context
    ```
  * For long-running applications, ensure to call cleanup methods explicitly when shutting down.

* **Connection pooling:**
  * Grizabella implements connection pooling to efficiently manage database connections.
  * The connection pool automatically manages idle connections and cleans them up after a configurable timeout period.
  * Connection pools are shared across managers for the same database type and path.

* **Singleton pattern for DB managers:**
  * DB managers are implemented using a singleton pattern with reference counting.
  * Multiple requests for the same database path will return the same manager instance.
  * Managers are automatically cleaned up when all references are released.

### Memory Management

* **Preventing memory leaks:**
  * Always release DB managers when no longer needed by calling the appropriate cleanup methods.
  * The system implements automatic cleanup on process shutdown, but explicit cleanup is recommended.
 * Monitor memory usage during long-running operations to detect potential leaks early.

* **Resource monitoring:**
  * `grizabella.core.resource_monitor` tracks CPU, memory, open-connection, and thread-count metrics in a background thread. Metrics are emitted to the Grizabella logger (file output when running under the MCP server) — there is no built-in web dashboard.
  * Use those logs, along with the MCP server log files it drops in the working directory, to spot resource regressions.

### Threading and Concurrency

* **Thread-safe operations:**
  * Database adapters are designed to be thread-safe, with separate connections per thread for Kùzu adapter.
 * Avoid sharing connection objects across threads directly; use the provided connection management instead.

* **Concurrent access patterns:**
  * Multiple threads can safely access the same database through the connection pool.
  * The system handles concurrent access efficiently while maintaining data integrity.

### Connection Lifecycle

* **Proper initialization:**
  * Always initialize the client with appropriate configuration including timeouts and retry settings.
  * Use the factory pattern to create and manage DB managers properly.

* **Graceful shutdown:**
  * Implement proper shutdown handlers that clean up all resources.
 * The system includes signal handlers for SIGINT and SIGTERM to ensure graceful shutdown.
  * All connections and resources are automatically cleaned up during shutdown.

### Troubleshooting Connection Issues

* **Connection timeouts:**
  * If experiencing connection timeouts, increase the timeout values in the configuration.
  * Check if the database files are accessible and not locked by another process.

* **Too many open files:**
  * This error indicates that too many connections are being held open simultaneously.
  * Ensure that connections are being properly returned to the pool or closed after use.
  * Consider adjusting the maximum connection pool size if needed for your use case.

* **Database locking issues:**
  * SQLite databases can experience locking issues with high concurrent write operations.
  * Consider using appropriate transaction management and connection pooling to reduce lock contention.