# Grizabella TypeScript API

[![npm version](https://badge.fury.io/js/grizabella-typescript-api.svg)](https://badge.fury.io/js/grizabella-typescript-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)

A comprehensive TypeScript client library for Grizabella, providing type-safe access to multi-database knowledge graph operations through MCP (Model Context Protocol) communication.

## 🚀 Features

- **Multi-Database Support**: Connect to SQLite, LadybugDB, and LanceDB databases
- **Type-Safe Operations**: Full TypeScript support with comprehensive type definitions
- **Schema Management**: Create and manage object types, relation types, and embeddings
- **Graph Operations**: Perform complex graph traversals and queries
- **Semantic Search**: Vector similarity search with embedding support
- **MCP Integration**: Seamless communication with Grizabella MCP servers
- **Error Handling**: Robust error handling with retry logic and detailed error types
- **Resource Management**: Context manager pattern with automatic cleanup
- **Developer Experience**: Rich debugging, logging, and performance monitoring

## 📦 Installation

### NPM
```bash
npm install grizabella-typescript-api
```

### Yarn
```bash
yarn add grizabella-typescript-api
```

### Requirements

- **Node.js**: 18.0.0 or higher
- **TypeScript**: 5.0.0 or higher
- **Grizabella MCP Server**: Running instance (local or remote)

## 🏁 Quick Start

### 🎯 **New to Grizabella?** Start Here!

**📖 [Quick Start Guide](docs/quickstart.md)** - Complete step-by-step tutorial for beginners

**💻 Working Example**: [`examples/basic-usage-working.ts`](examples/basic-usage-working.ts) - Compilable code you can run immediately

### Basic Connection

```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';

// Create and connect to a database
await using client = await GrizabellaClient.connect({
  dbNameOrPath: 'my-knowledge-base',
  createIfNotExists: true,
  debug: true,
});

// Client automatically connects and will disconnect when scope ends
console.log('Connected:', client.isConnected());
```

### Schema Definition and Data Operations

```typescript
// Define an object type
await client.createObjectType({
  name: 'Person',
  description: 'A person in the knowledge base',
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
    {
      name: 'email',
      data_type: PropertyDataType.TEXT,
      is_unique: true,
    },
  ],
});

// Create a relation type
await client.createRelationType({
  name: 'KNOWS',
  description: 'Person knows another person',
  source_object_type_names: ['Person'],
  target_object_type_names: ['Person'],
  properties: [
    {
      name: 'since',
      data_type: PropertyDataType.DATETIME,
      is_nullable: true,
    },
  ],
});

// Create object instances
const john = await client.upsertObject({
  id: 'john-doe-123',
  object_type_name: 'Person',
  weight: new Decimal('1.0'),
  upsert_date: new Date(),
  properties: {
    name: 'John Doe',
    age: 30,
    email: 'john@example.com',
  },
});

// Create relationships
await client.addRelation({
  id: 'friendship-1',
  relation_type_name: 'KNOWS',
  source_object_instance_id: 'john-doe-123',
  target_object_instance_id: 'jane-doe-456',
  weight: new Decimal('1.0'),
  upsert_date: new Date(),
  properties: {
    since: new Date('2022-01-15'),
  },
});
```

### Querying Data

```typescript
// Find objects with filters
const adults = await client.findObjects('Person', { age: { '>': 25 } });

// Get object by ID
const person = await client.getObjectById('john-doe-123', 'Person');

// Query relationships
const outgoingRelations = await client.getOutgoingRelations('john-doe-123', 'Person', 'KNOWS');
const incomingRelations = await client.getIncomingRelations('john-doe-123', 'Person');
```

### Semantic Search

```typescript
// Create an embedding definition
await client.createEmbeddingDefinition({
  name: 'person_bio_embedding',
  object_type_name: 'Person',
  source_property_name: 'biography',
  embedding_model: 'text-embedding-ada-002',
  dimensions: 1536,
  description: 'Embedding for person biographies',
});

// Find similar objects using semantic search
const similarPeople = await client.findSimilar(
  'person_bio_embedding',
  'software engineer with machine learning experience',
  10
);

console.log(`Found ${similarPeople.length} similar people`);
```

## 📚 API Overview

### Core Concepts

#### Object Types and Instances

- **ObjectTypeDefinition**: Schema definition for objects (like tables in databases)
- **ObjectInstance**: Concrete data instances conforming to an object type
- **PropertyDefinition**: Individual property specifications within object types

#### Relation Types and Instances

- **RelationTypeDefinition**: Schema for relationships between objects (like edges in graphs)
- **RelationInstance**: Concrete relationship instances between object instances

#### Embeddings and Semantic Search

- **EmbeddingDefinition**: Configuration for generating vector embeddings from object properties
- **SimilaritySearch**: Finding semantically similar objects using vector similarity

### Connection Management

```typescript
// Manual connection management
const client = new GrizabellaClient({
  dbNameOrPath: 'my-database',
  serverUrl: 'http://localhost:8000/mcp',
});

await client.connect();
// ... use client
await client.close();

// Context manager pattern (TypeScript 5.2+)
await using client = new GrizabellaClient({
  dbNameOrPath: 'my-database',
  serverUrl: 'http://localhost:8000/mcp',
});
// Client automatically connects
// ... use client
// Client automatically disconnects
```

### Error Handling

```typescript
import {
  GrizabellaError,
  ConnectionError,
  NotConnectedError,
  ValidationError,
  QueryError,
  withRetry,
} from 'grizabella-typescript-api';

try {
  await client.connect();
} catch (error) {
  if (error instanceof ConnectionError) {
    console.log('Failed to connect:', error.message);
  } else if (error instanceof ValidationError) {
    console.log('Invalid configuration:', error.message);
  }
}

// Using retry logic
const result = await withRetry(
  () => client.findObjects('Person'),
  { maxAttempts: 3, baseDelay: 1000 }
);
```

## ⚙️ Configuration

### Connection Options

```typescript
interface GrizabellaClientConfig {
  // Database configuration
  dbNameOrPath?: string | PathLike;
  createIfNotExists?: boolean;

  // Server configuration
  serverUrl: string;

  // Timeouts
  timeout?: number;           // Connection timeout (default: 30000ms)
  requestTimeout?: number;    // Request timeout (default: 30000ms)

  // Connection management
  autoReconnect?: boolean;         // Auto-reconnect on failure (default: true)
  maxReconnectAttempts?: number;   // Max reconnection attempts (default: 5)
  reconnectDelay?: number;         // Delay between reconnection attempts (default: 1000ms)

  // Development
  debug?: boolean;                 // Enable debug logging (default: false)

  // Retry configuration
  retryConfig?: Partial<RetryConfig>;
}
```

### Environment Variables

```bash
# Database configuration
GRIZABELLA_DB_PATH=./data/my-database
GRIZABELLA_CREATE_IF_NOT_EXISTS=true

# Server configuration
GRIZABELLA_SERVER_URL=http://localhost:8000/mcp

# Connection settings
GRIZABELLA_TIMEOUT=30000
GRIZABELLA_DEBUG=false
GRIZABELLA_AUTO_RECONNECT=true

# Retry configuration
GRIZABELLA_MAX_RETRIES=3
GRIZABELLA_RETRY_DELAY=1000
```

### Advanced Configuration

```typescript
import { loadConfigFromEnv, validateConfig, buildConfig } from 'grizabella-typescript-api';

// Load configuration from environment variables
const config = loadConfigFromEnv();

// Validate configuration
const validConfig = validateConfig(config);

// Build configuration with defaults
const finalConfig = buildConfig({
  dbNameOrPath: 'my-database',
  serverUrl: 'http://localhost:8000/mcp',
  // ... other options
});
```

## 🔧 Advanced Usage

### Complex Queries

```typescript
// Define a complex query with graph traversals
const query: ComplexQuery = {
  description: 'Find friends of friends who work in tech',
  query_root: {
    object_type_name: 'Person',
    relational_filters: [
      {
        property_name: 'industry',
        operator: '==',
        value: 'technology',
      },
    ],
    graph_traversals: [
      {
        relation_type_name: 'KNOWS',
        direction: 'outgoing',
        target_object_type_name: 'Person',
      },
      {
        relation_type_name: 'KNOWS',
        direction: 'outgoing',
        target_object_type_name: 'Person',
      },
    ],
  },
};

const result = await client.executeComplexQuery(query);
console.log(`Found ${result.object_instances.length} matching people`);
```

### Batch Operations

```typescript
import { processObjectInstancesBatch, createMultipleObjectInstances } from 'grizabella-typescript-api';

// Create multiple objects at once
const people = await createMultipleObjectInstances(client, 'Person', [
  { name: 'Alice', age: 28 },
  { name: 'Bob', age: 32 },
  { name: 'Charlie', age: 25 },
]);

// Process objects in batches
const results = await processObjectInstancesBatch(
  client,
  people,
  async (person) => {
    // Custom processing logic
    return await client.findObjects('Person', { name: person.properties.name });
  },
  { batchSize: 10 }
);
```

### Performance Monitoring

```typescript
import { timeAsync, createMemoryReport, PerformanceMonitor } from 'grizabella-typescript-api';

// Time async operations
const result = await timeAsync(
  () => client.findObjects('Person', { age: { '>': 25 } }),
  'findAdults'
);

// Create memory usage reports
const memoryReport = createMemoryReport();

// Use performance monitor
const monitor = new PerformanceMonitor();
monitor.start('complexQuery');

const result = await client.executeComplexQuery(complexQuery);
const metrics = monitor.end('complexQuery');

console.log(`Query took ${metrics.duration}ms`);
```

## 🛠️ Development

### Building from Source

```bash
# Clone the repository
git clone https://github.com/your-org/grizabella.git
cd grizabella/typescript

# Install dependencies
npm install

# Build the project
npm run build

# Run tests
npm run test

# Run linting
npm run lint
```

### Project Structure

```
typescript/
├── src/
│   ├── index.ts           # Main entry point
│   ├── client/
│   │   ├── GrizabellaClient.ts    # Main client class
│   │   ├── MCPClient.ts           # MCP communication layer
│   │   └── errors.ts              # Error handling
│   ├── types/
│   │   ├── core.ts                # Core type definitions
│   │   ├── embedding.ts           # Embedding types
│   │   ├── query.ts               # Query types
│   │   └── enums.ts               # Enumeration types
│   └── utils/
│       ├── validation.ts          # Validation utilities
│       ├── conversion.ts          # Type conversion utilities
│       ├── helpers.ts             # Helper functions
│       └── dev.ts                 # Developer experience utilities
├── dist/                          # Compiled JavaScript output
├── examples/                      # Usage examples
├── docs/                          # API documentation
└── tests/                         # Test files
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and add tests
4. Run the test suite: `npm test`
5. Ensure code passes linting: `npm run lint`
6. Commit your changes: `git commit -am 'Add my feature'`
7. Push to the branch: `git push origin feature/my-feature`
8. Submit a pull request

## 📖 Documentation

### 🚀 **Getting Started**
- [**Quick Start Guide**](./docs/quickstart.md) ⭐ *New comprehensive tutorial*
- [Examples Guide](./docs/examples-guide.md) 📚 *Overview of all examples*
- [Setup Guide](./docs/setup-guide.md) 🔧 *Installation and configuration*

### 📚 **Reference Documentation**
- [API Reference](./docs/api-reference.md) 📖 *Complete API documentation*
- [Best Practices](./docs/best-practices.md) ✨ *Production-ready patterns*
- [Error Handling](./docs/error-handling.md) 🛡️ *Comprehensive error management*

### 🔄 **Migration & Advanced**
- [Migration Guide](./docs/migration-guide.md) 🔄 *Python to TypeScript*
- [Troubleshooting](./docs/troubleshooting.md) 🔧 *Common issues and solutions*

### 💻 **Examples**
- [Working Basic Example](./examples/basic-usage-working.ts) ✅ *Compilable and tested*
- [Examples Index](./examples/) 📁 *All example files*

## 🤝 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/grizabella/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/grizabella/discussions)
- **Documentation**: [Full Documentation](https://grizabella.dev)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/)
- Inspired by modern graph database patterns
- Thanks to the open-source community

---

**Made with ❤️ by the Grizabella Team**