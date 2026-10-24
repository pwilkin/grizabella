"""Offline maintenance of a Grizabella database: ``grizabella-maintain``.

Run it with no engine (MCP server, UI, client) open on the database.

* ``stats``: rows, fragments, versions and bytes of each vector table, and
  node and edge counts of the graph tier next to SQLite's.
* ``compact``: compacts every vector table, drops the old versions and builds
  the vector index if the table is big enough. A table written to one row at
  a time for weeks (one fragment and one manifest per write) goes from
  gigabytes of manifests to one fragment.
* ``rebuild-graph``: recreates the graph tier from SQLite, which holds every
  object and relation. Upgrading LadybugDB across a storage-format change
  leaves a graph database the new engine refuses to open; the old files are
  moved into ``graph-backup-<time>/`` first, never deleted.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from grizabella.core.db_paths import KUZU_DIR_NAME, LANCEDB_DIR_NAME, SQLITE_DB_FILENAME, SQLITE_DIR_NAME

logger = logging.getLogger(__name__)

GRAPH_FILE_SUFFIXES = (".db", ".db.wal", ".db.wal.checkpoint", ".db.shadow")
PAGE_SIZE = 500


def _du(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _lancedb_adapter(db_path: Path) -> Any:
    from grizabella.db_layers.lancedb.lancedb_adapter import LanceDBAdapter

    return LanceDBAdapter(db_uri=str(db_path / LANCEDB_DIR_NAME), config={"maintenance_interval_s": 0})


def vector_table_stats(db_path: Path) -> list[dict[str, Any]]:
    """Per table: rows, fragments, versions on disk and bytes."""
    lance_dir = db_path / LANCEDB_DIR_NAME
    if not lance_dir.is_dir():
        return []
    adapter = _lancedb_adapter(db_path)
    try:
        out = []
        for name in adapter.list_embedding_tables():
            table_dir = lance_dir / f"{name}.lance"
            tbl = adapter.db.open_table(name)
            versions_dir = table_dir / "_versions"
            out.append({
                "table": name,
                "rows": tbl.count_rows(),
                "fragments": adapter._fragment_count(tbl),  # pylint: disable=protected-access
                "versions": len(os.listdir(versions_dir)) if versions_dir.is_dir() else None,
                "bytes": _du(table_dir),
                "indices": [str(getattr(i, "name", i)) for i in tbl.list_indices()],
            })
        return out
    finally:
        adapter.close()


def compact_vector_store(
    db_path: Path, table: Optional[str] = None, keep_versions_for_s: float = 0.0,
) -> list[dict[str, Any]]:
    """Compacts the vector tables and removes versions older than ``keep_versions_for_s``."""
    lance_dir = db_path / LANCEDB_DIR_NAME
    adapter = _lancedb_adapter(db_path)
    try:
        names = [table] if table else adapter.list_embedding_tables()
        reports = []
        for name in names:
            table_dir = lance_dir / f"{name}.lance"
            versions_dir = table_dir / "_versions"
            versions_before = len(os.listdir(versions_dir)) if versions_dir.is_dir() else None
            bytes_before = _du(table_dir)
            report = adapter.optimize_table(name, cleanup_older_than_s=keep_versions_for_s)
            report.update({
                "versions_before": versions_before,
                "versions_after": len(os.listdir(versions_dir)) if versions_dir.is_dir() else None,
                "bytes_before": bytes_before,
                "bytes_after": _du(table_dir),
            })
            reports.append(report)
        return reports
    finally:
        adapter.close()


def _graph_files(db_path: Path) -> list[Path]:
    base = db_path / KUZU_DIR_NAME
    found = [Path(str(base) + suffix) for suffix in GRAPH_FILE_SUFFIXES]
    found += sorted(db_path.glob(f"{KUZU_DIR_NAME}.db.wal*.corrupt"))
    found += sorted(db_path.glob(f"{KUZU_DIR_NAME}.db.shadow*"))
    return [p for p in dict.fromkeys(found) if p.exists()]


def _graph_count(kuzu: Any, query: str) -> Optional[int]:
    try:
        result = kuzu.connection.execute(query)
        if isinstance(result, list):
            result = result[0] if result else None
        if result is not None and result.has_next():
            return int(result.get_next()[0])
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Graph count failed (%s): %s", query, e)
    return None


def graph_stats(gb: Any) -> dict[str, Any]:
    """Node and edge counts per type in the graph tier, next to SQLite's."""
    mgr = gb._db_manager  # pylint: disable=protected-access
    helper = mgr._connection_helper  # pylint: disable=protected-access
    sqlite = helper.sqlite_adapter
    kuzu = helper.kuzu_adapter
    out: dict[str, Any] = {"objects": {}, "relations": {}}
    for otd in mgr.list_object_type_definitions():
        rows = sqlite.conn.execute(f'SELECT count(*) FROM "{sqlite._get_safe_table_name(otd.name)}"').fetchone()[0]  # pylint: disable=protected-access
        nodes = _graph_count(kuzu, f"MATCH (n:{otd.name}) RETURN count(n)")
        out["objects"][otd.name] = {"sqlite": rows, "graph": nodes}
    for rtd in mgr.list_relation_type_definitions():
        rows = sqlite.conn.execute(
            "SELECT count(*) FROM _grizabella_relation_instances WHERE relation_type_name = ?", (rtd.name,),
        ).fetchone()[0]
        edges = _graph_count(kuzu, f"MATCH ()-[r:{rtd.name}]->() RETURN count(r)")
        out["relations"][rtd.name] = {"sqlite": rows, "graph": edges}
    return out


def _stderr(line: str) -> None:
    print(line, file=sys.stderr)


def rebuild_graph(db_path: Path, progress: Any = _stderr) -> dict[str, Any]:
    """Recreates the graph tier from SQLite: every object as a node, every relation as an edge.

    The current graph files go into ``graph-backup-<time>/`` under the database.
    """
    from grizabella.api.client import Grizabella

    sqlite_file = db_path / SQLITE_DIR_NAME / SQLITE_DB_FILENAME
    if not sqlite_file.is_file():
        msg = f"No SQLite tier at {sqlite_file}: nothing to rebuild from."
        raise FileNotFoundError(msg)

    moved = []
    existing = _graph_files(db_path)
    if existing:
        backup = db_path / f"graph-backup-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        backup.mkdir()
        for path in existing:
            shutil.move(str(path), str(backup / path.name))
            moved.append(str(backup / path.name))
        progress(f"Moved the old graph files into {backup}")

    started = time.monotonic()
    report: dict[str, Any] = {"moved": moved, "nodes": {}, "edges": {}, "failed_nodes": 0, "failed_edges": 0}
    gb = Grizabella(db_name_or_path=db_path, create_if_not_exists=False)
    gb.connect()
    try:
        mgr = gb._db_manager  # pylint: disable=protected-access
        helper = mgr._connection_helper  # pylint: disable=protected-access
        sqlite = helper.sqlite_adapter
        kuzu = helper.kuzu_adapter

        for otd in mgr.list_object_type_definitions():
            done = 0
            offset = 0
            while True:
                page = sqlite.query_object_instances(otd.name, {}, limit=PAGE_SIZE, offset=offset)
                if not page:
                    break
                for obj in page:
                    try:
                        kuzu.upsert_object_instance(obj)
                        done += 1
                    except Exception as e:  # pylint: disable=broad-except
                        report["failed_nodes"] += 1
                        logger.error("Node %s (%s) failed: %s", obj.id, otd.name, e)
                offset += len(page)
            report["nodes"][otd.name] = done
            progress(f"  {otd.name}: {done} nodes")

        for rtd in mgr.list_relation_type_definitions():
            done = 0
            for rel in sqlite.find_relation_instances(relation_type_name=rtd.name):
                try:
                    kuzu.upsert_relation_instance(rel, rtd)
                    done += 1
                except Exception as e:  # pylint: disable=broad-except
                    report["failed_edges"] += 1
                    logger.error("Edge %s (%s) failed: %s", rel.id, rtd.name, e)
            report["edges"][rtd.name] = done
            progress(f"  {rtd.name}: {done} edges")

        kuzu.checkpoint()
        report["verify"] = graph_stats(gb)
    finally:
        gb.close()
    report["seconds"] = round(time.monotonic() - started, 1)
    return report


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point of ``grizabella-maintain``; returns the exit status."""
    parser = argparse.ArgumentParser(
        prog="grizabella-maintain",
        description="Offline maintenance of a Grizabella database. Stop every engine using it first.",
    )
    parser.add_argument("--db-path", required=True, help="The database directory (as given to grizabella-mcp --db-path).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log to stderr.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stats", help="Vector-table and graph-tier statistics.")
    compact = sub.add_parser("compact", help="Compact the vector tables and drop old versions.")
    compact.add_argument("--table", help="Only this table (default: all).")
    compact.add_argument(
        "--keep-versions-for", type=float, default=0.0, metavar="SECONDS",
        help="Keep versions younger than this (default 0: only the latest survives).",
    )
    sub.add_parser("rebuild-graph", help="Recreate the graph tier from SQLite (the old one is moved aside).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, stream=sys.stderr)
    # The background compaction thread has no business in a one-shot tool.
    os.environ.setdefault("GRIZABELLA_LANCEDB_MAINTENANCE_INTERVAL_S", "0")

    db_path = Path(args.db_path).expanduser().resolve()
    if not db_path.is_dir():
        print(f"No database at {db_path}", file=sys.stderr)
        return 2

    if args.command == "stats":
        from grizabella.api.client import Grizabella

        out: dict[str, Any] = {"vector_tables": vector_table_stats(db_path)}
        if _graph_files(db_path):
            try:
                gb = Grizabella(db_name_or_path=db_path, create_if_not_exists=False)
                gb.connect()
                try:
                    out["graph"] = graph_stats(gb)
                finally:
                    gb.close()
            except Exception as e:  # pylint: disable=broad-except
                out["graph"] = {"error": str(e)}
        else:
            out["graph"] = {"error": "no graph database"}
        _print_json(out)
        return 0
    if args.command == "compact":
        _print_json(compact_vector_store(db_path, args.table, args.keep_versions_for))
        return 0
    if args.command == "rebuild-graph":
        report = rebuild_graph(db_path)
        _print_json(report)
        mismatched = {
            kind: {name: c for name, c in counts.items() if c["sqlite"] != c["graph"]}
            for kind, counts in report.get("verify", {}).items()
        }
        if any(mismatched.values()):
            print(f"Graph and SQLite disagree: {mismatched}", file=sys.stderr)
            return 1
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
