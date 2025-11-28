"""Unit tests for GrizabellaDBManager relation instance management."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal

from grizabella.core.db_manager import GrizabellaDBManager
from grizabella.core.models import (
    RelationInstance,
    RelationTypeDefinition,
    PropertyDefinition,
    PropertyDataType,
    ObjectInstance, # Needed for creating source/target for RelationInstance
    ObjectTypeDefinition # Needed for creating source/target for RelationInstance
)
from grizabella.core.exceptions import InstanceError, SchemaError, DatabaseError


@pytest.fixture
def mock_sqlite_adapter():
    return MagicMock()

@pytest.fixture
def mock_lancedb_adapter():
    return MagicMock()

@pytest.fixture
def mock_kuzu_adapter():
    return MagicMock()

@pytest.fixture
def mock_connection_helper(mock_sqlite_adapter, mock_lancedb_adapter, mock_kuzu_adapter):
    helper = MagicMock()
    helper.sqlite_adapter = mock_sqlite_adapter
    helper.lancedb_adapter = mock_lancedb_adapter
    helper.kuzu_adapter = mock_kuzu_adapter
    helper.is_connected = True
    return helper

@pytest.fixture
def mock_schema_manager():
    manager = MagicMock()
    # Setup mock return values for schema manager methods if needed by _InstanceManager
    # For these tests, _InstanceManager methods are directly mocked, so deep schema mocking might not be needed.
    # However, if _InstanceManager calls _schema_manager.get_relation_type_definition, we need to mock it.
    mock_rtd = RelationTypeDefinition(
        name="WORKS_AT",
        source_object_type_names=["Person"],
        target_object_type_names=["Company"],
        properties=[]
    )
    manager.get_relation_type_definition.return_value = mock_rtd
    manager.get_object_type_definition.return_value = ObjectTypeDefinition(name="Dummy", properties=[]) # Generic OTD
    return manager

@pytest.fixture
def mock_instance_manager():
    return MagicMock()

@pytest.fixture
def db_manager_mocked_helpers(mock_connection_helper, mock_schema_manager, mock_instance_manager):
    with patch('grizabella.core.db_manager._ConnectionHelper', return_value=mock_connection_helper), \
         patch('grizabella.core.db_manager._SchemaManager', return_value=mock_schema_manager), \
         patch('grizabella.core.db_manager._InstanceManager', return_value=mock_instance_manager):
        # Patch db_paths to avoid actual file system operations during GrizabellaDBManager init
        with patch('grizabella.core.db_paths.get_db_instance_path', return_value=MagicMock(name="mock_db_instance_root")), \
             patch('grizabella.core.db_paths.get_sqlite_path', return_value="dummy_sqlite.db"), \
             patch('grizabella.core.db_paths.get_lancedb_uri', return_value="dummy_lancedb_uri"), \
             patch('grizabella.core.db_paths.get_kuzu_path', return_value="dummy_kuzu_path"):
            manager = GrizabellaDBManager(db_name_or_path="test_db_relations", create_if_not_exists=False)
            # Ensure manager considers itself connected for these tests
            manager._manager_fully_initialized = True 
            yield manager


@pytest.fixture
def sample_relation_instance() -> RelationInstance:
    return RelationInstance(
        id=uuid4(),
        relation_type_name="WORKS_AT",
        source_object_instance_id=uuid4(),
        target_object_instance_id=uuid4(),
        properties={"role": "Engineer", "years": 2},
        weight=Decimal("0.8"),
        upsert_date=datetime.now()
    )

# --- Test GrizabellaDBManager Relation Methods ---

def test_add_relation_instance_success(db_manager_mocked_helpers: GrizabellaDBManager, sample_relation_instance: RelationInstance, mock_instance_manager: MagicMock):
    mock_instance_manager.add_relation_instance.return_value = sample_relation_instance
    
    result = db_manager_mocked_helpers.add_relation_instance(sample_relation_instance)
    
    mock_instance_manager.add_relation_instance.assert_called_once_with(sample_relation_instance)
    assert result == sample_relation_instance

def test_add_relation_instance_disconnected(db_manager_mocked_helpers: GrizabellaDBManager, sample_relation_instance: RelationInstance):
    db_manager_mocked_helpers._manager_fully_initialized = False # Simulate disconnected
    with pytest.raises(DatabaseError, match="Manager not connected."):
        db_manager_mocked_helpers.add_relation_instance(sample_relation_instance)

def test_add_relation_instance_propagates_schema_error(db_manager_mocked_helpers: GrizabellaDBManager, sample_relation_instance: RelationInstance, mock_instance_manager: MagicMock):
    mock_instance_manager.add_relation_instance.side_effect = SchemaError("RTD not found")
    with pytest.raises(SchemaError, match="RTD not found"):
        db_manager_mocked_helpers.add_relation_instance(sample_relation_instance)

def test_get_relation_instance_found(db_manager_mocked_helpers: GrizabellaDBManager, sample_relation_instance: RelationInstance, mock_instance_manager: MagicMock):
    mock_instance_manager.get_relation_instance.return_value = sample_relation_instance
    relation_type_name = sample_relation_instance.relation_type_name
    relation_id = sample_relation_instance.id
    
    result = db_manager_mocked_helpers.get_relation_instance(relation_type_name, relation_id)
    
    mock_instance_manager.get_relation_instance.assert_called_once_with(relation_type_name, relation_id)
    assert result == sample_relation_instance

def test_get_relation_instance_not_found(db_manager_mocked_helpers: GrizabellaDBManager, mock_instance_manager: MagicMock):
    relation_type_name = "WORKS_AT"
    relation_id = uuid4()
    mock_instance_manager.get_relation_instance.return_value = None
    
    result = db_manager_mocked_helpers.get_relation_instance(relation_type_name, relation_id)
    
    mock_instance_manager.get_relation_instance.assert_called_once_with(relation_type_name, relation_id)
    assert result is None

def test_get_relation_instance_disconnected(db_manager_mocked_helpers: GrizabellaDBManager):
    db_manager_mocked_helpers._manager_fully_initialized = False
    with pytest.raises(DatabaseError, match="Manager not connected."):
        db_manager_mocked_helpers.get_relation_instance("WORKS_AT", uuid4())

def test_delete_relation_instance_success(db_manager_mocked_helpers: GrizabellaDBManager, mock_instance_manager: MagicMock):
    relation_type_name = "WORKS_AT"
    relation_id = uuid4()
    mock_instance_manager.delete_relation_instance.return_value = True
    
    result = db_manager_mocked_helpers.delete_relation_instance(relation_type_name, relation_id)
    
    mock_instance_manager.delete_relation_instance.assert_called_once_with(relation_type_name, relation_id)
    assert result is True

def test_delete_relation_instance_failure(db_manager_mocked_helpers: GrizabellaDBManager, mock_instance_manager: MagicMock):
    relation_type_name = "WORKS_AT"
    relation_id = uuid4()
    mock_instance_manager.delete_relation_instance.return_value = False
    
    result = db_manager_mocked_helpers.delete_relation_instance(relation_type_name, relation_id)
    
    mock_instance_manager.delete_relation_instance.assert_called_once_with(relation_type_name, relation_id)
    assert result is False

def test_delete_relation_instance_disconnected(db_manager_mocked_helpers: GrizabellaDBManager):
    db_manager_mocked_helpers._manager_fully_initialized = False
    with pytest.raises(DatabaseError, match="Manager not connected."):
        db_manager_mocked_helpers.delete_relation_instance("WORKS_AT", uuid4())

def test_find_relation_instances_success(db_manager_mocked_helpers: GrizabellaDBManager, sample_relation_instance: RelationInstance, mock_instance_manager: MagicMock):
    mock_instance_manager.find_relation_instances.return_value = [sample_relation_instance]
    
    relation_type_name = "WORKS_AT"
    src_id = uuid4()
    
    result = db_manager_mocked_helpers.find_relation_instances(
        relation_type_name=relation_type_name,
        source_object_id=src_id,
        limit=10
    )
    
    mock_instance_manager.find_relation_instances.assert_called_once_with(
        relation_type_name=relation_type_name,
        source_object_id=src_id,
        target_object_id=None,
        query=None,
        limit=10
    )
    assert result == [sample_relation_instance]

def test_find_relation_instances_disconnected(db_manager_mocked_helpers: GrizabellaDBManager):
    db_manager_mocked_helpers._manager_fully_initialized = False
    with pytest.raises(DatabaseError, match="Manager not connected."):
        db_manager_mocked_helpers.find_relation_instances(relation_type_name="WORKS_AT")

def test_find_relation_instances_propagates_error(db_manager_mocked_helpers: GrizabellaDBManager, mock_instance_manager: MagicMock):
    mock_instance_manager.find_relation_instances.side_effect = InstanceError("Kuzu query failed")
    with pytest.raises(InstanceError, match="Kuzu query failed"):
        db_manager_mocked_helpers.find_relation_instances(relation_type_name="WORKS_AT")