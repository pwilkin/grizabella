/**
 * Comprehensive Error Handling Framework for Grizabella TypeScript API
 *
 * This module provides a robust error handling system that maps MCP protocol
 * errors to user-friendly TypeScript exceptions, with consistent error codes,
 * context preservation, and recovery strategies.
 */

// ===== ERROR CODES AND CONSTANTS =====

/**
 * Enumeration of error codes for consistent error identification across the API.
 * These codes follow a hierarchical structure for better categorization.
 */
export enum ErrorCode {
  // ===== GENERAL ERRORS (1000-1999) =====
  /** Generic error base code */
  GENERIC_ERROR = 1000,
  /** Configuration error */
  CONFIGURATION_ERROR = 1100,
  /** Initialization error */
  INITIALIZATION_ERROR = 1200,

  // ===== CONNECTION ERRORS (2000-2999) =====
  /** Generic connection error */
  CONNECTION_ERROR = 2000,
  /** Network connection failed */
  CONNECTION_FAILED = 2100,
  /** Connection timeout */
  CONNECTION_TIMEOUT = 2200,
  /** Connection closed unexpectedly */
  CONNECTION_CLOSED = 2300,
  /** Not connected error */
  NOT_CONNECTED = 2400,
  /** Authentication/authorization error */
  AUTHENTICATION_ERROR = 2500,

  // ===== SCHEMA ERRORS (3000-3999) =====
  /** Generic schema error */
  SCHEMA_ERROR = 3000,
  /** Invalid schema definition */
  INVALID_SCHEMA = 3100,
  /** Schema validation failed */
  SCHEMA_VALIDATION_FAILED = 3200,
  /** Property definition error */
  PROPERTY_DEFINITION_ERROR = 3300,
  /** Type definition error */
  TYPE_DEFINITION_ERROR = 3400,
  /** Constraint violation */
  CONSTRAINT_VIOLATION = 3500,

  // ===== VALIDATION ERRORS (4000-4999) =====
  /** Generic validation error */
  VALIDATION_ERROR = 4000,
  /** Required field missing */
  REQUIRED_FIELD_MISSING = 4100,
  /** Invalid data type */
  INVALID_DATA_TYPE = 4200,
  /** Invalid value format */
  INVALID_VALUE_FORMAT = 4300,
  /** Value out of range */
  VALUE_OUT_OF_RANGE = 4400,

  // ===== EMBEDDING ERRORS (5000-5999) =====
  /** Generic embedding error */
  EMBEDDING_ERROR = 5000,
  /** Embedding model not found */
  EMBEDDING_MODEL_NOT_FOUND = 5100,
  /** Embedding generation failed */
  EMBEDDING_GENERATION_FAILED = 5200,
  /** Embedding dimension mismatch */
  EMBEDDING_DIMENSION_MISMATCH = 5300,
  /** Embedding storage error */
  EMBEDDING_STORAGE_ERROR = 5400,

  // ===== QUERY ERRORS (6000-6999) =====
  /** Generic query error */
  QUERY_ERROR = 6000,
  /** Invalid query syntax */
  INVALID_QUERY_SYNTAX = 6100,
  /** Query execution failed */
  QUERY_EXECUTION_FAILED = 6200,
  /** Query timeout */
  QUERY_TIMEOUT = 6300,
  /** Unsupported query operation */
  UNSUPPORTED_QUERY_OPERATION = 6400,

  // ===== MCP PROTOCOL ERRORS (7000-7999) =====
  /** Generic MCP protocol error */
  MCP_PROTOCOL_ERROR = 7000,
  /** MCP request failed */
  MCP_REQUEST_FAILED = 7100,
  /** MCP response parsing error */
  MCP_RESPONSE_PARSING_ERROR = 7200,
  /** MCP server error */
  MCP_SERVER_ERROR = 7300,
  /** MCP method not found */
  MCP_METHOD_NOT_FOUND = 7400,
}

/**
 * Error severity levels for categorizing errors by their impact.
 */
export enum ErrorSeverity {
  /** Low severity - informational or minor issues */
  LOW = 'LOW',
  /** Medium severity - functional issues that don't break the system */
  MEDIUM = 'MEDIUM',
  /** High severity - serious issues that may break functionality */
  HIGH = 'HIGH',
  /** Critical severity - system-breaking errors */
  CRITICAL = 'CRITICAL',
}

/**
 * Error categories for high-level error classification.
 */
export enum ErrorCategory {
  /** Network and connection related errors */
  CONNECTION = 'CONNECTION',
  /** Authentication and authorization errors */
  AUTHENTICATION = 'AUTHENTICATION',
  /** Schema and data validation errors */
  SCHEMA = 'SCHEMA',
  /** Data validation errors */
  VALIDATION = 'VALIDATION',
  /** Embedding-related errors */
  EMBEDDING = 'EMBEDDING',
  /** Query execution errors */
  QUERY = 'QUERY',
  /** MCP protocol errors */
  MCP_PROTOCOL = 'MCP_PROTOCOL',
  /** General system errors */
  SYSTEM = 'SYSTEM',
}

// ===== ERROR CONTEXT INTERFACES =====

/**
 * Base error context interface that all error contexts should extend.
 */
export interface BaseErrorContext {
  /** Timestamp when the error occurred */
  timestamp: Date;
  /** Additional contextual information */
  context?: Record<string, any>;
  /** Stack trace if available */
  stack?: string;
  /** Operation that was being performed when error occurred */
  operation?: string;
  /** User ID or session information if available */
  userId?: string;
  /** Request ID for tracking purposes */
  requestId?: string;
}

/**
 * Connection-related error context.
 */
export interface ConnectionErrorContext extends BaseErrorContext {
  /** Hostname or IP address that failed */
  host?: string;
  /** Port number that was attempted */
  port?: number;
  /** Connection timeout value */
  timeout?: number;
  /** Number of retry attempts made */
  retryCount?: number;
  /** Connection protocol (http, https, ws, etc.) */
  protocol?: string;
}

/**
 * Schema-related error context.
 */
export interface SchemaErrorContext extends BaseErrorContext {
  /** Name of the object type or relation type involved */
  typeName?: string;
  /** Property name that caused the error */
  propertyName?: string;
  /** Expected data type */
  expectedType?: string;
  /** Actual data type received */
  actualType?: string;
  /** Validation rule that was violated */
  violatedRule?: string;
  /** Schema definition that was being validated */
  schemaDefinition?: Record<string, any>;
}

/**
 * Validation-related error context.
 */
export interface ValidationErrorContext extends BaseErrorContext {
  /** Field name that failed validation */
  fieldName?: string;
  /** Expected value format or pattern */
  expectedFormat?: string;
  /** Actual value that caused validation failure */
  actualValue?: any;
  /** Validation rule that was violated */
  violatedRule?: string;
  /** Constraints that were checked */
  constraints?: Record<string, any>;
}

/**
 * Embedding-related error context.
 */
export interface EmbeddingErrorContext extends BaseErrorContext {
  /** Embedding model identifier */
  modelId?: string;
  /** Text that was being embedded */
  inputText?: string;
  /** Input text length */
  inputLength?: number;
  /** Expected embedding dimension */
  expectedDimension?: number;
  /** Actual embedding dimension */
  actualDimension?: number;
  /** Embedding generation parameters */
  parameters?: Record<string, any>;
}

/**
 * Query-related error context.
 */
export interface QueryErrorContext extends BaseErrorContext {
  /** Query that was being executed */
  query?: string;
  /** Query parameters */
  parameters?: Record<string, any>;
  /** Query execution time before timeout */
  executionTime?: number;
  /** Database or backend that was queried */
  backend?: string;
  /** Query result count if available */
  resultCount?: number;
}

/**
 * MCP protocol error context.
 */
export interface McpErrorContext extends BaseErrorContext {
  /** MCP method that was called */
  method?: string;
  /** MCP request ID */
  mcpRequestId?: string;
  /** MCP server URL or identifier */
  serverUrl?: string;
  /** Raw MCP response if available */
  rawResponse?: any;
  /** HTTP status code if applicable */
  httpStatusCode?: number;
}

// ===== BASE ERROR CLASS =====

/**
 * Base error class for all Grizabella API errors.
 * Provides consistent error handling with context preservation and debugging support.
 */
export class GrizabellaError extends Error {
  /** Error code for programmatic handling */
  public readonly code: ErrorCode;
  /** Error category for high-level classification */
  public readonly category: ErrorCategory;
  /** Error severity level */
  public readonly severity: ErrorSeverity;
  /** Whether this error is retryable */
  public readonly isRetryable: boolean;
  /** Error context with additional debugging information */
  public readonly errorContext: BaseErrorContext;
  /** Original error that caused this error (if any) */
  public override readonly cause?: Error;

  constructor(
    message: string,
    code: ErrorCode,
    category: ErrorCategory,
    severity: ErrorSeverity,
    isRetryable: boolean = false,
    context: Partial<BaseErrorContext> = {},
    cause?: Error
  ) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.category = category;
    this.severity = severity;
    this.isRetryable = isRetryable;
    if (cause) {
      this.cause = cause;
    }

    // Capture stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }

    // Build error context
    this.errorContext = {
      timestamp: new Date(),
      context: {},
      ...context,
    };

    if (this.stack) {
      this.errorContext.stack = this.stack;
    }
  }

  /**
   * Convert error to a plain object for logging or serialization.
   */
  public toJSON(): Record<string, any> {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      category: this.category,
      severity: this.severity,
      isRetryable: this.isRetryable,
      errorContext: this.errorContext,
      cause: this.cause ? {
        name: this.cause.name,
        message: this.cause.message,
        stack: this.cause.stack,
      } : undefined,
    };
  }

  /**
   * Create a detailed error message with context.
   */
  public getDetailedMessage(): string {
    let message = `[${this.code}] ${this.message}`;

    if (this.errorContext.operation) {
      message += ` (Operation: ${this.errorContext.operation})`;
    }

    if (this.errorContext.requestId !== undefined) {
      message += ` (Request ID: ${this.errorContext.requestId})`;
    }

    return message;
  }
}

// ===== SPECIFIC ERROR CLASSES =====

/**
 * Error thrown when connection-related issues occur.
 */
export class ConnectionError extends GrizabellaError {
  constructor(
    message: string,
    context: Partial<ConnectionErrorContext> = {},
    cause?: Error
  ) {
    super(
      message,
      ErrorCode.CONNECTION_ERROR,
      ErrorCategory.CONNECTION,
      ErrorSeverity.HIGH,
      true, // Connection errors are generally retryable
      context,
      cause
    );
  }
}

/**
 * Error thrown when not connected to a service.
*/
export class NotConnectedError extends GrizabellaError {
  constructor(
    message: string = 'Not connected to the service',
    context: Partial<ConnectionErrorContext> = {},
    cause?: Error
  ) {
    super(
      message,
      ErrorCode.NOT_CONNECTED,
      ErrorCategory.CONNECTION,
      ErrorSeverity.HIGH,
      false, // Not connected errors are generally not retryable
      context,
      cause
    );
  }
}

/**
 * Error thrown when schema validation or definition issues occur.
 */
export class SchemaError extends GrizabellaError {
  constructor(
    message: string,
    context: Partial<SchemaErrorContext> = {},
    cause?: Error
  ) {
    super(
      message,
      ErrorCode.SCHEMA_ERROR,
      ErrorCategory.SCHEMA,
      ErrorSeverity.MEDIUM,
      false, // Schema errors are generally not retryable
      context,
      cause
    );
  }
}

/**
 * Error thrown when data validation fails.
 */
export class ValidationError extends GrizabellaError {
  constructor(
    message: string,
    context: Partial<ValidationErrorContext> = {},
    cause?: Error
  ) {
    super(
      message,
      ErrorCode.VALIDATION_ERROR,
      ErrorCategory.VALIDATION,
      ErrorSeverity.MEDIUM,
      false, // Validation errors are generally not retryable
      context,
      cause
    );
  }
}

/**
 * Error thrown when embedding-related issues occur.
 */
export class EmbeddingError extends GrizabellaError {
  constructor(
    message: string,
    context: Partial<EmbeddingErrorContext> = {},
    cause?: Error
  ) {
    super(
      message,
      ErrorCode.EMBEDDING_ERROR,
      ErrorCategory.EMBEDDING,
      ErrorSeverity.MEDIUM,
      true, // Embedding errors can be retryable depending on the cause
      context,
      cause
    );
  }
}

/**
 * Error thrown when query execution fails.
 */
export class QueryError extends GrizabellaError {
  constructor(
    message: string,
    context: Partial<QueryErrorContext> = {},
    cause?: Error
  ) {
    super(
      message,
      ErrorCode.QUERY_ERROR,
      ErrorCategory.QUERY,
      ErrorSeverity.MEDIUM,
      true, // Query errors are often retryable
      context,
      cause
    );
  }
}

/**
 * Error thrown when MCP protocol issues occur.
 */
export class McpProtocolError extends GrizabellaError {
  constructor(
    message: string,
    context: Partial<McpErrorContext> = {},
    cause?: Error
  ) {
    super(
      message,
      ErrorCode.MCP_PROTOCOL_ERROR,
      ErrorCategory.MCP_PROTOCOL,
      ErrorSeverity.HIGH,
      true, // MCP protocol errors are generally retryable
      context,
      cause
    );
  }
}

// ===== MCP ERROR MAPPING UTILITIES =====

/**
 * Configuration for MCP error mapping.
 */
export interface McpErrorMappingConfig {
  /** Whether to include stack traces in mapped errors */
  includeStackTrace: boolean;
  /** Whether to preserve original MCP error details */
  preserveOriginalError: boolean;
  /** Custom error message mappings */
  customMessageMappings?: Record<string, string>;
}

/**
 * MCP error response structure.
 */
export interface McpErrorResponse {
  /** MCP error code */
  code: number;
  /** Error message */
  message: string;
  /** Additional error data */
  data?: any;
}

/**
 * Maps MCP protocol errors to appropriate GrizabellaError subclasses.
 * This function provides a centralized way to convert raw MCP errors into
 * user-friendly, typed errors that fit the Grizabella error hierarchy.
 */
export function mapMcpError(
  mcpError: McpErrorResponse,
  operation: string = 'unknown',
  config: Partial<McpErrorMappingConfig> = {}
): GrizabellaError {
  const defaultConfig: McpErrorMappingConfig = {
    includeStackTrace: false,
    preserveOriginalError: true,
    ...config,
  };

  const context: Partial<McpErrorContext> = {
    method: operation,
    rawResponse: defaultConfig.preserveOriginalError ? mcpError : undefined,
    timestamp: new Date(),
    operation,
  };

  // Map MCP error codes to Grizabella error codes and classes
  switch (mcpError.code) {
    // Connection-related MCP errors
    case -32000: // Parse error
    case -32001: // Invalid request
    case -32002: // Method not found
      return new McpProtocolError(
        `MCP protocol error: ${mcpError.message}`,
        { ...context, httpStatusCode: 400 },
        new Error(mcpError.message)
      );

    case -32600: // Invalid Request
      return new ValidationError(
        `Invalid request: ${mcpError.message}`,
        { violatedRule: 'request_format' },
        new Error(mcpError.message)
      );

    case -32601: // Method not found
      return new McpProtocolError(
        `Method not found: ${mcpError.message}`,
        { ...context, httpStatusCode: 404 },
        new Error(mcpError.message)
      );

    case -32602: // Invalid params
      return new ValidationError(
        `Invalid parameters: ${mcpError.message}`,
        { violatedRule: 'parameter_validation' },
        new Error(mcpError.message)
      );

    case -32603: // Internal error
      return new McpProtocolError(
        `MCP server internal error: ${mcpError.message}`,
        { ...context, httpStatusCode: 500 },
        new Error(mcpError.message)
      );

    case -32700: // Parse error
      return new McpProtocolError(
        `Failed to parse MCP response: ${mcpError.message}`,
        { ...context, httpStatusCode: 400 },
        new Error(mcpError.message)
      );

    // Network-related errors (typically negative codes)
    case -1: // Connection failed
      return new ConnectionError(
        `Connection failed: ${mcpError.message}`,
        { retryCount: 0 },
        new Error(mcpError.message)
      );

    case -2: // Timeout
      return new ConnectionError(
        `Connection timeout: ${mcpError.message}`,
        { timeout: 30000 }, // Default 30s timeout
        new Error(mcpError.message)
      );

    // Schema-related errors
    case 1001: // Schema validation error
      return new SchemaError(
        `Schema validation failed: ${mcpError.message}`,
        { violatedRule: 'schema_validation' },
        new Error(mcpError.message)
      );

    // Default case for unknown MCP errors
    default:
      return new McpProtocolError(
        `MCP error (${mcpError.code}): ${mcpError.message}`,
        context,
        new Error(mcpError.message)
      );
  }
}

/**
 * Utility function to check if an error is retryable based on its type and context.
 */
export function isRetryableError(error: Error): boolean {
  if (error instanceof GrizabellaError) {
    return error.isRetryable;
  }

  // For non-Grizabella errors, apply default retry logic
  const retryableMessages = [
    'timeout',
    'connection',
    'network',
    'temporary',
    'service unavailable',
    'server error',
  ];

  const message = error.message.toLowerCase();
  return retryableMessages.some(keyword => message.includes(keyword));
}

// ===== ERROR HANDLING PATTERNS =====

/**
 * Configuration for retry behavior.
 */
export interface RetryConfig {
  /** Maximum number of retry attempts */
  maxRetries: number;
  /** Initial delay before first retry (ms) */
  initialDelay: number;
  /** Maximum delay between retries (ms) */
  maxDelay: number;
  /** Backoff multiplier for exponential backoff */
  backoffMultiplier: number;
  /** Function to determine if an error should be retried */
  shouldRetry?: (error: Error, attempt: number) => boolean;
}

/**
 * Default retry configuration.
 */
export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 30000,
  backoffMultiplier: 2,
  shouldRetry: (error: Error, attempt: number) => {
    return attempt < 3 && isRetryableError(error);
  },
};

/**
 * Retry wrapper function for operations that may fail.
 */
export async function withRetry<T>(
  operation: () => Promise<T>,
  config: Partial<RetryConfig> = {}
): Promise<T> {
  const finalConfig = { ...DEFAULT_RETRY_CONFIG, ...config };
  let lastError: Error;
  let delay = finalConfig.initialDelay;

  for (let attempt = 0; attempt <= finalConfig.maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error as Error;

      // Check if we should retry
      if (attempt < finalConfig.maxRetries &&
          finalConfig.shouldRetry!(lastError, attempt)) {

        // Wait before retrying
        await new Promise(resolve => setTimeout(resolve, delay));

        // Calculate next delay with exponential backoff
        delay = Math.min(delay * finalConfig.backoffMultiplier, finalConfig.maxDelay);
      } else {
        break;
      }
    }
  }

  throw lastError!;
}

/**
 * Decorator function for methods that need error handling.
 * This is a higher-order function that wraps method calls with error handling.
 */
export function handleErrors(
  config: {
    retry?: Partial<RetryConfig>;
    mapError?: (error: Error) => GrizabellaError;
    logError?: boolean;
  } = {}
) {
  return function (
    _target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;

    descriptor.value = async function (...args: any[]) {
      const operation = () => originalMethod.apply(this, args);

      try {
        if (config.retry) {
          return await withRetry(operation, config.retry);
        } else {
          return await operation();
        }
      } catch (error) {
        const err = error as Error;

        // Log error if requested
        if (config.logError) {
          console.error(`Error in ${propertyKey}:`, err);
        }

        // Map error if custom mapping provided
        if (config.mapError) {
          throw config.mapError(err);
        }

        throw err;
      }
    };

    return descriptor;
  };
}

/**
 * Error boundary context for managing error state in applications.
 */
export interface ErrorBoundaryContext {
  /** Current error if any */
  error: GrizabellaError | null;
  /** Whether the error boundary is in error state */
  hasError: boolean;
  /** Function to clear the error */
  clearError: () => void;
  /** Function to set a new error */
  setError: (error: GrizabellaError) => void;
}

/**
 * Creates an error boundary context for managing error state.
 */
export function createErrorBoundary(): ErrorBoundaryContext {
  let currentError: GrizabellaError | null = null;

  return {
    get error() {
      return currentError;
    },

    get hasError() {
      return currentError !== null;
    },

    clearError() {
      currentError = null;
    },

    setError(error: GrizabellaError) {
      currentError = error;
    },
  };
}

// ===== LOGGING INTEGRATION =====

/**
 * Logger interface for error logging.
 */
export interface ErrorLogger {
  log(error: GrizabellaError): void;
  warn(error: GrizabellaError): void;
  error(error: GrizabellaError): void;
}

/**
 * Console-based error logger implementation.
 */
export class ConsoleErrorLogger implements ErrorLogger {
  log(error: GrizabellaError): void {
    console.log(error.getDetailedMessage(), error.toJSON());
  }

  warn(error: GrizabellaError): void {
    console.warn(error.getDetailedMessage(), error.toJSON());
  }

  error(error: GrizabellaError): void {
    console.error(error.getDetailedMessage(), error.toJSON());
  }
}

/**
 * Global error logger instance.
 */
let globalErrorLogger: ErrorLogger = new ConsoleErrorLogger();

/**
 * Set the global error logger.
 */
export function setGlobalErrorLogger(logger: ErrorLogger): void {
  globalErrorLogger = logger;
}

/**
 * Get the current global error logger.
 */
export function getGlobalErrorLogger(): ErrorLogger {
  return globalErrorLogger;
}

/**
 * Log an error using the global error logger.
 */
export function logError(error: GrizabellaError): void {
  switch (error.severity) {
    case ErrorSeverity.LOW:
      globalErrorLogger.log(error);
      break;
    case ErrorSeverity.MEDIUM:
      globalErrorLogger.warn(error);
      break;
    case ErrorSeverity.HIGH:
    case ErrorSeverity.CRITICAL:
      globalErrorLogger.error(error);
      break;
  }
}

// ===== UTILITY FUNCTIONS =====

/**
 * Type guard to check if an error is a GrizabellaError.
 */
export function isGrizabellaError(error: any): error is GrizabellaError {
  return error instanceof GrizabellaError;
}

/**
 * Type guard to check if an error is a specific error type.
 */
export function isErrorType<T extends GrizabellaError>(
  error: any,
  ErrorClass: new (...args: any[]) => T
): error is T {
  return error instanceof ErrorClass;
}

/**
 * Create a standardized error message with context.
 */
export function createErrorMessage(
  baseMessage: string,
  context?: Record<string, any>
): string {
  if (!context) {
    return baseMessage;
  }

  const contextParts = Object.entries(context)
    .filter(([_, value]) => value !== undefined && value !== null)
    .map(([key, value]) => `${key}: ${value}`)
    .join(', ');

  return contextParts ? `${baseMessage} (${contextParts})` : baseMessage;
}

/**
 * Extract error context from an unknown error.
 */
export function extractErrorContext(error: unknown): Partial<BaseErrorContext> {
  const context: Partial<BaseErrorContext> = {
    context: {},
  };

  if (error instanceof Error) {
    context.context = { originalMessage: error.message };
    if (error.stack) {
      context.stack = error.stack;
    }
  } else if (typeof error === 'string') {
    context.context = { originalMessage: error };
  } else {
    context.context = { originalError: error };
  }

  return context;
}