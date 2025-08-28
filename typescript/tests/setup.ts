/**
 * Jest test setup file
 *
 * This file is executed before each test file and sets up the test environment,
 * including global test utilities, mock configurations, and environment variables.
 */

import 'reflect-metadata';

// Set test environment
  process.env['NODE_ENV'] = 'test';
  process.env['JEST_WORKER_ID'] = '1';

// Global test configuration
global.testConfig = {
  timeout: 30000,
  retries: 3,
  mcpServerUrl: process.env['MCP_SERVER_URL'] || 'http://localhost:8000/mcp',
  databaseName: 'test_db',
  debug: false,
};

// Custom matchers for better assertions
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeValidUUID(): R;
      toBeValidDate(): R;
      toBeValidDecimal(): R;
      toHaveValidStructure(): R;
    }
  }

  var testConfig: {
    timeout: number;
    retries: number;
    mcpServerUrl: string;
    databaseName: string;
    debug: boolean;
  };
}

// Add custom matchers
expect.extend({
  toBeValidUUID(received: string) {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    const pass = uuidRegex.test(received);
    return {
      message: () => `expected ${received} to be a valid UUID`,
      pass,
    };
  },

  toBeValidDate(received: any) {
    const pass = received instanceof Date && !isNaN(received.getTime());
    return {
      message: () => `expected ${received} to be a valid Date`,
      pass,
    };
  },

  toBeValidDecimal(received: any) {
    const pass = received && typeof received.toString === 'function' && !isNaN(Number(received.toString()));
    return {
      message: () => `expected ${received} to be a valid Decimal`,
      pass,
    };
  },

  toHaveValidStructure(received: any) {
    const hasRequiredFields = received &&
      typeof received.id === 'string' &&
      typeof received.object_type_name === 'string' &&
      received.properties &&
      typeof received.properties === 'object';

    return {
      message: () => `expected ${JSON.stringify(received)} to have valid ObjectInstance structure`,
      pass: hasRequiredFields,
    };
  },
});

// Mock console methods for cleaner test output (but keep errors)
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

beforeAll(() => {
  // Suppress console.log and console.info in tests unless debug is enabled
  if (!global.testConfig.debug) {
    console.log = jest.fn();
    console.info = jest.fn();
    console.debug = jest.fn();
  }

  // Keep console.warn and console.error for important messages
  console.warn = (...args: any[]) => {
    if (global.testConfig.debug) {
      originalConsoleWarn(...args);
    }
  };

  console.error = (...args: any[]) => {
    originalConsoleError(...args);
  };
});

afterAll(() => {
  // Restore console methods
  console.log = originalConsoleWarn;
  console.info = originalConsoleWarn;
  console.debug = originalConsoleWarn;
  console.warn = originalConsoleWarn;
  console.error = originalConsoleError;
});

// Clean up after each test
afterEach(() => {
  jest.clearAllMocks();
  jest.clearAllTimers();
});

// Set default timeout for all tests
jest.setTimeout(global.testConfig.timeout);

// Export common test utilities
export * from './utils/test-helpers';
export * from './utils/mock-data';
export * from './__fixtures__/index';