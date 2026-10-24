# Changelog

## 0.8.1

The vector store is maintained instead of growing one fragment per write.

- **Upserts replace the object's row in one commit** (`merge_insert` on
  `object_instance_id`). Every write used to delete the row and append a new
  one: two commits, a one-row fragment, and a manifest listing every fragment.
  Bulk upserts also replace rather than duplicate, and keep one row per object
  when a batch names it twice.
- **Tables are compacted** after 64 writes, or by a background pass once writes
  have been quiet for five minutes, and versions older than ten minutes are
  removed. One knowledge base had reached 5,973 one-row fragments and 8,936
  manifests (3.2 GB, for 25 MB of vectors); a search took 184 ms and about one
  upsert in ten stalled for 30 s in Lance's own auto-cleanup. Compacted: 1
  fragment and 26 MB; LanceDB's part of a search 7 ms, of an upsert 8 ms.
- **A vector index is built at 50,000 rows** (`IVF_FLAT`, squared L2, so
  distances stay exact and in the unit unindexed searches have always used),
  probing half its partitions; it is rebuilt when the table wants twice the
  partitions or the index has piled up delta segments. The old code would have
  built an `IVF_PQ` cosine index at 999,999 rows, changing the distance metric
  under its callers. At 6,000 rows a flat scan takes 3 ms and is exact, while
  IVF_FLAT missed 3% of the top 52 and HNSW 21%.
- Settings: `GRIZABELLA_LANCEDB_COMPACT_AFTER_WRITES`,
  `_MAINTENANCE_INTERVAL_S` (0 disables the background pass),
  `_MAINTENANCE_IDLE_S`, `_CLEANUP_OLDER_THAN_S`, `_INDEX_MIN_ROWS`, or the same
  names (lower case) in the adapter's `config`.
- **`grizabella-maintain`**: `stats`, `compact` (the one-off for a database
  written by an earlier version) and `rebuild-graph` (recreates the graph tier
  from SQLite, moving the old files into `graph-backup-<time>/`; the way across
  a LadybugDB storage-format change).
- **`find_objects` takes `properties`**: return only the named properties of
  each object (id, weight and upsert date always come back). Seven short
  fields of 6,000 knowledge entries over MCP: 2 MB in 0.5 s, against 36 MB in
  55 s for whole rows on the same (busy) machine. Engines before 0.8.1 reject
  the argument ("Unexpected keyword argument").
- `find_similar` asks LanceDB for ids and distances only; the vectors it used to
  return and discard were 80% of the time of an 800-hit search.
- New client method and MCP tool `optimize_embeddings`.
- A failed re-embedding removes the object's old vector instead of leaving it
  to match the old text (the delete used to come first, unconditionally).
- Graph: a relation endpoint whose id exists in several node tables (a schema
  migrated to a new type keeps its ids) is resolved among the relation's own
  declared types, not by whichever table the id was written to last.

## 0.8.0

- LadybugDB 0.20.4 (storage format 47; databases written by 0.17.x need their
  graph tier recreated).
- The WAL self-heal leaves the WAL alone on a storage-format mismatch.
