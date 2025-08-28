import { MemoryInstance, PropertyDataType } from './enums';
export { PropertyDataType } from './enums';

/**
 * Defines a single property within an ObjectTypeDefinition or RelationTypeDefinition.
 * This model specifies the characteristics of a property, such as its name,
 * data type, and constraints (e.g., nullable, unique, indexed).
 */
export interface PropertyDefinition {
  /** The name of the property (e.g., 'title', 'age'). */
  name: string;

  /** The data type of the property. */
  data_type: PropertyDataType;

  /** Indicates if this property serves as a primary key for its ObjectTypeDefinition. */
  is_primary_key?: boolean;

  /** Specifies whether this property can have a null value. */
  is_nullable?: boolean;

  /** Indicates if this property should be indexed by supporting database layers. */
  is_indexed?: boolean;

  /** Specifies whether values for this property must be unique across all instances. */
  is_unique?: boolean;

  /** An optional human-readable description of the property. */
  description?: string;
}

/**
 * Defines the schema for a type of object (e.g., a node in a graph, a table row).
 * An ObjectTypeDefinition specifies the structure for a category of data entities.
 * It includes a unique name, an optional description, and a list of PropertyDefinitions.
 */
export interface ObjectTypeDefinition {
  /** A unique name for the object type (e.g., 'Document', 'Person'). Convention: PascalCase. */
  name: string;

  /** An optional human-readable description of what this object type represents. */
  description?: string;

  /** A list of properties that define the attributes of this object type. */
  properties: PropertyDefinition[];
}

/**
 * Represents a concrete instance of an ObjectTypeDefinition.
 * This model holds the actual data for an individual object, conforming to
 * the schema defined by its ObjectTypeDefinition.
 */
export interface ObjectInstance extends MemoryInstance {
  /** The name of the ObjectTypeDefinition that this instance conforms to. */
  object_type_name: string;

  /** A dictionary containing the actual data for the instance, mapping property names to their corresponding values. */
  properties: Record<string, any>;
}

/**
 * Defines the schema for a type of relation between objects (e.g., an edge in a graph).
 * A RelationTypeDefinition specifies the structure for relationships that can exist
 * between instances of ObjectTypeDefinitions. It includes a unique name, allowed source
 * and target object types, and any properties specific to the relation itself.
 */
export interface RelationTypeDefinition {
  /** A unique name for the relation type (e.g., 'HAS_AUTHOR', 'REFERENCES'). Convention: UPPER_SNAKE_CASE. */
  name: string;

  /** An optional human-readable description of what this relation type represents. */
  description?: string;

  /** A list of names of ObjectTypeDefinitions that are allowed as the source of this relation. */
  source_object_type_names: string[];

  /** A list of names of ObjectTypeDefinitions that are allowed as the target of this relation. */
  target_object_type_names: string[];

  /** A list of PropertyDefinitions that belong to the relation itself (edge properties). */
  properties?: PropertyDefinition[];
}

/**
 * Represents a concrete instance of a RelationTypeDefinition, linking two ObjectInstances.
 * This model captures a specific relationship between two objects, conforming to
 * the schema defined by its RelationTypeDefinition.
 */
export interface RelationInstance extends MemoryInstance {
  /** The name of the RelationTypeDefinition that this instance conforms to. */
  relation_type_name: string;

  /** The ID of the ObjectInstance that is the source of this relation. */
  source_object_instance_id: string;

  /** The ID of the ObjectInstance that is the target of this relation. */
  target_object_instance_id: string;

  /** A dictionary containing the actual data for the relation's own properties (edge properties), if any are defined. */
  properties?: Record<string, any>;
}

/**
 * A container for a list of RelationInstance objects.
 */
export interface RelationInstanceList {
  /** List of relation instances. */
  relations: RelationInstance[];
}

/**
 * Defines how an embedding should be generated and stored for an ObjectTypeDefinition.
 * This model specifies the configuration for creating vector embeddings from the content
 * of objects. It links an object type and one of its properties to an embedding model.
 */
export interface EmbeddingDefinition {
  /** A unique name for this embedding configuration (e.g., 'content_embedding_v1'). Convention: snake_case. */
  name: string;

  /** The name of the ObjectTypeDefinition this embedding applies to. */
  object_type_name: string;

  /** The name of the property within the ObjectTypeDefinition whose content will be used to generate the embedding. */
  source_property_name: string;

  /** An identifier for the embedding model to be used (e.g., 'text-embedding-ada-002'). */
  embedding_model: string;

  /** The expected dimensionality of the embedding vector. If not specified, may be inferred from the model. */
  dimensions?: number;

  /** An optional human-readable description of this embedding definition. */
  description?: string;
}

/**
 * Custom type definitions for method parameters and return types.
 */

/** Parameters for creating or updating an object type. */
export interface CreateObjectTypeParams {
  object_type_def: ObjectTypeDefinition;
}

/** Parameters for retrieving an object type definition. */
export interface GetObjectTypeParams {
  type_name: string;
}

/** Parameters for deleting an object type. */
export interface DeleteObjectTypeParams {
  type_name: string;
}

/** Parameters for creating a relation type. */
export interface CreateRelationTypeParams {
  relation_type_def: RelationTypeDefinition;
}

/** Parameters for retrieving a relation type. */
export interface GetRelationTypeParams {
  type_name: string;
}

/** Parameters for deleting a relation type. */
export interface DeleteRelationTypeParams {
  type_name: string;
}

/** Parameters for upserting an object instance. */
export interface UpsertObjectParams {
  obj: ObjectInstance;
}

/** Parameters for retrieving an object by ID. */
export interface GetObjectByIdParams {
  object_id: string;
  type_name: string;
}

/** Parameters for deleting an object. */
export interface DeleteObjectParams {
  object_id: string;
  type_name: string;
}

/** Parameters for finding objects with filters. */
export interface FindObjectsParams {
  type_name: string;
  filter_criteria?: Record<string, any>;
  limit?: number;
}

/** Parameters for adding a relation. */
export interface AddRelationParams {
  relation: RelationInstance;
}

/** Parameters for retrieving relations between objects. */
export interface GetRelationParams {
  from_object_id: string;
  to_object_id: string;
  relation_type_name: string;
}

/** Parameters for deleting a relation. */
export interface DeleteRelationParams {
  relation_type_name: string;
  relation_id: string;
}

/** Parameters for querying relations. */
export interface QueryRelationsParams {
  relation_type_name?: string;
  source_object_instance_id?: string;
  target_object_instance_id?: string;
  properties_query?: Record<string, any>;
  limit?: number;
}

/** Parameters for getting outgoing relations. */
export interface GetOutgoingRelationsParams {
  object_id: string;
  type_name: string;
  relation_type_name?: string;
}

/** Parameters for getting incoming relations. */
export interface GetIncomingRelationsParams {
  object_id: string;
  type_name: string;
  relation_type_name?: string;
}

/**
 * Query method parameters.
 */

/** Parameters for executing complex queries. */
export interface ExecuteComplexQueryParams {
  query: any; // ComplexQuery type will be defined elsewhere
  limit?: number;
  offset?: number;
}

/** Parameters for searching similar objects. */
export interface SearchSimilarObjectsParams {
  object_id: string;
  type_name: string;
  limit?: number;
  threshold?: number;
}

/** Parameters for finding similar objects. */
export interface FindSimilarParams {
  embedding_vector: number[];
  limit?: number;
  threshold?: number;
  object_type_names?: string[];
}

/** Similarity search result. */
export interface SimilaritySearchResult {
  object_id: string;
  object_type_name: string;
  score: number;
  properties: Record<string, any>;
}

/**
 * Embedding method parameters.
 */

/** Parameters for creating an embedding definition. */
export interface CreateEmbeddingDefinitionParams {
  name: string;
  object_type_name: string;
  source_property_name: string;
  embedding_model?: string;
  description?: string;
  dimensions?: number;
}

/** Parameters for retrieving an embedding definition. */
export interface GetEmbeddingDefinitionParams {
  name: string;
}

/** Parameters for deleting an embedding definition. */
export interface DeleteEmbeddingDefinitionParams {
  name: string;
}

/** Parameters for getting embedding vector for text. */
export interface GetEmbeddingVectorForTextParams {
  text: string;
  embedding_definition_name: string;
}

/** Embedding similarity result. */
export interface EmbeddingSimilarityResult {
  object_id: string;
  similarity_score: number;
  embedding_vector?: number[];
}

/** Parameters for searching similar objects with embeddings. */
export interface SearchSimilarObjectsWithEmbeddingsParams {
  text?: string;
  embedding_vector?: number[];
  embedding_definition_name: string;
  object_type_names?: string[];
  limit?: number;
  threshold?: number;
}