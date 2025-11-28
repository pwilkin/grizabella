# Plan to Update Architectural Documents

This plan outlines the steps to review and update Grizabella's architectural documentation to align with the current stable state of the codebase.

## 1. Foundational Design (`docs/foundational_design.md`)

- **Grizabella Client:**
  - The `Grizabella` client acts as the primary public API.
  - It initializes the `GrizabellaDBManager` and manages the connection lifecycle.
  - The `add_relation()` method in the client calls `add_relation_instance` on the `GrizabellaDBManager`.

- **GrizabellaDBManager:**
  - The `GrizabellaDBManager` coordinates the different database adapters: `SQLiteAdapter`, `LanceDBAdapter`, and `LadybugDBAdapter`.
  - It delegates schema and instance management to the `_SchemaManager` and `_InstanceManager` helpers.
  - The `add_relation_instance()` method is delegated to the `_InstanceManager`.

- **_InstanceManager:**
  - The `_InstanceManager`'s `add_relation_instance()` method is the core of the relation creation logic.
  - It first ensures the source and target object instances exist in LadybugDB by calling `upsert_object_instance()` on the `LadybugDBAdapter`. This is a key change to be documented.
  - It then calls `upsert_relation_instance()` on the `LadybugDBAdapter` to create the relation itself.

- **LadybugDBAdapter:**
  - The `upsert_relation_instance()` method in the `LadybugDBAdapter` uses a `MERGE` Cypher query to create or update the relation. This ensures idempotency.

- **Diagram:**

    ```mermaid
    sequenceDiagram
        participant Client as Grizabella Client
        participant DBManager as GrizabellaDBManager
        participant InstManager as _InstanceManager
        participant LadybugDB as LadybugDBAdapter

        Client->>DBManager: add_relation(relation)
        DBManager->>InstManager: add_relation_instance(relation)
        InstManager->>LadybugDB: upsert_object_instance(source_node)
        LadybugDB-->>InstManager: Source Node Upserted
        InstManager->>LadybugDB: upsert_object_instance(target_node)
        LadybugDB-->>InstManager: Target Node Upserted
        InstManager->>LadybugDB: upsert_relation_instance(relation)
        LadybugDB-->>InstManager: Relation Upserted
        InstManager-->>DBManager: RelationInstance
        DBManager-->>Client: RelationInstance
    end
    ```

## 2. Complex Query Engine Design (`docs/complex_query_engine_design.md`)

- **Query Planning (`QueryPlanner`):**
  - The `QueryPlanner` receives a `ComplexQuery` and validates its structure and schema references.
  - It iterates through each `QueryComponent`, creating a `PlannedComponentExecution` which contains an ordered list of `PlannedStep` objects.
  - The steps are ordered logically: relational filters (`sqlite_filter`), then embedding searches (`lancedb_search`), and finally graph traversals (`ladybugdb_traversal`).
  - Each step is designed to potentially chain its output (a list of object IDs) as input to the next, allowing for progressive filtering.
  - The final output is a `PlannedQuery` object, which is a complete, validated, and step-by-step execution plan.

- **Query Execution (`QueryExecutor`):**
  - The `QueryExecutor` processes the `PlannedQuery`.
  - It executes each `PlannedComponentExecution` sequentially. Within each component, it executes the `PlannedStep`s in their defined order.
  - The execution flow is as follows:
        1. **Initial Set:** The process starts with an initial set of object IDs, either from a `sqlite_filter` or by fetching all IDs for the component's object type if no filter is present.
        2. **Filtering:** The set of IDs is progressively filtered by each subsequent step (`lancedb_search`, `ladybugdb_traversal`). If any step returns an empty set of IDs, the execution for that component halts.
        3. **Aggregation:** The final ID sets from each `PlannedComponentExecution` are aggregated using an intersection, yielding a final set of object IDs that satisfy all query components.
  - The executor then fetches the full `ObjectInstance` data for the final aggregated IDs.

- **Diagram:**

    ```mermaid
    graph TD
        subgraph Query Planning
            A[ComplexQuery] --> B{QueryPlanner};
            B --> C[PlannedQuery];
        end

        subgraph Query Execution
            C --> D{QueryExecutor};
            D --> E{Execute Component 1};
            E --> F{Execute Component 2};
            F --> G{...};
            G --> H{Aggregate Results};
            H --> I[Fetch Final Objects];
            I --> J[QueryResult];
        end

        subgraph Component Execution
            direction LR
            S1[Initial IDs] --> S2{SQLite Filter};
            S2 --> S3{LanceDB Search};
            S3 --> S4{LadybugDB Traversal};
            S4 --> S5[Final Component IDs];
        end
    end
    ```

## 3. UI Design (`docs/ui_design_v0.1.md`)

- **UI Threading Model:**
  - All Grizabella client calls are centralized in the main UI thread to ensure thread safety with the underlying database connections.
  - Worker threads (`ApiClientThread`) are spawned for each asynchronous operation initiated by a UI view.
  - The `ApiClientThread`'s `run` method emits an `apiRequestReady` signal, passing the operation name and its arguments.
  - The `MainWindow`'s `handleApiRequest()` slot, running in the main thread, receives this signal.
  - The slot executes the requested method on the main `grizabella_client` instance.
  - Upon completion, the `MainWindow` calls the worker thread's `handleApiResponse()` slot, passing the result or error.
  - The worker thread then emits a `result_ready` or `error_occurred` signal, which is connected to the original UI view to update its state.

- **Diagram:**

    ```mermaid
    sequenceDiagram
        participant View as UI View
        participant Worker as ApiClientThread
        participant Main as MainWindow (Main Thread)
        participant Client as Grizabella Client

        View->>Worker: Start API Call
        Worker->>Main: apiRequestReady(op, args, kwargs)
        Main->>Client: execute_operation(*args, **kwargs)
        Client-->>Main: result
        Main->>Worker: handleApiResponse(success, result)
        Worker->>View: result_ready(result) or error_occurred(error)
    end
