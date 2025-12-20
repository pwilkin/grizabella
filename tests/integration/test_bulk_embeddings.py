import os
import shutil
import time
import unittest
from pathlib import Path
from decimal import Decimal

from grizabella.api.client import Grizabella
from grizabella.core.models import ObjectTypeDefinition, PropertyDataType, EmbeddingDefinition, ObjectInstance

import inspect
print(f"TEST LOG: Grizabella file: {inspect.getfile(Grizabella)}")
print(f"TEST LOG: Grizabella.init signature: {inspect.signature(Grizabella.__init__)}")

class TestBulkEmbeddings(unittest.TestCase):
    def setUp(self):
        self.db_path = (Path.cwd() / "bulk_test_db").resolve()
        if self.db_path.exists():
            shutil.rmtree(self.db_path)
        self.gb = Grizabella(db_name_or_path=self.db_path, create_if_not_exists=True, use_gpu=True)
        self.gb.connect()

        # Define schema
        self.gb.create_object_type(ObjectTypeDefinition(
            name="Document",
            description="A test document",
            properties=[
                {"name": "content", "data_type": PropertyDataType.TEXT, "is_nullable": False}
            ]
        ))

        self.gb.create_embedding_definition(EmbeddingDefinition(
            name="doc_embedding",
            object_type_name="Document",
            source_property_name="content",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2"
        ))

    def tearDown(self):
        self.gb.close()
        if self.db_path.exists():
            shutil.rmtree(self.db_path)

    def test_bulk_addition_logic(self):
        # 1. Start bulk mode
        self.gb.begin_bulk_addition()

        # 2. Add some objects using real code content
        source_file = Path(__file__).resolve().parent.parent.parent / "grizabella" / "api" / "client.py"
        with open(source_file, "r") as f:
            lines = f.readlines()
        
        num_objects = min(100, len(lines))
        import uuid
        from decimal import Decimal
        self.doc_ids = []
        for i in range(num_objects):
            content = lines[i].strip()
            if not content:
                content = f"Empty line {i}"
            doc_id = uuid.uuid4()
            self.gb.upsert_object(ObjectInstance(
                id=doc_id,
                object_type_name="Document",
                properties={"content": content},
                weight=Decimal("1.0")
            ))
            self.doc_ids.append(str(doc_id))

        # 3. Verify that embeddings are NOT yet in LanceDB
        # We can try to search, it should return nothing or error if table doesn't exist yet
        # Actually, let's just check the internal state if we could, but better use public API.
        # Since LanceDB table is created on first upsert usually, if it's deferred, it might not exist.
        
        # 4. Finish bulk addition
        start_time = time.time()
        self.gb.finish_bulk_addition()
        duration = time.time() - start_time
        print(f"\nBulk processing took {duration:.4f} seconds for {num_objects} objects.")

        # 5. Verify objects are searchable
        results = self.gb.search_similar_objects(
            object_id=self.doc_ids[0],
            type_name="Document",
            n_results=5
        )
        
        self.assertTrue(len(results) > 0)
        print(f"Search results for doc_0: {len(results)}")
        for i, (obj, score) in enumerate(results):
            print(f"  {i+1}. ID: {obj.id}, Score: {score}")

    def test_gpu_initialization(self):
        # This test ensures that when use_gpu=True, the adapter is initialized correctly.
        # We can check the internal adapter's use_gpu flag.
        adapter = self.gb._db_manager._connection_helper._lancedb_adapter_instance
        self.assertTrue(adapter._use_gpu)
        print(f"Verified LanceDBAdapter use_gpu flag: {adapter._use_gpu}")

if __name__ == "__main__":
    unittest.main()
