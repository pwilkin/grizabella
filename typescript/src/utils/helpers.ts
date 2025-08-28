/**
 * Common Helper Functions for Grizabella TypeScript API
 *
 * This module provides utility functions for common operations such as
 * object instance creation, relation building, query construction, and
 * configuration management to improve developer experience.
 */

import { v4 as uuidv4 } from 'uuid';
import { Decimal } from 'decimal.js';
import {
  PropertyDefinition,
  ObjectTypeDefinition,
  ObjectInstance,
  // RelationTypeDefinition,
  RelationInstance,
  // EmbeddingDefinition,
  FindObjectsParams,
  QueryRelationsParams,
} from '../types/core';
import { PropertyDataType } from '../types/enums';
import {
  ValidationError,
  createErrorMessage,
} from '../client/errors';
import { validateObjectInstance } from './validation';
import { convertObjectInstance } from './conversion';

// ===== OBJECT INSTANCE CREATION HELPERS =====

/**
 * Configuration for object instance creation.
 */
export interface ObjectInstanceConfig {
  /** Custom ID (if not provided, UUID will be generated) */
  id?: string;
  /** Weight for the instance (default: 1.0) */
  weight?: number;
  /** Custom upsert date (default: now) */
  upsertDate?: Date;
  /** Whether to validate the instance after creation */
  validate?: boolean;
  /** Whether to convert property values */
  convertValues?: boolean;
}

/**
 * Creates a new ObjectInstance with default values and optional configuration.
 */
export function createObjectInstance(
  objectTypeName: string,
  properties: Record<string, any>,
  config: ObjectInstanceConfig = {}
): ObjectInstance {
  const {
    id = uuidv4(),
    weight = 1.0,
    upsertDate = new Date(),
    validate = false,
    // convertValues = false, // This parameter is not used in this function
  } = config;

  const instance: ObjectInstance = {
    id,
    object_type_name: objectTypeName,
    weight: new Decimal(weight),
    upsert_date: upsertDate,
    properties: { ...properties },
  };

  // Validate the instance if requested
  if (validate) {
    // Note: We need the ObjectTypeDefinition for full validation
    // This would be passed in a real implementation
    console.warn('Validation requested but ObjectTypeDefinition not provided - skipping validation');
  }

  return instance;
}

/**
 * Creates a new ObjectInstance from an ObjectTypeDefinition with default property values.
 */
export function createObjectInstanceFromDefinition(
  objTypeDef: ObjectTypeDefinition,
  overrides: Record<string, any> = {},
  config: ObjectInstanceConfig = {}
): ObjectInstance {
  const defaultProperties: Record<string, any> = {};

  // Set default values based on property definitions
  for (const propDef of objTypeDef.properties) {
    if (overrides[propDef.name] !== undefined) {
      defaultProperties[propDef.name] = overrides[propDef.name];
    } else if (!propDef.is_nullable) {
      // Set sensible defaults for required properties
      switch (propDef.data_type) {
        case PropertyDataType.TEXT:
          defaultProperties[propDef.name] = '';
          break;
        case PropertyDataType.INTEGER:
        case PropertyDataType.FLOAT:
          defaultProperties[propDef.name] = 0;
          break;
        case PropertyDataType.BOOLEAN:
          defaultProperties[propDef.name] = false;
          break;
        case PropertyDataType.DATETIME:
          defaultProperties[propDef.name] = new Date();
          break;
        case PropertyDataType.UUID:
          defaultProperties[propDef.name] = uuidv4();
          break;
        case PropertyDataType.JSON:
          defaultProperties[propDef.name] = {};
          break;
        case PropertyDataType.BLOB:
          defaultProperties[propDef.name] = new Uint8Array(0);
          break;
        default:
          defaultProperties[propDef.name] = null;
      }
    }
  }

  const instance = createObjectInstance(objTypeDef.name, defaultProperties, config);

  // Validate against the definition
  if (config.validate !== false) {
    validateObjectInstance(instance, objTypeDef);
  }

  if (config.convertValues) {
    return convertObjectInstance(instance, objTypeDef.properties);
  }

  return instance;
}

// ===== RELATION BUILDING UTILITIES =====

/**
 * Configuration for relation instance creation.
 */
export interface RelationInstanceConfig {
  /** Custom ID (if not provided, UUID will be generated) */
  id?: string;
  /** Weight for the relation (default: 1.0) */
  weight?: number;
  /** Custom upsert date (default: now) */
  upsertDate?: Date;
  /** Whether to validate the relation after creation */
  validate?: boolean;
}

/**
 * Creates a new RelationInstance.
 */
export function createRelationInstance(
  relationTypeName: string,
  sourceObjectId: string,
  targetObjectId: string,
  properties?: Record<string, any>,
  config: RelationInstanceConfig = {}
): RelationInstance {
  const {
    id = uuidv4(),
    weight = 1.0,
    upsertDate = new Date(),
    validate = false,
  } = config;

  const instance: RelationInstance = {
    id,
    relation_type_name: relationTypeName,
    source_object_instance_id: sourceObjectId,
    target_object_instance_id: targetObjectId,
    weight: new Decimal(weight),
    upsert_date: upsertDate,
    properties: properties ? { ...properties } : {},
  };

  // Validate the instance if requested
  if (validate) {
    // Note: We need the RelationTypeDefinition for full validation
    console.warn('Validation requested but RelationTypeDefinition not provided - skipping validation');
  }

  return instance;
}

/**
 * Creates multiple relations from a single source to multiple targets.
 */
export function createRelationsFromSource(
  relationTypeName: string,
  sourceObjectId: string,
  targetObjectIds: string[],
  properties?: Record<string, any>,
  config: RelationInstanceConfig = {}
): RelationInstance[] {
  return targetObjectIds.map(targetId =>
    createRelationInstance(relationTypeName, sourceObjectId, targetId, properties, config)
  );
}

/**
 * Creates multiple relations from multiple sources to a single target.
 */
export function createRelationsToTarget(
  relationTypeName: string,
  sourceObjectIds: string[],
  targetObjectId: string,
  properties?: Record<string, any>,
  config: RelationInstanceConfig = {}
): RelationInstance[] {
  return sourceObjectIds.map(sourceId =>
    createRelationInstance(relationTypeName, sourceId, targetObjectId, properties, config)
  );
}

/**
 * Creates bidirectional relations between object pairs.
 */
export function createBidirectionalRelations(
  forwardRelationType: string,
  reverseRelationType: string,
  objectPairs: Array<[string, string]>,
  forwardProperties?: Record<string, any>,
  reverseProperties?: Record<string, any>,
  config: RelationInstanceConfig = {}
): RelationInstance[] {
  const relations: RelationInstance[] = [];

  for (const [sourceId, targetId] of objectPairs) {
    relations.push(
      createRelationInstance(forwardRelationType, sourceId, targetId, forwardProperties, config),
      createRelationInstance(reverseRelationType, targetId, sourceId, reverseProperties, config)
    );
  }

  return relations;
}

// ===== QUERY PARAMETER BUILDERS =====

/**
 * Configuration for query building.
 */
export interface QueryBuilderConfig {
  /** Default limit for queries */
  defaultLimit?: number;
  /** Maximum allowed limit */
  maxLimit?: number;
  /** Whether to include metadata in results */
  includeMetadata?: boolean;
}

/**
 * Builds FindObjectsParams with validation and defaults.
 */
export function buildFindObjectsQuery(
  typeName: string,
  filterCriteria?: Record<string, any>,
  options: {
    limit?: number;
    offset?: number;
    orderBy?: string;
    ascending?: boolean;
  } = {},
  config: QueryBuilderConfig = {}
): FindObjectsParams {
  const { defaultLimit = 100, maxLimit = 1000 } = config;
  const { limit = defaultLimit } = options;

  if (limit > maxLimit) {
    throw new ValidationError(
      createErrorMessage(`Limit exceeds maximum allowed value`, { limit, maxLimit }),
      { violatedRule: 'query_limit_too_large' }
    );
  }

  if (limit <= 0) {
    throw new ValidationError(
      createErrorMessage(`Limit must be positive`, { limit }),
      { violatedRule: 'invalid_query_limit' }
    );
  }

  const params: FindObjectsParams = {
    type_name: typeName,
    limit,
  };

  if (filterCriteria && Object.keys(filterCriteria).length > 0) {
    params.filter_criteria = filterCriteria;
  }

  return params;
}

/**
 * Builds QueryRelationsParams with validation and defaults.
 */
export function buildQueryRelationsQuery(
  options: {
    relationTypeName?: string;
    sourceObjectId?: string;
    targetObjectId?: string;
    propertiesQuery?: Record<string, any>;
    limit?: number;
  } = {},
  config: QueryBuilderConfig = {}
): QueryRelationsParams {
  const { defaultLimit = 100, maxLimit = 1000 } = config;
  const { limit = defaultLimit } = options;

  if (limit > maxLimit) {
    throw new ValidationError(
      createErrorMessage(`Limit exceeds maximum allowed value`, { limit, maxLimit }),
      { violatedRule: 'query_limit_too_large' }
    );
  }

  const params: QueryRelationsParams = {};

  if (options.relationTypeName) {
    params.relation_type_name = options.relationTypeName;
  }

  if (options.sourceObjectId) {
    params.source_object_instance_id = options.sourceObjectId;
  }

  if (options.targetObjectId) {
    params.target_object_instance_id = options.targetObjectId;
  }

  if (options.propertiesQuery) {
    params.properties_query = options.propertiesQuery;
  }

  if (limit > 0) {
    params.limit = limit;
  }

  return params;
}

/**
 * Builds complex filter criteria with a fluent interface.
 */
export class FilterBuilder {
  private criteria: Record<string, any> = {};

  /**
   * Add an equality filter.
   */
  equals(field: string, value: any): FilterBuilder {
    this.criteria[field] = value;
    return this;
  }

  /**
   * Add a range filter.
   */
  range(field: string, min?: any, max?: any): FilterBuilder {
    if (min !== undefined || max !== undefined) {
      this.criteria[field] = { min, max };
    }
    return this;
  }

  /**
   * Add a pattern filter for string fields.
   */
  like(field: string, pattern: string): FilterBuilder {
    this.criteria[field] = { $like: pattern };
    return this;
  }

  /**
   * Add an in-array filter.
   */
  in(field: string, values: any[]): FilterBuilder {
    this.criteria[field] = { $in: values };
    return this;
  }

  /**
   * Add a contains filter for arrays.
   */
  contains(field: string, value: any): FilterBuilder {
    this.criteria[field] = { $contains: value };
    return this;
  }

  /**
   * Add a custom filter condition.
   */
  where(field: string, condition: any): FilterBuilder {
    this.criteria[field] = condition;
    return this;
  }

  /**
   * Build the final criteria object.
   */
  build(): Record<string, any> {
    return { ...this.criteria };
  }

  /**
   * Create a new FilterBuilder instance.
   */
  static create(): FilterBuilder {
    return new FilterBuilder();
  }
}

// ===== CONFIGURATION HELPERS =====

/**
 * Configuration for ObjectTypeDefinition creation.
 */
export interface ObjectTypeConfig {
  /** Whether to add standard audit fields (created_at, updated_at) */
  includeAuditFields?: boolean;
  /** Whether to add soft delete support */
  includeSoftDelete?: boolean;
  /** Whether to use snake_case for property names (default: camelCase) */
  useSnakeCase?: boolean;
  /** Custom property templates to include */
  includeTemplates?: PropertyTemplate[];
}

/**
 * Property template for common property patterns.
 */
export interface PropertyTemplate {
  name: string;
  dataType: PropertyDataType;
  isNullable?: boolean;
  isUnique?: boolean;
  isIndexed?: boolean;
  description?: string;
}

/**
 * Predefined property templates.
 */
export const PROPERTY_TEMPLATES = {
  ID: { name: 'id', dataType: PropertyDataType.UUID, isNullable: false },
  NAME: { name: 'name', dataType: PropertyDataType.TEXT, isNullable: false },
  DESCRIPTION: { name: 'description', dataType: PropertyDataType.TEXT, isNullable: true },
  CREATED_AT: { name: 'created_at', dataType: PropertyDataType.DATETIME, isNullable: false },
  UPDATED_AT: { name: 'updated_at', dataType: PropertyDataType.DATETIME, isNullable: false },
  IS_ACTIVE: { name: 'is_active', dataType: PropertyDataType.BOOLEAN, isNullable: false, default: true },
  VERSION: { name: 'version', dataType: PropertyDataType.INTEGER, isNullable: false, default: 1 },
} as const;

/**
 * Creates an ObjectTypeDefinition with common configuration patterns.
 */
export function createObjectType(
  name: string,
  properties: PropertyDefinition[],
  config: ObjectTypeConfig = {}
): ObjectTypeDefinition {
  const {
    includeAuditFields = false,
    includeSoftDelete = false,
    useSnakeCase = false,
    includeTemplates = [],
  } = config;

  const allProperties = [...properties];

  // Add template properties
  for (const template of includeTemplates) {
    const property: PropertyDefinition = {
      name: template.name,
      data_type: template.dataType,
      is_nullable: template.isNullable ?? true,
      is_unique: template.isUnique ?? false,
      is_indexed: template.isIndexed ?? false,
    };
    
    // Only add description if it's provided
    if (template.description !== undefined) {
      property.description = template.description;
    }
    
    allProperties.push(property);
  }

  // Add audit fields
  if (includeAuditFields) {
    allProperties.push(
      {
        name: useSnakeCase ? 'created_at' : 'createdAt',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'Timestamp when the object was created',
      },
      {
        name: useSnakeCase ? 'updated_at' : 'updatedAt',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'Timestamp when the object was last updated',
      }
    );
  }

  // Add soft delete support
  if (includeSoftDelete) {
    allProperties.push({
      name: useSnakeCase ? 'deleted_at' : 'deletedAt',
      data_type: PropertyDataType.DATETIME,
      is_nullable: true,
      description: 'Timestamp when the object was soft deleted',
    });
  }

  return {
    name,
    description: `Object type for ${name}`,
    properties: allProperties,
  };
}

// ===== BATCH OPERATION HELPERS =====

/**
 * Configuration for batch operations.
 */
export interface BatchConfig {
  /** Maximum batch size */
  batchSize?: number;
  /** Whether to continue on individual errors */
  continueOnError?: boolean;
  /** Whether to validate each item before processing */
  validateItems?: boolean;
}

/**
 * Processes ObjectInstances in batches with error handling.
 */
export async function processObjectInstancesBatch<T>(
  instances: ObjectInstance[],
  processor: (batch: ObjectInstance[]) => Promise<T[]>,
  config: BatchConfig = {}
): Promise<T[]> {
  const { batchSize = 100, continueOnError = false, validateItems = false } = config;
  const results: T[] = [];
  const errors: Error[] = [];

  for (let i = 0; i < instances.length; i += batchSize) {
    const batch = instances.slice(i, i + batchSize);

    try {
      if (validateItems) {
        // Basic validation - full validation would need ObjectTypeDefinition
        batch.forEach(instance => {
          if (!instance.id || !instance.object_type_name) {
            throw new ValidationError('Invalid object instance structure');
          }
        });
      }

      const batchResults = await processor(batch);
      results.push(...batchResults);
    } catch (error) {
      if (continueOnError) {
        errors.push(error as Error);
        console.warn(`Batch ${Math.floor(i / batchSize) + 1} failed:`, error);
      } else {
        throw error;
      }
    }
  }

  if (errors.length > 0 && continueOnError) {
    console.warn(`${errors.length} batches failed during processing`);
  }

  return results;
}

/**
 * Creates multiple ObjectInstances with a factory pattern.
 */
export function createMultipleObjectInstances(
  objectTypeName: string,
  propertySets: Record<string, any>[],
  config: ObjectInstanceConfig = {}
): ObjectInstance[] {
  return propertySets.map(props => createObjectInstance(objectTypeName, props, config));
}

// ===== UTILITY FUNCTIONS =====

/**
 * Generates a unique object type name with a timestamp suffix.
 */
export function generateUniqueTypeName(baseName: string): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  return `${baseName}_${timestamp}_${random}`;
}

/**
 * Creates a deep clone of an ObjectInstance.
 */
export function cloneObjectInstance(instance: ObjectInstance): ObjectInstance {
  return {
    ...instance,
    weight: new Decimal(instance.weight),
    upsert_date: new Date(instance.upsert_date),
    properties: JSON.parse(JSON.stringify(instance.properties)),
  };
}

/**
 * Extracts property names from an ObjectTypeDefinition.
 */
export function getPropertyNames(objTypeDef: ObjectTypeDefinition): string[] {
  return objTypeDef.properties.map(prop => prop.name);
}

/**
 * Checks if an object type has a specific property.
 */
export function hasProperty(objTypeDef: ObjectTypeDefinition, propertyName: string): boolean {
  return objTypeDef.properties.some(prop => prop.name === propertyName);
}

/**
 * Gets a property definition by name.
 */
export function getPropertyDefinition(
  objTypeDef: ObjectTypeDefinition,
  propertyName: string
): PropertyDefinition | undefined {
  return objTypeDef.properties.find(prop => prop.name === propertyName);
}