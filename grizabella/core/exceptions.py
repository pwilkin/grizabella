"""Grizabella Core Custom Exceptions."""

class GrizabellaException(Exception):
    """Base exception class for Grizabella project."""

class ConfigurationError(GrizabellaException):
    """Exception raised for errors in configuration."""

class DatabaseError(GrizabellaException):
    """Exception raised for database-related errors."""

class SchemaError(GrizabellaException):
    """Exception raised for schema definition or validation errors."""

class InstanceError(GrizabellaException):
    """Exception raised for errors related to data instances."""

class EmbeddingError(GrizabellaException):
    """Exception raised for errors during embedding generation or processing."""
