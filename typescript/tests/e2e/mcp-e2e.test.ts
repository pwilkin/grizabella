import { describe, test, beforeAll, beforeEach, afterEach } from '@jest/globals';
import { v4 as uuidv4 } from 'uuid';
import * as fs from 'fs';
import * as path from 'path';
import { Decimal } from 'decimal.js';
import { MCPClient } from '../../src/client/MCPClient';
import {
  PropertyDataType,
  LogicalOperator,
  RelationalOperator,
  GraphTraversalDirection,
} from '../../src/types/enums';
import {
  ObjectTypeDefinition,
  RelationTypeDefinition,
  ObjectInstance,
  EmbeddingDefinition,
  EmbeddingVector,
  ComplexQuery,
  QueryComponent,
  EmbeddingSearchClause,
  QueryResult,
  LogicalGroup,
  NotClause,
} from '../../src/types';

describe('Grizabella TypeScript MCP API - End-to-End Scenario', () => {
  console.log('=== MCP TEST FILE LOADED ===');
  let client: MCPClient;
  let tempDir: string;
  const ids: Record<string, string> = {};

  // Fixed UUID for predictable entity
  const fixedPaperId4 = '550e8400-e29b-41d4-a716-446655440000';

  beforeAll(() => {
    // Generate predictable IDs for test isolation
    ids['author_1'] = uuidv4();
    ids['author_2'] = uuidv4();
    ids['author_3'] = uuidv4();
    ids['venue_1'] = uuidv4();
    ids['venue_2'] = uuidv4();
    ids['paper_1'] = uuidv4();
    ids['paper_2'] = uuidv4();
    ids['paper_3'] = uuidv4();
    ids['paper_4'] = fixedPaperId4;
    ids['temp_query_obj_paper'] = uuidv4();
  });

  beforeEach(async () => {
    process.stdout.write('=== beforeEach started ===\n');
    // Create temporary directory
    tempDir = fs.mkdtempSync(path.join(process.cwd(), 'test-temp-'));

    // Create MCP client with temporary database
    const dbPath = path.join(tempDir, 'e2e_mcp_test_db');
    client = new MCPClient({
      serverUrl: 'stdio',
      serverCommand: 'poetry',
      serverArgs: ['run', 'python', '-m', 'grizabella.mcp.server', '--db-path', dbPath],
      debug: true
    });

    // Connect to client
    await client.connect();

    // Phase 1: Schema Definition
    await defineSchema();

    // Phase 2: Data Population
    await populateData();
  });

  afterEach(async () => {
    // Close client and cleanup
    if (client) {
      await client.disconnect();
    }

    if (tempDir && fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  async function defineSchema() {
    process.stdout.write('=== Starting defineSchema ===\n');

    // ObjectTypeDefinitions
    const authorOtd: ObjectTypeDefinition = {
      name: 'Author',
      description: 'Represents a researcher or author of a scientific paper.',
      properties: [
        { name: 'full_name', data_type: PropertyDataType.TEXT, is_indexed: true, is_nullable: false },
        { name: 'email', data_type: PropertyDataType.TEXT, is_unique: true, is_nullable: true },
        { name: 'birth_year', data_type: PropertyDataType.INTEGER, is_nullable: true }
      ]
    };

    const paperOtd: ObjectTypeDefinition = {
      name: 'Paper',
      description: 'Represents a scientific publication.',
      properties: [
        { name: 'title', data_type: PropertyDataType.TEXT, is_indexed: true, is_nullable: false },
        { name: 'abstract', data_type: PropertyDataType.TEXT, is_nullable: true },
        { name: 'publication_year', data_type: PropertyDataType.INTEGER, is_indexed: true, is_nullable: false },
        { name: 'doi', data_type: PropertyDataType.TEXT, is_unique: true, is_nullable: true }
      ]
    };

    const venueOtd: ObjectTypeDefinition = {
      name: 'Venue',
      description: 'Represents a journal, conference, or workshop where papers are published.',
      properties: [
        { name: 'venue_name', data_type: PropertyDataType.TEXT, is_indexed: true, is_unique: true, is_nullable: false },
        { name: 'venue_type', data_type: PropertyDataType.TEXT, is_indexed: true, is_nullable: false },
        { name: 'city', data_type: PropertyDataType.TEXT, is_nullable: true }
      ]
    };

    const datetimeTestOtd: ObjectTypeDefinition = {
      name: 'TestDateTimeObject',
      description: 'An object type to test datetime handling.',
      properties: [
        { name: 'event_name', data_type: PropertyDataType.TEXT, is_nullable: false },
        { name: 'event_timestamp', data_type: PropertyDataType.DATETIME, is_nullable: false }
      ]
    };

    process.stdout.write('Creating object types...\n');
    await client.createObjectType({ object_type_def: authorOtd });
    await client.createObjectType({ object_type_def: paperOtd });
    await client.createObjectType({ object_type_def: venueOtd });
    await client.createObjectType({ object_type_def: datetimeTestOtd });
    process.stdout.write('Object types created successfully\n');

    // EmbeddingDefinition
    const paperAbstractEd: EmbeddingDefinition = {
      name: 'PaperAbstractEmbedding',
      object_type_name: 'Paper',
      source_property_name: 'abstract',
      embedding_model: 'mixedbread-ai/mxbai-embed-large-v1',
      description: 'Embedding for the abstract of papers.'
    };

    process.stdout.write('Creating embedding definition...\n');
    const embeddingParams: any = {
      name: paperAbstractEd.name,
      object_type_name: paperAbstractEd.object_type_name,
      source_property_name: paperAbstractEd.source_property_name,
      embedding_model: paperAbstractEd.embedding_model!,
      description: paperAbstractEd.description || 'Embedding for the abstract of papers.'
    };

    if (paperAbstractEd.dimensions !== undefined) {
      embeddingParams.dimensions = paperAbstractEd.dimensions;
    }

    await client.createEmbeddingDefinition(embeddingParams);
    process.stdout.write('Embedding definition created successfully\n');

    // RelationTypeDefinitions
    const authoredByRtd: RelationTypeDefinition = {
      name: 'AUTHORED_BY',
      description: 'Connects a Paper to its Author(s).',
      source_object_type_names: ['Paper'],
      target_object_type_names: ['Author'],
      properties: [
        { name: 'author_order', data_type: PropertyDataType.INTEGER, is_nullable: true, description: 'Order of authorship' }
      ]
    };

    const citesRtd: RelationTypeDefinition = {
      name: 'CITES',
      description: 'Connects a Paper to another Paper it cites.',
      source_object_type_names: ['Paper'],
      target_object_type_names: ['Paper'],
      properties: [
        { name: 'citation_context', data_type: PropertyDataType.TEXT, is_nullable: true, description: 'Brief context for citation.' }
      ]
    };

    const publishedInRtd: RelationTypeDefinition = {
      name: 'PUBLISHED_IN',
      description: 'Connects a Paper to the Venue it was published in.',
      source_object_type_names: ['Paper'],
      target_object_type_names: ['Venue'],
      properties: []
    };

    await client.createRelationType({ relation_type_def: authoredByRtd });
    await client.createRelationType({ relation_type_def: citesRtd });
    await client.createRelationType({ relation_type_def: publishedInRtd });
  }

  async function populateData() {
    // Author Instances
    await client.upsertObject({
      obj: {
        id: ids['author_1']!,
        object_type_name: 'Author',
        properties: {
          full_name: 'Dr. Alice Wonderland',
          email: 'alice@example.com',
          birth_year: 1980
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.upsertObject({
      obj: {
        id: ids['author_2']!,
        object_type_name: 'Author',
        properties: {
          full_name: 'Dr. Bob The Builder',
          email: 'bob@example.com',
          birth_year: 1975
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.upsertObject({
      obj: {
        id: ids['author_3']!,
        object_type_name: 'Author',
        properties: {
          full_name: 'Dr. Carol Danvers',
          email: 'carol@example.com',
          birth_year: 1985
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    // Venue Instances
    await client.upsertObject({
      obj: {
        id: ids['venue_1']!,
        object_type_name: 'Venue',
        properties: {
          venue_name: 'Journal of Fantastical AI',
          venue_type: 'Journal',
          city: 'Virtual'
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.upsertObject({
      obj: {
        id: ids['venue_2']!,
        object_type_name: 'Venue',
        properties: {
          venue_name: 'Conference on Practical Magic',
          venue_type: 'Conference',
          city: 'New Orleans'
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    // Paper Instances
    await client.upsertObject({
      obj: {
        id: ids['paper_1']!,
        object_type_name: 'Paper',
        properties: {
          title: 'Advanced Gryphon Behavior',
          abstract: 'This seminal paper explores the intricate and often misunderstood social structures within modern gryphon populations. We present a novel longitudinal dataset, collected over five years, and employ advanced statistical modeling to analyze their complex mating rituals and hierarchical dynamics. Our findings challenge previous assumptions about gryphon territoriality and communication patterns.',
          publication_year: 2023,
          doi: '10.1000/jfa.2023.001'
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.upsertObject({
      obj: {
        id: ids['paper_2']!,
        object_type_name: 'Paper',
        properties: {
          title: 'The Aerodynamics of Broomsticks',
          abstract: 'An in-depth computational and experimental study of broomstick flight dynamics, considering the interplay of magical enchantments and traditional material science. Various wood types and enchantment patterns were tested. Results indicate a strong, statistically significant correlation between willow wood construction and enhanced flight stability, particularly in turbulent conditions.',
          publication_year: 2022,
          doi: '10.2000/cpm.2022.002'
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.upsertObject({
      obj: {
        id: ids['paper_3']!,
        object_type_name: 'Paper',
        properties: {
          title: 'Quantum Entanglement in Potion Brewing',
          abstract: 'We investigate the previously hypothesized role of quantum mechanical effects in the efficacy of advanced potion-making. This research specifically focuses on entanglement-assisted ingredient mixing protocols. Our experimental results suggest that leveraging quantum entanglement can significantly enhance potion potency and reduce brewing time, potentially revolutionizing alchemical practices.',
          publication_year: 2023,
          doi: '10.1000/jfa.2023.003'
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.upsertObject({
      obj: {
        id: ids['paper_4']!,
        object_type_name: 'Paper',
        properties: {
          title: 'A History of Mythical Creatures',
          abstract: 'A foundational and comprehensive text on the historical study of mythical creatures across various cultures. This volume includes detailed chapters on early gryphon observations, their symbolism in ancient art, and documented interactions with human societies. It serves as a critical reference for researchers in cryptozoology and mythological studies.',
          publication_year: 2010,
          doi: '10.3000/hmc.2010.004'
        },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    // RelationInstances - AUTHORED_BY
    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'AUTHORED_BY',
        source_object_instance_id: ids['paper_1']!,
        target_object_instance_id: ids['author_1']!,
        properties: { author_order: 1 },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'AUTHORED_BY',
        source_object_instance_id: ids['paper_1']!,
        target_object_instance_id: ids['author_2']!,
        properties: { author_order: 2 },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'AUTHORED_BY',
        source_object_instance_id: ids['paper_2']!,
        target_object_instance_id: ids['author_2']!,
        properties: { author_order: 1 },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'AUTHORED_BY',
        source_object_instance_id: ids['paper_3']!,
        target_object_instance_id: ids['author_1']!,
        properties: { author_order: 1 },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'AUTHORED_BY',
        source_object_instance_id: ids['paper_3']!,
        target_object_instance_id: ids['author_3']!,
        properties: { author_order: 2 },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'AUTHORED_BY',
        source_object_instance_id: ids['paper_4']!,
        target_object_instance_id: ids['author_3']!,
        properties: { author_order: 1 },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    // RelationInstances - CITES
    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'CITES',
        source_object_instance_id: ids['paper_1']!,
        target_object_instance_id: ids['paper_4']!,
        properties: { citation_context: 'Builds upon foundational gryphon observations and historical accounts.' },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'CITES',
        source_object_instance_id: ids['paper_3']!,
        target_object_instance_id: ids['paper_2']!,
        properties: { citation_context: 'Compares quantum effects in potions to observed magical flight principles in broomsticks.' },
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    // RelationInstances - PUBLISHED_IN
    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'PUBLISHED_IN',
        source_object_instance_id: ids['paper_1']!,
        target_object_instance_id: ids['venue_1']!,
        properties: {},
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'PUBLISHED_IN',
        source_object_instance_id: ids['paper_2']!,
        target_object_instance_id: ids['venue_2']!,
        properties: {},
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'PUBLISHED_IN',
        source_object_instance_id: ids['paper_3']!,
        target_object_instance_id: ids['venue_1']!,
        properties: {},
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'PUBLISHED_IN',
        source_object_instance_id: ids['paper_4']!,
        target_object_instance_id: ids['venue_1']!,
        properties: {},
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });
  }

  async function getEmbeddingVectorForQueryText(text: string, embeddingDefinitionName = 'PaperAbstractEmbedding'): Promise<EmbeddingVector> {
    const result = await client.getEmbeddingVectorForText({
      text,
      embedding_definition_name: embeddingDefinitionName
    });
    return result;
  }

  async function runInitialQueries() {
    // Query 1
    const q1Text = 'gryphon social structures';
    const q1Vector = await getEmbeddingVectorForQueryText(q1Text);

    const query1: ComplexQuery = {
      description: 'Alice\'s 2023 papers on gryphon social behavior',
      components: [{
        object_type_name: 'Paper',
        relational_filters: [
          { property_name: 'publication_year', operator: '==' as RelationalOperator, value: 2023 }
        ],
        embedding_searches: [{
          embedding_definition_name: 'PaperAbstractEmbedding',
          similar_to_payload: q1Vector.vector,
          limit: 1,
        } as EmbeddingSearchClause],
        graph_traversals: [{
          relation_type_name: 'AUTHORED_BY',
          direction: 'outgoing' as GraphTraversalDirection,
          target_object_type_name: 'Author',
          target_object_properties: [
            { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Alice Wonderland' }
          ]
        }]
      }]
    };

    const result1 = await client.executeComplexQuery({ query: query1 });
    assertResults(result1, [ids['paper_1']!], 'Initial Query 1');

    // Query 2
    const query2: ComplexQuery = {
      description: 'Papers by Bob & Alice citing Paper 4',
      components: [{
        object_type_name: 'Paper',
        graph_traversals: [
          {
            relation_type_name: 'AUTHORED_BY',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Author',
            target_object_properties: [
              { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Bob The Builder' }
            ]
          },
          {
            relation_type_name: 'AUTHORED_BY',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Author',
            target_object_properties: [
              { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Alice Wonderland' }
            ]
          },
          {
            relation_type_name: 'CITES',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Paper',
            target_object_id: ids['paper_4']!
          }
        ]
      }]
    };

    const result2 = await client.executeComplexQuery({ query: query2 });
    assertResults(result2, [ids['paper_1']!], 'Initial Query 2');
  }

  async function modifyData() {
    // 1. Update Paper abstract (paper_1)
    const paper1 = await client.getObjectById({
      object_id: ids['paper_1']!,
      type_name: 'Paper'
    });
    if (paper1) {
      paper1.properties['abstract'] = 'A new study on dragon linguistics.';
      await client.upsertObject({ obj: paper1 });
    }

    // 2. Add CITES relation (paper_2 -> paper_4)
    await client.addRelation({
      relation: {
        id: uuidv4(),
        relation_type_name: 'CITES',
        source_object_instance_id: ids['paper_2']!,
        target_object_instance_id: ids['paper_4']!,
        properties: {},
        weight: new Decimal(1.0),
        upsert_date: new Date()
      }
    });

    // 3. Delete AUTHORED_BY relation (paper_1, author_2)
    const relationsToDelete = await client.getRelation({
      from_object_id: ids['paper_1']!,
      to_object_id: ids['author_2']!,
      relation_type_name: 'AUTHORED_BY'
    });
    expect(relationsToDelete.relations.length).toBeGreaterThan(0);

    for (const rel of relationsToDelete.relations) {
      await client.deleteRelation({
        relation_type_name: 'AUTHORED_BY',
        relation_id: rel.id
      });
    }
  }

  async function runPostModificationQueries() {
    // Re-run Query 1
    const q1Text = 'gryphon social structures';
    const q1Vector = await getEmbeddingVectorForQueryText(q1Text);

    const query1: ComplexQuery = {
      description: 'Alice\'s 2023 papers on gryphon social behavior (Post-Mod)',
      components: [{
        object_type_name: 'Paper',
        relational_filters: [
          { property_name: 'publication_year', operator: '==' as RelationalOperator, value: 2023 }
        ],
        embedding_searches: [{
          embedding_definition_name: 'PaperAbstractEmbedding',
          similar_to_payload: q1Vector.vector,
          limit: 1,
        } as EmbeddingSearchClause],
        graph_traversals: [{
          relation_type_name: 'AUTHORED_BY',
          direction: 'outgoing' as GraphTraversalDirection,
          target_object_type_name: 'Author',
          target_object_properties: [
            { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Alice Wonderland' }
          ]
        }]
      }]
    };

    const result1 = await client.executeComplexQuery({ query: query1 });
    assertResults(result1, [], 'Post-Mod Query 1');

    // Re-run Query 2
    const query2: ComplexQuery = {
      description: 'Papers by Bob & Alice citing Paper 4 (Post-Mod)',
      components: [{
        object_type_name: 'Paper',
        graph_traversals: [
          {
            relation_type_name: 'AUTHORED_BY',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Author',
            target_object_properties: [
              { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Bob The Builder' }
            ]
          },
          {
            relation_type_name: 'AUTHORED_BY',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Author',
            target_object_properties: [
              { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Alice Wonderland' }
            ]
          },
          {
            relation_type_name: 'CITES',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Paper',
            target_object_id: ids['paper_4']!
          }
        ]
      }]
    };

    const result2 = await client.executeComplexQuery({ query: query2 });
    assertResults(result2, [], 'Post-Mod Query 2');

    // New Query 4
    const query4: ComplexQuery = {
      description: 'Papers in CPM citing Paper 4',
      components: [{
        object_type_name: 'Paper',
        graph_traversals: [
          {
            relation_type_name: 'CITES',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Paper',
            target_object_id: ids['paper_4']!
          },
          {
            relation_type_name: 'PUBLISHED_IN',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Venue',
            target_object_id: ids['venue_2']!
          }
        ]
      }]
    };

    const result4 = await client.executeComplexQuery({ query: query4 });
    assertResults(result4, [ids['paper_2']!], 'Post-Mod Query 4');
  }

  async function runLogicalQueries() {
    // Complex logical query: (A AND B) OR (C AND NOT D)
    const component_A: QueryComponent = {
      object_type_name: 'Paper',
      relational_filters: [
        { property_name: 'publication_year', operator: '==' as RelationalOperator, value: 2023 }
      ]
    };

    const component_B: QueryComponent = {
      object_type_name: 'Paper',
      graph_traversals: [{
        relation_type_name: 'PUBLISHED_IN',
        direction: 'outgoing' as GraphTraversalDirection,
        target_object_type_name: 'Venue',
        target_object_id: ids['venue_1']!
      }]
    };

    const component_C: QueryComponent = {
      object_type_name: 'Paper',
      relational_filters: [
        { property_name: 'publication_year', operator: '==' as RelationalOperator, value: 2022 }
      ]
    };

    const component_D: QueryComponent = {
      object_type_name: 'Paper',
      graph_traversals: [{
        relation_type_name: 'AUTHORED_BY',
        direction: 'outgoing' as GraphTraversalDirection,
        target_object_type_name: 'Author',
        target_object_properties: [
          { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Carol Danvers' }
        ]
      }]
    };

    const logicalQuery: ComplexQuery = {
      description: 'Complex logical query: (year=2023 AND venue=JFA) OR (year=2022 AND NOT author=Carol)',
      query_root: {
        operator: LogicalOperator.OR,
        clauses: [
          {
            operator: LogicalOperator.AND,
            clauses: [component_A, component_B]
          },
          {
            operator: LogicalOperator.AND,
            clauses: [
              component_C,
              {
                clause: component_D
              } as NotClause
            ]
          }
        ]
      } as LogicalGroup
    };

    const result = await client.executeComplexQuery({ query: logicalQuery });
    assertResults(result, [ids['paper_1']!, ids['paper_2']!, ids['paper_3']!], 'Complex Logical Query');

    // Backward compatibility with components
    const queryBackwardCompat: ComplexQuery = {
      description: 'Backward compatibility test with components',
      components: [
        {
          object_type_name: 'Paper',
          relational_filters: [
            { property_name: 'publication_year', operator: '==' as RelationalOperator, value: 2023 }
          ]
        },
        {
          object_type_name: 'Paper',
          graph_traversals: [{
            relation_type_name: 'AUTHORED_BY',
            direction: 'outgoing' as GraphTraversalDirection,
            target_object_type_name: 'Author',
            target_object_properties: [
              { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Alice Wonderland' }
            ]
          }]
        }
      ]
    };

    const resultBackwardCompat = await client.executeComplexQuery({ query: queryBackwardCompat });

    // New explicit AND query
    const queryNewAnd: ComplexQuery = {
      description: 'New explicit AND query with query_root',
      query_root: {
        operator: LogicalOperator.AND,
        clauses: [
          {
            object_type_name: 'Paper',
            relational_filters: [
              { property_name: 'publication_year', operator: '==' as RelationalOperator, value: 2023 }
            ]
          },
          {
            object_type_name: 'Paper',
            graph_traversals: [{
              relation_type_name: 'AUTHORED_BY',
              direction: 'outgoing' as GraphTraversalDirection,
              target_object_type_name: 'Author',
              target_object_properties: [
                { property_name: 'full_name', operator: '==' as RelationalOperator, value: 'Dr. Alice Wonderland' }
              ]
            }]
          }
        ]
      } as LogicalGroup
    };

    const resultNewAnd = await client.executeComplexQuery({ query: queryNewAnd });

    const expectedIdsAndQuery = [ids['paper_1']!, ids['paper_3']!];

    assertResults(resultBackwardCompat, expectedIdsAndQuery, 'Backward Compatibility Query');
    assertResults(resultNewAnd, expectedIdsAndQuery, 'New AND Query');

    // Check that results are identical
    expect(resultBackwardCompat.object_instances.map(obj => obj.id).sort())
      .toEqual(resultNewAnd.object_instances.map(obj => obj.id).sort());
  }

  async function testDatetimeUpsert() {
    const datetimeObjId = uuidv4();
    const expectedDtUtc = new Date(Date.UTC(2023, 9, 26, 5, 0, 0)); // 2023-10-26 05:00:00 UTC

    const objToUpsert: ObjectInstance = {
      id: datetimeObjId,
      object_type_name: 'TestDateTimeObject',
      properties: {
        event_name: 'Test Event with Offset',
        event_timestamp: expectedDtUtc
      },
      weight: new Decimal('1.0'),
      upsert_date: new Date()
    };

    const upsertedObj = await client.upsertObject({ obj: objToUpsert });

    expect(upsertedObj.id).toBe(datetimeObjId);

    // Retrieve the object
    const retrievedObj = await client.getObjectById({
      object_id: datetimeObjId,
      type_name: 'TestDateTimeObject'
    });

    expect(retrievedObj).toBeDefined();
    expect(retrievedObj!.id).toBe(datetimeObjId);
    expect(retrievedObj!.properties['event_timestamp']).toBeInstanceOf(Date);
    expect(retrievedObj!.properties['event_timestamp']).toEqual(expectedDtUtc);
  }

  function assertResults(queryResult: QueryResult, expectedIds: string[], description: string) {
    expect(queryResult).toBeDefined();
    if (queryResult.errors && queryResult.errors.length > 0) {
      fail(`Query '${description}' failed with errors: ${queryResult.errors.join(', ')}`);
    }

    expect(Array.isArray(queryResult.object_instances)).toBe(true);

    const fetchedIds = new Set(queryResult.object_instances.map(obj => obj.id));
    const expectedIdSet = new Set(expectedIds);

    expect(fetchedIds).toEqual(expectedIdSet);
  }

  test('Full MCP E2E Scenario', async () => {
    // Initial queries
    await runInitialQueries();

    // Modify data
    await modifyData();

    // Post-modification queries
    await runPostModificationQueries();

    // Logical queries
    await runLogicalQueries();

    // Datetime test
    await testDatetimeUpsert();
  });
});