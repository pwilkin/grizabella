/**
 * Grizabella TypeScript API - Examples Index
 *
 * This file serves as the main entry point for all examples, providing
 * an overview of available examples and quick access to run them.
 */

// Export specific functions to avoid conflicts
export {
  basicConnectionExample,
  schemaAndDataExample,
  queryExample,
  relationsExample,
  errorHandlingExample,
} from './basic-usage';

export {
  basicConnectionExample as workingBasicConnectionExample,
  schemaAndDataExample as workingSchemaAndDataExample,
  queryExample as workingQueryExample,
  relationsExample as workingRelationsExample,
  errorHandlingExample as workingErrorHandlingExample,
} from './basic-usage-working';

export {
  basicCrudExample,
  queryOperationsExample,
  basicRelationsExample,
} from './data-operations';

export {
  basicFilteringExample,
  relationQueriesExample,
  complexQueryPatternsExample,
} from './query-search';

export {
  createObjectTypesExample,
  createRelationTypesExample,
  manageSchemaExample,
  schemaEvolutionExample,
} from './schema-management';

/**
 * Example Categories and Descriptions
 */
export const EXAMPLE_CATEGORIES = {
  'Basic Usage': {
    description: 'Fundamental operations for getting started with Grizabella',
    examples: [
      'Connection management (manual and context manager)',
      'Creating and querying object types',
      'Basic CRUD operations',
      'Simple relationship queries',
      'Error handling basics',
    ],
    file: 'basic-usage.ts',
  },
  'Data Operations': {
    description: 'Comprehensive data manipulation and CRUD operations',
    examples: [
      'Create, Read, Update, Delete operations',
      'Batch data processing',
      'Data validation patterns',
      'Relationship management',
      'Transaction-like operations',
    ],
    file: 'data-operations.ts',
  },
  'Query and Search': {
    description: 'Advanced querying and search capabilities',
    examples: [
      'Complex filtering and criteria',
      'Relationship traversals',
      'Query optimization patterns',
      'Search and filtering combinations',
      'Result pagination and limiting',
    ],
    file: 'query-search.ts',
  },
  'Schema Management': {
    description: 'Schema definition and management operations',
    examples: [
      'Object type creation and management',
      'Relation type definitions',
      'Schema evolution patterns',
      'Type validation and constraints',
      'Schema introspection',
    ],
    file: 'schema-management.ts',
  },
};

/**
 * Quick Start Examples
 * These are the most important examples for new users
 */
export const QUICK_START_EXAMPLES = [
  {
    name: 'Basic Connection and CRUD',
    description: 'Learn how to connect and perform basic operations',
    file: 'basic-usage-working.ts',
    function: 'main',
  },
  {
    name: 'Data Operations',
    description: 'Comprehensive CRUD and data manipulation',
    file: 'data-operations.ts',
    function: 'basicCrudExample',
  },
  {
    name: 'Query Patterns',
    description: 'Learn how to query and filter data',
    file: 'query-search.ts',
    function: 'basicFilteringExample',
  },
];

/**
 * Advanced Examples
 * For users who want to explore more complex scenarios
 */
export const ADVANCED_EXAMPLES = [
  {
    name: 'Schema Management',
    description: 'Define and manage complex schemas',
    file: 'schema-management.ts',
    function: 'createObjectTypesExample',
  },
  {
    name: 'Complex Queries',
    description: 'Advanced querying with relations',
    file: 'query-search.ts',
    function: 'complexQueryPatternsExample',
  },
  {
    name: 'Schema Evolution',
    description: 'Handle schema changes over time',
    file: 'schema-management.ts',
    function: 'schemaEvolutionExample',
  },
];

/**
 * Helper function to run a specific example
 */
export async function runExample(exampleName: string): Promise<void> {
  console.log(`🚀 Running example: ${exampleName}`);
  
  try {
    switch (exampleName) {
      case 'basic-usage':
        const { basicConnectionExample } = await import('./basic-usage');
        await basicConnectionExample();
        break;
        
      case 'basic-usage-working':
        // Since main is not exported, run one of the working examples
        const { basicConnectionExample: workingBasicConnection } = await import('./basic-usage-working');
        await workingBasicConnection();
        break;
        
      case 'data-operations':
        const { basicCrudExample } = await import('./data-operations');
        await basicCrudExample();
        break;
        
      case 'query-search':
        const { basicFilteringExample } = await import('./query-search');
        await basicFilteringExample();
        break;
        
      case 'schema-management':
        const { createObjectTypesExample } = await import('./schema-management');
        await createObjectTypesExample();
        break;
        
      default:
        throw new Error(`Unknown example: ${exampleName}`);
    }
    
    console.log(`✅ Example '${exampleName}' completed successfully!`);
  } catch (error) {
    console.error(`❌ Example '${exampleName}' failed:`, error);
    throw error;
  }
}

/**
 * List all available examples
 */
export function listExamples(): string[] {
  return Object.keys(EXAMPLE_CATEGORIES);
}

/**
 * Get example information
 */
export function getExampleInfo(exampleName: string): typeof EXAMPLE_CATEGORIES[keyof typeof EXAMPLE_CATEGORIES] | null {
  return EXAMPLE_CATEGORIES[exampleName as keyof typeof EXAMPLE_CATEGORIES] || null;
}

// Default export for convenience
export default {
  EXAMPLE_CATEGORIES,
  QUICK_START_EXAMPLES,
  ADVANCED_EXAMPLES,
  runExample,
  listExamples,
  getExampleInfo,
};