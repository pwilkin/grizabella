/**
 * Unit tests for error handling framework
 *
 * Tests all error classes, enums, contexts, and utility functions to ensure
 * proper error handling behavior throughout the TypeScript API.
 */

import {
  // Error classes
  GrizabellaError,
  ConnectionError,
  NotConnectedError,
  SchemaError,
  ValidationError,
  EmbeddingError,
  QueryError,
  McpProtocolError,

  // Error codes and enums
  ErrorCode,
  ErrorSeverity,
  ErrorCategory,

  // Error context interfaces
  ConnectionErrorContext,
  SchemaErrorContext,

  // Error mapping utilities
  mapMcpError,
  isRetryableError,

  // Error handling patterns
  withRetry,
  handleErrors,
  createErrorBoundary,

  // Logging integration
  ErrorLogger,
  ConsoleErrorLogger,
  setGlobalErrorLogger,
  getGlobalErrorLogger,
  logError,

  // Utility functions
  isGrizabellaError,
  isErrorType,
  createErrorMessage,
  extractErrorContext,

  // Error context interfaces
  // McpErrorContext,
} from '../../src/client/errors';

describe('Error Handling Framework', () => {
  describe('Error Enums', () => {
    it('should have all expected error codes', () => {
      expect(ErrorCode.GENERIC_ERROR).toBe(1000);
      expect(ErrorCode.CONNECTION_ERROR).toBe(2000);
      expect(ErrorCode.SCHEMA_ERROR).toBe(3000);
      expect(ErrorCode.VALIDATION_ERROR).toBe(4000);
      expect(ErrorCode.EMBEDDING_ERROR).toBe(5000);
      expect(ErrorCode.QUERY_ERROR).toBe(6000);
      expect(ErrorCode.MCP_PROTOCOL_ERROR).toBe(7000);
    });

    it('should have all expected error severities', () => {
      expect(Object.values(ErrorSeverity)).toEqual(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']);
    });

    it('should have all expected error categories', () => {
      expect(Object.values(ErrorCategory)).toEqual([
        'CONNECTION', 'AUTHENTICATION', 'SCHEMA', 'VALIDATION',
        'EMBEDDING', 'QUERY', 'MCP_PROTOCOL', 'SYSTEM'
      ]);
    });
  });

  describe('GrizabellaError Base Class', () => {
    let error: GrizabellaError;

    beforeEach(() => {
      error = new GrizabellaError(
        'Test error message',
        ErrorCode.GENERIC_ERROR,
        ErrorCategory.SYSTEM,
        ErrorSeverity.MEDIUM,
        true,
        { operation: 'test_operation', userId: 'test_user' },
        new Error('Original error')
      );
    });

    it('should create error with correct properties', () => {
      expect(error.message).toBe('Test error message');
      expect(error.code).toBe(ErrorCode.GENERIC_ERROR);
      expect(error.category).toBe(ErrorCategory.SYSTEM);
      expect(error.severity).toBe(ErrorSeverity.MEDIUM);
      expect(error.isRetryable).toBe(true);
      expect(error.cause?.message).toBe('Original error');
      expect(error.name).toBe('GrizabellaError');
    });

    it('should have proper error context', () => {
      expect(error.errorContext.timestamp).toBeInstanceOf(Date);
      expect(error.errorContext.operation).toBe('test_operation');
      expect(error.errorContext.userId).toBe('test_user');
    });

    it('should serialize to JSON correctly', () => {
      const json = error.toJSON();

      expect(json['name']).toBe('GrizabellaError');
      expect(json['message']).toBe('Test error message');
      expect(json['code']).toBe(ErrorCode.GENERIC_ERROR);
      expect(json['category']).toBe(ErrorCategory.SYSTEM);
      expect(json['severity']).toBe(ErrorSeverity.MEDIUM);
      expect(json['isRetryable']).toBe(true);
      expect((json['cause'] as any)?.['name']).toBe('Error');
      expect((json['cause'] as any)?.['message']).toBe('Original error');
    });

    it('should create detailed error message', () => {
      const detailedMessage = error.getDetailedMessage();

      expect(detailedMessage).toContain('[1000] Test error message');
      expect(detailedMessage).toContain('(Operation: test_operation)');
      // Request ID should not be included when it's undefined
      expect(detailedMessage).not.toContain('(Request ID:');
    });
  });

  describe('Specific Error Classes', () => {
    describe('ConnectionError', () => {
      it('should create connection error with correct defaults', () => {
        const error = new ConnectionError('Connection failed');

        expect(error.code).toBe(ErrorCode.CONNECTION_ERROR);
        expect(error.category).toBe(ErrorCategory.CONNECTION);
        expect(error.severity).toBe(ErrorSeverity.HIGH);
        expect(error.isRetryable).toBe(true);
      });

      it('should handle connection context', () => {
        const context: Partial<ConnectionErrorContext> = {
          host: 'localhost',
          port: 8000,
          timeout: 30000,
          retryCount: 2,
        };

        const error = new ConnectionError('Connection timeout', context);

        expect((error.errorContext as ConnectionErrorContext).host).toBe('localhost');
        expect((error.errorContext as ConnectionErrorContext).port).toBe(8000);
        expect((error.errorContext as ConnectionErrorContext).timeout).toBe(30000);
        expect((error.errorContext as ConnectionErrorContext).retryCount).toBe(2);
      });
    });

    describe('NotConnectedError', () => {
      it('should create not connected error with correct defaults', () => {
        const error = new NotConnectedError();

        expect(error.message).toBe('Not connected to the service');
        expect(error.code).toBe(ErrorCode.NOT_CONNECTED);
        expect(error.category).toBe(ErrorCategory.CONNECTION);
        expect(error.severity).toBe(ErrorSeverity.HIGH);
        expect(error.isRetryable).toBe(false);
      });
    });

    describe('SchemaError', () => {
      it('should create schema error with correct defaults', () => {
        const error = new SchemaError('Invalid schema definition');

        expect(error.code).toBe(ErrorCode.SCHEMA_ERROR);
        expect(error.category).toBe(ErrorCategory.SCHEMA);
        expect(error.severity).toBe(ErrorSeverity.MEDIUM);
        expect(error.isRetryable).toBe(false);
      });

      it('should handle schema context', () => {
        const context: Partial<SchemaErrorContext> = {
          typeName: 'Person',
          propertyName: 'name',
          expectedType: 'string',
          actualType: 'number',
          violatedRule: 'type_constraint',
        };

        const error = new SchemaError('Type mismatch', context);

        expect((error.errorContext as SchemaErrorContext).typeName).toBe('Person');
        expect((error.errorContext as SchemaErrorContext).propertyName).toBe('name');
        expect((error.errorContext as SchemaErrorContext).expectedType).toBe('string');
        expect((error.errorContext as SchemaErrorContext).actualType).toBe('number');
        expect((error.errorContext as SchemaErrorContext).violatedRule).toBe('type_constraint');
      });
    });

    describe('ValidationError', () => {
      it('should create validation error with correct defaults', () => {
        const error = new ValidationError('Field validation failed');

        expect(error.code).toBe(ErrorCode.VALIDATION_ERROR);
        expect(error.category).toBe(ErrorCategory.VALIDATION);
        expect(error.severity).toBe(ErrorSeverity.MEDIUM);
        expect(error.isRetryable).toBe(false);
      });
    });

    describe('EmbeddingError', () => {
      it('should create embedding error with correct defaults', () => {
        const error = new EmbeddingError('Embedding generation failed');

        expect(error.code).toBe(ErrorCode.EMBEDDING_ERROR);
        expect(error.category).toBe(ErrorCategory.EMBEDDING);
        expect(error.severity).toBe(ErrorSeverity.MEDIUM);
        expect(error.isRetryable).toBe(true);
      });
    });

    describe('QueryError', () => {
      it('should create query error with correct defaults', () => {
        const error = new QueryError('Query execution failed');

        expect(error.code).toBe(ErrorCode.QUERY_ERROR);
        expect(error.category).toBe(ErrorCategory.QUERY);
        expect(error.severity).toBe(ErrorSeverity.MEDIUM);
        expect(error.isRetryable).toBe(true);
      });
    });

    describe('McpProtocolError', () => {
      it('should create MCP protocol error with correct defaults', () => {
        const error = new McpProtocolError('MCP protocol violation');

        expect(error.code).toBe(ErrorCode.MCP_PROTOCOL_ERROR);
        expect(error.category).toBe(ErrorCategory.MCP_PROTOCOL);
        expect(error.severity).toBe(ErrorSeverity.HIGH);
        expect(error.isRetryable).toBe(true);
      });
    });
  });

  describe('MCP Error Mapping', () => {
    it('should map parse error correctly', () => {
      const mcpError = { code: -32000, message: 'Parse error' };
      const error = mapMcpError(mcpError, 'create_object_type');

      expect(error).toBeInstanceOf(McpProtocolError);
      expect(error.message).toContain('MCP protocol error');
      expect((error.errorContext as any).httpStatusCode).toBe(400);
    });

    it('should map invalid request error correctly', () => {
      const mcpError = { code: -32600, message: 'Invalid request' };
      const error = mapMcpError(mcpError, 'get_object_type');

      expect(error).toBeInstanceOf(ValidationError);
      expect(error.message).toContain('Invalid request');
    });

    it('should map method not found error correctly', () => {
      const mcpError = { code: -32601, message: 'Method not found' };
      const error = mapMcpError(mcpError, 'unknown_method');

      expect(error).toBeInstanceOf(McpProtocolError);
      expect(error.message).toContain('Method not found');
      expect((error.errorContext as any).httpStatusCode).toBe(404);
    });

    it('should map invalid params error correctly', () => {
      const mcpError = { code: -32602, message: 'Invalid parameters' };
      const error = mapMcpError(mcpError, 'create_relation_type');

      expect(error).toBeInstanceOf(ValidationError);
      expect(error.message).toContain('Invalid parameters');
    });

    it('should map internal error correctly', () => {
      const mcpError = { code: -32603, message: 'Internal error' };
      const error = mapMcpError(mcpError, 'complex_query');

      expect(error).toBeInstanceOf(McpProtocolError);
      expect(error.message).toContain('MCP server internal error');
      expect((error.errorContext as any).httpStatusCode).toBe(500);
    });

    it('should map connection failed error correctly', () => {
      const mcpError = { code: -1, message: 'Connection failed' };
      const error = mapMcpError(mcpError, 'connect');

      expect(error).toBeInstanceOf(ConnectionError);
      expect(error.message).toContain('Connection failed');
    });

    it('should map timeout error correctly', () => {
      const mcpError = { code: -2, message: 'Timeout' };
      const error = mapMcpError(mcpError, 'query');

      expect(error).toBeInstanceOf(ConnectionError);
      expect(error.message).toContain('Connection timeout');
    });

    it('should map schema validation error correctly', () => {
      const mcpError = { code: 1001, message: 'Schema validation failed' };
      const error = mapMcpError(mcpError, 'create_object_type');

      expect(error).toBeInstanceOf(SchemaError);
      expect(error.message).toContain('Schema validation failed');
    });

    it('should map unknown error to generic MCP protocol error', () => {
      const mcpError = { code: 9999, message: 'Unknown error' };
      const error = mapMcpError(mcpError, 'unknown_operation');

      expect(error).toBeInstanceOf(McpProtocolError);
      expect(error.message).toContain('MCP error (9999): Unknown error');
    });
  });

  describe('Retry Logic', () => {
    describe('isRetryableError', () => {
      it('should return true for retryable Grizabella errors', () => {
        const connectionError = new ConnectionError('Connection failed');
        expect(isRetryableError(connectionError)).toBe(true);
      });

      it('should return false for non-retryable Grizabella errors', () => {
        const validationError = new ValidationError('Validation failed');
        expect(isRetryableError(validationError)).toBe(false);
      });

      it('should return true for generic errors with retryable keywords', () => {
        const timeoutError = new Error('Request timeout occurred');
        const connectionError = new Error('Network connection failed');
        const tempError = new Error('Temporary service unavailable');

        expect(isRetryableError(timeoutError)).toBe(true);
        expect(isRetryableError(connectionError)).toBe(true);
        expect(isRetryableError(tempError)).toBe(true);
      });

      it('should return false for generic errors without retryable keywords', () => {
        const validationError = new Error('Invalid input format');
        const authError = new Error('Authentication failed');

        expect(isRetryableError(validationError)).toBe(false);
        expect(isRetryableError(authError)).toBe(false);
      });
    });

    describe('withRetry', () => {
      let mockOperation: jest.Mock;
      let mockError: Error;

      beforeEach(() => {
        mockOperation = jest.fn();
        mockError = new ConnectionError('Connection failed');
      });

      afterEach(() => {
        jest.clearAllMocks();
      });

      it('should succeed on first attempt', async () => {
        mockOperation.mockResolvedValue('success');

        const result = await withRetry(mockOperation);

        expect(result).toBe('success');
        expect(mockOperation).toHaveBeenCalledTimes(1);
      });

      it('should retry on failure and eventually succeed', async () => {
        mockOperation
          .mockRejectedValueOnce(mockError)
          .mockResolvedValue('success');

        const result = await withRetry(mockOperation, { maxRetries: 2, initialDelay: 1 });

        expect(result).toBe('success');
        expect(mockOperation).toHaveBeenCalledTimes(2);
      });

      it('should fail after all retries exhausted', async () => {
        mockOperation.mockRejectedValue(mockError);

        await expect(withRetry(mockOperation, { maxRetries: 2, initialDelay: 1 })).rejects.toThrow('Connection failed');
        expect(mockOperation).toHaveBeenCalledTimes(3);
      });

      it('should use exponential backoff', async () => {
        mockOperation.mockRejectedValue(mockError);

        await expect(withRetry(mockOperation, {
          maxRetries: 2,
          initialDelay: 1,
          backoffMultiplier: 2,
        })).rejects.toThrow();

        expect(mockOperation).toHaveBeenCalledTimes(3);
      });

      it('should respect custom retry condition', async () => {
        mockOperation.mockRejectedValue(mockError);

        const shouldRetry = jest.fn().mockReturnValue(false);
        await expect(withRetry(mockOperation, { shouldRetry })).rejects.toThrow();

        expect(mockOperation).toHaveBeenCalledTimes(1);
      });
    });

    describe('handleErrors decorator', () => {
      class TestClass {
        @handleErrors({
          retry: { maxRetries: 1 },
          logError: false,
        })
        async successfulOperation() {
          return 'success';
        }

        @handleErrors({
          retry: { maxRetries: 1 },
          logError: false,
        })
        async failingOperation() {
          throw new ConnectionError('Operation failed');
        }

        @handleErrors({
          mapError: (err) => new ValidationError('Mapped error', {}, err),
        })
        async operationWithCustomMapping() {
          throw new Error('Original error');
        }
      }

      it('should handle successful operations normally', async () => {
        const instance = new TestClass();
        const result = await instance.successfulOperation();

        expect(result).toBe('success');
      });

      it('should retry failing operations', async () => {
        const instance = new TestClass();

        await expect(instance.failingOperation()).rejects.toThrow('Operation failed');
      });

      it('should map errors with custom mapper', async () => {
        const instance = new TestClass();

        await expect(instance.operationWithCustomMapping()).rejects.toThrow('Mapped error');
      });
    });
  });

  describe('Error Boundary', () => {
    it('should create error boundary with correct initial state', () => {
      const boundary = createErrorBoundary();

      expect(boundary.error).toBeNull();
      expect(boundary.hasError).toBe(false);
    });

    it('should set and clear errors correctly', () => {
      const boundary = createErrorBoundary();
      const testError = new ValidationError('Test error');

      boundary.setError(testError);

      expect(boundary.error).toBe(testError);
      expect(boundary.hasError).toBe(true);

      boundary.clearError();

      expect(boundary.error).toBeNull();
      expect(boundary.hasError).toBe(false);
    });
  });

  describe('Logging Integration', () => {

    describe('ConsoleErrorLogger', () => {
      let logger: ConsoleErrorLogger;
      let error: GrizabellaError;

      beforeEach(() => {
        logger = new ConsoleErrorLogger();
        error = new ValidationError('Test error');
      });


      it('should warn for medium severity errors', () => {
        const warnSpy = jest.spyOn(console, 'warn').mockImplementation();

        logger.warn(error);

        expect(warnSpy).toHaveBeenCalledWith(
          expect.stringContaining('[4000] Test error'),
          expect.any(Object)
        );

        warnSpy.mockRestore();
      });

      it('should error for high severity errors', () => {
        const errorSpy = jest.spyOn(console, 'error').mockImplementation();
        const highSeverityError = new GrizabellaError(
          'High severity error',
          ErrorCode.GENERIC_ERROR,
          ErrorCategory.SYSTEM,
          ErrorSeverity.HIGH,
          false
        );

        logger.error(highSeverityError);

        expect(errorSpy).toHaveBeenCalledWith(
          expect.stringContaining('[1000] High severity error'),
          expect.any(Object)
        );

        errorSpy.mockRestore();
      });
    });

    describe('Global Error Logger', () => {
      it('should set and get global logger correctly', () => {
        const customLogger: ErrorLogger = {
          log: jest.fn(),
          warn: jest.fn(),
          error: jest.fn(),
        };

        setGlobalErrorLogger(customLogger);
        expect(getGlobalErrorLogger()).toBe(customLogger);
      });

      it('should log errors based on severity', () => {
        const logger = getGlobalErrorLogger();
        const logSpy = jest.spyOn(logger, 'log').mockImplementation();
        const warnSpy = jest.spyOn(logger, 'warn').mockImplementation();
        const errorSpy = jest.spyOn(logger, 'error').mockImplementation();

        // Test low severity
        const lowSeverityError = new GrizabellaError(
          'Low severity error',
          ErrorCode.GENERIC_ERROR,
          ErrorCategory.SYSTEM,
          ErrorSeverity.LOW,
          false
        );
        logError(lowSeverityError);

        // Test medium severity
        const mediumSeverityError = new GrizabellaError(
          'Medium severity error',
          ErrorCode.GENERIC_ERROR,
          ErrorCategory.SYSTEM,
          ErrorSeverity.MEDIUM,
          false
        );
        logError(mediumSeverityError);

        // Test high severity
        const highSeverityError = new GrizabellaError(
          'High severity error',
          ErrorCode.GENERIC_ERROR,
          ErrorCategory.SYSTEM,
          ErrorSeverity.HIGH,
          false
        );
        logError(highSeverityError);

        expect(logSpy).toHaveBeenCalledTimes(1);
        expect(warnSpy).toHaveBeenCalledTimes(1);
        expect(errorSpy).toHaveBeenCalledTimes(1);

        logSpy.mockRestore();
        warnSpy.mockRestore();
        errorSpy.mockRestore();
      });
    });
  });

  describe('Utility Functions', () => {
    describe('isGrizabellaError', () => {
      it('should return true for GrizabellaError instances', () => {
        const error = new ConnectionError('Test error');
        expect(isGrizabellaError(error)).toBe(true);
      });

      it('should return false for regular Error instances', () => {
        const error = new Error('Test error');
        expect(isGrizabellaError(error)).toBe(false);
      });

      it('should return false for non-error objects', () => {
        expect(isGrizabellaError('string')).toBe(false);
        expect(isGrizabellaError({})).toBe(false);
        expect(isGrizabellaError(null)).toBe(false);
        expect(isGrizabellaError(undefined)).toBe(false);
      });
    });

    describe('isErrorType', () => {
      it('should return true for correct error type', () => {
        const error = new ConnectionError('Test error');
        expect(isErrorType(error, ConnectionError as any)).toBe(true);
      });

      it('should return false for incorrect error type', () => {
        const error = new ConnectionError('Test error');
        expect(isErrorType(error, ValidationError as any)).toBe(false);
      });
    });

    describe('createErrorMessage', () => {
      it('should create message without context', () => {
        const message = createErrorMessage('Base message');
        expect(message).toBe('Base message');
      });

      it('should create message with context', () => {
        const context = {
          operation: 'create_object_type',
          typeName: 'Person',
          userId: 'user123',
          undefinedValue: undefined,
          nullValue: null,
        };

        const message = createErrorMessage('Base message', context);
        expect(message).toBe('Base message (operation: create_object_type, typeName: Person, userId: user123)');
      });
    });

    describe('extractErrorContext', () => {
      it('should extract context from Error instance', () => {
        const originalError = new Error('Original error message');
        originalError.stack = 'stack trace';

        const context = extractErrorContext(originalError);

        expect(context.context?.['originalMessage']).toBe('Original error message');
        expect(context.stack).toBe('stack trace');
      });

      it('should extract context from string', () => {
        const errorString = 'Error message';
        const context = extractErrorContext(errorString);

        expect(context.context?.['originalMessage']).toBe('Error message');
      });

      it('should extract context from unknown object', () => {
        const errorObject = { customProperty: 'custom value' };
        const context = extractErrorContext(errorObject);

        expect(context.context?.['originalError']).toEqual(errorObject);
      });
    });
  });
});