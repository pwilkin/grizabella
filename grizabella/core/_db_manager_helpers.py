"""Internal helper classes for GrizabellaDBManager."""

import logging
import threading  # For logging thread ID
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter
from grizabella.db_layers.lancedb.lancedb_adapter import LanceDBAdapter
from grizabella.db_layers.sqlite.sqlite_adapter import SQLiteAdapter

from .exceptions import (
    ConfigurationError,
    DatabaseError,
    EmbeddingError,
    InstanceError,
    SchemaError,
)
from .models import (
    EmbeddingDefinition,
    EmbeddingInstance,
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDefinition,  # Added for new method
    RelationInstance,  # Added for new methods
    RelationTypeDefinition,  # Added for new methods
)


class _ConnectionHelper:  # pylint: disable=R0902
    """Internal helper to manage database adapter connections."""

    def __init__(
        self,
        sqlite_db_file_path_str: str,
        lancedb_uri_str: str,
        kuzu_path_str: str,
        manager_logger: logging.Logger,
    ) -> None:
        import threading  # For logging thread ID
        self._logger = manager_logger # Ensure logger is set first
        self._logger.info(f"_ConnectionHelper: Initializing in thread ID: {threading.get_ident()}")
        self.sqlite_db_file_path: str = sqlite_db_file_path_str
        self.lancedb_uri: str = lancedb_uri_str
        self.kuzu_path: str = kuzu_path_str
        self._logger = manager_logger

        self._sqlite_adapter_instance: Optional[SQLiteAdapter] = None
        self._lancedb_adapter_instance: Optional[LanceDBAdapter] = None
        self._kuzu_adapter_instance: Optional[KuzuAdapter] = None
        self._adapters_are_connected: bool = False

    @property
    def sqlite_adapter(self) -> SQLiteAdapter:
        """Provides access to the SQLite adapter instance."""
        if not self._sqlite_adapter_instance or not self._adapters_are_connected:
            self._logger.error("Attempted to access SQLite adapter when not connected.")
            msg = "SQLite adapter not connected or available."
            raise DatabaseError(msg)
        return self._sqlite_adapter_instance

    @property
    def lancedb_adapter(self) -> LanceDBAdapter:
        """Provides access to the LanceDB adapter instance."""
        if not self._lancedb_adapter_instance or not self._adapters_are_connected:
            self._logger.error(
                "Attempted to access LanceDB adapter when not connected.",
            )
            msg = "LanceDB adapter not connected or available."
            raise DatabaseError(msg)
        return self._lancedb_adapter_instance

    @property
    def kuzu_adapter(self) -> "KuzuAdapter":
        """Provides access to the Kuzu adapter instance."""
        if not self._kuzu_adapter_instance or not self._adapters_are_connected:
            self._logger.error("Attempted to access Kuzu adapter when not connected.")
            msg = "Kuzu adapter not connected or available."
            raise DatabaseError(msg)
        return self._kuzu_adapter_instance

    @property
    def is_connected(self) -> bool:
        """Checks if all adapters are instantiated and report being connected."""
        return bool(
            self._adapters_are_connected
            and self._sqlite_adapter_instance
            and self._sqlite_adapter_instance.conn
            and self._lancedb_adapter_instance
            and self._kuzu_adapter_instance
            and self._kuzu_adapter_instance.conn,
        )

    def connect_all_adapters(self) -> None:
        """Connects all managed database adapters."""
        if self._adapters_are_connected:
            self._logger.debug(
                "_ConnectionHelper: Adapters already reported as connected.",
            )
            return
        try:
            self._logger.info(
                "_ConnectionHelper: Connecting SQLiteAdapter to %s",
                self.sqlite_db_file_path,
            )
            # SQLiteAdapter's __init__ calls _connect which establishes the connection.
            # We'll add logging there.
            self._sqlite_adapter_instance = SQLiteAdapter(
                db_path=self.sqlite_db_file_path,
            ) # Logging for connection creation will be in SQLiteAdapter
            self._logger.info("_ConnectionHelper: SQLiteAdapter initialized (object created).")

            self._logger.info(
                "_ConnectionHelper: Connecting LanceDBAdapter to %s", self.lancedb_uri,
            )
            self._lancedb_adapter_instance = LanceDBAdapter(db_uri=self.lancedb_uri)
            self._logger.info("_ConnectionHelper: LanceDBAdapter initialized.")

            self._logger.info(
                "_ConnectionHelper: Connecting KuzuAdapter to %s", self.kuzu_path,
            )
            self._kuzu_adapter_instance = KuzuAdapter(db_path=self.kuzu_path)
            self._logger.info("_ConnectionHelper: KuzuAdapter initialized.")
            self._adapters_are_connected = True
            self._logger.info("_ConnectionHelper: All adapters connected successfully.")
        except DatabaseError as e:
            self._logger.error(
                "_ConnectionHelper: DatabaseError during adapter connection: %s",
                e,
                exc_info=True,
            )
            self.close_all_adapters()
            raise
        except Exception as e:
            self._logger.error(
                "_ConnectionHelper: Unexpected error during adapter connection: %s",
                e,
                exc_info=True,
            )
            self.close_all_adapters()
            msg = f"_ConnectionHelper: Failed to connect adapters: {e}"
            raise ConfigurationError(
                msg,
            ) from e

    def close_all_adapters(self) -> None:
        """Closes all managed database adapters and resets their instances."""
        self._logger.debug("_ConnectionHelper: Closing all adapters.")
        if self._sqlite_adapter_instance:
            try:
                self._sqlite_adapter_instance.close()
                self._logger.debug("_ConnectionHelper: SQLiteAdapter closed.")
            except DatabaseError as e:
                self._logger.warning(
                    "_ConnectionHelper: Error closing SQLiteAdapter: %s",
                    e,
                    exc_info=True,
                )
            finally:
                self._sqlite_adapter_instance = None
        if self._lancedb_adapter_instance:
            try:
                self._lancedb_adapter_instance.close()
                self._logger.debug("_ConnectionHelper: LanceDBAdapter closed.")
            except DatabaseError as e:
                self._logger.warning(
                    "_ConnectionHelper: Error closing LanceDBAdapter: %s",
                    e,
                    exc_info=True,
                )
            finally:
                self._lancedb_adapter_instance = None
        if self._kuzu_adapter_instance:
            try:
                self._kuzu_adapter_instance.close()
                self._logger.debug("_ConnectionHelper: KuzuAdapter closed.")
            except DatabaseError as e:
                self._logger.warning(
                    "_ConnectionHelper: Error closing KuzuAdapter: %s", e, exc_info=True,
                )
            finally:
                self._kuzu_adapter_instance = None
        self._adapters_are_connected = False
        self._logger.debug("_ConnectionHelper: All adapters closed and state reset.")


class _SchemaManager:
    """Internal helper to manage schema definitions and their persistence."""

    def __init__(self, conn_helper: _ConnectionHelper, manager_logger: logging.Logger) -> None:
        self._conn_helper = conn_helper
        self._logger = manager_logger
        self._object_type_definitions: dict[str, ObjectTypeDefinition] = {}
        self._embedding_definitions: dict[str, EmbeddingDefinition] = {}
        self._relation_type_definitions: dict[str, RelationTypeDefinition] = {}

    def load_all_definitions(self) -> None:
        """Loads all schema definitions from the SQLite adapter into the in-memory cache."""
        self._logger.debug("_SchemaManager: Loading all schema definitions.")
        sqlite_adapter = self._conn_helper.sqlite_adapter
        self._object_type_definitions = {
            otd.name: otd for otd in sqlite_adapter.list_object_type_definitions()
        }
        self._embedding_definitions = {
            ed.name: ed for ed in sqlite_adapter.list_embedding_definitions()
        }
        self._relation_type_definitions = {
            rtd.name: rtd for rtd in sqlite_adapter.list_relation_type_definitions()
        }
        self._logger.debug(
            "_SchemaManager: Loaded %s OTDs, %s EDs, %s RTDs.",
            len(self._object_type_definitions),
            len(self._embedding_definitions),
            len(self._relation_type_definitions),
        )
        # After loading, ensure Kuzu schema exists for all loaded definitions
        for otd in self._object_type_definitions.values():
            try:
                self._ensure_kuzu_schema_for_otd(otd) # New helper
            except Exception as e:
                self._logger.error(f"_SchemaManager: Error ensuring Kuzu schema for loaded OTD '{otd.name}': {e}", exc_info=True)

        for rtd in self._relation_type_definitions.values():
            try:
                self._ensure_kuzu_schema_for_rtd(rtd) # New helper
            except Exception as e:
                self._logger.error(f"_SchemaManager: Error ensuring Kuzu schema for loaded RTD '{rtd.name}': {e}", exc_info=True)


    def clear_all_definitions(self) -> None:
        """Clears all cached schema definitions."""
        self._object_type_definitions.clear()
        self._embedding_definitions.clear()
        self._relation_type_definitions.clear()
        self._logger.debug("_SchemaManager: All cached schema definitions cleared.")

    def add_object_type_definition(
        self, otd: ObjectTypeDefinition, persist: bool = True,
    ) -> None:
        """Adds or updates an OTD in cache and persists it, including table creation."""
        is_update = otd.name in self._object_type_definitions
        self._logger.info(
            "_SchemaManager: %s object type definition '%s'.",
            "Updating" if is_update else "Adding new",
            otd.name,
        )
        if persist:
            try:
                self._conn_helper.sqlite_adapter.save_object_type_definition(otd)
                self._conn_helper.sqlite_adapter.create_object_type_table(otd)
                self._logger.debug(
                    "_SchemaManager: OTD '%s' saved and table ensured in SQLite.",
                    otd.name,
                )
            except (DatabaseError, SchemaError) as e:
                self._logger.error(
                    "_SchemaManager: Error persisting/creating table for OTD '%s': %s",
                    otd.name,
                    e,
                    exc_info=True,
                )
                raise
        self._object_type_definitions[otd.name] = otd
        self._ensure_kuzu_schema_for_otd(otd)

    def _ensure_kuzu_schema_for_otd(self, otd: ObjectTypeDefinition) -> None:
        """Ensures Kuzu node table exists for the given OTD."""
        self._logger.info(f"_SchemaManager: Ensuring Kuzu node table for OTD '{otd.name}'.")
        try:
            # First check if the node table already exists in Kuzu
            existing_tables = self._conn_helper.kuzu_adapter.list_object_types()
            if otd.name in existing_tables:
                self._logger.debug(f"Kuzu node table for OTD '{otd.name}' already exists. Skipping creation.")
                return

            # If not, create it
            self._conn_helper.kuzu_adapter.create_node_table(otd)
            self._logger.info(
                "_SchemaManager: Kuzu node table created for OTD '%s'.",
                otd.name,
            )
        except (SchemaError, DatabaseError) as e:
            self._logger.error(
                "_SchemaManager: Error ensuring Kuzu node table for OTD '%s': %s.",
                otd.name,
                e,
                exc_info=True,
            )
            raise # Re-raise to signal failure
        except Exception as e_unexp:
            self._logger.error(
                "_SchemaManager: Unexpected error ensuring Kuzu node table for OTD '%s': %s.",
                otd.name,
                e_unexp,
                exc_info=True,
            )
            raise SchemaError(f"Unexpected error during Kuzu node table ensure for {otd.name}: {e_unexp}") from e_unexp

    def get_object_type_definition(self, name: str) -> Optional[ObjectTypeDefinition]:
        """Retrieves an OTD from the cache by its name."""
        return self._object_type_definitions.get(name)

    def list_object_type_definitions(self) -> list[ObjectTypeDefinition]:
        """Lists all cached OTDs."""
        return list(self._object_type_definitions.values())

    def get_property_definition_for_object_type(
        self, object_type_name: str, property_name: str,
    ) -> Optional[
        "PropertyDefinition"
    ]:  # Forward ref if PropertyDefinition not imported yet
        """Retrieves a specific PropertyDefinition for a given ObjectTypeDefinition.

        Args:
            object_type_name: The name of the ObjectTypeDefinition.
            property_name: The name of the property to retrieve.

        Returns:
            The PropertyDefinition if found, else None.

        """
        otd = self.get_object_type_definition(object_type_name)
        if otd:
            for prop_def in otd.properties:
                if prop_def.name == property_name:
                    return prop_def
        return None

    def remove_object_type_definition(self, name: str, persist: bool = True) -> bool:
        """Removes an OTD from cache and underlying databases if persist is True."""
        if name not in self._object_type_definitions:
            self._logger.warning(
                "_SchemaManager: Attempted to remove non-existent OTD '%s'.", name,
            )
            return False
        if persist:
            try:
                try:
                    self._conn_helper.kuzu_adapter.drop_node_table(name)
                    self._logger.info(
                        "_SchemaManager: Kuzu node table drop initiated for OTD '%s'.",
                        name,
                    )
                except (SchemaError, DatabaseError) as e:
                    self._logger.error(
                        "_SchemaManager: Error dropping Kuzu node table for OTD '%s': %s.",
                        name,
                        e,
                        exc_info=True,
                    )
                self._conn_helper.sqlite_adapter.drop_object_type_table(name)
                if not self._conn_helper.sqlite_adapter.delete_object_type_definition(
                    name,
                ):
                    self._logger.warning(
                        "_SchemaManager: SQLite def for '%s' not found for deletion.",
                        name,
                    )
                self._logger.debug(
                    "_SchemaManager: OTD '%s' and table removed from SQLite.", name,
                )
            except (DatabaseError, SchemaError) as e:
                self._logger.error(
                    "_SchemaManager: Error removing OTD '%s' from SQLite: %s",
                    name,
                    e,
                    exc_info=True,
                )
                raise
        del self._object_type_definitions[name]
        return True

    def add_embedding_definition(
        self, ed: EmbeddingDefinition, persist: bool = True,
    ) -> None:
        """Adds or updates an ED in cache and persists it, including table creation."""
        self._logger.debug(
            "_SchemaManager: Received request to add ED '%s' for OTD '%s', property '%s', model '%s', dimensions: %s.",
            ed.name,
            ed.object_type_name,
            ed.source_property_name,
            ed.embedding_model,
            ed.dimensions,
        )
        otd = self.get_object_type_definition(ed.object_type_name)
        if not otd:
            msg = f"Cannot add ED '{ed.name}': OTD '{ed.object_type_name}' does not exist."
            self._logger.error(msg)
            raise SchemaError(
                msg,
            )
        if not any(p.name == ed.source_property_name for p in otd.properties):
            msg = (
                f"Cannot add ED '{ed.name}': Property '{ed.source_property_name}' not in OTD "
                f"'{otd.name}'."
            )
            self._logger.error(msg)
            raise SchemaError(
                msg,
            )

        if ed.dimensions is None:
            self._logger.info(
                "_SchemaManager: ED '%s' has no dimensions specified. Attempting to infer from model '%s'.",
                ed.name,
                ed.embedding_model,
            )
            try:
                embedding_model_obj = self._conn_helper.lancedb_adapter.get_embedding_model(
                    ed.embedding_model,
                )
                # Try to get dimensions using ndims() first, common for LanceDB embedding functions
                if hasattr(embedding_model_obj, "ndims") and callable(embedding_model_obj.ndims):
                    try:
                        inferred_dims = embedding_model_obj.ndims()
                        if inferred_dims and isinstance(inferred_dims, int) and inferred_dims > 0:
                            ed.dimensions = inferred_dims
                            self._logger.info(
                                "_SchemaManager: Inferred dimensions for ED '%s' as %s from model '%s' using ndims().",
                                ed.name,
                                ed.dimensions,
                                ed.embedding_model,
                            )
                        else:
                            self._logger.warning(
                                "_SchemaManager: model.ndims() for ED '%s' (model '%s') returned non-positive or invalid value: %s.",
                                ed.name,
                                ed.embedding_model,
                                inferred_dims,
                            )
                    except Exception as e_ndims:
                        self._logger.warning(
                            "_SchemaManager: Error calling model.ndims() for ED '%s' (model '%s'): %s. Will try fallback.",
                            ed.name,
                            ed.embedding_model,
                            e_ndims,
                        )

                if ed.dimensions is None: # If ndims() didn't work or wasn't available, try encoding a dummy string
                    self._logger.info(
                        "_SchemaManager: ED '%s' (model '%s') - ndims() did not yield dimension. Trying dummy string encoding.",
                        ed.name,
                        ed.embedding_model,
                    )
                    try:
                        # Use compute_source_embeddings for TransformersEmbeddingFunction
                        dummy_embeddings = embedding_model_obj.compute_source_embeddings(["test"])
                        if isinstance(dummy_embeddings, list) and len(dummy_embeddings) > 0:
                            first_embedding = dummy_embeddings[0]
                            if hasattr(first_embedding, "shape") and len(first_embedding.shape) > 0: # numpy array
                                inferred_dims = first_embedding.shape[-1]
                            elif isinstance(first_embedding, list): # list of floats
                                inferred_dims = len(first_embedding)
                            else:
                                inferred_dims = 0
                                self._logger.warning(
                                    "_SchemaManager: Dummy encoding for ED '%s' (model '%s') produced an unexpected embedding type: %s.",
                                    ed.name,
                                    ed.embedding_model,
                                    type(first_embedding),
                                )

                            if inferred_dims and isinstance(inferred_dims, int) and inferred_dims > 0:
                                ed.dimensions = inferred_dims
                                self._logger.info(
                                    "_SchemaManager: Inferred dimensions for ED '%s' as %s via dummy encoding with model '%s'.",
                                    ed.name,
                                    ed.dimensions,
                                    ed.embedding_model,
                                )
                            else:
                                self._logger.warning(
                                    "_SchemaManager: Could not infer a valid positive dimension for ED '%s' from model '%s' via dummy encoding. Inferred_dims: %s.",
                                    ed.name,
                                    ed.embedding_model,
                                    inferred_dims,
                                )
                        else:
                            self._logger.warning(
                                "_SchemaManager: Dummy encoding for ED '%s' (model '%s') did not return a list of embeddings or returned empty list.",
                                ed.name,
                                ed.embedding_model,
                            )
                    except Exception as e_encode:
                         self._logger.warning(
                            "_SchemaManager: Error during dummy string encoding for ED '%s' (model '%s'): %s.",
                            ed.name,
                            ed.embedding_model,
                            e_encode,
                        )


                if ed.dimensions is None: # If still None after all attempts
                    msg = (
                        f"Failed to infer dimensions for ED '{ed.name}' using model "
                        f"'{ed.embedding_model}'. LanceDB requires explicit dimensions."
                    )
                    self._logger.error(msg)
                    # Raise SchemaError here as LanceDBAdapter will fail anyway
                    raise SchemaError(msg)

            except EmbeddingError as e_inf:
                self._logger.error(
                    "_SchemaManager: EmbeddingError during dimension inference for ED '%s': %s. Cannot proceed.",
                    ed.name,
                    e_inf,
                    exc_info=True,
                )
                raise SchemaError(
                    f"Failed to infer dimensions for ED '{ed.name}' due to EmbeddingError: {e_inf}",
                ) from e_inf
            except Exception as e_gen: # pylint: disable=broad-except
                self._logger.error(
                    "_SchemaManager: Unexpected error during dimension inference for ED '%s': %s. Cannot proceed.",
                    ed.name,
                    e_gen,
                    exc_info=True,
                )
                raise SchemaError(
                    f"Unexpected error during dimension inference for ED '{ed.name}': {e_gen}",
                ) from e_gen


        if persist:
            try:
                self._conn_helper.sqlite_adapter.save_embedding_definition(ed)
                self._logger.debug("_SchemaManager: ED '%s' (dimensions: %s) saved to SQLite.", ed.name, ed.dimensions)
            except DatabaseError as e:
                self._logger.error(
                    "_SchemaManager: Error persisting ED '%s' to SQLite: %s",
                    ed.name,
                    e,
                    exc_info=True,
                )
                raise
            try:
                self._conn_helper.lancedb_adapter.create_embedding_table(ed)
                self._logger.info(
                    "_SchemaManager: LanceDB table creation initiated for ED '%s' (dimensions: %s).",
                    ed.name,
                    ed.dimensions,
                )
            except (SchemaError, DatabaseError, EmbeddingError) as e:
                self._logger.error(
                    "_SchemaManager: Error creating LanceDB table for ED '%s': %s.",
                    ed.name,
                    e,
                    exc_info=True,
                )
                raise
        self._embedding_definitions[ed.name] = ed

    def get_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:
        """Retrieves an ED from the cache by its name."""
        return self._embedding_definitions.get(name)

    def list_embedding_definitions(self) -> list[EmbeddingDefinition]:
        """Lists all cached EDs."""
        return list(self._embedding_definitions.values())

    def remove_embedding_definition(self, name: str, persist: bool = True) -> bool:
        """Removes an ED from cache and underlying databases if persist is True."""
        if name not in self._embedding_definitions:
            self._logger.warning(
                "_SchemaManager: Attempted to remove non-existent ED '%s'.", name,
            )
            return False
        if persist:
            try:
                self._conn_helper.sqlite_adapter.delete_embedding_definition(name)
                self._logger.debug("_SchemaManager: ED '%s' removed from SQLite.", name)
                try:
                    self._conn_helper.lancedb_adapter.drop_embedding_table(name)
                    self._logger.info(
                        "_SchemaManager: LanceDB table drop initiated for ED '%s'.",
                        name,
                    )
                except (DatabaseError, EmbeddingError) as e:
                    self._logger.error(
                        "_SchemaManager: Error dropping LanceDB table for ED '%s': %s.",
                        name,
                        e,
                        exc_info=True,
                    )
            except DatabaseError as e:
                self._logger.error(
                    "_SchemaManager: Error removing ED '%s' from SQLite: %s",
                    name,
                    e,
                    exc_info=True,
                )
                raise
        del self._embedding_definitions[name]
        self._logger.info("_SchemaManager: ED '%s' removed from cache.", name)
        return True

    def add_relation_type_definition(
        self, rtd: RelationTypeDefinition, persist: bool = True,
    ) -> None:
        """Adds or updates an RTD in cache and persists it, including table creation."""
        if not rtd.source_object_type_names:
            msg = f"Cannot add RTD '{rtd.name}': source_object_type_names is empty."
            raise SchemaError(
                msg,
            )
        if not rtd.target_object_type_names:
            msg = f"Cannot add RTD '{rtd.name}': target_object_type_names is empty."
            raise SchemaError(
                msg,
            )

        # Validate that the first source and target OTDs exist
        if not self.get_object_type_definition(rtd.source_object_type_names[0]):
            msg = f"Source OTD '{rtd.source_object_type_names[0]}' for RTD '{rtd.name}' not found."
            raise SchemaError(
                msg,
            )
        if not self.get_object_type_definition(rtd.target_object_type_names[0]):
            msg = f"Target OTD '{rtd.target_object_type_names[0]}' for RTD '{rtd.name}' not found."
            raise SchemaError(
                msg,
            )

        if persist:
            try:
                self._conn_helper.sqlite_adapter.save_relation_type_definition(rtd)
                self._logger.debug(
                    "_SchemaManager: RTD '%s' saved to SQLite.", rtd.name,
                )
            except DatabaseError as e:
                self._logger.error(
                    "_SchemaManager: Error persisting RTD '%s': %s",
                    rtd.name,
                    e,
                    exc_info=True,
                )
                raise
        self._relation_type_definitions[rtd.name] = rtd
        self._ensure_kuzu_schema_for_rtd(rtd)

    def _ensure_kuzu_schema_for_rtd(self, rtd: RelationTypeDefinition) -> None:
        """Ensures Kuzu node tables for source/target OTDs and the Kuzu relation table exist."""
        self._logger.info(f"_SchemaManager: Ensuring Kuzu schema for RTD '{rtd.name}'.")
        # Ensure source and target node tables exist in Kuzu
        object_type_names_to_ensure = set(rtd.source_object_type_names + rtd.target_object_type_names)
        self._logger.debug(f"_SchemaManager: Ensuring Kuzu node tables exist for: {object_type_names_to_ensure} for RTD '{rtd.name}'")

        try:
            existing_kuzu_node_tables = self._conn_helper.kuzu_adapter.list_object_types()
        except Exception as e_list_kuzu: # pylint: disable=broad-except
            self._logger.warning(f"_SchemaManager: Could not list existing Kuzu node tables: {e_list_kuzu}. Will attempt creation regardless.")
            existing_kuzu_node_tables = []

        for ot_name in object_type_names_to_ensure:
            otd_from_cache = self.get_object_type_definition(ot_name)
            if not otd_from_cache:
                msg = (
                    f"_SchemaManager: Cannot ensure Kuzu schema for RTD '{rtd.name}'. "
                    f"Referenced ObjectTypeDefinition '{ot_name}' not found in SQLite/cache."
                )
                self._logger.error(msg)
                raise SchemaError(msg)

            if ot_name not in existing_kuzu_node_tables:
                self._logger.info(
                    "_SchemaManager: Kuzu node table for OTD '%s' (dependency for RTD '%s') does not exist. Attempting to create it.",
                    ot_name,
                    rtd.name,
                )
                try:
                    # Use the _ensure_kuzu_schema_for_otd helper for consistency and error handling
                    self._ensure_kuzu_schema_for_otd(otd_from_cache)
                except (SchemaError, DatabaseError) as e_create_node: # Catch specific errors from helper
                    msg = (
                        f"_SchemaManager: Failed to create prerequisite Kuzu node table for OTD '{ot_name}' "
                        f"while preparing for RTD '{rtd.name}': {e_create_node}"
                    )
                    self._logger.error(msg, exc_info=True)
                    raise SchemaError(msg) from e_create_node
            else:
                self._logger.debug(f"_SchemaManager: Kuzu node table for OTD '{ot_name}' already exists.")

        # Now ensure the relation table itself exists
        try:
            # KuzuAdapter.create_rel_table should be idempotent or handle "already exists"
            # It internally calls list_relation_types to check if table exists.
            self._conn_helper.kuzu_adapter.create_rel_table(rtd)
            self._logger.info(
                "_SchemaManager: Kuzu relation table ensured/created for RTD '%s'.",
                rtd.name,
            )
        except (SchemaError, DatabaseError) as e:
            self._logger.error(
                "_SchemaManager: Error ensuring Kuzu rel table for RTD '%s': %s.",
                rtd.name,
                e,
                exc_info=True,
            )
            raise
        except Exception as e_unexp:
            self._logger.error(
                "_SchemaManager: Unexpected error ensuring Kuzu rel table for RTD '%s': %s.",
                rtd.name,
                e_unexp,
                exc_info=True,
            )
            raise SchemaError(f"Unexpected error during Kuzu rel table ensure for {rtd.name}: {e_unexp}") from e_unexp

    def get_relation_type_definition(
        self, name: str,
    ) -> Optional[RelationTypeDefinition]:
        """Retrieves an RTD from the cache by its name."""
        return self._relation_type_definitions.get(name)

    def list_relation_type_definitions(self) -> list[RelationTypeDefinition]:
        """Lists all cached RTDs."""
        return list(self._relation_type_definitions.values())

    def remove_relation_type_definition(self, name: str, persist: bool = True) -> bool:
        """Removes an RTD from cache and underlying databases if persist is True."""
        if name not in self._relation_type_definitions:
            return False
        if persist:
            try:
                try:
                    self._conn_helper.kuzu_adapter.drop_rel_table(name)
                    self._logger.info(
                        "_SchemaManager: Kuzu rel table drop initiated for RTD '%s'.",
                        name,
                    )
                except (SchemaError, DatabaseError) as e:
                    self._logger.error(
                        "_SchemaManager: Error dropping Kuzu rel table for RTD '%s': %s.",
                        name,
                        e,
                        exc_info=True,
                    )
                self._conn_helper.sqlite_adapter.delete_relation_type_definition(name)
                self._logger.debug(
                    "_SchemaManager: RTD '%s' removed from SQLite.", name,
                )
            except DatabaseError as e:
                self._logger.error(
                    "_SchemaManager: Error removing RTD '%s' from SQLite: %s",
                    name,
                    e,
                    exc_info=True,
                )
                raise
        del self._relation_type_definitions[name]
        return True


class _InstanceManager:
    """Internal helper to manage object instances and their embeddings."""

    def __init__(
        self,
        conn_helper: _ConnectionHelper,
        schema_manager: _SchemaManager,
        manager_logger: logging.Logger,
    ) -> None:
        self._conn_helper = conn_helper
        self._schema_manager = schema_manager
        self._logger = manager_logger

    def add_object_instance(self, instance: ObjectInstance) -> None:
        """Adds an object instance to the SQLite database."""
        if not self._schema_manager.get_object_type_definition(
            instance.object_type_name,
        ):
            msg = f"Cannot add instance: OTD '{instance.object_type_name}' not found."
            raise SchemaError(
                msg,
            )
        try:
            self._conn_helper.sqlite_adapter.add_object_instance(instance)
            self._logger.debug(
                "Object instance '%s' of type '%s' added.",
                instance.id,
                instance.object_type_name,
            )
        except (DatabaseError, InstanceError, SchemaError) as e:
            self._logger.error(
                "Error adding object instance '%s': %s", instance.id, e, exc_info=True,
            )
            raise

    def get_object_instance(
        self, object_type_name: str, instance_id: Any,
    ) -> Optional[ObjectInstance]:
        """Retrieves an object instance from SQLite by its type and ID."""
        if not self._schema_manager.get_object_type_definition(object_type_name):
            self._logger.warning(
                "Attempting to get instance of undefined OTD '%s'.", object_type_name,
            )
            return None
        try:
            return self._conn_helper.sqlite_adapter.get_object_instance(
                object_type_name, instance_id,
            )
        except (DatabaseError, SchemaError) as e:
            self._logger.error(
                "Error getting OI '%s' of type '%s': %s",
                instance_id,
                object_type_name,
                e,
                exc_info=True,
            )
            raise

    def update_object_instance(self, instance: ObjectInstance) -> None:
        """Updates an existing object instance in SQLite."""
        if not self._schema_manager.get_object_type_definition(
            instance.object_type_name,
        ):
            msg = f"Cannot update instance: OTD '{instance.object_type_name}' not found."
            raise SchemaError(
                msg,
            )
        try:
            self._conn_helper.sqlite_adapter.update_object_instance(instance)
            self._logger.debug(
                "Object instance '%s' of type '%s' updated.",
                instance.id,
                instance.object_type_name,
            )
        except (DatabaseError, InstanceError, SchemaError) as e:
            self._logger.error(
                "Error updating object instance '%s': %s", instance.id, e, exc_info=True,
            )
            raise

    def upsert_object_instance(self, instance: ObjectInstance) -> ObjectInstance:
        """Upserts an OI to SQLite and handles its embeddings in LanceDB."""
        self._logger.info(f"_InstanceManager: upsert_object_instance called in thread ID: {threading.get_ident()} for instance ID: {instance.id}, type: {instance.object_type_name}")
        otd = self._schema_manager.get_object_type_definition(instance.object_type_name)
        if not otd:
            msg = f"Cannot upsert instance: OTD '{instance.object_type_name}' not found."
            raise SchemaError(
                msg,
            )

        # Ensure upsert_date reflects the current operation time
        instance.upsert_date = datetime.now(timezone.utc)

        returned_instance: Optional[ObjectInstance] = None
        try:
            returned_instance = self._conn_helper.sqlite_adapter.upsert_object_instance(
                instance,
            )
            self._logger.debug(
                "OI '%s' of type '%s' upserted to SQLite.",
                instance.id,
                instance.object_type_name,
            )
            applicable_eds = [
                ed
                for ed in self._schema_manager.list_embedding_definitions()
                if ed.object_type_name == instance.object_type_name
            ]
            for ed_instance in applicable_eds:
                try:
                    self._conn_helper.lancedb_adapter.delete_embedding_instances_for_object(
                        instance.id, ed_instance.name,
                    )
                    self._logger.debug(
                        "Deleted existing embeddings for OI '%s', def '%s'.",
                        instance.id,
                        ed_instance.name,
                    )
                except Exception as e:  # pylint: disable=broad-except
                    self._logger.error(
                        "Error deleting old embeddings for OI '%s', def '%s': %s",
                        instance.id,
                        ed_instance.name,
                        e,
                        exc_info=True,
                    )  # Continue if one embedding fails
                text_to_embed = instance.properties.get(
                    ed_instance.source_property_name,
                )
                if isinstance(text_to_embed, str) and text_to_embed.strip():
                    try:
                        embedding_model_func = self._conn_helper.lancedb_adapter.get_embedding_model(
                            ed_instance.embedding_model,
                        )
                        # Use compute_source_embeddings for TransformersEmbeddingFunction
                        raw_embeddings_list = embedding_model_func.compute_source_embeddings([text_to_embed])
                        if not raw_embeddings_list:
                             self._logger.error(
                                "Model '%s' for OI '%s' returned empty list for text: %s",
                                ed_instance.embedding_model, instance.id, text_to_embed[:50],
                            )
                             raise EmbeddingError(f"Model {ed_instance.embedding_model} returned empty list for text.")

                        raw_vector = raw_embeddings_list[0]

                        if hasattr(raw_vector, "tolist"): # Handles numpy array
                            vector = raw_vector.tolist()
                        elif isinstance(raw_vector, list):
                            vector = raw_vector
                        else:
                            self._logger.error(
                                "Unexpected vector type from model '%s' for OI '%s': %s",
                                ed_instance.embedding_model, instance.id, type(raw_vector),
                            )
                            raise EmbeddingError(f"Unexpected vector type from model {ed_instance.embedding_model}")

                        preview = (
                            text_to_embed[:200] + "..."
                            if len(text_to_embed) > 200
                            else text_to_embed
                        )
                        embedding_instance_obj = EmbeddingInstance(
                            object_instance_id=instance.id,
                            embedding_definition_name=ed_instance.name,
                            vector=vector,
                            source_text_preview=preview,
                        )
                        self._conn_helper.lancedb_adapter.upsert_embedding_instance(
                            embedding_instance_obj, ed_instance,
                        )
                        self._logger.info(
                            "Generated/stored embedding for OI '%s' using def '%s'.",
                            instance.id,
                            ed_instance.name,
                        )
                    except EmbeddingError as ee:
                        self._logger.error(
                            "EmbeddingError for OI '%s', def '%s': %s",
                            instance.id,
                            ed_instance.name,
                            ee,
                            exc_info=True,
                        )  # Continue if one embedding fails
                    except Exception as e:  # pylint: disable=broad-except
                        self._logger.error(
                            "Unexpected error generating/storing embedding for OI '%s', "
                            "def '%s': %s",
                            instance.id,
                            ed_instance.name,
                            e,
                            exc_info=True,
                        )  # Continue if one embedding fails
                else:
                    self._logger.debug(
                        "No text for property '%s' in OI '%s'. Skipping embedding for def '%s'.",
                        ed_instance.source_property_name,
                        instance.id,
                        ed_instance.name,
                    )
            if returned_instance is None:
                msg = f"Upsert operation failed to return an instance for {instance.id}"
                raise InstanceError(
                    msg,
                )

            # Kuzu operation for ObjectInstance
            try:
                self._conn_helper.kuzu_adapter.upsert_object_instance(returned_instance)
                self._logger.info(
                    "OI '%s' of type '%s' upserted to Kuzu.",
                    instance.id,
                    instance.object_type_name,
                )
            except (DatabaseError, InstanceError, SchemaError) as e:
                self._logger.error(
                    "Error upserting OI '%s' to Kuzu: %s", instance.id, e, exc_info=True,
                )
                # Decide on error handling: re-raise, or just log?
                # For now, re-raise to make it visible.
                raise

            return returned_instance
        except (DatabaseError, InstanceError, SchemaError) as e:
            self._logger.error(
                "Error upserting OI '%s' (SQLite/pre-embedding/Kuzu): %s",
                instance.id,
                e,
                exc_info=True,
            )
            raise
        except Exception as e:  # pylint: disable=broad-except
            self._logger.error(
                "Unexpected error during embedding or Kuzu processing for OI '%s': %s",
                instance.id,
                e,
                exc_info=True,
            )
            msg = f"Failed during embedding or Kuzu processing for {instance.id}: {e}"
            raise DatabaseError(
                msg,
            ) from e

    def delete_object_instance(self, object_type_name: str, instance_id: Any) -> bool:
        """Deletes an OI from SQLite, its embeddings from LanceDB, and node from Kuzu."""
        otd = self._schema_manager.get_object_type_definition(object_type_name)
        if not otd:
            self._logger.warning(
                "Attempting to delete instance of undefined OTD '%s'.", object_type_name,
            )
            return False

        deleted_sqlite = False
        deleted_kuzu = False
        deleted_lancedb = False

        try:
            # LanceDB deletion (embeddings) - collect results
            applicable_eds = [
                ed
                for ed in self._schema_manager.list_embedding_definitions()
                if ed.object_type_name == object_type_name
            ]
            lancedb_errors = []
            for ed_instance in applicable_eds:
                try:
                    lancedb_result = self._conn_helper.lancedb_adapter.delete_embedding_instances_for_object(
                        instance_id, ed_instance.name,
                    )
                    if lancedb_result:
                        self._logger.info(
                            "Deleted embeddings for OI '%s' using def '%s' from LanceDB.",
                            instance_id,
                            ed_instance.name,
                        )
                        deleted_lancedb = True
                    else:
                        self._logger.debug(
                            "No embeddings found for OI '%s' using def '%s' in LanceDB.",
                            instance_id,
                            ed_instance.name,
                        )
                except Exception as e:  # pylint: disable=broad-except
                    lancedb_errors.append(f"ED '{ed_instance.name}': {e}")
                    self._logger.error(
                        "Error deleting embeddings for OI '%s', def '%s' from LanceDB: %s",
                        instance_id,
                        ed_instance.name,
                        e,
                        exc_info=True,
                    )  # Log and continue, as main deletion might still succeed

            # Report LanceDB deletion summary
            if lancedb_errors:
                self._logger.warning(
                    "LanceDB deletion completed with %d errors for OI '%s': %s",
                    len(lancedb_errors),
                    instance_id,
                    "; ".join(lancedb_errors[:3]),  # Limit error details in summary
                )

            # Kuzu deletion
            try:
                deleted_kuzu = self._conn_helper.kuzu_adapter.delete_object_instance(
                    object_type_name, instance_id,
                )
                if deleted_kuzu:
                    self._logger.info(
                        "OI '%s' of type '%s' deleted from Kuzu.",
                        instance_id,
                        object_type_name,
                    )
                else:
                    self._logger.warning(
                        "OI '%s' of type '%s' not found in Kuzu or delete failed.",
                        instance_id,
                        object_type_name,
                    )
            except (DatabaseError, InstanceError, SchemaError) as e:
                self._logger.error(
                    "Error deleting OI '%s' from Kuzu: %s",
                    instance_id,
                    e,
                    exc_info=True,
                )
                # Don't re-raise here - continue with SQLite deletion for partial cleanup

            # SQLite deletion (master record) - do this last as it's the primary store
            try:
                deleted_sqlite = self._conn_helper.sqlite_adapter.delete_object_instance(
                    object_type_name, instance_id,
                )
                if deleted_sqlite:
                    self._logger.debug(
                        "OI '%s' of type '%s' deleted from SQLite.",
                        instance_id,
                        object_type_name,
                    )
                else:
                    self._logger.warning(
                        "OI '%s' of type '%s' not found in SQLite or delete failed.",
                        instance_id,
                        object_type_name,
                    )
            except Exception as e:
                self._logger.error(
                    "Error deleting OI '%s' from SQLite: %s",
                    instance_id,
                    e,
                    exc_info=True,
                )
                # SQLite is the primary store, so this is more critical
                raise

            # Determine overall success based on primary store (SQLite)
            # Log summary of the deletion operation
            deletion_summary = []
            if deleted_sqlite:
                deletion_summary.append("SQLite: ✓")
            else:
                deletion_summary.append("SQLite: ✗")

            if deleted_kuzu:
                deletion_summary.append("Kuzu: ✓")
            elif not deleted_kuzu:
                deletion_summary.append("Kuzu: ✗ (not found or failed)")

            if deleted_lancedb:
                deletion_summary.append("LanceDB: ✓")
            elif applicable_eds and not deleted_lancedb:
                deletion_summary.append("LanceDB: ✗ (errors or not found)")

            self._logger.info(
                "Object deletion summary for OI '%s' of type '%s': %s",
                instance_id,
                object_type_name,
                " | ".join(deletion_summary),
            )

            # Return SQLite result as it's the primary store for existence
            return deleted_sqlite

        except Exception as e:  # Catch any remaining errors not handled above
            self._logger.error(
                "Unexpected error during delete_object_instance for OI '%s' of type '%s': %s",
                instance_id,
                object_type_name,
                e,
                exc_info=True,
            )
            msg = f"Failed during deletion or cleanup for {instance_id}: {e}"
            raise DatabaseError(msg) from e

    def query_object_instances(
        self,
        object_type_name: str,
        conditions: dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Queries OIs from SQLite based on specified conditions."""
        if not self._schema_manager.get_object_type_definition(object_type_name):
            msg = f"Cannot query instances: OTD '{object_type_name}' not found."
            raise SchemaError(
                msg,
            )
        try:
            return self._conn_helper.sqlite_adapter.find_object_instances(
                object_type_name, query=conditions, limit=limit, offset=offset,
            )
        except (DatabaseError, SchemaError) as e:
            self._logger.error(
                "Error querying OIs of type '%s': %s",
                object_type_name,
                e,
                exc_info=True,
            )
            raise

    def find_similar_objects_by_embedding(  # pylint: disable=R0913, R0912
        self,
        embedding_definition_name: str,
        query_text: Optional[str] = None,
        query_vector: Optional[list[float]] = None,
        *,  # Marks subsequent arguments as keyword-only
        limit: int = 10,
        filter_condition: Optional[str] = None,
        retrieve_full_objects: bool = False,
    ) -> list[dict[str, Any]]:
        """Finds objects based on vector similarity of their embeddings."""
        if not query_text and not query_vector:
            msg = "Either query_text or query_vector must be provided."
            raise ValueError(msg)
        if query_text and query_vector:
            msg = "Provide either query_text or query_vector, not both."
            raise ValueError(msg)
        ed_def = self._schema_manager.get_embedding_definition(
            embedding_definition_name,
        )
        if not ed_def:
            msg = f"ED '{embedding_definition_name}' not found."
            raise SchemaError(msg)
        final_query_vector: list[float]
        if query_text:
            try:
                self._logger.debug(
                    "Generating query vector for text: '%s...' using model '%s'",
                    query_text[:100],
                    ed_def.embedding_model,
                )
                embedding_model_func = self._conn_helper.lancedb_adapter.get_embedding_model(
                    ed_def.embedding_model,
                )
                # Use compute_query_embeddings for TransformersEmbeddingFunction when it's a query
                raw_query_embeddings = embedding_model_func.compute_query_embeddings([query_text])
                if not raw_query_embeddings:
                    self._logger.error(
                        "Model '%s' for query text '%s' returned empty list.",
                        ed_def.embedding_model, query_text[:50],
                    )
                    raise EmbeddingError(f"Model {ed_def.embedding_model} returned empty list for query text.")

                raw_query_vector = raw_query_embeddings[0]

                if hasattr(raw_query_vector, "tolist"): # Handles numpy array
                    final_query_vector = raw_query_vector.tolist()
                elif isinstance(raw_query_vector, list):
                    final_query_vector = raw_query_vector
                else:
                    self._logger.error(
                        "Unexpected query vector type from model '%s' for query text: %s",
                        ed_def.embedding_model, type(raw_query_vector),
                    )
                    raise EmbeddingError(f"Unexpected query vector type from model {ed_def.embedding_model}")
                self._logger.debug(
                    "Generated query vector with dimension %s", len(final_query_vector),
                )
            except Exception as e:  # pylint: disable=broad-except
                self._logger.error(
                    "Failed to generate embedding for query_text using '%s': %s",
                    ed_def.embedding_model,
                    e,
                    exc_info=True,
                )
                msg = f"Failed to generate query vector: {e}"
                raise EmbeddingError(msg) from e
        elif query_vector:
            final_query_vector = query_vector
            self._logger.debug(
                "Using provided query vector with dimension %s", len(final_query_vector),
            )
        else:
            msg = "Internal error: No query vector determined."
            raise ValueError(msg)
        if ed_def.dimensions and len(final_query_vector) != ed_def.dimensions:
            msg = (
                f"Query vector dim ({len(final_query_vector)}) does not match ED "
                f"'{ed_def.name}' dim ({ed_def.dimensions})."
            )
            raise EmbeddingError(
                msg,
            )
        try:
            self._logger.info(
                "Querying LanceDB table for '%s' with limit %s and filter: '%s'",
                embedding_definition_name,
                limit,
                filter_condition if filter_condition else "None",
            )
            lance_results = self._conn_helper.lancedb_adapter.query_similar_embeddings(
                embedding_definition_name=embedding_definition_name,
                query_vector=final_query_vector,
                limit=limit,
                filter_condition=filter_condition,
            )
            self._logger.debug(
                "Received %s results from LanceDB query.", len(lance_results),
            )
            if retrieve_full_objects:
                self._logger.warning(
                    "retrieve_full_objects=True is not fully implemented yet. "
                    "Returning raw LanceDB results.",
                )
            return lance_results  # type: ignore
        except (DatabaseError, SchemaError, EmbeddingError) as e:
            self._logger.error(
                "Error during similarity search for ED '%s': %s",
                embedding_definition_name,
                e,
                exc_info=True,
            )
            raise
        except Exception as e:  # pylint: disable=broad-except
            self._logger.error(
                "Unexpected error during similarity search for ED '%s': %s",
                embedding_definition_name,
                e,
                exc_info=True,
            )
            msg = f"Unexpected error during similarity search: {e}"
            raise DatabaseError(
                msg,
            ) from e

    # --- Relation Instance Management ---
    def add_relation_instance(self, instance: RelationInstance) -> RelationInstance:
        """Upserts a relation instance.

        This method first validates the relation type and its source/target object types.
        It then ensures that the source and target object instances exist in Kuzu,
        retrieving them from SQLite and upserting them into Kuzu if necessary.
        Finally, it upserts the relation instance itself into Kuzu and persists
        its metadata (if applicable) to SQLite.

        Args:
            instance: The RelationInstance to add or update.

        Returns:
            The upserted RelationInstance, typically reflecting Kuzu's state.

        Raises:
            SchemaError: If the relation type or related object types are not defined.
            InstanceError: If source or target objects cannot be found or ensured in Kuzu.
            DatabaseError: For other underlying database or processing errors.

        """
        self._logger.debug(
            f"_InstanceManager.add_relation_instance called with instance: {instance.id=}, "
            f"{instance.relation_type_name=}, {instance.source_object_instance_id=}, "
            f"{instance.target_object_instance_id=}, {instance.weight=}, "
            f"{instance.upsert_date=}, properties: {instance.properties}",
        )

        rtd = self._schema_manager.get_relation_type_definition(
            instance.relation_type_name,
        )
        if not rtd:
            msg = (
                f"Cannot add relation instance: RelationTypeDefinition "
                f"'{instance.relation_type_name}' not found."
            )
            raise SchemaError(
                msg,
            )

        if not rtd.source_object_type_names:
            msg = f"RTD '{rtd.name}' has no source object type names for relation instance '{instance.id}'."
            raise SchemaError(
                msg,
            )
        if not rtd.target_object_type_names:
            msg = f"RTD '{rtd.name}' has no target object type names for relation instance '{instance.id}'."
            raise SchemaError(
                msg,
            )

        source_otd = self._schema_manager.get_object_type_definition(
            rtd.source_object_type_names[0],
        )
        target_otd = self._schema_manager.get_object_type_definition(
            rtd.target_object_type_names[0],
        )
        if not source_otd:
            msg = f"Source ObjectType '{rtd.source_object_type_names[0]}' for RelationType '{rtd.name}' not found."
            raise SchemaError(
                msg,
            )
        if not target_otd:
            msg = f"Target ObjectType '{rtd.target_object_type_names[0]}' for RelationType '{rtd.name}' not found."
            raise SchemaError(
                msg,
            )

        # Kuzu's MATCH clause handles existence check for source and target object instances.
        # --- START: Ensure source and target objects exist in Kuzu ---
        self._logger.debug(f"Ensuring source object {instance.source_object_instance_id} (type {source_otd.name}) exists in Kuzu.")
        source_object_from_sqlite = self.get_object_instance(
            source_otd.name, instance.source_object_instance_id,
        )
        if source_object_from_sqlite:
            try:
                self._conn_helper.kuzu_adapter.upsert_object_instance(source_object_from_sqlite)
                self._logger.info(f"Source object {source_object_from_sqlite.id} ensured in Kuzu.")
            except Exception as e_kuzu_src:
                self._logger.error(f"Failed to upsert source object {source_object_from_sqlite.id} to Kuzu: {e_kuzu_src}", exc_info=True)
                raise InstanceError(f"Failed to ensure source object {source_object_from_sqlite.id} in Kuzu.") from e_kuzu_src
        else:
            self._logger.error(f"Source object {instance.source_object_instance_id} (type {source_otd.name}) not found in SQLite. Cannot create relation in Kuzu.")
            raise InstanceError(f"Source object {instance.source_object_instance_id} not found in primary store.")

        self._logger.debug(f"Ensuring target object {instance.target_object_instance_id} (type {target_otd.name}) exists in Kuzu.")
        target_object_from_sqlite = self.get_object_instance(
            target_otd.name, instance.target_object_instance_id,
        )
        if target_object_from_sqlite:
            try:
                self._conn_helper.kuzu_adapter.upsert_object_instance(target_object_from_sqlite)
                self._logger.info(f"Target object {target_object_from_sqlite.id} ensured in Kuzu.")
            except Exception as e_kuzu_tgt:
                self._logger.error(f"Failed to upsert target object {target_object_from_sqlite.id} to Kuzu: {e_kuzu_tgt}", exc_info=True)
                raise InstanceError(f"Failed to ensure target object {target_object_from_sqlite.id} in Kuzu.") from e_kuzu_tgt
        else:
            self._logger.error(f"Target object {instance.target_object_instance_id} (type {target_otd.name}) not found in SQLite. Cannot create relation in Kuzu.")
            raise InstanceError(f"Target object {instance.target_object_instance_id} not found in primary store.")
        # --- END: Ensure source and target objects exist in Kuzu ---

        # Ensure upsert_date reflects the current operation time
        instance.upsert_date = datetime.now(timezone.utc)

        # Outer try for the whole operation (SQLite and Kuzu)
        try:
            # Inner try for SQLite part
            try:
                self._conn_helper.sqlite_adapter.add_relation_instance(
                    instance,
                )  # Assumed method
                self._logger.info(
                    "Relation instance '%s' of type '%s' (metadata) added to SQLite.",
                    instance.id,
                    instance.relation_type_name,
                )
            except AttributeError:
                self._logger.warning(
                    "SQLiteAdapter.add_relation_instance not found. Skipping SQLite persistence for relation instance '%s'.",
                    instance.id,
                )
            except (
                DatabaseError,
                InstanceError,
                SchemaError,
            ) as e:  # Catch SQLite specific errors
                self._logger.error(
                    "Error adding relation instance '%s' to SQLite: %s",
                    instance.id,
                    e,
                    exc_info=True,
                )
                raise  # Re-raise to stop further processing if SQLite part is critical

            # Kuzu part, still within the outer try
            kuzu_instance = self._conn_helper.kuzu_adapter.upsert_relation_instance(
                instance, rtd,
            )
            self._logger.info(
                "Relation instance '%s' of type '%s' upserted to Kuzu.",
                instance.id,
                instance.relation_type_name,
            )
            return kuzu_instance  # IMPORTANT: Return the instance

        # These excepts are for the outer try block, covering SQLite re-raises or Kuzu errors
        except (DatabaseError, InstanceError, SchemaError) as e:
            self._logger.error(
                "Error during add_relation_instance for '%s' (type '%s'): %s",
                instance.id,
                instance.relation_type_name,
                e,
                exc_info=True,
            )
            raise
        except Exception as e:  # Catch-all for unexpected issues in the whole process
            self._logger.error(
                "Unexpected error during add_relation_instance for '%s': %s",
                instance.id,
                e,
                exc_info=True,
            )
            msg = f"Failed during relation instance add/upsert for {instance.id}: {e}"
            raise DatabaseError(
                msg,
            ) from e

    def get_relation_instance(
        self,
        relation_type_name: str,
        relation_id: str,  # Kuzu uses string IDs typically
    ) -> Optional[RelationInstance]:
        """Retrieves a relation instance from Kuzu."""
        # Convert string ID to UUID if your model expects UUID
        try:
            relation_uuid = (
                UUID(relation_id) if isinstance(relation_id, str) else relation_id
            )
        except ValueError:
            self._logger.exception(f"Invalid UUID format for relation_id: {relation_id}")
            return None

        if not self._schema_manager.get_relation_type_definition(relation_type_name):
            self._logger.warning(
                "Attempting to get relation instance of undefined RTD '%s'.",
                relation_type_name,
            )
            return None  # Or raise SchemaError depending on desired strictness
        try:
            return self._conn_helper.kuzu_adapter.get_relation_instance(
                relation_type_name, relation_uuid,
            )
        except (DatabaseError, InstanceError, SchemaError) as e:
            self._logger.error(
                "Error getting relation instance '%s' of type '%s' from Kuzu: %s",
                relation_id,
                relation_type_name,
                e,
                exc_info=True,
            )
            raise  # Re-raise to signal failure to the caller
        except Exception as e:
            self._logger.error(
                "Unexpected error getting relation instance '%s' from Kuzu: %s",
                relation_id,
                e,
                exc_info=True,
            )
            msg = f"Unexpected error getting relation instance {relation_id} from Kuzu: {e}"
            raise DatabaseError(
                msg,
            ) from e

    def delete_relation_instance(
        self, relation_type_name: str, relation_id: str,
    ) -> bool:
        """Deletes a relation instance from Kuzu and SQLite."""
        try:
            relation_uuid = (
                UUID(relation_id) if isinstance(relation_id, str) else relation_id
            )
        except ValueError:
            self._logger.exception(f"Invalid UUID format for relation_id: {relation_id}")
            return False

        if not self._schema_manager.get_relation_type_definition(relation_type_name):
            self._logger.warning(
                "Attempting to delete relation instance of undefined RTD '%s'.",
                relation_type_name,
            )
            return False

        deleted_kuzu = False
        deleted_sqlite = False

        try:
            deleted_kuzu = self._conn_helper.kuzu_adapter.delete_relation_instance(
                relation_type_name, relation_uuid,
            )
            if deleted_kuzu:
                self._logger.info(
                    "Relation instance '%s' of type '%s' deleted from Kuzu.",
                    relation_id,
                    relation_type_name,
                )
            else:
                self._logger.warning(
                    "Relation instance '%s' of type '%s' not found in Kuzu or delete failed.",
                    relation_id,
                    relation_type_name,
                )

            # Delete from SQLite (assuming this method exists or will be added)
            try:
                deleted_sqlite = (
                    self._conn_helper.sqlite_adapter.delete_relation_instance(
                        relation_type_name, relation_uuid,  # Assumed method
                    )
                )
                if deleted_sqlite:
                    self._logger.info(
                        "Relation instance '%s' (metadata) deleted from SQLite.",
                        relation_id,
                    )
            except AttributeError:
                self._logger.warning(
                    "SQLiteAdapter.delete_relation_instance not found. Skipping SQLite deletion for relation instance '%s'.",
                    relation_id,
                )
                deleted_sqlite = (
                    True  # Assume success if not implemented, to not block Kuzu success
                )
            except (DatabaseError, InstanceError, SchemaError) as e:
                self._logger.error(
                    "Error deleting relation instance '%s' from SQLite: %s",
                    relation_id,
                    e,
                    exc_info=True,
                )
                # If Kuzu succeeded but SQLite failed, how to reconcile?
                # For now, we log and the overall success depends on both if SQLite part is implemented.
                # If SQLite part is not critical for relation data, kuzu_deleted might be enough.
                # Let's make overall success dependent on Kuzu, and SQLite is best-effort if method exists.

            return deleted_kuzu  # Primary success depends on Kuzu deletion for now.

        except (DatabaseError, InstanceError, SchemaError) as e:
            self._logger.error(
                "Error deleting relation instance '%s' of type '%s': %s",
                relation_id,
                relation_type_name,
                e,
                exc_info=True,
            )
            raise
        except Exception as e:
            self._logger.error(
                "Unexpected error deleting relation instance '%s': %s",
                relation_id,
                e,
                exc_info=True,
            )
            msg = f"Failed during relation instance deletion for {relation_id}: {e}"
            raise DatabaseError(
                msg,
            ) from e

    def find_relation_instances(
        self,
        relation_type_name: Optional[str] = None,
        source_object_id: Optional[Any] = None,  # Allow string or UUID
        target_object_id: Optional[Any] = None,  # Allow string or UUID
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[RelationInstance]:
        """Exposes the Kuzu adapter's find_relation_instances method."""
        # Convert string IDs to UUIDs if provided
        src_uuid: Optional[UUID] = None
        if source_object_id:
            try:
                src_uuid = (
                    UUID(source_object_id)
                    if isinstance(source_object_id, str)
                    else source_object_id
                )
            except ValueError as exc:
                self._logger.exception(
                    f"Invalid UUID format for source_object_id: {source_object_id}",
                )
                msg = f"Invalid UUID format for source_object_id: {source_object_id}"
                raise InstanceError(
                    msg,
                ) from exc

        tgt_uuid: Optional[UUID] = None
        if target_object_id:
            try:
                tgt_uuid = (
                    UUID(target_object_id)
                    if isinstance(target_object_id, str)
                    else target_object_id
                )
            except ValueError as exc:
                self._logger.exception(
                    f"Invalid UUID format for target_object_id: {target_object_id}",
                )
                msg = f"Invalid UUID format for target_object_id: {target_object_id}"
                raise InstanceError(
                    msg,
                ) from exc

        try:
            return self._conn_helper.kuzu_adapter.find_relation_instances(
                relation_type_name=relation_type_name,
                source_object_id=src_uuid,
                target_object_id=tgt_uuid,
                query=query,
                limit=limit,
            )
        except (
            DatabaseError,
            InstanceError,
            SchemaError,
            ValueError,
        ) as e:  # ValueError for bad UUIDs from KuzuAdapter
            self._logger.error("Error finding relation instances: %s", e, exc_info=True)
            raise
        except Exception as e:
            self._logger.error(
                "Unexpected error finding relation instances: %s", e, exc_info=True,
            )
            msg = f"Unexpected error finding relation instances: {e}"
            raise DatabaseError(
                msg,
            ) from e

    # Note: The get_relation_instance, delete_relation_instance, and find_relation_instances
    # methods were already present in the file content provided in the previous turn (lines 904-1010).
    # The Pylance errors in db_manager.py likely arose because the _db_manager_helpers.py file
    # was not in the expected state when Pylance analyzed db_manager.py.
    # Since the methods are already there, no changes are needed for this specific step.
    # If the Pylance errors persist for db_manager.py after this, it might be a caching issue
    # or an incorrect assumption about the state of _db_manager_helpers.py during that analysis.
