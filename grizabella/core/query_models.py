"""Pydantic models for Grizabella Complex Query Engine."""
from enum import Enum
from typing import List, Literal, Optional, Union
from uuid import UUID
from grizabella.core.models import ObjectInstance
from pydantic import BaseModel, Field, model_validator

# Type definition for RelationalFilter value
FilterValueType = Union[
    str, int, float, bool, None, List[str], List[int], List[float], List[bool]
]

# Assuming ObjectInstance will be imported from grizabella.core.models
# This will create a circular import if ObjectInstance also imports from query_models.
# If that's the case, we might need to use forward references (e.g., 'ObjectInstance')
# or move some models around. For now, let's try a direct import.

class RelationalFilter(BaseModel):
    """Defines a filter condition based on an object's property value.

    This model is used within ``QueryComponent`` and ``GraphTraversalClause``
    to specify conditions for filtering objects based on their properties.
    It allows for various comparison operators against a given value.

    Attributes:
        property_name (str): :noindex: The name of the property on which to apply the filter.
            This must match a property defined in the relevant ``ObjectTypeDefinition``.

        operator (Literal): :noindex: The comparison operator to use. Supported operators
            include "==", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "CONTAINS",
            "STARTSWITH", and "ENDSWITH".

        value (FilterValueType): :noindex: The value to compare the property against. The type of this
            value should be compatible with the data type of the specified property.
            For "IN" operator, this should be a list of values.

    
    """

    property_name: str = Field(
        ...,
        description="Name of the property to filter on.",
    )
    operator: Literal[
        "==", "!=", ">", "<", ">=", "<=", "LIKE", "IN",
        "CONTAINS", "STARTSWITH", "ENDSWITH", # Added common operators
    ] = Field(
        ...,
        description="The comparison operator.",
    )
    value: FilterValueType = Field(
        ...,
        description="The value to compare against. For simple operators (==, !=, >, <, etc.), this can be a string, number, boolean, or null. For the 'IN' operator, this should be a list of values of the same type.",
    )


class EmbeddingSearchClause(BaseModel):
    """Defines a search based on embedding similarity.

    This clause is used within a ``QueryComponent`` to find objects that are
    semantically similar to a given query vector, based on pre-computed
    embeddings.

    Attributes:
        embedding_definition_name (str): :noindex: The name of the ``EmbeddingDefinition``
            to use for this search. This definition specifies the model and
            source property used to generate the embeddings being searched.

        similar_to_payload (List[float]): :noindex: The embedding vector to find
            similarities against. This vector should have the same dimensions
            as specified in the ``EmbeddingDefinition``.

        threshold (Optional[float]): :noindex: An optional similarity score threshold.
            Only results with a similarity score greater than or equal to this
            threshold will be returned. If None, no threshold is applied.

        limit (int): :noindex: The maximum number of similar items to retrieve and
            consider from this clause. Defaults to 10.

    
    """

    embedding_definition_name: str = Field(
        ...,
        description="Name of the EmbeddingDefinition to use for this search.",
    )
    similar_to_payload: list[float] = Field(
        ...,
        description="The embedding vector to find similarities against.",
    )
    # similar_to_object_id: Optional[UUID] = Field(
    #     default=None,
    #     description="Alternatively, specify an object ID whose embedding should be used as the query vector."
    # )
    # similar_to_object_type_name: Optional[str] = Field(
    #     default=None,
    #     description="Required if similar_to_object_id is specified."
    # )
    threshold: Optional[float] = Field(
        default=None,
        description="Optional similarity threshold. Only results above this score are returned.",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of similar items to consider from this clause.",
    )
    is_l2_distance: bool = Field(
        default=False,
        description="If True, indicates that the threshold is for L2 distance (smaller is better) "
                    "and the QueryEngine should not convert distance to cosine similarity.",
    )

    # @field_validator('similar_to_object_id')
    # def check_similar_to_object_details(cls, v, values):
    #     if v and not values.get('similar_to_object_type_name'):
    #         raise ValueError(
    #             "similar_to_object_type_name is required if similar_to_object_id is provided."
    #         )
    #     if values.get('similar_to_payload') and v:
    #         raise ValueError(
    #             "Cannot specify both similar_to_payload and similar_to_object_id."
    #         )
    #     if not values.get('similar_to_payload') and not v:
    #         raise ValueError(
    #             "Must specify either similar_to_payload or similar_to_object_id."
    #         )
    #     return v


class GraphTraversalClause(BaseModel):
    """Defines a graph traversal condition from a source object set.

    This clause is used within a ``QueryComponent`` to navigate relationships
    in the graph database. It specifies the type of relation to follow,
    the direction of traversal, and conditions on the target objects.

    Attributes:
        relation_type_name (str): :noindex: The name of the ``RelationTypeDefinition``
            that defines the type of relationship to traverse.

        direction (Literal["outgoing", "incoming"]): :noindex: The direction of the
            traversal from the current set of source objects. "outgoing" means
            following relations where the current objects are the source;
            "incoming" means following relations where they are the target.
            Defaults to "outgoing".

        target_object_type_name (str): :noindex: The expected ``ObjectTypeDefinition`` name
            of the target node(s) at the end of the traversal.

        target_object_id (Optional[UUID]): :noindex: An optional specific ID of a target
            object. If provided, the traversal will only consider paths leading
            to this specific object.

        target_object_properties (Optional[List[RelationalFilter]]): :noindex: Optional
            list of ``RelationalFilter``s to apply to the properties of the
            target object(s) found by the traversal.

    
    """

    relation_type_name: str = Field(
        ...,
        description="Name of the RelationTypeDefinition to traverse.",
    )
    direction: Literal["outgoing", "incoming"] = Field(
        default="outgoing",
        description="Direction of the traversal from the source object.",
    )
    target_object_type_name: str = Field(
        ...,
        description="Expected ObjectTypeDefinition name of the target node(s).",
    )
    target_object_id: Optional[UUID] = Field(
        default=None,
        description="Optional specific ID of the target object.",
    )
    target_object_properties: Optional[list[RelationalFilter]] = Field(
        default=None,
        description="Optional filters to apply to the properties of the target object(s).",
    )
    # Future enhancements:
    # min_hops: int = Field(default=1, description="Minimum number of hops for the traversal.")
    # max_hops: int = Field(default=1, description="Maximum number of hops for the traversal.")
    # relation_properties: Optional[List[RelationalFilter]] = Field(
    #     default=None,
    #     description="Optional filters to apply to the properties of the relation itself."
    # )


class QueryComponent(BaseModel):
    """Defines a single logical block of query conditions targeting a primary object type.

    A ``QueryComponent`` groups various types of search and filter conditions
    that apply to a specific ``ObjectTypeDefinition``. All conditions
    (relational filters, embedding searches, graph traversals) specified
    within a single component are implicitly ANDed together. The results
    from these conditions are intersected to produce a set of matching
    ``ObjectInstance``s of the ``object_type_name``.

    Attributes:
        object_type_name (str): :noindex: The primary ``ObjectTypeDefinition`` name that
            this component targets. The query starts by considering objects
            of this type.

        relational_filters (Optional[List[RelationalFilter]]): :noindex: A list of
            ``RelationalFilter``s to apply to the properties of objects of
            ``object_type_name``. Typically processed by a relational database layer.

        embedding_searches (Optional[List[EmbeddingSearchClause]]): :noindex: A list of
            ``EmbeddingSearchClause``s to perform semantic similarity searches.
            Typically processed by a vector database layer.

        graph_traversals (Optional[List[GraphTraversalClause]]): :noindex: A list of
            ``GraphTraversalClause``s to navigate relationships from or to
            objects of ``object_type_name``. Typically processed by a graph
            database layer.

    
    """

    object_type_name: str = Field(
        ...,
        description="The primary ObjectTypeDefinition name this component targets.",
    )
    relational_filters: Optional[list[RelationalFilter]] = Field(
        default=None,
        description="List of relational filters to apply (SQLite).",
    )
    embedding_searches: Optional[list[EmbeddingSearchClause]] = Field(
        default=None,
        description="List of embedding similarity searches to apply (LanceDB).",
    )
    graph_traversals: Optional[list[GraphTraversalClause]] = Field(
        default=None,
        description="List of graph traversals to apply (Kuzu).",
    )


class LogicalOperator(str, Enum):
    """Defines the logical operators for combining query clauses."""

    AND = "AND"
    OR = "OR"


class LogicalGroup(BaseModel):
    """Represents a group of query clauses combined by a single logical operator."""

    operator: LogicalOperator = Field(
        ...,
        description="The logical operator (AND, OR) to apply to the clauses in this group.",
    )
    clauses: List["QueryClause"] = Field(
        ...,
        description="A list of clauses to be combined. Clauses can be other LogicalGroups, NotClauses, or QueryComponents.",
    )


class NotClause(BaseModel):
    """Represents a logical NOT operation on a single query clause."""

    clause: "QueryClause" = Field(
        ...,
        description="The clause to be negated. Can be a LogicalGroup, another NotClause, or a QueryComponent.",
    )

# A Union to represent any valid node in our query tree
QueryClause = Union[LogicalGroup, NotClause, "QueryComponent"]

# Update the forward references in LogicalGroup and NotClause
LogicalGroup.model_rebuild()
NotClause.model_rebuild()


class ComplexQuery(BaseModel):
    """Represents a complex query that can span multiple database layers and object types."""

    description: Optional[str] = Field(
        default=None,
        description="Optional user-defined description for the query.",
    )

    # The new field for the logical query structure
    query_root: Optional[QueryClause] = Field(
        default=None,
        description="The root of the logical query tree.",
    )

    # The original field, kept for backward compatibility
    components: Optional[List["QueryComponent"]] = Field(
        default=None,
        description="[DEPRECATED] List of query components. Use 'query_root' for new queries.",
    )

    @model_validator(mode="before")
    @classmethod
    def check_exclusive_fields(cls, values):
        """Ensure that either 'components' or 'query_root' is provided, but not both."""
        components = values.get("components")
        query_root = values.get("query_root")

        if components is not None and query_root is not None:
            raise ValueError("Cannot specify both 'components' and 'query_root'.")

        if components is None and query_root is None:
            raise ValueError("Must specify either 'components' or 'query_root'.")

        return values


class QueryResult(BaseModel):
    """Represents the result of a complex query execution.

    This model encapsulates the ``ObjectInstance``s that match the criteria
    of a ``ComplexQuery``, along with any errors that may have occurred during
    the query planning or execution process.

    Attributes:
        object_instances (List[ObjectInstance]): :noindex: A list of ``ObjectInstance``s
            that satisfy all conditions of the ``ComplexQuery``.

        errors (Optional[List[str]]): :noindex: A list of error messages encountered
            during the execution of the query. If the query was successful,
            this will be None or an empty list.

    
    """

    object_instances: list[ObjectInstance] = Field(
        default_factory=list,
        description="List of ObjectInstances that match the complex query.",
    )
    errors: Optional[list[str]] = Field(
        default=None,
        description="List of errors encountered during query execution, if any.",
    )
    # Future:
    # execution_time_ms: Optional[float] = None
    # result_count: Optional[int] = None # Could be len(object_instances) but explicit might be useful
    # metadata: Optional[Dict[str, Any]] = None # For additional execution details


class EmbeddingVector(BaseModel):
    """A container for a list of floats representing an embedding vector."""

    vector: list[float]
