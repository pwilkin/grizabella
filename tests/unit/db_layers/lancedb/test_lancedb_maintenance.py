"""Upserts replace rows in one commit, and tables are compacted, cleaned and indexed."""

import os
import time
from pathlib import Path
from uuid import uuid4

import pytest

lancedb = pytest.importorskip("lancedb")

from grizabella.core.models import EmbeddingDefinition, EmbeddingInstance  # noqa: E402
from grizabella.db_layers.lancedb.lancedb_adapter import (  # noqa: E402
    MAX_INDEX_SEGMENTS,
    VECTOR_INDEX_PREFIX,
    LanceDBAdapter,
)

DIM = 16


@pytest.fixture
def ed() -> EmbeddingDefinition:
    return EmbeddingDefinition(
        name="maint_ed",
        object_type_name="Doc",
        source_property_name="text",
        embedding_model="huggingface/test-model",
        dimensions=DIM,
    )


def make_adapter(tmp_path: Path, **config) -> LanceDBAdapter:
    settings = {"maintenance_interval_s": 0, "cleanup_older_than_s": 0, "compact_after_writes": 0}
    settings.update(config)
    return LanceDBAdapter(db_uri=str(tmp_path / "lance"), config=settings)


def instance(ed: EmbeddingDefinition, value: float, object_id=None, preview=None) -> EmbeddingInstance:
    vec = [value * (i + 1) for i in range(DIM)]
    return EmbeddingInstance(
        object_instance_id=object_id or uuid4(),
        embedding_definition_name=ed.name,
        vector=vec,
        source_text_preview=preview,
    )


def fragments(adapter: LanceDBAdapter, name: str) -> int:
    return adapter.db.open_table(name).stats()["fragment_stats"]["num_fragments"]


def versions_on_disk(tmp_path: Path, name: str) -> int:
    return len(os.listdir(tmp_path / "lance" / f"{name}.lance" / "_versions"))


def test_upsert_replaces_the_row_in_one_commit(tmp_path, ed):
    adapter = make_adapter(tmp_path)
    try:
        adapter.create_embedding_table(ed)
        tbl = adapter.db.open_table(ed.name)
        oid = uuid4()
        adapter.upsert_embedding_instance(instance(ed, 0.1, oid, "first"), ed)
        v1 = adapter.db.open_table(ed.name).version
        adapter.upsert_embedding_instance(instance(ed, 0.2, oid, "second"), ed)
        tbl = adapter.db.open_table(ed.name)
        assert tbl.version == v1 + 1
        rows = tbl.to_arrow().to_pylist()
        assert [(r["object_instance_id"], r["source_text_preview"]) for r in rows] == [(str(oid), "second")]
        assert rows[0]["vector"][0] == pytest.approx(0.2)
    finally:
        adapter.close()


def test_bulk_upsert_keeps_one_row_per_object(tmp_path, ed):
    adapter = make_adapter(tmp_path)
    try:
        adapter.create_embedding_table(ed)
        a, b = uuid4(), uuid4()
        adapter.upsert_embedding_instance(instance(ed, 0.1, a, "old a"), ed)
        adapter.upsert_embedding_instances_bulk(
            [instance(ed, 0.2, a, "a once"), instance(ed, 0.3, b, "b"), instance(ed, 0.4, a, "a twice")], ed,
        )
        rows = {r["object_instance_id"]: r["source_text_preview"] for r in adapter.db.open_table(ed.name).to_arrow().to_pylist()}
        assert rows == {str(a): "a twice", str(b): "b"}
    finally:
        adapter.close()


def test_compacts_after_n_writes_and_drops_old_versions(tmp_path, ed):
    adapter = make_adapter(tmp_path, compact_after_writes=5)
    try:
        adapter.create_embedding_table(ed)
        for i in range(4):
            adapter.upsert_embedding_instance(instance(ed, 0.1 + i), ed)
        assert fragments(adapter, ed.name) == 4
        adapter.upsert_embedding_instance(instance(ed, 0.9), ed)
        assert fragments(adapter, ed.name) == 1
        assert versions_on_disk(tmp_path, ed.name) == 1
        assert adapter.db.open_table(ed.name).count_rows() == 5
    finally:
        adapter.close()


def test_optimize_table_reports_and_keeps_search_results(tmp_path, ed):
    adapter = make_adapter(tmp_path)
    try:
        adapter.create_embedding_table(ed)
        for i in range(12):
            adapter.upsert_embedding_instance(instance(ed, 0.05 * (i + 1)), ed)
        query = [0.3 * (i + 1) for i in range(DIM)]
        before = adapter.query_similar_embeddings(ed.name, query, limit=5, columns=["object_instance_id"])
        report = adapter.optimize_table(ed.name)
        after = adapter.query_similar_embeddings(ed.name, query, limit=5, columns=["object_instance_id"])
        assert report["fragments_before"] == 12
        assert report["fragments_after"] == 1
        assert report["rows"] == 12
        assert report["index_built"] is False
        assert [(r["object_instance_id"], r["_distance"]) for r in after] == [(r["object_instance_id"], r["_distance"]) for r in before]
        assert versions_on_disk(tmp_path, ed.name) == 1
    finally:
        adapter.close()


def test_column_projection_leaves_the_vector_out(tmp_path, ed):
    adapter = make_adapter(tmp_path)
    try:
        adapter.create_embedding_table(ed)
        adapter.upsert_embedding_instance(instance(ed, 0.1, preview="p"), ed)
        hit = adapter.query_similar_embeddings(ed.name, [0.1] * DIM, limit=1, columns=["object_instance_id"])[0]
        assert set(hit) == {"object_instance_id", "_distance"}
        full = adapter.query_similar_embeddings(ed.name, [0.1] * DIM, limit=1)[0]
        assert {"vector", "source_text_preview", "_distance"} <= set(full)
    finally:
        adapter.close()


def test_builds_an_exact_l2_index_past_the_threshold_and_rebuilds_as_it_grows(tmp_path, ed):
    adapter = make_adapter(tmp_path, index_min_rows=300)
    try:
        adapter.create_embedding_table(ed)
        adapter.upsert_embedding_instances_bulk([instance(ed, 0.001 * (i + 1)) for i in range(299)], ed)
        assert adapter.optimize_table(ed.name)["index_built"] is False
        adapter.upsert_embedding_instance(instance(ed, 0.5), ed)
        report = adapter.optimize_table(ed.name)
        assert report["index_built"] is True
        assert report["index_partitions"] == 1
        tbl = adapter.db.open_table(ed.name)
        assert [i.name for i in tbl.list_indices()] == [f"{VECTOR_INDEX_PREFIX}1"]

        # Same hits and the same (squared L2) distances as a flat scan.
        query = [0.137 * (i + 1) for i in range(DIM)]
        got = adapter.query_similar_embeddings(ed.name, query, limit=10, columns=["object_instance_id"])
        exact = tbl.search(query).bypass_vector_index().limit(10).select(["object_instance_id", "_distance"]).to_list()
        assert [r["object_instance_id"] for r in got] == [r["object_instance_id"] for r in exact]
        assert [r["_distance"] for r in got] == pytest.approx([r["_distance"] for r in exact])

        # Not rebuilt until the table wants twice the partitions, or has too many delta segments.
        passes = 1
        while not adapter.optimize_table(ed.name)["index_built"]:
            passes += 1
            assert passes <= MAX_INDEX_SEGMENTS + 1
        # Each pass adds a delta segment to the one the build left.
        assert passes == MAX_INDEX_SEGMENTS
        assert adapter.db.open_table(ed.name).index_stats(f"{VECTOR_INDEX_PREFIX}1").num_indices == 1
        adapter.upsert_embedding_instances_bulk([instance(ed, 0.002 * (i + 1)) for i in range(300)], ed)
        report = adapter.optimize_table(ed.name)
        assert report["index_built"] is True
        assert report["index_partitions"] == 2
        assert [i.name for i in adapter.db.open_table(ed.name).list_indices()] == [f"{VECTOR_INDEX_PREFIX}2"]
    finally:
        adapter.close()


def test_a_fresh_adapter_reads_the_partitions_of_an_existing_index(tmp_path, ed):
    adapter = make_adapter(tmp_path, index_min_rows=300)
    adapter.create_embedding_table(ed)
    adapter.upsert_embedding_instances_bulk([instance(ed, 0.001 * (i + 1)) for i in range(600)], ed)
    adapter.optimize_table(ed.name)
    adapter.close()

    reopened = make_adapter(tmp_path, index_min_rows=300)
    try:
        tbl = reopened.db.open_table(ed.name)
        assert reopened._read_index_partitions(ed.name, tbl) == 2  # pylint: disable=protected-access
        assert reopened.optimize_table(ed.name)["index_built"] is False
    finally:
        reopened.close()


def wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_background_pass_compacts_once_writes_go_quiet(tmp_path, ed):
    adapter = make_adapter(tmp_path, maintenance_interval_s=0.1, maintenance_idle_s=0.2, compact_after_writes=1000)
    try:
        adapter.create_embedding_table(ed)
        for i in range(3):
            adapter.upsert_embedding_instance(instance(ed, 0.1 * (i + 1)), ed)
        assert wait_for(lambda: fragments(adapter, ed.name) == 1)
        assert adapter.db.open_table(ed.name).count_rows() == 3
    finally:
        adapter.close()
    assert adapter._maintenance_thread is None  # pylint: disable=protected-access


def test_first_background_pass_compacts_a_table_left_fragmented(tmp_path, ed):
    writer = make_adapter(tmp_path)
    writer.create_embedding_table(ed)
    tbl = writer.db.open_table(ed.name)
    for i in range(6):
        tbl.add([{"object_instance_id": str(uuid4()), "vector": [0.1 * (i + 1)] * DIM, "source_text_preview": None}])
    writer.close()

    adapter = make_adapter(tmp_path, maintenance_interval_s=0.1, maintenance_idle_s=0.1, compact_after_writes=4)
    try:
        assert wait_for(lambda: fragments(adapter, ed.name) == 1)
    finally:
        adapter.close()


def test_settings_come_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GRIZABELLA_LANCEDB_COMPACT_AFTER_WRITES", "7")
    monkeypatch.setenv("GRIZABELLA_LANCEDB_MAINTENANCE_INTERVAL_S", "0")
    adapter = LanceDBAdapter(db_uri=str(tmp_path / "lance"))
    try:
        assert adapter.compact_after_writes == 7
        assert adapter.maintenance_interval_s == 0
        assert adapter._maintenance_thread is None  # pylint: disable=protected-access
    finally:
        adapter.close()
