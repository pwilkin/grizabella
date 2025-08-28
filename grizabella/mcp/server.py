"""Grizabella MCP Server.

This module provides an MCP (Model Context Protocol) server for Grizabella,
exposing its core functionalities as tools that can be called remotely.
It uses FastMCP to define and serve these tools.

Server Description: This MCP server exposes the core functionalities of the Grizabella
knowledge management system, allowing for the creation, retrieval, and querying of
structured data objects and their relationships.
"""

import argparse
from datetime import datetime, timezone
import functools
import logging
import os
import signal
import sys
import uuid
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
        logging.FileHandler('mcp-server-' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.log')
    ]
)

logger = logging.getLogger(__name__)


def log_tool_call(func):
    """Decorator to log detailed information about tool calls."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract tool name from function name (remove mcp_ prefix)
        tool_name = func.__name__
        if tool_name.startswith('mcp_'):
            tool_name = tool_name[4:]

        # Log the tool call with details
        logger.info(f"🔧 Tool Call: {tool_name}")

        # Log arguments if any (excluding 'self' for methods)
        if args:
            # Skip 'self' argument for methods
            actual_args = args[1:] if args and hasattr(args[0], '__class__') else args
            if actual_args:
                logger.info(f"📝 Arguments: {actual_args}")

        if kwargs:
            logger.info(f"📝 Keyword Arguments: {kwargs}")

        # Call the original function
        try:
            result = await func(*args, **kwargs)
            logger.info(f"✅ Tool Call Success: {tool_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Tool Call Failed: {tool_name} - Error: {e}")
            raise

    return wrapper


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
@log_tool_call
async def mcp_create_object_type(object_type_def: ObjectTypeDefinition) -> None:
    # ctx: ToolContext,  # Removed for now, FastMCP might inject or not require it.
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


@app.tool(
    name="list_object_types",
    description="Lists all defined object types in the knowledge base.",
)
@log_tool_call
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
@log_tool_call
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
@log_tool_call
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
@log_tool_call
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
@log_tool_call
async def mcp_create_embedding_definition(embedding_def: EmbeddingDefinition) -> None:
    try:
        gb = get_grizabella_client()

        # Strip 'huggingface/' prefix if present, as LanceDB registry expects just the model name
        # This ensures consistency with get_embedding_vector_for_text tool
        model_identifier = embedding_def.embedding_model
        if model_identifier.startswith('huggingface/'):
            model_identifier = model_identifier[len('huggingface/'):]
            logger.info(f"Stripped 'huggingface/' prefix from model identifier: '{embedding_def.embedding_model}' -> '{model_identifier}'")
            # Update the embedding definition with the stripped model identifier
            embedding_def.embedding_model = model_identifier

        # Auto-detect dimensions if not specified or if MCP client set a default
        logger.info(f"Checking dimensions for embedding definition '{embedding_def.name}': current dimensions = {embedding_def.dimensions}")
        if embedding_def.dimensions is None or embedding_def.dimensions == 0 or embedding_def.dimensions == 1536:
            logger.info(f"Auto-detecting dimensions for model '{model_identifier}' (overriding default {embedding_def.dimensions})")
            try:
                # Load the model to get its dimensions
                embedding_model_func = gb._db_manager._connection_helper.lancedb_adapter.get_embedding_model(model_identifier)

                # Generate a test embedding to determine dimensions
                test_text = "test"
                test_embeddings = embedding_model_func.compute_query_embeddings([test_text])
                if test_embeddings and len(test_embeddings) > 0:
                    detected_dimensions = len(test_embeddings[0])
                    embedding_def.dimensions = detected_dimensions
                    logger.info(f"Auto-detected {detected_dimensions} dimensions for model '{model_identifier}'")
                else:
                    # Fallback to a reasonable default
                    embedding_def.dimensions = 768
                    logger.warning(f"Could not detect dimensions for model '{model_identifier}', using default 768")
            except Exception as dim_error:
                # Fallback to a reasonable default
                embedding_def.dimensions = 768
                logger.warning(f"Error detecting dimensions for model '{model_identifier}': {dim_error}, using default 768")
        else:
            logger.info(f"Dimensions already specified for '{embedding_def.name}': {embedding_def.dimensions}")

        logger.info(f"Final dimensions for embedding definition '{embedding_def.name}': {embedding_def.dimensions}")

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
@log_tool_call
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
@log_tool_call
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
@log_tool_call
async def mcp_get_embedding_vector_for_text(args: GetEmbeddingVectorForTextArgs) -> EmbeddingVector:
    """Generates an embedding vector for a given text using a specified embedding definition."""
    gb = get_grizabella_client()
    embedding_def = gb.get_embedding_definition(args.embedding_definition_name)
    try:
        # 1. Get the embedding definition
        if not embedding_def:
            raise GrizabellaException(f"Embedding definition '{args.embedding_definition_name}' not found.")

        # 2. Generate embedding vector directly using the same logic as find_similar_objects_by_embedding
        # This approach mirrors the Python client's successful method
        logger.info(f"Generating embedding vector for text using model '{embedding_def.embedding_model}'")

        # Get the embedding model function
        # Strip 'huggingface/' prefix if present, as LanceDB registry expects just the model name
        model_identifier = embedding_def.embedding_model
        if model_identifier.startswith('huggingface/'):
            model_identifier = model_identifier[len('huggingface/'):]
            logger.info(f"Stripped 'huggingface/' prefix from model identifier: '{embedding_def.embedding_model}' -> '{model_identifier}'")

        logger.info(f"About to load embedding model with identifier: '{model_identifier}'")
        embedding_model_func = gb._db_manager._connection_helper.lancedb_adapter.get_embedding_model(
            model_identifier,
        )

        # Generate embedding using compute_query_embeddings (same as Python client)
        raw_query_embeddings = embedding_model_func.compute_query_embeddings([args.text_to_embed])
        if not raw_query_embeddings:
            logger.error(f"Model '{embedding_def.embedding_model}' returned empty list for text.")
            raise GrizabellaException(f"Model {embedding_def.embedding_model} returned empty list for text.")

        raw_query_vector = raw_query_embeddings[0]

        # Convert to list if it's a numpy array
        if hasattr(raw_query_vector, "tolist"):  # Handles numpy array
            final_query_vector = raw_query_vector.tolist()
        elif isinstance(raw_query_vector, list):
            final_query_vector = raw_query_vector
        else:
            logger.error(f"Unexpected query vector type from model '{embedding_def.embedding_model}': {type(raw_query_vector)}")
            raise GrizabellaException(f"Unexpected query vector type from model {embedding_def.embedding_model}")

        # Validate dimensions (temporarily disabled for debugging)
        logger.info(f"Generated embedding vector with {len(final_query_vector)} dimensions. ED specifies {embedding_def.dimensions} dimensions.")
        if embedding_def.dimensions and len(final_query_vector) != embedding_def.dimensions:
            logger.warning(
                f"Query vector dim ({len(final_query_vector)}) does not match ED "
                f"'{embedding_def.name}' dim ({embedding_def.dimensions}). Continuing anyway."
            )
            # raise GrizabellaException(msg)  # Temporarily disabled

        logger.info(f"Successfully generated embedding vector with dimension {len(final_query_vector)}")

        # Debug: Log what we're about to return
        debug_return_value = {"vector": final_query_vector}
        logger.info(f"MCP get_embedding_vector_for_text returning: type={type(debug_return_value)}, vector_type={type(debug_return_value['vector'])}, vector_length={len(debug_return_value['vector'])}")
        logger.info(f"MCP get_embedding_vector_for_text return value preview: {debug_return_value['vector'][:5]}...")

        # Return as a plain dict to ensure MCP serialization works correctly
        return debug_return_value

    except Exception as e:
        logger.error(f"Failed to generate embedding vector: {e}", exc_info=True)
        raise GrizabellaException(f"Failed to generate embedding vector: {e}") from e


# To run this server (example using uvicorn, if FastMCP is FastAPI/Starlette based):
# Ensure FastMCP documentation is checked for the correct way to run the server.
# If FastMCP provides its own CLI runner, use that.
# Example: uvicorn grizabella.mcp.server:app --reload
#
# The main FastMCP object `app` would typically be run by a command like:
# `python -m fastmcp grizabella.mcp.server:app`
# or similar, depending on FastMCP's conventions.

def shutdown_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print(f"Received signal {signum}, shutting down...", file=sys.stderr)
    logger.info(f"Received signal {signum}, shutting down...")
    # Perform any cleanup here if needed
    sys.exit(0)

def main():
    """Initializes client and runs the FastMCP application."""
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    parser = argparse.ArgumentParser(description="Grizabella MCP Server")
    parser.add_argument("--db-path", help="Path to the Grizabella database.")
    args = parser.parse_args()

    global grizabella_client_instance
    db_path = get_grizabella_db_path(args.db_path)
    
    try:
        with Grizabella(db_name_or_path=db_path, create_if_not_exists=True) as gb:
            grizabella_client_instance = gb
            app.run(show_banner=False)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Ensure clean termination
        grizabella_client_instance = None
        print("Server terminated cleanly", file=sys.stderr)
        
        sys.exit(0)

if __name__ == "__main__":
    # This allows the server to be run directly, defaulting to Stdio transport.
    main()
