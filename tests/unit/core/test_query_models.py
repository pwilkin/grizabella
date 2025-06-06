import pytest
from pydantic import ValidationError

from grizabella.core.query_models import (
    ComplexQuery,
    LogicalGroup,
    LogicalOperator,
    QueryComponent,
)


def test_complex_query_validation_both_fields_fail():
    """Tests that validation fails if both 'components' and 'query_root' are provided."""
    with pytest.raises(ValidationError) as exc_info:
        ComplexQuery(
            components=[QueryComponent(object_type_name="test")],
            query_root=LogicalGroup(
                operator=LogicalOperator.AND,
                clauses=[QueryComponent(object_type_name="test")],
            ),
        )
    assert "Cannot specify both 'components' and 'query_root'" in str(exc_info.value)


def test_complex_query_validation_neither_field_fails():
    """Tests that validation fails if neither 'components' nor 'query_root' is provided."""
    with pytest.raises(ValidationError) as exc_info:
        ComplexQuery()
    assert "Must specify either 'components' or 'query_root'" in str(exc_info.value)


def test_complex_query_validation_components_only_succeeds():
    """Tests that validation succeeds with only the deprecated 'components' field."""
    query = ComplexQuery(components=[QueryComponent(object_type_name="test")])
    assert query.components is not None
    assert query.query_root is None


def test_complex_query_validation_query_root_only_succeeds():
    """Tests that validation succeeds with only the new 'query_root' field."""
    query = ComplexQuery(
        query_root=LogicalGroup(
            operator=LogicalOperator.AND,
            clauses=[QueryComponent(object_type_name="test")],
        )
    )
    assert query.query_root is not None
    assert query.components is None