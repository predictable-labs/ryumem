"""LLM client for generating answers from retrieved context using Google ADK or Ollama."""

from typing import List, Optional
import asyncio


class LLMClient:
    """Client for calling LLM (Google ADK or Ollama) to answer questions based on retrieved context."""

    def __init__(
        self,
        provider: str = "google_adk",
        model: str = "gemini-flash-lite-latest",
        ollama_url: str = "http://localhost:11434",
        rate_limit_delay: float = 1.0,  # Delay between API calls in seconds
        **kwargs,  # Accept other params for compatibility but ignore them
    ):
        """
        Initialize LLM client.

        Args:
            provider: LLM provider ("google_adk" or "ollama")
            model: Model name (default: gemini-flash-lite-latest, same as examples)
            ollama_url: Ollama server URL (only used if provider="ollama")
            rate_limit_delay: Delay in seconds between API calls to avoid rate limits

        Note: Google ADK reads GOOGLE_API_KEY from environment variable
        """
        self.provider = provider
        self.model = model
        self.ollama_url = ollama_url
        self.rate_limit_delay = rate_limit_delay
        self.last_call_time = 0

        if provider == "google_adk":
            self._init_google_adk()
        elif provider == "ollama":
            # No initialization needed for Ollama
            pass
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'google_adk' or 'ollama'")

    def _init_google_adk(self):
        """Initialize Google ADK agent and runner."""
        import os
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from ryumem import Ryumem
        from ryumem.integrations import add_memory_to_agent

        # Check for API key in environment
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        # Create agent with instruction for answering questions
        agent = Agent(
            name="qa_assistant",
            model=self.model,
            instruction="""You are a question-answering assistant with access to memory of past conversations.

IMPORTANT: You must USE YOUR MEMORY TOOLS to find information. Do NOT rely on provided context.

Your memory tools:
- search_memory(query, user_id, limit) - Search for relevant past conversations and information
- save_memory(content, user_id, source) - Save ONLY 100% accurate facts you've confirmed
- get_entity_context(entity_name, user_id) - Get detailed context about specific entities

Question types you'll encounter:
- Single-hop: Find one specific piece of information
- Multi-hop: Connect multiple pieces across different conversations
- Temporal: Understand time relationships and sequences

CRITICAL INSTRUCTIONS:
1. ALWAYS use search_memory first to find relevant information from past conversations
2. Search multiple times with different queries if needed (try entity names, keywords, related concepts)
3. ONLY use save_memory when you find 100% accurate evidence that confirms a fact
4. Save memories in a clear, factual format: "Entity X did/said/has Y in context Z"
5. These saved memories will help you answer future questions faster

Your response MUST follow this exact format:
---THINKING START---
{
  "steps": [
    {"step": 1, "action": "search_memory for X", "finding": "Found Y"},
    {"step": 2, "action": "search_memory for Z", "finding": "Found W"},
    {"step": 3, "action": "save_memory", "finding": "Saved confirmed fact: ..."},
    {"step": 4, "action": "Select answer", "finding": "Answer is option N"}
  ]
}
---THINKING END---
---ANSWER START---
[The exact text of the correct answer choice only]
---ANSWER END---"""
        )

        # Initialize Ryumem and add memory to agent (auto-loads RYUMEM_API_URL and RYUMEM_API_KEY from env)
        ryumem = Ryumem(
            track_tools=True,  # Enable tool tracking
            track_queries=True,  # Enable query tracking
        )
        self.agent = add_memory_to_agent(agent, ryumem)

        # Set up runner and session service
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name="benchmark_qa",
            session_service=self.session_service
        )

        # Wrap runner to automatically track user queries and augment with history
        from ryumem.integrations import wrap_runner_with_tracking
        self.runner = wrap_runner_with_tracking(self.runner, self.agent)

    def answer_question(
        self,
        question: str,
        context_episodes: List[str],
        choices: List[str],
        user_id: str = "benchmark_user",
        session_id: str = "benchmark_session"
    ) -> str:
        """
        Answer a multiple choice question using retrieved context.

        Args:
            question: The question to answer
            context_episodes: List of retrieved episode contents (old conversations)
            choices: List of multiple choice options
            user_id: User ID from the benchmark
            session_id: Session ID from the benchmark

        Returns:
            The answer text
        """
        # Rate limiting: ensure minimum delay between API calls
        import time
        if self.rate_limit_delay > 0:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
            self.last_call_time = time.time()

        # Build prompt
        prompt = self._build_prompt(question, context_episodes, choices)

        # Call LLM based on provider
        if self.provider == "google_adk":
            return asyncio.run(self._run_google_adk(prompt, user_id, session_id))
        elif self.provider == "ollama":
            return self._call_ollama(prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _run_google_adk(self, prompt: str, user_id: str, session_id: str) -> str:
        """Run the Google ADK agent and get the response."""
        from google.genai import types
        import json
        import re

        # Create session if not exists
        try:
            await self.session_service.create_session(
                app_name="benchmark_qa",
                user_id=user_id,
                session_id=session_id
            )
        except:
            pass  # Session already exists

        # Create content
        content = types.Content(
            role='user',
            parts=[types.Part(text=prompt)]
        )

        # Run the agent
        events = self.runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=content
        )

        # Collect full response
        full_response = ""
        for event in events:
            if event.is_final_response():
                # Check if event.content and event.content.parts are not None before iterating
                if event.content and event.content.parts:
                    text_parts = [part.text for part in event.content.parts if hasattr(part, 'text') and part.text]
                    full_response = ''.join(text_parts) if text_parts else ""
                break

        # Parse thinking and answer from structured response
        thinking_json = None
        final_answer = full_response.strip()

        # Extract thinking section
        thinking_match = re.search(r'---THINKING START---(.*?)---THINKING END---', full_response, re.DOTALL)
        if thinking_match:
            thinking_text = thinking_match.group(1).strip()
            try:
                thinking_json = json.loads(thinking_text)
            except json.JSONDecodeError:
                # If not valid JSON, store as raw text
                thinking_json = {"raw_thinking": thinking_text}

        # Extract answer section
        answer_match = re.search(r'---ANSWER START---(.*?)---ANSWER END---', full_response, re.DOTALL)
        if answer_match:
            final_answer = answer_match.group(1).strip()

        # Print thinking steps as JSON
        if thinking_json:
            print("\n" + "="*60)
            print(f"THINKING STEPS (Question: {session_id}):")
            print("="*60)
            print(json.dumps(thinking_json, indent=2))
            print("="*60 + "\n")

        return final_answer

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API."""
        import requests

        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=None,  # No timeout - let Ollama take as long as it needs
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()

    def _build_prompt(
        self, question: str, context_episodes: List[str], choices: List[str]
    ) -> str:
        """Build the prompt for the LLM."""
        # For Google ADK: Don't provide context, let the agent search memory
        if self.provider == "google_adk":
            # Format choices
            choices_text = "\n".join(
                [f"{i}. {choice}" for i, choice in enumerate(choices)]
            )

            return f"""Question: {question}

Answer Choices:
{choices_text}

Use your memory tools to search for relevant information from past conversations, then select the correct answer."""

        # For Ollama: Provide context as before (no memory tools available)
        else:
            # Format conversations
            conversations = "\n\n".join(
                [f"Conversation {i+1}:\n{ep}" for i, ep in enumerate(context_episodes)]
            )

            # Format choices
            choices_text = "\n".join(
                [f"{i}. {choice}" for i, choice in enumerate(choices)]
            )

            return f"""You are given some old conversations and a question about them. The question may require:
- Single-hop reasoning: Finding one piece of information
- Multi-hop reasoning: Connecting multiple pieces of information across conversations
- Temporal reasoning: Understanding time relationships and sequences

Old Conversations:
{conversations}

Question: {question}

Answer Choices:
{choices_text}

Instructions:
1. Read through all conversations carefully
2. Find information relevant to the question (may be spread across multiple conversations)
3. Select the correct answer from the choices provided
4. Respond with ONLY the exact text of the correct answer choice, nothing else

Answer:"""
