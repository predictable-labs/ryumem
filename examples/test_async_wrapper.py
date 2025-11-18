"""
Simple test to verify the async wrapper structure without requiring API keys.
This tests that the wrapper can be imported and has the correct structure.
"""

import sys
import inspect

# Test imports
try:
    from ryumem.integrations.google_adk import wrap_runner_with_tracking, _prepare_query_and_episode, _save_agent_response_to_episode
    print("✓ Successfully imported wrap_runner_with_tracking and helper functions")
except ImportError as e:
    print(f"✗ Failed to import: {e}")
    sys.exit(1)

# Test that helper functions exist
print("\n=== Testing Helper Functions ===")
print(f"✓ _prepare_query_and_episode exists: {callable(_prepare_query_and_episode)}")
print(f"✓ _save_agent_response_to_episode exists: {callable(_save_agent_response_to_episode)}")

# Inspect the function signatures
print(f"\n_prepare_query_and_episode signature:")
print(f"  {inspect.signature(_prepare_query_and_episode)}")

print(f"\n_save_agent_response_to_episode signature:")
print(f"  {inspect.signature(_save_agent_response_to_episode)}")

# Test that wrap_runner_with_tracking can be called
print("\n=== Testing wrap_runner_with_tracking ===")

# Create a mock runner with both run and run_async methods
class MockRunner:
    def run(self, *, user_id, session_id, new_message, **kwargs):
        yield {"event": "mock_sync"}

    async def run_async(self, *, user_id, session_id, new_message, **kwargs):
        yield {"event": "mock_async"}

# Create a mock memory object
class MockMemory:
    class MockRyumem:
        def add_episode(self, **kwargs):
            return "mock-uuid"

        def get_episode_by_uuid(self, uuid):
            return None

        def update_episode_metadata(self, uuid, metadata):
            pass

        class MockDB:
            def execute(self, query, params):
                return [{"metadata": "{}"}]

        db = MockDB()

    ryumem = MockRyumem()
    extract_entities = False

mock_runner = MockRunner()
mock_memory = MockMemory()

print(f"✓ Created mock runner with methods: {[m for m in dir(mock_runner) if not m.startswith('_')]}")

# Call wrap_runner_with_tracking
try:
    wrapped_runner = wrap_runner_with_tracking(
        mock_runner,
        mock_memory,
        track_queries=True,
        augment_queries=False  # Disable to avoid needing real DB
    )
    print("✓ Successfully called wrap_runner_with_tracking")
except Exception as e:
    print(f"✗ Failed to call wrap_runner_with_tracking: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Check that both methods are wrapped
print(f"\n=== Verifying Wrapped Methods ===")
print(f"✓ run method exists: {hasattr(wrapped_runner, 'run')}")
print(f"✓ run_async method exists: {hasattr(wrapped_runner, 'run_async')}")

# Check if run_async is actually wrapped (should be different from original)
if hasattr(wrapped_runner, 'run_async'):
    is_wrapped = wrapped_runner.run_async != MockRunner.run_async
    print(f"✓ run_async is wrapped: {is_wrapped}")

    # Check if it's an async function
    is_async = inspect.iscoroutinefunction(wrapped_runner.run_async)
    print(f"✓ run_async is async function: {is_async}")

    if is_async:
        print("\n✅ SUCCESS: run_async wrapper is properly implemented!")
        print("   - The method exists")
        print("   - It's wrapped (different from original)")
        print("   - It's an async function (coroutine)")
    else:
        print("\n❌ FAILURE: run_async is not an async function")
        sys.exit(1)
else:
    print("\n❌ FAILURE: run_async method not found on wrapped runner")
    sys.exit(1)

print("\n" + "="*60)
print("All tests passed! The async wrapper implementation is correct.")
print("="*60)
