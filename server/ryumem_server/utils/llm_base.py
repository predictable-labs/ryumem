"""
Base utilities for LLM clients.

Provides shared prompt building and response parsing methods for entity extraction,
relationship extraction, and contradiction detection.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LLMExtractionMixin:
    """
    Mixin class providing common extraction methods for LLM clients.

    This class provides prompt building and tool definition methods that are
    identical across all LLM providers. Each provider's client class should
    inherit from this mixin and implement its own API calling logic.
    """

    @staticmethod
    def build_extract_entities_prompt(
        text: str,
        user_id: str,
        context: Optional[str] = None,
    ) -> tuple[str, str, List[Dict[str, Any]]]:
        """
        Build prompt and tools for entity extraction.

        Args:
            text: Input text to extract entities from
            user_id: User ID for self-reference resolution
            context: Optional context for better extraction

        Returns:
            Tuple of (system_prompt, user_prompt, tools)
        """
        system_prompt = f"""You are a smart assistant who understands entities and their types in a given text.
If user message contains self reference such as 'I', 'me', 'my' etc. then use {user_id} as the source entity.
Extract all the entities from the text. DO NOT answer the question itself if the given text is a question."""

        if context:
            system_prompt += f"\n\nContext from previous messages:\n{context}"

        user_prompt = text

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "extract_entities",
                    "description": "Extract entities and their types from the text",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "entity": {
                                            "type": "string",
                                            "description": "The entity name"
                                        },
                                        "entity_type": {
                                            "type": "string",
                                            "description": "The type of entity (e.g., PERSON, ORGANIZATION, CONCEPT)"
                                        }
                                    },
                                    "required": ["entity", "entity_type"]
                                }
                            }
                        },
                        "required": ["entities"]
                    }
                }
            }
        ]

        return system_prompt, user_prompt, tools

    @staticmethod
    def parse_entities_response(response: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Parse entities from LLM response with tool calls.

        Args:
            response: Response dictionary with optional 'tool_calls' key

        Returns:
            List of entities with 'entity' and 'entity_type' keys
        """
        entities = []
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                if tool_call["name"] == "extract_entities":
                    entities = tool_call["arguments"].get("entities", [])
        return entities

    @staticmethod
    def build_extract_relationships_prompt(
        text: str,
        entities: List[str],
        user_id: str,
        context: Optional[str] = None,
    ) -> tuple[str, str, List[Dict[str, Any]]]:
        """
        Build prompt and tools for relationship extraction.

        Args:
            text: Input text
            entities: List of entity names to find relationships for
            user_id: User ID for context
            context: Optional context

        Returns:
            Tuple of (system_prompt, user_prompt, tools)
        """
        system_prompt = f"""You are a smart assistant who understands relationships between entities.
Extract relationships between the provided entities from the text.
User ID: {user_id}

Rules:
1. Only extract relationships that are explicitly or implicitly mentioned in the text
2. Use clear, concise relationship names (e.g., WORKS_AT, KNOWS, LOCATED_IN)
3. Ensure source and destination are from the provided entity list
4. If you detect temporal information (when something started or ended), include it"""

        if context:
            system_prompt += f"\n\nContext:\n{context}"

        user_prompt = f"Entities: {', '.join(entities)}\n\nText: {text}"

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "extract_relationships",
                    "description": "Extract relationships between entities",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "relationships": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "source": {
                                            "type": "string",
                                            "description": "Source entity"
                                        },
                                        "relationship": {
                                            "type": "string",
                                            "description": "Relationship type"
                                        },
                                        "destination": {
                                            "type": "string",
                                            "description": "Destination entity"
                                        },
                                        "fact": {
                                            "type": "string",
                                            "description": "Natural language description of the relationship"
                                        }
                                    },
                                    "required": ["source", "relationship", "destination", "fact"]
                                }
                            }
                        },
                        "required": ["relationships"]
                    }
                }
            }
        ]

        return system_prompt, user_prompt, tools

    @staticmethod
    def parse_relationships_response(response: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Parse relationships from LLM response with tool calls.

        Args:
            response: Response dictionary with optional 'tool_calls' key

        Returns:
            List of relationships with 'source', 'relationship', 'destination' keys
        """
        relationships = []
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                if tool_call["name"] == "extract_relationships":
                    relationships = tool_call["arguments"].get("relationships", [])
        return relationships

    @staticmethod
    def build_detect_contradictions_prompt(
        new_facts: List[str],
        existing_facts: List[str],
    ) -> tuple[str, str, List[Dict[str, Any]]]:
        """
        Build prompt and tools for contradiction detection.

        Args:
            new_facts: List of new fact descriptions
            existing_facts: List of existing fact descriptions

        Returns:
            Tuple of (system_prompt, user_prompt, tools)
        """
        system_prompt = """You are an expert at detecting contradictions and outdated information.
Compare new facts against existing facts and identify any contradictions or updates.

A contradiction occurs when:
1. Facts directly oppose each other (e.g., "Alice works at Google" vs "Alice works at Meta")
2. A new fact makes an old fact outdated (e.g., "Alice moved to NYC" when previously "Alice lives in SF")
3. Temporal changes occur (e.g., "Alice graduated" vs "Alice is a student")"""

        user_prompt = f"""New facts:
{chr(10).join(f"{i}. {fact}" for i, fact in enumerate(new_facts))}

Existing facts:
{chr(10).join(f"{i}. {fact}" for i, fact in enumerate(existing_facts))}

Identify all contradictions."""

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "detect_contradictions",
                    "description": "Identify contradictions between new and existing facts",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contradictions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "new_fact_index": {
                                            "type": "integer",
                                            "description": "Index of the new fact"
                                        },
                                        "existing_fact_index": {
                                            "type": "integer",
                                            "description": "Index of the existing fact that contradicts"
                                        },
                                        "reason": {
                                            "type": "string",
                                            "description": "Explanation of the contradiction"
                                        }
                                    },
                                    "required": ["new_fact_index", "existing_fact_index", "reason"]
                                }
                            }
                        },
                        "required": ["contradictions"]
                    }
                }
            }
        ]

        return system_prompt, user_prompt, tools

    @staticmethod
    def parse_contradictions_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse contradictions from LLM response with tool calls.

        Args:
            response: Response dictionary with optional 'tool_calls' key

        Returns:
            List of contradictions with 'new_fact_index', 'existing_fact_index', 'reason'
        """
        contradictions = []
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                if tool_call["name"] == "detect_contradictions":
                    contradictions = tool_call["arguments"].get("contradictions", [])
        return contradictions

    # Structured Output Base Methods

    def _call_api_with_json_mode(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        """
        Provider-specific API call with JSON mode.

        Override in subclass for provider-specific API call.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Raw JSON string from API response
        """
        raise NotImplementedError("Subclass must implement _call_api_with_json_mode")

    async def _acall_api_with_json_mode(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        """
        Async provider-specific API call with JSON mode.

        Override in subclass for async provider-specific API call.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Raw JSON string from API response
        """
        raise NotImplementedError("Subclass must implement _acall_api_with_json_mode")

    @staticmethod
    def _build_json_prompt(system_prompt: str, schema: Dict[str, Any]) -> str:
        """
        Build enhanced system prompt with JSON schema guidance.

        Args:
            system_prompt: Original system prompt
            schema: JSON schema from Pydantic model

        Returns:
            Enhanced system prompt with schema guidance
        """
        schema_str = json.dumps(schema, indent=2)
        return f"""{system_prompt}

You MUST respond with valid JSON that conforms to this schema:
{schema_str}

Output ONLY the JSON object, no other text."""

    @staticmethod
    def _parse_structured_response(
        response_content: str,
        response_model: Type[BaseModel],
    ) -> BaseModel:
        """
        Parse and validate JSON response into Pydantic model.

        Args:
            response_content: Raw JSON string from API
            response_model: Pydantic model class for validation

        Returns:
            Instance of response_model with parsed data

        Raises:
            json.JSONDecodeError: If response is not valid JSON
            ValidationError: If JSON doesn't match schema
        """
        data = json.loads(response_content.strip())
        return response_model.model_validate(data)

    def create_structured_output(
        self,
        text_input: str,
        system_prompt: str,
        response_model: Type[BaseModel],
        temperature: float = 0.0,
    ) -> BaseModel:
        """
        Generate structured output parsed into a Pydantic model.

        Base implementation that calls provider-specific _call_api_with_json_mode().

        Args:
            text_input: The user input text to process
            system_prompt: System prompt with instructions
            response_model: Pydantic model class for response validation
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            Instance of response_model with parsed data
        """
        try:
            # Get JSON schema from Pydantic model
            schema = response_model.model_json_schema()

            # Build enhanced prompt with schema
            enhanced_prompt = self._build_json_prompt(system_prompt, schema)

            # Build messages
            messages = [
                {"role": "system", "content": enhanced_prompt},
                {"role": "user", "content": text_input},
            ]

            # Call provider-specific API
            response_content = self._call_api_with_json_mode(
                messages=messages,
                temperature=temperature,
                max_tokens=None,
            )

            # Parse and validate response
            result = self._parse_structured_response(response_content, response_model)

            logger.debug(f"Structured output: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating structured output: {e}")
            raise

    async def acreate_structured_output(
        self,
        text_input: str,
        system_prompt: str,
        response_model: Type[BaseModel],
        temperature: float = 0.0,
    ) -> BaseModel:
        """
        Async version of create_structured_output.

        Base implementation that calls provider-specific _acall_api_with_json_mode().

        Args:
            text_input: The user input text to process
            system_prompt: System prompt with instructions
            response_model: Pydantic model class for response validation
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            Instance of response_model with parsed data
        """
        try:
            # Get JSON schema from Pydantic model
            schema = response_model.model_json_schema()

            # Build enhanced prompt with schema
            enhanced_prompt = self._build_json_prompt(system_prompt, schema)

            # Build messages
            messages = [
                {"role": "system", "content": enhanced_prompt},
                {"role": "user", "content": text_input},
            ]

            # Call provider-specific async API
            response_content = await self._acall_api_with_json_mode(
                messages=messages,
                temperature=temperature,
                max_tokens=None,
            )

            # Parse and validate response
            result = self._parse_structured_response(response_content, response_model)

            logger.debug(f"Async structured output: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating async structured output: {e}")
            raise
