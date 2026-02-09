#!/usr/bin/env python3
"""
Migration script to create profiles for existing users.

This script scans the v_users_dev table for all users and creates
default profiles (PROFILE#MAIN) for users who don't have one yet.

Usage:
    python scripts/migrate_user_profiles.py [--dry-run] [--table-name TABLE_NAME]

Options:
    --dry-run: Preview what would be migrated without making changes
    --table-name: DynamoDB table name (default: v_users_dev)
"""

import boto3
import sys
import argparse
from datetime import datetime
from decimal import Decimal
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# DynamoDB setup
dynamodb = boto3.resource('dynamodb')


def scan_all_users(table_name):
    """Scan DynamoDB table and return all user records."""
    table = dynamodb.Table(table_name)
    users = []
    
    logger.info(f"Scanning table: {table_name}")
    
    # Scan with pagination
    response = table.scan()
    users.extend(response.get('Items', []))
    
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        users.extend(response.get('Items', []))
    
    # Filter for user records only (not profiles or other entities)
    # User records have 'id' field and entityType='USER' or don't have PK starting with USER#
    user_records = [
        user for user in users 
        if user.get('id') and (
            user.get('entityType') == 'USER' or 
            not user.get('PK', '').startswith('USER#')
        )
    ]
    
    logger.info(f"Found {len(user_records)} user records")
    return user_records


def check_profile_exists(table, user_id):
    """Check if a profile already exists for a user."""
    try:
        response = table.get_item(
            Key={'PK': f'USER#{user_id}', 'SK': 'PROFILE#MAIN'}
        )
        return 'Item' in response
    except Exception as e:
        logger.error(f"Error checking profile for user {user_id}: {str(e)}")
        return False


def create_default_profile(table, user, dry_run=False):
    """Create a default profile for a user."""
    user_id = user.get('id')
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    profile_item = {
        'PK': f'USER#{user_id}',
        'SK': 'PROFILE#MAIN',
        'userId': user_id,
        'entityType': 'USER_PROFILE',
        'firstName': user.get('firstName', ''),
        'lastName': user.get('lastName', ''),
        'phoneNumber': user.get('phoneNumber'),
        'language': 'en',
        'organization': None,
        'department': None,
        'timezone': 'UTC',
        'profilePictureUrl': None,
        'address': {
            'street': '',
            'city': '',
            'state': '',
            'country': '',
            'postalCode': ''
        },
        'preferences': {
            'notifications': True,
            'emailAlerts': True,
            'smsAlerts': False
        },
        'createdAt': timestamp,
        'updatedAt': timestamp
    }
    
    if dry_run:
        logger.info(f"[DRY RUN] Would create profile for user: {user_id} ({user.get('email')})")
        return True
    
    try:
        table.put_item(Item=profile_item)
        logger.info(f"Created profile for user: {user_id} ({user.get('email')})")
        return True
    except Exception as e:
        logger.error(f"Failed to create profile for user {user_id}: {str(e)}")
        return False


def migrate_profiles(table_name='v_users_dev', dry_run=False):
    """Main migration function."""
    table = dynamodb.Table(table_name)
    
    logger.info("=" * 60)
    logger.info("Starting User Profile Migration")
    logger.info(f"Table: {table_name}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("=" * 60)
    
    # Get all users
    users = scan_all_users(table_name)
    
    if not users:
        logger.warning("No users found to migrate")
        return
    
    # Track statistics
    stats = {
        'total_users': len(users),
        'profiles_exist': 0,
        'profiles_created': 0,
        'profiles_failed': 0
    }
    
    # Process each user
    for user in users:
        user_id = user.get('id')
        
        if not user_id:
            logger.warning(f"Skipping user with no ID: {user}")
            continue
        
        # Check if profile already exists
        if check_profile_exists(table, user_id):
            logger.info(f"Profile already exists for user: {user_id}")
            stats['profiles_exist'] += 1
            continue
        
        # Create profile
        if create_default_profile(table, user, dry_run):
            stats['profiles_created'] += 1
        else:
            stats['profiles_failed'] += 1
    
    # Print summary
    logger.info("=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"Total users processed:    {stats['total_users']}")
    logger.info(f"Profiles already existed: {stats['profiles_exist']}")
    logger.info(f"Profiles created:         {stats['profiles_created']}")
    logger.info(f"Profiles failed:          {stats['profiles_failed']}")
    logger.info("=" * 60)
    
    if dry_run:
        logger.info("This was a DRY RUN - no changes were made")
        logger.info("Run without --dry-run to perform the actual migration")
    else:
        logger.info("Migration complete!")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate existing users to have default profiles'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview migration without making changes'
    )
    parser.add_argument(
        '--table-name',
        default='v_users_dev',
        help='DynamoDB table name (default: v_users_dev)'
    )
    
    args = parser.parse_args()
    
    try:
        migrate_profiles(
            table_name=args.table_name,
            dry_run=args.dry_run
        )
    except KeyboardInterrupt:
        logger.info("\nMigration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed with error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
