"""Manages Grizabella database instances and their adapters."""
import datetime as dt  # Alias to avoid conflict if datetime module itself is used
import decimal
import logging
import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

# from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter # Moved to TYPE_CHECKING
from grizabella.db_layers.lancedb.lancedb_adapter import LanceDBAdapter
from grizabella.db_layers.sqlite.sqlite_adapter import SQLiteAdapter

from . import db_paths
from ._db_manager_helpers import _ConnectionHelper, _InstanceManager, _SchemaManager
from .exceptions import ConfigurationError, DatabaseError, EmbeddingError, InstanceError, SchemaError

# EmbeddingError re-added for find_objects_similar_to_instance
from .models import (
    EmbeddingDefinition,
    ObjectInstance,
    ObjectTypeDefinition,
    # EmbeddingInstance removed as it's not directly used in this file after refactoring
    PropertyDataType,
    PropertyDefinition,
    RelationInstance,  # Added for new relation methods
    RelationTypeDefinition,
)
from .query_engine import QueryExecutor, QueryPlanner  # Added import
from .query_models import ComplexQuery, QueryResult  # Added import

if TYPE_CHECKING:
    from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter

logger = logging.getLogger(__name__)

class GrizabellaDBManager: # pylint: disable=R0904, R0902
    """Manages a single Grizabella database instance, coordinating SQLite, LanceDB, and Kuzu."""

    def __init__(self, db_name_or_path: Union[str, Path] = "default",
                 create_if_not_exists: bool = True) -> None:
        self.db_instance_root: Path = db_paths.get_db_instance_path(
            db_name_or_path, create_if_not_exists,
        )
        self.db_name = self.db_instance_root.name
        sqlite_path_str = str(
            db_paths.get_sqlite_path(self.db_instance_root, create_if_not_exists),
        )
        lancedb_uri_str = db_paths.get_lancedb_uri(
            self.db_instance_root, create_if_not_exists,
        )
        kuzu_path_str = str(db_paths.get_kuzu_path(self.db_instance_root, create_if_not_exists))
        self._connection_helper = _ConnectionHelper(
            sqlite_path_str, lancedb_uri_str, kuzu_path_str, logger,
        )
        self._schema_manager = _SchemaManager(self._connection_helper, logger)
        self._instance_manager = _InstanceManager(
            self._connection_helper, self._schema_manager, logger,
        )
        # Query Engine components are initialized after connection and schema loading
        self._query_planner: Optional[QueryPlanner] = None
        self._query_executor: Optional[QueryExecutor] = None
        self._manager_fully_initialized: bool = False
        self.connect()

    def connect(self) -> None:
        """Establishes connections and loads schema definitions."""
        if self._manager_fully_initialized:
            logger.debug(
                "GrizabellaDBManager for '%s' already initialized.", self.db_name,
            )
            return
        try:
            logger.info(
                "GrizabellaDBManager: Initializing connections for instance: %s", self.db_name,
            )
            self._connection_helper.connect_all_adapters()
            logger.info("GrizabellaDBManager: Loading schema definitions.")
            self._schema_manager.load_all_definitions()
            logger.info("GrizabellaDBManager: Schema definitions loaded.")
            # Initialize query engine components that depend on a fully initialized manager
            self._query_planner = QueryPlanner(self)
            self._query_executor = QueryExecutor(self)
            self._manager_fully_initialized = True
            logger.info(
                "GrizabellaDBManager for '%s' connected and initialized successfully.", self.db_name,
            )
        except (DatabaseError, ConfigurationError) as e:
            logger.error(
                "Error during GrizabellaDBManager connect for '%s': %s",
                self.db_name, e, exc_info=True,
            )
            self.close()
            raise
        except Exception as e: # pylint: disable=broad-except
            logger.error(
                "Unexpected error during GrizabellaDBManager connect for '%s': %s",
                self.db_name, e, exc_info=True,
            )
            self.close()
            msg = (
                f"Failed to fully connect and initialize GrizabellaDBManager "
                f"for '{self.db_name}': {e}"
            )
            raise ConfigurationError(
                msg,
            ) from e

    def close(self) -> None:
        """Closes all database connections and clears caches."""
        logger.info(f"GrizabellaDBManager: close() called for instance: {self.db_name}. Manager fully initialized: {self._manager_fully_initialized}")
        try:
            # Attempt to close Kuzu first and more aggressively
            if hasattr(self._connection_helper, "_kuzu_adapter_instance") and self._connection_helper._kuzu_adapter_instance:
                logger.info(f"GrizabellaDBManager: Explicitly closing KuzuAdapter for {self.db_name}.")
                try:
                    self._connection_helper.kuzu_adapter.close() # Calls our logged close
                    logger.info(f"GrizabellaDBManager: KuzuAdapter.close() method called for {self.db_name}.")
                    # Force de-allocation attempt
                    del self._connection_helper._kuzu_adapter_instance
                    self._connection_helper._kuzu_adapter_instance = None
                    logger.info(f"GrizabellaDBManager: KuzuAdapter instance deleted and set to None for {self.db_name}.")
                except Exception as e_kuzu_close:
                    logger.error(f"GrizabellaDBManager: Error during explicit KuzuAdapter close/del for {self.db_name}: {e_kuzu_close}", exc_info=True)

            self._connection_helper.close_all_adapters() # This will now re-attempt Kuzu close if not for del, and others
            logger.info(f"GrizabellaDBManager: _connection_helper.close_all_adapters() completed for {self.db_name}.")
        except Exception as e:
            logger.error(f"GrizabellaDBManager: Error during _connection_helper.close_all_adapters() for {self.db_name}: {e}", exc_info=True)

        try:
            self._schema_manager.clear_all_definitions()
            logger.info(f"GrizabellaDBManager: _schema_manager.clear_all_definitions() completed for {self.db_name}.")
        except Exception as e:
            logger.error(f"GrizabellaDBManager: Error during _schema_manager.clear_all_definitions() for {self.db_name}: {e}", exc_info=True)

        self._query_planner = None
        self._query_executor = None
        self._manager_fully_initialized = False
        logger.info(f"GrizabellaDBManager for '{self.db_name}' state reset and marked as closed.")

    def __enter__(self):
        """Enter the runtime context related to this object."""
        if not self._manager_fully_initialized:
            self.connect()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the runtime context related to this object."""
        self.close()

    @property
    def sqlite_adapter(self) -> SQLiteAdapter:
        """Provides access to the SQLite adapter, ensuring connection."""
        if not self._manager_fully_initialized:
            msg = "GrizabellaDBManager not fully initialized."
            raise DatabaseError(msg)
        return self._connection_helper.sqlite_adapter
    @property
    def lancedb_adapter(self) -> LanceDBAdapter:
        """Provides access to the LanceDB adapter, ensuring connection."""
        if not self._manager_fully_initialized:
            msg = "GrizabellaDBManager not fully initialized."
            raise DatabaseError(msg)
        return self._connection_helper.lancedb_adapter
    @property
    def kuzu_adapter(self) -> "KuzuAdapter":
        """Provides access to the Kuzu adapter, ensuring connection."""
        if not self._manager_fully_initialized:
            msg = "GrizabellaDBManager not fully initialized."
            raise DatabaseError(msg)
        return self._connection_helper.kuzu_adapter
    @property
    def is_connected(self) -> bool:
        """Checks if the manager has been successfully initialized."""
        return self._manager_fully_initialized

    # --- Schema Management (Delegated) ---
    def add_object_type_definition(self, otd: ObjectTypeDefinition, persist: bool = True) -> None:
        """Adds or updates an object type definition."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        self._schema_manager.add_object_type_definition(otd, persist)
    def get_object_type_definition(self, name: str) -> Optional[ObjectTypeDefinition]:
        """Retrieves an object type definition by its name."""
        if not self._manager_fully_initialized:
            return None
        return self._schema_manager.get_object_type_definition(name)
    def list_object_type_definitions(self) -> list[ObjectTypeDefinition]:
        """Lists all object type definitions."""
        if not self._manager_fully_initialized:
            return []
        return self._schema_manager.list_object_type_definitions()
    def remove_object_type_definition(self, name: str, persist: bool = True) -> bool:
        """Removes an object type definition."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._schema_manager.remove_object_type_definition(name, persist)
    def add_embedding_definition(self, ed: EmbeddingDefinition, persist: bool = True) -> None:
        """Adds or updates an embedding definition."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        self._schema_manager.add_embedding_definition(ed, persist)
    def get_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:
        """Retrieves an embedding definition by its name."""
        if not self._manager_fully_initialized:
            return None
        return self._schema_manager.get_embedding_definition(name)
    def list_embedding_definitions(self) -> list[EmbeddingDefinition]:
        """Lists all embedding definitions."""
        if not self._manager_fully_initialized:
            return []
        return self._schema_manager.list_embedding_definitions()
    def remove_embedding_definition(self, name: str, persist: bool = True) -> bool:
        """Removes an embedding definition."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._schema_manager.remove_embedding_definition(name, persist)
    def add_relation_type_definition(self, rtd: RelationTypeDefinition,
                                     persist: bool = True) -> None:
        """Adds or updates a relation type definition."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        self._schema_manager.add_relation_type_definition(rtd, persist)
    def get_relation_type_definition(self, name: str) -> Optional[RelationTypeDefinition]:
        """Retrieves a relation type definition by its name."""
        if not self._manager_fully_initialized:
            return None
        return self._schema_manager.get_relation_type_definition(name)
    def list_relation_type_definitions(self) -> list[RelationTypeDefinition]:
        """Lists all relation type definitions."""
        if not self._manager_fully_initialized:
            return []
        return self._schema_manager.list_relation_type_definitions()
    def remove_relation_type_definition(self, name: str, persist: bool = True) -> bool:
        """Removes a relation type definition."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._schema_manager.remove_relation_type_definition(name, persist)

    # --- Object Instance Management (Delegated) ---
    def add_object_instance(self, instance: ObjectInstance) -> None:
        """Adds an object instance."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        self._instance_manager.add_object_instance(instance)
    def get_object_instance(self, object_type_name: str,
                              instance_id: Any) -> Optional[ObjectInstance]:
        """Retrieves an object instance by its type and ID."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._instance_manager.get_object_instance(object_type_name, instance_id)
    def update_object_instance(self, instance: ObjectInstance) -> None:
        """Updates an existing object instance."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        self._instance_manager.update_object_instance(instance)
    def upsert_object_instance(self, instance: ObjectInstance) -> ObjectInstance:
        """Upserts an object instance."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._instance_manager.upsert_object_instance(instance)
    def delete_object_instance(self, object_type_name: str, instance_id: Any) -> bool:
        """Deletes an object instance."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._instance_manager.delete_object_instance(object_type_name, instance_id)
    def query_object_instances(
        self, object_type_name: str, conditions: dict[str, Any],
        limit: Optional[int] = None, offset: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Queries object instances based on specified conditions."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._instance_manager.query_object_instances(
            object_type_name, conditions, limit, offset,
        )

    def get_objects_by_ids(
        self, object_type_name: str, object_ids: list[uuid.UUID],
    ) -> list[ObjectInstance]:
        """Retrieves multiple object instances by their type and a list of IDs.
        Delegates to the SQLite adapter.
        """
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        logger.debug( # Changed to debug as this might be called frequently
            "Fetching %d objects of type '%s' by IDs via SQLiteAdapter.",
            len(object_ids), object_type_name,
        )
        try:
            return self.sqlite_adapter.get_objects_by_ids(
                object_type_name=object_type_name, ids=object_ids,
            )
        except Exception as e:
            logger.error(
                "Error in GrizabellaDBManager.get_objects_by_ids for type '%s': %s",
                object_type_name, e, exc_info=True,
            )
            # Depending on desired error handling, could return empty list or re-raise
            # For now, re-raise to make errors visible during development
            msg = f"Failed to get objects by IDs for type '{object_type_name}': {e}"
            raise DatabaseError(
                msg,
            ) from e

    # --- Embedding Query Management (Delegated) ---
    def find_similar_objects_by_embedding( # pylint: disable=R0913
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
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._instance_manager.find_similar_objects_by_embedding(
            embedding_definition_name=embedding_definition_name,
            query_text=query_text,
            query_vector=query_vector,
            limit=limit,
            filter_condition=filter_condition,
            retrieve_full_objects=retrieve_full_objects,
        )

    def _process_raw_similarity_results( # pylint: disable=R0914
        self,
        raw_results: list[dict[str, Any]],
        source_object_id: uuid.UUID,
        target_object_type_name: str, # Type of objects in raw_results
        n_results: int,
    ) -> list[tuple[ObjectInstance, float]]:
        """Processes raw similarity results from LanceDB.
        Filters out the source object, fetches full ObjectInstances, and sorts by score.
        """
        final_results: list[tuple[ObjectInstance, float]] = []
        if not raw_results:
            return final_results

        result_ids_map: dict[uuid.UUID, float] = {}
        for res in raw_results:
            try:
                obj_id_str = res.get("object_instance_id")
                if not obj_id_str: # Ensure object_instance_id is present
                    logger.warning("Skipping result due to missing 'object_instance_id': %s", res)
                    continue
                obj_id = uuid.UUID(obj_id_str)
                # LanceDB uses '_distance', lower is better.
                score = float(res.get("_distance", 0.0))
                if obj_id == source_object_id:  # Filter out the source object itself
                    continue
                result_ids_map[obj_id] = score
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Skipping result due to parsing error: %s, error: %s", res, e)
                continue
        # Trailing whitespace removed from original line 329
        if not result_ids_map:
            return final_results

        # Get sorted list of (id, score) tuples, limited to n_results
        # Sort by score (distance, ascending)
        sorted_similar_items = sorted(result_ids_map.items(), key=lambda item: item[1])[:n_results]
        # Trailing whitespace removed from original line 336
        result_ids_to_fetch = [item[0] for item in sorted_similar_items]

        if result_ids_to_fetch:
            fetched_objects = self.get_objects_by_ids(target_object_type_name, result_ids_to_fetch)
            fetched_objects_map = {obj.id: obj for obj in fetched_objects}

            for obj_id_val, score_val in sorted_similar_items:
                if obj_id_val in fetched_objects_map:
                    final_results.append((fetched_objects_map[obj_id_val], score_val))
                else:
                    logger.warning("Could not fetch full object for ID %s after similarity search.", obj_id_val)
        # Trailing whitespace removed from original line 348
        return final_results

    def find_objects_similar_to_instance(
        self,
        source_object_id: uuid.UUID,
        source_object_type_name: str, # Used to validate the ED is for this type
        embedding_definition_name: str, # ED to use for source and target search
        n_results: int = 5,
        filter_condition: Optional[str] = None,
    ) -> list[tuple[ObjectInstance, float]]:
        """Finds objects similar to a given source object instance using its embedding.
        The similarity search is performed against objects of the type defined in the
        specified EmbeddingDefinition, using the same embedding.
        """
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)

        ed_def = self._schema_manager.get_embedding_definition(embedding_definition_name)
        if not ed_def:
            msg = f"EmbeddingDefinition '{embedding_definition_name}' not found."
            raise SchemaError(msg)

        if ed_def.object_type_name != source_object_type_name:
            msg = (
                f"EmbeddingDefinition '{embedding_definition_name}' is for object type "
                f"'{ed_def.object_type_name}', but source object is of type "
                f"'{source_object_type_name}'."
            )
            raise SchemaError(
                msg,
            )

        source_embedding_instances = self.lancedb_adapter.get_embedding_instances_for_object(
            object_instance_id=source_object_id,
            embedding_definition_name=embedding_definition_name,
        )

        if not source_embedding_instances:
            msg = (
                f"No embedding found for source object {source_object_id} "
                f"using definition '{embedding_definition_name}'."
            )
            raise EmbeddingError(
                msg,
            )
        source_vector = source_embedding_instances[0].vector

        similar_raw_results = self._instance_manager.find_similar_objects_by_embedding(
            embedding_definition_name=embedding_definition_name,
            query_vector=source_vector,
            limit=n_results + 1, # Fetch one extra in case source object is in results
            filter_condition=filter_condition,
            retrieve_full_objects=False,
        )
        # Trailing whitespace removed from original line 396
        target_object_type_for_results = ed_def.object_type_name
        return self._process_raw_similarity_results(
            raw_results=similar_raw_results,
            source_object_id=source_object_id,
            target_object_type_name=target_object_type_for_results,
            n_results=n_results,
        )

    # --- Relation Instance Management (New methods) ---
    def add_relation_instance(self, instance: RelationInstance) -> RelationInstance:
        """Persists the RelationInstance to SQLite (for metadata via _InstanceManager)
        and then to Kuzu (via _InstanceManager which calls KuzuAdapter).
        """
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        # _InstanceManager.add_relation_instance will handle fetching RTD for KuzuAdapter
        return self._instance_manager.add_relation_instance(instance)

    def get_relation_instance(
        self, relation_type_name: str, relation_id: uuid.UUID,  # Use uuid.UUID for clarity
    ) -> Optional[RelationInstance]:
        """Retrieves a relation instance primarily from Kuzu, potentially enriched
        with SQLite metadata if applicable in the future.
        """
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        # The _InstanceManager.get_relation_instance should handle the UUID conversion if needed
        return self._instance_manager.get_relation_instance(relation_type_name, str(relation_id))


    def delete_relation_instance(
        self, relation_type_name: str, relation_id: uuid.UUID, # Use uuid.UUID
    ) -> bool:
        """Deletes a relation instance from Kuzu and SQLite."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        return self._instance_manager.delete_relation_instance(relation_type_name, str(relation_id))

    def find_relation_instances( # pylint: disable=R0913, R0917
        self,
        relation_type_name: Optional[str] = None,
        source_object_id: Optional[uuid.UUID] = None, # Use uuid.UUID
        target_object_id: Optional[uuid.UUID] = None, # Use uuid.UUID
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[RelationInstance]:
        """Exposes the Kuzu adapter's find method via _InstanceManager."""
        if not self.is_connected:
            msg = "Manager not connected."
            raise DatabaseError(msg)
        # Pass UUIDs directly, _InstanceManager can convert to string if needed for adapter
        return self._instance_manager.find_relation_instances(
            relation_type_name=relation_type_name,
            source_object_id=source_object_id,
            target_object_id=target_object_id,
            query=query,
            limit=limit,
        )

    # --- Complex Query Processing ---
    def process_complex_query(self, query: ComplexQuery) -> QueryResult:
        """Processes a complex query by planning, executing, and aggregating results.
        (Placeholder implementation).
        """
        if not self.is_connected:
            logger.warning(
                "process_complex_query called on a disconnected GrizabellaDBManager for '%s'.",
                self.db_name,
            )
            return QueryResult(object_instances=[], errors=["Database not connected."])

        logger.info(
            "Processing complex query for DB '%s': %s", self.db_name, query.description or "Untitled Query",
        )

        if not self._query_planner or not self._query_executor:
            logger.error(
                "Query planner or executor not initialized for DB '%s'.", self.db_name,
            )
            return QueryResult(
                object_instances=[],
                errors=["Query engine components not initialized."],
            )

        try:
            planned_query = self._query_planner.plan(query)
            return self._query_executor.execute(planned_query)
        except Exception as e: # pylint: disable=W0718
            # Catching general Exception here is intentional to ensure any query
            # processing error is caught and returned in the QueryResult,
            # preventing the application from crashing. The specific error
            # is logged for debugging purposes.
            logger.error(
                "Error during complex query processing for DB '%s': %s",
                self.db_name, e, exc_info=True,
            )
            return QueryResult(
                object_instances=[],
                errors=[f"Failed to process complex query: {e}"],
            )

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    custom_path_test_dir = Path("./custom_grizabella_data_manager_test").resolve()
    NAMED_DB_PATH_STR = "my_test_gdbm_db"
    def run_tests(db_manager_instance: GrizabellaDBManager, db_id: str) -> None: # pylint: disable=R0915
        """Runs a series of tests against the provided GrizabellaDBManager instance."""
        assert db_manager_instance.is_connected
        doc_type = ObjectTypeDefinition(
            name="Document", description="A textual document.",
            properties=[
                PropertyDefinition(name="title", data_type=PropertyDataType.TEXT,
                                   is_nullable=False),
                PropertyDefinition(name="content", data_type=PropertyDataType.TEXT),
                PropertyDefinition(name="page_count", data_type=PropertyDataType.INTEGER,
                                   is_nullable=True, is_indexed=True),
                PropertyDefinition(name="published_date", data_type=PropertyDataType.DATETIME,
                                   is_nullable=True),
                PropertyDefinition(name="custom_meta", data_type=PropertyDataType.JSON,
                                   is_nullable=True),
            ],
        )
        db_manager_instance.add_object_type_definition(doc_type)
        retrieved_doc_type = db_manager_instance.get_object_type_definition("Document")
        assert retrieved_doc_type
        assert retrieved_doc_type.name == "Document"
        assert len(retrieved_doc_type.properties) == 5
        doc_id_1 = uuid.uuid4()
        doc_instance_1 = ObjectInstance(
            id=doc_id_1, object_type_name="Document",
            properties={
                "title": "My First Document",
                "content": "This is the content of my first document.",
                "page_count": 10,
                "published_date": dt.datetime.now(dt.timezone.utc),
                "custom_meta": {"author": "Roo", "version": 1},
            },
            weight=decimal.Decimal("0.8"),
        )
        db_manager_instance.add_object_instance(doc_instance_1)
        retrieved_instance_1 = db_manager_instance.get_object_instance("Document", doc_id_1)
        assert retrieved_instance_1
        assert retrieved_instance_1.id == doc_id_1
        assert retrieved_instance_1.properties["title"] == "My First Document"
        assert retrieved_instance_1.properties["custom_meta"]["author"] == "Roo"
        assert retrieved_instance_1.weight == decimal.Decimal("0.8")
        queried_instances = db_manager_instance.query_object_instances(
            "Document", {"title": "My First Document"},
        )
        assert len(queried_instances) == 1
        assert queried_instances[0].id == doc_id_1
        retrieved_instance_1.properties["page_count"] = 12
        retrieved_instance_1.weight = decimal.Decimal("0.9")
        db_manager_instance.update_object_instance(retrieved_instance_1)
        updated_instance_1 = db_manager_instance.get_object_instance("Document", doc_id_1)
        assert updated_instance_1
        assert updated_instance_1.properties["page_count"] == 12
        assert updated_instance_1.weight == decimal.Decimal("0.9")
        doc_id_2 = uuid.uuid4()
        doc_instance_2_upsert = ObjectInstance(
            id=doc_id_2, object_type_name="Document",
            properties={"title": "Second Doc Upsert"},
        )
        db_manager_instance.upsert_object_instance(doc_instance_2_upsert)
        retrieved_upsert_2 = db_manager_instance.get_object_instance("Document", doc_id_2)
        assert retrieved_upsert_2
        assert retrieved_upsert_2.properties["title"] == "Second Doc Upsert"
        doc_instance_1_upsert = ObjectInstance(
            id=doc_id_1, object_type_name="Document",
            properties={"title": "My First Doc Upserted"},
            weight=decimal.Decimal("1.0"),
        )
        db_manager_instance.upsert_object_instance(doc_instance_1_upsert)
        retrieved_upsert_1 = db_manager_instance.get_object_instance("Document", doc_id_1)
        assert retrieved_upsert_1
        assert retrieved_upsert_1.properties["title"] == "My First Doc Upserted"
        assert retrieved_upsert_1.weight == decimal.Decimal("1.0")
        assert db_manager_instance.delete_object_instance("Document", doc_id_1)
        assert db_manager_instance.get_object_instance("Document", doc_id_1) is None
        assert db_manager_instance.remove_object_type_definition("Document")
        assert db_manager_instance.get_object_type_definition("Document") is None
        try:
            db_manager_instance.get_object_instance("Document", doc_id_2)
        except SchemaError:
            pass
        except DatabaseError as de:
            if "no such table" in str(de).lower() or \
               "not found" in str(de).lower():
                pass
            else:
                raise
    try:
        with GrizabellaDBManager() as default_db:
            run_tests(default_db, "default_db")
        with GrizabellaDBManager(NAMED_DB_PATH_STR) as named_db:
            run_tests(named_db, NAMED_DB_PATH_STR)
        custom_path = custom_path_test_dir / "my_custom_instance"
        custom_path.parent.mkdir(parents=True, exist_ok=True)
        with GrizabellaDBManager(custom_path) as custom_db:
            run_tests(custom_db, str(custom_path))
            assert custom_db.db_instance_root == custom_path
    except (ConfigurationError, DatabaseError, SchemaError, InstanceError) as e:
        logger.error(
            "A Grizabella specific error occurred during tests: %s", e, exc_info=True,
        )
    except Exception as e: # pylint: disable=broad-except
        logger.error(
            "An unexpected error occurred during tests: %s", e, exc_info=True,
        )
    finally:
        default_db_path = db_paths.get_grizabella_base_dir(create_if_not_exists=False) / "default"
        if default_db_path.exists():
            shutil.rmtree(default_db_path, ignore_errors=True)
        if "NAMED_DB_PATH_STR" in locals() and NAMED_DB_PATH_STR:
            named_db_full_path = db_paths.get_grizabella_base_dir(
                create_if_not_exists=False,
            ) / NAMED_DB_PATH_STR
            if named_db_full_path.exists():
                shutil.rmtree(named_db_full_path, ignore_errors=True)
        if custom_path_test_dir.exists():
            shutil.rmtree(custom_path_test_dir, ignore_errors=True)
