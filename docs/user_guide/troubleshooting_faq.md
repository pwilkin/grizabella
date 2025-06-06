# Troubleshooting & FAQ

This section provides solutions to common problems and answers to frequently asked questions about Grizabella.

## Troubleshooting

### Installation Issues

*   **Common problems with `poetry install`:**
    *   Ensure you have Poetry installed correctly. Refer to the official Poetry documentation.
    *   Make sure your `pyproject.toml` file is not corrupted and all dependencies are resolvable.
    *   Try running `poetry lock --no-update` and then `poetry install` if you suspect a lock file issue.
    *   Check for network connectivity issues if packages fail to download.

*   **Missing Arrow C++ libraries for `lancedb`:**
    *   Grizabella uses `lancedb`, which in turn requires Apache Arrow C++ libraries.
    *   On Debian/Ubuntu, install them using: `sudo apt-get install -y libarrow-dev`
    *   On other systems, refer to the Apache Arrow installation guide for installing the C++ libraries.
    *   Alternatively, you might be able to install a pre-built `pyarrow` wheel that includes these, but system-wide installation is often more reliable for `lancedb`.

*   **Python version incompatibilities:**
    *   Grizabella is developed and tested with Python 3.9+. Using older versions might lead to unexpected errors.
    *   Ensure your Poetry environment is configured to use a compatible Python version. You can specify this in your `pyproject.toml` or when creating the environment with `poetry env use <python_version>`.

### Connection Issues (UI/API)

*   **"Cannot connect to database" / Default database not found:**
    *   **Check Path:** Verify that the database path specified (or the default path `~/.grizabella/default_db`) exists and is accessible.
    *   **Permissions:** Ensure Grizabella has read/write permissions for the database directory and its files.
    *   **Default Database:** If you haven't specified a custom path, Grizabella looks for a database at `~/.grizabella/default_db`. If this is your first time running Grizabella or if this directory was removed, it might not exist. The application should create it on first valid schema definition, but if you encounter issues, ensure the parent directory `~/.grizabella` is writable.

### Schema Definition Errors

*   **Common mistakes when defining `ObjectTypeDefinition`, `EmbeddingDefinition`, `RelationTypeDefinition`:**
    *   **Referencing non-existent types:** Ensure that any `ObjectType` referenced in a `RelationTypeDefinition` (as `from_type` or `to_type`) or in an `EmbeddingDefinition` (as `object_type_name`) has already been defined.
    *   **Incorrect property types:** Property types in `ObjectTypeDefinition` must be valid Python types (e.g., `str`, `int`, `float`, `bool`, `list`, `dict`) or Pydantic models.
    *   **Naming conventions:** While not strictly errors, adhere to consistent naming for clarity.
    *   **Embedding source fields:** Ensure the `source_fields` in an `EmbeddingDefinition` exist as properties in the corresponding `ObjectTypeDefinition`.

### Embedding Generation Failures

*   **SentenceTransformer model download issues:**
    *   **Network:** Check your internet connection. SentenceTransformer models are downloaded from Hugging Face Hub.
    *   **Model name typo:** Verify the model identifier (e.g., `all-MiniLM-L6-v2`) is correct. A typo will prevent the model from being found.
    *   **Firewall/Proxy:** If you are behind a corporate firewall or proxy, ensure it allows connections to Hugging Face.

*   **Dimension mismatches:**
    *   If you are using pre-computed embeddings or a custom model, ensure the embedding dimensions match what `lancedb` expects or what your downstream tasks require. The default models have specific output dimensions.

### Query Issues

*   **Complex query JSON parsing errors (UI input):**
    *   If inputting complex queries directly as JSON in the UI (if such a feature is available), ensure the JSON is well-formed. Validate it with a JSON linter.
    *   Pay attention to quotes, commas, and brackets.

*   **No results returned:**
    *   **Check filters:** Ensure your query filters are not too restrictive or unintentionally excluding all data.
    *   **Data existence:** Verify that data matching your query criteria actually exists in the database.
    *   **Embedding similarity:** If performing a vector search, the query vector might not be similar enough to any stored embeddings. Try broadening the search or using a more general query.
    *   **Case sensitivity:** Some text-based filters might be case-sensitive by default.

## FAQ (Frequently Asked Questions)

*   **Q: How do I specify a custom database location?**
    *   A: You can set the `GRIZABELLA_DB_PATH` environment variable to your desired directory path before launching Grizabella. Alternatively, some Grizabella components or the API client might allow specifying the path programmatically.

*   **Q: What embedding models are supported?**
    *   A: By default, Grizabella is configured to use a model like `Colbert` (or a similar high-quality SentenceTransformer model). However, you can specify any SentenceTransformer model identifier from the Hugging Face Hub when defining an `EmbeddingDefinition`. Grizabella will then attempt to download and use that model.

*   **Q: Can I have multiple embedding definitions for the same object type?**
    *   A: Yes. You can define multiple `EmbeddingDefinition`s for a single `ObjectType`. Each definition can use different source fields and/or a different embedding model, allowing for diverse semantic representations of your objects.

*   **Q: How is data consistency maintained across the three layers (SQLite, LanceDB, Kùzu)?**
    *   A: The Grizabella API and its core `DBManager` orchestrate operations across the different database layers. When an object is created, updated, or deleted, `DBManager` ensures that corresponding changes are made in the structured data store (SQLite), the vector store (LanceDB for embeddings), and the graph store (Kùzu for relations) as needed, based on your schema definitions.

*   **Q: Where can I report bugs or ask for help?**
    *   A: Please report bugs, suggest features, or ask for help by creating an issue on our GitHub repository: [`https://github.com/example/grizabella/issues`](https://github.com/example/grizabella/issues) (Note: This is a placeholder URL).