"""The open-time WAL self-heal must not fire on a storage-format mismatch.

A torn WAL and an engine upgrade both surface as "the database would not open",
but only one of them is fixed by throwing the WAL away. On a version mismatch the
WAL is the one thing still intact — the previous ladybug can replay it — so
quarantining it converts a reversible upgrade into data loss.
"""
from grizabella.db_layers.kuzu.thread_safe_kuzu_adapter import (
    ThreadSafeKuzuAdapter,
    _is_storage_version_mismatch,
)

VERSION_MISMATCH = RuntimeError(
    "Runtime exception: Trying to read a database file with a different version. "
    "Database file version: 39, Current build storage version: 47"
)
TORN_WAL = RuntimeError("Runtime exception: Corrupted wal file. Read out invalid WAL record type.")


class _Probe(ThreadSafeKuzuAdapter):
    """Just enough object to exercise the recovery decision, with no engine."""

    def __init__(self, db_path: str) -> None:  # noqa: D107 - deliberately skips super()
        self._db_path = db_path


def _db_with_wal(tmp_path):
    db = tmp_path / "kuzu_data.db"
    db.write_bytes(b"\0" * 4096)
    wal = tmp_path / "kuzu_data.db.wal"
    wal.write_bytes(b"torn-wal-payload")
    return db, wal


def test_predicate_separates_the_two_failures():
    assert _is_storage_version_mismatch(VERSION_MISMATCH)
    assert not _is_storage_version_mismatch(TORN_WAL)
    assert not _is_storage_version_mismatch(RuntimeError("Could not acquire lock"))


def test_torn_wal_is_quarantined(tmp_path):
    db, wal = _db_with_wal(tmp_path)
    probe = _Probe(str(db))

    assert probe._recover_from_corrupt_wal(TORN_WAL) is True
    assert not wal.exists(), "a torn WAL should be moved aside so the retry can open"
    assert (tmp_path / "kuzu_data.db.wal.corrupt").exists()


def test_version_mismatch_leaves_the_wal_alone(tmp_path):
    db, wal = _db_with_wal(tmp_path)
    before = wal.read_bytes()
    probe = _Probe(str(db))

    assert probe._recover_from_corrupt_wal(VERSION_MISMATCH) is False, (
        "reporting recovery would make the caller retry an open that cannot succeed"
    )
    assert wal.exists(), "the WAL is intact here — the OLD engine can still replay it"
    assert wal.read_bytes() == before
    assert not (tmp_path / "kuzu_data.db.wal.corrupt").exists()
