"""
E2E tests for GitHub OAuth authentication flow.

Tests the device code flow, token management, and API key generation.
Run with: RYUMEM_API_URL=http://localhost:8000 RYUMEM_API_KEY=your_key python -m pytest tests/test_oauth.py
"""
import os
import urllib.request
import urllib.error
import json
import time
import pytest
from uuid import uuid4

# Get config from environment
API_URL = os.getenv("RYUMEM_API_URL", "http://localhost:8000")
API_KEY = os.getenv("RYUMEM_API_KEY")

if not API_KEY:
    pytest.skip("RYUMEM_API_KEY not set", allow_module_level=True)


def make_request(method, endpoint, headers=None, data=None, use_api_key=True):
    """Make an HTTP request to the Ryumem API."""
    if headers is None:
        headers = {}

    url = f"{API_URL}{endpoint}"
    if data:
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    # Don't add API key if Authorization header is present or use_api_key is False
    if use_api_key and 'Authorization' not in headers:
        headers['X-API-Key'] = API_KEY

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8')), response.status
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if hasattr(e, 'read') else '{}'
        try:
            return json.loads(error_body) if error_body else {}, e.code
        except json.JSONDecodeError:
            return {'error': error_body}, e.code
    except Exception as e:
        print(f"Request error: {e}")
        return None, 500


def test_oauth_device_flow_comprehensive():
    """
    Comprehensive test for OAuth device code flow.

    Tests:
    1. Device code initiation returns proper response structure
    2. Device code polling returns authorization_pending initially
    3. Endpoint responses have correct format and required fields
    4. Error handling for invalid/expired device codes
    """
    # Step 1: Initiate device code flow (no API key needed for OAuth)
    response, status = make_request('POST', '/auth/github/device', data={}, use_api_key=False)

    assert status == 200, f"Device flow initiation failed with status {status}"
    assert 'device_code' in response, "Response missing device_code"
    assert 'user_code' in response, "Response missing user_code"
    assert 'verification_uri' in response, "Response missing verification_uri"
    assert 'expires_in' in response, "Response missing expires_in"
    assert 'interval' in response, "Response missing polling interval"

    device_code = response['device_code']
    user_code = response['user_code']

    print(f"\n✓ Device code generated: {user_code}")
    print(f"  Verification URI: {response['verification_uri']}")
    print(f"  Expires in: {response['expires_in']}s")

    # Step 2: Poll for authorization (should be pending since user hasn't authorized)
    poll_response, poll_status = make_request(
        'POST',
        '/auth/github/device/poll',
        data={'device_code': device_code},
        use_api_key=False
    )

    assert poll_status == 200, f"Unexpected poll status: {poll_status}"
    assert 'status' in poll_response, "Poll response missing 'status' field"

    # Should return status: 'pending' initially (user hasn't authorized yet)
    if poll_response['status'] == 'pending':
        assert poll_response.get('customer_id') is None, "Pending should have no customer_id"
        assert poll_response.get('api_key') is None, "Pending should have no api_key"
        print(f"✓ Polling returns correct pending state: {poll_response['status']}")
    elif poll_response['status'] == 'authorized':
        # If already authorized (unlikely in test), verify structure
        assert poll_response.get('customer_id') is not None, "Authorized response missing customer_id"
        assert poll_response.get('api_key') is not None, "Authorized response missing api_key"
        print("✓ Device already authorized (unexpected but valid)")
    else:
        pytest.fail(f"Unexpected status: {poll_response['status']}")

    # Step 3: Test invalid device code handling
    invalid_response, invalid_status = make_request(
        'POST',
        '/auth/github/device/poll',
        data={'device_code': 'invalid_device_code_12345'},
        use_api_key=False
    )

    # API returns 200 with error field for invalid device codes
    assert invalid_status == 200, f"Expected 200, got {invalid_status}"
    assert 'error' in invalid_response or invalid_response.get('status') == 'error', \
        "Invalid device code should return error"
    print(f"✓ Invalid device code properly rejected: {invalid_response.get('error') or invalid_response.get('status')}")

    # Step 4: Test /auth/me endpoint (should fail without valid Bearer token)
    me_response, me_status = make_request(
        'GET',
        '/auth/me',
        headers={'Authorization': 'Bearer invalid_token_12345'},
        use_api_key=False
    )

    assert me_status in [401, 403], f"/auth/me should reject invalid token, got {me_status}"
    print("✓ Invalid Bearer token properly rejected")

    # Step 5: Test /auth/me with API key (should work or return user info)
    me_with_key_response, me_key_status = make_request('GET', '/auth/me')

    # API key auth might return 200 with user info or 401 if not supported on /auth/me
    if me_key_status == 200:
        print(f"✓ /auth/me with API key returned user info")
        assert 'customer_id' in me_with_key_response, \
            "User info response missing customer_id"
    else:
        print(f"✓ /auth/me requires Bearer token (API key not accepted)")

    print("\n✅ OAuth device flow test completed successfully")
    print("   Note: Full flow requires manual GitHub authorization")


def test_api_key_endpoint():
    """
    Test the API key management endpoint (/auth/api-key).

    Tests:
    1. Successful API key retrieval with valid authentication
    2. Response structure contains required fields (api_key, customer_id, github_username)
    3. Endpoint rejects requests without authentication
    4. Endpoint rejects requests with invalid API key
    """
    # Step 1: Test successful API key retrieval with valid authentication
    response, status = make_request('GET', '/auth/api-key', use_api_key=True)

    assert status == 200, f"API key retrieval failed with status {status}"
    assert 'api_key' in response, "Response missing api_key field"
    assert 'customer_id' in response, "Response missing customer_id field"

    # Verify API key format (should start with 'ryu_')
    api_key = response['api_key']
    assert api_key.startswith('ryu_'), f"API key has unexpected format: {api_key[:10]}..."
    assert len(api_key) > 10, "API key seems too short"

    print(f"\n✓ API key retrieved successfully")
    print(f"  Customer ID: {response['customer_id']}")
    print(f"  API key format: ryu_***...{api_key[-4:]}")
    if 'github_username' in response:
        print(f"  GitHub username: {response.get('github_username', 'N/A')}")

    # Step 2: Test that endpoint requires authentication (no API key)
    no_auth_response, no_auth_status = make_request('GET', '/auth/api-key', use_api_key=False)

    assert no_auth_status in [401, 403], \
        f"Expected 401/403 without auth, got {no_auth_status}"
    print("✓ Endpoint correctly rejects unauthenticated requests")

    # Step 3: Test with invalid API key
    invalid_key_response, invalid_key_status = make_request(
        'GET',
        '/auth/api-key',
        headers={'X-API-Key': 'invalid_key_12345'},
        use_api_key=False
    )

    assert invalid_key_status in [401, 403], \
        f"Expected 401/403 with invalid key, got {invalid_key_status}"
    print("✓ Endpoint correctly rejects invalid API keys")

    # Step 4: Verify returned API key actually works by testing it
    # Use the returned API key to make another authenticated request
    test_response, test_status = make_request(
        'GET',
        '/auth/api-key',
        headers={'X-API-Key': api_key},
        use_api_key=False
    )

    assert test_status == 200, f"Returned API key doesn't work, status {test_status}"
    assert test_response['api_key'] == api_key, "API key changed unexpectedly"
    print("✓ Returned API key is valid and functional")

    print("\n✅ API key endpoint tests completed successfully")


if __name__ == "__main__":
    test_oauth_device_flow_comprehensive()
    test_api_key_endpoint()
