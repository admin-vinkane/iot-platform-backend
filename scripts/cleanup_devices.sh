#!/bin/bash

# Cleanup script for v_devices_dev table
# WARNING: This will delete data permanently!

set -e

REGION="ap-south-2"
TABLE_NAME="v_devices_dev"

echo "========================================="
echo "Device Data Cleanup Script"
echo "========================================="
echo "Region: $REGION"
echo "Table: $TABLE_NAME"
echo ""
echo "⚠️  WARNING: This will permanently delete data!"
echo ""

# Function to delete items by partition key prefix
delete_by_pk_prefix() {
    local prefix=$1
    local entity_name=$2
    
    echo "Fetching $entity_name records (PK starts with '$prefix')..."
    
    # Scan for all items with this PK prefix
    local items=$(aws dynamodb scan \
        --table-name "$TABLE_NAME" \
        --filter-expression "begins_with(PK, :prefix)" \
        --expression-attribute-values "{\":prefix\":{\"S\":\"$prefix\"}}" \
        --region "$REGION" \
        --output json)
    
    local count=$(echo "$items" | jq '.Items | length')
    echo "Found $count $entity_name records"
    
    if [ "$count" -eq 0 ]; then
        echo "No $entity_name records to delete"
        return
    fi
    
    # Extract PK and SK for batch delete
    local keys=$(echo "$items" | jq -c '.Items[] | {PK: .PK, SK: .SK}')
    
    # Delete in batches of 25 (DynamoDB limit)
    local batch_size=25
    local deleted=0
    
    echo "$keys" | while IFS= read -r key; do
        if [ -z "$key" ]; then
            continue
        fi
        
        # Collect batch
        batch="["
        for i in $(seq 1 $batch_size); do
            if [ -n "$key" ]; then
                if [ "$batch" != "[" ]; then
                    batch="$batch,"
                fi
                batch="$batch{\"DeleteRequest\":{\"Key\":$key}}"
                deleted=$((deleted + 1))
                read -r key || break
            else
                break
            fi
        done
        batch="$batch]"
        
        # Execute batch delete
        if [ "$batch" != "[]" ]; then
            aws dynamodb batch-write-item \
                --request-items "{\"$TABLE_NAME\":$batch}" \
                --region "$REGION" > /dev/null
            echo "  Deleted batch (total: $deleted)"
        fi
    done
    
    echo "✓ Deleted $deleted $entity_name records"
    echo ""
}

# Main menu
echo "What would you like to clean up?"
echo ""
echo "1. Delete ALL DEVICE records only (keeps installations, SIMs, contacts)"
echo "2. Delete ALL data (devices, installations, SIMs, contacts, surveys - EVERYTHING)"
echo "3. Delete specific entity type"
echo "4. Cancel"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "This will delete ALL devices and related data:"
        echo "  - DEVICE# (devices metadata)"
        echo "  - Device SIM associations"
        echo "  - Device installation associations"
        echo "  - Device repair history"
        echo ""
        read -p "Are you sure? Type 'DELETE DEVICES' to confirm: " confirm
        if [ "$confirm" = "DELETE DEVICES" ]; then
            echo ""
            echo "Starting device cleanup..."
            delete_by_pk_prefix "DEVICE#" "DEVICE"
            echo "✅ Device cleanup complete!"
        else
            echo "Cancelled."
        fi
        ;;
    
    2)
        echo ""
        echo "⚠️  DANGER: This will delete EVERYTHING in the table:"
        echo "  - All devices"
        echo "  - All installations"
        echo "  - All SIM cards"
        echo "  - All contacts"
        echo "  - All surveys"
        echo "  - All associations and history"
        echo ""
        read -p "Type 'DELETE EVERYTHING' to confirm: " confirm
        if [ "$confirm" = "DELETE EVERYTHING" ]; then
            echo ""
            echo "Starting complete cleanup..."
            delete_by_pk_prefix "DEVICE#" "DEVICE"
            delete_by_pk_prefix "INSTALL#" "INSTALL"
            delete_by_pk_prefix "SIM#" "SIM"
            delete_by_pk_prefix "CUSTOMER#" "CUSTOMER"
            delete_by_pk_prefix "SURVEY#" "SURVEY"
            echo "✅ Complete cleanup done!"
        else
            echo "Cancelled."
        fi
        ;;
    
    3)
        echo ""
        echo "Available entity types:"
        echo "  - DEVICE"
        echo "  - INSTALL"
        echo "  - SIM"
        echo "  - CUSTOMER"
        echo "  - SURVEY"
        echo ""
        read -p "Enter entity type to delete (e.g., DEVICE): " entity_type
        read -p "Type 'DELETE $entity_type' to confirm: " confirm
        if [ "$confirm" = "DELETE $entity_type" ]; then
            echo ""
            delete_by_pk_prefix "${entity_type}#" "$entity_type"
            echo "✅ $entity_type cleanup complete!"
        else
            echo "Cancelled."
        fi
        ;;
    
    4)
        echo "Cancelled."
        exit 0
        ;;
    
    *)
        echo "Invalid choice. Cancelled."
        exit 1
        ;;
esac
