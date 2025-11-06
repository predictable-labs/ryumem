"""
Ollama LLM client adapter for local model inference.

Provides the same interface as LLMClient but uses Ollama for local inference.
Supports models like Llama, Mistral, Qwen, etc.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Ollama client for local LLM inference.

    Compatible with the LLMClient interface for drop-in replacement.
    """

    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        max_retries: int = 3,
        timeout: int = 120,
    ):
        """
        Initialize Ollama client.

        Args:
            model: Ollama model name (e.g., "llama3.2:3b", "mistral", "qwen2.5:7b")
            base_url: Ollama server URL
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds

        Example models:
            - llama3.2:3b (fast, good quality)
            - mistral:7b (excellent reasoning)
            - qwen2.5:7b (great for structured output)
            - llama3.1:8b (balanced performance)
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # Verify Ollama is running
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            logger.info(f"Connected to Ollama at {self.base_url}")
        except Exception as e:
            logger.warning(f"Could not connect to Ollama: {e}")
            logger.warning("Make sure Ollama is running: ollama serve")

        logger.info(f"Initialized OllamaClient with model: {model}")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate completion using Ollama with retry logic.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional format specification (e.g., {"type": "json_object"})

        Returns:
            Response dict with 'content' key

        Example:
            response = client.generate([
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "What is the capital of France?"}
            ])
            print(response["content"])
        """
        # Build prompt from messages
        prompt = self._messages_to_prompt(messages)

        # Prepare request
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        # Add JSON format if requested
        if response_format and response_format.get("type") == "json_object":
            payload["format"] = "json"
            logger.debug(f"🔧 Requesting JSON format from Ollama")

        # Retry logic with exponential backoff
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                # Make request
                logger.debug(f"📤 Ollama request (attempt {attempt}/{self.max_retries}): model={self.model}, format={payload.get('format', 'text')}, timeout={self.timeout}s")

                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                result = response.json()
                content = result.get("response", "").strip()

                logger.debug(f"✅ Ollama response received (attempt {attempt}): {len(content)} chars")
                logger.debug(f"Generated response: '{content[:100]}...'")

                return {"content": content}

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Exponential backoff: 2s, 4s, 8s, 16s, ...
                    wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                    logger.warning(f"⚠️ Ollama timeout on attempt {attempt}/{self.max_retries}. Retrying in {wait_time}s... (timeout was {self.timeout}s)")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Ollama timeout after {self.max_retries} attempts (timeout: {self.timeout}s)")

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = min(2 ** attempt, 30)
                    logger.warning(f"⚠️ Ollama connection error on attempt {attempt}/{self.max_retries}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Ollama connection failed after {self.max_retries} attempts")

            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = min(2 ** attempt, 30)
                    logger.warning(f"⚠️ Ollama request error on attempt {attempt}/{self.max_retries}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Ollama request failed after {self.max_retries} attempts: {e}")

            except Exception as e:
                # For unexpected errors, don't retry
                logger.error(f"❌ Unexpected error during Ollama generation: {e}")
                raise

        # If we get here, all retries failed
        logger.error(f"❌ Ollama generation failed after {self.max_retries} attempts")
        raise last_exception if last_exception else Exception("Ollama generation failed")

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Convert OpenAI-style messages to a single prompt string.

        Args:
            messages: List of message dicts

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                prompt_parts.append(f"System: {content}\n")
            elif role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")

        prompt_parts.append("Assistant:")
        return "\n".join(prompt_parts)

    def extract_entities(
        self,
        text: str,
        user_id: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Extract entities from text using Ollama.

        Args:
            text: Text to extract entities from
            user_id: User ID for self-reference resolution
            context: Optional context from previous episodes

        Returns:
            List of entity dicts with 'entity' and 'entity_type' keys
        """
        system_prompt = """You are an entity extraction system. Your ONLY task is to output valid JSON.

DO NOT write explanations, comments, or conversational text.
DO NOT say things like "Here are the entities" or "The text contains".
ONLY output the JSON array, nothing else.

Extract all important entities (people, places, organizations, concepts, etc.) and return them in this EXACT format:
[
  {"entity": "entity_name", "entity_type": "PERSON"},
  {"entity": "entity_name", "entity_type": "LOCATION"}
]

Valid entity types: PERSON, LOCATION, ORGANIZATION, EVENT, CONCEPT, OTHER

Rules:
- Output MUST be valid JSON
- Be comprehensive but avoid duplicates
- Use proper capitalization for entity names
- If no entities found, return empty array: []"""

        user_prompt = f"""Text: "{text}"

User ID: {user_id} (use this for resolving "I", "me", "my")"""

        if context:
            user_prompt += f"\n\nContext from previous episodes:\n{context}"

        user_prompt += "\n\nOutput the JSON array now (no other text):"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # Note: Not using response_format here because it can confuse some models
            # into returning a single object instead of an array
            response = self.generate(
                messages,
                temperature=0.1,  # Lower temperature for more deterministic output
            )

            content = response["content"].strip()

            # Debug logging to see raw response
            logger.info(f"🔍 Raw Ollama response for entity extraction:")
            logger.info(f"   Prompt: {user_prompt[:100]}...")
            logger.info(f"   Response: {content}")

            # Try multiple JSON extraction strategies
            entities = self._extract_json_array(content)

            if entities is None:
                logger.warning(f"Could not extract valid JSON from: {content[:200]}...")
                return []

            # Validate structure
            if not isinstance(entities, list):
                logger.warning(f"Expected list, got: {type(entities)}")
                return []

            # Validate each entity has required fields
            valid_entities = []
            for entity in entities:
                if isinstance(entity, dict) and "entity" in entity and "entity_type" in entity:
                    valid_entities.append(entity)
                else:
                    logger.warning(f"Skipping invalid entity: {entity}")

            return valid_entities

        except Exception as e:
            logger.error(f"Error extracting entities with Ollama: {e}")
            return []

    def _extract_json_array(self, content: str) -> Optional[List]:
        """
        Extract JSON array from text using multiple strategies.

        Args:
            content: Text that may contain JSON

        Returns:
            Parsed JSON array or None if extraction fails
        """
        import re

        # Strategy 1: Direct JSON parse
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
            # If it's a single dict that looks like an entity/relationship, wrap it in an array
            if isinstance(result, dict):
                # Check if it's a single entity object (has 'entity' and 'entity_type')
                if "entity" in result and "entity_type" in result:
                    logger.debug("Wrapping single entity object in array")
                    return [result]
                # Check if it's a single relationship object
                if all(k in result for k in ["source", "relationship", "destination", "fact"]):
                    logger.debug("Wrapping single relationship object in array")
                    return [result]
                # If it's a dict with an array value, try to extract it
                for value in result.values():
                    if isinstance(value, list):
                        return value
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code blocks
        if "```json" in content:
            try:
                json_str = content.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        if "```" in content:
            try:
                json_str = content.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        # Strategy 3: Find JSON array using regex
        array_pattern = r'\[\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*\]'
        matches = re.findall(array_pattern, content, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        # Strategy 4: Find anything between [ and ]
        if '[' in content and ']' in content:
            try:
                start = content.index('[')
                end = content.rindex(']') + 1
                json_str = content[start:end]
                return json.loads(json_str)
            except (ValueError, json.JSONDecodeError):
                pass

        # Strategy 5: Handle JSONL format (multiple objects on separate lines)
        # This sometimes happens with local models
        lines = content.strip().split('\n')
        objects = []
        for line in lines:
            line = line.strip()
            if line and (line.startswith('{') or line.startswith('[')):
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        objects.append(obj)
                    elif isinstance(obj, list):
                        objects.extend(obj)
                except json.JSONDecodeError:
                    continue
        if objects:
            logger.debug(f"Extracted {len(objects)} objects from JSONL format")
            return objects

        return None

    def extract_relationships(
        self,
        text: str,
        entities: List[str],
        user_id: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Extract relationships between entities using Ollama.

        Args:
            text: Text to extract relationships from
            entities: List of entity names to find relationships for
            user_id: User ID for context
            context: Optional context

        Returns:
            List of relationship dicts with source, relationship, destination, fact
        """
        system_prompt = """You are a relationship extraction system. Your ONLY task is to output valid JSON.

DO NOT write explanations, comments, or conversational text.
DO NOT say things like "Here are the relationships" or "Based on the text".
ONLY output the JSON array, nothing else.

Given a text and entities, extract relationships between them in this EXACT format:
[
  {
    "source": "source_entity",
    "relationship": "WORKS_AT",
    "destination": "destination_entity",
    "fact": "Full sentence describing the relationship"
  }
]

Rules:
- Output MUST be valid JSON
- Use clear, uppercase relationship types: WORKS_AT, LIVES_IN, KNOWS, GRADUATED_FROM, etc.
- Only include relationships explicitly stated in the text
- If no relationships found, return empty array: []"""

        entities_str = ", ".join(entities)
        user_prompt = f"""Text: "{text}"

Entities: {entities_str}

User ID: {user_id}"""

        if context:
            user_prompt += f"\n\nContext:\n{context}"

        user_prompt += "\n\nOutput the JSON array now (no other text):"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # Note: Not using response_format here because it can confuse some models
            # into returning a single object instead of an array
            response = self.generate(
                messages,
                temperature=0.1,  # Lower temperature for more deterministic output
            )

            content = response["content"].strip()

            logger.debug(f"🔍 Raw Ollama response for relationship extraction: {content[:300]}...")

            # Try multiple JSON extraction strategies
            relationships = self._extract_json_array(content)

            if relationships is None:
                logger.warning(f"Could not extract valid JSON from: {content[:200]}...")
                return []

            if not isinstance(relationships, list):
                logger.warning(f"Expected list, got: {type(relationships)}")
                return []

            # Validate each relationship has required fields
            valid_relationships = []
            required_fields = {"source", "relationship", "destination", "fact"}
            for rel in relationships:
                if isinstance(rel, dict) and all(field in rel for field in required_fields):
                    valid_relationships.append(rel)
                else:
                    logger.warning(f"Skipping invalid relationship: {rel}")

            return valid_relationships

        except Exception as e:
            logger.error(f"Error extracting relationships with Ollama: {e}")
            return []

    def detect_contradictions(
        self,
        new_facts: List[str],
        existing_facts: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Detect contradictions between new and existing facts.

        Args:
            new_facts: List of new fact strings
            existing_facts: List of existing fact strings

        Returns:
            List of contradiction dicts with new_fact_index, existing_fact_index, reason
        """
        if not new_facts or not existing_facts:
            return []

        system_prompt = """You are an expert at detecting contradictions in facts.
Compare new facts against existing facts and identify any contradictions.

Return ONLY a JSON array of contradictions with this format:
[
  {
    "new_fact_index": 0,
    "existing_fact_index": 1,
    "reason": "Brief explanation of the contradiction"
  }
]

If there are no contradictions, return an empty array: []"""

        new_facts_str = "\n".join([f"{i}. {fact}" for i, fact in enumerate(new_facts)])
        existing_facts_str = "\n".join(
            [f"{i}. {fact}" for i, fact in enumerate(existing_facts)]
        )

        user_prompt = f"""New facts:
{new_facts_str}

Existing facts:
{existing_facts_str}

Detect contradictions as JSON:"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = self.generate(
                messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            content = response["content"].strip()

            # Parse JSON
            try:
                contradictions = json.loads(content)
            except json.JSONDecodeError:
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                    contradictions = json.loads(json_str)
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                    contradictions = json.loads(json_str)
                else:
                    return []

            if not isinstance(contradictions, list):
                return []

            return contradictions

        except Exception as e:
            logger.error(f"Error detecting contradictions with Ollama: {e}")
            return []

    def __repr__(self) -> str:
        """String representation."""
        return f"OllamaClient(model='{self.model}', base_url='{self.base_url}')"
