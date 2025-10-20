/**
 * Query and Search Examples for Grizabella TypeScript API
 *
 * This file demonstrates basic querying capabilities including filters,
 * simple searches, and basic query patterns.
 */

import { GrizabellaClient, PropertyDataType } from '../src/index';
import { Decimal } from 'decimal.js';

/**
 * Example 1: Basic Filtering
 * Shows how to use different filter criteria
 */
async function basicFilteringExample() {
  console.log('=== Basic Filtering Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'filtering-example-db',
    createIfNotExists: true,
  });

  // Create Person object type
  await client.createObjectType({
    name: 'Person',
    description: 'A person with detailed profile',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'email', data_type: PropertyDataType.TEXT, is_nullable: false, is_unique: true },
      { name: 'age', data_type: PropertyDataType.INTEGER, is_nullable: true },
      { name: 'department', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'salary', data_type: PropertyDataType.FLOAT, is_nullable: true },
      { name: 'is_active', data_type: PropertyDataType.BOOLEAN, is_nullable: false },
    ],
  });

  // Create test data
  const people = [
    {
      id: 'person-1',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Alice Johnson',
        email: 'alice@example.com',
        age: 28,
        department: 'Engineering',
        salary: 75000,
        is_active: true,
      },
    },
    {
      id: 'person-2',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Bob Smith',
        email: 'bob@example.com',
        age: 32,
        department: 'Engineering',
        salary: 85000,
        is_active: true,
      },
    },
    {
      id: 'person-3',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Charlie Brown',
        email: 'charlie@example.com',
        age: 35,
        department: 'Sales',
        salary: 65000,
        is_active: false,
      },
    },
    {
      id: 'person-4',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Diana Prince',
        email: 'diana@example.com',
        age: 29,
        department: 'Marketing',
        salary: 70000,
        is_active: true,
      },
    },
  ];

  for (const person of people) {
    await client.upsertObject(person);
  }

  // Find all people
  const allPeople = await client.findObjects('Person');
  console.log('✅ Total people:', allPeople.length);

  // Find by department
  const engineers = await client.findObjects('Person', {
    department: 'Engineering',
  });
  console.log('✅ Engineers:', engineers.length);

  // Find active people
  const activePeople = await client.findObjects('Person', {
    is_active: true,
  });
  console.log('✅ Active people:', activePeople.length);

  // Find people older than 30
  const olderPeople = await client.findObjects('Person', {
    age: { '>': 30 },
  });
  console.log('✅ People older than 30:', olderPeople.length);

  // Find people with salary between 70k and 80k
  const midSalaryPeople = await client.findObjects('Person', {
    salary: { '>=': 70000, '<=': 80000 },
  });
  console.log('✅ People with salary 70k-80k:', midSalaryPeople.length);

  // Combine multiple filters
  const activeEngineersOver30 = await client.findObjects('Person', {
    department: 'Engineering',
    is_active: true,
    age: { '>': 30 },
  });
  console.log('✅ Active engineers over 30:', activeEngineersOver30.length);
}

/**
 * Example 2: Relation Queries
 * Shows how to query relationships between objects
 */
async function relationQueriesExample() {
  console.log('\n=== Relation Queries Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'relation-queries-db',
    createIfNotExists: true,
  });

  // Create object types
  await client.createObjectType({
    name: 'Employee',
    description: 'An employee in the company',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'position', data_type: PropertyDataType.TEXT, is_nullable: false },
    ],
  });

  await client.createObjectType({
    name: 'Project',
    description: 'A company project',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'status', data_type: PropertyDataType.TEXT, is_nullable: false },
    ],
  });

  // Create relation type
  await client.createRelationType({
    name: 'ASSIGNED_TO',
    description: 'Employee assigned to project',
    source_object_type_names: ['Employee'],
    target_object_type_names: ['Project'],
    properties: [
      { name: 'role', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'assigned_date', data_type: PropertyDataType.DATETIME, is_nullable: true },
    ],
  });

  // Create employees
  const alice = await client.upsertObject({
    id: 'employee-1',
    object_type_name: 'Employee',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: { name: 'Alice', position: 'Developer' },
  });

  const bob = await client.upsertObject({
    id: 'employee-2',
    object_type_name: 'Employee',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: { name: 'Bob', position: 'Designer' },
  });

  // Create projects
  const webApp = await client.upsertObject({
    id: 'project-1',
    object_type_name: 'Project',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: { name: 'Web Application', status: 'Active' },
  });

  const mobileApp = await client.upsertObject({
    id: 'project-2',
    object_type_name: 'Project',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: { name: 'Mobile Application', status: 'Planning' },
  });

  // Create assignments
  await client.addRelation({
    id: 'assignment-1',
    relation_type_name: 'ASSIGNED_TO',
    source_object_instance_id: alice.id,
    target_object_instance_id: webApp.id,
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      role: 'Lead Developer',
      assigned_date: new Date(),
    },
  });

  await client.addRelation({
    id: 'assignment-2',
    relation_type_name: 'ASSIGNED_TO',
    source_object_instance_id: bob.id,
    target_object_instance_id: webApp.id,
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      role: 'UI Designer',
      assigned_date: new Date(),
    },
  });

  await client.addRelation({
    id: 'assignment-3',
    relation_type_name: 'ASSIGNED_TO',
    source_object_instance_id: alice.id,
    target_object_instance_id: mobileApp.id,
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      role: 'Consultant',
      assigned_date: new Date(),
    },
  });

  // Query outgoing relations (what projects is Alice working on?)
  const aliceProjects = await client.getOutgoingRelations(alice.id, 'Employee', 'ASSIGNED_TO');
  console.log('✅ Alice is assigned to', aliceProjects.length, 'projects');

  // Query incoming relations (who is working on the web app?)
  const webAppTeam = await client.getIncomingRelations(webApp.id, 'Project', 'ASSIGNED_TO');
  console.log('✅ Web app has', webAppTeam.length, 'team members');

  // Query all relations with specific parameters
  const allAssignments = await client.queryRelations({
    relation_type_name: 'ASSIGNED_TO',
  });
  console.log('✅ Total assignments:', allAssignments.length);
}

/**
 * Example 3: Complex Query Patterns
 * Shows more advanced query patterns
 */
async function complexQueryPatternsExample() {
  console.log('\n=== Complex Query Patterns Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'complex-queries-db',
    createIfNotExists: true,
  });

  // Create Product object type
  await client.createObjectType({
    name: 'Product',
    description: 'A product in inventory',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'category', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'price', data_type: PropertyDataType.FLOAT, is_nullable: false },
      { name: 'stock', data_type: PropertyDataType.INTEGER, is_nullable: false },
      { name: 'is_available', data_type: PropertyDataType.BOOLEAN, is_nullable: false },
      { name: 'rating', data_type: PropertyDataType.FLOAT, is_nullable: true },
    ],
  });

  // Create products with different attributes
  const products = [
    {
      id: 'product-1',
      object_type_name: 'Product',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Laptop',
        category: 'Electronics',
        price: 999.99,
        stock: 15,
        is_available: true,
        rating: 4.5,
      },
    },
    {
      id: 'product-2',
      object_type_name: 'Product',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Mouse',
        category: 'Electronics',
        price: 29.99,
        stock: 50,
        is_available: true,
        rating: 4.2,
      },
    },
    {
      id: 'product-3',
      object_type_name: 'Product',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Desk Chair',
        category: 'Furniture',
        price: 199.99,
        stock: 0,
        is_available: false,
        rating: 3.8,
      },
    },
    {
      id: 'product-4',
      object_type_name: 'Product',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        name: 'Coffee Maker',
        category: 'Appliances',
        price: 79.99,
        stock: 8,
        is_available: true,
        rating: 4.7,
      },
    },
  ];

  for (const product of products) {
    await client.upsertObject(product);
  }

  // Find products by category
  const electronics = await client.findObjects('Product', {
    category: 'Electronics',
  });
  console.log('✅ Electronics products:', electronics.length);

  // Find available products with stock
  const availableInStock = await client.findObjects('Product', {
    is_available: true,
    stock: { '>': 0 },
  });
  console.log('✅ Available products in stock:', availableInStock.length);

  // Find highly rated products (4.0+)
  const highlyRated = await client.findObjects('Product', {
    rating: { '>=': 4.0 },
  });
  console.log('✅ Highly rated products:', highlyRated.length);

  // Find products in specific price range
  const midRangeProducts = await client.findObjects('Product', {
    price: { '>=': 50, '<=': 200 },
  });
  console.log('✅ Mid-range products ($50-$200):', midRangeProducts.length);

  // Complex query: available electronics with good ratings
  const availableGoodElectronics = await client.findObjects('Product', {
    category: 'Electronics',
    is_available: true,
    rating: { '>=': 4.0 },
  });
  console.log('✅ Available electronics with good ratings:', availableGoodElectronics.length);
}

// Run all examples
async function main() {
  try {
    await basicFilteringExample();
    await relationQueriesExample();
    await complexQueryPatternsExample();
    console.log('\n🎉 All query and search examples completed successfully!');
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
  basicFilteringExample,
  relationQueriesExample,
  complexQueryPatternsExample,
};