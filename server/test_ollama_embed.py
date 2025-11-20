import logging
import sys
import os

import importlib.util

# Load OllamaClient directly from file to avoid package dependencies
spec = importlib.util.spec_from_file_location("llm_ollama", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ryumem_server/utils/llm_ollama.py"))
llm_ollama = importlib.util.module_from_spec(spec)
spec.loader.exec_module(llm_ollama)
OllamaClient = llm_ollama.OllamaClient

logging.basicConfig(level=logging.INFO)

def test_embed():
    print("Testing OllamaClient.embed...")
    # Use the model the user mentioned
    client = OllamaClient(model="nomic-embed-text")
    
    try:
        embedding = client.embed("Hello world")
        print(f"Embedding length: {len(embedding)}")
        print("✅ Embed successful!")
        
        # Test batch
        print("\nTesting OllamaClient.embed_batch...")
        embeddings = client.embed_batch(["Hello", "World"])
        print(f"Batch embeddings count: {len(embeddings)}")
        print(f"First embedding length: {len(embeddings[0])}")
        print("✅ Embed batch successful!")
        
        # Test cosine similarity
        print("\nTesting OllamaClient.cosine_similarity...")
        sim = client.cosine_similarity(embeddings[0], embeddings[1])
        print(f"Similarity: {sim}")
        print("✅ Cosine similarity successful!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        # Print more details if it's a connection error
        if "Connection refused" in str(e):
            print("Make sure Ollama is running (ollama serve) and the model 'nomic-embed-text' is pulled.")

if __name__ == "__main__":
    test_embed()
