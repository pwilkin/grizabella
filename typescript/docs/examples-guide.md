# Grizabella TypeScript API - Examples Guide

This guide provides a comprehensive overview of all available examples, organized by skill level and functionality. Each example demonstrates specific aspects of the Grizabella TypeScript API with working, compilable code.

## 🚀 Quick Start

If you're new to Grizabella, start with these resources:

1. **[Quick Start Guide](./quickstart.md)** - Step-by-step tutorial for beginners
2. **[Working Basic Example](../examples/basic-usage-working.ts)** - Compilable basic usage example
3. **[Setup Guide](./setup-guide.md)** - Installation and configuration

## 📚 Examples by Category

### 🟢 Beginner Examples

Perfect for getting started with the basics of Grizabella.

#### 1. Basic Usage (Working)
**File**: [`examples/basic-usage-working.ts`](../examples/basic-usage-working.ts)

**What you'll learn**:
- Connection management (context manager vs manual)
- Creating object types and instances
- Basic CRUD operations
- Simple relationship queries
- Error handling fundamentals

**Run it**:
```bash
npx ts-node examples/basic-usage-working.ts
```

**Key concepts demonstrated**:
- `GrizabellaClient.connect()` for automatic connection management
- `createObjectType()` for schema definition
- `upsertObject()` for data creation
- `findObjects()` for basic querying
- `addRelation()` for relationship creation

---

### 🟡 Intermediate Examples

Build on the basics with more complex scenarios and patterns.

#### 2. Schema Management
**File**: [`examples/schema-management.ts`](../examples/schema-management.ts) ⚠️ *Needs updates*

**What you'll learn**:
- Complex object type definitions
- Relation type creation with properties
- Schema validation patterns
- Helper functions for schema creation

**Status**: ⚠️ **Currently has compilation errors** - Use the working example above for now

#### 3. Data Operations
**File**: [`examples/data-operations.ts`](../examples/data-operations.ts) ⚠️ *Needs updates*

**What you'll learn**:
- Batch operations
- Data validation
- Performance monitoring
- Advanced data manipulation

**Status**: ⚠️ **Currently has compilation errors** - Refer to quickstart guide for working patterns

#### 4. Query and Search
**File**: [`examples/query-search.ts`](../examples/query-search.ts) ⚠️ *Needs updates*

**What you'll learn**:
- Advanced filtering
- Relationship queries
- Complex graph traversals
- Semantic search with embeddings

**Status**: ⚠️ **Currently has compilation errors** - Use basic patterns from quickstart

---

### 🔴 Advanced Examples

For production-ready patterns and complex use cases.

#### 5. Advanced Patterns
**File**: [`examples/advanced-patterns.ts`](../examples/advanced-patterns.ts) ⚠️ *Needs updates*

**What you'll learn**:
- Error boundaries and retry logic
- Connection pooling
- Performance optimization
- Production deployment patterns

**Status**: ⚠️ **Currently has compilation errors** - See best practices guide

---

## 🛠️ Working with the Examples

### Prerequisites

Make sure you have:
- Node.js 18+ and TypeScript 5.0+
- Grizabella MCP server running
- All dependencies installed: `npm install`

### Running Examples

#### Method 1: Direct Execution
```bash
# Run the working basic example
npx ts-node examples/basic-usage-working.ts
```

#### Method 2: Using the Examples Runner
```bash
# List all available examples
npx ts-node examples/index.ts list

# Run quick start examples
npx ts-node examples/index.ts quickstart

# Run a specific category
npx ts-node examples/index.ts run "Basic Usage"
```

### Compilation Issues

Some examples currently have compilation errors due to API changes. Here's how to work around them:

#### Use the Working Example
Start with [`examples/basic-usage-working.ts`](../examples/basic-usage-working.ts) - this compiles successfully and demonstrates the core API.

#### Test Compilation
```bash
# Test if an example compiles
npx tsc --noEmit --skipLibCheck examples/basic-usage-working.ts
```

#### Common Issues and Solutions

1. **Import Errors**: Use `../src/index` for development, or install the package and use the published name
2. **Type Errors**: Check the actual function signatures in the source code
3. **Missing Exports**: Some utilities may not be exported from the main index

---

## 📖 Learning Path

### Phase 1: Get Started (Day 1)
1. Read the [Quick Start Guide](./quickstart.md)
2. Run the [Working Basic Example](../examples/basic-usage-working.ts)
3. Experiment with creating your own object types

### Phase 2: Build Skills (Day 2-3)
1. Study the [API Reference](./api-reference.md)
2. Review the [Best Practices Guide](./best-practices.md)
3. Try modifying the working example with different data types

### Phase 3: Advanced Topics (Day 4-5)
1. Read about [Error Handling](./error-handling.md)
2. Study [Performance Optimization](./performance-optimization.md)
3. Learn about [Complex Queries](./api-reference.md#query-and-search)

### Phase 4: Production Ready (Day 6-7)
1. Review [Troubleshooting](./troubleshooting.md)
2. Study [Migration Guide](./migration-guide.md) if coming from Python
3. Set up monitoring and logging

---

## 🔧 Example Templates

### Basic Object Creation Template

```typescript
import { GrizabellaClient, PropertyDataType, Decimal } from 'grizabella-typescript-api';

async function createObjectExample() {
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'my-database',
    createIfNotExists: true,
  });

  // Create object type
  await client.createObjectType({
    name: 'MyObject',
    description: 'My custom object type',
    properties: [
      {
        name: 'name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_indexed: true,
      },
      {
        name: 'value',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
      },
    ],
  });

  // Create instance
  await client.upsertObject({
    id: 'my-object-1',
    object_type_name: 'MyObject',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      name: 'Test Object',
      value: 42,
    },
  });

  // Query
  const results = await client.findObjects('MyObject', {
    value: { '>': 30 }
  });

  console.log(`Found ${results.length} objects`);
}
```

### Error Handling Template

```typescript
import { 
  GrizabellaClient, 
  ConnectionError, 
  ValidationError, 
  QueryError 
} from 'grizabella-typescript-api';

async function robustOperation() {
  try {
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: 'my-database',
      createIfNotExists: true,
    });

    // Your operations here
    const results = await client.findObjects('MyObject');
    
  } catch (error) {
    if (error instanceof ConnectionError) {
      console.error('Connection failed:', error.message);
    } else if (error instanceof ValidationError) {
      console.error('Validation failed:', error.message);
    } else if (error instanceof QueryError) {
      console.error('Query failed:', error.message);
    } else {
      console.error('Unexpected error:', error);
    }
  }
}
```

---

## 🚨 Current Status

### ✅ Working
- [Quick Start Guide](./quickstart.md) - Complete beginner tutorial
- [Basic Usage Working Example](../examples/basic-usage-working.ts) - Compilable and tested
- Core API functionality in `GrizabellaClient`
- Error handling framework
- Basic CRUD operations

### ⚠️ Needs Updates
- Most example files have compilation errors due to API changes
- Some utility functions have different signatures than expected
- Advanced examples need updating to match current implementation

### 🔄 In Progress
- Fixing compilation errors in existing examples
- Updating API reference documentation
- Creating more working examples for intermediate concepts

---

## 🤝 Contributing

Found an issue with an example? Here's how to help:

1. **Check the Working Example First**: Make sure your code follows the patterns in `basic-usage-working.ts`
2. **Test Compilation**: Run `npx tsc --noEmit --skipLibCheck your-example.ts`
3. **Update Documentation**: If you fix an example, update this guide
4. **Report Issues**: Open an issue with details about compilation errors

---

## 📞 Getting Help

If you're stuck:

1. **Start with the Quick Start Guide** - It has working, tested code
2. **Check the API Reference** - Verify function signatures
3. **Review Error Handling** - Many issues are related to proper error handling
4. **Look at Test Files** - The E2E tests show working patterns

**Resources**:
- [Troubleshooting Guide](./troubleshooting.md)
- [API Reference](./api-reference.md)
- [Best Practices](./best-practices.md)

---

*Last updated: 2024-10-20*
*Status: Active development - examples being updated to match current API*