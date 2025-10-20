/**
 * Grizabella TypeScript API
 *
 * Main entry point for the TypeScript client library.
 * This file exports all public APIs and serves as the main module.
 */

// Export version information
export const VERSION = '1.0.0';

// Export Decimal for use in examples
export { Decimal } from 'decimal.js';

// ===== TYPE DEFINITIONS =====
export * from './types/index';

// ===== ERROR HANDLING FRAMEWORK =====
export {
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
  BaseErrorContext,
  ConnectionErrorContext,
  SchemaErrorContext,
  ValidationErrorContext,
  EmbeddingErrorContext,
  QueryErrorContext,
  McpErrorContext,

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

  // Configuration
  RetryConfig,
  DEFAULT_RETRY_CONFIG,
  ErrorBoundaryContext,

  // Utility functions
  isGrizabellaError,
  isErrorType,
  createErrorMessage,
  extractErrorContext,
} from './client/errors';

// ===== UTILITY FUNCTIONS =====

// Validation utilities
export {
  isValidUUID,
  validateUUID,
  normalizeUUID,
  validatePropertyDataType,
  validatePropertyDefinition,
  validateObjectTypeDefinition,
  validateObjectInstance,
  validateRelationTypeDefinition,
  validateRelationInstance,
  validateFilterValue,
  validateSchemaCompliance,
  validateObjectInstances,
  validateRelationInstances,
} from './utils/validation';

// Type conversion utilities
export {
  toDecimal,
  decimalToNumber,
  decimalToJSON,
  jsonToDecimal,
  toDate,
  dateToISOString,
  dateToTimestamp,
  timestampToDate,
  dateToLocaleString,
  snakeToCamel,
  camelToSnake,
  objectKeysToCamel,
  objectKeysToSnake,
  convertPropertyValue,
  convertObjectInstance,
  convertFilterValue,
  objectInstanceToJSON,
  jsonToObjectInstance,
  convertObjectInstances,
  convertRelationInstances,
} from './utils/conversion';

// Helper functions
export {
  createObjectInstance,
  createObjectInstanceFromDefinition,
  createRelationInstance,
  createRelationsFromSource,
  createRelationsToTarget,
  createBidirectionalRelations,
  buildFindObjectsQuery,
  buildQueryRelationsQuery,
  FilterBuilder,
  createObjectType,
  PROPERTY_TEMPLATES,
  processObjectInstancesBatch,
  createMultipleObjectInstances,
  generateUniqueTypeName,
  cloneObjectInstance,
  getPropertyNames,
  hasProperty,
  getPropertyDefinition,
  ObjectInstanceConfig,
  RelationInstanceConfig,
  QueryBuilderConfig,
  ObjectTypeConfig,
  PropertyTemplate,
  BatchConfig,
} from './utils/helpers';

// Developer experience utilities
export {
  parseConnectionString,
  buildConnectionString,
  validateConnectionInfo,
  buildConfig,
  validateConfig,
  loadConfigFromEnv,
  DEFAULT_CONFIG,
  ConsoleDebugLogger,
  NoOpLogger,
  setGlobalLogger,
  getGlobalLogger,
  createComponentLogger,
  PerformanceMonitor,
  setGlobalMonitor,
  getGlobalMonitor,
  timeAsync,
  timeSync,
  createSampleObjectInstance,
  prettyPrint,
  createMemoryReport,
  healthCheck,
  ConnectionInfo,
  GrizabellaConfig,
  LogLevel,
  DebugLogger,
  PerformanceMeasurement,
} from './utils/dev';

// Export main components
export { GrizabellaClient, GrizabellaClientConfig, ClientConnectionState } from './client/GrizabellaClient';
// export { MCPIntegration } from './mcp';

// Main initialization function (to be implemented)
export function initialize(): void {
  // TODO: Initialize the Grizabella client
  console.log('Grizabella TypeScript API initialized');
}

// Main cleanup function (to be implemented)
export function cleanup(): void {
  // TODO: Clean up resources
  console.log('Grizabella TypeScript API cleanup');
}