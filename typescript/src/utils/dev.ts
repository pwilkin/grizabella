/**
 * Developer Experience Utilities for Grizabella TypeScript API
 *
 * This module provides utilities for connection management, configuration,
 * debugging, and performance monitoring to enhance the developer experience.
 */

// import { Decimal } from 'decimal.js'; // This import is not used in this file
import {
  ValidationError,
  createErrorMessage,
} from '../client/errors';

// ===== CONNECTION STRING PARSING =====

/**
 * Parsed connection string components.
 */
export interface ConnectionInfo {
  /** Connection protocol (http, https, ws, wss) */
  protocol: string;
  /** Hostname or IP address */
  host: string;
  /** Port number */
  port: number;
  /** Database or path */
  database?: string;
  /** Username for authentication */
  username?: string;
  /** Password for authentication */
  password?: string;
  /** Additional connection parameters */
  params: Record<string, string>;
}

/**
 * Parses a connection string into components.
 * Supports formats like: protocol://username:password@host:port/database?param=value
 */
export function parseConnectionString(connectionString: string): ConnectionInfo {
  try {
    const url = new URL(connectionString);

    const info: any = {
      protocol: url.protocol.replace(':', ''),
      host: url.hostname,
      port: parseInt(url.port, 10) || (url.protocol.startsWith('https') ? 443 : 80),
      database: url.pathname.replace('/', '') || undefined,
      params: {},
    };

    // Parse authentication
    if (url.username) {
      info.username = decodeURIComponent(url.username);
    }
    if (url.password) {
      info.password = decodeURIComponent(url.password);
    }

    // Parse query parameters
    for (const [key, value] of url.searchParams) {
      info.params[key] = value;
    }

    return info;
  } catch (error) {
    throw new ValidationError(
      createErrorMessage('Invalid connection string format', { connectionString, error }),
      { violatedRule: 'invalid_connection_string' }
    );
  }
}

/**
 * Builds a connection string from components.
 */
export function buildConnectionString(info: ConnectionInfo): string {
  const auth = info.username && info.password
    ? `${encodeURIComponent(info.username)}:${encodeURIComponent(info.password)}@`
    : info.username
      ? `${encodeURIComponent(info.username)}@`
      : '';

  const params = Object.keys(info.params).length > 0
    ? `?${new URLSearchParams(info.params).toString()}`
    : '';

  return `${info.protocol}://${auth}${info.host}:${info.port}/${info.database || ''}${params}`;
}

/**
 * Validates connection string components.
 */
export function validateConnectionInfo(info: ConnectionInfo): void {
  if (!info.protocol) {
    throw new ValidationError('Connection protocol is required', { violatedRule: 'missing_protocol' });
  }

  if (!info.host) {
    throw new ValidationError('Connection host is required', { violatedRule: 'missing_host' });
  }

  if (!info.port || info.port <= 0 || info.port > 65535) {
    throw new ValidationError('Valid port number is required (1-65535)', { violatedRule: 'invalid_port' });
  }

  // Validate common protocols
  const validProtocols = ['http', 'https', 'ws', 'wss', 'grpc', 'graphql'];
  if (!validProtocols.includes(info.protocol.toLowerCase())) {
    console.warn(`Uncommon protocol: ${info.protocol}`);
  }
}

// ===== DEFAULT CONFIGURATION BUILDERS =====

/**
 * Configuration for the Grizabella client.
 */
export interface GrizabellaConfig {
  /** Connection settings */
  connection: {
    /** Connection string or connection info */
    connectionString?: string;
    connectionInfo?: ConnectionInfo;
    /** Connection timeout in milliseconds */
    timeout?: number;
    /** Maximum number of connection retries */
    maxRetries?: number;
  };

  /** Performance settings */
  performance: {
    /** Default query timeout */
    queryTimeout?: number;
    /** Batch size for operations */
    batchSize?: number;
    /** Enable connection pooling */
    enablePooling?: boolean;
    /** Maximum pool size */
    maxPoolSize?: number;
  };

  /** Caching settings */
  caching: {
    /** Enable result caching */
    enableCaching?: boolean;
    /** Cache TTL in milliseconds */
    cacheTTL?: number;
    /** Maximum cache size */
    maxCacheSize?: number;
  };

  /** Logging settings */
  logging: {
    /** Log level */
    level?: 'debug' | 'info' | 'warn' | 'error';
    /** Enable performance logging */
    enablePerformanceLogging?: boolean;
    /** Enable request/response logging */
    enableRequestLogging?: boolean;
  };

  /** Validation settings */
  validation: {
    /** Enable strict validation */
    strictValidation?: boolean;
    /** Validate data types */
    validateDataTypes?: boolean;
    /** Validate constraints */
    validateConstraints?: boolean;
  };
}

/**
 * Default configuration values.
 */
export const DEFAULT_CONFIG: Required<GrizabellaConfig> = {
  connection: {
    timeout: 30000,
    maxRetries: 3,
  },
  performance: {
    queryTimeout: 60000,
    batchSize: 100,
    enablePooling: true,
    maxPoolSize: 10,
  },
  caching: {
    enableCaching: true,
    cacheTTL: 300000, // 5 minutes
    maxCacheSize: 1000,
  },
  logging: {
    level: 'info',
    enablePerformanceLogging: false,
    enableRequestLogging: false,
  },
  validation: {
    strictValidation: true,
    validateDataTypes: true,
    validateConstraints: true,
  },
};

/**
 * Builds a complete configuration object with defaults.
 */
export function buildConfig(overrides: Partial<GrizabellaConfig> = {}): Required<GrizabellaConfig> {
  const config = { ...DEFAULT_CONFIG };

  // Deep merge overrides
  if (overrides.connection) {
    config.connection = { ...config.connection, ...overrides.connection };
  }
  if (overrides.performance) {
    config.performance = { ...config.performance, ...overrides.performance };
  }
  if (overrides.caching) {
    config.caching = { ...config.caching, ...overrides.caching };
  }
  if (overrides.logging) {
    config.logging = { ...config.logging, ...overrides.logging };
  }
  if (overrides.validation) {
    config.validation = { ...config.validation, ...overrides.validation };
  }

  // Validate configuration
  validateConfig(config);

  return config;
}

/**
 * Validates configuration object.
 */
export function validateConfig(config: Partial<GrizabellaConfig>): void {
  if (config.connection?.timeout && config.connection.timeout <= 0) {
    throw new ValidationError('Connection timeout must be positive', { violatedRule: 'invalid_timeout' });
  }

  if (config.performance?.queryTimeout && config.performance.queryTimeout <= 0) {
    throw new ValidationError('Query timeout must be positive', { violatedRule: 'invalid_query_timeout' });
  }

  if (config.performance?.batchSize && config.performance.batchSize <= 0) {
    throw new ValidationError('Batch size must be positive', { violatedRule: 'invalid_batch_size' });
  }

  if (config.caching?.cacheTTL && config.caching.cacheTTL <= 0) {
    throw new ValidationError('Cache TTL must be positive', { violatedRule: 'invalid_cache_ttl' });
  }
}

/**
 * Loads configuration from environment variables.
 */
export function loadConfigFromEnv(prefix: string = 'GRIZABELLA_'): Partial<GrizabellaConfig> {
  const config: Partial<GrizabellaConfig> = {};

  // Connection settings
  if (process.env[`${prefix}CONNECTION_STRING`]) {
    config.connection = {
      connectionString: process.env[`${prefix}CONNECTION_STRING`],
    } as any;
  }

  if (process.env[`${prefix}CONNECTION_TIMEOUT`]) {
    config.connection = {
      ...config.connection,
      timeout: parseInt(process.env[`${prefix}CONNECTION_TIMEOUT`]!, 10),
    } as any;
  }

  // Performance settings
  if (process.env[`${prefix}QUERY_TIMEOUT`]) {
    config.performance = {
      queryTimeout: parseInt(process.env[`${prefix}QUERY_TIMEOUT`]!, 10),
    };
  }

  if (process.env[`${prefix}BATCH_SIZE`]) {
    config.performance = {
      ...config.performance,
      batchSize: parseInt(process.env[`${prefix}BATCH_SIZE`]!, 10),
    };
  }

  // Logging settings
  if (process.env[`${prefix}LOG_LEVEL`]) {
    config.logging = {
      level: process.env[`${prefix}LOG_LEVEL`] as 'debug' | 'info' | 'warn' | 'error',
    };
  }

  return config;
}

// ===== DEBUG LOGGING HELPERS =====

/**
 * Debug logging levels.
 */
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

/**
 * Debug logger interface.
 */
export interface DebugLogger {
  debug(message: string, ...args: any[]): void;
  info(message: string, ...args: any[]): void;
  warn(message: string, ...args: any[]): void;
  error(message: string, ...args: any[]): void;
}

/**
 * Console-based debug logger.
 */
export class ConsoleDebugLogger implements DebugLogger {
  private level: LogLevel;

  constructor(level: LogLevel = LogLevel.INFO) {
    this.level = level;
  }

  debug(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.DEBUG) {
      console.debug(`[DEBUG] ${message}`, ...args);
    }
  }

  info(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.INFO) {
      console.info(`[INFO] ${message}`, ...args);
    }
  }

  warn(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.WARN) {
      console.warn(`[WARN] ${message}`, ...args);
    }
  }

  error(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.ERROR) {
      console.error(`[ERROR] ${message}`, ...args);
    }
  }
}

/**
 * No-operation logger for production.
 */
export class NoOpLogger implements DebugLogger {
  debug(): void {}
  info(): void {}
  warn(): void {}
  error(): void {}
}

/**
 * Global debug logger instance.
 */
let globalLogger: DebugLogger = new ConsoleDebugLogger();

/**
 * Set the global debug logger.
 */
export function setGlobalLogger(logger: DebugLogger): void {
  globalLogger = logger;
}

/**
 * Get the current global debug logger.
 */
export function getGlobalLogger(): DebugLogger {
  return globalLogger;
}

/**
 * Creates a logger for a specific component.
 */
export function createComponentLogger(component: string): DebugLogger {
  return {
    debug: (message: string, ...args: any[]) => globalLogger.debug(`[${component}] ${message}`, ...args),
    info: (message: string, ...args: any[]) => globalLogger.info(`[${component}] ${message}`, ...args),
    warn: (message: string, ...args: any[]) => globalLogger.warn(`[${component}] ${message}`, ...args),
    error: (message: string, ...args: any[]) => globalLogger.error(`[${component}] ${message}`, ...args),
  };
}

// ===== PERFORMANCE MONITORING UTILITIES =====

/**
 * Performance measurement result.
 */
export interface PerformanceMeasurement {
  /** Operation name */
  operation: string;
  /** Start time */
  startTime: number;
  /** End time */
  endTime: number;
  /** Duration in milliseconds */
  duration: number;
  /** Additional metadata */
  metadata?: Record<string, any>;
}

/**
 * Performance monitor for tracking operation timings.
 */
export class PerformanceMonitor {
  private measurements: Map<string, PerformanceMeasurement> = new Map();
  private logger: DebugLogger;

  constructor(logger: DebugLogger = getGlobalLogger()) {
    this.logger = logger;
  }

  /**
   * Starts timing an operation.
   */
  start(operation: string, metadata?: Record<string, any>): void {
    const startTime = performance.now();
    const measurement: any = {
      operation,
      startTime,
      endTime: 0,
      duration: 0,
    };
    
    if (metadata !== undefined) {
      measurement.metadata = metadata;
    }
    
    this.measurements.set(operation, measurement);

    this.logger.debug(`Started operation: ${operation}`);
  }

  /**
   * Ends timing an operation.
   */
  end(operation: string): PerformanceMeasurement | undefined {
    const measurement = this.measurements.get(operation);
    if (!measurement) {
      this.logger.warn(`No measurement found for operation: ${operation}`);
      return undefined;
    }

    measurement.endTime = performance.now();
    measurement.duration = measurement.endTime - measurement.startTime;

    this.measurements.delete(operation);

    this.logger.debug(`Completed operation: ${operation} (${measurement.duration.toFixed(2)}ms)`);

    return measurement;
  }

  /**
   * Times an async operation.
   */
  async timeAsync<T>(
    operation: string,
    asyncFn: () => Promise<T>,
    metadata?: Record<string, any>
  ): Promise<T> {
    this.start(operation, metadata);
    try {
      const result = await asyncFn();
      this.end(operation);
      return result;
    } catch (error) {
      this.end(operation);
      throw error;
    }
  }

  /**
   * Times a synchronous operation.
   */
  timeSync<T>(operation: string, syncFn: () => T, metadata?: Record<string, any>): T {
    this.start(operation, metadata);
    try {
      const result = syncFn();
      this.end(operation);
      return result;
    } catch (error) {
      this.end(operation);
      throw error;
    }
  }

  /**
   * Gets all current measurements.
   */
  getMeasurements(): PerformanceMeasurement[] {
    return Array.from(this.measurements.values());
  }

  /**
   * Clears all measurements.
   */
  clear(): void {
    this.measurements.clear();
  }

  /**
   * Generates a performance report.
   */
  generateReport(): Record<string, any> {
    const measurements = Array.from(this.measurements.values());

    if (measurements.length === 0) {
      return { message: 'No measurements available' };
    }

    const durations = measurements.map(m => m.duration);
    const totalDuration = durations.reduce((sum, d) => sum + d, 0);
    const avgDuration = totalDuration / measurements.length;
    const maxDuration = Math.max(...durations);
    const minDuration = Math.min(...durations);

    return {
      totalOperations: measurements.length,
      totalDuration: `${totalDuration.toFixed(2)}ms`,
      averageDuration: `${avgDuration.toFixed(2)}ms`,
      maxDuration: `${maxDuration.toFixed(2)}ms`,
      minDuration: `${minDuration.toFixed(2)}ms`,
      operations: measurements.map(m => ({
        operation: m.operation,
        duration: `${m.duration.toFixed(2)}ms`,
        metadata: m.metadata,
      })),
    };
  }
}

/**
 * Global performance monitor instance.
 */
let globalMonitor: PerformanceMonitor = new PerformanceMonitor();

/**
 * Set the global performance monitor.
 */
export function setGlobalMonitor(monitor: PerformanceMonitor): void {
  globalMonitor = monitor;
}

/**
 * Get the current global performance monitor.
 */
export function getGlobalMonitor(): PerformanceMonitor {
  return globalMonitor;
}

/**
 * Convenience function to time an async operation globally.
 */
export async function timeAsync<T>(
  operation: string,
  asyncFn: () => Promise<T>,
  metadata?: Record<string, any>
): Promise<T> {
  return globalMonitor.timeAsync(operation, asyncFn, metadata);
}

/**
 * Convenience function to time a synchronous operation globally.
 */
export function timeSync<T>(
  operation: string,
  syncFn: () => T,
  metadata?: Record<string, any>
): T {
  return globalMonitor.timeSync(operation, syncFn, metadata);
}

// ===== DEVELOPMENT UTILITIES =====

/**
 * Generates a sample ObjectInstance for testing.
 */
export function createSampleObjectInstance(
  objectTypeName: string = 'SampleType',
  properties: Record<string, any> = { name: 'Sample', value: 42 }
): import('../types/core').ObjectInstance {
  const { createObjectInstance } = require('./helpers');
  return createObjectInstance(objectTypeName, properties, { validate: false });
}

/**
 * Pretty-prints an object for debugging.
 */
export function prettyPrint(obj: any, indent: number = 2): string {
  return JSON.stringify(obj, null, indent);
}

/**
 * Creates a simple memory usage report.
 */
export function createMemoryReport(): Record<string, any> {
  if (typeof performance !== 'undefined' && (performance as any).memory) {
    const mem = (performance as any).memory;
    return {
      usedJSHeapSize: `${(mem.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
      totalJSHeapSize: `${(mem.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
      jsHeapSizeLimit: `${(mem.jsHeapSizeLimit / 1024 / 1024).toFixed(2)} MB`,
      usagePercentage: `${((mem.usedJSHeapSize / mem.jsHeapSizeLimit) * 100).toFixed(2)}%`,
    };
  }

  return { message: 'Memory information not available in this environment' };
}

/**
 * Simple health check utility.
 */
export async function healthCheck(
  endpoint: string,
  timeout: number = 5000
): Promise<{ status: 'healthy' | 'unhealthy'; responseTime?: number; error?: string }> {
  const startTime = performance.now();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const response = await fetch(endpoint, {
      method: 'GET',
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const responseTime = performance.now() - startTime;

    if (response.ok) {
      return { status: 'healthy', responseTime };
    } else {
      return {
        status: 'unhealthy',
        responseTime,
        error: `HTTP ${response.status}: ${response.statusText}`,
      };
    }
  } catch (error) {
    const responseTime = performance.now() - startTime;
    return {
      status: 'unhealthy',
      responseTime,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}