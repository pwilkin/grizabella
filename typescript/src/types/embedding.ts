import { MemoryInstance } from './enums';

/**
 * Defines how an embedding should be generated and stored for an ObjectTypeDefinition.
 * This model specifies the configuration for creating vector embeddings from
 * the content of objects. It links an object type and one of its properties
 * to an embedding model.
 */
export interface EmbeddingDefinition {
  /** A unique name for this embedding configuration (e.g., 'content_embedding_v1'). Convention: snake_case. */
  name: string;

  /** The name of the ObjectTypeDefinition this embedding applies to. */
  object_type_name: string;

  /** The name of the property within the ObjectTypeDefinition whose content will be embedded. */
  source_property_name: string;

  /** An identifier for the embedding model to be used (e.g., a Hugging Face model name). */
  embedding_model?: string;

  /** The expected dimensionality of the embedding vector. If None, the system may attempt to infer it from the model. */
  dimensions?: number;

  /** An optional human-readable description of this embedding definition. */
  description?: string;
}

/**
 * Represents an instance of an embedding, linked to an ObjectInstance.
 * This model stores a vector embedding generated from a specific property of
 * an ObjectInstance, according to an EmbeddingDefinition.
 */
export interface EmbeddingInstance extends MemoryInstance {
  /** The ID of the ObjectInstance to which this embedding belongs. */
  object_instance_id: string;

  /** The name of the EmbeddingDefinition that was used to generate this embedding. */
  embedding_definition_name: string;

  /** The actual embedding vector, represented as a list of floating-point numbers. */
  vector: number[];

  /** A truncated preview of the source text that was used to generate the embedding. */
  source_text_preview?: string;
}

/**
 * A container for a list of floats representing an embedding vector.
 * This is used for embedding operations and results.
 */
export interface EmbeddingVector {
  /** The embedding vector data. */
  vector: number[];
}

/**
 * Custom type definitions for embedding method parameters and return types.
 */

/** Parameters for creating an embedding definition. */
export interface CreateEmbeddingDefinitionParams {
  embedding_def: EmbeddingDefinition;
}

/** Parameters for retrieving an embedding definition. */
export interface GetEmbeddingDefinitionParams {
  name: string;
}

/** Parameters for deleting an embedding definition. */
export interface DeleteEmbeddingDefinitionParams {
  name: string;
}

/** Parameters for getting an embedding vector for text. */
export interface GetEmbeddingVectorForTextParams {
  text_to_embed: string;
  embedding_definition_name: string;
}

/** Result type for embedding-based similarity searches. */
export interface EmbeddingSimilarityResult {
  /** The object instance that was found to be similar. */
  object_instance: unknown; // Using 'unknown' to avoid circular imports, should be ObjectInstance

  /** The similarity score (distance or cosine similarity). */
  score: number;
}

/** Parameters for searching similar objects with embeddings. */
export interface SearchSimilarObjectsWithEmbeddingsParams {
  source_object_id: string;
  source_object_type_name: string;
  embedding_definition_name: string;
  n_results: number;
}