"""Grizabella MCP Server.

This module provides an MCP (Model Context Protocol) server for Grizabella,
exposing its core functionalities as tools that can be called remotely.
It uses FastMCP to define and serve these tools.

Server Description: This MCP server exposes the core functionalities of the Grizabella
knowledge management system, allowing for the creation, retrieval, and querying of
structured data objects and their relationships.
"""

import argparse
import logging
import os
import signal
import sys
import threading
import time
import uuid
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from fastmcp import FastMCP

# from mcp import ToolContext # MCPTool is not needed when using @app.tool decorator. ToolContext
# might be injected.
from pydantic import BaseModel

from grizabella.api.client import Grizabella
from grizabella.core.exceptions import GrizabellaException, SchemaError
from grizabella.core.models import (
    EmbeddingDefinition,
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDataType,
    RelationInstance,
    RelationInstanceList,
    RelationTypeDefinition,
)
from grizabella.core.query_models import ComplexQuery, EmbeddingVector, QueryResult

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# --- Configuration ---
GRIZABELLA_DB_PATH_ENV_VAR = "GRIZABELLA_DB_PATH"
DEFAULT_GRIZABELLA_DB_PATH = "grizabella_mcp_db"


def get_grizabella_db_path(db_path_arg: Optional[str] = None) -> Union[str, Path]:
    """Determines the database path from arg, env var, or default."""
    if db_path_arg:
        return db_path_arg
    return os.getenv(GRIZABELLA_DB_PATH_ENV_VAR, DEFAULT_GRIZABELLA_DB_PATH)


# --- Pydantic Models for Request Bodies (if not directly using core models) ---
# FastMCP might handle Pydantic models directly. If so, these might not be strictly necessary
# but can be useful for defining clear API contracts for the MCP tools.
# For now, we'll assume FastMCP can use the core Pydantic models from grizabella.core

# --- MCP Application ---
app = FastMCP(name="Grizabella", instructions="A tri-layer memory management system with a relational database, an embedding database and a graph database layer.")

# --- Grizabella Client Singleton ---
# This will be initialized in the main() function before the app runs.
grizabella_client_instance: Optional[Grizabella] = None

def get_grizabella_client() -> Grizabella:
    """Returns the shared Grizabella client instance."""
    if grizabella_client_instance is None:
        raise GrizabellaException("Grizabella client is not initialized.")
    return grizabella_client_instance


# --- MCP Tool Definitions ---


# Schema Management
@app.tool(
    name="create_object_type",
    description=(
        "Defines a new type of object in the knowledge base. This is like creating a table schema "
        "in a relational database or defining a node type in a graph. Once an object type is created, "
        "you can create instances (objects) of this type.\n\n"
        "Example:\n"
        "To create a 'Person' object type with 'name' and 'age' properties, you would call this tool "
        "with the following structure:\n"
        '{\n'
        '  "name": "Person",\n'
        '  "description": "A person object type",\n'
        '  "properties": [\n'
        '    {"name": "name", "data_type": "TEXT", "is_nullable": false},\n'
        '    {"name": "age", "data_type": "INTEGER", "is_nullable": true}\n'
        '  ]\n'
        '}'
    ),
)
async def mcp_create_object_type(object_type_def: ObjectTypeDefinition) -> None:
    # ctx: ToolContext,  # Removed for now, FastMCP might inject or not require it.
    gb = None
    try:
        gb = get_grizabella_client()
        gb.create_object_type(object_type_def)
        return  # Or a success message
    except SchemaError as e:
        # More specific error for schema violations (e.g., type already exists)
        msg = f"MCP: Schema error creating object type '{object_type_def.name}': {e}"
        raise GrizabellaException(msg) from e
    except GrizabellaException as e:
        # General Grizabella errors
        msg = f"MCP: Error creating object type '{object_type_def.name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        # Unexpected errors
        msg = f"MCP: Unexpected error creating object type '{object_type_def.name}': {e}"
        raise Exception(msg) from e
    finally:
        # Clean up to prevent memory leaks
        if gb:
            gb.close()


@app.tool(
    name="list_object_types",
    description="Lists all defined object types in the knowledge base.",
)
async def mcp_list_object_types() -> list[ObjectTypeDefinition]:
    try:
        gb = get_grizabella_client()
        return gb.list_object_types()
    except GrizabellaException as e:
        msg = f"MCP: Error listing object types: {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error listing object types: {e}"
        raise Exception(msg) from e


@app.tool(
    name="get_object_type",
    description=(
        "Retrieves the definition of a specific object type, including its properties.\n\n"
        "Example:\n"
        "To get the definition for the 'Person' object type:\n"
        '{\n'
        '  "type_name": "Person"\n'
        '}'
    ),
)
async def mcp_get_object_type(type_name: str) -> Optional[ObjectTypeDefinition]:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.get_object_type_definition(type_name)
    except GrizabellaException as e:
        msg = f"MCP: Error getting object type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error getting object type '{type_name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="delete_object_type",
    description=(
        "Deletes an object type definition. This will also delete all objects of this type and "
        "any relations connected to them.\n\n"
        "Example:\n"
        "To delete the 'Person' object type:\n"
        '{\n'
        '  "type_name": "Person"\n'
        '}'
    ),
)
async def mcp_delete_object_type(type_name: str) -> None:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        gb.delete_object_type(type_name)
        return
    except SchemaError as e:
        msg = f"MCP: Schema error deleting object type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except GrizabellaException as e:
        msg = f"MCP: Error deleting object type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error deleting object type '{type_name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="create_relation_type",
    description=(
        "Defines a new type of relation that can exist between objects. This is like defining a "
        "foreign key relationship or an edge type in a graph.\n\n"
        "Example:\n"
        "To create a 'KNOWS' relation type between two 'Person' objects:\n"
        '{\n'
        '  "relation_type_def": {\n'
        '    "name": "KNOWS",\n'
        '    "from_object_type_name": "Person",\n'
        '    "to_object_type_name": "Person",\n'
        '    "properties": [\n'
        '        {"name": "since", "type": "string"}\n'
        '    ]\n'
        '  }\n'
        '}'
    ),
)
async def mcp_create_relation_type(relation_type_def: RelationTypeDefinition) -> None:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        gb.create_relation_type(relation_type_def)
        return
    except SchemaError as e:
        msg = f"MCP: Schema error creating relation type '{relation_type_def.name}': {e}"
        raise GrizabellaException(msg) from e
    except GrizabellaException as e:
        msg = f"MCP: Error creating relation type '{relation_type_def.name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error creating relation type '{relation_type_def.name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="get_relation_type",
    description=(
        "Retrieves the definition of a specific relation type.\n\n"
        "Example:\n"
        "To get the definition for the 'KNOWS' relation type:\n"
        '{\n'
        '  "type_name": "KNOWS"\n'
        '}'
    ),
)
async def mcp_get_relation_type(type_name: str) -> Optional[RelationTypeDefinition]:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.get_relation_type(type_name)
    except GrizabellaException as e:
        msg = f"MCP: Error getting relation type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error getting relation type '{type_name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="delete_relation_type",
    description=(
        "Deletes a relation type definition. This will also delete all relations of this type.\n\n"
        "Example:\n"
        "To delete the 'KNOWS' relation type:\n"
        '{\n'
        '  "type_name": "KNOWS"\n'
        '}'
    ),
)
async def mcp_delete_relation_type(type_name: str) -> None:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        gb.delete_relation_type(type_name)
        return
    except SchemaError as e:
        msg = f"MCP: Schema error deleting relation type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except GrizabellaException as e:
        msg = f"MCP: Error deleting relation type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error deleting relation type '{type_name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="create_embedding_definition",
    description="Defines how an embedding should be generated for an object type.",
)
async def mcp_create_embedding_definition(embedding_def: EmbeddingDefinition) -> None:
    try:
        gb = get_grizabella_client()
        gb.create_embedding_definition(embedding_def)
        return
    except SchemaError as e:
        msg = f"MCP: Schema error creating embedding definition '{embedding_def.name}': {e}"
        raise GrizabellaException(msg) from e
    except GrizabellaException as e:
        msg = f"MCP: Error creating embedding definition '{embedding_def.name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error creating embedding definition '{embedding_def.name}': {e}"
        raise Exception(msg) from e


# Object Instance Management
@app.tool(
    name="upsert_object",
    description=(
        "Creates a new object instance or updates an existing one if an object with the same ID "
        "already exists.\n\n"
        "Example:\n"
        "To create or update a 'Person' object for John Doe:\n"
        '{\n'
        '  "obj": {\n'
        '    "id": "john_doe_123",\n'
        '    "object_type_name": "Person",\n'
        '    "properties": {\n'
        '      "name": "John Doe",\n'
        '      "age": 30\n'
        '    }\n'
        '  }\n'
        '}'
    ),
)
async def mcp_upsert_object(obj: ObjectInstance) -> ObjectInstance:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.upsert_object(obj)
    except SchemaError as e:
        msg = f"MCP: Schema error upserting object '{obj.id}' of type '{obj.object_type_name}': {e}"
        raise GrizabellaException(msg) from e
    except GrizabellaException as e:
        msg = f"MCP: Error upserting object '{obj.id}' of type '{obj.object_type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error upserting object '{obj.id}' of type '{obj.object_type_name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="get_object_by_id",
    description=(
        "Retrieves a single object instance by its unique ID and type.\n\n"
        "Example:\n"
        "To retrieve the 'Person' object for John Doe:\n"
        '{\n'
        '  "object_id": "john_doe_123",\n'
        '  "type_name": "Person"\n'
        '}'
    ),
)
async def mcp_get_object_by_id(
    object_id: str, type_name: str,
) -> Optional[ObjectInstance]:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.get_object_by_id(object_id, type_name)
    except GrizabellaException as e:
        msg = f"MCP: Error getting object '{object_id}' of type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error getting object '{object_id}' of type '{type_name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="delete_object",
    description=(
        "Deletes a single object instance by its unique ID and type.\n\n"
        "Example:\n"
        "To delete the 'Person' object for John Doe:\n"
        '{\n'
        '  "object_id": "john_doe_123",\n'
        '  "type_name": "Person"\n'
        '}'
    ),
)
async def mcp_delete_object(object_id: str, type_name: str) -> bool:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.delete_object(object_id, type_name)
    except GrizabellaException as e:
        msg = f"MCP: Error deleting object '{object_id}' of type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error deleting object '{object_id}' of type '{type_name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="find_objects",
    description=(
        "Finds and retrieves a list of objects of a given type, with optional filtering criteria.\n\n"
        "Example:\n"
        "To find all 'Person' objects where the age is greater than 30:\n"
        '{\n'
        '  "args": {\n'
        '    "type_name": "Person",\n'
        '    "filter_criteria": {\n'
        '      "age": {">": 30}\n'
        '    },\n'
        '    "limit": 10\n'
        '  }\n'
        '}'
    ),
)
async def mcp_find_objects(
    type_name: str,
    filter_criteria: Optional[dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> list[ObjectInstance]:
    """Finds and retrieves a list of objects of a given type, with optional filtering criteria.
    """
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.find_objects(
            type_name=type_name,
            filter_criteria=filter_criteria,
            limit=limit,
        )
    except GrizabellaException as e:
        msg = f"MCP: Error finding objects of type '{type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e:  # pylint: disable=broad-except
        msg = f"MCP: Unexpected error finding objects of type '{type_name}': {e}"
        raise Exception(msg) from e


# Relation Instance Management
@app.tool(
    name="add_relation",
    description=(
        "Creates a new relation instance between two existing objects.\n\n"
        "Example:\n"
        "To add a 'KNOWS' relation from John Doe to Jane Doe:\n"
        '{\n'
        '  "relation": {\n'
        '    "id": "knows_1",\n'
        '    "relation_type_name": "KNOWS",\n'
        '    "from_object_id": "john_doe_123",\n'
        '    "to_object_id": "jane_doe_456",\n'
        '    "properties": {\n'
        '        "since": "2022-01-15"\n'
        '    }\n'
        '  }\n'
        '}'
    ),
)
async def mcp_add_relation(relation: RelationInstance) -> RelationInstance:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.add_relation(relation)
    except SchemaError as e:
        msg = f"MCP: Schema error adding relation '{relation.id}' of type '{relation.relation_type_name}': {e}"
        raise GrizabellaException(msg) from e
    except GrizabellaException as e:
        msg = f"MCP: Error adding relation '{relation.id}' of type '{relation.relation_type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error adding relation '{relation.id}' of type '{relation.relation_type_name}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="get_relation",
    description=(
        "Retrieves specific relation instances between two objects of a certain relation type.\n\n"
        "Example:\n"
        "To get the 'KNOWS' relations between John Doe and Jane Doe:\n"
        '{\n'
        '  "from_object_id": "john_doe_123",\n'
        '  "to_object_id": "jane_doe_456",\n'
        '  "relation_type_name": "KNOWS"\n'
        '}'
    ),
)
async def mcp_get_relation(
    from_object_id: str, to_object_id: str, relation_type_name: str,
) -> RelationInstanceList:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        relations = gb.get_relation(from_object_id, to_object_id, relation_type_name)
        return RelationInstanceList(relations=relations)
    except GrizabellaException as e:
        msg = f"MCP: Error getting relation of type '{relation_type_name}' from '{from_object_id}' to '{to_object_id}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"M极: Unexpected error getting relation of type '{relation_type_name}' from '{from_object_id}' to '{to_object_id}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="delete_relation",
    description=(
        "Deletes a specific relation instance by its ID and type.\n\n"
        "Example:\n"
        "To delete the 'KNOWS' relation with ID 'knows_1':\n"
        '{\n'
        '  "relation_type_name": "KNOWS",\n'
        '  "relation_id": "knows_1"\n'
        '}'
    ),
)
async def mcp_delete_relation(
    relation_type_name: str, relation_id: str, # Changed parameters
) -> bool:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.delete_relation(relation_type_name, relation_id)
    except GrizabellaException as e:
        msg = f"MCP: Error deleting relation '{relation_id}' of type '{relation_type_name}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error deleting relation '{relation_id}' of type '{relation_type_name}': {e}"
        raise Exception(msg) from e


class GetRelationsArgs(BaseModel):
    object_id: str
    type_name: str
    relation_type_name: Optional[str] = None


@app.tool(
    name="get_outgoing_relations",
    description=(
        "Retrieves all outgoing relations from a specific object.\n\n"
        "Example:\n"
        "To get all outgoing relations from John Doe's 'Person' object:\n"
        '{\n'
        '  "args": {\n'
        '    "object_id": "john_doe_123",\n'
        '    "type_name": "Person"\n'
        '  }\n'
        '}'
    ),
)
async def mcp_get_outgoing_relations(
    object_id: str, type_name: str, relation_type_name: Optional[str] = None,
) -> list[RelationInstance]:
    """Retrieves all outgoing relations from a specific object.
    """
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.get_outgoing_relations(
            object_id=object_id,
            type_name=type_name,
            relation_type_name=relation_type_name,
        )
    except GrizabellaException as e:
        msg = f"MCP: Error getting outgoing relations for object '{object_id}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e:  # pylint: disable=broad-except
        msg = f"MCP: Unexpected error getting outgoing relations for object '{object_id}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="get_incoming_relations",
    description=(
        "Retrieves all incoming relations to a specific object.\n\n"
        "Example:\n"
        "To get all incoming relations to Jane Doe's 'Person' object:\n"
        '{\n'
        '  "args": {\n'
        '    "object_id": "jane_doe_456",\n'
        '    "type_name": "Person"\n'
        '  }\n'
        '}'
    ),
)
async def mcp_get_incoming_relations(
    object_id: str, type_name: str, relation_type_name: Optional[str] = None,
) -> list[RelationInstance]:
    """Retrieves all incoming relations to a specific object.
    """
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.get_incoming_relations(
            object_id=object_id,
            type_name=type_name,
            relation_type_name=relation_type_name,
        )
    except GrizabellaException as e:
        msg = f"MCP: Error getting incoming relations for object '{object_id}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e:  # pylint: disable=broad-except
        msg = f"MCP: Unexpected error getting incoming relations for object '{object_id}': {e}"
        raise Exception(msg) from e


# Querying
class SearchSimilarObjectsArgs(BaseModel):
    object_id: str
    type_name: str
    n_results: int = 5
    search_properties: Optional[list[str]] = None


@app.tool(
    name="search_similar_objects",
    description=(
        "Searches for objects that are semantically similar to a given object, based on embeddings "
        "of their properties. Note: This feature is not yet fully implemented.\n\n"
        "Example:\n"
        "To find 5 objects similar to John Doe's 'Person' object:\n"
        '{\n'
        '  "args": {\n'
        '    "object_id": "john_doe_123",\n'
        '    "type_name": "Person",\n'
        '    "n_results": 5\n'
        '  }\n'
        '}'
    ),
)
async def mcp_search_similar_objects(
    object_id: str,
    type_name: str,
    n_results: int = 5,
    search_properties: Optional[list[str]] = None,
) -> list[tuple[ObjectInstance, float]]:
    """Searches for objects that are semantically similar to a given object, based on embeddings of their properties.
    """
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        # The Grizabella client's search_similar_objects currently raises NotImplementedError.
        # We must call it to respect the interface, but handle the expected error.
        # If it were implemented, results would be List[Tuple[ObjectInstance, float]].
        # For now, to satisfy Pylint and type checkers if the method were to return,
        # we can assign and then immediately handle the expected NotImplementedError.
        # However, a cleaner approach is to directly call and handle.

        # Attempt the call and handle NotImplementedError specifically.
        # Other GrizabellaExceptions or general Exceptions will be caught below.
        try:
            # This line will raise NotImplementedError based on current client.py
            results: list[
                tuple[ObjectInstance, float]
            ] = gb.search_similar_objects(
                object_id=object_id,
                type_name=type_name,
                n_results=n_results,
                search_properties=search_properties,
            )
            return results  # This line will not be reached if NotImplementedError is raised
        except NotImplementedError as nie:
            # Specific handling for the known unimplemented feature.
            # Raising a general Exception here for the MCP layer is acceptable to signal this state.
            msg = f"MCP: search_similar_objects feature is not yet implemented in the Grizabella client: {nie}"
            raise Exception(msg) from nie

    except GrizabellaException as e:
        # Handle other Grizabella-specific errors, re-raise as GrizabellaException
        msg = f"MCP: Error searching similar objects for '{object_id}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e:  # pylint: disable=broad-except
        # Handle any other unexpected errors, re-raise as general Exception
        msg = f"MCP: Unexpected error searching similar objects for '{object_id}': {e}"
        raise Exception(msg) from e


@app.tool(
    name="execute_complex_query",
    description=(
        "Executes a complex, multi-step query that can combine graph traversals, vector searches, "
        "and structured data filtering.\n\n"
        "Example:\n"
        "To find 'the friends of friends of John Doe who are over 30':\n"
        '{\n'
        '  "query": {\n'
        '    "description": "Find friends of friends of John Doe over 30",\n'
        '    "steps": [\n'
        '      {\n'
        '        "step_type": "graph_traversal",\n'
        '        "start_node_query": {\n'
        '          "type_name": "Person",\n'
        '          "filter_criteria": {"name": "John Doe"}\n'
        '        },\n'
        '        "edge_traversals": [\n'
        '          {"relation_type_name": "KNOWS", "direction": "outgoing"},\n'
        '          {"relation_type_name": "KNOWS", "direction": "outgoing"}\n'
        '        ],\n'
        '        "result_filter": {\n'
        '          "age": {">": 30}\n'
        '        }\n'
        '      }\n'
        '    ]\n'
        '  }\n'
        '}'
    ),
)
async def mcp_execute_complex_query(query: ComplexQuery) -> QueryResult:
    # ctx: ToolContext,
    try:
        gb = get_grizabella_client()
        return gb.execute_complex_query(query)
    except GrizabellaException as e:
        msg = f"MCP: Error executing complex query '{query.description}': {e}"
        raise GrizabellaException(msg) from e
    except Exception as e: # pylint: disable=broad-except
        msg = f"MCP: Unexpected error executing complex query '{query.description}': {e}"
        raise Exception(msg) from e


class GetEmbeddingVectorForTextArgs(BaseModel):
    text_to_embed: str
    embedding_definition_name: str

@app.tool(
    name="get_embedding_vector_for_text",
    description="Generates an embedding vector for a given text using a specified embedding definition.",
)
async def mcp_get_embedding_vector_for_text(args: GetEmbeddingVectorForTextArgs) -> EmbeddingVector:
    """Generates an embedding vector for a given text using a specified embedding definition."""
    gb = get_grizabella_client()
    temp_obj_id = uuid.uuid4()
    embedding_def = gb.get_embedding_definition(args.embedding_definition_name)
    try:
        # 1. Get the embedding definition
        if not embedding_def:
            raise GrizabellaException(f"Embedding definition '{args.embedding_definition_name}' not found.")

        # 2. Get the corresponding object type definition
        obj_type_def = gb.get_object_type_definition(embedding_def.object_type_name)
        if not obj_type_def:
            raise GrizabellaException(f"Object type '{embedding_def.object_type_name}' not found for embedding definition.")

        # 3. Create a temporary object with dummy data for required fields
        temp_properties = {}
        for prop_def in obj_type_def.properties:
            if prop_def.name == embedding_def.source_property_name:
                temp_properties[prop_def.name] = args.text_to_embed
            elif not prop_def.is_nullable:
                # Provide dummy data for non-nullable fields
                if prop_def.data_type == PropertyDataType.TEXT:
                    temp_properties[prop_def.name] = f"dummy_{prop_def.name}"
                elif prop_def.data_type == PropertyDataType.INTEGER:
                    temp_properties[prop_def.name] = 0
                elif prop_def.data_type == PropertyDataType.FLOAT:
                    temp_properties[prop_def.name] = 0.0
                elif prop_def.data_type == PropertyDataType.BOOLEAN:
                    temp_properties[prop_def.name] = False
                elif prop_def.data_type == PropertyDataType.DATETIME:
                    temp_properties[prop_def.name] = datetime.now(timezone.utc).isoformat()
                elif prop_def.data_type == PropertyDataType.UUID:
                    temp_properties[prop_def.name] = str(uuid.uuid4())
                else:
                    # For BLOB, JSON, etc., we might need more robust dummy data generation
                    temp_properties[prop_def.name] = None # This might fail if not nullable, but it's a start

        temp_obj_instance = ObjectInstance(
            id=temp_obj_id,
            object_type_name=embedding_def.object_type_name,
            properties=temp_properties,
        )
        gb.upsert_object(temp_obj_instance)

        # 4. Retrieve the embedding vector
        # This relies on internal access, similar to the original test.
        embedding_instances = gb._db_manager.lancedb_adapter.get_embedding_instances_for_object(
           object_instance_id=temp_obj_id,
           embedding_definition_name=args.embedding_definition_name,
        )

        if not embedding_instances:
            raise GrizabellaException("Failed to generate or retrieve embedding for temporary object.")

        vector = embedding_instances[0].vector
        if not vector:
            raise GrizabellaException("Retrieved embedding instance has no vector.")

        return EmbeddingVector(vector=vector)

    finally:
        # 5. Clean up the temporary object
        if embedding_def:
            try:
                gb.delete_object(object_id=str(temp_obj_id), type_name=embedding_def.object_type_name)
            except Exception as e:
                # Log cleanup error but don't let it hide the main result/error
                print(f"MCP: Warning: Failed to clean up temporary object {temp_obj_id}: {e}", file=sys.stderr)


# To run this server (example using uvicorn, if FastMCP is FastAPI/Starlette based):
# Ensure FastMCP documentation is checked for the correct way to run the server.
# If FastMCP provides its own CLI runner, use that.
# Example: uvicorn grizabella.mcp.server:app --reload
#
# The main FastMCP object `app` would typically be run by a command like:
# `python -m fastmcp grizabella.mcp.server:app`
# or similar, depending on FastMCP's conventions.

# Global variables for memory profiling
snapshot1 = None
args = None

def print_memory_stats(label="Memory Stats"):
    """Print current memory statistics if profiling is enabled."""
    global snapshot1, args
    logger.info(f"print_memory_stats called with label: {label}")
    logger.info(f"args: {args}, profile_mem: {getattr(args, 'profile_mem', 'N/A') if args else 'N/A'}, snapshot1: {snapshot1 is not None}")
    if args and args.profile_mem and snapshot1:
        try:
            current_snapshot = tracemalloc.take_snapshot()
            top_stats = current_snapshot.compare_to(snapshot1, 'lineno')
            logger.info("[Current Top 10 memory consumers]")
            stats_output = []
            stats_output.append("[Current Top 10 memory consumers]")
            for stat in top_stats[:10]:
                logger.info(stat)
                stats_output.append(str(stat))
            
            # Save to file if specified
            # Save to file if specified
            if args.profile_file:
                try:
                    with open(args.profile_file, 'a') as f:
                        f.write(f"\n--- {label} at {datetime.now()} ---\n")
                        f.write('\n'.join(stats_output) + '\n')
                        f.flush()  # Ensure data is written immediately
                        os.fsync(f.fileno())  # Force OS to write to disk
                except Exception as e:
                    logger.error(f"Error saving memory stats to file: {e}")
        except Exception as e:
            logger.error(f"Error printing memory stats: {e}")

def shutdown_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print(f"Received signal {signum}, shutting down...")
    logger.info(f"Received signal {signum}, shutting down...")
    # Print final memory stats before exiting
    print_memory_stats()
    # Ensure memory profile file is flushed
    global args
    logger.info(f"Shutdown handler args: {args}")
    if args and args.profile_mem and args.profile_file:
        try:
            # Try to flush any buffered writes
            logger.info(f"Writing shutdown signal to profile file: {args.profile_file}")
            with open(args.profile_file, 'a') as f:
                f.write(f"\n--- Shutdown Signal {signum} received at {datetime.now()} ---\n")
                f.flush()
                os.fsync(f.fileno())
            logger.info("Shutdown signal written to profile file successfully")
            # Small delay to ensure file operations complete
            time.sleep(0.1)
        except Exception as e:
            print(f"Error writing shutdown signal to profile file: {e}")
            logger.error(f"Error writing shutdown signal to profile file: {e}")
    # Perform any cleanup here if needed
    sys.exit(0)

def main():
    """Initializes client and runs the FastMCP application."""
    global snapshot1, args
    
    # Start memory tracing
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    parser = argparse.ArgumentParser(description="Grizabella MCP Server")
    parser.add_argument("--db-path", help="Path to the Grizabella database.")
    parser.add_argument("--profile-mem", action="store_true", help="Enable memory profiling")
    parser.add_argument("--profile-interval", type=int, default=0, help="Interval in seconds to print memory stats (0 = disabled)")
    parser.add_argument("--profile-file", type=str, default="memory_profile.txt", help="File to save memory profiling data")
    args = parser.parse_args()

    global grizabella_client_instance
    db_path = get_grizabella_db_path(args.db_path)
    
    if args.profile_mem:
        logger.info("Memory profiling enabled")
        initial_stats = snapshot1.statistics('lineno')[:10]
        logger.info(f"Initial memory snapshot: {initial_stats}")
        logger.info(f"Initial memory stats count: {len(initial_stats)}")
        
        # Save initial snapshot to file
        if args.profile_file:
            try:
                with open(args.profile_file, 'w') as f:
                    f.write(f"Initial memory snapshot at {datetime.now()}\n")
                    for stat in snapshot1.statistics('lineno')[:10]:
                        f.write(f"{stat}\n")
                logger.info(f"Initial memory snapshot saved to {args.profile_file}")
            except Exception as e:
                logger.error(f"Error saving initial memory snapshot: {e}")

    # Start periodic memory reporting if interval is set (before app.run)
    memory_thread = None
    if args.profile_mem and args.profile_interval > 0:
        def periodic_memory_report():
            logger.info("Periodic memory reporting thread started")
            iteration = 0
            while True:
                try:
                    iteration += 1
                    logger.info(f"Periodic memory report #{iteration} triggered, sleeping for {args.profile_interval} seconds")  # type: ignore
                    time.sleep(args.profile_interval)  # type: ignore
                    logger.info(f"Periodic memory report #{iteration} running")
                    print_memory_stats(f"Periodic Report #{iteration}")
                    logger.info(f"Periodic memory report #{iteration} completed")
                except Exception as e:
                    logger.error(f"Error in periodic memory reporting thread: {e}")
                    # Continue running even if there's an error
                    time.sleep(5)  # Wait a bit before retrying
        
        memory_thread = threading.Thread(target=periodic_memory_report, daemon=True)
        memory_thread.start()
        logger.info(f"Periodic memory reporting enabled every {args.profile_interval} seconds")
    
    try:
        with Grizabella(db_name_or_path=db_path, create_if_not_exists=True) as gb:
            grizabella_client_instance = gb
            # Print memory stats before starting the server
            print_memory_stats("Before starting FastMCP server")
            app.run(show_banner=False)
            # Print memory stats after server stops (if it ever stops normally)
            print_memory_stats("After FastMCP server stopped")
    except Exception as e:
        print(f"Server error: {e}")
        # Print memory stats on error
        print_memory_stats()
        sys.exit(1)
    finally:
        # Ensure clean termination
        grizabella_client_instance = None
        print("Server terminated cleanly")
        
        if args and args.profile_mem and snapshot1:
            try:
                logger.info("Taking final memory snapshot")
                snapshot2 = tracemalloc.take_snapshot()
                top_stats = snapshot2.compare_to(snapshot1, 'lineno')
                logger.info("[Top 10 memory differences]")
                stats_output = []
                stats_output.append("[Top 10 memory differences]")
                for stat in top_stats[:10]:
                    logger.info(stat)
                    stats_output.append(str(stat))
                
                # Save to file if specified
                if args.profile_file:
                    try:
                        with open(args.profile_file, 'a') as f:
                            f.write(f"\n--- Final Memory Differences at {datetime.now()} ---\n")
                            f.write('\n'.join(stats_output) + '\n')
                            f.write(f"Total memory allocated: {sum(stat.size for stat in top_stats)} bytes\n")
                            f.flush()
                            os.fsync(f.fileno())
                        logger.info("Final memory differences written to file")
                    except Exception as e:
                        logger.error(f"Error writing final memory differences to file: {e}")
            except Exception as e:
                logger.error(f"Error in final memory profiling: {e}")
        
        sys.exit(0)

if __name__ == "__main__":
    # This allows the server to be run directly, defaulting to Stdio transport.
    main()
