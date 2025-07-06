"""Grizabella API Client.

This module provides the main Grizabella class, which serves as the public
API for interacting with the Grizabella data store.
"""

import logging  # Added import
import uuid
from pathlib import Path
from typing import Any, Optional, Union

from grizabella.core.db_manager import GrizabellaDBManager
from grizabella.core.exceptions import DatabaseError, SchemaError  # Added SchemaError
from grizabella.core.models import (
    EmbeddingDefinition,
    ObjectInstance,
    ObjectTypeDefinition,
    RelationInstance,
    RelationTypeDefinition,
)
from grizabella.core.query_models import ComplexQuery, QueryResult


class Grizabella:
    """Public API for interacting with the Grizabella data store.

    This class provides a high-level interface to manage and query data
    within a Grizabella database instance. It handles connection management,
    schema operations (object and relation types), data manipulation (objects
    and relations), embedding definitions, and complex queries.

    Attributes:
        _db_manager (GrizabellaDBManager): An instance of the database manager
            responsible for lower-level database interactions.
        _is_connected (bool): Tracks the connection state to the database.

    """

    def __init__(
        self,
        db_name_or_path: Union[str, Path] = "default",
        create_if_not_exists: bool = True,
    ) -> None:
        """Initializes the Grizabella API client.

        Sets up the connection to the specified Grizabella database. If the
        database does not exist and `create_if_not_exists` is True, it will
        be created.

        Args:
            db_name_or_path (Union[str, Path]): The name of the database or
                the file system path to the database directory.
                Defaults to "default".
            create_if_not_exists (bool): If True, the database will be
                created if it does not already exist. Defaults to True.

        """
        self._logger = logging.getLogger(__name__) # Initialize logger
        self._initial_db_name_or_path = db_name_or_path # Store the initial path/name
        self._db_manager = GrizabellaDBManager(
            db_name_or_path=db_name_or_path,
            create_if_not_exists=create_if_not_exists,
        )
        self._is_connected = False

    @property
    def db_name_or_path(self) -> Union[str, Path]:
        """Returns the database name or path this client was initialized with."""
        return self._initial_db_name_or_path

    def connect(self) -> None:
        """Connects to the underlying Grizabella database.

        Establishes a connection to the database if not already connected.
        This method is typically called automatically when using the client
        as a context manager or before performing database operations if
        the connection was previously closed.

        Raises:
            GrizabellaException: If there is an error connecting to the database.

        """
        if not self._is_connected:
            self._db_manager.connect()
            self._is_connected = True

    def close(self) -> None:
        """Closes the connection to the underlying Grizabella database.

        Releases any resources held by the database connection. It's important
        to close the connection when it's no longer needed, especially if not
        using the client as a context manager.

        Raises:
            GrizabellaException: If there is an error closing the database connection.

        """
        self._logger.info(f"Grizabella client close() called for db: {self.db_name_or_path}. Connected: {self._is_connected}")
        if self._is_connected:
            try:
                self._db_manager.close() # This should call _ConnectionHelper.close_all_adapters()
                self._logger.info(f"Grizabella client: self._db_manager.close() completed for {self.db_name_or_path}.")
            except Exception as e:
                self._logger.error(f"Grizabella client: Error during self._db_manager.close() for {self.db_name_or_path}: {e}", exc_info=True)
            finally:
                self._is_connected = False
                self._logger.info(f"Grizabella client: _is_connected set to False for {self.db_name_or_path}.")
        else:
            self._logger.info(f"Grizabella client: Already not connected for {self.db_name_or_path}, no action taken in close().")

    def __enter__(self) -> "Grizabella":
        """Context manager entry point. Connects to the database.

        Returns:
            Grizabella: The Grizabella API client instance.

        """
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Context manager exit point. Closes the database connection.

        Args:
            exc_type: The type of the exception, if any.
            exc_val: The exception instance, if any.
            exc_tb: The traceback object, if any.

        """
        self.close()

    # --- Schema Management ---
    def create_object_type(self, object_type_def: ObjectTypeDefinition) -> None:
        """Creates a new object type in the database.

        Object types define the schema for a category of objects, similar to
        tables in a relational database or node labels in a graph database.

        Args:
            object_type_def (ObjectTypeDefinition): The definition of the
                object type to create, including its name and properties.

        Raises:
            GrizabellaException: If the object type already exists or if there
                is an error during creation.
            NotConnectedError: If the client is not connected to the database.

        """
        self._db_manager.add_object_type_definition(object_type_def)

    def get_object_type_definition(
        self, type_name: str,
    ) -> Optional[ObjectTypeDefinition]:
        """Retrieves the definition of an object type.

        Args:
            type_name (str): The name of the object type to retrieve.

        Returns:
            Optional[ObjectTypeDefinition]: The definition of the object type
            if found, otherwise None.

        Raises:
            NotConnectedError: If the client is not connected to the database.

        """
        return self._db_manager.get_object_type_definition(type_name)

    def list_object_types(self) -> list[ObjectTypeDefinition]:
        """Lists all defined object types in the database.

        Returns:
            List[ObjectTypeDefinition]: A list of all object type definitions.

        Raises:
            NotConnectedError: If the client is not connected to the database.

        """
        if not self._is_connected:
            self._db_manager.connect()  # Ensure connection
        return self._db_manager.list_object_type_definitions()

    def delete_object_type(self, type_name: str) -> None:
        """Deletes an object type from the database.

        Warning: This operation may also delete all associated object instances
        and relations, depending on the underlying database implementation and
        cascade rules.

        Args:
            type_name (str): The name of the object type to delete.

        Raises:
            GrizabellaException: If the object type does not exist or if there
                is an error during deletion.
            NotConnectedError: If the client is not connected to the database.

        """
        self._db_manager.remove_object_type_definition(type_name)

    def create_relation_type(self, relation_type_def: RelationTypeDefinition) -> None:
        """Creates a new relation type in the database.

        Relation types define the schema for relationships between objects,
        including the source and target object types and any properties of
        the relation itself.

        Args:
            relation_type_def (RelationTypeDefinition): The definition of the
                relation type to create.

        Raises:
            GrizabellaException: If the relation type already exists or if
                there is an error during creation.
            NotConnectedError: If the client is not connected to the database.

        """
        self._db_manager.add_relation_type_definition(relation_type_def)

    def get_relation_type(self, type_name: str) -> Optional[RelationTypeDefinition]:
        """Retrieves the definition of a relation type.

        Args:
            type_name (str): The name of the relation type to retrieve.

        Returns:
            Optional[RelationTypeDefinition]: The definition of the relation
            type if found, otherwise None.

        Raises:
            NotConnectedError: If the client is not connected to the database.

        """
        return self._db_manager.get_relation_type_definition(type_name)

    def delete_relation_type(self, type_name: str) -> None:
        """Deletes a relation type from the database.

        Warning: This operation may also delete all associated relation instances,
        depending on the underlying database implementation.

        Args:
            type_name (str): The name of the relation type to delete.

        Raises:
            GrizabellaException: If the relation type does not exist or if
                there is an error during deletion.
            NotConnectedError: If the client is not connected to the database.

        """
        self._db_manager.remove_relation_type_definition(type_name)

    def list_relation_types(self) -> list[RelationTypeDefinition]:
        """Lists all defined relation types in the database.

        Returns:
            List[RelationTypeDefinition]: A list of all relation type definitions.

        Raises:
            NotConnectedError: If the client is not connected to the database.

        """
        if not self._is_connected:
            self._db_manager.connect()  # Ensure connection
        return self._db_manager.list_relation_type_definitions()

    # --- Data Management (Objects) ---
    def upsert_object(self, obj: ObjectInstance) -> ObjectInstance:
        """Creates a new object or updates an existing one.

        If an object with the same ID already exists, it will be updated
        with the properties from the provided `ObjectInstance`. Otherwise, a
        new object will be created.

        Args:
            obj (ObjectInstance): The object instance to create or update.
                It must include the object type name and its properties.
                The `id` field can be provided for updates or will be
                generated for new objects if not supplied.

        Returns:
            ObjectInstance: The created or updated object instance, potentially
            with a newly assigned ID or updated timestamps.

        Raises:
            GrizabellaException: If the object type does not exist or if there
                is an error during the upsert operation.
            NotConnectedError: If the client is not connected to the database.

        """
        return self._db_manager.upsert_object_instance(obj)

    def get_object_by_id(
        self, object_id: str, type_name: str,
    ) -> Optional[ObjectInstance]:
        """Retrieves an object by its ID and type.

        Args:
            object_id (str): The unique identifier of the object.
            type_name (str): The name of the object type.

        Returns:
            Optional[ObjectInstance]: The object instance if found,
            otherwise None.

        Raises:
            GrizabellaException: If the object type does not exist or if there
                is an error during retrieval.
            NotConnectedError: If the client is not connected to the database.

        """
        return self._db_manager.get_object_instance(
            object_type_name=type_name, instance_id=object_id,
        )

    def delete_object(self, object_id: str, type_name: str) -> bool:
        """Deletes an object by its ID and type.

        Args:
            object_id (str): The unique identifier of the object to delete.
            type_name (str): The name of the object type.

        Returns:
            bool: True if the object was successfully deleted, False otherwise
            (e.g., if the object was not found).

        Raises:
            GrizabellaException: If the object type does not exist or if there
                is an error during deletion.
            NotConnectedError: If the client is not connected to the database.

        """
        return self._db_manager.delete_object_instance(
            object_type_name=type_name, instance_id=object_id,
        )

    def find_objects(
        self,
        type_name: str,
        filter_criteria: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Finds objects of a given type, optionally matching filter criteria.

        Args:
            type_name (str): The name of the object type to search for.
            filter_criteria (Optional[Dict[str, Any]]): A dictionary where
                keys are property names and values are the values to filter by.
                Only objects matching all criteria will be returned.
                Defaults to None (no filtering).
            limit (Optional[int]): The maximum number of objects to return.
                Defaults to None (no limit).

        Returns:
            List[ObjectInstance]: A list of object instances matching the
            criteria.

        Raises:
            GrizabellaException: If the object type does not exist or if there
                is an error during the search.
            NotConnectedError: If the client is not connected to the database.

        """
        return self._db_manager.query_object_instances(
            object_type_name=type_name,
            conditions=filter_criteria or {},
            limit=limit,
        )

    # --- Data Management (Relations) ---
    def add_relation(self, relation: RelationInstance) -> RelationInstance:
        """Adds a new relation instance or updates an existing one (upsert).

        If the provided `RelationInstance` object includes an `id` that matches
        an existing relation, it will be updated. Otherwise, a new relation
        instance will be created. The `upsert_date` metadata field is
        automatically updated.

        Args:
            relation (RelationInstance): The relation instance to add or update.
                It must specify the relation type name, source object ID,
                target object ID, and any properties of the relation.
                The `id` field can be provided for updates.

        Returns:
            RelationInstance: The created or updated relation instance,
            potentially with a newly assigned ID or updated timestamps.

        Raises:
            GrizabellaException: If the relation type or involved objects do
                not exist, or if there is an error during the upsert operation.
            NotConnectedError: If the client is not connected to the database.

        """
        return self._db_manager.add_relation_instance(relation)

    def get_relation(
        self, from_object_id: str, to_object_id: str, relation_type_name: str,
    ) -> list[RelationInstance]:
        """Retrieves relation instances between two objects of a specific type.

        Note:
            This method's current implementation in the client API differs
            from the underlying `GrizabellaDBManager` which expects a
            `relation_id`. This method currently raises `NotImplementedError`
            and requires rework to correctly map to the DBManager's capabilities
            or a change in the client API signature.

        Args:
            from_object_id (str): The ID of the source object of the relation.
            to_object_id (str): The ID of the target object of the relation.
            relation_type_name (str): The name of the relation type.

        Returns:
            List[RelationInstance]: A list of relation instances matching the criteria.
            An empty list is returned if no matching relations are found.

        Raises:
            GrizabellaException: If there is an error during retrieval.
            NotConnectedError: If the client is not connected to the database.
            ValueError: If `from_object_id` or `to_object_id` are not valid UUID strings.

        """
        if not self._is_connected:
            self._db_manager.connect() # Ensure connection

        try:
            source_uuid = uuid.UUID(from_object_id)
            target_uuid = uuid.UUID(to_object_id)
        except ValueError as e:
            msg = (
                f"Invalid UUID string for from_object_id ('{from_object_id}') or "
                f"to_object_id ('{to_object_id}')."
            )
            raise ValueError(
                msg,
            ) from e

        return self._db_manager.find_relation_instances(
            relation_type_name=relation_type_name,
            source_object_id=source_uuid,
            target_object_id=target_uuid,
        )

    def delete_relation(
        self, relation_type_name: str, relation_id: str,
    ) -> bool:
        """Deletes a specific relation instance by its type and unique ID.

        Args:
            relation_type_name (str): The name of the relation type.
            relation_id (str): The unique identifier of the relation instance to delete.

        Returns:
            bool: True if the relation was successfully deleted, False otherwise
            (e.g., if the relation was not found).

        Raises:
            GrizabellaException: If there is an error during deletion.
            NotConnectedError: If the client is not connected to the database.
            ValueError: If `relation_id` is not a valid UUID string.

        """
        if not self._is_connected:
            self._db_manager.connect() # Ensure connection

        try:
            rel_uuid = uuid.UUID(relation_id)
        except ValueError as e:
            msg = f"Invalid UUID string for relation_id: '{relation_id}'."
            raise ValueError(
                msg,
            ) from e

        return self._db_manager.delete_relation_instance(
            relation_type_name=relation_type_name,
            relation_id=rel_uuid,
        )

    def query_relations(
        self,
        relation_type_name: Optional[str] = None,
        source_object_instance_id: Optional[str] = None,
        target_object_instance_id: Optional[str] = None,
        properties_query: Optional[dict[str, Any]] = None, # Matches 'query' in db_manager
        limit: Optional[int] = None,
    ) -> list[RelationInstance]:
        """Queries relation instances based on various criteria.

        Args:
            relation_type_name (Optional[str]): Filter by relation type name.
            source_object_instance_id (Optional[str]): Filter by source object ID (UUID string).
            target_object_instance_id (Optional[str]): Filter by target object ID (UUID string).
            properties_query (Optional[dict[str, Any]]): Filter by relation properties.
            limit (Optional[int]): Maximum number of results to return.

        Returns:
            List[RelationInstance]: A list of matching relation instances.

        Raises:
            NotConnectedError: If the client is not connected to the database.
            ValueError: If provided UUID strings are invalid.
            GrizabellaException: For other underlying database or processing errors.

        """
        if not self._is_connected:
            self._db_manager.connect()  # Ensure connection

        source_uuid: Optional[uuid.UUID] = None
        if source_object_instance_id:
            try:
                source_uuid = uuid.UUID(source_object_instance_id)
            except ValueError as e:
                raise ValueError(f"Invalid UUID string for source_object_instance_id: '{source_object_instance_id}'.") from e

        target_uuid: Optional[uuid.UUID] = None
        if target_object_instance_id:
            try:
                target_uuid = uuid.UUID(target_object_instance_id)
            except ValueError as e:
                raise ValueError(f"Invalid UUID string for target_object_instance_id: '{target_object_instance_id}'.") from e

        return self._db_manager.find_relation_instances(
            relation_type_name=relation_type_name,
            source_object_id=source_uuid, # Pass UUID object
            target_object_id=target_uuid, # Pass UUID object
            query=properties_query,
            limit=limit,
        )

    def get_outgoing_relations(
        self, object_id: str, type_name: str, relation_type_name: Optional[str] = None, # pylint: disable=unused-argument
    ) -> list[RelationInstance]:
        """Retrieves all outgoing relations from a given object.

        Args:
            object_id (str): The ID of the source object.
            type_name (str): The type name of the source object. (Note: This
                parameter is not directly used by the underlying DBManager's
                `find_relation_instances` for this specific query but is kept
                for API consistency or future use).
            relation_type_name (Optional[str]): If provided, filters relations
                by this specific relation type name. Defaults to None (no filter).

        Returns:
            List[RelationInstance]: A list of outgoing relation instances.

        Raises:
            GrizabellaException: If there is an error during retrieval.
            NotConnectedError: If the client is not connected to the database.
            ValueError: If `object_id` is not a valid UUID string.

        """
        if not self._is_connected:
            self._db_manager.connect()  # Ensure connection
        try:
            source_uuid = uuid.UUID(object_id)
        except ValueError as e:
            # It's generally better to let exceptions propagate or handle them more specifically.
            # For now, re-raising to make it clear to the caller.
            msg = f"Invalid UUID string for source_object_id: {object_id}"
            raise ValueError(
                msg,
            ) from e

        return self._db_manager.find_relation_instances(
            relation_type_name=relation_type_name, source_object_id=source_uuid,
        )

    def get_incoming_relations(
        self, object_id: str, type_name: str, relation_type_name: Optional[str] = None, # pylint: disable=unused-argument
    ) -> list[RelationInstance]:
        """Retrieves all incoming relations to a given object.

        Args:
            object_id (str): The ID of the target object.
            type_name (str): The type name of the target object. (Note: This
                parameter is not directly used by the underlying DBManager's
                `find_relation_instances` for this specific query but is kept
                for API consistency or future use).
            relation_type_name (Optional[str]): If provided, filters relations
                by this specific relation type name. Defaults to None (no filter).

        Returns:
            List[RelationInstance]: A list of incoming relation instances.

        Raises:
            GrizabellaException: If there is an error during retrieval.
            NotConnectedError: If the client is not connected to the database.
            ValueError: If `object_id` is not a valid UUID string.

        """
        if not self._is_connected:
            self._db_manager.connect()  # Ensure connection
        try:
            target_uuid = uuid.UUID(object_id)
        except ValueError as e:
            msg = f"Invalid UUID string for target_object_id: {object_id}"
            raise ValueError(
                msg,
            ) from e

        return self._db_manager.find_relation_instances(
            relation_type_name=relation_type_name, target_object_id=target_uuid,
        )

    # --- Embedding Definition Management ---
    def create_embedding_definition(
        self, embedding_def: EmbeddingDefinition,
    ) -> EmbeddingDefinition:
        """Creates a new embedding definition.

        Embedding definitions specify how embeddings should be generated and
        stored for objects of a particular type or for specific properties.

        Args:
            embedding_def (EmbeddingDefinition): The definition of the
                embedding to create, including its name, model details,
                and associated object type or properties.

        Returns:
            EmbeddingDefinition: The created embedding definition.

        Raises:
            GrizabellaException: If an embedding definition with the same name
                already exists or if there is an error during creation.
            NotConnectedError: If the client is not connected to the database.

        """
        if not self._is_connected:
            self._db_manager.connect()
        self._db_manager.add_embedding_definition(embedding_def, persist=True)
        return embedding_def

    def get_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:
        """Retrieves an embedding definition by its name.

        Args:
            name (str): The name of the embedding definition to retrieve.

        Returns:
            Optional[EmbeddingDefinition]: The embedding definition if found,
            otherwise None.

        Raises:
            NotConnectedError: If the client is not connected to the database.

        """
        if not self._is_connected:
            self._db_manager.connect()
        return self._db_manager.get_embedding_definition(name)

    def list_embedding_definitions(self) -> list[EmbeddingDefinition]:
        """Lists all embedding definitions in the database.

        Returns:
            List[EmbeddingDefinition]: A list of all embedding definitions.

        Raises:
            NotConnectedError: If the client is not connected to the database.

        """
        if not self._is_connected:
            self._db_manager.connect()
        return self._db_manager.list_embedding_definitions()

    def delete_embedding_definition(self, name: str) -> bool:
        """Deletes an embedding definition.

        Warning: This may also delete associated embedding vectors from the
        vector store, depending on the implementation.

        Args:
            name (str): The name of the embedding definition to delete.

        Returns:
            bool: True if the definition was successfully deleted, False
            otherwise (e.g., if not found).

        Raises:
            GrizabellaException: If there is an error during deletion.
            NotConnectedError: If the client is not connected to the database.

        """
        if not self._is_connected:
            self._db_manager.connect()
        return self._db_manager.remove_embedding_definition(name, persist=True)

    # --- Querying (Example: Embedding Search) ---
    def search_similar_objects(
        self,
        object_id: str,
        type_name: str,
        n_results: int = 5,
        search_properties: Optional[list[str]] = None,
    ) -> list[tuple[ObjectInstance, float]]:
        """Searches for objects similar to a given object using its embeddings.

        This method finds objects of the same type as the source object that
        are semantically similar, based on a specified or inferred embedding definition.

        Args:
            object_id (str): The ID of the source object to find similar items for.
            type_name (str): The type name of the source object.
            n_results (int): The maximum number of similar results to return.
                Defaults to 5.
            search_properties (Optional[List[str]]): If provided, the first element
                is used as the specific `embedding_definition_name` to use for both
                the source object's vector retrieval and the target search.
                If None or empty, the first available `EmbeddingDefinition` for the
                `type_name` will be used.

        Returns:
            List[Tuple[ObjectInstance, float]]: A list of tuples, where each
            tuple contains a similar `ObjectInstance` and its similarity score
            (typically distance, where lower is more similar).

        Raises:
            NotConnectedError: If the client is not connected to the database.
            ValueError: If `object_id` is not a valid UUID string.
            SchemaError: If a suitable `EmbeddingDefinition` cannot be found.
            EmbeddingError: If an embedding for the source object cannot be found.
            GrizabellaException: For other underlying database or processing errors.

        """
        if not self._is_connected:
            self._db_manager.connect()

        try:
            source_uuid = uuid.UUID(object_id)
        except ValueError as e:
            msg = f"Invalid UUID string for object_id: '{object_id}'."
            raise ValueError(msg) from e

        embedding_definition_name: Optional[str] = None
        if search_properties and search_properties[0]:
            embedding_definition_name = search_properties[0]
            # Validate this ED exists and is for the correct object type
            ed = self._db_manager.get_embedding_definition(embedding_definition_name)
            if not ed:
                msg = f"Specified EmbeddingDefinition '{embedding_definition_name}' not found."
                raise SchemaError(
                    msg,
                )
            if ed.object_type_name != type_name:
                msg = (
                    f"Specified EmbeddingDefinition '{embedding_definition_name}' is for object type "
                    f"'{ed.object_type_name}', but expected type '{type_name}' for object '{object_id}'."
                )
                raise SchemaError(
                    msg,
                )
        else:
            # Find the first available EmbeddingDefinition for the type_name
            all_eds = self._db_manager.list_embedding_definitions()
            for ed in all_eds:
                if ed.object_type_name == type_name:
                    embedding_definition_name = ed.name
                    break
            if not embedding_definition_name:
                msg = (
                    f"No EmbeddingDefinition found for object type '{type_name}'. "
                    "Cannot perform similarity search."
                )
                raise SchemaError(
                    msg,
                )

        return self._db_manager.find_objects_similar_to_instance(
            source_object_id=source_uuid,
            source_object_type_name=type_name,
            embedding_definition_name=embedding_definition_name,
            n_results=n_results,
        )

    def find_similar(
        self,
        embedding_name: str,
        query_text: str,
        limit: int = 5,
        filter_condition: Optional[str] = None,
    ) -> list[ObjectInstance]: # Changed return type to list[ObjectInstance] for simplicity in test
        """Finds objects semantically similar to a given query text.

        Args:
            embedding_name (str): The name of the EmbeddingDefinition to use.
            query_text (str): The text to find similar objects for.
            limit (int): The maximum number of similar results to return. Defaults to 5.
            filter_condition (Optional[str]): An SQL-like WHERE clause to pre-filter results.

        Returns:
            List[ObjectInstance]: A list of ObjectInstances that are semantically
            similar to the query_text, ordered by similarity.

        Raises:
            NotConnectedError: If the client is not connected to the database.
            SchemaError: If the specified EmbeddingDefinition is not found or is invalid.
            EmbeddingError: If an error occurs during embedding generation or search.
            GrizabellaException: For other underlying database or processing errors.

        """
        if not self._is_connected:
            self._db_manager.connect()

        ed = self._db_manager.get_embedding_definition(embedding_name)
        if not ed:
            msg = f"EmbeddingDefinition '{embedding_name}' not found."
            raise SchemaError(msg)

        # Call the db_manager's method that can handle query_text
        # This method in _InstanceManager returns raw results: list[dict[str, Any]]
        # where dicts contain 'object_instance_id' and '_distance'
        raw_results = self._db_manager.find_similar_objects_by_embedding(
            embedding_definition_name=embedding_name,
            query_text=query_text,
            limit=limit,
            retrieve_full_objects=False, # We need IDs and scores to process further
            filter_condition=filter_condition,
        )

        if not raw_results:
            return []

        # We need to convert raw_results (list of dicts with id and score)
        # into a list of ObjectInstance, similar to how find_objects_similar_to_instance does.
        # The _process_raw_similarity_results method in DBManager is suitable.
        # It expects a source_object_id for filtering, which is not applicable here.
        # We'll adapt its logic or call it carefully.

        # Let's get the target object type from the embedding definition
        target_object_type_name = ed.object_type_name

        # Re-implementing parts of _process_raw_similarity_results logic here
        # as it's not directly callable with a query_text scenario (no source_object_id)

        final_results_with_scores: list[tuple[ObjectInstance, float]] = []
        result_ids_map: dict[uuid.UUID, float] = {}

        for res in raw_results:
            try:
                obj_id_str = res.get("object_instance_id")
                if not obj_id_str:
                    continue
                obj_id = uuid.UUID(obj_id_str)
                score = float(res.get("_distance", 0.0)) # LanceDB uses _distance
                result_ids_map[obj_id] = score
            except (ValueError, KeyError, TypeError) as e:
                # self._db_manager._logger.warning(...) # Can't access logger directly
                print(f"Warning: Skipping result due to parsing error: {res}, error: {e}") # Basic print for now
                continue

        if not result_ids_map:
            return []

        sorted_similar_items = sorted(result_ids_map.items(), key=lambda item: item[1])[:limit]
        result_ids_to_fetch = [item[0] for item in sorted_similar_items]

        if result_ids_to_fetch:
            # Convert UUIDs to strings for get_objects_by_ids if it expects strings
            # However, db_manager.get_objects_by_ids takes list[uuid.UUID]
            fetched_objects = self._db_manager.get_objects_by_ids(
                target_object_type_name, result_ids_to_fetch,
            )
            fetched_objects_map = {obj.id: obj for obj in fetched_objects}

            for obj_id_val, _ in sorted_similar_items: # score_val not used in final list of ObjectInstance
                if obj_id_val in fetched_objects_map:
                    final_results_with_scores.append(
                        (fetched_objects_map[obj_id_val], _), # Keep score for potential future use
                    )

        # Return only the ObjectInstances, ordered by similarity (which sorted_similar_items already did)
        return [obj_inst for obj_inst, score in final_results_with_scores]

    # --- Complex Querying ---
    def execute_complex_query(self, query: ComplexQuery) -> QueryResult:
        """Executes a complex query spanning multiple database layers.

        Complex queries allow for sophisticated search patterns, including
        graph traversals, relational filters, and embedding-based searches,
        combined into a single query operation.

        Args:
            query (ComplexQuery): A ``ComplexQuery`` object defining the
                components of the search, such as graph traversals,
                relational filters, and embedding searches.

        Returns:
            QueryResult: A ``QueryResult`` object containing a list of matching
            ``ObjectInstance``s and a list of any errors encountered during
            query processing.

        Raises:
            NotConnectedError: If the client is not connected to the database.
            GrizabellaException: If there is an error during query planning
                or execution.

        """
        if not self._is_connected:
            raise DatabaseError("Database not connected. Call connect() before executing queries.")

        if hasattr(self._db_manager, "process_complex_query"):
            return self._db_manager.process_complex_query(query)
        # This indicates a missing implementation in the DBManager,
        # which is a development-time issue.
        # Raising NotImplementedError is more appropriate here.
        msg = "GrizabellaDBManager.process_complex_query not yet implemented."
        raise NotImplementedError(
            msg,
        )
