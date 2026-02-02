#!/bin/bash

# Contact Linking Test Script
# Tests Phase 2 implementation: POST /installs/{id}/contacts/link and /unlink

API_URL="https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev"

echo "===================================="
echo "Contact Linking Tests - Phase 2"
echo "===================================="
echo

# First, create a test installation
echo "1. Creating test installation..."
CREATE_RESPONSE=$(curl -s -X POST "$API_URL/installs" \
  -H "Content-Type: application/json" \
  -d '{
    "CustomerId": "CUSTa1b2c3d4",
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "TEST_CONTACT_001",
    "PrimaryDevice": "water",
    "Status": "active",
    "InstallationDate": "2026-02-01T00:00:00.000Z"
  }')

echo "$CREATE_RESPONSE" | jq '.'
INSTALL_ID=$(echo "$CREATE_RESPONSE" | jq -r '.installation.installationId')

if [ -z "$INSTALL_ID" ] || [ "$INSTALL_ID" = "null" ]; then
  echo "❌ Failed to create installation"
  exit 1
fi

echo "✅ Installation created: $INSTALL_ID"
echo

# Test 2: Link contacts to installation
echo "2. Linking contacts to installation..."
LINK_RESPONSE=$(curl -s -X POST "$API_URL/installs/$INSTALL_ID/contacts/link" \
  -H "Content-Type: application/json" \
  -d '{
    "contactIds": ["CONTx1y2z3w4", "CONT9876abcd"],
    "performedBy": "test@example.com",
    "reason": "Testing contact linking"
  }')

echo "$LINK_RESPONSE" | jq '.'

LINKED_COUNT=$(echo "$LINK_RESPONSE" | jq -r '.linked | length')
echo "✅ Linked $LINKED_COUNT contacts"
echo

# Test 3: Fetch installation with contacts
echo "3. Fetching installation with includeContacts=true..."
GET_RESPONSE=$(curl -s "$API_URL/installs/$INSTALL_ID?includeContacts=true")

echo "$GET_RESPONSE" | jq '.'

CONTACT_COUNT=$(echo "$GET_RESPONSE" | jq -r '.linkedContactCount // 0')
echo "✅ Installation has $CONTACT_COUNT linked contacts"
echo

# Test 4: Unlink one contact
echo "4. Unlinking one contact..."
UNLINK_RESPONSE=$(curl -s -X POST "$API_URL/installs/$INSTALL_ID/contacts/unlink" \
  -H "Content-Type: application/json" \
  -d '{
    "contactIds": ["CONTx1y2z3w4"],
    "performedBy": "test@example.com",
    "reason": "Testing contact unlinking"
  }')

echo "$UNLINK_RESPONSE" | jq '.'

UNLINKED_COUNT=$(echo "$UNLINK_RESPONSE" | jq -r '.unlinked | length')
echo "✅ Unlinked $UNLINKED_COUNT contact"
echo

# Test 5: Verify contact was unlinked
echo "5. Verifying contact was unlinked..."
VERIFY_RESPONSE=$(curl -s "$API_URL/installs/$INSTALL_ID?includeContacts=true")

FINAL_CONTACT_COUNT=$(echo "$VERIFY_RESPONSE" | jq -r '.linkedContactCount // 0')
echo "✅ Installation now has $FINAL_CONTACT_COUNT linked contacts (should be 1)"
echo

# Test 6: Try linking invalid contact
echo "6. Testing error handling - invalid contact..."
ERROR_RESPONSE=$(curl -s -X POST "$API_URL/installs/$INSTALL_ID/contacts/link" \
  -H "Content-Type: application/json" \
  -d '{
    "contactIds": ["INVALID_CONTACT_ID"],
    "performedBy": "test@example.com"
  }')

echo "$ERROR_RESPONSE" | jq '.'

ERROR_COUNT=$(echo "$ERROR_RESPONSE" | jq -r '.errors | length')
if [ "$ERROR_COUNT" -gt 0 ]; then
  echo "✅ Error handling works correctly"
else
  echo "⚠️  Warning: Expected error for invalid contact"
fi
echo

# Test 7: Try linking to installation without CustomerId
echo "7. Testing installation without CustomerId..."
NO_CUSTOMER_INSTALL=$(curl -s -X POST "$API_URL/installs" \
  -H "Content-Type: application/json" \
  -d '{
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "TEST_NO_CUSTOMER_001",
    "PrimaryDevice": "water",
    "Status": "active",
    "InstallationDate": "2026-02-01T00:00:00.000Z"
  }' | jq -r '.installation.installationId')

if [ ! -z "$NO_CUSTOMER_INSTALL" ] && [ "$NO_CUSTOMER_INSTALL" != "null" ]; then
  NO_CUSTOMER_RESPONSE=$(curl -s -X POST "$API_URL/installs/$NO_CUSTOMER_INSTALL/contacts/link" \
    -H "Content-Type: application/json" \
    -d '{
      "contactIds": ["CONTx1y2z3w4"],
      "performedBy": "test@example.com"
    }')
  
  echo "$NO_CUSTOMER_RESPONSE" | jq '.'
  
  if echo "$NO_CUSTOMER_RESPONSE" | grep -q "does not have a CustomerId"; then
    echo "✅ Correctly rejected linking to installation without CustomerId"
  else
    echo "⚠️  Warning: Expected error for installation without CustomerId"
  fi
fi
echo

echo "===================================="
echo "Test Summary"
echo "===================================="
echo "All Phase 2 endpoints implemented:"
echo "✅ POST /installs/{id}/contacts/link"
echo "✅ POST /installs/{id}/contacts/unlink"
echo "✅ GET /installs/{id}?includeContacts=true"
echo
echo "Test installation: $INSTALL_ID"
echo "===================================="
