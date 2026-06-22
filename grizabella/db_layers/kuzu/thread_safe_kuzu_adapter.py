"""Thread-safe Kuzu adapter with proper connection isolation.

This module provides a thread-safe implementation of the KuzuDB adapter
that addresses the threading issues causing memory leaks. It uses thread-local
storage to ensure each thread has its own connection while sharing the
database instance safely.
"""

import glob  # Added
import logging  # Added
import os  # Added
import threading  # For logging thread ID
import time  # For lock-contention retry backoff
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import ladybug as lbug

from grizabella.core.exceptions import DatabaseError, InstanceError, SchemaError, ConfigurationError
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
from grizabella.core.models import (
    ObjectTypeDefinition as ObjectTypeDefinitionModel,
)
from grizabella.core.models import (
    RelationTypeDefinition as RelationTypeDefinitionModel,
)
from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter
from grizabella.core.query_models import GraphTraversalClause  # Added for new method
from grizabella.db_layers.common.base_adapter import BaseDBAdapter

logger = logging.getLogger(__name__)

class ThreadSafeKuzuAdapter(KuzuAdapter):  # pylint: disable=R0904
    """Thread-safe Kuzu adapter with proper connection isolation.
    
    This adapter addresses the threading issues in the original KuzuAdapter by:
    - Using thread-local storage for connections
    - Proper cleanup of lock files and WAL files
    - Shared database instance with thread-local connections
    - Enhanced error handling and logging
    """

    def __init__(self, db_path: str, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize the thread-safe Kuzu adapter.
        
        For real_ladybug: Validates that the parent directory exists and creates
        the database file if it doesn't exist.
        For kuzu compatibility: Creates directory structure if needed.
        
        Args:
            db_path: Path to the Kuzu database (file path for real_ladybug, directory for kuzu)
            config: Optional configuration dictionary
            
        Raises:
            ConfigurationError: If the parent directory doesn't exist or cannot be created
        """
        thread_id = threading.get_ident()
        logger.info(f"ThreadSafeKuzuAdapter: Initializing in thread ID: {thread_id} for db_path: {db_path}")
        
        # Validate that parent directory exists for real_ladybug compatibility
        import os
        from pathlib import Path
        
        db_path_obj = Path(db_path)
        
        # Ensure parent directory exists
        parent_dir = db_path_obj.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"ThreadSafeKuzuAdapter: Created parent directory {parent_dir} for database")
            except OSError as e:
                msg = f"ThreadSafeKuzuAdapter: Unable to create parent directory {parent_dir}: {e}"
                raise ConfigurationError(msg) from e
        
        # For real_ladybug compatibility, ensure the database file path is properly formed
        if not db_path_obj.suffix:
            # If no extension, add .db to make it a proper file path
            db_path_obj = db_path_obj.with_suffix('.db')
            logger.info(f"ThreadSafeKuzuAdapter: Added .db extension, using {db_path_obj}")
        
        self._db_path = str(db_path_obj)
        self._config = config or {}
        self._lock = threading.RLock()
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Shared database instance (thread-safe in Kuzu)
        self._db: Optional[lbug.Database] = None
        self._db_lock = threading.Lock()

        # Periodic WAL checkpointing. ladybug appends every write to a sibling WAL that it
        # replays on next open. During a large project's write burst the WAL can grow to
        # ~10+ MB, at which point ladybug 0.16.1 trips a WAL-record assertion
        # ("UNREACHABLE_CODE") that *aborts the process mid-write* -- losing that project's
        # graph tail and failing its relationship storage entirely (observed on roche/stada).
        # We bound the WAL by checkpointing (flush WAL -> .db, truncate) once it grows past a
        # threshold. Tunable via KUZU_CHECKPOINT_WAL_MB (default 4 MB; 0 disables).
        # ladybug 0.16.1 SEGFAULTS *inside* CHECKPOINT under load. Verified by pinpoint:
        # roche dies with a libstdc++ heap-overrun immediately after a mid-write CHECKPOINT
        # ("about-to-CHECKPOINT wal=4.28MB" is the last log line before the SIGSEGV), while the
        # very same objects checkpoint fine in other projects -- a native bug in ladybug's
        # checkpoint serialization, dataset-dependent. So by default we do NOT checkpoint
        # mid-write at all: KUZU_CHECKPOINT_WAL_MB defaults to 0 (our size-gated checkpoint
        # off) AND ladybug's own auto-checkpoint is disabled (KUZU_AUTO_CHECKPOINT defaults to
        # 0) -- its internal CHECKPOINT is the same crash-prone code. The WAL is flushed only
        # once, at quiescent close, via ladybug's forceCheckpointOnClose (default True): no
        # concurrent writes there, which avoids the under-load crash. A kill mid-write leaves a
        # torn WAL that the open-time self-heal quarantines. Env vars do NOT propagate into this
        # MCP subprocess, so these defaults (not the env) are what actually take effect; set
        # KUZU_CHECKPOINT_WAL_MB>0 / KUZU_AUTO_CHECKPOINT=1 only if a future ladybug fixes this.
        self._writes_since_ckpt = 0
        try:
            self._ckpt_wal_bytes = int(float(os.environ.get("KUZU_CHECKPOINT_WAL_MB", "0")) * 1024 * 1024)
        except (TypeError, ValueError):
            self._ckpt_wal_bytes = 0
        self._ckpt_stat_interval = 50
        self._auto_ckpt = os.environ.get("KUZU_AUTO_CHECKPOINT", "0") not in ("0", "false", "False", "no")

        # The SAFE checkpoint: synchronously at finish_bulk_addition (the indexer's flush
        # boundaries every N files, and once at project end). It runs between write bursts --
        # after embeddings, with no concurrent Cypher -- so it avoids the under-load crash that
        # mid-write/auto checkpoints hit (roche proved a quiescent checkpoint is safe). And
        # because the indexer awaits the finish_bulk_addition MCP call, the WAL is durably
        # flushed before the process can be torn down -- unlike ladybug's forceCheckpointOnClose,
        # which a shutdown SIGKILL was interrupting, leaving a multi-MB WAL that the next open
        # quarantined (graph data lost while SQLite kept it -> the two tiers diverged). This is
        # what keeps the WAL bounded AND the graph tier complete. Default on; KUZU_CHECKPOINT_ON_FINISH=0 to disable.
        self._checkpoint_on_finish = os.environ.get("KUZU_CHECKPOINT_ON_FINISH", "1") not in ("0", "false", "False", "no")

        # Maps a node id -> the node table it lives in, so a relation upsert can MERGE on the
        # correct (source, target) type pair. A relation type may span several pairs (e.g.
        # CONTAINS: JavaClass->JavaMethod, JavaClass->JavaField, ...) and the rel table is now
        # created with all of them; resolving the real endpoint types here is what lets every
        # edge materialize instead of only the first declared pair. Populated cheaply as
        # objects are upserted; misses (cross-run references) fall back to PK-indexed probes.
        self._node_table_cache: dict[str, str] = {}

        # Initialize database (shared across threads)
        self._init_database()

    def _init_database(self):
        """Initialize the shared database instance."""
        with self._db_lock:
            if self._db is None:
                # Clean up stale lock files left behind by a previous unclean shutdown.
                self._cleanup_stale_files()
                try:
                    logger.info(f"ThreadSafeKuzuAdapter: Creating shared Database instance for {self._db_path}")
                    self._db = lbug.Database(self._db_path, auto_checkpoint=self._auto_ckpt)
                    logger.info(f"ThreadSafeKuzuAdapter: Shared Database instance created: {self._db}")
                except Exception as e:
                    # Lock contention: a previous process hasn't released its fcntl lock on
                    # the DB file yet (common when projects are indexed back-to-back, each in
                    # its own short-lived server). This is transient -- retry briefly.
                    if "could not set lock" in str(e).lower():
                        if self._retry_open_on_lock():
                            return
                        logger.error(
                            f"ThreadSafeKuzuAdapter: DB lock on {self._db_path} still held "
                            f"after retries"
                        )
                        raise DatabaseError(f"KuzuDB initialization error: {e}") from e
                    # A process killed mid-write (OOM/SIGKILL/timeout) can leave the
                    # write-ahead log in a state ladybug cannot replay: it asserts
                    # ("wal_record.cpp ... UNREACHABLE_CODE") on open instead of discarding
                    # it, which permanently bricks the graph tier on every later start.
                    # The main DB file is consistent up to its last checkpoint, so quarantine
                    # the unreplayable WAL and retry once. We lose only the un-checkpointed
                    # tail of the killed run, which was never committed anyway.
                    if self._recover_from_corrupt_wal(e):
                        try:
                            self._db = lbug.Database(self._db_path, auto_checkpoint=self._auto_ckpt)
                            logger.warning(
                                f"ThreadSafeKuzuAdapter: Recovered database for {self._db_path} "
                                f"after quarantining an unreplayable WAL"
                            )
                            return
                        except Exception as e2:
                            logger.error(f"ThreadSafeKuzuAdapter: Recovery retry failed: {e2}")
                            raise DatabaseError(
                                f"KuzuDB initialization error after WAL recovery: {e2}"
                            ) from e2
                    logger.error(f"ThreadSafeKuzuAdapter: Error creating database: {e}")
                    raise DatabaseError(f"KuzuDB initialization error: {e}") from e

    def _retry_open_on_lock(self) -> bool:
        """Retry opening the DB while another process releases its lock.

        Returns True if the DB was opened, False if it stayed locked through all retries
        (the caller then raises). Re-raises immediately on any non-lock error.
        """
        for attempt in range(1, 6):
            time.sleep(2)
            try:
                self._db = lbug.Database(self._db_path, auto_checkpoint=self._auto_ckpt)
                logger.warning(
                    f"ThreadSafeKuzuAdapter: Acquired DB lock for {self._db_path} "
                    f"on retry {attempt}"
                )
                return True
            except Exception as e:
                if "could not set lock" not in str(e).lower():
                    raise
                logger.info(
                    f"ThreadSafeKuzuAdapter: DB still locked (retry {attempt}/5): "
                    f"{self._db_path}"
                )
        return False

    def _recover_from_corrupt_wal(self, error: Exception) -> bool:
        """Quarantine a write-ahead log that ladybug failed to replay on open.

        Acts whenever an open fails AND a WAL file is present. The replay path trips
        several distinct ladybug failures -- the WAL-record assertion ("UNREACHABLE_CODE")
        and a binder bug ("Trying to create a vector with ANY type") among them -- so we
        no longer gate on the error text. This is safe because the WAL is checkpointed
        into the .db after every project (see finish_bulk_addition), so a leftover WAL
        only ever holds the current, uncommitted project's tail: dropping it loses
        nothing that was committed, and the project is simply re-indexed. Lock conflicts
        are handled separately (before this) so they never reach here. Returns True if a
        WAL file was moved aside, so the caller can retry opening the database.
        """
        # ladybug 0.16.1 keeps several sibling files that an unclean shutdown can leave
        # unreplayable: the WAL "<db>.wal", the checkpoint-WAL "<db>.wal.checkpoint", and
        # the shadow file "<db>.shadow". Quarantining only "<db>.wal" left the checkpoint
        # WAL behind, so the retry replayed *it* and still failed ("Corrupted wal file").
        # Move them all aside. (Older directory-style DBs keep "*.wal" inside the dir.)
        candidates: set = set()
        for suffix in (".wal", ".wal.checkpoint", ".shadow"):
            candidates.add(self._db_path + suffix)
        for pattern in (self._db_path + ".wal*", self._db_path + ".shadow*"):
            candidates.update(glob.glob(pattern))
        if os.path.isdir(self._db_path):
            candidates.update(glob.glob(os.path.join(self._db_path, "*.wal*")))
            candidates.update(glob.glob(os.path.join(self._db_path, "*.shadow*")))
        # Never re-quarantine our own already-quarantined files.
        wal_files = sorted(c for c in candidates if os.path.isfile(c) and not c.endswith(".corrupt"))

        moved = False
        for wal in wal_files:
            if os.path.isfile(wal):
                quarantine = wal + ".corrupt"
                try:
                    if os.path.exists(quarantine):
                        os.remove(quarantine)
                    os.rename(wal, quarantine)
                    logger.warning(
                        f"ThreadSafeKuzuAdapter: Quarantined unreplayable WAL {wal} -> "
                        f"{quarantine} (open failed with: {error})"
                    )
                    moved = True
                except OSError as oe:
                    logger.error(
                        f"ThreadSafeKuzuAdapter: Could not quarantine WAL {wal}: {oe}"
                    )
        return moved

    @property
    def connection(self) -> lbug.Connection:
        """Get thread-local connection.
        
        Returns:
            lbug.Connection: Thread-local database connection
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn
        
    def _create_connection(self) -> lbug.Connection:
        """Create a new thread-local connection.
        
        Returns:
            lbug.Connection: New database connection for current thread
        """
        thread_id = threading.get_ident()
        logger.info(f"ThreadSafeKuzuAdapter: Creating connection for thread {thread_id}")
        
        try:
            if self._db is None:
                raise DatabaseError("Database not initialized")
                
            conn = lbug.Connection(self._db)
            logger.info(f"ThreadSafeKuzuAdapter: Connection created for thread {thread_id}: {conn}")
            return conn
        except Exception as e:
            logger.error(f"ThreadSafeKuzuAdapter: Error creating connection for thread {thread_id}: {e}")
            raise DatabaseError(f"KuzuDB connection error: {e}") from e
            
    def _cleanup_stale_files(self):
        """Clean up stale lock and WAL files that might cause connection issues."""
        try:
            # Clean up lock files. ladybug single-file DBs keep the lock as a sibling
            # file ("<db>.lock"/"<db>.tmp"); directory-style DBs keep "*.lock" inside the
            # db directory. The original glob only handled the directory layout, so stale
            # sibling locks/temp files from a killed run were never removed.
            lock_files = glob.glob(os.path.join(self._db_path, "*.lock"), include_hidden=True)
            for sibling in (self._db_path + ".lock", self._db_path + ".tmp"):
                if os.path.isfile(sibling):
                    lock_files.append(sibling)
            if lock_files:
                logger.info(f"ThreadSafeKuzuAdapter: Found {len(lock_files)} stale lock files. Attempting removal.")
                for lock_file in lock_files:
                    try:
                        # Check if it's actually a file before removing
                        if os.path.isfile(lock_file):
                            os.remove(lock_file)
                            logger.info(f"ThreadSafeKuzuAdapter: Removed stale lock file: {lock_file}")
                        else:
                            logger.debug(f"ThreadSafeKuzuAdapter: Skipping non-file item: {lock_file}")
                    except OSError as e:
                        logger.warning(f"ThreadSafeKuzuAdapter: Could not remove lock file {lock_file}: {e}")
                        
            # Clean up WAL files
            wal_files = glob.glob(os.path.join(self._db_path, "*.wal"), include_hidden=True)
            if wal_files:
                logger.info(f"ThreadSafeKuzuAdapter: Found {len(wal_files)} stale WAL files. Attempting removal.")
                for wal_file in wal_files:
                    try:
                        # Check if it's actually a file before removing
                        if os.path.isfile(wal_file):
                            os.remove(wal_file)
                            logger.info(f"ThreadSafeKuzuAdapter: Removed stale WAL file: {wal_file}")
                        else:
                            logger.debug(f"ThreadSafeKuzuAdapter: Skipping non-file item: {wal_file}")
                    except OSError as e:
                        logger.warning(f"ThreadSafeKuzuAdapter: Could not remove WAL file {wal_file}: {e}")
                        
        except Exception as e:
            logger.warning(f"ThreadSafeKuzuAdapter: Error cleaning up stale files: {e}")

    def commit(self) -> None:
        """Commit the current transaction to persist changes."""
        if self.connection:
            # In Kuzu, the connection itself handles the persistence
            # For now, we'll add a logging statement to track commits
            logger.info(f"ThreadSafeKuzuAdapter: commit() called for {self._db_path} in thread ID: {threading.get_ident()}")
        else:
            logger.warning(f"ThreadSafeKuzuAdapter: commit() called but no connection available for {self._db_path}")

    def checkpoint(self) -> None:
        """Force a WAL checkpoint so committed graph data is flushed into the main DB
        file. Without this the write-ahead log grows across a project's writes and is
        replayed by the next short-lived process when it opens the DB -- that replay
        path occasionally trips a ladybug binder bug ('Trying to create a vector with
        ANY type'), which then fails every subsequent open. Checkpointing between
        projects keeps the WAL near-empty and the .db self-contained, so there is
        nothing to replay (and a kill loses at most the current, uncommitted project)."""
        with self._db_lock:
            if self._db is None:
                return
        try:
            self.connection.execute("CHECKPOINT")
            logger.info(f"ThreadSafeKuzuAdapter: CHECKPOINT completed for {self._db_path}")
        except Exception as e:
            logger.warning(f"ThreadSafeKuzuAdapter: CHECKPOINT failed for {self._db_path}: {e}")

    def _maybe_checkpoint(self) -> None:
        """Checkpoint when the WAL has grown past the configured threshold.

        Called after each committed write (object/relation). Statting the WAL on every
        single write would be wasteful, so we only check every ``_ckpt_stat_interval``
        writes; between checks the WAL can overshoot by at most that many writes, which is
        far below the ~10 MB assertion threshold. Keeps the WAL small so a process killed
        mid-run loses almost nothing and ladybug never reaches the WAL-record assertion."""
        if self._ckpt_wal_bytes <= 0:
            return
        self._writes_since_ckpt += 1
        if self._writes_since_ckpt < self._ckpt_stat_interval:
            return
        self._writes_since_ckpt = 0
        wal = self._db_path + ".wal"
        try:
            size = os.path.getsize(wal) if os.path.isfile(wal) else 0
        except OSError:
            size = 0
        if size >= self._ckpt_wal_bytes:
            logger.warning("PINPOINT about-to-CHECKPOINT wal=%d bytes", size)
            self.checkpoint()
            logger.warning("PINPOINT checkpoint-done")

    def _resolve_node_table(self, node_id: Any, candidate_types: list[str]) -> Optional[str]:
        """Return the node table that actually holds ``node_id``, among ``candidate_types``.

        A relation's endpoints can be any of the relation type's declared source/target
        types, not just the first. We find the real table with a PK-indexed probe per
        candidate (fast, stops at the first hit) and cache the answer so each id is resolved
        at most once. Returns None if the id is in none of the candidates (e.g. the endpoint
        was never indexed), in which case the caller keeps its previous fallback behaviour."""
        key = str(node_id)
        cached = self._node_table_cache.get(key)
        if cached is not None:
            return cached
        for tbl in candidate_types:
            try:
                r = self.connection.execute(
                    f"MATCH (n:{tbl} {{id: $id}}) RETURN 1 LIMIT 1",
                    parameters={"id": node_id},
                )
                if isinstance(r, list):
                    r = r[0] if r else None
                if r is not None and r.has_next():
                    self._node_table_cache[key] = tbl
                    return tbl
            except Exception:
                continue
        return None

    def close(self) -> None:
        """Close thread-local connection."""
        thread_id = threading.get_ident()
        logger.info(f"ThreadSafeKuzuAdapter: close() called in thread ID: {thread_id} for db_path: {self._db_path}")
        
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                # Kuzu connections are cleaned up by garbage collector
                # but we can explicitly dereference
                self._local.conn = None
                logger.info(f"ThreadSafeKuzuAdapter: Connection closed for thread {thread_id}")
            except Exception as e:
                logger.error(f"ThreadSafeKuzuAdapter: Error closing connection for thread {thread_id}: {e}")
        else:
            logger.debug(f"ThreadSafeKuzuAdapter: No connection to close for thread {thread_id}")

    def close_all(self) -> None:
        """Close all connections and database."""
        logger.info(f"ThreadSafeKuzuAdapter: close_all() called for db_path: {self._db_path}")
        
        with self._db_lock:
            if self._db is not None:
                try:
                    self._db = None
                    logger.info(f"ThreadSafeKuzuAdapter: Closed shared database instance for {self._db_path}")
                except Exception as e:
                    logger.error(f"ThreadSafeKuzuAdapter: Error closing database: {e}")

    # No column name workarounds needed — ladybug >= 0.16.1 handles
    # underscore names and Cypher keywords correctly.

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
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        try:
            existing_node_tables = self.list_object_types()
            if otd.name in existing_node_tables:
                logger.debug(f"ThreadSafeKuzuAdapter: Node table '{otd.name}' already exists. Skipping creation.")
                return
        except DatabaseError as e:
            logger.warning(f"ThreadSafeKuzuAdapter: Could not list existing node tables before creating '{otd.name}': {e}. Will attempt creation.")
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
                lbug_type = self._map_grizabella_to_kuzu_type(prop.data_type)
                lbug_col = prop.name
                properties_str_parts.append(f"{lbug_col} {lbug_type}")

            properties_str = ", ".join(properties_str_parts)
            query = f"CREATE NODE TABLE {otd.name} ({properties_str})"
            self.connection.execute(query)
            # Commit the transaction to persist changes
            self.commit()
            logger.info(f"ThreadSafeKuzuAdapter: Created node table '{otd.name}'")
        except Exception as e:
            msg = f"KuzuDB error creating node table '{otd.name}': {e}"
            raise SchemaError(
                msg,
            ) from e

    def drop_node_table(self, object_type_name: str) -> None:
        """Drops a Kuzu node table."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        try:
            query = f"DROP TABLE {object_type_name}"
            self.connection.execute(query)
            # Commit the transaction to persist changes
            self.commit()
            logger.info(f"ThreadSafeKuzuAdapter: Dropped node table '{object_type_name}'")
        except Exception as e:
            msg = f"KuzuDB error dropping node table '{object_type_name}': {e}"
            raise SchemaError(
                msg,
            ) from e

    # --- Relationship Table Management ---
    def create_rel_table(self, rtd: RelationTypeDefinitionModel) -> None:
        """Creates a Kuzu relationship table based on a RelationTypeDefinition if it doesn't already exist."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        try:
            existing_rel_tables = self.list_relation_types() # New method to be added
            if rtd.name in existing_rel_tables:
                logger.debug(f"ThreadSafeKuzuAdapter: Relation table '{rtd.name}' already exists. Skipping creation.")
                return
        except DatabaseError as e:
            logger.warning(f"ThreadSafeKuzuAdapter: Could not list existing relation tables before creating '{rtd.name}': {e}. Will attempt creation.")
            # Proceed to attempt creation if listing fails

        try:
            main_properties = "id UUID, weight DOUBLE, upsert_date TIMESTAMP"
            additional_properties_list = []
            for prop in rtd.properties:
                if prop.name.lower() not in ["id", "weight", "upsert_date"]:
                    lbug_type = self._map_grizabella_to_kuzu_type(prop.data_type)
                    lcol = prop.name
                    additional_properties_list.append(f"{lcol} {lbug_type}")
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

            # A relation type can legitimately connect several (source, target) type pairs
            # (e.g. CONTAINS links JavaClass->JavaMethod, JavaClass->JavaField, Xml->Xml, ...).
            # ladybug/Kuzu rel tables accept multiple FROM..TO pairs, so declare the full
            # cross product of the declared source x target types. Previously only the first
            # pair ([0]->[0]) was created, so every edge whose endpoints were any other pair
            # was silently dropped (~half of all edges). De-duplicate pairs to stay valid.
            seen_pairs: set = set()
            pair_clauses = []
            for s in rtd.source_object_type_names:
                for t in rtd.target_object_type_names:
                    if (s, t) in seen_pairs:
                        continue
                    seen_pairs.add((s, t))
                    pair_clauses.append(f"FROM {s} TO {t}")
            from_to_pairs = ", ".join(pair_clauses)

            query = (
                f"CREATE REL TABLE {rtd.name} ("
                f"{from_to_pairs}, {properties_str})"
            )
            self.connection.execute(query)
            # Commit the transaction to persist changes
            self.commit()
            logger.info(f"ThreadSafeKuzuAdapter: Created relation table '{rtd.name}'")
        except Exception as e:
            msg = f"KuzuDB error creating relationship table '{rtd.name}': {e}"
            raise SchemaError(
                msg,
            ) from e

    def drop_rel_table(self, relation_type_name: str) -> None:
        """Drops a Kuzu relationship table."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        try:
            query = f"DROP TABLE {relation_type_name}"
            self.connection.execute(query)
            # Commit the transaction to persist changes
            self.commit()
            logger.info(f"ThreadSafeKuzuAdapter: Dropped relation table '{relation_type_name}'")
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
        return None

    def update_object_type(self, definition: ObjectTypeDefinitionModel) -> None:
        """Not yet implemented for Kuzu."""
        msg = "ThreadSafeKuzuAdapter.update_object_type not yet implemented for Kuzu."
        raise NotImplementedError(
            msg,
        )

    def list_object_types(self) -> list[str]:
        """Lists all NODE table names from Kuzu."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        try:
            # Updated to include RETURN * as per Kuzu documentation for CALL
            raw_query_result = self.connection.execute("CALL SHOW_TABLES() RETURN *;")
            node_tables = []

            # conn.execute might return a list if multiple statements were run,
            # but for a single CALL, it should be a single QueryResult.
            # Handle both cases to satisfy Pylance and be robust.
            actual_query_result: Optional[lbug.query_result.QueryResult] = None
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
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)
        try:
            raw_query_result = self.connection.execute("CALL SHOW_TABLES() RETURN *;")
            rel_tables = []
            actual_query_result: Optional[lbug.query_result.QueryResult] = None
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
        return None

    # --- Object Instance Management (Nodes) ---
    def upsert_object_instance(self, instance: ObjectInstance) -> ObjectInstance:  # type: ignore[override]
        """Upserts a node using CREATE+MATCH/SET (avoids real_ladybug MERGE bugs)."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        table_name = instance.object_type_name

        # PINPOINT (diagnostic): log every object right before the ladybug write so the LAST
        # line in the log before a segfault identifies the crashing object. logging flushes
        # per-record, so this survives a hard native crash.
        try:
            _ps = {k: len(str(v)) for k, v in instance.properties.items()}
            _bg = max(_ps.items(), key=lambda kv: kv[1]) if _ps else ("", 0)
            logger.warning(
                "PINPOINT upsert_obj id=%s type=%s name=%r file=%r big=%s(%d) total=%d",
                instance.id, table_name, instance.properties.get("name"),
                instance.properties.get("file_path"), _bg[0], _bg[1], sum(_ps.values()),
            )
        except Exception:
            pass

        # Explicitly type params_for_query and props_for_set
        params_for_query: dict[str, Any] = {
            "id_param": instance.id, # Pass UUID object directly
        }

        # Build SET clause and populate params_for_query with correctly typed values
        set_clause_parts = []

        # For real_ladybug: Don't set the id property in SET clauses (it's a primary key)
        # The id is only used for matching in the MERGE clause
        params_for_query["id_param"] = instance.id

        # ALL columns must be included in SET to avoid real_ladybug binding bugs.
        # Column names are mapped to short aliases (k0, k1, ...) to work around
        # a parser bug with multi-word / underscore column names.
        for key, original_value in instance.properties.items():
            if key.lower() == "id":
                continue

            kcol = key
            set_clause_parts.append(f"n.{kcol} = ${kcol}")

            if original_value is None:
                params_for_query[kcol] = ""
            elif isinstance(original_value, UUID):
                params_for_query[kcol] = original_value
            elif isinstance(original_value, datetime):
                params_for_query[kcol] = original_value
            elif isinstance(original_value, str):
                try:
                    dt_value = datetime.fromisoformat(original_value)
                    params_for_query[kcol] = dt_value
                except (ValueError, TypeError):
                    params_for_query[kcol] = original_value
            else:
                params_for_query[kcol] = original_value

        if not set_clause_parts:
            msg = f"KuzuDB: No properties to set for object instance {instance.id} in {table_name}."
            raise InstanceError(msg)

        set_clause_str_on_create = ", ".join(set_clause_parts)

        # ON MATCH uses the same columns as ON CREATE
        set_clause_parts_on_match_list = []
        for key, original_value in instance.properties.items():
            if key.lower() == "id":
                continue
            kcol = key
            set_clause_parts_on_match_list.append(f"n.{kcol} = ${kcol}")

        on_match_cypher_clause = ""
        if set_clause_parts_on_match_list:
            set_clause_str_on_match = ", ".join(set_clause_parts_on_match_list)
            on_match_cypher_clause = f"ON MATCH SET {set_clause_str_on_match}"

        set_clause_str_on_create = ", ".join(set_clause_parts)

        query = f"""
            MERGE (n:{table_name} {{id: $id_param}})
            ON CREATE SET {set_clause_str_on_create}
            {on_match_cypher_clause}
            RETURN n.id
        """

        try:
            raw_query_result = self.connection.execute(query, parameters=params_for_query)

            actual_query_result = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if actual_query_result and actual_query_result.has_next():
                actual_query_result.get_next()

            self.commit()
            # Remember which table this id lives in so relation upserts can pick the right
            # (source, target) pair without a probe query.
            self._node_table_cache[str(instance.id)] = table_name
            self._maybe_checkpoint()
            return instance

        except Exception as e:
            msg = (
                f"KuzuDB error upserting object instance {instance.id} "
                f"into '{table_name}': {e}"
            )
            raise InstanceError(msg) from e

    # Add other required methods from the original KuzuAdapter...
    # For brevity, I'm including the most critical ones. The rest would follow the same pattern.
    
    def get_object_instance(self, object_type_name: str, instance_id: UUID) -> Optional[ObjectInstance]:
        """Retrieves a node by its ID from Kuzu and reconstructs an ObjectInstance."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        try:
            query = f"MATCH (n:{object_type_name} {{id: $id_param}}) RETURN n.*"
            params = {"id_param": instance_id}
            
            raw_query_result = self.connection.execute(query, parameters=params)
            
            actual_query_result: Optional[lbug.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result or not actual_query_result.has_next():
                return None

            row = actual_query_result.get_next()
            column_names = actual_query_result.get_column_names()
            
            # Reconstruct the object instance, reversing column name mapping
            properties = {}
            for i, value in enumerate(row):
                raw_col = column_names[i]
                prop_name = raw_col
                if prop_name != 'id':
                    properties[prop_name] = value

            return ObjectInstance(
                id=instance_id,
                object_type_name=object_type_name,
                properties=properties
            )

        except Exception as e:
            msg = f"KuzuDB error getting object instance {instance_id} from '{object_type_name}': {e}"
            raise InstanceError(msg) from e

    def delete_object_instance(self, object_type_name: str, instance_id: UUID) -> bool:
        """Deletes a node by its ID from Kuzu. Uses DETACH DELETE."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        try:
            query = f"MATCH (n:{object_type_name} {{id: $id_param}}) DETACH DELETE n"
            params = {"id_param": instance_id}  # Pass UUID object directly
            
            self.connection.execute(query, parameters=params)
            # Commit the transaction to persist changes
            self.commit()
            logger.info(f"ThreadSafeKuzuAdapter: Deleted object instance {instance_id} from {object_type_name}")
            return True

        except Exception as e:
            msg = f"KuzuDB error deleting object instance {instance_id} from '{object_type_name}': {e}"
            raise InstanceError(msg) from e

    # Placeholder methods for other required functionality
    # These would be implemented following the same pattern as above
    def find_object_instances(
        self,
        object_type_name: str,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[ObjectInstance]:
        """Find object instances - placeholder implementation."""
        return []

    def get_all_object_ids_for_type(self, object_type_name: str) -> list[UUID]:
        """Get all object IDs for type - placeholder implementation."""
        return []

    def upsert_embedding_instance(self, instance: EmbeddingInstance) -> EmbeddingInstance:
        """Upsert embedding instance - placeholder implementation."""
        return instance

    def get_embedding_instance(
        self, embedding_definition_name: str, object_instance_id: UUID,
    ) -> Optional[EmbeddingInstance]:
        """Get embedding instance - placeholder implementation."""
        return None

    def find_similar_embeddings(
        self,
        embedding_definition_name: str,
        vector: list[float],
        top_k: int = 5,
    ) -> list[EmbeddingInstance]:
        """Find similar embeddings - placeholder implementation."""
        return []

    def upsert_relation_instance(  # type: ignore # pylint: disable=arguments-differ
        self,
        instance: RelationInstance,
        rtd: Optional[RelationTypeDefinitionModel] = None,
    ) -> RelationInstance:
        """Upserts a relationship in Kuzu between the source_object_instance_id and
        target_object_instance_id in the table corresponding to instance.relation_type_name.
        Requires RelationTypeDefinition to know source/target node table names.
        """
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        logger.debug(
            f"ThreadSafeKuzuAdapter.upsert_relation_instance called with instance: {instance.id=}, "
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
            msg = f"ThreadSafeKuzuAdapter.upsert_relation_instance requires 'rtd' (RelationTypeDefinition) for relation type '{rel_table_name}'."
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

        # Resolve the endpoints' real node tables (a relation type can span several type
        # pairs; the rel table now holds them all). Fall back to the first declared type if
        # an endpoint can't be found -- the MERGE then simply matches nothing, as before.
        src_node_table = (
            self._resolve_node_table(instance.source_object_instance_id, rtd.source_object_type_names)
            or rtd.source_object_type_names[0]
        )
        tgt_node_table = (
            self._resolve_node_table(instance.target_object_instance_id, rtd.target_object_type_names)
            or rtd.target_object_type_names[0]
        )
        logger.warning(
            "PINPOINT upsert_rel id=%s type=%s %s->%s",
            instance.id, rel_table_name, src_node_table, tgt_node_table,
        )

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

        # Build SET clause - ONLY include user-defined properties, NOT built-in Kuzu properties
        set_clause_parts = []
        
        # Only set user-defined properties from the relation type definition
        # Exclude built-in Kuzu properties: id, weight, upsert_date (these are managed automatically)
        for prop in rtd.properties:
            if prop.name.lower() in ["id", "weight", "upsert_date"]:
                # Skip built-in Kuzu properties - they are automatically managed
                continue
                
            if prop.name in instance.properties:
                kcol = prop.name
                set_clause_parts.append(f"r.{kcol} = ${kcol}")

                original_value = instance.properties[prop.name]
                if isinstance(original_value, UUID):
                    params_for_query[kcol] = original_value
                elif isinstance(original_value, datetime):
                    params_for_query[kcol] = original_value
                elif isinstance(original_value, str):
                    try:
                        dt_value = datetime.fromisoformat(original_value)
                        params_for_query[kcol] = dt_value
                    except (ValueError, TypeError):
                        params_for_query[kcol] = original_value
                else:
                    params_for_query[kcol] = original_value

        # If there are no user-defined properties to set, we still need to create the relationship
        # Kuzu will handle the built-in properties (id, weight, upsert_date) automatically
        if set_clause_parts:
            set_clause_str = ", ".join(set_clause_parts)
        else:
            # No user properties to set, but we need a SET clause for the MERGE to work
            # Use a dummy SET to trigger the MERGE operation
            set_clause_str = "r.weight = r.weight"  # No-op SET clause

        # MERGE (not CREATE) on the relationship id so this is a true upsert: re-writing a
        # relation with the same deterministic id (e.g. the same edge re-derived in a later
        # run/process) matches the existing edge instead of appending a duplicate. With CREATE
        # the graph tier accumulated ~2x duplicate edges across runs even though the id was
        # set, because the id was never used to match. The id lives in the MERGE pattern, so
        # it must not also appear in SET (Kuzu rejects setting a merge-key); SET carries only
        # the user-defined properties (set_clause_str, a no-op when there are none).
        query = f"""
            MATCH (src:{src_node_table} {{id: $src_id_param}}), (tgt:{tgt_node_table} {{id: $tgt_id_param}})
            MERGE (src)-[r:{rel_table_name} {{id: $rel_id_param}}]->(tgt)
            SET {set_clause_str}
            RETURN r.id
        """
        logger.debug(f"Kuzu upsert_relation_instance query: {query}")
        logger.debug(f"Kuzu upsert_relation_instance params_for_query: { {k: (v, type(v)) for k,v in params_for_query.items()} }")

        try:
            raw_query_result = self.connection.execute(query, parameters=params_for_query)

            actual_query_result: Optional[lbug.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            # Debug: Let's see what we actually got
            # For CREATE operations, the ID might not be returned in the result
            # but we set it explicitly, so just return the ID we set
            if not actual_query_result:
                logger.warning(f"Kuzu upsert_relation_instance: No query result returned, but ID was set explicitly")
                # Don't treat this as an error for CREATE operations
                return instance.id
            elif not actual_query_result.has_next():
                logger.warning(f"Kuzu upsert_relation_instance: Query result has no next, but ID was set explicitly")
                # Don't treat this as an error for CREATE operations  
                return instance.id

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

            # Commit the transaction to persist changes
            self.commit()
            self._maybe_checkpoint()

            return instance

        except Exception as e:
            msg = (
                f"KuzuDB error upserting relation instance {instance.id} "
                f"into '{rel_table_name}': {e}"
            )
            raise InstanceError(
                msg,
            ) from e

    def get_relation_instance(
        self, relation_type_name: str, relation_id: UUID,
    ) -> Optional[RelationInstance]:
        """Retrieves a relationship by its ID and reconstructs a RelationInstance."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        query = f"MATCH (src)-[r:{relation_type_name} {{id: $rel_id_param}}]->(tgt) RETURN r, src.id AS src_node_id, tgt.id AS tgt_node_id"
        params = {"rel_id_param": relation_id}  # Pass UUID object

        try:
            raw_query_result = self.connection.execute(query, parameters=params)

            actual_query_result: Optional[lbug.query_result.QueryResult] = None
            if isinstance(raw_query_result, list):
                if raw_query_result:
                    actual_query_result = raw_query_result[0]
            else:
                actual_query_result = raw_query_result

            if not actual_query_result or not actual_query_result.has_next():
                return None

            row = actual_query_result.get_next()
            rel_data_from_kuzu = row[0]  # Relationship properties as a dict
            src_id_str = row[1]
            tgt_id_str = row[2]

            if not rel_data_from_kuzu or "id" not in rel_data_from_kuzu:
                return None

            rel_id_val = rel_data_from_kuzu.get("id")
            rel_id_obj: Optional[UUID] = None
            if isinstance(rel_id_val, UUID):
                rel_id_obj = rel_id_val
            elif isinstance(rel_id_val, str):
                rel_id_obj = UUID(rel_id_val)
            elif hasattr(rel_id_val, "value"):  # kuzu.UUID like
                rel_id_obj = UUID(str(rel_id_val.value))  # type: ignore
            else:
                return None

            reconstructed_args: dict[str, Any] = {  # Ensure type for Pydantic model
                "id": rel_id_obj,
                "relation_type_name": relation_type_name,
                "source_object_instance_id": src_id_str if isinstance(src_id_str, UUID) else UUID(src_id_str),
                "target_object_instance_id": tgt_id_str if isinstance(tgt_id_str, UUID) else UUID(tgt_id_str),
                "properties": {},
            }

            if "weight" in rel_data_from_kuzu:
                reconstructed_args["weight"] = rel_data_from_kuzu["weight"]
            if "upsert_date" in rel_data_from_kuzu:
                reconstructed_args["upsert_date"] = rel_data_from_kuzu["upsert_date"]

            temp_properties = {}
            internal_kuzu_fields = {"id", "weight", "upsert_date", "_src", "_dst", "_label", "_id"}
            for key, value in rel_data_from_kuzu.items():
                if key not in internal_kuzu_fields:
                    if hasattr(value, "value") and isinstance(value.value, (str, bytes)):  # kuzu.UUID like
                        try:
                            temp_properties[key] = UUID(str(value.value))  # type: ignore
                        except (ValueError):  # If not a valid UUID string, store as is
                            temp_properties[key] = str(value.value)  # type: ignore
                    elif isinstance(value, UUID):  # Already a Python UUID
                        temp_properties[key] = value
                    else:
                        temp_properties[key] = value
            reconstructed_args["properties"] = temp_properties

            return RelationInstance(**reconstructed_args)

        except Exception as e:
            msg = f"KuzuDB error getting relation instance {relation_id} from '{relation_type_name}': {e}"
            raise InstanceError(msg) from e

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
        if not self.connection:
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
            raw_query_result = self.connection.execute(final_query, parameters=params)

            actual_query_result: Optional[lbug.query_result.QueryResult] = None
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

                # Always set weight and upsert_date - if not in database, use defaults from MemoryInstance
                # This ensures the RelationInstance constructor gets all required fields
                from decimal import Decimal
                from datetime import datetime, timezone
                
                if "weight" in rel_data_from_kuzu and rel_data_from_kuzu["weight"] is not None:
                    reconstructed_args["weight"] = rel_data_from_kuzu["weight"]
                else:
                    reconstructed_args["weight"] = Decimal("1.0")  # Default from MemoryInstance
                    
                if "upsert_date" in rel_data_from_kuzu and rel_data_from_kuzu["upsert_date"] is not None:
                    reconstructed_args["upsert_date"] = rel_data_from_kuzu["upsert_date"]
                else:
                    reconstructed_args["upsert_date"] = datetime.now(timezone.utc)  # Default from MemoryInstance

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

    def delete_relation_instance(self, relation_type_name: str, relation_id: UUID) -> bool:
        """Deletes a relationship by its ID from Kuzu."""
        if not self.connection:
            msg = "KuzuDB not connected"
            raise DatabaseError(msg)

        query = f"MATCH ()-[r:{relation_type_name} {{id: $rel_id_param}}]->() DELETE r"
        params = {"rel_id_param": relation_id}  # Pass UUID object directly to match Kuzu expectation

        try:
            self.connection.execute(query, parameters=params)
            # Commit the transaction to persist changes
            self.commit()
            logger.info(f"ThreadSafeKuzuAdapter: Deleted relation instance {relation_id} from {relation_type_name}")
            return True
        except Exception as e:
            logger.error(f"ThreadSafeKuzuAdapter: Error deleting relation instance {relation_id} from {relation_type_name}: {e}", exc_info=True)
            # Kuzu might raise an exception if the relation doesn't exist
            # For consistency with the interface, we return False if there's an error
            return False

    def filter_object_ids_by_relations(
        self,
        source_object_type_name: str,
        object_ids: list[UUID],
        traversals: list[GraphTraversalClause],
    ) -> list[UUID]:
        """Filters a list of object IDs, returning only those that satisfy all specified graph traversals."""
        if not self.connection:
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
                    raw_query_result = self.connection.execute(query_str, parameters=params)

                    actual_query_result: Optional[lbug.query_result.QueryResult] = None
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