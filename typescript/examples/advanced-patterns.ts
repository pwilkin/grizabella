/**
 * Advanced Patterns Examples for Grizabella TypeScript API
 *
 * This file demonstrates advanced TypeScript patterns, error handling strategies,
 * performance monitoring, resource management, and best practices for production use.
 */

import {
  GrizabellaClient,
  PropertyDataType,
  Decimal,
  GrizabellaError,
  ConnectionError,
  NotConnectedError,
  ValidationError,
  QueryError,
  withRetry,
  DEFAULT_RETRY_CONFIG,
  createErrorBoundary,
  timeAsync,
  timeSync,
  PerformanceMonitor,
  createMemoryReport,
  ConnectionInfo,
  GrizabellaConfig,
  loadConfigFromEnv,
  validateConfig,
  buildConfig,
  setGlobalLogger,
  ConsoleDebugLogger,
  createObjectInstance,
} from '../src/index';

/**
 * Example 1: Advanced Error Handling and Recovery
 * Shows comprehensive error handling patterns with retry logic
 */
async function advancedErrorHandlingExample() {
  console.log('=== Advanced Error Handling Example ===');

  // Custom retry configuration
  const customRetryConfig = {
    ...DEFAULT_RETRY_CONFIG,
    maxAttempts: 3,
    baseDelay: 1000,
    maxDelay: 5000,
    backoffFactor: 2,
  };

  // Function with automatic retry logic
  async function connectWithRetry(): Promise<GrizabellaClient> {
    return await withRetry(async () => {
      const client = new GrizabellaClient({
        dbNameOrPath: 'error-handling-example-db',
        serverUrl: 'http://localhost:8000/mcp',
        createIfNotExists: true,
      });

      await client.connect();
      return client;
    }, customRetryConfig);
  }

  try {
    await using client = await connectWithRetry();
    console.log('✅ Connected with retry logic');

    // Example with error boundary
    const errorBoundary = createErrorBoundary({
      onError: (error: Error) => {
        console.error('Error caught by boundary:', error.message);
        return { fallback: 'error_occurred' };
      },
      shouldCatch: (error) => error instanceof QueryError,
    });

    // Use error boundary to wrap potentially failing operations
    const result = await errorBoundary(async () => {
      return await client.findObjects('NonExistentType');
    });

    if (result === 'error_occurred') {
      console.log('✅ Error boundary handled the error gracefully');
    }

  } catch (error) {
    console.error('❌ Connection failed after retries:', error.message);
  }

  // Manual error handling with different error types
  try {
    await using client = new GrizabellaClient({
      dbNameOrPath: 'error-handling-example-db',
      serverUrl: 'http://non-existent-server:8000/mcp',
      timeout: 2000,
    });

    await client.connect();
  } catch (error) {
    if (error instanceof ConnectionError) {
      console.log('🔌 Connection error:', error.message);
      console.log('   Server URL:', error.details?.host);
    } else if (error instanceof ValidationError) {
      console.log('⚠️ Validation error:', error.message);
    } else if (error instanceof NotConnectedError) {
      console.log('🔌 Not connected error:', error.message);
    } else if (error instanceof GrizabellaError) {
      console.log('🐛 Grizabella error:', error.message);
      console.log('   Category:', error.category);
      console.log('   Severity:', error.severity);
    } else {
      console.log('❓ Unknown error:', error.message);
    }
  }
}

/**
 * Example 2: Resource Management and Context Managers
 * Shows advanced resource management patterns
 */
async function resourceManagementExample() {
  console.log('\n=== Resource Management Example ===');

  // Custom resource manager class
  class DatabaseManager {
    private clients: Map<string, GrizabellaClient> = new Map();

    async getClient(name: string): Promise<GrizabellaClient> {
      if (!this.clients.has(name)) {
        const client = new GrizabellaClient({
          dbNameOrPath: `${name}-db`,
          serverUrl: 'http://localhost:8000/mcp',
          createIfNotExists: true,
        });

        await client.connect();
        this.clients.set(name, client);
      }

      return this.clients.get(name)!;
    }

    async closeAll(): Promise<void> {
      for (const [name, client] of this.clients) {
        try {
          await client.close();
          console.log(`✅ Closed client: ${name}`);
        } catch (error) {
          console.error(`❌ Error closing client ${name}:`, error);
        }
      }
      this.clients.clear();
    }
  }

  const manager = new DatabaseManager();

  try {
    // Get multiple clients
    const client1 = await manager.getClient('user-data');
    const client2 = await manager.getClient('analytics');

    console.log('✅ Created multiple managed clients');

    // Use clients
    const userCount = await client1.findObjects('User');
    const eventCount = await client2.findObjects('Event');

    console.log(`📊 Users: ${userCount.length}, Events: ${eventCount.length}`);

  } finally {
    // Always clean up
    await manager.closeAll();
  }

  // Advanced context manager pattern with custom logic
  class TransactionManager {
    private client: GrizabellaClient;
    private operations: Array<() => Promise<void>> = [];
    private rolledBack = false;

    constructor(client: GrizabellaClient) {
      this.client = client;
    }

    async addOperation(operation: () => Promise<void>) {
      this.operations.push(operation);
    }

    async commit(): Promise<void> {
      if (this.rolledBack) {
        throw new Error('Cannot commit a rolled back transaction');
      }

      for (const operation of this.operations) {
        await operation();
      }

      console.log('✅ Transaction committed');
    }

    async rollback(): Promise<void> {
      this.rolledBack = true;
      this.operations = [];
      console.log('🔄 Transaction rolled back');
    }

    async [Symbol.asyncDispose](): Promise<void> {
      if (!this.rolledBack) {
        await this.rollback();
      }
    }
  }

  // Usage example
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'transaction-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  await using transaction = new TransactionManager(client);

  try {
    // Add operations to transaction
    await transaction.addOperation(async () => {
      await client.upsertObject(createObjectInstance('User', {
        name: 'Transaction User',
        email: 'transaction@example.com',
      }));
    });

    // Commit transaction
    await transaction.commit();

  } catch (error) {
    // Transaction will auto-rollback
    console.log('❌ Transaction failed, auto-rolled back');
  }
}

/**
 * Example 3: Performance Monitoring and Optimization
 * Shows comprehensive performance monitoring patterns
 */
async function performanceMonitoringExample() {
  console.log('\n=== Performance Monitoring Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'performance-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  // Create test data
  await client.createObjectType({
    name: 'TestEntity',
    description: 'Entity for performance testing',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'value', data_type: PropertyDataType.INTEGER, is_nullable: true },
      { name: 'category', data_type: PropertyDataType.TEXT, is_nullable: true },
    ],
  });

  // Performance monitor usage
  const monitor = new PerformanceMonitor();

  // Monitor multiple operations
  const results = await Promise.all([
    timeAsync(
      () => client.createObjectType({
        name: 'AnotherEntity',
        description: 'Another test entity',
        properties: [{ name: 'data', data_type: PropertyDataType.TEXT, is_nullable: true }],
      }),
      'createObjectType'
    ),
    timeAsync(
      () => createMultipleObjectInstances(client, 'TestEntity', Array(100).fill(null).map((_, i) => ({
        name: `Test Entity ${i}`,
        value: i * 10,
        category: i % 2 === 0 ? 'even' : 'odd',
      }))),
      'bulkCreate'
    ),
  ]);

  console.log('⏱️ Performance Results:');
  results.forEach(result => {
    console.log(`  ${result.name}: ${result.duration}ms`);
  });

  // Memory monitoring
  const memoryBefore = createMemoryReport();
  console.log('\n🧠 Memory Before Operations:');
  Object.entries(memoryBefore).forEach(([key, value]) => {
    console.log(`  ${key}: ${value}`);
  });

  // Perform memory-intensive operations
  const largeQuery = await client.findObjects('TestEntity');

  const memoryAfter = createMemoryReport();
  console.log('\n🧠 Memory After Operations:');
  Object.entries(memoryAfter).forEach(([key, value]) => {
    console.log(`  ${key}: ${value}`);
  });

  // Synchronous timing for non-async operations
  const syncTime = timeSync(() => {
    const result = [];
    for (let i = 0; i < 1000; i++) {
      result.push(i * i);
    }
    return result;
  }, 'syncComputation');

  console.log(`\n⚡ Sync operation took: ${syncTime.duration}ms`);

  // Custom performance tracking
  class OperationTracker {
    private operations: Map<string, { count: number; totalTime: number }> = new Map();

    track<T>(name: string, operation: () => T): T {
      const start = Date.now();
      try {
        const result = operation();
        const duration = Date.now() - start;

        const current = this.operations.get(name) || { count: 0, totalTime: 0 };
        this.operations.set(name, {
          count: current.count + 1,
          totalTime: current.totalTime + duration,
        });

        return result;
      } catch (error) {
        const duration = Date.now() - start;

        const current = this.operations.get(name) || { count: 0, totalTime: 0 };
        this.operations.set(name, {
          count: current.count + 1,
          totalTime: current.totalTime + duration,
        });

        throw error;
      }
    }

    getStats(): Record<string, { count: number; averageTime: number }> {
      const stats: Record<string, { count: number; averageTime: number }> = {};

      for (const [name, data] of this.operations) {
        stats[name] = {
          count: data.count,
          averageTime: data.totalTime / data.count,
        };
      }

      return stats;
    }
  }

  const tracker = new OperationTracker();

  // Track various operations
  tracker.track('dataProcessing', () => {
    return largeQuery.filter(item => item.properties.value > 500);
  });

  tracker.track('dataAggregation', () => {
    const categories = largeQuery.reduce((acc, item) => {
      const cat = item.properties.category;
      acc[cat] = (acc[cat] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    return categories;
  });

  console.log('\n📊 Custom Tracker Stats:');
  const stats = tracker.getStats();
  Object.entries(stats).forEach(([name, stat]) => {
    console.log(`  ${name}: ${stat.count} calls, ${stat.averageTime.toFixed(2)}ms avg`);
  });
}

/**
 * Example 4: Configuration Management
 * Shows advanced configuration patterns and validation
 */
async function configurationManagementExample() {
  console.log('\n=== Configuration Management Example ===');

  // Environment-based configuration
  const envConfig = loadConfigFromEnv();
  console.log('📝 Environment config loaded');

  // Custom configuration with validation
  const customConfig: Partial<GrizabellaConfig> = {
    serverUrl: 'http://localhost:8000/mcp',
    dbNameOrPath: 'config-example-db',
    timeout: 15000,
    debug: true,
    autoReconnect: true,
    maxReconnectAttempts: 5,
    retryConfig: {
      maxAttempts: 3,
      baseDelay: 1000,
    },
  };

  const validConfig = validateConfig(customConfig);
  if (validConfig.isValid) {
    console.log('✅ Configuration is valid');
  } else {
    console.log('❌ Configuration errors:');
    validConfig.errors.forEach(error => console.log(`  - ${error}`));
  }

  // Build configuration with defaults
  const finalConfig = buildConfig({
    serverUrl: 'http://localhost:8000/mcp',
    dbNameOrPath: 'config-example-db',
    debug: true,
  });

  console.log('🔧 Final configuration:');
  console.log(`  Server: ${finalConfig.serverUrl}`);
  console.log(`  Database: ${finalConfig.dbNameOrPath}`);
  console.log(`  Debug: ${finalConfig.debug}`);
  console.log(`  Timeout: ${finalConfig.timeout}ms`);

  // Connection info utility
  const connectionInfo: ConnectionInfo = {
    host: 'localhost',
    port: 8000,
    database: 'config-example-db',
    protocol: 'http',
    ssl: false,
  };

  console.log('🔗 Connection info parsed from:', connectionInfo);

  // Using the final configuration
  await using client = new GrizabellaClient(finalConfig);

  try {
    await client.connect();
    console.log('✅ Connected with custom configuration');

    // Test configuration-specific features
    if (finalConfig.debug) {
      console.log('🐛 Debug mode is enabled');
    }

  } catch (error) {
    console.log('❌ Connection failed, but configuration was valid');
  }
}

/**
 * Example 5: Advanced TypeScript Patterns
 * Shows TypeScript-specific patterns and utilities
 */
async function advancedTypeScriptPatternsExample() {
  console.log('\n=== Advanced TypeScript Patterns Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'typescript-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  // Generic helper functions with type safety
  async function createTypedObject<T extends Record<string, any>>(
    client: GrizabellaClient,
    typeName: string,
    data: T
  ): Promise<ObjectInstance> {
    const instance = createObjectInstance(typeName, data);
    return await client.upsertObject(instance);
  }

  // Type-safe query builder
  class TypedQueryBuilder<T extends Record<string, any>> {
    constructor(
      private client: GrizabellaClient,
      private typeName: string
    ) {}

    async findByProperty<K extends keyof T>(
      property: K,
      value: T[K]
    ): Promise<ObjectInstance[]> {
      return await this.client.findObjects(this.typeName, {
        [property as string]: value,
      });
    }

    async findByRange<K extends keyof T>(
      property: K,
      min: T[K],
      max: T[K]
    ): Promise<ObjectInstance[]> {
      return await this.client.findObjects(this.typeName, {
        [property as string]: { '>=': min, '<=': max },
      });
    }
  }

  // Define interfaces for type safety
  interface UserData {
    name: string;
    email: string;
    age: number;
    department: string;
  }

  interface ProjectData {
    name: string;
    description: string;
    budget: number;
  }

  // Create schema
  await client.createObjectType({
    name: 'User',
    description: 'User with typed properties',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'email', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'age', data_type: PropertyDataType.INTEGER, is_nullable: true },
      { name: 'department', data_type: PropertyDataType.TEXT, is_nullable: true },
    ],
  });

  await client.createObjectType({
    name: 'Project',
    description: 'Project with typed properties',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'description', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'budget', data_type: PropertyDataType.FLOAT, is_nullable: true },
    ],
  });

  // Use typed helpers
  const userData: UserData = {
    name: 'Typed User',
    email: 'typed@example.com',
    age: 30,
    department: 'Engineering',
  };

  const user = await createTypedObject(client, 'User', userData);
  console.log('✅ Created typed user:', user.properties.name);

  const projectData: ProjectData = {
    name: 'Type-Safe Project',
    description: 'A project with type safety',
    budget: 100000,
  };

  const project = await createTypedObject(client, 'Project', projectData);
  console.log('✅ Created typed project:', project.properties.name);

  // Use typed query builder
  const userQuery = new TypedQueryBuilder<UserData>(client, 'User');
  const projectQuery = new TypedQueryBuilder<ProjectData>(client, 'Project');

  const engineers = await userQuery.findByProperty('department', 'Engineering');
  console.log(`✅ Found ${engineers.length} engineers using typed query`);

  const highBudgetProjects = await projectQuery.findByRange('budget', 50000, 200000);
  console.log(`✅ Found ${highBudgetProjects.length} high-budget projects using typed query`);

  // Advanced type utilities
  type ObjectTypeNames = 'User' | 'Project';
  type ObjectData<T extends ObjectTypeNames> =
    T extends 'User' ? UserData :
    T extends 'Project' ? ProjectData :
    never;

  async function createObject<T extends ObjectTypeNames>(
    typeName: T,
    data: ObjectData<T>
  ): Promise<ObjectInstance> {
    return await createTypedObject(client, typeName, data as any);
  }

  // Use advanced typed function
  const typedUser = await createObject('User', {
    name: 'Advanced Typed User',
    email: 'advanced@example.com',
    age: 25,
    department: 'Data Science',
  });

  console.log('✅ Created advanced typed user:', typedUser.properties.name);
}

/**
 * Main function to run all advanced patterns examples
 */
async function main() {
  console.log('🚀 Grizabella TypeScript API - Advanced Patterns Examples\n');

  // Set up global logging
  setGlobalLogger(new ConsoleDebugLogger());

  try {
    await advancedErrorHandlingExample();
    await resourceManagementExample();
    await performanceMonitoringExample();
    await configurationManagementExample();
    await advancedTypeScriptPatternsExample();

    console.log('\n✅ All advanced patterns examples completed successfully!');
  } catch (error) {
    console.error('\n❌ Error running examples:', error);
    process.exit(1);
  }
}

export {
  advancedErrorHandlingExample,
  resourceManagementExample,
  performanceMonitoringExample,
  configurationManagementExample,
  advancedTypeScriptPatternsExample,
};