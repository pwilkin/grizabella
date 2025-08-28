"""
Integration tests for LanceDB semantic search functionality in Grizabella.
"""
import pytest
import shutil
import uuid
from pathlib import Path

from grizabella.api.client import Grizabella
from grizabella.core.models import (
    ObjectTypeDefinition,
    PropertyDefinition,
    PropertyDataType,  # Added
    EmbeddingDefinition,
    ObjectInstance,
)

# --- Test Dataset Design ---
# Group 1: Fruits
FRUIT_GROUP = [
    "Apples are a popular and healthy fruit, often red or green.",
    "Bananas are yellow, curved fruits rich in potassium.",
    "Many people enjoy eating sweet, juicy oranges for vitamin C.",
    "Grapes grow in bunches and can be eaten raw or made into wine.",
    "A ripe mango is delicious and tropical.",
]
# Group 2: Space Exploration
SPACE_GROUP = [
    "Humans first landed on the moon in 1969.",
    "Mars is the fourth planet from the sun and a target for future missions.",
    "Telescopes allow us to observe distant galaxies and nebulae.",
    "The International Space Station orbits the Earth, conducting research.",
    "Black holes are regions of spacetime where gravity is so strong nothing can escape.",
]
# Group 3: Cooking Techniques
COOKING_GROUP = [
    "Braising involves searing food at high temperature, then simmering it in liquid.",
    "Sautéing is a method of cooking food quickly in a small amount of oil or fat.",
    "Grilling gives food a smoky flavor by cooking it over direct heat.",
    "Baking uses prolonged dry heat, normally in an oven.",
    "Sous vide cooking involves vacuum-sealing food and cooking it in a precise temperature water bath.",
]
# Distant/Outlier Fragments
DISTANT_FRAGMENTS = [
    "The stock market experienced significant volatility last week.",
    "Classical music often features complex harmonies and instrumentation.",
    "Effective project management requires clear communication and planning.",
    "Learning a new programming language can be challenging but rewarding.",
    "The history of ancient civilizations is fascinating.",
]

ALL_TEXTS = FRUIT_GROUP + SPACE_GROUP + COOKING_GROUP + DISTANT_FRAGMENTS

# Helper to create a temporary Grizabella instance
@pytest.fixture
def temp_grizabella_db():
    db_path_name = f"temp_test_db_{uuid.uuid4()}"
    # Grizabella client expects a name or a full path.
    # If just a name, it creates it in a default grizabella_data dir.
    # For full control over cleanup, we'll create a temporary directory
    # and pass the full path to the database *directory* Grizabella should use.
    temp_base_dir = Path(f"./temp_grizabella_dbs_{uuid.uuid4()}")
    temp_base_dir.mkdir(parents=True, exist_ok=True)
    db_instance_path = temp_base_dir / db_path_name

    # The Grizabella client's db_name_or_path refers to the directory where
    # the specific database instance (e.g., 'default' or a named one) will reside.
    # So, we pass the parent of where the actual db files will go.
    # Or, more simply, pass a unique name and let it use its default base,
    # then clean up that specific named instance.
    # Let's use a unique name and rely on Grizabella's pathing, then clean its specific dir.
    
    # Correction: db_name_or_path IS the instance path.
    # So, we create a directory for this specific test instance.
    db_instance_path.mkdir(parents=True, exist_ok=True)

    gz_client = Grizabella(db_name_or_path=db_instance_path, create_if_not_exists=True)
    gz_client.connect() # Explicitly connect
    yield gz_client
    # Cleanup
    try:
        gz_client.close()
    except Exception as e:
        print(f"Error closing Grizabella client: {e}")
    
    # Force remove the directory and its contents
    for _ in range(3): # Retry up to 3 times
        try:
            if db_instance_path.exists():
                shutil.rmtree(db_instance_path)
            # Also remove the parent temp_base_dir if it's empty or only contained this db
            if temp_base_dir.exists() and not any(temp_base_dir.iterdir()):
                 shutil.rmtree(temp_base_dir)
            elif temp_base_dir.exists() and db_instance_path.name in [d.name for d in temp_base_dir.iterdir()] and len(list(temp_base_dir.iterdir())) == 0 : # if only the db_instance_path was in it
                 shutil.rmtree(temp_base_dir)


            break
        except OSError as e:
            print(f"Error removing directory {db_instance_path} or {temp_base_dir}: {e}. Retrying...")
            import time
            time.sleep(0.1) # Brief pause before retry
    else:
        print(f"Failed to remove directory {db_instance_path} or {temp_base_dir} after multiple attempts.")


def test_semantic_search_with_lancedb(temp_grizabella_db: Grizabella):
    """
    Tests the semantic search capabilities using LanceDB with a diverse dataset.
    """
    gz_client = temp_grizabella_db

    # 1. Define ObjectTypeDefinition and EmbeddingDefinition
    text_doc_type = ObjectTypeDefinition(
        name="TextDocument",
        properties=[
            PropertyDefinition(name="content", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="group_id", data_type=PropertyDataType.TEXT), # To identify semantic group
        ],
    )
    gz_client.create_object_type(text_doc_type)

    embedding_def = EmbeddingDefinition(
        name="content_embedding",
        object_type_name="TextDocument",
        source_property_name="content",
        embedding_model="mixedbread-ai/mxbai-embed-large-v1", # Default model
    )
    gz_client.create_embedding_definition(embedding_def) # Corrected method name

    # 2. Populate the database
    object_ids_by_group = {
        "fruit": [],
        "space": [],
        "cooking": [],
        "distant": [],
    }
    all_object_ids = []

    for i, text in enumerate(FRUIT_GROUP):
        obj = ObjectInstance(
            object_type_name="TextDocument",
            properties={"content": text, "group_id": "fruit"},
        )
        created_obj = gz_client.upsert_object(obj) # Corrected method name
        object_ids_by_group["fruit"].append(created_obj.id)
        all_object_ids.append(created_obj.id)

    for i, text in enumerate(SPACE_GROUP):
        obj = ObjectInstance(
            object_type_name="TextDocument",
            properties={"content": text, "group_id": "space"},
        )
        created_obj = gz_client.upsert_object(obj) # Corrected method name
        object_ids_by_group["space"].append(created_obj.id)
        all_object_ids.append(created_obj.id)

    for i, text in enumerate(COOKING_GROUP):
        obj = ObjectInstance(
            object_type_name="TextDocument",
            properties={"content": text, "group_id": "cooking"},
        )
        created_obj = gz_client.upsert_object(obj) # Corrected method name
        object_ids_by_group["cooking"].append(created_obj.id)
        all_object_ids.append(created_obj.id)
    
    for i, text in enumerate(DISTANT_FRAGMENTS):
        obj = ObjectInstance(
            object_type_name="TextDocument",
            properties={"content": text, "group_id": "distant"},
        )
        created_obj = gz_client.upsert_object(obj) # Corrected method name
        object_ids_by_group["distant"].append(created_obj.id)
        all_object_ids.append(created_obj.id)

    # Ensure embeddings are generated (Grizabella might do this on create_object or on demand)
    # For LanceDB, it's typically on object creation/update if an embedding def exists.
    # We can add an explicit call if needed, or verify by trying a search.

    # 3. Test Execution and Assertions

    # Test Group 1: Fruits
    query_fruit = "Sweet and juicy citrus commonly eaten for breakfast." # Paraphrased query
    results_fruit = gz_client.find_similar(
        embedding_name="content_embedding", query_text=query_fruit, limit=3
    )
    result_fruit_ids = [res.id for res in results_fruit] # find_similar now returns list[ObjectInstance]
    
    print(f"Fruit Query ('{query_fruit}') Results: {result_fruit_ids}")
    for res_id in result_fruit_ids:
        # results_fruit contains ObjectInstance, so we can get properties directly
        # However, to be safe and consistent, let's re-fetch or use the instance from results_fruit
        obj_props = next((r.properties for r in results_fruit if r.id == res_id), None)
        if obj_props:
            print(f"  - ID: {res_id}, Group: {obj_props['group_id']}, Content: {obj_props['content'][:50]}...")
            assert obj_props["group_id"] == "fruit", \
                f"Expected fruit, got {obj_props['group_id']} for ID {res_id}"
        else:
            # Fallback if somehow the ID is not in the results_fruit list (should not happen)
            obj = gz_client.get_object_by_id(object_id=str(res_id), type_name="TextDocument")
            if obj:
                 print(f"  - ID: {res_id}, Group: {obj.properties['group_id']}, Content: {obj.properties['content'][:50]}...")
                 assert obj.properties["group_id"] == "fruit", \
                    f"Expected fruit, got {obj.properties['group_id']} for ID {res_id}"
            else:
                assert False, f"Could not retrieve object for ID {res_id}"
    # Assert that most results are from the fruit group
    fruit_matches = sum(1 for res_id in result_fruit_ids if res_id in object_ids_by_group["fruit"])
    assert fruit_matches >= 2, f"Expected at least 2 fruit matches, got {fruit_matches} for query: '{query_fruit}'"


    # Test Group 2: Space Exploration
    query_space = "Exploring celestial bodies beyond our planet."
    results_space = gz_client.find_similar(
        embedding_name="content_embedding", query_text=query_space, limit=3
    )
    result_space_ids = [res.id for res in results_space]

    print(f"Space Query ('{query_space}') Results: {result_space_ids}")
    for res_id in result_space_ids:
        obj_props = next((r.properties for r in results_space if r.id == res_id), None)
        if obj_props:
            print(f"  - ID: {res_id}, Group: {obj_props['group_id']}, Content: {obj_props['content'][:50]}...")
            assert obj_props["group_id"] == "space", \
                f"Expected space, got {obj_props['group_id']} for ID {res_id}"
        else:
            obj = gz_client.get_object_by_id(object_id=str(res_id), type_name="TextDocument")
            if obj:
                print(f"  - ID: {res_id}, Group: {obj.properties['group_id']}, Content: {obj.properties['content'][:50]}...")
                assert obj.properties["group_id"] == "space", \
                    f"Expected space, got {obj.properties['group_id']} for ID {res_id}"
            else:
                assert False, f"Could not retrieve object for ID {res_id}"
    space_matches = sum(1 for res_id in result_space_ids if res_id in object_ids_by_group["space"])
    assert space_matches >= 2, f"Expected at least 2 space matches, got {space_matches} for query: '{query_space}'"

    # Test Group 3: Cooking Techniques
    query_cooking = "Preparing food using heat."
    results_cooking = gz_client.find_similar(
        embedding_name="content_embedding", query_text=query_cooking, limit=3
    )
    result_cooking_ids = [res.id for res in results_cooking]
    
    print(f"Cooking Query ('{query_cooking}') Results: {result_cooking_ids}")
    for res_id in result_cooking_ids:
        obj_props = next((r.properties for r in results_cooking if r.id == res_id), None)
        if obj_props:
            print(f"  - ID: {res_id}, Group: {obj_props['group_id']}, Content: {obj_props['content'][:50]}...")
            assert obj_props["group_id"] == "cooking", \
                f"Expected cooking, got {obj_props['group_id']} for ID {res_id}"
        else:
            obj = gz_client.get_object_by_id(object_id=str(res_id), type_name="TextDocument")
            if obj:
                print(f"  - ID: {res_id}, Group: {obj.properties['group_id']}, Content: {obj.properties['content'][:50]}...")
                assert obj.properties["group_id"] == "cooking", \
                    f"Expected cooking, got {obj.properties['group_id']} for ID {res_id}"
            else:
                assert False, f"Could not retrieve object for ID {res_id}"
    cooking_matches = sum(1 for res_id in result_cooking_ids if res_id in object_ids_by_group["cooking"])
    assert cooking_matches >= 2, f"Expected at least 2 cooking matches, got {cooking_matches} for query: '{query_cooking}'"

    # Test with a Distant Fragment
    query_distant = "The philosophy of ethics and morality." # Semantically distant query
    results_distant = gz_client.find_similar(
        embedding_name="content_embedding", query_text=query_distant, limit=5
    )
    result_distant_ids = [res.id for res in results_distant]
    print(f"Distant Query ('{query_distant}') Results: {result_distant_ids}")

    # Assert that results are not strongly clustered with any specific group
    # This is harder to assert definitively without distance scores,
    # but we can check that no single group dominates excessively.
    fruit_matches_dist = sum(1 for res_id in result_distant_ids if res_id in object_ids_by_group["fruit"])
    space_matches_dist = sum(1 for res_id in result_distant_ids if res_id in object_ids_by_group["space"])
    cooking_matches_dist = sum(1 for res_id in result_distant_ids if res_id in object_ids_by_group["cooking"])
    
    print(f"  Distant query matches: Fruits={fruit_matches_dist}, Space={space_matches_dist}, Cooking={cooking_matches_dist}")
    
    # A loose assertion: no single group should have more than 2-3 matches in top 5 for a truly distant query
    assert fruit_matches_dist <= 3, "Distant query resulted in too many fruit matches"
    assert space_matches_dist <= 3, "Distant query resulted in too many space matches"
    assert cooking_matches_dist <= 3, "Distant query resulted in too many cooking matches"

    # Optional: Assert exclusion of distant items from specific group queries
    # For example, when querying for "fruit", none of the object_ids_by_group["distant"] should appear in top N.
    # This is implicitly tested if the primary assertions (results belong to the query group) are strong.
    # For instance, if limit=3 for fruit query and all 3 are fruits, then distant items are excluded.

    # If distance scores were available (e.g., res.distance), we could assert:
    # for res in results_distant:
    #     assert res.distance > SOME_THRESHOLD, "Distant query results should have higher dissimilarity"

    print("Semantic search test completed.")


# --- Code Snippet Test Data ---
# Group 1: Python List Comprehensions
PYTHON_LIST_COMP_GROUP = [
    "[x*x for x in range(10) if x % 2 == 0]",
    "squares_of_evens = [num**2 for num in numbers if num % 2 == 0]",
    "result = [item.upper() for item in my_list if len(item) > 3]",
    "filtered_squared_numbers = [n*n for n in input_array if n > 0 and n % 2 != 0]",
    "processed_data = [transform(value) for value in dataset if is_valid(value)]"
]
# Group 2: JavaScript Array Map/Filter
JAVASCRIPT_ARRAY_GROUP = [
    "const newArray = oldArray.map(item => item * 2).filter(item => item > 10);",
    "let processed = data.map(entry => ({ id: entry.id, value: entry.value.toUpperCase() })).filter(x => x.value.startsWith('A'));",
    "const userIds = users.filter(user => user.isActive).map(user => user.id);",
    "const activeAdminNames = accounts.filter(acc => acc.role === 'admin' && acc.status === 'active').map(acc => acc.profile.name);",
    "const prices = products.map(p => p.price).filter(price => price < 100.00);"
]
# Group 3: SQL Select Statements
SQL_SELECT_GROUP = [
    "SELECT name, email FROM customers WHERE country = 'USA' ORDER BY registration_date DESC;",
    "SELECT product_name, price, stock_quantity FROM products WHERE category_id = 5 AND price > 50.00;",
    "SELECT o.order_id, c.customer_name, SUM(oi.quantity * oi.unit_price) AS total_amount FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_date > '2023-01-01' GROUP BY o.order_id, c.customer_name;",
    "SELECT title, author, publication_year FROM books WHERE genre = 'Science Fiction' AND publication_year BETWEEN 2000 AND 2020;",
    "SELECT department_name, COUNT(employee_id) AS num_employees FROM employees JOIN departments ON employees.department_id = departments.department_id GROUP BY department_name HAVING COUNT(employee_id) > 10;"
]
# Distant/Outlier Code Snippets
DISTANT_CODE_FRAGMENTS = [
    "public class HelloWorld { public static void main(String[] args) { System.out.println(\"Hello, Java!\"); } }", # Java
    "<html><head><title>My Page</title></head><body><h1>Welcome</h1></body></html>", # HTML
    "def fibonacci(n):\n  if n <= 1:\n    return n\n  else:\n    return fibonacci(n-1) + fibonacci(n-2)", # Python, but recursive fib, different from list comp
    "const express = require('express'); const app = express(); app.get('/', (req, res) => res.send('Hello World')); app.listen(3000);", # Node.js server
    "CREATE TABLE users (id INT PRIMARY KEY, username VARCHAR(50) NOT NULL, email VARCHAR(100) UNIQUE);" # SQL DDL
]

ALL_CODE_TEXTS = PYTHON_LIST_COMP_GROUP + JAVASCRIPT_ARRAY_GROUP + SQL_SELECT_GROUP + DISTANT_CODE_FRAGMENTS


def test_semantic_search_with_code_snippets(temp_grizabella_db: Grizabella):
    """
    Tests semantic search with code snippets.
    """
    gz_client = temp_grizabella_db

    code_doc_type = ObjectTypeDefinition(
        name="CodeDocument",
        properties=[
            PropertyDefinition(name="code_content", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="language_group", data_type=PropertyDataType.TEXT),
        ],
    )
    gz_client.create_object_type(code_doc_type)

    code_embedding_def = EmbeddingDefinition(
        name="code_content_embedding",
        object_type_name="CodeDocument",
        source_property_name="code_content",
        embedding_model="jinaai/jina-embeddings-v2-base-code", # Using JinaAI model again
    )
    gz_client.create_embedding_definition(code_embedding_def)

    code_object_ids_by_group = {
        "python_list_comp": [],
        "javascript_array": [],
        "sql_select": [],
        "distant_code": [],
    }

    for text in PYTHON_LIST_COMP_GROUP:
        obj = ObjectInstance(object_type_name="CodeDocument", properties={"code_content": text, "language_group": "python_list_comp"})
        created_obj = gz_client.upsert_object(obj)
        code_object_ids_by_group["python_list_comp"].append(created_obj.id)

    for text in JAVASCRIPT_ARRAY_GROUP:
        obj = ObjectInstance(object_type_name="CodeDocument", properties={"code_content": text, "language_group": "javascript_array"})
        created_obj = gz_client.upsert_object(obj)
        code_object_ids_by_group["javascript_array"].append(created_obj.id)

    for text in SQL_SELECT_GROUP:
        obj = ObjectInstance(object_type_name="CodeDocument", properties={"code_content": text, "language_group": "sql_select"})
        created_obj = gz_client.upsert_object(obj)
        code_object_ids_by_group["sql_select"].append(created_obj.id)
    
    for text in DISTANT_CODE_FRAGMENTS:
        obj = ObjectInstance(object_type_name="CodeDocument", properties={"code_content": text, "language_group": "distant_code"})
        created_obj = gz_client.upsert_object(obj)
        code_object_ids_by_group["distant_code"].append(created_obj.id)

    # Test Python List Comprehensions
    query_python = "python code to create a new list by squaring even numbers from an existing list using list comprehension"
    results_python = gz_client.find_similar(embedding_name="code_content_embedding", query_text=query_python, limit=3)
    result_python_ids = [res.id for res in results_python]
    
    print(f"Python Query ('{query_python}') Results: {result_python_ids}")
    for res_id in result_python_ids:
        obj_props = next((r.properties for r in results_python if r.id == res_id), None)
        assert obj_props and obj_props["language_group"] == "python_list_comp", \
            f"Expected python_list_comp, got {obj_props['language_group'] if obj_props else 'None'} for ID {res_id}"
    python_matches = sum(1 for res_id in result_python_ids if res_id in code_object_ids_by_group["python_list_comp"])
    assert python_matches >= 2, f"Expected at least 2 python_list_comp matches, got {python_matches}" # Stricter assertion

    # Test JavaScript Array Methods
    query_js = "javascript code to transform and filter an array of objects using map and filter"
    results_js = gz_client.find_similar(embedding_name="code_content_embedding", query_text=query_js, limit=3)
    result_js_ids = [res.id for res in results_js]

    print(f"JS Query ('{query_js}') Results: {result_js_ids}")
    for res_id in result_js_ids:
        obj_props = next((r.properties for r in results_js if r.id == res_id), None)
        assert obj_props and obj_props["language_group"] == "javascript_array", \
            f"Expected javascript_array, got {obj_props['language_group'] if obj_props else 'None'} for ID {res_id}"
    js_matches = sum(1 for res_id in result_js_ids if res_id in code_object_ids_by_group["javascript_array"])
    assert js_matches >= 2, f"Expected at least 2 javascript_array matches, got {js_matches}" # Stricter assertion

    # Test SQL Select Statements
    query_sql = "SQL select statement to retrieve specific columns from a customer table with a where clause and order by"
    results_sql = gz_client.find_similar(embedding_name="code_content_embedding", query_text=query_sql, limit=3)
    result_sql_ids = [res.id for res in results_sql]

    print(f"SQL Query ('{query_sql}') Results: {result_sql_ids}")
    for res_id in result_sql_ids:
        obj_props = next((r.properties for r in results_sql if r.id == res_id), None)
        assert obj_props and obj_props["language_group"] == "sql_select", \
            f"Expected sql_select, got {obj_props['language_group'] if obj_props else 'None'} for ID {res_id}"
    sql_matches = sum(1 for res_id in result_sql_ids if res_id in code_object_ids_by_group["sql_select"])
    assert sql_matches >= 2, f"Expected at least 2 sql_select matches, got {sql_matches}" # Stricter assertion

    # Test with a Distant Code Query
    query_distant_code = "render a basic webpage with a title and heading" # HTML related
    results_distant_code = gz_client.find_similar(embedding_name="code_content_embedding", query_text=query_distant_code, limit=5)
    result_distant_code_ids = [res.id for res in results_distant_code]
    print(f"Distant Code Query ('{query_distant_code}') Results: {result_distant_code_ids}")

    python_matches_dist = sum(1 for res_id in result_distant_code_ids if res_id in code_object_ids_by_group["python_list_comp"])
    js_matches_dist = sum(1 for res_id in result_distant_code_ids if res_id in code_object_ids_by_group["javascript_array"])
    sql_matches_dist = sum(1 for res_id in result_distant_code_ids if res_id in code_object_ids_by_group["sql_select"])
    
    # Check if the HTML snippet is in the top results
    html_snippet_id = None
    for obj_id in code_object_ids_by_group["distant_code"]:
        # Fetch the object to check its content
        obj = gz_client.get_object_by_id(object_id=str(obj_id), type_name="CodeDocument")
        if obj and "<html>" in obj.properties["code_content"]:
            html_snippet_id = obj.id
            break
    
    if html_snippet_id:
      assert html_snippet_id in result_distant_code_ids, "Expected HTML snippet to be in distant query results for HTML-like query"


    print(f"  Distant code query matches: Python={python_matches_dist}, JS={js_matches_dist}, SQL={sql_matches_dist}")
    assert python_matches_dist <= 2, "Distant code query resulted in too many Python matches"
    assert js_matches_dist <= 2, "Distant code query resulted in too many JS matches"
    assert sql_matches_dist <= 2, "Distant code query resulted in too many SQL matches"

    print("Semantic search with code snippets test completed.")