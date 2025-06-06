import pytest
import tempfile
import shutil
import uuid
import logging
import warnings
from pathlib import Path
import json
from contextlib import AsyncExitStack
from typing import Optional, Dict
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from grizabella.core.models import (
    ObjectTypeDefinition, PropertyDefinition, PropertyDataType,
    EmbeddingDefinition, RelationTypeDefinition, ObjectInstance, RelationInstance, RelationInstanceList
)
from grizabella.core.query_models import (
    ComplexQuery, QueryComponent, RelationalFilter,
    EmbeddingSearchClause, GraphTraversalClause, QueryResult, EmbeddingVector,
    LogicalGroup, NotClause, LogicalOperator
)


# A container for test state
class E2EState:
    def __init__(self):
        self.db_dir: Optional[str] = None
        self.db_path: Optional[Path] = None
        self.server_script: str = "grizabella/mcp/server.py"
        self.ids: Dict[str, uuid.UUID] = {}
        self.fixed_paper_id_4: uuid.UUID = uuid.uuid4()
        self.session: Optional[ClientSession] = None

    def _generate_ids(self):
        self.ids["author_1"] = uuid.uuid4()
        self.ids["author_2"] = uuid.uuid4()
        self.ids["author_3"] = uuid.uuid4()
        self.ids["venue_1"] = uuid.uuid4()
        self.ids["venue_2"] = uuid.uuid4()
        self.ids["paper_1"] = uuid.uuid4()
        self.ids["paper_2"] = uuid.uuid4()
        self.ids["paper_3"] = uuid.uuid4()
        self.ids["paper_4"] = self.fixed_paper_id_4


@pytest.fixture
async def state():
    """
    Manages the state for the test, including setting up and tearing down
    the database and MCP session.
    """
    test_state = E2EState()
    test_state.db_dir = tempfile.mkdtemp(prefix="grizabella_mcp_e2e_")
    test_state.db_path = Path(test_state.db_dir) / "e2e_mcp_test_db"
    test_state._generate_ids()

    async with AsyncExitStack() as stack:
        server_args = [test_state.server_script, "--db-path", str(test_state.db_path)]
        params = StdioServerParameters(command="python", args=server_args)
        reader, writer = await stack.enter_async_context(stdio_client(params))  # type: ignore
        test_state.session = await stack.enter_async_context(ClientSession(reader, writer))
        await test_state.session.initialize()

        await _define_schema(test_state)
        await _populate_data(test_state)

        yield test_state

    if Path(test_state.db_dir).exists():
        shutil.rmtree(test_state.db_dir)


async def _define_schema(state: E2EState):
    assert state.session is not None
    author_otd = ObjectTypeDefinition(
        name="Author",
        description="Represents a researcher or author of a scientific paper.",
        properties=[
            PropertyDefinition(name="full_name", data_type=PropertyDataType.TEXT, is_indexed=True, is_nullable=False),
            PropertyDefinition(name="email", data_type=PropertyDataType.TEXT, is_unique=True, is_nullable=True),
            PropertyDefinition(name="birth_year", data_type=PropertyDataType.INTEGER, is_nullable=True),
        ]
    )
    paper_otd = ObjectTypeDefinition(
        name="Paper",
        description="Represents a scientific publication.",
        properties=[
            PropertyDefinition(name="title", data_type=PropertyDataType.TEXT, is_indexed=True, is_nullable=False),
            PropertyDefinition(name="abstract", data_type=PropertyDataType.TEXT, is_nullable=True),
            PropertyDefinition(name="publication_year", data_type=PropertyDataType.INTEGER, is_indexed=True, is_nullable=False),
            PropertyDefinition(name="doi", data_type=PropertyDataType.TEXT, is_unique=True, is_nullable=True),
        ]
    )
    venue_otd = ObjectTypeDefinition(
        name="Venue",
        description="Represents a journal, conference, or workshop where papers are published.",
        properties=[
            PropertyDefinition(name="venue_name", data_type=PropertyDataType.TEXT, is_indexed=True, is_unique=True, is_nullable=False),
            PropertyDefinition(name="venue_type", data_type=PropertyDataType.TEXT, is_indexed=True, is_nullable=False),
            PropertyDefinition(name="city", data_type=PropertyDataType.TEXT, is_nullable=True),
        ]
    )
    await state.session.call_tool("create_object_type", {"object_type_def": author_otd})
    await state.session.call_tool("create_object_type", {"object_type_def": paper_otd})
    await state.session.call_tool("create_object_type", {"object_type_def": venue_otd})

    paper_abstract_ed = EmbeddingDefinition(
        name="PaperAbstractEmbedding",
        object_type_name="Paper",
        source_property_name="abstract",
        embedding_model="colbert-ir/colbertv2.0",
        description="Embedding for the abstract of papers."
    )
    await state.session.call_tool("create_embedding_definition", {"embedding_def": paper_abstract_ed})

    authored_by_rtd = RelationTypeDefinition(
        name="AUTHORED_BY",
        description="Connects a Paper to its Author(s).",
        source_object_type_names=["Paper"],
        target_object_type_names=["Author"],
        properties=[PropertyDefinition(name="author_order", data_type=PropertyDataType.INTEGER, is_nullable=True)]
    )
    cites_rtd = RelationTypeDefinition(
        name="CITES",
        description="Connects a Paper to another Paper it cites.",
        source_object_type_names=["Paper"],
        target_object_type_names=["Paper"],
        properties=[PropertyDefinition(name="citation_context", data_type=PropertyDataType.TEXT, is_nullable=True)]
    )
    published_in_rtd = RelationTypeDefinition(
        name="PUBLISHED_IN",
        description="Connects a Paper to the Venue it was published in.",
        source_object_type_names=["Paper"],
        target_object_type_names=["Venue"],
        properties=[]
    )
    await state.session.call_tool("create_relation_type", {"relation_type_def": authored_by_rtd})
    await state.session.call_tool("create_relation_type", {"relation_type_def": cites_rtd})
    await state.session.call_tool("create_relation_type", {"relation_type_def": published_in_rtd})


async def _populate_data(state: E2EState):
    assert state.session is not None
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["author_1"], object_type_name="Author", properties={"full_name": "Dr. Alice Wonderland", "email": "alice@example.com", "birth_year": 1980}).model_dump()})
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["author_2"], object_type_name="Author", properties={"full_name": "Dr. Bob The Builder", "email": "bob@example.com", "birth_year": 1975}).model_dump()})
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["author_3"], object_type_name="Author", properties={"full_name": "Dr. Carol Danvers", "email": "carol@example.com", "birth_year": 1985}).model_dump()})
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["venue_1"], object_type_name="Venue", properties={"venue_name": "Journal of Fantastical AI", "venue_type": "Journal", "city": "Virtual"}).model_dump()})
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["venue_2"], object_type_name="Venue", properties={"venue_name": "Conference on Practical Magic", "venue_type": "Conference", "city": "New Orleans"}).model_dump()})
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["paper_1"], object_type_name="Paper", properties={"title": "Advanced Gryphon Behavior", "abstract": "This seminal paper explores the intricate and often misunderstood social structures within modern gryphon populations.", "publication_year": 2023, "doi": "10.1000/jfa.2023.001"}).model_dump()})
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["paper_2"], object_type_name="Paper", properties={"title": "The Aerodynamics of Broomsticks", "abstract": "An in-depth computational and experimental study of broomstick flight dynamics.", "publication_year": 2022, "doi": "10.2000/cpm.2022.002"}).model_dump()})
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["paper_3"], object_type_name="Paper", properties={"title": "Quantum Entanglement in Potion Brewing", "abstract": "We investigate the previously hypothesized role of quantum mechanical effects in the efficacy of advanced potion-making.", "publication_year": 2023, "doi": "10.1000/jfa.2023.003"}).model_dump()})
    await state.session.call_tool("upsert_object", {"obj": ObjectInstance(id=state.ids["paper_4"], object_type_name="Paper", properties={"title": "A History of Mythical Creatures", "abstract": "A foundational text on the historical study of mythical creatures.", "publication_year": 2010, "doi": "10.3000/hmc.2010.004"}).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="AUTHORED_BY", source_object_instance_id=state.ids["paper_1"], target_object_instance_id=state.ids["author_1"], properties={"author_order": 1}).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="AUTHORED_BY", source_object_instance_id=state.ids["paper_1"], target_object_instance_id=state.ids["author_2"], properties={"author_order": 2}).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="AUTHORED_BY", source_object_instance_id=state.ids["paper_2"], target_object_instance_id=state.ids["author_2"], properties={"author_order": 1}).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="AUTHORED_BY", source_object_instance_id=state.ids["paper_3"], target_object_instance_id=state.ids["author_1"], properties={"author_order": 1}).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="AUTHORED_BY", source_object_instance_id=state.ids["paper_3"], target_object_instance_id=state.ids["author_3"], properties={"author_order": 2}).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="AUTHORED_BY", source_object_instance_id=state.ids["paper_4"], target_object_instance_id=state.ids["author_3"], properties={"author_order": 1}).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="CITES", source_object_instance_id=state.ids["paper_1"], target_object_instance_id=state.ids["paper_4"]).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="CITES", source_object_instance_id=state.ids["paper_3"], target_object_instance_id=state.ids["paper_2"]).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="PUBLISHED_IN", source_object_instance_id=state.ids["paper_1"], target_object_instance_id=state.ids["venue_1"]).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="PUBLISHED_IN", source_object_instance_id=state.ids["paper_2"], target_object_instance_id=state.ids["venue_2"]).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="PUBLISHED_IN", source_object_instance_id=state.ids["paper_3"], target_object_instance_id=state.ids["venue_1"]).model_dump()})
    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="PUBLISHED_IN", source_object_instance_id=state.ids["paper_4"], target_object_instance_id=state.ids["venue_1"]).model_dump()})


async def _get_embedding_vector_for_query_text(state: E2EState, text_to_embed, embedding_def_name="PaperAbstractEmbedding"):
    assert state.session is not None
    res = await state.session.call_tool(
        "get_embedding_vector_for_text",
        {"args": {"text_to_embed": text_to_embed, "embedding_definition_name": embedding_def_name}}
    )
    if res.content and isinstance(res.content[0], TextContent):
        embedding_vector_model = EmbeddingVector(**json.loads(res.content[0].text))
        return embedding_vector_model.vector
    raise TypeError("Expected TextContent")


async def _run_initial_queries(state: E2EState):
    assert state.session is not None
    q1_text = "gryphon social structures"
    q1_vector = await _get_embedding_vector_for_query_text(state, q1_text)
    query1 = ComplexQuery(
        description="Alice's 2023 papers on gryphon social behavior",
        components=[
            QueryComponent(
                object_type_name="Paper",
                relational_filters=[RelationalFilter(property_name="publication_year", operator="==", value=2023)],
                embedding_searches=[EmbeddingSearchClause(embedding_definition_name="PaperAbstractEmbedding", similar_to_payload=q1_vector, limit=1)],
                graph_traversals=[GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Alice Wonderland")])]
            )
        ]
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result_q1 = await state.session.call_tool("execute_complex_query", {"query": query1})
        if w:
            for warning in w:
                logging.warning(f"Caught warning: {warning.message}", exc_info=True)
    if result_q1.content and isinstance(result_q1.content[0], TextContent):
        _assert_results(result_q1.content[0].text, [state.ids["paper_1"]], "Initial Query 1")

    query2 = ComplexQuery(
        description="Papers by Bob & Alice citing Paper 4",
        components=[
            QueryComponent(
                object_type_name="Paper",
                graph_traversals=[
                    GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Bob The Builder")]),
                    GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Alice Wonderland")]),
                    GraphTraversalClause(relation_type_name="CITES", direction="outgoing", target_object_type_name="Paper", target_object_id=state.ids["paper_4"])
                ]
            )
        ]
    )
    result_q2 = await state.session.call_tool("execute_complex_query", {"query": query2})
    if result_q2.content and isinstance(result_q2.content[0], TextContent):
        _assert_results(result_q2.content[0].text, [state.ids["paper_1"]], "Initial Query 2")


async def _modify_data(state: E2EState):
    assert state.session is not None
    paper1_res = await state.session.call_tool("get_object_by_id", {"object_id": str(state.ids["paper_1"]), "type_name": "Paper"})
    if paper1_res.content and isinstance(paper1_res.content[0], TextContent):
        paper1_to_update = ObjectInstance(**json.loads(paper1_res.content[0].text))
        paper1_to_update.properties["abstract"] = "A new study on dragon linguistics."
        await state.session.call_tool("upsert_object", {"obj": paper1_to_update.model_dump()})

    await state.session.call_tool("add_relation", {"relation": RelationInstance(relation_type_name="CITES", source_object_instance_id=state.ids["paper_2"], target_object_instance_id=state.ids["paper_4"]).model_dump()})

    relations_to_delete_res = await state.session.call_tool("get_relation", {"from_object_id": str(state.ids["paper_1"]), "to_object_id": str(state.ids["author_2"]), "relation_type_name": "AUTHORED_BY"})
    if relations_to_delete_res.content and isinstance(relations_to_delete_res.content[0], TextContent):
        relation_list_model = RelationInstanceList(**json.loads(relations_to_delete_res.content[0].text))
        for rel_to_delete in relation_list_model.relations:
            await state.session.call_tool("delete_relation", {"relation_type_name": "AUTHORED_BY", "relation_id": str(rel_to_delete.id)})


async def _run_post_modification_queries(state: E2EState):
    assert state.session is not None
    q1_text = "gryphon social structures"
    q1_vector = await _get_embedding_vector_for_query_text(state, q1_text)
    query1_mod = ComplexQuery(
        description="Alice's 2023 papers on gryphon social behavior (Post-Mod)",
        components=[
            QueryComponent(
                object_type_name="Paper",
                relational_filters=[RelationalFilter(property_name="publication_year", operator="==", value=2023)],
                embedding_searches=[EmbeddingSearchClause(embedding_definition_name="PaperAbstractEmbedding", similar_to_payload=q1_vector, limit=1)],
                graph_traversals=[GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Alice Wonderland")])]
            )
        ]
    )
    result_q1_mod = await state.session.call_tool("execute_complex_query", {"query": query1_mod})
    if result_q1_mod.content and isinstance(result_q1_mod.content[0], TextContent):
        _assert_results(result_q1_mod.content[0].text, [], "Post-Mod Query 1")

    query2_mod = ComplexQuery(
        description="Papers by Bob & Alice citing Paper 4 (Post-Mod)",
        components=[
            QueryComponent(
                object_type_name="Paper",
                graph_traversals=[
                    GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Bob The Builder")]),
                    GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Alice Wonderland")]),
                    GraphTraversalClause(relation_type_name="CITES", direction="outgoing", target_object_type_name="Paper", target_object_id=state.ids["paper_4"])
                ]
            )
        ]
    )
    result_q2_mod = await state.session.call_tool("execute_complex_query", {"query": query2_mod})
    if result_q2_mod.content and isinstance(result_q2_mod.content[0], TextContent):
        _assert_results(result_q2_mod.content[0].text, [], "Post-Mod Query 2")

    query4 = ComplexQuery(
        description="Papers in CPM citing Paper 4",
        components=[
            QueryComponent(
                object_type_name="Paper",
                graph_traversals=[
                    GraphTraversalClause(relation_type_name="CITES", direction="outgoing", target_object_type_name="Paper", target_object_id=state.ids["paper_4"]),
                    GraphTraversalClause(relation_type_name="PUBLISHED_IN", direction="outgoing", target_object_type_name="Venue", target_object_id=state.ids["venue_2"])
                ]
            )
        ]
    )
    result_q4 = await state.session.call_tool("execute_complex_query", {"query": query4})
    if result_q4.content and isinstance(result_q4.content[0], TextContent):
        _assert_results(result_q4.content[0].text, [state.ids["paper_2"]], "Post-Mod Query 4")


def _assert_results(query_result_json: str, expected_ids: list[uuid.UUID], description: str):
    query_result_dict = json.loads(query_result_json)
    query_result = QueryResult(**query_result_dict)
    assert query_result is not None, f"Query result for '{description}' should not be None."
    if query_result.errors:
        pytest.fail(f"Query '{description}' failed with errors: {query_result.errors}")
    
    fetched_ids = {uuid.UUID(obj['id']) for obj in query_result_dict['object_instances']}
    expected_id_set = set(expected_ids)
    
    assert fetched_ids == expected_id_set, (
        f"Mismatch in expected results for query '{description}'. "
        f"Expected: {expected_id_set}, Got: {fetched_ids}"
    )


async def _run_logical_queries(state: E2EState):
    """
    Runs tests for complex logical queries (AND, OR, NOT) and backward compatibility.
    """
    assert state.session is not None

    # 1. Test a complex nested query: (A AND B) OR (C AND NOT D)
    # A = publication_year == 2023 -> {paper_1, paper_3}
    # B = published in "Journal of Fantastical AI" -> {paper_1, paper_3, paper_4}
    # A AND B -> {paper_1, paper_3}
    component_A = QueryComponent(
        object_type_name="Paper",
        relational_filters=[RelationalFilter(property_name="publication_year", operator="==", value=2023)]
    )
    component_B = QueryComponent(
        object_type_name="Paper",
        graph_traversals=[GraphTraversalClause(relation_type_name="PUBLISHED_IN", direction="outgoing", target_object_type_name="Venue", target_object_id=state.ids["venue_1"])]
    )
    
    # C = publication_year == 2022 -> {paper_2}
    # D = authored by Dr. Carol Danvers -> {paper_3, paper_4}
    # NOT D -> {paper_1, paper_2}
    # C AND (NOT D) -> {paper_2}
    component_C = QueryComponent(
        object_type_name="Paper",
        relational_filters=[RelationalFilter(property_name="publication_year", operator="==", value=2022)]
    )
    component_D = QueryComponent(
        object_type_name="Paper",
        graph_traversals=[GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Carol Danvers")])]
    )

    # Final Query: (A AND B) OR (C AND NOT D) -> {paper_1, paper_3} U {paper_2} -> {paper_1, paper_2, paper_3}
    logical_query = ComplexQuery(
        description="Complex logical query: (year=2023 AND venue=JFA) OR (year=2022 AND NOT author=Carol)",
        query_root=LogicalGroup(
            operator=LogicalOperator.OR,
            clauses=[
                LogicalGroup(
                    operator=LogicalOperator.AND,
                    clauses=[component_A, component_B]
                ),
                LogicalGroup(
                    operator=LogicalOperator.AND,
                    clauses=[
                        component_C,
                        NotClause(clause=component_D)
                    ]
                )
            ]
        )
    )

    result_logical = await state.session.call_tool("execute_complex_query", {"query": logical_query.model_dump()})
    if result_logical.content and isinstance(result_logical.content[0], TextContent):
        _assert_results(
            result_logical.content[0].text,
            [state.ids["paper_1"], state.ids["paper_2"], state.ids["paper_3"]],
            "Complex Logical Query"
        )

    # 2. Test backward compatibility with the `components` field (implicit AND)
    # Query: Papers published in 2023 AND authored by "Dr. Alice Wonderland"
    # Expected: {paper_1, paper_3}
    
    # Using old `components` field
    query_backward_compat = ComplexQuery(
        description="Backward compatibility test with 'components'",
        components=[
            QueryComponent(
                object_type_name="Paper",
                relational_filters=[RelationalFilter(property_name="publication_year", operator="==", value=2023)]
            ),
            QueryComponent(
                object_type_name="Paper",
                graph_traversals=[GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Alice Wonderland")])]
            )
        ]
    )
    
    result_backward_compat = await state.session.call_tool("execute_complex_query", {"query": query_backward_compat.model_dump()})
    
    # Using new `query_root` field for the same AND query
    query_new_and = ComplexQuery(
        description="New explicit AND query with 'query_root'",
        query_root=LogicalGroup(
            operator=LogicalOperator.AND,
            clauses=[
                QueryComponent(
                    object_type_name="Paper",
                    relational_filters=[RelationalFilter(property_name="publication_year", operator="==", value=2023)]
                ),
                QueryComponent(
                    object_type_name="Paper",
                    graph_traversals=[GraphTraversalClause(relation_type_name="AUTHORED_BY", direction="outgoing", target_object_type_name="Author", target_object_properties=[RelationalFilter(property_name="full_name", operator="==", value="Dr. Alice Wonderland")])]
                )
            ]
        )
    )
    
    result_new_and = await state.session.call_tool("execute_complex_query", {"query": query_new_and.model_dump()})

    # Assert all results are the same and correct
    expected_ids_and_query = [state.ids["paper_1"], state.ids["paper_3"]]
    
    backward_compat_json = ""
    if result_backward_compat.content and isinstance(result_backward_compat.content[0], TextContent):
        backward_compat_json = result_backward_compat.content[0].text
        _assert_results(backward_compat_json, expected_ids_and_query, "Backward Compatibility Query")
    
    new_and_json = ""
    if result_new_and.content and isinstance(result_new_and.content[0], TextContent):
        new_and_json = result_new_and.content[0].text
        _assert_results(new_and_json, expected_ids_and_query, "New AND Query")

    # Also check that the JSON results are identical
    assert backward_compat_json and new_and_json and backward_compat_json == new_and_json, \
        "Backward compatible query result should match new explicit AND query result"


@pytest.mark.anyio
async def test_full_e2e_scenario(state: E2EState):
    """
    End-to-end test for the Grizabella engine via the MCP server.
    """
    await _run_initial_queries(state)
    await _run_logical_queries(state)
    await _modify_data(state)
    await _run_post_modification_queries(state)