import pytest
import sqlite3
from pathlib import Path
from uuid import uuid4, UUID
from datetime import datetime, timezone, timedelta # Added timedelta
from decimal import Decimal
from typing import Iterator # Added Iterator for fixture typing

from grizabella.core.models import (
    ObjectTypeDefinition,
    PropertyDefinition,
    PropertyDataType,
    ObjectInstance,
    EmbeddingDefinition,
    RelationTypeDefinition,
    MemoryInstance,
)
from grizabella.core.query_models import RelationalFilter # Added
from grizabella.db_layers.sqlite.sqlite_adapter import SQLiteAdapter
from grizabella.core.exceptions import DatabaseError, SchemaError, InstanceError

# --- Fixtures ---

@pytest.fixture
def in_memory_adapter() -> Iterator[SQLiteAdapter]: # Changed type hint
    """Provides an SQLiteAdapter connected to an in-memory database."""
    adapter = SQLiteAdapter(db_path=":memory:")
    yield adapter
    adapter.close()

@pytest.fixture
def file_based_adapter(tmp_path: Path) -> Iterator[SQLiteAdapter]: # Changed type hint
    """Provides an SQLiteAdapter connected to a temporary file-based database."""
    db_file = tmp_path / "test_grizabella.db"
    adapter = SQLiteAdapter(db_path=str(db_file))
    yield adapter
    adapter.close()

@pytest.fixture
def sample_otd_document() -> ObjectTypeDefinition:
    return ObjectTypeDefinition(
        name="TestDocument",
        description="A test document type.",
        properties=[
            PropertyDefinition(name="title", data_type=PropertyDataType.TEXT, is_nullable=False),
            PropertyDefinition(name="content", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="page_count", data_type=PropertyDataType.INTEGER, is_nullable=True, is_indexed=True),
            PropertyDefinition(name="version", data_type=PropertyDataType.FLOAT, is_nullable=True),
            PropertyDefinition(name="is_published", data_type=PropertyDataType.BOOLEAN, is_nullable=True),
            PropertyDefinition(name="published_at", data_type=PropertyDataType.DATETIME, is_nullable=True),
            PropertyDefinition(name="metadata", data_type=PropertyDataType.JSON, is_nullable=True),
            PropertyDefinition(name="unique_code", data_type=PropertyDataType.TEXT, is_unique=True, is_nullable=True),
            PropertyDefinition(name="attachment", data_type=PropertyDataType.BLOB, is_nullable=True),
            PropertyDefinition(name="external_id", data_type=PropertyDataType.UUID, is_nullable=True),
        ]
    )

@pytest.fixture
def sample_otd_author() -> ObjectTypeDefinition:
    return ObjectTypeDefinition(
        name="Author",
        properties=[
            PropertyDefinition(name="name", data_type=PropertyDataType.TEXT, is_nullable=False, is_indexed=True),
            PropertyDefinition(name="email", data_type=PropertyDataType.TEXT, is_unique=True),
        ]
    )

@pytest.fixture
def sample_embedding_def(sample_otd_document: ObjectTypeDefinition) -> EmbeddingDefinition:
    return EmbeddingDefinition(
        name="doc_content_embedding",
        object_type_name=sample_otd_document.name,
        source_property_name="content",
        embedding_model="test_model",
        dimensions=128
    )

@pytest.fixture
def sample_relation_def(sample_otd_document: ObjectTypeDefinition, sample_otd_author: ObjectTypeDefinition) -> RelationTypeDefinition:
    return RelationTypeDefinition(
        name="AUTHORED_BY",
        source_object_type_names=[sample_otd_document.name],
        target_object_type_names=[sample_otd_author.name],
        properties=[
            PropertyDefinition(name="role", data_type=PropertyDataType.TEXT)
        ]
    )

# --- Test Cases ---

class TestSQLiteAdapterConnection:
    def test_connect_in_memory(self, in_memory_adapter: SQLiteAdapter):
        assert in_memory_adapter.conn is not None
        assert in_memory_adapter.db_path == ":memory:"

    def test_connect_file_based(self, file_based_adapter: SQLiteAdapter, tmp_path: Path):
        assert file_based_adapter.conn is not None
        expected_path = tmp_path / "test_grizabella.db"
        assert file_based_adapter.db_path == str(expected_path)
        assert expected_path.exists()

    def test_close_connection(self, in_memory_adapter: SQLiteAdapter):
        in_memory_adapter.close()
        assert in_memory_adapter.conn is None
        with pytest.raises(DatabaseError, match="SQLite connection not established."):
            in_memory_adapter.save_object_type_definition(
                ObjectTypeDefinition(name="Fail", properties=[])
            )

    def test_init_meta_tables(self, in_memory_adapter: SQLiteAdapter):
        assert in_memory_adapter.conn is not None # Ensure connection
        cursor = in_memory_adapter.conn.cursor()
        tables = [
            SQLiteAdapter._META_TABLE_OBJECT_TYPES,
            SQLiteAdapter._META_TABLE_EMBEDDING_DEFS,
            SQLiteAdapter._META_TABLE_RELATION_TYPES,
        ]
        for table_name in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            assert cursor.fetchone() is not None, f"Metadata table '{table_name}' was not created."

class TestSQLiteSchemaDefinitionPersistence:
    def test_save_load_object_type_definition(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        in_memory_adapter.save_object_type_definition(sample_otd_document)
        loaded_otd = in_memory_adapter.load_object_type_definition(sample_otd_document.name)
        assert loaded_otd is not None
        assert loaded_otd.name == sample_otd_document.name
        assert loaded_otd.properties == sample_otd_document.properties
        assert loaded_otd.model_dump() == sample_otd_document.model_dump()


    def test_load_non_existent_object_type_definition(self, in_memory_adapter: SQLiteAdapter):
        assert in_memory_adapter.load_object_type_definition("NonExistent") is None

    def test_delete_object_type_definition(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        in_memory_adapter.save_object_type_definition(sample_otd_document)
        assert in_memory_adapter.delete_object_type_definition(sample_otd_document.name) is True
        assert in_memory_adapter.load_object_type_definition(sample_otd_document.name) is None
        assert in_memory_adapter.delete_object_type_definition(sample_otd_document.name) is False # Already deleted

    def test_list_object_type_definitions(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition, sample_otd_author: ObjectTypeDefinition):
        assert in_memory_adapter.list_object_type_definitions() == []
        in_memory_adapter.save_object_type_definition(sample_otd_document)
        in_memory_adapter.save_object_type_definition(sample_otd_author)
        
        defs = in_memory_adapter.list_object_type_definitions()
        assert len(defs) == 2
        assert any(d.name == sample_otd_document.name for d in defs)
        assert any(d.name == sample_otd_author.name for d in defs)

    # Similar tests for EmbeddingDefinition
    def test_save_load_embedding_definition(self, in_memory_adapter: SQLiteAdapter, sample_embedding_def: EmbeddingDefinition):
        in_memory_adapter.save_embedding_definition(sample_embedding_def)
        loaded_ed = in_memory_adapter.load_embedding_definition(sample_embedding_def.name)
        assert loaded_ed is not None
        assert loaded_ed.model_dump() == sample_embedding_def.model_dump()

    def test_delete_list_embedding_definitions(self, in_memory_adapter: SQLiteAdapter, sample_embedding_def: EmbeddingDefinition):
        in_memory_adapter.save_embedding_definition(sample_embedding_def)
        assert len(in_memory_adapter.list_embedding_definitions()) == 1
        in_memory_adapter.delete_embedding_definition(sample_embedding_def.name)
        assert in_memory_adapter.load_embedding_definition(sample_embedding_def.name) is None
        assert len(in_memory_adapter.list_embedding_definitions()) == 0

    # Similar tests for RelationTypeDefinition
    def test_save_load_relation_type_definition(self, in_memory_adapter: SQLiteAdapter, sample_relation_def: RelationTypeDefinition):
        in_memory_adapter.save_relation_type_definition(sample_relation_def)
        loaded_rtd = in_memory_adapter.load_relation_type_definition(sample_relation_def.name)
        assert loaded_rtd is not None
        assert loaded_rtd.model_dump() == sample_relation_def.model_dump()

    def test_delete_list_relation_type_definitions(self, in_memory_adapter: SQLiteAdapter, sample_relation_def: RelationTypeDefinition):
        in_memory_adapter.save_relation_type_definition(sample_relation_def)
        assert len(in_memory_adapter.list_relation_type_definitions()) == 1
        in_memory_adapter.delete_relation_type_definition(sample_relation_def.name)
        assert in_memory_adapter.load_relation_type_definition(sample_relation_def.name) is None
        assert len(in_memory_adapter.list_relation_type_definitions()) == 0


class TestSQLiteSchemaTableManagement:
    def test_create_object_type_table(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        in_memory_adapter.create_object_type_table(sample_otd_document)
        table_name = in_memory_adapter._get_safe_table_name(sample_otd_document.name)
        
        assert in_memory_adapter.conn is not None # Ensure connection
        cursor = in_memory_adapter.conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        columns_info = {row['name']: row for row in cursor.fetchall()}

        # Check MemoryInstance fields
        assert "id" in columns_info and columns_info["id"]["pk"] == 1 and columns_info["id"]["type"] == "TEXT"
        assert "weight" in columns_info and columns_info["weight"]["type"] == "REAL" and columns_info["weight"]["notnull"] == 1
        assert "upsert_date" in columns_info and columns_info["upsert_date"]["type"] == "TEXT" and columns_info["upsert_date"]["notnull"] == 1
        
        # Check properties from OTD
        for prop in sample_otd_document.properties:
            assert prop.name in columns_info
            expected_sqlite_type = in_memory_adapter._map_property_type_to_sqlite(prop.data_type)
            assert columns_info[prop.name]["type"] == expected_sqlite_type
            if not prop.is_nullable:
                assert columns_info[prop.name]["notnull"] == 1
            # SQLite PRAGMA doesn't directly show UNIQUE constraint this way for non-PK, need to check indices or insert attempts

        # Check index creation
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}' AND name='idx_{table_name}_page_count';")
        assert cursor.fetchone() is not None, "Index for page_count was not created."

    def test_drop_object_type_table(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        in_memory_adapter.create_object_type_table(sample_otd_document)
        table_name = in_memory_adapter._get_safe_table_name(sample_otd_document.name)
        
        in_memory_adapter.drop_object_type_table(sample_otd_document.name)
        
        assert in_memory_adapter.conn is not None # Ensure connection
        cursor = in_memory_adapter.conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        assert cursor.fetchone() is None, f"Table '{table_name}' was not dropped."

    def test_create_table_idempotency(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        in_memory_adapter.create_object_type_table(sample_otd_document)
        try:
            in_memory_adapter.create_object_type_table(sample_otd_document) # Call again
        except Exception as e:
            pytest.fail(f"Calling create_object_type_table again raised an exception: {e}")


class TestSQLiteObjectInstanceOperations:
    @pytest.fixture(autouse=True)
    def setup_otd_table(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        """Ensure the OTD and its table exist before each test in this class."""
        in_memory_adapter.save_object_type_definition(sample_otd_document) # Needed for instance methods
        in_memory_adapter.create_object_type_table(sample_otd_document)

    def test_add_get_object_instance(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        now = datetime.now(timezone.utc).replace(microsecond=0) # Normalize for comparison
        instance_id = uuid4()
        instance = ObjectInstance(
            id=instance_id,
            object_type_name=sample_otd_document.name,
            weight=Decimal("0.75"),
            upsert_date=now,
            properties={
                "title": "Test Title",
                "content": "Test content.",
                "page_count": 10,
                "version": 1.2,
                "is_published": True,
                "published_at": now,
                "metadata": {"key": "value", "num": 123},
                "unique_code": "CODE001",
                "attachment": b"some binary data",
                "external_id": uuid4()
            }
        )
        in_memory_adapter.add_object_instance(instance)
        
        loaded_instance = in_memory_adapter.get_object_instance(sample_otd_document.name, instance_id)
        assert loaded_instance is not None
        assert loaded_instance.id == instance_id
        assert loaded_instance.object_type_name == sample_otd_document.name
        assert loaded_instance.weight == instance.weight # Explicitly check weight
        assert loaded_instance.upsert_date.replace(tzinfo=None) == instance.upsert_date.replace(tzinfo=None) # Explicitly check upsert_date

        for key, value in instance.properties.items():
            loaded_value = loaded_instance.properties[key]
            if isinstance(value, datetime):
                # SQLite stores datetime as text, precision might differ slightly or TZ info lost
                assert loaded_value.replace(tzinfo=None) == value.replace(tzinfo=None)
            elif isinstance(value, float):
                 assert abs(loaded_value - value) < 0.00001 # Float comparison
            else:
                assert loaded_value == value
    
    def test_get_non_existent_instance(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        assert in_memory_adapter.get_object_instance(sample_otd_document.name, uuid4()) is None

    def test_add_instance_missing_otd_def(self, in_memory_adapter: SQLiteAdapter):
        # Temporarily remove OTD to test behavior
        in_memory_adapter.delete_object_type_definition("TestDocument") # sample_otd_document.name
        
        instance = ObjectInstance(id=uuid4(), object_type_name="TestDocument", properties={"title": "X"})
        with pytest.raises(SchemaError, match="ObjectTypeDefinition 'TestDocument' not found"):
            in_memory_adapter.add_object_instance(instance)

    def test_update_object_instance(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        instance_id = uuid4()
        original_instance = ObjectInstance(
            id=instance_id, object_type_name=sample_otd_document.name,
            weight=Decimal("0.5"), # Original weight
            upsert_date=datetime.now(timezone.utc) - timedelta(days=1), # Original date
            properties={"title": "Original Title", "page_count": 5}
        )
        in_memory_adapter.add_object_instance(original_instance)

        # Simulate time passing before update
        # time.sleep(0.01) # Not strictly needed if we set upsert_date explicitly
        
        new_upsert_date = datetime.now(timezone.utc).replace(microsecond=0)
        updated_instance_data = ObjectInstance(
            id=instance_id, object_type_name=sample_otd_document.name,
            weight=Decimal("0.9"), # Updated weight
            upsert_date=new_upsert_date, # Updated date
            properties={"title": "Updated Title", "page_count": 15, "content": "New content"}
        )
        in_memory_adapter.update_object_instance(updated_instance_data)

        loaded_instance = in_memory_adapter.get_object_instance(sample_otd_document.name, instance_id)
        assert loaded_instance is not None
        assert loaded_instance.properties["title"] == "Updated Title"
        assert loaded_instance.properties["page_count"] == 15
        assert loaded_instance.properties.get("content") == "New content" # Check added property
        assert loaded_instance.weight == Decimal("0.9") # Assert updated weight
        assert loaded_instance.upsert_date.replace(tzinfo=None) == new_upsert_date.replace(tzinfo=None) # Assert updated upsert_date

    def test_update_non_existent_instance(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        instance = ObjectInstance(id=uuid4(), object_type_name=sample_otd_document.name, properties={"title": "X"})
        with pytest.raises(InstanceError, match="not found in .* for update"):
            in_memory_adapter.update_object_instance(instance)

    def test_delete_object_instance(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        instance_id = uuid4()
        instance = ObjectInstance(id=instance_id, object_type_name=sample_otd_document.name, properties={"title": "To Delete"})
        in_memory_adapter.add_object_instance(instance)

        assert in_memory_adapter.delete_object_instance(sample_otd_document.name, instance_id) is True
        assert in_memory_adapter.get_object_instance(sample_otd_document.name, instance_id) is None
        assert in_memory_adapter.delete_object_instance(sample_otd_document.name, instance_id) is False # Already deleted

    def test_delete_instance_from_non_existent_table(self, in_memory_adapter: SQLiteAdapter):
        # Table for "NonExistentType" won't exist
        assert in_memory_adapter.delete_object_instance("NonExistentType", uuid4()) is False


    def test_query_object_instances_simple(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        id1 = uuid4()
        id2 = uuid4()
        inst1 = ObjectInstance(id=id1, object_type_name=sample_otd_document.name, properties={"title": "Query Target", "page_count": 20})
        inst2 = ObjectInstance(id=id2, object_type_name=sample_otd_document.name, properties={"title": "Another Doc", "page_count": 20})
        in_memory_adapter.add_object_instance(inst1)
        in_memory_adapter.add_object_instance(inst2)

        results = in_memory_adapter.query_object_instances(sample_otd_document.name, {"title": "Query Target"})
        assert len(results) == 1
        assert results[0].id == id1

        results_by_page = in_memory_adapter.query_object_instances(sample_otd_document.name, {"page_count": 20})
        assert len(results_by_page) == 2
        assert {res.id for res in results_by_page} == {id1, id2}
        
        results_limit = in_memory_adapter.query_object_instances(sample_otd_document.name, {"page_count": 20}, limit=1)
        assert len(results_limit) == 1


    def test_query_object_instances_multiple_conditions(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        id1 = uuid4()
        inst1 = ObjectInstance(id=id1, object_type_name=sample_otd_document.name, properties={"title": "MultiCond", "page_count": 30, "is_published": True})
        in_memory_adapter.add_object_instance(inst1)
        # Add another that doesn't match all
        in_memory_adapter.add_object_instance(ObjectInstance(id=uuid4(), object_type_name=sample_otd_document.name, properties={"title": "MultiCond", "page_count": 30, "is_published": False}))


        results = in_memory_adapter.query_object_instances(sample_otd_document.name, {"title": "MultiCond", "is_published": True})
        assert len(results) == 1
        assert results[0].id == id1

    def test_query_no_results(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        results = in_memory_adapter.query_object_instances(sample_otd_document.name, {"title": "NonExistentTitle"})
        assert len(results) == 0

    def test_query_by_base_field_id(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        instance_id = uuid4()
        instance = ObjectInstance(id=instance_id, object_type_name=sample_otd_document.name, properties={"title": "QueryByID"})
        in_memory_adapter.add_object_instance(instance)

        results = in_memory_adapter.query_object_instances(sample_otd_document.name, {"id": instance_id})
        assert len(results) == 1
        assert results[0].id == instance_id

    def test_upsert_object_instance(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        instance_id = uuid4()
        initial_date = (datetime.now(timezone.utc) - timedelta(seconds=10)).replace(microsecond=0)
        
        # First upsert (insert)
        instance_v1 = ObjectInstance(
            id=instance_id, object_type_name=sample_otd_document.name,
            weight=Decimal("0.6"),
            upsert_date=initial_date,
            properties={"title": "Upsert V1", "page_count": 1}
        )
        upserted_v1 = in_memory_adapter.upsert_object_instance(instance_v1)
        assert upserted_v1.properties["title"] == "Upsert V1"
        assert upserted_v1.weight == Decimal("0.6")
        # For upsert, the adapter's upsert_object_instance method itself should set the date
        # So, the date in upserted_v1 might be *newer* than initial_date if the method updates it.
        # Let's fetch to confirm persisted date.

        loaded_v1 = in_memory_adapter.get_object_instance(sample_otd_document.name, instance_id)
        assert loaded_v1 is not None
        assert loaded_v1.properties["page_count"] == 1
        assert loaded_v1.weight == Decimal("0.6")
        assert loaded_v1.upsert_date.replace(tzinfo=None) >= initial_date.replace(tzinfo=None) # Should be current time of upsert
        
        date_after_v1_upsert = loaded_v1.upsert_date # Capture the actual upsert date

        # time.sleep(0.01) # Ensure time progresses for next upsert_date check
        
        # Second upsert (update)
        update_date = datetime.now(timezone.utc).replace(microsecond=0)
        instance_v2 = ObjectInstance(
            id=instance_id, object_type_name=sample_otd_document.name,
            weight=Decimal("0.85"),
            upsert_date=update_date, # Provide a new date
            properties={"title": "Upsert V2", "page_count": 2, "content": "Added content"}
        )
        upserted_v2 = in_memory_adapter.upsert_object_instance(instance_v2)
        assert upserted_v2.properties["title"] == "Upsert V2"
        assert upserted_v2.properties["page_count"] == 2
        assert upserted_v2.weight == Decimal("0.85")
        # Again, the adapter's method should control the final upsert_date.

        loaded_v2 = in_memory_adapter.get_object_instance(sample_otd_document.name, instance_id)
        assert loaded_v2 is not None
        assert loaded_v2.properties["title"] == "Upsert V2"
        assert loaded_v2.properties["page_count"] == 2
        assert loaded_v2.properties.get("content") == "Added content"
        assert loaded_v2.weight == Decimal("0.85")
        assert loaded_v2.upsert_date.replace(tzinfo=None) >= date_after_v1_upsert.replace(tzinfo=None)
        assert loaded_v2.upsert_date.replace(tzinfo=None) >= update_date.replace(tzinfo=None) # Should be at or after this time

    def test_add_instance_with_all_property_types(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        instance_id = uuid4()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        external_uuid = uuid4()

        instance = ObjectInstance(
            id=instance_id,
            object_type_name=sample_otd_document.name,
            properties={
                "title": "Full Type Test",
                "content": "Testing all types.",
                "page_count": 101,
                "version": 3.14,
                "is_published": True,
                "published_at": now,
                "metadata": {"complex": True, "data": [1, "a"]},
                "unique_code": "UTC007",
                "attachment": b"\x01\x02\x03binary\x04",
                "external_id": external_uuid
            }
        )
        in_memory_adapter.add_object_instance(instance)
        loaded = in_memory_adapter.get_object_instance(sample_otd_document.name, instance_id)
        assert loaded is not None
        assert loaded.properties["title"] == "Full Type Test"
        assert loaded.properties["page_count"] == 101
        assert abs(loaded.properties["version"] - 3.14) < 0.00001
        assert loaded.properties["is_published"] is True
        assert loaded.properties["published_at"].replace(tzinfo=None) == now.replace(tzinfo=None)
        assert loaded.properties["metadata"] == {"complex": True, "data": [1, "a"]}
        assert loaded.properties["unique_code"] == "UTC007"
        assert loaded.properties["attachment"] == b"\x01\x02\x03binary\x04"
        assert loaded.properties["external_id"] == external_uuid

    def test_add_instance_with_null_values(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        instance_id = uuid4()
        instance = ObjectInstance(
            id=instance_id,
            object_type_name=sample_otd_document.name,
            properties={
                "title": "Test Nulls", # Non-nullable
                "content": None,
                "page_count": None,
                # ... other nullable fields can be None or omitted if default is None in Pydantic model
            }
        )
        in_memory_adapter.add_object_instance(instance)
        loaded = in_memory_adapter.get_object_instance(sample_otd_document.name, instance_id)
        assert loaded is not None
        assert loaded.properties["title"] == "Test Nulls"
        assert loaded.properties["content"] is None
        assert loaded.properties["page_count"] is None

    def test_add_instance_violating_not_null(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        instance_id = uuid4()
        instance = ObjectInstance(
            id=instance_id,
            object_type_name=sample_otd_document.name,
            properties={"title": None} # title is not nullable
        )
        with pytest.raises(InstanceError) as excinfo: # Changed from DatabaseError to InstanceError based on adapter code
            in_memory_adapter.add_object_instance(instance)
        assert "NOT NULL constraint failed" in str(excinfo.value) or "Integrity error" in str(excinfo.value)


    def test_add_instance_violating_unique(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        id1 = uuid4()
        inst1 = ObjectInstance(id=id1, object_type_name=sample_otd_document.name, properties={"title":"UniqueTest1", "unique_code": "UNIQUE123"})
        in_memory_adapter.add_object_instance(inst1)

        id2 = uuid4()
        inst2 = ObjectInstance(id=id2, object_type_name=sample_otd_document.name, properties={"title":"UniqueTest2", "unique_code": "UNIQUE123"}) # Same unique_code
        with pytest.raises(InstanceError) as excinfo: # Changed from DatabaseError to InstanceError
            in_memory_adapter.add_object_instance(inst2)
        assert "UNIQUE constraint failed" in str(excinfo.value) or "Integrity error" in str(excinfo.value)

# Placeholder for BaseDBAdapter abstract methods if they were to be tested directly on SQLiteAdapter
# For example, `create_object_type`, `get_object_type`, etc. are compositions of
# `save_object_type_definition`, `create_object_type_table` etc.
# These are implicitly tested via the GrizabellaDBManager or if one were to call them directly.

class TestSQLiteAdapterBaseOverrides:
    def test_create_get_delete_list_object_type_via_base_methods(
        self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition
    ):
        # Test create_object_type (combines save_definition and create_table)
        in_memory_adapter.create_object_type(sample_otd_document)
        
        # Test get_object_type
        loaded_otd = in_memory_adapter.get_object_type(sample_otd_document.name)
        assert loaded_otd is not None
        assert loaded_otd.name == sample_otd_document.name

        # Check table exists
        table_name = in_memory_adapter._get_safe_table_name(sample_otd_document.name)
        assert in_memory_adapter.conn is not None # Ensure connection
        cursor = in_memory_adapter.conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        assert cursor.fetchone() is not None

        # Test list_object_types
        types_list = in_memory_adapter.list_object_types()
        assert len(types_list) == 1
        assert types_list[0] == sample_otd_document.name

        # Test delete_object_type (combines drop_table and delete_definition)
        in_memory_adapter.delete_object_type(sample_otd_document.name)
        assert in_memory_adapter.get_object_type(sample_otd_document.name) is None
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        assert cursor.fetchone() is None
        assert in_memory_adapter.list_object_types() == []

    def test_add_get_embedding_definition_via_base_methods(
        self, in_memory_adapter: SQLiteAdapter, sample_embedding_def: EmbeddingDefinition
    ):
        in_memory_adapter.add_embedding_definition(sample_embedding_def)
        loaded_ed = in_memory_adapter.get_embedding_definition(sample_embedding_def.name)
        assert loaded_ed is not None
        assert loaded_ed.name == sample_embedding_def.name

    # find_object_instances is also a BaseDBAdapter method
    def test_find_object_instances_with_offset(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        # Setup: Ensure OTD and table exist
        in_memory_adapter.create_object_type(sample_otd_document)
    
        ids = [uuid4() for _ in range(5)]
        for i, test_id in enumerate(ids):
            inst = ObjectInstance(id=test_id, object_type_name=sample_otd_document.name,
                                  properties={"title": f"FindOffsetTest", "page_count": i})
            in_memory_adapter.add_object_instance(inst)

        # Query with limit and offset
        results_page1 = in_memory_adapter.find_object_instances(
            sample_otd_document.name, {"title": "FindOffsetTest"}, limit=2, offset=0
        )
        assert len(results_page1) == 2

        results_page2 = in_memory_adapter.find_object_instances(
            sample_otd_document.name, {"title": "FindOffsetTest"}, limit=2, offset=2
        )
        assert len(results_page2) == 2
        
        results_page3 = in_memory_adapter.find_object_instances(
            sample_otd_document.name, {"title": "FindOffsetTest"}, limit=2, offset=4
        )
        assert len(results_page3) == 1 # Only one remaining

        # Ensure no overlap between pages
        ids_page1 = {r.id for r in results_page1}
        ids_page2 = {r.id for r in results_page2}
        assert len(ids_page1.intersection(ids_page2)) == 0


class TestSQLiteAdapterQueryEngineMethods:
    @pytest.fixture(autouse=True)
    def setup_data(self, in_memory_adapter: SQLiteAdapter, sample_otd_document: ObjectTypeDefinition):
        """Setup OTD and some initial data for query engine method tests."""
        in_memory_adapter.create_object_type(sample_otd_document)
        self.adapter = in_memory_adapter
        self.otd_name = sample_otd_document.name

        self.obj1_id = uuid4()
        self.obj2_id = uuid4()
        self.obj3_id = uuid4()
        self.non_existent_id = uuid4()

        self.obj1 = ObjectInstance(id=self.obj1_id, object_type_name=self.otd_name, properties={"title": "Alpha", "page_count": 10, "is_published": True})
        self.obj2 = ObjectInstance(id=self.obj2_id, object_type_name=self.otd_name, properties={"title": "Bravo", "page_count": 20, "is_published": False})
        self.obj3 = ObjectInstance(id=self.obj3_id, object_type_name=self.otd_name, properties={"title": "Alpha", "page_count": 30, "is_published": True}) # Another "Alpha"

        self.adapter.add_object_instance(self.obj1)
        self.adapter.add_object_instance(self.obj2)
        self.adapter.add_object_instance(self.obj3)

    # --- Tests for find_object_ids_by_properties ---
    def test_find_object_ids_by_properties_simple_match(self):
        filters = [RelationalFilter(property_name="title", operator="==", value="Alpha")]
        ids = self.adapter.find_object_ids_by_properties(self.otd_name, filters)
        assert len(ids) == 2
        assert {self.obj1_id, self.obj3_id} == set(ids)

    def test_find_object_ids_by_properties_no_match(self):
        filters = [RelationalFilter(property_name="title", operator="==", value="Charlie")]
        ids = self.adapter.find_object_ids_by_properties(self.otd_name, filters)
        assert len(ids) == 0

    def test_find_object_ids_by_properties_with_initial_ids_filter(self):
        filters = [RelationalFilter(property_name="is_published", operator="==", value=True)]
        initial_ids = [self.obj1_id, self.obj2_id] # obj1 is published, obj2 is not
        
        ids = self.adapter.find_object_ids_by_properties(self.otd_name, filters, initial_ids=initial_ids)
        assert len(ids) == 1
        assert ids[0] == self.obj1_id

    def test_find_object_ids_by_properties_with_empty_initial_ids(self):
        filters = [RelationalFilter(property_name="title", operator="==", value="Alpha")]
        ids = self.adapter.find_object_ids_by_properties(self.otd_name, filters, initial_ids=[])
        assert len(ids) == 0

    def test_find_object_ids_by_properties_with_non_matching_initial_ids(self):
        filters = [RelationalFilter(property_name="title", operator="==", value="Alpha")]
        # obj2 has title "Bravo", so it won't match "Alpha" even if it's in initial_ids
        initial_ids = [self.obj2_id, self.non_existent_id]
        ids = self.adapter.find_object_ids_by_properties(self.otd_name, filters, initial_ids=initial_ids)
        assert len(ids) == 0

    def test_find_object_ids_by_properties_multiple_filters(self):
        filters = [
            RelationalFilter(property_name="title", operator="==", value="Alpha"),
            RelationalFilter(property_name="page_count", operator=">", value=15)
        ] # Should match obj3 (Alpha, 30 pages)
        ids = self.adapter.find_object_ids_by_properties(self.otd_name, filters)
        assert len(ids) == 1
        assert ids[0] == self.obj3_id

    # --- Tests for get_objects_by_ids ---
    def test_get_objects_by_ids_multiple_existing(self):
        ids_to_fetch = [self.obj1_id, self.obj3_id]
        objects = self.adapter.get_objects_by_ids(self.otd_name, ids_to_fetch)
        assert len(objects) == 2
        fetched_ids = {obj.id for obj in objects}
        assert fetched_ids == set(ids_to_fetch)
        # Check if properties are loaded correctly (simple check)
        for obj in objects:
            if obj.id == self.obj1_id:
                assert obj.properties["title"] == "Alpha"
            elif obj.id == self.obj3_id:
                assert obj.properties["title"] == "Alpha"


    def test_get_objects_by_ids_some_non_existent(self):
        ids_to_fetch = [self.obj1_id, self.non_existent_id, self.obj2_id]
        objects = self.adapter.get_objects_by_ids(self.otd_name, ids_to_fetch)
        assert len(objects) == 2 # Only obj1 and obj2 should be found
        fetched_ids = {obj.id for obj in objects}
        assert fetched_ids == {self.obj1_id, self.obj2_id}

    def test_get_objects_by_ids_all_non_existent(self):
        ids_to_fetch = [self.non_existent_id, uuid4()]
        objects = self.adapter.get_objects_by_ids(self.otd_name, ids_to_fetch)
        assert len(objects) == 0

    def test_get_objects_by_ids_empty_list_input(self):
        objects = self.adapter.get_objects_by_ids(self.otd_name, [])
        assert len(objects) == 0

    def test_get_objects_by_ids_duplicate_input_ids(self):
        # Should return unique objects even if IDs are duplicated in input
        ids_to_fetch = [self.obj1_id, self.obj2_id, self.obj1_id]
        objects = self.adapter.get_objects_by_ids(self.otd_name, ids_to_fetch)
        assert len(objects) == 2
        fetched_ids = {obj.id for obj in objects}
        assert fetched_ids == {self.obj1_id, self.obj2_id}