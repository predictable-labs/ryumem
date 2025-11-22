"""
LLM client wrapper for OpenAI models.
Handles function calling, retries, and error handling.
"""

import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Wrapper for OpenAI LLM client with retry logic and error handling.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """
        Initialize LLM client.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., 'gpt-4', 'gpt-4-turbo')
            max_retries: Maximum number of retries for API calls
            timeout: Timeout in seconds for API calls
        """
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.max_retries = max_retries

        logger.info(f"Initialized LLMClient with model: {model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM with optional function calling.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tool/function definitions
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Response dictionary with 'content' and optional 'tool_calls'
        """
        try:
            # Prepare kwargs
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            # Make API call
            response = self.client.chat.completions.create(**kwargs)

            # Extract response
            message = response.choices[0].message
            result: Dict[str, Any] = {
                "content": message.content or "",
                "role": message.role,
            }

            # Extract tool calls if present
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "arguments": eval(tool_call.function.arguments),  # Parse JSON string to dict
                    }
                    for tool_call in message.tool_calls
                ]

            logger.debug(f"LLM response: {result}")
            return result

        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            raise

    def extract_entities(
        self,
        text: str,
        user_id: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Extract entities from text using function calling.

        Args:
            text: Input text to extract entities from
            user_id: User ID for self-reference resolution
            context: Optional context for better extraction

        Returns:
            List of entities with 'entity' and 'entity_type' keys
        """
        system_prompt = f"""You are a smart assistant who understands entities and their types in a given text.
If user message contains self reference such as 'I', 'me', 'my' etc. then use {user_id} as the source entity.
Extract all the entities from the text. DO NOT answer the question itself if the given text is a question."""

        if context:
            system_prompt += f"\n\nContext from previous messages:\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

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

        response = self.generate(messages, tools=tools)

        # Extract entities from tool calls
        entities = []
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                if tool_call["name"] == "extract_entities":
                    entities = tool_call["arguments"].get("entities", [])

        logger.info(f"Extracted {len(entities)} entities from text")
        return entities

    def extract_relationships(
        self,
        text: str,
        entities: List[str],
        user_id: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Extract relationships between entities using function calling.

        Args:
            text: Input text
            entities: List of entity names to find relationships for
            user_id: User ID for context
            context: Optional context

        Returns:
            List of relationships with 'source', 'relationship', 'destination' keys
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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

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

        response = self.generate(messages, tools=tools)

        # Extract relationships from tool calls
        relationships = []
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                if tool_call["name"] == "extract_relationships":
                    relationships = tool_call["arguments"].get("relationships", [])

        logger.info(f"Extracted {len(relationships)} relationships from text")
        return relationships

    def detect_contradictions(
        self,
        new_facts: List[str],
        existing_facts: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Detect contradictions between new and existing facts.

        Args:
            new_facts: List of new fact descriptions
            existing_facts: List of existing fact descriptions

        Returns:
            List of contradictions with 'new_fact_index', 'existing_fact_index', 'reason'
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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

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

        response = self.generate(messages, tools=tools)

        # Extract contradictions from tool calls
        contradictions = []
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                if tool_call["name"] == "detect_contradictions":
                    contradictions = tool_call["arguments"].get("contradictions", [])

        logger.info(f"Detected {len(contradictions)} contradictions")
        return contradictions
