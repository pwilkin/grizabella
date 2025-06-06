"""
Basic Usage Example for Grizabella
----------------------------------

This script demonstrates:
1. Connecting to a Grizabella database.
2. Defining ObjectTypes (e.g., "Author", "Book").
3. Defining a RelationType (e.g., "WRITTEN_BY").
4. Creating ObjectInstances (authors and books).
5. Creating a RelationInstance connecting a book to an author.
6. Performing a simple query to retrieve objects.
"""
from grizabella.api.client import Grizabella
from grizabella.core.models import (
    ObjectTypeDefinition,
    RelationTypeDefinition,
    PropertyDefinition,
    ObjectInstance,
    RelationInstance,
    PropertyDataType, # Import Enum for data types
)

# Define the path for the Grizabella database
# Using a temporary database name for this example
DB_NAME = "basic_example_db_v2" # Changed to avoid conflict if old one exists

def main():
    """Main function to demonstrate basic Grizabella usage."""
    print(f"--- Running Grizabella Basic Usage Example (DB: {DB_NAME}) ---")

    try:
        # Connect to Grizabella using a 'with' statement for resource management
        # Note: destroy_on_exit is not a direct Grizabella client parameter.
        # Database lifecycle (creation/deletion) is handled by GrizabellaDBManager.
        # For examples, ensure db_name_or_path is unique or manage cleanup separately if needed.
        with Grizabella(db_name_or_path=DB_NAME, create_if_not_exists=True) as client:
            print(f"\n[1] Connected to Grizabella database: {client._db_manager.db_instance_root}") # Accessing via _db_manager for example path

            # --- Schema Definition ---
            print("\n[2] Defining Schema...")

            # Define "Author" ObjectType
            author_type_def = ObjectTypeDefinition(
                name="Author",
                properties=[
                    PropertyDefinition(name="name", data_type=PropertyDataType.TEXT, is_indexed=True),
                    PropertyDefinition(name="birth_year", data_type=PropertyDataType.INTEGER),
                ],
                description="Represents an author of a book."
            )
            client.create_object_type(author_type_def)
            print(f"  - Created ObjectTypeDefinition: {author_type_def.name}")

            # Define "Book" ObjectType
            book_type_def = ObjectTypeDefinition(
                name="Book",
                properties=[
                    PropertyDefinition(name="title", data_type=PropertyDataType.TEXT, is_indexed=True),
                    PropertyDefinition(name="publication_year", data_type=PropertyDataType.INTEGER),
                    PropertyDefinition(name="isbn", data_type=PropertyDataType.TEXT, is_unique=True),
                ],
                description="Represents a book."
            )
            client.create_object_type(book_type_def)
            print(f"  - Created ObjectTypeDefinition: {book_type_def.name}")

            # Define "WRITTEN_BY" RelationType (Book -> Author)
            written_by_relation_def = RelationTypeDefinition(
                name="WRITTEN_BY",
                source_object_type_names=["Book"],
                target_object_type_names=["Author"],
                properties=[
                    PropertyDefinition(name="role", data_type=PropertyDataType.TEXT, is_nullable=True)
                ],
                description="Connects a book to its author."
            )
            client.create_relation_type(written_by_relation_def)
            print(f"  - Created RelationTypeDefinition: {written_by_relation_def.name}")

            # --- Data Creation ---
            print("\n[3] Creating Object Instances...")

            # Create Author instances
            author1_obj = ObjectInstance(
                object_type_name="Author",
                properties={"name": "George Orwell", "birth_year": 1903},
            )
            author1 = client.upsert_object(author1_obj) # upsert_object returns the instance
            print(f"  - Created Author: {author1.properties['name']} (ID: {author1.id})")

            author2_obj = ObjectInstance(
                object_type_name="Author",
                properties={"name": "Aldous Huxley", "birth_year": 1894},
            )
            author2 = client.upsert_object(author2_obj)
            print(f"  - Created Author: {author2.properties['name']} (ID: {author2.id})")

            # Create Book instances
            book1_obj = ObjectInstance(
                object_type_name="Book",
                properties={"title": "Nineteen Eighty-Four", "publication_year": 1949, "isbn": "978-0451524935"},
            )
            book1 = client.upsert_object(book1_obj)
            print(f"  - Created Book: {book1.properties['title']} (ID: {book1.id})")

            book2_obj = ObjectInstance(
                object_type_name="Book",
                properties={"title": "Animal Farm", "publication_year": 1945, "isbn": "978-0451526342"},
            )
            book2 = client.upsert_object(book2_obj)
            print(f"  - Created Book: {book2.properties['title']} (ID: {book2.id})")

            book3_obj = ObjectInstance(
                object_type_name="Book",
                properties={"title": "Brave New World", "publication_year": 1932, "isbn": "978-0060850524"},
            )
            book3 = client.upsert_object(book3_obj)
            print(f"  - Created Book: {book3.properties['title']} (ID: {book3.id})")


            # --- Relation Creation ---
            print("\n[4] Creating Relation Instances...")
            relation1_obj = RelationInstance(
                relation_type_name="WRITTEN_BY",
                source_object_instance_id=book1.id, # Use .id from returned instance
                target_object_instance_id=author1.id,
                properties={"role": "Author"}
            )
            relation1 = client.add_relation(relation1_obj) # add_relation returns the instance
            print(f"  - Created Relation: Book '{book1.properties['title']}' WRITTEN_BY Author '{author1.properties['name']}' (ID: {relation1.id})")

            relation2_obj = RelationInstance(
                relation_type_name="WRITTEN_BY",
                source_object_instance_id=book2.id,
                target_object_instance_id=author1.id,
                properties={"role": "Author"} # Explicitly set role, or ensure default is handled by model/DB
            )
            relation2 = client.add_relation(relation2_obj)
            print(f"  - Created Relation: Book '{book2.properties['title']}' WRITTEN_BY Author '{author1.properties['name']}' (ID: {relation2.id})")

            relation3_obj = RelationInstance(
                relation_type_name="WRITTEN_BY",
                source_object_instance_id=book3.id,
                target_object_instance_id=author2.id,
                properties={"role": "Author"}
            )
            relation3 = client.add_relation(relation3_obj)
            print(f"  - Created Relation: Book '{book3.properties['title']}' WRITTEN_BY Author '{author2.properties['name']}' (ID: {relation3.id})")


            # --- Simple Querying ---
            print("\n[5] Performing Queries...")

            # Query 1: Get all books
            all_books = client.find_objects(type_name="Book")
            print(f"\n  Query 1: All Books ({len(all_books)} found)")
            for book_item in all_books:
                print(f"    - ID: {book_item.id}, Title: {book_item.properties['title']}, Year: {book_item.properties['publication_year']}")

            # Query 2: Get books by George Orwell
            # First, find George Orwell's ID
            george_orwell_instances = client.find_objects(
                type_name="Author",
                filter_criteria={"name": "George Orwell"} # Simple equality filter
            )
            if george_orwell_instances:
                george_orwell_author_instance = george_orwell_instances[0]
                print(f"\n  Found George Orwell with ID: {george_orwell_author_instance.id}")

                # Find relations where George Orwell is the target (Author) of "WRITTEN_BY"
                # Relation: Book --WRITTEN_BY--> Author
                # So, we need incoming relations to Author "George Orwell"
                relations_to_orwell = client.get_incoming_relations(
                    object_id=str(george_orwell_author_instance.id), # Expects string ID
                    type_name="Author", # Type of the object_id provided
                    relation_type_name="WRITTEN_BY"
                )
                print(f"  Found {len(relations_to_orwell)} 'WRITTEN_BY' relations pointing to George Orwell:")

                if relations_to_orwell:
                    print("  Books by George Orwell:")
                    for rel in relations_to_orwell:
                        # The source of "WRITTEN_BY" is a Book
                        book_id = str(rel.source_object_instance_id)
                        book_instance = client.get_object_by_id(object_id=book_id, type_name="Book")
                        if book_instance:
                            print(f"    - Title: {book_instance.properties['title']}")
                        else:
                            print(f"    - Could not retrieve book with ID: {book_id}")
                else:
                    print("    - No books found for George Orwell by querying relations.")
            else:
                print("\n  Could not find Author 'George Orwell' to query their books.")

            # Query 3: Get a specific book by ISBN (unique property)
            specific_book_isbn = "978-0060850524" # Brave New World
            queried_books_by_isbn = client.find_objects(
                type_name="Book",
                filter_criteria={"isbn": specific_book_isbn}
            )
            print(f"\n  Query 3: Book with ISBN '{specific_book_isbn}'")
            if queried_books_by_isbn:
                print(f"    - Found: {queried_books_by_isbn[0].properties['title']}")
            else:
                print(f"    - No book found with ISBN {specific_book_isbn}")

            print("\n[6] Basic example finished.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n--- End of Grizabella Basic Usage Example (DB: {DB_NAME}) ---")

if __name__ == "__main__":
    main()