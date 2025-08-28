import { ObjectInstance } from './core';
import {
  LogicalOperator,
  FilterValueType,
  RelationalOperator,
  GraphTraversalDirection,
} from './enums';

/**
 * Defines a filter condition based on an object's property value.
 * This model is used within QueryComponent and GraphTraversalClause
 * to specify conditions for filtering objects based on their properties.
 */
export interface RelationalFilter {
  /** The name of the property on which to apply the filter. */
  property_name: string;

  /** The comparison operator to use. */
  operator: RelationalOperator;

  /** The value to compare the property against. */
  value: FilterValueType;
}

/**
 * Defines a search based on embedding similarity.
 * This clause is used within a QueryComponent to find objects that are
 * semantically similar to a given query vector, based on pre-computed embeddings.
 */
export interface EmbeddingSearchClause {
  /** The name of the EmbeddingDefinition to use for this search. */
  embedding_definition_name: string;

  /** The embedding vector to find similarities against. */
  similar_to_payload: number[];

  /** An optional similarity score threshold. */
  threshold?: number;

  /** The maximum number of similar items to retrieve and consider from this clause. */
  limit?: number;

  /** If True, indicates that the threshold is for L2 distance (smaller is better). */
  is_l2_distance?: boolean;
}

/**
 * Defines a graph traversal condition from a source object set.
 * This clause is used within a QueryComponent to navigate relationships
 * in the graph database. It specifies the type of relation to follow,
 * the direction of traversal, and conditions on the target objects.
 */
export interface GraphTraversalClause {
  /** The name of the RelationTypeDefinition that defines the type of relationship to traverse. */
  relation_type_name: string;

  /** The direction of the traversal from the current set of source objects. */
  direction?: GraphTraversalDirection;

  /** The expected ObjectTypeDefinition name of the target node(s) at the end of the traversal. */
  target_object_type_name: string;

  /** An optional specific ID of a target object. */
  target_object_id?: string;

  /** Optional list of RelationalFilters to apply to the properties of the target object(s) found by the traversal. */
  target_object_properties?: RelationalFilter[];
}

/**
 * Defines a single logical block of query conditions targeting a primary object type.
 * A QueryComponent groups various types of search and filter conditions
 * that apply to a specific ObjectTypeDefinition. All conditions (relational filters,
 * embedding searches, graph traversals) specified within a single component
 * are implicitly ANDed together.
 */
export interface QueryComponent {
  /** The primary ObjectTypeDefinition name that this component targets. */
  object_type_name: string;

  /** A list of RelationalFilters to apply to the properties of objects of object_type_name. */
  relational_filters?: RelationalFilter[];

  /** A list of EmbeddingSearchClauses to perform semantic similarity searches. */
  embedding_searches?: EmbeddingSearchClause[];

  /** A list of GraphTraversalClauses to navigate relationships from or to objects of object_type_name. */
  graph_traversals?: GraphTraversalClause[];
}

/**
 * Represents a group of query clauses combined by a single logical operator.
 */
export interface LogicalGroup {
  /** The logical operator (AND, OR) to apply to the clauses in this group. */
  operator: LogicalOperator;

  /** A list of clauses to be combined. */
  clauses: QueryClause[];
}

/**
 * Represents a logical NOT operation on a single query clause.
 */
export interface NotClause {
  /** The clause to be negated. */
  clause: QueryClause;
}

/**
 * Union type representing any valid node in the query tree.
 * Can be a LogicalGroup, NotClause, or QueryComponent.
 */
export type QueryClause = LogicalGroup | NotClause | QueryComponent;

/**
 * Represents a complex query that can span multiple database layers and object types.
 * Complex queries allow for sophisticated search patterns, including
 * graph traversals, relational filters, and embedding-based searches,
 * combined into a single query operation.
 */
export interface ComplexQuery {
  /** Optional user-defined description for the query. */
  description?: string;

  /** The root of the logical query tree. */
  query_root?: QueryClause;

  /** [DEPRECATED] List of query components. Use 'query_root' for new queries. */
  components?: QueryComponent[];
}

/**
 * Represents the result of a complex query execution.
 * This model encapsulates the ObjectInstances that match the criteria
 * of a ComplexQuery, along with any errors that may have occurred during
 * the query planning or execution process.
 */
export interface QueryResult {
  /** A list of ObjectInstances that satisfy all conditions of the ComplexQuery. */
  object_instances: ObjectInstance[];

  /** A list of error messages encountered during the execution of the query. */
  errors?: string[];
}

/**
 * Custom type definitions for query method parameters and return types.
 */

/** Parameters for executing a complex query. */
export interface ExecuteComplexQueryParams {
  query: ComplexQuery;
}

/** Parameters for searching similar objects using embeddings. */
export interface SearchSimilarObjectsParams {
  object_id: string;
  type_name: string;
  n_results?: number;
  search_properties?: string[];
}

/** Parameters for finding similar objects by text query. */
export interface FindSimilarParams {
  embedding_name: string;
  query_text: string;
  limit?: number;
  filter_condition?: string;
}

/** Result type for similarity search operations. */
export interface SimilaritySearchResult {
  /** The similar object instance. */
  object: ObjectInstance;

  /** The similarity score (typically distance, lower is more similar). */
  score: number;
}