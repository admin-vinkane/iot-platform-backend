#!/usr/bin/env python3
"""
Migrate users from v_users_dev_bk (old schema with 'id' key) 
to v_users_dev (new schema with PK/SK composite keys).

Old Schema: { id: "user123", email: "...", ... }
New Schema: { PK: "USER#user123", SK: "USER#user123", id: "user123", email: "...", ... }
"""

import boto3
import logging
import argparse
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='ap-south-2')


def scan_source_table(table_name: str) -> List[Dict[str, Any]]:
    """Scan all items from source table (old schema)."""
    logger.info(f"Scanning source table: {table_name}")
    table = dynamodb.Table(table_name)
    
    items = []
    response = table.scan()
    items.extend(response.get('Items', []))
    
    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    
    logger.info(f"Found {len(items)} user records in source table")
    return items


def transform_user_to_new_schema(old_user: Dict[str, Any]) -> Dict[str, Any]:
    """Transform user record from old schema to new schema with PK/SK."""
    user_id = old_user.get('id')
    
    if not user_id:
        raise ValueError("User record missing 'id' field")
    
    # Create new record with PK/SK
    new_user = {
        'PK': f'USER#{user_id}',
        'SK': f'USER#{user_id}',
        'entityType': 'USER',
        **old_user  # Copy all existing fields
    }
    
    # Ensure timestamps exist
    if 'createdAt' not in new_user:
        new_user['createdAt'] = datetime.utcnow().isoformat() + 'Z'
    if 'updatedAt' not in new_user:
        new_user['updatedAt'] = datetime.utcnow().isoformat() + 'Z'
    
    return new_user


def write_user_to_target(table_name: str, user: Dict[str, Any], dry_run: bool = False) -> bool:
    """Write transformed user to target table."""
    if dry_run:
        logger.info(f"[DRY RUN] Would create user: {user.get('email', 'N/A')} (PK={user['PK']})")
        return True
    
    try:
        table = dynamodb.Table(table_name)
        table.put_item(Item=user)
        logger.info(f"✓ Migrated user: {user.get('email', 'N/A')} (ID: {user.get('id')})")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to migrate user {user.get('id')}: {str(e)}")
        return False


def check_target_table_exists(table_name: str) -> bool:
    """Check if target table exists and has correct schema."""
    try:
        client = boto3.client('dynamodb', region_name='ap-south-2')
        response = client.describe_table(TableName=table_name)
        
        # Verify it has PK/SK structure
        key_schema = response['Table']['KeySchema']
        has_pk = any(key['AttributeName'] == 'PK' and key['KeyType'] == 'HASH' for key in key_schema)
        has_sk = any(key['AttributeName'] == 'SK' and key['KeyType'] == 'RANGE' for key in key_schema)
        
        if not (has_pk and has_sk):
            logger.error(f"Table {table_name} exists but doesn't have PK/SK structure")
            return False
        
        logger.info(f"✓ Target table {table_name} exists with correct PK/SK schema")
        return True
    except client.exceptions.ResourceNotFoundException:
        logger.error(f"Target table {table_name} does not exist")
        return False
    except Exception as e:
        logger.error(f"Error checking target table: {str(e)}")
        return False


def migrate_users(source_table: str, target_table: str, dry_run: bool = False):
    """Main migration function."""
    logger.info("=" * 60)
    logger.info("User Schema Migration: Old Schema → New Schema (PK/SK)")
    logger.info(f"Source Table: {source_table}")
    logger.info(f"Target Table: {target_table}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("=" * 60)
    
    # Validate target table
    if not check_target_table_exists(target_table):
        logger.error("Migration aborted: Target table validation failed")
        return
    
    # Scan source table
    try:
        source_users = scan_source_table(source_table)
    except Exception as e:
        logger.error(f"Failed to scan source table: {str(e)}")
        return
    
    if not source_users:
        logger.warning("No users found in source table")
        return
    
    # Migrate each user
    logger.info(f"\nStarting migration of {len(source_users)} users...")
    logger.info("-" * 60)
    
    success_count = 0
    failure_count = 0
    
    for user in source_users:
        try:
            # Transform to new schema
            new_user = transform_user_to_new_schema(user)
            
            # Write to target table
            if write_user_to_target(target_table, new_user, dry_run):
                success_count += 1
            else:
                failure_count += 1
        except Exception as e:
            logger.error(f"Error processing user {user.get('id', 'unknown')}: {str(e)}")
            failure_count += 1
    
    # Summary
    logger.info("=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"Total users processed:  {len(source_users)}")
    logger.info(f"Successfully migrated:  {success_count}")
    logger.info(f"Failed:                 {failure_count}")
    logger.info("=" * 60)
    
    if dry_run:
        logger.info("\n⚠️  This was a DRY RUN - no changes were made")
        logger.info("Run without --dry-run to perform actual migration")
    else:
        logger.info("\n✅ Migration complete!")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate users from old schema (id) to new schema (PK/SK)'
    )
    parser.add_argument(
        '--source-table',
        default='v_users_dev_bk',
        help='Source table name (old schema)'
    )
    parser.add_argument(
        '--target-table',
        default='v_users_dev',
        help='Target table name (new schema with PK/SK)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview migration without making changes'
    )
    
    args = parser.parse_args()
    
    migrate_users(
        source_table=args.source_table,
        target_table=args.target_table,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
