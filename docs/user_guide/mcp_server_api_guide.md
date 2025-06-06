# Grizabella MCP Server API Guide

This guide provides detailed information about the Grizabella Model Context Protocol (MCP) server API. The MCP server exposes Grizabella's core functionalities as tools that can be accessed remotely.

## Launching the MCP Server

To launch the Grizabella MCP server, navigate to the root directory of the Grizabella project and run the following command:

```bash
poetry run grizabella-mcp
```

This command starts the MCP server, making its tools available for interaction. The server typically runs using `fastmcp`, which might be based on FastAPI/Starlette.

## Database Configuration

The Grizabella MCP server requires a database to store its data. The path to this database can be configured using the `GRIZABELLA_DB_PATH` environment variable.

-   **Environment Variable:** `GRIZABELLA_DB_PATH`
-   **Default Value:** If the environment variable is not set, the server will use `grizabella_mcp_db` (relative to where the server is run) as the database path.

**Example:**

To set a custom database path (e.g., `/opt/grizabella_data/my_db`):

```bash
export GRIZABELLA_DB_PATH="/opt/grizabella_data/my_db"
poetry run grizabella-mcp
```

If the specified database file or directory doesn't exist, Grizabella will attempt to create it.

## MCP Tools / Operations

The Grizabella MCP server exposes several tools, each corresponding to an operation on the Grizabella data store. These tools are defined in [`grizabella/mcp/server.py`](grizabella/mcp/server.py:1) and map to methods of the `Grizabella` API client.

Requests to these tools are typically JSON-RPC style, where the MCP client sends a JSON payload specifying the tool name and its arguments. Responses are also in JSON format.

### Error Handling

Errors are generally reported as a JSON response containing an error message. This might be a standard FastAPI/FastMCP error structure, often including a "detail" field or an "error" field. For Grizabella-specific errors, the message will typically be prefixed with "Grizabella API Error:".

---

### Schema Management

#### 1. `create_object_type`

*   **Description:** Creates a new object type definition (e.g., a table schema or a node type in a graph).
*   **Input Parameters (JSON):**
    *   `object_type_def` (object, required): The definition of the object type. This structure is based on the [`ObjectTypeDefinition`](grizabella/core/models.py:116) Pydantic model.
        *   `name` (string, required): Unique name for the object type (e.g., "Document", "Person"). Convention: PascalCase.
        *   `description` (string, optional): Optional description of the object type.
        *   `properties` (array, required): List of property definitions for this object type. Each property definition is an object:
            *   `name` (string, required): Name of the property (e.g., "title", "age").
            *   `data_type` (string, required): Data type of the property. Must be one of the values from [`PropertyDataType`](grizabella/core/models.py:10) (e.g., "TEXT", "INTEGER", "FLOAT", "BOOLEAN", "DATETIME", "BLOB", "JSON", "UUID").
            *   `is_primary_key` (boolean, optional, default: `false`): Is this property a primary key?
            *   `is_nullable` (boolean, optional, default: `true`): Can this property be null?
            *   `is_indexed` (boolean, optional, default: `false`): Should this property be indexed?
            *   `is_unique` (boolean, optional, default: `false`): Does this property require unique values?
            *   `description` (string, optional): Optional description of the property.
*   **Example Input (JSON):**
    ```json
    {
        "object_type_def": {
            "name": "Document",
            "description": "Represents a text document.",
            "properties": [
                {
                    "name": "title",
                    "data_type": "TEXT",
                    "is_indexed": true
                },
                {
                    "name": "content",
                    "data_type": "TEXT"
                },
                {
                    "name": "published_date",
                    "data_type": "DATETIME",
                    "is_nullable": true
                }
            ]
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns `null` or a success message upon successful creation.
*   **Example Output (JSON):**
    ```json
    null
    ```
    (Or potentially a success object depending on FastMCP's conventions for void returns)

#### 2. `get_object_type`

*   **Description:** Retrieves the definition of a specific object type.
*   **Input Parameters (JSON):**
    *   `type_name` (string, required): The name of the object type to retrieve.
*   **Example Input (JSON):**
    ```json
    {
        "type_name": "Document"
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns an [`ObjectTypeDefinition`](grizabella/core/models.py:116) object if found, or `null` if not found. The structure is the same as the `object_type_def` input for `create_object_type`.
*   **Example Output (JSON):**
    ```json
    {
        "name": "Document",
        "description": "Represents a text document.",
        "properties": [
            {
                "name": "title",
                "data_type": "TEXT",
                "is_primary_key": false,
                "is_nullable": true,
                "is_indexed": true,
                "is_unique": false,
                "description": null
            },
            {
                "name": "content",
                "data_type": "TEXT",
                "is_primary_key": false,
                "is_nullable": true,
                "is_indexed": false,
                "is_unique": false,
                "description": null
            },
            {
                "name": "published_date",
                "data_type": "DATETIME",
                "is_primary_key": false,
                "is_nullable": true,
                "is_indexed": false,
                "is_unique": false,
                "description": null
            }
        ]
    }
    ```

#### 3. `delete_object_type`

*   **Description:** Deletes an object type definition.
*   **Input Parameters (JSON):**
    *   `type_name` (string, required): The name of the object type to delete.
*   **Example Input (JSON):**
    ```json
    {
        "type_name": "Document"
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns `null` or a success message upon successful deletion.
*   **Example Output (JSON):**
    ```json
    null
    ```

#### 4. `create_relation_type`

*   **Description:** Creates a new relation type definition.
*   **Input Parameters (JSON):**
    *   `relation_type_def` (object, required): The definition of the relation type. This structure is based on the [`RelationTypeDefinition`](grizabella/core/models.py:235) Pydantic model.
        *   `name` (string, required): Unique name for the relation type (e.g., "HAS_AUTHOR"). Convention: UPPER_SNAKE_CASE.
        *   `description` (string, optional): Optional description of the relation type.
        *   `source_object_type_names` (array of strings, required): List of names of allowed source `ObjectTypeDefinition`s.
        *   `target_object_type_names` (array of strings, required): List of names of allowed target `ObjectTypeDefinition`s.
        *   `properties` (array, optional, default: `[]`): List of property definitions for the relation itself (edge properties). Structure is the same as for `ObjectTypeDefinition` properties.
*   **Example Input (JSON):**
    ```json
    {
        "relation_type_def": {
            "name": "AUTHORED_BY",
            "description": "Indicates authorship of a document by a person.",
            "source_object_type_names": ["Document"],
            "target_object_type_names": ["Person"],
            "properties": [
                {
                    "name": "role",
                    "data_type": "TEXT",
                    "is_nullable": true
                }
            ]
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns `null` or a success message.
*   **Example Output (JSON):**
    ```json
    null
    ```

#### 5. `get_relation_type`

*   **Description:** Retrieves the definition of a specific relation type.
*   **Input Parameters (JSON):**
    *   `type_name` (string, required): The name of the relation type to retrieve.
*   **Example Input (JSON):**
    ```json
    {
        "type_name": "AUTHORED_BY"
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns a [`RelationTypeDefinition`](grizabella/core/models.py:235) object if found, or `null` if not found. The structure is the same as the `relation_type_def` input for `create_relation_type`.
*   **Example Output (JSON):**
    ```json
    {
        "name": "AUTHORED_BY",
        "description": "Indicates authorship of a document by a person.",
        "source_object_type_names": ["Document"],
        "target_object_type_names": ["Person"],
        "properties": [
            {
                "name": "role",
                "data_type": "TEXT",
                "is_primary_key": false,
                "is_nullable": true,
                "is_indexed": false,
                "is_unique": false,
                "description": null
            }
        ]
    }
    ```

#### 6. `delete_relation_type`

*   **Description:** Deletes a relation type definition.
*   **Input Parameters (JSON):**
    *   `type_name` (string, required): The name of the relation type to delete.
*   **Example Input (JSON):**
    ```json
    {
        "type_name": "AUTHORED_BY"
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns `null` or a success message.
*   **Example Output (JSON):**
    ```json
    null
    ```

---

### Object Instance Management

#### 7. `upsert_object`

*   **Description:** Creates a new object instance or updates an existing one if an object with the same ID already exists.
*   **Input Parameters (JSON):**
    *   `obj` (object, required): The object instance to create or update. This structure is based on the [`ObjectInstance`](grizabella/core/models.py:285) Pydantic model.
        *   `id` (string, optional, UUID format): Unique identifier for the object. If not provided, a new UUID will be generated. If provided and an object with this ID exists, it will be updated.
        *   `weight` (number, optional, default: `1.0`): A decimal value (0-10) for ranking/relevance.
        *   `upsert_date` (string, optional, ISO 8601 datetime format): Timestamp of last update. Automatically set if not provided.
        *   `object_type_name` (string, required): Name of the `ObjectTypeDefinition` this instance conforms to.
        *   `properties` (object, required): Key-value pairs representing the actual data for the instance, where keys are property names.
*   **Example Input (JSON):**
    ```json
    {
        "obj": {
            "object_type_name": "Document",
            "properties": {
                "title": "My First Document",
                "content": "This is the content of my first document.",
                "published_date": "2024-01-15T10:00:00Z"
            }
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns the created or updated [`ObjectInstance`](grizabella/core/models.py:285) object, including its `id` and `upsert_date`.
*   **Example Output (JSON):**
    ```json
    {
        "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "weight": 1.0,
        "upsert_date": "2024-06-04T19:55:00.123456Z",
        "object_type_name": "Document",
        "properties": {
            "title": "My First Document",
            "content": "This is the content of my first document.",
            "published_date": "2024-01-15T10:00:00Z"
        }
    }
    ```

#### 8. `get_object_by_id`

*   **Description:** Retrieves a specific object instance by its ID and type name.
*   **Input Parameters (JSON):**
    *   `object_id` (string, required, UUID format): The ID of the object to retrieve.
    *   `type_name` (string, required): The name of the object type.
*   **Example Input (JSON):**
    ```json
    {
        "object_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "type_name": "Document"
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns the [`ObjectInstance`](grizabella/core/models.py:285) object if found, or `null` if not found.
*   **Example Output (JSON):** (Same structure as `upsert_object` output)

#### 9. `delete_object`

*   **Description:** Deletes an object instance by its ID and type name.
*   **Input Parameters (JSON):**
    *   `object_id` (string, required, UUID format): The ID of the object to delete.
    *   `type_name` (string, required): The name of the object type.
*   **Example Input (JSON):**
    ```json
    {
        "object_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "type_name": "Document"
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns `true` if deletion was successful, `false` otherwise (e.g., if the object was not found).
*   **Example Output (JSON):**
    ```json
    true
    ```

#### 10. `find_objects`

*   **Description:** Finds object instances of a given type, optionally matching filter criteria.
*   **Input Parameters (JSON):**
    *   `args` (object, required): Arguments for finding objects. Based on [`FindObjectsArgs`](grizabella/mcp/server.py:179).
        *   `type_name` (string, required): The name of the object type to search for.
        *   `filter_criteria` (object, optional): A dictionary of property names to values for exact matching.
        *   `limit` (integer, optional): Maximum number of objects to return.
*   **Example Input (JSON):**
    ```json
    {
        "args": {
            "type_name": "Document",
            "filter_criteria": {
                "author_id": "person_xyz"
            },
            "limit": 10
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns a list of [`ObjectInstance`](grizabella/core/models.py:285) objects that match the criteria.
*   **Example Output (JSON):**
    ```json
    [
        {
            "id": "doc1-uuid",
            "weight": 1.0,
            "upsert_date": "2024-06-04T20:10:00Z",
            "object_type_name": "Document",
            "properties": { "title": "Doc One", "author_id": "person_xyz" }
        },
        {
            "id": "doc2-uuid",
            "weight": 1.0,
            "upsert_date": "2024-06-04T20:11:00Z",
            "object_type_name": "Document",
            "properties": { "title": "Doc Two", "author_id": "person_xyz" }
        }
    ]
    ```

---

### Relation Instance Management

#### 11. `add_relation`

*   **Description:** Adds a new relation instance between two objects.
*   **Input Parameters (JSON):**
    *   `relation` (object, required): The relation instance to add. This structure is based on the [`RelationInstance`](grizabella/core/models.py:345) Pydantic model.
        *   `id` (string, optional, UUID format): Unique ID for the relation. Auto-generated if not provided.
        *   `weight` (number, optional, default: `1.0`): Relevance weight.
        *   `upsert_date` (string, optional, ISO 8601 datetime): Auto-set if not provided.
        *   `relation_type_name` (string, required): Name of the `RelationTypeDefinition`.
        *   `source_object_instance_id` (string, required, UUID format): ID of the source object.
        *   `target_object_instance_id` (string, required, UUID format): ID of the target object.
        *   `properties` (object, optional, default: `{}`): Key-value pairs for relation properties.
*   **Example Input (JSON):**
    ```json
    {
        "relation": {
            "relation_type_name": "AUTHORED_BY",
            "source_object_instance_id": "doc1-uuid",
            "target_object_instance_id": "person_xyz-uuid",
            "properties": {
                "role": "Primary Author"
            }
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns the created [`RelationInstance`](grizabella/core/models.py:345) object.
*   **Example Output (JSON):**
    ```json
    {
        "id": "rel1-uuid",
        "weight": 1.0,
        "upsert_date": "2024-06-04T20:15:00Z",
        "relation_type_name": "AUTHORED_BY",
        "source_object_instance_id": "doc1-uuid",
        "target_object_instance_id": "person_xyz-uuid",
        "properties": {
            "role": "Primary Author"
        }
    }
    ```

#### 12. `get_relation`

*   **Description:** Retrieves a specific relation instance between two objects of a given relation type.
*   **Input Parameters (JSON):**
    *   `from_object_id` (string, required, UUID format): ID of the source object.
    *   `to_object_id` (string, required, UUID format): ID of the target object.
    *   `relation_type_name` (string, required): Name of the relation type.
*   **Example Input (JSON):**
    ```json
    {
        "from_object_id": "doc1-uuid",
        "to_object_id": "person_xyz-uuid",
        "relation_type_name": "AUTHORED_BY"
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns the [`RelationInstance`](grizabella/core/models.py:345) object if found, or `null`.
*   **Example Output (JSON):** (Same structure as `add_relation` output)

#### 13. `delete_relation`

*   **Description:** Deletes a specific relation instance.
*   **Input Parameters (JSON):**
    *   `from_object_id` (string, required, UUID format): ID of the source object.
    *   `to_object_id` (string, required, UUID format): ID of the target object.
    *   `relation_type_name` (string, required): Name of the relation type.
*   **Example Input (JSON):**
    ```json
    {
        "from_object_id": "doc1-uuid",
        "to_object_id": "person_xyz-uuid",
        "relation_type_name": "AUTHORED_BY"
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns `true` if deletion was successful, `false` otherwise.
*   **Example Output (JSON):**
    ```json
    true
    ```

#### 14. `get_outgoing_relations`

*   **Description:** Retrieves all outgoing relation instances from a given object.
*   **Input Parameters (JSON):**
    *   `args` (object, required): Arguments for fetching relations. Based on [`GetRelationsArgs`](grizabella/mcp/server.py:249).
        *   `object_id` (string, required, UUID format): ID of the source object.
        *   `type_name` (string, required): Object type name of the source object.
        *   `relation_type_name` (string, optional): If provided, filters by this relation type.
*   **Example Input (JSON):**
    ```json
    {
        "args": {
            "object_id": "doc1-uuid",
            "type_name": "Document",
            "relation_type_name": "AUTHORED_BY"
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns a list of [`RelationInstance`](grizabella/core/models.py:345) objects.
*   **Example Output (JSON):**
    ```json
    [
        {
            "id": "rel1-uuid",
            "weight": 1.0,
            "upsert_date": "2024-06-04T20:15:00Z",
            "relation_type_name": "AUTHORED_BY",
            "source_object_instance_id": "doc1-uuid",
            "target_object_instance_id": "person_xyz-uuid",
            "properties": { "role": "Primary Author" }
        }
    ]
    ```

#### 15. `get_incoming_relations`

*   **Description:** Retrieves all incoming relation instances to a given object.
*   **Input Parameters (JSON):**
    *   `args` (object, required): Arguments for fetching relations. Based on [`GetRelationsArgs`](grizabella/mcp/server.py:249).
        *   `object_id` (string, required, UUID format): ID of the target object.
        *   `type_name` (string, required): Object type name of the target object.
        *   `relation_type_name` (string, optional): If provided, filters by this relation type.
*   **Example Input (JSON):**
    ```json
    {
        "args": {
            "object_id": "person_xyz-uuid",
            "type_name": "Person",
            "relation_type_name": "AUTHORED_BY"
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns a list of [`RelationInstance`](grizabella/core/models.py:345) objects.
*   **Example Output (JSON):** (Same structure as `get_outgoing_relations` output)

---

### Querying

#### 16. `search_similar_objects`

*   **Description:** Searches for objects similar to a given object, typically using embeddings. (Note: The Grizabella API for this might involve providing an embedding vector directly or specifying an object whose embedding should be used. The MCP layer currently expects object ID and type name.)
*   **Input Parameters (JSON):**
    *   `args` (object, required): Arguments for similarity search. Based on [`SearchSimilarObjectsArgs`](grizabella/mcp/server.py:291).
        *   `object_id` (string, required, UUID format): ID of the object to find similar items for.
        *   `type_name` (string, required): Object type name of the object.
        *   `n_results` (integer, optional, default: `5`): Number of similar results to return.
        *   `search_properties` (array of strings, optional): List of property names to consider for similarity (if applicable to the underlying embedding strategy).
*   **Example Input (JSON):**
    ```json
    {
        "args": {
            "object_id": "doc1-uuid",
            "type_name": "Document",
            "n_results": 3
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns a list of tuples, where each tuple contains an [`ObjectInstance`](grizabella/core/models.py:285) and a float representing the similarity score.
    *   The JSON structure will be an array of arrays/objects, e.g., `[[ObjectInstance, score], [ObjectInstance, score]]`.
*   **Example Output (JSON):**
    ```json
    [
        [
            {
                "id": "doc_similar1_uuid",
                "weight": 1.0,
                "upsert_date": "2024-06-01T10:00:00Z",
                "object_type_name": "Document",
                "properties": { "title": "A Very Similar Document" }
            },
            0.95
        ],
        [
            {
                "id": "doc_similar2_uuid",
                "weight": 1.0,
                "upsert_date": "2024-05-20T14:30:00Z",
                "object_type_name": "Document",
                "properties": { "title": "Another Related Article" }
            },
            0.88
        ]
    ]
    ```

#### 17. `execute_complex_query`

*   **Description:** Executes a complex query that can span multiple database layers (relational, graph, vector) and object types.
*   **Input Parameters (JSON):**
    *   `query` (object, required): The complex query definition. This structure is based on the [`ComplexQuery`](grizabella/core/query_models.py:205) Pydantic model.
        *   `description` (string, optional): Optional description for the query.
        *   `components` (array, required): List of `QueryComponent` objects.
            *   Each `QueryComponent` ([`QueryComponent`](grizabella/core/query_models.py:162)) has:
                *   `object_type_name` (string, required): Primary object type for this component.
                *   `relational_filters` (array, optional): List of `RelationalFilter` objects.
                    *   Each `RelationalFilter` ([`RelationalFilter`](grizabella/core/query_models.py:13)) has:
                        *   `property_name` (string, required)
                        *   `operator` (string, required, e.g., "==", "!=", "LIKE", "IN")
                        *   `value` (any, required)
                *   `embedding_searches` (array, optional): List of `EmbeddingSearchClause` objects.
                    *   Each `EmbeddingSearchClause` ([`EmbeddingSearchClause`](grizabella/core/query_models.py:47)) has:
                        *   `embedding_definition_name` (string, required)
                        *   `similar_to_payload` (array of floats, required): The query vector.
                        *   `threshold` (float, optional)
                        *   `limit` (integer, optional, default: 10)
                *   `graph_traversals` (array, optional): List of `GraphTraversalClause` objects.
                    *   Each `GraphTraversalClause` ([`GraphTraversalClause`](grizabella/core/query_models.py:109)) has:
                        *   `relation_type_name` (string, required)
                        *   `direction` (string, optional, "outgoing" or "incoming", default: "outgoing")
                        *   `target_object_type_name` (string, required)
                        *   `target_object_id` (string, optional, UUID format)
                        *   `target_object_properties` (array, optional): List of `RelationalFilter` objects for the target.
*   **Example Input (JSON):**
    ```json
    {
        "query": {
            "description": "Find recent documents by 'John Doe' that mention 'AI research'.",
            "components": [
                {
                    "object_type_name": "Person",
                    "relational_filters": [
                        {
                            "property_name": "name",
                            "operator": "==",
                            "value": "John Doe"
                        }
                    ]
                },
                {
                    "object_type_name": "Document",
                    "relational_filters": [
                        {
                            "property_name": "published_date",
                            "operator": ">=",
                            "value": "2024-01-01T00:00:00Z"
                        }
                    ],
                    "embedding_searches": [
                        {
                            "embedding_definition_name": "document_content_embedding",
                            "similar_to_payload": [0.1, 0.2, ..., 0.9], // Example vector for "AI research"
                            "limit": 5
                        }
                    ],
                    "graph_traversals": [
                        {
                            "relation_type_name": "AUTHORED_BY",
                            "direction": "incoming", // Document is target, Person is source
                            "target_object_type_name": "Person"
                            // Link to the "Person" component implicitly by the query engine logic
                        }
                    ]
                }
            ]
        }
    }
    ```
*   **Output Parameters (JSON):**
    *   Returns a [`QueryResult`](grizabella/core/query_models.py:246) object.
        *   `object_instances` (array): List of [`ObjectInstance`](grizabella/core/models.py:285) objects that match the query.
        *   `errors` (array of strings, optional): List of errors encountered, if any.
*   **Example Output (JSON):**
    ```json
    {
        "object_instances": [
            {
                "id": "doc_ai_1_uuid",
                "weight": 1.0,
                "upsert_date": "2024-03-10T12:00:00Z",
                "object_type_name": "Document",
                "properties": {
                    "title": "Advancements in AI Research",
                    "content": "...",
                    "published_date": "2024-03-10T12:00:00Z"
                }
            }
        ],
        "errors": null
    }
    ```

---

## Example `curl` Requests

Here are a few examples of how to interact with the MCP server using `curl`. Assume the server is running on `http://localhost:8000` (the default for FastAPI/Uvicorn, adjust if your FastMCP setup uses a different port). The MCP protocol usually involves a POST request with a JSON body.

**1. Create an Object Type**

```bash
curl -X POST http://localhost:8000/mcp \
-H "Content-Type: application/json" \
-d '{
    "jsonrpc": "2.0",
    "method": "create_object_type",
    "params": {
        "object_type_def": {
            "name": "Person",
            "properties": [
                {"name": "full_name", "data_type": "TEXT"},
                {"name": "email", "data_type": "TEXT", "is_unique": true}
            ]
        }
    },
    "id": 1
}'
```
*(Note: The exact JSON-RPC structure (`jsonrpc`, `method`, `params`, `id`) might vary slightly based on FastMCP's specific implementation. The `params` would contain the arguments for the tool, e.g., `{"object_type_def": {...}}` for `create_object_type`.)*

If FastMCP uses a simpler REST-like mapping where tool names are part of the URL, it might look different, e.g., `POST http://localhost:8000/create_object_type`. The examples above assume a common MCP/JSON-RPC pattern where the tool name is in the `method` field. For Grizabella's `FastMCP` usage, it's more likely that the parameters are directly passed as the JSON body for a POST request to a tool-specific endpoint (e.g. `POST /create_object_type` with the body being `{"object_type_def": {...}}`).

Let's assume a simpler POST to `/tool_name` with direct parameters:

**1. Create an Object Type (Simpler POST)**

```bash
curl -X POST http://localhost:8000/create_object_type \
-H "Content-Type: application/json" \
-d '{
    "object_type_def": {
        "name": "Person",
        "description": "A human being.",
        "properties": [
            {"name": "full_name", "data_type": "TEXT", "is_indexed": true},
            {"name": "email", "data_type": "TEXT", "is_unique": true, "is_nullable": true},
            {"name": "age", "data_type": "INTEGER", "is_nullable": true}
        ]
    }
}'
```

**2. Upsert an Object Instance**

```bash
curl -X POST http://localhost:8000/upsert_object \
-H "Content-Type: application/json" \
-d '{
    "obj": {
        "object_type_name": "Person",
        "properties": {
            "full_name": "Jane Doe",
            "email": "jane.doe@example.com",
            "age": 30
        }
    }
}'
```
Response:
```json
{
    "id": "generated-uuid-for-jane",
    "weight": 1.0,
    "upsert_date": "YYYY-MM-DDTHH:MM:SS.ffffffZ",
    "object_type_name": "Person",
    "properties": {
        "full_name": "Jane Doe",
        "email": "jane.doe@example.com",
        "age": 30
    }
}
```

**3. Get an Object by ID**

```bash
curl -X POST http://localhost:8000/get_object_by_id \
-H "Content-Type: application/json" \
-d '{
    "object_id": "generated-uuid-for-jane",
    "type_name": "Person"
}'
```

**4. Execute a Complex Query** (Payload can be large)

```bash
curl -X POST http://localhost:8000/execute_complex_query \
-H "Content-Type: application/json" \
-d '{
    "query": {
        "description": "Find Person named Jane Doe",
        "components": [
            {
                "object_type_name": "Person",
                "relational_filters": [
                    {
                        "property_name": "full_name",
                        "operator": "==",
                        "value": "Jane Doe"
                    }
                ]
            }
        ]
    }
}'
```

Please consult the FastMCP documentation or observe server logs for the exact request format if these examples don't work directly. The key is that the JSON payload in the request body should match the input parameters defined for each tool.