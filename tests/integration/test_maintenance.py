"""grizabella-maintain against real SQLite, LanceDB and LadybugDB tiers in a temp dir."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from grizabella.api.client import Grizabella
from grizabella.core.models import (
    EmbeddingDefinition,
    EmbeddingInstance,
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDataType,
    PropertyDefinition,
    RelationInstance,
    RelationTypeDefinition,
)
from grizabella.maintenance import compact_vector_store, main, rebuild_graph


@pytest.fixture(autouse=True)
def no_background_compaction(monkeypatch):
    monkeypatch.setenv("GRIZABELLA_LANCEDB_MAINTENANCE_INTERVAL_S", "0")


def seed(db: Path) -> dict:
    """Two notes superseding a third, as a knowledge base records a correction, under a
    schema and its migrated copy (same ids in both node tables, as a type migration leaves them).
    """
    gb = Grizabella(db_name_or_path=db, create_if_not_exists=True)
    gb.connect()
    try:
        old, mid, new = uuid4(), uuid4(), uuid4()
        for suffix in ("", "V2"):
            note = f"Note{suffix}"
            supersedes = f"SUPERSEDES{'_V2' if suffix else ''}"
            gb.create_object_type(ObjectTypeDefinition(
                name=note,
                properties=[
                    PropertyDefinition(name="title", data_type=PropertyDataType.TEXT),
                    PropertyDefinition(name="superseded_by", data_type=PropertyDataType.TEXT, is_nullable=True),
                ],
            ))
            gb.create_relation_type(RelationTypeDefinition(
                name=supersedes,
                source_object_type_names=[note],
                target_object_type_names=[note],
                properties=[PropertyDefinition(name="reason", data_type=PropertyDataType.TEXT, is_nullable=True)],
            ))
            gb.upsert_object(ObjectInstance(id=old, object_type_name=note, properties={"title": "old", "superseded_by": str(mid)}))
            gb.upsert_object(ObjectInstance(id=mid, object_type_name=note, properties={"title": "mid", "superseded_by": str(new)}))
            gb.upsert_object(ObjectInstance(id=new, object_type_name=note, properties={"title": "new"}))
            gb.add_relation(RelationInstance(
                relation_type_name=supersedes, source_object_instance_id=mid, target_object_instance_id=old,
                properties={"reason": "measured again"},
            ))
            gb.add_relation(RelationInstance(
                relation_type_name=supersedes, source_object_instance_id=new, target_object_instance_id=mid,
                properties={"reason": "fixed the units"},
            ))
    finally:
        gb.close()
    return {"old": old, "mid": mid, "new": new}


def test_rebuild_graph_from_sqlite_after_the_graph_became_unreadable(tmp_path):
    db = tmp_path / "db"
    ids = seed(db)

    # What an engine upgrade across a storage format leaves: a graph file the
    # new LadybugDB will not open.
    graph = db / "kuzu_data.db"
    graph.write_bytes(b"not a ladybug database" * 100)
    for leftover in db.glob("kuzu_data.db.*"):
        leftover.unlink()

    report = rebuild_graph(db, progress=lambda _line: None)

    assert report["failed_nodes"] == 0 and report["failed_edges"] == 0
    assert report["nodes"] == {"Note": 3, "NoteV2": 3}
    assert report["edges"] == {"SUPERSEDES": 2, "SUPERSEDES_V2": 2}
    for kind in ("objects", "relations"):
        for name, counts in report["verify"][kind].items():
            assert counts["sqlite"] == counts["graph"] == (3 if kind == "objects" else 2), name
    (moved,) = report["moved"]
    assert Path(moved).read_bytes().startswith(b"not a ladybug database")

    gb = Grizabella(db_name_or_path=db, create_if_not_exists=False)
    gb.connect()
    try:
        kuzu = gb._db_manager._connection_helper.kuzu_adapter  # pylint: disable=protected-access
        for note, supersedes in (("Note", "SUPERSEDES"), ("NoteV2", "SUPERSEDES_V2")):
            result = kuzu.connection.execute(
                f"MATCH (a:{note})-[r:{supersedes}]->(b:{note}) RETURN a.title, b.title, r.reason ORDER BY a.title",
            )
            rows = []
            while result.has_next():
                rows.append(result.get_next())
            assert rows == [["mid", "old", "measured again"], ["new", "mid", "fixed the units"]]
        incoming = gb.get_incoming_relations(str(ids["old"]), "NoteV2", "SUPERSEDES_V2")
        assert [r.properties["reason"] for r in incoming] == ["measured again"]
    finally:
        gb.close()


def test_compact_reports_and_shrinks_a_fragmented_table(tmp_path):
    from grizabella.db_layers.lancedb.lancedb_adapter import LanceDBAdapter

    db = tmp_path / "db"
    (db / "lancedb_data").mkdir(parents=True)
    ed = EmbeddingDefinition(name="Note_search", object_type_name="Note", source_property_name="title",
                             embedding_model="huggingface/test", dimensions=8)
    writer = LanceDBAdapter(db_uri=str(db / "lancedb_data"), config={"maintenance_interval_s": 0, "compact_after_writes": 0})
    writer.create_embedding_table(ed)
    for i in range(20):
        writer.upsert_embedding_instance(
            EmbeddingInstance(object_instance_id=uuid4(), embedding_definition_name=ed.name, vector=[float(i)] * 8), ed,
        )
    writer.close()

    (report,) = compact_vector_store(db)
    assert report["table"] == "Note_search"
    assert report["rows"] == 20
    assert report["fragments_before"] == 20 and report["fragments_after"] == 1
    assert report["versions_before"] >= 20 and report["versions_after"] == 1
    assert report["bytes_after"] < report["bytes_before"]


def test_cli_stats_and_compact(tmp_path, capsys):
    db = tmp_path / "db"
    seed(db)
    assert main(["--db-path", str(db), "compact"]) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert main(["--db-path", str(db), "stats"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["graph"]["objects"]["Note"] == {"sqlite": 3, "graph": 3}
    assert out["graph"]["relations"]["SUPERSEDES_V2"] == {"sqlite": 2, "graph": 2}
    assert main(["--db-path", str(tmp_path / "missing"), "stats"]) == 2
    assert os.environ["GRIZABELLA_LANCEDB_MAINTENANCE_INTERVAL_S"] == "0"
