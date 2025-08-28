/**
 * Test utilities and helper functions
 *
 * This module provides common utilities used across different test suites,
 * including test data generation, assertion helpers, and test lifecycle management.
 */

import { Decimal } from 'decimal.js';
import { v4 as uuidv4 } from 'uuid';
import type {
  ObjectTypeDefinition,
  ObjectInstance,
  RelationTypeDefinition,
  RelationInstance,
  PropertyDefinition,
  EmbeddingDefinition,
} from '../../src/types/core';
import { PropertyDataType } from '../../src/types/enums';

/**
 * Generate a unique test ID with a prefix
 */
export function generateTestId(prefix: string = 'test'): string {
  return `${prefix}_${uuidv4().substring(0, 8)}`;
}

/**
 * Generate a random UUID
 */
export function generateUUID(): string {
  return uuidv4();
}

/**
 * Create a test timestamp (current time)
 */
export function createTestTimestamp(): Date {
  return new Date();
}

/**
 * Create a test Decimal value
 */
export function createTestDecimal(value: number | string = 1.0): Decimal {
  return new Decimal(value);
}

/**
 * Create a test property definition
 */
export function createTestPropertyDefinition(
  name: string = 'testProperty',
  dataType: PropertyDataType = PropertyDataType.TEXT,
  options: Partial<PropertyDefinition> = {}
): PropertyDefinition {
  return {
    name,
    data_type: dataType,
    is_nullable: options.is_nullable ?? false,
    is_unique: options.is_unique ?? false,
    ...(options.description !== undefined ? { description: options.description } : {}),
  };
}

/**
 * Create a test object type definition
 */
export function createTestObjectTypeDefinition(
  name: string = 'TestObject',
  properties: PropertyDefinition[] = []
): ObjectTypeDefinition {
  if (properties.length === 0) {
    properties = [
      createTestPropertyDefinition('name', PropertyDataType.TEXT),
      createTestPropertyDefinition('description', PropertyDataType.TEXT, { is_nullable: true }),
    ];
  }

  return {
    name,
    description: `Test object type: ${name}`,
    properties,
  };
}

/**
 * Create a test object instance
 */
export function createTestObjectInstance(
  objectTypeName: string = 'TestObject',
  properties: Record<string, any> = {},
  options: Partial<ObjectInstance> = {}
): ObjectInstance {
  const defaultProperties = {
    name: `Test Object ${generateTestId()}`,
    description: 'A test object instance',
    ...properties,
  };

  return {
    id: options.id || generateUUID(),
    object_type_name: objectTypeName,
    weight: options.weight || createTestDecimal(1.0),
    upsert_date: options.upsert_date || createTestTimestamp(),
    properties: defaultProperties,
  };
}

/**
 * Create a test relation type definition
 */
export function createTestRelationTypeDefinition(
  name: string = 'TEST_RELATION',
  sourceType: string = 'TestObjectA',
  targetType: string = 'TestObjectB',
  properties: PropertyDefinition[] = []
): RelationTypeDefinition {
  if (properties.length === 0) {
    properties = [
      createTestPropertyDefinition('strength', PropertyDataType.FLOAT, { is_nullable: true }),
    ];
  }

  return {
    name,
    description: `Test relation type: ${name}`,
    source_object_type_names: [sourceType],
    target_object_type_names: [targetType],
    properties,
  };
}

/**
 * Create a test relation instance
 */
export function createTestRelationInstance(
  relationTypeName: string = 'TEST_RELATION',
  sourceId: string,
  targetId: string,
  properties: Record<string, any> = {},
  options: Partial<RelationInstance> = {}
): RelationInstance {
  const defaultProperties = {
    strength: 0.8,
    ...properties,
  };

  return {
    id: options.id || generateUUID(),
    relation_type_name: relationTypeName,
    source_object_instance_id: sourceId,
    target_object_instance_id: targetId,
    weight: options.weight || createTestDecimal(1.0),
    upsert_date: options.upsert_date || createTestTimestamp(),
    properties: defaultProperties,
  };
}

/**
 * Create a test embedding definition
 */
export function createTestEmbeddingDefinition(
  name: string = 'test_embedding',
  objectTypeName: string = 'TestObject',
  sourceProperty: string = 'content'
): EmbeddingDefinition {
  return {
    name,
    object_type_name: objectTypeName,
    source_property_name: sourceProperty,
    embedding_model: 'text-embedding-ada-002',
    dimensions: 1536,
    description: `Test embedding for ${objectTypeName}`,
  };
}

/**
 * Create a batch of test object instances
 */
export function createTestObjectBatch(
  objectTypeName: string,
  count: number,
  properties: Record<string, any> = {}
): ObjectInstance[] {
  return Array.from({ length: count }, (_, index) =>
    createTestObjectInstance(objectTypeName, {
      ...properties,
      name: `Test Object ${index + 1}`,
      index,
    })
  );
}

/**
 * Sleep for a specified number of milliseconds
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Retry a function with exponential backoff
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  initialDelay: number = 1000,
  backoffMultiplier: number = 2
): Promise<T> {
  let lastError: Error;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      if (attempt === maxRetries) {
        throw lastError;
      }

      const delay = initialDelay * Math.pow(backoffMultiplier, attempt);
      await sleep(delay);
    }
  }

  throw lastError!;
}

/**
 * Assert that a function throws a specific error type
 */
export async function assertThrowsError<T extends Error>(
  fn: () => Promise<any> | any,
  errorType: new (...args: any[]) => T,
  messagePattern?: string | RegExp
): Promise<T> {
  try {
    const result = await fn();
    throw new Error(`Expected function to throw ${errorType.name}, but it returned: ${result}`);
  } catch (error) {
    if (!(error instanceof errorType)) {
      throw new Error(`Expected error type ${errorType.name}, but got ${error?.constructor?.name}: ${error}`);
    }

    if (messagePattern) {
      const message = error.message;
      const pattern = typeof messagePattern === 'string' ? new RegExp(messagePattern) : messagePattern;
      if (!pattern.test(message)) {
        throw new Error(`Error message "${message}" does not match pattern ${pattern}`);
      }
    }

    return error;
  }
}

/**
 * Create a mock MCP server response
 */
export function createMockMcpResponse(data: any, isError: boolean = false): any {
  return {
    content: [{
      type: 'text',
      text: JSON.stringify(data),
    }],
    isError,
  };
}

/**
 * Deep clone an object (useful for test data manipulation)
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Generate random test data based on property type
 */
export function generateRandomValue(dataType: PropertyDataType): any {
  switch (dataType) {
    case PropertyDataType.TEXT:
      return `Random text ${generateTestId()}`;
    case PropertyDataType.INTEGER:
      return Math.floor(Math.random() * 1000);
    case PropertyDataType.FLOAT:
      return Math.random() * 100;
    case PropertyDataType.BOOLEAN:
      return Math.random() > 0.5;
    case PropertyDataType.DATETIME:
      return createTestTimestamp();
    case PropertyDataType.UUID:
      return generateUUID();
    default:
      return `Random value ${generateTestId()}`;
  }
}