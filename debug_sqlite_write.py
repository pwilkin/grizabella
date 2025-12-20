import os
import shutil
import sqlite3
from pathlib import Path

db_path = (Path.cwd() / "bulk_test_db").resolve()
print(f"DB Root Path: {db_path}")

if db_path.exists():
    shutil.rmtree(db_path)

db_path.mkdir(parents=True, exist_ok=True)
sqlite_dir = db_path / "sqlite_data"
sqlite_dir.mkdir(parents=True, exist_ok=True)
db_file = sqlite_dir / "grizabella.db"
print(f"DB File Path: {db_file}")

try:
    conn = sqlite3.connect(str(db_file))
    print("Connection opened.")
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO test (id) VALUES (1)")
    conn.commit()
    print("Write successful.")
    conn.close()
except Exception as e:
    print(f"Failed: {e}")

# Check permissions
print(f"CWD: {os.getcwd()}")
print(f"CWD stats: {os.stat('.')}")
if db_file.exists():
    print(f"DB file stats: {os.stat(db_file)}")
print(f"SQLite dir stats: {os.stat(sqlite_dir)}")
print(f"DB Root stats: {os.stat(db_path)}")
