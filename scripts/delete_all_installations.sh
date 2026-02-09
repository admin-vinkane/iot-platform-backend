#!/bin/bash

# Script to delete all installations with cascade=true option
# This will remove installations and all their associations (devices, contacts)

set -e  # Exit on error

# Configuration
API_BASE_URL="https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev"
DELETED_BY="${1:-admin}"  # First argument or default to 'admin'

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================="
echo "  DELETE ALL INSTALLATIONS (CASCADE)"
echo "================================================="
echo ""
echo -e "${YELLOW}WARNING: This will delete ALL installations and their associations!${NC}"
echo -e "${YELLOW}Deleted by: ${DELETED_BY}${NC}"
echo ""
read -p "Are you sure you want to continue? (type 'YES' to confirm): " confirmation

if [ "$confirmation" != "YES" ]; then
    echo -e "${RED}Operation cancelled.${NC}"
    exit 0
fi

echo ""
echo "Fetching all installations..."

# Get all installations
INSTALLS_RESPONSE=$(curl -s -X GET "${API_BASE_URL}/installs")

# Extract installation IDs using jq (handle both array and nested object formats)
INSTALL_IDS=$(echo "$INSTALLS_RESPONSE" | jq -r '.installs[]?.InstallationId // .[].InstallationId // .[].installationId // empty')

if [ -z "$INSTALL_IDS" ]; then
    echo -e "${YELLOW}No installations found.${NC}"
    exit 0
fi

# Count installations
TOTAL_COUNT=$(echo "$INSTALL_IDS" | wc -l | tr -d ' ')
echo -e "${GREEN}Found ${TOTAL_COUNT} installation(s) to delete${NC}"
echo ""

# Initialize counters
SUCCESS_COUNT=0
FAIL_COUNT=0

# Loop through each installation and delete with cascade
while IFS= read -r INSTALL_ID; do
    if [ -n "$INSTALL_ID" ]; then
        echo "Deleting installation: ${INSTALL_ID}"
        
        # Delete with cascade=true
        RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE \
            "${API_BASE_URL}/installs/${INSTALL_ID}?cascade=true&deletedBy=${DELETED_BY}")
        
        # Extract HTTP code (last line)
        HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
        # Extract response body (all but last line)
        BODY=$(echo "$RESPONSE" | sed '$d')
        
        if [ "$HTTP_CODE" -eq 200 ]; then
            # Extract total deleted count from response
            TOTAL_DELETED=$(echo "$BODY" | jq -r '.totalDeleted // "N/A"')
            echo -e "${GREEN}✓ Successfully deleted ${INSTALL_ID} (${TOTAL_DELETED} total records)${NC}"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            ERROR_MSG=$(echo "$BODY" | jq -r '.error // .message // "Unknown error"')
            echo -e "${RED}✗ Failed to delete ${INSTALL_ID}: ${ERROR_MSG} (HTTP ${HTTP_CODE})${NC}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
        
        # Small delay to avoid rate limiting
        sleep 0.5
    fi
done <<< "$INSTALL_IDS"

echo ""
echo "================================================="
echo "  DELETION SUMMARY"
echo "================================================="
echo -e "Total installations: ${TOTAL_COUNT}"
echo -e "${GREEN}Successfully deleted: ${SUCCESS_COUNT}${NC}"
echo -e "${RED}Failed: ${FAIL_COUNT}${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}All installations deleted successfully!${NC}"
    exit 0
else
    echo -e "${YELLOW}Some deletions failed. Check the output above for details.${NC}"
    exit 1
fi
