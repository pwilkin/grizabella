/**
 * Grizabella TypeScript API Client
 *
 * This module provides the main GrizabellaClient class, which serves as the public
 * API for interacting with the Grizabella data store through MCP communication.
 * It provides connection management, error handling, and serves as the foundation
 * for all data operations.
 */

import { PathLike } from 'fs';

// MCP Client integration
import { MCPClient, MCPClientConfig } from './MCPClient';

// Error handling imports
import {
  ConnectionError,
  NotConnectedError,
  ValidationError,
  QueryError,
} from './errors';

// Type imports
import type {
  // Core types
  ObjectTypeDefinition,
  ObjectInstance,
  RelationTypeDefinition,
  RelationInstance,
  EmbeddingDefinition,
  EmbeddingVector,
  ComplexQuery,
  QueryResult,
  SimilaritySearchResult,
  RelationInstanceList,
  QueryRelationsParams,
  // Parameter types
  FindObjectsParams,
  GetOutgoingRelationsParams,
  SearchSimilarObjectsParams,
  SearchSimilarObjectsWithEmbeddingsParams,
} from '../types/index.js';

/**
 * Configuration options for the Grizabella client connection.
 */
export interface GrizabellaClientConfig {
  /** The database name or path to connect to */
  dbNameOrPath?: string | PathLike;
  /** Whether to create the database if it doesn't exist */
  createIfNotExists?: boolean;
  /** MCP server URL or command to connect to */
  serverUrl?: string;
  /** Command to start the server for stdio transport */
  serverCommand?: string;
  /** Arguments for the server command */
  serverArgs?: string[];
  /** Connection timeout in milliseconds */
  timeout?: number;
  /** Whether to enable debug logging */
  debug?: boolean;
  /** Whether to automatically reconnect on connection loss */
  autoReconnect?: boolean;
  /** Maximum number of reconnection attempts */
  maxReconnectAttempts?: number;
  /** Reconnection delay in milliseconds */
  reconnectDelay?: number;
  /** Request timeout in milliseconds */
  requestTimeout?: number;
  /** Retry configuration for failed requests */
  retryConfig?: Partial<{
    maxRetries: number;
    baseDelay: number;
    maxDelay: number;
    backoffMultiplier: number;
    jitter: boolean;
  }>;
}

/**
 * Connection state enumeration for the client.
 */
export enum ClientConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
}

/**
 * Main API client for interacting with Grizabella data store.
 *
 * This class provides a high-level interface to manage connections, schema,
 * data operations, and complex queries through MCP communication. It handles
 * connection lifecycle, error mapping, and provides both explicit connection
 * management and context manager patterns for resource management.
 *
 * Example usage:
 * ```typescript
 * // Explicit connection management
 * const client = new GrizabellaClient({
 *   dbNameOrPath: 'my-database',
 *   createIfNotExists: true,
 *   debug: true,
 * });
 *
 * await client.connect();
 * // ... use client for operations ...
 * await client.close();
 *
 * // Context manager pattern (TypeScript 5.2+)
 * await using client = new GrizabellaClient({
 *   dbNameOrPath: 'my-database',
 *   createIfNotExists: true,
 * });
 * // ... use client for operations ...
 * // Connection automatically closed
 * ```
 */
export class GrizabellaClient {
  private _mcpClient: MCPClient;
  private _config: Required<GrizabellaClientConfig>;
  private _connectionState: ClientConnectionState = ClientConnectionState.DISCONNECTED;
  private _dbNameOrPath: string | PathLike;
  private _createIfNotExists: boolean;
  private _connectionCleanupRegistered: boolean = false;

  /**
   * Creates a new Grizabella client instance.
   *
   * @param config - Configuration options for the client
   *
   * @example
   * ```typescript
   * const client = new GrizabellaClient({
   *   dbNameOrPath: 'my-database',
   *   createIfNotExists: true,
   *   debug: true,
   * });
   * ```
   */
  constructor(config: GrizabellaClientConfig) {
    process.stdout.write('=== GrizabellaClient constructor called with config: ' + JSON.stringify(config, null, 2) + '\n');

    // Store and resolve database configuration
    this._dbNameOrPath = GrizabellaClient.resolveDatabasePath(config.dbNameOrPath ?? 'default');
    this._createIfNotExists = config.createIfNotExists ?? true;

    // Build the MCP server command with database path
    const dbPath = String(this._dbNameOrPath);
    const serverCommand = `/devel/alt/grizabella/.venv/bin/python`;
    const serverArgs = [`-m`, `grizabella.mcp.server`, `--db-path`, dbPath];

    // Build complete configuration with defaults
    this._config = {
      dbNameOrPath: this._dbNameOrPath,
      createIfNotExists: this._createIfNotExists,
      serverUrl: 'stdio', // Use stdio transport
      serverCommand: serverCommand, // Store the command to start the server
      serverArgs: serverArgs, // Store the arguments for the server command
      timeout: config.timeout ?? 30000,
      debug: config.debug ?? true, // Enable debug mode to see response structure
      autoReconnect: config.autoReconnect ?? true,
      maxReconnectAttempts: config.maxReconnectAttempts ?? 5,
      reconnectDelay: config.reconnectDelay ?? 1000,
      requestTimeout: config.requestTimeout ?? 30000,
      retryConfig: config.retryConfig ?? {
        maxRetries: 3,
        baseDelay: 1000,
        maxDelay: 30000,
        backoffMultiplier: 2,
        jitter: true,
      },
    };

    // Validate configuration
    this.validateConfiguration();

    // Initialize MCP client with server configuration
    const mcpConfig: MCPClientConfig = {
      serverUrl: this._config.serverUrl,
      serverCommand: this._config.serverCommand,
      serverArgs: this._config.serverArgs,
      timeout: this._config.timeout,
      autoReconnect: this._config.autoReconnect,
      maxReconnectAttempts: this._config.maxReconnectAttempts,
      reconnectDelay: this._config.reconnectDelay,
      requestTimeout: this._config.requestTimeout,
      retryConfig: this._config.retryConfig,
      debug: this._config.debug,
    };

    if (this._config.debug) {
      console.log('Creating MCPClient with config:', JSON.stringify(mcpConfig, null, 2));
    }

    this._mcpClient = new MCPClient(mcpConfig);

    if (this._config.debug) {
      console.log(`GrizabellaClient initialized for database: ${this._dbNameOrPath}`);
      console.log(`MCP server command: ${serverCommand}`);
    }
  }

  /**
   * Static factory method to create and connect a client (context manager pattern).
   *
   * This method creates a new GrizabellaClient instance and automatically connects it,
   * making it ready for use. This is the TypeScript equivalent of Python's context
   * manager pattern and is designed to be used with 'await using'.
   *
   * @param config - Configuration options for the client
   * @returns Promise that resolves to a connected GrizabellaClient
   * @throws ConnectionError if connection fails
   *
   * @example
   * ```typescript
   * // TypeScript 5.2+ context manager pattern
   * await using client = await GrizabellaClient.connect({
   *   dbNameOrPath: 'my-database',
   *   createIfNotExists: true,
   *   debug: true,
   * });
   *
   * // Client is automatically connected and ready to use
   * // ... perform database operations ...
   * // Client automatically disconnects when exiting scope
   * ```
   */
  static async connect(config: GrizabellaClientConfig): Promise<GrizabellaClient> {
    const client = new GrizabellaClient(config);
    await client.connect();
    return client;
  }

  // ===== CONNECTION MANAGEMENT =====

  /**
   * Establishes connection to the Grizabella database through MCP server.
   *
   * This method connects to the MCP server and validates the connection
   * before allowing database operations. The connection process includes:
   * 1. Connecting to the MCP server
   * 2. Validating server capabilities
   * 3. Setting up database context
   *
   * @returns Promise that resolves when connected
   * @throws ConnectionError if connection fails
   *
   * @example
   * ```typescript
   * const client = new GrizabellaClient({
   *   dbNameOrPath: 'my-database',
   *   serverUrl: 'http://localhost:8000/mcp',
   * });
   *
   * await client.connect();
   * console.log('Connected successfully!');
   * ```
   */
  async connect(): Promise<void> {
    if (this._connectionState === ClientConnectionState.CONNECTED) {
      return;
    }

    if (this._connectionState === ClientConnectionState.CONNECTING) {
      // Wait for existing connection attempt
      return new Promise((resolve, reject) => {
        const checkConnection = () => {
          if (this._connectionState === ClientConnectionState.CONNECTED) {
            resolve();
          } else if (this._connectionState === ClientConnectionState.ERROR) {
            reject(new ConnectionError('Connection attempt failed'));
          } else {
            setTimeout(checkConnection, 100);
          }
        };
        checkConnection();
      });
    }

    this._connectionState = ClientConnectionState.CONNECTING;
  
    try {
      // Connect to MCP server
      await this._mcpClient.connect();
      this._connectionState = ClientConnectionState.CONNECTED;
  
      // Register cleanup on process exit to ensure proper resource cleanup
      if (!this._connectionCleanupRegistered) {
        this.registerCleanupHandlers();
        this._connectionCleanupRegistered = true;
      }
  
      if (this._config.debug) {
        console.log(`Connected to Grizabella database: ${this._dbNameOrPath}`);
      }
    } catch (error) {
      this._connectionState = ClientConnectionState.ERROR;
      const connectionError = new ConnectionError(
        `Failed to connect to Grizabella database: ${this._dbNameOrPath}`,
        { host: this._config.serverUrl },
        error instanceof Error ? error : new Error(String(error))
      );
      throw connectionError;
    }
   }

  /**
   * Closes the connection to the Grizabella database.
   *
   * This method gracefully disconnects from the MCP server and cleans up
   * any resources. After calling close(), the client cannot be used for
   * database operations until connect() is called again.
   *
   * @returns Promise that resolves when disconnected
   *
   * @example
   * ```typescript
   * await client.close();
   * console.log('Disconnected successfully!');
   * ```
   */
  async close(): Promise<void> {
    if (this._connectionState === ClientConnectionState.DISCONNECTED) {
      return;
    }

    try {
      await this._mcpClient.disconnect();
      this._connectionState = ClientConnectionState.DISCONNECTED;

      if (this._config.debug) {
        console.log(`Disconnected from Grizabella database: ${this._dbNameOrPath}`);
      }
    } catch (error) {
      // Log error but don't throw - cleanup should be best effort
      if (this._config.debug) {
        console.warn(`Error during disconnect: ${error}`);
      }
      this._connectionState = ClientConnectionState.ERROR;
    } finally {
      // Remove cleanup handlers since we're explicitly closing
      this.removeCleanupHandlers();
    }
  }

  /**
   * Async resource disposal for 'await using' pattern (TypeScript 5.2+).
   *
   * This method enables the client to be used with the 'await using' syntax
   * for automatic resource management, similar to Python's 'async with'.
   *
   * @returns Promise that resolves when resources are cleaned up
   *
   * @example
   * ```typescript
   * // TypeScript 5.2+ context manager pattern
   * await using client = new GrizabellaClient({
   *   dbNameOrPath: 'my-database',
   *   createIfNotExists: true,
   * });
   *
   * // Client automatically connects
   * // ... use client for operations ...
   * // Client automatically disconnects when exiting scope
   * ```
   */
  async [Symbol.asyncDispose](): Promise<void> {
    await this.close();
  }

  /**
   * Gets the current connection state of the client.
   */
  getConnectionState(): ClientConnectionState {
    return this._connectionState;
  }

  /**
   * Checks if the client is currently connected to the database.
   */
  isConnected(): boolean {
    return this._connectionState === ClientConnectionState.CONNECTED &&
           this._mcpClient.isConnected();
  }

  /**
   * Gets the database name or path this client was initialized with.
   */
  get dbNameOrPath(): string | PathLike {
    return this._dbNameOrPath;
  }

  /**
   * Gets whether this client was configured to create the database if it doesn't exist.
   */
  get createIfNotExists(): boolean {
    return this._createIfNotExists;
  }

  /**
   * Registers cleanup handlers for graceful shutdown.
   */
 private registerCleanupHandlers(): void {
    const cleanup = async () => {
      if (this._config.debug) {
        console.log('Cleaning up Grizabella client resources...');
      }
      try {
        await this.close();
      } catch (error) {
        if (this._config.debug) {
          console.error('Error during cleanup:', error);
        }
      }
    };

    // Register for process termination signals
    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);
    process.on('exit', cleanup);
  }

  /**
   * Removes cleanup handlers when client is explicitly closed.
   */
  private removeCleanupHandlers(): void {
    // In a real implementation, we would remove the specific handler functions
    // For now, we'll just mark that cleanup is no longer needed
    this._connectionCleanupRegistered = false;
  }

  // ===== SCHEMA MANAGEMENT METHODS =====

  /**
   * Creates a new object type definition.
   *
   * This method defines a new object type with the specified properties and constraints.
   * The object type will be available for creating object instances and defining relations.
   *
   * @param objectTypeDef - The object type definition to create
   * @returns Promise that resolves when the object type is created
   * @throws SchemaError if the definition is invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * await client.createObjectType({
   *   name: 'Person',
   *   description: 'A person in the knowledge base',
   *   properties: [
   *     {
   *       name: 'name',
   *       data_type: PropertyDataType.TEXT,
   *       is_nullable: false,
   *     },
   *     {
   *       name: 'age',
   *       data_type: PropertyDataType.INTEGER,
   *       is_nullable: true,
   *     },
   *   ],
   * });
   * ```
   */
  async createObjectType(objectTypeDef: ObjectTypeDefinition): Promise<void> {
    this.ensureConnected();
    return await this._mcpClient.createObjectType({ object_type_def: objectTypeDef });
  }

  /**
   * Retrieves an object type definition by name.
   *
   * This method fetches the definition of a previously created object type,
   * including all its properties and constraints.
   *
   * @param typeName - The name of the object type to retrieve
   * @returns Promise that resolves to the object type definition, or null if not found
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const personType = await client.getObjectType('Person');
   * if (personType) {
   *   console.log('Person type properties:', personType.properties);
   * }
   * ```
   */
  async getObjectType(typeName: string): Promise<ObjectTypeDefinition | null> {
    this.ensureConnected();
    return await this._mcpClient.getObjectType({ type_name: typeName });
  }

  /**
   * Lists all defined object types.
   *
   * This method returns a list of all object type definitions that have been
   * created in the knowledge base.
   *
   * @returns Promise that resolves to an array of object type definitions
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const objectTypes = await client.listObjectTypes();
   * console.log('Available object types:', objectTypes.map(t => t.name));
   * ```
   */
  async listObjectTypes(): Promise<ObjectTypeDefinition[]> {
    this.ensureConnected();
    return await this._mcpClient.listObjectTypes();
  }

  /**
   * Deletes an object type definition.
   *
   * This method removes an object type definition from the knowledge base.
   * Note that this may affect existing object instances and relations.
   *
   * @param typeName - The name of the object type to delete
   * @returns Promise that resolves when the object type is deleted
   * @throws SchemaError if the object type cannot be deleted
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * await client.deleteObjectType('Person');
   * ```
   */
  async deleteObjectType(typeName: string): Promise<void> {
    this.ensureConnected();
    return await this._mcpClient.deleteObjectType({ type_name: typeName });
  }

  /**
   * Creates a new relation type definition.
   *
   * This method defines a new relation type with specified source/target object types
   * and properties. The relation type will be available for creating relation instances.
   *
   * @param relationTypeDef - The relation type definition to create
   * @returns Promise that resolves when the relation type is created
   * @throws SchemaError if the definition is invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * await client.createRelationType({
   *   name: 'KNOWS',
   *   description: 'Person knows another person',
   *   source_object_type_names: ['Person'],
   *   target_object_type_names: ['Person'],
   *   properties: [
   *     {
   *       name: 'since',
   *       data_type: PropertyDataType.DATETIME,
   *       is_nullable: true,
   *     },
   *   ],
   * });
   * ```
   */
  async createRelationType(relationTypeDef: RelationTypeDefinition): Promise<void> {
    this.ensureConnected();
    return await this._mcpClient.createRelationType({ relation_type_def: relationTypeDef });
  }

  /**
   * Retrieves a relation type definition by name.
   *
   * This method fetches the definition of a previously created relation type,
   * including all its properties, source/target types, and constraints.
   *
   * @param typeName - The name of the relation type to retrieve
   * @returns Promise that resolves to the relation type definition, or null if not found
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const knowsType = await client.getRelationType('KNOWS');
   * if (knowsType) {
   *   console.log('Source types:', knowsType.source_object_type_names);
   * }
   * ```
   */
  async getRelationType(typeName: string): Promise<RelationTypeDefinition | null> {
    this.ensureConnected();
    return await this._mcpClient.getRelationType({ type_name: typeName });
  }

  /**
   * Lists all defined relation types.
   *
   * This method returns a list of all relation type definitions that have been
   * created in the knowledge base.
   *
   * @returns Promise that resolves to an array of relation type definitions
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const relationTypes = await client.listRelationTypes();
   * console.log('Available relation types:', relationTypes.map(t => t.name));
   * ```
   */
  async listRelationTypes(): Promise<RelationTypeDefinition[]> {
    this.ensureConnected();
    return await this._mcpClient.listRelationTypes();
  }

  /**
   * Deletes a relation type definition.
   *
   * This method removes a relation type definition from the knowledge base.
   * Note that this may affect existing relation instances.
   *
   * @param typeName - The name of the relation type to delete
   * @returns Promise that resolves when the relation type is deleted
   * @throws SchemaError if the relation type cannot be deleted
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * await client.deleteRelationType('KNOWS');
   * ```
   */
  async deleteRelationType(typeName: string): Promise<void> {
    this.ensureConnected();
    return await this._mcpClient.deleteRelationType({ type_name: typeName });
  }

  // ===== EMBEDDING DEFINITION MANAGEMENT METHODS =====

  /**
   * Creates a new embedding definition.
   *
   * This method defines how embeddings should be generated for objects of a specific type,
   * linking an object type and one of its properties to an embedding model for semantic search.
   *
   * @param embeddingDef - The embedding definition to create
   * @returns Promise that resolves to the created embedding definition
   * @throws ValidationError if the definition is invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const embeddingDef: EmbeddingDefinition = {
   *   name: 'person_bio_embedding',
   *   object_type_name: 'Person',
   *   source_property_name: 'biography',
   *   embedding_model: 'text-embedding-ada-002',
   *   dimensions: 1536,
   *   description: 'Embedding for person biographies',
   * };
   *
   * const createdDef = await client.createEmbeddingDefinition(embeddingDef);
   * console.log('Created embedding definition:', createdDef.name);
   * ```
   */
  async createEmbeddingDefinition(embeddingDef: EmbeddingDefinition): Promise<EmbeddingDefinition> {
    this.ensureConnected();

    if (this._config.debug) {
      console.log('Creating embedding definition with params:', JSON.stringify(embeddingDef, null, 2));
    }

    await this._mcpClient.createEmbeddingDefinition(embeddingDef);
    return embeddingDef; // Return the original definition as created
  }

  /**
   * Retrieves an embedding definition by name.
   *
   * This method fetches the definition of a previously created embedding configuration,
   * including the object type, source property, model, and other metadata.
   *
   * @param name - The name of the embedding definition to retrieve
   * @returns Promise that resolves to the embedding definition, or null if not found
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const embeddingDef = await client.getEmbeddingDefinition('person_bio_embedding');
   * if (embeddingDef) {
   *   console.log('Found embedding definition:', embeddingDef.object_type_name);
   * } else {
   *   console.log('Embedding definition not found');
   * }
   * ```
   */
  async getEmbeddingDefinition(name: string): Promise<EmbeddingDefinition | null> {
    this.ensureConnected();
    return await this._mcpClient.getEmbeddingDefinition({ name });
  }

  /**
   * Lists all defined embedding definitions.
   *
   * This method returns a list of all embedding definitions that have been created
   * in the knowledge base, including their configurations for semantic search.
   *
   * @returns Promise that resolves to an array of embedding definitions
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const embeddingDefs = await client.listEmbeddingDefinitions();
   * console.log('Available embedding definitions:', embeddingDefs.map(ed => ed.name));
   * ```
   */
  async listEmbeddingDefinitions(): Promise<EmbeddingDefinition[]> {
    this.ensureConnected();

    // Note: listEmbeddingDefinitions is not yet implemented in the MCP server
    // For now, we'll throw a descriptive error that matches the Python client behavior
    throw new QueryError(
      'listEmbeddingDefinitions method not yet implemented in MCP server. ' +
      'This feature is planned for future implementation.',
      {
        operation: 'listEmbeddingDefinitions',
      }
    );
  }

  /**
   * Deletes an embedding definition.
   *
   * This method removes an embedding definition from the knowledge base.
   * Note that this may also affect existing embeddings depending on the
   * database implementation's handling of embedding data.
   *
   * @param name - The name of the embedding definition to delete
   * @returns Promise that resolves to true if deleted, false if not found
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const deleted = await client.deleteEmbeddingDefinition('person_bio_embedding');
   * if (deleted) {
   *   console.log('Embedding definition deleted successfully');
   * } else {
   *   console.log('Embedding definition not found');
   * }
   * ```
   */
  async deleteEmbeddingDefinition(name: string): Promise<boolean> {
    this.ensureConnected();

    try {
      await this._mcpClient.deleteEmbeddingDefinition({ name });
      return true; // If no error, assume successful deletion
    } catch (error) {
      // If the error indicates the embedding definition was not found,
      // return false instead of throwing
      if (error instanceof Error && error.message.includes('not found')) {
        return false;
      }
      // Re-throw other errors (connection issues, etc.)
      throw error;
    }
  }

  // ===== DATA MANAGEMENT METHODS =====

  // ===== OBJECT INSTANCE MANAGEMENT =====

  /**
   * Creates or updates an object instance.
   *
   * This method handles both creation of new object instances and updates to existing ones.
   * The operation is determined by the presence of an ID in the object instance - if an ID
   * exists, it will update the existing object; otherwise, it will create a new one.
   *
   * @param obj - The object instance to create or update
   * @returns Promise that resolves to the created or updated object instance
   * @throws ValidationError if the object data is invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const person = await client.upsertObject({
   *   id: 'john-doe-123',
   *   object_type_name: 'Person',
   *   weight: new Decimal('1.0'),
   *   upsert_date: new Date(),
   *   properties: {
   *     name: 'John Doe',
   *     age: 30,
   *     email: 'john@example.com',
   *   },
   * });
   * ```
   */
  async upsertObject(obj: ObjectInstance): Promise<ObjectInstance> {
    this.ensureConnected();
    return await this._mcpClient.upsertObject({ obj });
  }

  /**
   * Retrieves an object instance by ID and type.
   *
   * This method fetches a specific object instance using its unique identifier
   * and object type name for additional context and validation.
   *
   * @param objectId - The unique identifier of the object instance
   * @param typeName - The name of the object type
   * @returns Promise that resolves to the object instance, or null if not found
   * @throws ValidationError if the ID format is invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const person = await client.getObjectById('john-doe-123', 'Person');
   * if (person) {
   *   console.log('Found person:', person.properties.name);
   * }
   * ```
   */
  async getObjectById(objectId: string, typeName: string): Promise<ObjectInstance | null> {
    this.ensureConnected();
    return await this._mcpClient.getObjectById({ object_id: objectId, type_name: typeName });
  }

  /**
   * Removes an object instance.
   *
   * This method deletes an object instance by its ID and type name.
   * Note that this may also affect related relations depending on the
   * database implementation's referential integrity settings.
   *
   * @param objectId - The unique identifier of the object instance to delete
   * @param typeName - The name of the object type
   * @returns Promise that resolves to true if deleted, false if not found
   * @throws ValidationError if the ID format is invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const deleted = await client.deleteObject('john-doe-123', 'Person');
   * if (deleted) {
   *   console.log('Person deleted successfully');
   * } else {
   *   console.log('Person not found');
   * }
   * ```
   */
  async deleteObject(objectId: string, typeName: string): Promise<boolean> {
    this.ensureConnected();
    return await this._mcpClient.deleteObject({ object_id: objectId, type_name: typeName });
  }

  /**
   * Finds objects with optional filtering criteria.
   *
   * This method performs a query against object instances of a specific type,
   * with optional filtering based on property values and limits on result count.
   *
   * @param typeName - The name of the object type to query
   * @param filterCriteria - Optional filtering criteria for property values
   * @param limit - Optional maximum number of results to return
   * @returns Promise that resolves to an array of matching object instances
   * @throws ValidationError if filter criteria are invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * // Find all Person objects where age > 25
   * const adults = await client.findObjects('Person', { age: { '>': 25 } }, 100);
   *
   * // Find objects by exact property match
   * const johns = await client.findObjects('Person', { name: 'John Doe' });
   *
   * // Find all objects of a type without filtering
   * const allPeople = await client.findObjects('Person');
   * ```
   */
  async findObjects(
    typeName: string,
    filterCriteria?: Record<string, unknown>,
    limit?: number
  ): Promise<ObjectInstance[]> {
    this.ensureConnected();
    
    // Build params object conditionally to avoid passing undefined values
    const params: FindObjectsParams = {
      type_name: typeName
    };
    
    if (filterCriteria !== undefined) {
      params.filter_criteria = filterCriteria;
    }
    
    if (limit !== undefined) {
      params.limit = limit;
    }
    
    return await this._mcpClient.findObjects(params);
  }

  // ===== RELATION INSTANCE MANAGEMENT =====

  /**
   * Creates a new relation instance between objects.
   *
   * This method establishes a relationship between two object instances using
   * the specified relation type and optional properties.
   *
   * @param relation - The relation instance to create
   * @returns Promise that resolves to the created relation instance
   * @throws ValidationError if the relation data is invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const relation = await client.addRelation({
   *   id: 'knows-relation-1',
   *   relation_type_name: 'KNOWS',
   *   source_object_instance_id: 'john-doe-123',
   *   target_object_instance_id: 'jane-doe-456',
   *   weight: new Decimal('1.0'),
   *   upsert_date: new Date(),
   *   properties: {
   *     since: new Date('2022-01-15'),
   *   },
   * });
   * ```
   */
  async addRelation(relation: RelationInstance): Promise<RelationInstance> {
    this.ensureConnected();
    return await this._mcpClient.addRelation({ relation });
  }

  /**
   * Retrieves relations between specific objects.
   *
   * This method finds all relations of a given type that exist between
   * two specific object instances.
   *
   * @param fromObjectId - The source object instance ID
   * @param toObjectId - The target object instance ID
   * @param relationTypeName - The name of the relation type
   * @returns Promise that resolves to a list of matching relations
   * @throws ValidationError if the parameters are invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const relations = await client.getRelation(
   *   'john-doe-123',
   *   'jane-doe-456',
   *   'KNOWS'
   * );
   * console.log('Found relations:', relations.relations.length);
   * ```
   */
  async getRelation(
    fromObjectId: string,
    toObjectId: string,
    relationTypeName: string
  ): Promise<RelationInstanceList> {
    this.ensureConnected();
    return await this._mcpClient.getRelation({
      from_object_id: fromObjectId,
      to_object_id: toObjectId,
      relation_type_name: relationTypeName,
    });
  }

  /**
   * Removes a relation instance.
   *
   * This method deletes a specific relation instance by its type name and ID.
   *
   * @param relationTypeName - The name of the relation type
   * @param relationId - The unique identifier of the relation instance
   * @returns Promise that resolves to true if deleted, false if not found
   * @throws ValidationError if the parameters are invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * const deleted = await client.deleteRelation('KNOWS', 'knows-relation-1');
   * if (deleted) {
   *   console.log('Relation deleted successfully');
   * } else {
   *   console.log('Relation not found');
   * }
   * ```
   */
  async deleteRelation(relationTypeName: string, relationId: string): Promise<boolean> {
    this.ensureConnected();
    return await this._mcpClient.deleteRelation({
      relation_type_name: relationTypeName,
      relation_id: relationId,
    });
  }

  /**
   * Queries relations with various criteria.
   *
   * This method performs complex relation queries with multiple optional filters
   * including source/target object IDs, relation type, and property-based filtering.
   *
   * @param params - Query parameters for relation filtering
   * @returns Promise that resolves to an array of matching relation instances
   * @throws ValidationError if query parameters are invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * // Query all KNOWS relations
   * const knowsRelations = await client.queryRelations({
   *   relation_type_name: 'KNOWS',
   *   limit: 50,
   * });
   *
   * // Query relations from a specific object
   * const outgoingRelations = await client.queryRelations({
   *   source_object_instance_id: 'john-doe-123',
   * });
   *
   * // Query with property filtering
   * const recentRelations = await client.queryRelations({
   *   relation_type_name: 'KNOWS',
   *   properties_query: { since: { '>': new Date('2023-01-01') } },
   * });
   * ```
   */
  async queryRelations(params: QueryRelationsParams): Promise<RelationInstance[]> {
    this.ensureConnected();
    // Note: This method needs to be implemented in the MCP client
    // For now, we'll throw a descriptive error
    throw new QueryError(
      'queryRelations method not yet implemented in MCP client wrapper. Use getOutgoingRelations, getIncomingRelations, or getRelation instead.',
      {
        operation: 'queryRelations',
        parameters: params as Record<string, unknown>,
      }
    );
  }

  /**
   * Retrieves outgoing relations from an object.
   *
   * This method finds all relations where the specified object is the source,
   * optionally filtered by relation type name.
   *
   * @param objectId - The source object instance ID
   * @param typeName - The object type name for validation
   * @param relationTypeName - Optional relation type name filter
   * @returns Promise that resolves to an array of outgoing relation instances
   * @throws ValidationError if the parameters are invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * // Get all outgoing relations from John
   * const relations = await client.getOutgoingRelations('john-doe-123', 'Person');
   *
   * // Get only KNOWS relations from John
   * const knowsRelations = await client.getOutgoingRelations(
   *   'john-doe-123',
   *   'Person',
   *   'KNOWS'
   * );
   * ```
   */
  async getOutgoingRelations(
    objectId: string,
    typeName: string,
    relationTypeName?: string
  ): Promise<RelationInstance[]> {
    this.ensureConnected();
    
    // Build params object conditionally to avoid passing undefined values
    const params: GetOutgoingRelationsParams = {
      object_id: objectId,
      type_name: typeName
    };
    
    if (relationTypeName !== undefined) {
      params.relation_type_name = relationTypeName;
    }
    
    return await this._mcpClient.getOutgoingRelations(params);
  }

  /**
   * Retrieves incoming relations to an object.
   *
   * This method finds all relations where the specified object is the target,
   * optionally filtered by relation type name.
   *
   * @param objectId - The target object instance ID
   * @param typeName - The object type name for validation
   * @param relationTypeName - Optional relation type name filter
   * @returns Promise that resolves to an array of incoming relation instances
   * @throws ValidationError if the parameters are invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * // Get all incoming relations to John
   * const relations = await client.getIncomingRelations('john-doe-123', 'Person');
   *
   * // Get only WORKS_FOR relations to John
   * const workRelations = await client.getIncomingRelations(
   *   'john-doe-123',
   *   'Person',
   *   'WORKS_FOR'
   * );
   * ```
   */
  async getIncomingRelations(
    objectId: string,
    typeName: string,
    relationTypeName?: string
  ): Promise<RelationInstance[]> {
    this.ensureConnected();
    
    // Build params object conditionally to avoid passing undefined values
    const params: GetOutgoingRelationsParams = {
      object_id: objectId,
      type_name: typeName
    };
    
    if (relationTypeName !== undefined) {
      params.relation_type_name = relationTypeName;
    }
    
    return await this._mcpClient.getIncomingRelations(params);
  }

  // ===== QUERY AND SEARCH METHODS =====

  /**
   * Searches for objects similar to a given object.
   *
   * This method finds objects that are semantically similar to the specified object
   * based on their embedding vectors. It's useful for finding related content,
   * recommendations, or similar entities within the same object type.
   *
   * @param objectId - The unique identifier of the object to find similarities for
   * @param typeName - The name of the object type
   * @param nResults - Optional maximum number of similar objects to return (default: 5)
   * @param searchProperties - Optional array of property names to consider for similarity search
   * @returns Promise that resolves to an array of tuples containing similar objects and their similarity scores
   * @throws ValidationError if the parameters are invalid
   * @throws NotConnectedError if not connected
   *
   * @example
   * ```typescript
   * // Find similar people to John Doe
   * const similarPeople = await client.searchSimilarObjects('john-doe-123', 'Person', 10);
   * console.log('Found', similarPeople.length, 'similar people');
   *
   * // Find similar documents based on specific properties
   * const similarDocs = await client.searchSimilarObjects(
   *   'doc-456',
   *   'Document',
   *   5,
   *   ['title', 'content']
   * );
   * ```
   */
  async searchSimilarObjects(
    objectId: string,
    typeName: string,
    nResults?: number,
    // searchProperties?: string[]  // Parameter is defined in the interface but not used in the implementation
  ): Promise<Array<[ObjectInstance, number]>> {
    this.ensureConnected();
    
    // Build params object conditionally to avoid passing undefined values
    const params: SearchSimilarObjectsParams = {
      object_id: objectId,
      type_name: typeName
    };
    
    if (nResults !== undefined) {
      params.limit = nResults;
    }
    
    // Note: Not adding threshold parameter since it doesn't exist in the SearchSimilarObjectsParams interface
    // The interface shows it as optional but with 'exactOptionalPropertyTypes: true', we can't pass undefined
    
    return await this._mcpClient.searchSimilarObjects(params);
  }

  /**
   * Finds objects similar to query text using embeddings.
   *
   * This method performs semantic search by converting the query text into an embedding
   * vector and finding objects with similar embeddings. It's particularly useful for
   * natural language queries, content discovery, and recommendation systems.
   *
   * @param embeddingName - The name of the embedding definition to use for the search
   * @param queryText - The text query to find similar objects for
   * @param limit - Optional maximum number of results to return (default: 5)
   * @param filterCondition - Optional filter condition to apply to results
   * @returns Promise that resolves to an array of similarity search results
   * @throws ValidationError if the parameters are invalid
   * @throws NotConnectedError if not connected
   * @throws QueryError if the embedding definition is not found or invalid
   *
   * @example
   * ```typescript
   * // Find documents similar to a query
   * const similarDocs = await client.findSimilar(
   *   'document_embedding',
   *   'machine learning and artificial intelligence',
   *   10
   * );
   *
   * console.log('Found', similarDocs.length, 'similar documents');
   * similarDocs.forEach(result => {
   *   console.log('Document:', result.object.properties.title);
   *   console.log('Similarity score:', result.score);
   * });
   *
   * // Find products with filtering
   * const similarProducts = await client.findSimilar(
   *   'product_embedding',
   *   'wireless bluetooth headphones',
   *   5,
   *   'price < 100'
   * );
   * ```
   */
  async findSimilar(
    embeddingName: string,
    queryText: string,
    limit?: number,
    // filterCondition?: string  // Parameter is defined in the interface but not used in the implementation
  ): Promise<SimilaritySearchResult[]> {
    this.ensureConnected();

    // Validate parameters
    if (!embeddingName || embeddingName.trim() === '') {
      throw new ValidationError('embeddingName is required and cannot be empty');
    }
    if (!queryText || queryText.trim() === '') {
      throw new ValidationError('queryText is required and cannot be empty');
    }

    // Call the MCP client method that handles the complex workflow
    // Build params object conditionally to avoid passing undefined values
    const params: SearchSimilarObjectsWithEmbeddingsParams = {
      text: queryText,
      embedding_definition_name: embeddingName
    };
    
    if (limit !== undefined) {
      params.limit = limit;
    }
    
    // Note: Not adding threshold parameter since with 'exactOptionalPropertyTypes: true',
    // we can't pass undefined. The parameter is optional in the interface.
    
    const results = await this._mcpClient.findSimilar(params);

    return results;
  }

  /**
   * Generates an embedding vector for given text.
   *
   * This method converts text into an embedding vector using the specified embedding definition.
   * The embedding vector can be used for semantic similarity searches and other embedding-based operations.
   *
   * @param text - The text to generate an embedding vector for
   * @param embeddingDefinitionName - The name of the embedding definition to use (default: 'PaperAbstractEmbedding')
   * @returns Promise that resolves to the embedding vector
   * @throws ValidationError if the text or embedding definition name is invalid
   * @throws NotConnectedError if not connected
   * @throws QueryError if the embedding generation fails
   *
   * @example
   * ```typescript
   * // Generate embedding for query text
   * const embeddingVector = await client.getEmbeddingVectorForText(
   *   'machine learning and artificial intelligence',
   *   'document_embedding'
   * );
   *
   * console.log('Embedding vector:', embeddingVector.vector);
   * ```
   */
  async getEmbeddingVectorForText(text: string, embeddingDefinitionName = 'PaperAbstractEmbedding'): Promise<EmbeddingVector> {
    this.ensureConnected();

    // Validate parameters
    if (!text || text.trim() === '') {
      throw new ValidationError('Text is required and cannot be empty');
    }
    if (!embeddingDefinitionName || embeddingDefinitionName.trim() === '') {
      throw new ValidationError('Embedding definition name is required and cannot be empty');
    }

    // Generate the embedding vector
    const result = await this._mcpClient.getEmbeddingVectorForText({
      text: text,
      embedding_definition_name: embeddingDefinitionName,
    });

    return result;
  }

  /**
   * Executes a complex query with graph traversals and filters.
   *
   * This method allows for sophisticated queries that can span multiple object types,
   * perform graph traversals, apply complex filters, and combine multiple search criteria.
   * It's designed for advanced use cases that require more than simple property-based filtering.
   *
   * @param query - The complex query definition containing logical clauses, filters, and traversals
   * @returns Promise that resolves to the query result containing matching objects and any errors
   * @throws ValidationError if the query structure is invalid
   * @throws NotConnectedError if not connected
   * @throws QueryError if the query execution fails
   *
   * @example
   * ```typescript
   * // Find friends of friends who are over 30
   * const query: ComplexQuery = {
   *   description: 'Find friends of friends over 30',
   *   query_root: {
   *     object_type_name: 'Person',
   *     relational_filters: [
   *       {
   *         property_name: 'age',
   *         operator: '>',
   *         value: 30,
   *       },
   *     ],
   *     graph_traversals: [
   *       {
   *         relation_type_name: 'KNOWS',
   *         direction: 'outgoing',
   *         target_object_type_name: 'Person',
   *       },
   *       {
   *         relation_type_name: 'KNOWS',
   *         direction: 'outgoing',
   *         target_object_type_name: 'Person',
   *       },
   *     ],
   *   },
   * };
   *
   * const result = await client.executeComplexQuery(query);
   * console.log('Found', result.object_instances.length, 'matching objects');
   * if (result.errors && result.errors.length > 0) {
   *   console.log('Query errors:', result.errors);
   * }
   *
   * // Query with multiple conditions and embedding search
   * const complexQuery: ComplexQuery = {
   *   description: 'Advanced search combining filters and embeddings',
   *   query_root: {
   *     operator: 'AND',
   *     clauses: [
   *       {
   *         object_type_name: 'Document',
   *         relational_filters: [
   *           {
   *             property_name: 'published_date',
   *             operator: '>',
   *             value: new Date('2023-01-01'),
   *           },
   *         ],
   *         embedding_searches: [
   *           {
   *             embedding_definition_name: 'document_embedding',
   *             similar_to_payload: [0.1, 0.2, 0.3], // embedding vector
   *             threshold: 0.8,
   *             limit: 10,
   *           },
   *         ],
   *       },
   *     ],
   *   },
   * };
   * ```
   */
  async executeComplexQuery(query: ComplexQuery): Promise<QueryResult> {
    this.ensureConnected();

    // Validate query structure
    if (!query) {
      throw new ValidationError('Query is required');
    }

    if (!query.query_root && !query.components) {
      throw new ValidationError('Query must have either query_root or components defined');
    }

    // Execute the complex query
    const result = await this._mcpClient.executeComplexQuery({
      query: query,
    });

    return result;
  }

  // ===== PRIVATE HELPER METHODS =====

  /**
   * Ensures the client is connected before performing operations.
   * @throws NotConnectedError if not connected
   */
  private ensureConnected(): void {
    if (!this.isConnected()) {
      throw new NotConnectedError('Grizabella client is not connected. Call connect() first.');
    }
  }

  // /**
  //  * Creates a database context string for error reporting and logging.
  //  */
  // private getDatabaseContext(): Record<string, any> {
  //   return {
  //     database: this._dbNameOrPath,
  //     serverUrl: this._config.serverUrl,
  //     createIfNotExists: this._createIfNotExists,
  //     connectionState: this._connectionState,
  //   };
  // }

  // ===== CONFIGURATION AND VALIDATION =====

  /**
   * Validates the client configuration.
   * @throws ValidationError if configuration is invalid
   */
  private validateConfiguration(): void {
    if (!this._config.serverUrl) {
      throw new ConnectionError('Server URL or command is required');
    }

    // Validate server URL format
    try {
      if (this._config.serverUrl.startsWith('http')) {
        new URL(this._config.serverUrl);
      } else {
        // For stdio commands, ensure it's not empty and looks like a command
        if (!this._config.serverUrl.trim()) {
          throw new Error('Invalid server command');
        }
        // Basic validation for command format
        if (!this._config.serverUrl.includes('grizabella.mcp.server')) {
          console.warn('Server command does not appear to be a Grizabella MCP server command');
        }
      }
    } catch (error) {
      throw new ConnectionError(
        `Invalid server URL/command format: ${this._config.serverUrl}`,
        { host: this._config.serverUrl },
        error instanceof Error ? error : new Error(String(error))
      );
    }

    // Validate database name/path
    if (!this._dbNameOrPath || String(this._dbNameOrPath).trim() === '') {
      throw new ConnectionError('Database name or path is required');
    }

    // Validate timeout values
    if (this._config.timeout <= 0) {
      throw new ConnectionError('Timeout must be positive');
    }

    if (this._config.requestTimeout <= 0) {
      throw new ConnectionError('Request timeout must be positive');
    }
  }

  /**
   * Resolves the database path to an absolute path if needed.
   * @param dbPath - The database path to resolve
   * @returns The resolved database path
   */
  private static resolveDatabasePath(dbPath: string | PathLike): string | PathLike {
    // If it's already absolute or if it's a string that looks like a name rather than a path,
    // return as-is
    const pathStr = String(dbPath);

    if (pathStr.includes('/') || pathStr.includes('\\') ||
        pathStr.startsWith('http') || pathStr.startsWith('sqlite:///')) {
      return dbPath;
    }

    // For simple names, assume they should be treated as database names
    return dbPath;
  }

}

/**
 * Type exports for external use.
 */

/**
 * ## Comprehensive Usage Examples
 *
 * ### 1. Basic Connection Management
 * ```typescript
 * import { GrizabellaClient } from './client/GrizabellaClient';
 *
 * // Create and connect manually
 * const client = new GrizabellaClient({
 *   dbNameOrPath: 'my-database',
 *   createIfNotExists: true,
 *   debug: true,
 * });
 *
 * await client.connect();
 * console.log('Connected:', client.isConnected());
 * await client.close();
 * ```
 *
 * ### 2. Context Manager Pattern (TypeScript 5.2+)
 * ```typescript
 * // Using static connect method
 * await using client = await GrizabellaClient.connect({
 *   dbNameOrPath: 'my-database',
 *   serverUrl: 'http://localhost:8000/mcp',
 * });
 * // Client automatically connects and disconnects
 *
 * // Using constructor with await using
 * await using client = new GrizabellaClient({
 *   dbNameOrPath: 'my-database',
 *   serverUrl: 'http://localhost:8000/mcp',
 * });
 * await client.connect(); // Must call connect explicitly
 * // Client automatically disconnects via Symbol.asyncDispose
 * ```
 *
 * ### 3. Database Configuration
 * ```typescript
 * // Using a specific database path
 * const client1 = new GrizabellaClient({
 *   dbNameOrPath: './data/my-database',
 *   createIfNotExists: true,
 * });
 *
 * // Using default database location
 * const client2 = new GrizabellaClient({
 *   dbNameOrPath: 'my-database',
 *   createIfNotExists: true,
 * });
 * ```
 *
 * ### 4. Error Handling
 * ```typescript
 * import { ConnectionError, NotConnectedError } from './errors';
 *
 * try {
 *   const client = new GrizabellaClient({
 *     dbNameOrPath: 'my-database',
 *     serverUrl: 'invalid-url',
 *   });
 *   await client.connect();
 * } catch (error) {
 *   if (error instanceof ConnectionError) {
 *     console.log('Connection failed:', error.message);
 *   } else {
 *     console.log('Other error:', error.message);
 *   }
 * }
 * ```
 *
 * ### 5. Connection State Monitoring
 * ```typescript
 * const client = new GrizabellaClient({
 *   dbNameOrPath: 'my-database',
 *   serverUrl: 'http://localhost:8000/mcp',
 * });
 *
 * console.log('State:', client.getConnectionState());
 * await client.connect();
 * console.log('Connected:', client.isConnected());
 * console.log('State:', client.getConnectionState());
 * ```
 *
 * ### 6. Configuration Options
 * ```typescript
 * const client = new GrizabellaClient({
 *   dbNameOrPath: './data/my-database',
 *   serverUrl: 'http://localhost:8000/mcp',
 *   createIfNotExists: true,
 *   timeout: 10000,
 *   debug: true,
 *   autoReconnect: true,
 *   maxReconnectAttempts: 3,
 *   reconnectDelay: 2000,
 * });
 * ```
 *
 * ## Integration with Python Client API
 *
 * The TypeScript client maintains API compatibility with the Python client:
 *
 * | Python API | TypeScript API |
 * |------------|----------------|
 * | `Grizabella(db, create)` | `new GrizabellaClient({dbNameOrPath, createIfNotExists})` |
 * | `client.connect()` | `await client.connect()` |
 * | `client.close()` | `await client.close()` |
 * | `with client:` | `await using client = await GrizabellaClient.connect()` |
 *
 * ## Best Practices
 *
 * 1. **Always handle connection errors** - Network issues can occur at any time
 * 2. **Use context managers** - They ensure proper resource cleanup
 * 3. **Validate configuration** - Check required parameters before creating clients
 * 4. **Monitor connection state** - Check `isConnected()` before operations
 * 5. **Enable debug logging** - Helps with troubleshooting connection issues
 * 6. **Configure timeouts appropriately** - Balance responsiveness with reliability
 */