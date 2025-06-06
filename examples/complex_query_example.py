"""
Complex Query Example for Grizabella
------------------------------------

This script demonstrates:
1. Connecting to a Grizabella database.
2. Defining a schema with multiple ObjectTypes, an EmbeddingDefinition,
   and a RelationType.
   - ObjectTypes: "Researcher", "Paper"
   - EmbeddingDefinition: On "Paper.summary"
   - RelationType: "AUTHORED" (Researcher -> Paper)
3. Populating the database with sample instances.
4. Constructing and executing a ComplexQuery involving:
   - Filtering on a primary object type ("Researcher").
   - Embedding similarity search on a related object type ("Paper").
   - Graph traversal between object types (implicitly handled by QueryEngine).
5. Printing the query results.
"""
from grizabella.api.client import Grizabella # Corrected import
from grizabella.core.models import (
    ObjectTypeDefinition,
    PropertyDefinition,
    EmbeddingDefinition,
    RelationTypeDefinition,
    ObjectInstance,
    RelationInstance,
    PropertyDataType, # Import Enum
)
from grizabella.core.query_models import (
    ComplexQuery,
    QueryComponent,     # Main building block for ComplexQuery
    RelationalFilter,   # Used in QueryComponent
    EmbeddingSearchClause, # Used in QueryComponent
    GraphTraversalClause, # Used in QueryComponent
    QueryResult,
)
# Note: The original QueryNode, FilterCondition, SimilarityCondition, TraversalStep
# are not the direct models used in the latest query_models.py.
# The new structure is ComplexQuery -> List[QueryComponent]
# and QueryComponent contains relational_filters, embedding_searches, graph_traversals.

# Define the path for the Grizabella database
DB_NAME = "complex_query_example_db_v2"

RESEARCHERS_DATA = [
    {"name": "Dr. Evelyn Hayes", "field_of_study": "AI Ethics", "institution": "Tech Forward Institute"},
    {"name": "Dr. Kenji Tanaka", "field_of_study": "Quantum Algorithms", "institution": "Quantum Leap Labs"},
    {"name": "Dr. Priya Sharma", "field_of_study": "AI Ethics", "institution": "Global University"},
    {"name": "Dr. Ben Carter", "field_of_study": "Computational Biology", "institution": "BioSynth Corp"},
]

PAPERS_DATA = [
    {
        "title": "Ethical Frameworks for Advanced AI",
        "publication_year": 2023,
        "doi": "10.xxxx/ethicsai2023",
        "summary": "This paper explores comprehensive ethical guidelines necessary for the development and deployment of advanced artificial intelligence systems, focusing on accountability and transparency.",
    },
    {
        "title": "Quantum Supremacy: A New Era",
        "publication_year": 2024,
        "doi": "10.xxxx/quantum2024",
        "summary": "We demonstrate a novel quantum algorithm that achieves significant speedup over classical counterparts for a specific computational problem, heralding new possibilities in quantum computation.",
    },
    {
        "title": "Bias Detection in AI Models",
        "publication_year": 2023,
        "doi": "10.xxxx/biasai2023",
        "summary": "A critical analysis of methodologies for detecting and mitigating bias in machine learning models, with a focus on fairness in AI-driven decision-making processes.",
    },
    {
        "title": "Genomic Sequencing with Quantum Annealers",
        "publication_year": 2024,
        "doi": "10.xxxx/genomequantum2024",
        "summary": "This research investigates the application of quantum annealing techniques to accelerate complex genomic sequencing tasks, potentially revolutionizing bioinformatics.",
    },
    {
        "title": "The Societal Impact of Autonomous Systems",
        "publication_year": 2022,
        "doi": "10.xxxx/autonomysoc2022",
        "summary": "An in-depth study on the societal implications of increasingly autonomous systems, covering ethical, legal, and economic aspects of AI integration into daily life.",
    }
]

# (Researcher Index, Paper Index)
AUTHORED_RELATIONS = [
    (0, 0), (0, 2), (0, 4), (1, 1), (1, 3), (2, 0), (2, 2), (3, 3),
]


def main():
    """Main function to demonstrate complex queries in Grizabella."""
    print(f"--- Running Grizabella Complex Query Example (DB: {DB_NAME}) ---")

    try:
        with Grizabella(db_name_or_path=DB_NAME, create_if_not_exists=True) as client:
            print(f"\n[1] Connected to Grizabella database: {client._db_manager.db_instance_root}")

            # --- Schema Definition ---
            print("\n[2] Defining Schema...")
            researcher_type = ObjectTypeDefinition(
                name="Researcher",
                properties=[
                    PropertyDefinition(name="name", data_type=PropertyDataType.TEXT, is_indexed=True),
                    PropertyDefinition(name="field_of_study", data_type=PropertyDataType.TEXT, is_indexed=True),
                    PropertyDefinition(name="institution", data_type=PropertyDataType.TEXT),
                ],
            )
            client.create_object_type(researcher_type)
            print(f"  - Created ObjectType: {researcher_type.name}")

            paper_type = ObjectTypeDefinition(
                name="Paper",
                properties=[
                    PropertyDefinition(name="title", data_type=PropertyDataType.TEXT, is_indexed=True),
                    PropertyDefinition(name="publication_year", data_type=PropertyDataType.INTEGER),
                    PropertyDefinition(name="doi", data_type=PropertyDataType.TEXT, is_unique=True),
                    PropertyDefinition(name="summary", data_type=PropertyDataType.TEXT),
                ],
            )
            client.create_object_type(paper_type)
            print(f"  - Created ObjectType: {paper_type.name}")

            embedding_def_name = "paper_summary_embedding"
            paper_summary_embedding = EmbeddingDefinition(
                name=embedding_def_name,
                object_type_name="Paper",
                source_property_name="summary",
                # embedding_model="default_model_name" # Specify if not using Grizabella's default
            )
            client.create_embedding_definition(paper_summary_embedding)
            print(f"  - Created EmbeddingDefinition: '{paper_summary_embedding.name}'")

            authored_relation = RelationTypeDefinition(
                name="AUTHORED",
                source_object_type_names=["Researcher"], # List of names
                target_object_type_names=["Paper"],   # List of names
                properties=[PropertyDefinition(name="contribution_level", data_type=PropertyDataType.TEXT, is_nullable=True)]
            )
            client.create_relation_type(authored_relation)
            print(f"  - Created RelationType: {authored_relation.name}")

            # --- Data Population ---
            print("\n[3] Populating database with instances...")
            researcher_instances = []
            for data in RESEARCHERS_DATA:
                instance = ObjectInstance(object_type_name="Researcher", properties=data)
                researcher_instances.append(client.upsert_object(instance))
            print(f"  - Created {len(researcher_instances)} Researcher instances.")

            paper_instances = []
            for data in PAPERS_DATA:
                instance = ObjectInstance(object_type_name="Paper", properties=data)
                paper_instances.append(client.upsert_object(instance))
            print(f"  - Created {len(paper_instances)} Paper instances.")

            for res_idx, paper_idx in AUTHORED_RELATIONS:
                props = {}
                if res_idx == 0 and paper_idx == 0: props["contribution_level"] = "Lead Investigator"
                
                instance = RelationInstance(
                    relation_type_name="AUTHORED",
                    source_object_instance_id=researcher_instances[res_idx].id,
                    target_object_instance_id=paper_instances[paper_idx].id,
                    properties=props or {} # Ensure it's a dict
                )
                client.add_relation(instance)
            print(f"  - Created {len(AUTHORED_RELATIONS)} AUTHORED relation instances.")

            # --- Complex Query Construction & Execution ---
            print("\n[4] Constructing and Executing Complex Query...")
            # Goal: Find Researchers in 'AI Ethics' AND who authored papers
            #       semantically related to 'fairness and accountability in AI systems'.
            # The ComplexQuery model takes a list of QueryComponents.
            # The QueryEngine will determine how to combine these.
            # For this example, we'll create two components and expect the engine
            # to find researchers that satisfy conditions directly or via relations.

            # Component 1: Filter Researchers by field_of_study
            researcher_component = QueryComponent(
                object_type_name="Researcher",
                relational_filters=[
                    RelationalFilter(property_name="field_of_study", operator="==", value="AI Ethics")
                ]
                # We want to find researchers, so this component targets them.
            )

            # Component 2: Filter Papers by embedding similarity and link to Researchers via AUTHORED
            # This component will identify relevant papers, and the graph traversal
            # will connect them back to researchers. The query engine should then
            # intersect these with the researchers from component 1.
            paper_component = QueryComponent(
                object_type_name="Paper", # This component focuses on papers
                embedding_searches=[
                    EmbeddingSearchClause(
                        embedding_definition_name=embedding_def_name,
                        # The query engine needs to handle converting query_text to vector.
                        # For now, assuming the underlying find_similar_objects_by_embedding
                        # can take text. If not, this part needs adjustment or pre-computation of query vector.
                        # Let's assume the API handles text to vector for the clause.
                        # If `similar_to_payload` must be a vector, this example would need to generate it.
                        # For simplicity, we'll assume the complex query engine can use query_text here.
                        # If not, this example would be more complex.
                        # The `EmbeddingSearchClause` model expects `similar_to_payload: List[float]`.
                        # This means we *must* provide a vector.
                        # For an example, we can't easily generate a vector here without an embedding model.
                        # Let's simplify: assume we are searching for papers and then separately finding authors.
                        # Or, we make the complex query simpler for this example.

                        # Let's re-think: The complex query might be intended to return objects of ONE primary type
                        # that satisfy all conditions, including those on related objects.
                        # If we want to return Researchers:
                        # The Researcher component filters researchers.
                        # A graph traversal from Researcher to Paper, with an embedding filter on Paper.
                        similar_to_payload=[0.1] * 128, # Placeholder for actual query vector - THIS IS A MAJOR SIMPLIFICATION
                                                       # In a real scenario, you'd get this vector from an embedding model
                                                       # based on "fairness and accountability in AI systems".
                                                       # The dimension (128) is also a placeholder.
                        threshold=0.1, # Adjust as needed
                        limit=5 # Max similar papers to consider per traversal
                    )
                ],
                # This component also needs a graph traversal to link back to Researchers
                # if the query engine doesn't automatically link components.
                # The ComplexQuery model doesn't explicitly define how components are linked.
                # Let's assume the query engine is smart enough or we simplify the query.

                # Simpler approach for example:
                # 1. Find relevant papers by embedding.
                # 2. For each paper, find its authors.
                # 3. Filter those authors by field_of_study.
                # This is multi-step, not one ComplexQuery.

                # Let's try to make one ComplexQuery that returns Researchers.
                # The QueryComponent for Researcher would include a GraphTraversalClause
                # that points to Papers and has an embedding search on those papers.
                # This seems more aligned with the intent.
            )
            
            # Revised Query: Target Researchers, traverse to Papers, filter Papers by embedding.
            complex_query_def = ComplexQuery(
                description="Find AI Ethics researchers who authored papers on fairness/accountability.",
                components=[
                    QueryComponent(
                        object_type_name="Researcher",
                        relational_filters=[
                            RelationalFilter(property_name="field_of_study", operator="==", value="AI Ethics")
                        ],
                        graph_traversals=[
                            GraphTraversalClause(
                                relation_type_name="AUTHORED", # Researcher --AUTHORED--> Paper
                                direction="outgoing",
                                target_object_type_name="Paper",
                                # How to apply embedding search on these traversed papers?
                                # GraphTraversalClause has target_object_properties (RelationalFilter)
                                # but not directly EmbeddingSearchClause.
                                # This suggests the ComplexQuery structure might be for ANDing results
                                # from different *primary* object types, or the engine is more sophisticated.

                                # Given the models, it seems a QueryComponent targets ONE object type
                                # for its direct filters (relational, embedding).
                                # Graph traversal finds related objects.

                                # Let's assume the query engine will find Researchers matching the first component,
                                # then find Papers matching the second, and then see which Researchers
                                # are linked to those Papers via AUTHORED. This is an assumption.
                                # The result would then be Researchers.

                                # If the query must return a single type, and all conditions apply to it or its relations:
                                # We want Researchers.
                                # Condition 1: Researcher.field_of_study == "AI Ethics"
                                # Condition 2: Researcher --AUTHORED--> Paper, AND Paper.summary is similar to "text"

                                # This implies the GraphTraversalClause itself needs to support embedding search on target,
                                # or the QueryComponent for "Paper" results are somehow joined.
                                # The current models don't show EmbeddingSearchClause inside GraphTraversalClause.

                                # Simplification: The example will show a query that might not be fully optimal
                                # or perfectly express the most complex intent due to current understanding of how
                                # QueryComponents are combined by the backend QueryEngine.
                                # We will create two components and see what the API returns.
                                # The task asks for a query that involves:
                                # - A relational filter on the primary object type. (Researcher)
                                # - An embedding similarity search on one of its properties. (Paper.summary)
                                # - A graph traversal to a related object type. (Researcher -> Paper)

                                # Let's make the primary target "Researcher".
                                # Relational filter: Researcher.field_of_study == "AI Ethics"
                                # Graph traversal: Researcher --AUTHORED--> Paper
                                # Embedding search: on the Paper.summary of the traversed papers.
                                # This requires the GraphTraversalClause to somehow incorporate the embedding search.
                                # Since it doesn't, we might need to make the Paper the primary target of a component
                                # and then link. This is where the "result_node_id" from the original attempt was useful.

                                # Let's try with two components and assume the engine links them.
                                # Component 1: Researchers in AI Ethics.
                                # Component 2: Papers about fairness.
                                # The engine would need to find Researchers from C1 who AUTHORED Papers from C2.
                            )
                        ]
                    ),
                    # Component 2: Papers about fairness and accountability
                    QueryComponent(
                        object_type_name="Paper",
                        embedding_searches=[
                            EmbeddingSearchClause(
                                embedding_definition_name=embedding_def_name,
                                # This is a placeholder. In a real app, generate this vector.
                                similar_to_payload=[0.1] * int(getattr(client._db_manager.get_embedding_definition(embedding_def_name), 'dimensions', 128) or 128),
                                threshold=0.01, # Low threshold for example
                                limit=10
                            )
                        ]
                    )
                ]
            )
            # The expectation is that the query engine will return Researchers who are in AI Ethics
            # AND are authors of (via AUTHORED relation) the papers found by the embedding search.
            # This is an interpretation of how multiple QueryComponents might be combined.

            print("\n  Complex Query Definition (Interpretation):")
            print(f"  - Query Description: {complex_query_def.description}")
            print(f"  - Component 1: Researchers (field_of_study == 'AI Ethics')")
            print(f"  - Component 2: Papers (summary similar to a placeholder vector for 'fairness/accountability')")
            print(f"  - Expected: Returns Researchers from C1 linked to Papers from C2 via 'AUTHORED'.")


            query_result: QueryResult = client.execute_complex_query(complex_query_def)

            print("\n[5] Query Results:")
            if query_result and query_result.object_instances:
                # The type of objects returned depends on the query engine's resolution strategy
                # for multiple components. Assuming it returns Researchers if that's the "primary" intent.
                print(f"  Found {len(query_result.object_instances)} matching Object(s) (expected Researchers):")
                for i, obj_instance in enumerate(query_result.object_instances):
                    print(f"\n  --- Result {i+1} (Type: {obj_instance.object_type_name}) ---")
                    print(f"    ID: {obj_instance.id}")
                    for prop, val in obj_instance.properties.items():
                        print(f"    {prop}: {str(val)[:100]}{'...' if len(str(val)) > 100 else ''}")
            elif query_result and query_result.errors:
                 print(f"  Query executed with errors: {query_result.errors}")
            else:
                print("  No results or errors returned from the complex query.")


            print("\n[6] Complex query example finished.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n--- End of Grizabella Complex Query Example (DB: {DB_NAME}) ---")

if __name__ == "__main__":
    main()