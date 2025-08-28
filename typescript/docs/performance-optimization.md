# Performance Optimization Guide

Comprehensive guide to optimizing performance when using the Grizabella TypeScript API in production applications.

## Table of Contents

- [Performance Principles](#performance-principles)
- [Connection Optimization](#connection-optimization)
- [Query Optimization](#query-optimization)
- [Data Operation Optimization](#data-operation-optimization)
- [Memory Management](#memory-management)
- [Caching Strategies](#caching-strategies)
- [Monitoring and Profiling](#monitoring-and-profiling)
- [Production Tuning](#production-tuning)

## Performance Principles

### 1. Measure First, Optimize Second

Always profile before optimizing:

```typescript
import { timeAsync, createMemoryReport } from 'grizabella-typescript-api';

// Time critical operations
const result = await timeAsync(
  () => client.findObjects('User', { department: 'Engineering' }),
  'findEngineers'
);

console.log(`Query took ${result.duration}ms for ${result.result.length} results`);
```

### 2. Use Appropriate Data Structures

Choose the right data types for your use case:

```typescript
// Use TEXT for searchable content
{
  name: 'description',
  data_type: PropertyDataType.TEXT,
  is_indexed: true, // Enable for search performance
}

// Use appropriate numeric types
{
  name: 'salary',
  data_type: PropertyDataType.FLOAT, // Or INTEGER for whole numbers
  is_indexed: true,
}
```

### 3. Implement Connection Pooling

Reuse connections instead of creating new ones:

```typescript
class DatabaseConnectionPool {
  private clients: Map<string, GrizabellaClient> = new Map();
  private maxPoolSize = 10;

  async getClient(): Promise<GrizabellaClient> {
    if (this.clients.size < this.maxPoolSize) {
      const client = await GrizabellaClient.connect({
        dbNameOrPath: process.env.DB_PATH!,
        serverUrl: process.env.GRIZABELLA_SERVER_URL!,
      });
      this.clients.set(client.dbNameOrPath, client);
    }

    // Return existing or create new client
    return Array.from(this.clients.values())[0];
  }

  async closeAll(): Promise<void> {
    for (const client of this.clients.values()) {
      await client.close();
    }
    this.clients.clear();
  }
}
```

## Connection Optimization

### Connection Configuration

Optimize connection settings for your environment:

```typescript
const optimizedConfig: GrizabellaClientConfig = {
  dbNameOrPath: 'production-db',
  serverUrl: 'http://localhost:8000/mcp',
  createIfNotExists: false, // Don't create in production

  // Connection optimization
  timeout: 30000,
  requestTimeout: 25000,
  autoReconnect: true,
  maxReconnectAttempts: 5,
  reconnectDelay: 1000,

  // Production settings
  debug: false, // Disable in production
};
```

### Connection Health Monitoring

Monitor connection health and performance:

```typescript
class ConnectionMonitor {
  private client: GrizabellaClient;
  private healthCheckInterval = 30000; // 30 seconds
  private lastHealthCheck = 0;
  private consecutiveFailures = 0;

  constructor(client: GrizabellaClient) {
    this.client = client;
    this.startHealthMonitoring();
  }

  private startHealthMonitoring() {
    setInterval(async () => {
      try {
        const startTime = Date.now();
        await this.client.findObjects('HealthCheck', {}, 1);
        const duration = Date.now() - startTime;

        this.consecutiveFailures = 0;

        if (duration > 5000) {
          console.warn(`Slow connection detected: ${duration}ms`);
        }

      } catch (error) {
        this.consecutiveFailures++;

        if (this.consecutiveFailures >= 3) {
          console.error('Multiple connection failures detected');
          // Trigger reconnection or alert
        }
      }
    }, this.healthCheckInterval);
  }
}
```

### Context Manager Optimization

Use context managers efficiently:

```typescript
// ✅ Good: Reuse client for multiple operations
await using client = await databaseManager.getClient();

const user = await client.getObjectById('user-123', 'User');
const profile = await client.getObjectById('user-123-profile', 'UserProfile');
const posts = await client.findObjects('Post', { author_id: 'user-123' });

// ❌ Bad: Multiple context managers
await using client1 = await databaseManager.getClient();
const user = await client1.getObjectById('user-123', 'User');

await using client2 = await databaseManager.getClient();
const profile = await client2.getObjectById('user-123-profile', 'UserProfile');
```

## Query Optimization

### Index Strategy

Design indexes for common query patterns:

```typescript
const userSchema: ObjectTypeDefinition = {
  name: 'User',
  properties: [
    // Primary identifiers - always indexed
    {
      name: 'email',
      data_type: PropertyDataType.TEXT,
      is_nullable: false,
      is_unique: true,
      is_indexed: true,
    },

    // Foreign keys - index for joins
    {
      name: 'department_id',
      data_type: PropertyDataType.TEXT,
      is_nullable: true,
      is_indexed: true,
    },

    // Frequently queried fields
    {
      name: 'status',
      data_type: PropertyDataType.TEXT,
      is_nullable: false,
      is_indexed: true,
    },

    // Range queries
    {
      name: 'created_at',
      data_type: PropertyDataType.DATETIME,
      is_nullable: false,
      is_indexed: true,
    },

    // Non-indexed fields (searchable content)
    {
      name: 'biography',
      data_type: PropertyDataType.TEXT,
      is_nullable: true,
      // Not indexed - use embedding search instead
    },
  ],
};
```

### Query Pattern Optimization

Choose the most efficient query patterns:

```typescript
class OptimizedUserQueries {
  constructor(private client: GrizabellaClient) {}

  // ✅ Efficient: Specific indexed field
  async findActiveUsersByDepartment(department: string) {
    return await this.client.findObjects('User', {
      department,
      is_active: true,
    });
  }

  // ✅ Efficient: Range queries on indexed fields
  async findUsersCreatedInDateRange(startDate: Date, endDate: Date) {
    return await this.client.findObjects('User', {
      created_at: { '>=': startDate, '<=': endDate }
    });
  }

  // ❌ Inefficient: Multiple non-indexed field queries
  async findUsersByMultipleUnindexedFields() {
    return await this.client.findObjects('User', {
      first_name: 'John', // Not indexed
      city: 'New York',   // Not indexed
      hobby: 'Reading',   // Not indexed
    });
  }

  // ✅ Better: Use embedding search for content
  async findUsersByBiography(query: string) {
    return await this.client.findSimilar(
      'user_biography_embedding',
      query,
      10
    );
  }
}
```

### Batch Query Optimization

Process multiple queries efficiently:

```typescript
class BatchQueryProcessor {
  constructor(private client: GrizabellaClient) {}

  // ✅ Good: Batch similar operations
  async getMultipleUsersByIds(userIds: string[]) {
    const promises = userIds.map(id =>
      this.client.getObjectById(id, 'User')
    );

    const results = await Promise.all(promises);
    return results.filter(user => user !== null);
  }

  // ✅ Good: Use batch creation for multiple objects
  async createMultipleUsers(userData: Partial<User>[]) {
    const userObjects = userData.map(data =>
      createObjectInstance('User', data)
    );

    return await createMultipleObjectInstances(
      this.client,
      'User',
      userObjects
    );
  }

  // ❌ Bad: Sequential processing
  async createUsersSequentially(userData: Partial<User>[]) {
    const results = [];
    for (const data of userData) {
      const user = await this.client.upsertObject(
        createObjectInstance('User', data)
      );
      results.push(user);
    }
    return results;
  }
}
```

## Data Operation Optimization

### Bulk Operations

Use bulk operations for multiple records:

```typescript
import { createMultipleObjectInstances } from 'grizabella-typescript-api';

async function bulkCreateUsers(client: GrizabellaClient, users: UserData[]) {
  const BATCH_SIZE = 100;

  // Process in batches to avoid memory issues
  for (let i = 0; i < users.length; i += BATCH_SIZE) {
    const batch = users.slice(i, i + BATCH_SIZE);

    const userObjects = batch.map(user => createObjectInstance('User', user));

    const createdUsers = await createMultipleObjectInstances(
      client,
      'User',
      userObjects
    );

    console.log(`Created batch of ${createdUsers.length} users`);
  }
}
```

### Lazy Loading and Pagination

Implement efficient data loading patterns:

```typescript
class PaginatedUserRepository {
  private readonly PAGE_SIZE = 50;

  async getUsersPaginated(filters: any = {}, page = 1) {
    const offset = (page - 1) * this.PAGE_SIZE;

    // Note: Actual pagination implementation depends on your database
    // This is a conceptual example
    const users = await this.client.findObjects(
      'User',
      filters,
      this.PAGE_SIZE,
      offset
    );

    return {
      users,
      page,
      pageSize: this.PAGE_SIZE,
      hasMore: users.length === this.PAGE_SIZE,
    };
  }

  async *getUsersIterator(filters: any = {}) {
    let page = 1;
    let hasMore = true;

    while (hasMore) {
      const result = await this.getUsersPaginated(filters, page);
      yield result.users;

      hasMore = result.hasMore;
      page++;
    }
  }
}

// Usage with iterator
async function processAllUsers(client: GrizabellaClient) {
  const repo = new PaginatedUserRepository(client);

  for await (const users of repo.getUsersIterator({ is_active: true })) {
    for (const user of users) {
      await processUser(user); // Process each user individually
    }
  }
}
```

### Transaction-Like Operations

Implement atomic operations:

```typescript
class AtomicOperations {
  constructor(private client: GrizabellaClient) {}

  async transferUserBetweenDepartments(
    userId: string,
    fromDepartment: string,
    toDepartment: string
  ) {
    // Verify user exists and is in correct department
    const user = await this.client.getObjectById(userId, 'User');
    if (!user || user.properties.department !== fromDepartment) {
      throw new Error('Invalid user or department');
    }

    // Verify target department exists
    const targetDept = await this.client.findObjects('Department', {
      name: toDepartment
    });

    if (targetDept.length === 0) {
      throw new Error('Target department does not exist');
    }

    // Update user department
    const updatedUser = await this.client.upsertObject({
      ...user,
      properties: {
        ...user.properties,
        department: toDepartment,
        department_changed_at: new Date(),
      },
    });

    // Log the transfer
    await this.client.upsertObject(createObjectInstance('DepartmentTransfer', {
      user_id: userId,
      from_department: fromDepartment,
      to_department: toDepartment,
      transferred_at: new Date(),
    }));

    return updatedUser;
  }
}
```

## Memory Management

### Memory-Efficient Processing

Process large datasets without loading everything into memory:

```typescript
class MemoryEfficientProcessor {
  private readonly CHUNK_SIZE = 1000;

  async processLargeDataset(client: GrizabellaClient) {
    const memoryBefore = createMemoryReport();

    // Get total count first
    const allUsers = await client.findObjects('User', {}, 1);
    const totalCount = allUsers.length;

    console.log(`Processing ${totalCount} users in chunks`);

    for (let offset = 0; offset < totalCount; offset += this.CHUNK_SIZE) {
      // Process chunk
      const chunk = await client.findObjects('User', {}, this.CHUNK_SIZE, offset);

      for (const user of chunk) {
        await this.processUser(user);
      }

      // Force garbage collection hint
      if (global.gc) {
        global.gc();
      }

      const memoryAfter = createMemoryReport();
      console.log(`Processed ${offset + chunk.length} users. Memory: ${memoryAfter.heapUsed} bytes`);
    }
  }

  private async processUser(user: any) {
    // Process individual user
    // This method processes one user at a time to minimize memory usage
  }
}
```

### Object Instance Optimization

Create lightweight object instances:

```typescript
class LightweightObjectFactory {
  // Only include essential fields
  createUserSummary(user: User): object {
    return {
      id: user.id,
      name: user.properties.name,
      email: user.properties.email,
      department: user.properties.department,
      // Exclude large fields like biography, profile_picture, etc.
    };
  }

  // Create object for list view (minimal data)
  createUserListItem(user: User): object {
    return {
      id: user.id,
      name: user.properties.name,
      department: user.properties.department,
      is_active: user.properties.is_active,
    };
  }

  // Create object for detail view (all data)
  createUserDetail(user: User): User {
    return user; // Full object
  }
}
```

### Memory Monitoring

Monitor and manage memory usage:

```typescript
class MemoryManager {
  private readonly MAX_MEMORY_USAGE = 800 * 1024 * 1024; // 800MB
  private checkInterval = 10000; // 10 seconds

  constructor() {
    this.startMemoryMonitoring();
  }

  private startMemoryMonitoring() {
    setInterval(() => {
      const memory = createMemoryReport();

      if (memory.heapUsed > this.MAX_MEMORY_USAGE) {
        console.warn('High memory usage detected:', memory.heapUsed);
        this.onHighMemoryUsage();
      }
    }, this.checkInterval);
  }

  private onHighMemoryUsage() {
    // Force garbage collection if available
    if (global.gc) {
      global.gc();
      console.log('Forced garbage collection');
    }

    // Additional cleanup actions
    this.clearCaches();
    this.closeIdleConnections();
  }

  private clearCaches() {
    // Clear application caches
    console.log('Clearing application caches');
  }

  private closeIdleConnections() {
    // Close idle database connections
    console.log('Closing idle connections');
  }
}
```

## Caching Strategies

### Multi-Level Caching

Implement multiple caching layers:

```typescript
class MultiLevelCache {
  private l1Cache = new Map<string, any>(); // Fast in-memory cache
  private l2Cache: RedisCache; // Distributed cache
  private l3Cache: DatabaseCache; // Database cache

  async get(key: string): Promise<any | null> {
    // Check L1 cache first
    if (this.l1Cache.has(key)) {
      return this.l1Cache.get(key);
    }

    // Check L2 cache
    const l2Value = await this.l2Cache.get(key);
    if (l2Value) {
      // Promote to L1 cache
      this.l1Cache.set(key, l2Value);
      return l2Value;
    }

    // Check L3 cache
    const l3Value = await this.l3Cache.get(key);
    if (l3Value) {
      // Promote to higher caches
      await this.l2Cache.set(key, l3Value);
      this.l1Cache.set(key, l3Value);
      return l3Value;
    }

    return null;
  }

  async set(key: string, value: any, ttl?: number): Promise<void> {
    // Set in all caches
    this.l1Cache.set(key, value);
    await this.l2Cache.set(key, value, ttl);
    await this.l3Cache.set(key, value, ttl);
  }
}
```

### Database Query Result Caching

Cache frequently accessed query results:

```typescript
class QueryResultCache {
  private cache = new Map<string, { data: any; timestamp: number; ttl: number }>();

  generateKey(typeName: string, filters: any): string {
    return `${typeName}:${JSON.stringify(filters)}`;
  }

  async get(typeName: string, filters: any): Promise<any[] | null> {
    const key = this.generateKey(typeName, filters);
    const cached = this.cache.get(key);

    if (cached && Date.now() - cached.timestamp < cached.ttl) {
      return cached.data;
    }

    return null;
  }

  async set(typeName: string, filters: any, data: any[], ttl = 300000): Promise<void> {
    const key = this.generateKey(typeName, filters);
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl,
    });
  }

  clear(): void {
    this.cache.clear();
  }
}

// Usage in repository
class CachedUserRepository extends UserRepository {
  private cache = new QueryResultCache();

  async findByDepartment(department: string): Promise<User[]> {
    // Check cache first
    const cached = await this.cache.get('User', { department });
    if (cached) {
      return cached;
    }

    // Fetch from database
    const users = await super.findByDepartment(department);

    // Cache result
    await this.cache.set('User', { department }, users, 300000); // 5 minutes

    return users;
  }
}
```

### Cache Invalidation Strategies

Implement proper cache invalidation:

```typescript
class CacheInvalidationManager {
  constructor(private cache: MultiLevelCache) {}

  // Invalidate by pattern
  async invalidateUserCache(userId: string): Promise<void> {
    const patterns = [
      `User:${JSON.stringify({ id: userId })}`,
      `User:*`, // Invalidate all user queries
    ];

    for (const pattern of patterns) {
      await this.cache.invalidatePattern(pattern);
    }
  }

  // Invalidate on data changes
  async onUserUpdated(userId: string): Promise<void> {
    await this.invalidateUserCache(userId);

    // Also invalidate related caches
    await this.invalidateDepartmentCache();
    await this.invalidateSearchCache();
  }

  // Time-based invalidation
  async cleanupExpiredCache(): Promise<void> {
    // Remove expired cache entries
    await this.cache.cleanup();
  }
}
```

## Monitoring and Profiling

### Performance Monitoring Setup

Implement comprehensive performance monitoring:

```typescript
import { PerformanceMonitor, timeAsync, timeSync } from 'grizabella-typescript-api';

class ApplicationPerformanceMonitor {
  private monitor = new PerformanceMonitor();

  async monitorDatabaseOperation<T>(
    name: string,
    operation: () => Promise<T>
  ): Promise<T> {
    const startTime = Date.now();
    const memoryBefore = createMemoryReport();

    try {
      const result = await operation();

      const duration = Date.now() - startTime;
      const memoryAfter = createMemoryReport();

      this.recordMetrics(name, {
        duration,
        memoryDelta: memoryAfter.heapUsed - memoryBefore.heapUsed,
        success: true,
      });

      return result;

    } catch (error) {
      const duration = Date.now() - startTime;

      this.recordMetrics(name, {
        duration,
        success: false,
        error: error.message,
      });

      throw error;
    }
  }

  private recordMetrics(name: string, metrics: any): void {
    // Send to monitoring service (e.g., Prometheus, DataDog)
    console.log(`Performance metrics for ${name}:`, metrics);

    // Check performance thresholds
    if (metrics.duration > 5000) {
      console.warn(`Slow operation detected: ${name} took ${metrics.duration}ms`);
    }

    if (metrics.memoryDelta > 50 * 1024 * 1024) { // 50MB
      console.warn(`High memory usage: ${name} used ${metrics.memoryDelta} bytes`);
    }
  }
}
```

### Database Query Profiling

Profile and optimize database queries:

```typescript
class QueryProfiler {
  private queryStats = new Map<string, {
    count: number;
    totalTime: number;
    minTime: number;
    maxTime: number;
  }>();

  async profileQuery<T>(
    name: string,
    query: () => Promise<T>
  ): Promise<T> {
    const startTime = Date.now();

    try {
      const result = await query();
      const duration = Date.now() - startTime;

      this.recordQueryStats(name, duration, true);

      // Log slow queries
      if (duration > 1000) {
        console.warn(`Slow query detected: ${name} took ${duration}ms`);
      }

      return result;

    } catch (error) {
      const duration = Date.now() - startTime;
      this.recordQueryStats(name, duration, false);
      throw error;
    }
  }

  private recordQueryStats(name: string, duration: number, success: boolean): void {
    const current = this.queryStats.get(name) || {
      count: 0,
      totalTime: 0,
      minTime: Infinity,
      maxTime: -Infinity,
    };

    current.count++;
    current.totalTime += duration;
    current.minTime = Math.min(current.minTime, duration);
    current.maxTime = Math.max(current.maxTime, duration);

    this.queryStats.set(name, current);
  }

  getQueryStats(): Record<string, any> {
    const stats: Record<string, any> = {};

    for (const [name, data] of this.queryStats) {
      stats[name] = {
        count: data.count,
        averageTime: data.totalTime / data.count,
        minTime: data.minTime,
        maxTime: data.maxTime,
        totalTime: data.totalTime,
      };
    }

    return stats;
  }
}
```

### Automated Performance Testing

Create automated performance tests:

```typescript
class PerformanceTestSuite {
  constructor(private client: GrizabellaClient) {}

  async runPerformanceTests() {
    console.log('Running performance test suite...');

    // Test 1: Connection performance
    await this.testConnectionPerformance();

    // Test 2: Query performance
    await this.testQueryPerformance();

    // Test 3: Bulk operation performance
    await this.testBulkOperationPerformance();

    // Test 4: Memory usage
    await this.testMemoryUsage();

    console.log('Performance test suite completed');
  }

  private async testConnectionPerformance() {
    const result = await timeAsync(
      async () => {
        await using testClient = await GrizabellaClient.connect({
          dbNameOrPath: 'performance-test-db',
          serverUrl: 'http://localhost:8000/mcp',
        });
        return testClient;
      },
      'connection'
    );

    console.log(`Connection time: ${result.duration}ms`);
  }

  private async testQueryPerformance() {
    // Create test data
    const testUsers = Array(1000).fill(null).map((_, i) => ({
      name: `Test User ${i}`,
      email: `test${i}@example.com`,
    }));

    await createMultipleObjectInstances(this.client, 'User', testUsers);

    // Test different query types
    const queries = [
      {
        name: 'Find all users',
        query: () => this.client.findObjects('User'),
      },
      {
        name: 'Find users by email',
        query: () => this.client.findObjects('User', { email: 'test500@example.com' }),
      },
    ];

    for (const { name, query } of queries) {
      const result = await timeAsync(query, name);
      console.log(`${name}: ${result.duration}ms for ${result.result.length} results`);
    }
  }

  private async testBulkOperationPerformance() {
    const bulkData = Array(100).fill(null).map((_, i) => ({
      name: `Bulk User ${i}`,
      email: `bulk${i}@example.com`,
    }));

    const result = await timeAsync(
      () => createMultipleObjectInstances(this.client, 'User', bulkData),
      'bulkCreate'
    );

    console.log(`Bulk create: ${result.duration}ms for ${result.result.length} records`);
  }

  private async testMemoryUsage() {
    const memoryBefore = createMemoryReport();

    // Perform memory-intensive operation
    const allUsers = await this.client.findObjects('User');

    const memoryAfter = createMemoryReport();
    const memoryDelta = memoryAfter.heapUsed - memoryBefore.heapUsed;

    console.log(`Memory usage: ${memoryDelta} bytes for ${allUsers.length} users`);
  }
}
```

## Production Tuning

### Environment-Specific Configuration

Configure for different environments:

```typescript
// config/production.ts
export const productionConfig: GrizabellaClientConfig = {
  dbNameOrPath: process.env.DATABASE_PATH || '/data/production-db',
  serverUrl: process.env.GRIZABELLA_SERVER_URL!,
  createIfNotExists: false,
  debug: false,

  // Optimized for production
  timeout: 60000,
  requestTimeout: 55000,
  autoReconnect: true,
  maxReconnectAttempts: 10,
  reconnectDelay: 5000,

  // Performance tuning
  retryConfig: {
    maxAttempts: 3,
    baseDelay: 1000,
    maxDelay: 10000,
    backoffFactor: 2,
  },
};

// config/development.ts
export const developmentConfig: GrizabellaClientConfig = {
  dbNameOrPath: process.env.DATABASE_PATH || './data/dev-db',
  serverUrl: process.env.GRIZABELLA_SERVER_URL || 'http://localhost:8000/mcp',
  createIfNotExists: true,
  debug: true,

  // Relaxed settings for development
  timeout: 30000,
  requestTimeout: 25000,
  autoReconnect: true,
  maxReconnectAttempts: 3,
  reconnectDelay: 1000,
};
```

### Database Server Tuning

Optimize the Grizabella MCP server:

```python
# MCP server configuration for production
server_config = {
    # Connection settings
    'host': '0.0.0.0',
    'port': 8000,
    'max_connections': 100,

    # Performance settings
    'worker_processes': 4,
    'worker_connections': 1024,

    # Database settings
    'db_connection_pool_size': 20,
    'db_connection_timeout': 30,
    'db_query_timeout': 60,

    # Caching settings
    'query_cache_size': 1000,
    'query_cache_ttl': 300,

    # Monitoring
    'enable_metrics': True,
    'metrics_port': 9090,
}
```

### Load Testing

Implement load testing for production validation:

```typescript
class LoadTester {
  constructor(private client: GrizabellaClient) {}

  async runLoadTest() {
    const concurrentUsers = 50;
    const requestsPerUser = 100;
    const results = [];

    console.log(`Starting load test: ${concurrentUsers} users, ${requestsPerUser} requests each`);

    const promises = Array(concurrentUsers).fill(null).map(async (_, userId) => {
      const userResults = {
        userId,
        requests: 0,
        errors: 0,
        totalTime: 0,
      };

      for (let i = 0; i < requestsPerUser; i++) {
        try {
          const startTime = Date.now();

          // Simulate user operations
          await this.simulateUserOperations(userId);

          const duration = Date.now() - startTime;
          userResults.requests++;
          userResults.totalTime += duration;

        } catch (error) {
          userResults.errors++;
          console.error(`User ${userId} request ${i} failed:`, error);
        }
      }

      return userResults;
    });

    const userResults = await Promise.all(promises);

    // Aggregate results
    const totalRequests = userResults.reduce((sum, r) => sum + r.requests, 0);
    const totalErrors = userResults.reduce((sum, r) => sum + r.errors, 0);
    const totalTime = userResults.reduce((sum, r) => sum + r.totalTime, 0);
    const averageRequestTime = totalTime / totalRequests;

    console.log('Load test results:');
    console.log(`Total requests: ${totalRequests}`);
    console.log(`Total errors: ${totalErrors}`);
    console.log(`Error rate: ${(totalErrors / totalRequests * 100).toFixed(2)}%`);
    console.log(`Average request time: ${averageRequestTime.toFixed(2)}ms`);

    return {
      totalRequests,
      totalErrors,
      averageRequestTime,
      userResults,
    };
  }

  private async simulateUserOperations(userId: number) {
    // Simulate realistic user operations
    const operations = [
      () => this.client.getObjectById(`user-${userId}`, 'User'),
      () => this.client.findObjects('User', { department: 'Engineering' }),
      () => this.client.upsertObject(createObjectInstance('User', {
        name: `Load Test User ${userId}`,
        email: `loadtest${userId}@example.com`,
      })),
    ];

    const randomOperation = operations[Math.floor(Math.random() * operations.length)];
    await randomOperation();
  }
}
```

This performance optimization guide provides comprehensive strategies for optimizing the Grizabella TypeScript API in production. The key principles are:

1. **Measure and profile** before optimizing
2. **Use appropriate data structures** and indexing
3. **Implement connection pooling** and reuse
4. **Batch operations** and use pagination
5. **Monitor memory usage** and implement caching
6. **Profile queries** and optimize bottlenecks
7. **Use context managers** efficiently
8. **Implement proper monitoring** and alerting

Following these practices will help you achieve optimal performance and scalability with the Grizabella TypeScript API.