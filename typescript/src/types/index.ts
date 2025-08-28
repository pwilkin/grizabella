/**
 * TypeScript Type Definitions for Grizabella API
 *
 * This module provides comprehensive TypeScript type definitions that mirror
 * all the Pydantic models and enums from the Grizabella Python codebase.
 *
 * These types are designed to provide type safety when working with the Grizabella
 * tri-layer memory management system, which includes relational, embedding, and
 * graph database layers.
 */

// ===== ENUMS AND PRIMITIVES =====
export {
  PropertyDataType,
  LogicalOperator,
  type FilterValueType,
  type RelationalOperator,
  type GraphTraversalDirection,
  type MemoryInstance,
} from './enums';

// ===== CORE MODEL INTERFACES =====
export type {
  PropertyDefinition,
  ObjectTypeDefinition,
  ObjectInstance,
  RelationTypeDefinition,
  RelationInstance,
  RelationInstanceList,

  // Core method parameters
  CreateObjectTypeParams,
  GetObjectTypeParams,
  DeleteObjectTypeParams,
  CreateRelationTypeParams,
  GetRelationTypeParams,
  DeleteRelationTypeParams,
  UpsertObjectParams,
  GetObjectByIdParams,
  DeleteObjectParams,
  FindObjectsParams,
  AddRelationParams,
  GetRelationParams,
  DeleteRelationParams,
  QueryRelationsParams,
  GetOutgoingRelationsParams,
  GetIncomingRelationsParams,

  // Query method parameters
  ExecuteComplexQueryParams,
  SearchSimilarObjectsParams,
  FindSimilarParams,
  SimilaritySearchResult,

  // Embedding method parameters
  CreateEmbeddingDefinitionParams,
  GetEmbeddingDefinitionParams,
  DeleteEmbeddingDefinitionParams,
  GetEmbeddingVectorForTextParams,
  EmbeddingSimilarityResult,
  SearchSimilarObjectsWithEmbeddingsParams,
} from './core';

// ===== QUERY-RELATED TYPES =====
export type {
  RelationalFilter,
  EmbeddingSearchClause,
  GraphTraversalClause,
  QueryComponent,
  LogicalGroup,
  NotClause,
  QueryClause,
  ComplexQuery,
  QueryResult,
} from './query';

// ===== EMBEDDING TYPES =====
export type {
  EmbeddingDefinition,
  EmbeddingInstance,
  EmbeddingVector,
} from './embedding';

export type {
  EmbeddingSimilarityResult as EmbeddingSearchResult,
} from './embedding';

// ===== UTILITY TYPES =====
/**
 * Utility type for making all properties of T optional except for required ones.
 * Useful for partial updates and optional parameters.
 */
export type PartialExcept<T, K extends keyof T> = Partial<T> & Pick<T, K>;

/**
 * Utility type for extracting the properties type from an ObjectInstance.
 * Useful when you need to work with just the properties data.
 */
export type ObjectProperties<T> = T extends { properties: infer P } ? P : never;

/**
 * Utility type for creating a new object type with specific properties.
 * Useful for defining strongly-typed property bags.
 */
export type PropertyBag<T = any> = Record<string, T>;

/**
 * Utility type representing a UUID string.
 * Provides better type safety than generic string.
 */
export type UUID = string;

/**
 * Utility type for database operation results that may contain errors.
 * Common pattern in the Grizabella API.
 */
export interface OperationResult<T = any> {
  /** The result data if the operation was successful. */
  data?: T;

  /** Error message if the operation failed. */
  error?: string;

  /** Whether the operation was successful. */
  success: boolean;
}

/**
 * Utility type for paginated results.
 * Common pattern for list operations that may return large datasets.
 */
export interface PaginatedResult<T> {
  /** The items in the current page. */
  items: T[];

  /** Total number of items available. */
  total: number;

  /** Current page number (1-based). */
  page: number;

  /** Number of items per page. */
  page_size: number;

  /** Whether there are more pages available. */
  has_more: boolean;
}

// ===== CONSTANTS =====
/**
 * Default weight value for new MemoryInstances.
 */
export const DEFAULT_WEIGHT = 1.0;

/**
 * Maximum weight value for MemoryInstances.
 */
export const MAX_WEIGHT = 10.0;

/**
 * Minimum weight value for MemoryInstances.
 */
export const MIN_WEIGHT = 0.0;

/**
 * Default embedding model identifier used by EmbeddingDefinitions.
 */
export const DEFAULT_EMBEDDING_MODEL = 'huggingface/colbert-ir/colbertv2.0';