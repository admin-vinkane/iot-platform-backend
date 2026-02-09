# Migration Script - User Profiles

## Overview

This script creates default profiles for all existing users in the `v_users_dev` DynamoDB table who don't already have a profile record.

## Prerequisites

- Python 3.7+
- boto3 installed: `pip install boto3`
- AWS credentials configured (via `aws configure` or environment variables)
- Access to DynamoDB table (v_users_dev)

## Usage

### Dry Run (Preview Only)
```bash
python migrate_user_profiles.py --dry-run
```

This shows what would be created without making any changes.

### Production Run
```bash
python migrate_user_profiles.py
```

### Custom Table Name
```bash
python migrate_user_profiles.py --table-name v_users_prod
```

## What It Does

1. Scans the DynamoDB table for all user records
2. For each user, checks if a profile exists (PK=USER#{userId}, SK=PROFILE#MAIN)
3. If no profile exists, creates one with:
   - `firstName`, `lastName` copied from user record
   - `phoneNumber` copied from user record
   - Default `language` = "en"
   - Default `timezone` = "UTC"
   - Empty address fields
   - Default preferences (notifications enabled)

## Example Output

```
============================================================
Starting User Profile Migration
Table: v_users_dev
Dry Run: False
============================================================
Scanning table: v_users_dev
Found 50 user records
Profile already exists for user: user1
Created profile for user: user2 (user2@example.com)
Created profile for user: user3 (user3@example.com)
Profile already exists for user: user4
...
============================================================
Migration Summary
============================================================
Total users processed:    50
Profiles already existed: 20
Profiles created:         30
Profiles failed:          0
============================================================
Migration complete!
```

## Profile Structure Created

```python
{
  'PK': 'USER#{userId}',
  'SK': 'PROFILE#MAIN',
  'userId': '{userId}',
  'entityType': 'USER_PROFILE',
  'firstName': '{from user record}',
  'lastName': '{from user record}',
  'phoneNumber': '{from user record or None}',
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
  'createdAt': '2026-02-04T16:00:00Z',
  'updatedAt': '2026-02-04T16:00:00Z'
}
```

## Safety Features

- **Dry Run Mode**: Always test with `--dry-run` first
- **Idempotent**: Safe to run multiple times (skips existing profiles)
- **Non-Destructive**: Only creates new records, never deletes or modifies existing ones
- **Error Handling**: Continues processing if individual profile creation fails

## Troubleshooting

### "Unable to locate credentials"
Configure AWS credentials:
```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=ap-south-2
```

### "Table not found"
Verify table name and region:
```bash
aws dynamodb describe-table --table-name v_users_dev
```

### "Access Denied"
Ensure IAM user/role has DynamoDB permissions:
- `dynamodb:Scan` (to read users)
- `dynamodb:GetItem` (to check for existing profiles)
- `dynamodb:PutItem` (to create profiles)

## When to Run

Run this script:
- ✅ After deploying the User Profile API for the first time
- ✅ When you want to ensure all users have profiles
- ✅ After importing users from another system
- ❌ Not needed if all users are created after profile API deployment (profiles auto-create on first access)

## Notes

- Script only processes records without a PK starting with "USER#" (actual user records, not profiles)
- Profiles are NOT created for soft-deleted or inactive users
- The script respects existing profiles and will not overwrite them
- Use `--dry-run` to preview changes before committing
