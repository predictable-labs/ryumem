"""
Example: Using Ryumem with LiteLLM for multi-provider LLM support

This example demonstrates how to use Ryumem with LiteLLM to access
100+ LLM providers through a unified interface.

LiteLLM automatically detects the provider from the model name and
uses the appropriate API key from environment variables.

Supported providers include:
- OpenAI (gpt-4o, gpt-4o-mini, etc.)
- Anthropic Claude (claude-3-5-sonnet-20241022, etc.)
- Google Gemini (gemini/gemini-2.0-flash-exp, etc.)
- AWS Bedrock (bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0, etc.)
- Cohere (command-r-plus, etc.)
- And 100+ more!
"""

import os
from ryumem import Ryumem
from ryumem.core.config import RyumemConfig
from dotenv import load_dotenv

load_dotenv()

# Set up environment variables (normally loaded from .env file)
# os.environ["ANTHROPIC_API_KEY"] = "your-anthropic-key"
# os.environ["OPENAI_API_KEY"] = "your-openai-key"
# os.environ["GOOGLE_API_KEY"] = "your-google-key"


def example_1_anthropic_claude():
    """
    Example 1: Using Anthropic Claude with automatic embedding fallback

    Since Anthropic doesn't provide embeddings, Ryumem will automatically
    fall back to OpenAI or Gemini embeddings if the API key is available.
    """
    print("\n" + "="*80)
    print("Example 1: Anthropic Claude with LiteLLM")
    print("="*80)

    # Configure for Anthropic Claude via LiteLLM
    config = RyumemConfig()
    config.llm.provider = "litellm"
    config.llm.model = "claude-3-5-sonnet-20241022"
    # Embedding will auto-fallback to Gemini (configured in validate_provider_compatibility)

    # Initialize Ryumem
    ryumem = Ryumem(config=config)

    # Add some episodes
    ryumem.add_episode(
        "Alice is a software engineer at Anthropic working on Claude.",
        user_id="user_1"
    )

    ryumem.add_episode(
        "Bob met Alice at the AI conference in San Francisco.",
        user_id="user_1"
    )

    print("\n✅ Example 1 completed successfully!")


def example_2_openai_via_litellm():
    """
    Example 2: Using OpenAI via LiteLLM with automatic embedding selection

    LiteLLM can also be used with OpenAI models. The embedding model
    will be automatically selected based on the LLM model.
    """
    print("\n" + "="*80)
    print("Example 2: OpenAI via LiteLLM")
    print("="*80)

    # Configure for OpenAI via LiteLLM
    config = RyumemConfig()
    config.llm.provider = "litellm"
    config.llm.model = "gpt-4o-mini"
    # Embedding will auto-select to "text-embedding-3-large" via LiteLLM

    # Initialize Ryumem
    ryumem = Ryumem(config=config)

    # Add episodes
    ryumem.add_episode(
        "The company annual meeting is scheduled for next Monday at 2 PM.",
        user_id="user_2"
    )

    ryumem.add_episode(
        "Please bring your laptop and presentation materials.",
        user_id="user_2"
    )

    print("\n✅ Example 2 completed successfully!")


def example_3_gemini_via_litellm():
    """
    Example 3: Using Google Gemini via LiteLLM

    Demonstrates using Gemini models through LiteLLM with automatic
    embedding model selection.
    """
    print("\n" + "="*80)
    print("Example 3: Google Gemini via LiteLLM")
    print("="*80)

    # Configure for Gemini via LiteLLM
    config = RyumemConfig()
    config.llm.provider = "litellm"
    config.llm.model = "gemini/gemini-2.0-flash-exp"
    # Embedding will auto-select to "text-embedding-004" via LiteLLM

    # Initialize Ryumem
    ryumem = Ryumem(config=config)

    # Add episodes
    ryumem.add_episode(
        "Project Alpha deadline is December 15th.",
        user_id="user_3"
    )

    ryumem.add_episode(
        "We need to complete the frontend redesign before the deadline.",
        user_id="user_3"
    )

    print("\n✅ Example 3 completed successfully!")


def example_4_mixed_providers():
    """
    Example 4: Mixed provider configuration

    Use LiteLLM for LLM operations but OpenAI directly for embeddings.
    This demonstrates manual override of auto-selected embeddings.
    """
    print("\n" + "="*80)
    print("Example 4: Mixed Provider Configuration")
    print("="*80)

    # Configure with explicit embedding override
    config = RyumemConfig()
    config.llm.provider = "litellm"
    config.llm.model = "claude-3-5-sonnet-20241022"

    # Explicitly set embedding provider (override auto-selection)
    # This example shows you can manually override the auto-selected embeddings
    config.embedding.provider = "gemini"
    config.embedding.model = "text-embedding-004"
    config.embedding.dimensions = 768

    # Initialize Ryumem
    ryumem = Ryumem(config=config)

    # Add episodes
    ryumem.add_episode(
        "The team prefers using Claude for reasoning tasks.",
        user_id="user_4"
    )

    ryumem.add_episode(
        "OpenAI embeddings provide better semantic search quality.",
        user_id="user_4"
    )

    print("\n✅ Example 4 completed successfully!")


def example_5_environment_variables():
    """
    Example 5: Configuration via environment variables

    Shows how to configure LiteLLM using environment variables,
    which is the recommended approach for production deployments.
    """
    print("\n" + "="*80)
    print("Example 5: Environment Variable Configuration")
    print("="*80)

    # Set environment variables (normally in .env file)
    os.environ["RYUMEM_LLM_PROVIDER"] = "litellm"
    os.environ["RYUMEM_LLM_MODEL"] = "gpt-4o-mini"

    # Load config from environment
    config = RyumemConfig()

    # Initialize Ryumem
    ryumem = Ryumem(config=config)

    # Add episodes
    ryumem.add_episode(
        "Environment variables make configuration more secure and flexible.",
        user_id="user_5"
    )

    print("\n✅ Example 5 completed successfully!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("Ryumem + LiteLLM Examples")
    print("="*80)
    print("\nThese examples demonstrate using Ryumem with LiteLLM for multi-provider support.")
    print("Make sure to set the appropriate API keys in your environment:")
    print("  - ANTHROPIC_API_KEY for Claude models")
    print("  - OPENAI_API_KEY for OpenAI models and embeddings")
    print("  - GOOGLE_API_KEY for Gemini models")
    print("\nRunning examples...\n")

    # Run examples (comment out if API keys not available)
    try:
        example_1_anthropic_claude()
    except Exception as e:
        print(f"❌ Example 1 failed: {e}")

    try:
        example_2_openai_via_litellm()
    except Exception as e:
        print(f"❌ Example 2 failed: {e}")

    try:
        example_3_gemini_via_litellm()
    except Exception as e:
        print(f"❌ Example 3 failed: {e}")

    try:
        example_4_mixed_providers()
    except Exception as e:
        print(f"❌ Example 4 failed: {e}")

    try:
        example_5_environment_variables()
    except Exception as e:
        print(f"❌ Example 5 failed: {e}")

    print("\n" + "="*80)
    print("All examples completed!")
    print("="*80)
