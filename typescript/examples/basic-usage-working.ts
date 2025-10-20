/**
 * Working Basic Usage Example for Grizabella TypeScript API
 *
 * This file demonstrates the fundamental operations that actually work
 * with the current implementation, using correct imports and API calls.
 */

import { 
  GrizabellaClient, 
  PropertyDataType, 
  Decimal 
} from '../src/index';

/**
 * Example 1: Basic Connection Management
 * Shows different ways to connect and manage client lifecycle
 */
async function basicConnectionExample() {
  console.log('=== Basic Connection Example ===');

  // Method 1: Context manager pattern (recommended for TypeScript 5.2+)
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'basic-example-db',
    createIfNotExists: true,
    debug: true,
  });

  console.log('Connected using context manager pattern');
  console.log('Database:', client.dbNameOrPath);
  console.log('Is connected:', client.isConnected());
  
  // Client automatically disconnects when scope ends
}

/**
 * Example 2: Creating Object Types and Instances
 * Shows how to define schemas and create data
 */
async function schemaAndDataExample() {
  console.log('\n=== Schema and Data Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-example-db',
    createIfNotExists: true,
  });

  // Create an object type for books
  await client.createObjectType({
    name: 'Book',
    description: 'A book in the library',
    properties: [
      {
        name: 'title',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        description: 'The title of the book',
      },
      {
        name: 'author',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        description: 'The author of the book',
      },
      {
        name: 'isbn',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
        description: 'The ISBN of the book',
      },
      {
        name: 'published_year',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
        description: 'The year the book was published',
      },
      {
        name: 'price',
        data_type: PropertyDataType.FLOAT,
        is_nullable: true,
        description: 'The price of the book',
      },
    ],
  });

  console.log('Created Book object type');

  // Create book instances
  const books = [
    {
      id: 'book-1',
      object_type_name: 'Book',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: {
        title: 'The Great Gatsby',
        author: 'F. Scott Fitzgerald',
        isbn: '978-0-7432-7356-5',
        published_year: 1925,
        price: 12.99,
      },
    },
    {
      id: 'book-2',
      object_type_name: 'Book',
      weight: new Decimal('0.8'),
      upsert_date: new Date(),
      properties: {
        title: '1984',
        author: 'George Orwell',
        isbn: '978-0-452-28423-4',
        published_year: 1949,
        price: 15.50,
      },
    },
  ];

  for (const book of books) {
    await client.upsertObject(book);
  }

  console.log(`Created ${books.length} book instances`);
}

/**
 * Example 3: Basic Queries and Retrieval
 * Shows how to query and retrieve data
 */
async function queryExample() {
  console.log('\n=== Basic Query Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'schema-example-db', // Reuse the same database
  });

  // Get a specific book by ID
  const book = await client.getObjectById('book-1', 'Book');
  if (book) {
    console.log('Found book:', book.properties.title);
  }

  // Find all books
  const allBooks = await client.findObjects('Book');
  console.log(`Total books: ${allBooks.length}`);

  // Find books by specific criteria
  const oldBooks = await client.findObjects('Book', {
    published_year: { '<': 1950 }
  });
  console.log(`Books published before 1950: ${oldBooks.length}`);

  // Find books by author
  const fitzgeraldBooks = await client.findObjects('Book', {
    author: 'F. Scott Fitzgerald'
  });
  console.log(`Books by Fitzgerald: ${fitzgeraldBooks.length}`);
}

/**
 * Example 4: Relations Between Objects
 * Shows how to create and query relationships
 */
async function relationsExample() {
  console.log('\n=== Relations Example ===');

  await using client = await GrizabellaClient.connect({
    dbNameOrPath: 'relations-example-db',
    createIfNotExists: true,
  });

  // Create Person object type
  await client.createObjectType({
    name: 'Person',
    description: 'A person',
    properties: [
      {
        name: 'name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
      },
      {
        name: 'age',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
      },
    ],
  });

  // Create relation type
  await client.createRelationType({
    name: 'FRIEND_OF',
    description: 'Person is friends with another person',
    source_object_type_names: ['Person'],
    target_object_type_names: ['Person'],
    properties: [
      {
        name: 'since_year',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
        description: 'Year when friendship started',
      },
    ],
  });

  // Create people
  const people = [
    {
      id: 'person-1',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: { name: 'Alice', age: 30 },
    },
    {
      id: 'person-2',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: { name: 'Bob', age: 32 },
    },
    {
      id: 'person-3',
      object_type_name: 'Person',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: { name: 'Charlie', age: 28 },
    },
  ];

  for (const person of people) {
    await client.upsertObject(person);
  }

  // Create friendships
  const friendships = [
    {
      id: 'friendship-1',
      relation_type_name: 'FRIEND_OF',
      source_object_instance_id: 'person-1',
      target_object_instance_id: 'person-2',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: { since_year: 2015 },
    },
    {
      id: 'friendship-2',
      relation_type_name: 'FRIEND_OF',
      source_object_instance_id: 'person-2',
      target_object_instance_id: 'person-3',
      weight: new Decimal('1.0'),
      upsert_date: new Date(),
      properties: { since_year: 2018 },
    },
  ];

  for (const friendship of friendships) {
    await client.addRelation(friendship);
  }

  console.log('Created people and friendships');

  // Query relationships
  const aliceFriends = await client.getOutgoingRelations('person-1', 'Person', 'FRIEND_OF');
  console.log(`Alice has ${aliceFriends.length} friends`);

  const bobFriends = await client.getOutgoingRelations('person-2', 'Person', 'FRIEND_OF');
  console.log(`Bob has ${bobFriends.length} friends`);
}

/**
 * Example 5: Error Handling
 * Shows how to handle common errors gracefully
 */
async function errorHandlingExample() {
  console.log('\n=== Error Handling Example ===');

  try {
    // Try to connect with a valid configuration
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: 'error-example-db',
      createIfNotExists: true,
    });

    // Try to get a non-existent object
    const result = await client.getObjectById('non-existent-id', 'Book');
    if (result === null) {
      console.log('Object not found (expected)');
    }

    // Try to create invalid data (this should show validation)
    try {
      await client.upsertObject({
        id: 'invalid-book',
        object_type_name: 'Book', // This type doesn't exist in this database
        weight: new Decimal('1.0'),
        upsert_date: new Date(),
        properties: {
          title: 'Invalid Book',
        },
      });
    } catch (error: unknown) {
      console.log('Schema error caught:', error instanceof Error ? error.message : String(error));
    }

  } catch (error: unknown) {
    console.log('Connection failed:', error instanceof Error ? error.message : String(error));
  }
}

/**
 * Main function to run all examples
 */
async function main() {
  console.log('🧪 Grizabella TypeScript API - Working Basic Usage Examples\n');

  try {
    await basicConnectionExample();
    await schemaAndDataExample();
    await queryExample();
    await relationsExample();
    await errorHandlingExample();

    console.log('\n✅ All basic usage examples completed successfully!');
  } catch (error) {
    console.error('\n❌ Error running examples:', error);
    process.exit(1);
  }
}

// Run examples if this file is executed directly
if (require.main === module) {
  main().catch(console.error);
}

export {
  basicConnectionExample,
  schemaAndDataExample,
  queryExample,
  relationsExample,
  errorHandlingExample,
};