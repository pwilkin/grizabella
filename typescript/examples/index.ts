/**
 * Grizabella TypeScript API - Examples Index
 *
 * This file serves as the main entry point for all examples, providing
 * an overview of available examples and quick access to run them.
 */

// Export all examples
export * from './basic-usage';
export * from './schema-management';
export * from './data-operations';
export * from './query-search';
export * from './advanced-patterns';

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

  'Schema Management': {
    description: 'Advanced schema definition and management patterns',
    examples: [
      'Complex object types with constraints',
      'Relation types with properties',
      'Embedding definitions for semantic search',
      'Schema validation and inspection',
      'Using helper functions and templates',
    ],
    file: 'schema-management.ts',
  },

  'Data Operations': {
    description: 'Comprehensive data manipulation and batch operations',
    examples: [
      'CRUD operations with error handling',
      'Batch creation and processing',
      'Data validation patterns',
      'Performance monitoring',
      'Advanced data manipulation',
    ],
    file: 'data-operations.ts',
  },

  'Query and Search': {
    description: 'Advanced querying, graph traversals, and semantic search',
    examples: [
      'Basic and advanced filtering',
      'Relationship queries and traversals',
      'Complex graph queries',
      'Semantic search with embeddings',
      'Query performance optimization',
    ],
    file: 'query-search.ts',
  },

  'Advanced Patterns': {
    description: 'TypeScript-specific patterns and production-ready practices',
    examples: [
      'Advanced error handling and retry logic',
      'Resource management and context managers',
      'Performance monitoring and optimization',
      'Configuration management patterns',
      'Advanced TypeScript patterns and type safety',
    ],
    file: 'advanced-patterns.ts',
  },
} as const;

/**
 * Quick Start Examples Runner
 *
 * This function runs a curated set of examples to demonstrate core functionality.
 * It's perfect for getting started quickly or testing the setup.
 */
export async function runQuickStartExamples(): Promise<void> {
  console.log('🚀 Running Grizabella TypeScript API Quick Start Examples\n');

  const { basicConnectionExample } = await import('./basic-usage');
  const { schemaHelpersExample } = await import('./schema-management');
  const { basicCRUDEexample } = await import('./data-operations');
  const { basicAndAdvancedFilteringExample } = await import('./query-search');
  const { advancedErrorHandlingExample } = await import('./advanced-patterns');

  try {
    // Run core examples in logical order
    console.log('📖 Running basic connection example...');
    await basicConnectionExample();

    console.log('\n🏗️ Running schema helpers example...');
    await schemaHelpersExample();

    console.log('\n💾 Running basic CRUD example...');
    await basicCRUDEexample();

    console.log('\n🔍 Running query examples...');
    await basicAndAdvancedFilteringExample();

    console.log('\n🛡️ Running error handling example...');
    await advancedErrorHandlingExample();

    console.log('\n✅ Quick start examples completed successfully!');
    console.log('\n💡 Next steps:');
    console.log('  • Explore individual example files for detailed patterns');
    console.log('  • Check the docs/ directory for API reference');
    console.log('  • Review the main README.md for comprehensive documentation');

  } catch (error) {
    console.error('\n❌ Quick start examples failed:', error);
    console.log('\n🔧 Troubleshooting:');
    console.log('  • Ensure a Grizabella MCP server is running');
    console.log('  • Check the server URL and connection settings');
    console.log('  • Verify TypeScript compilation with: npm run build');
    process.exit(1);
  }
}

/**
 * Development Helper Functions
 */

/**
 * List all available examples with descriptions
 */
export function listAllExamples(): void {
  console.log('📚 Grizabella TypeScript API - Available Examples\n');

  Object.entries(EXAMPLE_CATEGORIES).forEach(([category, info]) => {
    console.log(`🔹 ${category}`);
    console.log(`   ${info.description}`);
    console.log(`   File: examples/${info.file}`);
    console.log('   Examples:');
    info.examples.forEach(example => {
      console.log(`     • ${example}`);
    });
    console.log('');
  });
}

/**
 * Get examples by category
 */
export function getExamplesByCategory(categoryName: string) {
  return EXAMPLE_CATEGORIES[categoryName as keyof typeof EXAMPLE_CATEGORIES];
}

/**
 * Run a specific example by name
 */
export async function runExample(categoryName: string, exampleName?: string): Promise<void> {
  const category = EXAMPLE_CATEGORIES[categoryName as keyof typeof EXAMPLE_CATEGORIES];
  if (!category) {
    console.error(`❌ Category "${categoryName}" not found.`);
    console.log('Available categories:', Object.keys(EXAMPLE_CATEGORIES).join(', '));
    return;
  }

  console.log(`🎯 Running examples from: ${categoryName}`);
  console.log(`📁 File: examples/${category.file}\n`);

  try {
    // Dynamic import based on category
    let module;
    switch (categoryName) {
      case 'Basic Usage':
        module = await import('./basic-usage');
        break;
      case 'Schema Management':
        module = await import('./schema-management');
        break;
      case 'Data Operations':
        module = await import('./data-operations');
        break;
      case 'Query and Search':
        module = await import('./query-search');
        break;
      case 'Advanced Patterns':
        module = await import('./advanced-patterns');
        break;
      default:
        throw new Error(`Unknown category: ${categoryName}`);
    }

    if (exampleName) {
      // Run specific example function
      const exampleFunction = module[exampleName.replace(/\s+/g, '') + 'Example'];
      if (typeof exampleFunction === 'function') {
        await exampleFunction();
      } else {
        console.error(`❌ Example "${exampleName}" not found in ${categoryName}`);
        console.log('Available examples:', category.examples.join(', '));
      }
    } else {
      // Run all examples in the category
      const exampleFunctions = Object.keys(module).filter(key =>
        key.endsWith('Example') && typeof module[key] === 'function'
      );

      for (const funcName of exampleFunctions) {
        console.log(`\n--- Running ${funcName.replace('Example', ' Example')} ---`);
        await module[funcName]();
      }
    }

    console.log(`\n✅ ${categoryName} examples completed successfully!`);

  } catch (error) {
    console.error(`❌ Error running ${categoryName} examples:`, error);
  }
}

// CLI interface for running examples directly
if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'quickstart':
    case 'quick-start':
      runQuickStartExamples().catch(console.error);
      break;

    case 'list':
      listAllExamples();
      break;

    case 'run':
      if (args.length >= 2) {
        runExample(args[1], args[2]).catch(console.error);
      } else {
        console.log('Usage: ts-node examples/index.ts run <category> [example]');
        console.log('Example: ts-node examples/index.ts run "Basic Usage"');
      }
      break;

    default:
      console.log('🤖 Grizabella TypeScript API Examples');
      console.log('');
      console.log('Usage:');
      console.log('  ts-node examples/index.ts quickstart    # Run quick start examples');
      console.log('  ts-node examples/index.ts list          # List all examples');
      console.log('  ts-node examples/index.ts run <category> [example]  # Run specific examples');
      console.log('');
      console.log('Available categories:');
      Object.keys(EXAMPLE_CATEGORIES).forEach(cat => {
        console.log(`  • ${cat}`);
      });
      break;
  }
}