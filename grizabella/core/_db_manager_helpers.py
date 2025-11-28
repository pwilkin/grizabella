"""Internal helper classes for GrizabellaDBManager."""

import logging
import threading  # For logging thread ID
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

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

if TYPE_CHECKING:
    from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter
    from grizabella.db_layers.lancedb.lancedb_adapter import LanceDBAdapter
    from grizabella.db_layers.sqlite.sqlite_adapter import SQLiteAdapter


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

        self._sqlite_adapter_instance: Optional["SQLiteAdapter"] = None
        self._lancedb_adapter_instance: Optional["LanceDBAdapter"] = None
        self._kuzu_adapter_instance: Optional["KuzuAdapter"] = None
        self._adapters_are_connected: bool = False

    @property
    def sqlite_adapter(self) -> "SQLiteAdapter":
        """Provides access to the SQLite adapter instance."""
        if not self._sqlite_adapter_instance or not self._adapters_are_connected:
            self._logger.error("Attempted to access SQLite adapter when not connected.")
            msg = "SQLite adapter not connected or available."
            raise DatabaseError(msg)
        return self._sqlite_adapter_instance

    @property
    def lancedb_adapter(self) -> "LanceDBAdapter":
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
            # ThreadSafeSQLiteAdapter's __init__ calls _connect which establishes the connection.
            # We'll add logging there.
            from grizabella.db_layers.sqlite.thread_safe_sqlite_adapter import ThreadSafeSQLiteAdapter
            self._sqlite_adapter_instance = ThreadSafeSQLiteAdapter(
                db_path=self.sqlite_db_file_path,
            ) # Logging for connection creation will be in ThreadSafeSQLiteAdapter
            self._logger.info("_ConnectionHelper: SQLiteAdapter initialized (object created).")

            self._logger.info(
                "_ConnectionHelper: Connecting LanceDBAdapter to %s", self.lancedb_uri,
            )
            from grizabella.db_layers.lancedb.lancedb_adapter import LanceDBAdapter
            self._lancedb_adapter_instance = LanceDBAdapter(db_uri=self.lancedb_uri)
            self._logger.info("_ConnectionHelper: LanceDBAdapter initialized.")

            self._logger.info(
                "_ConnectionHelper: Connecting KuzuAdapter to %s", self.kuzu_path,
            )
            from grizabella.db_layers.kuzu.thread_safe_kuzu_adapter import ThreadSafeKuzuAdapter
            self._kuzu_adapter_instance = ThreadSafeKuzuAdapter(db_path=self.kuzu_path)
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
            instance = self._conn_helper.sqlite_adapter.get_object_instance(
                object_type_name, instance_id,
            )
            self._logger.debug(
                "Retrieved object instance '%s' of type '%s'.", instance_id, object_type_name,
            )
            return instance
        except (DatabaseError, InstanceError) as e:
            self._logger.error(
                "Error retrieving object instance '%s': %s", instance_id, e, exc_info=True,
            )
            raise

    def update_object_instance(self, instance: ObjectInstance) -> None:
        """Updates an existing object instance in the SQLite database."""
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
                "Updated object instance '%s' of type '%s'.",
                instance.id,
                instance.object_type_name,
            )
        except (DatabaseError, InstanceError, SchemaError) as e:
            self._logger.error(
                "Error updating object instance '%s': %s", instance.id, e, exc_info=True,
            )
            raise

    def upsert_object_instance(self, instance: ObjectInstance) -> ObjectInstance:
        """Upserts an object instance in both SQLite and Kuzu, and generates embeddings if applicable."""
        if not self._schema_manager.get_object_type_definition(
            instance.object_type_name,
        ):
            msg = f"Cannot upsert instance: OTD '{instance.object_type_name}' not found."
            raise SchemaError(
                msg,
            )
        try:
            # First upsert in SQLite
            self._conn_helper.sqlite_adapter.upsert_object_instance(instance)
            
            # Then upsert in Kuzu for graph operations
            self._conn_helper.kuzu_adapter.upsert_object_instance(instance)
            
            # Generate and upsert embeddings if applicable
            self._generate_embeddings_for_instance(instance)
            
            self._logger.debug(
                "Upserted object instance '%s' of type '%s' in SQLite, Kuzu, and generated embeddings.",
                instance.id,
                instance.object_type_name,
            )
            return instance
        except (DatabaseError, InstanceError, SchemaError, EmbeddingError) as e:
            self._logger.error(
                "Error upserting object instance '%s': %s", instance.id, e, exc_info=True,
            )
            raise
    
    def _generate_embeddings_for_instance(self, instance: ObjectInstance) -> None:
        """Generate and save embeddings for an object instance based on applicable EmbeddingDefinitions."""
        # Find all EmbeddingDefinitions that apply to this object type
        applicable_embeddings = [
            ed for ed in self._schema_manager.list_embedding_definitions()
            if ed.object_type_name == instance.object_type_name
        ]
        
        if not applicable_embeddings:
            return  # No embeddings to generate for this object type
            
        for embedding_def in applicable_embeddings:
            try:
                # Delete existing embeddings first (defensive deletion)
                self._conn_helper.lancedb_adapter.delete_embedding_instances_for_object(
                    instance.id, embedding_def.name
                )
                
                # Get the source text from the specified property
                source_text = instance.properties.get(embedding_def.source_property_name)
                if not source_text or not source_text.strip():
                    self._logger.warning(
                        f"No source text found for property '{embedding_def.source_property_name}' "
                        f"on instance '{instance.id}' for embedding definition '{embedding_def.name}'. Skipping."
                    )
                    continue
                
                # Generate embedding using the model
                embedding_model = self._conn_helper.lancedb_adapter.get_embedding_model(
                    embedding_def.embedding_model
                )
                
                # Generate embeddings - handle both compute_source_embeddings and compute_query_embeddings
                if hasattr(embedding_model, 'compute_source_embeddings'):
                    embeddings = embedding_model.compute_source_embeddings([source_text])
                elif hasattr(embedding_model, 'compute_query_embeddings'):
                    embeddings = embedding_model.compute_query_embeddings([source_text])
                else:
                    raise EmbeddingError(
                        f"Embedding model '{embedding_def.embedding_model}' does not have "
                        "compute_source_embeddings or compute_query_embeddings method"
                    )
                
                if not embeddings or len(embeddings) == 0:
                    raise EmbeddingError(
                        f"Embedding generation returned empty result for instance '{instance.id}' "
                        f"with embedding definition '{embedding_def.name}'"
                    )
                
                # Get the first embedding vector
                embedding_vector = embeddings[0]
                
                # Convert numpy arrays to lists if needed
                if hasattr(embedding_vector, 'tolist'):
                    embedding_vector = embedding_vector.tolist()
                elif hasattr(embedding_vector, 'tolist'):  # Some numpy types
                    embedding_vector = embedding_vector.tolist()
                elif not isinstance(embedding_vector, list):
                    raise EmbeddingError(
                        f"Unexpected embedding vector type: {type(embedding_vector)}"
                    )
                
                # Create EmbeddingInstance and save to LanceDB
                from .models import EmbeddingInstance
                embedding_instance = EmbeddingInstance(
                    object_instance_id=instance.id,
                    embedding_definition_name=embedding_def.name,
                    vector=embedding_vector,
                    source_text_preview=source_text[:100] if len(source_text) > 100 else source_text,
                )
                
                # Upsert the embedding instance to LanceDB
                self._conn_helper.lancedb_adapter.upsert_embedding_instance(
                    embedding_instance, embedding_def
                )
                
                self._logger.debug(
                    "Generated and saved embedding for instance '%s' using definition '%s'",
                    instance.id, embedding_def.name
                )
                
            except Exception as e:
                self._logger.error(
                    "Error generating embedding for instance '%s' with definition '%s': %s",
                    instance.id, embedding_def.name, e, exc_info=True
                )
                # Continue with other embeddings even if one fails
                continue

    def delete_object_instance(self, object_type_name: str, instance_id: Any) -> bool:
        """Deletes an object instance from both SQLite and Kuzu."""
        if not self._schema_manager.get_object_type_definition(object_type_name):
            self._logger.warning(
                "Attempting to delete instance of undefined OTD '%s'.", object_type_name,
            )
            return False
        
        try:
            # First delete from Kuzu
            kuzu_deleted = False
            try:
                kuzu_deleted = self._conn_helper.kuzu_adapter.delete_object_instance(
                    object_type_name, instance_id,
                )
            except Exception as e_kuzu:
                self._logger.warning(
                    "Error deleting object instance '%s' from Kuzu: %s", instance_id, e_kuzu,
                )
            
            # Then delete from SQLite
            sqlite_deleted = self._conn_helper.sqlite_adapter.delete_object_instance(
                object_type_name, instance_id,
            )
            
            if kuzu_deleted or sqlite_deleted:
                # Delete embeddings if applicable
                applicable_embeddings = [
                    ed for ed in self._schema_manager.list_embedding_definitions()
                    if ed.object_type_name == object_type_name
                ]
                for embedding_def in applicable_embeddings:
                    try:
                        self._conn_helper.lancedb_adapter.delete_embedding_instances_for_object(
                            instance_id, embedding_def.name
                        )
                    except Exception as e_embed:
                        self._logger.warning(
                            "Error deleting embeddings for instance '%s' with definition '%s': %s",
                            instance_id, embedding_def.name, e_embed,
                        )
                
                self._logger.debug(
                    "Deleted object instance '%s' of type '%s' from %s.",
                    instance_id,
                    object_type_name,
                    "both SQLite and Kuzu" if kuzu_deleted and sqlite_deleted
                    else "Kuzu only" if kuzu_deleted
                    else "SQLite only",
                )
                return True
            else:
                self._logger.warning(
                    "Object instance '%s' of type '%s' not found in either database.",
                    instance_id,
                    object_type_name,
                )
                return False
                
        except (DatabaseError, InstanceError) as e:
            self._logger.error(
                "Error deleting object instance '%s': %s", instance_id, e, exc_info=True,
            )
            raise

    def query_object_instances(
        self,
        object_type_name: str,
        conditions: dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Queries object instances from SQLite based on specified conditions."""
        if not self._schema_manager.get_object_type_definition(object_type_name):
            self._logger.warning(
                "Attempting to query instances of undefined OTD '%s'.", object_type_name,
            )
            return []
        try:
            return self._conn_helper.sqlite_adapter.query_object_instances(
                object_type_name, conditions, limit, offset,
            )
        except (DatabaseError, SchemaError) as e:
            self._logger.error(
                "Error querying object instances of type '%s': %s",
                object_type_name, e, exc_info=True,
            )
            raise

    def find_similar_objects_by_embedding( # pylint: disable=R0913
        self,
        embedding_definition_name: str,
        query_text: Optional[str] = None,
        query_vector: Optional[list[float]] = None,
        limit: int = 5,
        filter_condition: Optional[str] = None,
        retrieve_full_objects: bool = False,
    ) -> list[dict[str, Any]]:
        """Finds objects based on vector similarity of their embeddings."""
        ed_def = self._schema_manager.get_embedding_definition(embedding_definition_name)
        if not ed_def:
            msg = f"ED '{embedding_definition_name}' not found."
            raise SchemaError(
                msg,
            )
        try:
            # Validate input parameters
            if query_text is None and query_vector is None:
                msg = "Either query_text or query_vector must be provided."
                raise ValueError(msg)
            if query_text is not None and query_vector is not None:
                msg = "Provide either query_text or query_vector, not both."
                raise ValueError(msg)
            
            # If query_text is provided, generate the embedding vector
            if query_text is not None and query_vector is None:
                try:
                    embedding_model = self._conn_helper.lancedb_adapter.get_embedding_model(
                        ed_def.embedding_model
                    )
                    embeddings = embedding_model.compute_query_embeddings([query_text])
                    query_vector = embeddings[0]
                except Exception as e:
                    msg = f"Failed to generate query vector: {e}"
                    raise EmbeddingError(msg) from e
            
            # Validate vector dimensions if both query_vector and embedding definition have dimensions
            if query_vector is not None and ed_def.dimensions is not None:
                if len(query_vector) != ed_def.dimensions:
                    msg = (
                        f"Query vector dim ({len(query_vector)}) does not match ED "
                        f"'{ed_def.name}' dim ({ed_def.dimensions})."
                    )
                    raise EmbeddingError(msg)
            
            # Use query_similar_embeddings for similarity search
            results = self._conn_helper.lancedb_adapter.query_similar_embeddings(
                embedding_definition_name=embedding_definition_name,
                query_vector=query_vector,  # type: ignore[arg-type]  # Validated above to not be None
                limit=limit,
                filter_condition=filter_condition,
            )
            
            # Log warning if retrieve_full_objects was requested but not implemented
            if retrieve_full_objects:
                self._logger.warning("retrieve_full_objects=True is not fully implemented yet. Returning raw LanceDB results.")
            
            return results
        except (DatabaseError, EmbeddingError) as e:
            self._logger.error(
                "Error finding similar objects for embedding definition '%s': %s",
                embedding_definition_name, e, exc_info=True,
            )
            raise

    def add_relation_instance(self, instance: RelationInstance) -> RelationInstance:
        """Persists the RelationInstance to SQLite (for metadata) and Kuzu (for graph operations)."""
        # Get the RTD to ensure it exists and is properly configured
        rtd = self._schema_manager.get_relation_type_definition(instance.relation_type_name)
        if not rtd:
            msg = f"Cannot add relation instance: RTD '{instance.relation_type_name}' not found."
            raise SchemaError(
                msg,
            )
        
        try:
            # First add to SQLite for metadata persistence
            self._conn_helper.sqlite_adapter.add_relation_instance(instance)
            
            # Then add to Kuzu for graph operations
            self._conn_helper.kuzu_adapter.upsert_relation_instance(instance, rtd)
            
            self._logger.debug(
                "Added relation instance '%s' of type '%s'.",
                instance.id,
                instance.relation_type_name,
            )
            return instance
        except (DatabaseError, InstanceError, SchemaError) as e:
            self._logger.error(
                "Error adding relation instance '%s': %s", instance.id, e, exc_info=True,
            )
            raise

    def get_relation_instance(
        self, relation_type_name: str, relation_id: Any,
    ) -> Optional[RelationInstance]:
        """Retrieves a relation instance primarily from Kuzu, potentially enriched with SQLite metadata."""
        rtd = self._schema_manager.get_relation_type_definition(relation_type_name)
        if not rtd:
            self._logger.warning(
                "Attempting to get relation instance of undefined RTD '%s'.", relation_type_name,
            )
            return None
        
        try:
            # Get from Kuzu
            kuzu_instance = self._conn_helper.kuzu_adapter.get_relation_instance(
                relation_type_name, relation_id,
            )
            
            if kuzu_instance:
                self._logger.debug(
                    "Retrieved relation instance '%s' of type '%s'.", relation_id, relation_type_name,
                )
            
            return kuzu_instance
        except (DatabaseError, InstanceError) as e:
            self._logger.error(
                "Error retrieving relation instance '%s': %s", relation_id, e, exc_info=True,
            )
            raise

    def delete_relation_instance(self, relation_type_name: str, relation_id: Any) -> bool:
        """Deletes a relation instance from both Kuzu and SQLite."""
        rtd = self._schema_manager.get_relation_type_definition(relation_type_name)
        if not rtd:
            self._logger.warning(
                "Attempting to delete relation instance of undefined RTD '%s'.", relation_type_name,
            )
            return False
        
        try:
            # Delete from Kuzu first
            kuzu_deleted = False
            try:
                kuzu_deleted = self._conn_helper.kuzu_adapter.delete_relation_instance(
                    relation_type_name, relation_id,
                )
            except Exception as e_kuzu:
                self._logger.warning(
                    "Error deleting relation instance '%s' from Kuzu: %s", relation_id, e_kuzu,
                )
            
            # Then delete from SQLite
            sqlite_deleted = self._conn_helper.sqlite_adapter.delete_relation_instance(
                relation_type_name, relation_id,
            )
            
            if kuzu_deleted or sqlite_deleted:
                self._logger.debug(
                    "Deleted relation instance '%s' of type '%s' from %s.",
                    relation_id,
                    relation_type_name,
                    "both SQLite and Kuzu" if kuzu_deleted and sqlite_deleted 
                    else "Kuzu only" if kuzu_deleted 
                    else "SQLite only",
                )
                return True
            else:
                self._logger.warning(
                    "Relation instance '%s' of type '%s' not found in either database.",
                    relation_id,
                    relation_type_name,
                )
                return False
                
        except (DatabaseError, InstanceError) as e:
            self._logger.error(
                "Error deleting relation instance '%s': %s", relation_id, e, exc_info=True,
            )
            raise

    def find_relation_instances( # pylint: disable=R0913, R0917
        self,
        relation_type_name: Optional[str] = None,
        source_object_id: Optional[UUID] = None,
        target_object_id: Optional[UUID] = None,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[RelationInstance]:
        """Finds relation instances from Kuzu based on various criteria."""
        if relation_type_name:
            rtd = self._schema_manager.get_relation_type_definition(relation_type_name)
            if not rtd:
                self._logger.warning(
                    "Attempting to find relation instances of undefined RTD '%s'.", relation_type_name,
                )
                return []
        
        try:
            return self._conn_helper.kuzu_adapter.find_relation_instances(
                relation_type_name=relation_type_name,
                source_object_id=source_object_id,
                target_object_id=target_object_id,
                query=query,
                limit=limit,
            )
        except (DatabaseError, SchemaError) as e:
            self._logger.error(
                "Error finding relation instances: %s", e, exc_info=True,
            )
            raise