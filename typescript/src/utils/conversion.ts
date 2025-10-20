/**
 * Type Conversion Utilities for Grizabella TypeScript API
 *
 * This module provides comprehensive type conversion functions for seamless
 * interoperability between Python backend types and TypeScript frontend types,
 * including Decimal handling, date/time conversions, and property value transformations.
 */

import { Decimal } from 'decimal.js';
import {
  PropertyDataType,
  PropertyDefinition,
  ObjectInstance,
  RelationInstance,
} from '../types/core';
import {
  FilterValueType,
  RelationalOperator,
} from '../types/enums';
import {
  ValidationError,
  createErrorMessage,
} from '../client/errors';

// ===== DECIMAL CONVERSION UTILITIES =====

/**
 * Converts various numeric representations to Decimal.
 */
export function toDecimal(value: any): Decimal {
  if (value instanceof Decimal) {
    return value;
  }

  if (typeof value === 'number') {
    if (!isFinite(value)) {
      throw new ValidationError(
        createErrorMessage('Cannot convert non-finite number to Decimal', { value }),
        { violatedRule: 'finite_number_required' }
      );
    }
    return new Decimal(value);
  }

  if (typeof value === 'string') {
    try {
      return new Decimal(value);
    } catch (error) {
      throw new ValidationError(
        createErrorMessage('Invalid string for Decimal conversion', { value, error }),
        { violatedRule: 'valid_decimal_string' }
      );
    }
  }

  if (typeof value === 'boolean') {
    return new Decimal(value ? 1 : 0);
  }

  throw new ValidationError(
    createErrorMessage('Cannot convert value to Decimal', { value, type: typeof value }),
    { violatedRule: 'unsupported_decimal_conversion' }
  );
}

/**
 * Safely converts Decimal to number, with optional precision handling.
 */
export function decimalToNumber(decimal: Decimal, maxPrecision: number = 10): number {
  // Check if the decimal can be safely represented as a number
  if (decimal.isNaN() || !decimal.isFinite()) {
    throw new ValidationError(
      createErrorMessage('Cannot convert non-finite Decimal to number', { decimal: decimal.toString() }),
      { violatedRule: 'finite_decimal_required' }
    );
  }

  // Check precision to avoid floating point issues
  const precision = decimal.precision();
  if (precision > maxPrecision) {
    console.warn(`Decimal precision (${precision}) exceeds maximum (${maxPrecision}), potential loss of precision`);
  }

  const num = decimal.toNumber();
  if (!isFinite(num)) {
    throw new ValidationError(
      createErrorMessage('Decimal too large for number conversion', { decimal: decimal.toString() }),
      { violatedRule: 'decimal_too_large' }
    );
  }

  return num;
}

/**
 * Converts Decimal to JSON-compatible representation.
 */
export function decimalToJSON(decimal: Decimal): string {
  return decimal.toJSON();
}

/**
 * Converts JSON Decimal representation back to Decimal.
 */
export function jsonToDecimal(jsonValue: string): Decimal {
  return new Decimal(jsonValue);
}

// ===== DATE/TIME CONVERSION UTILITIES =====

/**
 * Converts various date representations to Date object.
 */
export function toDate(value: any): Date {
  if (value instanceof Date) {
    return value;
  }

  if (typeof value === 'number') {
    const date = new Date(value);
    if (isNaN(date.getTime())) {
      throw new ValidationError(
        createErrorMessage('Invalid timestamp for Date conversion', { value }),
        { violatedRule: 'valid_timestamp' }
      );
    }
    return date;
  }

  if (typeof value === 'string') {
    const date = new Date(value);
    if (isNaN(date.getTime())) {
      throw new ValidationError(
        createErrorMessage('Invalid date string for Date conversion', { value }),
        { violatedRule: 'valid_date_string' }
      );
    }
    return date;
  }

  throw new ValidationError(
    createErrorMessage('Cannot convert value to Date', { value, type: typeof value }),
    { violatedRule: 'unsupported_date_conversion' }
  );
}

/**
 * Converts Date to ISO string.
 */
export function dateToISOString(date: Date): string {
  return date.toISOString();
}

/**
 * Converts Date to Unix timestamp.
 */
export function dateToTimestamp(date: Date): number {
  return Math.floor(date.getTime() / 1000);
}

/**
 * Converts Unix timestamp to Date.
 */
export function timestampToDate(timestamp: number): Date {
  return new Date(timestamp * 1000);
}

/**
 * Converts Date to locale string with consistent formatting.
 */
export function dateToLocaleString(date: Date, locale: string = 'en-US'): string {
  return date.toLocaleString(locale);
}

// ===== PYTHON-TO-TYPESCRIPT TYPE CONVERSION =====

/**
 * Converts Python-style snake_case to TypeScript camelCase.
 */
export function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

/**
 * Converts TypeScript camelCase to Python-style snake_case.
 */
export function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

/**
 * Recursively converts object keys from snake_case to camelCase.
 */
export function objectKeysToCamel(obj: any): any {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(objectKeysToCamel);
  }

  const converted: Record<string, any> = {};
  for (const [key, value] of Object.entries(obj)) {
    converted[snakeToCamel(key)] = objectKeysToCamel(value);
  }

  return converted;
}

/**
 * Recursively converts object keys from camelCase to snake_case.
 */
export function objectKeysToSnake(obj: any): any {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(objectKeysToSnake);
  }

  const converted: Record<string, any> = {};
  for (const [key, value] of Object.entries(obj)) {
    converted[camelToSnake(key)] = objectKeysToSnake(value);
  }

  return converted;
}

// ===== PROPERTY VALUE CONVERSION =====

/**
 * Converts a raw value to the appropriate TypeScript type based on PropertyDataType.
 */
export function convertPropertyValue(value: any, dataType: PropertyDataType): any {
  if (value === null || value === undefined) {
    return value;
  }

  switch (dataType) {
    case PropertyDataType.TEXT:
      return typeof value === 'string' ? value : String(value);

    case PropertyDataType.INTEGER:
      if (typeof value === 'string') {
        const parsed = parseInt(value, 10);
        if (isNaN(parsed)) {
          throw new ValidationError(
            createErrorMessage('Cannot convert string to integer', { value }),
            { violatedRule: 'string_to_integer_conversion' }
          );
        }
        return parsed;
      }
      if (typeof value === 'number') {
        if (!Number.isInteger(value)) {
          return Math.round(value);
        }
        return value;
      }
      if (typeof value === 'boolean') {
        return value ? 1 : 0;
      }
      throw new ValidationError(
        createErrorMessage('Cannot convert value to integer', { value, type: typeof value }),
        { violatedRule: 'unsupported_integer_conversion' }
      );

    case PropertyDataType.FLOAT:
      if (typeof value === 'string') {
        const parsed = parseFloat(value);
        if (isNaN(parsed)) {
          throw new ValidationError(
            createErrorMessage('Cannot convert string to float', { value }),
            { violatedRule: 'string_to_float_conversion' }
          );
        }
        return parsed;
      }
      if (typeof value === 'number') {
        return value;
      }
      if (typeof value === 'boolean') {
        return value ? 1.0 : 0.0;
      }
      throw new ValidationError(
        createErrorMessage('Cannot convert value to float', { value, type: typeof value }),
        { violatedRule: 'unsupported_float_conversion' }
      );

    case PropertyDataType.BOOLEAN:
      if (typeof value === 'boolean') {
        return value;
      }
      if (typeof value === 'string') {
        const lower = value.toLowerCase();
        if (lower === 'true' || lower === '1' || lower === 'yes') {
          return true;
        }
        if (lower === 'false' || lower === '0' || lower === 'no') {
          return false;
        }
        throw new ValidationError(
          createErrorMessage('Cannot convert string to boolean', { value }),
          { violatedRule: 'string_to_boolean_conversion' }
        );
      }
      if (typeof value === 'number') {
        return value !== 0;
      }
      throw new ValidationError(
        createErrorMessage('Cannot convert value to boolean', { value, type: typeof value }),
        { violatedRule: 'unsupported_boolean_conversion' }
      );

    case PropertyDataType.DATETIME:
      return toDate(value);

    case PropertyDataType.BLOB:
      if (value instanceof Uint8Array) {
        return value;
      }
      if (Array.isArray(value)) {
        return new Uint8Array(value);
      }
      if (typeof value === 'string') {
        // Assume base64 encoding
        try {
          const binaryString = atob(value);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          return bytes;
        } catch {
          throw new ValidationError(
            createErrorMessage('Invalid base64 string for BLOB conversion', { value }),
            { violatedRule: 'invalid_base64_blob' }
          );
        }
      }
      throw new ValidationError(
        createErrorMessage('Cannot convert value to BLOB', { value, type: typeof value }),
        { violatedRule: 'unsupported_blob_conversion' }
      );

    case PropertyDataType.JSON:
      if (typeof value === 'object') {
        return value;
      }
      if (typeof value === 'string') {
        try {
          return JSON.parse(value);
        } catch {
          throw new ValidationError(
            createErrorMessage('Invalid JSON string', { value }),
            { violatedRule: 'invalid_json_string' }
          );
        }
      }
      throw new ValidationError(
        createErrorMessage('Cannot convert value to JSON', { value, type: typeof value }),
        { violatedRule: 'unsupported_json_conversion' }
      );

    case PropertyDataType.UUID:
      if (typeof value === 'string') {
        return value.toLowerCase();
      }
      throw new ValidationError(
        createErrorMessage('Cannot convert value to UUID', { value, type: typeof value }),
        { violatedRule: 'unsupported_uuid_conversion' }
      );

    default:
      throw new ValidationError(
        createErrorMessage('Unknown data type for conversion', { dataType }),
        { violatedRule: 'unknown_data_type_conversion' }
      );
  }
}

/**
 * Converts an entire ObjectInstance's properties using property definitions.
 */
export function convertObjectInstance(
  objInstance: ObjectInstance,
  propertyDefs: PropertyDefinition[]
): ObjectInstance {
  const convertedProperties: Record<string, any> = {};

  for (const propDef of propertyDefs) {
    const rawValue = objInstance.properties[propDef.name];
    if (rawValue !== undefined) {
      try {
        convertedProperties[propDef.name] = convertPropertyValue(rawValue, propDef.data_type);
      } catch (error) {
        if (error instanceof ValidationError) {
          throw error;
        }
        throw new ValidationError(
          createErrorMessage(`Failed to convert property '${propDef.name}'`, {
            value: rawValue,
            dataType: propDef.data_type,
            error,
          }),
          { fieldName: propDef.name, violatedRule: 'property_conversion_failure' }
        );
      }
    }
  }

  return {
    ...objInstance,
    properties: convertedProperties,
  };
}

/**
 * Converts filter values for query operations.
 */
export function convertFilterValue(
  value: FilterValueType,
  operator: RelationalOperator
): FilterValueType {
  if (value === null || value === undefined) {
    return value;
  }

  // Handle array values
  if (Array.isArray(value)) {
    return value.map(item => convertFilterValue(item, operator) as any);
  }

  // Handle string values for pattern matching
  if (typeof value === 'string') {
    return value;
  }

  // Handle numeric values
  if (typeof value === 'number') {
    return value;
  }

  // Handle boolean values
  if (typeof value === 'boolean') {
    return value;
  }

  // Handle Date values
  if (value instanceof Date) {
    return value;
  }

  // Handle Decimal values
  if (value instanceof Decimal) {
    return value;
  }

  // Return as-is for other types
  return value;
}

// ===== SERIALIZATION UTILITIES =====

/**
 * Converts an ObjectInstance to a JSON-serializable format.
 */
export function objectInstanceToJSON(objInstance: ObjectInstance): Record<string, any> {
  const json: Record<string, any> = {
    id: objInstance.id,
    object_type_name: objInstance.object_type_name,
    weight: decimalToJSON(objInstance.weight),
    upsert_date: dateToISOString(objInstance.upsert_date),
    properties: {},
  };

  for (const [key, value] of Object.entries(objInstance.properties)) {
    if (value instanceof Decimal) {
      json['properties'][key] = decimalToJSON(value);
    } else if (value instanceof Date) {
      json['properties'][key] = dateToISOString(value);
    } else if (value instanceof Uint8Array) {
      // Convert Uint8Array to base64
      const binaryString = Array.from(value, byte => String.fromCharCode(byte)).join('');
      json['properties'][key] = btoa(binaryString);
    } else {
      json['properties'][key] = value;
    }
  }

  return json;
}

/**
 * Converts a JSON representation back to an ObjectInstance.
 */
export function jsonToObjectInstance(json: Record<string, any>): ObjectInstance {
  const properties: Record<string, any> = {};

  for (const [key, value] of Object.entries(json['properties'] || {})) {
    // Try to detect and convert special types
    if (typeof value === 'string') {
      // Check if it's a Decimal (string representation)
      try {
        const decimal = new Decimal(value);
        if (decimal.toString() === value) {
          properties[key] = decimal;
          continue;
        }
      } catch {}

      // Check if it's an ISO date string
      const date = new Date(value);
      if (!isNaN(date.getTime()) && value === date.toISOString()) {
        properties[key] = date;
        continue;
      }

      // Check if it's base64 (for BLOB data)
      try {
        const binaryString = atob(value);
        if (binaryString.length > 0) {
          properties[key] = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            properties[key][i] = binaryString.charCodeAt(i);
          }
          continue;
        }
      } catch {}
    }

    properties[key] = value;
  }

  return {
    id: json['id'],
    object_type_name: json['object_type_name'],
    weight: jsonToDecimal(json['weight']),
    upsert_date: new Date(json['upsert_date']),
    properties,
  };
}

// ===== BATCH CONVERSION UTILITIES =====

/**
 * Converts multiple ObjectInstances using their property definitions.
 */
export function convertObjectInstances(
  instances: ObjectInstance[],
  propertyDefs: PropertyDefinition[]
): ObjectInstance[] {
  return instances.map(instance => convertObjectInstance(instance, propertyDefs));
}

/**
 * Converts multiple RelationInstances.
 */
export function convertRelationInstances(
  instances: RelationInstance[]
): RelationInstance[] {
  return instances.map(instance => ({
    ...instance,
    // Convert relation properties if they exist
    properties: instance.properties ? objectKeysToCamel(instance.properties) : undefined,
  }));
}