/**
 * MCP Client for Grizabella TypeScript API
 *
 * This module provides a comprehensive MCP (Model Context Protocol) client
 * that communicates with the Grizabella MCP server to perform knowledge
 * management operations. It handles connection management, tool calling,
 * error mapping, and response transformation.
 */


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
  /** Whether to use GPU for embedding models */
  useGpu?: boolean;
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
 private reconnectAttempts: number = 0;
 private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 1000; // in ms
  private reconnectPromise: Promise<void> | null = null;
  private reconnectResolve: (() => void) | null = null;
  private reconnectReject: ((error: Error) => void) | null = null;

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
      useGpu: false,
      ...config,
    } as Required<MCPClientConfig>;

    // Initialize reconnect configuration
    this.maxReconnectAttempts = this.config.maxReconnectAttempts;
    this.reconnectDelay = this.config.reconnectDelay;

    process.stderr.write('MCPClient final config debug=' + this.config.debug + '\n');
    if (this.config.debug) {
      process.stderr.write('MCPClient created with debug enabled, config:' + JSON.stringify(this.config, null, 2) + '\n');
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

    // If we're already trying to reconnect, return the existing promise
    if (this.reconnectPromise) {
      return this.reconnectPromise;
    }

    this.connectionState = ConnectionState.CONNECTING;

    try {
      // Import and create the appropriate transport based on server URL
      if (this.config.serverUrl === 'stdio' && this.config.serverCommand) {
        // Stdio transport for local servers
        const { StdioClientTransport } = await import('@modelcontextprotocol/sdk/client/stdio.js');
        const finalArgs = this.config.serverArgs || [];
        process.stderr.write(`MCPClient spawning: ${this.config.serverCommand} ${finalArgs.join(' ')}\n`);
        this.transport = new StdioClientTransport({
          command: this.config.serverCommand,
          args: finalArgs,
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

      // Add event listeners for connection events
      this.setupConnectionEventListeners();

      await this.client.connect(this.transport);
      this.connectionState = ConnectionState.CONNECTED;
      this.reconnectAttempts = 0; // Reset reconnect attempts on successful connection

      if (this.config.debug) {
        console.error('Connected to MCP server');
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

    // Reject any pending reconnection promise
    if (this.reconnectReject) {
      this.reconnectReject(new Error('Client disconnected'));
      this.reconnectPromise = null;
      this.reconnectResolve = null;
      this.reconnectReject = null;
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
      console.error('Disconnected from MCP server');
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

  // ===== CONNECTION EVENT HANDLERS =====
  
  /**
   * Sets up event listeners for connection events to handle reconnection.
   */
  private setupConnectionEventListeners(): void {
    if (!this.client || !this.transport) {
      return;
    }

    // For stdio transport, we need to handle process events
    // Since transport is an abstract class, we need to check the underlying process
    // Access the transport's process if it's a stdio transport
    const transportAny: any = this.transport;
    if (transportAny.process) {
      // This is likely a stdio transport
      transportAny.process.on('exit', (code: number, signal: string) => {
        if (this.config.debug) {
          console.error(`Transport process exited with code ${code}, signal ${signal}`);
        }
        this.handleTransportDisconnect();
      });
      
      transportAny.process.on('error', (error: Error) => {
        if (this.config.debug) {
          console.error(`Transport process error:`, error);
        }
        this.handleTransportDisconnect();
      });
    }
 }

  /**
   * Handles transport disconnection events.
   */
  private async handleTransportDisconnect(): Promise<void> {
    if (this.config.debug) {
      console.error('Transport disconnected, attempting reconnection...');
    }
    
    this.connectionState = ConnectionState.ERROR;
    
    if (this.config.autoReconnect) {
      await this.attemptReconnect();
    }
  }

  /**
   * Attempts to reconnect to the MCP server with exponential backoff.
   */
  private async attemptReconnect(): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      if (this.config.debug) {
        console.error(`Max reconnection attempts (${this.maxReconnectAttempts}) reached. Giving up.`);
      }
      return;
    }

    this.connectionState = ConnectionState.RECONNECTING;
    
    if (this.config.debug) {
      console.error(`Attempting reconnection (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts}) in ${this.reconnectDelay}ms...`);
    }

    // Create a promise for the reconnection attempt
    this.reconnectPromise = new Promise((resolve, reject) => {
      this.reconnectResolve = resolve;
      this.reconnectReject = reject;
    });

    // Wait for the delay before attempting to reconnect
    await new Promise(resolve => setTimeout(resolve, this.reconnectDelay));

    try {
      // Disconnect any existing client/transport
      if (this.client) {
        try {
          await this.client.close();
        } catch (error) {
          if (this.config.debug) {
            console.warn('Error closing existing client during reconnection:', error);
          }
        }
      }
      
      this.client = null;
      this.transport = null;

      // Attempt to reconnect
      await this.connect();
      
      if (this.config.debug) {
        console.error('Reconnection successful!');
      }
      
      this.reconnectAttempts = 0; // Reset on successful reconnection
      
      if (this.reconnectResolve) {
        this.reconnectResolve();
        this.reconnectPromise = null;
        this.reconnectResolve = null;
        this.reconnectReject = null;
      }
    } catch (error) {
      if (this.config.debug) {
        console.error(`Reconnection attempt failed:`, error);
      }
      
      this.reconnectAttempts++;
      
      // Calculate exponential backoff delay (with max delay)
      const maxDelay = this.config.reconnectDelay * 10; // Max 10x the original delay
      const nextDelay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts), maxDelay);
      
      // Set up the next reconnection attempt
      this.reconnectTimer = setTimeout(async () => {
        await this.attemptReconnect();
      }, nextDelay);
    }
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
   private async callTool<T>(toolName: string, args: Record<string, unknown> = {}): Promise<T> {
     this.ensureConnected();

     const operation = async (): Promise<T> => {
       try {
         if (this.config.debug) {
           console.error(`Making tool call: ${toolName}`, JSON.stringify(args, null, 2));
         }
         const result = await this.client!.callTool({
           name: toolName,
           arguments: args,
         });

         // Debug: Log the raw result structure for get_embedding_vector_for_text
         if (toolName === 'get_embedding_vector_for_text' && this.config.debug) {
           console.error(`Raw MCP result for ${toolName}:`, JSON.stringify(result, null, 2));
         }

        // Handle MCP-specific errors
        if (result.isError) {
          console.error(`Error result from tool ${toolName}:`, JSON.stringify(result, null, 2));
          if (result['error']) {
            // Try to parse as MCP error response
            let mcpError;
            try {
              mcpError = JSON.parse((result['error'] as { message: string }).message);
            } catch {
              mcpError = { code: -1, message: (result['error'] as { message: string }).message };
            }
            console.error(`Parsed MCP error for ${toolName}:`, mcpError);
            throw mapMcpError(mcpError, toolName);
          }
          console.error(`No error details for failed tool ${toolName}`);
          throw new Error(`Tool call failed: ${toolName}`);
        }

        // Debug: Log the final parsed result for get_embedding_vector_for_text
        if (toolName === 'get_embedding_vector_for_text' && this.config.debug) {
          console.error(`About to parse result for ${toolName}. Raw result structure:`, JSON.stringify(result, null, 2));
        }

        // Handle MCP protocol response format
        if (Array.isArray(result.content) && result.content.length > 0) {
          const content = result.content[0];
          if (content.type === 'text') {
            try {
              const parsedData = JSON.parse(content.text);
              return parsedData;
            } catch (_parseError) {
              if (this.config.debug) {
                console.error(`Failed to parse MCP text content for ${toolName}:`, content.text);
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
          console.error(`Final parsed result for ${toolName}:`, JSON.stringify(finalResult, null, 2));
          console.error(`Final result type: ${typeof finalResult}`);
          if (typeof finalResult === 'object' && finalResult !== null) {
            console.error(`Final result has vector property: ${'vector' in finalResult}`);
            if ('vector' in finalResult) {
              const vectorValue = (finalResult as { vector?: unknown }).vector;
              console.error(`Vector value type: ${typeof vectorValue}, isArray: ${Array.isArray(vectorValue)}, length: ${Array.isArray(vectorValue) ? vectorValue.length : 'N/A'}`);
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
   * Finds relation instances based on optional filters.
   */
  async findRelations(params: {
    relation_type_name?: string;
    source_object_id?: string;
    target_object_id?: string;
    limit?: number;
  }): Promise<RelationInstance[]> {
    const args: Record<string, unknown> = {};
    if (params.relation_type_name !== undefined) {
      args['relation_type_name'] = params.relation_type_name;
    }
    if (params.source_object_id !== undefined) {
      args['source_object_id'] = params.source_object_id;
    }
    if (params.target_object_id !== undefined) {
      args['target_object_id'] = params.target_object_id;
    }
    if (params.limit !== undefined) {
      args['limit'] = params.limit;
    }
    return await this.callTool<RelationInstance[]>('find_relations', args);
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
     const rawResult = await this.callTool<unknown>('get_object_by_id', {
       object_id: params.object_id,
       type_name: params.type_name,
     });

     // Debug: Log the raw result structure
     if (this.config.debug) {
       console.error('getObjectById raw result:', JSON.stringify(rawResult, null, 2));
     }

     let result: ObjectInstance | null;

     // Handle MCP protocol response format
     if (Array.isArray(rawResult) && rawResult.length > 0 && rawResult[0].type === 'text') {
       // MCP protocol format: [{"type":"text","text":"{json_string}"}]
       try {
         const parsedData = JSON.parse(rawResult[0].text);
         result = parsedData;
       } catch (_parseError) {
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
  private deserializeProperties(properties: Record<string, unknown>): Record<string, unknown> {
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
    const rawResult = await this.callTool<unknown>('get_relation', {
      from_object_id: params.from_object_id,
      to_object_id: params.to_object_id,
      relation_type_name: params.relation_type_name,
    });

    // Debug: Log the raw result structure
    if (this.config.debug) {
      console.error('getRelation raw result:', JSON.stringify(rawResult, null, 2));
    }

    let result: RelationInstanceList;

    // Handle MCP protocol response format
    if (Array.isArray(rawResult) && rawResult.length > 0 && rawResult[0].type === 'text') {
      // MCP protocol format: [{"type":"text","text":"{json_string}"}]
      try {
        const parsedData = JSON.parse(rawResult[0].text);
        result = parsedData;
      } catch (_parseError) {
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
    const args: Record<string, unknown> = {
      object_id: params.object_id,
      type_name: params.type_name,
    };
    if (params.relation_type_name !== undefined) {
      args['relation_type_name'] = params.relation_type_name;
    }
    return await this.callTool<RelationInstance[]>('get_outgoing_relations', args);
  }

  /**
   * Retrieves incoming relations to an object.
   */
  async getIncomingRelations(params: GetIncomingRelationsParams): Promise<RelationInstance[]> {
    const args: Record<string, unknown> = {
      object_id: params.object_id,
      type_name: params.type_name,
    };
    if (params.relation_type_name !== undefined) {
      args['relation_type_name'] = params.relation_type_name;
    }
    return await this.callTool<RelationInstance[]>('get_incoming_relations', args);
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
   * Starts a bulk addition operation.
   */
  async beginBulkAddition(): Promise<void> {
    await this.callTool('begin_bulk_addition');
  }

  /**
   * Finishes a bulk addition operation.
   */
  async finishBulkAddition(): Promise<void> {
    await this.callTool('finish_bulk_addition');
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
      console.error('getEmbeddingVectorForText raw result:', JSON.stringify(rawResult, null, 2));
    }

    let vector: number[];

    // Handle MCP protocol response format
    if (Array.isArray(rawResult) && rawResult.length > 0 && rawResult[0].type === 'text') {
      // MCP protocol format: [{"type":"text","text":"{json_string}"}]
      try {
        const parsedData = JSON.parse(rawResult[0].text);
        vector = parsedData.vector;
      } catch (_parseError) {
        throw new Error(`Failed to parse MCP text response: ${rawResult[0].text}`);
      }
    } else if ((rawResult as { vector?: unknown }).vector) {
      // Direct format: {"vector": [numbers]}
      vector = (rawResult as { vector: number[] }).vector;
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
        process.stderr.write('MCPClient.executeComplexQuery called with:' + JSON.stringify(params, null, 2) + '\n');
      }

      const rawResult = await this.callTool<unknown>('execute_complex_query', {
        query: params.query,
      });

      // Debug: Log the raw result structure
      if (this.config.debug) {
        console.error('executeComplexQuery raw result:', JSON.stringify(rawResult, null, 2));
      }

      let result: QueryResult;

      // Handle MCP protocol response format
      if (Array.isArray(rawResult) && rawResult.length > 0 && rawResult[0].type === 'text') {
        // MCP protocol format: [{"type":"text","text":"{json_string}"}]
        try {
          const parsedData = JSON.parse(rawResult[0].text);
          result = parsedData;
        } catch (_parseError) {
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
   * Dispatches directly to the Python MCP server's `find_similar_by_embedding`
   * tool, which embeds the query text server-side, performs the vector search
   * in LanceDB, and (when enabled) re-scores the top-K candidates with a
   * cross-encoder reranker before returning the top `limit` objects.
   *
   * If only a pre-computed `embedding_vector` is supplied (no `text`), the
   * call falls back to an `execute_complex_query` with an
   * `EmbeddingSearchClause` — that path does not support reranking because
   * cross-encoders need the raw query text.
   */
  async findSimilar(params: SearchSimilarObjectsWithEmbeddingsParams): Promise<SimilaritySearchResult[]> {
    this.ensureConnected();

    if (!params.text && !params.embedding_vector) {
      throw new QueryError(
        'findSimilar requires either `text` (preferred, enables reranking) or a precomputed `embedding_vector`.',
        { operation: 'findSimilar' },
      );
    }

    try {
      if (params.text) {
        // Preferred path: the server embeds the text, runs the ANN search,
        // and optionally reranks — all in one MCP tool call.
        const toolArgs: Record<string, unknown> = {
          embedding_definition_name: params.embedding_definition_name,
          query_text: params.text,
          limit: params.limit ?? 5,
        };
        if (params.filter_condition !== undefined) {
          toolArgs['filter_condition'] = params.filter_condition;
        }
        if (params.rerank !== undefined) {
          toolArgs['rerank'] = params.rerank;
        }
        if (params.rerank_model !== undefined) {
          toolArgs['rerank_model'] = params.rerank_model;
        }
        if (params.rerank_candidates !== undefined) {
          toolArgs['rerank_candidates'] = params.rerank_candidates;
        }
        const objects = await this.callTool<ObjectInstance[]>('find_similar_by_embedding', {
          args: toolArgs,
        });
        return objects.map((obj) => ({
          object_id: obj.id,
          object_type_name: obj.object_type_name,
          score: Number(obj.properties?.['_similarity_score'] ?? 0),
          properties: obj.properties,
        }));
      }

      // Vector-only path: use execute_complex_query so we can pass a
      // pre-computed vector through EmbeddingSearchClause. No reranking.
      const queryResult = await this.callTool<{
        object_instances: ObjectInstance[];
        errors?: string[];
      }>('execute_complex_query', {
        query: {
          description: 'findSimilar (vector-only)',
          components: [
            {
              object_type_name: params.object_type_names?.[0] ?? '',
              embedding_searches: [
                {
                  embedding_definition_name: params.embedding_definition_name,
                  similar_to_payload: params.embedding_vector,
                  limit: params.limit ?? 5,
                  ...(params.threshold !== undefined ? { threshold: params.threshold } : {}),
                },
              ],
            },
          ],
        },
      });
      return (queryResult.object_instances ?? []).map((obj) => ({
        object_id: obj.id,
        object_type_name: obj.object_type_name,
        score: 0,
        properties: obj.properties,
      }));
    } catch (error) {
      throw new QueryError(
        `findSimilar operation failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        {
          operation: 'findSimilar',
          context: {
            embedding_definition_name: params.embedding_definition_name,
            has_text: Boolean(params.text),
            has_vector: Boolean(params.embedding_vector),
            limit: params.limit,
            rerank: params.rerank,
            rerank_model: params.rerank_model,
          },
        },
        error instanceof Error ? error : new Error(String(error)),
      );
    }
  }
}