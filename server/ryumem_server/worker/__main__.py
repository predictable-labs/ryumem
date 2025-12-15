"""
Entry point for running the entity extraction worker.

Usage:
    python -m ryumem_server.worker

Environment variables:
    REDIS_URL - Redis connection URL (default: redis://localhost:6379)
    SERVER_URL - Ryumem server URL (default: http://localhost:8000)
    WORKER_INTERNAL_KEY - Shared secret for internal endpoints
    GOOGLE_API_KEY - API key for Gemini (default provider)
    OPENAI_API_KEY - API key for OpenAI (if using openai provider)
    LLM_PROVIDER - LLM provider (default: gemini)
    EMBEDDING_PROVIDER - Embedding provider (default: gemini)
    LLM_MODEL - Model name for extraction
    EMBEDDING_MODEL - Model name for embeddings
"""

import asyncio

# Load .env file before importing anything else
from dotenv import load_dotenv
load_dotenv()

from ryumem_server.worker.entity_extraction import main

if __name__ == "__main__":
    asyncio.run(main())
