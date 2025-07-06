"""Query Planner and Executor for Grizabella's Complex Query Engine."""

import logging
from typing import TYPE_CHECKING, Any, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from grizabella.core.models import (
    ObjectInstance,
)
from grizabella.core.query_models import (
    ComplexQuery,
    EmbeddingSearchClause,
    GraphTraversalClause,
    LogicalGroup,
    LogicalOperator,
    NotClause,
    QueryClause,
    QueryComponent,
    QueryResult,
    RelationalFilter,
)

logger = logging.getLogger(__name__)

# Forward declaration for type hinting GrizabellaDBManager
if TYPE_CHECKING:
    from grizabella.core.db_manager import GrizabellaDBManager


# --- NEW/UPDATED PLANNED MODELS ---
class PlannedStep(BaseModel):
    """Represents a single step in an execution plan for a query component."""

    step_type: Literal["sqlite_filter", "lancedb_search", "kuzu_traversal"]
    details: dict[str, Any]
    input_object_ids_source_step_index: Optional[int] = Field(
        default=None,
        description="Index of the step within this component's plan providing input IDs",
    )


class PlannedComponentExecution(BaseModel):
    """Represents the execution plan for a single QueryComponent (a leaf in the plan tree)."""

    component_index: int
    object_type_name: str
    steps: list[PlannedStep]
    original_component: QueryComponent


class PlannedLogicalGroup(BaseModel):
    """Represents a planned logical group, mirroring the query structure."""

    operator: LogicalOperator
    clauses: List["PlannedClause"]


class PlannedNotClause(BaseModel):
    """Represents a planned NOT clause, mirroring the query structure."""

    clause: "PlannedClause"


# A Union for any node in our planned query tree
PlannedClause = Union[
    PlannedLogicalGroup, PlannedNotClause, PlannedComponentExecution,
]

# Update the forward references in the recursive models
PlannedLogicalGroup.model_rebuild()
PlannedNotClause.model_rebuild()


class PlannedQuery(BaseModel):
    """Represents the full, tree-based execution plan for a ComplexQuery."""

    original_query: ComplexQuery
    final_target_object_type_name: str  # Primary object type for final result fetching
    plan_root: PlannedClause


class QueryPlanner:
    """Analyzes a ComplexQuery and decomposes it into a recursive, executable plan."""

    def __init__(self, db_manager: "GrizabellaDBManager") -> None:
        self._db_manager = db_manager
        self._schema_manager = db_manager._schema_manager

    def plan(self, query: ComplexQuery) -> PlannedQuery:
        """Generates a tree-based execution plan for the given complex query."""
        logger.info("Planning complex query: %s", query.description or "Untitled Query")

        query_root = query.query_root

        # Backward compatibility: if components are provided, convert them to a query_root
        if not query_root and query.components:
            logger.info(
                "No 'query_root' found. Converting 'components' list to an AND group for backward compatibility.",
            )
            if not query.components:
                raise ValueError("ComplexQuery must have at least one component.")
            # Create a synthetic LogicalGroup to wrap the old components list
            query_root = LogicalGroup(operator=LogicalOperator.AND, clauses=list(query.components))

        if not query_root:
            raise ValueError("Query must have a 'query_root' or a 'components' list.")

        # Determine the final target object type by finding the first component in the tree
        final_target_object_type = self._find_first_object_type(query_root)
        if not final_target_object_type:
            raise ValueError("Could not determine a target object type for the query.")

        otd_final_target = self._schema_manager.get_object_type_definition(
            final_target_object_type,
        )
        if not otd_final_target:
            raise ValueError(
                f"Primary target ObjectTypeDefinition '{final_target_object_type}' not found in schema.",
            )

        # Start the recursive planning process
        plan_root = self._plan_clause(query_root, {"i": 0})

        return PlannedQuery(
            original_query=query,
            final_target_object_type_name=final_target_object_type,
            plan_root=plan_root,
        )

    def _find_first_object_type(self, clause: QueryClause) -> Optional[str]:
        """Recursively traverses the query tree to find the first object type name."""
        if isinstance(clause, QueryComponent):
            return clause.object_type_name
        if isinstance(clause, LogicalGroup):
            for child_clause in clause.clauses:
                found_type = self._find_first_object_type(child_clause)
                if found_type:
                    return found_type
        elif isinstance(clause, NotClause):
            return self._find_first_object_type(clause.clause)
        return None

    def _plan_clause(
        self, clause: QueryClause, component_index_counter: dict[str, int],
    ) -> PlannedClause:
        """Recursively plans a single clause of a query."""
        if isinstance(clause, LogicalGroup):
            planned_children = [
                self._plan_clause(c, component_index_counter) for c in clause.clauses
            ]
            return PlannedLogicalGroup(operator=clause.operator, clauses=planned_children)

        if isinstance(clause, NotClause):
            planned_child = self._plan_clause(clause.clause, component_index_counter)
            return PlannedNotClause(clause=planned_child)

        if isinstance(clause, QueryComponent):
            # This is the logic for planning a single leaf-node component
            component = clause
            idx = component_index_counter["i"]
            component_index_counter["i"] += 1

            component_steps: list[PlannedStep] = []
            current_input_src_idx_for_component: Optional[int] = None
            component_object_type_name = component.object_type_name

            otd_component = self._schema_manager.get_object_type_definition(
                component_object_type_name,
            )
            if not otd_component:
                raise ValueError(
                    f"QueryComponent {idx}: ObjectTypeDefinition '{component_object_type_name}' not found.",
                )

            # 1. Relational Filters (SQLite)
            if component.relational_filters:
                for rel_filter in component.relational_filters:
                    self._validate_relational_filter(rel_filter, component_object_type_name, idx)
                component_steps.append(
                    PlannedStep(
                        step_type="sqlite_filter",
                        details={
                            "object_type_name": component_object_type_name,
                            "filters": component.relational_filters,
                        },
                        input_object_ids_source_step_index=None,
                    ),
                )
                current_input_src_idx_for_component = len(component_steps) - 1

            # 2. Embedding Searches (LanceDB)
            if component.embedding_searches:
                for emb_search in component.embedding_searches:
                    self._validate_embedding_search(emb_search, component_object_type_name, idx)
                    component_steps.append(
                        PlannedStep(
                            step_type="lancedb_search",
                            details={
                                "embedding_search_clause": emb_search,
                                "object_type_name": component_object_type_name,
                            },
                            input_object_ids_source_step_index=current_input_src_idx_for_component,
                        ),
                    )
                    current_input_src_idx_for_component = len(component_steps) - 1

            # 3. Graph Traversals (Kuzu)
            if component.graph_traversals:
                for traversal in component.graph_traversals:
                    self._validate_graph_traversal(traversal, component_object_type_name, idx)
                    component_steps.append(
                        PlannedStep(
                            step_type="kuzu_traversal",
                            details={
                                "source_object_type_name": component_object_type_name,
                                "graph_traversal_clause": traversal,
                            },
                            input_object_ids_source_step_index=current_input_src_idx_for_component,
                        ),
                    )
                    current_input_src_idx_for_component = len(component_steps) - 1

            return PlannedComponentExecution(
                component_index=idx,
                object_type_name=component.object_type_name,
                steps=component_steps,
                original_component=component,
            )

        raise TypeError(f"Unsupported clause type during planning: {type(clause)}")

    def _validate_relational_filter(
        self,
        rel_filter: RelationalFilter,
        object_type_name: str,
        component_idx: int,
        context: str = "relational_filters",
    ) -> None:
        prop_def = self._schema_manager.get_property_definition_for_object_type(
            object_type_name, rel_filter.property_name,
        )
        if not prop_def:
            raise ValueError(
                f"QueryComponent {component_idx}: Property '{rel_filter.property_name}' "
                f"not found for ObjectType '{object_type_name}'.",
            )
        # Simplified validation for brevity in this refactoring

    def _validate_embedding_search(
        self, emb_search: EmbeddingSearchClause, object_type_name: str, component_idx: int,
    ) -> None:
        emb_def = self._schema_manager.get_embedding_definition(
            emb_search.embedding_definition_name,
        )
        if not emb_def:
            raise ValueError(
                f"QueryComponent {component_idx}: EmbeddingDefinition "
                f"'{emb_search.embedding_definition_name}' not found.",
            )
        if emb_def.object_type_name != object_type_name:
            raise ValueError(
                f"QueryComponent {component_idx}: EmbeddingDefinition "
                f"'{emb_search.embedding_definition_name}' is for ObjectType '{emb_def.object_type_name}', "
                f"but component targets '{object_type_name}'.",
            )
        # Simplified validation

    def _validate_graph_traversal(
        self, traversal: GraphTraversalClause, source_object_type_name: str, component_idx: int,
    ) -> None:
        rtd = self._schema_manager.get_relation_type_definition(
            traversal.relation_type_name,
        )
        if not rtd:
            raise ValueError(
                f"QueryComponent {component_idx}: RelationTypeDefinition "
                f"'{traversal.relation_type_name}' not found.",
            )
        if source_object_type_name not in rtd.source_object_type_names:
            raise ValueError(
                f"QueryComponent {component_idx}: Relation '{traversal.relation_type_name}' "
                f"cannot originate from ObjectType '{source_object_type_name}'.",
            )
        if traversal.target_object_type_name not in rtd.target_object_type_names:
            raise ValueError(
                f"QueryComponent {component_idx}: Relation '{traversal.relation_type_name}' "
                f"cannot target ObjectType '{traversal.target_object_type_name}'.",
            )
        # Simplified validation


class QueryExecutor:
    """Executes a tree-based PlannedQuery using a recursive, post-order traversal."""

    def __init__(self, db_manager: "GrizabellaDBManager") -> None:
        self._db_manager = db_manager

    def execute(self, planned_query: PlannedQuery) -> QueryResult:
        """Executes the planned query tree and returns the final result."""
        logger.info(
            "Executing planned query for: %s",
            planned_query.original_query.description or "Untitled Query",
        )
        errors: list[str] = []

        try:
            # Start the recursive execution from the root of the plan
            final_aggregated_ids = self._execute_node(planned_query.plan_root, errors)
        except Exception as e:
            msg = f"Top-level error during query execution: {type(e).__name__}: {e}"
            logger.error(msg, exc_info=True)
            errors.append(msg)
            final_aggregated_ids = set()

        final_instances: list[ObjectInstance] = []
        if final_aggregated_ids and not errors:
            try:
                final_instances = self._db_manager.get_objects_by_ids(
                    object_type_name=planned_query.final_target_object_type_name,
                    object_ids=list(final_aggregated_ids),
                )
                logger.info("Fetched %d full object instances.", len(final_instances))
            except Exception as e:
                msg = f"Error fetching final object instances: {e}"
                logger.error(msg, exc_info=True)
                errors.append(msg)

        return QueryResult(
            object_instances=final_instances, errors=errors if errors else None,
        )

    def _execute_node(
        self, plan_node: PlannedClause, errors: list[str],
    ) -> set[UUID]:
        """Recursively executes a node in the plan tree and returns a set of object IDs."""
        if isinstance(plan_node, PlannedLogicalGroup):
            # Execute all child clauses first
            child_results = [self._execute_node(c, errors) for c in plan_node.clauses]

            if plan_node.operator == LogicalOperator.AND:
                if not child_results:
                    return set()
                # Intersect all resulting ID sets
                result_set = child_results[0].copy()
                for i in range(1, len(child_results)):
                    result_set.intersection_update(child_results[i])
                return result_set

            if plan_node.operator == LogicalOperator.OR:
                # Union all resulting ID sets
                result_set = set()
                for res in child_results:
                    result_set.update(res)
                return result_set

        if isinstance(plan_node, PlannedNotClause):
            # Execute the child clause to get the set of IDs to exclude
            excluded_ids = self._execute_node(plan_node.clause, errors)

            # To perform a NOT, we need the "universe" of all possible IDs for the type
            object_type_name = self._find_first_object_type_from_plan(plan_node.clause)
            if not object_type_name:
                msg = "Could not determine object type for NOT clause execution."
                logger.error(msg)
                errors.append(msg)
                return set()

            all_ids_for_type = (
                self._db_manager.sqlite_adapter.get_all_object_ids_for_type(
                    object_type_name,
                )
            )
            universe_set = set(all_ids_for_type if all_ids_for_type else [])

            # Return the set difference
            return universe_set.difference(excluded_ids)

        if isinstance(plan_node, PlannedComponentExecution):
            # Execute the steps for a single leaf component
            return self._execute_component(plan_node, errors)

        raise TypeError(f"Unsupported plan node type during execution: {type(plan_node)}")

    def _find_first_object_type_from_plan(
        self, plan_node: PlannedClause,
    ) -> Optional[str]:
        """Recursively finds the first object type in a planned clause."""
        if isinstance(plan_node, PlannedComponentExecution):
            return plan_node.object_type_name
        if isinstance(plan_node, PlannedLogicalGroup):
            for child in plan_node.clauses:
                if (found_type := self._find_first_object_type_from_plan(child)):
                    return found_type
        elif isinstance(plan_node, PlannedNotClause):
            return self._find_first_object_type_from_plan(plan_node.clause)
        return None

    def _execute_component(
        self, component_plan: PlannedComponentExecution, errors: list[str],
    ) -> set[UUID]:
        """Executes the planned steps for a single component and returns resulting IDs."""
        logger.info(
            "Executing component %d (ObjectType: %s)",
            component_plan.component_index,
            component_plan.object_type_name,
        )
        intermediate_step_results: dict[int, list[UUID]] = {}
        current_ids: Optional[list[UUID]] = None

        if not component_plan.steps:
            # No steps means all objects of this type
            all_ids = self._db_manager.sqlite_adapter.get_all_object_ids_for_type(
                component_plan.object_type_name,
            )
            return set(all_ids if all_ids else [])

        for step_idx, step in enumerate(component_plan.steps):
            input_ids: Optional[list[UUID]] = None
            if step.input_object_ids_source_step_index is not None:
                input_ids = intermediate_step_results.get(
                    step.input_object_ids_source_step_index,
                )

            if input_ids is not None and not input_ids:
                logger.info("Component %d short-circuited due to empty input ID set.", component_plan.component_index)
                return set()

            try:
                step_output_ids: list[UUID] = []
                if step.step_type == "sqlite_filter":
                    step_output_ids = self._db_manager.sqlite_adapter.find_object_ids_by_properties(
                        object_type_name=step.details["object_type_name"],
                        filters=step.details["filters"],
                        initial_ids=input_ids,
                    )
                elif step.step_type == "lancedb_search":
                    emb_clause = step.details["embedding_search_clause"]
                    results_with_distance = self._db_manager.lancedb_adapter.find_object_ids_by_similarity(
                        embedding_definition_name=emb_clause.embedding_definition_name,
                        query_vector=emb_clause.similar_to_payload,
                        limit=emb_clause.limit,
                        initial_ids=input_ids,
                    )
                    # Apply thresholding
                    step_output_ids = []
                    if emb_clause.threshold is not None:
                        for res_id, distance in results_with_distance:
                            if emb_clause.is_l2_distance:
                                if distance <= emb_clause.threshold:
                                    step_output_ids.append(res_id)
                            else:  # Assuming cosine similarity, higher is better
                                # Convert L2 distance to cosine similarity before comparing
                                cosine_similarity = 1 - (distance**2) / 2
                                if cosine_similarity >= emb_clause.threshold:
                                    step_output_ids.append(res_id)
                    else:
                        step_output_ids = [res_id for res_id, _ in results_with_distance]

                elif step.step_type == "kuzu_traversal":
                    if input_ids is None:
                        input_ids = self._db_manager.sqlite_adapter.get_all_object_ids_for_type(
                            component_plan.object_type_name,
                        ) or []

                    if not input_ids:
                        step_output_ids = []
                    else:
                        step_output_ids = self._db_manager.kuzu_adapter.filter_object_ids_by_relations(
                            source_object_type_name=step.details["source_object_type_name"],
                            object_ids=input_ids,
                            traversals=[step.details["graph_traversal_clause"]],
                        )

                intermediate_step_results[step_idx] = step_output_ids
                current_ids = step_output_ids

                if not current_ids:
                    logger.info("Component %d, Step %d yielded no results.", component_plan.component_index, step_idx)
                    return set()

            except Exception as e:
                msg = f"Error in component {component_plan.component_index}, step {step_idx} ({step.step_type}): {e}"
                logger.error(msg, exc_info=True)
                errors.append(msg)
                return set()

        return set(current_ids if current_ids is not None else [])
