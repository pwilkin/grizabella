# Getting Started with Grizabella

This guide will help you take your first steps with Grizabella, whether you're using it as a Python library, interacting with the PySide6 UI, or connecting via the MCP server.

## Using Grizabella as a Library (Python API)

The Grizabella Python API provides a powerful way to integrate its multi-layer database capabilities into your applications.

Here's a short example demonstrating basic operations:

```python
from grizabella.api import Grizabella
from grizabella.core.models import ObjectTypeDefinition, PropertyDefinition, DataType

# 1. Initialize and connect to Grizabella
# This will use the default database path (~/.grizabella/default_grizabella.db)
# or create it if it doesn't exist.
# For more robust error handling, wrap in try...finally or use a 'with' statement.

print("Initializing Grizabella client...")
client = Grizabella() # You can specify a db_path: client = Grizabella(db_path="/path/to/your/grizabella.db")

try:
    print("Connecting to the database...")
    client.connect()
    print("Successfully connected.")

    # 2. Define a simple Object Type
    print("Defining 'Note' object type...")
    note_type_def = ObjectTypeDefinition(
        name="Note",
        description="A simple text note.",
        properties=[
            PropertyDefinition(name="title", data_type=DataType.STRING, is_required=True),
            PropertyDefinition(name="content", data_type=DataType.TEXT),
        ]
    )
    client.create_object_type(note_type_def)
    print(f"Object type '{note_type_def.name}' created.")

    # 3. Create an Object Instance of this type
    print("Creating an instance of 'Note'...")
    note_instance_data = {
        "title": "My First Note",
        "content": "This is a test note created using the Grizabella Python API."
    }
    # The create_object_instance method returns the created object with its assigned ID
    created_note = client.create_object_instance(object_type_name="Note", data=note_instance_data)
    print(f"Created note with ID: {created_note.id}")
    print(f"  Title: {created_note.data['title']}")
    print(f"  Content: {created_note.data['content']}")


    # 4. Retrieve the object
    print(f"Retrieving note with ID: {created_note.id}...")
    retrieved_note = client.get_object_instance(object_type_name="Note", instance_id=created_note.id)

    if retrieved_note:
        print("Successfully retrieved note:")
        print(f"  ID: {retrieved_note.id}")
        print(f"  Type: {retrieved_note.object_type_name}")
        print(f"  Title: {retrieved_note.data['title']}")
        print(f"  Content: {retrieved_note.data['content']}")
        print(f"  Created at: {retrieved_note.created_at}")
        print(f"  Updated at: {retrieved_note.updated_at}")
    else:
        print(f"Could not retrieve note with ID: {created_note.id}")

finally:
    # 5. Close the connection
    print("Closing the database connection...")
    client.close()
    print("Connection closed.")

# Alternative using a 'with' statement for automatic connection management:
#
# with Grizabella() as client_with:
#     # ... perform operations ...
#     pass # Connection is automatically closed here
```

This snippet covers:

* Initializing the `Grizabella` client.
* Connecting to the database (which also handles schema migrations).
* Defining an `ObjectTypeDefinition` for a "Note".
* Creating an `ObjectInstance` of that "Note".
* Retrieving the created `ObjectInstance` by its ID.
* Closing the database connection.

Explore the API documentation for more advanced features like creating relations, managing embeddings, and performing complex queries.

## Using the PySide6 UI (Brief Overview)

The Grizabella PySide6 UI provides a graphical way to interact with your Grizabella databases.

1. **Launch the UI:**
    If you installed Grizabella from source using Poetry, run:

    ```bash
    poetry run grizabella-ui
    ```

2. **Connection View:**
    Upon launching, you'll see the **Connection View**.
    * **Default Database:** You can connect to the default Grizabella database (usually located at `~/.grizabella/default_grizabella.db`). If it doesn't exist, Grizabella will offer to create it for you.
    * **Specify Path:** Alternatively, you can click "Browse" to select an existing Grizabella database file or choose a location for a new one.
    * Click "Connect" to open the database.

3. **Basic Navigation (Post-Connection):**
    Once connected, the main window will appear.
    * **Schema Editor (Object Types / Relation Types):** Navigate to the "Object Types" or "Relation Types" sections (often tabs or sidebar items) to define your data structures. You can create new types, add properties, and define their data types.
    * **Object Explorer / Relation Explorer:** After defining your schemas, go to the "Object Explorer" or "Relation Explorer" to create instances of your object and relation types. You can fill in their properties and see them listed.

    This provides a very high-level overview. The UI offers more detailed views for managing embeddings, executing queries, and exploring data. Refer to the full UI guide for comprehensive instructions.

## Using the MCP Server (Brief Overview)

The Grizabella MCP (Model Context Protocol) server allows other applications or AI agents to interact with Grizabella programmatically over a network interface.

1. **Launch the MCP Server:**
    If you installed Grizabella from source using Poetry, run:

    ```bash
    poetry run grizabella-mcp
    ```

    By default, the server will start (e.g., on `http://localhost:8000` - check the server startup logs for the exact address and port).

2. **Interacting with the MCP Server (Conceptual Example):**
    You can interact with the MCP server using any HTTP client, such as `curl` or a programmatic client in your preferred language. The exact tools and request formats will depend on the MCP tools exposed by Grizabella.

    Here's a *conceptual* example using `curl` to list available object types (assuming an MCP tool named `list_object_types` exists and the server is on `localhost:8000`):

    ```bash
    # This is a hypothetical example. The actual tool name and parameters may differ.
    curl -X POST http://localhost:8000/mcp \
         -H "Content-Type: application/json" \
         -d '{
               "tool_name": "list_object_types",
               "arguments": {}
             }'
    ```

    The server would respond with a JSON payload containing the list of object types or an error if the request is invalid or the tool doesn't exist.

    **Note:** The specific MCP tools available and their request/response schemas are defined within the Grizabella MCP server implementation. You'll need to refer to the Grizabella MCP documentation (or inspect its capabilities if it provides a discovery mechanism) for actual tool names and argument structures. A common basic tool might be to get schema information or list instances of a certain type.

This section provides a starting point. As you delve deeper, consult the API reference, UI guides, and MCP server documentation for detailed information on all of Grizabella's capabilities.
