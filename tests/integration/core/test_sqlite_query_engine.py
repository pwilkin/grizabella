import pytest
from uuid import uuid4
from grizabella.core.models import (
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDefinition,
    PropertyDataType,
)
from grizabella.core.query_models import (
    ComplexQuery,
    QueryComponent,
    RelationalFilter,
    LogicalGroup,
    LogicalOperator,
    NotClause,
)
from grizabella.core.db_manager import GrizabellaDBManager
import tempfile
import shutil
from pathlib import Path

@pytest.fixture
def db_manager():
    """
    Provides a GrizabellaDBManager instance with an in-memory SQLite database,
    pre-populated with test data.
    """
    db_dir = tempfile.mkdtemp(prefix="grizabella_sqlite_integration_")
    db_path = Path(db_dir)
    
    manager = GrizabellaDBManager(db_name_or_path=db_path)

    # Define a test object type
    otd = ObjectTypeDefinition(
        name="TestObject",
        properties=[
            PropertyDefinition(name="name", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="value", data_type=PropertyDataType.INTEGER),
            PropertyDefinition(name="category", data_type=PropertyDataType.TEXT),
        ],
    )
    manager.add_object_type_definition(otd)

    # Add test instances
    instances = [
        ObjectInstance(id=uuid4(), object_type_name="TestObject", properties={"name": "A", "value": 10, "category": "cat1"}),
        ObjectInstance(id=uuid4(), object_type_name="TestObject", properties={"name": "B", "value": 20, "category": "cat1"}),
        ObjectInstance(id=uuid4(), object_type_name="TestObject", properties={"name": "C", "value": 30, "category": "cat2"}),
        ObjectInstance(id=uuid4(), object_type_name="TestObject", properties={"name": "D", "value": 40, "category": "cat2"}),
    ]
    
    for inst in instances:
        manager.upsert_object_instance(inst)

    # Store instances in the fixture for easy access in tests
    
    yield manager, instances

    manager.close()
    shutil.rmtree(db_dir)

def get_instance_ids(instances, names):
    return {inst.id for inst in instances if inst.properties["name"] in names}

def test_logical_and(db_manager):
    """Tests a LogicalGroup with an AND operator."""
    manager, instances = db_manager
    
    # Query for objects with value > 15 AND category == "cat1"
    # Expected: "B"
    query = ComplexQuery(
        query_root=LogicalGroup(
            operator=LogicalOperator.AND,
            clauses=[
                QueryComponent(
                    object_type_name="TestObject",
                    relational_filters=[RelationalFilter(property_name="value", operator=">", value=15)],
                ),
                QueryComponent(
                    object_type_name="TestObject",
                    relational_filters=[RelationalFilter(property_name="category", operator="==", value="cat1")],
                ),
            ],
        )
    )

    result = manager.process_complex_query(query)
    
    assert not result.errors
    assert len(result.object_instances) == 1
    assert result.object_instances[0].id in get_instance_ids(instances, ["B"])

def test_logical_or(db_manager):
    """Tests a LogicalGroup with an OR operator."""
    manager, instances = db_manager

    # Query for objects with value < 15 OR category == "cat2"
    # Expected: "A", "C", "D"
    query = ComplexQuery(
        query_root=LogicalGroup(
            operator=LogicalOperator.OR,
            clauses=[
                QueryComponent(
                    object_type_name="TestObject",
                    relational_filters=[RelationalFilter(property_name="value", operator="<", value=15)],
                ),
                QueryComponent(
                    object_type_name="TestObject",
                    relational_filters=[RelationalFilter(property_name="category", operator="==", value="cat2")],
                ),
            ],
        )
    )

    result = manager.process_complex_query(query)

    assert not result.errors
    assert len(result.object_instances) == 3
    
    expected_ids = get_instance_ids(instances, ["A", "C", "D"])
    result_ids = {inst.id for inst in result.object_instances}
    assert result_ids == expected_ids

def test_not_clause(db_manager):
    """Tests a NotClause."""
    manager, instances = db_manager

    # Query for objects NOT in category "cat1"
    # Expected: "C", "D"
    query = ComplexQuery(
        query_root=NotClause(
            clause=QueryComponent(
                object_type_name="TestObject",
                relational_filters=[RelationalFilter(property_name="category", operator="==", value="cat1")],
            )
        )
    )

    result = manager.process_complex_query(query)

    assert not result.errors
    assert len(result.object_instances) == 2

    expected_ids = get_instance_ids(instances, ["C", "D"])
    result_ids = {inst.id for inst in result.object_instances}
    assert result_ids == expected_ids

def test_nested_query(db_manager):
    """Tests a nested query: (value > 15 AND category == "cat2") OR name == "A"."""
    manager, instances = db_manager

    # Expected: "C", "D", "A"
    query = ComplexQuery(
        query_root=LogicalGroup(
            operator=LogicalOperator.OR,
            clauses=[
                LogicalGroup(
                    operator=LogicalOperator.AND,
                    clauses=[
                        QueryComponent(
                            object_type_name="TestObject",
                            relational_filters=[RelationalFilter(property_name="value", operator=">", value=15)],
                        ),
                        QueryComponent(
                            object_type_name="TestObject",
                            relational_filters=[RelationalFilter(property_name="category", operator="==", value="cat2")],
                        ),
                    ],
                ),
                QueryComponent(
                    object_type_name="TestObject",
                    relational_filters=[RelationalFilter(property_name="name", operator="==", value="A")],
                ),
            ],
        )
    )

    result = manager.process_complex_query(query)

    assert not result.errors
    assert len(result.object_instances) == 3

    expected_ids = get_instance_ids(instances, ["A", "C", "D"])
    result_ids = {inst.id for inst in result.object_instances}
    assert result_ids == expected_ids