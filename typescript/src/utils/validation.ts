/**
 * Data Validation Utilities for Grizabella TypeScript API
 *
 * This module provides comprehensive validation functions for data integrity,
 * schema compliance, and type safety across the Grizabella API ecosystem.
 */

import { Decimal } from 'decimal.js';
import {
  PropertyDataType,
  PropertyDefinition,
  ObjectTypeDefinition,
  ObjectInstance,
  RelationTypeDefinition,
  RelationInstance,
} from '../types/core';
import {
  // MemoryInstance,
  FilterValueType,
  RelationalOperator,
} from '../types/enums';
import {
  ValidationError,
  SchemaError,
  createErrorMessage,
} from '../client/errors';

// ===== UUID VALIDATION =====

/**
 * Regular expression for UUID v4 validation.
 */
const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Validates if a string is a valid UUID v4.
 */
export function isValidUUID(value: string): boolean {
  return typeof value === 'string' && UUID_V4_REGEX.test(value);
}

/**
 * Validates UUID and throws ValidationError if invalid.
 */
export function validateUUID(value: string, fieldName: string = 'uuid'): void {
  if (!isValidUUID(value)) {
    throw new ValidationError(
      createErrorMessage(`Invalid UUID format for field '${fieldName}'`, { value }),
      {
        fieldName,
        expectedFormat: 'UUID v4',
        actualValue: value,
        violatedRule: 'uuid_format',
      }
    );
  }
}

/**
 * Validates and normalizes a UUID string.
 */
export function normalizeUUID(value: string, fieldName: string = 'uuid'): string {
  const normalized = value.trim().toLowerCase();
  validateUUID(normalized, fieldName);
  return normalized;
}

// ===== DATA TYPE VALIDATION =====

/**
 * Validates a value against a specific PropertyDataType.
 */
export function validatePropertyDataType(
  value: unknown,
  dataType: PropertyDataType,
  fieldName: string = 'property'
): void {
  switch (dataType) {
    case PropertyDataType.TEXT:
      if (typeof value !== 'string') {
        throw new ValidationError(
          createErrorMessage(`Expected string for TEXT property '${fieldName}'`, { value }),
          { fieldName, actualValue: value, violatedRule: 'text_type' }
        );
      }
      break;

    case PropertyDataType.INTEGER:
      if (typeof value !== 'number' || !Number.isInteger(value)) {
        throw new ValidationError(
          createErrorMessage(`Expected integer for INTEGER property '${fieldName}'`, { value }),
          { fieldName, actualValue: value, violatedRule: 'integer_type' }
        );
      }
      break;

    case PropertyDataType.FLOAT:
      if (typeof value !== 'number' || !isFinite(value)) {
        throw new ValidationError(
          createErrorMessage(`Expected finite number for FLOAT property '${fieldName}'`, { value }),
          { fieldName, actualValue: value, violatedRule: 'float_type' }
        );
      }
      break;

    case PropertyDataType.BOOLEAN:
      if (typeof value !== 'boolean') {
        throw new ValidationError(
          createErrorMessage(`Expected boolean for BOOLEAN property '${fieldName}'`, { value }),
          { fieldName, actualValue: value, violatedRule: 'boolean_type' }
        );
      }
      break;

    case PropertyDataType.DATETIME:
      if (!(value instanceof Date) && typeof value !== 'string') {
        throw new ValidationError(
          createErrorMessage(`Expected Date or ISO string for DATETIME property '${fieldName}'`, { value }),
          { fieldName, actualValue: value, violatedRule: 'datetime_type' }
        );
      }
      // Validate ISO string format if string provided
      if (typeof value === 'string') {
        const date = new Date(value);
        if (isNaN(date.getTime())) {
          throw new ValidationError(
            createErrorMessage(`Invalid ISO date string for DATETIME property '${fieldName}'`, { value }),
            { fieldName, actualValue: value, violatedRule: 'datetime_format' }
          );
        }
      }
      break;

    case PropertyDataType.BLOB:
      if (!(value instanceof Uint8Array) && !Array.isArray(value)) {
        throw new ValidationError(
          createErrorMessage(`Expected Uint8Array or byte array for BLOB property '${fieldName}'`, { value }),
          { fieldName, actualValue: value, violatedRule: 'blob_type' }
        );
      }
      break;

    case PropertyDataType.JSON:
      try {
        if (typeof value === 'string') {
          JSON.parse(value);
        } else if (typeof value !== 'object' || value === null) {
          throw new Error('Invalid JSON');
        }
      } catch {
        throw new ValidationError(
          createErrorMessage(`Expected valid JSON for JSON property '${fieldName}'`, { value }),
          { fieldName, actualValue: value, violatedRule: 'json_validity' }
        );
      }
      break;

    case PropertyDataType.UUID:
      if (typeof value !== 'string' || !isValidUUID(value)) {
        throw new ValidationError(
          createErrorMessage(`Expected valid UUID for UUID property '${fieldName}'`, { value }),
          { fieldName, actualValue: value, violatedRule: 'uuid_type' }
        );
      }
      break;

    default:
      throw new ValidationError(
        createErrorMessage(`Unknown data type '${dataType}' for property '${fieldName}'`, { dataType }),
        { fieldName, actualValue: dataType, violatedRule: 'unknown_data_type' }
      );
  }
}

// ===== PROPERTY DEFINITION VALIDATION =====

/**
 * Validates a PropertyDefinition structure.
 */
export function validatePropertyDefinition(propDef: PropertyDefinition): void {
  if (!propDef.name || typeof propDef.name !== 'string') {
    throw new SchemaError(
      'Property definition must have a valid name',
      { propertyName: propDef.name, violatedRule: 'property_name_required' }
    );
  }

  if (!propDef.data_type || !Object.values(PropertyDataType).includes(propDef.data_type)) {
    throw new SchemaError(
      createErrorMessage('Invalid property data type', { dataType: propDef.data_type }),
      { propertyName: propDef.name, violatedRule: 'invalid_data_type' }
    );
  }

  // Validate property constraints
  if (propDef.is_primary_key && propDef.is_nullable) {
    throw new SchemaError(
      'Primary key properties cannot be nullable',
      { propertyName: propDef.name, violatedRule: 'primary_key_not_nullable' }
    );
  }

  if (propDef.is_unique && propDef.is_nullable && !propDef.is_primary_key) {
    throw new SchemaError(
      'Unique properties should typically not be nullable unless they are primary keys',
      { propertyName: propDef.name, violatedRule: 'unique_not_nullable' }
    );
  }
}

// ===== OBJECT TYPE DEFINITION VALIDATION =====

/**
 * Validates an ObjectTypeDefinition structure.
 */
export function validateObjectTypeDefinition(objTypeDef: ObjectTypeDefinition): void {
  if (!objTypeDef.name || typeof objTypeDef.name !== 'string') {
    throw new SchemaError(
      'Object type definition must have a valid name',
      { typeName: objTypeDef.name, violatedRule: 'object_type_name_required' }
    );
  }

  if (!objTypeDef.properties || !Array.isArray(objTypeDef.properties)) {
    throw new SchemaError(
      'Object type definition must have properties array',
      { typeName: objTypeDef.name, violatedRule: 'properties_array_required' }
    );
  }

  if (objTypeDef.properties.length === 0) {
    throw new SchemaError(
      'Object type definition must have at least one property',
      { typeName: objTypeDef.name, violatedRule: 'minimum_properties' }
    );
  }

  // Validate each property definition
  objTypeDef.properties.forEach(validatePropertyDefinition);

  // Check for duplicate property names
  const propNames = objTypeDef.properties.map(p => p.name);
  const duplicates = propNames.filter((name, index) => propNames.indexOf(name) !== index);
  if (duplicates.length > 0) {
    throw new SchemaError(
      createErrorMessage('Duplicate property names found', { duplicates }),
      { typeName: objTypeDef.name, violatedRule: 'unique_property_names' }
    );
  }

  // Check for primary key
  const primaryKeys = objTypeDef.properties.filter(p => p.is_primary_key);
  if (primaryKeys.length > 1) {
    throw new SchemaError(
      'Object type definition can have at most one primary key property',
      { typeName: objTypeDef.name, violatedRule: 'single_primary_key' }
    );
  }
}

// ===== OBJECT INSTANCE VALIDATION =====

/**
 * Validates an ObjectInstance against its ObjectTypeDefinition.
 */
export function validateObjectInstance(
  objInstance: ObjectInstance,
  objTypeDef: ObjectTypeDefinition
): void {
  if (!objInstance.object_type_name) {
    throw new ValidationError(
      'Object instance must have object_type_name',
      { violatedRule: 'object_type_name_required' }
    );
  }

  if (objInstance.object_type_name !== objTypeDef.name) {
    throw new ValidationError(
      createErrorMessage('Object instance type name does not match definition', {
        instanceType: objInstance.object_type_name,
        definitionType: objTypeDef.name,
      }),
      { violatedRule: 'type_name_mismatch' }
    );
  }

  if (!objInstance.properties || typeof objInstance.properties !== 'object') {
    throw new ValidationError(
      'Object instance must have properties object',
      { violatedRule: 'properties_object_required' }
    );
  }

  // Validate MemoryInstance fields
  if (!isValidUUID(objInstance.id)) {
    throw new ValidationError(
      'Object instance must have valid UUID id',
      { fieldName: 'id', violatedRule: 'valid_uuid_id' }
    );
  }

  if (!(objInstance.weight instanceof Decimal) || objInstance.weight.lt(0) || objInstance.weight.gt(10)) {
    throw new ValidationError(
      'Object instance weight must be a Decimal between 0 and 10',
      { fieldName: 'weight', violatedRule: 'valid_weight_range' }
    );
  }

  if (!(objInstance.upsert_date instanceof Date)) {
    throw new ValidationError(
      'Object instance upsert_date must be a Date',
      { fieldName: 'upsert_date', violatedRule: 'valid_upsert_date' }
    );
  }

  // Validate each property value
  for (const propDef of objTypeDef.properties) {
    const propValue = objInstance.properties[propDef.name];

    // Check required fields
    if (propValue === undefined || propValue === null) {
      if (!propDef.is_nullable) {
        throw new ValidationError(
          createErrorMessage(`Required property '${propDef.name}' is missing or null`, { propDef }),
          { fieldName: propDef.name, violatedRule: 'required_property_missing' }
        );
      }
      continue; // Skip validation for nullable null/undefined values
    }

    // Validate data type
    validatePropertyDataType(propValue, propDef.data_type, propDef.name);
  }
}

// ===== RELATION TYPE DEFINITION VALIDATION =====

/**
 * Validates a RelationTypeDefinition structure.
 */
export function validateRelationTypeDefinition(relationTypeDef: RelationTypeDefinition): void {
  if (!relationTypeDef.name || typeof relationTypeDef.name !== 'string') {
    throw new SchemaError(
      'Relation type definition must have a valid name',
      { typeName: relationTypeDef.name, violatedRule: 'relation_type_name_required' }
    );
  }

  if (!relationTypeDef.source_object_type_names || !Array.isArray(relationTypeDef.source_object_type_names)) {
    throw new SchemaError(
      'Relation type definition must have source_object_type_names array',
      { typeName: relationTypeDef.name, violatedRule: 'source_types_array_required' }
    );
  }

  if (!relationTypeDef.target_object_type_names || !Array.isArray(relationTypeDef.target_object_type_names)) {
    throw new SchemaError(
      'Relation type definition must have target_object_type_names array',
      { typeName: relationTypeDef.name, violatedRule: 'target_types_array_required' }
    );
  }

  if (relationTypeDef.source_object_type_names.length === 0) {
    throw new SchemaError(
      'Relation type definition must have at least one source object type',
      { typeName: relationTypeDef.name, violatedRule: 'minimum_source_types' }
    );
  }

  if (relationTypeDef.target_object_type_names.length === 0) {
    throw new SchemaError(
      'Relation type definition must have at least one target object type',
      { typeName: relationTypeDef.name, violatedRule: 'minimum_target_types' }
    );
  }

  // Validate relation properties if they exist
  if (relationTypeDef.properties) {
    relationTypeDef.properties.forEach(validatePropertyDefinition);
  }
}

// ===== RELATION INSTANCE VALIDATION =====

/**
 * Validates a RelationInstance against its RelationTypeDefinition.
 */
export function validateRelationInstance(
  relationInstance: RelationInstance,
  relationTypeDef: RelationTypeDefinition
): void {
  if (!relationInstance.relation_type_name) {
    throw new ValidationError(
      'Relation instance must have relation_type_name',
      { violatedRule: 'relation_type_name_required' }
    );
  }

  if (relationInstance.relation_type_name !== relationTypeDef.name) {
    throw new ValidationError(
      createErrorMessage('Relation instance type name does not match definition', {
        instanceType: relationInstance.relation_type_name,
        definitionType: relationTypeDef.name,
      }),
      { violatedRule: 'relation_type_name_mismatch' }
    );
  }

  if (!isValidUUID(relationInstance.source_object_instance_id)) {
    throw new ValidationError(
      'Relation instance must have valid UUID source_object_instance_id',
      { fieldName: 'source_object_instance_id', violatedRule: 'valid_source_uuid' }
    );
  }

  if (!isValidUUID(relationInstance.target_object_instance_id)) {
    throw new ValidationError(
      'Relation instance must have valid UUID target_object_instance_id',
      { fieldName: 'target_object_instance_id', violatedRule: 'valid_target_uuid' }
    );
  }

  // Validate MemoryInstance fields
  if (!isValidUUID(relationInstance.id)) {
    throw new ValidationError(
      'Relation instance must have valid UUID id',
      { fieldName: 'id', violatedRule: 'valid_uuid_id' }
    );
  }

  if (!(relationInstance.weight instanceof Decimal) || relationInstance.weight.lt(0) || relationInstance.weight.gt(10)) {
    throw new ValidationError(
      'Relation instance weight must be a Decimal between 0 and 10',
      { fieldName: 'weight', violatedRule: 'valid_weight_range' }
    );
  }

  if (!(relationInstance.upsert_date instanceof Date)) {
    throw new ValidationError(
      'Relation instance upsert_date must be a Date',
      { fieldName: 'upsert_date', violatedRule: 'valid_upsert_date' }
    );
  }

  // Validate relation properties if they exist
  if (relationTypeDef.properties && relationInstance.properties) {
    for (const propDef of relationTypeDef.properties) {
      const propValue = relationInstance.properties[propDef.name];

      if (propValue === undefined || propValue === null) {
        if (!propDef.is_nullable) {
          throw new ValidationError(
            createErrorMessage(`Required relation property '${propDef.name}' is missing or null`, { propDef }),
            { fieldName: propDef.name, violatedRule: 'required_relation_property_missing' }
          );
        }
        continue;
      }

      validatePropertyDataType(propValue, propDef.data_type, propDef.name);
    }
  }
}

// ===== FILTER VALUE VALIDATION =====

/**
 * Validates a filter value for query operations.
 */
export function validateFilterValue(
  value: FilterValueType,
  operator: RelationalOperator,
  fieldName: string = 'filter'
): void {
  if (value === null || value === undefined) {
    // Null/undefined values are only valid with specific operators
    if (!['==', '!='].includes(operator)) {
      throw new ValidationError(
        createErrorMessage(`Null/undefined values not allowed with operator '${operator}'`, { value, operator }),
        { fieldName, violatedRule: 'null_value_operator' }
      );
    }
    return;
  }

  // Validate array values for specific operators
  if (['IN', 'CONTAINS'].includes(operator)) {
    if (!Array.isArray(value)) {
      throw new ValidationError(
        createErrorMessage(`Operator '${operator}' requires an array value`, { value, operator }),
        { fieldName, violatedRule: 'array_value_required' }
      );
    }

    if (value.length === 0) {
      throw new ValidationError(
        createErrorMessage(`Operator '${operator}' requires a non-empty array`, { value, operator }),
        { fieldName, violatedRule: 'non_empty_array_required' }
      );
    }

    // Validate each array element
    value.forEach((item, index) => {
      if (item === null || item === undefined) {
        throw new ValidationError(
          createErrorMessage(`Array element at index ${index} cannot be null/undefined`, { value, index }),
          { fieldName, violatedRule: 'array_element_not_null' }
        );
      }
    });
  }

  // Validate string values for pattern operators
  if (['LIKE', 'STARTSWITH', 'ENDSWITH'].includes(operator)) {
    if (typeof value !== 'string') {
      throw new ValidationError(
        createErrorMessage(`Operator '${operator}' requires a string value`, { value, operator }),
        { fieldName, violatedRule: 'string_value_required' }
      );
    }
  }
}

// ===== SCHEMA COMPLIANCE CHECKING =====

/**
 * Comprehensive schema compliance check for ObjectTypeDefinition.
 */
export function validateSchemaCompliance(objTypeDef: ObjectTypeDefinition): void {
  try {
    validateObjectTypeDefinition(objTypeDef);

    // Additional compliance checks
    const primaryKeyProps = objTypeDef.properties.filter(p => p.is_primary_key);
    if (primaryKeyProps.length === 0) {
      console.warn(`ObjectTypeDefinition '${objTypeDef.name}' has no primary key property. Consider adding one for data integrity.`);
    }

    // Check naming conventions
    if (!/^[A-Z][a-zA-Z0-9]*$/.test(objTypeDef.name)) {
      console.warn(`ObjectTypeDefinition name '${objTypeDef.name}' should follow PascalCase convention.`);
    }

    objTypeDef.properties.forEach(prop => {
      if (!/^[a-z][a-zA-Z0-9_]*$/.test(prop.name)) {
        console.warn(`Property name '${prop.name}' in '${objTypeDef.name}' should follow snake_case or camelCase convention.`);
      }
    });

  } catch (error) {
    if (error instanceof ValidationError || error instanceof SchemaError) {
      throw error;
    }
    throw new SchemaError(
      createErrorMessage('Schema compliance check failed', { originalError: error }),
      { typeName: objTypeDef.name, violatedRule: 'schema_compliance_check' }
    );
  }
}

// ===== BATCH VALIDATION UTILITIES =====

/**
 * Validates multiple ObjectInstances against their ObjectTypeDefinition.
 */
export function validateObjectInstances(
  instances: ObjectInstance[],
  objTypeDef: ObjectTypeDefinition
): void {
  const errors: ValidationError[] = [];

  instances.forEach((instance, index) => {
    try {
      validateObjectInstance(instance, objTypeDef);
    } catch (error) {
      if (error instanceof ValidationError) {
        errors.push(error);
      } else {
        errors.push(new ValidationError(
          createErrorMessage(`Unexpected error validating instance at index ${index}`, { error }),
          { violatedRule: 'unexpected_validation_error' }
        ));
      }
    }
  });

  if (errors.length > 0) {
    throw new ValidationError(
      createErrorMessage(`Validation failed for ${errors.length} of ${instances.length} instances`, {
        errorCount: errors.length,
        totalCount: instances.length,
      }),
      { violatedRule: 'batch_validation_failure' }
    );
  }
}

/**
 * Validates multiple RelationInstances against their RelationTypeDefinition.
 */
export function validateRelationInstances(
  instances: RelationInstance[],
  relationTypeDef: RelationTypeDefinition
): void {
  const errors: ValidationError[] = [];

  instances.forEach((instance, index) => {
    try {
      validateRelationInstance(instance, relationTypeDef);
    } catch (error) {
      if (error instanceof ValidationError) {
        errors.push(error);
      } else {
        errors.push(new ValidationError(
          createErrorMessage(`Unexpected error validating relation at index ${index}`, { error }),
          { violatedRule: 'unexpected_relation_validation_error' }
        ));
      }
    }
  });

  if (errors.length > 0) {
    throw new ValidationError(
      createErrorMessage(`Relation validation failed for ${errors.length} of ${instances.length} instances`, {
        errorCount: errors.length,
        totalCount: instances.length,
      }),
      { violatedRule: 'batch_relation_validation_failure' }
    );
  }
}