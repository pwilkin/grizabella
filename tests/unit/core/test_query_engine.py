"""Unit tests for the Complex Query Engine components (QueryPlanner and QueryExecutor)."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from grizabella.core.query_engine import (
    QueryPlanner,
    QueryExecutor,
    PlannedStep,
    PlannedComponentExecution,
    PlannedLogicalGroup,
    PlannedNotClause,
)
from grizabella.core.query_models import (
    ComplexQuery,
    QueryComponent,
    RelationalFilter,
    LogicalGroup,
    LogicalOperator,
    NotClause,
)
from grizabella.core.models import (
    ObjectTypeDefinition,
    EmbeddingDefinition,
    RelationTypeDefinition,
    PropertyDefinition,
    PropertyDataType,
)
from grizabella.core.db_manager import GrizabellaDBManager


@pytest.fixture
def mock_schema_manager_fixture():
    """Provides a mock _SchemaManager."""
    mock = MagicMock()
    mock.get_object_type_definition.return_value = ObjectTypeDefinition(
        name="TestObject",
        properties=[PropertyDefinition(name="prop1", data_type=PropertyDataType.TEXT)],
    )
    mock.get_embedding_definition.return_value = EmbeddingDefinition(
        name="TestEmbedding",
        object_type_name="TestObject",
        source_property_name="prop1",
        dimensions=10,
    )
    mock.get_relation_type_definition.return_value = RelationTypeDefinition(
        name="TestRelation",
        source_object_type_names=["TestObject"],
        target_object_type_names=["TestObject"],
    )
    mock.get_property_definition_for_object_type.return_value = PropertyDefinition(
        name="prop1", data_type=PropertyDataType.TEXT
    )
    return mock


@pytest.fixture
def mock_db_manager_fixture(mock_schema_manager_fixture: MagicMock):
    """Provides a mock GrizabellaDBManager with a mocked _SchemaManager."""
    mock = MagicMock(spec=GrizabellaDBManager)
    mock._schema_manager = mock_schema_manager_fixture
    mock.sqlite_adapter = MagicMock()
    mock.lancedb_adapter = MagicMock()
    mock.kuzu_adapter = MagicMock()
    mock.get_objects_by_ids.return_value = []
    return mock


@pytest.fixture
def query_planner_fixture(mock_db_manager_fixture: MagicMock) -> QueryPlanner:
    """Provides a QueryPlanner instance with a mocked GrizabellaDBManager."""
    return QueryPlanner(db_manager=mock_db_manager_fixture)


@pytest.fixture
def query_executor_fixture(mock_db_manager_fixture: MagicMock) -> QueryExecutor:
    """Provides a QueryExecutor instance with a mocked GrizabellaDBManager."""
    return QueryExecutor(db_manager=mock_db_manager_fixture)


# --- QueryPlanner Tests ---


def test_planner_backward_compatibility_with_components(
    query_planner_fixture: QueryPlanner,
):
    """Tests that the planner correctly transforms a legacy 'components' query."""
    qc1 = QueryComponent(object_type_name="TestObject")
    qc2 = QueryComponent(object_type_name="TestObject")
    query = ComplexQuery(components=[qc1, qc2])

    planned_query = query_planner_fixture.plan(query)

    assert isinstance(planned_query.plan_root, PlannedLogicalGroup)
    assert planned_query.plan_root.operator == LogicalOperator.AND
    assert len(planned_query.plan_root.clauses) == 2
    assert isinstance(planned_query.plan_root.clauses[0], PlannedComponentExecution)
    assert isinstance(planned_query.plan_root.clauses[1], PlannedComponentExecution)


def test_planner_creates_nested_logical_plan(query_planner_fixture: QueryPlanner):
    """Tests that the planner correctly creates a nested logical plan."""
    qc1 = QueryComponent(object_type_name="TestObject", relational_filters=[RelationalFilter(property_name="p1", operator="==", value="v1")])
    qc2 = QueryComponent(object_type_name="TestObject", relational_filters=[RelationalFilter(property_name="p2", operator="==", value="v2")])
    qc3 = QueryComponent(object_type_name="TestObject", relational_filters=[RelationalFilter(property_name="p3", operator="==", value="v3")])

    query = ComplexQuery(
        query_root=LogicalGroup(
            operator=LogicalOperator.AND,
            clauses=[
                qc1,
                LogicalGroup(operator=LogicalOperator.OR, clauses=[qc2, NotClause(clause=qc3)]),
            ],
        )
    )

    planned_query = query_planner_fixture.plan(query)
    plan_root = planned_query.plan_root

    assert isinstance(plan_root, PlannedLogicalGroup)
    assert plan_root.operator == LogicalOperator.AND
    assert len(plan_root.clauses) == 2

    # First clause is a component
    assert isinstance(plan_root.clauses[0], PlannedComponentExecution)
    assert plan_root.clauses[0].original_component == qc1

    # Second clause is another logical group
    nested_group = plan_root.clauses[1]
    assert isinstance(nested_group, PlannedLogicalGroup)
    assert nested_group.operator == LogicalOperator.OR
    assert len(nested_group.clauses) == 2

    # Nested clauses
    assert isinstance(nested_group.clauses[0], PlannedComponentExecution)
    assert nested_group.clauses[0].original_component == qc2
    assert isinstance(nested_group.clauses[1], PlannedNotClause)
    assert isinstance(nested_group.clauses[1].clause, PlannedComponentExecution)
    assert nested_group.clauses[1].clause.original_component == qc3


# --- QueryExecutor Tests ---

@pytest.fixture
def mock_executor_dbs(mock_db_manager_fixture: MagicMock):
    """Fixture to simplify mocking adapter results for executor tests."""
    # Define some UUIDs
    id1, id2, id3, id4 = uuid4(), uuid4(), uuid4(), uuid4()
    all_ids = [id1, id2, id3, id4]

    # Mock the "universe" of all IDs for a given type
    mock_db_manager_fixture.sqlite_adapter.get_all_object_ids_for_type.return_value = all_ids

    # Mock component execution results
    # This function will be called by the executor for each leaf component
    def execute_component_mock(plan_node: PlannedComponentExecution, errors: list):
        # Use the component's index to return a specific set of IDs
        if plan_node.component_index == 0:
            return {id1, id2}
        if plan_node.component_index == 1:
            return {id2, id3}
        if plan_node.component_index == 2:
            return {id3, id4}
        return set()

    return execute_component_mock, (id1, id2, id3, id4)


def test_executor_and_logic(query_executor_fixture: QueryExecutor, mock_executor_dbs):
    """Tests that the executor correctly computes the intersection for AND."""
    execute_component_mock, (id1, id2, id3, _) = mock_executor_dbs
    query_executor_fixture._execute_component = MagicMock(side_effect=execute_component_mock)

    # Plan: AND(Comp0, Comp1) -> {id1, id2} AND {id2, id3} -> {id2}
    plan = PlannedLogicalGroup(
        operator=LogicalOperator.AND,
        clauses=[
            PlannedComponentExecution(component_index=0, object_type_name="Test", steps=[], original_component=QueryComponent(object_type_name="Test")),
            PlannedComponentExecution(component_index=1, object_type_name="Test", steps=[], original_component=QueryComponent(object_type_name="Test")),
        ],
    )

    result_ids = query_executor_fixture._execute_node(plan, [])
    assert result_ids == {id2}


def test_executor_or_logic(query_executor_fixture: QueryExecutor, mock_executor_dbs):
    """Tests that the executor correctly computes the union for OR."""
    execute_component_mock, (id1, id2, id3, _) = mock_executor_dbs
    query_executor_fixture._execute_component = MagicMock(side_effect=execute_component_mock)

    # Plan: OR(Comp0, Comp1) -> {id1, id2} OR {id2, id3} -> {id1, id2, id3}
    plan = PlannedLogicalGroup(
        operator=LogicalOperator.OR,
        clauses=[
            PlannedComponentExecution(component_index=0, object_type_name="Test", steps=[], original_component=QueryComponent(object_type_name="Test")),
            PlannedComponentExecution(component_index=1, object_type_name="Test", steps=[], original_component=QueryComponent(object_type_name="Test")),
        ],
    )

    result_ids = query_executor_fixture._execute_node(plan, [])
    assert result_ids == {id1, id2, id3}


def test_executor_not_logic(query_executor_fixture: QueryExecutor, mock_db_manager_fixture: MagicMock, mock_executor_dbs):
    """Tests that the executor correctly computes the set difference for NOT."""
    execute_component_mock, (id1, id2, id3, id4) = mock_executor_dbs
    query_executor_fixture._execute_component = MagicMock(side_effect=execute_component_mock)
    
    # Mock the universe of IDs
    mock_db_manager_fixture.sqlite_adapter.get_all_object_ids_for_type.return_value = [id1, id2, id3, id4]

    # Plan: NOT(Comp1) -> {id1, id2, id3, id4} - {id2, id3} -> {id1, id4}
    plan = PlannedNotClause(
        clause=PlannedComponentExecution(component_index=1, object_type_name="TestObject", steps=[], original_component=QueryComponent(object_type_name="TestObject"))
    )

    result_ids = query_executor_fixture._execute_node(plan, [])
    assert result_ids == {id1, id4}
    mock_db_manager_fixture.sqlite_adapter.get_all_object_ids_for_type.assert_called_once_with("TestObject")


def test_executor_nested_logic(query_executor_fixture: QueryExecutor, mock_executor_dbs):
    """Tests a nested query: Comp0 AND (Comp1 OR Comp2)."""
    execute_component_mock, (id1, id2, id3, id4) = mock_executor_dbs
    query_executor_fixture._execute_component = MagicMock(side_effect=execute_component_mock)

    # Comp0 -> {id1, id2}
    # Comp1 -> {id2, id3}
    # Comp2 -> {id3, id4}
    # (Comp1 OR Comp2) -> {id2, id3, id4}
    # Comp0 AND (result) -> {id1, id2} AND {id2, id3, id4} -> {id2}
    plan = PlannedLogicalGroup(
        operator=LogicalOperator.AND,
        clauses=[
            PlannedComponentExecution(component_index=0, object_type_name="Test", steps=[], original_component=QueryComponent(object_type_name="Test")),
            PlannedLogicalGroup(
                operator=LogicalOperator.OR,
                clauses=[
                    PlannedComponentExecution(component_index=1, object_type_name="Test", steps=[], original_component=QueryComponent(object_type_name="Test")),
                    PlannedComponentExecution(component_index=2, object_type_name="Test", steps=[], original_component=QueryComponent(object_type_name="Test")),
                ],
            ),
        ],
    )

    result_ids = query_executor_fixture._execute_node(plan, [])
    assert result_ids == {id2}


def test_executor_component_execution_calls_adapter(query_executor_fixture: QueryExecutor, mock_db_manager_fixture: MagicMock):
    """Tests that executing a component correctly calls the underlying DB adapter."""
    obj_id = uuid4()
    mock_db_manager_fixture.sqlite_adapter.find_object_ids_by_properties.return_value = [obj_id]

    comp_plan = PlannedComponentExecution(
        component_index=0,
        object_type_name="TestObject",
        steps=[
            PlannedStep(
                step_type="sqlite_filter",
                details={
                    "object_type_name": "TestObject",
                    "filters": [RelationalFilter(property_name="prop1", operator="==", value="val1")]
                },
                input_object_ids_source_step_index=None
            )
        ],
        original_component=QueryComponent(object_type_name="TestObject")
    )

    result_ids = query_executor_fixture._execute_component(comp_plan, [])
    assert result_ids == {obj_id}
    mock_db_manager_fixture.sqlite_adapter.find_object_ids_by_properties.assert_called_once()