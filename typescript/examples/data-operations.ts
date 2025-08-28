/**
 * Data Operations Examples for Grizabella TypeScript API
 *
 * This file demonstrates comprehensive data operations including CRUD operations,
 * batch processing, data validation, and advanced data manipulation patterns.
 */

import {
  GrizabellaClient,
  PropertyDataType,
  Decimal,
  ObjectInstance,
  RelationInstance,
  createObjectInstance,
  createRelationInstance,
  processObjectInstancesBatch,
  createMultipleObjectInstances,
  validateObjectInstance,
  validateRelationInstance,
  timeAsync,
  createMemoryReport,
} from '../src/index';

/**
 * Setup function to create common schema for examples
 */
async function setupSchema(client: GrizabellaClient) {
  // Create Person object type
  await client.createObjectType({
    name: 'Person',
    description: 'A person in the system',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'email', data_type: PropertyDataType.TEXT, is_nullable: false, is_unique: true },
      { name: 'age', data_type: PropertyDataType.INTEGER, is_nullable: true },
      { name: 'department', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'salary', data_type: PropertyDataType.FLOAT, is_nullable: true },
      { name: 'is_active', data_type: PropertyDataType.BOOLEAN, is_nullable: false },
    ],
  });

  // Create Project object type
  await client.createObjectType({
    name: 'Project',
    description: 'A project in the organization',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'description', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'budget', data_type: PropertyDataType.FLOAT, is_nullable: true },
      { name: 'status', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'deadline', data_type: PropertyDataType.DATETIME, is_nullable: true },
    ],
  });

  // Create relation types
  await client.createRelationType({
    name: 'WORKS_ON',
    description: 'Person works on a project',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Project'],
    properties: [
      { name: 'role', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'start_date', data_type: PropertyDataType.DATETIME, is_nullable: true },
      { name: 'hours_per_week', data_type: PropertyDataType.INTEGER, is_nullable: true },
    ],
  });

  console.log('✅ Schema setup completed');
}

/**
 * Example 1: Basic CRUD Operations
 * Shows Create, Read, Update, Delete operations
 */
async function basicCRUDEexample() {
  console.log('=== Basic CRUD Operations Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'crud-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  await setupSchema(client);

  // CREATE: Create a new person
  const person = await client.upsertObject({
    id: 'person-1',
    object_type_name: 'Person',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      name: 'Alice Johnson',
      email: 'alice.johnson@company.com',
      age: 28,
      department: 'Engineering',
      salary: 85000.0,
      is_active: true,
    },
  });

  console.log('✅ Created person:', person.properties.name);

  // READ: Retrieve the person
  const retrievedPerson = await client.getObjectById('person-1', 'Person');
  if (retrievedPerson) {
    console.log('✅ Retrieved person:', retrievedPerson.properties.name);
  }

  // UPDATE: Modify the person's information
  const updatedPerson = await client.upsertObject({
    ...person,
    properties: {
      ...person.properties,
      salary: 90000.0, // Give Alice a raise
      department: 'Senior Engineering', // Promote her
    },
  });

  console.log('✅ Updated person salary:', updatedPerson.properties.salary);

  // CREATE another person
  const person2 = await client.upsertObject({
    id: 'person-2',
    object_type_name: 'Person',
    weight: new Decimal('0.9'),
    upsert_date: new Date(),
    properties: {
      name: 'Bob Smith',
      email: 'bob.smith@company.com',
      age: 32,
      department: 'Engineering',
      salary: 78000.0,
      is_active: true,
    },
  });

  // FIND: Query multiple people
  const engineers = await client.findObjects('Person', {
    department: 'Engineering'
  });

  console.log(`✅ Found ${engineers.length} engineers`);

  // DELETE: Remove a person
  const deleted = await client.deleteObject('person-2', 'Person');
  console.log('✅ Deleted person:', deleted);

  // Verify deletion
  const deletedPerson = await client.getObjectById('person-2', 'Person');
  console.log('✅ Person deleted (null result):', deletedPerson === null);
}

/**
 * Example 2: Batch Operations
 * Shows how to perform operations on multiple objects efficiently
 */
async function batchOperationsExample() {
  console.log('\n=== Batch Operations Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'batch-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  await setupSchema(client);

  // Create multiple people using batch helper
  const peopleData = [
    { name: 'Charlie Brown', email: 'charlie@company.com', age: 25, department: 'Design' },
    { name: 'Diana Prince', email: 'diana@company.com', age: 30, department: 'Marketing' },
    { name: 'Eve Adams', email: 'eve@company.com', age: 27, department: 'Engineering' },
    { name: 'Frank Miller', email: 'frank@company.com', age: 35, department: 'Sales' },
    { name: 'Grace Lee', email: 'grace@company.com', age: 29, department: 'Engineering' },
  ];

  const createdPeople = await createMultipleObjectInstances(
    client,
    'Person',
    peopleData.map((p, index) => ({
      ...p,
      salary: 60000 + (index * 5000), // Varying salaries
      is_active: true,
    }))
  );

  console.log(`✅ Created ${createdPeople.length} people in batch`);

  // Create projects
  const projectsData = [
    { name: 'Website Redesign', description: 'Complete website overhaul', budget: 50000, status: 'active' },
    { name: 'Mobile App', description: 'New mobile application', budget: 75000, status: 'planning' },
    { name: 'Database Migration', description: 'Migrate to new database system', budget: 30000, status: 'completed' },
  ];

  const createdProjects = await createMultipleObjectInstances(client, 'Project', projectsData);
  console.log(`✅ Created ${createdProjects.length} projects in batch`);

  // Batch process: Assign people to projects
  const assignments = [
    { personId: 'person-3', projectId: 'project-1', role: 'Lead Developer' },
    { personId: 'person-5', projectId: 'project-1', role: 'Designer' },
    { personId: 'person-4', projectId: 'project-2', role: 'Project Manager' },
    { personId: 'person-3', projectId: 'project-2', role: 'Developer' },
  ];

  const assignmentRelations = assignments.map((assignment, index) =>
    createRelationInstance({
      id: `assignment-${index + 1}`,
      relation_type_name: 'WORKS_ON',
      source_object_instance_id: assignment.personId,
      target_object_instance_id: assignment.projectId,
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        role: assignment.role,
        start_date: new Date(),
        hours_per_week: 40,
      },
    })
  );

  // Process relations in batch
  for (const relation of assignmentRelations) {
    await client.addRelation(relation);
  }

  console.log(`✅ Created ${assignmentRelations.length} project assignments`);
}

/**
 * Example 3: Data Validation and Error Handling
 * Shows comprehensive data validation and error handling patterns
 */
async function validationAndErrorHandlingExample() {
  console.log('\n=== Data Validation and Error Handling Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'validation-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  await setupSchema(client);

  // Get the Person schema for validation
  const personType = await client.getObjectType('Person');

  // Example 1: Valid object instance
  const validPerson = createObjectInstance('Person', {
    name: 'Valid Person',
    email: 'valid@example.com',
    age: 25,
    is_active: true,
  });

  const validValidation = validateObjectInstance(validPerson, personType!);
  console.log('✅ Valid person validation:', validValidation.isValid);

  // Example 2: Invalid object instance (missing required fields)
  const invalidPerson = createObjectInstance('Person', {
    name: 'Invalid Person',
    email: 'invalid@example.com',
    // Missing required 'is_active' field
  });

  const invalidValidation = validateObjectInstance(invalidPerson, personType!);
  if (!invalidValidation.isValid) {
    console.log('❌ Invalid person validation errors:');
    invalidValidation.errors.forEach(error => console.log(`  - ${error}`));
  }

  // Example 3: Duplicate unique constraint violation
  try {
    await client.upsertObject(validPerson);
    console.log('✅ Created first person with email');

    // Try to create another person with the same email
    const duplicatePerson = createObjectInstance('Person', {
      name: 'Duplicate Person',
      email: 'valid@example.com', // Same email
      is_active: true,
    });

    await client.upsertObject(duplicatePerson);
    console.log('❌ This should have failed due to duplicate email');
  } catch (error) {
    console.log('✅ Caught expected duplicate email error:', error.message);
  }

  // Example 4: Valid relation instance
  const project = await client.upsertObject(createObjectInstance('Project', {
    name: 'Validation Test Project',
    status: 'active',
  }));

  const relation = createRelationInstance({
    id: 'validation-relation-1',
    relation_type_name: 'WORKS_ON',
    source_object_instance_id: validPerson.id,
    target_object_instance_id: project.id,
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      role: 'Developer',
      hours_per_week: 40,
    },
  });

  const relationValidation = validateRelationInstance(relation);
  console.log('✅ Valid relation validation:', relationValidation.isValid);
}

/**
 * Example 4: Performance Monitoring and Optimization
 * Shows how to monitor and optimize data operations
 */
async function performanceExample() {
  console.log('\n=== Performance Monitoring Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'performance-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  await setupSchema(client);

  // Create test data
  const testPeople = Array.from({ length: 100 }, (_, i) => ({
    name: `Test Person ${i}`,
    email: `test${i}@example.com`,
    age: 20 + (i % 50), // Ages 20-69
    department: ['Engineering', 'Sales', 'Marketing', 'Design'][i % 4],
    salary: 50000 + (i * 1000),
    is_active: i % 10 !== 0, // 90% active
  }));

  // Time the batch creation
  const createResult = await timeAsync(
    () => createMultipleObjectInstances(client, 'Person', testPeople),
    'batchCreate'
  );

  console.log(`✅ Created ${createResult.result.length} people in ${createResult.duration}ms`);
  console.log(`📊 Average time per person: ${(createResult.duration / createResult.result.length).toFixed(2)}ms`);

  // Time different query patterns
  const queryPatterns = [
    { name: 'Find all active people', query: () => client.findObjects('Person', { is_active: true }) },
    { name: 'Find engineers', query: () => client.findObjects('Person', { department: 'Engineering' }) },
    { name: 'Find by age range', query: () => client.findObjects('Person', { age: { '>=': 30, '<=': 50 } }) },
    { name: 'Find by complex criteria', query: () => client.findObjects('Person', {
      department: 'Engineering',
      is_active: true,
      age: { '>': 25 }
    })},
  ];

  console.log('\n⏱️ Query Performance Results:');
  for (const pattern of queryPatterns) {
    const result = await timeAsync(pattern.query, pattern.name);
    console.log(`  ${pattern.name}: ${result.result.length} results in ${result.duration}ms`);
  }

  // Memory usage report
  const memoryReport = createMemoryReport();
  console.log('\n🧠 Memory Usage:');
  Object.entries(memoryReport).forEach(([key, value]) => {
    console.log(`  ${key}: ${value}`);
  });
}

/**
 * Example 5: Advanced Data Manipulation
 * Shows complex data operations and transformations
 */
async function advancedManipulationExample() {
  console.log('\n=== Advanced Data Manipulation Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'advanced-example-db',
    serverUrl: 'http://localhost:8000/mcp',
    createIfNotExists: true,
  });

  await setupSchema(client);

  // Create employees with varying data
  const employees = await createMultipleObjectInstances(client, 'Person', [
    { name: 'John Doe', email: 'john@company.com', age: 30, department: 'Engineering', salary: 75000, is_active: true },
    { name: 'Jane Smith', email: 'jane@company.com', age: 28, department: 'Engineering', salary: 72000, is_active: true },
    { name: 'Bob Johnson', email: 'bob@company.com', age: 35, department: 'Sales', salary: 65000, is_active: true },
    { name: 'Alice Brown', email: 'alice@company.com', age: 32, department: 'Marketing', salary: 60000, is_active: true },
    { name: 'Charlie Wilson', email: 'charlie@company.com', age: 26, department: 'Engineering', salary: 68000, is_active: false },
  ]);

  // Create projects
  const projects = await createMultipleObjectInstances(client, 'Project', [
    { name: 'AI Platform', description: 'Next-gen AI platform', budget: 500000, status: 'active', deadline: new Date('2024-12-31') },
    { name: 'Mobile App', description: 'Customer mobile application', budget: 200000, status: 'active', deadline: new Date('2024-06-30') },
    { name: 'Data Migration', description: 'Legacy system migration', budget: 150000, status: 'completed', deadline: new Date('2024-03-15') },
  ]);

  // Batch process: Assign employees to projects based on department
  const assignments = await processObjectInstancesBatch(
    client,
    employees,
    async (employee) => {
      const employeeData = employee.properties;

      // Find suitable projects based on department and availability
      let suitableProject = null;
      if (employeeData.department === 'Engineering') {
        suitableProject = projects.find(p => p.properties.name === 'AI Platform');
      } else if (employeeData.department === 'Sales' || employeeData.department === 'Marketing') {
        suitableProject = projects.find(p => p.properties.name === 'Mobile App');
      }

      if (suitableProject && employeeData.is_active) {
        const relation = createRelationInstance({
          id: `emp-${employee.id}-proj-${suitableProject.id}`,
          relation_type_name: 'WORKS_ON',
          source_object_instance_id: employee.id,
          target_object_instance_id: suitableProject.id,
          weight: new Decimal('1.0'),
          upsert_date: new Date(),
          properties: {
            role: employeeData.department === 'Engineering' ? 'Developer' : 'Specialist',
            start_date: new Date(),
            hours_per_week: 40,
          },
        });

        await client.addRelation(relation);
        return { employee: employeeData.name, project: suitableProject.properties.name };
      }

      return null;
    },
    { batchSize: 5 }
  );

  const successfulAssignments = assignments.filter(a => a !== null);
  console.log(`✅ Created ${successfulAssignments.length} smart assignments`);

  // Query and analyze the assignments
  for (const project of projects) {
    if (project.properties.status === 'active') {
      const relations = await client.getIncomingRelations(project.id, 'Project', 'WORKS_ON');
      console.log(`📊 ${project.properties.name}: ${relations.length} team members`);

      // Calculate team salary cost
      let totalCost = 0;
      for (const relation of relations) {
        const person = await client.getObjectById(relation.source_object_instance_id, 'Person');
        if (person && person.properties.salary) {
          totalCost += person.properties.salary;
        }
      }

      console.log(`💰 Total team cost: $${totalCost.toLocaleString()}`);
    }
  }
}

/**
 * Main function to run all data operations examples
 */
async function main() {
  console.log('💾 Grizabella TypeScript API - Data Operations Examples\n');

  try {
    await basicCRUDEexample();
    await batchOperationsExample();
    await validationAndErrorHandlingExample();
    await performanceExample();
    await advancedManipulationExample();

    console.log('\n✅ All data operations examples completed successfully!');
  } catch (error) {
    console.error('\n❌ Error running examples:', error);
    process.exit(1);
  }
}

export {
  basicCRUDEexample,
  batchOperationsExample,
  validationAndErrorHandlingExample,
  performanceExample,
  advancedManipulationExample,
};