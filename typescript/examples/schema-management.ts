/**
 * Schema Management Examples for Grizabella TypeScript API
 *
 * This file demonstrates basic schema management operations including
 * object type definitions, relation type definitions, and basic schema patterns.
 */

import { GrizabellaClient, PropertyDataType } from '../src/index';
import { Decimal } from 'decimal.js';

/**
 * Example 1: Creating Object Types
 * Shows how to create different types of object schemas
 */
async function createObjectTypesExample() {
  console.log('=== Creating Object Types Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-example-db',
    createIfNotExists: true,
  });

  // Create a simple Person object type
  await client.createObjectType({
    name: 'Person',
    description: 'A person in the system',
    properties: [
      {
        name: 'first_name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        description: 'First name of the person',
      },
      {
        name: 'last_name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        description: 'Last name of the person',
      },
      {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'Unique email address',
      },
      {
        name: 'age',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
        description: 'Age in years',
      },
      {
        name: 'is_active',
        data_type: PropertyDataType.BOOLEAN,
        is_nullable: false,
        description: 'Whether the person is active',
      },
    ],
  });

  console.log('✅ Created Person object type');

  // Create a Product object type with different property types
  await client.createObjectType({
    name: 'Product',
    description: 'A product in inventory',
    properties: [
      {
        name: 'name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_indexed: true,
        description: 'Product name',
      },
      {
        name: 'description',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'Product description',
      },
      {
        name: 'price',
        data_type: PropertyDataType.FLOAT,
        is_nullable: false,
        description: 'Product price',
      },
      {
        name: 'category',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_indexed: true,
        description: 'Product category',
      },
      {
        name: 'in_stock',
        data_type: PropertyDataType.INTEGER,
        is_nullable: false,
        description: 'Number of items in stock',
      },
      {
        name: 'created_date',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'When the product was created',
      },
    ],
  });

  console.log('✅ Created Product object type');

  // Create an Order object type
  await client.createObjectType({
    name: 'Order',
    description: 'A customer order',
    properties: [
      {
        name: 'order_number',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'Unique order number',
      },
      {
        name: 'customer_email',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        description: 'Customer email address',
      },
      {
        name: 'total_amount',
        data_type: PropertyDataType.FLOAT,
        is_nullable: false,
        description: 'Total order amount',
      },
      {
        name: 'status',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        description: 'Order status (pending, shipped, delivered)',
      },
      {
        name: 'order_date',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'When the order was placed',
      },
    ],
  });

  console.log('✅ Created Order object type');
}

/**
 * Example 2: Creating Relation Types
 * Shows how to create relationships between object types
 */
async function createRelationTypesExample() {
  console.log('\n=== Creating Relation Types Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-example-db',
    createIfNotExists: true,
  });

  // Create a simple relation between Person and Product
  await client.createRelationType({
    name: 'OWNS',
    description: 'Person owns a product',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Product'],
    properties: [
      {
        name: 'purchase_date',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'When the product was purchased',
      },
      {
        name: 'purchase_price',
        data_type: PropertyDataType.FLOAT,
        is_nullable: true,
        description: 'Price at time of purchase',
      },
    ],
  });

  console.log('✅ Created OWNS relation type');

  // Create a relation between Person and Order
  await client.createRelationType({
    name: 'PLACED_ORDER',
    description: 'Person placed an order',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Order'],
    properties: [
      {
        name: 'placement_date',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'When the order was placed',
      },
    ],
  });

  console.log('✅ Created PLACED_ORDER relation type');

  // Create a relation between Order and Product
  await client.createRelationType({
    name: 'CONTAINS',
    description: 'Order contains products',
    source_object_type_names: ['Order'],
    target_object_type_names: ['Product'],
    properties: [
      {
        name: 'quantity',
        data_type: PropertyDataType.INTEGER,
        is_nullable: false,
        description: 'Quantity of product in order',
      },
      {
        name: 'unit_price',
        data_type: PropertyDataType.FLOAT,
        is_nullable: false,
        description: 'Price per unit at time of order',
      },
    ],
  });

  console.log('✅ Created CONTAINS relation type');
}

/**
 * Example 3: Managing Schema
 * Shows how to list, retrieve, and delete schema elements
 */
async function manageSchemaExample() {
  console.log('\n=== Managing Schema Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-example-db',
    createIfNotExists: true,
  });

  // List all object types
  const objectTypes = await client.listObjectTypes();
  console.log('✅ Found object types:', objectTypes.map(t => t.name).join(', '));

  // Get a specific object type
  const personType = await client.getObjectType('Person');
  if (personType) {
    console.log('✅ Retrieved Person type with', personType.properties.length, 'properties');
    console.log('   Properties:', personType.properties.map(p => p.name).join(', '));
  }

  // List all relation types
  const relationTypes = await client.listRelationTypes();
  console.log('✅ Found relation types:', relationTypes.map(t => t.name).join(', '));

  // Get a specific relation type
  const ownsRelation = await client.getRelationType('OWNS');
  if (ownsRelation) {
    console.log('✅ Retrieved OWNS relation type');
    console.log('   Source types:', ownsRelation.source_object_type_names.join(', '));
    console.log('   Target types:', ownsRelation.target_object_type_names.join(', '));
  }
}

/**
 * Example 4: Schema Evolution
 * Shows how to handle schema changes and migrations
 */
async function schemaEvolutionExample() {
  console.log('\n=== Schema Evolution Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-evolution-db',
    createIfNotExists: true,
  });

  // Create initial version of User type
  await client.createObjectType({
    name: 'User',
    description: 'A user account',
    properties: [
      {
        name: 'username',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'Unique username',
      },
      {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'Unique email address',
      },
      {
        name: 'created_at',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'Account creation date',
      },
    ],
  });

  console.log('✅ Created initial User type');

  // Create some users with the initial schema
  const user1 = await client.upsertObject({
    id: 'user-1',
    object_type_name: 'User',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      username: 'alice',
      email: 'alice@example.com',
      created_at: new Date('2023-01-01'),
    },
  });

  console.log('✅ Created user with initial schema:', user1.properties.username);

  // Note: In a real scenario, you would need to handle schema migration
  // This example shows the pattern, but actual schema modification
  // would depend on the specific database capabilities

  // For now, let's create a new type that extends the concept
  await client.createObjectType({
    name: 'ExtendedUser',
    description: 'An extended user profile',
    properties: [
      {
        name: 'username',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'Unique username',
      },
      {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'Unique email address',
      },
      {
        name: 'created_at',
        data_type: PropertyDataType.DATETIME,
        is_nullable: false,
        description: 'Account creation date',
      },
      {
        name: 'profile_picture',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'URL to profile picture',
      },
      {
        name: 'bio',
        data_type: PropertyDataType.TEXT,
        is_nullable: true,
        description: 'User biography',
      },
      {
        name: 'is_verified',
        data_type: PropertyDataType.BOOLEAN,
        is_nullable: false,
        description: 'Whether the user is verified',
      },
    ],
  });

  console.log('✅ Created ExtendedUser type with additional properties');

  // Create an extended user
  const extendedUser = await client.upsertObject({
    id: 'extended-user-1',
    object_type_name: 'ExtendedUser',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      username: 'bob',
      email: 'bob@example.com',
      created_at: new Date('2023-02-01'),
      profile_picture: 'https://example.com/bob.jpg',
      bio: 'Software developer who loves TypeScript',
      is_verified: true,
    },
  });

  console.log('✅ Created extended user:', extendedUser.properties.username);
}

// Run all examples
async function main() {
  try {
    await createObjectTypesExample();
    await createRelationTypesExample();
    await manageSchemaExample();
    await schemaEvolutionExample();
    console.log('\n🎉 All schema management examples completed successfully!');
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
  createObjectTypesExample,
  createRelationTypesExample,
  manageSchemaExample,
  schemaEvolutionExample,
};