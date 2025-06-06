# Core Concepts in Grizabella

This document explains the fundamental concepts in Grizabella, providing a foundation for understanding how to define schemas, manage data, and utilize the system effectively.

## Database Instances

A Grizabella database instance is a self-contained environment where your schema definitions and data are stored. When you initialize the Grizabella client, you specify which database instance to connect to.

- **Default Path:** If you initialize `Grizabella()` without specifying a `db_name_or_path`, it will connect to or create a database named "default" in a standard Grizabella data directory (e.g., `~/.grizabella/databases/default`).
- **Named Instances:** You can use a simple string name like `"my_project_db"`. Grizabella will manage this database within its standard data directory (e.g., `~/.grizabella/databases/my_project_db`).
- **Custom Paths:** You can provide a full file system path (as a string or `pathlib.Path` object) to a directory where you want the database to be stored. This gives you full control over the location of your database files.

```python
from grizabella import Grizabella
from pathlib import Path

# Connect to the default database instance
db_default = Grizabella()

# Connect to a named database instance
db_named = Grizabella(db_name_or_path="my_project_db")

# Connect to a database at a custom path
db_custom_path = Grizabella(db_name_or_path=Path("/opt/grizabella_data/my_app_db"))
```

## Schema Definitions

The schema in Grizabella defines the structure of your data. It consists of Object Types, Embedding Definitions, and Relation Types.

### Object Types

Object Types define the blueprint for the kinds of entities you want to store in Grizabella. Think of them as analogous to tables in a relational database or node labels in a graph database. Each Object Type has a name and a set of properties.

**Structure:**

- `name`: A unique name for the object type (e.g., "Document", "User"). Conventionally, PascalCase is used.
- `description`: An optional human-readable description.
- `properties`: A list of `PropertyDefinition` objects that define the attributes of this object type.

**Properties (`PropertyDefinition`):**

- `name`: The name of the property (e.g., "title", "email", "creation_date").
- `data_type`: The data type of the property, chosen from `PropertyDataType` enum (e.g., `TEXT`, `INTEGER`, `FLOAT`, `BOOLEAN`, `DATETIME`, `BLOB`, `JSON`, `UUID`).
- `is_primary_key`: (Optional, boolean) Indicates if this property serves as a domain-specific primary key. An `ObjectInstance` always has a system-generated unique `id` (UUID). This flag is for an additional, user-defined primary key. An `ObjectTypeDefinition` can have at most one such primary key. Defaults to `False`.
- `is_nullable`: (boolean) Can this property have a null value? Defaults to `True`.
- `is_indexed`: (boolean) Should this property be indexed by underlying databases to speed up queries? Defaults to `False`.
- `is_unique`: (boolean) Must values for this property be unique across all instances of this Object Type? Defaults to `False`.
- `description`: An optional description of the property.

**Conceptual Pydantic Model Example for `ObjectTypeDefinition`:**

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class PropertyDataType(str, Enum):
    TEXT = "TEXT"
    INTEGER = "INTEGER"
    # ... other types

class PropertyDefinition(BaseModel):
    name: str
    data_type: PropertyDataType
    is_primary_key: bool = False
    is_nullable: bool = True
    is_indexed: bool = False
    is_unique: bool = False
    description: Optional[str] = None

class ObjectTypeDefinition(BaseModel):
    name: str = Field(description="Unique name for the object type. Convention: PascalCase.")
    description: Optional[str] = Field(default=None, description="Optional description.")
    properties: List[PropertyDefinition] = Field(description="List of properties.")

# Example Usage (conceptual, actual usage via Grizabella client)
# book_type = ObjectTypeDefinition(
#     name="Book",
#     description="Represents a book in the library.",
#     properties=[
#         PropertyDefinition(name="title", data_type=PropertyDataType.TEXT, is_indexed=True),
#         PropertyDefinition(name="isbn", data_type=PropertyDataType.TEXT, is_primary_key=True, is_unique=True),
#         PropertyDefinition(name="published_year", data_type=PropertyDataType.INTEGER),
#         PropertyDefinition(name="pages", data_type=PropertyDataType.INTEGER, is_nullable=True),
#     ]
# )
```

*(The actual `ObjectTypeDefinition` and `PropertyDefinition` models are available in [`grizabella.core.models`][])*

### Embedding Definitions

Embedding Definitions specify how vector embeddings should be generated and stored for objects of a particular type. Embeddings are numerical representations of data (often text) that capture semantic meaning, enabling similarity searches.

**Purpose:**

- To configure the automatic generation of vector embeddings from specific properties of your objects.
- To link an object type and one ofits properties to a specific embedding model.
- To enable semantic search capabilities (e.g., "find documents similar to this text").

**Structure (`EmbeddingDefinition`):**

- `name`: A unique name for this embedding configuration (e.g., "product_description_embedding"). Conventionally, snake_case.
- `object_type_name`: The name of the `ObjectTypeDefinition` this embedding applies to (e.g., "Product").
- `source_property_name`: The name of the property within the `object_type_name` whose content will be used to generate the embedding (e.g., "description"). This property should typically be of `PropertyDataType.TEXT`.
- `embedding_model`: An identifier for the embedding model to be used (e.g., a Hugging Face model name like "sentence-transformers/all-MiniLM-L6-v2").
- `dimensions`: (Optional, integer) The expected dimensionality of the embedding vector. If `None`, the system may attempt to infer it from the model.
- `description`: An optional human-readable description.

**Example (conceptual):**

```python
# Conceptual Pydantic Model for EmbeddingDefinition
# from pydantic import BaseModel, Field
# from typing import Optional

# class EmbeddingDefinition(BaseModel):
#     name: str
#     object_type_name: str
#     source_property_name: str
#     embedding_model: str
#     dimensions: Optional[int] = None
#     description: Optional[str] = None

# Example Usage (conceptual, actual usage via Grizabella client)
# article_content_embedding = EmbeddingDefinition(
#     name="article_content_embedding_v1",
#     object_type_name="Article", # Assumes an ObjectType "Article" exists
#     source_property_name="body_text", # Assumes "Article" has a "body_text" property
#     embedding_model="sentence-transformers/all-MiniLM-L6-v2",
#     dimensions=384,
#     description="Embeds the main body text of articles for similarity search."
# )
```

*(The actual `EmbeddingDefinition` model is available in [`grizabella.core.models`][])*

### Relation Types

Relation Types define the schema for relationships between `ObjectInstance`s. They are analogous to edge labels in a graph database or foreign key relationships (with potential properties on the join table) in a relational database.

**Structure (`RelationTypeDefinition`):**

- `name`: A unique name for the relation type (e.g., "WROTE", "CONTAINS_ITEM"). Conventionally, UPPER_SNAKE_CASE.
- `description`: An optional human-readable description.
- `source_object_type_names`: A list of `ObjectTypeDefinition` names that are allowed as the source (or "from" side) of this relation.
- `target_object_type_names`: A list of `ObjectTypeDefinition` names that are allowed as the target (or "to" side) of this relation.
- `properties`: (Optional) A list of `PropertyDefinition` objects that define attributes belonging to the relation itself (often called edge properties). Defaults to an empty list.

**Example (conceptual):**

```python
# Conceptual Pydantic Model for RelationTypeDefinition
# from pydantic import BaseModel, Field
# from typing import List, Optional
# from .object_types import PropertyDefinition # Assuming PropertyDefinition is defined

# class RelationTypeDefinition(BaseModel):
#     name: str
#     description: Optional[str] = None
#     source_object_type_names: List[str]
#     target_object_type_names: List[str]
#     properties: List[PropertyDefinition] = Field(default_factory=list)

# Example Usage (conceptual, actual usage via Grizabella client)
# authored_by_relation = RelationTypeDefinition(
#     name="AUTHORED_BY",
#     description="Indicates that a Book was written by an Author.",
#     source_object_type_names=["Book"], # Assumes "Book" ObjectType exists
#     target_object_type_names=["Author"], # Assumes "Author" ObjectType exists
#     properties=[
#         PropertyDefinition(name="role", data_type=PropertyDataType.TEXT, is_nullable=True) # e.g., "Primary Author", "Editor"
#     ]
# )
```

*(The actual `RelationTypeDefinition` model is available in [`grizabella.core.models`][])*

## Data Instances

Data instances are the actual pieces of data you store in Grizabella. They conform to the schemas defined by Object Types, Embedding Definitions, and Relation Types.

- **Objects (`ObjectInstance`):** A concrete instance of an `ObjectTypeDefinition`. It has a unique system-generated `id` (UUID), an `object_type_name` linking it to its definition, and a `properties` dictionary holding the actual data for the fields defined in the `ObjectTypeDefinition`.
  - Example: An `ObjectInstance` of type "Book" might have `properties: {"title": "The Great Gatsby", "isbn": "9780743273565", "published_year": 1925}`.

- **Relations (`RelationInstance`):** A concrete instance of a `RelationTypeDefinition`. It links two `ObjectInstance`s (a source and a target) and has a `relation_type_name`. It also has a unique system-generated `id` (UUID) and can have its own `properties` if defined in the `RelationTypeDefinition`.
  - Example: A `RelationInstance` of type "AUTHORED_BY" might link a "Book" object (source) to an "Author" object (target), with `properties: {"role": "Primary Author"}`.

- **Embeddings (`EmbeddingInstance`):** A concrete instance of an embedding. It stores the vector generated from a specific property of an `ObjectInstance` according to an `EmbeddingDefinition`. It includes the `object_instance_id` it belongs to, the `embedding_definition_name` used, the `vector` itself (a list of floats), and optionally a `source_text_preview`.
  - Example: An `EmbeddingInstance` linked to the "Book" object for "The Great Gatsby", generated using "article_content_embedding_v1" (if applicable), would contain the actual vector.

## Memory Metadata (`MemoryInstance`)

All core data instances in Grizabella (`ObjectInstance`, `RelationInstance`, `EmbeddingInstance`) inherit from a base model called `MemoryInstance`. This base model provides common metadata fields crucial for managing and understanding the data:

- **`id` (UUID):** A universally unique identifier automatically generated for every instance upon creation. This is the primary way to uniquely identify any piece of data within Grizabella.
- **`weight` (Decimal, 0-10):** A numerical value representing the importance, relevance, or confidence associated with the data instance. It defaults to `1.0`. This can be used for:
  - Ranking search results.
  - Prioritizing data during processing or eviction.
  - Implementing decay functions where older or less relevant data might have its weight reduced.
- **`upsert_date` (datetime):** A timestamp (in UTC) indicating when the instance was last created or updated (upserted). This is automatically set by the system. It's useful for:
  - Tracking data freshness.
  - Implementing time-based queries or filtering.
  - Auditing changes.

These metadata fields provide a consistent way to manage and query your data's lifecycle and significance within Grizabella.
