/**
 * Data Operations Examples for Grizabella TypeScript API
 *
 * This file demonstrates basic data operations including CRUD operations,
 * simple queries, and basic data manipulation patterns.
 */

import { GrizabellaClient, PropertyDataType } from '../src/index';
import { Decimal } from 'decimal.js';

/**
 * Example 1: Basic CRUD Operations
 * Shows how to create, read, update, and delete objects
 */
async function basicCrudExample() {
  console.log('=== Basic CRUD Operations Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'crud-example-db',
    createIfNotExists: true,
  });

  // Create a simple Person object type
  await client.createObjectType({
    name: 'Person',
    description: 'A person in the system',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'email', data_type: PropertyDataType.TEXT, is_nullable: false, is_unique: true },
      { name: 'age', data_type: PropertyDataType.INTEGER, is_nullable: true },
    ],
  });

  // Create a person (Create)
  const person = await client.upsertObject({
    id: 'person-1',
    object_type_name: 'Person',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      name: 'John Doe',
      email: 'john@example.com',
      age: 30,
    },
  });

  console.log('✅ Created person:', person.properties.name);

  // Read the person (Read)
  const retrievedPerson = await client.getObjectById('person-1', 'Person');
  if (retrievedPerson) {
    console.log('✅ Retrieved person:', retrievedPerson.properties.name);
  }

  // Update the person (Update)
  const updatedPerson = await client.upsertObject({
    id: 'person-1',
    object_type_name: 'Person',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      name: 'John Doe',
      email: 'john@example.com',
      age: 31, // Updated age
    },
  });

  console.log('✅ Updated person age to:', updatedPerson.properties.age);

  // Delete the person (Delete)
  const deleted = await client.deleteObject('person-1', 'Person');
  console.log('✅ Deleted person:', deleted);

  // Verify deletion
  const deletedPerson = await client.getObjectById('person-1', 'Person');
  console.log('✅ Person deletion verified:', deletedPerson === null);
}

/**
 * Example 2: Query Operations
 * Shows how to find objects with different criteria
 */
async function queryOperationsExample() {
  console.log('\n=== Query Operations Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'query-example-db',
    createIfNotExists: true,
  });

  // Create Person object type
  await client.createObjectType({
    name: 'Person',
    description: 'A person in the system',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'department', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'age', data_type: PropertyDataType.INTEGER, is_nullable: true },
      { name: 'is_active', data_type: PropertyDataType.BOOLEAN, is_nullable: false },
    ],
  });

  // Create multiple people
  const people = [
    {
      id: 'person-1',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: { name: 'Alice', department: 'Engineering', age: 28, is_active: true },
    },
    {
      id: 'person-2',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: { name: 'Bob', department: 'Engineering', age: 32, is_active: true },
    },
    {
      id: 'person-3',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: { name: 'Charlie', department: 'Sales', age: 35, is_active: false },
    },
  ];

  for (const person of people) {
    await client.upsertObject(person);
  }

  // Find all people
  const allPeople = await client.findObjects('Person');
  console.log('✅ Found all people:', allPeople.length);

  // Find active engineers
  const activeEngineers = await client.findObjects('Person', {
    department: 'Engineering',
    is_active: true,
  });
  console.log('✅ Found active engineers:', activeEngineers.length);

  // Find people older than 30
  const olderPeople = await client.findObjects('Person', {
    age: { '>': 30 },
  });
  console.log('✅ Found people older than 30:', olderPeople.length);
}

/**
 * Example 3: Basic Relations
 * Shows how to create and query relationships
 */
async function basicRelationsExample() {
  console.log('\n=== Basic Relations Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'relations-example-db',
    createIfNotExists: true,
  });

  // Create object types
  await client.createObjectType({
    name: 'Person',
    description: 'A person in the system',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
    ],
  });

  await client.createObjectType({
    name: 'Project',
    description: 'A project in the system',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
    ],
  });

  // Create relation type
  await client.createRelationType({
    name: 'WORKS_ON',
    description: 'Person works on a project',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Project'],
    properties: [
      { name: 'role', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'start_date', data_type: PropertyDataType.DATETIME, is_nullable: true },
    ],
  });

  // Create objects
  const person = await client.upsertObject({
    id: 'person-1',
    object_type_name: 'Person',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: { name: 'Alice' },
  });

  const project = await client.upsertObject({
    id: 'project-1',
    object_type_name: 'Project',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: { name: 'AI Platform' },
  });

  // Create relation
  const relation = await client.addRelation({
    id: 'relation-1',
    relation_type_name: 'WORKS_ON',
    source_object_instance_id: person.id,
    target_object_instance_id: project.id,
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      role: 'Developer',
      start_date: new Date(),
    },
  });

  console.log('✅ Created relation:', relation.properties.role);

  // Query outgoing relations from person
  const outgoingRelations = await client.getOutgoingRelations(person.id, 'Person', 'WORKS_ON');
  console.log('✅ Found outgoing relations:', outgoingRelations.length);

  // Query incoming relations to project
  const incomingRelations = await client.getIncomingRelations(project.id, 'Project', 'WORKS_ON');
  console.log('✅ Found incoming relations:', incomingRelations.length);
}

// Run all examples
async function main() {
  try {
    await basicCrudExample();
    await queryOperationsExample();
    await basicRelationsExample();
    console.log('\n🎉 All data operations examples completed successfully!');
  } catch (error) {
    console.error('❌ Example failed:', error);
    process.exit(1);
  }
}

// Run if this file is executed directly
if (require.main === module) {
  main();
}

export {
  basicCrudExample,
  queryOperationsExample,
  basicRelationsExample,
};