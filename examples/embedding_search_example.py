"""
Embedding Search Example for Grizabella
---------------------------------------

This script demonstrates:
1. Connecting to a Grizabella database.
2. Defining an ObjectType (e.g., "Article") with a text property for embedding.
3. Defining an EmbeddingDefinition for the text property.
4. Upserting ObjectInstances (articles with abstracts).
5. Performing a similarity search using the DBManager's find_similar_objects_by_embedding.
6. Printing the similar articles found.
"""
from grizabella.api.client import Grizabella # Corrected import
from grizabella.core.models import (
    ObjectTypeDefinition,
    PropertyDefinition,
    EmbeddingDefinition,
    ObjectInstance,
    PropertyDataType, # Import Enum
)
# FindSimilarQuery is part of ComplexQuery, not directly used for client.find_similar
# from grizabella.core.query_models import FindSimilarQuery

# Define the path for the Grizabella database
DB_NAME = "embedding_example_db_v2"

# Sample data for articles
ARTICLES_DATA = [
    {
        "title": "The Future of AI in Healthcare",
        "abstract": "Artificial intelligence is poised to revolutionize healthcare by improving diagnostics, personalizing treatments, and streamlining administrative tasks. Machine learning algorithms can analyze vast amounts of medical data to identify patterns and predict patient outcomes with greater accuracy.",
    },
    {
        "title": "Exploring Quantum Computing",
        "abstract": "Quantum computing holds the promise of solving complex problems currently intractable for classical computers. Its principles are based on quantum mechanics, utilizing qubits to perform calculations at unprecedented speeds. Applications range from drug discovery to materials science.",
    },
    {
        "title": "Advances in Renewable Energy",
        "abstract": "Renewable energy sources like solar and wind power are becoming increasingly vital in the global effort to combat climate change. Recent technological advancements have made these energy solutions more efficient and cost-effective, paving the way for a sustainable future.",
    },
    {
        "title": "Understanding Neural Networks",
        "abstract": "Neural networks, inspired by the human brain, are a cornerstone of modern artificial intelligence. They consist of interconnected layers of nodes or 'neurons' that process information, enabling capabilities like image recognition, natural language processing, and complex decision-making.",
    },
    {
        "title": "The Impact of Big Data on Business",
        "abstract": "Big data analytics allows businesses to extract valuable insights from large and complex datasets. This information can be used to optimize operations, understand customer behavior, and drive strategic decision-making, leading to improved performance and competitive advantage.",
    },
]

def main():
    """Main function to demonstrate embedding search in Grizabella."""
    print(f"--- Running Grizabella Embedding Search Example (DB: {DB_NAME}) ---")

    try:
        with Grizabella(db_name_or_path=DB_NAME, create_if_not_exists=True) as client:
            print(f"\n[1] Connected to Grizabella database: {client._db_manager.db_instance_root}")

            # --- Schema Definition ---
            print("\n[2] Defining Schema with Embeddings...")

            # Define "Article" ObjectType
            article_type_def = ObjectTypeDefinition(
                name="Article",
                properties=[
                    PropertyDefinition(name="title", data_type=PropertyDataType.TEXT, is_indexed=True),
                    PropertyDefinition(name="abstract", data_type=PropertyDataType.TEXT), # This will be embedded
                ],
                description="Represents a news article or scientific paper."
            )
            client.create_object_type(article_type_def)
            print(f"  - Created ObjectTypeDefinition: {article_type_def.name}")

            # Define EmbeddingDefinition for the "abstract" property of "Article"
            embedding_def_name = "article_abstract_default_embedding"
            article_abstract_embedding_def = EmbeddingDefinition(
                name=embedding_def_name, # Name for this embedding configuration
                object_type_name="Article",
                source_property_name="abstract", # Property to embed
                # embedding_model="all-MiniLM-L6-v2" # Example: explicitly specify model if needed, defaults in Grizabella
                description="Embedding for Article abstracts using default model."
            )
            client.create_embedding_definition(article_abstract_embedding_def)
            print(f"  - Created EmbeddingDefinition: '{article_abstract_embedding_def.name}' for {article_abstract_embedding_def.object_type_name}.{article_abstract_embedding_def.source_property_name}")

            # --- Data Creation (with embedding generation) ---
            print("\n[3] Creating Object Instances (Articles)...")
            article_ids = []
            for i, article_data in enumerate(ARTICLES_DATA):
                article_obj_instance = ObjectInstance( # Create ObjectInstance model
                    object_type_name="Article",
                    properties=article_data
                )
                # upsert_object returns the full instance including ID
                created_article_instance = client.upsert_object(article_obj_instance)
                article_ids.append(created_article_instance.id)
                print(f"  - Created Article: '{created_article_instance.properties['title']}' (ID: {created_article_instance.id})")

            print(f"\n  Successfully created {len(article_ids)} articles.")
            # Embeddings are typically generated by LanceDBAdapter upon object insertion/update
            # if an EmbeddingDefinition exists.

            # --- Embedding Similarity Search ---
            print("\n[4] Performing Embedding Similarity Search...")

            query_text = "AI applications in medicine and patient care"
            print(f"  - Searching for articles similar to: '{query_text}' using embedding: '{embedding_def_name}'")

            # Use the DBManager's method for find_similar
            # client.find_similar is not the correct method based on client.py
            # GrizabellaDBManager.find_similar_objects_by_embedding is the one.
            similar_articles_results = client._db_manager.find_similar_objects_by_embedding(
                embedding_definition_name=embedding_def_name,
                query_text=query_text,
                limit=3,
                retrieve_full_objects=True # Get full object data
            )

            print(f"\n  Found {len(similar_articles_results)} similar articles:")
            if similar_articles_results:
                for i, result_item_dict in enumerate(similar_articles_results):
                    # result_item_dict is a Dict[str, Any]
                    # If retrieve_full_objects=True, it should contain 'id', 'score',
                    # and 'object_instance_data' (or similar) which is a dict of properties.
                    obj_id = result_item_dict.get("id")
                    score = result_item_dict.get("score", 0.0)
                    
                    # Reconstruct ObjectInstance for consistent handling if needed, or use dict directly
                    # For this example, we'll print from the dict.
                    # The actual structure of result_item_dict depends on LanceDBAdapter's implementation.
                    # Assuming 'object_instance_data' contains the properties.
                    properties = result_item_dict.get("object_instance_data", {}).get("properties", {})
                    title = properties.get("title", "N/A")

                    print(f"    {i+1}. Title: '{title}' (ID: {obj_id})")
                    print(f"        Score: {score:.4f}")
                    # print(f"        Abstract: {properties.get('abstract', '')[:100]}...")
            else:
                print("    - No similar articles found.")

            # Example with retrieve_full_objects=False
            print("\n  - Searching again with retrieve_full_objects=False...")
            similar_articles_raw_results = client._db_manager.find_similar_objects_by_embedding(
                embedding_definition_name=embedding_def_name,
                query_text=query_text,
                limit=2,
                retrieve_full_objects=False
            )
            print(f"\n  Found {len(similar_articles_raw_results)} similar articles (raw results):")
            if similar_articles_raw_results:
                for i, result_item_dict in enumerate(similar_articles_raw_results):
                    # result_item_dict should be simpler, e.g., {'id': ..., 'score': ...}
                    obj_id = result_item_dict.get("id")
                    score = result_item_dict.get("score", 0.0)
                    print(f"    {i+1}. Object ID: {obj_id}, Score: {score:.4f}")
                    # To get full object: full_obj = client.get_object_by_id(object_id=str(obj_id), type_name="Article")
            else:
                print("    - No similar articles found (raw).")

            print("\n[5] Embedding search example finished.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n--- End of Grizabella Embedding Search Example (DB: {DB_NAME}) ---")

if __name__ == "__main__":
    main()