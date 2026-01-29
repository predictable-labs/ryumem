"""
Gemini LLM client adapter for Google's Generative AI.

Provides the same interface as LLMClient but uses Google's Gemini models.
Supports both LLM operations and embeddings.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from .llm_base import LLMExtractionMixin

logger = logging.getLogger(__name__)


class GeminiClient(LLMExtractionMixin):
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
        system_prompt, user_prompt, tools = self.build_extract_entities_prompt(
            text, user_id, context
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self.generate(messages, tools=tools)
        entities = self.parse_entities_response(response)

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
        system_prompt, user_prompt, tools = self.build_extract_relationships_prompt(
            text, entities, user_id, context
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self.generate(messages, tools=tools)
        relationships = self.parse_relationships_response(response)

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
        system_prompt, user_prompt, tools = self.build_detect_contradictions_prompt(
            new_facts, existing_facts
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self.generate(messages, tools=tools)
        contradictions = self.parse_contradictions_response(response)

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

        Uses Gemini's controlled generation with JSON schema.

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

            # Convert messages to Gemini format
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_input},
            ]
            gemini_messages = self._convert_messages(messages)

            # Use Gemini's JSON mode with schema
            response = self.client.models.generate_content(
                model=self.model,
                contents=gemini_messages,
                config=self.genai.types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                )
            )

            # Parse response into Pydantic model
            content = response.text.strip()
            data = json.loads(content)
            result = response_model.model_validate(data)

            logger.debug(f"Structured output: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating structured output with Gemini: {e}")
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

        Note: Gemini client is synchronous, so this runs in a thread pool.

        Args:
            text_input: The user input text to process
            system_prompt: System prompt with instructions
            response_model: Pydantic model class for response validation
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            Instance of response_model with parsed data
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.create_structured_output(
                text_input, system_prompt, response_model, temperature
            )
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"GeminiClient(model='{self.model}')"
