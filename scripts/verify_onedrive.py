#!/usr/bin/env python3
"""
Verify OneDrive file upload and search
"""
import json
import requests
import time

def load_oauth_tokens():
    """Load OAuth tokens"""
    try:
        with open('.oauth_tokens.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ No OAuth tokens found")
        return None

def check_onedrive_files():
    """Check OneDrive files and search for Scribe.xlsx"""
    oauth_tokens = load_oauth_tokens()
    if not oauth_tokens:
        return False
    
    headers = {'Authorization': f'Bearer {oauth_tokens["access_token"]}'}
    
    print("🔍 Checking OneDrive files...")
    
    # Method 1: List root files
    print("\n1. Listing root files:")
    url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        files = response.json().get('value', [])
        print(f"   Found {len(files)} files in root:")
        for file in files:
            print(f"   - {file['name']} (ID: {file['id']})")
            if 'Scribe.xlsx' in file['name']:
                print(f"     ✅ Found Scribe.xlsx!")
    else:
        print(f"   ❌ Failed to list files: {response.status_code}")
    
    # Method 2: Search for Scribe.xlsx
    print("\n2. Searching for 'Scribe.xlsx':")
    search_url = "https://graph.microsoft.com/v1.0/me/drive/search(q='Scribe.xlsx')"
    search_response = requests.get(search_url, headers=headers)
    
    if search_response.status_code == 200:
        search_files = search_response.json().get('value', [])
        print(f"   Search found {len(search_files)} files:")
        for file in search_files:
            print(f"   - {file['name']} (ID: {file['id']})")
            if file['name'] == 'Scribe.xlsx':
                print(f"     ✅ Exact match found!")
                return True
    else:
        print(f"   ❌ Search failed: {search_response.status_code}")
    
    # Method 3: Direct access attempt
    print("\n3. Trying direct access:")
    direct_url = "https://graph.microsoft.com/v1.0/me/drive/root:/Scribe.xlsx"
    direct_response = requests.get(direct_url, headers=headers)
    
    if direct_response.status_code == 200:
        file_info = direct_response.json()
        print(f"   ✅ Direct access successful: {file_info['name']}")
        return True
    else:
        print(f"   ❌ Direct access failed: {direct_response.status_code}")
    
    return False

def main():
    print("🔍 OneDrive File Verification")
    print("=" * 40)
    
    if check_onedrive_files():
        print("\n✅ Scribe.xlsx is accessible in OneDrive!")
        print("The search index might need a few minutes to update.")
        print("Try running the comprehensive test again in a moment.")
    else:
        print("\n❌ Scribe.xlsx not found or not accessible.")
        print("You may need to upload it again or check permissions.")

if __name__ == "__main__":
    main()
