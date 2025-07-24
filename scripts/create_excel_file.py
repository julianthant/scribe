import requests
import json

# Load OAuth tokens
with open('.oauth_tokens.json', 'r') as f:
    tokens = json.load(f)

headers = {'Authorization': f'Bearer {tokens["access_token"]}'}

# Create a simple Excel file in OneDrive
file_content = {
    "name": "scribe.xlsx",
    "file": {},
    "@microsoft.graph.conflictBehavior": "replace"
}

# Create the file
response = requests.post(
    'https://graph.microsoft.com/v1.0/me/drive/root/children',
    headers=headers,
    json=file_content
)

if response.status_code in [200, 201]:
    print("✅ Created scribe.xlsx in OneDrive successfully!")
    result = response.json()
    print(f"📁 File ID: {result.get('id')}")
    print(f"🌐 Web URL: {result.get('webUrl')}")
else:
    print(f"❌ Failed to create file: {response.status_code}")
    print(f"Response: {response.text}")
