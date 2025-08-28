/**
 * Query and Search Examples for Grizabella TypeScript API
 *
 * This file demonstrates advanced querying capabilities including complex filters,
 * graph traversals, semantic search, similarity matching, and query optimization.
 */

import {
  GrizabellaClient,
  PropertyDataType,
  Decimal,
  ComplexQuery,
  ObjectInstance,
  createObjectInstance,
  createMultipleObjectInstances,
  timeAsync,
} from '../src/index';

/**
 * Setup function to create comprehensive test data
 */
async function setupTestData(client: GrizabellaClient) {
  // Create object types
  await client.createObjectType({
    name: 'Person',
    description: 'A person with detailed profile',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false, is_indexed: true },
      { name: 'email', data_type: PropertyDataType.TEXT, is_nullable: false, is_unique: true },
      { name: 'age', data_type: PropertyDataType.INTEGER, is_nullable: true },
      { name: 'department', data_type: PropertyDataType.TEXT, is_nullable: true, is_indexed: true },
      { name: 'biography', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'skills', data_type: PropertyDataType.JSON, is_nullable: true },
    ],
  });

  await client.createObjectType({
    name: 'Project',
    description: 'A project with description and metadata',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false, is_indexed: true },
      { name: 'description', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'budget', data_type: PropertyDataType.FLOAT, is_nullable: true },
      { name: 'status', data_type: PropertyDataType.TEXT, is_nullable: false },
      { name: 'tags', data_type: PropertyDataType.JSON, is_nullable: true },
    ],
  });

  await client.createObjectType({
    name: 'Technology',
    description: 'A technology or programming language',
    properties: [
      { name: 'name', data_type: PropertyDataType.TEXT, is_nullable: false, is_unique: true },
      { name: 'category', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'description', data_type: PropertyDataType.TEXT, is_nullable: true },
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
      { name: 'contribution_percentage', data_type: PropertyDataType.FLOAT, is_nullable: true },
    ],
  });

  await client.createRelationType({
    name: 'KNOWS',
    description: 'Person knows another person',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Person'],
    properties: [
      { name: 'strength', data_type: PropertyDataType.TEXT, is_nullable: true },
    ],
  });

  await client.createRelationType({
    name: 'USES_TECHNOLOGY',
    description: 'Person uses a technology',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Technology'],
    properties: [
      { name: 'proficiency_level', data_type: PropertyDataType.TEXT, is_nullable: true },
      { name: 'years_experience', data_type: PropertyDataType.INTEGER, is_nullable: true },
    ],
  });

  console.log('✅ Test schema created');

  // Create sample data
  const people = await createMultipleObjectInstances(client, 'Person', [
    {
      name: 'Alice Johnson',
      email: 'alice@company.com',
      age: 30,
      department: 'Engineering',
      biography: 'Senior software engineer with expertise in machine learning and distributed systems. Passionate about scalable architectures.',
      skills: ['Python', 'Machine Learning', 'Kubernetes', 'AWS']
    },
    {
      name: 'Bob Smith',
      email: 'bob@company.com',
      age: 28,
      department: 'Engineering',
      biography: 'Full-stack developer specializing in React and Node.js. Experience in building user-facing applications.',
      skills: ['JavaScript', 'React', 'Node.js', 'PostgreSQL']
    },
    {
      name: 'Charlie Brown',
      email: 'charlie@company.com',
      age: 35,
      department: 'Data Science',
      biography: 'Data scientist with background in statistics and machine learning. Expert in Python data analysis libraries.',
      skills: ['Python', 'R', 'TensorFlow', 'Pandas']
    },
    {
      name: 'Diana Prince',
      email: 'diana@company.com',
      age: 32,
      department: 'Engineering',
      biography: 'DevOps engineer focused on cloud infrastructure and automation. AWS certified solutions architect.',
      skills: ['AWS', 'Docker', 'Kubernetes', 'Terraform']
    },
    {
      name: 'Eve Adams',
      email: 'eve@company.com',
      age: 26,
      department: 'Engineering',
      biography: 'Frontend developer with expertise in modern JavaScript frameworks and design systems.',
      skills: ['TypeScript', 'React', 'CSS', 'Figma']
    },
  ]);

  const projects = await createMultipleObjectInstances(client, 'Project', [
    {
      name: 'AI Recommendation Engine',
      description: 'Machine learning-powered recommendation system for e-commerce platform',
      budget: 150000,
      status: 'active',
      tags: ['AI', 'Machine Learning', 'E-commerce']
    },
    {
      name: 'Customer Portal',
      description: 'Modern web application for customer self-service and account management',
      budget: 200000,
      status: 'active',
      tags: ['Web Development', 'React', 'Node.js']
    },
    {
      name: 'Data Analytics Platform',
      description: 'Real-time data analytics and visualization platform for business intelligence',
      budget: 300000,
      status: 'planning',
      tags: ['Data Science', 'Analytics', 'Visualization']
    },
  ]);

  const technologies = await createMultipleObjectInstances(client, 'Technology', [
    { name: 'Python', category: 'Programming Language', description: 'Versatile programming language for data science and web development' },
    { name: 'JavaScript', category: 'Programming Language', description: 'Dynamic programming language for web development' },
    { name: 'React', category: 'Framework', description: 'JavaScript library for building user interfaces' },
    { name: 'AWS', category: 'Cloud Platform', description: 'Amazon Web Services cloud computing platform' },
    { name: 'Kubernetes', category: 'Container Orchestration', description: 'Container orchestration platform for automating deployment' },
  ]);

  // Create relationships
  const relations = [
    // Alice works on AI project as lead
    { from: people[0].id, to: projects[0].id, type: 'WORKS_ON', role: 'Lead Engineer', contribution: 100 },
    // Bob works on Customer Portal
    { from: people[1].id, to: projects[1].id, type: 'WORKS_ON', role: 'Full Stack Developer', contribution: 100 },
    // Charlie works on both AI and Analytics
    { from: people[2].id, to: projects[0].id, type: 'WORKS_ON', role: 'Data Scientist', contribution: 60 },
    { from: people[2].id, to: projects[2].id, type: 'WORKS_ON', role: 'Lead Data Scientist', contribution: 40 },
    // Diana works on Customer Portal
    { from: people[3].id, to: projects[1].id, type: 'WORKS_ON', role: 'DevOps Engineer', contribution: 100 },
    // Eve works on Customer Portal
    { from: people[4].id, to: projects[1].id, type: 'WORKS_ON', role: 'Frontend Developer', contribution: 100 },

    // Friendships
    { from: people[0].id, to: people[1].id, type: 'KNOWS', strength: 'close' },
    { from: people[1].id, to: people[2].id, type: 'KNOWS', strength: 'professional' },
    { from: people[2].id, to: people[3].id, type: 'KNOWS', strength: 'close' },

    // Technology skills (simplified - each person knows some technologies)
    { from: people[0].id, to: technologies[0].id, type: 'USES_TECHNOLOGY', level: 'expert', years: 8 },
    { from: people[0].id, to: technologies[4].id, type: 'USES_TECHNOLOGY', level: 'advanced', years: 5 },
    { from: people[1].id, to: technologies[1].id, type: 'USES_TECHNOLOGY', level: 'expert', years: 6 },
    { from: people[1].id, to: technologies[2].id, type: 'USES_TECHNOLOGY', level: 'expert', years: 4 },
    { from: people[2].id, to: technologies[0].id, type: 'USES_TECHNOLOGY', level: 'expert', years: 10 },
    { from: people[3].id, to: technologies[3].id, type: 'USES_TECHNOLOGY', level: 'expert', years: 7 },
    { from: people[3].id, to: technologies[4].id, type: 'USES_TECHNOLOGY', level: 'advanced', years: 4 },
  ];

  for (const relation of relations) {
    const relationInstance = {
      id: `rel-${relation.from}-${relation.to}-${relation.type}`,
      relation_type_name: relation.type,
      source_object_instance_id: relation.from,
      target_object_instance_id: relation.to,
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {},
    };

    if (relation.role) relationInstance.properties.role = relation.role;
    if (relation.contribution) relationInstance.properties.contribution_percentage = relation.contribution;
    if (relation.strength) relationInstance.properties.strength = relation.strength;
    if (relation.level) relationInstance.properties.proficiency_level = relation.level;
    if (relation.years) relationInstance.properties.years_experience = relation.years;

    await client.addRelation(relationInstance);
  }

  console.log('✅ Test data created');
  return { people, projects, technologies };
}

/**
 * Example 1: Basic and Advanced Filtering
 * Shows various filtering techniques and query patterns
 */
async function basicAndAdvancedFilteringExample() {
  console.log('=== Basic and Advanced Filtering Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'query-example-db',

    createIfNotExists: true,
  });

  const { people } = await setupTestData(client);

  // Basic equality filter
  const engineers = await client.findObjects('Person', { department: 'Engineering' });
  console.log(`✅ Found ${engineers.length} engineers`);

  // Range filter
  const adults = await client.findObjects('Person', { age: { '>': 25, '<=': 35 } });
  console.log(`✅ Found ${adults.length} people aged 26-35`);

  // Multiple conditions with AND logic
  const seniorEngineers = await client.findObjects('Person', {
    department: 'Engineering',
    age: { '>': 28 }
  });
  console.log(`✅ Found ${seniorEngineers.length} senior engineers`);

  // Text pattern matching (if supported)
  try {
    const johns = await client.findObjects('Person', { name: { 'LIKE': 'John%' } });
    console.log(`✅ Found ${johns.length} people whose name starts with "John"`);
  } catch (error) {
    console.log('ℹ️ LIKE operator not supported in this implementation');
  }

  // Complex nested queries
  const complexResults = await client.findObjects('Person', {
    department: 'Engineering',
    age: { '>': 25 },
    // Note: This would be more complex in a real implementation
  });

  console.log(`✅ Complex query found ${complexResults.length} results`);

  // Limit results
  const limitedResults = await client.findObjects('Person', {}, 3);
  console.log(`✅ Limited query returned ${limitedResults.length} results`);
}

/**
 * Example 2: Relationship Queries
 * Shows how to query and traverse relationships
 */
async function relationshipQueriesExample() {
  console.log('\n=== Relationship Queries Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'relationship-example-db',

    createIfNotExists: true,
  });

  const { people, projects } = await setupTestData(client);

  // Get outgoing relations (who is Alice connected to?)
  const aliceRelations = await client.getOutgoingRelations(people[0].id, 'Person');
  console.log(`✅ Alice has ${aliceRelations.length} outgoing relations`);

  // Get incoming relations (who is connected to Alice?)
  const aliceIncoming = await client.getIncomingRelations(people[0].id, 'Person');
  console.log(`✅ Alice has ${aliceIncoming.length} incoming relations`);

  // Get specific relation types
  const aliceFriendships = await client.getOutgoingRelations(people[0].id, 'Person', 'KNOWS');
  console.log(`✅ Alice has ${aliceFriendships.length} friendships`);

  // Get project team members
  const aiProject = projects.find(p => p.properties.name === 'AI Recommendation Engine');
  if (aiProject) {
    const teamMembers = await client.getIncomingRelations(aiProject.id, 'Project', 'WORKS_ON');
    console.log(`✅ AI project has ${teamMembers.length} team members`);

    // Get detailed team information
    for (const relation of teamMembers) {
      const person = await client.getObjectById(relation.source_object_instance_id, 'Person');
      const role = relation.properties.role || 'Unknown role';
      console.log(`  - ${person?.properties.name}: ${role}`);
    }
  }

  // Find mutual connections (people who know people Alice knows)
  const aliceFriends = await client.getOutgoingRelations(people[0].id, 'Person', 'KNOWS');
  for (const friendship of aliceFriends) {
    const friend = await client.getObjectById(friendship.target_object_instance_id, 'Person');
    if (friend) {
      const friendsFriends = await client.getOutgoingRelations(friend.id, 'Person', 'KNOWS');
      console.log(`✅ ${friend.properties.name} has ${friendsFriends.length} friends`);
    }
  }
}

/**
 * Example 3: Complex Graph Queries
 * Shows advanced graph traversal and complex query patterns
 */
async function complexGraphQueriesExample() {
  console.log('\n=== Complex Graph Queries Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'complex-query-example-db',

    createIfNotExists: true,
  });

  const { people, projects } = await setupTestData(client);

  // Query: Find people who work on projects with budget > $100k
  const highBudgetProjects = await client.findObjects('Project', { budget: { '>': 100000 } });
  console.log(`✅ Found ${highBudgetProjects.length} high-budget projects`);

  // For each high-budget project, find team members
  for (const project of highBudgetProjects) {
    const teamRelations = await client.getIncomingRelations(project.id, 'Project', 'WORKS_ON');
    const teamMembers = await Promise.all(
      teamRelations.map(rel =>
        client.getObjectById(rel.source_object_instance_id, 'Person')
      )
    );

    const validMembers = teamMembers.filter(member => member !== null);
    console.log(`📊 ${project.properties.name} ($${project.properties.budget}): ${validMembers.length} team members`);
  }

  // Complex query: Find people who know someone who works on AI projects
  const aiProject = projects.find(p => p.properties.name === 'AI Recommendation Engine');
  if (aiProject) {
    const aiTeam = await client.getIncomingRelations(aiProject.id, 'Project', 'WORKS_ON');
    const aiTeamIds = aiTeam.map(rel => rel.source_object_instance_id);

    // Find friends of AI team members
    for (const teamMemberId of aiTeamIds) {
      const friends = await client.getOutgoingRelations(teamMemberId, 'Person', 'KNOWS');
      if (friends.length > 0) {
        const teamMember = await client.getObjectById(teamMemberId, 'Person');
        console.log(`👥 ${teamMember?.properties.name} has ${friends.length} friends`);
      }
    }
  }
}

/**
 * Example 4: Semantic Search and Similarity
 * Shows vector similarity search capabilities
 */
async function semanticSearchExample() {
  console.log('\n=== Semantic Search Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'semantic-example-db',

    createIfNotExists: true,
  });

  const { people } = await setupTestData(client);

  // Create embedding definition for person biographies
  await client.createEmbeddingDefinition({
    name: 'person_biography_embedding',
    object_type_name: 'Person',
    source_property_name: 'biography',
    embedding_model: 'text-embedding-ada-002',
    dimensions: 1536,
    description: 'Semantic embedding for person biography text',
  });

  console.log('✅ Created embedding definition');

  try {
    // Find people similar to a machine learning expert
    const mlQuery = 'expert in machine learning and artificial intelligence with Python skills';
    const similarPeople = await client.findSimilar(
      'person_biography_embedding',
      mlQuery,
      5
    );

    console.log(`🎯 Found ${similarPeople.length} people similar to ML expert query:`);
    similarPeople.forEach((result, index) => {
      console.log(`  ${index + 1}. ${result.object.properties.name} (score: ${result.score.toFixed(3)})`);
    });

    // Find similar objects to a specific person
    const alice = people.find(p => p.properties.name === 'Alice Johnson');
    if (alice) {
      const similarToAlice = await client.searchSimilarObjects(alice.id, 'Person', 3);
      console.log(`\n👤 People similar to Alice Johnson:`);

      for (const [person, score] of similarToAlice) {
        console.log(`  - ${person.properties.name} (similarity: ${score.toFixed(3)})`);
      }
    }

  } catch (error) {
    console.log('ℹ️ Semantic search not fully implemented in this example environment');
    console.log('   Error:', error.message);
  }
}

/**
 * Example 5: Query Performance and Optimization
 * Shows performance monitoring and query optimization techniques
 */
async function performanceOptimizationExample() {
  console.log('\n=== Query Performance and Optimization Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'performance-example-db',

    createIfNotExists: true,
  });

  await setupTestData(client);

  // Performance comparison of different query types
  const queries = [
    {
      name: 'Find all people',
      query: () => client.findObjects('Person'),
    },
    {
      name: 'Find engineers',
      query: () => client.findObjects('Person', { department: 'Engineering' }),
    },
    {
      name: 'Find by age range',
      query: () => client.findObjects('Person', { age: { '>': 25, '<': 35 } }),
    },
    {
      name: 'Complex multi-condition',
      query: () => client.findObjects('Person', {
        department: 'Engineering',
        age: { '>': 25 },
      }),
    },
  ];

  console.log('⏱️ Query Performance Comparison:');
  for (const querySpec of queries) {
    const result = await timeAsync(querySpec.query, querySpec.name);
    const avgTime = result.duration / Math.max(result.result.length, 1);
    console.log(`  ${querySpec.name}:`);
    console.log(`    Results: ${result.result.length}`);
    console.log(`    Total time: ${result.duration}ms`);
    console.log(`    Avg per result: ${avgTime.toFixed(2)}ms`);
  }

  // Relationship query performance
  const relationQueries = [
    {
      name: 'Get all relations from one person',
      query: async () => {
        const people = await client.findObjects('Person');
        if (people.length > 0) {
          return client.getOutgoingRelations(people[0].id, 'Person');
        }
        return [];
      },
    },
    {
      name: 'Get specific relation type',
      query: async () => {
        const people = await client.findObjects('Person');
        if (people.length > 0) {
          return client.getOutgoingRelations(people[0].id, 'Person', 'KNOWS');
        }
        return [];
      },
    },
  ];

  console.log('\n🔗 Relationship Query Performance:');
  for (const querySpec of relationQueries) {
    const result = await timeAsync(querySpec.query, querySpec.name);
    console.log(`  ${querySpec.name}: ${result.result.length} results in ${result.duration}ms`);
  }
}

/**
 * Main function to run all query and search examples
 */
async function main() {
  console.log('🔍 Grizabella TypeScript API - Query and Search Examples\n');

  try {
    await basicAndAdvancedFilteringExample();
    await relationshipQueriesExample();
    await complexGraphQueriesExample();
    await semanticSearchExample();
    await performanceOptimizationExample();

    console.log('\n✅ All query and search examples completed successfully!');
  } catch (error) {
    console.error('\n❌ Error running examples:', error);
    process.exit(1);
  }
}

export {
  basicAndAdvancedFilteringExample,
  relationshipQueriesExample,
  complexGraphQueriesExample,
  semanticSearchExample,
  performanceOptimizationExample,
};