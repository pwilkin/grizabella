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

  /**
   * Optional cross-encoder model identifier (e.g.
   * 'cross-encoder/ms-marco-MiniLM-L-6-v2' or
   * 'mixedbread-ai/mxbai-rerank-base-v1'). When set, semantic searches
   * against this definition can post-process the top-K vector hits with
   * this reranker. Reranking requires the query to be provided as text
   * (not just a pre-computed vector).
   */
  reranker_model?: string;

  /**
   * Default oversampling factor used when reranking: the vector search
   * fetches `limit * rerank_candidate_multiplier` candidates before the
   * cross-encoder re-scores them down to `limit` results. Defaults to 5
   * on the server side when omitted.
   */
  rerank_candidate_multiplier?: number;
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
  /** The EmbeddingDefinition to search against. */
  embedding_definition_name: string;

  /** Raw text of the query; required when `embedding_vector` is not supplied
   *  and required for reranking (cross-encoders need text pairs). */
  text?: string;

  /** Pre-computed query vector. Mutually exclusive with `text`. */
  embedding_vector?: number[];

  /** Maximum number of results to return. Defaults to 5. */
  limit?: number;

  /** Optional LanceDB WHERE clause applied before ANN search. */
  filter_condition?: string;

  /** Optional similarity score threshold (cosine unless `is_l2_distance`). */
  threshold?: number;

  /** Force-enable or force-disable cross-encoder reranking. `undefined`
   *  auto-enables if the EmbeddingDefinition carries a reranker_model or
   *  `rerank_model` is supplied. */
  rerank?: boolean;

  /** Override the cross-encoder model identifier for this call only. */
  rerank_model?: string;

  /** Number of vector hits to pull before reranking (defaults to
   *  limit * EmbeddingDefinition.rerank_candidate_multiplier). */
  rerank_candidates?: number;
}