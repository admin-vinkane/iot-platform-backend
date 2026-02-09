#!/bin/bash

# Test script for Device UUID Auto-Generation
# Tests the PUT /devices endpoint with and without DeviceId

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# API endpoint (update this to match your environment)
API_ENDPOINT="${API_ENDPOINT:-https://your-api-gateway-url.amazonaws.com/dev/devices}"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Device UUID Auto-Generation Tests${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Test 1: Create device WITHOUT DeviceId (should auto-generate UUID)
echo -e "${YELLOW}Test 1: Create device WITHOUT DeviceId${NC}"
echo "Request: Creating device without DeviceId - should auto-generate UUID"
RESPONSE1=$(curl -s -X PUT "$API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "EntityType": "DEVICE",
    "DeviceName": "Auto UUID Test Device",
    "DeviceType": "water",
    "SerialNumber": "AUTO-TEST-001",
    "devicenum": "IMEI-AUTO-001",
    "Status": "active",
    "Location": "Test Lab A",
    "CreatedBy": "test-script"
  }')

echo "Response:"
echo "$RESPONSE1" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE1"

# Extract DeviceId from response
DEVICE_ID_1=$(echo "$RESPONSE1" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('created', {}).get('DeviceId', ''))" 2>/dev/null)

if [[ "$RESPONSE1" == *"created successfully"* ]] && [[ -n "$DEVICE_ID_1" ]]; then
    echo -e "${GREEN}✓ Test 1 PASSED: Device created with auto-generated UUID: $DEVICE_ID_1${NC}"
else
    echo -e "${RED}✗ Test 1 FAILED: Device creation failed or no DeviceId returned${NC}"
fi
echo ""

# Test 2: Create device WITH explicit DeviceId
echo -e "${YELLOW}Test 2: Create device WITH explicit DeviceId${NC}"
CUSTOM_DEVICE_ID="custom-test-device-$(date +%s)"
echo "Request: Creating device with custom DeviceId: $CUSTOM_DEVICE_ID"
RESPONSE2=$(curl -s -X PUT "$API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "{
    \"EntityType\": \"DEVICE\",
    \"DeviceId\": \"$CUSTOM_DEVICE_ID\",
    \"DeviceName\": \"Custom ID Test Device\",
    \"DeviceType\": \"chlorine\",
    \"SerialNumber\": \"CUSTOM-TEST-002\",
    \"devicenum\": \"IMEI-CUSTOM-002\",
    \"Status\": \"active\",
    \"Location\": \"Test Lab B\",
    \"CreatedBy\": \"test-script\"
  }")

echo "Response:"
echo "$RESPONSE2" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE2"

DEVICE_ID_2=$(echo "$RESPONSE2" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('created', {}).get('DeviceId', ''))" 2>/dev/null)

if [[ "$RESPONSE2" == *"created successfully"* ]] && [[ "$DEVICE_ID_2" == "$CUSTOM_DEVICE_ID" ]]; then
    echo -e "${GREEN}✓ Test 2 PASSED: Device created with custom DeviceId: $DEVICE_ID_2${NC}"
else
    echo -e "${RED}✗ Test 2 FAILED: Device creation failed or DeviceId mismatch${NC}"
fi
echo ""

# Test 3: Update existing device (from Test 1)
if [[ -n "$DEVICE_ID_1" ]]; then
    echo -e "${YELLOW}Test 3: Update existing device (auto-generated UUID)${NC}"
    echo "Request: Updating device $DEVICE_ID_1"
    sleep 2  # Wait to ensure timestamp difference
    RESPONSE3=$(curl -s -X PUT "$API_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d "{
        \"EntityType\": \"DEVICE\",
        \"DeviceId\": \"$DEVICE_ID_1\",
        \"Status\": \"inactive\",
        \"Location\": \"Test Lab C - Maintenance\",
        \"UpdatedBy\": \"test-script-update\"
      }")
    
    echo "Response:"
    echo "$RESPONSE3" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE3"
    
    if [[ "$RESPONSE3" == *"updated"* ]] && [[ "$RESPONSE3" == *"inactive"* ]]; then
        echo -e "${GREEN}✓ Test 3 PASSED: Device updated successfully${NC}"
    else
        echo -e "${RED}✗ Test 3 FAILED: Device update failed${NC}"
    fi
else
    echo -e "${YELLOW}Test 3: SKIPPED (Test 1 device creation failed)${NC}"
fi
echo ""

# Test 4: Case sensitivity test (lowercase deviceId)
echo -e "${YELLOW}Test 4: Case sensitivity test (lowercase 'deviceId')${NC}"
echo "Request: Creating device with lowercase 'deviceId' field"
RESPONSE4=$(curl -s -X PUT "$API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "EntityType": "DEVICE",
    "deviceId": "lowercase-test-device",
    "DeviceName": "Case Sensitivity Test",
    "DeviceType": "water",
    "SerialNumber": "CASE-TEST-001",
    "devicenum": "IMEI-CASE-001",
    "Status": "active",
    "Location": "Test Lab D",
    "CreatedBy": "test-script"
  }')

echo "Response:"
echo "$RESPONSE4" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE4"

DEVICE_ID_4=$(echo "$RESPONSE4" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('created', {}).get('DeviceId', ''))" 2>/dev/null)

if [[ "$RESPONSE4" == *"created successfully"* ]] && [[ "$DEVICE_ID_4" == "lowercase-test-device" ]]; then
    echo -e "${GREEN}✓ Test 4 PASSED: Lowercase 'deviceId' accepted and normalized${NC}"
else
    echo -e "${RED}✗ Test 4 FAILED: Case sensitivity handling failed${NC}"
fi
echo ""

# Test 5: UUID format validation
echo -e "${YELLOW}Test 5: UUID format validation${NC}"
if [[ -n "$DEVICE_ID_1" ]]; then
    # UUID v4 regex pattern: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    UUID_PATTERN="^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    
    if [[ "$DEVICE_ID_1" =~ $UUID_PATTERN ]]; then
        echo -e "${GREEN}✓ Test 5 PASSED: Auto-generated DeviceId is valid UUID v4: $DEVICE_ID_1${NC}"
    else
        echo -e "${RED}✗ Test 5 FAILED: DeviceId is not valid UUID v4 format: $DEVICE_ID_1${NC}"
    fi
else
    echo -e "${YELLOW}Test 5: SKIPPED (Test 1 device creation failed)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "Test 1 (Auto-generate UUID):     $(if [[ -n "$DEVICE_ID_1" ]]; then echo -e "${GREEN}PASSED${NC}"; else echo -e "${RED}FAILED${NC}"; fi)"
echo -e "Test 2 (Custom DeviceId):         $(if [[ "$DEVICE_ID_2" == "$CUSTOM_DEVICE_ID" ]]; then echo -e "${GREEN}PASSED${NC}"; else echo -e "${RED}FAILED${NC}"; fi)"
echo -e "Test 3 (Update device):           $(if [[ "$RESPONSE3" == *"updated"* ]]; then echo -e "${GREEN}PASSED${NC}"; else echo -e "${YELLOW}SKIPPED${NC}"; fi)"
echo -e "Test 4 (Case sensitivity):        $(if [[ "$DEVICE_ID_4" == "lowercase-test-device" ]]; then echo -e "${GREEN}PASSED${NC}"; else echo -e "${RED}FAILED${NC}"; fi)"
echo -e "Test 5 (UUID format):             $(if [[ "$DEVICE_ID_1" =~ $UUID_PATTERN ]]; then echo -e "${GREEN}PASSED${NC}"; else echo -e "${YELLOW}SKIPPED${NC}"; fi)"
echo ""

# Cleanup instructions
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Cleanup${NC}"
echo -e "${BLUE}======================================${NC}"
echo "Test devices created:"
[[ -n "$DEVICE_ID_1" ]] && echo "  - $DEVICE_ID_1 (auto-generated UUID)"
[[ -n "$DEVICE_ID_2" ]] && echo "  - $DEVICE_ID_2 (custom ID)"
[[ -n "$DEVICE_ID_4" ]] && echo "  - $DEVICE_ID_4 (case sensitivity test)"
echo ""
echo "To delete test devices, use DELETE endpoint with each DeviceId"
echo ""
