# Grizabella TypeScript API - Quick Start Guide

Welcome to the Grizabella TypeScript API! This guide will help you get started quickly with the knowledge graph database that supports multi-database operations through MCP (Model Context Protocol) communication.

## 🚀 What You'll Learn

- How to install and set up the Grizabella TypeScript API
- Basic connection patterns
- Creating schemas and data
- Performing queries and searches
- Best practices for common operations

## 📋 Prerequisites

Before you begin, ensure you have:

- **Node.js**: 18.0.0 or higher
- **TypeScript**: 5.0.0 or higher  
- **Grizabella MCP Server**: A running instance of the Grizabella server

## 📦 Installation

### Install the Package

```bash
npm install grizabella-typescript-api
```

### Install Development Dependencies

```bash
npm install -D typescript @types/node ts-node
```

## 🔧 Basic Setup

### 1. Create Your First Connection

The Grizabella TypeScript API provides two main patterns for connection management:

#### Context Manager Pattern (Recommended)

```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';

async function basicExample() {
  // Automatic connection and cleanup
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'my-knowledge-base',
    createIfNotExists: true,
    debug: true,
  });

  console.log('Connected successfully!');
  // Client automatically disconnects when scope ends
}
```

#### Manual Connection Management

```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';

async function manualExample() {
  const client = new GrizabellaClient({
    dbNameOrPath: 'my-knowledge-base',
    createIfNotExists: true,
    debug: true,
  });

  await client.connect();
  console.log('Connected successfully!');
  
  // ... your operations here ...
  
  await client.close();
  console.log('Disconnected');
}
```

## 🏗️ Creating Your Schema

### Define Object Types

Object types are like tables in traditional databases - they define the structure of your data:

```typescript
import { PropertyDataType } from 'grizabella-typescript-api';

async function createPersonSchema(client: GrizabellaClient) {
  await client.createObjectType({
    name: 'Person',
    description: 'A person in the knowledge base',
    properties: [
      {
        name: 'name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_indexed: true,
        description: 'The person\'s full name',
      },
      {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'Unique email address',
      },
      {
        name: 'age',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
        description: 'Age in years',
      },
      {
        name: 'department',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        is_indexed: true,
        description: 'Department or team',
      },
    ],
  });
  
  console.log('✅ Person schema created');
}
```

### Define Relation Types

Relations define how objects are connected to each other:

```typescript
async function createWorkRelationSchema(client: GrizabellaClient) {
  await client.createRelationType({
    name: 'WORKS_FOR',
    description: 'Person works for a company',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Company'],
    properties: [
      {
        name: 'start_date',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'When the person started working',
      },
      {
        name: 'position',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'Job position or title',
      },
    ],
  });
  
  console.log('✅ WORKS_FOR relation created');
}
```

## 💾 Working with Data

### Create Objects

```typescript
import { Decimal } from 'grizabella-typescript-api';

async function createPeople(client: GrizabellaClient) {
  const people = [
    {
      id: 'person-1',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Alice Johnson',
        email: 'alice@company.com',
        age: 30,
        department: 'Engineering',
      },
    },
    {
      id: 'person-2',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Bob Smith',
        email: 'bob@company.com',
        age: 28,
        department: 'Marketing',
      },
    },
  ];

  for (const person of people) {
    await client.upsertObject(person);
  }

  console.log('✅ Created people');
}
```

### Create Relations

```typescript
async function createRelations(client: GrizabellaClient) {
  // First create a company
  await client.upsertObject({
    id: 'company-1',
    object_type_name: 'Company',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      name: 'Tech Corp',
      industry: 'Technology',
    },
  });

  // Then create relations
  const relations = [
    {
      id: 'relation-1',
      relation_type_name: 'WORKS_FOR',
      source_object_instance_id: 'person-1',
      target_object_instance_id: 'company-1',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        start_date: new Date('2022-01-15'),
        position: 'Senior Developer',
      },
    },
    {
      id: 'relation-2',
      relation_type_name: 'WORKS_FOR',
      source_object_instance_id: 'person-2',
      target_object_instance_id: 'company-1',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        start_date: new Date('2023-03-01'),
        position: 'Marketing Manager',
      },
    },
  ];

  for (const relation of relations) {
    await client.addRelation(relation);
  }

  console.log('✅ Created relations');
}
```

## 🔍 Querying Data

### Basic Object Queries

```typescript
async function queryPeople(client: GrizabellaClient) {
  // Get all people
  const allPeople = await client.findObjects('Person');
  console.log(`Found ${allPeople.length} people`);

  // Find people by department
  const engineers = await client.findObjects('Person', {
    department: 'Engineering'
  });
  console.log(`Found ${engineers.length} engineers`);

  // Find people by age range
  const youngPeople = await client.findObjects('Person', {
    age: { '>=': 25, '<=': 35 }
  });
  console.log(`Found ${youngPeople.length} young professionals`);

  // Get a specific person by ID
  const alice = await client.getObjectById('person-1', 'Person');
  if (alice) {
    console.log(`Found: ${alice.properties.name}`);
  }
}
```

### Query Relations

```typescript
async function queryRelations(client: GrizabellaClient) {
  // Get Alice's outgoing relations (who she works for)
  const aliceRelations = await client.getOutgoingRelations('person-1', 'Person', 'WORKS_FOR');
  console.log(`Alice works for ${aliceRelations.length} companies`);

  // Get all people who work for Tech Corp
  const companyEmployees = await client.getIncomingRelations('company-1', 'Company', 'WORKS_FOR');
  console.log(`Tech Corp has ${companyEmployees.length} employees`);
}
```

## 🛡️ Error Handling

The Grizabella API provides comprehensive error handling with specific error types:

```typescript
import { 
  GrizabellaError, 
  ConnectionError, 
  ValidationError, 
  QueryError 
} from 'grizabella-typescript-api';

async function robustExample() {
  try {
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: 'my-database',
      createIfNotExists: true,
    });

    // Your operations here
    const people = await client.findObjects('Person');
    
  } catch (error) {
    if (error instanceof ConnectionError) {
      console.error('Connection failed:', error.message);
      // Handle connection issues
    } else if (error instanceof ValidationError) {
      console.error('Data validation failed:', error.message);
      // Handle validation issues
    } else if (error instanceof QueryError) {
      console.error('Query failed:', error.message);
      // Handle query issues
    } else if (error instanceof GrizabellaError) {
      console.error('Grizabella error:', error.message);
      // Handle other Grizabella-specific errors
    } else {
      console.error('Unexpected error:', error);
      // Handle generic errors
    }
  }
}
```

## 🎯 Complete Example

Here's a complete working example that ties everything together:

```typescript
import { GrizabellaClient, PropertyDataType, Decimal } from 'grizabella-typescript-api';

async function completeExample() {
  console.log('🚀 Starting Grizabella TypeScript API Example');

  try {
    // 1. Connect to database
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: 'quickstart-example',
      createIfNotExists: true,
      debug: true,
    });

    console.log('✅ Connected to database');

    // 2. Create schema
    await client.createObjectType({
      name: 'Person',
      description: 'A person in the system',
      properties: [
        {
          name: 'name',
          data_type: PropertyDataType.TEXT,
          is_nullable: false,
          is_indexed: true,
        },
        {
          name: 'email',
          data_type: PropertyDataType.TEXT,
          is_nullable: false,
          is_unique: true,
        },
        {
          name: 'age',
          data_type: PropertyDataType.INTEGER,
          is_nullable: true,
        },
      ],
    });

    console.log('✅ Created Person schema');

    // 3. Add data
    await client.upsertObject({
      id: 'person-1',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'John Doe',
        email: 'john@example.com',
        age: 30,
      },
    });

    console.log('✅ Created person');

    // 4. Query data
    const people = await client.findObjects('Person');
    console.log(`✅ Found ${people.length} people`);

    people.forEach(person => {
      console.log(`  - ${person.properties.name} (${person.properties.email})`);
    });

    console.log('🎉 Example completed successfully!');

  } catch (error) {
    console.error('❌ Example failed:', error);
  }
}

// Run the example
completeExample();
```

## 📚 Next Steps

Now that you've mastered the basics, explore these topics:

- **Advanced Queries**: Complex graph traversals and filtering
- **Semantic Search**: Vector embeddings and similarity search
- **Performance Optimization**: Batch operations and indexing
- **Error Handling**: Advanced error patterns and recovery
- **Production Deployment**: Connection pooling and monitoring

## 🔗 Additional Resources

- [API Reference](./api-reference.md) - Complete API documentation
- [Best Practices](./best-practices.md) - Production-ready patterns
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions
- [Examples](../examples/) - Comprehensive code examples

## 💡 Tips for Success

1. **Use Context Managers**: Prefer `await using` for automatic resource cleanup
2. **Validate Data**: Always validate data before inserting to catch errors early
3. **Handle Errors**: Use specific error types for better error handling
4. **Index Properties**: Add indexes to frequently queried properties for better performance
5. **Use Decimal**: Always use `Decimal` for weight values to ensure precision

Happy coding with Grizabella! 🎊