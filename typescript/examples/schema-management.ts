/**
 * Schema Management Examples for Grizabella TypeScript API
 *
 * This file demonstrates advanced schema management operations including
 * object type definitions, relation type definitions, embedding definitions,
 * and schema validation patterns.
 */

import {
  GrizabellaClient,
  PropertyDataType,
  ObjectTypeDefinition,
  RelationTypeDefinition,
  EmbeddingDefinition,
  validateObjectTypeDefinition,
  validateRelationTypeDefinition,
  validateObjectInstance,
  createObjectType,
  PROPERTY_TEMPLATES,
} from '../src/index';

/**
 * Example 1: Creating Complex Object Types
 * Shows how to create sophisticated object schemas with constraints
 */
async function complexObjectTypesExample() {
  console.log('=== Complex Object Types Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-management-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  // Create a comprehensive Person object type
  const personType: ObjectTypeDefinition = {
    name: 'Person',
    description: 'A detailed person profile with various attributes',
    properties: [
      {
        name: 'first_name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_indexed: true,
        description: 'First name of the person',
      },
      {
        name: 'last_name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_indexed: true,
        description: 'Last name of the person',
      },
      {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        is_indexed: true,
        description: 'Email address (must be unique)',
      },
      {
        name: 'phone',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'Phone number',
      },
      {
        name: 'date_of_birth',
        data_type: PropertyDataType.DATETIME,
        is_nullable: true,
        description: 'Date of birth',
      },
      {
        name: 'age',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
        is_indexed: true,
        description: 'Current age in years',
      },
      {
        name: 'salary',
        data_type: PropertyDataType.FLOAT,
        is_nullable: true,
        description: 'Annual salary',
      },
      {
        name: 'is_active',
        data_type: PropertyDataType.BOOLEAN,
        is_nullable: false,
        description: 'Whether the person is currently active',
      },
      {
        name: 'metadata',
        data_type: PropertyDataType.JSON,
        is_nullable: true,
        description: 'Additional metadata as JSON',
      },
      {
        name: 'profile_picture',
        data_type: PropertyDataType.BLOB,
        is_nullable: true,
        description: 'Profile picture as binary data',
      },
    ],
  };

  // Validate the object type definition before creating
  const validationResult = validateObjectTypeDefinition(personType);
  if (!validationResult.isValid) {
    console.error('Person type validation failed:', validationResult.errors);
    return;
  }

  await client.createObjectType(personType);
  console.log('✅ Created complex Person object type');

  // Create a Company object type
  const companyType: ObjectTypeDefinition = {
    name: 'Company',
    description: 'A business organization',
    properties: [
      {
        name: 'name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        is_indexed: true,
        description: 'Company name',
      },
      {
        name: 'industry',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        is_indexed: true,
        description: 'Industry sector',
      },
      {
        name: 'founded_year',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
        description: 'Year the company was founded',
      },
      {
        name: 'employee_count',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
        description: 'Number of employees',
      },
      {
        name: 'headquarters',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'Headquarters location',
      },
    ],
  };

  await client.createObjectType(companyType);
  console.log('✅ Created Company object type');
}

/**
 * Example 2: Creating Complex Relation Types
 * Shows how to create relationships with properties
 */
async function complexRelationTypesExample() {
  console.log('\n=== Complex Relation Types Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-management-db',
    serverUrl: 'http://localhost:8000/mcp',
  });

  // Employment relationship with detailed properties
  const employmentRelation: RelationTypeDefinition = {
    name: 'WORKS_FOR',
    description: 'Employment relationship between Person and Company',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Company'],
    properties: [
      {
        name: 'job_title',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_indexed: true,
        description: 'Job title or position',
      },
      {
        name: 'department',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'Department within the company',
      },
      {
        name: 'start_date',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        is_indexed: true,
        description: 'Employment start date',
      },
      {
        name: 'end_date',
        data_type: PropertyDataType.DATETIME,
        is_nullable: true,
        description: 'Employment end date (null if current)',
      },
      {
        name: 'salary',
        data_type: PropertyDataType.FLOAT,
        is_nullable: true,
        description: 'Salary for this position',
      },
      {
        name: 'is_manager',
        data_type: PropertyDataType.BOOLEAN,
        is_nullable: false,
        description: 'Whether this is a management position',
      },
    ],
  };

  // Validate relation type definition
  const validationResult = validateRelationTypeDefinition(employmentRelation);
  if (!validationResult.isValid) {
    console.error('Employment relation validation failed:', validationResult.errors);
    return;
  }

  await client.createRelationType(employmentRelation);
  console.log('✅ Created complex WORKS_FOR relation type');

  // Friendship relationship
  const friendshipRelation: RelationTypeDefinition = {
    name: 'IS_FRIENDS_WITH',
    description: 'Friendship relationship between two people',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Person'],
    properties: [
      {
        name: 'friendship_level',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'Level of friendship (close, casual, acquaintance)',
      },
      {
        name: 'met_through',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'How they met (work, school, mutual friends, etc.)',
      },
      {
        name: 'years_known',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
        description: 'Number of years they have known each other',
      },
    ],
  };

  await client.createRelationType(friendshipRelation);
  console.log('✅ Created IS_FRIENDS_WITH relation type');
}

/**
 * Example 3: Embedding Definitions for Semantic Search
 * Shows how to set up embeddings for vector similarity search
 */
async function embeddingDefinitionsExample() {
  console.log('\n=== Embedding Definitions Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-management-db',
    serverUrl: 'http://localhost:8000/mcp',
  });

  // Create embedding for person biographies
  const personBioEmbedding: EmbeddingDefinition = {
    name: 'person_biography_embedding',
    object_type_name: 'Person',
    source_property_name: 'biography', // Assuming we add this property
    embedding_model: 'text-embedding-ada-002',
    dimensions: 1536,
    description: 'Semantic embedding for person biography text',
  };

  await client.createEmbeddingDefinition(personBioEmbedding);
  console.log('✅ Created person biography embedding definition');

  // Create embedding for company descriptions
  const companyDescEmbedding: EmbeddingDefinition = {
    name: 'company_description_embedding',
    object_type_name: 'Company',
    source_property_name: 'description', // Assuming we add this property
    embedding_model: 'text-embedding-ada-002',
    dimensions: 1536,
    description: 'Semantic embedding for company descriptions',
  };

  await client.createEmbeddingDefinition(companyDescEmbedding);
  console.log('✅ Created company description embedding definition');

  // List all embedding definitions
  const embeddings = await client.listEmbeddingDefinitions();
  console.log(`📊 Total embedding definitions: ${embeddings.length}`);

  embeddings.forEach(embedding => {
    console.log(`  - ${embedding.name}: ${embedding.description}`);
  });
}

/**
 * Example 4: Using Helper Functions for Schema Creation
 * Shows how to use utility functions to create schemas more efficiently
 */
async function schemaHelpersExample() {
  console.log('\n=== Schema Helpers Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'helpers-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  // Use createObjectType helper to create a document type
  const documentType = createObjectType({
    name: 'Document',
    description: 'A document with content and metadata',
    properties: [
      {
        name: 'title',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_indexed: true,
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
        name: 'tags',
        data_type: PropertyDataType.JSON,
        is_nullable: true,
      },
      {
        name: 'word_count',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
      },
    ],
  });

  await client.createObjectType(documentType);
  console.log('✅ Created Document object type using helper');

  // Create a project type using property templates
  const projectType = createObjectType({
    name: 'Project',
    description: 'A project with standard properties',
    properties: [
      PROPERTY_TEMPLATES.name, // Predefined name property
      PROPERTY_TEMPLATES.description, // Predefined description property
      {
        name: 'status',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        description: 'Project status (active, completed, on-hold)',
      },
      {
        name: 'budget',
        data_type: PropertyDataType.FLOAT,
        is_nullable: true,
        description: 'Project budget',
      },
      {
        name: 'deadline',
        data_type: PropertyDataType.DATETIME,
        is_nullable: true,
        description: 'Project deadline',
      },
    ],
  });

  await client.createObjectType(projectType);
  console.log('✅ Created Project object type with templates');
}

/**
 * Example 5: Schema Validation and Inspection
 * Shows how to validate schemas and inspect existing definitions
 */
async function schemaValidationExample() {
  console.log('\n=== Schema Validation and Inspection Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-management-db',
    serverUrl: 'http://localhost:8000/mcp',
  });

  // List all object types
  const objectTypes = await client.listObjectTypes();
  console.log(`📋 Object Types (${objectTypes.length}):`);

  objectTypes.forEach(type => {
    console.log(`  • ${type.name}: ${type.description || 'No description'}`);
    console.log(`    Properties: ${type.properties.length}`);
  });

  // List all relation types
  const relationTypes = await client.listRelationTypes();
  console.log(`\n🔗 Relation Types (${relationTypes.length}):`);

  relationTypes.forEach(type => {
    console.log(`  • ${type.name}: ${type.description || 'No description'}`);
    console.log(`    Source: [${type.source_object_type_names.join(', ')}]`);
    console.log(`    Target: [${type.target_object_type_names.join(', ')}]`);
  });

  // Inspect specific object type
  const personType = await client.getObjectType('Person');
  if (personType) {
    console.log('\n👤 Person Type Details:');
    console.log(`  Description: ${personType.description}`);
    console.log('  Properties:');

    personType.properties.forEach(prop => {
      const constraints = [];
      if (prop.is_primary_key) constraints.push('PRIMARY KEY');
      if (prop.is_nullable === false) constraints.push('NOT NULL');
      if (prop.is_unique) constraints.push('UNIQUE');
      if (prop.is_indexed) constraints.push('INDEXED');

      console.log(`    - ${prop.name} (${prop.data_type}) ${constraints.join(', ')}`);
      if (prop.description) {
        console.log(`      └─ ${prop.description}`);
      }
    });
  }

  // Validate an object instance against the schema
  const testPerson = {
    id: 'test-person-123',
    object_type_name: 'Person',
    weight: 1.0,
    upsert_date: new Date(),
    properties: {
      first_name: 'John',
      last_name: 'Doe',
      email: 'john.doe@example.com',
      is_active: true,
      // Missing required fields to test validation
    },
  };

  const instanceValidation = validateObjectInstance(testPerson, personType!);
  if (!instanceValidation.isValid) {
    console.log('\n❌ Instance validation errors:');
    instanceValidation.errors.forEach(error => {
      console.log(`  - ${error}`);
    });
  }
}

/**
 * Main function to run all schema management examples
 */
async function main() {
  console.log('🏗️ Grizabella TypeScript API - Schema Management Examples\n');

  try {
    await complexObjectTypesExample();
    await complexRelationTypesExample();
    await embeddingDefinitionsExample();
    await schemaHelpersExample();
    await schemaValidationExample();

    console.log('\n✅ All schema management examples completed successfully!');
  } catch (error) {
    console.error('\n❌ Error running examples:', error);
    process.exit(1);
  }
}

export {
  complexObjectTypesExample,
  complexRelationTypesExample,
  embeddingDefinitionsExample,
  schemaHelpersExample,
  schemaValidationExample,
};