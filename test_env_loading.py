"""Quick test to verify environment variables are being loaded correctly."""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

print("=" * 60)
print("Environment Variables Test")
print("=" * 60)

# Check what's in the environment
env_vars = {
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "RYUMEM_LLM_PROVIDER": os.getenv("RYUMEM_LLM_PROVIDER"),
    "RYUMEM_LLM_MODEL": os.getenv("RYUMEM_LLM_MODEL"),
    "RYUMEM_OLLAMA_BASE_URL": os.getenv("RYUMEM_OLLAMA_BASE_URL"),
    "RYUMEM_EMBEDDING_MODEL": os.getenv("RYUMEM_EMBEDDING_MODEL"),
}

print("\nEnvironment variables loaded:")
for key, value in env_vars.items():
    if key == "OPENAI_API_KEY" and value:
        print(f"  {key}: {value[:20]}...")
    else:
        print(f"  {key}: {value}")

# Now test config loading
print("\n" + "=" * 60)
print("Testing RyumemConfig.from_env()")
print("=" * 60)

from ryumem.core.config import RyumemConfig

try:
    config = RyumemConfig.from_env()

    print(f"\n✅ Config loaded successfully!")
    print(f"  LLM Provider: {config.llm_provider}")
    print(f"  LLM Model: {config.llm_model}")
    print(f"  Ollama Base URL: {config.ollama_base_url}")
    print(f"  Embedding Model: {config.embedding_model}")
    print(f"  OpenAI API Key: {'Present' if config.openai_api_key else 'Missing'}")

except Exception as e:
    print(f"\n❌ Error loading config: {e}")

print("\n" + "=" * 60)
