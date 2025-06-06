"""Abstract Base Class for Grizabella database adapters."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from uuid import UUID

from grizabella.core.models import (
    EmbeddingDefinition,
    EmbeddingInstance,
    ObjectInstance,
    ObjectTypeDefinition,
    RelationInstance,
    # PropertyDefinition # Not used directly in base
    RelationTypeDefinition,
)

# from grizabella.core.exceptions import (
#     SchemaError, DatabaseError, InstanceError
# ) # Not used directly in base


class BaseDBAdapter(ABC): # pylint: disable=R0904
    """Abstract Base Class for Grizabella database adapters.
    Defines the common interface for interacting with different database backends.
    """

    def __init__(self, db_path: str, config: Optional[dict[str, Any]] = None) -> None:
        self.db_path = db_path
        self.config = config or {}
        self._connect()

    @abstractmethod
    def _connect(self) -> None:
        """Establish a connection to the database."""

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""

    # --- Schema Management ---
    @abstractmethod
    def create_object_type(self, definition: ObjectTypeDefinition) -> None:
        """Create a new object type (e.g., table) in the database."""

    @abstractmethod
    def get_object_type(self, name: str) -> Optional[ObjectTypeDefinition]:
        """Retrieve an object type definition by name."""

    @abstractmethod
    def update_object_type(self, definition: ObjectTypeDefinition) -> None:
        """Update an existing object type (e.g., add/remove columns). May be limited by DB."""

    @abstractmethod
    def delete_object_type(self, name: str) -> None:
        """Delete an object type and all its instances."""

    @abstractmethod
    def list_object_types(self) -> list[str]:
        """List names of all object types in the database."""

    # --- Object Instance Management ---
    @abstractmethod
    def upsert_object_instance(self, instance: ObjectInstance) -> ObjectInstance:
        """Create or update an object instance."""

    @abstractmethod
    def get_object_instance(
        self, object_type_name: str, instance_id: UUID,
    ) -> Optional[ObjectInstance]:
        """Retrieve an object instance by its type and ID."""

    @abstractmethod
    def delete_object_instance(self, object_type_name: str, instance_id: UUID) -> bool:
        """Delete an object instance by its type and ID. Returns True if deleted."""

    @abstractmethod
    def find_object_instances(
        self,
        object_type_name: str,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Find object instances based on a query."""

    @abstractmethod
    def get_all_object_ids_for_type(self, object_type_name: str) -> list[UUID]:
        """Retrieve all object instance IDs for a given object type."""

    # --- Embedding Management (primarily for LanceDB, but interface can be here) ---
    @abstractmethod
    def add_embedding_definition(self, definition: EmbeddingDefinition) -> None:
        """Define how embeddings should be created for an object type."""

    @abstractmethod
    def get_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:
        """Retrieve an embedding definition by name."""

    @abstractmethod
    def upsert_embedding_instance(self, instance: EmbeddingInstance) -> EmbeddingInstance:
        """Store or update an embedding instance."""

    @abstractmethod
    def get_embedding_instance(
        self, embedding_definition_name: str, object_instance_id: UUID,
    ) -> Optional[EmbeddingInstance]:
        """Retrieve a specific embedding instance."""

    @abstractmethod
    def find_similar_embeddings(
        self,
        embedding_definition_name: str,
        vector: list[float],
        top_k: int = 5,
    ) -> list[EmbeddingInstance]:
        """Find objects with similar embeddings."""

    # --- Relation Management (primarily for Kuzu, but interface can be here) ---
    @abstractmethod
    def create_relation_type(self, definition: RelationTypeDefinition) -> None:
        """Create a new relation type between object types."""

    @abstractmethod
    def get_relation_type(self, name: str) -> Optional[RelationTypeDefinition]:
        """Retrieve a relation type definition by name."""

    @abstractmethod
    def upsert_relation_instance(self, instance: RelationInstance, rtd: Optional[RelationTypeDefinition] = None) -> RelationInstance:
        """Create or update a relation instance between two object instances."""

    @abstractmethod
    def get_relation_instance(
        self, relation_type_name: str, relation_id: UUID,
    ) -> Optional[RelationInstance]:
        """Retrieve a relation instance by its type and ID."""

    @abstractmethod
    def find_relation_instances( # pylint: disable=R0913, R0917
        self,
        relation_type_name: Optional[str] = None,
        source_object_id: Optional[UUID] = None,
        target_object_id: Optional[UUID] = None,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[RelationInstance]:
        """Find relation instances based on various criteria."""

    @abstractmethod
    def delete_relation_instance(self, relation_type_name: str, relation_id: UUID) -> bool:
        """Delete a relation instance. Returns True if deleted."""
