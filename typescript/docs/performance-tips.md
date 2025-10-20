# Performance Optimization Guide

This guide covers performance optimization techniques for the Grizabella TypeScript API, helping you build efficient, scalable applications.

## 🚀 Quick Performance Wins

### 1. Use Context Managers for Connection Management

Always prefer the context manager pattern for automatic resource cleanup:

```typescript
// ✅ Good: Automatic cleanup
await using client = await GrizabellaClient.connect({
  dbNameOrPath: 'my-database',
  createIfNotExists: true,
});

// Your operations here
// Connection automatically closed

// ❌ Avoid: Manual cleanup (easy to forget)
const client = new GrizabellaClient(config);
await client.connect();
// ... operations ...
await client.close(); // Easy to forget!
```

### 2. Optimize Object Queries

#### Use Indexed Properties

```typescript
// ✅ Good: Index frequently queried properties
await client.createObjectType({
  name: 'Person',
  properties: [
    {
      name: 'email',
      data_type: PropertyDataType.TEXT,
      is_indexed: true, // Index for fast lookups
      is_unique: true,
    },
    {
      name: 'department',
      data_type: PropertyDataType.TEXT,
      is_indexed: true, // Index for filtering
    },
  ],
});

// Fast queries using indexed properties
const engineers = await client.findObjects('Person', {
  department: 'Engineering' // Uses index
});
```

#### Limit Query Results

```typescript
// ✅ Good: Limit results when you don't need all data
const recentUsers = await client.findObjects('Person', {
  created_at: { '>=': new Date('2024-01-01') }
}, 100); // Limit to 100 results

// ❌ Avoid: Getting all data when you only need some
const allUsers = await client.findObjects('Person'); // Potentially thousands of results
```

### 3. Batch Operations

#### Create Multiple Objects Efficiently

```typescript
// ✅ Good: Use helper for batch creation (when available)
const people = await createMultipleObjectInstances('Person', [
  { name: 'Alice', email: 'alice@company.com' },
  { name: 'Bob', email: 'bob@company.com' },
  { name: 'Charlie', email: 'charlie@company.com' },
]);

// ✅ Alternative: Manual batching
const batchSize = 50;
const allUserData = /* ... large array ... */;

for (let i = 0; i < allUserData.length; i += batchSize) {
  const batch = allUserData.slice(i, i + batchSize);
  const promises = batch.map(data => 
    client.upsertObject(createObjectInstance('Person', data))
  );
  await Promise.all(promises);
}
```

## 🔧 Advanced Optimization Techniques

### 4. Connection Management

#### Reuse Connections

```typescript
// ✅ Good: Create a singleton client for your application
class DatabaseService {
  private static client: GrizabellaClient | null = null;
  
  static async getClient(): Promise<GrizabellaClient> {
    if (!this.client) {
      this.client = await GrizabellaClient.connect({
        dbNameOrPath: process.env.DB_PATH,
        createIfNotExists: true,
      });
    }
    return this.client;
  }
  
  static async cleanup(): Promise<void> {
    if (this.client) {
      await this.client.close();
      this.client = null;
    }
  }
}

// Use in your application
const client = await DatabaseService.getClient();
const results = await client.findObjects('Person');
```

#### Configure Timeouts Appropriately

```typescript
// ✅ Good: Configure timeouts based on your use case
const client = new GrizabellaClient({
  dbNameOrPath: 'my-database',
  timeout: 30000,        // Connection timeout
  requestTimeout: 15000, // Request timeout (shorter for web apps)
  autoReconnect: true,
  maxReconnectAttempts: 3,
  reconnectDelay: 1000,
});
```

### 5. Memory Management

#### Process Large Result Sets in Chunks

```typescript
// ✅ Good: Process large datasets in chunks
async function processAllPeople(client: GrizabellaClient) {
  const pageSize = 100;
  let offset = 0;
  let hasMore = true;
  
  while (hasMore) {
    const people = await client.findObjects('Person', {}, pageSize);
    
    if (people.length === 0) {
      hasMore = false;
    } else {
      // Process this chunk
      for (const person of people) {
        await processPerson(person);
      }
      offset += pageSize;
    }
  }
}
```

#### Clean Up Resources

```typescript
// ✅ Good: Use try-finally for resource cleanup
async function robustOperation() {
  const client = new GrizabellaClient(config);
  try {
    await client.connect();
    // Your operations here
  } finally {
    await client.close();
  }
}
```

### 6. Query Optimization

#### Use Specific Filters

```typescript
// ✅ Good: Be specific with filters
const activeEngineers = await client.findObjects('Person', {
  department: 'Engineering',
  status: 'active',
  age: { '>=': 25, '<=': 65 }
});

// ❌ Avoid: Getting all data and filtering in memory
const allPeople = await client.findObjects('Person');
const activeEngineers = allPeople.filter(p => 
  p.properties.department === 'Engineering' &&
  p.properties.status === 'active' &&
  p.properties.age >= 25 &&
  p.properties.age <= 65
);
```

#### Optimize Relation Queries

```typescript
// ✅ Good: Query specific relation types
const managerRelations = await client.getOutgoingRelations(
  'person-123', 
  'Person', 
  'MANAGES' // Specific relation type
);

// ✅ Better: Get only what you need
const directReports = await client.getOutgoingRelations(
  'manager-123',
  'Person',
  'MANAGES',
  50 // Limit results
);
```

## 📊 Monitoring and Profiling

### 7. Performance Monitoring

#### Measure Operation Times

```typescript
import { timeAsync } from 'grizabella-typescript-api';

// ✅ Good: Measure critical operations
const result = await timeAsync(async () => {
  return await client.findObjects('Person', {
    department: 'Engineering'
  });
}, 'find-engineers');

console.log(`Query took ${result.duration}ms`);
console.log(`Found ${result.result.length} engineers`);
```

#### Monitor Memory Usage

```typescript
import { createMemoryReport } from 'grizabella-typescript-api';

// ✅ Good: Check memory usage during operations
const beforeMemory = createMemoryReport();

// Perform memory-intensive operation
const results = await client.findObjects('Person');

const afterMemory = createMemoryReport();
console.log('Memory usage:', {
  before: beforeMemory,
  after: afterMemory,
  difference: afterMemory.heapUsed - beforeMemory.heapUsed
});
```

### 8. Error Handling Performance

#### Use Specific Error Types

```typescript
// ✅ Good: Handle errors efficiently
try {
  const result = await client.findObjects('Person');
} catch (error) {
  if (error instanceof QueryError) {
    // Log query-specific errors
    console.error('Query failed:', error.message);
    // Return empty result or cached data
    return [];
  } else if (error instanceof ConnectionError) {
    // Handle connection issues
    console.error('Connection failed:', error.message);
    throw error; // Re-throw for retry logic
  } else {
    // Handle unexpected errors
    console.error('Unexpected error:', error);
    throw error;
  }
}
```

#### Implement Retry Logic

```typescript
import { withRetry, DEFAULT_RETRY_CONFIG } from 'grizabella-typescript-api';

// ✅ Good: Retry transient failures
const retryConfig = {
  ...DEFAULT_RETRY_CONFIG,
  maxAttempts: 3,
  baseDelay: 1000,
  maxDelay: 5000,
};

const result = await withRetry(async () => {
  return await client.findObjects('Person');
}, retryConfig);
```

## 🎯 Production Best Practices

### 9. Environment-Specific Optimization

#### Development vs Production Configuration

```typescript
// ✅ Good: Different configs for different environments
const isDevelopment = process.env.NODE_ENV === 'development';

const config = {
  dbNameOrPath: process.env.DB_PATH,
  createIfNotExists: isDevelopment,
  debug: isDevelopment,
  timeout: isDevelopment ? 60000 : 30000,
  requestTimeout: isDevelopment ? 30000 : 10000,
  autoReconnect: !isDevelopment,
  maxReconnectAttempts: isDevelopment ? 5 : 3,
};
```

### 10. Caching Strategies

#### Cache Frequently Accessed Data

```typescript
// ✅ Good: Simple in-memory cache for static data
class ObjectCache {
  private cache = new Map<string, { data: any; timestamp: number }>();
  private readonly ttl = 5 * 60 * 1000; // 5 minutes
  
  async get(key: string, fetcher: () => Promise<any>): Promise<any> {
    const cached = this.cache.get(key);
    const now = Date.now();
    
    if (cached && (now - cached.timestamp) < this.ttl) {
      return cached.data;
    }
    
    const data = await fetcher();
    this.cache.set(key, { data, timestamp: now });
    return data;
  }
  
  clear(): void {
    this.cache.clear();
  }
}

// Usage
const cache = new ObjectCache();
const objectTypes = await cache.get(
  'object-types',
  () => client.listObjectTypes()
);
```

## 🚨 Common Performance Pitfalls

### ❌ What to Avoid

1. **Don't create multiple clients** - Reuse connections
2. **Don't fetch all data** - Use filters and limits
3. **Don't ignore indexing** - Index frequently queried properties
4. **Don't forget cleanup** - Always close connections
5. **Don't block the event loop** - Use async operations properly

### ✅ What to Do

1. **Use context managers** - Automatic resource cleanup
2. **Index strategically** - Based on query patterns
3. **Batch operations** - Reduce round trips
4. **Monitor performance** - Measure and optimize
5. **Handle errors gracefully** - Don't let errors cascade

## 📈 Performance Metrics to Track

### Key Performance Indicators

1. **Query Response Time**: Average time for common queries
2. **Connection Time**: Time to establish database connections
3. **Memory Usage**: Heap and overall memory consumption
4. **Error Rate**: Frequency of failed operations
5. **Throughput**: Operations per second

### Monitoring Tools

```typescript
// Simple performance tracker
class PerformanceTracker {
  private metrics = new Map<string, number[]>();
  
  startTimer(name: string): () => void {
    const start = performance.now();
    return () => {
      const duration = performance.now() - start;
      if (!this.metrics.has(name)) {
        this.metrics.set(name, []);
      }
      this.metrics.get(name)!.push(duration);
    };
  }
  
  getStats(name: string) {
    const times = this.metrics.get(name) || [];
    if (times.length === 0) return null;
    
    return {
      count: times.length,
      average: times.reduce((a, b) => a + b, 0) / times.length,
      min: Math.min(...times),
      max: Math.max(...times),
      p95: times.sort((a, b) => a - b)[Math.floor(times.length * 0.95)],
    };
  }
}

// Usage
const tracker = new PerformanceTracker();
const endTimer = tracker.startTimer('find-people');
const people = await client.findObjects('Person');
endTimer();

console.log('Find people stats:', tracker.getStats('find-people'));
```

---

## 🔗 Additional Resources

- [API Reference](./api-reference.md) - Complete API documentation
- [Best Practices](./best-practices.md) - Production-ready patterns
- [Error Handling](./error-handling.md) - Comprehensive error management
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions

---

*Last updated: 2024-10-20*
*Focus: Practical performance optimization for real-world applications*