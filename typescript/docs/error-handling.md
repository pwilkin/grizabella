# Error Handling Guide

Comprehensive guide to error handling in the Grizabella TypeScript API.

## Overview

The Grizabella TypeScript API provides a robust error handling framework designed to help developers handle various failure scenarios gracefully. This guide covers error types, handling patterns, best practices, and recovery strategies.

## Error Hierarchy

```
GrizabellaError (base)
├── ConnectionError        # Connection and network issues
├── NotConnectedError      # Operations attempted while disconnected
├── SchemaError           # Schema definition and validation errors
├── ValidationError       # Data validation errors
├── EmbeddingError        # Embedding-related errors
├── QueryError           # Query execution errors
└── McpProtocolError     # MCP protocol communication errors
```

## Error Properties

All Grizabella errors include the following properties:

```typescript
interface GrizabellaError extends Error {
  readonly category: ErrorCategory;        // Error category
  readonly severity: ErrorSeverity;        // Error severity level
  readonly details?: Record<string, any>;  // Additional context
  readonly cause?: Error;                  // Original cause (if wrapped)
}
```

### Error Categories

- `connection`: Network and connectivity issues
- `validation`: Data validation failures
- `schema`: Schema definition problems
- `query`: Query execution issues
- `embedding`: Vector embedding problems
- `protocol`: MCP communication errors

### Error Severity Levels

- `low`: Minor issues that don't affect core functionality
- `medium`: Issues that may affect some operations
- `high`: Serious issues that affect core functionality
- `critical`: System-level failures requiring immediate attention

## Basic Error Handling

### Try-Catch with Type Guards

```typescript
import { GrizabellaClient, ConnectionError, ValidationError } from 'grizabella-typescript-api';

try {
  const client = new GrizabellaClient({
    dbNameOrPath: 'my-db',
    serverUrl: 'http://localhost:8000/mcp',
  });

  await client.connect();

} catch (error) {
  // Type guard pattern
  if (error instanceof ConnectionError) {
    console.error('Failed to connect:', error.message);
    console.log('Server URL:', error.details?.host);

    // Handle connection-specific recovery
    if (error.details?.retryable) {
      // Retry logic here
    }

  } else if (error instanceof ValidationError) {
    console.error('Configuration validation failed:', error.message);
    console.log('Validation errors:', error.details?.errors);

  } else if (error instanceof GrizabellaError) {
    console.error('Grizabella error:', error.message);
    console.log('Category:', error.category);
    console.log('Severity:', error.severity);

  } else {
    console.error('Unknown error:', error);
  }
}
```

### Async Error Handling

```typescript
async function performDatabaseOperation(): Promise<void> {
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'my-db',
    serverUrl: 'http://localhost:8000/mcp',
  });

  try {
    const result = await client.findObjects('Person', { active: true });
    console.log('Found', result.length, 'active people');

  } catch (error) {
    // Handle different error types appropriately
    if (error instanceof NotConnectedError) {
      console.error('Client disconnected during operation');
      // Reconnection logic might be appropriate here

    } else if (error instanceof QueryError) {
      console.error('Query failed:', error.message);
      console.log('Query details:', error.details?.query);

    } else {
      console.error('Unexpected error:', error);
    }

    throw error; // Re-throw if caller should handle it
  }
}
```

## Advanced Error Handling Patterns

### Retry Logic

Use the built-in retry utility for transient failures:

```typescript
import { withRetry, DEFAULT_RETRY_CONFIG } from 'grizabella-typescript-api';

// Custom retry configuration
const retryConfig = {
  ...DEFAULT_RETRY_CONFIG,
  maxAttempts: 3,
  baseDelay: 1000,
  maxDelay: 5000,
  backoffFactor: 2,
};

// Retry with custom configuration
const result = await withRetry(
  async () => {
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: 'my-db',
      serverUrl: 'http://localhost:8000/mcp',
    });

    return await client.findObjects('Person');
  },
  retryConfig
);
```

### Error Boundaries

Create error boundaries to handle errors gracefully:

```typescript
import { createErrorBoundary } from 'grizabella-typescript-api';

async function processUserData(userId: string) {
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'user-db',
    serverUrl: 'http://localhost:8000/mcp',
  });

  // Create error boundary for user operations
  const userOperationBoundary = createErrorBoundary({
    onError: (error: Error) => {
      console.error(`User operation failed for ${userId}:`, error.message);

      // Log to monitoring system
      logError(error, { userId, operation: 'processUserData' });

      return { fallback: null, error: true };
    },
    shouldCatch: (error) => error instanceof QueryError || error instanceof ValidationError,
  });

  const result = await userOperationBoundary(async () => {
    const user = await client.getObjectById(userId, 'User');
    if (!user) {
      throw new ValidationError('User not found', { userId });
    }

    // Process user data
    const updatedUser = {
      ...user,
      properties: {
        ...user.properties,
        lastProcessed: new Date(),
      },
    };

    return await client.upsertObject(updatedUser);
  });

  if (result.error) {
    console.log('Operation failed, using fallback');
    return null;
  }

  return result;
}
```

### Circuit Breaker Pattern

Implement circuit breaker for external service failures:

```typescript
class CircuitBreaker {
  private failures = 0;
  private lastFailureTime = 0;
  private readonly threshold = 5;
  private readonly timeout = 60000; // 1 minute

  async execute<T>(operation: () => Promise<T>): Promise<T> {
    if (this.isOpen) {
      throw new Error('Circuit breaker is open');
    }

    try {
      const result = await operation();
      this.onSuccess();
      return result;

    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private get isOpen(): boolean {
    if (this.failures >= this.threshold) {
      const timeSinceLastFailure = Date.now() - this.lastFailureTime;
      if (timeSinceLastFailure < this.timeout) {
        return true; // Still in open state
      } else {
        // Half-open: allow one request to test
        this.failures = Math.floor(this.threshold / 2);
        return false;
      }
    }
    return false;
  }

  private onSuccess(): void {
    this.failures = 0;
  }

  private onFailure(): void {
    this.failures++;
    this.lastFailureTime = Date.now();
  }
}

// Usage with database operations
const circuitBreaker = new CircuitBreaker();

const result = await circuitBreaker.execute(async () => {
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'my-db',
    serverUrl: 'http://localhost:8000/mcp',
  });

  return await client.findObjects('Person');
});
```

## Specific Error Scenarios

### Connection Errors

```typescript
try {
  await client.connect();
} catch (error) {
  if (error instanceof ConnectionError) {
    switch (error.details?.reason) {
      case 'timeout':
        console.log('Connection timed out. Check network connectivity.');
        break;
      case 'invalid_url':
        console.log('Invalid server URL format.');
        break;
      case 'server_error':
        console.log('Server returned an error. Check server logs.');
        break;
      default:
        console.log('Unknown connection error:', error.message);
    }
  }
}
```

### Schema Validation Errors

```typescript
try {
  await client.createObjectType({
    name: 'User',
    properties: [
      {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_unique: true,
        // Missing required 'is_nullable' field
      },
    ],
  });
} catch (error) {
  if (error instanceof SchemaError) {
    console.error('Schema validation failed:');
    error.details?.validationErrors?.forEach(validationError => {
      console.log(`- ${validationError.field}: ${validationError.message}`);
    });
  }
}
```

### Data Validation Errors

```typescript
import { validateObjectInstance } from 'grizabella-typescript-api';

const userData = {
  id: 'user-1',
  object_type_name: 'User',
  weight: new Decimal('1.0'),
  upsert_date: new Date(),
  properties: {
    name: '', // Empty name should fail validation
    email: 'invalid-email', // Invalid email format
  },
};

const userType = await client.getObjectType('User');
const validation = validateObjectInstance(userData, userType!);

if (!validation.isValid) {
  console.error('Validation failed:');
  validation.errors.forEach(error => {
    console.log(`- ${error.field}: ${error.message}`);
  });

  // Don't proceed with invalid data
  return;
}

// Data is valid, proceed with operation
await client.upsertObject(userData);
```

### Query Errors

```typescript
try {
  const result = await client.findObjects('User', {
    age: { '>': 25 },
    department: 'invalid_department', // This might cause issues
  });
} catch (error) {
  if (error instanceof QueryError) {
    console.error('Query execution failed:', error.message);
    console.log('Query details:', error.details?.query);
    console.log('Filter criteria:', error.details?.filterCriteria);

    // Check if it's a syntax error
    if (error.details?.type === 'syntax') {
      console.log('Try simplifying your query filters');
    }

    // Check if it's a timeout
    if (error.details?.type === 'timeout') {
      console.log('Query timed out. Try reducing result size or adding more specific filters.');
    }
  }
}
```

## Best Practices

### 1. Always Use Specific Error Types

```typescript
// ❌ Avoid generic error handling
try {
  await client.connect();
} catch (error) {
  console.log('Something went wrong');
}

// ✅ Use specific error types
try {
  await client.connect();
} catch (error) {
  if (error instanceof ConnectionError) {
    // Handle connection errors specifically
  } else if (error instanceof ValidationError) {
    // Handle validation errors specifically
  }
}
```

### 2. Implement Proper Logging

```typescript
import { setGlobalLogger, ConsoleDebugLogger } from 'grizabella-typescript-api';

// Enable detailed logging
setGlobalLogger(new ConsoleDebugLogger());

try {
  await client.connect();
} catch (error) {
  // Log with context
  logError(error, {
    operation: 'database_connect',
    timestamp: new Date(),
    config: { serverUrl: 'http://localhost:8000/mcp' },
  });
}
```

### 3. Use Resource Management

```typescript
// ✅ Good: Context manager handles cleanup
await using client = await GrizabellaClient.connect(config);

// ❌ Bad: Manual cleanup can be forgotten
const client = new GrizabellaClient(config);
await client.connect();
// ... operations ...
// Forgot to call client.close()
```

### 4. Implement Graceful Degradation

```typescript
async function getUserData(userId: string) {
  try {
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: 'user-db',
      serverUrl: 'http://localhost:8000/mcp',
    });

    return await client.getObjectById(userId, 'User');

  } catch (error) {
    console.error('Failed to get user data:', error);

    // Return cached data or default values
    return getCachedUserData(userId) || {
      id: userId,
      properties: { name: 'Unknown User' },
    };
  }
}
```

### 5. Handle Batch Operation Failures

```typescript
import { processObjectInstancesBatch } from 'grizabella-typescript-api';

const results = await processObjectInstancesBatch(
  client,
  userBatch,
  async (user) => {
    try {
      return await client.upsertObject(user);
    } catch (error) {
      console.error(`Failed to process user ${user.id}:`, error);
      // Return null for failed items
      return null;
    }
  },
  { batchSize: 10 }
);

// Separate successful and failed operations
const successful = results.filter(r => r !== null);
const failed = results.filter(r => r === null);

console.log(`Processed ${successful.length} users successfully, ${failed.length} failed`);
```

### 6. Implement Circuit Breakers for Production

```typescript
class DatabaseService {
  private circuitBreaker = new CircuitBreaker();
  private client?: GrizabellaClient;

  async queryUsers(criteria: any) {
    return await this.circuitBreaker.execute(async () => {
      if (!this.client) {
        this.client = await GrizabellaClient.connect({
          dbNameOrPath: 'production-db',
          serverUrl: process.env.DATABASE_URL!,
        });
      }

      return await this.client.findObjects('User', criteria);
    });
  }
}
```

### 7. Use Error Context for Debugging

```typescript
async function processOrder(orderId: string) {
  const context = {
    operation: 'processOrder',
    orderId,
    timestamp: new Date(),
    userId: getCurrentUserId(),
  };

  try {
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: 'orders-db',
      serverUrl: 'http://localhost:8000/mcp',
    });

    const order = await client.getObjectById(orderId, 'Order');
    if (!order) {
      throw new ValidationError('Order not found', { orderId, ...context });
    }

    // Process order...
    const result = await client.upsertObject({
      ...order,
      properties: {
        ...order.properties,
        status: 'processed',
        processedAt: new Date(),
      },
    });

    return result;

  } catch (error) {
    // Add context to error
    if (error instanceof GrizabellaError) {
      error.details = { ...error.details, ...context };
    }

    throw error;
  }
}
```

## Error Recovery Strategies

### Automatic Retry with Exponential Backoff

```typescript
async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  maxAttempts: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error as Error;

      // Don't retry certain errors
      if (error instanceof ValidationError || error instanceof SchemaError) {
        throw error;
      }

      if (attempt < maxAttempts) {
        const delay = baseDelay * Math.pow(2, attempt - 1);
        console.log(`Attempt ${attempt} failed, retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError!;
}
```

### Graceful Service Degradation

```typescript
class UserService {
  private cache = new Map<string, any>();
  private dbAvailable = true;

  async getUser(userId: string) {
    // Try database first
    if (this.dbAvailable) {
      try {
        const client = await GrizabellaClient.connect({
          dbNameOrPath: 'user-db',
          serverUrl: process.env.DATABASE_URL!,
        });

        const user = await client.getObjectById(userId, 'User');
        if (user) {
          // Cache successful result
          this.cache.set(userId, user);
          return user;
        }

      } catch (error) {
        console.error('Database unavailable:', error);
        this.dbAvailable = false;

        // Set timer to check database availability later
        setTimeout(() => {
          this.dbAvailable = true;
        }, 30000); // 30 seconds
      }
    }

    // Fallback to cache
    const cachedUser = this.cache.get(userId);
    if (cachedUser) {
      console.log('Serving user from cache');
      return cachedUser;
    }

    // Final fallback
    return {
      id: userId,
      properties: { name: 'Unknown User', fromCache: false },
    };
  }
}
```

## Monitoring and Alerting

### Error Metrics Collection

```typescript
import { logError, setGlobalErrorLogger } from 'grizabella-typescript-api';

// Custom error logger for monitoring
class MonitoringErrorLogger {
  logError(error: GrizabellaError, context?: Record<string, any>) {
    // Send to monitoring service
    monitoring.trackError({
      message: error.message,
      category: error.category,
      severity: error.severity,
      details: error.details,
      context,
      stack: error.stack,
    });

    // Send alerts for critical errors
    if (error.severity === 'critical') {
      alerting.sendAlert({
        title: 'Critical Grizabella Error',
        message: error.message,
        details: error.details,
      });
    }
  }
}

// Set global error logger
setGlobalErrorLogger(new MonitoringErrorLogger());
```

### Health Checks

```typescript
async function healthCheck(): Promise<HealthStatus> {
  const checks = {
    database: false,
    schema: false,
    connectivity: false,
  };

  try {
    // Check database connectivity
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: 'health-check-db',
      serverUrl: 'http://localhost:8000/mcp',
      timeout: 5000,
    });
    checks.connectivity = true;

    // Check basic operations
    await client.findObjects('HealthCheck', {}, 1);
    checks.database = true;

    // Check schema
    const types = await client.listObjectTypes();
    checks.schema = types.length > 0;

  } catch (error) {
    console.error('Health check failed:', error);
  }

  return {
    status: Object.values(checks).every(Boolean) ? 'healthy' : 'unhealthy',
    checks,
    timestamp: new Date(),
  };
}
```

This comprehensive error handling guide provides patterns and best practices for building robust applications with the Grizabella TypeScript API. Remember to always handle errors appropriately for your specific use case and environment.