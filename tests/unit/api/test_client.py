import unittest
from unittest.mock import patch
from uuid import uuid4 # Import UUID

from grizabella.api.client import Grizabella
from grizabella.core.models import (
    ObjectTypeDefinition,
    PropertyDefinition,
    PropertyDataType,
    ObjectInstance,
    RelationTypeDefinition,
    RelationInstance,
    EmbeddingDefinition, # Added
)
from grizabella.core.query_models import ComplexQuery, QueryComponent, QueryResult # Added
from grizabella.core.exceptions import DatabaseError # Added GrizabellaException and DatabaseError


class TestGrizabellaAPI(unittest.TestCase):
    """Unit tests for the Grizabella API client."""

    @patch("grizabella.api.client.GrizabellaDBManager")
    def setUp(self, MockDBManager):
        """Set up for each test."""
        self.mock_db_manager_instance = MockDBManager.return_value
        self.db_path = "test_db"
        self.grizabella_client = Grizabella(
            db_name_or_path=self.db_path, create_if_not_exists=True
        )
        # Reset mocks for each test if needed, though setUp does this per test method
        self.mock_db_manager_instance.reset_mock()

    def test_init_grizabella_db_manager(self):
        """Test that GrizabellaDBManager is initialized correctly."""
        # GrizabellaDBManager is patched at class level for setUp,
        # so we need a local patch to check constructor call
        with patch("grizabella.api.client.GrizabellaDBManager") as MockDBManagerLocal:
            db_path_local = "local_test_db"
            Grizabella(db_name_or_path=db_path_local, create_if_not_exists=False)
            MockDBManagerLocal.assert_called_once_with(
                db_name_or_path=db_path_local, create_if_not_exists=False
            )

    def test_connect_delegates_to_db_manager(self):
        """Test that connect() calls db_manager.connect()."""
        self.grizabella_client.connect()
        self.mock_db_manager_instance.connect.assert_called_once()
        self.assertTrue(self.grizabella_client._is_connected)

    def test_connect_idempotent(self):
        """Test that connect() is idempotent."""
        self.grizabella_client.connect()
        self.grizabella_client.connect() # Call again
        self.mock_db_manager_instance.connect.assert_called_once() # Still called once
        self.assertTrue(self.grizabella_client._is_connected)


    def test_close_delegates_to_db_manager(self):
        """Test that close() calls db_manager.close()."""
        # First connect to set _is_connected to True
        self.grizabella_client.connect()
        self.mock_db_manager_instance.reset_mock() # Reset after connect call

        self.grizabella_client.close()
        self.mock_db_manager_instance.close.assert_called_once()
        self.assertFalse(self.grizabella_client._is_connected)

    def test_close_idempotent(self):
        """Test that close() is idempotent."""
        self.grizabella_client.connect()
        self.grizabella_client.close()
        self.mock_db_manager_instance.reset_mock() # Reset after first close
        self.grizabella_client.close() # Call again
        self.mock_db_manager_instance.close.assert_not_called() # Not called again
        self.assertFalse(self.grizabella_client._is_connected)


    def test_context_manager_connects_and_closes(self):
        """Test that the context manager calls connect() and close()."""
        with patch("grizabella.api.client.GrizabellaDBManager") as MockDBManagerCtx:
            mock_manager_instance_ctx = MockDBManagerCtx.return_value
            db_path_ctx = "ctx_test_db"

            with Grizabella(db_name_or_path=db_path_ctx) as client_ctx:
                mock_manager_instance_ctx.connect.assert_called_once()
                self.assertIsInstance(client_ctx, Grizabella)
                self.assertTrue(client_ctx._is_connected) # Check internal state

            mock_manager_instance_ctx.close.assert_called_once()
            self.assertFalse(client_ctx._is_connected) # Check internal state after exit

    # --- Schema Management Method Tests (Example) ---
    def test_create_object_type_delegates_and_returns(self):
        """Test create_object_type delegates correctly."""
        object_type_def = ObjectTypeDefinition(
            name="TestNode",
            properties=[
                PropertyDefinition(name="name", data_type=PropertyDataType.TEXT)
            ],
        )
        self.grizabella_client.create_object_type(object_type_def)
        # Corrected to check add_object_type_definition
        self.mock_db_manager_instance.add_object_type_definition.assert_called_once_with(
            object_type_def
        )


    def test_get_object_type_definition_delegates_and_returns(self): # Renamed test and method
        """Test get_object_type_definition delegates and returns value."""
        type_name = "TestNode"
        expected_def = ObjectTypeDefinition(
            name=type_name,
            properties=[
                PropertyDefinition(name="name", data_type=PropertyDataType.TEXT)
            ],
        )
        self.mock_db_manager_instance.get_object_type_definition.return_value = expected_def # Mock correct manager method

        result = self.grizabella_client.get_object_type_definition(type_name) # Call correct client method
        self.mock_db_manager_instance.get_object_type_definition.assert_called_once_with( # Assert correct manager method
            type_name
        )
        self.assertEqual(result, expected_def)

    def test_get_object_type_definition_returns_none_when_manager_does(self): # Renamed test and method
        """Test get_object_type_definition returns None if manager returns None."""
        type_name = "NonExistentNode"
        self.mock_db_manager_instance.get_object_type_definition.return_value = None # Mock correct manager method
        result = self.grizabella_client.get_object_type_definition(type_name) # Call correct client method
        self.mock_db_manager_instance.get_object_type_definition.assert_called_once_with( # Assert correct manager method
            type_name
        )
        self.assertIsNone(result)

    def test_delete_object_type_delegates(self):
        """Test delete_object_type delegates correctly."""
        type_name = "TestNodeToDelete"
        self.grizabella_client.delete_object_type(type_name)
        # Corrected to check remove_object_type_definition
        self.mock_db_manager_instance.remove_object_type_definition.assert_called_once_with(
            type_name
        )

    def test_create_relation_type_delegates(self):
        """Test create_relation_type delegates correctly."""
        relation_type_def = RelationTypeDefinition(
            name="RELATES_TO",
            source_object_type_names=["TestNodeA"],
            target_object_type_names=["TestNodeB"],
        )
        self.grizabella_client.create_relation_type(relation_type_def)
        # Corrected to check add_relation_type_definition
        self.mock_db_manager_instance.add_relation_type_definition.assert_called_once_with(
            relation_type_def
        )

    def test_get_relation_type_delegates_and_returns(self):
        """Test get_relation_type delegates and returns value."""
        type_name = "RELATES_TO"
        expected_def = RelationTypeDefinition(
            name=type_name,
            source_object_type_names=["TestNodeA"],
            target_object_type_names=["TestNodeB"],
        )
        # Connect client
        self.grizabella_client.connect()
        self.mock_db_manager_instance.connect.assert_called_once()

        self.mock_db_manager_instance.get_relation_type_definition.return_value = expected_def

        result = self.grizabella_client.get_relation_type(type_name)
        # Corrected to check get_relation_type_definition
        self.mock_db_manager_instance.get_relation_type_definition.assert_called_once_with(
            type_name
        )
        self.assertEqual(result, expected_def)

    def test_delete_relation_type_delegates(self):
        """Test delete_relation_type delegates correctly."""
        type_name = "RELATES_TO_DELETE"
        self.grizabella_client.delete_relation_type(type_name)
        # Corrected to check remove_relation_type_definition
        self.mock_db_manager_instance.remove_relation_type_definition.assert_called_once_with(
            type_name
        )

    # --- Data Management (Objects) Method Tests (Example) ---
    def test_upsert_object_delegates_and_returns(self):
        """Test upsert_object delegates and returns the object."""
        obj_instance = ObjectInstance(
            object_type_name="TestNode", properties={"name": "Test Instance"}
        )
        # Assume manager might add/update ID or timestamps
        returned_obj_instance = obj_instance.model_copy(
            update={"id": uuid4()}
        )
        self.mock_db_manager_instance.upsert_object_instance.return_value = ( # Corrected manager method
            returned_obj_instance
        )

        result = self.grizabella_client.upsert_object(obj_instance)
        self.mock_db_manager_instance.upsert_object_instance.assert_called_once_with( # Corrected manager method
            obj_instance
        )
        self.assertEqual(result, returned_obj_instance)
        self.assertIsNot(result, obj_instance) # Ensure it's the returned one

    def test_get_object_by_id_delegates_and_returns(self):
        """Test get_object_by_id delegates and returns value."""
        obj_id = uuid4() # Keep as UUID object
        type_name = "TestNode"
        expected_obj = ObjectInstance(
            id=obj_id, object_type_name=type_name, properties={"name": "Found"}
        )
        self.mock_db_manager_instance.get_object_instance.return_value = expected_obj # Corrected manager method

        result = self.grizabella_client.get_object_by_id(str(obj_id), type_name) # Pass str for API
        self.mock_db_manager_instance.get_object_instance.assert_called_once_with( # Corrected manager method
            object_type_name=type_name, instance_id=str(obj_id)
        )
        self.assertEqual(result, expected_obj)

    def test_delete_object_delegates_and_returns_bool(self):
        """Test delete_object delegates and returns boolean status."""
        obj_id = uuid4()
        type_name = "TestNode"
        self.mock_db_manager_instance.delete_object_instance.return_value = True # Corrected manager method

        result = self.grizabella_client.delete_object(str(obj_id), type_name)
        self.mock_db_manager_instance.delete_object_instance.assert_called_once_with( # Corrected manager method
            object_type_name=type_name, instance_id=str(obj_id)
        )
        self.assertTrue(result)
        
        # Reset mock for second call assertion if it's a different scenario
        # For this test, it's fine as it's testing return value change
        self.mock_db_manager_instance.delete_object.return_value = False
        # We need to ensure the mock is called again if we expect a new call
        # For this specific test, we are testing the return value of the *same* conceptual call
        # but with a different mocked return. If it were two distinct calls in the test logic,
        # we'd need to be more careful or reset.
        # Let's assume the API allows calling delete on already deleted, and it would return False.
        # A more robust test might use different obj_id or reset mock.
        # For now, let's ensure the call count is as expected for the second scenario.
        # To be precise, we'd do:
        # self.mock_db_manager_instance.reset_mock()
        # self.mock_db_manager_instance.delete_object.return_value = False
        # result_fail = self.grizabella_client.delete_object(str(obj_id), type_name)
        # self.mock_db_manager_instance.delete_object.assert_called_once_with(str(obj_id), type_name)
        # self.assertFalse(result_fail)
        # However, the original test implies the manager is called twice with same args but different returns.
        # So, we'll check call_count if it's > 1 or use call_args_list.
        # For simplicity, let's assume the second call is intended.
        
        # To test the second scenario properly, let's use a different object ID or reset the mock
        # For this example, we'll assume the test means to check the return value on a subsequent call
        # to the *same* object ID, and the manager's behavior changes.
        # The previous call was `assert_called_once_with`. If we call again, it will fail.
        # So, we should use a new obj_id or reset the mock.
        # Let's use a new obj_id for clarity.
        
        obj_id_2 = uuid4()
        self.mock_db_manager_instance.delete_object_instance.return_value = False # Corrected manager method
        result_fail = self.grizabella_client.delete_object(str(obj_id_2), type_name)
        self.mock_db_manager_instance.delete_object_instance.assert_called_with( # Corrected manager method
            object_type_name=type_name, instance_id=str(obj_id_2) # Use assert_called_with for the second call
        )
        self.assertFalse(result_fail)


    def test_find_objects_delegates_and_returns_list(self):
        """Test find_objects delegates and returns a list of objects."""
        type_name = "TestNode"
        filter_criteria = {"status": "active"}
        limit = 10
        expected_objects = [
            ObjectInstance(object_type_name=type_name, properties={"name": "Obj1"}),
            ObjectInstance(object_type_name=type_name, properties={"name": "Obj2"}),
        ]
        self.mock_db_manager_instance.query_object_instances.return_value = expected_objects # Corrected manager method

        result = self.grizabella_client.find_objects(
            type_name, filter_criteria, limit
        )
        self.mock_db_manager_instance.query_object_instances.assert_called_once_with(
            object_type_name=type_name, conditions=filter_criteria, limit=limit
        )
        self.assertEqual(result, expected_objects)

    # --- Data Management (Relations) Method Tests (Example) ---
    def test_add_relation_delegates_and_returns(self):
        """Test add_relation delegates and returns the relation."""
        relation_instance = RelationInstance(
            relation_type_name="RELATES_TO",
            source_object_instance_id=uuid4(),
            target_object_instance_id=uuid4(),
            properties={"since": "2023"},
        )
        returned_relation = relation_instance.model_copy(update={"id": uuid4()})
        self.mock_db_manager_instance.add_relation_instance.return_value = returned_relation # Corrected manager method

        result = self.grizabella_client.add_relation(relation_instance)
        self.mock_db_manager_instance.add_relation_instance.assert_called_once_with( # Corrected manager method
            relation_instance
        )
        self.assertEqual(result, returned_relation)

    def test_get_relation_delegates_and_returns(self):
        """Test get_relation delegates and returns value."""
        from_id_uuid = uuid4()
        to_id_uuid = uuid4()
        from_id_str = str(from_id_uuid)
        to_id_str = str(to_id_uuid)
        rel_type = "KNOWS"
        expected_rel = RelationInstance(
            relation_type_name=rel_type,
            source_object_instance_id=from_id_uuid,
            target_object_instance_id=to_id_uuid,
            properties={}
        )
        # Connect client
        self.grizabella_client.connect()
        self.mock_db_manager_instance.connect.assert_called_once()

        self.mock_db_manager_instance.find_relation_instances.return_value = [expected_rel] # find_relation_instances returns a list
        result = self.grizabella_client.get_relation(from_id_str, to_id_str, rel_type)
        self.mock_db_manager_instance.find_relation_instances.assert_called_once_with(
            relation_type_name=rel_type,
            source_object_id=from_id_uuid,
            target_object_id=to_id_uuid,
        )
        # get_relation is documented to return List[RelationInstance]
        self.assertEqual(result, [expected_rel])

    def test_delete_relation_delegates_and_returns_bool(self):
        """Test delete_relation delegates and returns boolean status."""
        relation_id_uuid = uuid4()
        relation_id_str = str(relation_id_uuid)
        rel_type = "KNOWS"
        # Mock the correct underlying manager method
        self.mock_db_manager_instance.delete_relation_instance.return_value = True
        result = self.grizabella_client.delete_relation(rel_type, relation_id_str)
        # Assert the correct underlying manager method was called with correct args
        self.mock_db_manager_instance.delete_relation_instance.assert_called_once_with(
            relation_type_name=rel_type, relation_id=relation_id_uuid
        )
        self.assertTrue(result)

    def test_get_outgoing_relations_delegates(self):
        """Test get_outgoing_relations delegates and returns list."""
        obj_id_uuid = uuid4()
        obj_id_str = str(obj_id_uuid)
        type_name = "Person"
        rel_type_name = "FRIENDS_WITH"
        expected_relations = [
            RelationInstance(relation_type_name=rel_type_name, source_object_instance_id=obj_id_uuid, target_object_instance_id=uuid4())
        ]
        # Connect client
        self.grizabella_client.connect()
        self.mock_db_manager_instance.connect.assert_called_once()

        self.mock_db_manager_instance.find_relation_instances.return_value = expected_relations
        result = self.grizabella_client.get_outgoing_relations(obj_id_str, type_name, rel_type_name)
        self.mock_db_manager_instance.find_relation_instances.assert_called_once_with(
            relation_type_name=rel_type_name,
            source_object_id=obj_id_uuid
        )
        self.assertEqual(result, expected_relations)

    def test_get_incoming_relations_delegates(self):
        """Test get_incoming_relations delegates and returns list."""
        obj_id_uuid = uuid4()
        obj_id_str = str(obj_id_uuid)
        type_name = "Project"
        rel_type_name = "WORKS_ON"
        expected_relations = [
            RelationInstance(relation_type_name=rel_type_name, source_object_instance_id=uuid4(), target_object_instance_id=obj_id_uuid)
        ]
        # Connect client
        self.grizabella_client.connect()
        self.mock_db_manager_instance.connect.assert_called_once()

        self.mock_db_manager_instance.find_relation_instances.return_value = expected_relations
        result = self.grizabella_client.get_incoming_relations(obj_id_str, type_name, rel_type_name)
        self.mock_db_manager_instance.find_relation_instances.assert_called_once_with(
            relation_type_name=rel_type_name,
            target_object_id=obj_id_uuid
        )
        self.assertEqual(result, expected_relations)


    # --- Querying Method Tests (Example) ---
    def test_search_similar_objects_delegates_and_returns(self):
        """Test search_similar_objects delegates and returns results."""
        obj_id_uuid = uuid4()
        obj_id_str = str(obj_id_uuid)
        type_name = "Document"
        n_results = 3
        embedding_def_name = "content_embedding"
        search_props = [embedding_def_name]

        # Connect client
        self.grizabella_client.connect()
        # Assuming connect() might have been called in setUp or other tests,
        # we'll use assert_called() or ensure it's reset if strict once counts are needed here.
        # For this test, ensuring it's connected is key.
        # If this is the first connect call for this mock in this test method context:
        self.mock_db_manager_instance.connect.assert_called_once()


        # Mock get_embedding_definition
        mock_ed = EmbeddingDefinition(
            name=embedding_def_name,
            object_type_name=type_name, # Match type_name
            embedding_model="test_model", # Corrected parameter name
            source_property_name="text_content",
            dimensions=128
        )
        self.mock_db_manager_instance.get_embedding_definition.return_value = mock_ed

        mock_similar_obj = ObjectInstance(
            object_type_name=type_name, properties={"title": "Similar Doc"}
        )
        expected_results = [(mock_similar_obj, 0.95)]
        # Mock the correct underlying manager method
        self.mock_db_manager_instance.find_objects_similar_to_instance.return_value = (
            expected_results
        )

        result = self.grizabella_client.search_similar_objects(
            obj_id_str, type_name, n_results, search_props
        )

        # Assert get_embedding_definition was called
        self.mock_db_manager_instance.get_embedding_definition.assert_called_once_with(embedding_def_name)

        # Assert the correct underlying manager method was called
        self.mock_db_manager_instance.find_objects_similar_to_instance.assert_called_once_with(
            source_object_id=obj_id_uuid, # Client converts str to UUID
            source_object_type_name=type_name,
            embedding_definition_name=embedding_def_name,
            n_results=n_results,
        )
        self.assertEqual(result, expected_results)

    # --- Complex Query Method Tests ---
    def test_execute_complex_query_delegates_and_returns_result(self):
        """Test execute_complex_query delegates to manager and returns QueryResult."""
        sample_query = ComplexQuery(
            components=[QueryComponent(object_type_name="TestNode")]
        )
        expected_object_instance = ObjectInstance(id=uuid4(), object_type_name="TestNode", properties={"name": "Result Obj"})
        expected_query_result = QueryResult(
            object_instances=[expected_object_instance],
            errors=[]
        )

        # Test that DatabaseError is raised if not connected
        with self.assertRaisesRegex(DatabaseError, "Database not connected"):
            self.grizabella_client.execute_complex_query(sample_query)

        # Connect the client
        self.grizabella_client.connect()
        self.mock_db_manager_instance.connect.assert_called_once() # Ensure connect was called

        self.mock_db_manager_instance.process_complex_query.return_value = expected_query_result
        result = self.grizabella_client.execute_complex_query(sample_query)

        self.mock_db_manager_instance.process_complex_query.assert_called_once_with(sample_query)
        self.assertEqual(result, expected_query_result)
        self.assertIsInstance(result, QueryResult)
        self.assertEqual(len(result.object_instances), 1)
        self.assertEqual(result.object_instances[0], expected_object_instance)

    def test_execute_complex_query_propagates_exception(self):
        """Test execute_complex_query propagates exceptions from the manager."""
        sample_query = ComplexQuery(
            components=[QueryComponent(object_type_name="ErrorNode")]
        )
        # Using DatabaseError as a plausible exception from process_complex_query
        self.mock_db_manager_instance.process_complex_query.side_effect = DatabaseError("Complex query processing failed")

        # Connect the client first
        self.grizabella_client.connect()
        self.mock_db_manager_instance.connect.assert_called_once() # Ensure connect was called

        with self.assertRaisesRegex(DatabaseError, "Complex query processing failed"):
            self.grizabella_client.execute_complex_query(sample_query)
        
        self.mock_db_manager_instance.process_complex_query.assert_called_once_with(sample_query)


    # --- Exception Propagation Test (Example) ---
    # @patch("grizabella.api.client.GrizabellaDBManager")
    # def test_method_propagates_grizabella_exception(self, MockDBManagerExc):
    #     """Test that a GrizabellaException from manager is propagated."""
    #     mock_manager_instance_exc = MockDBManagerExc.return_value
    #     client_exc = Grizabella(db_name_or_path="exc_db")

    #     type_name = "ErrorNode"
    #     # Configure the mock method to raise a Grizabella-specific exception
    #     mock_manager_instance_exc.get_object_type.side_effect = GrizabellaException(
    #         "Manager error"
    #     )

    #     with self.assertRaisesRegex(GrizabellaException, "Manager error"):
    #         client_exc.get_object_type(type_name)

    #     mock_manager_instance_exc.get_object_type.assert_called_once_with(type_name)


if __name__ == "__main__":
    unittest.main()