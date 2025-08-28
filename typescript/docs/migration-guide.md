# Migration Guide

Complete guide for migrating from the Python Grizabella client to the TypeScript API.

## Table of Contents

- [Overview](#overview)
- [Key Differences](#key-differences)
- [Migration Steps](#migration-steps)
- [Code Examples](#code-examples)
- [Breaking Changes](#breaking-changes)
- [Best Practices Migration](#best-practices-migration)
- [Testing Migration](#testing-migration)
- [Troubleshooting](#troubleshooting)

## Overview

This guide helps you migrate existing Python Grizabella applications to the new TypeScript API. The TypeScript API provides better type safety, improved developer experience, and enhanced performance while maintaining compatibility with the core Grizabella functionality.

### Benefits of Migrating

- **Type Safety**: Compile-time error checking and IntelliSense support
- **Better Performance**: Optimized JavaScript runtime
- **Modern Tooling**: Access to npm ecosystem and modern development tools
- **Enhanced DX**: Better debugging, testing, and development workflows
- **Future-Ready**: Active TypeScript ecosystem and ongoing improvements

### Migration Timeline

- **Phase 1**: Setup and basic connection (1-2 days)
- **Phase 2**: Schema migration (2-3 days)
- **Phase 3**: Data operations migration (3-5 days)
- **Phase 4**: Advanced features migration (2-3 days)
- **Phase 5**: Testing and optimization (2-3 days)

## Key Differences

### Connection Management

**Python:**
```python
from grizabella import Grizabella

# Context manager
with Grizabella(db="my-db", create=True) as client:
    # Use client
    pass

# Manual management
client = Grizabella(db="my-db", create=True)
client.connect()
# ... use client
client.close()
```

**TypeScript:**
```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';

// Context manager (recommended)
await using client = await GrizabellaClient.connect({
  dbNameOrPath: 'my-db',
  serverUrl: 'http://localhost:8000/mcp',
  createIfNotExists: true,
});

// Manual management
const client = new GrizabellaClient({
  dbNameOrPath: 'my-db',
  serverUrl: 'http://localhost:8000/mcp',
  createIfNotExists: true,
});

await client.connect();
// ... use client
await client.close();
```

### Schema Definition

**Python:**
```python
# Define object type
person_type = {
    "name": "Person",
    "properties": {
        "name": {"type": "TEXT", "nullable": False},
        "age": {"type": "INTEGER", "nullable": True},
    }
}

# Create object type
client.create_object_type(person_type)
```

**TypeScript:**
```typescript
// Define object type with full type safety
const personType: ObjectTypeDefinition = {
  name: 'Person',
  description: 'A person in the system',
  properties: [
    {
      name: 'name',
      data_type: PropertyDataType.TEXT,
      is_nullable: false,
      description: 'Person name',
    },
    {
      name: 'age',
      data_type: PropertyDataType.INTEGER,
      is_nullable: true,
      description: 'Person age',
    },
  ],
};

// Create with validation
await client.createObjectType(personType);
```

### Data Operations

**Python:**
```python
# Create object
person = {
    "id": "person-1",
    "name": "John Doe",
    "age": 30,
}

client.upsert_object("Person", person)

# Find objects
people = client.find_objects("Person", {"age": {"gt": 25}})
```

**TypeScript:**
```typescript
// Create object with type safety
const person = await client.upsertObject({
  id: 'person-1',
  object_type_name: 'Person',
  weight: new Decimal('1.0'),
  upsert_date: new Date(),
  properties: {
    name: 'John Doe',
    age: 30,
  },
});

// Find objects with type safety
const people = await client.findObjects('Person', { age: { '>': 25 } });
```

## Migration Steps

### Phase 1: Project Setup

1. **Create TypeScript Project**
   ```bash
   mkdir my-migrated-app
   cd my-migrated-app
   npm init -y
   npm install grizabella-typescript-api typescript @types/node
   ```

2. **Setup TypeScript Configuration**
   ```json
   // tsconfig.json
   {
     "compilerOptions": {
       "target": "ES2022",
       "lib": ["ES2022"],
       "module": "CommonJS",
       "strict": true,
       "esModuleInterop": true,
       "outDir": "./dist"
     }
   }
   ```

3. **Create Basic Connection**
   ```typescript
   // src/database.ts
   import { GrizabellaClient } from 'grizabella-typescript-api';

   export async function createClient() {
     return await GrizabellaClient.connect({
       dbNameOrPath: process.env.DB_PATH || './data/migrated-db',
       serverUrl: process.env.GRIZABELLA_SERVER_URL || 'http://localhost:8000/mcp',
       createIfNotExists: true,
       debug: process.env.NODE_ENV === 'development',
     });
   }
   ```

### Phase 2: Schema Migration

1. **Export Existing Schema (Python)**
   ```python
   # export_schema.py
   import json
   from grizabella import Grizabella

   with Grizabella(db="existing-db") as client:
       object_types = client.list_object_types()
       relation_types = client.list_relation_types()

       schema = {
           "object_types": object_types,
           "relation_types": relation_types,
       }

       with open('existing_schema.json', 'w') as f:
           json.dump(schema, f, indent=2)
   ```

2. **Import Schema in TypeScript**
   ```typescript
   // src/migration/import-schema.ts
   import { GrizabellaClient, PropertyDataType } from 'grizabella-typescript-api';
   import * as fs from 'fs';

   export async function importSchema(client: GrizabellaClient) {
     const schemaData = JSON.parse(fs.readFileSync('existing_schema.json', 'utf-8'));

     // Import object types
     for (const objType of schemaData.object_types) {
       // Convert Python schema format to TypeScript
       const tsObjectType = {
         name: objType.name,
         description: objType.description || '',
         properties: objType.properties.map((prop: any) => ({
           name: prop.name,
           data_type: prop.type as PropertyDataType,
           is_nullable: prop.nullable !== false,
           is_unique: prop.unique || false,
           is_indexed: prop.indexed || false,
           description: prop.description || '',
         })),
       };

       await client.createObjectType(tsObjectType);
       console.log(`✅ Created object type: ${objType.name}`);
     }

     // Import relation types
     for (const relType of schemaData.relation_types) {
       const tsRelationType = {
         name: relType.name,
         description: relType.description || '',
         source_object_type_names: relType.source_types || [],
         target_object_type_names: relType.target_types || [],
         properties: relType.properties || [],
       };

       await client.createRelationType(tsRelationType);
       console.log(`✅ Created relation type: ${relType.name}`);
     }
   }
   ```

### Phase 3: Data Migration

1. **Export Data (Python)**
   ```python
   # export_data.py
   import json
   from grizabella import Grizabella

   with Grizabella(db="existing-db") as client:
       # Export all data by object type
       data_export = {}

       for obj_type in client.list_object_types():
           objects = client.find_objects(obj_type["name"])
           data_export[obj_type["name"]] = objects

       with open('existing_data.json', 'w') as f:
           json.dump(data_export, f, indent=2, default=str)
   ```

2. **Import Data (TypeScript)**
   ```typescript
   // src/migration/import-data.ts
   import { GrizabellaClient } from 'grizabella-typescript-api';
   import { Decimal } from 'decimal.js';
   import * as fs from 'fs';

   export async function importData(client: GrizabellaClient) {
     const data = JSON.parse(fs.readFileSync('existing_data.json', 'utf-8'));

     for (const [objectType, objects] of Object.entries(data)) {
       console.log(`📥 Importing ${objects.length} ${objectType} objects...`);

       for (const obj of objects as any[]) {
         // Convert Python object to TypeScript format
         const tsObject = {
           id: obj.id,
           object_type_name: objectType,
           weight: new Decimal(obj.weight || '1.0'),
           upsert_date: new Date(obj.upsert_date || Date.now()),
           properties: obj.properties || {},
         };

         await client.upsertObject(tsObject);
       }

       console.log(`✅ Imported ${objects.length} ${objectType} objects`);
     }
   }
   ```

### Phase 4: Code Migration

1. **Migrate Service Classes**

**Python Service:**
```python
# services/user_service.py
class UserService:
    def __init__(self, client):
        self.client = client

    def create_user(self, user_data):
        return self.client.upsert_object("User", user_data)

    def get_user(self, user_id):
        return self.client.get_object("User", user_id)

    def find_users_by_department(self, department):
        return self.client.find_objects("User", {"department": department})
```

**TypeScript Service:**
```typescript
// src/services/user-service.ts
import { GrizabellaClient } from 'grizabella-typescript-api';

export interface User {
  readonly id: string;
  readonly email: string;
  readonly first_name: string;
  readonly last_name: string;
  readonly department?: string;
  readonly is_active: boolean;
}

export class UserService {
  constructor(private client: GrizabellaClient) {}

  async createUser(userData: Omit<User, 'id'>): Promise<User> {
    const user = await this.client.upsertObject({
      id: generateUserId(),
      object_type_name: 'User',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: userData,
    });

    return user as User;
  }

  async getUser(userId: string): Promise<User | null> {
    const user = await this.client.getObjectById(userId, 'User');
    return user as User | null;
  }

  async findUsersByDepartment(department: string): Promise<User[]> {
    const users = await this.client.findObjects('User', { department });
    return users as User[];
  }
}
```

2. **Migrate Complex Queries**

**Python:**
```python
# Find users with active projects
def find_users_with_active_projects(client):
    users = client.find_objects("User")
    active_projects = client.find_objects("Project", {"status": "active"})

    result = []
    for user in users:
        # Check if user has active projects
        relations = client.get_outgoing_relations(user["id"], "User", "WORKS_ON")
        for relation in relations:
            project_id = relation["target_object_instance_id"]
            if any(p["id"] == project_id for p in active_projects):
                result.append(user)
                break

    return result
```

**TypeScript:**
```typescript
// src/queries/complex-queries.ts
import { GrizabellaClient } from 'grizabella-typescript-api';

export interface UserWithProjects {
  user: User;
  activeProjects: Project[];
}

export async function findUsersWithActiveProjects(
  client: GrizabellaClient
): Promise<UserWithProjects[]> {
  // Get active projects first
  const activeProjects = await client.findObjects('Project', { status: 'active' });
  const activeProjectIds = new Set(activeProjects.map(p => p.id));

  // Get all users
  const users = await client.findObjects('User');

  const result: UserWithProjects[] = [];

  for (const user of users) {
    // Get user's projects
    const relations = await client.getOutgoingRelations(user.id, 'User', 'WORKS_ON');
    const userProjectIds = relations.map(r => r.target_object_instance_id);
    const userActiveProjects = activeProjects.filter(p => userProjectIds.has(p.id));

    if (userActiveProjects.length > 0) {
      result.push({
        user: user as User,
        activeProjects: userActiveProjects as Project[],
      });
    }
  }

  return result;
}
```

## Code Examples

### Complete Migration Example

**Python (Original):**
```python
# app.py
from grizabella import Grizabella

def main():
    with Grizabella(db="my-app-db", create=True) as client:
        # Create schema
        client.create_object_type({
            "name": "User",
            "properties": {
                "name": {"type": "TEXT", "nullable": False},
                "email": {"type": "TEXT", "nullable": False, "unique": True},
            }
        })

        # Create user
        user = {
            "id": "user-1",
            "name": "John Doe",
            "email": "john@example.com",
        }

        client.upsert_object("User", user)

        # Find user
        found_user = client.get_object("User", "user-1")
        print(f"Found user: {found_user}")

if __name__ == "__main__":
    main()
```

**TypeScript (Migrated):**
```typescript
// src/app.ts
import { GrizabellaClient, PropertyDataType } from 'grizabella-typescript-api';

interface User {
  readonly id: string;
  readonly name: string;
  readonly email: string;
}

async function main() {
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'my-app-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  // Create schema with full type safety
  await client.createObjectType({
    name: 'User',
    description: 'A user in the system',
    properties: [
      {
        name: 'name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        description: 'User full name',
      },
      {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'User email address',
      },
    ],
  });

  // Create user with type safety
  const user = await client.upsertObject({
    id: 'user-1',
    object_type_name: 'User',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      name: 'John Doe',
      email: 'john@example.com',
    },
  });

  // Find user with type safety
  const foundUser = await client.getObjectById('user-1', 'User');
  if (foundUser) {
    console.log(`Found user: ${foundUser.properties.name}`);
  }
}

main().catch(console.error);
```

### Repository Pattern Migration

**Python Repository:**
```python
class UserRepository:
    def __init__(self, client):
        self.client = client

    def save(self, user):
        return self.client.upsert_object("User", user)

    def find_by_id(self, user_id):
        return self.client.get_object("User", user_id)

    def find_by_email(self, email):
        users = self.client.find_objects("User", {"email": email})
        return users[0] if users else None
```

**TypeScript Repository:**
```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';

export interface User {
  readonly id: string;
  readonly email: string;
  readonly name: string;
}

export class UserRepository {
  constructor(private client: GrizabellaClient) {}

  async save(user: User): Promise<User> {
    const result = await this.client.upsertObject({
      id: user.id,
      object_type_name: 'User',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        email: user.email,
        name: user.name,
      },
    });

    return result as User;
  }

  async findById(userId: string): Promise<User | null> {
    const result = await this.client.getObjectById(userId, 'User');
    return result as User | null;
  }

  async findByEmail(email: string): Promise<User | null> {
    const users = await this.client.findObjects('User', { email }, 1);
    return users.length > 0 ? (users[0] as User) : null;
  }
}
```

## Breaking Changes

### API Changes

1. **Method Naming**: Python uses snake_case, TypeScript uses camelCase
   - `create_object_type()` → `createObjectType()`
   - `get_object()` → `getObjectById()`
   - `find_objects()` → `findObjects()`

2. **Parameter Structure**:
   - Python: `upsert_object(type_name, object_data)`
   - TypeScript: `upsertObject(object_instance)`

3. **Object Instance Format**:
   - Python: Flat object with properties
   - TypeScript: Structured object with metadata

4. **Error Handling**:
   - Python: Generic exceptions
   - TypeScript: Specific error types with detailed context

### Data Type Changes

| Python | TypeScript | Notes |
|--------|------------|-------|
| `"TEXT"` | `PropertyDataType.TEXT` | Import enum |
| `"INTEGER"` | `PropertyDataType.INTEGER` | Import enum |
| `"FLOAT"` | `PropertyDataType.FLOAT` | Import enum |
| `"BOOLEAN"` | `PropertyDataType.BOOLEAN` | Import enum |
| `"DATETIME"` | `PropertyDataType.DATETIME` | Import enum |
| `"JSON"` | `PropertyDataType.JSON` | Import enum |
| `"UUID"` | `PropertyDataType.UUID` | Import enum |

### Filter Operator Changes

| Python | TypeScript | Notes |
|--------|------------|-------|
| `{"gt": value}` | `{">": value}` | Use string operators |
| `{"gte": value}` | `{">=": value}` | Use string operators |
| `{"lt": value}` | `{"<": value}` | Use string operators |
| `{"lte": value}` | `{"<=": value}` | Use string operators |
| `{"eq": value}` | Direct value or `{"==": value}` | Simplified |
| `{"neq": value}` | `{"!=": value}` | Use string operators |

## Best Practices Migration

### 1. Add Type Safety

**Before:**
```python
def process_user(user_data):
    return client.upsert_object("User", user_data)
```

**After:**
```typescript
interface UserData {
  name: string;
  email: string;
  age?: number;
}

async function processUser(userData: UserData): Promise<User> {
  return await client.upsertObject({
    id: generateUserId(),
    object_type_name: 'User',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: userData,
  }) as User;
}
```

### 2. Use Repository Pattern

**Before:**
```python
# Direct client usage throughout
user = client.upsert_object("User", user_data)
```

**After:**
```typescript
// Centralized data access
const userRepository = new UserRepository(client);
const user = await userRepository.save(userData);
```

### 3. Implement Proper Error Handling

**Before:**
```python
try:
    user = client.get_object("User", user_id)
except Exception as e:
    print(f"Error: {e}")
```

**After:**
```typescript
import { NotConnectedError, ValidationError } from 'grizabella-typescript-api';

async function getUser(userId: string): Promise<User | null> {
  try {
    const user = await client.getObjectById(userId, 'User');
    return user as User | null;
  } catch (error) {
    if (error instanceof NotConnectedError) {
      logger.error('Database not connected', { userId });
      throw error;
    }

    if (error instanceof ValidationError) {
      logger.warn('Invalid user ID format', { userId });
      return null;
    }

    logger.error('Unexpected error getting user', { userId, error });
    throw error;
  }
}
```

### 4. Add Validation

**Before:**
```python
def create_user(name, email):
    user_data = {"name": name, "email": email}
    return client.upsert_object("User", user_data)
```

**After:**
```typescript
import { validateObjectInstance } from 'grizabella-typescript-api';

async function createUser(name: string, email: string): Promise<User> {
  // Input validation
  if (!name || !email) {
    throw new ValidationError('Name and email are required');
  }

  if (!isValidEmail(email)) {
    throw new ValidationError('Invalid email format');
  }

  const userData = { name, email };
  const userObject = createObjectInstance('User', userData);

  // Schema validation
  const userType = await client.getObjectType('User');
  const validation = validateObjectInstance(userObject, userType!);

  if (!validation.isValid) {
    throw new ValidationError(`Validation failed: ${validation.errors.join(', ')}`);
  }

  return await client.upsertObject(userObject) as User;
}
```

## Testing Migration

### Unit Testing Migration

**Python (pytest):**
```python
# tests/test_user_service.py
import pytest
from services.user_service import UserService

def test_create_user(mock_client):
    service = UserService(mock_client)
    user_data = {"name": "John", "email": "john@example.com"}

    result = service.create_user(user_data)

    assert result["name"] == "John"
    assert result["email"] == "john@example.com"
    mock_client.upsert_object.assert_called_once()
```

**TypeScript (Jest):**
```typescript
// tests/services/user-service.test.ts
import { UserService } from '../../src/services/user-service';
import { createMockClient } from '../mocks/database-client';

describe('UserService', () => {
  let service: UserService;
  let mockClient: jest.Mocked<GrizabellaClient>;

  beforeEach(() => {
    mockClient = createMockClient();
    service = new UserService(mockClient);
  });

  describe('createUser', () => {
    it('should create a user successfully', async () => {
      const userData = { name: 'John', email: 'john@example.com' };
      const mockUser = createMockUser(userData);

      mockClient.upsertObject.mockResolvedValue(mockUser);

      const result = await service.createUser(userData);

      expect(result.name).toBe('John');
      expect(result.email).toBe('john@example.com');
      expect(mockClient.upsertObject).toHaveBeenCalledWith(
        expect.objectContaining({
          object_type_name: 'User',
          properties: userData,
        })
      );
    });

    it('should validate email format', async () => {
      const invalidUserData = { name: 'John', email: 'invalid-email' };

      await expect(service.createUser(invalidUserData)).rejects.toThrow(ValidationError);
    });
  });
});
```

### Integration Testing

**Python:**
```python
# tests/integration/test_database.py
import pytest
from grizabella import Grizabella

@pytest.fixture
def client():
    with Grizabella(db="test-db", create=True) as client:
        yield client

def test_full_user_lifecycle(client):
    # Create user
    user = {"id": "test-1", "name": "Test User", "email": "test@example.com"}
    client.upsert_object("User", user)

    # Retrieve user
    found = client.get_object("User", "test-1")
    assert found["name"] == "Test User"

    # Update user
    updated = {"id": "test-1", "name": "Updated User", "email": "test@example.com"}
    client.upsert_object("User", updated)

    found_updated = client.get_object("User", "test-1")
    assert found_updated["name"] == "Updated User"
```

**TypeScript:**
```typescript
// tests/integration/database.test.ts
import { GrizabellaClient } from 'grizabella-typescript-api';
import { TestDatabase } from './test-database';

describe('Database Integration', () => {
  let testDb: TestDatabase;

  beforeEach(async () => {
    testDb = new TestDatabase();
    await testDb.setup();
  });

  afterEach(async () => {
    await testDb.cleanup();
  });

  it('should handle full user lifecycle', async () => {
    const client = await testDb.getClient();

    // Create user
    const user = await client.upsertObject({
      id: 'test-1',
      object_type_name: 'User',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Test User',
        email: 'test@example.com',
      },
    });

    expect(user.properties.name).toBe('Test User');

    // Retrieve user
    const found = await client.getObjectById('test-1', 'User');
    expect(found?.properties.name).toBe('Test User');

    // Update user
    const updated = await client.upsertObject({
      ...user,
      properties: {
        ...user.properties,
        name: 'Updated User',
      },
    });

    expect(updated.properties.name).toBe('Updated User');
  });
});
```

## Troubleshooting

### Common Migration Issues

1. **Connection Issues**
   ```typescript
   // Ensure server URL is correct
   const client = new GrizabellaClient({
     dbNameOrPath: 'my-db',
     serverUrl: process.env.GRIZABELLA_SERVER_URL || 'http://localhost:8000/mcp',
   });
   ```

2. **Type Errors**
   ```typescript
   // Check TypeScript configuration
   // Ensure all imports are correct
   import { GrizabellaClient, PropertyDataType } from 'grizabella-typescript-api';
   ```

3. **Schema Compatibility**
   ```typescript
   // Validate schema before migration
   const validation = validateObjectTypeDefinition(objectType);
   if (!validation.isValid) {
     console.error('Schema validation failed:', validation.errors);
   }
   ```

4. **Data Format Issues**
   ```typescript
   // Ensure data conforms to schema
   const userType = await client.getObjectType('User');
   const validation = validateObjectInstance(userObject, userType!);
   ```

### Migration Checklist

- [ ] ✅ Setup TypeScript project
- [ ] ✅ Install dependencies
- [ ] ✅ Configure TypeScript
- [ ] ✅ Setup environment variables
- [ ] ✅ Create basic connection
- [ ] ✅ Export existing Python data
- [ ] ✅ Import schema definitions
- [ ] ✅ Import data
- [ ] ✅ Migrate service classes
- [ ] ✅ Update tests
- [ ] ✅ Test functionality
- [ ] ✅ Update deployment scripts
- [ ] ✅ Train team on new patterns

### Performance Considerations

1. **Batch Operations**: Use `createMultipleObjectInstances` for bulk operations
2. **Connection Pooling**: Implement connection reuse
3. **Caching**: Add caching for frequently accessed data
4. **Indexing**: Ensure proper indexing in schema
5. **Monitoring**: Add performance monitoring

### Rollback Plan

1. **Keep Python Version**: Maintain Python application during migration
2. **Gradual Migration**: Migrate services one at a time
3. **Feature Flags**: Use feature flags to switch between implementations
4. **Data Backup**: Ensure data is backed up before migration
5. **Testing**: Comprehensive testing before going live

This migration guide provides a comprehensive path from Python to TypeScript. The process may take time, but the benefits of type safety, better performance, and modern tooling make it worthwhile. Take it one step at a time and thoroughly test each phase before proceeding.