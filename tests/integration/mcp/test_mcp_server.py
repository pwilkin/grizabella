import pytest
import json
from uuid import uuid4, UUID

from grizabella.core.models import ObjectTypeDefinition, PropertyDefinition, ObjectInstance, PropertyDataType, RelationInstance, RelationTypeDefinition

from mcp import ClientSession
from mcp.types import TextContent




# --- Test Cases ---

@pytest.mark.anyio
async def test_mcp_get_object_type_success(mcp_session: ClientSession):
    """Test successful retrieval of an object type via MCP."""
    type_name_to_get = "TestTypeIntegration"
    expected_obj_type_def = ObjectTypeDefinition(
        name=type_name_to_get,
        description="A test object type for integration testing",
        properties=[
            PropertyDefinition(name="prop1", data_type=PropertyDataType.TEXT, is_nullable=False)
        ],
    )

    # Setup and Teardown are managed via MCP calls to avoid direct DB access
    try:
        # Ensure clean state by deleting if it exists
        await mcp_session.call_tool("delete_object_type", arguments={"type_name": type_name_to_get})
        
        # Create the object type for the test
        await mcp_session.call_tool(
            "create_object_type",
            arguments={"object_type_def": expected_obj_type_def.model_dump()}
        )

        # Call the MCP tool to get the object type
        result = await mcp_session.call_tool(
            "get_object_type", arguments={"type_name": type_name_to_get}
        )

        # Assertions
        assert result is not None
        assert not result.isError
        assert result.content and len(result.content) == 1
        assert isinstance(result.content[0], TextContent)
        
        text_content = result.content[0].text
        assert text_content is not None
        returned_data = json.loads(text_content)
        parsed_result = ObjectTypeDefinition.model_validate(returned_data)
        
        assert parsed_result.name == expected_obj_type_def.name
        assert parsed_result.description == expected_obj_type_def.description
        assert len(parsed_result.properties) == 1
        assert parsed_result.properties[0].name == "prop1"

    finally:
        # Teardown: Clean up the created ObjectTypeDefinition
        await mcp_session.call_tool("delete_object_type", arguments={"type_name": type_name_to_get})


@pytest.mark.anyio
async def test_mcp_get_object_type_not_found(mcp_session: ClientSession):
    """Test retrieval of a non-existent object type via MCP."""
    type_name_to_get = "TrulyNonExistentTypeForMCPTest"

    # Ensure the type does not exist by attempting deletion
    await mcp_session.call_tool("delete_object_type", arguments={"type_name": type_name_to_get})

    result = await mcp_session.call_tool(
        "get_object_type", arguments={"type_name": type_name_to_get}
    )
    assert result is not None
    assert not result.isError
    assert result.content and len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    text_content = result.content[0].text
    assert text_content == "null"


@pytest.mark.anyio
async def test_mcp_upsert_object_success(mcp_session: ClientSession):
    """Test successful upsertion of an object via MCP."""
    test_id = uuid4()
    obj_type_name = "UserIntegrationTest"

    user_otd = ObjectTypeDefinition(
        name=obj_type_name,
        properties=[
            PropertyDefinition(name="name", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="email", data_type=PropertyDataType.TEXT)
        ]
    )
    
    expected_instance = ObjectInstance(
        id=test_id,
        object_type_name=obj_type_name,
        properties={"name": "Test User", "email": "test@example.com"}
    )

    try:
        # Setup: Ensure OTD exists, creating if necessary
        get_otd_res = await mcp_session.call_tool("get_object_type", {"type_name": obj_type_name})
        assert get_otd_res.content and isinstance(get_otd_res.content[0], TextContent)
        if get_otd_res.content[0].text == "null":
             await mcp_session.call_tool("create_object_type", {"object_type_def": user_otd.model_dump()})

        # Ensure object does not exist before upsert
        await mcp_session.call_tool("delete_object", {"object_id": str(test_id), "type_name": obj_type_name})

        # Call the MCP tool to upsert the object
        result = await mcp_session.call_tool(
            "upsert_object", arguments={"obj": expected_instance.model_dump()}
        )

        # Assertions on the upsert result
        assert result is not None
        assert not result.isError
        assert result.content and isinstance(result.content[0], TextContent)
        text_content = result.content[0].text
        assert text_content is not None
        parsed_result = ObjectInstance.model_validate(json.loads(text_content))
        assert parsed_result.id == expected_instance.id
        assert parsed_result.properties == expected_instance.properties

        # Verify directly by getting the object via another MCP call
        verify_res = await mcp_session.call_tool(
            "get_object_by_id", {"object_id": str(test_id), "type_name": obj_type_name}
        )
        assert verify_res.content and isinstance(verify_res.content[0], TextContent)
        verified_obj = ObjectInstance.model_validate(json.loads(verify_res.content[0].text))
        assert verified_obj.id == expected_instance.id
        assert verified_obj.properties == expected_instance.properties

    finally:
        # Teardown
        await mcp_session.call_tool("delete_object", {"object_id": str(test_id), "type_name": obj_type_name})
        await mcp_session.call_tool("delete_object_type", {"type_name": obj_type_name})

# TODO: Add more tests for other MCP operations:
# - Get/Delete ObjectByID
# - GetOutgoing/Incoming Relations
# - SearchSimilarObjects
# - ExecuteComplexQuery
# - Test error handling (e.g., GrizabellaException being raised and translated)

# Example of how to run tests with pytest:
# poetry run pytest tests/integration/mcp/test_mcp_server.py

@pytest.mark.anyio
async def test_mcp_relation_type_crud(mcp_session: ClientSession):
    """Test creating, getting, and deleting a RelationType via MCP."""
    relation_type_name = "WorksWith"
    from_obj_type = "Person"
    to_obj_type = "Company"

    # Define ObjectTypes first
    person_otd = ObjectTypeDefinition(name=from_obj_type, properties=[])
    company_otd = ObjectTypeDefinition(name=to_obj_type, properties=[])
    
    relation_type_def = RelationTypeDefinition(
        name=relation_type_name,
        source_object_type_names=[from_obj_type],
        target_object_type_names=[to_obj_type],
        properties=[]
    )

    try:
        # Setup: Ensure a clean state and create necessary object types
        await mcp_session.call_tool("delete_relation_type", {"type_name": relation_type_name})
        await mcp_session.call_tool("delete_object_type", {"type_name": from_obj_type})
        await mcp_session.call_tool("delete_object_type", {"type_name": to_obj_type})
        
        await mcp_session.call_tool("create_object_type", {"object_type_def": person_otd.model_dump()})
        await mcp_session.call_tool("create_object_type", {"object_type_def": company_otd.model_dump()})

        # 1. Create RelationType
        create_res = await mcp_session.call_tool(
            "create_relation_type", {"relation_type_def": relation_type_def.model_dump()}
        )
        assert not create_res.isError

        # 2. Get RelationType
        get_res = await mcp_session.call_tool("get_relation_type", {"type_name": relation_type_name})
        assert not get_res.isError
        assert get_res.content and isinstance(get_res.content[0], TextContent)
        
        returned_data = json.loads(get_res.content[0].text)
        parsed_result = RelationTypeDefinition.model_validate(returned_data)
        
        assert parsed_result.name == relation_type_name
        assert parsed_result.source_object_type_names == [from_obj_type]
        assert parsed_result.target_object_type_names == [to_obj_type]

        # 3. Delete RelationType
        delete_res = await mcp_session.call_tool("delete_relation_type", {"type_name": relation_type_name})
        assert not delete_res.isError

        # Verify deletion
        get_after_delete_res = await mcp_session.call_tool("get_relation_type", {"type_name": relation_type_name})
        assert not get_after_delete_res.isError
        assert get_after_delete_res.content and isinstance(get_after_delete_res.content[0], TextContent)
        assert get_after_delete_res.content[0].text == "null"

    finally:
        # Teardown
        await mcp_session.call_tool("delete_relation_type", {"type_name": relation_type_name})
        await mcp_session.call_tool("delete_object_type", {"type_name": from_obj_type})
        await mcp_session.call_tool("delete_object_type", {"type_name": to_obj_type})

@pytest.mark.anyio
async def test_mcp_relation_instance_crud(mcp_session: ClientSession):
    """Test creating, getting, and deleting a RelationInstance via MCP."""
    # Define names
    person_type_name = "Dev"
    company_type_name = "TechCorp"
    works_at_relation_name = "WORKS_AT"

    # Define OTDs
    person_otd = ObjectTypeDefinition(name=person_type_name, properties=[PropertyDefinition(name="name", data_type=PropertyDataType.TEXT)])
    company_otd = ObjectTypeDefinition(name=company_type_name, properties=[PropertyDefinition(name="name", data_type=PropertyDataType.TEXT)])

    # Define RTD
    works_at_rtd = RelationTypeDefinition(
        name=works_at_relation_name,
        source_object_type_names=[person_type_name],
        target_object_type_names=[company_type_name],
        properties=[]
    )

    # Define Instances
    person_id = uuid4()
    company_id = uuid4()
    person_instance = ObjectInstance(id=person_id, object_type_name=person_type_name, properties={"name": "Alex"})
    company_instance = ObjectInstance(id=company_id, object_type_name=company_type_name, properties={"name": "Grizabella Inc."})
    
    relation_instance = RelationInstance(
        relation_type_name=works_at_relation_name,
        source_object_instance_id=person_id,
        target_object_instance_id=company_id,
        properties={}
    )

    try:
        # Setup: Clean slate and create schema
        await mcp_session.call_tool("delete_relation_type", {"type_name": works_at_relation_name})
        await mcp_session.call_tool("delete_object_type", {"type_name": person_type_name})
        await mcp_session.call_tool("delete_object_type", {"type_name": company_type_name})

        await mcp_session.call_tool("create_object_type", {"object_type_def": person_otd.model_dump()})
        await mcp_session.call_tool("create_object_type", {"object_type_def": company_otd.model_dump()})
        await mcp_session.call_tool("create_relation_type", {"relation_type_def": works_at_rtd.model_dump()})

        # Create object instances
        await mcp_session.call_tool("upsert_object", {"obj": person_instance.model_dump()})
        await mcp_session.call_tool("upsert_object", {"obj": company_instance.model_dump()})

        # 1. Add Relation
        add_res = await mcp_session.call_tool("add_relation", {"relation": relation_instance.model_dump()})
        assert not add_res.isError
        assert add_res.content and isinstance(add_res.content[0], TextContent)
        added_relation = RelationInstance.model_validate(json.loads(add_res.content[0].text))
        relation_id_to_delete = str(added_relation.id)


        # 2. Get Relation
        get_res = await mcp_session.call_tool(
            "get_relation",
            {
                "from_object_id": str(person_id),
                "to_object_id": str(company_id),
                "relation_type_name": works_at_relation_name,
            },
        )
        assert not get_res.isError
        assert get_res.content and isinstance(get_res.content[0], TextContent)
        # The result is a RelationInstanceList
        relations_list_data = json.loads(get_res.content[0].text)
        assert len(relations_list_data["relations"]) == 1
        retrieved_relation = RelationInstance.model_validate(relations_list_data["relations"][0])
        assert retrieved_relation.source_object_instance_id == person_id
        assert retrieved_relation.target_object_instance_id == company_id

        # 3. Delete Relation
        delete_res = await mcp_session.call_tool(
            "delete_relation",
            {"relation_type_name": works_at_relation_name, "relation_id": relation_id_to_delete},
        )
        assert not delete_res.isError

        # Verify Deletion
        get_after_delete_res = await mcp_session.call_tool(
            "get_relation",
            {
                "from_object_id": str(person_id),
                "to_object_id": str(company_id),
                "relation_type_name": works_at_relation_name,
            },
        )
        assert not get_after_delete_res.isError
        assert get_after_delete_res.content and isinstance(get_after_delete_res.content[0], TextContent)
        relations_list_after_delete = json.loads(get_after_delete_res.content[0].text)
        assert len(relations_list_after_delete["relations"]) == 0

    finally:
        # Teardown
        await mcp_session.call_tool("delete_object", {"object_id": str(person_id), "type_name": person_type_name})
        await mcp_session.call_tool("delete_object", {"object_id": str(company_id), "type_name": company_type_name})
        await mcp_session.call_tool("delete_relation_type", {"type_name": works_at_relation_name})
        await mcp_session.call_tool("delete_object_type", {"type_name": person_type_name})
        await mcp_session.call_tool("delete_object_type", {"type_name": company_type_name})
@pytest.mark.anyio
async def test_mcp_find_objects(mcp_session: ClientSession):
    """Test finding objects with filter criteria via MCP."""
    obj_type_name = "FindableObject"
    otd = ObjectTypeDefinition(
        name=obj_type_name,
        properties=[
            PropertyDefinition(name="name", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="value", data_type=PropertyDataType.INTEGER),
        ],
    )

    obj1_id = uuid4()
    obj2_id = uuid4()
    obj3_id = uuid4()

    obj1 = ObjectInstance(id=obj1_id, object_type_name=obj_type_name, properties={"name": "obj1", "value": 10})
    obj2 = ObjectInstance(id=obj2_id, object_type_name=obj_type_name, properties={"name": "obj2", "value": 20})
    obj3 = ObjectInstance(id=obj3_id, object_type_name=obj_type_name, properties={"name": "obj3", "value": 20})

    try:
        # Setup
        await mcp_session.call_tool("delete_object_type", {"type_name": obj_type_name})
        await mcp_session.call_tool("create_object_type", {"object_type_def": otd.model_dump()})
        await mcp_session.call_tool("upsert_object", {"obj": obj1.model_dump()})
        await mcp_session.call_tool("upsert_object", {"obj": obj2.model_dump()})
        await mcp_session.call_tool("upsert_object", {"obj": obj3.model_dump()})

        # First, get all objects to ensure they are there
        all_objects_res = await mcp_session.call_tool("find_objects", arguments={"type_name": obj_type_name})
        print("All objects response:", all_objects_res)

        # Find objects with value 20
        find_args = {
            "type_name": obj_type_name,
            "filter_criteria": {"value": 20},
            "limit": 5
        }
        
        find_res = await mcp_session.call_tool("find_objects", arguments=find_args)
        
        assert not find_res.isError
        assert find_res.content and isinstance(find_res.content[0], TextContent)
        
        results_data = [json.loads(c.text) for c in find_res.content if isinstance(c, TextContent)]
        print("Filtered results data:", results_data)
        assert len(results_data) == 2
        
        result_ids = {UUID(item["id"]) for item in results_data}
        assert obj2_id in result_ids
        assert obj3_id in result_ids
        assert obj1_id not in result_ids

    finally:
        # Teardown
        await mcp_session.call_tool("delete_object_type", {"type_name": obj_type_name})