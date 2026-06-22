# Python API Usage - Detailed Guide

This guide provides a detailed walkthrough of the Grizabella Python API, covering connection management, schema definition, data manipulation, and querying.

## Connecting to Grizabella

The primary entry point to interacting with Grizabella is the `Grizabella` class from the [`grizabella.api.client`][] module.

### `Grizabella(db_name_or_path: Union[str, Path] = "default", create_if_not_exists: bool = True, use_gpu: bool = False)`

**Parameters:**

* `db_name_or_path` (Union[str, Path], optional):
  * Specifies the database instance to connect to.
  * If a string like `"my_db"` is provided, Grizabella manages it under `~/.grizabella/db_instances/my_db`.
  * If a `pathlib.Path` object or a string representing an absolute filesystem path is provided, Grizabella uses that specific directory as-is.
  * Defaults to `"default"`, which resolves to `~/.grizabella/db_instances/default_db`.
* `create_if_not_exists` (bool, optional):
  * If `True` (the default), the database directory and necessary files will be created if they don't already exist.
  * If `False` and the database does not exist, an error will likely occur upon trying to connect or perform operations.
* `use_gpu` (bool, optional):
  * If `True`, the embedding model and the optional cross-encoder reranker attempt to use CUDA. Requires a functioning PyTorch CUDA install.
  * Defaults to `False`.

**Default Behavior:**

Initializing `Grizabella()` without arguments connects to (or creates) the `default_db` instance under `~/.grizabella/db_instances/`.

Multiple `Grizabella` clients pointing at the same resolved path share a single underlying `GrizabellaDBManager` via a reference-counted singleton factory, so it is cheap to construct per-request clients inside services.

**Usage with `with` Statement:**

The recommended way to use the `Grizabella` client is with a `with` statement. This ensures that the database connection is automatically opened when entering the block and closed when exiting, even if errors occur.

```python
from pathlib import Path
from grizabella import Grizabella
from grizabella.core.models import ObjectTypeDefinition, PropertyDefinition, PropertyDataType

# Example using the 'with' statement for automatic connection management
db_path = Path("./my_grizabella_db")

try:
    with Grizabella(db_name_or_path=db_path, create_if_not_exists=True) as gz:
        # The connection is now active within this block
        print(f"Successfully connected to Grizabella database at: {gz.db_name_or_path}")

        # You can now perform operations, e.g., list object types
        object_types = gz.list_object_types()
        if not object_types:
            print("No object types found yet.")
        else:
            print("Existing object types:")
            for ot_def in object_types:
                print(f"- {ot_def.name}")

except Exception as e:
    print(f"An error occurred: {e}")

# Outside the 'with' block, the connection is automatically closed.
```

## Schema Management

Schema management involves defining the structure of your data using Object Types, Embedding Definitions, and Relation Types.

### Object Type Management

#### `create_object_type(object_type_def: ObjectTypeDefinition) -> None`

* **Signature:** `def create_object_type(self, object_type_def: ObjectTypeDefinition) -> None:`
* **Purpose:** Creates a new object type (e.g., a table schema or node label) in the database.
* **Example:**

```python
from grizabella import Grizabella
from grizabella.core.models import ObjectTypeDefinition, PropertyDefinition, PropertyDataType

# Define an Object Type for "User"
user_type_def = ObjectTypeDefinition(
    name="User",
    description="Represents a user in the system.",
    properties=[
        PropertyDefinition(name="user_id", data_type=PropertyDataType.TEXT, is_primary_key=True, is_unique=True, is_indexed=True),
        PropertyDefinition(name="username", data_type=PropertyDataType.TEXT, is_unique=True, is_indexed=True),
        PropertyDefinition(name="email", data_type=PropertyDataType.TEXT, is_unique=True),
        PropertyDefinition(name="full_name", data_type=PropertyDataType.TEXT, is_nullable=True),
        PropertyDefinition(name="join_date", data_type=PropertyDataType.DATETIME),
        PropertyDefinition(name="is_active", data_type=PropertyDataType.BOOLEAN, is_nullable=False),  # PropertyDefinition has no `default` field; set values explicitly when upserting instances.
    ]
)

with Grizabella(db_name_or_path="user_guide_db") as gz:
    try:
        gz.create_object_type(user_type_def)
        print(f"Object type '{user_type_def.name}' created successfully.")
    except Exception as e: # Replace with specific Grizabella exceptions if available
        print(f"Error creating object type '{user_type_def.name}': {e}")
```

#### `get_object_type_definition(type_name: str) -> Optional[ObjectTypeDefinition]`

* **Signature:** `def get_object_type_definition(self, type_name: str) -> Optional[ObjectTypeDefinition]:`
* **Purpose:** Retrieves the definition of a specific object type.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client from the previous example
with Grizabella(db_name_or_path="user_guide_db") as gz:
    user_type_name = "User"
    retrieved_def = gz.get_object_type_definition(user_type_name)

    if retrieved_def:
        print(f"Retrieved definition for '{retrieved_def.name}':")
        for prop in retrieved_def.properties:
            print(f"  - {prop.name} ({prop.data_type.value})")
    else:
        print(f"Object type '{user_type_name}' not found.")
```

#### `list_object_types() -> List[ObjectTypeDefinition]`

* **Signature:** `def list_object_types(self) -> List[ObjectTypeDefinition]:`
* **Purpose:** Lists all object type definitions currently in the database.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client
with Grizabella(db_name_or_path="user_guide_db") as gz:
    all_object_types = gz.list_object_types()
    if all_object_types:
        print("All defined object types:")
        for ot_def in all_object_types:
            print(f"- {ot_def.name} (Description: {ot_def.description or 'N/A'})")
    else:
        print("No object types are defined in the database yet.")
```

#### `delete_object_type(type_name: str) -> None`

* **Signature:** `def delete_object_type(self, type_name: str) -> None:`
* **Purpose:** Deletes an object type definition from the database. **Warning:** This may also delete all associated object instances and relations.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client
# with Grizabella(db_name_or_path="user_guide_db") as gz:
#     type_to_delete = "TemporaryType"
#     # First, create it if it doesn't exist for the example to run
#     if not gz.get_object_type_definition(type_to_delete):
#         temp_type = ObjectTypeDefinition(name=type_to_delete, properties=[PropertyDefinition(name="field", data_type=PropertyDataType.TEXT)])
#         gz.create_object_type(temp_type)
#         print(f"Created '{type_to_delete}' for deletion example.")
#
#     try:
#         gz.delete_object_type(type_to_delete)
#         print(f"Object type '{type_to_delete}' deleted successfully.")
#     except Exception as e: # Replace with specific Grizabella exceptions
#         print(f"Error deleting object type '{type_to_delete}': {e}")
```

### Embedding Definition Management

#### `create_embedding_definition(embedding_def: EmbeddingDefinition) -> EmbeddingDefinition`

* **Signature:** `def create_embedding_definition(self, embedding_def: EmbeddingDefinition) -> EmbeddingDefinition:`
* **Purpose:** Creates a new embedding definition, specifying how embeddings are generated for a particular object type and property.
* **Example:**

```python
from grizabella import Grizabella
from grizabella.core.models import EmbeddingDefinition, ObjectTypeDefinition, PropertyDefinition, PropertyDataType

# First, ensure the Object Type "User" exists (from previous example)
with Grizabella(db_name_or_path="user_guide_db") as gz:
    if not gz.get_object_type_definition("User"):
        user_type_def = ObjectTypeDefinition(
            name="User",
            properties=[
                PropertyDefinition(name="user_id", data_type=PropertyDataType.TEXT, is_primary_key=True),
                PropertyDefinition(name="username", data_type=PropertyDataType.TEXT),
                PropertyDefinition(name="profile_bio", data_type=PropertyDataType.TEXT) # Property to embed
            ]
        )
        gz.create_object_type(user_type_def)
        print("Created 'User' object type for embedding example.")


    # Define an Embedding Definition for the "profile_bio" property of "User".
    # `embedding_model` is resolved through the LanceDB embedding registry; if
    # you do not prefix it with a provider, `huggingface` is assumed.
    # `reranker_model` is optional — when set, semantic searches can re-score
    # the top vector hits with a cross-encoder.
    user_bio_embedding_def = EmbeddingDefinition(
        name="user_profile_bio_sbert",
        object_type_name="User",
        source_property_name="profile_bio",
        embedding_model="huggingface/sentence-transformers/all-MiniLM-L6-v2",
        dimensions=384,
        reranker_model="cross-encoder/ms-marco-MiniLM-L-6-v2",  # optional
        rerank_candidate_multiplier=5,  # oversample 5x before reranking
        description="Embeds user profile bios for similarity search, with optional reranking."
    )

    try:
        created_emb_def = gz.create_embedding_definition(user_bio_embedding_def)
        print(f"Embedding definition '{created_emb_def.name}' created successfully.")
    except Exception as e:
        print(f"Error creating embedding definition '{user_bio_embedding_def.name}': {e}")
```

#### `get_embedding_definition(name: str) -> Optional[EmbeddingDefinition]`

* **Signature:** `def get_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:`
* **Purpose:** Retrieves a specific embedding definition by its name.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client
with Grizabella(db_name_or_path="user_guide_db") as gz:
    emb_def_name = "user_profile_bio_sbert"
    retrieved_emb_def = gz.get_embedding_definition(emb_def_name)

    if retrieved_emb_def:
        print(f"Retrieved embedding definition '{retrieved_emb_def.name}':")
        print(f"  - Object Type: {retrieved_emb_def.object_type_name}")
        print(f"  - Source Property: {retrieved_emb_def.source_property_name}")
        print(f"  - Model: {retrieved_emb_def.embedding_model}")
    else:
        print(f"Embedding definition '{emb_def_name}' not found.")
```

#### `list_embedding_definitions() -> List[EmbeddingDefinition]`

* **Signature:** `def list_embedding_definitions(self) -> List[EmbeddingDefinition]:`
* **Purpose:** Lists all embedding definitions in the database.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client
with Grizabella(db_name_or_path="user_guide_db") as gz:
    all_emb_defs = gz.list_embedding_definitions()
    if all_emb_defs:
        print("All defined embedding definitions:")
        for emb_def in all_emb_defs:
            print(f"- {emb_def.name} (Model: {emb_def.embedding_model})")
    else:
        print("No embedding definitions are defined yet.")
```

#### `delete_embedding_definition(name: str) -> bool`

* **Signature:** `def delete_embedding_definition(self, name: str) -> bool:`
* **Purpose:** Deletes an embedding definition. May also delete associated embedding vectors.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client
# with Grizabella(db_name_or_path="user_guide_db") as gz:
#     emb_def_to_delete = "temp_embedding_def"
#     # Create it first for the example
#     if not gz.get_object_type_definition("TempObj"):
#         gz.create_object_type(ObjectTypeDefinition(name="TempObj", properties=[PropertyDefinition(name="text", data_type=PropertyDataType.TEXT)]))
#     if not gz.get_embedding_definition(emb_def_to_delete):
#         temp_emb_def = EmbeddingDefinition(name=emb_def_to_delete, object_type_name="TempObj", source_property_name="text", embedding_model="test-model")
#         gz.create_embedding_definition(temp_emb_def)
#         print(f"Created '{emb_def_to_delete}' for deletion example.")
#
#     try:
#         deleted = gz.delete_embedding_definition(emb_def_to_delete)
#         if deleted:
#             print(f"Embedding definition '{emb_def_to_delete}' deleted successfully.")
#         else:
#             print(f"Embedding definition '{emb_def_to_delete}' not found or not deleted.")
#     except Exception as e:
#         print(f"Error deleting embedding definition '{emb_def_to_delete}': {e}")
```

### Relation Type Management

#### `create_relation_type(relation_type_def: RelationTypeDefinition) -> None`

* **Signature:** `def create_relation_type(self, relation_type_def: RelationTypeDefinition) -> None:`
* **Purpose:** Creates a new relation type, defining the schema for relationships between objects.
* **Example:**

```python
from grizabella import Grizabella
from grizabella.core.models import RelationTypeDefinition, PropertyDefinition, PropertyDataType, ObjectTypeDefinition

# Ensure source and target Object Types exist (e.g., "User" and "Post")
with Grizabella(db_name_or_path="user_guide_db") as gz:
    if not gz.get_object_type_definition("User"):
        user_type_def = ObjectTypeDefinition(name="User", properties=[PropertyDefinition(name="user_id", data_type=PropertyDataType.TEXT, is_primary_key=True)])
        gz.create_object_type(user_type_def)
    if not gz.get_object_type_definition("Post"):
        post_type_def = ObjectTypeDefinition(name="Post", properties=[PropertyDefinition(name="post_id", data_type=PropertyDataType.TEXT, is_primary_key=True)])
        gz.create_object_type(post_type_def)
    print("Ensured 'User' and 'Post' object types exist for relation example.")

    # Define a Relation Type "AUTHORED"
    authored_relation_def = RelationTypeDefinition(
        name="AUTHORED",
        description="Indicates that a User authored a Post.",
        source_object_type_names=["User"],
        target_object_type_names=["Post"],
        properties=[
            PropertyDefinition(name="authored_date", data_type=PropertyDataType.DATETIME),
            PropertyDefinition(name="is_primary_author", data_type=PropertyDataType.BOOLEAN),  # no `default=` kwarg — set the value on each RelationInstance
        ]
    )

    try:
        gz.create_relation_type(authored_relation_def)
        print(f"Relation type '{authored_relation_def.name}' created successfully.")
    except Exception as e:
        print(f"Error creating relation type '{authored_relation_def.name}': {e}")
```

#### `get_relation_type(type_name: str) -> Optional[RelationTypeDefinition]`

* **Signature:** `def get_relation_type(self, type_name: str) -> Optional[RelationTypeDefinition]:`
* **Purpose:** Retrieves the definition of a specific relation type.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client
with Grizabella(db_name_or_path="user_guide_db") as gz:
    relation_type_name = "AUTHORED"
    retrieved_rel_def = gz.get_relation_type(relation_type_name)

    if retrieved_rel_def:
        print(f"Retrieved definition for relation type '{retrieved_rel_def.name}':")
        print(f"  - Source Types: {retrieved_rel_def.source_object_type_names}")
        print(f"  - Target Types: {retrieved_rel_def.target_object_type_names}")
        if retrieved_rel_def.properties:
            print("  - Properties:")
            for prop in retrieved_rel_def.properties:
                print(f"    - {prop.name} ({prop.data_type.value})")
    else:
        print(f"Relation type '{relation_type_name}' not found.")
```

#### `delete_relation_type(type_name: str) -> None`

* **Signature:** `def delete_relation_type(self, type_name: str) -> None:`
* **Purpose:** Deletes a relation type definition. **Warning:** May also delete associated relation instances.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client
# with Grizabella(db_name_or_path="user_guide_db") as gz:
#     rel_type_to_delete = "TEMP_RELATION"
#     # Create it first for the example
#     if not gz.get_object_type_definition("ObjA"): gz.create_object_type(ObjectTypeDefinition(name="ObjA", properties=[]))
#     if not gz.get_object_type_definition("ObjB"): gz.create_object_type(ObjectTypeDefinition(name="ObjB", properties=[]))
#
#     if not gz.get_relation_type(rel_type_to_delete):
#         temp_rel_def = RelationTypeDefinition(name=rel_type_to_delete, source_object_type_names=["ObjA"], target_object_type_names=["ObjB"])
#         gz.create_relation_type(temp_rel_def)
#         print(f"Created '{rel_type_to_delete}' for deletion example.")
#
#     try:
#         gz.delete_relation_type(rel_type_to_delete)
#         print(f"Relation type '{rel_type_to_delete}' deleted successfully.")
#     except Exception as e:
#         print(f"Error deleting relation type '{rel_type_to_delete}': {e}")
```

## Data Management

Data management involves creating, retrieving, updating, and deleting instances of your defined schemas (Objects and Relations).

### Object Instance Management

#### `upsert_object(obj: ObjectInstance) -> ObjectInstance`

* **Signature:** `def upsert_object(self, obj: ObjectInstance) -> ObjectInstance:`
* **Purpose:** Creates a new object instance or updates an existing one if an object with the same `id` already exists. The `upsert_date` metadata field is automatically updated. The `weight` field can be set or defaults to 1.0.
* **Example:**

```python
import uuid
from datetime import datetime, timezone
from grizabella import Grizabella
from grizabella.core.models import ObjectInstance, ObjectTypeDefinition, PropertyDefinition, PropertyDataType

# Ensure "User" ObjectType exists
with Grizabella(db_name_or_path="user_guide_db") as gz:
    if not gz.get_object_type_definition("User"):
        user_type_def = ObjectTypeDefinition(
            name="User",
            properties=[
                PropertyDefinition(name="user_id", data_type=PropertyDataType.TEXT, is_primary_key=True),
                PropertyDefinition(name="username", data_type=PropertyDataType.TEXT),
                PropertyDefinition(name="email", data_type=PropertyDataType.TEXT),
                PropertyDefinition(name="join_date", data_type=PropertyDataType.DATETIME),
                PropertyDefinition(name="profile_bio", data_type=PropertyDataType.TEXT, is_nullable=True),
            ]
        )
        gz.create_object_type(user_type_def)
        print("Created 'User' object type for upsert example.")

    # Create a new user object
    new_user_data = {
        "user_id": "usr_" + uuid.uuid4().hex[:8], # Domain-specific ID
        "username": "jdoe",
        "email": "jdoe@example.com",
        "join_date": datetime.now(timezone.utc),
        "profile_bio": "Loves hiking and coding."
    }
    new_user_instance = ObjectInstance(
        object_type_name="User",
        properties=new_user_data,
        weight=5.0 # Custom weight
    )

    try:
        created_user = gz.upsert_object(new_user_instance)
        print(f"User '{created_user.properties['username']}' (ID: {created_user.id}) upserted successfully.")
        print(f"  Upsert Date: {created_user.upsert_date}, Weight: {created_user.weight}")

        # Update the user's email (upsert again using the system ID)
        created_user.properties["email"] = "john.doe.updated@example.com"
        created_user.weight = 5.5 # Update weight
        # Note: upsert_date will be updated automatically by the system on upsert
        
        updated_user = gz.upsert_object(created_user) # Pass the whole instance with its ID
        print(f"User '{updated_user.properties['username']}' (ID: {updated_user.id}) updated successfully.")
        print(f"  New Email: {updated_user.properties['email']}")
        print(f"  Updated Upsert Date: {updated_user.upsert_date}, New Weight: {updated_user.weight}")

    except Exception as e:
        print(f"Error upserting user: {e}")
```

#### `get_object_by_id(object_id: str, type_name: str) -> Optional[ObjectInstance]`

* **Signature:** `def get_object_by_id(self, object_id: str, type_name: str) -> Optional[ObjectInstance]:`
* **Purpose:** Retrieves a specific object instance by its system-generated `id` and its type name.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client and 'created_user' from previous example
# For this example, let's re-fetch the user created above.
with Grizabella(db_name_or_path="user_guide_db") as gz:
    # First, let's find an existing user to get its ID
    users = gz.find_objects(type_name="User", filter_criteria={"username": "jdoe"}, limit=1)
    if users:
        user_to_get_id = users[0].id
        user_type_name = "User"

        retrieved_object = gz.get_object_by_id(object_id=str(user_to_get_id), type_name=user_type_name)
        if retrieved_object:
            print(f"Retrieved object by ID '{user_to_get_id}':")
            print(f"  Type: {retrieved_object.object_type_name}")
            print(f"  Properties: {retrieved_object.properties}")
            print(f"  Weight: {retrieved_object.weight}, Upsert Date: {retrieved_object.upsert_date}")
        else:
            print(f"Object with ID '{user_to_get_id}' of type '{user_type_name}' not found.")
    else:
        print("No user 'jdoe' found to get ID for example.")

```

#### `delete_object(object_id: str, type_name: str) -> bool`

* **Signature:** `def delete_object(self, object_id: str, type_name: str) -> bool:`
* **Purpose:** Deletes an object instance by its system-generated `id` and type name.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client
# Let's create a temporary object to delete
with Grizabella(db_name_or_path="user_guide_db") as gz:
    temp_obj_props = {"user_id": "temp_del_user", "username": "tempdelete"}
    temp_obj = ObjectInstance(object_type_name="User", properties=temp_obj_props)
    created_temp_obj = gz.upsert_object(temp_obj)
    print(f"Created temporary object with ID '{created_temp_obj.id}' for deletion.")

    object_to_delete_id = str(created_temp_obj.id)
    object_type_name = "User"

    try:
        deleted = gz.delete_object(object_id=object_to_delete_id, type_name=object_type_name)
        if deleted:
            print(f"Object with ID '{object_to_delete_id}' of type '{object_type_name}' deleted successfully.")
        else:
            print(f"Object with ID '{object_to_delete_id}' not found or not deleted.")
    except Exception as e:
        print(f"Error deleting object: {e}")
```

### Relation Instance Management

#### `add_relation(relation: RelationInstance) -> RelationInstance`

* **Signature:** `def add_relation(self, relation: RelationInstance) -> RelationInstance:`
* **Purpose:** Adds a new relation instance or updates an existing one if the provided `RelationInstance` object includes an `id` that matches an existing relation. The `upsert_date` metadata field is automatically updated upon creation or update. The `weight` field can be set or defaults to 1.0. This method effectively performs an "upsert" operation for relations.
* **Example:**

```python
import uuid
from datetime import datetime, timezone
from grizabella import Grizabella
from grizabella.core.models import (
    ObjectInstance, RelationInstance,
    ObjectTypeDefinition, RelationTypeDefinition,
    PropertyDefinition, PropertyDataType
)

with Grizabella(db_name_or_path="user_guide_db") as gz:
    # 1. Ensure Object Types ("User", "Post") and Relation Type ("AUTHORED") exist
    if not gz.get_object_type_definition("User"):
        gz.create_object_type(ObjectTypeDefinition(name="User", properties=[PropertyDefinition(name="user_id", data_type=PropertyDataType.TEXT, is_primary_key=True)]))
    if not gz.get_object_type_definition("Post"):
        gz.create_object_type(ObjectTypeDefinition(name="Post", properties=[PropertyDefinition(name="post_id", data_type=PropertyDataType.TEXT, is_primary_key=True), PropertyDefinition(name="title", data_type=PropertyDataType.TEXT)]))
    if not gz.get_relation_type("AUTHORED"):
        gz.create_relation_type(RelationTypeDefinition(name="AUTHORED", source_object_type_names=["User"], target_object_type_names=["Post"], properties=[PropertyDefinition(name="authored_date", data_type=PropertyDataType.DATETIME)]))
    print("Ensured types for relation example.")

    # 2. Create source and target ObjectInstances
    author_obj = gz.upsert_object(ObjectInstance(object_type_name="User", properties={"user_id": "author_" + uuid.uuid4().hex[:4]}))
    post_obj = gz.upsert_object(ObjectInstance(object_type_name="Post", properties={"post_id": "post_" + uuid.uuid4().hex[:4], "title": "My First Post"}))
    print(f"Created author (ID: {author_obj.id}) and post (ID: {post_obj.id}).")

    # 3. Create the RelationInstance
    authored_relation = RelationInstance(
        relation_type_name="AUTHORED",
        source_object_instance_id=author_obj.id,
        target_object_instance_id=post_obj.id,
        properties={"authored_date": datetime.now(timezone.utc)},
        weight=2.5 # Custom weight for the relation
    )

    try:
        created_relation = gz.add_relation(authored_relation)
        print(f"Relation '{created_relation.relation_type_name}' (ID: {created_relation.id}) added successfully.")
        print(f"  From: {created_relation.source_object_instance_id}")
        print(f"  To:   {created_relation.target_object_instance_id}")
        print(f"  Properties: {created_relation.properties}")
        print(f"  Weight: {created_relation.weight}, Upsert Date: {created_relation.upsert_date}")
    except Exception as e:
        print(f"Error adding relation: {e}")
```

#### `get_relation(from_object_id: str, to_object_id: str, relation_type_name: str) -> List[RelationInstance]`

* **Purpose:** Retrieves relations of a given type between two specific objects
  (identified by UUID strings). Returns all matching relations — useful because
  multiple parallel relations of the same type may exist between the same pair.

    ```python
    with Grizabella(db_name_or_path="user_guide_db") as gz:
        rels = gz.get_relation(
            from_object_id=str(author_obj.id),
            to_object_id=str(post_obj.id),
            relation_type_name="AUTHORED",
        )
        for rel in rels:
            print(rel.id, rel.properties)
    ```

#### `delete_relation(relation_type_name: str, relation_id: str) -> bool`

* **Purpose:** Deletes a single relation by its type name and UUID. Returns
  `True` if the row was actually removed from SQLite and/or the Kuzu graph,
  `False` if it wasn't found.

    ```python
    gz.delete_relation(relation_type_name="AUTHORED", relation_id=str(rel.id))
    ```

For bulk lookups by source/target/relation-type/property filters (rather than a
specific two-object pair), see `query_relations(...)` on the client.

#### `get_outgoing_relations(object_id: str, type_name: str, relation_type_name: Optional[str] = None) -> List[RelationInstance]`

* **Signature:** `def get_outgoing_relations(self, object_id: str, type_name: str, relation_type_name: Optional[str] = None) -> List[RelationInstance]:`
* **Purpose:** Retrieves all outgoing relations from a given object.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client and 'author_obj' from previous example
with Grizabella(db_name_or_path="user_guide_db") as gz:
    # Find an author to get their outgoing relations
    authors = gz.find_objects(type_name="User", limit=1) # Get any user
    if authors:
        author_to_query_id = str(authors[0].id)
        author_type_name = "User" # Type name of the source object

        outgoing_relations = gz.get_outgoing_relations(
            object_id=author_to_query_id,
            type_name=author_type_name, # type_name of the source object_id
            relation_type_name="AUTHORED" # Optional: filter by relation type
        )

        if outgoing_relations:
            print(f"Outgoing 'AUTHORED' relations for object ID '{author_to_query_id}':")
            for rel in outgoing_relations:
                print(f"  - Relation ID: {rel.id}, Target ID: {rel.target_object_instance_id}, Props: {rel.properties}")
        else:
            print(f"No outgoing 'AUTHORED' relations found for object ID '{author_to_query_id}'.")
    else:
        print("No author found to query outgoing relations.")
```

#### `get_incoming_relations(object_id: str, type_name: str, relation_type_name: Optional[str] = None) -> List[RelationInstance]`

* **Signature:** `def get_incoming_relations(self, object_id: str, type_name: str, relation_type_name: Optional[str] = None) -> List[RelationInstance]:`
* **Purpose:** Retrieves all incoming relations to a given object.
* **Example:**

```python
# Assuming 'gz' is an active Grizabella client and 'post_obj' from a previous example
with Grizabella(db_name_or_path="user_guide_db") as gz:
    # Find a post to get its incoming relations
    posts = gz.find_objects(type_name="Post", limit=1) # Get any post
    if posts:
        post_to_query_id = str(posts[0].id)
        post_type_name = "Post" # Type name of the target object

        incoming_relations = gz.get_incoming_relations(
            object_id=post_to_query_id,
            type_name=post_type_name, # type_name of the target object_id
            relation_type_name="AUTHORED" # Optional: filter by relation type
        )

        if incoming_relations:
            print(f"Incoming 'AUTHORED' relations for object ID '{post_to_query_id}':")
            for rel in incoming_relations:
                print(f"  - Relation ID: {rel.id}, Source ID: {rel.source_object_instance_id}, Props: {rel.properties}")
        else:
            print(f"No incoming 'AUTHORED' relations found for object ID '{post_to_query_id}'.")
    else:
        print("No post found to query incoming relations.")

```

## Querying

Grizabella provides several ways to query your data, from simple object lookups to complex multi-faceted queries.

### Simple Object Queries (`find_objects`)

* **Signature:** `def find_objects(self, type_name: str, filter_criteria: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[ObjectInstance]:`
  * Note: The client API uses `find_objects`. The prompt mentioned `query_objects`. We'll document `find_objects` as it's in the client.
* **Purpose:** Finds objects of a given type, optionally matching filter criteria on their properties.
* **Examples:**

  * **Filtering with simple equality:**

    ```python
    # Assuming 'gz' is an active Grizabella client
    with Grizabella(db_name_or_path="user_guide_db") as gz:
        # Find all active users named "jdoe"
        active_jdoes = gz.find_objects(
            type_name="User",
            filter_criteria={"username": "jdoe", "is_active": True} # Assuming 'is_active' property exists
        )
        if active_jdoes:
            print(f"Found {len(active_jdoes)} active user(s) named 'jdoe':")
            for user in active_jdoes:
                print(f"  - ID: {user.id}, Email: {user.properties.get('email')}")
        else:
            print("No active users named 'jdoe' found.")
    ```

  * **Using `limit`:** (Offset is not directly supported by `find_objects`, but by `query_object_instances` in DBManager)

    ```python
    # Assuming 'gz' is an active Grizabella client
    with Grizabella(db_name_or_path="user_guide_db") as gz:
        # Get up to 5 posts (any posts)
        latest_posts = gz.find_objects(type_name="Post", limit=5)
        if latest_posts:
            print(f"Found {len(latest_posts)} post(s) (limit 5):")
            for post in latest_posts:
                print(f"  - ID: {post.id}, Title: {post.properties.get('title')}")
        else:
            print("No posts found.")
    ```

  * The `filter_criteria` currently supports exact matches. For more complex conditions (e.g., >, <, LIKE), you would typically use the `execute_complex_query` method or if the underlying `query_object_instances` in `DBManager` evolves to support richer conditions directly through `find_objects`.

### Embedding Similarity Search (`find_similar`)

* **Signature:**
  `def find_similar(self, embedding_name: str, query_text: str, limit: int = 5, filter_condition: Optional[str] = None, rerank: Optional[bool] = None, rerank_model: Optional[str] = None, rerank_candidates: Optional[int] = None) -> list[ObjectInstance]:`
* **Purpose:** Runs a semantic search against a given `EmbeddingDefinition`.
  The query text is embedded with the same model that produced the stored
  vectors, a top-K ANN lookup runs on LanceDB, and full `ObjectInstance`s
  are fetched from SQLite for the hits.
* **Reranking:** If the `EmbeddingDefinition` carries a `reranker_model`
  (or you pass `rerank_model=` explicitly), the top candidates are
  post-processed with a cross-encoder for sharper relevance:
  * `rerank=None` (default) — rerank automatically iff a model is configured.
  * `rerank=True` — force reranking; combined with `rerank_model` lets you
    rerank definitions that don't otherwise have a model configured.
  * `rerank=False` — skip reranking even if a model is configured.
  * `rerank_candidates` — how many vector hits to fetch before reranking.
    Defaults to `limit * EmbeddingDefinition.rerank_candidate_multiplier`.
* **Example — plain vector search:**

    ```python
    with Grizabella(db_name_or_path="user_guide_db") as gz:
        similar_users = gz.find_similar(
            embedding_name="user_profile_bio_sbert",
            query_text="Looking for software engineers passionate about Python.",
            limit=3,
        )
        for user in similar_users:
            print(f"  - ID: {user.id}, Username: {user.properties.get('username')}")
    ```

* **Example — force-enable reranking with an explicit model:**

    ```python
    similar_users = gz.find_similar(
        embedding_name="user_profile_bio_sbert",
        query_text="experienced backend engineer for high-throughput APIs",
        limit=5,
        rerank=True,
        rerank_model="mixedbread-ai/mxbai-rerank-base-v1",
        rerank_candidates=50,  # oversample before cross-encoding
    )
    ```

* **Note on legacy method:** The client also exposes `search_similar_objects(object_id, type_name, ...)`
  for "find objects similar to *this* object", which uses the given object's stored embedding as the query
  vector. Because this path doesn't have access to the original query text, it does not currently invoke
  the reranker.

### Complex Queries (`execute_complex_query`)

* **Signature:** `def execute_complex_query(self, query: ComplexQuery) -> QueryResult:`
* **Purpose:** Executes a sophisticated query that can combine relational filters, graph traversals, and embedding searches across multiple object types and database layers.
* **Pydantic Models:** Uses `ComplexQuery`, `QueryComponent`, `RelationalFilter`, `EmbeddingSearchClause`, `GraphTraversalClause` from [`grizabella.core.query_models`][].
* **Example 1: Find active users who authored posts about "Python"**

    ```python
    from grizabella import Grizabella
    from grizabella.core.query_models import (
        ComplexQuery, QueryComponent, RelationalFilter, GraphTraversalClause
    )
    # Assume ObjectTypes: User (username, is_active), Post (title, content)
    # Assume RelationType: AUTHORED (User -> Post)
    # Assume EmbeddingDefinition: post_content_embed (on Post.content)

    # This example requires an embedding vector for "Python".
    # In a real scenario, you'd generate this using the same model as 'post_content_embed'.
    # For this example, we'll use a relational filter on title for simplicity,
    # as generating the vector here is out of scope.
    # A true embedding search would use EmbeddingSearchClause.

    with Grizabella(db_name_or_path="user_guide_db") as gz:
        # Ensure types exist for the example
        if not gz.get_object_type_definition("User"):
            gz.create_object_type(ObjectTypeDefinition(name="User", properties=[
                PropertyDefinition(name="user_id", data_type=PropertyDataType.TEXT, is_primary_key=True),
                PropertyDefinition(name="username", data_type=PropertyDataType.TEXT),
                PropertyDefinition(name="is_active", data_type=PropertyDataType.BOOLEAN, is_nullable=False)
            ]))
        if not gz.get_object_type_definition("Post"):
            gz.create_object_type(ObjectTypeDefinition(name="Post", properties=[
                PropertyDefinition(name="post_id", data_type=PropertyDataType.TEXT, is_primary_key=True),
                PropertyDefinition(name="title", data_type=PropertyDataType.TEXT, is_indexed=True),
                PropertyDefinition(name="content", data_type=PropertyDataType.TEXT)
            ]))
        if not gz.get_relation_type("AUTHORED"):
            gz.create_relation_type(RelationTypeDefinition(name="AUTHORED", source_object_type_names=["User"], target_object_type_names=["Post"]))
        print("Ensured types for complex query example 1.")

        # Create some sample data
        active_user = gz.upsert_object(ObjectInstance(object_type_name="User", properties={"user_id": "user_cq1", "username": "coder1", "is_active": True}))
        inactive_user = gz.upsert_object(ObjectInstance(object_type_name="User", properties={"user_id": "user_cq2", "username": "coder2", "is_active": False}))
        python_post = gz.upsert_object(ObjectInstance(object_type_name="Post", properties={"post_id": "post_cq1", "title": "Intro to Python", "content": "Python is great."}))
        java_post = gz.upsert_object(ObjectInstance(object_type_name="Post", properties={"post_id": "post_cq2", "title": "Java Basics", "content": "Java is also cool."}))

        gz.add_relation(RelationInstance(relation_type_name="AUTHORED", source_object_instance_id=active_user.id, target_object_instance_id=python_post.id))
        gz.add_relation(RelationInstance(relation_type_name="AUTHORED", source_object_instance_id=inactive_user.id, target_object_instance_id=java_post.id))
        gz.add_relation(RelationInstance(relation_type_name="AUTHORED", source_object_instance_id=active_user.id, target_object_instance_id=java_post.id)) # Active user also wrote a Java post
        print("Added sample data for complex query example 1.")


        complex_query_def = ComplexQuery(
            description="Find active users who authored posts with 'Python' in the title.",
            components=[
                QueryComponent(
                    object_type_name="User", # Start with Users
                    relational_filters=[
                        RelationalFilter(property_name="is_active", operator="==", value=True)
                    ],
                    graph_traversals=[
                        GraphTraversalClause(
                            relation_type_name="AUTHORED",
                            direction="outgoing",
                            target_object_type_name="Post",
                            target_object_properties=[ # Filter on properties of the target "Post" objects
                                RelationalFilter(property_name="title", operator="CONTAINS", value="Python")
                            ]
                        )
                    ]
                )
            ]
        )

        try:
            query_result = gz.execute_complex_query(complex_query_def)
            if query_result.errors:
                print(f"Errors during complex query: {query_result.errors}")
            
            if query_result.object_instances:
                print("Users matching the complex query:")
                for obj_instance in query_result.object_instances:
                    # The result instances are of the primary object_type_name of the first component, "User"
                    print(f"  - User ID: {obj_instance.id}, Username: {obj_instance.properties.get('username')}")
            else:
                print("No users found matching the complex query.")
        except NotImplementedError:
            print("execute_complex_query or its underlying DBManager.process_complex_query is not fully implemented.")
        except Exception as e:
            print(f"An error occurred executing complex query: {e}")
    ```

* **Example 2: "CAR" example - Find "Car" objects that are "Red" and "LocatedIn" a "City" named "Testville" and have a "HAS_PART" relation to a "Part" object whose "part_name" is "EngineV8".**

    ```python
    # Assuming ObjectTypes: Car(color), City(name), Part(part_name)
    # Assuming RelationTypes: LocatedIn (Car -> City), HAS_PART (Car -> Part)
    with Grizabella(db_name_or_path="user_guide_db") as gz:
        # Setup (ensure types and some data exist)
        for ot_name, props in [("Car", [("color", PropertyDataType.TEXT)]), ("City", [("name", PropertyDataType.TEXT)]), ("Part", [("part_name", PropertyDataType.TEXT)])]:
            if not gz.get_object_type_definition(ot_name):
                gz.create_object_type(ObjectTypeDefinition(name=ot_name, properties=[PropertyDefinition(name=p[0], data_type=p[1]) for p in props]))
        for rt_name, src, tgt in [("LocatedIn", "Car", "City"), ("HAS_PART", "Car", "Part")]:
            if not gz.get_relation_type(rt_name):
                gz.create_relation_type(RelationTypeDefinition(name=rt_name, source_object_type_names=[src], target_object_type_names=[tgt]))
        print("Ensured types for CAR complex query example.")

        # Sample Data
        red_car1 = gz.upsert_object(ObjectInstance(object_type_name="Car", properties={"color": "Red"}))
        blue_car = gz.upsert_object(ObjectInstance(object_type_name="Car", properties={"color": "Blue"}))
        testville = gz.upsert_object(ObjectInstance(object_type_name="City", properties={"name": "Testville"}))
        otherville = gz.upsert_object(ObjectInstance(object_type_name="City", properties={"name": "Otherville"}))
        engine_v8 = gz.upsert_object(ObjectInstance(object_type_name="Part", properties={"part_name": "EngineV8"}))
        engine_v6 = gz.upsert_object(ObjectInstance(object_type_name="Part", properties={"part_name": "EngineV6"}))

        gz.add_relation(RelationInstance(relation_type_name="LocatedIn", source_object_instance_id=red_car1.id, target_object_instance_id=testville.id))
        gz.add_relation(RelationInstance(relation_type_name="LocatedIn", source_object_instance_id=blue_car.id, target_object_instance_id=testville.id))
        gz.add_relation(RelationInstance(relation_type_name="HAS_PART", source_object_instance_id=red_car1.id, target_object_instance_id=engine_v8.id))
        gz.add_relation(RelationInstance(relation_type_name="HAS_PART", source_object_instance_id=blue_car.id, target_object_instance_id=engine_v6.id))
        print("Added sample data for CAR complex query example.")


        car_query = ComplexQuery(
            description="Find Red Cars in Testville with a V8 Engine.",
            components=[
                QueryComponent(
                    object_type_name="Car",
                    relational_filters=[
                        RelationalFilter(property_name="color", operator="==", value="Red")
                    ],
                    graph_traversals=[
                        GraphTraversalClause( # Car --LocatedIn--> City
                            relation_type_name="LocatedIn",
                            direction="outgoing",
                            target_object_type_name="City",
                            target_object_properties=[
                                RelationalFilter(property_name="name", operator="==", value="Testville")
                            ]
                        ),
                        GraphTraversalClause( # Car --HAS_PART--> Part
                            relation_type_name="HAS_PART",
                            direction="outgoing",
                            target_object_type_name="Part",
                            target_object_properties=[
                                RelationalFilter(property_name="part_name", operator="==", value="EngineV8")
                            ]
                        )
                    ]
                )
            ]
        )
        try:
            car_query_result = gz.execute_complex_query(car_query)
            if car_query_result.errors:
                print(f"Errors during CAR complex query: {car_query_result.errors}")

            if car_query_result.object_instances:
                print("Cars matching the CAR complex query:")
                for car in car_query_result.object_instances:
                    print(f"  - Car ID: {car.id}, Color: {car.properties.get('color')}")
            else:
                print("No cars found matching the CAR complex query.")
        except NotImplementedError:
            print("execute_complex_query or its underlying DBManager.process_complex_query is not fully implemented.")
        except Exception as e:
            print(f"An error occurred executing CAR complex query: {e}")

    ```

    **Interpreting `QueryResult`:**
    The `QueryResult` object contains:
  * `object_instances`: A list of `ObjectInstance`s that match the entire complex query. These instances will be of the `object_type_name` specified in the *first* component of your `ComplexQuery` if not otherwise specified by future features like explicit return types.
  * `errors`: A list of strings, containing any error messages encountered during query planning or execution. Check this list to debug issues.

#### Reranking inside a Complex Query

`EmbeddingSearchClause` carries the same rerank knobs as
`Grizabella.find_similar`. If you provide the raw `rerank_query_text`, the
query engine oversamples the vector step and cross-encodes the candidates
before handing the surviving IDs to the next step (graph traversal,
relational filter, etc.).

```python
from grizabella.core.query_models import (
    ComplexQuery, QueryComponent, EmbeddingSearchClause, GraphTraversalClause, RelationalFilter,
)

# Vector for the query (obtained via `get_embedding_vector_for_text` or
# your own encoder). For brevity here we reuse the LanceDB-side model:
query_text = "Python performance tips"
query_vec = gz._db_manager._connection_helper.lancedb_adapter.get_embedding_model(
    "sentence-transformers/all-MiniLM-L6-v2"
).compute_query_embeddings([query_text])[0]

query = ComplexQuery(
    description="Active users who authored posts semantically close to 'Python performance tips'.",
    components=[
        QueryComponent(
            object_type_name="Post",
            embedding_searches=[
                EmbeddingSearchClause(
                    embedding_definition_name="post_content_embed",
                    similar_to_payload=list(query_vec),
                    limit=5,
                    # Rerank-specific fields:
                    rerank_query_text=query_text,
                    rerank=True,                    # None/True/False
                    # rerank_model="...",           # optional per-call override
                    # rerank_candidates=50,         # optional oversampling override
                ),
            ],
            graph_traversals=[
                GraphTraversalClause(
                    relation_type_name="AUTHORED",
                    direction="incoming",
                    target_object_type_name="User",
                    target_object_properties=[
                        RelationalFilter(property_name="is_active", operator="==", value=True),
                    ],
                ),
            ],
        ),
    ],
)
result = gz.execute_complex_query(query)
```

When reranking runs, the threshold field on the clause is skipped (the units
change from cosine distance to cross-encoder scores), and candidate output is
ordered by rerank score descending.

This detailed guide should help you effectively use the Grizabella Python API.
Consult the source docstrings in [`grizabella.core.models`][],
[`grizabella.core.query_models`][], and [`grizabella.api.client`][] for the
authoritative parameter descriptions.
