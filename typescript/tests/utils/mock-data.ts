/**
 * Mock data generators for testing
 *
 * This module provides pre-defined mock data and generators for common test scenarios,
 * helping to create consistent and realistic test data across different test suites.
 */

import type {
  ObjectTypeDefinition,
  ObjectInstance,
  RelationTypeDefinition,
  RelationInstance,
  EmbeddingDefinition,
} from '../../src/types/core';
import { PropertyDataType } from '../../src/types/enums';
import {
  createTestObjectTypeDefinition,
  createTestObjectInstance,
  createTestRelationTypeDefinition,
  createTestRelationInstance,
  createTestEmbeddingDefinition,
  createTestDecimal,
} from './test-helpers';

// ===== PRE-DEFINED MOCK DATA =====

/**
 * Mock person object type for testing
 */
export const mockPersonType: ObjectTypeDefinition = createTestObjectTypeDefinition('Person', [
  {
    name: 'name',
    data_type: PropertyDataType.TEXT,
    is_nullable: false,
    is_unique: true,
  },
  {
    name: 'email',
    data_type: PropertyDataType.TEXT,
    is_nullable: false,
    is_unique: true,
  },
  {
    name: 'age',
    data_type: PropertyDataType.INTEGER,
    is_nullable: true,
  },
  {
    name: 'bio',
    data_type: PropertyDataType.TEXT,
    is_nullable: true,
  },
]);

/**
 * Mock document object type for testing
 */
export const mockDocumentType: ObjectTypeDefinition = createTestObjectTypeDefinition('Document', [
  {
    name: 'title',
    data_type: PropertyDataType.TEXT,
    is_nullable: false,
  },
  {
    name: 'content',
    data_type: PropertyDataType.TEXT,
    is_nullable: false,
  },
  {
    name: 'author',
    data_type: PropertyDataType.TEXT,
    is_nullable: true,
  },
  {
    name: 'published_date',
    data_type: PropertyDataType.DATETIME,
    is_nullable: true,
  },
]);

/**
 * Mock organization object type for testing
 */
export const mockOrganizationType: ObjectTypeDefinition = createTestObjectTypeDefinition('Organization', [
  {
    name: 'name',
    data_type: PropertyDataType.TEXT,
    is_nullable: false,
    is_unique: true,
  },
  {
    name: 'industry',
    data_type: PropertyDataType.TEXT,
    is_nullable: true,
  },
  {
    name: 'founded_date',
    data_type: PropertyDataType.DATETIME,
    is_nullable: true,
  },
]);

/**
 * Mock relation types for testing
 */
export const mockKnowsRelation: RelationTypeDefinition = createTestRelationTypeDefinition(
  'KNOWS',
  'Person',
  'Person',
  [
    {
      name: 'since',
      data_type: PropertyDataType.DATETIME,
      is_nullable: true,
    },
    {
      name: 'strength',
      data_type: PropertyDataType.FLOAT,
      is_nullable: true,
    },
  ]
);

export const mockWorksForRelation: RelationTypeDefinition = createTestRelationTypeDefinition(
  'WORKS_FOR',
  'Person',
  'Organization',
  [
    {
      name: 'title',
      data_type: PropertyDataType.TEXT,
      is_nullable: true,
    },
    {
      name: 'start_date',
      data_type: PropertyDataType.DATETIME,
      is_nullable: true,
    },
    {
      name: 'salary',
      data_type: PropertyDataType.FLOAT,
      is_nullable: true,
    },
  ]
);

export const mockAuthoredRelation: RelationTypeDefinition = createTestRelationTypeDefinition(
  'AUTHORED',
  'Person',
  'Document',
  [
    {
      name: 'contribution',
      data_type: PropertyDataType.FLOAT,
      is_nullable: true,
    },
  ]
);

// ===== MOCK OBJECT INSTANCES =====

/**
 * Mock person instances
 */
export const mockPersonInstances: ObjectInstance[] = [
  createTestObjectInstance('Person', {
    name: 'John Doe',
    email: 'john@example.com',
    age: 30,
    bio: 'Software engineer with 5 years of experience in web development.',
  }, { id: 'john-doe-123' }),

  createTestObjectInstance('Person', {
    name: 'Jane Smith',
    email: 'jane@example.com',
    age: 28,
    bio: 'Data scientist specializing in machine learning and AI.',
  }, { id: 'jane-smith-456' }),

  createTestObjectInstance('Person', {
    name: 'Bob Johnson',
    email: 'bob@example.com',
    age: 35,
    bio: 'Product manager with expertise in user experience design.',
  }, { id: 'bob-johnson-789' }),
];

/**
 * Mock organization instances
 */
export const mockOrganizationInstances: ObjectInstance[] = [
  createTestObjectInstance('Organization', {
    name: 'Tech Corp',
    industry: 'Technology',
    founded_date: new Date('2015-01-15'),
  }, { id: 'tech-corp-123' }),

  createTestObjectInstance('Organization', {
    name: 'Data Solutions Inc',
    industry: 'Data Analytics',
    founded_date: new Date('2018-06-20'),
  }, { id: 'data-solutions-456' }),
];

/**
 * Mock document instances
 */
export const mockDocumentInstances: ObjectInstance[] = [
  createTestObjectInstance('Document', {
    title: 'Introduction to TypeScript',
    content: 'TypeScript is a superset of JavaScript that adds static typing...',
    author: 'John Doe',
    published_date: new Date('2023-01-15'),
  }, { id: 'doc-typescript-123' }),

  createTestObjectInstance('Document', {
    title: 'Machine Learning Fundamentals',
    content: 'Machine learning is a subset of AI that enables systems to learn...',
    author: 'Jane Smith',
    published_date: new Date('2023-03-20'),
  }, { id: 'doc-ml-456' }),
];

// ===== MOCK RELATION INSTANCES =====

/**
 * Mock relation instances
 */
export const mockRelationInstances: RelationInstance[] = [
  // John knows Jane
  createTestRelationInstance(
    'KNOWS',
    'john-doe-123',
    'jane-smith-456',
    {
      since: new Date('2020-05-10'),
      strength: createTestDecimal(0.9),
    },
    { id: 'john-jane-123' }
  ),

  // John works for Tech Corp
  createTestRelationInstance(
    'WORKS_FOR',
    'john-doe-123',
    'tech-corp-123',
    {
      title: 'Senior Software Engineer',
      start_date: new Date('2022-01-15'),
      salary: createTestDecimal(95000),
    },
    { id: 'john-techcorp-456' }
  ),

  // Jane works for Data Solutions
  createTestRelationInstance(
    'WORKS_FOR',
    'jane-smith-456',
    'data-solutions-456',
    {
      title: 'Data Scientist',
      start_date: new Date('2021-03-01'),
      salary: createTestDecimal(88000),
    },
    { id: 'jane-datasolutions-789' }
  ),

  // John authored the TypeScript document
  createTestRelationInstance(
    'AUTHORED',
    'john-doe-123',
    'doc-typescript-123',
    {
      contribution: createTestDecimal(1.0),
    },
    { id: 'john-authored-typescript-123' }
  ),

  // Jane authored the ML document
  createTestRelationInstance(
    'AUTHORED',
    'jane-smith-456',
    'doc-ml-456',
    {
      contribution: createTestDecimal(1.0),
    },
    { id: 'jane-authored-ml-456' }
  ),
];

// ===== MOCK EMBEDDING DEFINITIONS =====

/**
 * Mock embedding definitions
 */
export const mockPersonBioEmbedding: EmbeddingDefinition = createTestEmbeddingDefinition(
  'person_bio_embedding',
  'Person',
  'bio'
);

export const mockDocumentContentEmbedding: EmbeddingDefinition = createTestEmbeddingDefinition(
  'document_content_embedding',
  'Document',
  'content'
);

// ===== MOCK COMPLEX QUERIES =====

/**
 * Mock complex query for finding friends of friends
 */
export const mockTestData = {
  description: 'Test data for unit tests',
  person: mockPersonInstances[2], // Bob Johnson
};

// ===== UTILITY FUNCTIONS =====

/**
 * Get all mock object types
 */
export function getAllMockObjectTypes(): ObjectTypeDefinition[] {
  return [mockPersonType, mockDocumentType, mockOrganizationType];
}

/**
 * Get all mock relation types
 */
export function getAllMockRelationTypes(): RelationTypeDefinition[] {
  return [mockKnowsRelation, mockWorksForRelation, mockAuthoredRelation];
}

/**
 * Get all mock object instances
 */
export function getAllMockObjectInstances(): ObjectInstance[] {
  return [
    ...mockPersonInstances,
    ...mockOrganizationInstances,
    ...mockDocumentInstances,
  ];
}

/**
 * Get all mock relation instances
 */
export function getAllMockRelationInstances(): RelationInstance[] {
  return mockRelationInstances;
}

/**
 * Get all mock embedding definitions
 */
export function getAllMockEmbeddingDefinitions(): EmbeddingDefinition[] {
  return [mockPersonBioEmbedding, mockDocumentContentEmbedding];
}

/**
 * Create a complete test dataset
 */
export function createCompleteTestDataset() {
  return {
    objectTypes: getAllMockObjectTypes(),
    relationTypes: getAllMockRelationTypes(),
    objectInstances: getAllMockObjectInstances(),
    relationInstances: getAllMockRelationInstances(),
    embeddingDefinitions: getAllMockEmbeddingDefinitions(),
  };
}