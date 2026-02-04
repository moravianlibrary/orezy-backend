import os
from time import sleep
import requests

API_URL = "http://localhost:8000"

def main():
    # Login as admin
    response = requests.post(f"{API_URL}/users/login", data={
        "username": os.environ["ADMIN_EMAIL"],
        "password": os.environ["ADMIN_PASSWORD"]
    })
    response.raise_for_status()
    token = response.json()["access_token"]

    # Use the token for subsequent requests
    bearer_headers = {"Authorization": f"Bearer {token}"}

    print(f"Logged in as admin, access token: {token}")

    try:
        # Create a new group
        response = requests.post(f"{API_URL}/groups/", json={
            "name": "Integration Test Group",
            "description": "Group for integration testing"
        }, headers=bearer_headers)
        response.raise_for_status()
        group_id = response.json()["id"]
        group_api_key = response.json()["api_key"]
        title_id = "test-book-001"

        print(f"Created group with ID: {group_id} and API Key: {group_api_key}")

        # Use api key to create a new title
        headers = {"X-API-Key": group_api_key}
        response = requests.post(f"{API_URL}/integration/create?group_id={group_id}", json={
            "external_id": title_id,
        }, headers=headers)
        response.raise_for_status()

        print("Created title using group API key.")

        # Check status of the created title
        response = {"state": None}
        while response["state"] != "ready":
            sleep(5)
            response = requests.get(f"{API_URL}/integration/{title_id}/status", headers=headers)
            response.raise_for_status()
            response = response.json()
            print(f"Title status: {response['state']}")
        print("Title processing completed.")

        # Get coordinates
        response = requests.get(f"{API_URL}/integration/{title_id}/coordinates", headers=headers)
        response.raise_for_status()
        print(f"Coordinates for title {title_id}: {response.json()}")

        # Cleanup
        response = requests.post(f"{API_URL}/integration/{title_id}/complete", headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        response = requests.delete(f"{API_URL}/groups/{group_id}", headers=bearer_headers)
        raise e

    # Delete the group
    response = requests.delete(f"{API_URL}/groups/{group_id}", headers=bearer_headers)
    response.raise_for_status()
    print("Cleaned up created group and title.")

    return True

assert main()