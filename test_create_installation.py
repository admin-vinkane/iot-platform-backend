#!/usr/bin/env python3
"""
Test script to create an installation with device linking
"""

import json
import requests

# API Gateway endpoint
API_BASE_URL = "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev"

print("="*60)
print("Step 1: Fetching existing devices...")
print("="*60)

# Get existing devices
try:
    devices_response = requests.get(f"{API_BASE_URL}/devices")
    if devices_response.status_code == 200:
        devices_data = devices_response.json()
        
        # Handle both direct list and wrapped response
        if isinstance(devices_data, list):
            devices = devices_data
        elif isinstance(devices_data.get('body'), str):
            devices_body = json.loads(devices_data['body'])
            devices = devices_body.get('devices', [])
        else:
            devices = devices_data.get('body', {}).get('devices', [])
        
        # Filter devices without LinkedInstallationId
        available_devices = [d for d in devices if not d.get('LinkedInstallationId')]
        
        if available_devices:
            device_ids = [d['deviceId'] for d in available_devices[:2]]  # Get first 2 unlinked devices
            print(f"✅ Found {len(devices)} total devices")
            print(f"✅ Found {len(available_devices)} devices without LinkedInstallationId")
            print(f"Using devices: {device_ids}")
            for d in available_devices[:2]:
                print(f"  - {d['deviceId']}: {d['deviceName']} ({d['deviceType']}) - Status: {d['status']}")
        else:
            print("⚠️  No unlinked devices found, creating installation without devices")
            device_ids = []
    else:
        print(f"⚠️  Failed to fetch devices (status {devices_response.status_code}), proceeding without devices")
        device_ids = []
except Exception as e:
    print(f"⚠️  Error fetching devices: {e}, proceeding without devices")
    import traceback
    traceback.print_exc()
    device_ids = []

# Test payload with devices
payload = {
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "005",
    "PrimaryDevice": "water",
    "Status": "active",
    "InstallationDate": "2026-01-31",
    "CreatedBy": "test-admin"
}

# Add device IDs if found
if device_ids:
    payload["deviceIds"] = device_ids

print("\n" + "="*60)
print("Step 2: Creating installation...")
print("="*60)
print("Payload:")
print(json.dumps(payload, indent=2))
print("\n")

# Call POST /installs endpoint
try:
    response = requests.post(
        f"{API_BASE_URL}/installs",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=30
    )
    
    print(f"Response Status: {response.status_code}")
    print("\nResponse Body:")
    response_data = response.json()
    print(json.dumps(response_data, indent=2))
    
    # Parse and display results
    if response.status_code == 201:
        print("\n" + "="*60)
        print("✅ Installation created successfully!")
        print("="*60)
        
        if isinstance(response_data.get('body'), str):
            body = json.loads(response_data['body'])
        else:
            body = response_data.get('body', {})
        
        if 'installation' in body:
            inst = body['installation']
            print(f"\n📋 Installation ID: {inst.get('InstallationId')}")
            print(f"📍 Location: {inst.get('stateName')} > {inst.get('districtName')} > {inst.get('mandalName')}")
            print(f"🏘️  Village: {inst.get('villageName')} > {inst.get('habitationName')}")
            print(f"📊 Status: {inst.get('Status')}")
            print(f"💧 Primary Device: {inst.get('PrimaryDevice')}")
            
            if inst.get('thingsboardStatus'):
                print(f"\n🔗 Thingsboard Status: {inst.get('thingsboardStatus')}")
                if inst.get('thingsboardAssets'):
                    assets = inst['thingsboardAssets']
                    print(f"   • Habitation Asset: {assets.get('habitation', {}).get('id')}")
            
            if inst.get('deviceLinking'):
                linking = inst['deviceLinking']
                print(f"\n🔌 Device Linking:")
                print(f"   • Linked: {len(linking.get('linked', []))} devices")
                if linking.get('linked'):
                    for dev in linking['linked']:
                        print(f"     - {dev['deviceId']}: {dev['status']}")
                if linking.get('errors'):
                    print(f"   • Errors: {len(linking['errors'])}")
                    for err in linking['errors']:
                        print(f"     - {err['deviceId']}: {err['error']}")
    else:
        print(f"\n❌ Failed with status code: {response.status_code}")
        
except requests.exceptions.Timeout:
    print("❌ Request timed out after 30 seconds")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
