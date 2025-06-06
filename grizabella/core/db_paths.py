"""Defines paths and helper functions for Grizabella database instances."""
import os
from pathlib import Path
from typing import Union

from .exceptions import ConfigurationError

# Default directory names within a Grizabella database instance
SQLITE_DIR_NAME = "sqlite_data"
LANCEDB_DIR_NAME = "lancedb_data"
KUZU_DIR_NAME = "kuzu_data"
SQLITE_DB_FILENAME = "grizabella.db"

# Default Grizabella user directory and default database name
GRIZABELLA_BASE_DIR_NAME = ".grizabella"
DEFAULT_DB_INSTANCE_NAME = "default_db"

def get_grizabella_base_dir(create_if_not_exists: bool = True) -> Path:
    """Gets the base directory for Grizabella user data (~/.grizabella).

    Args:
        create_if_not_exists: If True, creates the directory if it doesn't exist.

    Returns:
        Path to the Grizabella base directory.

    Raises:
        ConfigurationError: If the directory cannot be created.

    """
    base_dir = Path.home() / GRIZABELLA_BASE_DIR_NAME
    if create_if_not_exists and not base_dir.exists():
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Could not create Grizabella base directory at {base_dir}: {e}"
            raise ConfigurationError(
                msg,
            ) from e
    return base_dir

def get_db_instance_path(
    db_name_or_path: Union[str, Path],
    create_if_not_exists: bool = True,
) -> Path:
    """Resolves the root path for a Grizabella database instance.

    If db_name_or_path is a simple name (not an absolute path), it's treated
    as a named database under the Grizabella base directory.
    "default" is an alias for DEFAULT_DB_INSTANCE_NAME.
    If it's an absolute path, that path is used directly.

    Args:
        db_name_or_path: The name of the database instance (e.g., "my_project", "default")
                         or an absolute Path to a custom database instance directory.
        create_if_not_exists: If True, creates the instance directory if it doesn't exist.

    Returns:
        Path to the Grizabella database instance root directory.

    Raises:
        ConfigurationError: If the directory cannot be created or path is invalid.

    """
    grizabella_base = get_grizabella_base_dir(create_if_not_exists)
    instance_path: Path

    if isinstance(db_name_or_path, Path):
        if not db_name_or_path.is_absolute():
            # Interpret relative paths as relative to grizabella_base for consistency
            # Or raise error: raise ConfigurationError("Custom Path must be absolute.")
            instance_path = grizabella_base / db_name_or_path
        else:
            instance_path = db_name_or_path
    elif isinstance(db_name_or_path, str):
        # Check if it looks like an absolute path (heuristic)
        if os.path.isabs(db_name_or_path):
            instance_path = Path(db_name_or_path)
        else:
            name = (
                DEFAULT_DB_INSTANCE_NAME
                if db_name_or_path.lower() == "default"
                else db_name_or_path
            )
            if not name or "/" in name or "\\" in name or ":" in name: # Basic validation for name
                msg = f"Invalid database instance name: {name}"
                raise ConfigurationError(msg)
            instance_path = grizabella_base / name
    else:
        msg = "db_name_or_path must be a string or a Path object."
        raise TypeError(msg)

    if create_if_not_exists and not instance_path.exists():
        try:
            instance_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Could not create database instance directory at {instance_path}: {e}"
            raise ConfigurationError(
                msg,
            ) from e
    elif not instance_path.is_dir() and instance_path.exists():
        msg = f"Database instance path {instance_path} exists but is not a directory."
        raise ConfigurationError(
            msg,
        )

    return instance_path

def get_sqlite_path(db_instance_root: Path, create_if_not_exists: bool = True) -> Path:
    """Gets the path to the SQLite database file within an instance directory."""
    sqlite_dir = db_instance_root / SQLITE_DIR_NAME
    if create_if_not_exists and not sqlite_dir.exists():
        try:
            sqlite_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Could not create SQLite data directory at {sqlite_dir}: {e}"
            raise ConfigurationError(
                msg,
            ) from e
    return sqlite_dir / SQLITE_DB_FILENAME

def get_lancedb_uri(db_instance_root: Path, create_if_not_exists: bool = True) -> str:
    """Gets the URI (directory path) for LanceDB within an instance directory."""
    lancedb_dir = db_instance_root / LANCEDB_DIR_NAME
    if create_if_not_exists and not lancedb_dir.exists():
        try:
            lancedb_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Could not create LanceDB data directory at {lancedb_dir}: {e}"
            raise ConfigurationError(
                msg,
            ) from e
    return str(lancedb_dir) # LanceDB connect() takes a URI string

def get_kuzu_path(db_instance_root: Path, create_if_not_exists: bool = True) -> Path:
    """Gets the path to the Kuzu database directory within an instance directory."""
    kuzu_dir = db_instance_root / KUZU_DIR_NAME
    if create_if_not_exists and not kuzu_dir.exists():
        try:
            kuzu_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Could not create Kuzu data directory at {kuzu_dir}: {e}"
            raise ConfigurationError(
                msg,
            ) from e
    return kuzu_dir
