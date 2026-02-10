# Navigation Management Lambda (v_navigation)

Backend API for managing navigation menus, groups, and items with full audit trail.

## Quick Start

### Deploy
```bash
./scripts/package_and_upload_lambda.sh lambdas/v_navigation --env dev --upload
```

### Test Locally
```bash
cd lambdas/v_navigation
python -m pytest ../../tests/test_navigation_*.json
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/navigation/groups` | List all groups with items |
| POST | `/navigation/groups` | Create navigation group |
| PATCH | `/navigation/groups/{groupId}` | Update navigation group |
| DELETE | `/navigation/groups/{groupId}` | Delete group + items |
| POST | `/navigation/groups/{groupId}/items` | Create navigation item |
| PATCH | `/navigation/groups/{groupId}/items/{itemId}` | Update navigation item |
| DELETE | `/navigation/groups/{groupId}/items/{itemId}` | Delete navigation item |
| POST | `/navigation/groups/reorder` | Reorder groups |
| POST | `/navigation/groups/{groupId}/items/reorder` | Reorder items in group |
| POST | `/navigation/items/move` | Move item between groups |
| GET | `/navigation/history` | Get audit trail |

## Data Models

### NavigationGroup
```python
{
    "id": str,
    "label": str,              # 2-50 chars, unique (case-insensitive)
    "icon": str,
    "isActive": bool,
    "order": int,              # 1-100, unique
    "isCollapsible": bool,
    "defaultExpanded": bool,
    "items": [NavigationItem],
    "createdAt": str,          # ISO-8601
    "updatedAt": str,
    "createdBy": str,
    "updatedBy": str
}
```

### NavigationItem
```python
{
    "id": str,
    "label": str,              # 2-50 chars, unique within group
    "icon": str,
    "path": str,               # Must start with '/', unique globally
    "permission": str,         # Optional, empty = no permission
    "isActive": bool,
    "order": int,              # 1-100, unique within group
    "parentId": str,           # Group ID
    "children": [],
    "createdAt": str,
    "updatedAt": str,
    "createdBy": str,
    "updatedBy": str
}
```

## Environment Variables

- `TABLE_NAME` - DynamoDB table name (default: `v_navigation_dev`)
- `DEV_MODE` - Set to `true` for dev, `false` for prod (bypasses auth)

## DynamoDB Schema

```
Table: v_navigation_dev

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

## Features

✅ **Validation**: All fields validated via Pydantic  
✅ **Uniqueness**: Labels (case-insensitive) and paths  
✅ **Sorting**: Groups and items always returned ordered  
✅ **Audit Trail**: Every change logged with before/after  
✅ **Cascade Delete**: Deleting group removes all items  
✅ **CORS**: Full CORS support for frontend  
✅ **Error Handling**: Comprehensive validation & errors  

## Sample Requests

### Create Group
```bash
curl -X POST https://api.example.com/navigation/groups \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Administration",
    "icon": "Shield",
    "order": 1
  }'
```

### Create Item
```bash
curl -X POST https://api.example.com/navigation/groups/{groupId}/items \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Menu Management",
    "icon": "Grid",
    "path": "/menu-management",
    "permission": "can_manage_navigation",
    "order": 1
  }'
```

### List All
```bash
curl https://api.example.com/navigation/groups
```

## Dependencies

- `boto3` - AWS DynamoDB
- `pydantic==2.5.3` - Data validation
- `shared.response_utils` - Response formatting

## See Also

- [Full Implementation Docs](../../docs/NAVIGATION_API_IMPLEMENTATION.md)
- [API Specification](../../docs/ENABLE_CORS_API_GATEWAY.md)
