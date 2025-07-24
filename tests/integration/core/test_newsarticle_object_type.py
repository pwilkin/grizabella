import unittest
import tempfile
import os
from grizabella.api.client import Grizabella
from grizabella.core.models import ObjectTypeDefinition, PropertyDefinition, PropertyDataType

class TestNewsArticleObjectType(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the database
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_db")
        
        # Initialize the client
        self.client = Grizabella(db_name_or_path=self.db_path, create_if_not_exists=True)
        self.client.connect()

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def test_create_newsarticle_object_type(self):
        # Define the NewsArticle object type
        news_article_def = ObjectTypeDefinition(
            name="NewsArticle",
            description="A news article object type",
            properties=[
                PropertyDefinition(name="title", data_type=PropertyDataType.TEXT, is_nullable=False),
                PropertyDefinition(name="content", data_type=PropertyDataType.TEXT, is_nullable=False),
                PropertyDefinition(name="url", data_type=PropertyDataType.TEXT, is_nullable=False),
                PropertyDefinition(name="date", data_type=PropertyDataType.DATETIME, is_nullable=False),
                PropertyDefinition(name="author", data_type=PropertyDataType.TEXT, is_nullable=True)
            ]
        )

        # Create the object type
        self.client.create_object_type(news_article_def)

        # Verify the object type was created
        retrieved_def = self.client.get_object_type_definition("NewsArticle")
        self.assertIsNotNone(retrieved_def, "Failed to retrieve NewsArticle definition")
        if retrieved_def:
            print("Yeah! NewsArticle object type created successfully!")
            self.assertEqual(retrieved_def.name, "NewsArticle")
            self.assertEqual(len(retrieved_def.properties), 5)

            # Verify specific properties
            title_prop = next(p for p in retrieved_def.properties if p.name == "title")
            self.assertEqual(title_prop.data_type, PropertyDataType.TEXT)
            self.assertFalse(title_prop.is_nullable)

            author_prop = next(p for p in retrieved_def.properties if p.name == "author")
            self.assertEqual(author_prop.data_type, PropertyDataType.TEXT)
            self.assertTrue(author_prop.is_nullable)
        

if __name__ == "__main__":
    unittest.main()