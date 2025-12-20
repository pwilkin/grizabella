import unittest
import os
import shutil
from pathlib import Path
from uuid import uuid4
from decimal import Decimal
from grizabella.api.client import Grizabella
from grizabella.core.models import ObjectTypeDefinition, ObjectInstance, PropertyDataType, RelationTypeDefinition, RelationInstance

class TestKuzuIntegration(unittest.TestCase):
    """Integration tests for Kuzu (LadybugDB) adapter."""

    def setUp(self):
        self.db_path = (Path.cwd() / "kuzu_integration_db").resolve()
        if self.db_path.exists():
            shutil.rmtree(self.db_path)
        # Initialize Grizabella
        self.gb = Grizabella(db_name_or_path=self.db_path, create_if_not_exists=True)
        self.gb.connect()

    def tearDown(self):
        self.gb.close()
        if self.db_path.exists():
            try:
                shutil.rmtree(self.db_path)
            except OSError:
                pass # Ignore errors if directory is busy

    def test_kuzu_basic_operations(self):
        """Test basic Kuzu operations: type creation, object upsert, relations."""
        # 1. Create Object Types
        person_otd = ObjectTypeDefinition(
            name="Person",
            description="A system user",
            properties=[
                {"name": "username", "data_type": PropertyDataType.TEXT, "is_nullable": False}
            ]
        )
        self.gb.create_object_type(person_otd)

        org_otd = ObjectTypeDefinition(
            name="Org",
            description="A user group",
            properties=[
                {"name": "org_name", "data_type": PropertyDataType.TEXT, "is_nullable": False}
            ]
        )
        self.gb.create_object_type(org_otd)

        # 2. Create Relation Type
        member_of_rtd = RelationTypeDefinition(
            name="MemberOf",
            description="User is a member of an organization",
            source_object_type_names=["Person"],
            target_object_type_names=["Org"],
            properties=[]
        )
        self.gb.create_relation_type(member_of_rtd)

        # 3. Create Instances
        person_id = uuid4()
        person_instance = ObjectInstance(
            id=person_id,
            object_type_name="Person",
            properties={"username": "alice"},
            weight=Decimal("1.0")
        )
        self.gb.upsert_object(person_instance)

        org_id = uuid4()
        org_instance = ObjectInstance(
            id=org_id,
            object_type_name="Org",
            properties={"org_name": "admins"},
            weight=Decimal("1.0")
        )
        self.gb.upsert_object(org_instance)

        # 4. Create Relation
        rel_instance = RelationInstance(
            id=uuid4(),
            relation_type_name="MemberOf",
            source_object_instance_id=person_id,
            target_object_instance_id=org_id,
            weight=Decimal("1.0")
        )
        self.gb.add_relation(rel_instance)

        # 5. Verify data retrieval (via relations)
        outgoing = self.gb.get_outgoing_relations(str(person_id), "Person", "MemberOf")
        self.assertEqual(len(outgoing), 1)
        self.assertEqual(outgoing[0].target_object_instance_id, org_id)

        incoming = self.gb.get_incoming_relations(str(org_id), "Org", "MemberOf")
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].source_object_instance_id, person_id)

if __name__ == "__main__":
    unittest.main()
