"""LLM client for generating answers from retrieved context using Google ADK."""

from typing import List, Optional
import asyncio


class LLMClient:
    """Client for calling Google ADK (Gemini) to answer questions based on retrieved context."""

    def __init__(
        self,
        model: str = "gemini-2.0-flash-exp",
        **kwargs,  # Accept other params for compatibility but ignore them
    ):
        """
        Initialize LLM client with Google ADK.

        Args:
            model: Gemini model name (default: gemini-2.0-flash-exp)

        Note: Reads GOOGLE_API_KEY from environment variable
        """
        import os
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        # Check for API key in environment
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        self.model = model

        # Create agent with instruction for answering questions
        self.agent = Agent(
            name="qa_assistant",
            model=model,
            instruction="""You are given some old conversations and a question about them. The question may require:
- Single-hop reasoning: Finding one piece of information
- Multi-hop reasoning: Connecting multiple pieces of information across conversations
- Temporal reasoning: Understanding time relationships and sequences

Your task:
1. Read through all conversations carefully
2. Find information relevant to the question (may be spread across multiple conversations)
3. Select the correct answer from the choices provided
4. Respond with ONLY the exact text of the correct answer choice, nothing else"""
        )

        # Set up runner and session service
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name="benchmark_qa",
            session_service=self.session_service
        )

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
        # Build prompt
        prompt = self._build_prompt(question, context_episodes, choices)

        # Run the agent synchronously
        return asyncio.run(self._run_agent(prompt, user_id, session_id))

    async def _run_agent(self, prompt: str, user_id: str, session_id: str) -> str:
        """Run the agent and get the response."""
        from google.genai import types

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

        # Extract response
        for event in events:
            if event.is_final_response():
                text_parts = [part.text for part in event.content.parts if hasattr(part, 'text') and part.text]
                return ''.join(text_parts) if text_parts else ""

        return ""

    def _build_prompt(
        self, question: str, context_episodes: List[str], choices: List[str]
    ) -> str:
        """Build the prompt for the LLM."""
        # Format conversations
        conversations = "\n\n".join(
            [f"Conversation {i+1}:\n{ep}" for i, ep in enumerate(context_episodes)]
        )

        # Format choices
        choices_text = "\n".join(
            [f"{i}. {choice}" for i, choice in enumerate(choices)]
        )

        return f"""Old Conversations:
{conversations}

Question: {question}

Answer Choices:
{choices_text}

Respond with ONLY the exact text of the correct answer choice, nothing else.

Answer:"""
