# Troubleshooting Guide

Comprehensive guide to common issues and their solutions when using the Grizabella TypeScript API.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Connection Problems](#connection-problems)
- [Schema Issues](#schema-issues)
- [Data Operation Errors](#data-operation-errors)
- [Performance Issues](#performance-issues)
- [TypeScript Errors](#typescript-errors)
- [Runtime Errors](#runtime-errors)
- [Debugging Techniques](#debugging-techniques)
- [Getting Help](#getting-help)

## Installation Issues

### Package Installation Fails

**Problem:**
```bash
npm install grizabella-typescript-api
# Error: EACCES: permission denied
```

**Solutions:**

1. **Permission Issues:**
   ```bash
   # Use sudo (not recommended)
   sudo npm install grizabella-typescript-api

   # Or fix npm permissions
   sudo chown -R $(whoami) ~/.npm
   ```

2. **Network Issues:**
   ```bash
   # Try with different registry
   npm install grizabella-typescript-api --registry https://registry.npmjs.org/

   # Or use yarn
   yarn add grizabella-typescript-api
   ```

3. **Node Version Issues:**
   ```bash
   # Check Node version
   node --version  # Should be 18.0.0 or higher

   # Update Node if necessary
   nvm install 20
   nvm use 20
   ```

### TypeScript Compilation Errors

**Problem:**
```bash
npm run build
# error TS2307: Cannot find module 'grizabella-typescript-api'
```

**Solutions:**

1. **Missing Type Definitions:**
   ```bash
   # Install types if available
   npm install @types/grizabella-typescript-api --save-dev

   # Or check if package.json has types field
   npm info grizabella-typescript-api
   ```

2. **Module Resolution Issues:**
   ```json
   // tsconfig.json
   {
     "compilerOptions": {
       "moduleResolution": "node",
       "esModuleInterop": true,
       "allowSyntheticDefaultImports": true
     }
   }
   ```

3. **Clean Install:**
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   npm run build
   ```

### Import Errors

**Problem:**
```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';
// Module not found
```

**Solutions:**

1. **Package Not Installed:**
   ```bash
   npm install grizabella-typescript-api
   ```

2. **Case Sensitivity:**
   ```typescript
   // Correct import (check exact case)
   import { GrizabellaClient } from 'grizabella-typescript-api';
   ```

3. **Module Resolution:**
   ```json
   // tsconfig.json
   {
     "compilerOptions": {
       "baseUrl": ".",
       "paths": {
         "*": ["node_modules/*"]
       }
     }
   }
   ```

## Connection Problems

### Connection Refused

**Problem:**
```typescript
await client.connect();
// Error: Connection refused
```

**Solutions:**

1. **Server Not Running:**
   ```bash
   # Start Grizabella MCP server
   python -m grizabella.mcp.server --port 8000 --host localhost
   ```

2. **Wrong Server URL:**
   ```typescript
   // Check server URL
   const client = new GrizabellaClient({
     serverUrl: 'http://localhost:8000/mcp', // Correct
     // serverUrl: 'http://localhost:8000',  // Wrong - missing /mcp
   });
   ```

3. **Firewall Blocking:**
   ```bash
   # Check if port is open
   curl http://localhost:8000/mcp

   # On Windows
   Test-NetConnection -ComputerName localhost -Port 8000

   # On Linux/Mac
   nc -zv localhost 8000
   ```

### Connection Timeout

**Problem:**
```typescript
await client.connect();
// Error: Connection timeout
```

**Solutions:**

1. **Increase Timeout:**
   ```typescript
   const client = new GrizabellaClient({
     serverUrl: 'http://localhost:8000/mcp',
     timeout: 60000, // 60 seconds
     requestTimeout: 60000,
   });
   ```

2. **Check Server Health:**
   ```bash
   # Test server response time
   curl -w "@curl-format.txt" http://localhost:8000/mcp
   ```

3. **Network Issues:**
   ```bash
   # Check network connectivity
   ping localhost

   # Test with different network interface
   serverUrl: 'http://127.0.0.1:8000/mcp'
   ```

### Authentication Issues

**Problem:**
```typescript
await client.connect();
// Error: Authentication failed
```

**Solutions:**

1. **Check Credentials:**
   ```typescript
   const client = new GrizabellaClient({
     serverUrl: 'http://localhost:8000/mcp',
     // Add authentication if required by your MCP server
   });
   ```

2. **Server Configuration:**
   ```python
   # MCP server configuration
   server = GrizabellaMCPServer(
       db_path="my-database",
       host="localhost",
       port=8000,
       # auth_required=False  # Check auth settings
   )
   ```

## Schema Issues

### Invalid Schema Definition

**Problem:**
```typescript
await client.createObjectType({
  name: 'User',
  properties: [
    {
      name: 'email',
      data_type: PropertyDataType.TEXT,
      is_unique: true,
      // Missing required is_nullable field
    }
  ]
});
// Error: Invalid schema
```

**Solutions:**

1. **Validate Schema:**
   ```typescript
   import { validateObjectTypeDefinition } from 'grizabella-typescript-api';

   const schema = { /* your schema */ };
   const validation = validateObjectTypeDefinition(schema);

   if (!validation.isValid) {
     console.error('Schema validation errors:', validation.errors);
     // Fix errors before creating
   }
   ```

2. **Complete Required Fields:**
   ```typescript
   // Correct schema
   const userSchema: ObjectTypeDefinition = {
     name: 'User',
     description: 'A user account',
     properties: [
       {
         name: 'email',
         data_type: PropertyDataType.TEXT,
         is_nullable: false, // Required field
         is_unique: true,
         description: 'User email address',
       }
     ]
   };
   ```

### Schema Already Exists

**Problem:**
```typescript
await client.createObjectType(userSchema);
// Error: Object type 'User' already exists
```

**Solutions:**

1. **Check Existing Schema:**
   ```typescript
   const existing = await client.getObjectType('User');
   if (existing) {
     console.log('User type already exists:', existing);
     return; // Skip creation
   }
   ```

2. **Use createIfNotExists Pattern:**
   ```typescript
   async function ensureObjectType(client: GrizabellaClient, schema: ObjectTypeDefinition) {
     try {
       await client.createObjectType(schema);
       console.log(`✅ Created object type: ${schema.name}`);
     } catch (error) {
       if (error.message?.includes('already exists')) {
         console.log(`ℹ️ Object type ${schema.name} already exists`);
       } else {
         throw error;
       }
     }
   }
   ```

### Schema Compatibility Issues

**Problem:**
```typescript
await client.upsertObject(userData);
// Error: Property 'age' not found in schema
```

**Solutions:**

1. **Check Object Type Definition:**
   ```typescript
   const userType = await client.getObjectType('User');
   console.log('User properties:', userType?.properties.map(p => p.name));
   ```

2. **Validate Object Against Schema:**
   ```typescript
   import { validateObjectInstance } from 'grizabella-typescript-api';

   const validation = validateObjectInstance(userData, userType!);
   if (!validation.isValid) {
     console.error('Validation errors:', validation.errors);
   }
   ```

## Data Operation Errors

### Object Not Found

**Problem:**
```typescript
const user = await client.getObjectById('user-123', 'User');
// Returns null
```

**Solutions:**

1. **Check Object ID:**
   ```typescript
   // Ensure ID format is correct
   const userId = 'user-123'; // Should match actual ID

   // List existing objects
   const users = await client.findObjects('User');
   console.log('Existing user IDs:', users.map(u => u.id));
   ```

2. **Check Object Type:**
   ```typescript
   // Ensure object type name matches
   const user = await client.getObjectById('user-123', 'User'); // Case sensitive
   ```

3. **Debug Query:**
   ```typescript
   const allUsers = await client.findObjects('User');
   const found = allUsers.find(u => u.id === 'user-123');
   console.log('User found in list:', !!found);
   ```

### Unique Constraint Violation

**Problem:**
```typescript
await client.upsertObject({
  id: 'user-1',
  object_type_name: 'User',
  properties: {
    email: 'duplicate@example.com', // Already exists
  }
});
// Error: Unique constraint violation
```

**Solutions:**

1. **Check Existing Values:**
   ```typescript
   const existing = await client.findObjects('User', {
     email: 'duplicate@example.com'
   });

   if (existing.length > 0) {
     console.log('Email already exists for user:', existing[0].id);
     // Handle duplicate case
   }
   ```

2. **Use Update Pattern:**
   ```typescript
   async function upsertUserByEmail(client: GrizabellaClient, userData: any) {
     const existing = await client.findObjects('User', {
       email: userData.email
     }, 1);

     if (existing.length > 0) {
       // Update existing user
       return await client.upsertObject({
         ...existing[0],
         properties: {
           ...existing[0].properties,
           ...userData,
         },
       });
     } else {
       // Create new user
       return await client.upsertObject({
         id: generateUserId(),
         object_type_name: 'User',
         weight: new Decimal('1.0'),
         upsert_date: new Date(),
         properties: userData,
       });
     }
   }
   ```

### Invalid Data Types

**Problem:**
```typescript
await client.upsertObject({
  properties: {
    age: 'twenty-five', // Should be number
  }
});
// Error: Invalid data type
```

**Solutions:**

1. **Type Validation:**
   ```typescript
   function validateUserData(data: any): UserData {
     return {
       name: String(data.name),
       email: String(data.email),
       age: data.age ? Number(data.age) : undefined,
       department: data.department ? String(data.department) : undefined,
     };
   }

   const validatedData = validateUserData(rawUserData);
   await client.upsertObject(createObjectInstance('User', validatedData));
   ```

2. **Schema-Based Validation:**
   ```typescript
   import { validateObjectInstance } from 'grizabella-typescript-api';

   const userObject = createObjectInstance('User', userData);
   const userType = await client.getObjectType('User');
   const validation = validateObjectInstance(userObject, userType!);

   if (!validation.isValid) {
     throw new Error(`Validation failed: ${validation.errors.join(', ')}`);
   }
   ```

## Performance Issues

### Slow Queries

**Problem:**
```typescript
const users = await client.findObjects('User', { department: 'Engineering' });
// Takes more than 5 seconds
```

**Solutions:**

1. **Add Indexes:**
   ```typescript
   // Ensure property is indexed in schema
   const userSchema: ObjectTypeDefinition = {
     name: 'User',
     properties: [
       {
         name: 'department',
         data_type: PropertyDataType.TEXT,
         is_indexed: true, // Add index for better performance
       }
     ]
   };
   ```

2. **Use More Specific Filters:**
   ```typescript
   // Instead of broad queries
   const users = await client.findObjects('User', {
     department: 'Engineering',
     is_active: true, // Add more specific filters
   }, 100); // Limit results
   ```

3. **Profile Query Performance:**
   ```typescript
   import { timeAsync } from 'grizabella-typescript-api';

   const result = await timeAsync(
     () => client.findObjects('User', { department: 'Engineering' }),
     'findEngineers'
   );

   console.log(`Query took ${result.duration}ms for ${result.result.length} results`);
   ```

### Memory Issues

**Problem:**
```typescript
const allUsers = await client.findObjects('User');
// Memory usage spikes, application crashes
```

**Solutions:**

1. **Use Pagination:**
   ```typescript
   async function getUsersInBatches(client: GrizabellaClient, batchSize = 100) {
     const allUsers: any[] = [];
     let offset = 0;
     let hasMore = true;

     while (hasMore) {
       // Note: This is a conceptual example
       // Actual implementation depends on your database's pagination support
       const batch = await client.findObjects('User', {}, batchSize, offset);
       allUsers.push(...batch);
       hasMore = batch.length === batchSize;
       offset += batchSize;
     }

     return allUsers;
   }
   ```

2. **Stream Processing:**
   ```typescript
   async function processUsersInStream(client: GrizabellaClient) {
     // Process users one by one instead of loading all into memory
     const userIds = await getUserIds(); // Get just IDs

     for (const userId of userIds) {
       const user = await client.getObjectById(userId, 'User');
       if (user) {
         await processUser(user); // Process individual user
       }
     }
   }
   ```

3. **Increase Memory Limits:**
   ```bash
   # Increase Node.js memory limit
   node --max-old-space-size=4096 dist/index.js

   # Or set in package.json
   {
     "scripts": {
       "start": "node --max-old-space-size=4096 dist/index.js"
     }
   }
   ```

### Connection Pooling Issues

**Problem:**
```typescript
// Multiple concurrent connections causing issues
for (let i = 0; i < 100; i++) {
  await client.connect(); // Creates new connection each time
}
```

**Solutions:**

1. **Reuse Client Instances:**
   ```typescript
   // Create client once and reuse
   const client = await GrizabellaClient.connect(config);

   // Use the same client for multiple operations
   const promises = Array(100).fill(null).map((_, i) =>
     client.getObjectById(`user-${i}`, 'User')
   );

   const results = await Promise.all(promises);
   ```

2. **Implement Connection Pooling:**
   ```typescript
   class DatabaseConnectionPool {
     private clients: GrizabellaClient[] = [];
     private maxConnections = 10;

     async getClient(): Promise<GrizabellaClient> {
       if (this.clients.length > 0) {
         return this.clients.pop()!;
       }

       if (this.clients.length < this.maxConnections) {
         const client = await GrizabellaClient.connect(config);
         return client;
       }

       // Wait for available client
       return new Promise((resolve) => {
         // Implementation for waiting queue
       });
     }

     releaseClient(client: GrizabellaClient): void {
       this.clients.push(client);
     }
   }
   ```

## TypeScript Errors

### Type Import Issues

**Problem:**
```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';
// error TS7016: Could not find a declaration file for module
```

**Solutions:**

1. **Check Installation:**
   ```bash
   npm list grizabella-typescript-api
   ls node_modules/grizabella-typescript-api/dist/
   ```

2. **Manual Type Declaration:**
   ```typescript
   // types/grizabella.d.ts
   declare module 'grizabella-typescript-api' {
     export class GrizabellaClient {
       // Add method declarations as needed
     }
   }
   ```

3. **Update tsconfig.json:**
   ```json
   {
     "compilerOptions": {
       "skipLibCheck": true,
       "typeRoots": ["node_modules/@types", "./types"]
     }
   }
   ```

### Strict Type Checking

**Problem:**
```typescript
const result = await client.findObjects('User');
// error TS2322: Type 'ObjectInstance[]' is not assignable to 'User[]'
```

**Solutions:**

1. **Type Assertion:**
   ```typescript
   const users = await client.findObjects('User') as User[];
   ```

2. **Type Guards:**
   ```typescript
   function isUser(obj: any): obj is User {
     return obj &&
            typeof obj.id === 'string' &&
            typeof obj.properties.name === 'string';
   }

   const results = await client.findObjects('User');
   const users = results.filter(isUser);
   ```

3. **Repository Pattern:**
   ```typescript
   class UserRepository {
     constructor(private client: GrizabellaClient) {}

     async findAll(): Promise<User[]> {
       const results = await this.client.findObjects('User');
       return results as User[];
     }
   }
   ```

### Interface Mismatches

**Problem:**
```typescript
interface User {
  id: string;
  name: string;
}

const user = await client.upsertObject({
  // Error: Missing required properties
  id: 'user-1',
  object_type_name: 'User',
  properties: { name: 'John' }
});
```

**Solutions:**

1. **Complete Object Structure:**
   ```typescript
   const user = await client.upsertObject({
     id: 'user-1',
     object_type_name: 'User',
     weight: new Decimal('1.0'), // Required
     upsert_date: new Date(),     // Required
     properties: {
       name: 'John',
       email: 'john@example.com', // Other required properties
     }
   });
   ```

2. **Helper Functions:**
   ```typescript
   function createUserObject(data: Partial<User>): ObjectInstance {
     return {
       id: data.id || generateUserId(),
       object_type_name: 'User',
       weight: new Decimal('1.0'),
       upsert_date: new Date(),
       properties: data,
     };
   }

   const user = await client.upsertObject(createUserObject({
     name: 'John',
     email: 'john@example.com'
   }));
   ```

## Runtime Errors

### Async/Await Issues

**Problem:**
```typescript
async function getUser() {
  const user = client.getObjectById('user-1', 'User'); // Missing await
  return user; // Promise<User | null> instead of User | null
}
```

**Solutions:**

1. **Proper Await Usage:**
   ```typescript
   async function getUser(userId: string): Promise<User | null> {
     const user = await client.getObjectById(userId, 'User');
     return user;
   }
   ```

2. **Error Handling in Async Functions:**
   ```typescript
   async function getUser(userId: string): Promise<User | null> {
     try {
       return await client.getObjectById(userId, 'User');
     } catch (error) {
       console.error('Failed to get user:', error);
       return null;
     }
   }
   ```

### Promise Rejection

**Problem:**
```typescript
const result = await client.findObjects('NonExistentType');
// Unhandled promise rejection
```

**Solutions:**

1. **Try-Catch in Async Functions:**
   ```typescript
   async function safeFindObjects(typeName: string) {
     try {
       return await client.findObjects(typeName);
     } catch (error) {
       console.error(`Failed to find objects of type ${typeName}:`, error);
       return []; // Return empty array as fallback
     }
   }
   ```

2. **Global Error Handlers:**
   ```typescript
   process.on('unhandledRejection', (reason, promise) => {
     console.error('Unhandled Rejection at:', promise, 'reason:', reason);
     // Send to monitoring service
   });

   process.on('uncaughtException', (error) => {
     console.error('Uncaught Exception:', error);
     // Graceful shutdown
     process.exit(1);
   });
   ```

## Debugging Techniques

### Enable Debug Logging

```typescript
const client = new GrizabellaClient({
  dbNameOrPath: 'my-db',
  serverUrl: 'http://localhost:8000/mcp',
  debug: true, // Enable debug logging
});

// Or set globally
setGlobalLogger(new ConsoleDebugLogger());
```

### Connection Debugging

```typescript
const client = new GrizabellaClient({
  serverUrl: 'http://localhost:8000/mcp',
  timeout: 5000,
  debug: true,
});

try {
  await client.connect();
} catch (error) {
  console.log('Connection error details:', {
    message: error.message,
    name: error.name,
    stack: error.stack,
  });
}
```

### Query Debugging

```typescript
import { timeAsync } from 'grizabella-typescript-api';

// Time and log queries
async function debugQuery() {
  const result = await timeAsync(
    () => client.findObjects('User', { department: 'Engineering' }),
    'findEngineers'
  );

  console.log(`Query took ${result.duration}ms`);
  console.log(`Found ${result.result.length} users`);

  if (result.duration > 1000) {
    console.warn('Query is slow, consider optimization');
  }
}
```

### Memory Debugging

```typescript
import { createMemoryReport } from 'grizabella-typescript-api';

function logMemoryUsage(label: string) {
  const report = createMemoryReport();
  console.log(`${label} - Memory:`, {
    heapUsed: Math.round(report.heapUsed / 1024 / 1024) + 'MB',
    heapTotal: Math.round(report.heapTotal / 1024 / 1024) + 'MB',
    external: Math.round(report.external / 1024 / 1024) + 'MB',
  });
}

// Usage
logMemoryUsage('Before operation');
await performMemoryIntensiveOperation();
logMemoryUsage('After operation');
```

### Network Debugging

```typescript
const client = new GrizabellaClient({
  serverUrl: 'http://localhost:8000/mcp',
  debug: true,
  timeout: 10000,
});

// Enable Node.js network debugging
process.env.NODE_DEBUG = 'http';

// Or use external tools
// curl -v http://localhost:8000/mcp
// Wireshark for packet analysis
```

## Getting Help

### Documentation Resources

1. **Official Documentation:**
   - API Reference: `docs/api-reference.md`
   - Best Practices: `docs/best-practices.md`
   - Setup Guide: `docs/setup-guide.md`
   - Migration Guide: `docs/migration-guide.md`

2. **Examples:**
   - `examples/basic-usage.ts`
   - `examples/schema-management.ts`
   - `examples/data-operations.ts`
   - `examples/query-search.ts`
   - `examples/advanced-patterns.ts`

### Community Support

1. **GitHub Issues:**
   ```bash
   # Search existing issues
   # Create new issue if needed
   # Provide minimal reproduction case
   ```

2. **Stack Overflow:**
   - Tag: `grizabella`
   - Include: TypeScript version, Node.js version, error messages

3. **Community Forums:**
   - Discord server
   - Reddit communities
   - Technical blogs

### Professional Support

1. **Enterprise Support:**
   - Contact sales team
   - Priority support channels
   - Dedicated support engineers

2. **Consulting Services:**
   - Code review services
   - Architecture consulting
   - Performance optimization

### Issue Reporting Template

```markdown
## Issue Description
<!-- Brief description of the problem -->

## Environment
- **OS:** (e.g., macOS 12.0, Windows 11, Ubuntu 20.04)
- **Node.js:** (e.g., v18.0.0)
- **TypeScript:** (e.g., v5.0.0)
- **Grizabella TypeScript API:** (e.g., v1.0.0)
- **Grizabella MCP Server:** (e.g., v1.0.0)

## Steps to Reproduce
1. <!-- Step 1 -->
2. <!-- Step 2 -->
3. <!-- Step 3 -->

## Expected Behavior
<!-- What should happen -->

## Actual Behavior
<!-- What actually happens -->

## Error Messages
<!-- Full error messages, stack traces -->

## Code Sample
<!-- Minimal code sample that reproduces the issue -->
\`\`\`typescript
// Your code here
\`\`\`

## Additional Context
<!-- Screenshots, configuration files, etc. -->
```

### Debugging Checklist

- [ ] ✅ Verify Node.js and TypeScript versions
- [ ] ✅ Check package installation
- [ ] ✅ Confirm Grizabella server is running
- [ ] ✅ Validate connection configuration
- [ ] ✅ Test basic connectivity
- [ ] ✅ Check schema definitions
- [ ] ✅ Validate data types
- [ ] ✅ Review error messages carefully
- [ ] ✅ Enable debug logging
- [ ] ✅ Test with minimal reproduction case
- [ ] ✅ Check for similar issues in documentation

This troubleshooting guide covers the most common issues you'll encounter when using the Grizabella TypeScript API. If you can't find a solution to your problem, don't hesitate to reach out to the community or create a detailed issue report on GitHub.