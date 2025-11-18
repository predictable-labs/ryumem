"""
Gemini LLM client adapter for Google's Generative AI.

Provides the same interface as LLMClient but uses Google's Gemini models.
Supports both LLM operations and embeddings.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Gemini client for Google AI inference.

    Compatible with the LLMClient interface for drop-in replacement.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash-exp",
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Google API key (optional, will use GOOGLE_API_KEY env var if not provided)
            model: Gemini model name (e.g., "gemini-2.0-flash-exp", "gemini-1.5-pro")
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds

        Example models:
            - gemini-2.0-flash-exp (fast, great quality)
            - gemini-1.5-pro (best reasoning)
            - gemini-1.5-flash (fast, good quality)
        """
        try:
            import google.genai as genai
            self.genai = genai
        except ImportError:
            raise ImportError(
                "google-genai is required for GeminiClient. "
                "Install it with: pip install google-genai"
            )

        # Initialize client - google.genai automatically uses GOOGLE_API_KEY env var
        # if api_key is not provided
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = genai.Client()

        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout

        logger.info(f"Initialized GeminiClient with model: {model}")

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
        Generate a response from Gemini with optional function calling.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tool/function definitions (OpenAI format)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Response dictionary with 'content' and optional 'tool_calls'
        """
        try:
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages(messages)

            # Prepare generation config
            config = {
                "temperature": temperature,
            }
            if max_tokens:
                config["max_output_tokens"] = max_tokens

            # Convert tools if provided
            gemini_tools = None
            if tools:
                gemini_tools = self._convert_tools(tools)

            # Make API call
            if gemini_tools:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=gemini_messages,
                    config=self.genai.types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                        tools=gemini_tools,
                    )
                )
            else:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=gemini_messages,
                    config=self.genai.types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    )
                )

            # Extract response
            result: Dict[str, Any] = {
                "content": response.text or "",
                "role": "assistant",
            }

            # Extract tool calls if present
            if response.candidates and response.candidates[0].content.parts:
                tool_calls = []
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        tool_calls.append({
                            "id": f"call_{hash(fc.name)}",  # Generate ID
                            "name": fc.name,
                            "arguments": dict(fc.args) if fc.args else {},
                        })

                if tool_calls:
                    result["tool_calls"] = tool_calls

            logger.debug(f"Gemini response: {result}")
            return result

        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            raise

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List:
        """
        Convert OpenAI-style messages to Gemini format.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            List of Gemini Content objects
        """
        gemini_messages = []
        system_instruction = None

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                # Gemini uses system_instruction separately
                system_instruction = content
            elif role == "user":
                gemini_messages.append(
                    self.genai.types.Content(
                        role="user",
                        parts=[self.genai.types.Part(text=content)]
                    )
                )
            elif role == "assistant":
                gemini_messages.append(
                    self.genai.types.Content(
                        role="model",  # Gemini uses 'model' instead of 'assistant'
                        parts=[self.genai.types.Part(text=content)]
                    )
                )

        # Prepend system instruction as first user message if present
        if system_instruction:
            gemini_messages.insert(0, self.genai.types.Content(
                role="user",
                parts=[self.genai.types.Part(text=f"System: {system_instruction}")]
            ))

        return gemini_messages

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List:
        """
        Convert OpenAI-style tools to Gemini format.

        Args:
            tools: List of tool definitions in OpenAI format

        Returns:
            List of Gemini Tool objects
        """
        gemini_tools = []

        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]

                # Convert parameters
                params = func.get("parameters", {})

                gemini_func = self.genai.types.FunctionDeclaration(
                    name=func["name"],
                    description=func.get("description", ""),
                    parameters=params
                )

                gemini_tools.append(self.genai.types.Tool(
                    function_declarations=[gemini_func]
                ))

        return gemini_tools

    def extract_entities(
        self,
        text: str,
        user_id: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Extract entities from text using Gemini function calling.

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
        Extract relationships between entities using Gemini function calling.

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
        Generate embedding for a single text using Google's embedding API.
        Compatible with EmbeddingClient interface.

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
                # Return 768-dimensional zero vector for text-embedding-004
                return [0.0] * 768

            # Call embedding API
            logger.debug(f"🌐 Gemini API call for embedding: '{text[:50]}...'")
            model_name = self.model if self.model == "text-embedding-004" else "text-embedding-004"
            result = self.client.models.embed_content(
                model=model_name,
                contents=text,  # Changed from 'content' to 'contents'
            )

            # Extract embedding
            # Handle both response formats
            if hasattr(result, 'embeddings'):
                embedding = result.embeddings[0].values
            elif hasattr(result, 'embedding'):
                embedding = result.embedding.values if hasattr(result.embedding, 'values') else result.embedding
            else:
                raise ValueError(f"Unexpected embedding response format: {type(result)}")

            logger.debug(f"Generated Gemini embedding for text: '{text[:50]}...' (dim: {len(embedding)})")
            return embedding

        except Exception as e:
            logger.error(f"Error generating Gemini embedding: {e}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using Google's embedding API.
        Compatible with EmbeddingClient interface.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            if not texts:
                return []

            embeddings = []

            # Process in batches to avoid rate limits
            batch_size = 100
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]

                # Clean texts
                clean_batch = [text.replace("\n", " ").strip() for text in batch]

                # Call embedding API
                result = self.client.models.embed_content(
                    model=self.model if self.model == "text-embedding-004" else "text-embedding-004",
                    contents=clean_batch,
                )

                # Extract embeddings
                for embedding in result.embeddings:
                    embeddings.append(embedding.values)

            logger.debug(f"Generated {len(embeddings)} Gemini embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Error generating batch embeddings with Gemini: {e}")
            raise

    def __repr__(self) -> str:
        """String representation."""
        return f"GeminiClient(model='{self.model}')"
