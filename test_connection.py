import requests

print("Testing connection to StatsBomb data...")
try:
    url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json"
    response = requests.get(url, timeout=10)
    print(f"Success! Status code: {response.status_code}")
    print(f"Data size: {len(response.content)} bytes")
except Exception as e:
    print(f"Error: {e}")