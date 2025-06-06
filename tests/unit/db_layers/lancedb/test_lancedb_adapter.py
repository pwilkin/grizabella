import pytest
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4, UUID
from unittest.mock import patch, MagicMock

# Attempt to import lancedb related components for testing
try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    lancedb = None
    LANCEDB_AVAILABLE = False

from grizabella.core.models import EmbeddingDefinition, EmbeddingInstance
from grizabella.db_layers.lancedb.lancedb_adapter import LanceDBAdapter, EmbeddingError
from grizabella.core.exceptions import DatabaseError, SchemaError


# Skip all tests in this module if lancedb is not available
pytestmark = pytest.mark.skipif(not LANCEDB_AVAILABLE, reason="lancedb library not found, skipping LanceDBAdapter tests")

@pytest.fixture
def temp_lancedb_uri():
    """Create a temporary directory for LanceDB data and return its URI."""
    temp_base_dir = tempfile.mkdtemp(prefix="grizabella_test_lancedb_base_")
    # LanceDB connects to a directory, ensure this specific directory exists.
    lancedb_data_path = Path(temp_base_dir) / "lancedb_test_data"
    lancedb_data_path.mkdir(parents=True, exist_ok=True)
    uri = str(lancedb_data_path)
    print(f"LanceDB Test Fixture: Created LanceDB URI at '{uri}'") # For debugging
    yield uri
    # Teardown: remove the temporary directory
    shutil.rmtree(temp_base_dir, ignore_errors=True)


@pytest.fixture
def embedding_def_sample1():
    return EmbeddingDefinition(
        name="test_embedding_def_1",
        object_type_name="TestObject",
        source_property_name="text_content",
        embedding_model="huggingface/colbert-ir/colbertv2.0", # Example model
        dimensions=128 # Example dimension
    )

@pytest.fixture
def embedding_def_sample2():
    return EmbeddingDefinition(
        name="another_embedding_table",
        object_type_name="AnotherObject",
        source_property_name="description",
        embedding_model="huggingface/other-model",
        dimensions=768 # Different dimension
    )

@pytest.fixture
def embedding_def_no_dims():
    return EmbeddingDefinition(
        name="no_dims_def",
        object_type_name="ObjectNoDims",
        source_property_name="data",
        embedding_model="some/model",
        dimensions=None # No dimension specified
    )

@pytest.fixture
def embedding_instance_sample1(embedding_def_sample1):
    return EmbeddingInstance(
        object_instance_id=uuid4(),
        embedding_definition_name=embedding_def_sample1.name,
        vector=[0.1] * embedding_def_sample1.dimensions, # Use correct dimension
        source_text_preview="Sample text preview"
    )

@pytest.fixture
def embedding_instance_sample2(embedding_def_sample1): # Another instance for the same def
    return EmbeddingInstance(
        object_instance_id=uuid4(), # Different object_instance_id for this one
        embedding_definition_name=embedding_def_sample1.name,
        vector=[0.2] * embedding_def_sample1.dimensions,
        source_text_preview="Another sample"
    )


def test_lancedb_adapter_initialization(temp_lancedb_uri):
    """Test LanceDBAdapter initialization and connection."""
    adapter = None
    try:
        adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
        assert adapter.db is not None, "LanceDB connection object should be initialized."
        assert Path(temp_lancedb_uri).exists(), "LanceDB data directory should be created."
        # Check if a .lancedb folder or similar is created by connect, if applicable
        # For now, just checking the base URI path exists is sufficient.
    finally:
        if adapter:
            adapter.close()


def test_create_embedding_table(temp_lancedb_uri, embedding_def_sample1):
    """Test creation of an embedding table."""
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.create_embedding_table(embedding_def_sample1)
        table_name = adapter._sanitize_table_name(embedding_def_sample1.name)
        assert table_name in adapter.list_embedding_tables(), f"Table '{table_name}' should exist after creation."

        # Verify schema if possible (requires opening table and checking fields)
        assert adapter.db is not None # For Pylance
        tbl = adapter.db.open_table(table_name)
        schema = tbl.schema
        # LanceDB schema fields might be slightly different from Pydantic model names
        # Check for core fields based on LanceDBEmbeddingSchema
        # PyArrow schema fields:
        field_names = [f.name for f in schema]

        assert "object_instance_id" in field_names
        assert "vector" in field_names
        assert "source_text_preview" in field_names
        
        # Check vector dimension if accessible
        schema.field("vector")
        # For fixed_size_list, the list_size is the dimension
        # This depends on how LanceDB stores Vector type in PyArrow schema
        # Example: pa.types.is_fixed_size_list(vector_field.type)
        # and vector_field.type.list_size == embedding_def_sample1.dimensions
        # This part might need adjustment based on actual LanceDB schema representation
        # For now, presence of 'vector' field is the primary check.

    finally:
        if adapter:
            adapter.close()


def test_create_embedding_table_already_exists(temp_lancedb_uri, embedding_def_sample1):
    """Test creating a table that already exists (should not raise error, should skip)."""
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.create_embedding_table(embedding_def_sample1) # First creation
        table_name = adapter._sanitize_table_name(embedding_def_sample1.name)
        assert table_name in adapter.list_embedding_tables()

        adapter.create_embedding_table(embedding_def_sample1) # Second attempt
        assert table_name in adapter.list_embedding_tables(), "Table should still exist after attempting to re-create."
    finally:
        if adapter:
            adapter.close()


def test_create_embedding_table_no_dimensions(temp_lancedb_uri, embedding_def_no_dims):
    """Test creating a table when EmbeddingDefinition has no dimensions (should raise SchemaError)."""
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        with pytest.raises(SchemaError, match="must have 'dimensions' > 0"):
            adapter.create_embedding_table(embedding_def_no_dims)
    finally:
        if adapter:
            adapter.close()


def test_drop_embedding_table(temp_lancedb_uri, embedding_def_sample1):
    """Test dropping an embedding table."""
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.create_embedding_table(embedding_def_sample1)
        table_name = adapter._sanitize_table_name(embedding_def_sample1.name)
        assert table_name in adapter.list_embedding_tables()

        adapter.drop_embedding_table(embedding_def_sample1.name)
        assert table_name not in adapter.list_embedding_tables(), f"Table '{table_name}' should not exist after being dropped."
    finally:
        if adapter:
            adapter.close()


def test_drop_embedding_table_not_exists(temp_lancedb_uri):
    """Test dropping a table that does not exist (should not raise error)."""
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.drop_embedding_table("non_existent_table_def_name")
        # No assertion needed, just ensuring no error is raised.
    finally:
        if adapter:
            adapter.close()


def test_list_embedding_tables(temp_lancedb_uri, embedding_def_sample1, embedding_def_sample2):
    """Test listing embedding tables."""
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        assert adapter.list_embedding_tables() == [], "Should be no tables initially."

        adapter.create_embedding_table(embedding_def_sample1)
        table1_name = adapter._sanitize_table_name(embedding_def_sample1.name)
        
        listed_tables = adapter.list_embedding_tables()
        assert len(listed_tables) == 1
        assert table1_name in listed_tables

        adapter.create_embedding_table(embedding_def_sample2)
        table2_name = adapter._sanitize_table_name(embedding_def_sample2.name)

        listed_tables = adapter.list_embedding_tables()
        assert len(listed_tables) == 2
        assert table1_name in listed_tables
        assert table2_name in listed_tables

        adapter.drop_embedding_table(embedding_def_sample1.name)
        listed_tables = adapter.list_embedding_tables()
        assert len(listed_tables) == 1
        assert table1_name not in listed_tables
        assert table2_name in listed_tables

    finally:
        if adapter:
            adapter.close()


def test_sanitize_table_name(temp_lancedb_uri):
    """Test the table name sanitization."""
    # Adapter instance needed only to access the method, db connection not strictly required for this.
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri) 
    try:
        assert adapter._sanitize_table_name("valid_name") == "valid_name"
        assert adapter._sanitize_table_name("name with spaces") == "name_with_spaces"
        assert adapter._sanitize_table_name("name.with.dots") == "name.with.dots" # Dots are allowed by default
        assert adapter._sanitize_table_name("name/with/slashes") == "name_with_slashes"
        assert adapter._sanitize_table_name("name-with-hyphens") == "name-with-hyphens" # Hyphens allowed
        assert adapter._sanitize_table_name("TestName") == "TestName"
        assert adapter._sanitize_table_name("test_123") == "test_123"
        assert adapter._sanitize_table_name("!@#$%^&*()") == "__________" 
    finally:
        if adapter:
            adapter.close()

def test_get_embedding_model(temp_lancedb_uri):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        with patch('grizabella.db_layers.lancedb.lancedb_adapter.LANCEDB_EMBEDDING_REGISTRY') as MockRegistry:
            # Mock the chained call: get(...).create(...)
            mock_provider = MagicMock()
            mock_model_func = MagicMock()
            MockRegistry.get.return_value = mock_provider
            mock_provider.create.return_value = mock_model_func

            # First call - should load and cache
            model1 = adapter.get_embedding_model("huggingface/test-model")
            MockRegistry.get.assert_called_once_with("huggingface")
            mock_provider.create.assert_called_once_with(name="huggingface/test-model", trust_remote_code=True)
            assert model1 is mock_model_func
            assert "huggingface/test-model" in adapter._embedding_model_cache

            # Second call - should return from cache
            model2 = adapter.get_embedding_model("huggingface/test-model")
            mock_provider.create.assert_called_once() # Still called only once
            assert model2 is mock_model_func

    finally:
        if adapter:
            adapter.close()

def test_get_embedding_model_load_failure(temp_lancedb_uri):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        with patch('grizabella.db_layers.lancedb.lancedb_adapter.LANCEDB_EMBEDDING_REGISTRY') as MockRegistry:
            mock_provider = MagicMock()
            MockRegistry.get.return_value = mock_provider
            mock_provider.create.side_effect = Exception("Load failed")
            
            with pytest.raises(EmbeddingError, match="Failed to load embedding model 'test/model' via LanceDB registry: Load failed"):
                adapter.get_embedding_model("test/model")
    finally:
        if adapter:
            adapter.close()


def test_upsert_embedding_instance(temp_lancedb_uri, embedding_def_sample1, embedding_instance_sample1):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.create_embedding_table(embedding_def_sample1) # Ensure table exists
        
        returned_instance = adapter.upsert_embedding_instance(embedding_instance_sample1, embedding_def_sample1)
        assert returned_instance == embedding_instance_sample1

        table_name = adapter._sanitize_table_name(embedding_def_sample1.name)
        assert adapter.db is not None # For Pylance
        tbl = adapter.db.open_table(table_name)
        
        # Verify data in table
        results = tbl.search().where(f"object_instance_id = '{str(embedding_instance_sample1.object_instance_id)}'").to_list()
        assert len(results) == 1
        record = results[0]
        assert record["object_instance_id"] == str(embedding_instance_sample1.object_instance_id)
        assert record["vector"] == pytest.approx(embedding_instance_sample1.vector)
        assert record["source_text_preview"] == embedding_instance_sample1.source_text_preview

    finally:
        if adapter:
            adapter.close()

def test_upsert_embedding_instance_table_not_exist(temp_lancedb_uri, embedding_def_sample1, embedding_instance_sample1):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        # Do NOT create table
        # Adjusted regex to be more flexible with the "Error: Table ... was not found" part.
        with pytest.raises(DatabaseError, match=f"LanceDB: Table '{embedding_def_sample1.name}' for ED '{embedding_def_sample1.name}' not found. Cannot upsert. Error: Table '{embedding_def_sample1.name}' was not found"):
            adapter.upsert_embedding_instance(embedding_instance_sample1, embedding_def_sample1)
    finally:
        if adapter:
            adapter.close()


def test_get_embedding_instances_for_object(temp_lancedb_uri, embedding_def_sample1, embedding_instance_sample1, embedding_instance_sample2):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.create_embedding_table(embedding_def_sample1)
        adapter.upsert_embedding_instance(embedding_instance_sample1, embedding_def_sample1)
        
        # Add another instance for a *different* object ID to ensure filtering works
        # embedding_instance_sample2 has a different object_id due to fixture modification
        adapter.upsert_embedding_instance(embedding_instance_sample2, embedding_def_sample1)


        # Retrieve for embedding_instance_sample1.object_instance_id
        retrieved_instances_1 = adapter.get_embedding_instances_for_object(
            embedding_instance_sample1.object_instance_id,
            embedding_def_sample1.name
        )
        assert len(retrieved_instances_1) == 1
        retrieved_1 = retrieved_instances_1[0]
        assert retrieved_1.object_instance_id == embedding_instance_sample1.object_instance_id
        assert retrieved_1.embedding_definition_name == embedding_instance_sample1.embedding_definition_name
        assert retrieved_1.vector == pytest.approx(embedding_instance_sample1.vector)
        assert retrieved_1.source_text_preview == embedding_instance_sample1.source_text_preview

        # Retrieve for embedding_instance_sample2.object_instance_id
        retrieved_instances_2 = adapter.get_embedding_instances_for_object(
            embedding_instance_sample2.object_instance_id,
            embedding_def_sample1.name
        )
        assert len(retrieved_instances_2) == 1
        retrieved_2 = retrieved_instances_2[0]
        assert retrieved_2.object_instance_id == embedding_instance_sample2.object_instance_id
        assert retrieved_2.vector == pytest.approx(embedding_instance_sample2.vector)


        # Test with an object ID that has no embeddings
        non_existent_obj_id = uuid4()
        retrieved_empty = adapter.get_embedding_instances_for_object(non_existent_obj_id, embedding_def_sample1.name)
        assert len(retrieved_empty) == 0

        # Test with a non-existent embedding definition name (table not found)
        retrieved_no_table = adapter.get_embedding_instances_for_object(embedding_instance_sample1.object_instance_id, "non_existent_def")
        assert len(retrieved_no_table) == 0
        
    finally:
        if adapter:
            adapter.close()

def test_get_embedding_instance(temp_lancedb_uri, embedding_def_sample1, embedding_instance_sample1):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.create_embedding_table(embedding_def_sample1)
        adapter.upsert_embedding_instance(embedding_instance_sample1, embedding_def_sample1)

        retrieved = adapter.get_embedding_instance(embedding_def_sample1.name, embedding_instance_sample1.object_instance_id)
        assert retrieved is not None
        assert retrieved.object_instance_id == embedding_instance_sample1.object_instance_id
        assert retrieved.vector == pytest.approx(embedding_instance_sample1.vector)

        # Test non-existent
        assert adapter.get_embedding_instance(embedding_def_sample1.name, uuid4()) is None
        assert adapter.get_embedding_instance("non_existent_def", embedding_instance_sample1.object_instance_id) is None
    finally:
        if adapter:
            adapter.close()


def test_delete_embedding_instances_for_object(temp_lancedb_uri, embedding_def_sample1, embedding_instance_sample1):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.create_embedding_table(embedding_def_sample1)
        adapter.upsert_embedding_instance(embedding_instance_sample1, embedding_def_sample1)
        
        # Create another instance with the same object_id to test deletion of multiple
        same_obj_instance_2 = EmbeddingInstance(
            object_instance_id=embedding_instance_sample1.object_instance_id, # Same object_id
            embedding_definition_name=embedding_def_sample1.name,
            vector=[0.9] * embedding_def_sample1.dimensions,
            source_text_preview="Same object, second embedding"
        )
        adapter.upsert_embedding_instance(same_obj_instance_2, embedding_def_sample1)


        # Add an instance for a different object to ensure only specified one is deleted
        other_obj_id = uuid4()
        other_instance = EmbeddingInstance(
            object_instance_id=other_obj_id,
            embedding_definition_name=embedding_def_sample1.name,
            vector=[0.3] * embedding_def_sample1.dimensions,
            source_text_preview="Other object text"
        )
        adapter.upsert_embedding_instance(other_instance, embedding_def_sample1)

        # Check initial state
        table_name = adapter._sanitize_table_name(embedding_def_sample1.name)
        assert adapter.db is not None # For Pylance
        tbl = adapter.db.open_table(table_name)
        assert len(tbl.search().to_list()) == 3 # sample1, same_obj_instance_2, other_instance

        # Delete instances for embedding_instance_sample1.object_instance_id
        adapter.delete_embedding_instances_for_object(embedding_instance_sample1.object_instance_id, embedding_def_sample1.name)
        
        # Verify deletion by re-opening the table to get the latest state
        assert adapter.db is not None # For Pylance
        tbl_after_delete = adapter.db.open_table(table_name)
        results_after_delete = tbl_after_delete.search().where(f"object_instance_id = '{str(embedding_instance_sample1.object_instance_id)}'").to_list()
        assert len(results_after_delete) == 0
        
        # Verify other object's instance is still there using the refreshed table handle
        results_other_obj = tbl_after_delete.search().where(f"object_instance_id = '{str(other_obj_id)}'").to_list()
        assert len(results_other_obj) == 1

        # Test deleting from non-existent table (should not error)
        adapter.delete_embedding_instances_for_object(uuid4(), "non_existent_def_name")

    finally:
        if adapter:
            adapter.close()

@pytest.fixture
def embedding_data_for_search(embedding_def_sample1):
    """Provides a list of EmbeddingInstance objects for populating a table for search tests."""
    dim = embedding_def_sample1.dimensions
    return [
        EmbeddingInstance(object_instance_id=uuid4(), embedding_definition_name=embedding_def_sample1.name, vector=[0.1] * dim, source_text_preview="item one apple"),
        EmbeddingInstance(object_instance_id=uuid4(), embedding_definition_name=embedding_def_sample1.name, vector=[0.11] * dim, source_text_preview="item one a bit different"), # very similar to 0.1
        EmbeddingInstance(object_instance_id=uuid4(), embedding_definition_name=embedding_def_sample1.name, vector=[0.5] * dim, source_text_preview="item two banana"),
        EmbeddingInstance(object_instance_id=uuid4(), embedding_definition_name=embedding_def_sample1.name, vector=[0.9] * dim, source_text_preview="item three cherry"),
        EmbeddingInstance(object_instance_id=uuid4(), embedding_definition_name=embedding_def_sample1.name, vector=[0.91] * dim, source_text_preview="item three also cherry like"), # very similar to 0.9
    ]

def populate_table_for_search(adapter, embedding_def, embedding_instances):
    """Helper to create table and add data."""
    adapter.create_embedding_table(embedding_def)
    for inst in embedding_instances:
        adapter.upsert_embedding_instance(inst, embedding_def)

def test_query_similar_embeddings_basic(temp_lancedb_uri, embedding_def_sample1, embedding_data_for_search):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        populate_table_for_search(adapter, embedding_def_sample1, embedding_data_for_search)
        
        query_vector = [0.105] * embedding_def_sample1.dimensions # Closest to the first two items
        
        results = adapter.query_similar_embeddings(
            embedding_definition_name=embedding_def_sample1.name,
            query_vector=query_vector,
            limit=2
        )
        
        assert len(results) == 2
        # Results are dictionaries. Check for expected keys.
        for res in results:
            assert "object_instance_id" in res
            assert "vector" in res
            assert "source_text_preview" in res
            assert "_distance" in res # LanceDB adds this
            
            retrieved_vectors = [r['vector'] for r in results]
            expected_top_vectors = [inst.vector for inst in embedding_data_for_search[:2]]
    
            assert len(retrieved_vectors) == len(expected_top_vectors)
            # Check that each retrieved vector is approximately equal to one of the expected vectors.
            # This handles potential reordering by the search if distances are identical.
            # And uses pytest.approx for float comparisons.
            
            # Convert expected_top_vectors to a list of pytest.approx objects for comparison
            expected_top_vectors_approx = [pytest.approx(vec) for vec in expected_top_vectors]
    
            matched_expected_vectors = [False] * len(expected_top_vectors_approx)
            for ret_vec in retrieved_vectors:
                found_match = False
                for i, exp_vec_approx in enumerate(expected_top_vectors_approx):
                    if not matched_expected_vectors[i] and ret_vec == exp_vec_approx:
                        matched_expected_vectors[i] = True
                        found_match = True
                        break
                assert found_match, f"Retrieved vector {ret_vec} not found in expected top vectors."
    
            if len(results) == 2:
                assert results[0]["_distance"] <= results[1]["_distance"] # Distances should be ordered

    finally:
        if adapter:
            adapter.close()

def test_query_similar_embeddings_limit(temp_lancedb_uri, embedding_def_sample1, embedding_data_for_search):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        populate_table_for_search(adapter, embedding_def_sample1, embedding_data_for_search)
        query_vector = [0.0] * embedding_def_sample1.dimensions # Generic query vector
        
        results_limit_1 = adapter.query_similar_embeddings(
            embedding_definition_name=embedding_def_sample1.name,
            query_vector=query_vector,
            limit=1
        )
        assert len(results_limit_1) == 1

        results_limit_3 = adapter.query_similar_embeddings(
            embedding_definition_name=embedding_def_sample1.name,
            query_vector=query_vector,
            limit=3
        )
        assert len(results_limit_3) == 3
        
        results_limit_10 = adapter.query_similar_embeddings(
            embedding_definition_name=embedding_def_sample1.name,
            query_vector=query_vector,
            limit=10 
        )
        assert len(results_limit_10) == len(embedding_data_for_search)

    finally:
        if adapter:
            adapter.close()

def test_query_similar_embeddings_with_filter(temp_lancedb_uri, embedding_def_sample1, embedding_data_for_search):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        populate_table_for_search(adapter, embedding_def_sample1, embedding_data_for_search)
        query_vector = [0.1] * embedding_def_sample1.dimensions
        
        target_obj_id = str(embedding_data_for_search[0].object_instance_id)
        
        results = adapter.query_similar_embeddings(
            embedding_definition_name=embedding_def_sample1.name,
            query_vector=query_vector,
            limit=5,
            filter_condition=f"object_instance_id = '{target_obj_id}'"
        )
        
        assert len(results) == 1
        assert results[0]["object_instance_id"] == target_obj_id
        assert "apple" in results[0]["source_text_preview"].lower()

        results_no_match_filter = adapter.query_similar_embeddings(
            embedding_definition_name=embedding_def_sample1.name,
            query_vector=query_vector,
            limit=5,
            filter_condition="source_text_preview = 'non_existent_text_for_filter'"
        )
        assert len(results_no_match_filter) == 0

    finally:
        if adapter:
            adapter.close()

def test_query_similar_embeddings_table_not_exist(temp_lancedb_uri, embedding_def_sample1):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        query_vector = [0.1] * embedding_def_sample1.dimensions
        # Adjusted regex to be more flexible
        with pytest.raises(SchemaError, match=f"LanceDB: Table '{embedding_def_sample1.name}' for ED '{embedding_def_sample1.name}' not found. Error: Table '{embedding_def_sample1.name}' was not found"):
            adapter.query_similar_embeddings(
                embedding_definition_name=embedding_def_sample1.name,
                query_vector=query_vector
            )
    finally:
        if adapter:
            adapter.close()

def test_query_similar_embeddings_no_results_found(temp_lancedb_uri, embedding_def_sample1):
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        adapter.create_embedding_table(embedding_def_sample1)
        query_vector = [0.1] * embedding_def_sample1.dimensions
        
        results = adapter.query_similar_embeddings(
            embedding_definition_name=embedding_def_sample1.name,
            query_vector=query_vector
        )
        assert len(results) == 0
    finally:
        if adapter:
            adapter.close()

def test_find_similar_embeddings_calls_query_similar(temp_lancedb_uri, embedding_def_sample1):
    """
    Tests that the compatibility `find_similar_embeddings` method correctly calls
    the new `query_similar_embeddings` method and processes its results.
    """
    adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
    try:
        # Mock the new query_similar_embeddings method
        mock_query_results = [
            {
                "object_instance_id": str(uuid4()), 
                "vector": [0.1] * embedding_def_sample1.dimensions, 
                "source_text_preview": "mock preview 1",
                "_distance": 0.01
            },
            {
                "object_instance_id": str(uuid4()), 
                "vector": [0.2] * embedding_def_sample1.dimensions, 
                "source_text_preview": "mock preview 2",
                "_distance": 0.02
            }
        ]
        adapter.query_similar_embeddings = MagicMock(return_value=mock_query_results)
        
        query_vector = [0.15] * embedding_def_sample1.dimensions
        top_k = 2
        
        results_instances = adapter.find_similar_embeddings(
            embedding_definition_name=embedding_def_sample1.name,
            vector=query_vector,
            top_k=top_k
        )
        
        adapter.query_similar_embeddings.assert_called_once_with(
            embedding_definition_name=embedding_def_sample1.name,
            query_vector=query_vector,
            limit=top_k,
            filter_condition=None
        )
        
        assert len(results_instances) == len(mock_query_results)
        for i, res_inst in enumerate(results_instances):
            assert isinstance(res_inst, EmbeddingInstance)
            assert res_inst.object_instance_id == UUID(mock_query_results[i]["object_instance_id"])
            assert res_inst.vector == mock_query_results[i]["vector"]
            assert res_inst.source_text_preview == mock_query_results[i]["source_text_preview"]
            assert res_inst.embedding_definition_name == embedding_def_sample1.name

    finally:
        if adapter:
            adapter.close()


class TestLanceDBAdapterQueryEngineMethods:
    @pytest.fixture(autouse=True)
    def setup_lancedb_data(self, temp_lancedb_uri, embedding_def_sample1, embedding_data_for_search):
        self.adapter = LanceDBAdapter(db_uri=temp_lancedb_uri)
        self.embedding_def = embedding_def_sample1
        self.embedding_data = embedding_data_for_search
        populate_table_for_search(self.adapter, self.embedding_def, self.embedding_data)
        
        # Store IDs for easy access in tests
        self.ids_in_table = [inst.object_instance_id for inst in self.embedding_data]
        self.query_vector_close_to_first_two = [0.105] * self.embedding_def.dimensions

        yield # For teardown if adapter needs explicit close in fixture, but it's handled in test methods

        self.adapter.close()


    def test_find_object_ids_by_similarity_basic(self):
        """Test basic search, returns only IDs and respects limit."""
        results_ids = self.adapter.find_object_ids_by_similarity(
            embedding_definition_name=self.embedding_def.name,
            query_vector=self.query_vector_close_to_first_two,
            limit=2
        )
        assert len(results_ids) == 2
        # The top 2 results from embedding_data_for_search are self.ids_in_table[0] and self.ids_in_table[1]
        # Order might vary if distances are identical, so check set equality
        # The method returns (UUID, distance) tuples. Extract IDs for comparison.
        result_ids_only = {res_id for res_id, _ in results_ids}
        assert result_ids_only == {self.ids_in_table[0], self.ids_in_table[1]}

    def test_find_object_ids_by_similarity_with_initial_ids(self):
        """Test filtering results based on initial_ids."""
        # Query vector is close to ids_in_table[0] and ids_in_table[1].
        # Provide initial_ids that include one of them and one that's not as close.
        initial_ids = [self.ids_in_table[1], self.ids_in_table[3]]
        
        results_ids = self.adapter.find_object_ids_by_similarity(
            embedding_definition_name=self.embedding_def.name,
            query_vector=self.query_vector_close_to_first_two,
            limit=5, # High limit to ensure similarity search itself doesn't exclude
            initial_ids=initial_ids
        )
        # Should only return ids_in_table[1] because it's in initial_ids and is among the most similar.
        # ids_in_table[3] is in initial_ids but is not among the most similar to the query_vector.
        # ids_in_table[0] is very similar but not in initial_ids.
        # The current implementation returns all initial_ids that are found in the similarity search results.
        # The query is close to id[0] and id[1]. The initial_ids are id[1] and id[3].
        # The search result will contain id[1] and id[3] (since limit is high).
        # Thus, the expected length is 2.
        assert len(results_ids) == 2
        result_ids_only = {res_id for res_id, _ in results_ids}
        assert result_ids_only == {self.ids_in_table[1], self.ids_in_table[3]}

    def test_find_object_ids_by_similarity_with_empty_initial_ids(self):
        """Test with empty initial_ids, should return empty list."""
        results_ids = self.adapter.find_object_ids_by_similarity(
            embedding_definition_name=self.embedding_def.name,
            query_vector=self.query_vector_close_to_first_two,
            limit=2,
            initial_ids=[]
        )
        assert len(results_ids) == 0

    def test_find_object_ids_by_similarity_with_non_matching_initial_ids(self):
        """Test when initial_ids are provided but none are in the top similarity results."""
        # Query vector is close to ids_in_table[0] and ids_in_table[1].
        # Provide initial_ids that are not close.
        initial_ids = [self.ids_in_table[2], self.ids_in_table[3]]
        
        results_ids = self.adapter.find_object_ids_by_similarity(
            embedding_definition_name=self.embedding_def.name,
            query_vector=self.query_vector_close_to_first_two,
            limit=2,
            initial_ids=initial_ids
        )
        assert len(results_ids) == 0 # None of the initial_ids are among the top 2 similar

    def test_find_object_ids_by_similarity_no_results_from_search(self):
        """Test when the similarity search itself yields no results (e.g., very high threshold implicitly)."""
        # This is hard to test directly without a threshold parameter in find_object_ids_by_similarity
        # or by mocking the underlying search to return empty.
        # For now, we assume if lancedb search returns empty, this method returns empty.
        # We can test this by querying with a vector very far from all existing data,
        # though lancedb will always return *something* unless the table is empty or limit is 0.
        # Let's test with an empty table scenario (by dropping and re-creating an empty one).
        
        self.adapter.drop_embedding_table(self.embedding_def.name)
        self.adapter.create_embedding_table(self.embedding_def) # Now it's empty

        results_ids = self.adapter.find_object_ids_by_similarity(
            embedding_definition_name=self.embedding_def.name,
            query_vector=self.query_vector_close_to_first_two,
            limit=2
        )
        assert len(results_ids) == 0

    def test_find_object_ids_by_similarity_table_not_exist(self):
        """Test behavior when the target table does not exist."""
        with pytest.raises(SchemaError, match="LanceDB: Table 'non_existent_def' for ED 'non_existent_def' not found."):
            self.adapter.find_object_ids_by_similarity(
                embedding_definition_name="non_existent_def",
                query_vector=self.query_vector_close_to_first_two,
                limit=2
            )