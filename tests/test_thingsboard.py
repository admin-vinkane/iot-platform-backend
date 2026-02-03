#!/usr/bin/env python3
"""Test Thingsboard API connectivity"""

import sys
import os
sys.path.insert(0, '.')
from shared.thingsboard_utils import get_thingsboard_token, TB_HOST
import requests

# Check if JWT token is set
if not os.environ.get("THINGSBOARD_TOKEN"):
    print("⚠️  THINGSBOARD_TOKEN environment variable is not set!")
    print("\nTo test the API, first set your JWT token:")
    print("  export THINGSBOARD_TOKEN='your-jwt-token-here'")
    print("\nOr get a token from Thingsboard:")
    print(f"  curl -X POST {TB_HOST}/api/auth/login \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"username\": \"your-username\", \"password\": \"your-password\"}' \\")
    print("    | jq -r '.token'")
    sys.exit(1)

try:
    print('🔑 Getting Thingsboard JWT token from environment...')
    token = get_thingsboard_token()
    if token:
        print(f'✅ Token obtained (first 50 chars): {token[:50]}...')
        
        # Test API - get tenant assets
        print(f'\n📊 Testing API at {TB_HOST}')
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(f'{TB_HOST}/api/tenant/assets?pageSize=5&page=0', headers=headers, timeout=10)
        print(f'Status Code: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            print(f'✅ API is working!')
            print(f'Total Assets: {data.get("totalElements", 0)}')
            print(f'Assets in response: {len(data.get("data", []))}')
            if data.get('data'):
                print(f'\nFirst 3 assets:')
                for asset in data['data'][:3]:
                    print(f'  - {asset.get("name")} (Type: {asset.get("type")})')
        else:
            print(f'❌ API Error: {response.text}')
    else:
        print('❌ Failed to get token')
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
