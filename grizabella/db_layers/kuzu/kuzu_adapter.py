"""Grizabella adapter for KuzuDB graph database."""

import glob  # Added
import logging  # Added
import os  # Added
import threading  # For logging thread ID
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import kuzu

from grizabella.core.exceptions import DatabaseError, InstanceError, SchemaError
from grizabella.core.models import (
    EmbeddingDefinition,
    EmbeddingInstance,
    ObjectInstance,
    PropertyDataType,
    # These are also needed for TYPE_CHECKING block if it were to use them directly
    # ObjectTypeDefinition, # Already aliased
    # RelationTypeDefinition # Already aliased
    RelationInstance,
)

# import pandas as pd # Removed as get_as_df() was problematic
from grizabella.core.models import (
    ObjectTypeDefinition as ObjectTypeDefinitionModel,
)
from grizabella.core.models import (
    RelationTypeDefinition as RelationTypeDefinitionModel,
)
from grizabella.core.query_models import GraphTraversalClause  # Added for new method
from grizabella.db_layers.common.base_adapter import BaseDBAdapter

logger = logging.getLogger(__name__) # Added logger instantiation

class KuzuAdapter(BaseDBAdapter):  # pylint: disable=R0904
    """Grizabella adapter for KuzuDB.
    Handles graph node and relationship table schema management.
    """

    def __init__(self, db_path: str, config: Optional[dict[str, Any]] = None) -> None:
        logger.info(f"KuzuAdapter: Initializing in thread ID: {threading.get_ident()} for db_path: {db_path}")
        self.db: Optional[kuzu.Database] = None
        self.conn: Optional[kuzu.Connection] = None
        super().__init__(db_path, config)

    def _connect(self) -> None:
        """Establish a connection to the Kuzu database."""
        logger.info(f"KuzuAdapter: _connect called in thread ID: {threading.get_ident()} for db_path: {self.db_path}")
        try:
            # Clean up stale lock files
            lock_files = glob.glob(os.path.join(self.db_path, "*.lock"), include_hidden=True)
            if lock_files:
                logger.info(f"KuzuAdapter: Found {len(lock_files)} lock files. Attempting removal.")
                for lock_file in lock_files:
                    try:
                        os.remove(lock_file)
                        logger.info(f"KuzuAdapter: Removed lock file: {lock_file}")
                    except OSError as e:
                        logger.warning(f"KuzuAdapter: Could not remove WAL file {lock_file}: {e}")
            # Kuzu might also create WAL files that could interfere if not cleared after a crash,
            # especially if the lock file is gone but WAL remains.
            # Look for .wal files in the wal directory
            wal_files = glob.glob(os.path.join(self.db_path, "*.wal"), include_hidden=True)
            if wal_files:
                logger.info(f"KuzuAdapter: Found {len(wal_files)} WAL files. Attempting removal.")
                for wal_file in wal_files:
                    try:
                        os.remove(wal_file)
                        logger.info(f"KuzuAdapter: Removed WAL file: {wal_file}")
                    except OSError as e:
                        logger.warning(f"KuzuAdapter: Could not remove WAL file {wal_file}: {e}")
            logger.info(f"KuzuAdapter: Lock checks finished, starting connection in thread ID: {threading.get_ident()}.")
            self.db = kuzu.Database(self.db_path)
            logger.info(f"KuzuAdapter: kuzu.Database() successful in thread ID: {threading.get_ident()}. DB object: {self.db}")
            self.conn = kuzu.Connection(self.db)
            logger.info(f"KuzuAdapter: kuzu.Connection() successful in thread ID: {threading.get_ident()}. Connection object: {self.conn}")
        except Exception as e:
            logger.error(f"KuzuAdapter: Error during _connect in thread ID: {threading.get_ident()}: {e}", exc_info=True)
            msg = f"KuzuDB connection error to {self.db_path}: {e}"
            raise DatabaseError(
                msg,
            ) from e

    def close(self) -> None:
        """Close the KuzuDB database connection."""
        logger.info(f"KuzuAdapter: close() called in thread ID: {threading.get_ident()} for db_path: {self.db_path}. Connection state: {'Connected' if self.conn else 'Not Connected'}, DB state: {'Exists' if self.db else 'None'}")
        # Kuzu's Python API documentation suggests that connections and databases
        # are managed by Python's garbage collector when they go out of scope.
        # Explicitly setting to None helps ensure they are dereferenced.
        if self.conn:
            self.conn = None
            logger.info(f"KuzuAdapter: self.conn set to None for {self.db_path}.")
        if self.db:
            self.db = None
            logger.info(f"KuzuAdapter: self.db set to None for {self.db_path}.")
        logger.info(f"KuzuAdapter: close() method finished for {self.db_path}.")

    def _map_grizabella_to_kuzu_type(self, prop_type: PropertyDataType) -> str:
        """Maps Grizabella PropertyDataType to Kuzu data type strings."""
        mapping = {
            PropertyDataType.TEXT: "STRING",
            PropertyDataType.INTEGER: "INT64",
            PropertyDataType.FLOAT: "DOUBLE",
            PropertyDataType.BOOLEAN: "BOOL",
            PropertyDataType.DATETIME: "TIMESTAMP",
            PropertyDataType.BLOB: "BLOB",
            PropertyDataType.JSON: "STRING",
            PropertyDataType.UUID: "UUID",
        }
        kuzu_type = mapping.get(prop_type)
        if not kuzu_type:
            msg = f"Unsupported Grizabella data type for Kuzu: {prop_type}"
            raise SchemaError(msg)
        return kuzu_type

    # --- Node Table Management ---
    def create_node_table(self, otd: ObjectTypeDefinitionModel) -> None:
        """Creates a Kuzu node table based on an ObjectTypeDefinition if it doesn't already exist."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        try:
            existing_node_tables = self.list_object_types()
            if otd.name in existing_node_tables:
                logger.debug(f"KuzuAdapter: Node table '{otd.name}' already exists. Skipping creation.")
                return
        except DatabaseError as e:
            logger.warning(f"KuzuAdapter: Could not list existing node tables before creating '{otd.name}': {e}. Will attempt creation.")
            # Proceed to attempt creation if listing fails, Kuzu will error if it exists.

        try:
            properties_str_parts = ["id UUID PRIMARY KEY"]
            for prop in otd.properties:
                if prop.name.lower() == "id":
                    if prop.data_type != PropertyDataType.UUID:  # pylint: disable=W0311
                        msg = (
                            f"Property 'id' for Kuzu node table '{otd.name}' must be UUID "
                            "type in ObjectTypeDefinition."
                        )
                        raise SchemaError(
                            msg,
                        )
                    continue
                kuzu_type = self._map_grizabella_to_kuzu_type(prop.data_type)
                properties_str_parts.append(f"{prop.name} {kuzu_type}")

            properties_str = ", ".join(properties_str_parts)
            query = f"CREATE NODE TABLE {otd.name} ({properties_str})"
            self.conn.execute(query)
        except Exception as e:
            msg = f"KuzuDB error creating node table '{otd.name}': {e}"
            raise SchemaError(
                msg,
            ) from e

    def drop_node_table(self, object_type_name: str) -> None:
        """Drops a Kuzu node table."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        try:
            query = f"DROP TABLE {object_type_name}"
            self.conn.execute(query)
        except Exception as e:
            msg = f"KuzuDB error dropping node table '{object_type_name}': {e}"
            raise SchemaError(
                msg,
            ) from e

    # --- Relationship Table Management ---
    def create_rel_table(self, rtd: RelationTypeDefinitionModel) -> None:
        """Creates a Kuzu relationship table based on a RelationTypeDefinition if it doesn't already exist."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        try:
            existing_rel_tables = self.list_relation_types() # New method to be added
            if rtd.name in existing_rel_tables:
                logger.debug(f"KuzuAdapter: Relation table '{rtd.name}' already exists. Skipping creation.")
                return
        except DatabaseError as e:
            logger.warning(f"KuzuAdapter: Could not list existing relation tables before creating '{rtd.name}': {e}. Will attempt creation.")
            # Proceed to attempt creation if listing fails

        try:
            main_properties = "id UUID, weight DOUBLE, upsert_date TIMESTAMP"
            additional_properties_list = []
            for prop in rtd.properties:
                if prop.name.lower() not in ["id", "weight", "upsert_date"]:
                    kuzu_type = self._map_grizabella_to_kuzu_type(prop.data_type)
                    additional_properties_list.append(f"{prop.name} {kuzu_type}")
                else:
                    pass

            properties_str = main_properties
            if additional_properties_list:
                properties_str += f", {', '.join(additional_properties_list)}"

            if not rtd.source_object_type_names:
                msg = f"RTD '{rtd.name}' has no source object type names defined."
                raise SchemaError(
                    msg,
                )
            if not rtd.target_object_type_names:
                msg = f"RTD '{rtd.name}' has no target object type names defined."
                raise SchemaError(
                    msg,
                )

            source_table_name = rtd.source_object_type_names[0]
            target_table_name = rtd.target_object_type_names[0]

            query = (
                f"CREATE REL TABLE {rtd.name} ("
                f"FROM {source_table_name} "
                f"TO {target_table_name}, {properties_str})"
            )
            self.conn.execute(query)
        except Exception as e:
            msg = f"KuzuDB error creating relationship table '{rtd.name}': {e}"
            raise SchemaError(
                msg,
            ) from e

    def drop_rel_table(self, relation_type_name: str) -> None:
        """Drops a Kuzu relationship table."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        try:
            query = f"DROP TABLE {relation_type_name}"
            self.conn.execute(query)
        except Exception as e:
            msg = (
                f"KuzuDB error dropping relationship table "
                f"'{relation_type_name}': {e}"
            )
            raise SchemaError(
                msg,
            ) from e

    # --- BaseDBAdapter Method Implementations (Schema-related) ---
    def create_object_type(self, definition: ObjectTypeDefinitionModel) -> None:
        """Creates a Kuzu node table for the given object type definition."""
        self.create_node_table(definition)

    def delete_object_type(self, name: str) -> None:
        """Drops the Kuzu node table for the given object type name."""
        self.drop_node_table(name)

    def create_relation_type(self, definition: RelationTypeDefinitionModel) -> None:
        """Creates a Kuzu relationship table for the given relation type definition."""
        self.create_rel_table(definition)

    def delete_relation_type(self, name: str) -> None:
        """Deletes a relation type (drops the Kuzu REL table)."""
        self.drop_rel_table(name)

    def get_object_type(self, name: str) -> Optional[ObjectTypeDefinitionModel]:
        """Not directly supported by Kuzu schema inspection for full OTD."""

    def update_object_type(self, definition: ObjectTypeDefinitionModel) -> None:
        """Not yet implemented for Kuzu."""
        msg = "KuzuAdapter.update_object_type not yet implemented for Kuzu."
        raise NotImplementedError(
            msg,
        )

    def list_object_types(self) -> list[str]:
        """Lists all NODE table names from Kuzu."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        try:
            # Updated to include RETURN * as per Kuzu documentation for CALL
            raw_query_result = self.conn.execute("CALL SHOW_TABLES() RETURN *;")
            node_tables = []

            # conn.execute might return a list if multiple statements were run,
            # but for a single CALL, it should be a single QueryResult.
            # Handle both cases to satisfy Pylance and be robust.
            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if (
                actual_query_result
            ):  # Ensure query_result is not None and is a QueryResult
                column_names = actual_query_result.get_column_names()
                while actual_query_result.has_next():
                    row = actual_query_result.get_next()
                    table_info = dict(zip(column_names, row))
                    if (
                        table_info.get("type") == "NODE"
                    ):  # Kuzu uses 'type' for table type
                        node_tables.append(table_info.get("name"))
            return node_tables
        except Exception as e:
            msg = f"KuzuDB error listing object types: {e}"
            raise DatabaseError(msg) from e

    def list_relation_types(self) -> list[str]:
        """Lists all REL table names from Kuzu."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        try:
            raw_query_result = self.conn.execute("CALL SHOW_TABLES() RETURN *;")
            rel_tables = []
            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if actual_query_result:
                column_names = actual_query_result.get_column_names()
                while actual_query_result.has_next():
                    row = actual_query_result.get_next()
                    table_info = dict(zip(column_names, row))
                    if table_info.get("type") == "REL":
                        rel_tables.append(table_info.get("name"))
            return rel_tables
        except Exception as e:
            msg = f"KuzuDB error listing relation types: {e}"
            raise DatabaseError(msg) from e

    def get_relation_type(self, name: str) -> Optional[RelationTypeDefinitionModel]:
        """Not directly supported by Kuzu schema inspection for full RTD."""

    # --- Object Instance Management (Nodes) ---
    def upsert_object_instance(self, instance: ObjectInstance) -> ObjectInstance:
        """Upserts a node into the Kuzu node table corresponding to instance.object_type_name.
        Uses Kuzu's MERGE Cypher clause. 'id' is the primary key for matching.
        Maps instance.properties to Kuzu node properties.
        """
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        table_name = instance.object_type_name

        # Explicitly type params_for_query and props_for_set
        params_for_query: dict[str, Any] = {
            "id_param": instance.id, # Pass UUID object directly
        }

        # props_for_set should include 'id' and all other properties from instance.properties
        props_for_set: dict[str, Any] = {
            "id": str(instance.id),
        }  # Kuzu expects UUID as string

        # Build SET clause and populate params_for_query with correctly typed values
        set_clause_parts = []
        # Add id parameter
        params_for_query["id_param"] = instance.id
        set_clause_parts.append("n.id = $id_param")

        # Process each property
        for key, original_value in instance.properties.items():
            param_name = f"p_{key}"
            set_clause_parts.append(f"n.{key} = ${param_name}")
            # Ensure the parameter type matches Kuzu's expectation for the property
            if isinstance(original_value, UUID):
                params_for_query[param_name] = original_value # Pass UUID object
            elif isinstance(original_value, datetime):
                params_for_query[param_name] = original_value  # Pass datetime object directly
            elif isinstance(original_value, str):
                # Handle datetime strings by converting to datetime objects
                try:
                    dt_value = datetime.fromisoformat(original_value)
                    params_for_query[param_name] = dt_value
                except (ValueError, TypeError):
                    # If conversion fails, pass the original string
                    params_for_query[param_name] = original_value
            else:
                params_for_query[param_name] = original_value

        # props_for_set should include 'id' and all other properties from instance.properties
        props_for_set: dict[str, Any] = {
            "id": str(instance.id),
        }  # Kuzu expects UUID as string
        # Convert all property values to types Kuzu can handle directly in Cypher
        # For example, datetime to string, UUID to string.
        # Kuzu's Python API might handle some conversions, but explicit is safer for $props_for_set.
        for key, value in instance.properties.items():
            # props_for_set is used to gather all properties that need to be in the SET clause
            props_for_set[key] = value # Store original types from instance.properties

        if not set_clause_parts:
            msg = f"KuzuDB: No properties to set for object instance {instance.id} in {table_name}."
            raise InstanceError(msg)

        set_clause_str_on_create = ", ".join(set_clause_parts)

        # For ON MATCH, exclude setting the 'id' property as it's used for matching.
        # Only include other properties from instance.properties.
        set_clause_parts_on_match_list = []
        for key, original_value in instance.properties.items(): # Iterate only over instance.properties
            param_name = f"p_{key}" # Ensure param_name matches those in params_for_query
            # We need to ensure that $p_key is actually in params_for_query
            # params_for_query was built from all_node_properties which includes 'id'
            # So, $p_id will be there, but other $p_key for instance.properties also.
            set_clause_parts_on_match_list.append(f"n.{key} = ${param_name}")

        on_match_cypher_clause = ""
        if set_clause_parts_on_match_list:
            set_clause_str_on_match = ", ".join(set_clause_parts_on_match_list)
            on_match_cypher_clause = f"ON MATCH SET {set_clause_str_on_match}"
        # If set_clause_parts_on_match_list is empty (i.e., instance.properties was empty),
        # then on_match_cypher_clause remains an empty string, and Kuzu's MERGE
        # will not have an ON MATCH SET clause, which is valid if no properties need updating.

        query = f"""
            MERGE (n:{table_name} {{id: $id_param}})
            ON CREATE SET {set_clause_str_on_create}
            {on_match_cypher_clause}
            RETURN n.id
        """

        try:

            raw_query_result = self.conn.execute(query, parameters=params_for_query)

            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result or not actual_query_result.has_next():
                msg = (
                    f"KuzuDB: Upsert for object instance {instance.id} in "
                    f"{table_name} did not return the expected ID, indicating a potential issue."
                )
                raise InstanceError(
                    msg,
                )

            returned_id_val = actual_query_result.get_next()[0]

            # Kuzu might return UUID as kuzu.UUID object or string depending on context/version.
            # Ensure we compare it correctly with our UUID object.
            returned_id_obj: Optional[UUID] = None
            if isinstance(returned_id_val, UUID):
                returned_id_obj = returned_id_val
            elif isinstance(returned_id_val, str):
                try:
                    returned_id_obj = UUID(returned_id_val)
                except ValueError as exc:
                    msg = (
                        f"KuzuDB: Returned ID '{returned_id_val}' from upsert "
                        f"for table {table_name} is not a valid UUID string."
                    )
                    raise InstanceError(
                        msg,
                    ) from exc
            # Kuzu's internal UUID type might be different, check for a 'value' attribute
            elif hasattr(returned_id_val, "value") and isinstance(returned_id_val.value, (str, bytes)):  # type: ignore
                try:
                    returned_id_obj = UUID(str(returned_id_val.value))  # type: ignore
                except (ValueError, TypeError) as exc:
                    msg = (
                        f"KuzuDB: Returned ID value '{returned_id_val.value}' from kuzu object "  # type: ignore
                        f"for table {table_name} is not a valid UUID string."
                    )
                    raise InstanceError(
                        msg,
                    ) from exc
            else:
                msg = (
                    f"KuzuDB: Returned ID from upsert for table {table_name} has unexpected "
                    f"type {type(returned_id_val)}: {returned_id_val}"
                )
                raise InstanceError(
                    msg,
                )

            if returned_id_obj != instance.id:
                pass
                # This could indicate a serious issue if Kuzu's MERGE behaves unexpectedly
                # or if there's a type mismatch leading to misinterpretation of ID.
                # For now, we proceed but this should be monitored.

            return instance

        except Exception as e:
            msg = (
                f"KuzuDB error upserting object instance {instance.id} "
                f"into '{table_name}': {e}"
            )
            raise InstanceError(
                msg,
            ) from e

    def get_object_instance(
        self, object_type_name: str, instance_id: UUID,
    ) -> Optional[ObjectInstance]:
        """Retrieves a node by its ID from Kuzu and reconstructs an ObjectInstance."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        # Kuzu expects UUID as string for parameter binding
        query = f"MATCH (n:{object_type_name} {{id: $instance_id_param}}) RETURN n"
        params = {"instance_id_param": instance_id} # Pass UUID object

        try:
            # Ensure params is passed correctly as a dictionary
            raw_query_result = self.conn.execute(query, parameters=params)

            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result or not actual_query_result.has_next():
                return None

            node_data_from_kuzu = actual_query_result.get_next()[0]

            if not node_data_from_kuzu or "id" not in node_data_from_kuzu:
                return None

            # Handle Kuzu's UUID representation (can be string or kuzu.UUID object)
            retrieved_id_val = node_data_from_kuzu.get("id")
            retrieved_id_obj: Optional[UUID] = None
            if isinstance(retrieved_id_val, UUID):
                retrieved_id_obj = retrieved_id_val
            elif isinstance(retrieved_id_val, str):
                try:
                    retrieved_id_obj = UUID(retrieved_id_val)
                except ValueError as exc:
                    msg = (
                        f"KuzuDB: Retrieved ID '{retrieved_id_val}' from table {object_type_name} "
                        "is not a valid UUID string."
                    )
                    raise InstanceError(
                        msg,
                    ) from exc
            elif hasattr(retrieved_id_val, "value") and isinstance(
                retrieved_id_val.value, (str, bytes),
            ):
                try:
                    retrieved_id_obj = UUID(str(retrieved_id_val.value))
                except (ValueError, TypeError) as exc:
                    msg = (
                        f"KuzuDB: Retrieved ID value '{retrieved_id_val.value}' from kuzu object "
                        f"for table {object_type_name} is not a valid UUID string."
                    )
                    raise InstanceError(
                        msg,
                    ) from exc
            else:
                msg = (
                    f"KuzuDB: Retrieved ID from table {object_type_name} has unexpected "
                    f"type {type(retrieved_id_val)}: {retrieved_id_val}"
                )
                raise InstanceError(
                    msg,
                )

            if retrieved_id_obj != instance_id:
                msg = (
                    f"ID mismatch retrieving {instance_id} from {object_type_name}: "
                    f"Expected {instance_id}, got {retrieved_id_obj}"
                )
                raise InstanceError(
                    msg,
                )

            reconstructed_args = {
                "id": retrieved_id_obj,  # Use the converted UUID object
                "object_type_name": object_type_name,
                "properties": {},
            }

            temp_properties = {}
            for key, value in node_data_from_kuzu.items():
                if key == "id":
                    continue
                if key == "weight":  # If 'weight' was a defined property in OTD
                    reconstructed_args["weight"] = value
                elif (
                    key == "upsert_date"
                ):  # If 'upsert_date' was a defined property in OTD
                    reconstructed_args["upsert_date"] = value
                else:
                    temp_properties[key] = value

            reconstructed_args["properties"] = temp_properties

            return ObjectInstance(**reconstructed_args)

        except Exception as e:
            msg = (
                f"KuzuDB error getting object instance {instance_id} "
                f"from '{object_type_name}': {e}"
            )
            raise InstanceError(
                msg,
            ) from e

    def delete_object_instance(self, object_type_name: str, instance_id: UUID) -> bool:
        """Deletes a node by its ID from Kuzu. Uses DETACH DELETE.
        Returns True if the node was deleted, False otherwise.
        """
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        # Kuzu expects UUID as string for parameter binding
        query = (
            f"MATCH (n:{object_type_name} {{id: $instance_id_param}}) DETACH DELETE n"
        )
        params = {"instance_id_param": instance_id} # Pass UUID object

        try:
            raw_query_result = self.conn.execute(query, parameters=params)

            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result:
                # This case should ideally not happen if execute ran without error,
                # but good to be defensive.
                return False

            summary = actual_query_result.get_query_summary()  # type: ignore[attr-defined]
            nodes_deleted = summary.get_num_nodes_deleted() if summary else 0  # type: ignore[attr-defined]

            return nodes_deleted > 0
        except Exception as e:
            # Check for specific Kuzu errors, e.g. table not found (RuntimeError)
            # kuzu.runtime_error.NotFoundError might be relevant if table doesn't exist
            if "NotFoundError" in str(
                type(e),
            ) and f"Table {object_type_name} does not exist." in str(e):
                msg = f"KuzuDB: Table '{object_type_name}' not found."
                raise SchemaError(
                    msg,
                ) from e

            # For other errors, we can say deletion failed.
            return False

    def find_object_instances(  # pylint: disable=R0913
        self,
        object_type_name: str,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Not yet implemented (Subtask 3.2)."""
        msg = "KuzuAdapter.find_object_instances not yet implemented (Subtask 3.2)."
        raise NotImplementedError(
            msg,
        )

    def get_all_object_ids_for_type(self, object_type_name: str) -> list[UUID]:
        """Kuzu is not typically used to fetch all object IDs for a type without further filtering;
        this is generally a relational store task for broad ID lists.
        """
        msg = "KuzuAdapter.get_all_object_ids_for_type is not applicable or not implemented."
        raise NotImplementedError(msg)

    # --- Embedding Management (Not applicable for Kuzu) ---
    def add_embedding_definition(self, definition: EmbeddingDefinition) -> None:
        """Embedding definitions are not managed by KuzuAdapter."""

    def get_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:
        """Embedding definitions are not managed by KuzuAdapter."""

    def upsert_embedding_instance(
        self, instance: EmbeddingInstance,
    ) -> EmbeddingInstance:
        """Not applicable for KuzuAdapter."""
        msg = "KuzuAdapter.upsert_embedding_instance is not applicable."
        raise NotImplementedError(
            msg,
        )

    def get_embedding_instance(
        self, embedding_definition_name: str, object_instance_id: UUID,
    ) -> Optional[EmbeddingInstance]:
        """Not applicable for KuzuAdapter."""
        msg = "KuzuAdapter.get_embedding_instance is not applicable."
        raise NotImplementedError(
            msg,
        )

    def find_similar_embeddings(  # pylint: disable=R0913
        self, embedding_definition_name: str, vector: list[float], top_k: int = 5,
    ) -> list[EmbeddingInstance]:
        """Not applicable for KuzuAdapter."""
        msg = "KuzuAdapter.find_similar_embeddings is not applicable."
        raise NotImplementedError(
            msg,
        )

    # --- Relation Instance Management (Edges) ---
    def upsert_relation_instance(  # type: ignore # pylint: disable=arguments-differ
        self,
        instance: RelationInstance,
        rtd: Optional[RelationTypeDefinitionModel] = None,
    ) -> RelationInstance:
        """Upserts a relationship in Kuzu between the source_object_instance_id and
        target_object_instance_id in the table corresponding to instance.relation_type_name.
        Requires RelationTypeDefinition to know source/target node table names.
        """
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        logger.debug(
            f"KuzuAdapter.upsert_relation_instance called with instance: {instance.id=}, "
            f"{instance.relation_type_name=}, {instance.source_object_instance_id=}, "
            f"{type(instance.source_object_instance_id)=}, {instance.target_object_instance_id=}, "
            f"{type(instance.target_object_instance_id)=}, {instance.weight=}, "
            f"{type(instance.weight)=}, {instance.upsert_date=}, {type(instance.upsert_date)=}, "
            f"properties: { {k: (v, type(v)) for k, v in instance.properties.items()} }",
        )
        if rtd:
            logger.debug(f"Using RTD: {rtd.name}, source_types: {rtd.source_object_type_names}, target_types: {rtd.target_object_type_names}")
        else:
            logger.warning("RTD is None in upsert_relation_instance")


        rel_table_name = instance.relation_type_name
        if not rtd:
            # This adapter requires RTD to function, so if it's None, we cannot proceed.
            # This aligns with the previous non-optional behavior but now matches the base signature.
            msg = f"KuzuAdapter.upsert_relation_instance requires 'rtd' (RelationTypeDefinition) for relation type '{rel_table_name}'."
            raise ValueError(
                msg,
            )

        if not rtd.source_object_type_names:
            msg = f"RTD '{rtd.name}' for relation instance '{instance.id}' has no source object type names."
            raise SchemaError(
                msg,
            )
        if not rtd.target_object_type_names:
            msg = f"RTD '{rtd.name}' for relation instance '{instance.id}' has no target object type names."
            raise SchemaError(
                msg,
            )

        src_node_table = rtd.source_object_type_names[0]
        tgt_node_table = rtd.target_object_type_names[0]

        params_for_query: dict[str, Any] = {
            "src_id_param": instance.source_object_instance_id, # Pass UUID object
            "tgt_id_param": instance.target_object_instance_id, # Pass UUID object
            "rel_id_param": instance.id, # Pass UUID object
        }

        props_for_set: dict[str, Any] = {
            "id": str(instance.id),
            "weight": float(instance.weight),  # Kuzu expects float for DOUBLE
            "upsert_date": instance.upsert_date,  # Kuzu Python API handles datetime to TIMESTAMP
        }
        # Add custom properties, converting UUIDs to strings
        for key, value in instance.properties.items():
            # props_for_set is used to gather all properties that need to be in the SET clause
            props_for_set[key] = value # Store original types

        # Build SET clause and populate params_for_query with correctly typed values
        set_clause_parts = []
        # Iterate over all properties intended for the relation (id, weight, upsert_date + instance.properties)
        all_relation_properties = {
            "id": instance.id,
            "weight": float(instance.weight),
            "upsert_date": instance.upsert_date,
            **instance.properties,
        }

        for key, original_value in all_relation_properties.items():
            param_name = f"p_{key}"
            set_clause_parts.append(f"r.{key} = ${param_name}")
            # Ensure the parameter type matches Kuzu's expectation
            if key == "id": # 'id' property in Kuzu is UUID
                params_for_query[param_name] = instance.id # Pass UUID object
            elif isinstance(original_value, UUID): # Other potential UUID properties
                params_for_query[param_name] = original_value # Pass UUID object
            else:
                params_for_query[param_name] = original_value

        if not set_clause_parts:
            msg = f"KuzuDB: No properties to set for relation instance {instance.id} in {rel_table_name}."
            raise InstanceError(msg)
        set_clause_str = ", ".join(set_clause_parts)

        # Diagnostic: Check if source node exists
        check_src_query = f"MATCH (s:{src_node_table} {{id: $src_id_param}}) RETURN s.id"
        logger.debug(f"KuzuAdapter: Checking source node existence with query: {check_src_query} and params: {{'src_id_param': instance.source_object_instance_id}}")
        src_exists_result = self.conn.execute(check_src_query, parameters={"src_id_param": instance.source_object_instance_id})

        actual_src_exists_result: Optional[kuzu.query_result.QueryResult] = None
        if isinstance(src_exists_result, list):
            if src_exists_result:
                actual_src_exists_result = src_exists_result[0]
        else:
            actual_src_exists_result = src_exists_result

        if not actual_src_exists_result or not actual_src_exists_result.has_next():
            logger.error(f"KuzuAdapter: DIAGNOSTIC - Source node {instance.source_object_instance_id} NOT FOUND in table {src_node_table}.")
        else:
            logger.debug(f"KuzuAdapter: DIAGNOSTIC - Source node {instance.source_object_instance_id} FOUND in table {src_node_table}.")

        # Diagnostic: Check if target node exists
        check_tgt_query = f"MATCH (t:{tgt_node_table} {{id: $tgt_id_param}}) RETURN t.id"
        logger.debug(f"KuzuAdapter: Checking target node existence with query: {check_tgt_query} and params: {{'tgt_id_param': instance.target_object_instance_id}}")
        tgt_exists_result = self.conn.execute(check_tgt_query, parameters={"tgt_id_param": instance.target_object_instance_id})

        actual_tgt_exists_result: Optional[kuzu.query_result.QueryResult] = None
        if isinstance(tgt_exists_result, list):
            if tgt_exists_result:
                actual_tgt_exists_result = tgt_exists_result[0]
        else:
            actual_tgt_exists_result = tgt_exists_result

        if not actual_tgt_exists_result or not actual_tgt_exists_result.has_next():
            logger.error(f"KuzuAdapter: DIAGNOSTIC - Target node {instance.target_object_instance_id} NOT FOUND in table {tgt_node_table}.")
        else:
            logger.debug(f"KuzuAdapter: DIAGNOSTIC - Target node {instance.target_object_instance_id} FOUND in table {tgt_node_table}.")

        query = f"""
            MATCH (src:{src_node_table} {{id: $src_id_param}}), (tgt:{tgt_node_table} {{id: $tgt_id_param}})
            MERGE (src)-[r:{rel_table_name} {{id: $rel_id_param}}]->(tgt)
            ON CREATE SET {set_clause_str}
            ON MATCH SET {set_clause_str}
            RETURN r.id
        """
        logger.debug(f"Kuzu upsert_relation_instance query: {query}")
        logger.debug(f"Kuzu upsert_relation_instance params_for_query: { {k: (v, type(v)) for k,v in params_for_query.items()} }")

        try:
            raw_query_result = self.conn.execute(query, parameters=params_for_query)

            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result or not actual_query_result.has_next():
                msg = (
                    f"KuzuDB: Upsert for relation instance {instance.id} in "
                    f"{rel_table_name} did not return the expected ID."
                )
                raise InstanceError(
                    msg,
                )

            returned_id_val = actual_query_result.get_next()[0]
            returned_id_obj: Optional[UUID] = None
            if isinstance(returned_id_val, UUID):
                returned_id_obj = returned_id_val
            elif isinstance(returned_id_val, str):
                returned_id_obj = UUID(returned_id_val)
            elif hasattr(returned_id_val, "value"):  # kuzu.UUID like
                returned_id_obj = UUID(str(returned_id_val.value))  # type: ignore
            else:
                msg = f"Unexpected type for returned ID: {type(returned_id_val)}"
                raise InstanceError(
                    msg,
                )

            if returned_id_obj != instance.id:
                pass

            return instance

        except Exception as e:
            msg = (
                f"KuzuDB error upserting relation instance {instance.id} "
                f"into '{rel_table_name}': {e}"
            )
            raise InstanceError(
                msg,
            ) from e

    def get_relation_instance(  # type: ignore
        self, relation_type_name: str, relation_id: UUID,
    ) -> Optional[RelationInstance]:
        """Retrieves a relationship by its ID and reconstructs a RelationInstance."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        query = f"""
            MATCH (src)-[r:{relation_type_name} {{id: $rel_id_param}}]->(tgt)
            RETURN r, src.id AS source_object_instance_id, tgt.id AS target_object_instance_id
        """
        params = {"rel_id_param": relation_id} # Pass UUID object

        try:
            raw_query_result = self.conn.execute(query, parameters=params)

            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result or not actual_query_result.has_next():
                return None

            row = actual_query_result.get_next()
            rel_data_from_kuzu = row[0]  # The relationship properties
            src_id_str = row[1]
            tgt_id_str = row[2]

            if not rel_data_from_kuzu or "id" not in rel_data_from_kuzu:
                return None

            retrieved_id_val = rel_data_from_kuzu.get("id")
            retrieved_id_obj: Optional[UUID] = None
            if isinstance(retrieved_id_val, UUID):
                retrieved_id_obj = retrieved_id_val
            elif isinstance(retrieved_id_val, str):
                retrieved_id_obj = UUID(retrieved_id_val)
            elif hasattr(retrieved_id_val, "value"):  # kuzu.UUID like
                retrieved_id_obj = UUID(str(retrieved_id_val.value))  # type: ignore
            else:
                msg = f"Unexpected type for retrieved relation ID: {type(retrieved_id_val)}"
                raise InstanceError(
                    msg,
                )

            if retrieved_id_obj != relation_id:
                msg = (
                    f"ID mismatch retrieving relation {relation_id} from {relation_type_name}: "
                    f"Expected {relation_id}, got {retrieved_id_obj}"
                )
                raise InstanceError(
                    msg,
                )

            reconstructed_args: dict[str, Any] = {  # Ensure type for Pydantic model
                "id": retrieved_id_obj,
                "relation_type_name": relation_type_name,
                "source_object_instance_id": UUID(src_id_str),
                "target_object_instance_id": UUID(tgt_id_str),
                "properties": {},
            }

            # Standard properties from MemoryInstance base
            if "weight" in rel_data_from_kuzu:
                reconstructed_args["weight"] = rel_data_from_kuzu["weight"]
            if "upsert_date" in rel_data_from_kuzu:
                # Kuzu returns datetime.datetime for TIMESTAMP
                reconstructed_args["upsert_date"] = rel_data_from_kuzu["upsert_date"]

            temp_properties = {}
            for key, value in rel_data_from_kuzu.items():
                # Kuzu internal properties often start with '_' or are specific like 'id', 'weight', 'upsert_date'
                # We only want user-defined properties here.
                if key not in [
                    "id",
                    "weight",
                    "upsert_date",
                    "_src",
                    "_dst",
                    "_label",
                    "_id",
                ]:
                    # Convert Kuzu UUID objects back to Python UUID if they are properties
                    if hasattr(value, "value") and isinstance(
                        value.value, (str, bytes),
                    ):  # kuzu.UUID like
                        try:
                            temp_properties[key] = UUID(str(value.value))  # type: ignore
                        except ValueError:
                            temp_properties[key] = str(value.value)  # type: ignore If not a valid UUID, keep as string
                    elif isinstance(value, UUID):  # Already a Python UUID
                        temp_properties[key] = value
                    else:
                        temp_properties[key] = value

            reconstructed_args["properties"] = temp_properties

            return RelationInstance(**reconstructed_args)

        except Exception as e:
            msg = (
                f"KuzuDB error getting relation instance {relation_id} "
                f"from '{relation_type_name}': {e}"
            )
            raise InstanceError(
                msg,
            ) from e

    def find_relation_instances(  # pylint: disable=R0913, R0917, R0912
        self,
        relation_type_name: Optional[str] = None,
        source_object_id: Optional[UUID] = None,
        target_object_id: Optional[UUID] = None,
        query: Optional[dict[str, Any]] = None,  # Query on relation properties
        limit: Optional[int] = None,
    ) -> list[RelationInstance]:
        """Queries relationships. Supports filtering by relation type,
        source node ID, target node ID, and properties.
        """
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        if not relation_type_name and not source_object_id and not target_object_id and not query:
            # If no specific relation type, source/target ID, or property query is given,
            # scanning all relations is too broad and potentially resource-intensive.
            # Return empty list as a sensible default for such an open-ended request.
            return []

        # If querying by properties, relation_type_name is mandatory (this is handled later)
        # if query and not relation_type_name:
        #     ... raise ValueError ...

        # If filtering by source/target ID without a specific relation_type_name,
        # the query MATCH (src)-[r]->(tgt) can be too broad.
        # Raise ValueError to make the API contract clear.
        if not relation_type_name and (source_object_id or target_object_id):
            msg = (
                "Querying relations by source/target ID without specifying "
                "'relation_type_name' is too broad and requires 'relation_type_name'."
            )
            raise ValueError(msg)

        params: dict[str, Any] = {}
        where_clauses: list[str] = []

        # Base MATCH clause
        # If relation_type_name is None, Kuzu requires a more generic match,
        # and we'll use TYPE(r) to determine the relation type later.
        # However, filtering on r's properties without knowing its type is problematic.
        rel_label_cypher = f":{relation_type_name}" if relation_type_name else ""
        match_clause = f"MATCH (src)-[r{rel_label_cypher}]->(tgt)"

        cypher_query_parts = [match_clause]

        if source_object_id:
            where_clauses.append("src.id = $src_id_param")
            params["src_id_param"] = source_object_id # Pass UUID object

        if target_object_id:
            where_clauses.append("tgt.id = $tgt_id_param")
            params["tgt_id_param"] = target_object_id # Pass UUID object

        if query:
            if not relation_type_name:
                # This is a practical limitation: Kuzu needs to know the relation type
                # to correctly interpret property names for filtering.
                msg = (
                    "Querying by relation properties (using the 'query' parameter) "
                    "requires specifying the 'relation_type_name'."
                )
                raise ValueError(
                    msg,
                )
            for prop_name, prop_value in query.items():
                param_key = f"prop_{prop_name}"  # Ensure unique param names for safety
                where_clauses.append(f"r.{prop_name} = ${param_key}")
                if isinstance(prop_value, UUID):
                    params[param_key] = str(prop_value)
                # Add other type conversions if Kuzu requires them for specific WHERE clause values
                # e.g. datetime to Kuzu's timestamp string format if not handled by driver
                else:
                    params[param_key] = prop_value

        if where_clauses:
            cypher_query_parts.append("WHERE " + " AND ".join(where_clauses))

        # Return relationship data, source/target IDs.
        # If relation_type_name is known, use it directly. Otherwise, try label(r).
        if relation_type_name:
            # We already know the relation_type_name, no need to fetch it from Kuzu's TYPE() or label().
            # The actual_relation_type will be this known name.
            cypher_query_parts.append(
                "RETURN r, src.id AS src_node_id, tgt.id AS tgt_node_id",
            )
        else:
            # If relation_type_name was not provided (broader query), try to get it using label(r)
            # This case is somewhat restricted by earlier checks in the method.
            cypher_query_parts.append(
                "RETURN r, src.id AS src_node_id, tgt.id AS tgt_node_id, label(r) as actual_relation_type_from_kuzu",
            )

        if limit is not None:
            if not isinstance(limit, int) or limit <= 0:
                msg = "Limit must be a positive integer."
                raise ValueError(msg)
            cypher_query_parts.append(
                f"LIMIT {limit}",
            )  # Kuzu expects integer literal for LIMIT

        final_query = " ".join(cypher_query_parts)

        results: list[RelationInstance] = []
        try:
            raw_query_result = self.conn.execute(final_query, parameters=params)

            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result:
                return results

            while actual_query_result.has_next():
                row = actual_query_result.get_next()
                rel_data_from_kuzu = row[0]  # Relationship properties as a dict
                src_id_str = row[1]
                tgt_id_str = row[2]

                actual_rel_type_to_use: str
                if relation_type_name:
                    actual_rel_type_to_use = relation_type_name
                # This branch is taken if relation_type_name was None in the input,
                # and we used label(r) in the query.
                elif len(row) > 3: # Check if label(r) was actually returned
                     actual_rel_type_to_use = row[3] # from label(r)
                else:
                    # This should not happen if the query was built correctly for this case.
                    # Fallback or raise error. For now, let's try to make it robust.
                    # If relation_type_name was None, and label(r) wasn't in RETURN, this is an issue.
                    # However, the method logic tries to ensure relation_type_name if querying by props.
                    # If it's a very generic query, this might be problematic.
                    # For safety, if it's missing, we can't form a valid RelationInstance.
                    logger.warning("Could not determine actual relation type for a found relation.")
                    continue


                if not rel_data_from_kuzu or "id" not in rel_data_from_kuzu:
                    continue

                rel_id_val = rel_data_from_kuzu.get("id")
                rel_id_obj: Optional[UUID] = None
                if isinstance(rel_id_val, UUID):
                    rel_id_obj = rel_id_val
                elif isinstance(rel_id_val, str):
                    try:
                        rel_id_obj = UUID(rel_id_val)
                    except ValueError:
                        continue
                elif hasattr(rel_id_val, "value") and isinstance(
                    rel_id_val.value, (str, bytes),
                ):  # kuzu.UUID like
                    try:
                        rel_id_obj = UUID(str(rel_id_val.value))  # type: ignore
                    except ValueError:
                        continue
                else:
                    continue

                reconstructed_args: dict[str, Any] = {
                    "id": rel_id_obj,
                    "relation_type_name": actual_rel_type_to_use,
                    "source_object_instance_id": src_id_str if isinstance(src_id_str, UUID) else UUID(src_id_str),
                    "target_object_instance_id": tgt_id_str if isinstance(tgt_id_str, UUID) else UUID(tgt_id_str),
                    "properties": {},
                }

                if "weight" in rel_data_from_kuzu:
                    reconstructed_args["weight"] = rel_data_from_kuzu["weight"]
                if "upsert_date" in rel_data_from_kuzu:
                    reconstructed_args["upsert_date"] = rel_data_from_kuzu[
                        "upsert_date"
                    ]

                temp_properties = {}
                internal_kuzu_fields = {
                    "id",
                    "weight",
                    "upsert_date",
                    "_src",
                    "_dst",
                    "_label",
                    "_id",
                }
                for key, value in rel_data_from_kuzu.items():
                    if key not in internal_kuzu_fields:
                        if hasattr(value, "value") and isinstance(
                            value.value, (str, bytes),
                        ):  # kuzu.UUID like
                            try:
                                temp_properties[key] = UUID(str(value.value))  # type: ignore
                            except (
                                ValueError
                            ):  # If not a valid UUID string, store as is
                                temp_properties[key] = str(value.value)  # type: ignore
                        elif isinstance(value, UUID):  # Already a Python UUID
                            temp_properties[key] = value
                        else:
                            temp_properties[key] = value
                reconstructed_args["properties"] = temp_properties
                results.append(RelationInstance(**reconstructed_args))

            return results

        except Exception as e:
            # Log the query and params for debugging if needed
            # print(f"Failed query: {final_query}")
            # print(f"Failed params: {params}")
            msg = f"KuzuDB error finding relation instances: {e}"
            raise InstanceError(msg) from e

    def delete_relation_instance(self, relation_type_name: str, relation_id: UUID) -> bool:  # type: ignore
        """Deletes a relationship by its ID from Kuzu."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        query = f"MATCH ()-[r:{relation_type_name} {{id: $rel_id_param}}]->() DELETE r"
        params = {"rel_id_param": relation_id} # Pass UUID object

        try:
            raw_query_result = self.conn.execute(query, parameters=params)

            actual_query_result: Optional[kuzu.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result:
                return False

            summary = actual_query_result.get_query_summary()  # type: ignore[attr-defined]
            rels_deleted = summary.get_num_rels_deleted() if summary else 0  # type: ignore[attr-defined]

            return rels_deleted > 0
        except Exception as e:
            if "NotFoundError" in str(type(e)) and f"Table {relation_type_name} does not exist." in str(e):  # type: ignore
                msg = f"KuzuDB: Table '{relation_type_name}' not found."
                raise SchemaError(
                    msg,
                ) from e
            return False

    def filter_object_ids_by_relations(
        self,
        source_object_type_name: str,
        object_ids: list[UUID],
        traversals: list[GraphTraversalClause],
    ) -> list[UUID]:
        """Filters a list of object IDs, returning only those that satisfy all specified graph traversals."""
        if not self.conn:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        if not object_ids:
            return []
        if (
            not traversals
        ):  # If no traversals, all initial IDs satisfy the (empty) conditions
            return object_ids

        final_matching_ids: list[UUID] = []

        for obj_id in object_ids:
            current_id_satisfies_all = True
            for traversal_idx, traversal in enumerate(traversals):
                # Pass UUID object directly for src_id_param if obj_id is UUID
                params: dict[str, Any] = {"src_id_param": obj_id if isinstance(obj_id, UUID) else str(obj_id)}
                match_parts: list[str] = []
                where_clauses: list[str] = []

                src_node_label = source_object_type_name
                rel_label = traversal.relation_type_name
                tgt_node_label = traversal.target_object_type_name

                if traversal.direction == "outgoing":
                    path_pattern = f"(src:{src_node_label} {{id: $src_id_param}}) -[rel:{rel_label}]-> (tgt:{tgt_node_label})"
                else:  # incoming
                    path_pattern = f"(src:{src_node_label} {{id: $src_id_param}}) <-[rel:{rel_label}]- (tgt:{tgt_node_label})"
                match_parts.append(path_pattern)

                if traversal.target_object_id:
                    param_key_tgt_id = f"tgt_id_param_{traversal_idx}"
                    where_clauses.append(f"tgt.id = ${param_key_tgt_id}")
                    # Pass UUID object directly if target_object_id is UUID
                    params[param_key_tgt_id] = traversal.target_object_id if isinstance(traversal.target_object_id, UUID) else str(traversal.target_object_id)

                if traversal.target_object_properties:
                    for prop_idx, prop_filter in enumerate(
                        traversal.target_object_properties,
                    ):
                        prop_name_in_cypher = prop_filter.property_name
                        param_key_prop_val = f"tgt_prop_val_{traversal_idx}_{prop_idx}"

                        if prop_filter.operator.upper() == "IN":
                            if not isinstance(prop_filter.value, (list, tuple)):
                                msg = f"Value for IN operator on property '{prop_name_in_cypher}' must be a list/tuple."
                                raise ValueError(
                                    msg,
                                )
                            if not prop_filter.value:
                                where_clauses.append("false")
                                continue

                            list_literal_items = []
                            for item in prop_filter.value:
                                if isinstance(item, str):
                                    list_literal_items.append(f"'{item}'")
                                elif isinstance(item, bool):
                                    list_literal_items.append(str(item).lower())
                                else:
                                    list_literal_items.append(str(item))

                            where_clauses.append(
                                f"tgt.{prop_name_in_cypher} IN [{', '.join(list_literal_items)}]",
                            )
                        else: # For operators like ==, !=, >, < etc.
                            operator_to_use = "=" if prop_filter.operator == "==" else prop_filter.operator
                            # Embed string literals for equality/inequality checks for robustness with Kuzu
                            if isinstance(prop_filter.value, str) and operator_to_use in ["=", "!="]: # Refined condition
                                escaped_value = prop_filter.value.replace("'", "''")
                                where_clauses.append(
                                    f"tgt.{prop_name_in_cypher} {operator_to_use} '{escaped_value}'",
                                )
                                # No parameter needed as it's embedded
                            elif isinstance(prop_filter.value, UUID): # Check if value is UUID
                                where_clauses.append(
                                    f"tgt.{prop_name_in_cypher} {operator_to_use} ${param_key_prop_val}",
                                )
                                params[param_key_prop_val] = prop_filter.value # Pass UUID object
                            else: # For numbers, booleans, or other operators with strings
                                where_clauses.append(
                                    f"tgt.{prop_name_in_cypher} {operator_to_use} ${param_key_prop_val}",
                                )
                                params[param_key_prop_val] = prop_filter.value

                query_str = f"MATCH {', '.join(match_parts)}"
                if where_clauses:
                    query_str += " WHERE " + " AND ".join(where_clauses)
                query_str += " RETURN count(tgt)" # Changed from RETURN true LIMIT 1

                # Diagnostic print (now commented out)
                # print(f"DEBUG: Query for obj_id {obj_id}, traversal {traversal_idx}:")
                # print(f"DEBUG: Query String: {query_str}")
                # print(f"DEBUG: Parameters: {params}")

                try:
                    prepared_statement = self.conn.prepare(query_str)
                    raw_query_result = self.conn.execute(
                        prepared_statement, parameters=params,
                    )

                    actual_query_result: Optional[kuzu.query_result.QueryResult] = None
                    if isinstance(raw_query_result, list):
                        if raw_query_result:
                            actual_query_result = raw_query_result[0]
                    else:
                        actual_query_result = raw_query_result

                        if not actual_query_result or not actual_query_result.has_next():
                            current_id_satisfies_all = False
                            break

                        # If query is "RETURN count(tgt)", get_next()[0] will be the count
                        count_result = actual_query_result.get_next()[0]
                        if not isinstance(count_result, int) or count_result == 0:
                            current_id_satisfies_all = False
                            break
                except RuntimeError as runtime_kuzu_error: # Catch generic RuntimeError
                    err_msg_lower = str(runtime_kuzu_error).lower()
                    # Check for common Kuzu messages indicating a schema problem (e.g., table not found, binder issues)
                    # These are typically indicative of issues Kuzu itself reports at a schema/query binding level.
                    is_kuzu_schema_issue = (
                        ("table" in err_msg_lower and "does not exist" in err_msg_lower) or
                        ("binder exception" in err_msg_lower) or
                        ("catalog exception" in err_msg_lower) or # Another common Kuzu schema error
                        ("cannot delete node table" in err_msg_lower and "referenced by relationship" in err_msg_lower)
                    )
                    if is_kuzu_schema_issue:
                        raise SchemaError(f"Kuzu schema/binder error during traversal query: {runtime_kuzu_error}") from runtime_kuzu_error
                    # For other RuntimeErrors not identified as schema issues,
                    # assume the traversal for this specific obj_id failed.
                    current_id_satisfies_all = False
                    break
                except (SchemaError, DatabaseError) as db_exc: # Our own specific errors
                    raise db_exc
                except Exception: # Catch-all for other truly unexpected errors (non-Runtime, non-Grizabella specific)
                    current_id_satisfies_all = False
                    break

            if current_id_satisfies_all:
                final_matching_ids.append(obj_id)

        return final_matching_ids
