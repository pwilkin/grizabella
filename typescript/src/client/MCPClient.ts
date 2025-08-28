/**
 * MCP Client for Grizabella TypeScript API
 *
 * This module provides a comprehensive MCP (Model Context Protocol) client
 * that communicates with the Grizabella MCP server to perform knowledge
 * management operations. It handles connection management, tool calling,
 * error mapping, and response transformation.
 */


import { Decimal } from 'decimal.js';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { Transport } from '@modelcontextprotocol/sdk/shared/transport.js';

// Error handling imports
import {
  GrizabellaError,
  mapMcpError,
  ConnectionError,
  NotConnectedError,
  withRetry,
  RetryConfig,
  QueryError,
} from './errors';

// Type imports
import type {
  // Core types
  ObjectTypeDefinition,
  ObjectInstance,
  RelationTypeDefinition,
  RelationInstance,
  RelationInstanceList,
  EmbeddingDefinition,
  EmbeddingVector,
  QueryResult,
  SimilaritySearchResult,
  
  // Parameter types
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
  GetOutgoingRelationsParams,
  GetIncomingRelationsParams,
  ExecuteComplexQueryParams,
  SearchSimilarObjectsParams,
  CreateEmbeddingDefinitionParams,
  GetEmbeddingDefinitionParams,
  DeleteEmbeddingDefinitionParams,
  GetEmbeddingVectorForTextParams,
  SearchSimilarObjectsWithEmbeddingsParams,
} from '../types/index.js';

// Enum imports
import { PropertyDataType } from '../types/enums';

/**
 * Configuration options for the MCP client connection.
 */
export interface MCPClientConfig {
  /**
   * The server URL to connect to for HTTP/SSE transport, or 'stdio' for stdio transport.
   * If using stdio, the `serverCommand` must be provided.
   */
  serverUrl: string;
  /**
   * The command to start the server for stdio transport. Required when serverUrl is 'stdio'.
   */
  serverCommand?: string;
  /**
   * Arguments for the server command.
   */
  serverArgs?: string[];
  /** Connection timeout in milliseconds */
  timeout?: number;
  /** Whether to automatically reconnect on connection loss */
  autoReconnect?: boolean;
  /** Maximum number of reconnection attempts */
  maxReconnectAttempts?: number;
  /** Reconnection delay in milliseconds */
  reconnectDelay?: number;
  /** Request timeout in milliseconds */
  requestTimeout?: number;
  /** Retry configuration for failed requests */
  retryConfig?: Partial<RetryConfig>;
  /** Whether to enable debug logging */
  debug?: boolean;
}

/**
 * Connection state enumeration.
 */
export enum ConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
  RECONNECTING = 'reconnecting',
}

/**
 * MCP Client class for communicating with Grizabella MCP server.
 *
 * This class provides a high-level interface to all MCP server tools,
 * handling connection management, error mapping, and response transformation.
 * It implements proper error handling with retry logic and connection recovery.
 */
export class MCPClient {
  private client: Client | null = null;
  private transport: Transport | null = null;
  private config: Required<MCPClientConfig>;
  private connectionState: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectTimer: NodeJS.Timeout | null = null;

  /**
   * Creates a new MCP client instance.
   *
   * @param config - Configuration options for the client
   */
  constructor(config: MCPClientConfig) {
    this.config = {
      serverCommand: config.serverCommand,
      serverArgs: config.serverArgs,
      timeout: 300,
      autoReconnect: true,
      maxReconnectAttempts: 5,
      reconnectDelay: 1000,
      requestTimeout: 30000,
      debug: false,
      ...config,
    } as Required<MCPClientConfig>;

    process.stdout.write('MCPClient final config debug=' + this.config.debug + '\n');
    if (this.config.debug) {
      process.stdout.write('MCPClient created with debug enabled, config:' + JSON.stringify(this.config, null, 2) + '\n');
    }
  }

  // ===== CONNECTION MANAGEMENT =====

  /**
   * Establishes connection to the MCP server.
   *
   * @returns Promise that resolves when connected
   * @throws ConnectionError if connection fails
   */
  async connect(): Promise<void> {
    if (this.connectionState === ConnectionState.CONNECTED) {
      return;
    }

    this.connectionState = ConnectionState.CONNECTING;

    try {
      // Import and create the appropriate transport based on server URL
      if (this.config.serverUrl === 'stdio' && this.config.serverCommand) {
        // Stdio transport for local servers
        const { StdioClientTransport } = await import('@modelcontextprotocol/sdk/client/stdio.js');
        this.transport = new StdioClientTransport({
          command: this.config.serverCommand,
          args: this.config.serverArgs || [],
        });
      } else if (this.config.serverUrl.startsWith('http')) {
        // HTTP/SSE transport for remote servers
        const { SSEClientTransport } = await import('@modelcontextprotocol/sdk/client/sse.js');
        this.transport = new SSEClientTransport(new URL(this.config.serverUrl));
      } else {
        throw new Error(`Invalid server configuration: ${this.config.serverUrl}`);
      }

      // Create and connect the MCP client
      this.client = new Client(
        {
          name: 'grizabella-typescript-client',
          version: '1.0.0',
        },
        {
          capabilities: {},
        }
      );

      await this.client.connect(this.transport);
      this.connectionState = ConnectionState.CONNECTED;
      // this.reconnectAttempts = 0; // This property doesn't exist

      if (this.config.debug) {
        console.log('Connected to MCP server');
      }
    } catch (error) {
      this.connectionState = ConnectionState.ERROR;
      const connectionError = new ConnectionError(
        `Failed to connect to MCP server: ${error instanceof Error ? error.message : 'Unknown error'}`,
        { host: this.config.serverUrl },
        error instanceof Error ? error : new Error(String(error))
      );
      throw connectionError;
    }
  }

  /**
   * Disconnects from the MCP server.
   */
  async disconnect(): Promise<void> {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.client) {
      try {
        await this.client.close();
      } catch (error) {
        if (this.config.debug) {
          console.warn('Error during client close:', error);
        }
      }
      this.client = null;
    }

    if (this.transport) {
      // Transport cleanup if needed
      this.transport = null;
    }

    this.connectionState = ConnectionState.DISCONNECTED;

    if (this.config.debug) {
      console.log('Disconnected from MCP server');
    }
  }

  /**
   * Gets the current connection state.
   */
  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Checks if the client is currently connected.
   */
  isConnected(): boolean {
    return this.connectionState === ConnectionState.CONNECTED;
  }

  // ===== PRIVATE HELPER METHODS =====

  /**
   * Ensures the client is connected before making a request.
   * @throws NotConnectedError if not connected
   */
  private ensureConnected(): void {
    if (!this.isConnected()) {
      throw new NotConnectedError('MCP client is not connected');
    }
  }

  /**
   * Makes a tool call with error handling and retries.
    */
   private async callTool<T>(toolName: string, args: Record<string, any> = {}): Promise<T> {
     this.ensureConnected();

     const operation = async (): Promise<T> => {
       try {
         if (this.config.debug) {
           console.log(`Making tool call: ${toolName}`, JSON.stringify(args, null, 2));
         }
         const result = await this.client!.callTool({
           name: toolName,
           arguments: args,
         });

         // Debug: Log the raw result structure for get_embedding_vector_for_text
         if (toolName === 'get_embedding_vector_for_text' && this.config.debug) {
           console.log(`Raw MCP result for ${toolName}:`, JSON.stringify(result, null, 2));
         }

        // Handle MCP-specific errors
        if (result.isError) {
          console.log(`Error result from tool ${toolName}:`, JSON.stringify(result, null, 2));
          if (result['error']) {
            // Try to parse as MCP error response
            let mcpError;
            try {
              mcpError = JSON.parse((result['error'] as any).message);
            } catch {
              mcpError = { code: -1, message: (result['error'] as any).message };
            }
            console.log(`Parsed MCP error for ${toolName}:`, mcpError);
            throw mapMcpError(mcpError, toolName);
          }
          console.log(`No error details for failed tool ${toolName}`);
          throw new Error(`Tool call failed: ${toolName}`);
        }

        // Debug: Log the final parsed result for get_embedding_vector_for_text
        if (toolName === 'get_embedding_vector_for_text' && this.config.debug) {
          console.log(`About to parse result for ${toolName}. Raw result structure:`, JSON.stringify(result, null, 2));
        }

        // Handle MCP protocol response format
        if (Array.isArray(result.content) && result.content.length > 0) {
          const content = result.content[0];
          if (content.type === 'text') {
            try {
              const parsedData = JSON.parse(content.text);
              return parsedData;
            } catch (parseError) {
              if (this.config.debug) {
                console.log(`Failed to parse MCP text content for ${toolName}:`, content.text);
              }
              throw new Error(`Failed to parse MCP text response: ${content.text}`);
            }
          } else {
            throw new Error(`Unsupported content type: ${content.type}`);
          }
        }

        // Legacy response format handling
        if (!result['result']) {
          // Check if the result has a different structure
          if (result.hasOwnProperty('content')) {
            return result['content'] as unknown as T;
          }
          // For void operations, return undefined
          if (toolName === 'create_object_type' || toolName === 'create_relation_type' ||
              toolName === 'upsert_object' || toolName === 'add_relation' ||
              toolName === 'delete_object' || toolName === 'delete_relation' ||
              toolName === 'delete_object_type' || toolName === 'delete_relation_type') {
            return undefined as unknown as T;
          }
          throw new Error(`Empty response from tool: ${toolName}`);
        }

        // If result is already a string, parse it
        if (typeof result['result'] === 'string') {
          try {
            return JSON.parse(result['result']);
          } catch {
            return result['result'] as unknown as T;
          }
        }

        // If result is an object, return it directly
        const finalResult = result['result'] as T;

        // Debug: Log the final parsed result for get_embedding_vector_for_text
        if (toolName === 'get_embedding_vector_for_text' && this.config.debug) {
          console.log(`Final parsed result for ${toolName}:`, JSON.stringify(finalResult, null, 2));
          console.log(`Final result type: ${typeof finalResult}`);
          if (typeof finalResult === 'object' && finalResult !== null) {
            console.log(`Final result has vector property: ${'vector' in finalResult}`);
            if ('vector' in finalResult) {
              const vectorValue = (finalResult as any).vector;
              console.log(`Vector value type: ${typeof vectorValue}, isArray: ${Array.isArray(vectorValue)}, length: ${Array.isArray(vectorValue) ? vectorValue.length : 'N/A'}`);
            }
          }
        }

        return finalResult;
      } catch (error) {
        // If it's already a GrizabellaError, re-throw it
        if (error instanceof GrizabellaError) {
          throw error;
        }

        // Otherwise, wrap in a generic error
        const message = error instanceof Error ? error.message : 'Unknown error';
        throw new ConnectionError(
          `Tool call failed: ${toolName} - ${message}`,
          { operation: toolName },
          error instanceof Error ? error : new Error(message)
        );
      }
    };

    // Apply retry logic
    return withRetry(operation, this.config.retryConfig);
  }

  // ===== SCHEMA MANAGEMENT METHODS =====

  /**
   * Creates a new object type definition.
   */
  async createObjectType(params: CreateObjectTypeParams): Promise<void> {
    await this.callTool('create_object_type', {
      object_type_def: params.object_type_def,
    });
  }

  /**
   * Retrieves an object type definition by name.
   */
  async getObjectType(params: GetObjectTypeParams): Promise<ObjectTypeDefinition | null> {
    return await this.callTool<ObjectTypeDefinition | null>('get_object_type', {
      type_name: params.type_name,
    });
  }

  /**
   * Lists all defined object types.
   */
  async listObjectTypes(): Promise<ObjectTypeDefinition[]> {
    return await this.callTool<ObjectTypeDefinition[]>('list_object_types');
  }

  /**
   * Lists all defined relation types.
   */
  async listRelationTypes(): Promise<RelationTypeDefinition[]> {
    return await this.callTool<RelationTypeDefinition[]>('list_relation_types');
  }

  /**
   * Deletes an object type definition.
   */
  async deleteObjectType(params: DeleteObjectTypeParams): Promise<void> {
    await this.callTool('delete_object_type', {
      type_name: params.type_name,
    });
  }

  /**
   * Creates a new relation type definition.
   */
  async createRelationType(params: CreateRelationTypeParams): Promise<void> {
    await this.callTool('create_relation_type', {
      relation_type_def: params.relation_type_def,
    });
  }

  /**
   * Retrieves a relation type definition by name.
   */
  async getRelationType(params: GetRelationTypeParams): Promise<RelationTypeDefinition | null> {
    return await this.callTool<RelationTypeDefinition | null>('get_relation_type', {
      type_name: params.type_name,
    });
  }

  /**
   * Deletes a relation type definition.
   */
  async deleteRelationType(params: DeleteRelationTypeParams): Promise<void> {
    await this.callTool('delete_relation_type', {
      type_name: params.type_name,
    });
  }

  // ===== OBJECT OPERATIONS METHODS =====

  /**
   * Creates or updates an object instance.
   */
  async upsertObject(params: UpsertObjectParams): Promise<ObjectInstance> {
    const result = await this.callTool<ObjectInstance>('upsert_object', {
      obj: params.obj,
    });

    // If the server returns undefined (bug in MCP server), try to fetch the object by ID
    if (!result) {
      if (this.config.debug) {
        console.warn('upsertObject returned undefined, attempting to fetch object by ID:', params.obj.id);
      }
      const fetched = await this.getObjectById({
        object_id: params.obj.id,
        type_name: params.obj.object_type_name
      });
      if (fetched) {
        return fetched;
      }
      throw new Error(`Failed to upsert and retrieve object ${params.obj.id}`);
    }

    return result;
  }

  /**
   * Retrieves an object instance by ID and type.
   */
   async getObjectById(params: GetObjectByIdParams): Promise<ObjectInstance | null> {
     const rawResult = await this.callTool<any>('get_object_by_id', {
       object_id: params.object_id,
       type_name: params.type_name,
     });

     // Debug: Log the raw result structure
     if (this.config.debug) {
       console.log('getObjectById raw result:', JSON.stringify(rawResult, null, 2));
     }

     let result: ObjectInstance | null;

     // Handle MCP protocol response format
     if (Array.isArray(rawResult) && rawResult.length > 0 && rawResult[0].type === 'text') {
       // MCP protocol format: [{"type":"text","text":"{json_string}"}]
       try {
         const parsedData = JSON.parse(rawResult[0].text);
         result = parsedData;
       } catch (parseError) {
         throw new Error(`Failed to parse MCP text response: ${rawResult[0].text}`);
       }
     } else if (rawResult && typeof rawResult === 'object') {
       // Direct format: {object_instance} or null
       result = rawResult as ObjectInstance | null;
     } else {
       throw new Error(`Invalid object by ID response format: ${JSON.stringify(rawResult)}`);
     }

     // Deserialize datetime properties
     if (result && result.properties) {
       result.properties = this.deserializeProperties(result.properties);
     }

     return result;
   }

  /**
   * Deserializes properties, converting datetime strings to Date objects.
   */
  private deserializeProperties(properties: Record<string, any>): Record<string, any> {
    const deserialized = { ...properties };

    for (const [key, value] of Object.entries(deserialized)) {
      if (typeof value === 'string') {
        // Check if it's an ISO 8601 datetime string
        const isoRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$/;
        if (isoRegex.test(value)) {
          try {
            deserialized[key] = new Date(value);
          } catch (dateError) {
            // If parsing fails, keep the original string
            if (this.config.debug) {
              console.warn(`Failed to parse datetime string '${value}' for property '${key}':`, dateError);
            }
          }
        }
      }
    }

    return deserialized;
  }

  /**
  * Deletes an object instance.
  */
 async deleteObject(params: DeleteObjectParams): Promise<boolean> {
   return await this.callTool<boolean>('delete_object', {
     object_id: params.object_id,
     type_name: params.type_name,
   });
 }


 /**
  * Finds objects with optional filtering criteria.
  */
  async findObjects(params: FindObjectsParams): Promise<ObjectInstance[]> {
    return await this.callTool<ObjectInstance[]>('find_objects', {
      type_name: params.type_name,
      filter_criteria: params.filter_criteria,
      limit: params.limit,
    });
  }

  // ===== RELATION OPERATIONS METHODS =====

  /**
   * Adds a new relation instance.
   */
  async addRelation(params: AddRelationParams): Promise<RelationInstance> {
    return await this.callTool<RelationInstance>('add_relation', {
      relation: params.relation,
    });
  }

  /**
   * Retrieves relations between objects.
   */
  async getRelation(params: GetRelationParams): Promise<RelationInstanceList> {
    const rawResult = await this.callTool<any>('get_relation', {
      from_object_id: params.from_object_id,
      to_object_id: params.to_object_id,
      relation_type_name: params.relation_type_name,
    });

    // Debug: Log the raw result structure
    if (this.config.debug) {
      console.log('getRelation raw result:', JSON.stringify(rawResult, null, 2));
    }

    let result: RelationInstanceList;

    // Handle MCP protocol response format
    if (Array.isArray(rawResult) && rawResult.length > 0 && rawResult[0].type === 'text') {
      // MCP protocol format: [{"type":"text","text":"{json_string}"}]
      try {
        const parsedData = JSON.parse(rawResult[0].text);
        result = parsedData;
      } catch (parseError) {
        throw new Error(`Failed to parse MCP text response: ${rawResult[0].text}`);
      }
    } else if (rawResult && typeof rawResult === 'object') {
      // Direct format: {relations: [...], count: number}
      result = rawResult as RelationInstanceList;
    } else {
      throw new Error(`Invalid relation response format: ${JSON.stringify(rawResult)}`);
    }

    return result;
  }

  /**
   * Deletes a relation instance.
   */
  async deleteRelation(params: DeleteRelationParams): Promise<boolean> {
    return await this.callTool<boolean>('delete_relation', {
      relation_type_name: params.relation_type_name,
      relation_id: params.relation_id,
    });
  }

  /**
   * Retrieves outgoing relations from an object.
   */
  async getOutgoingRelations(params: GetOutgoingRelationsParams): Promise<RelationInstance[]> {
    return await this.callTool<RelationInstance[]>('get_outgoing_relations', {
      object_id: params.object_id,
      type_name: params.type_name,
      relation_type_name: params.relation_type_name,
    });
  }

  /**
   * Retrieves incoming relations to an object.
   */
  async getIncomingRelations(params: GetIncomingRelationsParams): Promise<RelationInstance[]> {
    return await this.callTool<RelationInstance[]>('get_incoming_relations', {
      object_id: params.object_id,
      type_name: params.type_name,
      relation_type_name: params.relation_type_name,
    });
  }

  // ===== EMBEDDING OPERATIONS METHODS =====

  /**
   * Creates a new embedding definition.
   */
  async createEmbeddingDefinition(params: CreateEmbeddingDefinitionParams): Promise<void> {
    await this.callTool('create_embedding_definition', {
      embedding_def: {
        name: params.name,
        object_type_name: params.object_type_name,
        source_property_name: params.source_property_name,
        embedding_model: params.embedding_model,
        description: params.description,
        dimensions: params.dimensions,
      },
    });
  }

  /**
   * Retrieves an embedding definition by name.
   */
  async getEmbeddingDefinition(_params: GetEmbeddingDefinitionParams): Promise<EmbeddingDefinition | null> {
    // Note: This tool is not implemented in the MCP server yet
    // We'll return null for now to maintain API compatibility
    return null;
  }

  /**
   * Deletes an embedding definition.
   */
  async deleteEmbeddingDefinition(_params: DeleteEmbeddingDefinitionParams): Promise<void> {
    // Note: This tool is not implemented in the MCP server yet
    // We'll throw a not implemented error
    throw new Error('deleteEmbeddingDefinition not implemented in MCP server');
  }

  /**
   * Generates an embedding vector for given text.
   */
  async getEmbeddingVectorForText(params: GetEmbeddingVectorForTextParams): Promise<EmbeddingVector> {
    const rawResult = await this.callTool<{ vector: number[] }>('get_embedding_vector_for_text', {
      args: {
        text_to_embed: params.text,
        embedding_definition_name: params.embedding_definition_name,
      },
    });

    // Debug: Log the raw result structure
    if (this.config.debug) {
      console.log('getEmbeddingVectorForText raw result:', JSON.stringify(rawResult, null, 2));
    }

    let vector: number[];

    // Handle MCP protocol response format
    if (Array.isArray(rawResult) && rawResult.length > 0 && rawResult[0].type === 'text') {
      // MCP protocol format: [{"type":"text","text":"{json_string}"}]
      try {
        const parsedData = JSON.parse(rawResult[0].text);
        vector = parsedData.vector;
      } catch (parseError) {
        throw new Error(`Failed to parse MCP text response: ${rawResult[0].text}`);
      }
    } else if ((rawResult as any).vector) {
      // Direct format: {"vector": [numbers]}
      vector = (rawResult as any).vector;
    } else {
      throw new Error(`Invalid embedding vector response format: ${JSON.stringify(rawResult)}`);
    }

    if (!vector || !Array.isArray(vector)) {
      throw new Error(`Invalid embedding vector: expected array, got ${typeof vector}`);
    }

    return { vector };
  }

  // ===== QUERY OPERATIONS METHODS =====

  /**
   * Searches for objects similar to a given object.
   */
  async searchSimilarObjects(params: SearchSimilarObjectsParams): Promise<Array<[ObjectInstance, number]>> {
    // Note: This tool exists but throws NotImplementedError in the current server
    try {
      return await this.callTool<Array<[ObjectInstance, number]>>('search_similar_objects', {
        object_id: params.object_id,
        type_name: params.type_name,
        limit: params.limit,
        threshold: params.threshold,
      });
    } catch (error) {
      // Re-throw with more context about the limitation
      if (error instanceof Error && error.message.includes('not yet implemented')) {
        throw new Error('searchSimilarObjects is not yet implemented in the Grizabella MCP server');
      }
      throw error;
    }
  }

  /**
   * Executes a complex query.
   */
   async executeComplexQuery(params: ExecuteComplexQueryParams): Promise<QueryResult> {
      if (this.config.debug) {
        process.stdout.write('MCPClient.executeComplexQuery called with:' + JSON.stringify(params, null, 2) + '\n');
      }

      const rawResult = await this.callTool<any>('execute_complex_query', {
        query: params.query,
      });

      // Debug: Log the raw result structure
      if (this.config.debug) {
        console.log('executeComplexQuery raw result:', JSON.stringify(rawResult, null, 2));
      }

      let result: QueryResult;

      // Handle MCP protocol response format
      if (Array.isArray(rawResult) && rawResult.length > 0 && rawResult[0].type === 'text') {
        // MCP protocol format: [{"type":"text","text":"{json_string}"}]
        try {
          const parsedData = JSON.parse(rawResult[0].text);
          result = parsedData;
        } catch (parseError) {
          throw new Error(`Failed to parse MCP text response: ${rawResult[0].text}`);
        }
      } else if (rawResult && typeof rawResult === 'object') {
        // Direct format: {object_instances: [...], errors: [...]}
        result = rawResult as QueryResult;
      } else {
        throw new Error(`Invalid complex query response format: ${JSON.stringify(rawResult)}`);
      }

      // Ensure the result has the expected structure
      return {
        object_instances: result.object_instances || [],
        errors: result.errors || [],
      };
   }

  /**
   * Finds objects similar to query text using embeddings.
   *
   * This method implements the findSimilar workflow that requires multiple MCP calls:
   * 1. Create a temporary object with the query text
   * 2. Generate embedding for the query text
   * 3. Search for similar objects using the embedding
   * 4. Clean up the temporary object
   */
  async findSimilar(params: SearchSimilarObjectsWithEmbeddingsParams): Promise<SimilaritySearchResult[]> {
    this.ensureConnected();

    let tempObjectId: string | null = null;
    const tempObjectType = 'temp_query_object';
    const tempObjectPrefix = `temp_query_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    try {
      // Step 1: Create a temporary object to hold the query text
      const tempObject: ObjectInstance = {
        id: tempObjectPrefix,
        object_type_name: tempObjectType,
        weight: new Decimal('1.0'),
        upsert_date: new Date(),
        properties: {
          text: params.text || '',
        },
      };

      // Create the temporary object type if it doesn't exist
      try {
        await this.createObjectType({
          object_type_def: {
            name: tempObjectType,
            description: 'Temporary object type for query processing',
            properties: [
              {
                name: 'text',
                data_type: PropertyDataType.TEXT,
                is_nullable: false,
              },
            ],
          },
        });
      } catch (error) {
        // Object type might already exist, continue
      }

      await this.upsertObject({ obj: tempObject });
      tempObjectId = tempObjectPrefix;

      // Step 2: Get embedding vector for the query text
      await this.callTool<{ vector: number[] }>('get_embedding_vector_for_text', {
        args: {
          text_to_embed: params.text,
          embedding_definition_name: params.embedding_definition_name,
        },
      });

      // Step 3: Search for similar objects using the embedding
      // Note: We use the search_similar_objects tool with the temp object
      const similarObjects = await this.callTool<Array<[ObjectInstance, number]>>('search_similar_objects', {
        object_id: tempObjectId,
        type_name: tempObjectType,
        limit: params.limit,
        threshold: params.threshold,
      });

      // Step 4: Transform results to SimilaritySearchResult format
      const results: SimilaritySearchResult[] = similarObjects.map(([obj, score]) => ({
        object_id: obj.id,
        object_type_name: obj.object_type_name,
        score: score,
        properties: obj.properties,
      }));

      return results;

    } catch (error) {
      // Re-throw with more context
      throw new QueryError(
        `findSimilar operation failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        {
          operation: 'findSimilar',
          context: {
            embedding_definition_name: params.embedding_definition_name,
            text: params.text,
            limit: params.limit,
            threshold: params.threshold,
          },
        },
        error instanceof Error ? error : new Error(String(error))
      );
    } finally {
      // Step 5: Clean up temporary object
      if (tempObjectId) {
        try {
          await this.deleteObject({
            object_id: tempObjectId,
            type_name: tempObjectType,
          });
        } catch (cleanupError) {
          // Log cleanup error but don't fail the operation
          if (this.config.debug) {
            console.warn('Failed to cleanup temporary object:', cleanupError);
          }
          
        }
      }
    }
  }
}