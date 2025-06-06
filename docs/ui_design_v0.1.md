# Grizabella PySide6 UI - Initial Design Document

**Version:** 0.1
**Date:** 2025-06-04

## 1. Overall UI Structure & Main Views

The Grizabella UI will be a desktop application built using PySide6. It will feature a main window with a standard layout to provide a familiar user experience.

* **Main Window Layout:**
  * **Menu Bar:** Standard application menus (File, Edit, View, Tools, Help).
    * `File`: Connect to DB, Create New DB, Close DB, Settings, Exit.
    * `Edit`: (Context-dependent) Undo, Redo, Cut, Copy, Paste, Delete.
    * `View`: Toggle visibility of different panels/views, Zoom (for graph).
    * `Tools`: Schema Management, Query Builder, Data Import/Export (future).
    * `Help`: About, Documentation.
  * **Toolbar:** Quick access icons for common actions (e.g., Connect, New Object, New Relation, Run Query).
  * **Status Bar:** Display information about the current connection, ongoing operations, and selection details.
  * **Central Area:** A `QTabWidget` or a `QMainWindow` with `QDockWidget`s to host the main views. A tabbed interface is likely simpler for the initial version, with dockable widgets as a potential future enhancement for user customization.

* **Primary Views/Panels (as tabs or dockable widgets):**

    1. **Database Connection/Management View:**
        * **Purpose:** Allows users to connect to existing Grizabella database instances or create new ones.
        * **Components:**
            * List of recently used databases.
            * Fields to input database name/path.
            * Button to "Connect" or "Create & Connect".
            * Status indicator for connection.

    2. **Schema Explorer & Editor View:**
        * **Purpose:** Define, view, and manage `ObjectTypeDefinition`s, `EmbeddingDefinition`s, and `RelationTypeDefinition`s.
        * **Layout:** A `QTabWidget` with three sub-tabs: "Object Types", "Embedding Definitions", "Relation Types".
        * **"Object Types" Tab:**
            * Left: `QTreeView` or `QListView` displaying existing `ObjectTypeDefinition` names.
            * Right: A form area (potentially using `QFormLayout`) to display/edit the selected `ObjectTypeDefinition`'s details (name, description, properties).
            * Properties will be displayed in a `QTableView` within this form, allowing adding/editing/removing `PropertyDefinition`s.
        * **"Embedding Definitions" Tab:**
            * Left: `QTreeView` or `QListView` displaying existing `EmbeddingDefinition` names.
            * Right: A form area to display/edit selected `EmbeddingDefinition` details (name, object type, source property, model, dimensions, description).
        * **"Relation Types" Tab:**
            * Left: `QTreeView` or `QListView` displaying existing `RelationTypeDefinition` names.
            * Right: A form area to display/edit selected `RelationTypeDefinition` details (name, description, source/target object types, properties). Properties will be in a `QTableView`.

    3. **Data Explorer View:**
        * **Purpose:** View, add, edit, and delete `ObjectInstance`s and `RelationInstance`s.
        * **Layout:** A `QTabWidget` with two sub-tabs: "Objects" and "Relations".
        * **"Objects" Tab (Object Explorer/Editor):**
            * Top-Left: `QComboBox` to select an `ObjectTypeDefinition`.
            * Below ComboBox: `QTableView` to list `ObjectInstance`s of the selected type. Columns would include `id`, key properties, and `upsert_date`.
            * Right: A form (using `QFormLayout`) to display/edit the properties of the selected `ObjectInstance`.
            * Toolbar/Buttons: Add New Object, Delete Selected Object, Save Changes.
        * **"Relations" Tab (Relation Explorer/Editor):**
            * Top-Left: `QComboBox` to select a `RelationTypeDefinition`.
            * Below ComboBox: `QTableView` to list `RelationInstance`s of the selected type. Columns: `id`, `source_object_instance_id`, `target_object_instance_id`, key properties.
            * Right: A form to display/edit properties of the selected `RelationInstance`.
            * Toolbar/Buttons: Add New Relation (could open a dialog to select source/target objects), Delete Selected Relation, Save Changes.

    4. **Query Builder & Results View:**
        * **Purpose:** Construct and execute queries, and view their results.
        * **Layout:** Potentially a split view.
        * **Top/Left (Query Builder):**
            * `QTabWidget` for different query types:
                * **Simple Filter:** Select `ObjectTypeDefinition`, add `RelationalFilter`s via a simple UI.
                * **Similarity Search:** Select `ObjectTypeDefinition`, `EmbeddingDefinition`, input/select object for similarity, set N results.
                * **Complex Query:** A more advanced UI to build `ComplexQuery` objects, allowing definition of `QueryComponent`s with `relational_filters`, `embedding_searches`, and `graph_traversals`. This will be the most complex part to design. Initially, it might involve manually editing a JSON-like structure or a guided step-by-step builder.
            * Button: "Execute Query".
        * **Bottom/Right (Query Results):**
            * `QTableView` to display `QueryResult.object_instances`. Columns will be dynamic based on the objects returned.
            * A text area to display `QueryResult.errors`.

    5. **Graph Visualization View (Optional - Basic):**
        * **Purpose:** A simple visual representation of selected objects and their direct relationships.
        * **Components:** A custom widget (potentially using `QGraphicsView` or integrating a library like `Graphviz` or a Qt-specific graph library if available and simple).
        * **Interaction:** Selecting an object in the Object Explorer could highlight it here. Double-clicking an object could focus the graph on it.

## 2. Key UI Components & Widgets

* **Database Connection/Management View:**
  * `QListView` / `QComboBox` for recent DBs.
  * `QLineEdit` for DB path/name.
  * `QPushButton` for connect/create.
  * `QLabel` for status.

* **Schema Explorer & Editor View:**
  * `QTabWidget` for main categories.
  * `QTreeView` / `QListView` for listing schema definition names.
  * `QFormLayout` for displaying/editing definition details.
  * `QLineEdit` for names, descriptions, model IDs.
  * `QComboBox` for `PropertyDataType`, `ObjectTypeDefinition` selection (in `EmbeddingDefinition` and `RelationTypeDefinition`).
  * `QTableView` for `PropertyDefinition` lists within `ObjectTypeDefinition` and `RelationTypeDefinition`.
    * Custom `QAbstractTableModel` will be needed.
    * Delegates (`QItemDelegate`) for editing cells (e.g., `QComboBox` for `PropertyDataType`).
  * `QCheckBox` for boolean flags (e.g., `is_primary_key`, `is_nullable`).
  * `QSpinBox` / `QDoubleSpinBox` for numerical inputs (e.g., `dimensions`).
  * `QPushButton`s for "Add Property", "Remove Property", "Save Definition".

* **Data Explorer View:**
  * `QTabWidget` for Objects/Relations.
  * `QComboBox` to select `ObjectTypeDefinition` / `RelationTypeDefinition`.
  * `QTableView` to list instances.
    * Custom `QAbstractTableModel` for `ObjectInstance`s and `RelationInstance`s.
  * `QFormLayout` for editing instance properties.
    * Widgets will be dynamically generated based on `PropertyDefinition`s (e.g., `QLineEdit` for TEXT, `QSpinBox` for INTEGER, `QDateTimeEdit` for DATETIME).
  * `QPushButton`s for "Add", "Delete", "Save".
  * Dialogs (`QDialog`) for creating new relations (to pick source/target objects).

* **Query Builder & Results View:**
  * `QTabWidget` for query types.
  * `QFormLayout`, `QLineEdit`, `QComboBox`, `QSpinBox` for building simple and similarity queries.
  * For Complex Queries:
    * `QTreeView` or a custom widget to represent the `ComplexQuery` structure.
    * Dialogs or embedded forms to edit `QueryComponent`, `RelationalFilter`, `EmbeddingSearchClause`, `GraphTraversalClause`.
  * `QPushButton` ("Execute Query").
  * `QTableView` for results.
  * `QTextEdit` (read-only) for errors.

* **Graph Visualization View:**
  * `QGraphicsView` with `QGraphicsScene` for custom drawing if built from scratch.
  * Or a wrapper around an external library.

* **General:**
  * `QMainWindow`, `QMenuBar`, `QToolBar`, `QStatusBar`.
  * `QMessageBox` for confirmations and error messages.
  * `QProgressDialog` or progress indication in status bar for long operations.

## 3. Interaction Flow (High-Level)

* **User Defines a New Object Type:**
    1. Navigate to "Schema Explorer & Editor" -> "Object Types" tab.
    2. Click "Add New Object Type" button.
    3. A new entry appears in the list, and the right-hand form is enabled for a new `ObjectTypeDefinition`.
    4. User enters `name` (e.g., "Book") and `description`.
    5. User clicks "Add Property" in the properties `QTableView`.
    6. A new row appears in the table. User edits property `name` (e.g., "title"), `data_type` (e.g., `TEXT` via `QComboBox`), `is_nullable`, etc.
    7. User adds more properties (e.g., "author_name" - TEXT, "published_year" - INTEGER).
    8. User clicks "Save Object Type".
    9. UI calls `grizabella.create_object_type(object_type_def)`.
    10. Status bar/message box confirms success or shows error.

* **User Adds a New Object Instance:**
    1. Navigate to "Data Explorer" -> "Objects" tab.
    2. Select "Book" from the `ObjectTypeDefinition` `QComboBox`.
    3. Click "Add New Object" button.
    4. The right-hand form is populated with fields corresponding to "Book" properties ("title", "author_name", "published_year").
    5. User fills in the property values.
    6. User clicks "Save Object".
    7. UI constructs an `ObjectInstance` and calls `grizabella.upsert_object(obj_instance)`.
    8. The `QTableView` listing objects is refreshed.
    9. If `EmbeddingDefinition`s exist for "Book", the UI might indicate that embeddings are being generated in the background (see API Interaction).

* **User Creates a Relation Between Two Object Instances:**
    1. (Assume "Author" `ObjectTypeDefinition` and instances exist).
    2. (Assume "WROTE" `RelationTypeDefinition` exists, linking "Author" to "Book").
    3. Navigate to "Data Explorer" -> "Relations" tab.
    4. Select "WROTE" from the `RelationTypeDefinition` `QComboBox`.
    5. Click "Add New Relation".
    6. A dialog appears:
        * Prompts to select Source Object Type ("Author") and then an existing Author instance (e.g., via a searchable list/table).
        * Prompts to select Target Object Type ("Book") and then an existing Book instance.
        * Fields for any properties of the "WROTE" relation.
    7. User confirms selections and fills relation properties.
    8. UI constructs a `RelationInstance` and calls `grizabella.add_relation(relation_instance)`.
    9. The `QTableView` listing relations is refreshed.

* **User Performs a Complex Query:**
    1. Navigate to "Query Builder & Results" view.
    2. Select "Complex Query" tab.
    3. User interacts with the UI to define `QueryComponent`s:
        * Component 1: `object_type_name`: "Author", `relational_filters`: [`property_name`: "genre", `operator`: "==", `value`: "SciFi"].
        * Component 2 (linked via traversal from Component 1, though initial design is AND of components): `object_type_name`: "Book", `graph_traversals`: [`relation_type_name`: "WROTE", `direction`: "outgoing", `target_object_type_name`: "Book"].
    4. User clicks "Execute Query".
    5. UI constructs the `ComplexQuery` model.
    6. UI calls `grizabella.execute_complex_query(query)`.
    7. Results (`QueryResult.object_instances`) are displayed in the results `QTableView`. Errors in the error area.

## 4. Data Presentation

* **Schema Definitions (`ObjectTypeDefinition`, `EmbeddingDefinition`, `RelationTypeDefinition`):**
  * Names: `QListView` or `QTreeView`.
  * Details: `QFormLayout` with appropriate input widgets for each field.
  * `PropertyDefinition` lists: `QTableView`.

* **Instances (`ObjectInstance`, `RelationInstance`):**
  * Lists of instances: `QTableView`. Columns will show key identifiers and a few important properties.
  * Individual instance details: `QFormLayout`, with widgets dynamically generated based on the schema's `PropertyDefinition`s.

* **Query Results (`QueryResult.object_instances`):**
  * `QTableView`. Columns will be dynamically determined by the properties of the returned `ObjectInstance`s. For heterogeneous results, a common subset of properties or a more flexible view might be needed (advanced).

* **Properties (`PropertyDefinition`, instance properties):**
  * In tables: `QTableView` rows.
  * In forms: `QLabel` for name, appropriate input widget for value/type.

* **Enums (e.g., `PropertyDataType`):**
  * `QComboBox`.

## 5. API Interaction

* The UI will instantiate the `Grizabella` API client ([`grizabella/api/client.py`](grizabella/api/client.py:16)).
* **Connection Management:**
  * The `Database Connection/Management View` will use `Grizabella(db_name_or_path, create_if_not_exists)` to initialize and `grizabella.connect()` / `grizabella.close()`. The connection status will be tracked.
* **Data Fetching:**
  * Schema views will use `get_object_type()`, `get_relation_type()` (and similar for embeddings, assuming they are added to the API or managed via a convention).
  * Data Explorer will use `find_objects()` to populate tables, and `get_object_by_id()` / `get_relation()` when an item is selected for editing.
* **Data Modification:**
  * Schema Editor will use `create_object_type()`, `delete_object_type()`, etc.
  * Data Explorer will use `upsert_object()`, `delete_object()`, `add_relation()`, `delete_relation()`.
* **Querying:**
  * Query Builder will use `find_objects()` (for simple property filters), `search_similar_objects()`, and `execute_complex_query()`.
* **Threading for Long-Running API Calls:**
  * To ensure the UI remains responsive, all potentially long-running Grizabella API calls are executed in a non-blocking manner.
  * The architecture centralizes all Grizabella client operations in the main UI thread to guarantee thread-safe interactions with the underlying database connections, which may not be safe for concurrent access from multiple threads.
  * The process is as follows:
    1. **Initiation:** A UI view (e.g., `ObjectExplorerView`) that needs to perform an API call instantiates an `ApiClientThread`.
    2. **Signal Emission:** The `ApiClientThread`'s `run()` method is executed, which immediately emits an `apiRequestReady` signal. This signal carries the name of the API operation and its arguments.
    3. **Main Thread Execution:** The `MainWindow`, which runs in the main UI thread, has a slot `handleApiRequest` connected to the `apiRequestReady` signal. This slot receives the request and executes the corresponding method on the single, main `grizabella_client` instance.
    4. **Result Handling:** Once the API call completes, the `handleApiRequest` slot calls the `handleApiResponse` slot on the originating `ApiClientThread` instance, passing the result or error.
    5. **UI Update:** The `handleApiResponse` slot in the worker thread then emits a `result_ready` or `error_occurred` signal, which is connected back to the initial UI view, allowing it to update its state with the new data or display an error message.
  * This model ensures that the UI never freezes while maintaining thread-safe access to the Grizabella client.
* **Models (`QAbstractItemModel`):**
  * Custom Qt models (`QAbstractTableModel`, `QAbstractListModel`) will be implemented to bridge the Grizabella data (lists of `ObjectInstance`s, `PropertyDefinition`s, etc.) with `QTableView` and `QListView`. These models will handle fetching data (or being populated by data fetched by controller logic) and notifying views of changes.

**6. Modularity and File Structure (within `grizabella/ui/`)**

```text
grizabella/ui/
├── main_window.py           # Defines the QMainWindow, menu, toolbar, status bar, docks/tabs
├── app.py                   # Main application entry point, initializes QApplication & MainWindow
│
├── views/                   # Main content panels/views
│   ├── __init__.py
│   ├── connection_view.py     # Database Connection/Management View
│   ├── schema_editor_view.py  # Schema Explorer & Editor View
│   ├── data_explorer_view.py  # Object and Relation Explorer/Editor View
│   └── query_view.py          # Query Builder & Results View
│   └── graph_view.py          # (Optional) Graph Visualization View
│
├── widgets/                 # Custom, reusable UI components
│   ├── __init__.py
│   ├── property_editor.py     # Widget for editing a list of PropertyDefinitions in a table
│   ├── object_form.py         # Dynamically generated form for ObjectInstance properties
│   └── (other custom widgets as needed)
│
├── dialogs/                 # Custom QDialog subclasses
│   ├── __init__.py
│   ├── new_relation_dialog.py # Dialog for creating a new relation
│   └── (other dialogs like settings, confirmation, etc.)
│
├── models/                  # Qt Item Models (QAbstractTableModel, QAbstractListModel)
│   ├── __init__.py
│   ├── object_type_model.py
│   ├── object_instance_model.py
│   ├── relation_type_model.py
│   ├── relation_instance_model.py
│   └── property_definition_model.py
│
├── delegates/               # Custom QItemDelegates for QTableViews/QListViews
│   ├── __init__.py
│   └── (e.g., ComboBoxDelegate for PropertyDataType)
│
├── threads/                 # QThread subclasses for background API calls
│   ├── __init__.py
│   └── api_worker.py          # Generic worker or specific workers for different API calls
│
└── resources/               # Icons, qss stylesheets (future)
    ├── icons/
    └── styles/
```

## 7. (Optional) Simple Wireframes/Mockups

* **Main Window Sketch:**

    ```mermaid
    graph TD
        A[Menu Bar: File, Edit, View, Tools, Help] --> B(Toolbar: Icons);
        B --> C{Central Area: QTabWidget};
        C --> D[Status Bar: Connection Info, Messages];

        subgraph Central Area (QTabWidget)
            T1[Tab: DB Connection]
            T2[Tab: Schema Editor]
            T3[Tab: Data Explorer]
            T4[Tab: Query Builder]
            T5[Tab: Graph View (Opt.)]
        end
    ```

* **Schema Editor (Object Types Tab) Sketch:**

    ```mermaid
    graph TD
        subgraph Schema Editor - Object Types
            direction LR
            L1[List: ObjectTypeA, ObjectTypeB] --> R1{Form: ObjectTypeB Details};
            R1 --> N[Name: QLineEdit];
            R1 --> D[Description: QTextEdit];
            R1 --> P[Properties: QTableView];
            P --> P1[Col: Name | Col: Type | Col: Nullable? | ...];
            P --> AddPropBtn[Button: Add Property];
            P --> RemPropBtn[Button: Remove Property];
            R1 --> SaveBtn[Button: Save Object Type];
        end
    ```

* **Data Explorer (Objects Tab) Sketch:**

    ```mermaid
    graph TD
        subgraph Data Explorer - Objects
            direction LR
            LeftPanel --> Combo[Select Object Type: QComboBox];
            Combo --> Table[Object Instances: QTableView];
            Table --> Col1[ID | Prop1 | Prop2 | ...];
            LeftPanel --> AddObjBtn[Button: Add New Object];
            LeftPanel --> DelObjBtn[Button: Delete Selected];

            Table -- Selects Row --> RightPanel[Form: Selected Object Properties];
            RightPanel --> PropField1[Property1_Name: QLineEdit (value)];
            RightPanel --> PropField2[Property2_Name: QSpinBox (value)];
            RightPanel --> SaveChangesBtn[Button: Save Changes];
        end
