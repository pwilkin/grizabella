"""Grizabella Core Package.

This package aggregates the core components of the Grizabella framework,
including exceptions, data models, utility functions, database path management,
and the main database manager.
"""
from . import db_paths  # Make db_paths accessible as grizabella.core.db_paths
from .db_manager import GrizabellaDBManager
from .exceptions import (
    ConfigurationError,
    DatabaseError,
    EmbeddingError,
    GrizabellaException,
    InstanceError,
    SchemaError,
)
from .models import (
    EmbeddingDefinition,
    EmbeddingInstance,
    MemoryInstance,
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDataType,
    PropertyDefinition,
    RelationInstance,
    RelationTypeDefinition,
)
from .utils import (
    generate_uuid,
    get_current_utc_timestamp,
)

__all__ = [
    "ConfigurationError",
    "DatabaseError",
    "EmbeddingDefinition",
    "EmbeddingError",
    "EmbeddingInstance",
    # DB Manager
    "GrizabellaDBManager",
    # Exceptions
    "GrizabellaException",
    "InstanceError",
    "MemoryInstance",
    "ObjectInstance",
    "ObjectTypeDefinition",
    # Models
    "PropertyDataType",
    "PropertyDefinition",
    "RelationInstance",
    "RelationTypeDefinition",
    "SchemaError",
    # DB Paths (module itself)
    "db_paths",
    # Utils
    "generate_uuid",
    "get_current_utc_timestamp",
]
