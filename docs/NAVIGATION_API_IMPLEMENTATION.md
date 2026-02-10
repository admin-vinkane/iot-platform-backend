# Navigation Management API Implementation

## Overview

Created a new Lambda function `v_navigation` to handle all menu/navigation management operations. This follows the existing architectural pattern of domain-specific lambdas.

## Location

```
lambdas/v_navigation/
├── requirements.txt
└── v_navigation_api.py (1,150+ lines)
```

## Features Implemented

### ✅ All 11 API Endpoints

1. **GET /navigation/groups** - List all groups with nested items
2. **POST /navigation/groups** - Create navigation group
3. **PATCH /navigation/groups/{groupId}** - Update navigation group
4. **DELETE /navigation/groups/{groupId}** - Delete group and all items
5. **POST /navigation/groups/{groupId}/items** - Create navigation item
6. **PATCH /navigation/groups/{groupId}/items/{itemId}** - Update navigation item
7. **DELETE /navigation/groups/{groupId}/items/{itemId}** - Delete navigation item
8. **POST /navigation/groups/reorder** - Reorder groups
9. **POST /navigation/groups/{groupId}/items/reorder** - Reorder items within group
10. **POST /navigation/items/move** - Move item between groups
11. **GET /navigation/history** - Fetch audit trail

### ✅ Data Models (Pydantic)

- **NavigationGroup** / NavigationGroupCreate / NavigationGroupUpdate
- **NavigationItem** / NavigationItemCreate / NavigationItemUpdate
- **NavigationChangeHistory**
- **ReorderRequest** / ReorderItemsRequest / MoveItemRequest

### ✅ Validation Rules (as per spec)

- Group label: 2-50 characters, unique (case-insensitive)
- Group order: 1-100, unique
- Item label: 2-50 characters, unique within group (case-insensitive)
- Item path: starts with '/', no spaces, unique across all items
- Item order: 1-100, unique within group
- Permission: optional (empty string = no permission)

### ✅ Features

- **Audit Trail**: All changes recorded in history with before/after values
- **Hierarchical Data**: Groups contain items, properly nested
- **Sorting**: Groups and items returned sorted by `order` field
- **CORS Support**: OPTIONS preflight handling
- **Error Handling**: Comprehensive validation and error responses
- **Shared Utilities**: Uses `response_utils` for consistent responses
- **DEV_MODE**: Authentication bypass for development

## DynamoDB Schema

### Entity Types
- `NAVIGATION_GROUP`
- `NAVIGATION_ITEM`
- `NAVIGATION_HISTORY`

### Key Structure
```
Groups:
  PK: GROUP#{groupId}
  SK: METADATA#{groupId}

Items:
  PK: ITEM#{itemId}
  SK: METADATA#{itemId}
  parentId: {groupId}

History:
  PK: HISTORY#{historyId}
  SK: TIMESTAMP#{iso8601}
```

## Deployment Steps

### 1. Create DynamoDB Table

```bash
# Using AWS CLI or Terraform
aws dynamodb create-table \
  --table-name v_navigation_dev \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

### 2. Package and Upload Lambda

```bash
./scripts/package_and_upload_lambda.sh lambdas/v_navigation --env dev --upload
```

### 3. Configure API Gateway Routes

Add these routes to your API Gateway (v2 HTTP API):

```
GET    /navigation/groups
POST   /navigation/groups
PATCH  /navigation/groups/{groupId}
DELETE /navigation/groups/{groupId}
POST   /navigation/groups/{groupId}/items
PATCH  /navigation/groups/{groupId}/items/{itemId}
DELETE /navigation/groups/{groupId}/items/{itemId}
POST   /navigation/groups/reorder
POST   /navigation/groups/{groupId}/items/reorder
POST   /navigation/items/move
GET    /navigation/history
```

### 4. Set Environment Variables

```bash
TABLE_NAME=v_navigation_dev
DEV_MODE=true  # Set to "false" in production
```

### 5. Configure IAM Permissions

Lambda execution role needs:
```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
    "dynamodb:Query",
    "dynamodb:Scan"
  ],
  "Resource": [
    "arn:aws:dynamodb:*:*:table/v_navigation_dev",
    "arn:aws:dynamodb:*:*:table/v_navigation_dev/*"
  ]
}
```

## Testing

### Sample Requests

#### Create Group
```bash
curl -X POST https://your-api.com/navigation/groups \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Administration",
    "icon": "Shield",
    "isActive": true,
    "order": 1,
    "isCollapsible": true,
    "defaultExpanded": false
  }'
```

#### Create Item
```bash
curl -X POST https://your-api.com/navigation/groups/{groupId}/items \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Menu Management",
    "icon": "Grid",
    "path": "/menu-management",
    "permission": "can_manage_navigation",
    "isActive": true,
    "order": 1
  }'
```

#### List All Groups
```bash
curl https://your-api.com/navigation/groups
```

#### Get History
```bash
curl https://your-api.com/navigation/history
```

## Architecture Benefits

### Why Separate Lambda?

1. **Domain Separation**: Navigation is distinct from user management
2. **Independent Deployment**: Changes don't affect user/auth systems
3. **Scalability**: Can scale independently based on traffic
4. **Maintainability**: Smaller, focused codebase (1,150 lines vs 2,579 in v_users)
5. **Error Isolation**: Navigation issues don't impact user authentication

### Follows Existing Patterns

- DynamoDB entity types (PK/SK structure)
- Pydantic models for validation
- Shared response utilities
- CORS handling
- DEV_MODE authentication bypass
- Comprehensive logging
- ISO-8601 timestamps
- Decimal conversion for JSON serialization

## History Tracking

Every operation is logged with:
- Entity type (group/item)
- Entity ID
- Change type (created/updated/deleted/reordered/moved/status_changed)
- Field-level changes (before/after values)
- User who made the change
- Timestamp
- Optional IP address

## Next Steps

1. **Deploy Lambda**: Use existing packaging scripts
2. **Create DynamoDB Table**: Use Terraform or AWS CLI
3. **Configure API Gateway**: Add routes with path parameters
4. **Enable CORS**: Configure API Gateway CORS settings
5. **Test Endpoints**: Use provided sample requests
6. **Seed Initial Data**: Create default navigation structure
7. **Add Authentication**: Replace DEV_MODE with proper JWT validation

## API Response Format

All responses follow the existing SuccessResponse/ErrorResponse pattern:

**Success (200/201):**
```json
{
  "statusCode": 200,
  "body": { ... },
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  }
}
```

**Error (4xx/5xx):**
```json
{
  "statusCode": 400,
  "body": {
    "error": "Error message"
  },
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  }
}
```

## Dependencies

- `boto3` - AWS SDK
- `pydantic==2.5.3` - Data validation
- `shared.response_utils` - Response formatting
- Python 3.9+ (Lambda runtime)

## Notes

- All timestamps use ISO-8601 format with 'Z' suffix
- Decimal types auto-converted to int/float for JSON
- Path validation enforces leading '/' and no spaces
- Label uniqueness is case-insensitive
- Deleting a group cascades to all child items
- History is never deleted (audit trail preserved)
