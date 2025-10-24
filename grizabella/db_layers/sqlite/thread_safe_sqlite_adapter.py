"""Thread-safe SQLite adapter with proper connection isolation.

This module provides a thread-safe implementation of the SQLite adapter
that addresses the threading issues causing memory leaks. It uses thread-local
storage to ensure each thread has its own connection while sharing the
database file safely.
"""

import logging
import sqlite3
import threading
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from grizabella.core.exceptions import DatabaseError, InstanceError, SchemaError
from grizabella.core.models import (
    EmbeddingDefinition,
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDataType,
    RelationInstance,
    RelationTypeDefinition,
)
from grizabella.core.query_models import RelationalFilter # Added for new methods
from grizabella.db_layers.sqlite.sqlite_adapter import SQLiteAdapter
from grizabella.db_layers.common.base_adapter import BaseDBAdapter

logger = logging.getLogger(__name__)


class ThreadSafeSQLiteAdapter(SQLiteAdapter):
    """Thread-safe SQLite adapter with proper connection isolation.
    
    This adapter addresses the threading issues in the original SQLiteAdapter by:
    - Using thread-local storage for connections
    - Proper connection lifecycle management per thread
    - Enhanced error handling and logging
    """
    
    _META_TABLE_OBJECT_TYPES = "_grizabella_object_types"
    _META_TABLE_EMBEDDING_DEFS = "_grizabella_embedding_definitions"
    _META_TABLE_RELATION_TYPES = "_grizabella_relation_types"
    
    def __init__(self, db_path: str, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize the thread-safe SQLite adapter.
        
        Args:
            db_path: Path to the SQLite database
            config: Optional configuration dictionary
        """
        thread_id = threading.get_ident()
        logger.info(f"ThreadSafeSQLiteAdapter: Initializing in thread ID: {thread_id} for db: {db_path}")
        
        self.db_path = db_path
        self.config = config or {}
        self._lock = threading.RLock()
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Initialize metadata tables (this can be done once since it's schema)
        self._init_meta_tables()
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Get thread-local connection.
        
        Returns:
            sqlite3.Connection: Thread-local database connection
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new thread-local connection.
        
        Ensures that the parent directory for the database file exists before
        attempting to connect. This prevents errors when using new database paths
        that don't have their parent directories created yet.
        
        Returns:
            sqlite3.Connection: New database connection for current thread
            
        Raises:
            DatabaseError: If unable to create parent directory or connect to database
        """
        import os
        from pathlib import Path
        
        thread_id = threading.get_ident()
        logger.info(f"ThreadSafeSQLiteAdapter: Creating connection for thread {thread_id}")
        
        # Ensure parent directory exists before attempting to connect
        db_path_obj = Path(self.db_path)
        parent_dir = db_path_obj.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"ThreadSafeSQLiteAdapter: Created parent directory {parent_dir} for database")
            except OSError as e:
                msg = f"Unable to create parent directory {parent_dir} for database {self.db_path}: {e}"
                raise DatabaseError(msg) from e
        
        try:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            logger.info(f"ThreadSafeSQLiteAdapter: sqlite3.connect successful for thread {thread_id}. Connection object: {conn}")
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        except sqlite3.Error as e:
            msg = f"SQLite connection error to '{self.db_path}': {e}"
            raise DatabaseError(msg) from e
    
    def _init_meta_tables(self) -> None:
        """Initializes tables for storing Grizabella schema definitions if they don't exist.
        
        Ensures that the parent directory for the database file exists before
        attempting to connect. This prevents errors when using new database paths
        that don't have their parent directories created yet.
        """
        import os
        from pathlib import Path
        
        # Ensure parent directory exists before attempting to connect
        db_path_obj = Path(self.db_path)
        parent_dir = db_path_obj.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"ThreadSafeSQLiteAdapter: Created parent directory {parent_dir} for database")
            except OSError as e:
                msg = f"Unable to create parent directory {parent_dir} for database {self.db_path}: {e}"
                raise DatabaseError(msg) from e
        
        # Create a temporary connection to initialize metadata tables
        temp_conn = None
        try:
            temp_conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            temp_conn.row_factory = sqlite3.Row
            temp_conn.execute("PRAGMA foreign_keys = ON;")
            
            with temp_conn:
                temp_conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._META_TABLE_OBJECT_TYPES} (
                        name TEXT PRIMARY KEY,
                        definition TEXT NOT NULL -- JSON string of ObjectTypeDefinition
                    )
                """,
                )
                temp_conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._META_TABLE_EMBEDDING_DEFS} (
                        name TEXT PRIMARY KEY,
                        definition TEXT NOT NULL -- JSON string of EmbeddingDefinition
                    )
                """,
                )
                temp_conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._META_TABLE_RELATION_TYPES} (
                        name TEXT PRIMARY KEY,
                        definition TEXT NOT NULL -- JSON string of RelationTypeDefinition
                    )
                """,
                )
        except sqlite3.Error as e:
            msg = f"SQLite error initializing metadata tables: {e}"
            raise DatabaseError(msg) from e
        finally:
            if temp_conn:
                temp_conn.close()
    
    def close(self) -> None:
        """Close thread-local connection."""
        thread_id = threading.get_ident()
        logger.info(f"ThreadSafeSQLiteAdapter: close() called in thread ID: {thread_id} for db: {self.db_path}")
        
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
                logger.info(f"ThreadSafeSQLiteAdapter: Connection closed for thread {thread_id}")
                # Remove the connection from thread-local storage
                delattr(self._local, 'conn')
            except sqlite3.Error as e:
                logger.error(f"ThreadSafeSQLiteAdapter: sqlite3.Error during close for {self.db_path}: {e}", exc_info=True)
                msg = f"SQLite error closing connection: {e}"
                raise DatabaseError(msg) from e
        else:
            logger.debug(f"ThreadSafeSQLiteAdapter: No connection to close for thread {thread_id}")
    
    def _save_definition(
        self, table_name: str, name: str, definition: BaseModel,
    ) -> None:
        """Saves a Pydantic model definition as JSON into the specified metadata table."""
        try:
            with self.conn:
                self.conn.execute(
                    f"INSERT OR REPLACE INTO {table_name} (name, definition) VALUES (?, ?)",
                    (name, definition.model_dump_json()),
                )
        except sqlite3.Error as e:
            msg = f"Error saving definition '{name}' to {table_name}: {e}"
            raise DatabaseError(msg) from e

    def _load_definition(
        self, table_name: str, name: str, model_class: type,
    ) -> Optional[BaseModel]:
        """Loads a Pydantic model definition from JSON stored in the specified metadata table."""
        logger.info(f"ThreadSafeSQLiteAdapter: _load_definition called in thread ID: {threading.get_ident()} for table: {table_name}, name: {name}")
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
            raise DatabaseError(msg) from e
        except (ValueError, TypeError) as e:  # Updated from json.JSONDecodeError
            msg = f"Error decoding JSON for definition '{name}' from {table_name}: {e}"
            raise SchemaError(msg) from e

    def _delete_definition(self, table_name: str, name: str) -> bool:
        """Deletes a definition from the specified metadata table. Returns True if deleted."""
        try:
            with self.conn:
                cursor = self.conn.execute(
                    f"DELETE FROM {table_name} WHERE name = ?", (name,),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            msg = f"Error deleting definition '{name}' from {table_name}: {e}"
            raise DatabaseError(msg) from e

    def _list_definitions(self, table_name: str, model_class: type) -> list[BaseModel]:
        """Lists all definitions of a given model_class from the specified metadata table."""
        definitions = []
        try:
            cursor = self.conn.execute(f"SELECT definition FROM {table_name}")
            for row in cursor:
                definitions.append(model_class.model_validate_json(row["definition"]))
            return definitions
        except sqlite3.Error as e:
            msg = f"Error listing definitions from {table_name}: {e}"
            raise DatabaseError(msg) from e
        except (ValueError, TypeError) as e: # Updated from json.JSONDecodeError
            msg = f"Error decoding JSON for definitions from {table_name}: {e}"
            raise SchemaError(msg) from e

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
            raise SchemaError(msg) from e

    def drop_object_type_table(self, object_type_name: str) -> None:
        """Drops an SQLite table corresponding to an object type."""
        table_name = self._get_safe_table_name(object_type_name)
        try:
            with self.conn:
                self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        except sqlite3.Error as e:
            msg = (
                f"Error dropping table for object type '{object_type_name}' "
                f"(table: {table_name}): {e}"
            )
            raise SchemaError(msg) from e

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
            import json
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
            import json
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
        otd = self.load_object_type_definition(instance.object_type_name)
        if not otd:
            msg = (
                f"ObjectTypeDefinition '{instance.object_type_name}' not found for "
                f"instance {instance.id}"
            )
            raise SchemaError(msg)

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
            raise InstanceError(msg) from e
        except sqlite3.Error as e:
            msg = f"Error adding instance {instance.id} to '{table_name}': {e}"
            raise DatabaseError(msg) from e

    def get_object_instance(
        self, object_type_name: str, instance_id: UUID,
    ) -> Optional[ObjectInstance]:
        """Retrieves an object instance by its type and ID."""
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
        except sqlite3.Error as e:
            msg = f"Error retrieving instance {instance_id} from '{table_name}': {e}"
            raise DatabaseError(msg) from e

    def update_object_instance(self, instance: ObjectInstance) -> None:
        """Updates an existing object instance in the SQLite table."""
        otd = self.load_object_type_definition(instance.object_type_name)
        if not otd:
            msg = (
                f"ObjectTypeDefinition '{instance.object_type_name}' not found for "
                f"instance {instance.id}"
            )
            raise SchemaError(msg)

        table_name = self._get_safe_table_name(instance.object_type_name)

        # Build SET clause for all properties
        set_parts = []
        values = []
        for prop_def in otd.properties:
            set_parts.append(f'"{prop_def.name}" = ?')
            values.append(
                self._serialize_value(
                    instance.properties.get(prop_def.name), prop_def.data_type,
                ),
            )

        # Add weight and upsert_date
        set_parts.append('weight = ?')
        values.append(float(instance.weight))
        set_parts.append('upsert_date = ?')
        values.append(instance.upsert_date.isoformat())

        # Add ID to the end for WHERE clause
        values.append(str(instance.id))

        sql = f'UPDATE "{table_name}" SET {", ".join(set_parts)} WHERE id = ?'

        try:
            with self.conn:
                cursor = self.conn.execute(sql, tuple(values))
                if cursor.rowcount == 0:
                    # If no rows were updated, the instance might not exist
                    # For upsert behavior, we should insert instead
                    self.add_object_instance(instance)
        except sqlite3.Error as e:
            msg = f"Error updating instance {instance.id} in '{table_name}': {e}"
            raise DatabaseError(msg) from e

    def delete_object_instance(self, object_type_name: str, instance_id: UUID) -> bool:
        """Deletes an object instance from the SQLite table. Returns True if deleted."""
        table_name = self._get_safe_table_name(object_type_name)
        sql = f'DELETE FROM "{table_name}" WHERE id = ?'

        try:
            with self.conn:
                cursor = self.conn.execute(sql, (str(instance_id),))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            msg = f"Error deleting instance {instance_id} from '{table_name}': {e}"
            raise DatabaseError(msg) from e

    def query_object_instances(  # pylint: disable=R0914
        self,
        object_type_name: str,
        query_dict: dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Queries object instances based on a dictionary of conditions."""
        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            msg = f"ObjectTypeDefinition '{object_type_name}' not found."
            raise SchemaError(msg)

        table_name = self._get_safe_table_name(object_type_name)

        where_clauses = ["1=1"]  # Start with a tautology
        params = []

        for key, value in query_dict.items():
            # Check if the property exists in the object type
            prop_exists = any(p.name == key for p in otd.properties)
            if not prop_exists and key not in ["id", "weight", "upsert_date"]:
                continue  # Skip unknown properties

            # For now, assume equality. Can be extended for other operators.
            where_clauses.append(f'"{key}" = ?')
            params.append(self._serialize_value(value, PropertyDataType.TEXT))  # Simplified

        where_clause = " AND ".join(where_clauses)

        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        offset_clause = f"OFFSET {offset}" if offset is not None else ""

        sql = (
            f'SELECT * FROM "{table_name}" WHERE {where_clause} '
            f"{limit_clause} {offset_clause}"
        )

        try:
            cursor = self.conn.execute(sql, tuple(params))
            instances = []
            for row in cursor:
                instances.append(self._row_to_object_instance(row, otd))
            return instances
        except sqlite3.Error as e:
            msg = f"Error querying instances from '{table_name}': {e}"
            raise DatabaseError(msg) from e

    def create_object_type(self, definition: ObjectTypeDefinition) -> None:
        """Creates an object type by creating the corresponding table."""
        self.create_object_type_table(definition)

    def delete_object_type(self, name: str) -> None:
        """Deletes an object type by dropping the corresponding table."""
        self.drop_object_type_table(name)

    def list_object_types(self) -> list[str]:
        """Lists all object type names by querying the metadata table."""
        try:
            cursor = self.conn.execute(f"SELECT name FROM {self._META_TABLE_OBJECT_TYPES}")
            return [row["name"] for row in cursor]
        except sqlite3.Error as e:
            msg = f"Error listing object types: {e}"
            raise DatabaseError(msg) from e

    def upsert_object_instance(self, instance: ObjectInstance) -> ObjectInstance:
        """Upserts an object instance (inserts if new, updates if exists)."""
        logger.info(f"ThreadSafeSQLiteAdapter: upsert_object_instance called in thread ID: {threading.get_ident()} for instance ID: {instance.id}, type: {instance.object_type_name}")
        
        # First, try to get the existing instance
        existing = self.get_object_instance(instance.object_type_name, instance.id)
        
        if existing:
            # Instance exists, update it
            self.update_object_instance(instance)
        else:
            # Instance doesn't exist, add it
            self.add_object_instance(instance)
        
        # Return the instance as provided
        return instance

    def find_object_instances(  # pylint: disable=R0914
        self,
        object_type_name: str,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Finds object instances based on a query dictionary, with limit and offset."""
        return self.query_object_instances(object_type_name, query or {}, limit, offset)

    def find_object_ids_by_properties(
        self,
        object_type_name: str,
        filters: list[RelationalFilter],
        initial_ids: Optional[list[UUID]] = None,
    ) -> list[UUID]:
        """Finds object instance IDs based on property filters, optionally refining an initial list of IDs."""
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
                    if not r_filter.value: # Empty IN list
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
            raise DatabaseError(msg) from e

    def get_objects_by_ids(
        self,
        object_type_name: str,
        ids: list[UUID],
    ) -> list[ObjectInstance]:
        """Retrieves multiple object instances by their type and a list of IDs."""
        if not ids:
            return []

        otd = self.load_object_type_definition(object_type_name)
        if not otd:
            msg = f"ObjectTypeDefinition '{object_type_name}' not found."
            raise SchemaError(msg)

        table_name = self._get_safe_table_name(object_type_name)

        id_placeholders = ",".join(["?"] * len(ids))
        sql = f'SELECT * FROM "{table_name}" WHERE id IN ({id_placeholders})'

        try:
            cursor = self.conn.execute(sql, [str(id_val) for id_val in ids])
            instances = []
            for row in cursor:
                instances.append(self._row_to_object_instance(row, otd))
            return instances
        except sqlite3.Error as e:
            msg = f"Error retrieving instances from '{table_name}': {e}"
            raise DatabaseError(msg) from e

    def get_all_object_ids_for_type(self, object_type_name: str) -> list[UUID]:
        """Retrieve all object instance IDs for a given object type."""
        table_name = self._get_safe_table_name(object_type_name)
        sql = f'SELECT id FROM "{table_name}"'

        try:
            cursor = self.conn.execute(sql)
            return [UUID(row["id"]) for row in cursor]
        except sqlite3.Error as e:
            msg = f"Error retrieving all IDs for type '{object_type_name}': {e}"
            raise DatabaseError(msg) from e

    def create_relation_type(self, definition: RelationTypeDefinition) -> None:
        """Creates a relation type by saving its definition."""
        self.save_relation_type_definition(definition)

    def delete_relation_type(self, name: str) -> None:
        """Deletes a relation type by removing its definition."""
        self.delete_relation_type_definition(name)

    def list_relation_types(self) -> list[str]:
        """Lists all relation type names by querying the metadata table."""
        try:
            cursor = self.conn.execute(f"SELECT name FROM {self._META_TABLE_RELATION_TYPES}")
            return [row["name"] for row in cursor]
        except sqlite3.Error as e:
            msg = f"Error listing relation types: {e}"
            raise DatabaseError(msg) from e

    def update_object_type(self, definition: ObjectTypeDefinition) -> None:
        """Updates an existing object type definition."""
        self.save_object_type_definition(definition)