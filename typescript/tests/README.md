# Grizabella TypeScript API - Testing Framework

This directory contains comprehensive testing framework for the Grizabella TypeScript API, designed to ensure quality, reliability, and maintainability through rigorous testing practices.

## 🏗️ Testing Architecture

### Directory Structure

```
tests/
├── setup.ts                    # Global test setup and configuration
├── global-setup.ts            # Jest global setup (starts MCP server)
├── global-teardown.ts         # Jest global teardown (stops MCP server)
├── utils/                     # Test utilities and helpers
│   ├── test-helpers.ts        # Common test functions and generators
│   └── mock-data.ts           # Pre-defined mock data and fixtures
├── __fixtures__/              # Test fixtures and data
│   └── index.ts              # Fixture exports
├── unit/                      # Unit tests (isolated functions/classes)
│   ├── errors.test.ts         # Error handling framework tests
│   ├── validation.test.ts     # Data validation utilities tests
│   ├── conversion.test.ts     # Type conversion utilities tests
│   └── helpers.test.ts        # Helper functions tests
├── integration/               # Integration tests (real MCP communication)
│   ├── client/                # GrizabellaClient integration tests
│   │   ├── connection.test.ts # Connection management tests
│   │   ├── schema.test.ts     # Schema management tests
│   │   └── data-operations.test.ts # CRUD operations tests
│   └── mcp/                   # MCPClient integration tests
│       ├── connection.test.ts # MCP connection tests
│       └── tools.test.ts      # MCP tool calling tests
├── e2e/                       # End-to-end tests (complete workflows)
│   ├── workflows/             # Complete workflow tests
│   └── scenarios/             # User scenario tests
└── performance/               # Performance and load tests
    ├── load.test.ts           # Load testing scenarios
    └── benchmarks.test.ts     # Performance benchmarks
```

## 🚀 Quick Start

### Running Tests

```bash
# Run all tests
npm test

# Run specific test suites
npm run test:unit          # Unit tests only
npm run test:integration   # Integration tests only
npm run test:e2e           # End-to-end tests only
npm run test:performance   # Performance tests only

# Watch mode for development
npm run test:watch

# Generate coverage reports
npm run test:coverage
npm run test:coverage:report  # HTML coverage report

# CI mode (no watch, with coverage)
npm run test:ci
```

### Prerequisites

1. **Node.js 18+** and **npm 8+**
2. **Running MCP server** (automatically started for integration tests)
3. **Test environment variables** (optional):
   ```bash
   export MCP_SERVER_URL=http://localhost:8000/mcp  # Custom MCP server URL
   export DEBUG=true                                 # Enable debug logging
   ```

## 📋 Test Categories

### 1. Unit Tests (`tests/unit/`)

Focus on isolated testing of individual functions and classes without external dependencies.

**What to test:**
- Function input/output validation
- Error handling and edge cases
- Data transformation logic
- Utility functions
- Class instantiation and methods

**Example:**
```typescript
describe('isValidUUID', () => {
  it('should return true for valid UUID v4', () => {
    const validUUID = '550e8400-e29b-41d4-a716-446655440000';
    expect(isValidUUID(validUUID)).toBe(true);
  });
});
```

### 2. Integration Tests (`tests/integration/`)

Test real interactions with MCP server and external dependencies.

**What to test:**
- MCP client communication
- Schema operations (create, read, update)
- Data operations (CRUD, queries)
- Error handling with real server
- Connection lifecycle management

**Example:**
```typescript
describe('GrizabellaClient Integration', () => {
  let client: GrizabellaClient;

  beforeEach(async () => {
    client = await GrizabellaClient.connect({
      dbNameOrPath: 'test_db',
      serverUrl: global.testConfig.mcpServerUrl,
    });
  });

  it('should create and retrieve object types', async () => {
    const objType = await client.createObjectType(mockPersonType);
    expect(objType).toBeDefined();

    const retrieved = await client.getObjectType('Person');
    expect(retrieved?.name).toBe('Person');
  });
});
```

### 3. End-to-End Tests (`tests/e2e/`)

Test complete user workflows and scenarios.

**What to test:**
- Complete data pipelines
- Multi-step operations
- User journeys and workflows
- System integration scenarios

### 4. Performance Tests (`tests/performance/`)

Test system performance under various loads.

**What to test:**
- Response times and throughput
- Memory usage patterns
- Concurrent operation handling
- Resource utilization

## 🛠️ Test Utilities

### Test Helpers (`tests/utils/test-helpers.ts`)

Common utilities for test creation and assertion:

```typescript
import {
  createTestObjectInstance,
  generateTestId,
  assertThrowsError,
  sleep
} from '../utils/test-helpers';

// Create test data
const person = createTestObjectInstance('Person', {
  name: 'John Doe',
  age: 30
});

// Generate unique IDs
const uniqueId = generateTestId('test-object');

// Assert error throwing
await assertThrowsError(
  () => validateUUID('invalid'),
  ValidationError,
  'Invalid UUID'
);

// Add delays in tests
await sleep(1000);
```

### Mock Data (`tests/utils/mock-data.ts`)

Pre-defined test data and fixtures:

```typescript
import {
  mockPersonType,
  mockPersonInstances,
  createCompleteTestDataset
} from '../utils/mock-data';

// Use predefined fixtures
const person = mockPersonInstances[0];
expect(person.properties.name).toBe('John Doe');

// Create complete test dataset
const { objectTypes, relationTypes, objectInstances } = createCompleteTestDataset();
```

### Custom Matchers

The test framework extends Jest with custom matchers:

```typescript
expect(uuid).toBeValidUUID();
expect(date).toBeValidDate();
expect(decimal).toBeValidDecimal();
expect(object).toHaveValidStructure();
```

## 🔧 Configuration

### Jest Configuration (`jest.config.js`)

Key configuration options:

```javascript
module.exports = {
  // Use ts-jest for TypeScript
  preset: 'ts-jest',

  // Test file patterns
  testMatch: ['<rootDir>/tests/**/*.test.ts'],

  // Setup files
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],

  // Coverage configuration
  collectCoverageFrom: ['src/**/*.ts'],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },

  // Global setup/teardown for MCP server
  globalSetup: '<rootDir>/tests/global-setup.ts',
  globalTeardown: '<rootDir>/tests/global-teardown.ts',
};
```

### TypeScript Configuration (`tsconfig.test.json`)

Test-specific TypeScript configuration with relaxed rules for test files:

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    // ... other relaxed settings for tests
  },
  "include": [
    "src/**/*",
    "tests/**/*",
    "examples/**/*"
  ]
}
```

## 📊 Coverage Reporting

### Coverage Goals

- **Statements**: 80%
- **Branches**: 80%
- **Functions**: 80%
- **Lines**: 80%

### Generating Reports

```bash
# Text summary
npm run test:coverage

# HTML report (opens in browser)
npm run test:coverage:report

# JSON report for CI/CD
npm run test:ci
```

### Coverage Files

- `coverage/lcov-report/index.html` - HTML report
- `coverage/coverage-final.json` - Raw coverage data
- `coverage/coverage-summary.json` - Summary for CI

## 🐛 Debugging Tests

### Debug Mode

```bash
# Run tests in debug mode
npm run test:debug

# With specific test
npm run test:debug -- tests/unit/errors.test.ts
```

### Common Debugging Techniques

1. **Use `--verbose` flag** for detailed test output
2. **Add `console.log` statements** (automatically suppressed in CI)
3. **Use `--runInBand`** to disable parallel execution
4. **Check `.jest` directory** for cached test results

## 🌐 Environment Variables

### Test Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_SERVER_URL` | `http://localhost:8000/mcp` | MCP server URL for integration tests |
| `DEBUG` | `false` | Enable debug logging |
| `JEST_TIMEOUT` | `30000` | Default test timeout (ms) |
| `CI` | `false` | Enable CI mode (affects logging) |

### Example Usage

```bash
# Custom MCP server
MCP_SERVER_URL=http://localhost:9000/mcp npm test

# Debug mode
DEBUG=true npm run test:watch

# CI environment
CI=true npm run test:ci
```

## 📈 Best Practices

### Test Organization

1. **One concept per test** - Each test should verify one behavior
2. **Descriptive test names** - Use clear, descriptive test descriptions
3. **Arrange-Act-Assert pattern** - Structure tests clearly
4. **DRY principle** - Use shared utilities and fixtures
5. **Independent tests** - Tests should not depend on each other

### Example Test Structure

```typescript
describe('UUID Validation', () => {
  describe('isValidUUID', () => {
    it('should return true for valid UUID v4', () => {
      // Arrange
      const validUUID = '550e8400-e29b-41d4-a716-446655440000';

      // Act
      const result = isValidUUID(validUUID);

      // Assert
      expect(result).toBe(true);
    });

    it('should return false for invalid UUID', () => {
      // Arrange
      const invalidUUID = 'invalid-uuid';

      // Act & Assert
      expect(isValidUUID(invalidUUID)).toBe(false);
    });
  });
});
```

### Error Testing

```typescript
describe('Error Handling', () => {
  it('should throw ValidationError for invalid input', async () => {
    await assertThrowsError(
      () => validateUUID('invalid'),
      ValidationError,
      'Invalid UUID format'
    );
  });
});
```

### Integration Test Setup

```typescript
describe('GrizabellaClient Integration', () => {
  let client: GrizabellaClient;

  beforeAll(async () => {
    client = await GrizabellaClient.connect({
      dbNameOrPath: 'test_db',
      serverUrl: global.testConfig.mcpServerUrl,
    });
  });

  afterAll(async () => {
    await client?.close();
  });

  beforeEach(async () => {
    // Clean up test data
    // Reset database state
  });

  it('should perform CRUD operations', async () => {
    // Test implementation
  });
});
```

## 🚨 Troubleshooting

### Common Issues

1. **MCP server connection failures**
   - Check if MCP server is running
   - Verify `MCP_SERVER_URL` environment variable
   - Review server logs for connection errors

2. **Test timeouts**
   - Increase timeout for slow operations
   - Check for infinite loops or hanging promises
   - Verify network connectivity for integration tests

3. **Coverage reporting issues**
   - Ensure source maps are generated
   - Check TypeScript compilation output
   - Verify file paths in coverage configuration

4. **Memory issues**
   - Use `--runInBand` for large test suites
   - Check for memory leaks in async operations
   - Monitor heap usage in performance tests

### Debug Commands

```bash
# Run specific test with detailed output
npm test -- --verbose tests/unit/validation.test.ts

# Debug specific test
node --inspect-brk node_modules/.bin/jest --runInBand tests/unit/errors.test.ts

# Run tests with coverage for specific file
npm run test:coverage -- tests/unit/helpers.test.ts

# Check TypeScript compilation
npm run test:types
```

## 🤝 Contributing

### Adding New Tests

1. **Choose appropriate directory** based on test type (unit/integration/e2e)
2. **Follow naming convention**: `*.test.ts` or `*.spec.ts`
3. **Use existing utilities** from `tests/utils/`
4. **Add proper documentation** and examples
5. **Ensure coverage goals** are met

### Test Maintenance

1. **Keep tests up-to-date** with code changes
2. **Remove obsolete tests** when features are removed
3. **Update fixtures** when data structures change
4. **Review test performance** regularly

## 📝 Additional Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [TypeScript Testing Guide](https://www.typescriptlang.org/docs/handbook/testing.html)
- [Testing Best Practices](https://github.com/goldbergyoni/javascript-testing-best-practices)
- [Grizabella API Documentation](../docs/README.md)