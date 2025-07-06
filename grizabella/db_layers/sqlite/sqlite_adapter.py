"""Grizabella adapter for SQLite3 database."""

import json
import logging  # Added
import sqlite3
import threading  # For logging thread ID
from datetime import datetime  # timezone is not used directly here
from decimal import Decimal
from typing import Any, Optional  # Union is not used
from uuid import UUID  # uuid4 is not used directly here

from pydantic import BaseModel

from grizabella.core.exceptions import DatabaseError, InstanceError, SchemaError
from grizabella.core.models import (
    EmbeddingDefinition,
    ObjectInstance,
    ObjectTypeDefinition,
    # PropertyDefinition, # Not directly used in this file's top-level logic
    PropertyDataType,
    # MemoryInstance, # Not directly used in this file's top-level logic
    RelationInstance,  # Added import
    RelationTypeDefinition,
)
from grizabella.core.query_models import RelationalFilter  # Added for new methods
from grizabella.db_layers.common.base_adapter import BaseDBAdapter

logger = logging.getLogger(__name__) # Added module-level logger


class SQLiteAdapter(BaseDBAdapter):  # pylint: disable=R0904
    """Grizabella adapter for SQLite3.
    Handles relational data storage and schema definition persistence.
    """

    _META_TABLE_OBJECT_TYPES = "_grizabella_object_types"
    _META_TABLE_EMBEDDING_DEFS = "_grizabella_embedding_definitions"
    _META_TABLE_RELATION_TYPES = "_grizabella_relation_types"

    def __init__(self, db_path: str, config: Optional[dict[str, Any]] = None) -> None:
        logger.info(f"SQLiteAdapter: Initializing in thread ID: {threading.get_ident()} for db: {db_path}")
        self.conn: Optional[sqlite3.Connection] = None
        super().__init__(db_path, config)  # This will call _connect

    def _connect(self) -> None:
        """Establish a connection to the SQLite database."""
        logger.info(f"SQLiteAdapter: _connect called in thread ID: {threading.get_ident()} for db: {self.db_path}")
        try:
            self.conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            logger.info(f"SQLiteAdapter: sqlite3.connect successful in thread ID: {threading.get_ident()} for db: {self.db_path}. Connection object: {self.conn}")
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self._init_meta_tables()
        except sqlite3.Error as e:
            msg = f"SQLite connection error to '{self.db_path}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def _init_meta_tables(self) -> None:
        """Initializes tables for storing Grizabella schema definitions if they don't exist."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        try:
            with self.conn:
                self.conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._META_TABLE_OBJECT_TYPES} (
                        name TEXT PRIMARY KEY,
                        definition TEXT NOT NULL -- JSON string of ObjectTypeDefinition
                    )
                """,
                )
                self.conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._META_TABLE_EMBEDDING_DEFS} (
                        name TEXT PRIMARY KEY,
                        definition TEXT NOT NULL -- JSON string of EmbeddingDefinition
                    )
                """,
                )
                self.conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._META_TABLE_RELATION_TYPES} (
                        name TEXT PRIMARY KEY,
                        definition TEXT NOT NULL -- JSON string of RelationTypeDefinition
                    )
                """,
                )
        except sqlite3.Error as e:
            msg = f"SQLite error initializing metadata tables: {e}"
            raise DatabaseError(
                msg,
            ) from e

    def close(self) -> None:
        """Close the SQLite database connection."""
        logger.info(f"SQLiteAdapter: close() called in thread ID: {threading.get_ident()} for db: {self.db_path}. Connection state: {'Connected' if self.conn else 'Not Connected'}")
        if self.conn:
            try:
                self.conn.close()
                logger.info(f"SQLiteAdapter: self.conn.close() executed for {self.db_path}.")
                self.conn = None
            except sqlite3.Error as e:
                logger.error(f"SQLiteAdapter: sqlite3.Error during close for {self.db_path}: {e}", exc_info=True)
                msg = f"SQLite error closing connection: {e}"
                raise DatabaseError(msg) from e

    # --- Schema Definition Persistence ---

    def _save_definition(
        self, table_name: str, name: str, definition: BaseModel,
    ) -> None:
        """Saves a Pydantic model definition as JSON into the specified metadata table."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        try:
            with self.conn:
                self.conn.execute(
                    f"INSERT OR REPLACE INTO {table_name} (name, definition) VALUES (?, ?)",
                    (name, definition.model_dump_json()),
                )
        except sqlite3.Error as e:
            msg = f"Error saving definition '{name}' to {table_name}: {e}"
            raise DatabaseError(
                msg,
            ) from e

    def _load_definition(
        self, table_name: str, name: str, model_class: type,
    ) -> Optional[BaseModel]:
        """Loads a Pydantic model definition from JSON stored in the specified metadata table."""
        logger.info(f"SQLiteAdapter: _load_definition called in thread ID: {threading.get_ident()} for table: {table_name}, name: {name}")
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        try:
            cursor = self.conn.execute(
                f"SELECT definition FROM {table_name} WHERE name = ?", (name,),
            )
            row = cursor.fetchone()
            if row:
                return model_class.model_validate_json(row["definition"])
            return None
        except sqlite3.Error as e:
            msg = f"Error loading definition '{name}' from {table_name}: {e}"
            raise DatabaseError(
                msg,
            ) from e
        except json.JSONDecodeError as e:
            msg = f"Error decoding JSON for definition '{name}' from {table_name}: {e}"
            raise SchemaError(
                msg,
            ) from e

    def _delete_definition(self, table_name: str, name: str) -> bool:
        """Deletes a definition from the specified metadata table. Returns True if deleted."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        try:
            with self.conn:
                cursor = self.conn.execute(
                    f"DELETE FROM {table_name} WHERE name = ?", (name,),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            msg = f"Error deleting definition '{name}' from {table_name}: {e}"
            raise DatabaseError(
                msg,
            ) from e

    def _list_definitions(self, table_name: str, model_class: type) -> list[BaseModel]:
        """Lists all definitions of a given model_class from the specified metadata table."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        definitions = []
        try:
            cursor = self.conn.execute(f"SELECT definition FROM {table_name}")
            for row in cursor:
                definitions.append(model_class.model_validate_json(row["definition"]))
            return definitions
        except sqlite3.Error as e:
            msg = f"Error listing definitions from {table_name}: {e}"
            raise DatabaseError(
                msg,
            ) from e
        except json.JSONDecodeError as e:
            msg = f"Error decoding JSON for definitions from {table_name}: {e}"
            raise SchemaError(
                msg,
            ) from e

    # ObjectTypeDefinition
    def save_object_type_definition(self, otd: ObjectTypeDefinition) -> None:
        """Saves an ObjectTypeDefinition to the metadata table."""
        self._save_definition(self._META_TABLE_OBJECT_TYPES, otd.name, otd)

    def load_object_type_definition(self, name: str) -> Optional[ObjectTypeDefinition]:
        """Loads an ObjectTypeDefinition from the metadata table."""
        return self._load_definition(
            self._META_TABLE_OBJECT_TYPES, name, ObjectTypeDefinition,
        )  # type: ignore

    def delete_object_type_definition(self, name: str) -> bool:
        """Deletes an ObjectTypeDefinition from the metadata table."""
        return self._delete_definition(self._META_TABLE_OBJECT_TYPES, name)

    def list_object_type_definitions(self) -> list[ObjectTypeDefinition]:
        """Lists all ObjectTypeDefinitions from the metadata table."""
        return self._list_definitions(
            self._META_TABLE_OBJECT_TYPES, ObjectTypeDefinition,
        )  # type: ignore

    # EmbeddingDefinition
    def save_embedding_definition(self, ed: EmbeddingDefinition) -> None:
        """Saves an EmbeddingDefinition to the metadata table."""
        self._save_definition(self._META_TABLE_EMBEDDING_DEFS, ed.name, ed)

    def load_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:
        """Loads an EmbeddingDefinition from the metadata table."""
        return self._load_definition(
            self._META_TABLE_EMBEDDING_DEFS, name, EmbeddingDefinition,
        )  # type: ignore

    def delete_embedding_definition(self, name: str) -> bool:
        """Deletes an EmbeddingDefinition from the metadata table."""
        return self._delete_definition(self._META_TABLE_EMBEDDING_DEFS, name)

    def list_embedding_definitions(self) -> list[EmbeddingDefinition]:
        """Lists all EmbeddingDefinitions from the metadata table."""
        return self._list_definitions(
            self._META_TABLE_EMBEDDING_DEFS, EmbeddingDefinition,
        )  # type: ignore

    # RelationTypeDefinition
    def save_relation_type_definition(self, rtd: RelationTypeDefinition) -> None:
        """Saves a RelationTypeDefinition to the metadata table."""
        self._save_definition(self._META_TABLE_RELATION_TYPES, rtd.name, rtd)

    def load_relation_type_definition(
        self, name: str,
    ) -> Optional[RelationTypeDefinition]:
        """Loads a RelationTypeDefinition from the metadata table."""
        return self._load_definition(
            self._META_TABLE_RELATION_TYPES, name, RelationTypeDefinition,
        )  # type: ignore

    def delete_relation_type_definition(self, name: str) -> bool:
        """Deletes a RelationTypeDefinition from the metadata table."""
        return self._delete_definition(self._META_TABLE_RELATION_TYPES, name)

    def list_relation_type_definitions(self) -> list[RelationTypeDefinition]:
        """Lists all RelationTypeDefinitions from the metadata table."""
        return self._list_definitions(
            self._META_TABLE_RELATION_TYPES, RelationTypeDefinition,
        )  # type: ignore

    # --- Schema Management (Object Types) ---
    def _map_property_type_to_sqlite(self, prop_type: PropertyDataType) -> str:
        mapping = {
            PropertyDataType.TEXT: "TEXT",
            PropertyDataType.INTEGER: "INTEGER",
            PropertyDataType.FLOAT: "REAL",
            PropertyDataType.BOOLEAN: "INTEGER",  # 0 or 1
            PropertyDataType.DATETIME: "TEXT",  # Store as ISO format string
            PropertyDataType.BLOB: "BLOB",
            PropertyDataType.JSON: "TEXT",  # Store as JSON string
            PropertyDataType.UUID: "TEXT",  # Store as string
        }
        if prop_type not in mapping:
            msg = f"Unsupported property data type for SQLite: {prop_type}"
            raise SchemaError(msg)
        return mapping[prop_type]

    def _get_safe_table_name(self, object_type_name: str) -> str:
        # Basic sanitization, can be expanded. Using prefix to avoid SQL keyword clashes.
        return f"ot_{object_type_name.lower()}"

    def create_object_type_table(self, otd: ObjectTypeDefinition) -> None:
        """Creates a new SQLite table based on an ObjectTypeDefinition."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)

        table_name = self._get_safe_table_name(otd.name)
        columns = []

        # MemoryInstance base fields
        columns.append("id TEXT PRIMARY KEY")  # UUID stored as TEXT
        columns.append("weight REAL NOT NULL")
        columns.append("upsert_date TEXT NOT NULL")  # Store as ISO format string

        # Properties from ObjectTypeDefinition
        for prop in otd.properties:
            col_def = (
                f'"{prop.name}" {self._map_property_type_to_sqlite(prop.data_type)}'
            )
            if (
                prop.is_primary_key
            ):  # Note: 'id' is already PK. This handles explicit PKs if design
                # changes.
                # For now, we assume 'id' from MemoryInstance is the true PK.
                # If a property is marked is_primary_key, it should ideally be the 'id' field.
                # If not, it implies a composite key or alternative PK,
                # which needs careful handling.
                # Current design: 'id' is the PK. If another prop is PK,
                # it's likely an error or needs specific logic.
                # We will make it UNIQUE and NOT NULL if it's marked as PK but not 'id'.
                if prop.name.lower() != "id":  # 'id' is already the PK
                    col_def += " UNIQUE NOT NULL"
            else:  # Not a primary key property
                if not prop.is_nullable:
                    col_def += " NOT NULL"
                if prop.is_unique:
                    col_def += " UNIQUE"
            columns.append(col_def)

        create_table_sql = (
            f"CREATE TABLE IF NOT EXISTS \"{table_name}\" ({', '.join(columns)})"
        )

        indices_sql = []
        for prop in otd.properties:
            if prop.is_indexed:
                index_name = f"idx_{table_name}_{prop.name}"
                indices_sql.append(
                    f'CREATE INDEX IF NOT EXISTS "{index_name}" ON '
                    f'"{table_name}" ("{prop.name}")',
                )

        try:
            with self.conn:
                self.conn.execute(create_table_sql)
                for index_sql in indices_sql:
                    self.conn.execute(index_sql)
        except sqlite3.Error as e:
            msg = (
                f"Error creating table or indices for object type '{otd.name}' "
                f"(table: {table_name}): {e}"
            )
            raise SchemaError(
                msg,
            ) from e

    def drop_object_type_table(self, object_type_name: str) -> None:
        """Drops an SQLite table corresponding to an object type."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        table_name = self._get_safe_table_name(object_type_name)
        try:
            with self.conn:
                self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        except sqlite3.Error as e:
            msg = (
                f"Error dropping table for object type '{object_type_name}' "
                f"(table: {table_name}): {e}"
            )
            raise SchemaError(
                msg,
            ) from e

    # --- Object Instance Operations ---
    def _serialize_value(self, value: Any, data_type: PropertyDataType) -> Any:
        """Serializes a Python value to its SQLite-compatible representation."""
        result: Any
        if value is None:
            result = None
        elif data_type == PropertyDataType.UUID:
            result = str(value)
        elif data_type == PropertyDataType.DATETIME:
            if isinstance(value, datetime):
                result = value.isoformat()
            else:
                result = str(value)  # Or raise error if not datetime
        elif data_type == PropertyDataType.JSON:
            result = json.dumps(value)
        elif data_type == PropertyDataType.BOOLEAN:
            result = 1 if value else 0
        elif data_type == PropertyDataType.FLOAT and isinstance(
            value, Decimal,
        ):  # For condecimal
            result = float(value)
        else:
            result = value
        return result

    def _deserialize_value(self, value: Any, data_type: PropertyDataType) -> Any:
        """Deserializes a value from SQLite to its Python representation."""
        if value is None:
            return None
        if data_type == PropertyDataType.UUID:
            return UUID(value)
        if data_type == PropertyDataType.DATETIME:
            return datetime.fromisoformat(value)
        if data_type == PropertyDataType.JSON:
            return json.loads(value)
        if data_type == PropertyDataType.BOOLEAN:
            return bool(value)
        return value

    def _row_to_object_instance(
        self, row: sqlite3.Row, otd: ObjectTypeDefinition,
    ) -> ObjectInstance:
        """Converts a sqlite3.Row to an ObjectInstance."""
        props = {}
        for prop_def in otd.properties:
            props[prop_def.name] = self._deserialize_value(
                row[prop_def.name], prop_def.data_type,
            )

        return ObjectInstance(
            id=UUID(row["id"]),
            weight=Decimal(str(row["weight"])),  # SQLite REAL to Decimal
            upsert_date=datetime.fromisoformat(row["upsert_date"]),
            object_type_name=otd.name,
            properties=props,
        )

    def add_object_instance(self, instance: ObjectInstance) -> None:
        """Adds a new object instance to the appropriate SQLite table."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        otd = self.load_object_type_definition(instance.object_type_name)
        if not otd:
            msg = (
                f"ObjectTypeDefinition '{instance.object_type_name}' not found for "
                f"instance {instance.id}"
            )
            raise SchemaError(
                msg,
            )

        table_name = self._get_safe_table_name(instance.object_type_name)

        cols = ["id", "weight", "upsert_date"] + [p.name for p in otd.properties]
        placeholders = ["?"] * len(cols)

        values = [
            str(instance.id),
            float(instance.weight),  # Store Decimal as REAL
            instance.upsert_date.isoformat(),
        ]
        for prop_def in otd.properties:
            values.append(
                self._serialize_value(
                    instance.properties.get(prop_def.name), prop_def.data_type,
                ),
            )

        sql = (
            f"INSERT INTO \"{table_name}\" ({', '.join(f'"{c}"' for c in cols)}) "
            f"VALUES ({', '.join(placeholders)})"
        )

        try:
            with self.conn:
                self.conn.execute(sql, tuple(values))
        except sqlite3.IntegrityError as e:
            msg = (
                f"Integrity error adding instance {instance.id} to "
                f"'{table_name}': {e}. Check for uniqueness constraints."
            )
            raise InstanceError(
                msg,
            ) from e
        except sqlite3.Error as e:
            msg = f"Error adding instance {instance.id} to '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def get_object_instance(
        self, object_type_name: str, instance_id: UUID,
    ) -> Optional[ObjectInstance]:
        """Retrieves an object instance by its type and ID."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            msg = f"ObjectTypeDefinition '{object_type_name}' not found."
            raise SchemaError(msg)

        table_name = self._get_safe_table_name(object_type_name)
        sql = f'SELECT * FROM "{table_name}" WHERE id = ?'

        try:
            cursor = self.conn.execute(sql, (str(instance_id),))
            row = cursor.fetchone()
            if row:
                return self._row_to_object_instance(row, otd)
            return None
        except sqlite3.Error as e:
            msg = f"Error getting instance {instance_id} from '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def update_object_instance(self, instance: ObjectInstance) -> None:
        """Updates an existing object instance in the SQLite table."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        otd = self.load_object_type_definition(instance.object_type_name)
        if not otd:
            msg = (
                f"ObjectTypeDefinition '{instance.object_type_name}' not found for "
                f"instance {instance.id}"
            )
            raise SchemaError(
                msg,
            )

        table_name = self._get_safe_table_name(instance.object_type_name)

        set_clauses = ["weight = ?", "upsert_date = ?"]
        values = [float(instance.weight), instance.upsert_date.isoformat()]

        for prop_def in otd.properties:
            set_clauses.append(f'"{prop_def.name}" = ?')
            values.append(
                self._serialize_value(
                    instance.properties.get(prop_def.name), prop_def.data_type,
                ),
            )

        values.append(str(instance.id))  # For WHERE clause

        sql = f"UPDATE \"{table_name}\" SET {', '.join(set_clauses)} WHERE id = ?"

        try:
            with self.conn:
                cursor = self.conn.execute(sql, tuple(values))
                if cursor.rowcount == 0:
                    msg = f"Instance {instance.id} not found in '{table_name}' for update."
                    raise InstanceError(
                        msg,
                    )
        except sqlite3.IntegrityError as e:
            msg = (
                f"Integrity error updating instance {instance.id} "
                f"in '{table_name}': {e}."
            )
            raise InstanceError(
                msg,
            ) from e
        except sqlite3.Error as e:
            msg = f"Error updating instance {instance.id} in '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def delete_object_instance(self, object_type_name: str, instance_id: UUID) -> bool:
        """Deletes an object instance from the SQLite table. Returns True if deleted."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        # OTD check not strictly necessary for delete,
        # but good for consistency if table name depends on it
        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            # If OTD doesn't exist, table likely doesn't either, or is orphaned.
            # Depending on strictness, could raise SchemaError or just try to delete.
            # For now, let's assume if OTD is gone, table should be too.
            # However, the request is to delete an instance, so the table might still exist.
            pass

        table_name = self._get_safe_table_name(object_type_name)
        sql = f'DELETE FROM "{table_name}" WHERE id = ?'

        try:
            with self.conn:
                cursor = self.conn.execute(sql, (str(instance_id),))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            # If table doesn't exist, sqlite3 will raise an OperationalError
            if "no such table" in str(e).lower():
                return False  # Effectively, instance is not there
            msg = f"Error deleting instance {instance_id} from '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def query_object_instances(  # pylint: disable=R0914
        self,
        object_type_name: str,
        conditions: dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None,  # Added to match find_object_instances
    ) -> list[ObjectInstance]:
        """Queries object instances based on a dictionary of conditions."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            msg = f"ObjectTypeDefinition '{object_type_name}' not found."
            raise SchemaError(msg)

        table_name = self._get_safe_table_name(object_type_name)

        where_clauses = []
        query_values = []

        # Find PropertyDefinition for each condition key to get data_type for serialization
        prop_defs_map = {p.name: p for p in otd.properties}
        # Also consider base fields like id, weight, upsert_date
        base_fields_types = {
            "id": PropertyDataType.UUID,
            "weight": PropertyDataType.FLOAT,  # Stored as REAL
            "upsert_date": PropertyDataType.DATETIME,
        }

        if conditions:  # Ensure conditions is not None
            for key, value in conditions.items():
                # Determine data_type for serialization
                data_type: Optional[PropertyDataType] = None
                if key in prop_defs_map:
                    data_type = prop_defs_map[key].data_type
                elif key in base_fields_types:
                    data_type = base_fields_types[key]  # type: ignore
                else:
                    msg = (
                        f"Condition key '{key}' is not a defined property or "
                        f"base field for object type '{object_type_name}'."
                    )
                    raise SchemaError(
                        msg,
                    )

                where_clauses.append(f'"{key}" = ?')
                query_values.append(
                    self._serialize_value(value, data_type),  # type: ignore
                )

        sql = f'SELECT * FROM "{table_name}"'
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        if limit is not None:
            sql += " LIMIT ?"
            query_values.append(limit)
        if offset is not None:  # Added offset handling
            sql += " OFFSET ?"
            query_values.append(offset)

        instances = []
        try:
            cursor = self.conn.execute(sql, tuple(query_values))
            for row in cursor:
                instances.append(self._row_to_object_instance(row, otd))
            return instances
        except sqlite3.Error as e:
            msg = f"Error querying instances from '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    # --- Placeholder/Not Implemented for methods not directly part of this task's SQLite focus ---

    def create_object_type(self, definition: ObjectTypeDefinition) -> None:
        # This method is part of BaseDBAdapter, but for SQLite, it's a combination of:
        # 1. Storing definition (handled by save_object_type_definition)
        # 2. Creating the actual SQL table (handled by create_object_type_table)
        # The GrizabellaDBManager will coordinate these.
        self.save_object_type_definition(definition)
        self.create_object_type_table(definition)

    def get_object_type(self, name: str) -> Optional[ObjectTypeDefinition]:
        return self.load_object_type_definition(name)

    def delete_object_type(self, name: str) -> None:
        # Coordinated by GrizabellaDBManager
        self.drop_object_type_table(name)
        self.delete_object_type_definition(name)

    def list_object_types(self) -> list[str]:
        # Returns names of defined object types
        defs = self.list_object_type_definitions()
        return [d.name for d in defs]

    # Embedding and Relation instance methods are typically not for SQLite in a tri-layer system
    # or would be very simple if SQLite were the sole store.
    # For this task, we focus on schema definition storage for them.

    def upsert_embedding_instance(self, instance: Any) -> Any:
        msg = "SQLiteAdapter.upsert_embedding_instance is not typically used for vector storage."
        raise NotImplementedError(
            msg,
        )

    def get_embedding_instance(
        self, embedding_definition_name: str, object_instance_id: UUID,
    ) -> Optional[Any]:
        msg = "SQLiteAdapter.get_embedding_instance is not typically used."
        raise NotImplementedError(
            msg,
        )

    def find_similar_embeddings(
        self, embedding_definition_name: str, vector: list[float], top_k: int = 5,
    ) -> list[Any]:
        msg = "SQLiteAdapter.find_similar_embeddings is not applicable for SQLite."
        raise NotImplementedError(
            msg,
        )

    def create_relation_type(self, definition: RelationTypeDefinition) -> None:
        self.save_relation_type_definition(definition)
        # Actual relation table creation might be needed if SQLite stores relations.
        # For now, only definition persistence.

    def get_relation_type(self, name: str) -> Optional[RelationTypeDefinition]:
        return self.load_relation_type_definition(name)

    def add_relation_instance(self, instance: RelationInstance) -> RelationInstance:
        """Placeholder for adding relation instance metadata to SQLite.
        Currently, Grizabella primarily uses Kuzu for relation storage and querying.
        This method can be expanded if SQLite needs to store relation metadata.
        """
        return instance

    def upsert_relation_instance(
        self, instance: RelationInstance, rtd: Optional[RelationTypeDefinition] = None,
    ) -> (
        RelationInstance
    ):  # pylint: disable=arguments-differ # Changed type hint from Any
        """Placeholder for upserting relation instance metadata to SQLite."""
        return instance

    def get_relation_instance(
        self, relation_type_name: str, relation_id: UUID,
    ) -> Optional[RelationInstance]:  # Changed type hint
        """Placeholder for getting relation instance metadata from SQLite."""
        return None

    def find_relation_instances(  # pylint: disable=R0913, R0917
        self,
        relation_type_name: Optional[str] = None,
        source_object_id: Optional[UUID] = None,
        target_object_id: Optional[UUID] = None,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[RelationInstance]:  # Changed type hint
        """Placeholder for finding relation instance metadata from SQLite."""
        return []

    def delete_relation_instance(
        self, relation_type_name: str, relation_id: UUID,
    ) -> bool:
        """Placeholder for deleting relation instance metadata from SQLite."""
        return True

    # BaseDBAdapter abstract methods that need concrete implementation
    # or to be managed by GrizabellaDBManager
    def update_object_type(self, definition: ObjectTypeDefinition) -> None:
        # SQL ALTER TABLE is complex. A common strategy is:
        # 1. Save new definition.
        # 2. Create new table with new schema.
        # 3. Copy data from old table to new table (transforming as needed).
        # 4. Drop old table.
        # 5. Rename new table to old table name.
        # This is a complex operation and often handled with migration tools.
        # For now, just saving the definition.
        # Actual table alteration is out of scope for this initial pass.
        self.save_object_type_definition(definition)
        # print(f"Warning: Object type definition '{definition.name}' updated in metadata. "
        #       "Live table schema alteration is not yet implemented in SQLiteAdapter.")
        msg = "SQLiteAdapter.update_object_type schema migration not fully implemented."
        raise NotImplementedError(
            msg,
        )

    def upsert_object_instance(
        self, instance: ObjectInstance,
    ) -> ObjectInstance:  # pylint: disable=R0914
        # Attempt to update, if it fails (e.g. rowcount is 0), then insert.
        # This is a common pattern for upsert.
        # More robust upsert: INSERT ... ON CONFLICT (id) DO UPDATE SET ...
        logger.info(f"SQLiteAdapter: upsert_object_instance called in thread ID: {threading.get_ident()} for instance ID: {instance.id}, type: {instance.object_type_name}")
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)

        otd = self.load_object_type_definition(instance.object_type_name)
        if not otd:
            msg = (
                f"ObjectTypeDefinition '{instance.object_type_name}' not found for "
                f"instance {instance.id}"
            )
            raise SchemaError(
                msg,
            )

        table_name = self._get_safe_table_name(instance.object_type_name)

        cols = ["id", "weight", "upsert_date"] + [p.name for p in otd.properties]

        insert_values = [
            str(instance.id),
            float(instance.weight),
            instance.upsert_date.isoformat(),
        ]
        for prop_def in otd.properties:
            insert_values.append(
                self._serialize_value(
                    instance.properties.get(prop_def.name), prop_def.data_type,
                ),
            )

        # set_clauses_for_update = ["weight = ?", "upsert_date = ?"]
        # Not used with ON CONFLICT excluded
        # update_values_for_conflict = [float(instance.weight), instance.upsert_date.isoformat()]
        # Not used

        # for prop_def in otd.properties: # Not used
        #    set_clauses_for_update.append(f"\"{prop_def.name}\" = ?")
        #    update_values_for_conflict.append(
        #       self._serialize_value(instance.properties.get(prop_def.name), prop_def.data_type)
        # )

        # SQL for ON CONFLICT DO UPDATE
        # Exclude 'id' from the SET part of ON CONFLICT
        update_set_string = ", ".join(
            ["weight = excluded.weight", "upsert_date = excluded.upsert_date"]
            + [f'"{p.name}" = excluded."{p.name}"' for p in otd.properties],
        )

        sql = (
            f"INSERT INTO \"{table_name}\" ({', '.join(f'"{c}"' for c in cols)}) "
            f"VALUES ({', '.join(['?'] * len(cols))}) "
            f"ON CONFLICT(id) DO UPDATE SET {update_set_string}"
        )

        try:
            with self.conn:
                self.conn.execute(sql, tuple(insert_values))
                self.conn.commit() # Explicit commit
                logger.debug(f"SQLiteAdapter: Explicit commit called for instance ID: {instance.id}")
            return instance  # Return the input instance as it should now be in the DB
        except sqlite3.IntegrityError as e:
            msg = (
                f"Integrity error upserting instance {instance.id} "
                f"in '{table_name}': {e}."
            )
            raise InstanceError(
                msg,
            ) from e
        except sqlite3.Error as e:
            msg = f"Error upserting instance {instance.id} in '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def find_object_instances(  # pylint: disable=R0914
        self,
        object_type_name: str,
        query: Optional[
            dict[str, Any]
        ] = None,  # Renamed from 'conditions' to match BaseDBAdapter
        limit: Optional[int] = None,
        offset: Optional[int] = None,  # Added offset
    ) -> list[ObjectInstance]:
        """Finds object instances based on a query dictionary, with limit and offset."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            msg = f"ObjectTypeDefinition '{object_type_name}' not found."
            raise SchemaError(msg)

        table_name = self._get_safe_table_name(object_type_name)
        where_clauses = []
        query_values = []

        prop_defs_map = {p.name: p for p in otd.properties}
        base_fields_types = {
            "id": PropertyDataType.UUID,
            "weight": PropertyDataType.FLOAT,
            "upsert_date": PropertyDataType.DATETIME,
        }

        if query:
            for key, value in query.items():
                data_type: Optional[PropertyDataType] = None
                if key in prop_defs_map:
                    data_type = prop_defs_map[key].data_type
                elif key in base_fields_types:
                    data_type = base_fields_types[key]  # type: ignore
                else:
                    msg = (
                        f"Query key '{key}' is not a defined property or "
                        f"base field for '{object_type_name}'."
                    )
                    raise SchemaError(
                        msg,
                    )

                where_clauses.append(f'"{key}" = ?')
                query_values.append(
                    self._serialize_value(value, data_type),  # type: ignore
                )

        sql = f'SELECT * FROM "{table_name}"'
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        limit_offset_values = []
        if limit is not None:
            sql += " LIMIT ?"
            limit_offset_values.append(limit)
        if offset is not None:
            sql += " OFFSET ?"
            limit_offset_values.append(offset)

        final_query_values = query_values + limit_offset_values
        instances = []
        try:
            print(f"Executing SQL: {sql} with values: {final_query_values}")
            cursor = self.conn.execute(sql, tuple(final_query_values))
            rows = cursor.fetchall()
            logger.debug(f"Raw rows from DB: {rows}")
            for row in rows:
                instances.append(self._row_to_object_instance(row, otd))
            return instances
        except sqlite3.Error as e:
            msg = f"Error finding instances from '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def add_embedding_definition(self, definition: EmbeddingDefinition) -> None:
        """Saves an embedding definition (metadata only in SQLite)."""
        self.save_embedding_definition(definition)

    def get_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:
        """Loads an embedding definition (metadata only from SQLite)."""
        return self.load_embedding_definition(name)

    def find_object_ids_by_properties(
        self,
        object_type_name: str,
        filters: list[RelationalFilter],
        initial_ids: Optional[list[UUID]] = None,
    ) -> list[UUID]:
        """Finds object instance IDs based on property filters, optionally refining an initial list of IDs."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            msg = f"ObjectTypeDefinition '{object_type_name}' not found."
            raise SchemaError(msg)

        table_name = self._get_safe_table_name(object_type_name)
        prop_defs_map = {p.name: p for p in otd.properties}
        base_fields_types = {
            "id": PropertyDataType.UUID,
            "weight": PropertyDataType.FLOAT,
            "upsert_date": PropertyDataType.DATETIME,
        }

        where_clauses: list[str] = []
        query_values: list[Any] = []

        if filters:
            for r_filter in filters:
                prop_name = r_filter.property_name
                data_type: Optional[PropertyDataType] = None
                if prop_name in prop_defs_map:
                    data_type = prop_defs_map[prop_name].data_type
                elif prop_name in base_fields_types:
                    data_type = base_fields_types[prop_name]  # type: ignore
                else:
                    msg = f"Filter property '{prop_name}' not found for object type '{object_type_name}'."
                    raise SchemaError(
                        msg,
                    )

                # Basic operator mapping, can be expanded
                # Ensure operator is valid for the data type
                # For 'IN' operator, value should be a list/tuple
                if r_filter.operator.upper() == "IN":
                    if not isinstance(r_filter.value, (list, tuple)):
                        msg = f"Value for IN operator on property '{prop_name}' must be a list or tuple."
                        raise ValueError(
                            msg,
                        )
                    if not r_filter.value:  # Empty IN list
                        where_clauses.append("0 = 1")  # Always false
                        continue
                    placeholders = ", ".join(["?"] * len(r_filter.value))
                    where_clauses.append(
                        f'"{prop_name}" {r_filter.operator.upper()} ({placeholders})',
                    )
                    for val_item in r_filter.value:
                        query_values.append(self._serialize_value(val_item, data_type))  # type: ignore
                else:
                    where_clauses.append(f'"{prop_name}" {r_filter.operator} ?')
                    query_values.append(self._serialize_value(r_filter.value, data_type))  # type: ignore

        if initial_ids is not None:
            if not initial_ids:  # If initial_ids is empty, no results can match
                return []
            id_placeholders = ", ".join(["?"] * len(initial_ids))
            where_clauses.append(f"id IN ({id_placeholders})")
            for obj_id in initial_ids:
                query_values.append(str(obj_id))

        sql = f'SELECT id FROM "{table_name}"'
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        found_ids: list[UUID] = []
        try:
            cursor = self.conn.execute(sql, tuple(query_values))
            for row in cursor:
                found_ids.append(UUID(row["id"]))
            return found_ids
        except sqlite3.Error as e:
            msg = f"Error finding object IDs from '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def get_objects_by_ids(
        self, object_type_name: str, ids: list[UUID],
    ) -> list[ObjectInstance]:
        """Retrieves multiple object instances by their type and a list of IDs."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)
        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            msg = f"ObjectTypeDefinition '{object_type_name}' not found."
            raise SchemaError(msg)

        if not ids:
            return []

        table_name = self._get_safe_table_name(object_type_name)
        id_placeholders = ", ".join(["?"] * len(ids))
        sql = f'SELECT * FROM "{table_name}" WHERE id IN ({id_placeholders})'

        str_ids = [str(obj_id) for obj_id in ids]

        instances: list[ObjectInstance] = []
        try:
            cursor = self.conn.execute(sql, tuple(str_ids))
            for row in cursor:
                instances.append(self._row_to_object_instance(row, otd))
            return instances
        except sqlite3.Error as e:
            msg = f"Error getting instances by IDs from '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    def get_all_object_ids_for_type(self, object_type_name: str) -> list[UUID]:
        """Retrieve all object instance IDs for a given object type."""
        if not self.conn:
            msg = "SQLite connection not established."
            raise DatabaseError(msg)

        # OTD check is good practice, though not strictly needed if table name is derived directly
        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            # If OTD doesn't exist, the table shouldn't either, or it's an orphaned table.
            # Returning empty list is reasonable as no valid objects of this type exist.
            logger.warning(
                f"ObjectTypeDefinition '{object_type_name}' not found when trying to get all IDs. "
                "Assuming no instances exist or table is missing.",
            )
            return []

        table_name = self._get_safe_table_name(object_type_name)
        sql = f'SELECT id FROM "{table_name}"'

        found_ids: list[UUID] = []
        try:
            cursor = self.conn.execute(sql)
            for row in cursor:
                found_ids.append(UUID(row["id"]))
            return found_ids
        except sqlite3.Error as e:
            # If table doesn't exist, sqlite3 will raise an OperationalError
            if "no such table" in str(e).lower():
                logger.warning(
                    f"Table '{table_name}' for ObjectType '{object_type_name}' not found. Returning empty list of IDs.",
                )
                return []
            msg = f"Error getting all IDs from '{table_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e
