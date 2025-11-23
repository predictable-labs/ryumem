import urllib.request
import urllib.error
import json
import time
import sys

BASE_URL = "http://localhost:8000"
ADMIN_KEY = "change_this_to_a_secure_random_string"

def make_request(method, endpoint, headers={}, data=None):
    url = f"{BASE_URL}{endpoint}"
    if data:
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8')), response.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8')) if e.read() else {}, e.code
    except Exception as e:
        print(f"Error: {e}")
        return None, 500

def test_multitenancy():
    print("Waiting for server to start...")
    time.sleep(5) # Give server time to start
    
    print("\n1. Registering Customer A...")
    resp_a, status_a = make_request("POST", "/register", {"X-Admin-Key": ADMIN_KEY}, {"customer_id": "customer_A"})
    if status_a != 200:
        print(f"Failed to register A: {status_a} {resp_a}")
        return
    key_a = resp_a['api_key']
    print(f"Success! Key A: {key_a}")

    print("\n2. Registering Customer B...")
    resp_b, status_b = make_request("POST", "/register", {"X-Admin-Key": ADMIN_KEY}, {"customer_id": "customer_B"})
    if status_b != 200:
        print(f"Failed to register B: {status_b} {resp_b}")
        return
    key_b = resp_b['api_key']
    print(f"Success! Key B: {key_b}")

    print("\n3. Adding Episode for Customer A...")
    episode_data = {
        "content": "Secret info for Customer A",
        "user_id": "user_1",
        "source": "text"
    }
    resp_add, status_add = make_request("POST", "/episodes", {"X-API-Key": key_a}, episode_data)
    if status_add != 200:
        print(f"Failed to add episode: {status_add} {resp_add}")
        return
    print("Episode added.")

    print("\n4. Searching as Customer A (Should find it)...")
    search_data = {
        "query": "Secret info",
        "user_id": "user_1",
        "limit": 5
    }
    resp_search_a, status_search_a = make_request("POST", "/search", {"X-API-Key": key_a}, search_data)
    if status_search_a != 200:
        print(f"Search A failed: {status_search_a} {resp_search_a}")
        return
    
    count_a = resp_search_a.get('count', 0)
    print(f"Customer A found {count_a} results.")
    if count_a == 0:
        print("FAILURE: Customer A should have found the episode.")
    
    print("\n5. Searching as Customer B (Should NOT find it)...")
    search_data_b = {
        "query": "Secret info",
        "user_id": "user_1", # Same user_id, but different tenant
        "limit": 5
    }
    resp_search_b, status_search_b = make_request("POST", "/search", {"X-API-Key": key_b}, search_data_b)
    if status_search_b != 200:
        print(f"Search B failed: {status_search_b} {resp_search_b}")
        return

    count_b = resp_search_b.get('count', 0)
    print(f"Customer B found {count_b} results.")
    if count_b > 0:
        print("FAILURE: Customer B should NOT have found the episode.")
    else:
        print("SUCCESS: Customer B found nothing.")

if __name__ == "__main__":
    test_multitenancy()
