import pytest
import kuzu
import shutil
from pathlib import Path
from typing import Dict, Optional, Any # Added Any
from uuid import uuid4
from datetime import datetime # Added datetime
from unittest.mock import patch, MagicMock # Added MagicMock

from grizabella.core.models import (
    ObjectTypeDefinition,
    ObjectInstance, # Added
    RelationTypeDefinition,
    RelationInstance, # Added
    PropertyDefinition,
    PropertyDataType
)
from grizabella.core.query_models import GraphTraversalClause, RelationalFilter # Added
from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter
from grizabella.core.exceptions import SchemaError # Added InstanceError

# Define a temporary directory for Kuzu database files
TEMP_KUZU_DB_DIR = Path("./temp_kuzu_test_db")

@pytest.fixture(scope="function")
def kuzu_adapter_fixture():
    """
    Fixture to set up and tear down KuzuAdapter with a temporary DB.
    """
    if TEMP_KUZU_DB_DIR.exists():
        shutil.rmtree(TEMP_KUZU_DB_DIR)
    TEMP_KUZU_DB_DIR.mkdir(parents=True, exist_ok=True)
    
    adapter = KuzuAdapter(db_path=str(TEMP_KUZU_DB_DIR))
    yield adapter
    
    adapter.close() 
    if TEMP_KUZU_DB_DIR.exists():
        shutil.rmtree(TEMP_KUZU_DB_DIR)

@pytest.fixture
def sample_otd_person() -> ObjectTypeDefinition:
    return ObjectTypeDefinition(
        name="Person",
        properties=[
            PropertyDefinition(name="name", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="age", data_type=PropertyDataType.INTEGER),
            PropertyDefinition(name="isVerified", data_type=PropertyDataType.BOOLEAN),
            PropertyDefinition(name="score", data_type=PropertyDataType.FLOAT),
            PropertyDefinition(name="created_at", data_type=PropertyDataType.DATETIME),
            PropertyDefinition(name="some_blob", data_type=PropertyDataType.BLOB),
            PropertyDefinition(name="metadata", data_type=PropertyDataType.JSON),
        ]
    )

@pytest.fixture
def sample_otd_organisation() -> ObjectTypeDefinition:
    return ObjectTypeDefinition(
        name="Organisation",
        properties=[
            PropertyDefinition(name="name", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="industry", data_type=PropertyDataType.TEXT),
        ]
    )

@pytest.fixture
def sample_rtd_works_at(sample_otd_person: ObjectTypeDefinition, sample_otd_organisation: ObjectTypeDefinition) -> RelationTypeDefinition:
    return RelationTypeDefinition(
        name="WorksAt",
        source_object_type_names=[sample_otd_person.name],
        target_object_type_names=[sample_otd_organisation.name],
        properties=[
            PropertyDefinition(name="role", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="start_date", data_type=PropertyDataType.DATETIME)
        ]
    )

@pytest.fixture
def sample_person_instance(sample_otd_person: ObjectTypeDefinition) -> ObjectInstance:
    return ObjectInstance(
        id=uuid4(),
        object_type_name=sample_otd_person.name,
        properties={
            "name": "John Doe",
            "age": 30,
            "isVerified": True,
            "score": 75.5,
            "created_at": datetime.now(),
            "metadata": {"email": "john.doe@example.com"}
        }
    )

@pytest.fixture
def sample_org_instance(sample_otd_organisation: ObjectTypeDefinition) -> ObjectInstance:
    return ObjectInstance(
        id=uuid4(),
        object_type_name=sample_otd_organisation.name,
        properties={
            "name": "Acme Corp",
            "industry": "Technology"
        }
    )


@pytest.fixture
def sample_works_at_instance(
    sample_person_instance: ObjectInstance,
    sample_org_instance: ObjectInstance,
    sample_rtd_works_at: RelationTypeDefinition
) -> RelationInstance:
    return RelationInstance(
        id=uuid4(),
        relation_type_name=sample_rtd_works_at.name,
        source_object_instance_id=sample_person_instance.id,
        target_object_instance_id=sample_org_instance.id,
        properties={
            "role": "Engineer",
            "start_date": datetime.now()
        },
        weight=0.9
    )


def get_kuzu_table_schema(conn: kuzu.Connection, table_name: str) -> Dict[str, str]:
    """Helper to get Kuzu table schema for validation."""
    assert conn is not None, "Kuzu connection must be established for get_kuzu_table_schema"
    # Add RETURN * to the CALL statement
    raw_result = conn.execute(f"CALL TABLE_INFO('{table_name}') RETURN *")
    schema = {}

    actual_result: Optional[kuzu.query_result.QueryResult] = None
    if isinstance(raw_result, list):
        if raw_result:
            actual_result = raw_result[0]
    else:
        actual_result = raw_result

    # Assuming TABLE_INFO returns columns like 'name' and 'type' for properties
    # Adjust if the actual column names from Kuzu's TABLE_INFO are different
    if actual_result:
        column_names = actual_result.get_column_names()
        name_col_idx = column_names.index('name') if 'name' in column_names else -1
        type_col_idx = column_names.index('type') if 'type' in column_names else -1 # Kuzu uses 'type' for property type

        if name_col_idx != -1 and type_col_idx != -1:
            while actual_result.has_next():
                row = actual_result.get_next()
                schema[row[name_col_idx]] = row[type_col_idx]
    return schema

def test_kuzu_adapter_init_connect_close():
    """Test adapter initialization, connection, and implicit close."""
    if TEMP_KUZU_DB_DIR.exists():
        shutil.rmtree(TEMP_KUZU_DB_DIR)
    TEMP_KUZU_DB_DIR.mkdir(parents=True, exist_ok=True)
    
    adapter = KuzuAdapter(db_path=str(TEMP_KUZU_DB_DIR))
    assert adapter.db is not None, "Database object should be initialized"
    assert adapter.conn is not None, "Connection object should be initialized"
    
    assert TEMP_KUZU_DB_DIR.exists()
    assert any(TEMP_KUZU_DB_DIR.iterdir()), "Kuzu database directory should not be empty"

    adapter.close() 
    assert adapter.db is None, "Database object should be None after close"
    assert adapter.conn is None, "Connection object should be None after close"
    
    if TEMP_KUZU_DB_DIR.exists():
        shutil.rmtree(TEMP_KUZU_DB_DIR)

def test_create_and_drop_node_table(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition):
    """Test creation and deletion of a Kuzu node table."""
    adapter = kuzu_adapter_fixture
    otd = sample_otd_person

    adapter.create_node_table(otd)
    
    assert adapter.conn is not None
    schema = get_kuzu_table_schema(adapter.conn, otd.name)
    assert "id" in schema and schema["id"] == "UUID"
    assert "name" in schema and schema["name"] == "STRING"
    assert "age" in schema and schema["age"] == "INT64"
    assert "isVerified" in schema and schema["isVerified"] == "BOOL"
    assert "score" in schema and schema["score"] == "DOUBLE"
    assert "created_at" in schema and schema["created_at"] == "TIMESTAMP"
    assert "some_blob" in schema and schema["some_blob"] == "BLOB"
    assert "metadata" in schema and schema["metadata"] == "STRING"

    adapter.drop_node_table(otd.name)
    
    assert adapter.conn is not None
    with pytest.raises(RuntimeError): 
         get_kuzu_table_schema(adapter.conn, otd.name)

def test_create_node_table_with_explicit_id_property(kuzu_adapter_fixture: KuzuAdapter):
    adapter = kuzu_adapter_fixture
    otd_with_id = ObjectTypeDefinition(
        name="TestWithId",
        properties=[
            PropertyDefinition(name="id", data_type=PropertyDataType.UUID), 
            PropertyDefinition(name="description", data_type=PropertyDataType.TEXT)
        ]
    )
    adapter.create_node_table(otd_with_id)
    assert adapter.conn is not None
    schema = get_kuzu_table_schema(adapter.conn, otd_with_id.name)
    assert "id" in schema and schema["id"] == "UUID" 
    assert "description" in schema and schema["description"] == "STRING"
    
    assert adapter.conn is not None # Added assertion
    # Add RETURN * and process results carefully
    raw_result_pk_check = adapter.conn.execute(f"CALL TABLE_INFO('{otd_with_id.name}') RETURN *")
    id_is_pk = False
    column_names_for_debug = []
    all_rows_data_for_debug = []

    actual_result_pk_check: Optional[kuzu.query_result.QueryResult] = None
    if isinstance(raw_result_pk_check, list):
        if raw_result_pk_check:
            actual_result_pk_check = raw_result_pk_check[0]
    else:
        actual_result_pk_check = raw_result_pk_check
        
    if actual_result_pk_check:
        column_names_for_debug = actual_result_pk_check.get_column_names()
        # First, collect all rows
        while actual_result_pk_check.has_next():
            all_rows_data_for_debug.append(list(actual_result_pk_check.get_next()))
        
        # Now, try to find the column indices
        name_col_idx = -1
        pk_col_idx = -1
        
        try:
            name_col_idx = column_names_for_debug.index('name')
        except ValueError:
            pass # name column not found

        try:
            # Use the correct column name 'primary key' as identified from the debug output
            pk_col_idx = column_names_for_debug.index('primary key')
        except ValueError:
            pass # pk column not found

        if name_col_idx != -1 and pk_col_idx != -1:
            for row_data in all_rows_data_for_debug: # Iterate over the collected rows
                # Ensure accessing by correct index and checking boolean True or integer 1
                if row_data[name_col_idx] == 'id' and (row_data[pk_col_idx] is True or row_data[pk_col_idx] == 1):
                    id_is_pk = True
                    break
    
    if not id_is_pk:
        # Construct a detailed error message if the assertion fails
        error_message = f"Kuzu 'id' column should be primary key. id_is_pk is {id_is_pk}.\n"
        if column_names_for_debug: # Check if column_names were populated
            error_message += f"TABLE_INFO Columns: {column_names_for_debug}\n"
            error_message += "TABLE_INFO All Rows:\n"
            for r_data_debug in all_rows_data_for_debug:
                error_message += f"  {r_data_debug}\n"
        else:
            error_message += "No result from TABLE_INFO query or query result was empty, or column names could not be retrieved."
        raise AssertionError(error_message)

    adapter.drop_node_table(otd_with_id.name)


def test_create_node_table_id_property_wrong_type(kuzu_adapter_fixture: KuzuAdapter):
    adapter = kuzu_adapter_fixture
    otd_wrong_id = ObjectTypeDefinition(
        name="WrongIdType",
        properties=[
            PropertyDefinition(name="id", data_type=PropertyDataType.TEXT), 
            PropertyDefinition(name="description", data_type=PropertyDataType.TEXT)
        ]
    )
    with pytest.raises(SchemaError, match="Property 'id' for Kuzu node table 'WrongIdType' must be UUID type"):
        adapter.create_node_table(otd_wrong_id)


def test_create_and_drop_rel_table(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_otd_person: ObjectTypeDefinition, sample_otd_organisation: ObjectTypeDefinition):
    """Test creation and deletion of a Kuzu relationship table."""
    adapter = kuzu_adapter_fixture
    rtd = sample_rtd_works_at

    adapter.create_node_table(sample_otd_person)
    adapter.create_node_table(sample_otd_organisation)

    adapter.create_rel_table(rtd)

    assert adapter.conn is not None
    schema = get_kuzu_table_schema(adapter.conn, rtd.name)
    assert "id" in schema and schema["id"] == "UUID" 
    assert "weight" in schema and schema["weight"] == "DOUBLE" 
    assert "upsert_date" in schema and schema["upsert_date"] == "TIMESTAMP" 
    assert "role" in schema and schema["role"] == "STRING" 
    assert "start_date" in schema and schema["start_date"] == "TIMESTAMP" 

    adapter.drop_rel_table(rtd.name)

    assert adapter.conn is not None
    with pytest.raises(RuntimeError): 
         get_kuzu_table_schema(adapter.conn, rtd.name)

    adapter.drop_node_table(sample_otd_person.name)
    adapter.drop_node_table(sample_otd_organisation.name)

def test_drop_non_existent_table(kuzu_adapter_fixture: KuzuAdapter):
    """Test dropping a non-existent table to see Kuzu's behavior."""
    adapter = kuzu_adapter_fixture
    with pytest.raises(SchemaError, match="KuzuDB error dropping node table 'NonExistentTable'"):
        adapter.drop_node_table("NonExistentTable")
    
    with pytest.raises(SchemaError, match="KuzuDB error dropping relationship table 'NonExistentRelTable'"):
        adapter.drop_rel_table("NonExistentRelTable")

def test_unsupported_property_type(kuzu_adapter_fixture: KuzuAdapter):
    """Test creating a table with an unsupported Grizabella property type."""
    adapter = kuzu_adapter_fixture
    
    # To test the adapter's handling of an unmapped Grizabella type,
    # we need to simulate _map_grizabella_to_kuzu_type failing for a valid PropertyDataType.
    # We can do this by temporarily patching the mapping or the method itself.
    # For simplicity, let's assume PropertyDataType.BLOB is temporarily unmapped for this test.
    
    original_mapping_func = adapter._map_grizabella_to_kuzu_type

    def mock_map_type_for_test(prop_type):
        if prop_type == PropertyDataType.BLOB: # Choose a type to simulate as unmapped
            # Simulate the behavior of mapping.get(prop_type) returning None
            # which then causes the original method to raise SchemaError
            raise SchemaError(f"Unsupported Grizabella data type for Kuzu: {prop_type}")
        return original_mapping_func(prop_type)

    with patch.object(adapter, '_map_grizabella_to_kuzu_type', side_effect=mock_map_type_for_test):
        otd_with_temporarily_unsupported_type = ObjectTypeDefinition(
            name="UnsupportedTypeTable",
            properties=[
                PropertyDefinition(name="data", data_type=PropertyDataType.BLOB) # Use a valid Grizabella type
            ]
        )
        # Match the actual error message which includes the adapter's prefix and the full Enum member string
        with pytest.raises(SchemaError, match="KuzuDB error creating node table 'UnsupportedTypeTable': Unsupported Grizabella data type for Kuzu: PropertyDataType.BLOB"):
            adapter.create_node_table(otd_with_temporarily_unsupported_type)

def test_adapter_create_object_type(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    adapter.create_object_type(sample_otd_person) 
    assert adapter.conn is not None
    schema = get_kuzu_table_schema(adapter.conn, sample_otd_person.name)
    assert "id" in schema and schema["id"] == "UUID"
    adapter.delete_object_type(sample_otd_person.name)

def test_adapter_delete_object_type(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person)
    adapter.delete_object_type(sample_otd_person.name)
    assert adapter.conn is not None
    with pytest.raises(RuntimeError):
         get_kuzu_table_schema(adapter.conn, sample_otd_person.name)

def test_adapter_create_relation_type(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_otd_person: ObjectTypeDefinition, sample_otd_organisation: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person)
    adapter.create_node_table(sample_otd_organisation)
    adapter.create_relation_type(sample_rtd_works_at) 
    assert adapter.conn is not None
    schema = get_kuzu_table_schema(adapter.conn, sample_rtd_works_at.name)
    assert "role" in schema
    adapter.delete_relation_type(sample_rtd_works_at.name)

def test_adapter_delete_relation_type(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_otd_person: ObjectTypeDefinition, sample_otd_organisation: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person)
    adapter.create_node_table(sample_otd_organisation)
    adapter.create_rel_table(sample_rtd_works_at)
    adapter.delete_relation_type(sample_rtd_works_at.name)
    assert adapter.conn is not None
    with pytest.raises(RuntimeError):
         get_kuzu_table_schema(adapter.conn, sample_rtd_works_at.name)
    adapter.drop_node_table(sample_otd_person.name)
    adapter.drop_node_table(sample_otd_organisation.name)

def test_list_object_types(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition, sample_otd_organisation: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    assert adapter.list_object_types() == [] 

    adapter.create_node_table(sample_otd_person)
    tables = adapter.list_object_types()
    assert len(tables) == 1
    assert sample_otd_person.name in tables

    adapter.create_node_table(sample_otd_organisation)
    tables = adapter.list_object_types()
    assert len(tables) == 2
    assert sample_otd_person.name in tables
    assert sample_otd_organisation.name in tables
    
    adapter.drop_node_table(sample_otd_person.name)
    tables = adapter.list_object_types()
    assert len(tables) == 1
    assert sample_otd_organisation.name in tables

    adapter.drop_node_table(sample_otd_organisation.name)
    assert adapter.list_object_types() == []

# --- Node Instance Operation Tests ---

def test_upsert_object_instance(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition, sample_person_instance: ObjectInstance):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person) # Ensure table exists

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_query_result.has_next.return_value = True
    mock_query_result.get_next.return_value = [str(sample_person_instance.id)] # Kuzu returns ID as string
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    returned_instance = adapter.upsert_object_instance(sample_person_instance)
    assert returned_instance == sample_person_instance

    expected_query_fragment_merge = f"MERGE (n:{sample_person_instance.object_type_name} {{id: $id_param}})"
    
    args, kwargs = mock_conn.execute.call_args
    actual_query = args[0]
    actual_params = kwargs.get('parameters', args[1] if len(args) > 1 else {})


    assert expected_query_fragment_merge in actual_query
    # Updated assertions for individual SET properties
    assert "ON CREATE SET n.id = $id_param" in actual_query
    assert "n.name = $p_name" in actual_query
    assert "n.age = $p_age" in actual_query
    assert "n.isVerified = $p_isVerified" in actual_query
    assert "n.score = $p_score" in actual_query
    assert "n.created_at = $p_created_at" in actual_query
    assert "n.metadata = $p_metadata" in actual_query
    assert "ON MATCH SET n.name = $p_name" in actual_query
    assert "n.age = $p_age" in actual_query
    assert "n.isVerified = $p_isVerified" in actual_query
    assert "n.score = $p_score" in actual_query
    assert "n.created_at = $p_created_at" in actual_query
    assert "n.metadata = $p_metadata" in actual_query
    assert "n.name = $p_name" in actual_query
    assert "n.age = $p_age" in actual_query
    assert "n.isVerified = $p_isVerified" in actual_query
    assert "n.score = $p_score" in actual_query
    assert "n.created_at = $p_created_at" in actual_query
    assert "n.metadata = $p_metadata" in actual_query

    assert actual_params['id_param'] == sample_person_instance.id
    assert actual_params['p_name'] == sample_person_instance.properties['name']
    assert actual_params['p_age'] == sample_person_instance.properties['age']
    assert actual_params['p_isVerified'] == sample_person_instance.properties['isVerified']
    assert actual_params['p_score'] == sample_person_instance.properties['score']
    assert actual_params['p_created_at'] == sample_person_instance.properties['created_at']
    assert actual_params['p_metadata'] == sample_person_instance.properties['metadata']


def test_get_object_instance_found(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition, sample_person_instance: ObjectInstance):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person)

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    
    kuzu_node_data = {'id': str(sample_person_instance.id)}
    kuzu_node_data.update({k: v for k, v in sample_person_instance.properties.items()})
    # Simulate how Kuzu might return datetime (as datetime object if type mapping is good)
    kuzu_node_data['created_at'] = sample_person_instance.properties['created_at']


    mock_query_result.has_next.return_value = True
    mock_query_result.get_next.return_value = [kuzu_node_data]
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    retrieved = adapter.get_object_instance(sample_person_instance.object_type_name, sample_person_instance.id)
    
    assert retrieved is not None
    assert retrieved.id == sample_person_instance.id
    assert retrieved.object_type_name == sample_person_instance.object_type_name
    assert retrieved.properties['name'] == sample_person_instance.properties['name']
    assert retrieved.properties['age'] == sample_person_instance.properties['age']
    # For datetime, direct comparison might fail due to precision if not handled carefully by mock
    assert retrieved.properties['created_at'].year == sample_person_instance.properties['created_at'].year


def test_get_object_instance_not_found(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person)

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_query_result.has_next.return_value = False # Simulate not found
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    non_existent_id = uuid4()
    retrieved = adapter.get_object_instance(sample_otd_person.name, non_existent_id)
    assert retrieved is None

def test_delete_object_instance_found(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition, sample_person_instance: ObjectInstance):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person)

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    # Adapter code: summary = actual_query_result.get_query_summary(); nodes_deleted = summary.get_num_nodes_deleted()
    # This requires mock_query_result.get_query_summary() to return a mock that has get_num_nodes_deleted()
    mock_summary_obj = MagicMock()
    mock_summary_obj.get_num_nodes_deleted.return_value = 1
    mock_query_result.get_query_summary = MagicMock(return_value=mock_summary_obj)
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    deleted = adapter.delete_object_instance(sample_person_instance.object_type_name, sample_person_instance.id)
    assert deleted is True
    
    args, kwargs = mock_conn.execute.call_args
    actual_query = args[0]
    actual_params = kwargs.get('parameters', args[1] if len(args) > 1 else {})
    assert f"MATCH (n:{sample_person_instance.object_type_name} {{id: $instance_id_param}}) DETACH DELETE n" in actual_query
    assert actual_params['instance_id_param'] == sample_person_instance.id


def test_delete_object_instance_not_found(kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person)

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_summary_obj = MagicMock()
    mock_summary_obj.get_num_nodes_deleted.return_value = 0
    mock_query_result.get_query_summary = MagicMock(return_value=mock_summary_obj)
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn
    
    non_existent_id = uuid4()
    deleted = adapter.delete_object_instance(sample_otd_person.name, non_existent_id)
    assert deleted is False

# --- Relationship Instance Operation Tests ---

def test_upsert_relation_instance(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_works_at_instance: RelationInstance, sample_otd_person: ObjectTypeDefinition, sample_otd_organisation: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    # Ensure node tables exist for the relation
    adapter.create_node_table(sample_otd_person)
    adapter.create_node_table(sample_otd_organisation)
    adapter.create_rel_table(sample_rtd_works_at)

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_query_result.has_next.return_value = True
    mock_query_result.get_next.return_value = [str(sample_works_at_instance.id)]
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    returned_instance = adapter.upsert_relation_instance(sample_works_at_instance, sample_rtd_works_at)
    assert returned_instance == sample_works_at_instance

    args, kwargs = mock_conn.execute.call_args
    actual_query = args[0]
    actual_params = kwargs.get('parameters', args[1] if len(args) > 1 else {})

    assert f"MATCH (src:{sample_rtd_works_at.source_object_type_names[0]} {{id: $src_id_param}})" in actual_query
    assert f"(tgt:{sample_rtd_works_at.target_object_type_names[0]} {{id: $tgt_id_param}})" in actual_query
    assert f"MERGE (src)-[r:{sample_works_at_instance.relation_type_name} {{id: $rel_id_param}}]->(tgt)" in actual_query
    # Updated assertions for individual SET properties
    assert "ON CREATE SET r.id = $p_id" in actual_query
    assert "r.weight = $p_weight" in actual_query
    assert "r.upsert_date = $p_upsert_date" in actual_query
    assert "r.role = $p_role" in actual_query
    assert "r.start_date = $p_start_date" in actual_query
    assert "ON MATCH SET r.id = $p_id" in actual_query
    assert "r.weight = $p_weight" in actual_query
    assert "r.upsert_date = $p_upsert_date" in actual_query
    assert "r.role = $p_role" in actual_query
    assert "r.start_date = $p_start_date" in actual_query

    assert actual_params['src_id_param'] == sample_works_at_instance.source_object_instance_id
    assert actual_params['tgt_id_param'] == sample_works_at_instance.target_object_instance_id
    assert actual_params['rel_id_param'] == sample_works_at_instance.id
    assert actual_params['p_id'] == sample_works_at_instance.id
    assert actual_params['p_weight'] == float(sample_works_at_instance.weight)
    assert actual_params['p_upsert_date'] == sample_works_at_instance.upsert_date
    assert actual_params['p_role'] == sample_works_at_instance.properties['role']
    assert actual_params['p_start_date'] == sample_works_at_instance.properties['start_date']


def test_get_relation_instance_found(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_works_at_instance: RelationInstance, sample_otd_person: ObjectTypeDefinition, sample_otd_organisation: ObjectTypeDefinition):
    adapter = kuzu_adapter_fixture
    adapter.create_node_table(sample_otd_person)
    adapter.create_node_table(sample_otd_organisation)
    adapter.create_rel_table(sample_rtd_works_at)

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    
    kuzu_rel_data: Dict[str, Any] = {'id': str(sample_works_at_instance.id)} # Initialize with Any
    kuzu_rel_data.update(sample_works_at_instance.properties)
    kuzu_rel_data['weight'] = float(sample_works_at_instance.weight)
    kuzu_rel_data['upsert_date'] = sample_works_at_instance.upsert_date


    mock_query_result.has_next.return_value = True
    mock_query_result.get_next.return_value = [
        kuzu_rel_data,
        str(sample_works_at_instance.source_object_instance_id),
        str(sample_works_at_instance.target_object_instance_id)
    ]
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    retrieved = adapter.get_relation_instance(sample_works_at_instance.relation_type_name, sample_works_at_instance.id)

    assert retrieved is not None
    assert retrieved.id == sample_works_at_instance.id
    assert retrieved.relation_type_name == sample_works_at_instance.relation_type_name
    assert retrieved.source_object_instance_id == sample_works_at_instance.source_object_instance_id
    assert retrieved.target_object_instance_id == sample_works_at_instance.target_object_instance_id
    assert retrieved.properties['role'] == sample_works_at_instance.properties['role']
    assert retrieved.weight == sample_works_at_instance.weight
    assert retrieved.upsert_date == sample_works_at_instance.upsert_date

def test_get_relation_instance_not_found(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition):
    adapter = kuzu_adapter_fixture
    # adapter.create_rel_table(sample_rtd_works_at) # Table needs to exist for query to be valid

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_query_result.has_next.return_value = False # Simulate not found
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    non_existent_id = uuid4()
    retrieved = adapter.get_relation_instance(sample_rtd_works_at.name, non_existent_id)
    assert retrieved is None


def test_delete_relation_instance_found(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_works_at_instance: RelationInstance):
    adapter = kuzu_adapter_fixture
    # adapter.create_rel_table(sample_rtd_works_at)

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_summary_obj = MagicMock()
    mock_summary_obj.get_num_rels_deleted.return_value = 1
    mock_query_result.get_query_summary = MagicMock(return_value=mock_summary_obj)
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    deleted = adapter.delete_relation_instance(sample_works_at_instance.relation_type_name, sample_works_at_instance.id)
    assert deleted is True

    args, kwargs = mock_conn.execute.call_args
    actual_query = args[0]
    actual_params = kwargs.get('parameters', args[1] if len(args) > 1 else {})
    assert f"MATCH ()-[r:{sample_works_at_instance.relation_type_name} {{id: $rel_id_param}}]->() DELETE r" in actual_query
    assert actual_params['rel_id_param'] == sample_works_at_instance.id


def test_delete_relation_instance_not_found(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition):
    adapter = kuzu_adapter_fixture
    # adapter.create_rel_table(sample_rtd_works_at)

    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_summary_obj = MagicMock()
    mock_summary_obj.get_num_rels_deleted.return_value = 0
    mock_query_result.get_query_summary = MagicMock(return_value=mock_summary_obj)
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    non_existent_id = uuid4()
    deleted = adapter.delete_relation_instance(sample_rtd_works_at.name, non_existent_id)
    assert deleted is False

# --- Find Relation Instances Tests ---

def test_find_relation_instances_by_type(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_works_at_instance: RelationInstance):
    adapter = kuzu_adapter_fixture
    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    
    kuzu_rel_data = {'id': str(sample_works_at_instance.id), 'role': 'Engineer', 'weight': 0.9, 'upsert_date': sample_works_at_instance.upsert_date}
    
    mock_query_result.has_next.side_effect = [True, False] # One result
    mock_query_result.get_next.return_value = [
        kuzu_rel_data,
        str(sample_works_at_instance.source_object_instance_id),
        str(sample_works_at_instance.target_object_instance_id),
        sample_works_at_instance.relation_type_name
    ]
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    results = adapter.find_relation_instances(relation_type_name=sample_rtd_works_at.name)
    assert len(results) == 1
    assert results[0].id == sample_works_at_instance.id
    assert results[0].properties['role'] == 'Engineer'
    assert results[0].weight == sample_works_at_instance.weight
    assert results[0].upsert_date.year == sample_works_at_instance.upsert_date.year # Basic check for datetime

    args, kwargs = mock_conn.execute.call_args
    actual_query = args[0]
    assert f"MATCH (src)-[r:{sample_rtd_works_at.name}]->(tgt)" in actual_query
    assert "RETURN r, src.id AS src_node_id, tgt.id AS tgt_node_id" in actual_query


def test_find_relation_instances_by_source_id(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_works_at_instance: RelationInstance):
    adapter = kuzu_adapter_fixture
    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_query_result.has_next.side_effect = [True, False]
    mock_query_result.get_next.return_value = [
        {'id': str(sample_works_at_instance.id), 'role': 'Dev'},
        str(sample_works_at_instance.source_object_instance_id),
        str(sample_works_at_instance.target_object_instance_id),
        sample_rtd_works_at.name
    ]
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    results = adapter.find_relation_instances(
        relation_type_name=sample_rtd_works_at.name,
        source_object_id=sample_works_at_instance.source_object_instance_id
    )
    assert len(results) == 1
    assert results[0].source_object_instance_id == sample_works_at_instance.source_object_instance_id

    args, kwargs = mock_conn.execute.call_args
    actual_query = args[0]
    actual_params = kwargs.get('parameters', args[1] if len(args) > 1 else {})
    assert "src.id = $src_id_param" in actual_query
    assert actual_params['src_id_param'] == sample_works_at_instance.source_object_instance_id # Compare UUID objects


def test_find_relation_instances_with_property_query(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition, sample_works_at_instance: RelationInstance):
    adapter = kuzu_adapter_fixture
    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_query_result.has_next.side_effect = [True, False]
    mock_query_result.get_next.return_value = [
        {'id': str(sample_works_at_instance.id), 'role': 'Manager'},
        str(sample_works_at_instance.source_object_instance_id),
        str(sample_works_at_instance.target_object_instance_id),
        sample_rtd_works_at.name
    ]
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    results = adapter.find_relation_instances(
        relation_type_name=sample_rtd_works_at.name,
        query={"role": "Manager"}
    )
    assert len(results) == 1
    assert results[0].properties['role'] == "Manager"

    args, kwargs = mock_conn.execute.call_args
    actual_query = args[0]
    actual_params = kwargs.get('parameters', args[1] if len(args) > 1 else {})
    assert "r.role = $prop_role" in actual_query
    assert actual_params['prop_role'] == "Manager"


def test_find_relation_instances_with_limit(kuzu_adapter_fixture: KuzuAdapter, sample_rtd_works_at: RelationTypeDefinition):
    adapter = kuzu_adapter_fixture
    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_query_result.has_next.return_value = False # No results needed for this check
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    adapter.find_relation_instances(relation_type_name=sample_rtd_works_at.name, limit=5)
    
    args, _ = mock_conn.execute.call_args
    actual_query = args[0]
    assert "LIMIT 5" in actual_query

def test_find_relation_instances_no_type_with_property_query_raises_error(kuzu_adapter_fixture: KuzuAdapter):
    adapter = kuzu_adapter_fixture
    # Ensure the regex correctly escapes parentheses and matches the exact error string.
    with pytest.raises(ValueError, match=r"Querying by relation properties \(using the 'query' parameter\) requires specifying the 'relation_type_name'"):
        adapter.find_relation_instances(query={"some_prop": "some_value"})

def test_find_relation_instances_no_filters_returns_empty(kuzu_adapter_fixture: KuzuAdapter):
    """
    Tests that calling find_relation_instances with no specific relation_type_name
    (and no other filters that would imply a type) returns an empty list due to implementation constraints.
    """
    adapter = kuzu_adapter_fixture
    mock_conn = MagicMock(spec=kuzu.Connection)
    adapter.conn = mock_conn
    
    results = adapter.find_relation_instances() # No filters at all
    assert results == []
    # Check that execute was not called, or called with a query that Kuzu would likely reject for property access
    # For this specific test, we expect it to return early.
    mock_conn.execute.assert_not_called()

    # Test with only source_id (still no relation_type_name for property access)
    # This should now raise a ValueError due to the adapter changes.
    expected_error_message = "Querying relations by source/target ID without specifying 'relation_type_name' is too broad and requires 'relation_type_name'."
    with pytest.raises(ValueError, match=expected_error_message):
        adapter.find_relation_instances(source_object_id=uuid4())
    mock_conn.execute.assert_not_called() # Ensure execute is still not called

# Test for the initial check in find_relation_instances
def test_find_relation_instances_minimal_filters(kuzu_adapter_fixture: KuzuAdapter):
    adapter = kuzu_adapter_fixture
    mock_conn = MagicMock(spec=kuzu.Connection)
    mock_query_result = MagicMock(spec=kuzu.QueryResult)
    mock_query_result.has_next.return_value = False # No data needed, just testing query construction
    mock_conn.execute.return_value = mock_query_result
    adapter.conn = mock_conn

    # Case 1: Only relation_type_name
    adapter.find_relation_instances(relation_type_name="TestRel")
    args, kwargs = mock_conn.execute.call_args
    assert "MATCH (src)-[r:TestRel]->(tgt)" in args[0]
    mock_conn.execute.reset_mock()

    # Case 2: Only source_object_id (this should ideally also have relation_type_name for useful query)
    # The current implementation of find_relation_instances might return early or build a generic query.
    # Let's test the behavior when only source_object_id is provided.
    # The code has: if not relation_type_name and not source_object_id and not target_object_id and not query: return []
    # So, if only source_object_id is given, it should proceed.
    # The query would be MATCH (src)-[r]->(tgt) WHERE src.id = $src_id_param RETURN r, src.id, tgt.id, TYPE(r)
    # This is a valid query.
    test_src_id = uuid4()
    expected_error_message = "Querying relations by source/target ID without specifying 'relation_type_name' is too broad and requires 'relation_type_name'."
    with pytest.raises(ValueError, match=expected_error_message):
        adapter.find_relation_instances(source_object_id=test_src_id)
    mock_conn.execute.assert_not_called()
    mock_conn.execute.reset_mock()

    # Case 3: Only target_object_id
    test_tgt_id = uuid4()
    with pytest.raises(ValueError, match=expected_error_message):
        adapter.find_relation_instances(target_object_id=test_tgt_id)
    mock_conn.execute.assert_not_called()
    mock_conn.execute.reset_mock()

    # Case 4: Only query (this should raise ValueError as per implementation)
    with pytest.raises(ValueError, match=r"Querying by relation properties \(using the 'query' parameter\) requires specifying the 'relation_type_name'"):
        adapter.find_relation_instances(query={"some_prop": "val"})
    mock_conn.execute.assert_not_called() # Should not reach execute

    # Case 5: No filters at all - should return early
    adapter.find_relation_instances()
    mock_conn.execute.assert_not_called() # Should return early based on the check


class TestKuzuAdapterQueryEngineMethods:
    @pytest.fixture(autouse=True)
    def setup_kuzu_data(self, kuzu_adapter_fixture: KuzuAdapter, sample_otd_person: ObjectTypeDefinition, sample_otd_organisation: ObjectTypeDefinition, sample_rtd_works_at: RelationTypeDefinition):
        self.adapter = kuzu_adapter_fixture
        self.person_otd = sample_otd_person
        self.org_otd = sample_otd_organisation
        self.works_at_rtd = sample_rtd_works_at

        self.adapter.create_node_table(self.person_otd)
        self.adapter.create_node_table(self.org_otd)
        self.adapter.create_rel_table(self.works_at_rtd)

        # Create some instances
        self.person1_id = uuid4()
        self.person2_id = uuid4()
        self.person3_id = uuid4() # Will not have a relation initially
        self.org1_id = uuid4()
        self.org2_id = uuid4()

        self.adapter.upsert_object_instance(ObjectInstance(id=self.person1_id, object_type_name=self.person_otd.name, properties={"name": "Alice", "age": 30}))
        self.adapter.upsert_object_instance(ObjectInstance(id=self.person2_id, object_type_name=self.person_otd.name, properties={"name": "Bob", "age": 25}))
        self.adapter.upsert_object_instance(ObjectInstance(id=self.person3_id, object_type_name=self.person_otd.name, properties={"name": "Charlie", "age": 35}))
        self.adapter.upsert_object_instance(ObjectInstance(id=self.org1_id, object_type_name=self.org_otd.name, properties={"name": "OrgA", "industry": "Tech"}))
        self.adapter.upsert_object_instance(ObjectInstance(id=self.org2_id, object_type_name=self.org_otd.name, properties={"name": "OrgB", "industry": "Finance"}))

        # Person1 WorksAt OrgA
        self.rel1_id = uuid4()
        self.adapter.upsert_relation_instance(RelationInstance(id=self.rel1_id, relation_type_name=self.works_at_rtd.name, source_object_instance_id=self.person1_id, target_object_instance_id=self.org1_id, properties={"role": "Engineer"}), self.works_at_rtd)
        
        # Person2 WorksAt OrgB
        self.rel2_id = uuid4()
        self.adapter.upsert_relation_instance(RelationInstance(id=self.rel2_id, relation_type_name=self.works_at_rtd.name, source_object_instance_id=self.person2_id, target_object_instance_id=self.org2_id, properties={"role": "Analyst"}), self.works_at_rtd)

        # Person1 also WorksAt OrgB (as Manager)
        self.rel3_id = uuid4()
        self.adapter.upsert_relation_instance(RelationInstance(id=self.rel3_id, relation_type_name=self.works_at_rtd.name, source_object_instance_id=self.person1_id, target_object_instance_id=self.org2_id, properties={"role": "Manager"}), self.works_at_rtd)


    def test_filter_object_ids_basic_traversal(self):
        """Test basic outgoing traversal to find people who work at any org."""
        traversals = [
            GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name, direction="outgoing")
        ]
        # All people who have a WorksAt relation
        initial_ids = [self.person1_id, self.person2_id, self.person3_id]
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.person_otd.name, initial_ids, traversals)
        
        assert set(filtered_ids) == {self.person1_id, self.person2_id} # Person3 has no relations

    def test_filter_object_ids_no_matching_traversal(self):
        """Test traversal that yields no results."""
        traversals = [
            GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name, direction="outgoing", target_object_id=uuid4()) # Non-existent org
        ]
        initial_ids = [self.person1_id, self.person2_id]
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.person_otd.name, initial_ids, traversals)
        assert len(filtered_ids) == 0

    def test_filter_object_ids_with_initial_ids(self):
        """Test filtering an initial list of source IDs."""
        traversals = [
            GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name, direction="outgoing")
        ]
        initial_ids = [self.person2_id, self.person3_id] # Only person2 has a relation
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.person_otd.name, initial_ids, traversals)
        assert set(filtered_ids) == {self.person2_id}

    def test_filter_object_ids_empty_initial_ids(self):
        traversals = [
            GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name, direction="outgoing")
        ]
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.person_otd.name, [], traversals)
        assert len(filtered_ids) == 0

    def test_filter_object_ids_non_matching_initial_ids(self):
        """Initial IDs provided, but none can make the traversal."""
        traversals = [
            GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name, direction="outgoing", target_object_id=self.org1_id) # Target OrgA
        ]
        initial_ids = [self.person2_id, self.person3_id] # Person2 works at OrgB, Person3 works nowhere
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.person_otd.name, initial_ids, traversals)
        assert len(filtered_ids) == 0

    def test_filter_object_ids_traversal_with_target_props(self):
        """Test traversal with property filters on the target node."""
        # Find people who work at an org in "Tech" industry (OrgA)
        traversals = [
            GraphTraversalClause(
                relation_type_name=self.works_at_rtd.name,
                target_object_type_name=self.org_otd.name,
                direction="outgoing",
                target_object_properties=[RelationalFilter(property_name="industry", operator="==", value="Tech")]
            )
        ]
        initial_ids = [self.person1_id, self.person2_id]
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.person_otd.name, initial_ids, traversals)
        assert set(filtered_ids) == {self.person1_id} # Only Person1 works at OrgA (Tech)

    def test_filter_object_ids_traversal_with_specific_target_id(self):
        """Test traversal to a specific target node ID."""
        # Find people who work at OrgB
        traversals = [
            GraphTraversalClause(
                relation_type_name=self.works_at_rtd.name,
                target_object_type_name=self.org_otd.name,
                direction="outgoing",
                target_object_id=self.org2_id
            )
        ]
        initial_ids = [self.person1_id, self.person2_id, self.person3_id]
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.person_otd.name, initial_ids, traversals)
        # Person1 works at OrgB (as Manager), Person2 works at OrgB (as Analyst)
        assert set(filtered_ids) == {self.person1_id, self.person2_id}

    def test_filter_object_ids_incoming_traversal(self):
        """Test an incoming traversal (e.g., find Orgs that have a Person working as 'Engineer')."""
        traversals = [
            GraphTraversalClause(
                relation_type_name=self.works_at_rtd.name,
                target_object_type_name=self.person_otd.name, # Target is Person
                direction="incoming", # From Org's perspective, who is coming in
                target_object_properties=[] # No specific person properties for this test
                # We could filter on relation properties if supported, e.g. r.role = 'Engineer'
                # For now, this will find Orgs that have *any* Person working there.
                # To filter by role, we'd need to enhance the clause or the adapter's query building.
                # Let's assume the task implies filtering on the *source* node (Org) based on traversal.
                # The method filters source_object_ids.
            )
        ]
        # Find Orgs that have at least one employee.
        initial_ids = [self.org1_id, self.org2_id]
        # This test is slightly misaligned with the method's purpose if we want to filter by relation props.
        # The method filters the *source* IDs. So, we are finding Orgs (source) that have an incoming WorksAt from a Person (target).
        # This is equivalent to finding Orgs that have employees.
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.org_otd.name, initial_ids, traversals)
        assert set(filtered_ids) == {self.org1_id, self.org2_id} # Both orgs have employees

    def test_filter_object_ids_multiple_traversals_and_logic(self):
        """Test with multiple traversals (AND logic)."""
        # Find People who WorkAt OrgA AND WorkAt OrgB
        traversals = [
            GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name, direction="outgoing", target_object_id=self.org1_id), # Works at OrgA
            GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name, direction="outgoing", target_object_id=self.org2_id)  # Works at OrgB
        ]
        initial_ids = [self.person1_id, self.person2_id, self.person3_id]
        filtered_ids = self.adapter.filter_object_ids_by_relations(self.person_otd.name, initial_ids, traversals)
        assert set(filtered_ids) == {self.person1_id} # Only Person1 works at both OrgA and OrgB

    def test_filter_object_ids_source_node_table_not_exist(self):
        self.adapter.drop_rel_table(self.works_at_rtd.name) # Drop relations first
        self.adapter.drop_node_table(self.person_otd.name) # Then drop Person table
        traversals = [GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name)]
        # This will now likely fail because the relation table also doesn't exist,
        # or if filter_object_ids_by_relations checks source table first.
        # The original intent was to check for a missing source node table.
        # For Kuzu, if the source table is gone, the query on it would fail.
        # Let's adjust the expectation or the test setup if Kuzu's error changes.
        # For now, the primary goal is to avoid the "cannot delete node table ... referenced by relationship"
        # The test should check for an error indicating the source table is missing for the query.
        with pytest.raises(SchemaError, match=f"Kuzu source node table '{self.person_otd.name}' does not exist|Table {self.person_otd.name} does not exist"): # Kuzu might give different errors
            self.adapter.filter_object_ids_by_relations(self.person_otd.name, [self.person1_id], traversals)

    def test_filter_object_ids_target_node_table_not_exist(self):
        self.adapter.drop_rel_table(self.works_at_rtd.name) # Drop relations first
        self.adapter.drop_node_table(self.org_otd.name) # Then drop Organisation table
        traversals = [GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name)]
        # Similar to the above, the error might change. The key is that the target table is missing for the query.
        with pytest.raises(SchemaError, match=f"Kuzu target node table '{self.org_otd.name}' for traversal via '{self.works_at_rtd.name}' does not exist|Table {self.org_otd.name} does not exist"):
            self.adapter.filter_object_ids_by_relations(self.person_otd.name, [self.person1_id], traversals)
            
    def test_filter_object_ids_relation_table_not_exist(self):
        # Ensure source and target node tables exist before dropping relation table
        # This test specifically checks for missing relation table.
        # self.adapter.create_node_table(self.person_otd) # Should be created by fixture
        # self.adapter.create_node_table(self.org_otd)   # Should be created by fixture
        self.adapter.drop_rel_table(self.works_at_rtd.name) # Drop WorksAt table
        traversals = [GraphTraversalClause(relation_type_name=self.works_at_rtd.name, target_object_type_name=self.org_otd.name)]
        with pytest.raises(SchemaError, match=f"Kuzu relation table '{self.works_at_rtd.name}' does not exist|Table {self.works_at_rtd.name} does not exist"):
            self.adapter.filter_object_ids_by_relations(self.person_otd.name, [self.person1_id], traversals)