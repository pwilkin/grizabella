# Grizabella TypeScript API Reference

Complete API reference for the Grizabella TypeScript client library.

## Table of Contents

- [GrizabellaClient](#grizabellaclient)
  - [Constructor](#constructor)
  - [Connection Management](#connection-management)
  - [Schema Management](#schema-management)
  - [Data Operations](#data-operations)
  - [Query and Search](#query-and-search)
- [Type Definitions](#type-definitions)
  - [Core Types](#core-types)
  - [Configuration Types](#configuration-types)
  - [Error Types](#error-types)
- [Utility Functions](#utility-functions)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

## GrizabellaClient

The main client class for interacting with Grizabella databases through MCP communication.

### Constructor

```typescript
new GrizabellaClient(config: GrizabellaClientConfig)
```

Creates a new Grizabella client instance.

#### Parameters

- `config` (GrizabellaClientConfig): Configuration options for the client

#### Example

```typescript
const client = new GrizabellaClient({
  dbNameOrPath: 'my-database',
  createIfNotExists: true,
  debug: true,
});
```

**Note:** The client uses stdio transport by default and automatically starts the MCP server. The `serverUrl` parameter is optional and defaults to 'stdio'.

### Static Methods

#### `connect(config)`

```typescript
static async connect(config: GrizabellaClientConfig): Promise<GrizabellaClient>
```

Factory method that creates and connects a client (context manager pattern).

#### Parameters

- `config` (GrizabellaClientConfig): Configuration options

#### Returns

- `Promise<GrizabellaClient>`: Connected client instance

#### Example

```typescript
await using client = await GrizabellaClient.connect({
  dbNameOrPath: 'my-database',
  createIfNotExists: true,
  debug: true,
});
```

**Note:** The static `connect()` method creates a client and automatically connects it. This is the recommended approach for TypeScript 5.2+ context manager pattern.

## Connection Management

### `connect()`

```typescript
async connect(): Promise<void>
```

Establishes connection to the Grizabella database through MCP server.

#### Throws

- `ConnectionError`: If connection fails
- `ValidationError`: If configuration is invalid

#### Example

```typescript
const client = new GrizabellaClient(config);
await client.connect();
```

### `close()`

```typescript
async close(): Promise<void>
```

Closes the connection to the Grizabella database.

#### Example

```typescript
await client.close();
```

### `isConnected()`

```typescript
isConnected(): boolean
```

Checks if the client is currently connected to the database.

#### Returns

- `boolean`: True if connected, false otherwise

### `getConnectionState()`

```typescript
getConnectionState(): ClientConnectionState
```

Gets the current connection state of the client.

#### Returns

- `ClientConnectionState`: Current connection state

### `[Symbol.asyncDispose]()`

```typescript
async [Symbol.asyncDispose](): Promise<void>
```

Async resource disposal for 'await using' pattern (TypeScript 5.2+).

## Schema Management

### Object Types

#### `createObjectType(objectTypeDef)`

```typescript
async createObjectType(objectTypeDef: ObjectTypeDefinition): Promise<void>
```

Creates a new object type definition.

##### Parameters

- `objectTypeDef` (ObjectTypeDefinition): The object type definition to create

##### Throws

- `SchemaError`: If the definition is invalid
- `NotConnectedError`: If not connected

##### Example

```typescript
await client.createObjectType({
  name: 'Person',
  description: 'A person in the system',
  properties: [
    {
      name: 'name',
      data_type: PropertyDataType.TEXT,
      is_nullable: false,
    },
    {
      name: 'age',
      data_type: PropertyDataType.INTEGER,
      is_nullable: true,
    },
  ],
});
```

#### `getObjectType(typeName)`

```typescript
async getObjectType(typeName: string): Promise<ObjectTypeDefinition | null>
```

Retrieves an object type definition by name.

##### Parameters

- `typeName` (string): The name of the object type to retrieve

##### Returns

- `Promise<ObjectTypeDefinition | null>`: The object type definition, or null if not found

#### `listObjectTypes()`

```typescript
async listObjectTypes(): Promise<ObjectTypeDefinition[]>
```

Lists all defined object types.

##### Returns

- `Promise<ObjectTypeDefinition[]>`: Array of object type definitions

#### `deleteObjectType(typeName)`

```typescript
async deleteObjectType(typeName: string): Promise<void>
```

Deletes an object type definition.

##### Parameters

- `typeName` (string): The name of the object type to delete

### Relation Types

#### `createRelationType(relationTypeDef)`

```typescript
async createRelationType(relationTypeDef: RelationTypeDefinition): Promise<void>
```

Creates a new relation type definition.

##### Parameters

- `relationTypeDef` (RelationTypeDefinition): The relation type definition to create

#### `getRelationType(typeName)`

```typescript
async getRelationType(typeName: string): Promise<RelationTypeDefinition | null>
```

Retrieves a relation type definition by name.

#### `listRelationTypes()`

```typescript
async listRelationTypes(): Promise<RelationTypeDefinition[]>
```

Lists all defined relation types.

#### `deleteRelationType(typeName)`

```typescript
async deleteRelationType(typeName: string): Promise<void>
```

Deletes a relation type definition.

### Embedding Definitions

#### `createEmbeddingDefinition(embeddingDef)`

```typescript
async createEmbeddingDefinition(embeddingDef: EmbeddingDefinition): Promise<EmbeddingDefinition>
```

Creates a new embedding definition.

##### Parameters

- `embeddingDef` (EmbeddingDefinition): The embedding definition to create

##### Returns

- `Promise<EmbeddingDefinition>`: The created embedding definition

#### `getEmbeddingDefinition(name)`

```typescript
async getEmbeddingDefinition(name: string): Promise<EmbeddingDefinition | null>
```

Retrieves an embedding definition by name.

#### `listEmbeddingDefinitions()`

```typescript
async listEmbeddingDefinitions(): Promise<EmbeddingDefinition[]>
```

Lists all defined embedding definitions.

#### `deleteEmbeddingDefinition(name)`

```typescript
async deleteEmbeddingDefinition(name: string): Promise<boolean>
```

Deletes an embedding definition.

##### Returns

- `Promise<boolean>`: True if deleted, false if not found

## Data Operations

### Object Instance Management

#### `upsertObject(obj)`

```typescript
async upsertObject(obj: ObjectInstance): Promise<ObjectInstance>
```

Creates or updates an object instance.

##### Parameters

- `obj` (ObjectInstance): The object instance to create or update

##### Returns

- `Promise<ObjectInstance>`: The created or updated object instance

##### Example

```typescript
const person = await client.upsertObject({
  id: 'person-1',
  object_type_name: 'Person',
  weight: new Decimal('1.0'),
  upsert_date: new Date(),
  properties: {
    name: 'John Doe',
    age: 30,
    email: 'john@example.com',
  },
});
```

#### `getObjectById(objectId, typeName)`

```typescript
async getObjectById(objectId: string, typeName: string): Promise<ObjectInstance | null>
```

Retrieves an object instance by ID and type.

##### Parameters

- `objectId` (string): The unique identifier of the object instance
- `typeName` (string): The name of the object type

##### Returns

- `Promise<ObjectInstance | null>`: The object instance, or null if not found

#### `deleteObject(objectId, typeName)`

```typescript
async deleteObject(objectId: string, typeName: string): Promise<boolean>
```

Deletes an object instance.

##### Parameters

- `objectId` (string): The unique identifier of the object instance
- `typeName` (string): The name of the object type

##### Returns

- `Promise<boolean>`: True if deleted, false if not found

#### `findObjects(typeName, filterCriteria, limit)`

```typescript
async findObjects(
  typeName: string,
  filterCriteria?: Record<string, any>,
  limit?: number
): Promise<ObjectInstance[]>
```

Finds objects with optional filtering criteria.

##### Parameters

- `typeName` (string): The name of the object type to query
- `filterCriteria` (Record<string, any>, optional): Filtering criteria for property values
- `limit` (number, optional): Maximum number of results to return

##### Returns

- `Promise<ObjectInstance[]>`: Array of matching object instances

##### Example

```typescript
// Find all engineers
const engineers = await client.findObjects('Person', {
  department: 'Engineering'
});

// Find people aged 25-35
const adults = await client.findObjects('Person', {
  age: { '>': 25, '<=': 35 }
}, 100);
```

### Relation Instance Management

#### `addRelation(relation)`

```typescript
async addRelation(relation: RelationInstance): Promise<RelationInstance>
```

Creates a new relation instance between objects.

##### Parameters

- `relation` (RelationInstance): The relation instance to create

##### Returns

- `Promise<RelationInstance>`: The created relation instance

#### `getRelation(fromObjectId, toObjectId, relationTypeName)`

```typescript
async getRelation(
  fromObjectId: string,
  toObjectId: string,
  relationTypeName: string
): Promise<RelationInstanceList>
```

Retrieves relations between specific objects.

#### `deleteRelation(relationTypeName, relationId)`

```typescript
async deleteRelation(relationTypeName: string, relationId: string): Promise<boolean>
```

Deletes a relation instance.

#### `queryRelations(params)`

```typescript
async queryRelations(params: QueryRelationsParams): Promise<RelationInstance[]>
```

Queries relations with various criteria.

#### `getOutgoingRelations(objectId, typeName, relationTypeName)`

```typescript
async getOutgoingRelations(
  objectId: string,
  typeName: string,
  relationTypeName?: string
): Promise<RelationInstance[]>
```

Retrieves outgoing relations from an object.

#### `getIncomingRelations(objectId, typeName, relationTypeName)`

```typescript
async getIncomingRelations(
  objectId: string,
  typeName: string,
  relationTypeName?: string
): Promise<RelationInstance[]>
```

Retrieves incoming relations to an object.

## Query and Search

### Similarity Search

#### `searchSimilarObjects(objectId, typeName, nResults, searchProperties)`

```typescript
async searchSimilarObjects(
  objectId: string,
  typeName: string,
  nResults?: number,
  searchProperties?: string[]
): Promise<Array<[ObjectInstance, number]>>
```

Searches for objects similar to a given object using embeddings.

##### Parameters

- `objectId` (string): The unique identifier of the object to find similarities for
- `typeName` (string): The name of the object type
- `nResults` (number, optional): Maximum number of similar objects to return
- `searchProperties` (string[], optional): Array of property names to consider

##### Returns

- `Promise<Array<[ObjectInstance, number]>>`: Array of tuples containing similar objects and similarity scores

#### `findSimilar(embeddingName, queryText, limit, filterCondition)`

```typescript
async findSimilar(
  embeddingName: string,
  queryText: string,
  limit?: number,
  filterCondition?: string
): Promise<SimilaritySearchResult[]>
```

Finds objects similar to query text using embeddings.

##### Parameters

- `embeddingName` (string): The name of the embedding definition to use
- `queryText` (string): The text query to find similar objects for
- `limit` (number, optional): Maximum number of results to return
- `filterCondition` (string, optional): Filter condition to apply to results

##### Returns

- `Promise<SimilaritySearchResult[]>`: Array of similarity search results

### Complex Queries

#### `executeComplexQuery(query)`

```typescript
async executeComplexQuery(query: ComplexQuery): Promise<QueryResult>
```

Executes a complex query with graph traversals and filters.

##### Parameters

- `query` (ComplexQuery): The complex query definition

##### Returns

- `Promise<QueryResult>`: The query result containing matching objects and errors

## Type Definitions

### Core Types

#### ObjectTypeDefinition

Schema definition for objects.

```typescript
interface ObjectTypeDefinition {
  name: string;           // Unique name for the object type
  description?: string;   // Human-readable description
  properties: PropertyDefinition[]; // List of properties
}
```

#### PropertyDefinition

Defines a single property within an object type.

```typescript
interface PropertyDefinition {
  name: string;                    // Property name
  data_type: PropertyDataType;     // Data type
  is_primary_key?: boolean;        // Whether this is a primary key
  is_nullable?: boolean;           // Whether the property can be null
  is_indexed?: boolean;            // Whether the property is indexed
  is_unique?: boolean;             // Whether values must be unique
  description?: string;            // Property description
}
```

#### ObjectInstance

Represents a concrete instance of an object type.

```typescript
interface ObjectInstance extends MemoryInstance {
  object_type_name: string;        // Name of the object type
  properties: Record<string, any>; // Property values
}
```

#### RelationTypeDefinition

Schema for relationships between objects.

```typescript
interface RelationTypeDefinition {
  name: string;                           // Unique relation type name
  description?: string;                   // Human-readable description
  source_object_type_names: string[];     // Allowed source object types
  target_object_type_names: string[];     // Allowed target object types
  properties?: PropertyDefinition[];      // Relation properties
}
```

#### RelationInstance

Represents a concrete relationship instance.

```typescript
interface RelationInstance extends MemoryInstance {
  relation_type_name: string;             // Name of the relation type
  source_object_instance_id: string;      // Source object ID
  target_object_instance_id: string;      // Target object ID
  properties?: Record<string, any>;       // Relation properties
}
```

#### EmbeddingDefinition

Configuration for generating embeddings.

```typescript
interface EmbeddingDefinition {
  name: string;                    // Unique embedding definition name
  object_type_name: string;        // Object type to embed
  source_property_name: string;    // Property to use for embedding
  embedding_model: string;         // Embedding model identifier
  dimensions?: number;             // Embedding dimensions
  description?: string;            // Human-readable description
}
```

#### MemoryInstance

Common interface for storable instances.

```typescript
interface MemoryInstance {
  id: string;              // Unique identifier
  weight: Decimal;         // Importance/relevance weight (0-10)
  upsert_date: Date;       // Last modification timestamp
}
```

### Configuration Types

#### GrizabellaClientConfig

Configuration options for the Grizabella client.

```typescript
interface GrizabellaClientConfig {
  dbNameOrPath?: string | PathLike;     // Database name or path
  createIfNotExists?: boolean;          // Create database if it doesn't exist
  serverUrl: string;                    // MCP server URL
  timeout?: number;                     // Connection timeout (ms)
  debug?: boolean;                      // Enable debug logging
  autoReconnect?: boolean;              // Auto-reconnect on failure
  maxReconnectAttempts?: number;        // Max reconnection attempts
  reconnectDelay?: number;              // Delay between reconnection attempts
  requestTimeout?: number;              // Request timeout (ms)
  retryConfig?: Partial<RetryConfig>;   // Retry configuration
}
```

#### ClientConnectionState

Enumeration of possible connection states.

```typescript
enum ClientConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
}
```

### Error Types

#### GrizabellaError

Base error class for all Grizabella-related errors.

```typescript
class GrizabellaError extends Error {
  readonly category: ErrorCategory;
  readonly severity: ErrorSeverity;
  readonly details?: Record<string, any>;
  readonly cause?: Error;
}
```

#### Specialized Error Classes

- `ConnectionError`: Connection-related errors
- `NotConnectedError`: Operations attempted while not connected
- `SchemaError`: Schema definition and validation errors
- `ValidationError`: Data validation errors
- `EmbeddingError`: Embedding-related errors
- `QueryError`: Query execution errors
- `McpProtocolError`: MCP protocol errors

## Utility Functions

### Validation Functions

#### `validateObjectTypeDefinition(definition)`

Validates an object type definition.

#### `validateRelationTypeDefinition(definition)`

Validates a relation type definition.

#### `validateObjectInstance(instance, definition)`

Validates an object instance against its type definition.

#### `validateRelationInstance(instance)`

Validates a relation instance.

### Conversion Functions

#### `createObjectInstance(typeName, properties)`

Creates a new object instance with default metadata.

#### `createRelationInstance(relationData)`

Creates a new relation instance with default metadata.

#### `createMultipleObjectInstances(client, typeName, dataArray)`

Creates multiple object instances in batch.

### Helper Functions

#### `processObjectInstancesBatch(client, instances, processor, options)`

Processes object instances in batches with a custom processor function.

#### `withRetry(operation, config)`

Executes an operation with automatic retry logic.

#### `createErrorBoundary(options)`

Creates an error boundary for handling errors gracefully.

### Performance Utilities

#### `timeAsync(operation, name)`

Times an async operation and returns duration and result.

#### `timeSync(operation, name)`

Times a synchronous operation.

#### `createMemoryReport()`

Creates a memory usage report.

#### `PerformanceMonitor`

Class for monitoring performance metrics.

### Configuration Utilities

#### `loadConfigFromEnv()`

Loads configuration from environment variables.

#### `validateConfig(config)`

Validates a configuration object.

#### `buildConfig(overrides)`

Builds a complete configuration with defaults.

## Error Handling

### Error Hierarchy

```
GrizabellaError (base)
├── ConnectionError
├── NotConnectedError
├── SchemaError
├── ValidationError
├── EmbeddingError
├── QueryError
└── McpProtocolError
```

### Error Properties

All Grizabella errors include:

- `message`: Human-readable error message
- `category`: Error category (e.g., 'connection', 'validation')
- `severity`: Error severity ('low', 'medium', 'high', 'critical')
- `details`: Additional error context
- `cause`: Original error that caused this error

### Error Handling Patterns

#### Basic Error Handling

```typescript
try {
  await client.connect();
} catch (error) {
  if (error instanceof ConnectionError) {
    console.log('Connection failed:', error.message);
    console.log('Server URL:', error.details?.host);
  }
}
```

#### Retry Logic

```typescript
import { withRetry, DEFAULT_RETRY_CONFIG } from 'grizabella-typescript-api';

const result = await withRetry(
  () => client.findObjects('Person'),
  {
    maxAttempts: 3,
    baseDelay: 1000,
    maxDelay: 5000,
  }
);
```

#### Error Boundaries

```typescript
import { createErrorBoundary } from 'grizabella-typescript-api';

const errorBoundary = createErrorBoundary({
  onError: (error) => {
    console.error('Error caught by boundary:', error.message);
    return { fallback: null };
  },
  shouldCatch: (error) => error instanceof QueryError,
});

const result = await errorBoundary(async () => {
  return await client.executeComplexQuery(complexQuery);
});
```

## Best Practices

### Connection Management

1. **Use context managers** when possible (TypeScript 5.2+)
2. **Always handle connection errors** explicitly
3. **Configure timeouts appropriately** for your environment
4. **Enable auto-reconnect** for production applications
5. **Validate configuration** before creating clients

### Data Operations

1. **Validate data** before operations using utility functions
2. **Use batch operations** for multiple records
3. **Handle partial failures** in batch operations
4. **Set appropriate weights** for important data
5. **Use meaningful IDs** for better traceability

### Query Optimization

1. **Use specific filters** to reduce result sets
2. **Limit results** when you don't need all matches
3. **Index frequently queried properties** in your schema
4. **Profile query performance** using timing utilities
5. **Consider embedding dimensions** for similarity search

### Error Handling

1. **Catch specific error types** rather than generic errors
2. **Implement retry logic** for transient failures
3. **Log errors appropriately** for debugging
4. **Use error boundaries** for graceful degradation
5. **Validate inputs** before operations

### Performance

1. **Monitor memory usage** in long-running applications
2. **Batch operations** to reduce network overhead
3. **Use connection pooling** when appropriate
4. **Cache frequently accessed data** when possible
5. **Profile and optimize** slow operations

### TypeScript Best Practices

1. **Use strict typing** throughout your application
2. **Leverage utility types** for complex data structures
3. **Create type guards** for runtime type checking
4. **Use generics** for reusable components
5. **Document complex types** with TSDoc comments