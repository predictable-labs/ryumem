"""
LiteLLM client adapter for unified LLM access.

Provides the same interface as LLMClient but uses LiteLLM for accessing
100+ LLM providers through a single unified API.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Embedding model defaults for different LLM models
# Maps LLM model name -> embedding model name (None = no native embeddings)
LITELLM_EMBEDDING_DEFAULTS = {
    # OpenAI models
    "gpt-4o": "text-embedding-3-large",
    "gpt-4o-mini": "text-embedding-3-large",
    "gpt-4": "text-embedding-3-large",
    "gpt-4-turbo": "text-embedding-3-large",
    "gpt-3.5-turbo": "text-embedding-3-large",
    "openai/gpt-4o": "text-embedding-3-large",
    "openai/gpt-4o-mini": "text-embedding-3-large",
    "openai/gpt-4": "text-embedding-3-large",
    "openai/gpt-4-turbo": "text-embedding-3-large",
    "openai/gpt-3.5-turbo": "text-embedding-3-large",

    # Anthropic models (no native embeddings)
    "claude-3-5-sonnet-20241022": None,
    "claude-3-opus-20240229": None,
    "claude-3-sonnet-20240229": None,
    "claude-3-haiku-20240307": None,
    "anthropic/claude-3-5-sonnet-20241022": None,
    "anthropic/claude-3-opus-20240229": None,
    "anthropic/claude-3-sonnet-20240229": None,
    "anthropic/claude-3-haiku-20240307": None,

    # Google Gemini models
    "gemini-1.5-pro": "text-embedding-004",
    "gemini-1.5-flash": "text-embedding-004",
    "gemini-2.0-flash-exp": "text-embedding-004",
    "gemini/gemini-1.5-pro": "text-embedding-004",
    "gemini/gemini-1.5-flash": "text-embedding-004",
    "gemini/gemini-2.0-flash-exp": "text-embedding-004",

    # Cohere models
    "command-r-plus": "embed-english-v3.0",
    "command-r": "embed-english-v3.0",
    "command": "embed-english-v3.0",
    "cohere/command-r-plus": "embed-english-v3.0",
    "cohere/command-r": "embed-english-v3.0",

    # AWS Bedrock models
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": "bedrock/amazon.titan-embed-text-v2:0",
    "bedrock/anthropic.claude-3-opus-20240229-v1:0": "bedrock/amazon.titan-embed-text-v2:0",
    "bedrock/anthropic.claude-3-sonnet-20240229-v1:0": "bedrock/amazon.titan-embed-text-v2:0",
}

# Embedding dimensions for different embedding models
EMBEDDING_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    "text-embedding-004": 768,
    "embed-english-v3.0": 1024,
    "bedrock/amazon.titan-embed-text-v2:0": 1024,
}


class LiteLLMClient:
    """
    LiteLLM client for unified LLM access across 100+ providers.

    Compatible with the LLMClient interface for drop-in replacement.
    LiteLLM automatically detects the provider from the model name and
    uses the appropriate API key from environment variables.

    Examples:
        # OpenAI
        client = LiteLLMClient(model="gpt-4o-mini")

        # Anthropic
        client = LiteLLMClient(model="claude-3-5-sonnet-20241022")

        # Gemini
        client = LiteLLMClient(model="gemini/gemini-2.0-flash-exp")

        # AWS Bedrock
        client = LiteLLMClient(model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0")
    """

    def __init__(
        self,
        model: str,
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """
        Initialize LiteLLM client.

        Args:
            model: Model name in LiteLLM format (e.g., 'gpt-4o-mini', 'claude-3-5-sonnet-20241022')
            max_retries: Maximum number of retries for API calls
            timeout: Timeout in seconds for API calls

        LiteLLM automatically detects provider from model name:
        - "gpt-4o" -> OpenAI (uses OPENAI_API_KEY)
        - "claude-3-5-sonnet-20241022" -> Anthropic (uses ANTHROPIC_API_KEY)
        - "gemini/gemini-2.0-flash-exp" -> Google (uses GOOGLE_API_KEY)
        - "bedrock/..." -> AWS Bedrock (uses AWS credentials)
        """
        try:
            import litellm
            self.litellm = litellm
        except ImportError:
            raise ImportError(
                "litellm is required for LiteLLMClient. "
                "Install it with: pip install litellm"
            )

        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout

        # Configure LiteLLM
        litellm.set_verbose = False  # Disable verbose logging
        litellm.drop_params = True   # Auto-drop unsupported params per provider

        logger.info(f"Initialized LiteLLMClient with model: {model}")

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
            tools: Optional list of tool/function definitions (OpenAI format)
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
                "timeout": self.timeout,
            }

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            # Make API call via LiteLLM
            response = self.litellm.completion(**kwargs)

            # Extract response (LiteLLM returns OpenAI-compatible format)
            message = response.choices[0].message
            result: Dict[str, Any] = {
                "content": message.content or "",
                "role": message.role,
            }

            # Extract tool calls if present
            if hasattr(message, 'tool_calls') and message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "arguments": eval(tool_call.function.arguments),  # Parse JSON string to dict
                    }
                    for tool_call in message.tool_calls
                ]

            logger.debug(f"LiteLLM response: {result}")
            return result

        except Exception as e:
            logger.error(f"Error generating LiteLLM response: {e}")
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

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text using LiteLLM.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector as list of floats
        """
        try:
            # Clean text
            text = text.replace("\n", " ").strip()
            if not text:
                logger.warning("Empty text provided for embedding, returning zero vector")
                # Return appropriate zero vector based on model
                dim = EMBEDDING_DIMENSIONS.get(self.model, 1536)
                return [0.0] * dim

            # Call embedding API via LiteLLM
            logger.debug(f"LiteLLM embedding call for: '{text[:50]}...'")
            response = self.litellm.embedding(
                model=self.model,
                input=text,
            )

            # Extract embedding (LiteLLM returns OpenAI-compatible format)
            embedding = response.data[0]['embedding']

            logger.debug(f"Generated embedding for text: '{text[:50]}...' (dim: {len(embedding)})")
            return embedding

        except Exception as e:
            logger.error(f"Error generating LiteLLM embedding: {e}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using LiteLLM.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            if not texts:
                return []

            # Clean texts
            clean_texts = [text.replace("\n", " ").strip() for text in texts]

            # Call embedding API via LiteLLM (handles batching internally)
            logger.debug(f"LiteLLM batch embedding call for {len(clean_texts)} texts")
            response = self.litellm.embedding(
                model=self.model,
                input=clean_texts,
            )

            # Extract embeddings (LiteLLM returns OpenAI-compatible format)
            embeddings = [item['embedding'] for item in response.data]

            logger.debug(f"Generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Error generating batch embeddings with LiteLLM: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def create_structured_output(
        self,
        text_input: str,
        system_prompt: str,
        response_model: Type[BaseModel],
        temperature: float = 0.0,
    ) -> BaseModel:
        """
        Generate structured output parsed into a Pydantic model.

        Uses LiteLLM's JSON mode with schema guidance in the prompt.

        Args:
            text_input: The user input text to process
            system_prompt: System prompt with instructions
            response_model: Pydantic model class for response validation
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            Instance of response_model with parsed data
        """
        try:
            # Get JSON schema from Pydantic model for prompt guidance
            schema = response_model.model_json_schema()
            schema_str = json.dumps(schema, indent=2)

            enhanced_prompt = f"""{system_prompt}

You MUST respond with valid JSON that conforms to this schema:
{schema_str}

Output ONLY the JSON object, no other text."""

            messages = [
                {"role": "system", "content": enhanced_prompt},
                {"role": "user", "content": text_input},
            ]

            # Make API call with JSON response format
            response = self.litellm.completion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                timeout=self.timeout,
                response_format={"type": "json_object"},
            )

            # Parse response
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            result = response_model.model_validate(data)

            logger.debug(f"Structured output: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LiteLLM response: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating structured output with LiteLLM: {e}")
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

        Args:
            text_input: The user input text to process
            system_prompt: System prompt with instructions
            response_model: Pydantic model class for response validation
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            Instance of response_model with parsed data
        """
        try:
            # Get JSON schema from Pydantic model for prompt guidance
            schema = response_model.model_json_schema()
            schema_str = json.dumps(schema, indent=2)

            enhanced_prompt = f"""{system_prompt}

You MUST respond with valid JSON that conforms to this schema:
{schema_str}

Output ONLY the JSON object, no other text."""

            messages = [
                {"role": "system", "content": enhanced_prompt},
                {"role": "user", "content": text_input},
            ]

            # Make async API call with JSON response format
            response = await self.litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                timeout=self.timeout,
                response_format={"type": "json_object"},
            )

            # Parse response
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            result = response_model.model_validate(data)

            logger.debug(f"Async structured output: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LiteLLM response: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating async structured output with LiteLLM: {e}")
            raise

    def __repr__(self) -> str:
        """String representation."""
        return f"LiteLLMClient(model='{self.model}')"
