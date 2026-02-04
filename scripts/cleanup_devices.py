#!/usr/bin/env python3
"""
Cleanup script to delete all DEVICE records from v_devices_dev table
"""

import boto3
import sys
from botocore.exceptions import ClientError

REGION = "ap-south-2"
TABLE_NAME = "v_devices_dev"

def delete_devices():
    """Delete all device records from DynamoDB"""
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)
    
    print("=" * 60)
    print("Device Data Cleanup Script")
    print("=" * 60)
    print(f"Region: {REGION}")
    print(f"Table: {TABLE_NAME}")
    print()
    print("⚠️  WARNING: This will permanently delete ALL DEVICE data!")
    print()
    
    # Scan for all device items
    print("Scanning for DEVICE records...")
    items_to_delete = []
    
    try:
        response = table.scan(
            FilterExpression='begins_with(PK, :prefix)',
            ExpressionAttributeValues={':prefix': 'DEVICE#'}
        )
        
        items_to_delete.extend(response.get('Items', []))
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='begins_with(PK, :prefix)',
                ExpressionAttributeValues={':prefix': 'DEVICE#'},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items_to_delete.extend(response.get('Items', []))
        
        print(f"Found {len(items_to_delete)} DEVICE records to delete")
        
        if len(items_to_delete) == 0:
            print("No devices to delete. Exiting.")
            return
        
        # Confirm deletion
        print()
        confirm = input("Type 'DELETE DEVICES' to confirm: ")
        if confirm != "DELETE DEVICES":
            print("Cancelled.")
            return
        
        print()
        print("Deleting devices...")
        
        # Delete in batches of 25 (DynamoDB limit)
        deleted = 0
        failed = 0
        
        for i in range(0, len(items_to_delete), 25):
            batch = items_to_delete[i:i+25]
            
            with table.batch_writer() as batch_writer:
                for item in batch:
                    try:
                        batch_writer.delete_item(
                            Key={
                                'PK': item['PK'],
                                'SK': item['SK']
                            }
                        )
                        deleted += 1
                    except ClientError as e:
                        print(f"  Error deleting {item['PK']}/{item['SK']}: {e}")
                        failed += 1
            
            print(f"  Progress: {deleted}/{len(items_to_delete)} deleted", end='\r')
        
        print()
        print()
        print(f"✅ Cleanup complete!")
        print(f"   Deleted: {deleted}")
        if failed > 0:
            print(f"   Failed: {failed}")
        
    except ClientError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    delete_devices()
