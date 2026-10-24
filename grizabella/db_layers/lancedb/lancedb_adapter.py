"""Grizabella adapter for LanceDB, handling vector embeddings."""

import logging  # Added import
import math
import os
import re
import threading  # For logging and synchronization
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from pydantic import BaseModel  # For fallback schema

# Remove direct SentenceTransformer import, will be handled by LanceDB registry
# from sentence_transformers import SentenceTransformer
from grizabella.core.exceptions import DatabaseError, EmbeddingError, SchemaError

# Application-specific imports
from grizabella.core.models import (
    EmbeddingDefinition,
    EmbeddingInstance,
    ObjectInstance,  # For TYPE_CHECKING
    ObjectTypeDefinition,  # For TYPE_CHECKING
    RelationInstance,  # For TYPE_CHECKING
    RelationTypeDefinition,  # For TYPE_CHECKING
)
from grizabella.db_layers.common.base_adapter import BaseDBAdapter

# Conditional imports for LanceDB
_LANCEDB_MODULE = None
LanceModelClass = None  # pylint: disable=C0103
_VECTOR_CLASS = None
LANCEDB_AVAILABLE = False

try:
    import lancedb as _lancedb_actual  # Third-party, but conditional
    from lancedb.embeddings import get_registry as _get_registry_actual
    from lancedb.pydantic import LanceModel as _LanceModel_actual
    from lancedb.pydantic import Vector as _Vector_actual
    _LANCEDB_MODULE = _lancedb_actual
    LanceModelClass = _LanceModel_actual # Renamed to conform to PascalCase
    _VECTOR_CLASS = _Vector_actual
    LANCEDB_EMBEDDING_REGISTRY = _get_registry_actual() # Call the function to get the registry object
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_EMBEDDING_REGISTRY = None # Define it as None if import fails

# --- Table maintenance ---
# Each write used to append a one-row fragment plus a manifest listing every
# fragment, and nothing compacted. A knowledge base of 6k vectors reached 5,973
# fragments and 8,936 manifests (3.0 GB of manifests for 25 MB of vectors): a
# search scanned every fragment (184 ms; 5 ms once compacted), and Lance's own
# auto-cleanup, which runs every 20 commits, read every manifest, stalling
# about one upsert in ten for 30 s. Tables are now compacted after
# COMPACT_AFTER_WRITES writes, or by a background pass once writes have been
# quiet for MAINTENANCE_IDLE_S, and versions older than CLEANUP_OLDER_THAN_S
# are removed. Compacting that table takes 50 ms but rewrites all 25 MB, which
# stays on disk until the cleanup; a few dozen small fragments cost a search
# about 2 ms. Hence a long quiet period and a short retention.
DEFAULT_COMPACT_AFTER_WRITES = 64
DEFAULT_MAINTENANCE_INTERVAL_S = 60.0  # 0 disables the background pass
DEFAULT_MAINTENANCE_IDLE_S = 300.0
DEFAULT_CLEANUP_OLDER_THAN_S = 600.0

# On that table, compacted (5,983 rows of 1024 dims), a flat scan took 3 ms and
# is exact. IVF_FLAT took 1.6 ms but lost 3% of the top 52 (8% of the top 208)
# at the default probes; IVF_HNSW_SQ lost 21%. Lance itself asks for ~256 rows
# per partition. So the index waits until a flat scan costs something.
DEFAULT_INDEX_MIN_ROWS = 50_000
MIN_ROWS_PER_PARTITION = 256
# IVF_FLAT keeps the distances exact, and in the metric unindexed searches
# have always used (squared L2): callers calibrate relevance on those numbers.
VECTOR_INDEX_TYPE = "IVF_FLAT"
VECTOR_INDEX_METRIC = "l2"
VECTOR_INDEX_PREFIX = "vector_ivf_flat_p"  # + the partition count it was trained with
MIN_NPROBES = 20
# Every optimize() adds a delta segment to the index, even with no new rows,
# and a search reads each one. Past this many, the index is rebuilt.
MAX_INDEX_SEGMENTS = 8

_SETTING_ENV_PREFIX = "GRIZABELLA_LANCEDB_"

if TYPE_CHECKING:
    import lancedb  # For type hints only
    # Core models for type hints are now imported above directly

logger = logging.getLogger(__name__) # Added logger

# Schema definition using runtime check
if LANCEDB_AVAILABLE and LanceModelClass is not None:
    class LanceDBEmbeddingSchema(LanceModelClass): # type: ignore # pylint: disable=R0903
        """Pydantic model for LanceDB table schema for embeddings."""

        object_instance_id: str
        # vector will be added dynamically in create_embedding_table using _Vector_class
        source_text_preview: Optional[str] = None
else:
    # Fallback if lancedb is not installed
    class LanceDBEmbeddingSchema(BaseModel): # type: ignore # pylint: disable=R0903
        """Fallback Pydantic model if LanceDB is not installed."""

        object_instance_id: str
        vector: list[float]
        source_text_preview: Optional[str] = None


class LanceDBAdapter(BaseDBAdapter): # pylint: disable=R0904
    """Grizabella adapter for LanceDB.
    Handles vector embeddings storage and similarity search.
    """

    if TYPE_CHECKING:
        db: Optional[lancedb.DBConnection]
    else:
        db: Optional[Any] # Runtime can be Any if lancedb is not available

    def __init__(self, db_uri: str, config: Optional[dict[str, Any]] = None, use_gpu: bool = False) -> None:
        """Initializes the LanceDB adapter.

        ``config`` may set ``compact_after_writes``, ``maintenance_interval_s``,
        ``maintenance_idle_s``, ``cleanup_older_than_s`` and ``index_min_rows``;
        each can also come from ``GRIZABELLA_LANCEDB_<NAME>`` in the environment.
        """
        self.db = None # Initialize db attribute
        self._model_lock = threading.Lock()  # Lock for model loading
        self._model_cache: dict[str, Any] = {}
        self._use_gpu = use_gpu
        # Writes, maintenance and searches on tables. Searches take it too: a
        # cleanup may delete the files of the version a concurrent search reads.
        self._table_lock = threading.RLock()
        self._pending_writes: dict[str, int] = {}
        self._last_write_at = 0.0
        self._index_partitions: dict[str, int] = {}
        self._stop_maintenance = threading.Event()
        self._maintenance_thread: Optional[threading.Thread] = None
        settings = config or {}
        self.compact_after_writes = int(self._setting(settings, "compact_after_writes", DEFAULT_COMPACT_AFTER_WRITES))
        self.maintenance_interval_s = float(self._setting(settings, "maintenance_interval_s", DEFAULT_MAINTENANCE_INTERVAL_S))
        self.maintenance_idle_s = float(self._setting(settings, "maintenance_idle_s", DEFAULT_MAINTENANCE_IDLE_S))
        self.cleanup_older_than_s = float(self._setting(settings, "cleanup_older_than_s", DEFAULT_CLEANUP_OLDER_THAN_S))
        self.index_min_rows = int(self._setting(settings, "index_min_rows", DEFAULT_INDEX_MIN_ROWS))
        super().__init__(db_path=db_uri, config=config)
        self._start_maintenance_thread()

    @staticmethod
    def _setting(config: dict[str, Any], name: str, default: Any) -> Any:
        if config.get(name) is not None:
            return config[name]
        return os.environ.get(_SETTING_ENV_PREFIX + name.upper(), default)

    def _connect(self) -> None:
        """Establish a connection to the LanceDB database."""
        if not LANCEDB_AVAILABLE or not _LANCEDB_MODULE:
            return
        try:
            path_exists = os.path.exists(self.db_path)
            os.path.isdir(self.db_path) if path_exists else False

            connection_attempt = _LANCEDB_MODULE.connect(self.db_path)

            if connection_attempt is None:
                error_msg = f"LanceDB connect() returned None for URI {self.db_path}."
                self.db = None
                raise ConnectionError(error_msg)
            self.db = connection_attempt
        except Exception as e: # pylint: disable=W0718
            self.db = None
            error_msg = f"Failed to connect to LanceDB at {self.db_path}: {e!r}"
            raise ConnectionError(error_msg) from e

    def close(self) -> None:
        """Close the LanceDB database connection (if applicable)."""
        logger.info(f"LanceDBAdapter: close() called in thread ID: {threading.get_ident()} for db_uri: {self.db_path}. DB object state: {'Exists' if self.db else 'None'}")
        self._stop_maintenance.set()
        thread = self._maintenance_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=30)
        self._maintenance_thread = None
        if self.db:
            # LanceDB connection objects don't have an explicit close() method in the same way
            # as traditional DB drivers. Setting to None helps with garbage collection and
            # signals that the connection is no longer in use by this adapter instance.
            self.db = None
            logger.info(f"LanceDBAdapter: self.db set to None for {self.db_path}.")
        else:
            logger.info(f"LanceDBAdapter: No active DB object to close for {self.db_path}.")

    def _sanitize_table_name(self, name: str) -> str:
        """Sanitizes a string to be a valid LanceDB table name."""
        return re.sub(r"[^0-9a-zA-Z_.-]", "_", name)

    def create_embedding_table(self, ed: EmbeddingDefinition) -> None:
        """Creates a new LanceDB table for the given EmbeddingDefinition."""
        if self.db is None:
            msg = "LanceDB not connected. Cannot create table."
            raise DatabaseError(msg)
        if not LANCEDB_AVAILABLE or not LanceModelClass or not _VECTOR_CLASS:
            msg = (
                "LanceDB runtime components not available. "
                                "Cannot create table schema."
            )
            raise DatabaseError(msg)

        table_name = self._sanitize_table_name(ed.name)

        if table_name in self.db.list_tables().tables:
            return

        try:
            if ed.dimensions is None or ed.dimensions <= 0:
                msg = f"LanceDB: ED '{ed.name}' must have 'dimensions' > 0. Got: {ed.dimensions}"
                raise SchemaError(
                    msg,
                )

            class DynamicSchema(LanceModelClass): # type: ignore # pylint: disable=R0903
                """Dynamically created schema for LanceDB table."""

                object_instance_id: str
                vector: _VECTOR_CLASS(ed.dimensions) # type: ignore
                source_text_preview: Optional[str] = None

            with self._table_lock:
                self.db.create_table(table_name, schema=DynamicSchema, mode="create")
                self._pending_writes.pop(table_name, None)
                self._index_partitions.pop(table_name, None)
            logger.info(f"LanceDB: Table '{table_name}' created.")

        except Exception as e: # pylint: disable=W0718
            msg = (
                f"LanceDB: Error creating table '{table_name}' for "
                              f"'{ed.name}': {e}"
            )
            raise SchemaError(msg) from e

    def drop_embedding_table(self, embedding_definition_name: str) -> None:
        """Drops the LanceDB table associated with the EmbeddingDefinition."""
        if self.db is None:
            msg = "LanceDB not connected. Cannot drop table."
            raise DatabaseError(msg)

        table_name = self._sanitize_table_name(embedding_definition_name)
        try:
            if table_name not in self.db.list_tables().tables:
                return

            with self._table_lock:
                self.db.drop_table(table_name)
                self._pending_writes.pop(table_name, None)
                self._index_partitions.pop(table_name, None)
        except Exception as e: # pylint: disable=W0718
            msg = f"LanceDB: Error dropping table '{table_name}': {e}"
            raise DatabaseError(msg) from e

    def list_embedding_tables(self) -> list[str]:
        """Returns a list of existing LanceDB table names."""
        if self.db is None:
            return []
        try:
            return list(self.db.list_tables().tables) # Ensure a List is returned
        except Exception as e: # pylint: disable=W0718
            msg = f"LanceDB: Error listing tables: {e}"
            raise DatabaseError(msg) from e

    # --- Methods from BaseDBAdapter not in scope for this subtask
    # or not applicable to LanceDB's role ---

    def create_object_type(self, definition: "ObjectTypeDefinition") -> None: # Match BaseDBAdapter
        """LanceDB tables are primarily for embeddings, not general object types."""

    def get_object_type(self, name: str) -> Optional[ObjectTypeDefinition]: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.get_object_type not applicable/implemented."
        raise NotImplementedError(
            msg,
        )

    def update_object_type(self, definition: ObjectTypeDefinition) -> None: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.update_object_type not applicable/implemented."
        raise NotImplementedError(
            msg,
        )

    def delete_object_type(self, name: str) -> None:
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.delete_object_type not applicable/implemented."
        raise NotImplementedError(
            msg,
        )

    def list_object_types(self) -> list[str]:
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.list_object_types not applicable/implemented."
        raise NotImplementedError(
            msg,
        )

    def upsert_object_instance(
        self, instance: ObjectInstance,
    ) -> ObjectInstance: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.upsert_object_instance not applicable/implemented."
        raise NotImplementedError(
            msg,
        )

    def get_object_instance(
        self, object_type_name: str, instance_id: UUID,
    ) -> Optional[ObjectInstance]: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.get_object_instance not applicable/implemented."
        raise NotImplementedError(
            msg,
        )

    def delete_object_instance(self, object_type_name: str, instance_id: UUID) -> bool:
        """Not applicable/implemented for LanceDB for this subtask."""
        msg = "LanceDBAdapter.delete_object_instance not applicable/implemented for this subtask."
        raise NotImplementedError(
            msg,
        )

    def find_object_instances(
        self,
        object_type_name: str,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[ObjectInstance]: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.find_object_instances not applicable/implemented."
        raise NotImplementedError(
            msg,
        )

    def get_all_object_ids_for_type(self, object_type_name: str) -> list[UUID]:
        """LanceDB is not designed to fetch all object IDs for a type directly; this is a relational store task."""
        msg = "LanceDBAdapter.get_all_object_ids_for_type is not applicable."
        raise NotImplementedError(msg)

    # --- Embedding Definition Management (Core to this adapter's role
    # via table management) ---
    def add_embedding_definition(self, definition: EmbeddingDefinition) -> None:
        """Handles the creation of the corresponding LanceDB table for an embedding definition."""

    def get_embedding_definition(self, name: str) -> Optional[EmbeddingDefinition]:
        """Definitions are managed by SQLite."""
        msg = "LanceDBAdapter.get_embedding_definition: Definitions are managed by SQLite."
        raise NotImplementedError(
            msg,
        )

    def remove_embedding_definition(self, embedding_definition_name: str) -> None:
        """Handles the deletion of the corresponding LanceDB table for an embedding definition."""


    # --- Embedding Instance Management (Subtask 2.2) ---

    def get_embedding_model(self, model_identifier: str) -> Any:
        """Loads an embedding model function using LanceDB's registry.
        Caches loaded models so repeated calls don't reload weights.
        """
        if not LANCEDB_AVAILABLE or not LANCEDB_EMBEDDING_REGISTRY:
            msg = "LanceDB or its embedding registry is not available. Cannot load models."
            raise EmbeddingError(msg)

        device = "cuda" if self._use_gpu else "cpu"
        cache_key = f"{model_identifier}:{device}"

        with self._model_lock:
            if cache_key in self._model_cache:
                return self._model_cache[cache_key]

        try:
            provider_name = "huggingface"
            actual_model_name = model_identifier

            if ":" in model_identifier:
                parts = model_identifier.split(":", 1)
                if len(parts) == 2:
                    provider_name = parts[0]
                    actual_model_name = parts[1]

            provider = LANCEDB_EMBEDDING_REGISTRY.get(provider_name)
            try:
                model = provider.create(name=actual_model_name, device=device, trust_remote_code=True)
            except TypeError:
                model = provider.create(name=actual_model_name, trust_remote_code=True)

            with self._model_lock:
                self._model_cache[cache_key] = model
            logger.info("Loaded and cached embedding model '%s' on %s", model_identifier, device)
            return model
        except Exception as e: # pylint: disable=W0718
            msg = f"Failed to load embedding model '{model_identifier}' via LanceDB registry: {e}"
            raise EmbeddingError(msg) from e

    def upsert_embedding_instance(
        self,
        instance: EmbeddingInstance,
        embedding_definition: Optional[EmbeddingDefinition] = None,
    ) -> EmbeddingInstance:
        """Adds or replaces the embedding record of ``instance.object_instance_id``."""
        if embedding_definition is None:
            msg = (
                "LanceDBAdapter.upsert_embedding_instance "
                             "requires an EmbeddingDefinition argument."
            )
            raise ValueError(msg)

        if self.db is None:
            msg = "LanceDB not connected. Cannot upsert EI."
            raise DatabaseError(msg)
        if not LANCEDB_AVAILABLE or not LanceModelClass or not _VECTOR_CLASS:
            msg = "LanceDB runtime components not available. Cannot upsert EI."
            raise DatabaseError(msg)
        table_name = self._sanitize_table_name(embedding_definition.name)

        if (embedding_definition.dimensions and
                len(instance.vector) != embedding_definition.dimensions):
            msg = (
                f"Vector dim mismatch for '{embedding_definition.name}'. "
                f"Expected {embedding_definition.dimensions}, got {len(instance.vector)}."
            )
            raise EmbeddingError(
                msg,
            )

        row = {
            "object_instance_id": str(instance.object_instance_id),
            "vector": instance.vector,
            "source_text_preview": instance.source_text_preview,
        }

        with self._table_lock:
            tbl = self._open_table_for_write(table_name, embedding_definition.name)
            try:
                self._merge_rows(tbl, [row])
            except Exception as e: # pylint: disable=W0718
                msg = f"LanceDB: Error upserting EI to table '{table_name}': {e}"
                raise DatabaseError(msg) from e
            self._note_write(table_name)
        return instance

    def upsert_embedding_instances_bulk(
        self,
        instances: list[EmbeddingInstance],
        embedding_definition: EmbeddingDefinition,
    ) -> None:
        """Adds or replaces many embedding records in one commit."""
        if not instances:
            return

        if self.db is None:
            msg = "LanceDB not connected. Cannot bulk upsert EIs."
            raise DatabaseError(msg)

        table_name = self._sanitize_table_name(embedding_definition.name)

        # One row per object: a batch naming an object twice would otherwise
        # insert it twice (merge_insert does not reject duplicate source rows).
        rows_by_id: dict[str, dict[str, Any]] = {}
        for instance in instances:
            if (embedding_definition.dimensions and
                    len(instance.vector) != embedding_definition.dimensions):
                msg = (
                    f"Vector dim mismatch for instance '{instance.object_instance_id}' and ED '{embedding_definition.name}'. "
                    f"Expected {embedding_definition.dimensions}, got {len(instance.vector)}."
                )
                raise EmbeddingError(msg)

            rows_by_id[str(instance.object_instance_id)] = {
                "object_instance_id": str(instance.object_instance_id),
                "vector": instance.vector,
                "source_text_preview": instance.source_text_preview,
            }

        with self._table_lock:
            tbl = self._open_table_for_write(table_name, embedding_definition.name)
            try:
                self._merge_rows(tbl, list(rows_by_id.values()))
                logger.info(f"LanceDB: Bulk upserted {len(rows_by_id)} EIs to table '{table_name}'.")
            except Exception as e:
                msg = f"LanceDB: Error bulk upserting EIs to table '{table_name}': {e}"
                raise DatabaseError(msg) from e
            self._note_write(table_name)

    def _open_table_for_write(self, table_name: str, definition_name: str) -> Any:
        try:
            return self.db.open_table(table_name)  # type: ignore[union-attr]
        except Exception as e: # pylint: disable=W0718
            msg = (
                f"LanceDB: Table '{table_name}' for ED '{definition_name}' not found. "
                f"Cannot upsert. Error: {e}"
            )
            raise DatabaseError(msg) from e

    @staticmethod
    def _merge_rows(tbl: Any, rows: list[dict[str, Any]]) -> None:
        # One commit per write, replacing the object's row in place. Callers
        # used to delete the old row and append a new one: two commits, and a
        # new fragment every time.
        (
            tbl.merge_insert("object_instance_id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )

    # --- Maintenance ---

    def _note_write(self, table_name: str) -> None:
        """Counts a write; compacts at once when enough have piled up. Caller holds the lock."""
        self._pending_writes[table_name] = self._pending_writes.get(table_name, 0) + 1
        self._last_write_at = time.monotonic()
        if self.compact_after_writes > 0 and self._pending_writes[table_name] >= self.compact_after_writes:
            try:
                self.optimize_table(table_name)
            except Exception as e: # pylint: disable=W0718
                # The write itself succeeded; a failed compaction is retried later.
                logger.error(f"LanceDB: Compacting '{table_name}' after a write failed: {e}", exc_info=True)

    def optimize_table(
        self, table_name: str, cleanup_older_than_s: Optional[float] = None,
    ) -> dict[str, Any]:
        """Compacts one table, updates or builds its vector index, and removes old versions.

        Returns what changed: rows, fragments before and after, whether an
        index was (re)built, and the seconds it took.
        """
        if self.db is None:
            msg = "LanceDB not connected. Cannot optimize."
            raise DatabaseError(msg)
        older_than = self.cleanup_older_than_s if cleanup_older_than_s is None else cleanup_older_than_s
        started = time.monotonic()
        with self._table_lock:
            tbl = self.db.open_table(table_name)
            fragments_before = self._fragment_count(tbl)
            tbl.optimize(cleanup_older_than=timedelta(seconds=max(0.0, older_than)))
            indexed = self._ensure_vector_index(table_name, tbl)
            self._pending_writes[table_name] = 0
            report = {
                "table": table_name,
                "rows": tbl.count_rows(),
                "fragments_before": fragments_before,
                "fragments_after": self._fragment_count(tbl),
                "version": tbl.version,
                "index_built": indexed,
                "index_partitions": self._index_partitions.get(table_name, 0),
                "seconds": round(time.monotonic() - started, 3),
            }
        logger.info(f"LanceDB: Optimized table: {report}")
        return report

    def optimize_all(self, cleanup_older_than_s: Optional[float] = None) -> list[dict[str, Any]]:
        """Runs :meth:`optimize_table` on every table."""
        return [self.optimize_table(name, cleanup_older_than_s) for name in self.list_embedding_tables()]

    @staticmethod
    def _fragment_count(tbl: Any) -> int:
        try:
            return int(tbl.stats()["fragment_stats"]["num_fragments"])
        except Exception: # pylint: disable=W0718
            return -1

    @staticmethod
    def _wanted_partitions(rows: int) -> int:
        return max(1, min(int(math.sqrt(rows)), rows // MIN_ROWS_PER_PARTITION))

    def _vector_indices(self, tbl: Any) -> list[Any]:
        return [i for i in tbl.list_indices() if "vector" in list(getattr(i, "columns", []))]

    def _ensure_vector_index(self, table_name: str, tbl: Any) -> bool:
        """Builds the vector index past ``index_min_rows``, and rebuilds it once the table has
        grown enough to want twice the partitions, or once it has piled up delta segments.
        Returns whether it built one.
        """
        current = self._read_index_partitions(table_name, tbl)
        if self.index_min_rows <= 0:
            return False
        rows = tbl.count_rows()
        if rows < self.index_min_rows:
            return False
        wanted = self._wanted_partitions(rows)
        if current and wanted < 2 * current and self._index_segments(tbl) <= MAX_INDEX_SEGMENTS:
            return False
        # Each delta segment is listed under the index's name; drop the name once.
        for name in dict.fromkeys(index.name for index in self._vector_indices(tbl)):
            tbl.drop_index(name)
        tbl.create_index(
            metric=VECTOR_INDEX_METRIC,
            vector_column_name="vector",
            index_type=VECTOR_INDEX_TYPE,
            num_partitions=wanted,
            replace=True,
            name=f"{VECTOR_INDEX_PREFIX}{wanted}",
        )
        self._index_partitions[table_name] = wanted
        logger.info(f"LanceDB: Built {VECTOR_INDEX_TYPE} index on '{table_name}' ({rows} rows, {wanted} partitions).")
        return True

    def _index_segments(self, tbl: Any) -> int:
        indices = self._vector_indices(tbl)
        if not indices:
            return 0
        try:
            stats = tbl.index_stats(indices[0].name)
            return int(stats.num_indices) if stats is not None else 0
        except Exception: # pylint: disable=W0718
            return 0

    def _read_index_partitions(self, table_name: str, tbl: Any) -> int:
        """The partition count of the table's vector index (0 if none), read once per table."""
        if table_name not in self._index_partitions:
            partitions = 0
            for index in self._vector_indices(tbl):
                name = str(getattr(index, "name", ""))
                if name.startswith(VECTOR_INDEX_PREFIX):
                    try:
                        partitions = int(name[len(VECTOR_INDEX_PREFIX):])
                    except ValueError:
                        partitions = 0
                else:
                    # An index this adapter did not name: probe generously.
                    partitions = 4 * MIN_NPROBES
            self._index_partitions[table_name] = partitions
        return self._index_partitions[table_name]

    def _tune_search(self, query: Any, table_name: str, tbl: Any) -> Any:
        """Probes half the partitions of an IVF index (at least MIN_NPROBES), for recall."""
        partitions = self._read_index_partitions(table_name, tbl)
        if partitions:
            query = query.nprobes(max(MIN_NPROBES, math.ceil(partitions / 2)))
        return query

    def _start_maintenance_thread(self) -> None:
        if self.db is None or self.maintenance_interval_s <= 0:
            return
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop, name="grizabella-lancedb-maintenance", daemon=True,
        )
        self._maintenance_thread.start()

    def _maintenance_loop(self) -> None:
        first = True
        wait = min(self.maintenance_interval_s, self.maintenance_idle_s)
        while not self._stop_maintenance.wait(wait):
            try:
                self.run_maintenance(check_fragmentation=first)
                first = False
            except Exception as e: # pylint: disable=W0718
                logger.error(f"LanceDB: Background maintenance failed: {e}", exc_info=True)
            wait = self.maintenance_interval_s

    def run_maintenance(self, check_fragmentation: bool = False) -> list[dict[str, Any]]:
        """One background pass: compacts tables written to since their last compaction once
        writes have been quiet for ``maintenance_idle_s``. With ``check_fragmentation`` (the
        first pass after opening), also any table left fragmented by an earlier run.
        """
        if self.db is None:
            return []
        reports = []
        with self._table_lock:
            if self._stop_maintenance.is_set() or self.db is None:
                return []
            quiet = time.monotonic() - self._last_write_at >= self.maintenance_idle_s
            for name in self.list_embedding_tables():
                due = quiet and self._pending_writes.get(name, 0) > 0
                if not due and check_fragmentation:
                    threshold = max(2, self.compact_after_writes)
                    due = self._fragment_count(self.db.open_table(name)) > threshold
                if due:
                    reports.append(self.optimize_table(name))
        return reports

    def get_embedding_instance(
        self, embedding_definition_name: str, object_instance_id: UUID,
    ) -> Optional[EmbeddingInstance]:
        """Retrieves a single embedding instance for a given object ID and embedding definition."""
        instances = self.get_embedding_instances_for_object(
            object_instance_id, embedding_definition_name,
        )
        if instances:
            return instances[0]
        return None

    def get_embedding_instances_for_object(
        self, object_instance_id: UUID, embedding_definition_name: str,
    ) -> list[EmbeddingInstance]:
        """Retrieves all embedding instances for a given object ID and embedding definition."""
        if self.db is None:
            msg = "LanceDB not connected. Cannot get embedding instances."
            raise DatabaseError(msg)

        table_name = self._sanitize_table_name(embedding_definition_name)
        with self._table_lock:
            try:
                # Re-opened on each call: it is how a search sees another process's
                # writes, and costs nothing measurable once the table is compacted.
                tbl = self.db.open_table(table_name)
            except Exception: # TableNotFoundError # pylint: disable=W0718
                return []
            try:
                query_result = tbl.search() \
                    .where(f"object_instance_id = '{object_instance_id!s}'") \
                    .select(["object_instance_id", "vector", "source_text_preview"]) \
                    .to_list()
            except Exception as e: # pylint: disable=W0718
                msg = (
                    f"LanceDB: Error retrieving EIs from table "
                                    f"'{table_name}': {e}"
                )
                raise DatabaseError(msg) from e

        try:
            instances = []
            for record in query_result:
                instances.append(
                    EmbeddingInstance(
                        object_instance_id=UUID(record["object_instance_id"]),
                        embedding_definition_name=embedding_definition_name,
                        vector=record["vector"],
                        source_text_preview=record.get("source_text_preview"),
                    ),
                )
            return instances
        except Exception as e: # pylint: disable=W0718
            msg = (
                f"LanceDB: Error retrieving EIs from table "
                                f"'{table_name}': {e}"
            )
            raise DatabaseError(msg) from e


    def delete_embedding_instances_for_object(
        self, object_instance_id: UUID, embedding_definition_name: str,
    ) -> None:
        """Deletes all embedding instances for a given object ID from a specific embedding table."""
        if self.db is None:
            msg = "LanceDB not connected. Cannot delete embedding instances."
            raise DatabaseError(msg)

        table_name = self._sanitize_table_name(embedding_definition_name)
        with self._table_lock:
            try:
                tbl = self.db.open_table(table_name)
            except Exception: # TableNotFoundError # pylint: disable=W0718
                return

            try:
                delete_condition = f"object_instance_id = '{object_instance_id!s}'"
                tbl.delete(delete_condition)
            except Exception as e: # pylint: disable=W0718
                msg = (
                    f"LanceDB: Error deleting EIs from table "
                                    f"'{table_name}': {e}"
                )
                raise DatabaseError(msg) from e
            self._note_write(table_name)

    def find_similar_embeddings(
        self, embedding_definition_name: str, vector: list[float], top_k: int = 5,
    ) -> list[EmbeddingInstance]: # pylint: disable=R0913
        """Finds objects with similar embeddings. Adapts to BaseDBAdapter."""
        results_dict_list = self.query_similar_embeddings(
            embedding_definition_name=embedding_definition_name,
            query_vector=vector,
            limit=top_k,
            filter_condition=None,
        )
        similar_instances = []
        for res_dict in results_dict_list:
            similar_instances.append(
                EmbeddingInstance(
                    object_instance_id=UUID(res_dict["object_instance_id"]),
                    embedding_definition_name=embedding_definition_name,
                    vector=res_dict["vector"],
                    source_text_preview=res_dict.get("source_text_preview"),
                ),
            )
        return similar_instances

    def query_similar_embeddings(
        self,
        embedding_definition_name: str,
        query_vector: list[float],
        limit: int = 10,
        filter_condition: Optional[str] = None,
        columns: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Queries the LanceDB table for embeddings similar to the query_vector.

        ``columns`` limits the row to those columns plus ``_distance``; by
        default every column comes back, the vector included (4 KB a row at
        1024 dimensions, which made up 80% of the time of an 800-row search).
        """
        if self.db is None:
            msg = "LanceDB not connected. Cannot query similar embeddings."
            raise DatabaseError(msg)

        table_name = self._sanitize_table_name(embedding_definition_name)
        with self._table_lock:
            try:
                tbl = self.db.open_table(table_name)
            except Exception as e: # pylint: disable=W0718
                msg = (
                    f"LanceDB: Table '{table_name}' for ED '{embedding_definition_name}' not found. "
                    f"Error: {e}"
                )
                raise SchemaError(
                    msg,
                ) from e

            try:
                # Squared L2 unless an index says otherwise; ours are built with it too.
                search_query = self._tune_search(tbl.search(query_vector), table_name, tbl)

                if filter_condition:
                    search_query = search_query.where(filter_condition)

                if columns:
                    wanted = list(dict.fromkeys([*columns, "_distance"]))
                    search_query = search_query.select(wanted)

                search_query = search_query.limit(limit)
                return search_query.to_list()

            except Exception as e: # pylint: disable=W0718
                msg = f"LanceDB: Error querying similar embeddings in table '{table_name}': {e}"
                raise DatabaseError(
                    msg,
                ) from e

    def find_object_ids_by_similarity(
        self,
        embedding_definition_name: str,
        query_vector: list[float],
        limit: int,
        initial_ids: Optional[list[UUID]] = None,
        filter_condition: Optional[str] = None, # Added as per design doc, though might be complex
    ) -> list[tuple[UUID, float]]: # Return (ID, distance) tuples
        """Finds object instance IDs and their distances by embedding similarity, optionally filtering by initial_ids."""
        if self.db is None:
            msg = "LanceDB not connected. Cannot query similar embeddings."
            raise DatabaseError(msg)

        table_name = self._sanitize_table_name(embedding_definition_name)
        with self._table_lock:
            try:
                tbl = self.db.open_table(table_name)
            except Exception as e: # pylint: disable=W0718
                msg = (
                    f"LanceDB: Table '{table_name}' for ED '{embedding_definition_name}' not found. "
                    f"Error: {e}"
                )
                raise SchemaError(
                    msg,
                ) from e

            try:
                search_query = self._tune_search(tbl.search(query_vector), table_name, tbl)

                # LanceDB's Python API `where` clause is for filtering on attributes *before* ANN search.
                # If `initial_ids` are provided, we need to perform the ANN search first,
                # then filter the results.
                # The `filter_condition` parameter from the design doc would also apply to attributes
                # in the LanceDB table.

                if filter_condition: # This applies to LanceDB table attributes
                    search_query = search_query.where(filter_condition)

                search_query = search_query.limit(limit)
                # Select object_instance_id and _distance for ranking
                search_query = search_query.select(["object_instance_id", "_distance"])
                results_from_lancedb = search_query.to_list() # List of dicts
                logger.info(f"LanceDB raw search results for ED '{embedding_definition_name}' (query_vector_snippet: {str(query_vector)[:100]}..., limit {limit}):\n{results_from_lancedb}")

                # Store as (id, distance) tuples
                candidate_results_with_distance = []
                for record in results_from_lancedb:
                    try:
                        obj_id = UUID(record["object_instance_id"])
                        distance = record["_distance"] # LanceDB returns distance
                        candidate_results_with_distance.append((obj_id, distance))
                    except (ValueError, TypeError, KeyError):
                        continue # Skip invalid records

                if initial_ids is not None:
                    initial_ids_set = set(initial_ids)
                    # Filter by initial_ids
                    filtered_by_initial_ids = [
                        (obj_id, dist) for obj_id, dist in candidate_results_with_distance
                        if obj_id in initial_ids_set
                    ]
                else:
                    filtered_by_initial_ids = candidate_results_with_distance

                # Sort by distance (ascending, as lower distance is more similar)
                filtered_by_initial_ids.sort(key=lambda x: x[1])

                # Apply the limit to the filtered and sorted results.
                # If initial_ids were provided, the test implies we should effectively take the top 1 from that filtered set,
                # overriding the general 'limit' for the count if the test's specific expectation of 1 result is to be met.
                # This is a specific interpretation to make the test_find_object_ids_by_similarity_with_initial_ids pass.
                if initial_ids is not None:
                    # The limit should apply to the results *after* filtering by initial_ids and sorting.
                    # Now return (id, distance) tuples
                    final_results_with_distance = [(obj_id, dist) for obj_id, dist in filtered_by_initial_ids[:limit]]
                else:
                    final_results_with_distance = [(obj_id, dist) for obj_id, dist in filtered_by_initial_ids[:limit]]

                logger.info(f"LanceDBAdapter.find_object_ids_by_similarity returning final_results_with_distance (limit: {limit}, initial_ids was {'None' if initial_ids is None else 'Provided'}): {final_results_with_distance}")
                return final_results_with_distance

            except Exception as e: # pylint: disable=W0718
                msg = f"LanceDB: Error querying similar object IDs in table '{table_name}': {e}"
                raise DatabaseError(
                    msg,
                ) from e


    # --- Relation Management (Not applicable to LanceDB) ---
    def create_relation_type(
        self, definition: RelationTypeDefinition,
    ) -> None: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.create_relation_type is not applicable."
        raise NotImplementedError(
            msg,
        )

    def get_relation_type(
        self, name: str,
    ) -> Optional[RelationTypeDefinition]: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.get_relation_type is not applicable."
        raise NotImplementedError(
            msg,
        )

    def upsert_relation_instance( # pylint: disable=arguments-differ
        self, instance: RelationInstance, rtd: Optional[RelationTypeDefinition] = None,
    ) -> RelationInstance: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.upsert_relation_instance is not applicable."
        raise NotImplementedError(
            msg,
        )

    def get_relation_instance(
        self, relation_type_name: str, relation_id: UUID,
    ) -> Optional[RelationInstance]: # Match BaseDBAdapter
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.get_relation_instance is not applicable."
        raise NotImplementedError(
            msg,
        )

    def find_relation_instances( # pylint: disable=R0913, R0917
        self,
        relation_type_name: Optional[str] = None,
        source_object_id: Optional[UUID] = None,
        target_object_id: Optional[UUID] = None,
        query: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[RelationInstance]:
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.find_relation_instances is not applicable."
        raise NotImplementedError(
            msg,
        )

    def delete_relation_instance(self, relation_type_name: str, relation_id: UUID) -> bool:
        """Not applicable/implemented for LanceDB."""
        msg = "LanceDBAdapter.delete_relation_instance is not applicable."
        raise NotImplementedError(
            msg,
        )
