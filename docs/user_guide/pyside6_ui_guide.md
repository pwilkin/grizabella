# Grizabella PySide6 UI Guide

This guide provides a comprehensive walkthrough of the Grizabella PySide6 User Interface. It will help you understand how to navigate the application, manage your graph database schema, explore data, and execute queries.

## Launching the UI

To launch the Grizabella PySide6 UI, ensure you have Grizabella installed and your environment configured. Open your terminal and run the following command:

```bash
poetry run grizabella-ui
```

This will start the application and open the main window.

## Connection View

Upon launching, the first view you'll encounter is the **Connection View**. This view allows you to establish a connection to your Grizabella database.

[Screenshot of Connection View]

*   **Default Database:** To connect to the default Grizabella database, simply click the "Connect" button. The application will attempt to connect to the database at the default location (`~/.grizabella/default_db`).
*   **Named Database:** If you have a named database (e.g., `my_project_db`), you can type its name into the "Database Name or Path" field and click "Connect". Grizabella will look for this database within its standard database directory.
*   **Custom Path:** To connect to a database at a specific file system path, you can either type the full path into the "Database Name or Path" field or use the "Browse" button.
*   **Browse Functionality:** Clicking the "Browse" button opens a file dialog, allowing you to navigate to and select your Grizabella database directory.
*   **Status Bar Feedback:** The status bar at the bottom of the window will provide feedback on the connection process, indicating whether the connection was successful or if any errors occurred.

Once a successful connection is established, the UI will transition to the main application window.

## Main Window Layout

After successfully connecting to a database, the main window displays a tabbed interface, providing access to different functionalities of Grizabella.

[Screenshot of Main Window with Tabs]

The main components are organized into the following tabs:

*   **Schema Editor:** Manage your database schema, including Object Types, Embedding Definitions, and Relation Types.
*   **Object Explorer:** View, create, edit, and delete object instances.
*   **Relation Explorer:** View, create, edit, and delete relation instances.
*   **Query View:** Execute various types of queries against your database.

## Schema Editor

The Schema Editor is a powerful tool for defining and modifying the structure of your graph database. It consists of three sub-tabs: Object Types, Embedding Definitions, and Relation Types.

### 1. Object Types View

This view allows you to manage the different types of objects (nodes) in your graph.

[Screenshot of Object Types View]

*   **Viewing Object Types:** A list on the left displays all currently defined Object Types. Clicking on an Object Type in this list will show its details on the right.
*   **Viewing Details:** The details panel shows:
    *   **Name:** The unique name of the Object Type.
    *   **Description:** A user-provided description of the Object Type.
    *   **Properties Table:** A table listing all properties defined for this Object Type, including their:
        *   Name
        *   Data Type (e.g., `string`, `integer`, `float`, `boolean`, `list<string>`, `vector<float>`)
        *   Primary Key (PK): Indicates if the property is part of the primary key.
        *   Nullable: Indicates if the property can have null values.
        *   Default Value: The default value for the property, if any.
*   **"New Object Type" Button:**
    *   Clicking this button opens the `ObjectTypeDialog`.
    *   [Screenshot of ObjectTypeDialog]
    *   **`ObjectTypeDialog` Fields:**
        *   **Name:** Enter a unique name for the new Object Type.
        *   **Description:** Provide a meaningful description.
        *   **Properties Table:**
            *   Use the "Add Property" button to add a new row to the table.
            *   For each property, you can specify:
                *   **Name:** The property's name.
                *   **Data Type:** Select from a dropdown of supported data types.
                *   **PK:** Check this box if the property is a primary key.
                *   **Nullable:** Check this box if the property can be null.
                *   **Default:** Optionally, provide a default value.
            *   Use the "Remove Selected Property" button to delete a property from the list.
    *   Click "OK" to create the new Object Type or "Cancel" to discard.
*   **"Edit Selected" Button:** Select an Object Type from the list and click this button to open the `ObjectTypeDialog` pre-filled with its current details, allowing you to modify it.
*   **"Delete Selected" Button:** Select an Object Type from the list and click this button to delete it. A confirmation dialog will appear.

### 2. Embedding Definitions View

This view manages how embeddings are generated and stored for your objects. Embeddings are crucial for similarity searches and other machine learning tasks.

[Screenshot of Embedding Definitions View]

*   **Structure:** Similar to the Object Types view, it features a list of existing Embedding Definitions on the left and a details panel on the right.
*   **Details:** When an Embedding Definition is selected, its details are displayed, including its name, the Object Type it applies to, the source property used for embedding, the embedding model, dimensions, and description.
*   **"New Embedding Definition" Button:**
    *   Opens the `EmbeddingDefinitionDialog`.
    *   [Screenshot of EmbeddingDefinitionDialog]
    *   **`EmbeddingDefinitionDialog` Fields:**
        *   **Name:** A unique name for this embedding definition.
        *   **Object Type:** A dropdown list to select the Object Type for which this embedding will be generated.
        *   **Source Property:** A dropdown list of properties from the selected Object Type. This list is dynamically populated based on the chosen Object Type. This property's value will be used as input to the embedding model.
        *   **Model:** Specify the embedding model to be used (e.g., `all-MiniLM-L6-v2`).
        *   **Dimensions:** The dimensionality of the embedding vector produced by the model.
        *   **Description:** An optional description for this embedding definition.
    *   Click "OK" to create or "Cancel" to discard.
*   **"Edit Selected" Button:** (Placeholder for future functionality) Currently, editing might involve deleting and recreating.
*   **"Delete Selected" Button:** Deletes the selected Embedding Definition after confirmation.

### 3. Relation Types View

This view allows you to define the types of relationships (edges) that can exist between your objects.

[Screenshot of Relation Types View]

*   **Structure:** Again, a list of Relation Types is on the left, with details appearing on the right upon selection.
*   **Details:** The details panel shows the Relation Type's name, description, the source Object Type, the target Object Type, and a table of any properties defined for the relation itself.
*   **"New Relation Type" Button:**
    *   Opens the `RelationTypeDialog`.
    *   [Screenshot of RelationTypeDialog]
    *   **`RelationTypeDialog` Fields:**
        *   **Name:** A unique name for the new Relation Type.
        *   **Description:** A description of what this relation represents.
        *   **Source Object Type:** A dropdown to select the Object Type from which relations of this type can originate.
        *   **Target Object Type:** A dropdown to select the Object Type to which relations of this type can point.
        *   **Properties Table:** Similar to the Object Type properties table, you can define properties specific to the relation itself (e.g., `weight`, `timestamp`, `role`). Use "Add Property" and "Remove Selected Property" to manage these.
    *   Click "OK" to create or "Cancel" to discard.
*   **"Edit Selected" Button:** (Placeholder for future functionality)
*   **"Delete Selected" Button:** Deletes the selected Relation Type after confirmation.

## Object Explorer View

The Object Explorer allows you to browse, create, modify, and delete instances of your defined Object Types.

[Screenshot of Object Explorer View]

*   **Select Object Type:** Use the dropdown menu at the top to choose the Object Type whose instances you want to view.
*   **Instances Table:** Once an Object Type is selected, the table below will populate with its instances.
    *   The columns in this table are dynamically generated based on the properties of the selected Object Type.
*   **"New Object" Button:**
    *   Opens the `ObjectInstanceDialog`.
    *   [Screenshot of ObjectInstanceDialog for a sample Object Type]
    *   **`ObjectInstanceDialog`:** This dialog presents a form that is dynamically generated based on the properties of the Object Type selected in the explorer.
        *   For each property, an appropriate input field is provided (e.g., line edit for strings, spin box for integers).
        *   A special `weight` field might be present for certain configurations, typically used in graph algorithms.
    *   Fill in the property values and click "OK" to create the new object instance.
*   **"View/Edit Selected" Button:** Select an object instance from the table and click this button. The `ObjectInstanceDialog` will open, pre-filled with the selected object's data, allowing you to view or modify its properties.
*   **"Delete Selected" Button:** Select an object instance and click this button to delete it after confirmation.
*   **"Refresh List" Button:** Click this to reload the list of object instances from the database, reflecting any recent changes.

## Relation Explorer View

The Relation Explorer is used to manage instances of the relationships defined in your schema.

[Screenshot of Relation Explorer View]

*   **Select Relation Type:** Choose a Relation Type from the dropdown menu to view its instances.
*   **Optional Filters:**
    *   **Source Object ID:** You can filter relations by the ID of their source object.
    *   **Target Object ID:** You can filter relations by the ID of their target object.
    *   Enter the respective IDs and apply the filter to narrow down the list.
*   **Instances Table:** The table displays instances of the selected Relation Type, matching any applied filters. Columns will include source ID, target ID, and any properties defined for the Relation Type.
*   **"New Relation" Button:**
    *   Opens the `RelationInstanceDialog`.
    *   [Screenshot of RelationInstanceDialog for a sample Relation Type, showing ComboBoxes for Source and Target Object selection]
    *   **`RelationInstanceDialog` Fields:**
        *   **Relation Type:** Pre-selected based on the explorer's context, or selectable if opened generically.
        *   **Source Object:** Select the source object instance for this relation using a filterable dropdown list (ComboBox). This replaces manual ID input and helps ensure the object exists.
        *   **Target Object:** Select the target object instance for this relation using a filterable dropdown list (ComboBox). This also replaces manual ID input.
        *   **Dynamic Properties:** Input fields for any properties defined for this Relation Type (e.g., `weight`).
        *   A `weight` field might be present for specifying the strength or cost of the relation.
    *   Click "OK" to create the new relation instance.
*   **"View/Edit Selected" Button:** Select a relation instance from the table to open the `RelationInstanceDialog` with its data pre-filled for viewing or editing.
*   **"Delete Selected" Button:** Deletes the selected relation instance after confirmation.

## Query View

The Query View is your interface for interacting with Grizabella's query engine, allowing you to retrieve specific data from your graph.

[Screenshot of Query View]

*   **Query Type Selector:** A dropdown menu allows you to choose the type of query you want to perform:
    *   Simple Object Query
    *   Embedding Similarity Search
    *   Complex Query
*   **Executing Queries:** After configuring your query parameters, click the "Execute Query" button.
*   **Results Display:** The results of your query will be displayed in the table at the bottom of the view.

### 1. Simple Object Query

This allows for basic retrieval of objects based on property conditions.

[Screenshot of Simple Object Query section]

*   **Object Type:** Select the Object Type you want to query from the dropdown.
*   **Conditions:** Enter conditions for filtering the objects. The current simple format might be a basic key-value pair or a simple expression (e.g., `name = "Alice"` or `age > 30`). Refer to specific examples or further documentation for the exact supported syntax.

### 2. Embedding Similarity Search

This query type finds objects whose embeddings are most similar to a given query text or vector.

[Screenshot of Embedding Similarity Search section]

*   **Embedding Definition:** Select the Embedding Definition (which implies an Object Type and an embedding model) to use for the search.
*   **Query Text/Vector:**
    *   Enter query text (which will be embedded using the selected definition's model).
    *   Alternatively, you might be able to paste a pre-computed query vector.
*   **Limit:** Specify the maximum number of similar objects to return.
*   **Filter:** Optionally, provide additional property-based filters to apply to the candidate objects before or after the similarity search.

### 3. Complex Query

This option is for more advanced queries, typically expressed in a structured format like JSON.

[Screenshot of Complex Query section]

*   **JSON Input:** A text area is provided where you can enter your complex query in JSON format. This allows for intricate graph traversals, multi-hop queries, and sophisticated filtering logic. Refer to the Grizabella Complex Query Language documentation for details on constructing these queries.
    *   Example: `{"object_type": "Person", "filters": [{"property": "city", "operator": "==", "value": "New York"}], "relations": [{"relation_type": "WORKS_AT", "target_object_type": "Company", "filters": [{"property": "industry", "operator": "==", "value": "Technology"}]}]}` (This is a conceptual example, actual syntax may vary).

## General UI Concepts

Several concepts apply across the Grizabella PySide6 UI:

*   **Threading for API Calls:** Most operations that interact with the backend database (e.g., fetching data, creating items, executing queries) are performed in separate threads. This ensures that the UI remains responsive and does not freeze during potentially long-running operations.
*   **Error Messages:** If an error occurs (e.g., invalid input, database error), a `QMessageBox` dialog will typically appear, displaying a descriptive error message to inform the user.
*   **Status Bar Updates:** The status bar at the bottom of the main window provides ongoing feedback about the application's state, such as "Connecting to database...", "Query executed successfully.", "Error: Object Type not found.", etc. This is a key place to look for quick updates on operations.
*   **Appearance:** The Grizabella UI uses the `qt_material` library to apply a modern Material Design theme (specifically, `light_blue.xml`), enhancing the visual appeal and user experience.

---

This guide should provide a solid foundation for using the Grizabella PySide6 UI. As new features are added, this documentation will be updated.