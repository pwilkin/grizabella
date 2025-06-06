import pytest
from uuid import uuid4
import numpy as np
from grizabella.core.models import (
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDefinition,
    PropertyDataType,
    EmbeddingDefinition,
)
from grizabella.core.query_models import (
    ComplexQuery,
    QueryComponent,
    RelationalFilter,
    EmbeddingSearchClause,
    LogicalGroup,
    LogicalOperator,
    NotClause,
)
from grizabella.core.db_manager import GrizabellaDBManager
import tempfile
import shutil
from pathlib import Path

# Mock embedding model for predictable vectors
class MockEmbeddingModel:
    def __init__(self, dimension=4):
        self.dimension = dimension

    def compute_source_embeddings(self, texts):
        embeddings = []
        for text in texts:
            if "apple" in text:
                embeddings.append(np.array([1.0, 0.0, 0.0, 0.0]))
            elif "banana" in text:
                embeddings.append(np.array([0.0, 1.0, 0.0, 0.0]))
            elif "cat" in text:
                embeddings.append(np.array([0.0, 0.0, 1.0, 0.0]))
            else:
                embeddings.append(np.array([0.0, 0.0, 0.0, 1.0]))
        return embeddings

    def compute_query_embeddings(self, texts):
        return self.compute_source_embeddings(texts)

@pytest.fixture
def db_manager_with_lancedb(monkeypatch):
    """
    Provides a GrizabellaDBManager instance with both SQLite and LanceDB,
    pre-populated with test data and embeddings.
    """
    db_dir = tempfile.mkdtemp(prefix="grizabella_lancedb_integration_")
    db_path = Path(db_dir)
    
    manager = GrizabellaDBManager(db_name_or_path=db_path)

    # Mock the embedding model loading
    mock_model = MockEmbeddingModel()
    monkeypatch.setattr(
        "grizabella.db_layers.lancedb.lancedb_adapter.LanceDBAdapter.get_embedding_model",
        lambda self, model_identifier: mock_model
    )

    # Define a test object type
    otd = ObjectTypeDefinition(
        name="Doc",
        properties=[
            PropertyDefinition(name="content", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="author", data_type=PropertyDataType.TEXT),
        ],
    )
    manager.add_object_type_definition(otd)

    # Define an embedding on the 'content' property
    ed = EmbeddingDefinition(
        name="content_embedding",
        object_type_name="Doc",
        source_property_name="content",
        embedding_model="mock/model",
        dimensions=4,
    )
    manager.add_embedding_definition(ed)

    # Add test instances
    instances = [
        ObjectInstance(id=uuid4(), object_type_name="Doc", properties={"content": "An apple a day", "author": "alice"}),
        ObjectInstance(id=uuid4(), object_type_name="Doc", properties={"content": "A ripe banana", "author": "bob"}),
        ObjectInstance(id=uuid4(), object_type_name="Doc", properties={"content": "A curious cat", "author": "alice"}),
        ObjectInstance(id=uuid4(), object_type_name="Doc", properties={"content": "Another apple story", "author": "charlie"}),
    ]
    
    for inst in instances:
        manager.upsert_object_instance(inst)

    yield manager, instances

    manager.close()
    shutil.rmtree(db_dir)

def get_instance_ids(instances, content_substrings):
    return {inst.id for inst in instances if any(sub in inst.properties["content"] for sub in content_substrings)}
def test_logical_and_with_lancedb(db_manager_with_lancedb):
    """Tests AND operator combining a relational filter (SQLite) and an embedding search (LanceDB)."""
    manager, instances = db_manager_with_lancedb

    # Query for docs by author "alice" AND similar to "apple"
    # Expected: The "An apple a day" doc.
    query = ComplexQuery(
        query_root=LogicalGroup(
            operator=LogicalOperator.AND,
            clauses=[
                QueryComponent(
                    object_type_name="Doc",
                    relational_filters=[RelationalFilter(property_name="author", operator="==", value="alice")],
                ),
                QueryComponent(
                    object_type_name="Doc",
                    embedding_searches=[
                        EmbeddingSearchClause(
                            embedding_definition_name="content_embedding",
                            similar_to_payload=[1.0, 0.0, 0.0, 0.0],  # Vector for "apple"
                            limit=2,
                        )
                    ],
                ),
            ],
        ),
    )

    result = manager.process_complex_query(query)

    assert not result.errors
    assert len(result.object_instances) == 1
    expected_ids = get_instance_ids(instances, ["An apple a day"])
    assert result.object_instances[0].id in expected_ids

def test_logical_or_with_lancedb(db_manager_with_lancedb):
    """Tests OR operator combining a relational filter and an embedding search."""
    manager, instances = db_manager_with_lancedb

    # Query for docs by author "bob" OR similar to "apple"
    # Expected: "A ripe banana" (by bob), "An apple a day", "Another apple story"
    query = ComplexQuery(
        query_root=LogicalGroup(
            operator=LogicalOperator.OR,
            clauses=[
                QueryComponent(
                    object_type_name="Doc",
                    relational_filters=[RelationalFilter(property_name="author", operator="==", value="bob")],
                ),
                QueryComponent(
                    object_type_name="Doc",
                    embedding_searches=[
                        EmbeddingSearchClause(
                            embedding_definition_name="content_embedding",
                            similar_to_payload=[1.0, 0.0, 0.0, 0.0],  # Vector for "apple"
                            limit=2,
                        )
                    ],
                ),
            ],
        ),
    )

    result = manager.process_complex_query(query)

    assert not result.errors
    assert len(result.object_instances) == 3
    expected_ids = get_instance_ids(instances, ["ripe banana", "apple"])
    result_ids = {inst.id for inst in result.object_instances}
    assert result_ids == expected_ids

def test_not_clause_with_lancedb(db_manager_with_lancedb):
    """Tests a NotClause on an embedding search."""
    manager, instances = db_manager_with_lancedb

    # Query for docs NOT similar to "apple"
    # Expected: "A ripe banana", "A curious cat"
    query = ComplexQuery(
        query_root=NotClause(
            clause=QueryComponent(
                object_type_name="Doc",
                embedding_searches=[
                    EmbeddingSearchClause(
                        embedding_definition_name="content_embedding",
                        similar_to_payload=[1.0, 0.0, 0.0, 0.0],  # Vector for "apple"
                        limit=2,
                    )
                ],
            )
        ),
    )

    result = manager.process_complex_query(query)

    assert not result.errors
    assert len(result.object_instances) == 2
    expected_ids = get_instance_ids(instances, ["banana", "cat"])
    result_ids = {inst.id for inst in result.object_instances}
    assert result_ids == expected_ids

def test_nested_query_with_lancedb(db_manager_with_lancedb):
    """Tests a nested query with both relational and embedding clauses."""
    manager, instances = db_manager_with_lancedb

    # Query for: (author is "alice" AND content is similar to "cat") OR (author is "charlie")
    # Expected: "A curious cat" (alice AND cat), "Another apple story" (charlie)
    query = ComplexQuery(
        query_root=LogicalGroup(
            operator=LogicalOperator.OR,
            clauses=[
                LogicalGroup(
                    operator=LogicalOperator.AND,
                    clauses=[
                        QueryComponent(
                            object_type_name="Doc",
                            relational_filters=[RelationalFilter(property_name="author", operator="==", value="alice")],
                        ),
                        QueryComponent(
                            object_type_name="Doc",
                            embedding_searches=[
                                EmbeddingSearchClause(
                                    embedding_definition_name="content_embedding",
                                    similar_to_payload=[0.0, 0.0, 1.0, 0.0],  # Vector for "cat"
                                    limit=1,
                                )
                            ],
                        ),
                    ],
                ),
                QueryComponent(
                    object_type_name="Doc",
                    relational_filters=[RelationalFilter(property_name="author", operator="==", value="charlie")],
                ),
            ],
        ),
    )

    result = manager.process_complex_query(query)

    assert not result.errors
    assert len(result.object_instances) == 2
    expected_ids = get_instance_ids(instances, ["curious cat", "Another apple story"])
    result_ids = {inst.id for inst in result.object_instances}
    assert result_ids == expected_ids