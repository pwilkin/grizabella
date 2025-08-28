# Best Practices Guide

Comprehensive guide to best practices for using the Grizabella TypeScript API effectively in production applications.

## Table of Contents

- [Project Structure](#project-structure)
- [TypeScript Configuration](#typescript-configuration)
- [Connection Management](#connection-management)
- [Schema Design](#schema-design)
- [Data Operations](#data-operations)
- [Error Handling](#error-handling)
- [Performance Optimization](#performance-optimization)
- [Testing](#testing)
- [Security](#security)
- [Monitoring and Observability](#monitoring-and-observability)

## Project Structure

### Recommended Directory Structure

```
my-grizabella-app/
├── src/
│   ├── config/
│   │   ├── database.ts          # Database configuration
│   │   ├── index.ts             # Configuration exports
│   │   └── types.ts             # Shared configuration types
│   ├── database/
│   │   ├── client.ts            # Grizabella client setup
│   │   ├── schemas/             # Schema definitions
│   │   │   ├── user.ts
│   │   │   ├── product.ts
│   │   │   └── index.ts
│   │   ├── repositories/        # Data access layer
│   │   │   ├── user-repository.ts
│   │   │   ├── product-repository.ts
│   │   │   └── base-repository.ts
│   │   └── services/            # Business logic
│   │       ├── user-service.ts
│   │       ├── product-service.ts
│   │       └── index.ts
│   ├── types/
│   │   ├── domain.ts            # Domain-specific types
│   │   ├── api.ts               # API response types
│   │   └── index.ts
│   ├── utils/
│   │   ├── validation.ts        # Validation helpers
│   │   ├── error-handling.ts    # Error handling utilities
│   │   └── index.ts
│   └── index.ts                 # Main application entry
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
├── scripts/
├── .env.example
├── package.json
└── tsconfig.json
```

### File Organization Principles

1. **Separate concerns**: Keep database logic separate from business logic
2. **Use repositories**: Abstract data access behind repository pattern
3. **Centralize configuration**: Keep all configuration in one place
4. **Type safety**: Define clear interfaces for all data structures
5. **Error boundaries**: Implement error handling at appropriate layers

## TypeScript Configuration

### Recommended tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022"],
    "module": "CommonJS",
    "moduleResolution": "node",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "noImplicitThis": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noPropertyAccessFromIndexSignature": true,
    "noImplicitReturns": true,
    "allowSyntheticDefaultImports": true,
    "esModuleInterop": true,
    "skipLibCheck": false,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "types": ["node"]
  },
  "include": [
    "src/**/*"
  ],
  "exclude": [
    "node_modules",
    "dist",
    "tests"
  ]
}
```

### TypeScript Best Practices

```typescript
// ✅ Good: Use strict typing
interface UserData {
  readonly id: string;
  readonly name: string;
  readonly email: string;
  readonly age: number;
  readonly department: string;
  readonly isActive: boolean;
  readonly createdAt: Date;
}

// ❌ Bad: Avoid any types
interface LooseUser {
  id: any;
  name: any;
  data: any;
}

// ✅ Good: Use union types for specific values
type UserStatus = 'active' | 'inactive' | 'suspended';

// ✅ Good: Use generics for reusable components
class Repository<T extends { id: string }> {
  async findById(id: string): Promise<T | null> {
    // Implementation
    return null;
  }

  async save(entity: T): Promise<T> {
    // Implementation
    return entity;
  }
}

// ✅ Good: Use branded types for type safety
type UserId = string & { readonly __brand: 'UserId' };
type ProductId = string & { readonly __brand: 'ProductId' };

function createUserId(id: string): UserId {
  return id as UserId;
}
```

## Connection Management

### Connection Pooling Strategy

```typescript
// config/database.ts
export interface DatabaseConfig {
  readonly primary: GrizabellaClientConfig;
  readonly readReplicas?: GrizabellaClientConfig[];
  readonly pool: {
    readonly minConnections: number;
    readonly maxConnections: number;
    readonly acquireTimeout: number;
    readonly idleTimeout: number;
  };
}

// database/client.ts
export class DatabaseClientManager {
  private clients: Map<string, GrizabellaClient> = new Map();
  private connectionPool: ConnectionPool;

  constructor(private config: DatabaseConfig) {
    this.connectionPool = new ConnectionPool(config.pool);
  }

  async getClient(name: string = 'primary'): Promise<GrizabellaClient> {
    if (!this.clients.has(name)) {
      const clientConfig = name === 'primary'
        ? this.config.primary
        : this.config.readReplicas?.find(r => r.name === name);

      if (!clientConfig) {
        throw new Error(`Database client '${name}' not configured`);
      }

      const client = new GrizabellaClient(clientConfig);
      await client.connect();

      this.clients.set(name, client);
    }

    return this.clients.get(name)!;
  }

  async closeAll(): Promise<void> {
    for (const [name, client] of this.clients) {
      try {
        await client.close();
      } catch (error) {
        console.error(`Error closing client ${name}:`, error);
      }
    }
    this.clients.clear();
  }
}
```

### Context Manager Pattern

```typescript
// ✅ Recommended: Use context managers
export async function processUserData(userId: string) {
  await using client = await databaseManager.getClient('primary');

  // Client automatically closed when scope ends
  return await client.getObjectById(userId, 'User');
}

// For operations requiring multiple clients
export async function syncUserData(userId: string) {
  await using primaryClient = await databaseManager.getClient('primary');
  await using replicaClient = await databaseManager.getClient('replica-1');

  const user = await primaryClient.getObjectById(userId, 'User');
  const profile = await replicaClient.getObjectById(`${userId}_profile`, 'UserProfile');

  return { user, profile };
}
```

### Connection Health Checks

```typescript
export class DatabaseHealthChecker {
  private lastCheck = 0;
  private readonly checkInterval = 30000; // 30 seconds

  async isHealthy(client: GrizabellaClient): Promise<boolean> {
    try {
      // Simple health check query
      const result = await client.findObjects('HealthCheck', {}, 1);
      return true;
    } catch (error) {
      console.error('Health check failed:', error);
      return false;
    }
  }

  async ensureHealthy(client: GrizabellaClient): Promise<void> {
    const now = Date.now();
    if (now - this.lastCheck > this.checkInterval) {
      const healthy = await this.isHealthy(client);
      if (!healthy) {
        throw new Error('Database health check failed');
      }
      this.lastCheck = now;
    }
  }
}
```

## Schema Design

### Schema Design Principles

1. **Use meaningful names**: Choose clear, descriptive names for object types and properties
2. **Plan for growth**: Design schemas that can accommodate future requirements
3. **Use appropriate data types**: Choose the most specific data type for each property
4. **Establish relationships early**: Plan your relationship types alongside object types
5. **Consider indexing**: Identify properties that will be frequently queried
6. **Document your schema**: Include descriptions for all types and properties

### Schema Definition Best Practices

```typescript
// schemas/user.ts
export const USER_SCHEMA: ObjectTypeDefinition = {
  name: 'User',
  description: 'Represents a user account in the system',
  properties: [
    {
      name: 'email',
      data_type: PropertyDataType.TEXT,
      is_nullable: false,
      is_unique: true,
      is_indexed: true,
      description: 'User email address (must be unique)',
    },
    {
      name: 'first_name',
      data_type: PropertyDataType.TEXT,
      is_nullable: false,
      description: 'User first name',
    },
    {
      name: 'last_name',
      data_type: PropertyDataType.TEXT,
      is_nullable: false,
      description: 'User last name',
    },
    {
      name: 'age',
      data_type: PropertyDataType.INTEGER,
      is_nullable: true,
      is_indexed: true,
      description: 'User age in years',
    },
    {
      name: 'department',
      data_type: PropertyDataType.TEXT,
      is_nullable: true,
      is_indexed: true,
      description: 'User department',
    },
    {
      name: 'is_active',
      data_type: PropertyDataType.BOOLEAN,
      is_nullable: false,
      description: 'Whether the user account is active',
    },
    {
      name: 'created_at',
      data_type: PropertyDataType.DATETIME,
      is_nullable: false,
      is_indexed: true,
      description: 'When the user account was created',
    },
    {
      name: 'updated_at',
      data_type: PropertyDataType.DATETIME,
      is_nullable: false,
      description: 'When the user account was last updated',
    },
  ],
};

// Relationship schemas
export const USER_DEPARTMENT_RELATION: RelationTypeDefinition = {
  name: 'BELONGS_TO_DEPARTMENT',
  description: 'User belongs to a department',
  source_object_type_names: ['User'],
  target_object_type_names: ['Department'],
  properties: [
    {
      name: 'joined_at',
      data_type: PropertyDataType.DATETIME,
      is_nullable: false,
      description: 'When the user joined the department',
    },
    {
      name: 'role',
      data_type: PropertyDataType.TEXT,
      is_nullable: true,
      description: 'User role within the department',
    },
  ],
};
```

### Schema Versioning

```typescript
export class SchemaManager {
  private readonly schemaVersion = '1.0.0';

  async ensureSchema(client: GrizabellaClient): Promise<void> {
    // Check if schema version exists
    const versionCheck = await client.findObjects('SchemaVersion', {
      version: this.schemaVersion
    });

    if (versionCheck.length === 0) {
      // Apply schema migrations
      await this.applyMigrations(client);

      // Record schema version
      await client.upsertObject({
        id: `schema-${this.schemaVersion}`,
        object_type_name: 'SchemaVersion',
        weight: new Decimal('1.0'),
        upsert_date: new Date(),
        properties: {
          version: this.schemaVersion,
          applied_at: new Date(),
          description: 'User management schema v1.0.0',
        },
      });
    }
  }

  private async applyMigrations(client: GrizabellaClient): Promise<void> {
    // Create object types
    await client.createObjectType(USER_SCHEMA);

    // Create relation types
    await client.createRelationType(USER_DEPARTMENT_RELATION);

    // Create embedding definitions if needed
    // await client.createEmbeddingDefinition(...);
  }
}
```

## Data Operations

### Repository Pattern

```typescript
// repositories/base-repository.ts
export abstract class BaseRepository<T extends { id: string }> {
  protected client: GrizabellaClient;

  constructor(client: GrizabellaClient) {
    this.client = client;
  }

  abstract getObjectTypeName(): string;

  async findById(id: string): Promise<T | null> {
    try {
      const result = await this.client.getObjectById(id, this.getObjectTypeName());
      return result as T | null;
    } catch (error) {
      if (error instanceof QueryError) {
        console.error(`Error finding ${this.getObjectTypeName()} by ID:`, error);
        return null;
      }
      throw error;
    }
  }

  async findAll(criteria?: Record<string, any>, limit?: number): Promise<T[]> {
    try {
      const results = await this.client.findObjects(this.getObjectTypeName(), criteria, limit);
      return results as T[];
    } catch (error) {
      if (error instanceof QueryError) {
        console.error(`Error finding ${this.getObjectTypeName()}:`, error);
        return [];
      }
      throw error;
    }
  }

  async save(entity: T): Promise<T> {
    try {
      const objectInstance = await this.client.upsertObject(entity as any);
      return objectInstance as T;
    } catch (error) {
      console.error(`Error saving ${this.getObjectTypeName()}:`, error);
      throw error;
    }
  }

  async delete(id: string): Promise<boolean> {
    try {
      return await this.client.deleteObject(id, this.getObjectTypeName());
    } catch (error) {
      console.error(`Error deleting ${this.getObjectTypeName()}:`, error);
      return false;
    }
  }
}

// repositories/user-repository.ts
export interface User {
  readonly id: string;
  readonly email: string;
  readonly first_name: string;
  readonly last_name: string;
  readonly age?: number;
  readonly department?: string;
  readonly is_active: boolean;
  readonly created_at: Date;
  readonly updated_at: Date;
}

export class UserRepository extends BaseRepository<User> {
  getObjectTypeName(): string {
    return 'User';
  }

  async findByEmail(email: string): Promise<User | null> {
    const users = await this.findAll({ email }, 1);
    return users.length > 0 ? users[0] : null;
  }

  async findByDepartment(department: string): Promise<User[]> {
    return await this.findAll({ department });
  }

  async findActiveUsers(): Promise<User[]> {
    return await this.findAll({ is_active: true });
  }

  async updateUser(id: string, updates: Partial<User>): Promise<User | null> {
    const existingUser = await this.findById(id);
    if (!existingUser) {
      return null;
    }

    const updatedUser = {
      ...existingUser,
      ...updates,
      updated_at: new Date(),
    };

    return await this.save(updatedUser);
  }
}
```

### Service Layer

```typescript
// services/user-service.ts
export class UserService {
  constructor(
    private userRepository: UserRepository,
    private schemaManager: SchemaManager
  ) {}

  async initialize(): Promise<void> {
    await using client = await databaseManager.getClient();
    await this.schemaManager.ensureSchema(client);
  }

  async createUser(userData: Omit<User, 'id' | 'created_at' | 'updated_at'>): Promise<User> {
    await using client = await databaseManager.getClient();

    // Validate user data
    if (!userData.email || !userData.first_name || !userData.last_name) {
      throw new ValidationError('Missing required user fields');
    }

    // Check if email already exists
    const existingUser = await this.userRepository.findByEmail(userData.email);
    if (existingUser) {
      throw new ValidationError('Email already exists');
    }

    // Create user object
    const user: User = {
      id: generateUserId(),
      ...userData,
      created_at: new Date(),
      updated_at: new Date(),
    };

    return await this.userRepository.save(user);
  }

  async getUserById(id: string): Promise<User | null> {
    return await this.userRepository.findById(id);
  }

  async updateUser(id: string, updates: Partial<User>): Promise<User | null> {
    return await this.userRepository.updateUser(id, updates);
  }

  async deactivateUser(id: string): Promise<boolean> {
    const result = await this.userRepository.updateUser(id, {
      is_active: false,
      updated_at: new Date(),
    });

    return result !== null;
  }

  async getUsersByDepartment(department: string): Promise<User[]> {
    return await this.userRepository.findByDepartment(department);
  }
}
```

## Error Handling

### Global Error Handling Strategy

```typescript
// utils/error-handling.ts
export class ErrorHandler {
  static handle(error: unknown, context?: Record<string, any>): never {
    if (error instanceof GrizabellaError) {
      this.handleGrizabellaError(error, context);
    } else if (error instanceof Error) {
      this.handleGenericError(error, context);
    } else {
      this.handleUnknownError(error, context);
    }
  }

  private static handleGrizabellaError(error: GrizabellaError, context?: Record<string, any>): never {
    // Log error with context
    console.error('Grizabella Error:', {
      message: error.message,
      category: error.category,
      severity: error.severity,
      details: error.details,
      context,
      stack: error.stack,
    });

    // Send to monitoring service
    monitoring.trackError(error, context);

    // Determine if error should be retried
    if (this.isRetryable(error)) {
      throw new RetryableError(error.message, error);
    }

    throw error;
  }

  private static isRetryable(error: GrizabellaError): boolean {
    return error.category === 'connection' && error.severity !== 'critical';
  }

  private static handleGenericError(error: Error, context?: Record<string, any>): never {
    console.error('Generic Error:', {
      message: error.message,
      context,
      stack: error.stack,
    });

    monitoring.trackError(error, context);
    throw error;
  }

  private static handleUnknownError(error: unknown, context?: Record<string, any>): never {
    console.error('Unknown Error:', {
      error: String(error),
      context,
    });

    monitoring.trackError(error, context);
    throw new Error(`Unknown error: ${String(error)}`);
  }
}

// Usage in services
export class BaseService {
  protected async handleOperation<T>(
    operation: () => Promise<T>,
    context?: Record<string, any>
  ): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      ErrorHandler.handle(error, context);
    }
  }
}
```

### Retry Logic

```typescript
// utils/retry.ts
export interface RetryConfig {
  readonly maxAttempts: number;
  readonly baseDelay: number;
  readonly maxDelay: number;
  readonly backoffFactor: number;
  readonly retryableErrors: string[];
}

export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxAttempts: 3,
  baseDelay: 1000,
  maxDelay: 10000,
  backoffFactor: 2,
  retryableErrors: ['ConnectionError', 'TimeoutError'],
};

export async function withRetry<T>(
  operation: () => Promise<T>,
  config: RetryConfig = DEFAULT_RETRY_CONFIG
): Promise<T> {
  let lastError: Error;

  for (let attempt = 1; attempt <= config.maxAttempts; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error as Error;

      if (attempt === config.maxAttempts || !shouldRetry(error, config)) {
        break;
      }

      const delay = Math.min(
        config.baseDelay * Math.pow(config.backoffFactor, attempt - 1),
        config.maxDelay
      );

      console.log(`Attempt ${attempt} failed, retrying in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError!;
}

function shouldRetry(error: unknown, config: RetryConfig): boolean {
  if (!(error instanceof GrizabellaError)) {
    return false;
  }

  return config.retryableErrors.some(errorType =>
    error.constructor.name === errorType
  );
}
```

## Performance Optimization

### Query Optimization

```typescript
// services/optimized-user-service.ts
export class OptimizedUserService extends UserService {
  private readonly BATCH_SIZE = 100;

  async bulkCreateUsers(users: Omit<User, 'id' | 'created_at' | 'updated_at'>[]): Promise<User[]> {
    const results: User[] = [];

    // Process in batches
    for (let i = 0; i < users.length; i += this.BATCH_SIZE) {
      const batch = users.slice(i, i + this.BATCH_SIZE);
      const createdUsers = await this.createUserBatch(batch);
      results.push(...createdUsers);
    }

    return results;
  }

  private async createUserBatch(users: Omit<User, 'id' | 'created_at' | 'updated_at'>[]): Promise<User[]> {
    await using client = await databaseManager.getClient();

    // Pre-validate all users
    const validatedUsers = users.map(user => {
      if (!user.email || !user.first_name || !user.last_name) {
        throw new ValidationError('Missing required user fields');
      }
      return user;
    });

    // Create user objects
    const userObjects = validatedUsers.map(user => ({
      id: generateUserId(),
      ...user,
      created_at: new Date(),
      updated_at: new Date(),
    }));

    // Batch create
    const createdUsers = await createMultipleObjectInstances(
      client,
      'User',
      userObjects
    );

    return createdUsers as User[];
  }

  async searchUsers(query: string): Promise<User[]> {
    await using client = await databaseManager.getClient();

    // Use embedding search if available
    try {
      const searchResults = await client.findSimilar(
        'user_biography_embedding',
        query,
        10
      );

      // Get full user objects
      const userIds = searchResults.map(result => result.object.properties.id);
      const users = await Promise.all(
        userIds.map(id => this.getUserById(id))
      );

      return users.filter(user => user !== null) as User[];

    } catch (error) {
      // Fallback to traditional search
      console.log('Embedding search not available, using fallback');
      return await this.userRepository.findAll({
        first_name: { 'LIKE': `%${query}%` }
      });
    }
  }
}
```

### Caching Strategy

```typescript
// utils/cache.ts
export class Cache<T> {
  private cache = new Map<string, { data: T; timestamp: number }>();
  private readonly ttl: number;

  constructor(ttlMs: number = 300000) { // 5 minutes default
    this.ttl = ttlMs;
  }

  get(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) {
      return null;
    }

    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }

    return entry.data;
  }

  set(key: string, value: T): void {
    this.cache.set(key, {
      data: value,
      timestamp: Date.now(),
    });
  }

  clear(): void {
    this.cache.clear();
  }

  size(): number {
    return this.cache.size;
  }
}

// services/cached-user-service.ts
export class CachedUserService extends UserService {
  private cache = new Cache<User>(300000); // 5 minute TTL

  async getUserById(id: string): Promise<User | null> {
    // Check cache first
    const cached = this.cache.get(id);
    if (cached) {
      return cached;
    }

    // Fetch from database
    const user = await super.getUserById(id);
    if (user) {
      this.cache.set(id, user);
    }

    return user;
  }

  async updateUser(id: string, updates: Partial<User>): Promise<User | null> {
    const updatedUser = await super.updateUser(id, updates);

    // Update cache
    if (updatedUser) {
      this.cache.set(id, updatedUser);
    }

    return updatedUser;
  }
}
```

## Testing

### Unit Testing

```typescript
// tests/repositories/user-repository.test.ts
import { UserRepository } from '../../src/repositories/user-repository';
import { createMockClient } from '../mocks/database-client';

describe('UserRepository', () => {
  let repository: UserRepository;
  let mockClient: jest.Mocked<GrizabellaClient>;

  beforeEach(() => {
    mockClient = createMockClient();
    repository = new UserRepository(mockClient);
  });

  describe('findById', () => {
    it('should return user when found', async () => {
      const mockUser = createMockUser();
      mockClient.getObjectById.mockResolvedValue(mockUser);

      const result = await repository.findById('user-1');

      expect(result).toEqual(mockUser);
      expect(mockClient.getObjectById).toHaveBeenCalledWith('user-1', 'User');
    });

    it('should return null when not found', async () => {
      mockClient.getObjectById.mockResolvedValue(null);

      const result = await repository.findById('non-existent');

      expect(result).toBeNull();
    });

    it('should handle errors gracefully', async () => {
      mockClient.getObjectById.mockRejectedValue(new Error('Database error'));

      const result = await repository.findById('user-1');

      expect(result).toBeNull();
    });
  });
});
```

### Integration Testing

```typescript
// tests/integration/user-service.integration.test.ts
describe('UserService Integration', () => {
  let service: UserService;
  let testDb: TestDatabase;

  beforeEach(async () => {
    testDb = new TestDatabase();
    await testDb.setup();

    const client = await testDb.getClient();
    const repository = new UserRepository(client);
    const schemaManager = new SchemaManager();

    service = new UserService(repository, schemaManager);
    await service.initialize();
  });

  afterEach(async () => {
    await testDb.cleanup();
  });

  describe('createUser', () => {
    it('should create a user successfully', async () => {
      const userData = {
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        is_active: true,
      };

      const user = await service.createUser(userData);

      expect(user).toBeDefined();
      expect(user?.email).toBe(userData.email);
      expect(user?.first_name).toBe(userData.first_name);
      expect(user?.is_active).toBe(true);
    });

    it('should prevent duplicate emails', async () => {
      const userData = {
        email: 'duplicate@example.com',
        first_name: 'Test',
        last_name: 'User',
        is_active: true,
      };

      await service.createUser(userData);

      await expect(service.createUser(userData)).rejects.toThrow(ValidationError);
    });
  });
});
```

## Security

### Input Validation

```typescript
// utils/validation.ts
export class ValidationService {
  static validateEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  static sanitizeString(input: string): string {
    return input.trim().replace(/[<>]/g, '');
  }

  static validateUserData(data: Partial<User>): ValidationResult {
    const errors: string[] = [];

    if (data.email && !this.validateEmail(data.email)) {
      errors.push('Invalid email format');
    }

    if (data.first_name && data.first_name.length < 2) {
      errors.push('First name must be at least 2 characters');
    }

    if (data.last_name && data.last_name.length < 2) {
      errors.push('Last name must be at least 2 characters');
    }

    if (data.age && (data.age < 0 || data.age > 150)) {
      errors.push('Age must be between 0 and 150');
    }

    return {
      isValid: errors.length === 0,
      errors,
    };
  }
}
```

### Authentication and Authorization

```typescript
// services/auth-service.ts
export class AuthService {
  constructor(private userRepository: UserRepository) {}

  async authenticateUser(email: string, password: string): Promise<User | null> {
    const user = await this.userRepository.findByEmail(email);
    if (!user) {
      return null;
    }

    // Verify password (implementation depends on your auth system)
    const isValidPassword = await this.verifyPassword(password, user.password_hash);
    if (!isValidPassword) {
      return null;
    }

    return user;
  }

  async authorizeUser(userId: string, action: string, resource: string): Promise<boolean> {
    const user = await this.userRepository.findById(userId);
    if (!user) {
      return false;
    }

    // Check user permissions based on roles, groups, etc.
    return this.checkPermissions(user, action, resource);
  }

  private async verifyPassword(password: string, hash: string): Promise<boolean> {
    // Implementation depends on your password hashing strategy
    return await bcrypt.compare(password, hash);
  }

  private checkPermissions(user: User, action: string, resource: string): boolean {
    // Implementation depends on your authorization system
    // This could check roles, permissions, resource ownership, etc.
    return true; // Placeholder
  }
}
```

## Monitoring and Observability

### Metrics Collection

```typescript
// utils/metrics.ts
export class MetricsCollector {
  private metrics: Map<string, { count: number; sum: number; min: number; max: number }> = new Map();

  recordMetric(name: string, value: number): void {
    const current = this.metrics.get(name) || {
      count: 0,
      sum: 0,
      min: Infinity,
      max: -Infinity,
    };

    current.count++;
    current.sum += value;
    current.min = Math.min(current.min, value);
    current.max = Math.max(current.max, value);

    this.metrics.set(name, current);
  }

  getMetrics(): Record<string, { count: number; average: number; min: number; max: number }> {
    const result: Record<string, any> = {};

    for (const [name, data] of this.metrics) {
      result[name] = {
        count: data.count,
        average: data.sum / data.count,
        min: data.min,
        max: data.max,
      };
    }

    return result;
  }

  reset(): void {
    this.metrics.clear();
  }
}

// Global metrics instance
export const metrics = new MetricsCollector();

// Usage in services
export class MonitoredUserService extends UserService {
  async getUserById(id: string): Promise<User | null> {
    const startTime = Date.now();

    try {
      const user = await super.getUserById(id);
      const duration = Date.now() - startTime;

      metrics.recordMetric('user_service.get_user_by_id.duration', duration);
      metrics.recordMetric('user_service.get_user_by_id.success', 1);

      return user;
    } catch (error) {
      const duration = Date.now() - startTime;
      metrics.recordMetric('user_service.get_user_by_id.duration', duration);
      metrics.recordMetric('user_service.get_user_by_id.error', 1);
      throw error;
    }
  }
}
```

### Logging Strategy

```typescript
// utils/logger.ts
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

export interface LogEntry {
  timestamp: Date;
  level: LogLevel;
  message: string;
  context?: Record<string, any>;
  error?: Error;
}

export class Logger {
  private level: LogLevel = LogLevel.INFO;

  setLevel(level: LogLevel): void {
    this.level = level;
  }

  debug(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.DEBUG, message, context);
  }

  info(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.INFO, message, context);
  }

  warn(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.WARN, message, context);
  }

  error(message: string, error?: Error, context?: Record<string, any>): void {
    this.log(LogLevel.ERROR, message, { ...context, error });
  }

  private log(level: LogLevel, message: string, context?: Record<string, any>): void {
    if (level < this.level) {
      return;
    }

    const entry: LogEntry = {
      timestamp: new Date(),
      level,
      message,
      context,
    };

    // Output to console or external service
    console.log(JSON.stringify(entry));
  }
}

// Global logger instance
export const logger = new Logger();
```

This comprehensive best practices guide provides patterns and principles for building robust, scalable, and maintainable applications with the Grizabella TypeScript API. Following these practices will help you avoid common pitfalls and build high-quality software.