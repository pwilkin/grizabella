/**
 * Unit tests for validation utilities
 *
 * Tests all validation functions for data integrity, schema compliance,
 * and type safety across the Grizabella API ecosystem.
 */

import { Decimal } from 'decimal.js';
import {
  PropertyDataType,
} from '../../src/types/enums';

import {
  PropertyDefinition,
  ObjectTypeDefinition,
  ObjectInstance,
  RelationTypeDefinition,
  RelationInstance,
} from '../../src/types';
import {
  ValidationError,
  SchemaError,
} from '../../src/client/errors';
import {
  // UUID validation
  isValidUUID,
  validateUUID,
  normalizeUUID,

  // Data type validation
  validatePropertyDataType,

  // Property definition validation
  validatePropertyDefinition,

  // Object type definition validation
  validateObjectTypeDefinition,

  // Object instance validation
  validateObjectInstance,

  // Relation type definition validation
  validateRelationTypeDefinition,

  // Relation instance validation
  validateRelationInstance,

  // Filter value validation
  validateFilterValue,

  // Schema compliance checking
  validateSchemaCompliance,

  // Batch validation utilities
  validateObjectInstances,
  validateRelationInstances,
} from '../../src/utils/validation';

import {
  createTestObjectTypeDefinition,
  createTestObjectInstance,
  createTestRelationTypeDefinition,
  createTestRelationInstance,
  assertThrowsError,
} from '../utils/test-helpers';

describe('Validation Utilities', () => {
  describe('UUID Validation', () => {
    const validUUID = '550e8400-e29b-41d4-a716-446655440000';
    const invalidUUID = 'invalid-uuid';

    describe('isValidUUID', () => {
      it('should return true for valid UUID v4', () => {
        expect(isValidUUID(validUUID)).toBe(true);
      });

      it('should return false for invalid UUID', () => {
        expect(isValidUUID(invalidUUID)).toBe(false);
      });

      it('should return false for non-string values', () => {
        expect(isValidUUID(123 as any)).toBe(false);
        expect(isValidUUID(null as any)).toBe(false);
        expect(isValidUUID(undefined as any)).toBe(false);
        expect(isValidUUID({} as any)).toBe(false);
      });

      it('should return false for valid UUID v1', () => {
        const uuidV1 = '550e8400-e29b-11d4-a716-446655440000';
        expect(isValidUUID(uuidV1)).toBe(false);
      });

      it('should be case insensitive', () => {
        const upperUUID = validUUID.toUpperCase();
        const lowerUUID = validUUID.toLowerCase();

        expect(isValidUUID(upperUUID)).toBe(true);
        expect(isValidUUID(lowerUUID)).toBe(true);
      });
    });

    describe('validateUUID', () => {
      it('should not throw for valid UUID', () => {
        expect(() => validateUUID(validUUID)).not.toThrow();
      });

      it('should throw ValidationError for invalid UUID', async () => {
        await assertThrowsError(
          () => validateUUID(invalidUUID),
          ValidationError,
          'Invalid UUID format'
        );
      });

      it('should include field name in error message', async () => {
        await assertThrowsError(
          () => validateUUID(invalidUUID, 'userId'),
          ValidationError,
          "Invalid UUID format for field 'userId'"
        );
      });
    });

    describe('normalizeUUID', () => {
      it('should normalize valid UUID to lowercase and trimmed', () => {
        const input = `  ${validUUID.toUpperCase()}  `;
        const normalized = normalizeUUID(input);

        expect(normalized).toBe(validUUID.toLowerCase());
      });

      it('should throw ValidationError for invalid UUID', async () => {
        await assertThrowsError(
          () => normalizeUUID(invalidUUID),
          ValidationError,
          'Invalid UUID format'
        );
      });
    });
  });

  describe('Property Data Type Validation', () => {
    describe('TEXT validation', () => {
      it('should accept valid strings', () => {
        expect(() => validatePropertyDataType('valid string', PropertyDataType.TEXT)).not.toThrow();
        expect(() => validatePropertyDataType('', PropertyDataType.TEXT)).not.toThrow();
      });

      it('should reject non-strings', async () => {
        await assertThrowsError(
          () => validatePropertyDataType(123, PropertyDataType.TEXT),
          ValidationError,
          'Expected string for TEXT property'
        );
      });
    });

    describe('INTEGER validation', () => {
      it('should accept valid integers', () => {
        expect(() => validatePropertyDataType(42, PropertyDataType.INTEGER)).not.toThrow();
        expect(() => validatePropertyDataType(0, PropertyDataType.INTEGER)).not.toThrow();
        expect(() => validatePropertyDataType(-123, PropertyDataType.INTEGER)).not.toThrow();
      });

      it('should reject floats', async () => {
        await assertThrowsError(
          () => validatePropertyDataType(42.5, PropertyDataType.INTEGER),
          ValidationError,
          'Expected integer for INTEGER property'
        );
      });

      it('should reject non-numbers', async () => {
        await assertThrowsError(
          () => validatePropertyDataType('42', PropertyDataType.INTEGER),
          ValidationError,
          'Expected integer for INTEGER property'
        );
      });
    });

    describe('FLOAT validation', () => {
      it('should accept valid floats', () => {
        expect(() => validatePropertyDataType(42.5, PropertyDataType.FLOAT)).not.toThrow();
        expect(() => validatePropertyDataType(0.0, PropertyDataType.FLOAT)).not.toThrow();
        expect(() => validatePropertyDataType(-123.456, PropertyDataType.FLOAT)).not.toThrow();
        expect(() => validatePropertyDataType(Infinity, PropertyDataType.FLOAT)).toThrow();
      });

      it('should reject non-finite numbers', async () => {
        await assertThrowsError(
          () => validatePropertyDataType(NaN, PropertyDataType.FLOAT),
          ValidationError,
          'Expected finite number for FLOAT property'
        );
      });

      it('should reject non-numbers', async () => {
        await assertThrowsError(
          () => validatePropertyDataType('42.5', PropertyDataType.FLOAT),
          ValidationError,
          'Expected finite number for FLOAT property'
        );
      });
    });

    describe('BOOLEAN validation', () => {
      it('should accept boolean values', () => {
        expect(() => validatePropertyDataType(true, PropertyDataType.BOOLEAN)).not.toThrow();
        expect(() => validatePropertyDataType(false, PropertyDataType.BOOLEAN)).not.toThrow();
      });

      it('should reject non-booleans', async () => {
        await assertThrowsError(
          () => validatePropertyDataType('true', PropertyDataType.BOOLEAN),
          ValidationError,
          'Expected boolean for BOOLEAN property'
        );
      });
    });

    describe('DATETIME validation', () => {
      it('should accept Date objects', () => {
        const date = new Date();
        expect(() => validatePropertyDataType(date, PropertyDataType.DATETIME)).not.toThrow();
      });

      it('should accept valid ISO date strings', () => {
        expect(() => validatePropertyDataType('2023-01-15T10:30:00Z', PropertyDataType.DATETIME)).not.toThrow();
        expect(() => validatePropertyDataType('2023-01-15', PropertyDataType.DATETIME)).not.toThrow();
      });

      it('should reject invalid date strings', async () => {
        await assertThrowsError(
          () => validatePropertyDataType('invalid-date', PropertyDataType.DATETIME),
          ValidationError,
          'Invalid ISO date string'
        );
      });

      it('should reject other types', async () => {
        await assertThrowsError(
          () => validatePropertyDataType(123, PropertyDataType.DATETIME),
          ValidationError,
          'Expected Date or ISO string for DATETIME property'
        );
      });
    });

    describe('BLOB validation', () => {
      it('should accept Uint8Array', () => {
        const blob = new Uint8Array([1, 2, 3]);
        expect(() => validatePropertyDataType(blob, PropertyDataType.BLOB)).not.toThrow();
      });

      it('should accept number arrays', () => {
        const blob = [1, 2, 3];
        expect(() => validatePropertyDataType(blob, PropertyDataType.BLOB)).not.toThrow();
      });

      it('should reject other types', async () => {
        await assertThrowsError(
          () => validatePropertyDataType('blob', PropertyDataType.BLOB),
          ValidationError,
          'Expected Uint8Array or byte array for BLOB property'
        );
      });
    });

    describe('JSON validation', () => {
      it('should accept valid JSON objects', () => {
        expect(() => validatePropertyDataType({ key: 'value' }, PropertyDataType.JSON)).not.toThrow();
        expect(() => validatePropertyDataType([1, 2, 3], PropertyDataType.JSON)).not.toThrow();
      });

      it('should accept valid JSON strings', () => {
        expect(() => validatePropertyDataType('{"key": "value"}', PropertyDataType.JSON)).not.toThrow();
        expect(() => validatePropertyDataType('[1, 2, 3]', PropertyDataType.JSON)).not.toThrow();
      });

      it('should reject invalid JSON strings', async () => {
        await assertThrowsError(
          () => validatePropertyDataType('{"invalid": json}', PropertyDataType.JSON),
          ValidationError,
          'Expected valid JSON for JSON property'
        );
      });

      it('should reject null and undefined', async () => {
        await assertThrowsError(
          () => validatePropertyDataType(null, PropertyDataType.JSON),
          ValidationError,
          'Expected valid JSON for JSON property'
        );
      });
    });

    describe('UUID validation', () => {
      it('should accept valid UUID strings', () => {
        const validUUID = '550e8400-e29b-41d4-a716-446655440000';
        expect(() => validatePropertyDataType(validUUID, PropertyDataType.UUID)).not.toThrow();
      });

      it('should reject invalid UUID strings', async () => {
        await assertThrowsError(
          () => validatePropertyDataType('invalid-uuid', PropertyDataType.UUID),
          ValidationError,
          'Expected valid UUID for UUID property'
        );
      });

      it('should reject non-string values', async () => {
        await assertThrowsError(
          () => validatePropertyDataType(123, PropertyDataType.UUID),
          ValidationError,
          'Expected valid UUID for UUID property'
        );
      });
    });

    describe('Unknown data type', () => {
      it('should throw ValidationError for unknown data types', async () => {
        await assertThrowsError(
          () => validatePropertyDataType('value', 'UNKNOWN' as any),
          ValidationError,
          "Unknown data type 'UNKNOWN'"
        );
      });
    });
  });

  describe('Property Definition Validation', () => {
    it('should accept valid property definitions', () => {
      const propDef: PropertyDefinition = {
        name: 'testProperty',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: false,
      };

      expect(() => validatePropertyDefinition(propDef)).not.toThrow();
    });

    it('should reject property without name', async () => {
      const propDef = {
        data_type: PropertyDataType.TEXT,
      } as PropertyDefinition;

      await assertThrowsError(
        () => validatePropertyDefinition(propDef),
        SchemaError,
        'Property definition must have a valid name'
      );
    });

    it('should reject property with invalid name', async () => {
      const propDef = {
        name: '',
        data_type: PropertyDataType.TEXT,
      } as PropertyDefinition;

      await assertThrowsError(
        () => validatePropertyDefinition(propDef),
        SchemaError,
        'Property definition must have a valid name'
      );
    });

    it('should reject property with invalid data type', async () => {
      const propDef = {
        name: 'testProperty',
        data_type: 'INVALID' as any,
      } as PropertyDefinition;

      await assertThrowsError(
        () => validatePropertyDefinition(propDef),
        SchemaError,
        'Invalid property data type'
      );
    });

    it('should reject nullable primary key', async () => {
      const propDef: PropertyDefinition = {
        name: 'id',
        data_type: PropertyDataType.UUID,
        is_nullable: true,
        is_primary_key: true,
      };

      await assertThrowsError(
        () => validatePropertyDefinition(propDef),
        SchemaError,
        'Primary key properties cannot be nullable'
      );
    });

    it('should reject nullable unique property', async () => {
      const propDef: PropertyDefinition = {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        is_unique: true,
      };

      await assertThrowsError(
        () => validatePropertyDefinition(propDef),
        SchemaError,
        'Unique properties should typically not be nullable'
      );
    });
  });

  describe('Object Type Definition Validation', () => {
    it('should accept valid object type definitions', () => {
      const objTypeDef = createTestObjectTypeDefinition('Person', [
        { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
        { name: 'age', data_type: PropertyDataType.INTEGER, is_nullable: true },
      ]);

      expect(() => validateObjectTypeDefinition(objTypeDef)).not.toThrow();
    });

    it('should reject object type without name', async () => {
      const objTypeDef = {
        name: '',
        properties: [],
      } as ObjectTypeDefinition;

      await assertThrowsError(
        () => validateObjectTypeDefinition(objTypeDef),
        SchemaError,
        'Object type definition must have a valid name'
      );
    });

    it('should reject object type without properties array', async () => {
      const objTypeDef = {
        name: 'Person',
      } as ObjectTypeDefinition;

      await assertThrowsError(
        () => validateObjectTypeDefinition(objTypeDef),
        SchemaError,
        'Object type definition must have properties array'
      );
    });

    it('should reject object type with empty properties', async () => {
      const objTypeDef: ObjectTypeDefinition = {
        name: 'Person',
        properties: [],
      };

      await assertThrowsError(
        () => validateObjectTypeDefinition(objTypeDef),
        SchemaError,
        'Object type definition must have at least one property'
      );
    });

    it('should reject object type with duplicate property names', async () => {
      const objTypeDef: ObjectTypeDefinition = {
        name: 'Person',
        properties: [
          { name: 'name', data_type: PropertyDataType.TEXT },
          { name: 'name', data_type: PropertyDataType.INTEGER },
        ],
      };

      await assertThrowsError(
        () => validateObjectTypeDefinition(objTypeDef),
        SchemaError,
        'Duplicate property names found'
      );
    });

    it('should reject object type with multiple primary keys', async () => {
      const objTypeDef: ObjectTypeDefinition = {
        name: 'Person',
        properties: [
          { name: 'id1', data_type: PropertyDataType.UUID, is_primary_key: true },
          { name: 'id2', data_type: PropertyDataType.UUID, is_primary_key: true },
        ],
      };

      await assertThrowsError(
        () => validateObjectTypeDefinition(objTypeDef),
        SchemaError,
        'Object type definition can have at most one primary key property'
      );
    });
  });

  describe('Object Instance Validation', () => {
    let objTypeDef: ObjectTypeDefinition;
    let validInstance: ObjectInstance;

    beforeEach(() => {
      objTypeDef = createTestObjectTypeDefinition('Person', [
        { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
        { name: 'age', data_type: PropertyDataType.INTEGER, is_nullable: true },
      ]);

      validInstance = createTestObjectInstance('Person', {
        name: 'John Doe',
        age: 30,
      });
    });

    it('should accept valid object instances', () => {
      expect(() => validateObjectInstance(validInstance, objTypeDef)).not.toThrow();
    });

    it('should reject instance without object_type_name', async () => {
      const invalidInstance = { ...validInstance, object_type_name: undefined };

      await assertThrowsError(
        () => validateObjectInstance(invalidInstance as any, objTypeDef),
        ValidationError,
        'Object instance must have object_type_name'
      );
    });

    it('should reject instance with mismatched type name', async () => {
      const invalidInstance = createTestObjectInstance('WrongType', {
        name: 'John Doe',
        age: 30,
      });

      await assertThrowsError(
        () => validateObjectInstance(invalidInstance, objTypeDef),
        ValidationError,
        'Object instance type name does not match definition'
      );
    });

    it('should reject instance without properties object', async () => {
      const invalidInstance = { ...validInstance, properties: undefined };

      await assertThrowsError(
        () => validateObjectInstance(invalidInstance as any, objTypeDef),
        ValidationError,
        'Object instance must have properties object'
      );
    });

    it('should reject instance with invalid UUID id', async () => {
      const invalidInstance = {
        ...validInstance,
        id: 'invalid-uuid',
      };

      await assertThrowsError(
        () => validateObjectInstance(invalidInstance, objTypeDef),
        ValidationError,
        'Object instance must have valid UUID id'
      );
    });

    it('should reject instance with invalid weight', async () => {
      const invalidInstance = {
        ...validInstance,
        weight: new Decimal(-1),
      };

      await assertThrowsError(
        () => validateObjectInstance(invalidInstance, objTypeDef),
        ValidationError,
        'Object instance weight must be a Decimal between 0 and 10'
      );
    });

    it('should reject instance with invalid upsert_date', async () => {
      const invalidInstance = {
        ...validInstance,
        upsert_date: 'invalid-date' as any,
      };

      await assertThrowsError(
        () => validateObjectInstance(invalidInstance, objTypeDef),
        ValidationError,
        'Object instance upsert_date must be a Date'
      );
    });

    it('should reject instance with missing required property', async () => {
      const invalidInstance = createTestObjectInstance('Person', {
        age: 30,
        name: undefined, // Explicitly set name to undefined to test missing required property
      });

      await assertThrowsError(
        () => validateObjectInstance(invalidInstance, objTypeDef),
        ValidationError,
        "Required property 'name' is missing or null"
      );
    });

    it('should reject instance with invalid property data type', async () => {
      const invalidInstance = createTestObjectInstance('Person', {
        name: 123, // Should be string
        age: 30,
      });

      await assertThrowsError(
        () => validateObjectInstance(invalidInstance, objTypeDef),
        ValidationError,
        'Expected string for TEXT property'
      );
    });
  });

  describe('Relation Type Definition Validation', () => {
    it('should accept valid relation type definitions', () => {
      const relationTypeDef = createTestRelationTypeDefinition(
        'KNOWS',
        'Person',
        'Person',
        [
          { name: 'since', data_type: PropertyDataType.DATETIME, is_nullable: true },
        ]
      );

      expect(() => validateRelationTypeDefinition(relationTypeDef)).not.toThrow();
    });

    it('should reject relation type without name', async () => {
      const relationTypeDef = {
        source_object_type_names: ['Person'],
        target_object_type_names: ['Person'],
      } as RelationTypeDefinition;

      await assertThrowsError(
        () => validateRelationTypeDefinition(relationTypeDef),
        SchemaError,
        'Relation type definition must have a valid name'
      );
    });

    it('should reject relation type without source types', async () => {
      const relationTypeDef = {
        name: 'KNOWS',
        target_object_type_names: ['Person'],
      } as RelationTypeDefinition;

      await assertThrowsError(
        () => validateRelationTypeDefinition(relationTypeDef),
        SchemaError,
        'Relation type definition must have source_object_type_names array'
      );
    });

    it('should reject relation type without target types', async () => {
      const relationTypeDef = {
        name: 'KNOWS',
        source_object_type_names: ['Person'],
      } as RelationTypeDefinition;

      await assertThrowsError(
        () => validateRelationTypeDefinition(relationTypeDef),
        SchemaError,
        'Relation type definition must have target_object_type_names array'
      );
    });

    it('should reject relation type with empty source types', async () => {
      const relationTypeDef: RelationTypeDefinition = {
        name: 'KNOWS',
        source_object_type_names: [],
        target_object_type_names: ['Person'],
      };

      await assertThrowsError(
        () => validateRelationTypeDefinition(relationTypeDef),
        SchemaError,
        'Relation type definition must have at least one source object type'
      );
    });

    it('should reject relation type with empty target types', async () => {
      const relationTypeDef: RelationTypeDefinition = {
        name: 'KNOWS',
        source_object_type_names: ['Person'],
        target_object_type_names: [],
      };

      await assertThrowsError(
        () => validateRelationTypeDefinition(relationTypeDef),
        SchemaError,
        'Relation type definition must have at least one target object type'
      );
    });
  });

  describe('Relation Instance Validation', () => {
    let relationTypeDef: RelationTypeDefinition;
    let validRelation: RelationInstance;

    beforeEach(() => {
      relationTypeDef = createTestRelationTypeDefinition(
        'KNOWS',
        'Person',
        'Person',
        [
          { name: 'since', data_type: PropertyDataType.DATETIME, is_nullable: true },
        ]
      );

      validRelation = createTestRelationInstance(
        'KNOWS',
        '550e8400-e29b-41d4-a716-446655440000',
        '550e8400-e29b-41d4-a716-446655440001',
        { since: new Date() }
      );
    });

    it('should accept valid relation instances', () => {
      expect(() => validateRelationInstance(validRelation, relationTypeDef)).not.toThrow();
    });

    it('should reject relation without relation_type_name', async () => {
      const invalidRelation = { ...validRelation, relation_type_name: undefined };

      await assertThrowsError(
        () => validateRelationInstance(invalidRelation as any, relationTypeDef),
        ValidationError,
        'Relation instance must have relation_type_name'
      );
    });

    it('should reject relation with mismatched type name', async () => {
      const invalidRelation = createTestRelationInstance(
        'DIFFERENT_TYPE',
        '550e8400-e29b-41d4-a716-446655440000',
        '550e8400-e29b-41d4-a716-446655440001'
      );

      await assertThrowsError(
        () => validateRelationInstance(invalidRelation, relationTypeDef),
        ValidationError,
        'Relation instance type name does not match definition'
      );
    });

    it('should reject relation with invalid source UUID', async () => {
      const invalidRelation = createTestRelationInstance(
        'KNOWS',
        'invalid-uuid',
        '550e8400-e29b-41d4-a716-446655440001'
      );

      await assertThrowsError(
        () => validateRelationInstance(invalidRelation, relationTypeDef),
        ValidationError,
        'Relation instance must have valid UUID source_object_instance_id'
      );
    });

    it('should reject relation with invalid target UUID', async () => {
      const invalidRelation = createTestRelationInstance(
        'KNOWS',
        '550e8400-e29b-41d4-a716-446655440000',
        'invalid-uuid'
      );

      await assertThrowsError(
        () => validateRelationInstance(invalidRelation, relationTypeDef),
        ValidationError,
        'Relation instance must have valid UUID target_object_instance_id'
      );
    });

    it('should reject relation with invalid weight', async () => {
      const invalidRelation = {
        ...validRelation,
        weight: new Decimal(15), // Weight > 10
      };

      await assertThrowsError(
        () => validateRelationInstance(invalidRelation, relationTypeDef),
        ValidationError,
        'Relation instance weight must be a Decimal between 0 and 10'
      );
    });

    it('should reject relation with invalid upsert_date', async () => {
      const invalidRelation = {
        ...validRelation,
        upsert_date: 'invalid-date' as any,
      };

      await assertThrowsError(
        () => validateRelationInstance(invalidRelation, relationTypeDef),
        ValidationError,
        'Relation instance upsert_date must be a Date'
      );
    });

    it('should reject relation with invalid property data type', async () => {
      const invalidRelation = createTestRelationInstance(
        'KNOWS',
        '550e8400-e29b-41d4-a716-446655440000',
        '550e8400-e29b-41d4-a716-446655440001',
        { since: 'invalid-date' } // Should be Date
      );

      await assertThrowsError(
        () => validateRelationInstance(invalidRelation, relationTypeDef),
        ValidationError,
        'Invalid ISO date string for DATETIME property'
      );
    });
  });

  describe('Filter Value Validation', () => {
    describe('NULL and UNDEFINED values', () => {
      it('should accept null/undefined with == operator', () => {
        expect(() => validateFilterValue(null, '==')).not.toThrow();
        expect(() => validateFilterValue(undefined as any, '==')).not.toThrow();
        expect(() => validateFilterValue(null, '!=')).not.toThrow();
      });

      it('should reject null/undefined with other operators', async () => {
        await assertThrowsError(
          () => validateFilterValue(null, '>'),
          ValidationError,
          "Null/undefined values not allowed with operator '>'"
        );
      });
    });

    describe('IN and CONTAINS operators', () => {
      it('should accept non-empty arrays', () => {
        expect(() => validateFilterValue([1, 2, 3], 'IN')).not.toThrow();
        expect(() => validateFilterValue(['a', 'b'], 'CONTAINS')).not.toThrow();
      });

      it('should reject non-arrays', async () => {
        await assertThrowsError(
          () => validateFilterValue('not-an-array', 'IN'),
          ValidationError,
          "Operator 'IN' requires an array value"
        );
      });

      it('should reject empty arrays', async () => {
        await assertThrowsError(
          () => validateFilterValue([], 'IN'),
          ValidationError,
          "Operator 'IN' requires a non-empty array"
        );
      });

      it('should reject arrays with null elements', async () => {
        await assertThrowsError(
          () => validateFilterValue([1 as any, null as any, 3 as any], 'IN'),
          ValidationError,
          'Array element at index 1 cannot be null/undefined'
        );
      });
    });

    describe('Pattern operators', () => {
      it('should accept strings with LIKE, STARTSWITH, ENDSWITH', () => {
        expect(() => validateFilterValue('pattern', 'LIKE')).not.toThrow();
        expect(() => validateFilterValue('prefix', 'STARTSWITH')).not.toThrow();
        expect(() => validateFilterValue('suffix', 'ENDSWITH')).not.toThrow();
      });

      it('should reject non-strings with pattern operators', async () => {
        await assertThrowsError(
          () => validateFilterValue(123, 'LIKE'),
          ValidationError,
          "Operator 'LIKE' requires a string value"
        );
      });
    });
  });

  describe('Schema Compliance Validation', () => {
    let consoleWarnSpy: jest.SpyInstance;

    beforeEach(() => {
      consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
    });

    afterEach(() => {
      consoleWarnSpy.mockRestore();
    });

    it('should accept valid schemas', () => {
      const objTypeDef = createTestObjectTypeDefinition('Person', [
        { name: 'id', data_type: PropertyDataType.UUID, is_primary_key: true },
        { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      ]);

      expect(() => validateSchemaCompliance(objTypeDef)).not.toThrow();
    });

    it('should warn about missing primary key', () => {
      const objTypeDef = createTestObjectTypeDefinition('Person', [
        { name: 'name', data_type: PropertyDataType.TEXT },
      ]);

      validateSchemaCompliance(objTypeDef);

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('has no primary key property')
      );
    });

    it('should warn about naming convention violations', () => {
      const objTypeDef: ObjectTypeDefinition = {
        name: 'person', // Should be PascalCase
        properties: [
          { name: 'INVALID_NAME', data_type: PropertyDataType.TEXT }, // Should be camelCase
        ],
      };

      validateSchemaCompliance(objTypeDef);

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('should follow PascalCase convention')
      );
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('should follow snake_case or camelCase convention')
      );
    });
  });

  describe('Batch Validation', () => {
    let objTypeDef: ObjectTypeDefinition;
    let relationTypeDef: RelationTypeDefinition;

    beforeEach(() => {
      objTypeDef = createTestObjectTypeDefinition('Person', [
        { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      ]);

      relationTypeDef = createTestRelationTypeDefinition('KNOWS', 'Person', 'Person', [
        { name: 'strength', data_type: PropertyDataType.FLOAT, is_nullable: true },
      ]);
    });

    describe('validateObjectInstances', () => {
      it('should accept all valid instances', () => {
        const instances = [
          createTestObjectInstance('Person', { name: 'John' }),
          createTestObjectInstance('Person', { name: 'Jane' }),
        ];

        expect(() => validateObjectInstances(instances, objTypeDef)).not.toThrow();
      });

      it('should reject batch with invalid instances', async () => {
        const instances = [
          createTestObjectInstance('Person', { name: 'John' }),
          createTestObjectInstance('Person', { name: 123 as any }), // Invalid
        ];

        await assertThrowsError(
          () => validateObjectInstances(instances, objTypeDef),
          ValidationError,
          'Validation failed for 1 of 2 instances'
        );
      });
    });

    describe('validateRelationInstances', () => {
      it('should accept all valid relation instances', () => {
        const validUUID1 = '550e8400-e29b-41d4-a716-446655440000';
        const validUUID2 = '550e8400-e29b-41d4-a716-446655440001';
        const validUUID3 = '550e8400-e29b-41d4-a716-446655440002';
        const validUUID4 = '550e8400-e29b-41d4-a716-446655440003';

        const instances = [
          {
            id: '550e8400-e29b-41d4-a716-446655440005',
            relation_type_name: 'KNOWS',
            source_object_instance_id: validUUID1,
            target_object_instance_id: validUUID2,
            weight: new Decimal(1.0),
            upsert_date: new Date(),
            properties: { strength: 0.8 },
          },
          {
            id: '550e8400-e29b-41d4-a716-446655440006',
            relation_type_name: 'KNOWS',
            source_object_instance_id: validUUID3,
            target_object_instance_id: validUUID4,
            weight: new Decimal(1.0),
            upsert_date: new Date(),
            properties: { strength: 0.8 },
          },
        ];

        expect(() => validateRelationInstances(instances, relationTypeDef)).not.toThrow();
      });

      it('should reject batch with invalid relation instances', async () => {
        const validUUID1 = '550e8400-e29b-41d4-a716-446655440000';
        const validUUID2 = '550e8400-e29b-41d4-a716-446655440001';

        const instances = [
          // Valid instance
          {
            id: '550e8400-e29b-41d4-a716-446655440005',
            relation_type_name: 'KNOWS',
            source_object_instance_id: validUUID1,
            target_object_instance_id: validUUID2,
            weight: new Decimal(1.0),
            upsert_date: new Date(),
            properties: { strength: 0.8 },
          },
          // Invalid instance with bad UUID
          {
            id: '550e8400-e29b-41d4-a716-446655440006',
            relation_type_name: 'KNOWS',
            source_object_instance_id: 'invalid-uuid', // Invalid UUID
            target_object_instance_id: '550e8400-e29b-41d4-a716-446655440007',
            weight: new Decimal(1.0),
            upsert_date: new Date(),
            properties: { strength: 0.8 },
          },
        ];

        await assertThrowsError(
          () => validateRelationInstances(instances, relationTypeDef),
          ValidationError,
          'Relation validation failed for 1 of 2 instances'
        );
      });
    });
  });
});