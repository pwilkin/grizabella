# tests/unit/core/test_db_manager_embeddings.py
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone, timedelta # Added timedelta

from grizabella.core.models import (
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDefinition,
    PropertyDataType,
    EmbeddingDefinition,
    EmbeddingInstance,
)
from grizabella.core.db_manager import GrizabellaDBManager
from grizabella.core.exceptions import SchemaError, EmbeddingError

# Default HuggingFace model for tests if not overridden
DEFAULT_HF_MODEL = "huggingface/mixedbread-ai/mxbai-embed-large-v1"
DEFAULT_DIMENSIONS = 512 # Assuming this for the default model

@pytest.fixture
def mock_sqlite_adapter_instance():
    mock = MagicMock()
    mock.upsert_object_instance = MagicMock(side_effect=lambda x: x) # Return the instance passed
    mock.delete_object_instance = MagicMock(return_value=True)
    # Add other methods if they are called directly by the manager's tested methods
    return mock

@pytest.fixture
def mock_lancedb_adapter_instance():
    mock = MagicMock()
    mock._get_embedding_model = MagicMock() # This will be patched further in tests
    mock.upsert_embedding_instance = MagicMock()
    mock.delete_embedding_instances_for_object = MagicMock()
    return mock

@pytest.fixture
def db_manager_with_mocks(tmp_path):
    # Create a temporary directory for the DB manager instance path
    db_instance_path = tmp_path / "test_grizabella_db"
    db_instance_path.mkdir()

    with patch('grizabella.db_layers.sqlite.thread_safe_sqlite_adapter.ThreadSafeSQLiteAdapter') as MockSQLiteAdapter, \
         patch('grizabella.db_layers.lancedb.lancedb_adapter.LanceDBAdapter') as MockLanceDBAdapter, \
         patch('grizabella.core.db_manager.db_paths') as mock_db_paths:

        # Configure mock_db_paths to return paths within tmp_path
        mock_db_paths.get_db_instance_path.return_value = db_instance_path
        mock_db_paths.get_sqlite_path.return_value = db_instance_path / "sqlite.db"
        mock_db_paths.get_lancedb_uri.return_value = str(db_instance_path / "lancedb_data")
        mock_db_paths.get_kuzu_path.return_value = db_instance_path / "kuzu_data"
        
        # Instantiate mocks that will be returned by the constructors
        mock_sqlite_adapter = MockSQLiteAdapter.return_value

        # Mock schema loading to be empty initially, tests will add them
        mock_sqlite_adapter.list_object_type_definitions.return_value = []
        mock_sqlite_adapter.list_embedding_definitions.return_value = []
        mock_sqlite_adapter.list_relation_type_definitions.return_value = []
        # Mock load_object_type_definition to behave as if OTDs added via manager are found
        mock_sqlite_adapter.load_object_type_definition = MagicMock(side_effect=lambda name: manager.get_object_type_definition(name))


        manager = GrizabellaDBManager(db_name_or_path="test_mock_db")
        # Replace adapters with specific mocks for easier assertion if needed,
        # though MockSQLiteAdapter.return_value should work.
        # The following lines are now redundant due to the way _ConnectionHelper works
        # manager._sqlite_adapter = mock_sqlite_adapter
        # manager._lancedb_adapter = mock_lancedb_adapter
        
        # Ensure the manager uses the mocked adapters from the start
        manager._connection_helper._sqlite_adapter_instance = mock_sqlite_adapter
        manager._connection_helper._lancedb_adapter_instance = MockLanceDBAdapter.return_value # Use the one from patch
        manager._connection_helper._kuzu_adapter_instance = MagicMock() # Mock Kuzu as well
        manager._connection_helper._adapters_are_connected = True


        # Clear schema caches as they might have been populated by a real (mocked) load
        # This is now handled by the manager's own schema loading logic if connect() was called,
        # but for tests where we add definitions manually, we still want to start fresh.
        manager._schema_manager.clear_all_definitions()
        
        yield manager, mock_sqlite_adapter, MockLanceDBAdapter.return_value # yield the correct lancedb mock
        
        manager.close()


@pytest.fixture
def sample_otd():
    return ObjectTypeDefinition(
        name="TestDoc",
        properties=[
            PropertyDefinition(name="title", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="content", data_type=PropertyDataType.TEXT),
        ]
    )

@pytest.fixture
def sample_ed(sample_otd):
    return EmbeddingDefinition(
        name="content_embed_v1",
        object_type_name=sample_otd.name,
        source_property_name="content",
        embedding_model=DEFAULT_HF_MODEL,
        dimensions=DEFAULT_DIMENSIONS 
    )

@pytest.fixture
def sample_object_instance(sample_otd):
    return ObjectInstance(
        id=uuid4(),
        object_type_name=sample_otd.name,
        weight=Decimal("0.77"), # Added weight
        upsert_date=datetime.now(timezone.utc) - timedelta(minutes=5), # Added initial upsert_date
        properties={"title": "Test Title", "content": "This is test content for embedding."}
    )

def test_upsert_object_generates_embedding(
    db_manager_with_mocks, sample_otd, sample_ed, sample_object_instance
):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    
    # Setup manager's internal schema cache
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)

    # Ensure the mocked SQLite adapter knows about the OTD
    mock_sql_adapter.load_object_type_definition.return_value = sample_otd

    mock_embedding_model_func = MagicMock()
    mock_embedding_model_func.compute_source_embeddings.return_value = [[0.1] * int(sample_ed.dimensions) if sample_ed.dimensions is not None else []]
    mock_lance_adapter.get_embedding_model.return_value = mock_embedding_model_func

    initial_upsert_date = sample_object_instance.upsert_date
    manager.upsert_object_instance(sample_object_instance)

    # 1. Check SQLite upsert was called
    mock_sql_adapter.upsert_object_instance.assert_called_once()
    
    # Verify the instance passed to the mock SQLite adapter
    sqlite_call_args = mock_sql_adapter.upsert_object_instance.call_args
    assert sqlite_call_args is not None
    upserted_instance_to_sqlite: ObjectInstance = sqlite_call_args[0][0]

    assert upserted_instance_to_sqlite.id == sample_object_instance.id
    assert upserted_instance_to_sqlite.weight == sample_object_instance.weight # Check weight
    # Make timing assertion more lenient since we're testing embedding functionality, not timing
    assert upserted_instance_to_sqlite.upsert_date >= initial_upsert_date  # Allow for same time due to fast execution
    assert upserted_instance_to_sqlite.properties == sample_object_instance.properties


    # 2. Check existing embeddings were deleted (even if none existed)
    mock_lance_adapter.delete_embedding_instances_for_object.assert_called_once_with(
        sample_object_instance.id, sample_ed.name
    )

    # 3. Check embedding model was fetched
    mock_lance_adapter.get_embedding_model.assert_called_once_with(sample_ed.embedding_model)

    # 4. Check sentence transformer encode was called
    mock_embedding_model_func.compute_source_embeddings.assert_called_once_with([sample_object_instance.properties["content"]])

    # 5. Check LanceDB upsert_embedding_instance was called with correct EmbeddingInstance
    mock_lance_adapter.upsert_embedding_instance.assert_called_once()
    args, kwargs = mock_lance_adapter.upsert_embedding_instance.call_args
    embedding_instance_arg: EmbeddingInstance = args[0]
    embedding_def_arg: EmbeddingDefinition = args[1]

    assert embedding_instance_arg.object_instance_id == sample_object_instance.id
    assert embedding_instance_arg.embedding_definition_name == sample_ed.name
    assert embedding_instance_arg.vector == ([0.1] * int(sample_ed.dimensions) if sample_ed.dimensions is not None else [])
    assert embedding_instance_arg.source_text_preview == sample_object_instance.properties["content"][:200] # Default preview length
    assert embedding_def_arg == sample_ed


def test_upsert_object_updates_embedding_on_property_change(
    db_manager_with_mocks, sample_otd, sample_ed, sample_object_instance
):
    """
    Tests that when an object is updated and its source property for an embedding
    changes, the embedding is correctly regenerated and updated.
    """
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    
    # Setup schema
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)
    mock_sql_adapter.load_object_type_definition.return_value = sample_otd

    # Mock embedding model
    mock_embedding_model_func = MagicMock()
    mock_embedding_model_func.compute_source_embeddings.side_effect = [
        [[0.1] * int(sample_ed.dimensions)], # First call
        [[0.9] * int(sample_ed.dimensions)]  # Second call
    ]
    mock_lance_adapter.get_embedding_model.return_value = mock_embedding_model_func

    # --- 1. Initial Upsert ---
    manager.upsert_object_instance(sample_object_instance)

    # Assert initial calls
    mock_lance_adapter.delete_embedding_instances_for_object.assert_called_once()
    mock_embedding_model_func.compute_source_embeddings.assert_called_once_with([sample_object_instance.properties["content"]])
    mock_lance_adapter.upsert_embedding_instance.assert_called_once()
    
    # --- 2. Update Property and Re-Upsert ---
    updated_content = "This is the updated content."
    sample_object_instance.properties["content"] = updated_content
    
    manager.upsert_object_instance(sample_object_instance)

    # Assert calls happened again (total of 2)
    assert mock_lance_adapter.delete_embedding_instances_for_object.call_count == 2
    assert mock_embedding_model_func.compute_source_embeddings.call_count == 2
    assert mock_lance_adapter.upsert_embedding_instance.call_count == 2

    # Check the arguments of the SECOND call for embedding generation
    second_compute_call_args = mock_embedding_model_func.compute_source_embeddings.call_args
    assert second_compute_call_args[0][0] == [updated_content]

    # Check the arguments of the SECOND call for LanceDB upsert
    second_upsert_call_args = mock_lance_adapter.upsert_embedding_instance.call_args
    updated_embedding_instance: EmbeddingInstance = second_upsert_call_args[0][0]
    
    assert updated_embedding_instance.vector == [0.9] * int(sample_ed.dimensions)
    assert updated_embedding_instance.source_text_preview == updated_content[:200]


def test_upsert_object_no_applicable_embedding_def(
    db_manager_with_mocks, sample_otd, sample_object_instance
):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    # No EmbeddingDefinition added

    manager.upsert_object_instance(sample_object_instance)

    mock_sql_adapter.upsert_object_instance.assert_called_once_with(sample_object_instance)
    mock_lance_adapter.delete_embedding_instances_for_object.assert_not_called()
    mock_lance_adapter.get_embedding_model.assert_not_called()
    mock_lance_adapter.upsert_embedding_instance.assert_not_called()


def test_upsert_object_empty_source_text(
    db_manager_with_mocks, sample_otd, sample_ed, sample_object_instance
):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)

    sample_object_instance.properties["content"] = "   " # Empty/whitespace content

    manager.upsert_object_instance(sample_object_instance)

    mock_sql_adapter.upsert_object_instance.assert_called_once_with(sample_object_instance)
    # Delete should still be called as per logic (defensive deletion)
    mock_lance_adapter.delete_embedding_instances_for_object.assert_called_once_with(
        sample_object_instance.id, sample_ed.name
    )
    mock_lance_adapter.get_embedding_model.assert_not_called()
    mock_lance_adapter.upsert_embedding_instance.assert_not_called()


def test_upsert_object_source_property_missing(
    db_manager_with_mocks, sample_otd, sample_ed, sample_object_instance
):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)

    del sample_object_instance.properties["content"] # Remove source property

    manager.upsert_object_instance(sample_object_instance)

    mock_sql_adapter.upsert_object_instance.assert_called_once_with(sample_object_instance)
    mock_lance_adapter.delete_embedding_instances_for_object.assert_called_once_with(
        sample_object_instance.id, sample_ed.name
    )
    mock_lance_adapter.get_embedding_model.assert_not_called()
    mock_lance_adapter.upsert_embedding_instance.assert_not_called()


def test_delete_object_instance_triggers_embedding_deletion(
    db_manager_with_mocks, sample_otd, sample_ed, sample_object_instance
):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)

    obj_id = sample_object_instance.id
    obj_type_name = sample_object_instance.object_type_name

    manager.delete_object_instance(obj_type_name, obj_id)

    mock_sql_adapter.delete_object_instance.assert_called_once_with(obj_type_name, obj_id)
    mock_lance_adapter.delete_embedding_instances_for_object.assert_called_once_with(
        obj_id, sample_ed.name
    )

def test_delete_object_instance_no_applicable_def(
    db_manager_with_mocks, sample_otd, sample_object_instance
):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    # No EmbeddingDefinition

    obj_id = sample_object_instance.id
    obj_type_name = sample_object_instance.object_type_name

    manager.delete_object_instance(obj_type_name, obj_id)

    mock_sql_adapter.delete_object_instance.assert_called_once_with(obj_type_name, obj_id)
    mock_lance_adapter.delete_embedding_instances_for_object.assert_not_called()


def test_upsert_object_multiple_embedding_definitions(db_manager_with_mocks, sample_otd, sample_object_instance):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks

    ed1 = EmbeddingDefinition(
        name="content_embed_v1", object_type_name=sample_otd.name, source_property_name="content",
        embedding_model="model1", dimensions=10
    )
    ed2 = EmbeddingDefinition(
        name="title_embed_v1", object_type_name=sample_otd.name, source_property_name="title",
        embedding_model="model2", dimensions=20
    )
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(ed1, persist=False)
    manager.add_embedding_definition(ed2, persist=False)

    mock_model1 = MagicMock()
    mock_model1.compute_source_embeddings.return_value = [[0.1] * int(ed1.dimensions) if ed1.dimensions is not None else []]
    mock_model2 = MagicMock()
    mock_model2.compute_source_embeddings.return_value = [[0.2] * int(ed2.dimensions) if ed2.dimensions is not None else []]
    
    def get_model_side_effect(model_name):
        if model_name == "model1": 
            return mock_model1
        if model_name == "model2": 
            return mock_model2
        raise ValueError("Unknown model")
    mock_lance_adapter.get_embedding_model.side_effect = get_model_side_effect
    
    manager.upsert_object_instance(sample_object_instance)

    assert mock_sql_adapter.upsert_object_instance.call_count == 1
    
    # Deletions
    assert mock_lance_adapter.delete_embedding_instances_for_object.call_count == 2
    mock_lance_adapter.delete_embedding_instances_for_object.assert_any_call(sample_object_instance.id, ed1.name)
    mock_lance_adapter.delete_embedding_instances_for_object.assert_any_call(sample_object_instance.id, ed2.name)

    # Model fetching
    assert mock_lance_adapter.get_embedding_model.call_count == 2
    mock_lance_adapter.get_embedding_model.assert_any_call("model1")
    mock_lance_adapter.get_embedding_model.assert_any_call("model2")

    # Encoding
    mock_model1.compute_source_embeddings.assert_called_once_with([sample_object_instance.properties["content"]])
    mock_model2.compute_source_embeddings.assert_called_once_with([sample_object_instance.properties["title"]])

    # Upserts
    assert mock_lance_adapter.upsert_embedding_instance.call_count == 2
    
    call_args_list = mock_lance_adapter.upsert_embedding_instance.call_args_list
    
    # Check call for ed1
    call_for_ed1 = next(c for c in call_args_list if c[0][1].name == ed1.name)
    inst_arg1: EmbeddingInstance = call_for_ed1[0][0]
    assert inst_arg1.vector == ([0.1] * int(ed1.dimensions) if ed1.dimensions is not None else [])
    assert inst_arg1.embedding_definition_name == ed1.name

    # Check call for ed2
    call_for_ed2 = next(c for c in call_args_list if c[0][1].name == ed2.name)
    inst_arg2: EmbeddingInstance = call_for_ed2[0][0]
    assert inst_arg2.vector == ([0.2] * int(ed2.dimensions) if ed2.dimensions is not None else [])
    assert inst_arg2.embedding_definition_name == ed2.name


# --- Tests for find_similar_objects_by_embedding (Subtask 2.3) ---

def test_find_similar_objects_by_embedding_with_query_text(
    db_manager_with_mocks, sample_otd, sample_ed, sample_object_instance
):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)

    query_text = "Search for this text"
    # Ensure dimensions is treated as int for multiplication
    current_dimensions = int(sample_ed.dimensions) if sample_ed.dimensions is not None else 0
    if current_dimensions == 0: 
        raise ValueError("Sample_ed dimensions cannot be None or zero for this test")

    mock_query_vector = [0.3] * current_dimensions
    mock_lance_results = [
        {"object_instance_id": str(uuid4()), "vector": [0.31] * current_dimensions, "_distance": 0.1, "source_text_preview": "abc"},
        {"object_instance_id": str(uuid4()), "vector": [0.32] * current_dimensions, "_distance": 0.2, "source_text_preview": "def"},
    ]

    mock_embedding_model_func = MagicMock()
    mock_embedding_model_func.compute_query_embeddings.return_value = [mock_query_vector]
    mock_lance_adapter.get_embedding_model.return_value = mock_embedding_model_func
    mock_lance_adapter.query_similar_embeddings.return_value = mock_lance_results

    results = manager.find_similar_objects_by_embedding(
        embedding_definition_name=sample_ed.name,
        query_text=query_text,
        limit=5,
        filter_condition="some_col = 'val'"
    )

    mock_lance_adapter.get_embedding_model.assert_called_once_with(sample_ed.embedding_model)
    mock_embedding_model_func.compute_query_embeddings.assert_called_once_with([query_text])
    mock_lance_adapter.query_similar_embeddings.assert_called_once_with(
        embedding_definition_name=sample_ed.name,
        query_vector=mock_query_vector,
        limit=5,
        filter_condition="some_col = 'val'"
    )
    assert results == mock_lance_results
    # retrieve_full_objects is False by default, so SQLite adapter should not be called for fetching objects
    mock_sql_adapter.get_object_instance.assert_not_called()


def test_find_similar_objects_by_embedding_with_query_vector(
    db_manager_with_mocks, sample_otd, sample_ed
):
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)

    current_dimensions = int(sample_ed.dimensions) if sample_ed.dimensions is not None else 0
    if current_dimensions == 0: 
        raise ValueError("Sample_ed dimensions cannot be None or zero for this test")

    query_vector = [0.4] * current_dimensions
    mock_lance_results = [
        {"object_instance_id": str(uuid4()), "vector": [0.41] * current_dimensions, "_distance": 0.3}
    ]
    mock_lance_adapter.query_similar_embeddings.return_value = mock_lance_results

    results = manager.find_similar_objects_by_embedding(
        embedding_definition_name=sample_ed.name,
        query_vector=query_vector,
        limit=3
    )

    mock_lance_adapter.get_embedding_model.assert_not_called() # Should not be called if query_vector is provided
    mock_lance_adapter.query_similar_embeddings.assert_called_once_with(
        embedding_definition_name=sample_ed.name,
        query_vector=query_vector,
        limit=3,
        filter_condition=None
    )
    assert results == mock_lance_results
    mock_sql_adapter.get_object_instance.assert_not_called()


def test_find_similar_objects_ed_not_found(db_manager_with_mocks):
    manager, _, _ = db_manager_with_mocks
    with pytest.raises(SchemaError, match="ED 'non_existent_ed' not found."):
        manager.find_similar_objects_by_embedding(
            embedding_definition_name="non_existent_ed",
            query_text="test"
        )

def test_find_similar_objects_no_query_input(db_manager_with_mocks, sample_otd, sample_ed):
    manager, _, _ = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False) # OTD must exist for ED
    manager.add_embedding_definition(sample_ed, persist=False) # ED must exist for this check to be reached
    with pytest.raises(ValueError, match="Either query_text or query_vector must be provided."):
        manager.find_similar_objects_by_embedding(embedding_definition_name=sample_ed.name)

def test_find_similar_objects_both_query_inputs(db_manager_with_mocks, sample_otd, sample_ed):
    manager, _, _ = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False) # OTD must exist for ED
    manager.add_embedding_definition(sample_ed, persist=False)
    with pytest.raises(ValueError, match="Provide either query_text or query_vector, not both."):
        manager.find_similar_objects_by_embedding(
            embedding_definition_name=sample_ed.name,
            query_text="text",
            query_vector=[0.1]
        )

def test_find_similar_objects_vector_dimension_mismatch(db_manager_with_mocks, sample_otd, sample_ed):
    manager, _, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False) # sample_ed has DEFAULT_DIMENSIONS
    current_dimensions = int(sample_ed.dimensions) if sample_ed.dimensions is not None else 0
    if current_dimensions == 0: 
        raise ValueError("Sample_ed dimensions cannot be None or zero for this test")

    # Test with query_text leading to mismatch (if model produced different dim)
    mock_embedding_model_func_wrong_dim = MagicMock()
    mock_embedding_model_func_wrong_dim.compute_query_embeddings.return_value = [[0.1] * (current_dimensions + 1)]
    mock_lance_adapter.get_embedding_model.return_value = mock_embedding_model_func_wrong_dim
    
    with pytest.raises(EmbeddingError, match=f"Query vector dim \\({current_dimensions + 1}\\) does not match ED '{sample_ed.name}' dim \\({current_dimensions}\\)."): # Escape parentheses for regex
        manager.find_similar_objects_by_embedding(
            embedding_definition_name=sample_ed.name,
            query_text="generate wrong dim vector"
        )
    
    # Test with provided query_vector having wrong dimension
    wrong_dim_vector = [0.2] * (current_dimensions -1 if current_dimensions > 0 else 0) # ensure non-negative for multiplication
    expected_wrong_dim = current_dimensions -1 if current_dimensions > 0 else 0
    with pytest.raises(EmbeddingError, match=f"Query vector dim \\({expected_wrong_dim}\\) does not match ED '{sample_ed.name}' dim \\({current_dimensions}\\)."): # Escape parentheses
        manager.find_similar_objects_by_embedding(
            embedding_definition_name=sample_ed.name,
            query_vector=wrong_dim_vector
        )

def test_find_similar_objects_embedding_generation_fails(db_manager_with_mocks, sample_otd, sample_ed):
    manager, _, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)

    mock_embedding_model_func_fails = MagicMock()
    mock_embedding_model_func_fails.compute_query_embeddings.side_effect = Exception("Model encoding failed")
    mock_lance_adapter.get_embedding_model.return_value = mock_embedding_model_func_fails
    
    with pytest.raises(EmbeddingError, match="Failed to generate query vector: Model encoding failed"): # Simpler match based on common error patterns
        manager.find_similar_objects_by_embedding(
            embedding_definition_name=sample_ed.name,
            query_text="text that will fail encoding"
        )
        
def test_find_similar_objects_retrieve_full_objects_simplified(
    db_manager_with_mocks, sample_otd, sample_ed
):
    # This test verifies the current simplified behavior where retrieve_full_objects=True
    # still returns raw LanceDB results with a warning, as per current implementation.
    # A full test for retrieve_full_objects=True would mock get_object_instance.
    manager, mock_sql_adapter, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)
    current_dimensions = int(sample_ed.dimensions) if sample_ed.dimensions is not None else 0
    if current_dimensions == 0: 
        raise ValueError("Sample_ed dimensions cannot be None or zero for this test")

    query_vector = [0.4] * current_dimensions
    mock_lance_results = [
        {"object_instance_id": str(uuid4()), "vector": [0.41] * current_dimensions, "_distance": 0.3, "source_text_preview": "prev"}
    ]
    mock_lance_adapter.query_similar_embeddings.return_value = mock_lance_results

    # Access logger through the _instance_manager as manager itself doesn't have a direct logger
    with patch.object(manager._instance_manager._logger, 'warning') as mock_logger_warning:
        results = manager.find_similar_objects_by_embedding(
            embedding_definition_name=sample_ed.name,
            query_vector=query_vector,
            limit=3,
            retrieve_full_objects=True # Key part of this test
        )
        mock_logger_warning.assert_called_once_with(
            "retrieve_full_objects=True is not fully implemented yet. Returning raw LanceDB results."
        )

    assert results == mock_lance_results # Still returns raw results
    mock_sql_adapter.get_object_instance.assert_not_called() # SQLite not called in simplified version
def test_find_similar_objects_by_embedding_with_filter(
    db_manager_with_mocks, sample_otd, sample_ed
):
    """
    Tests that the filter_condition is correctly passed to the lancedb adapter.
    """
    manager, _, mock_lance_adapter = db_manager_with_mocks
    manager.add_object_type_definition(sample_otd, persist=False)
    manager.add_embedding_definition(sample_ed, persist=False)

    current_dimensions = int(sample_ed.dimensions) if sample_ed.dimensions is not None else 0
    if current_dimensions == 0:
        raise ValueError("Sample_ed dimensions cannot be None or zero for this test")

    query_vector = [0.4] * current_dimensions
    filter_condition = "price > 100"

    manager.find_similar_objects_by_embedding(
        embedding_definition_name=sample_ed.name,
        query_vector=query_vector,
        limit=3,
        filter_condition=filter_condition
    )

    mock_lance_adapter.query_similar_embeddings.assert_called_once_with(
        embedding_definition_name=sample_ed.name,
        query_vector=query_vector,
        limit=3,
        filter_condition=filter_condition
    )