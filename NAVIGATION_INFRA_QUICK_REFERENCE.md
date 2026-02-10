## DynamoDB Table

**Table Name:** `v_navigation_{environment}`

**Keys:**
- **PK** (HASH): String - Format: `GROUP#{id}`, `ITEM#{id}`, `HISTORY#{id}`
- **SK** (RANGE): String - Format: `METADATA#{id}`, `TIMESTAMP#{iso8601}`

**Attributes:**
- `entityType`: String - `NAVIGATION_GROUP`, `NAVIGATION_ITEM`, `NAVIGATION_HISTORY`
- `parentId`: String - For items, references parent group ID

**Global Secondary Indexes:**
1. **GSI1-EntityType**
   - Hash: `entityType`
   - Range: `SK`
   - Projection: ALL

2. **GSI2-ParentId** 
   - Hash: `parentId`
   - Range: `order`
   - Projection: ALL

**Billing Mode:** PAY_PER_REQUEST

---

## API Gateway Routes (11 total)

### Lambda Integration
- **Function Name:** `v_navigation_{environment}`
- **Handler:** `v_navigation_api.lambda_handler`
- **Runtime:** `python3.11`
- **Timeout:** 30s
- **Memory:** 512MB

### Routes

| Method | Path | Parameters |
|--------|------|------------|
| GET | `/navigation/groups` | - |
| POST | `/navigation/groups` | - |
| PATCH | `/navigation/groups/{groupId}` | groupId |
| DELETE | `/navigation/groups/{groupId}` | groupId |
| POST | `/navigation/groups/reorder` | - |
| POST | `/navigation/groups/{groupId}/items` | groupId |
| PATCH | `/navigation/groups/{groupId}/items/{itemId}` | groupId, itemId |
| DELETE | `/navigation/groups/{groupId}/items/{itemId}` | groupId, itemId |
| POST | `/navigation/groups/{groupId}/items/reorder` | groupId |
| POST | `/navigation/items/move` | - |
| GET | `/navigation/history` | - |

### OPTIONS Routes (for CORS)
- `OPTIONS /navigation/groups`
- `OPTIONS /navigation/groups/{groupId}`
- `OPTIONS /navigation/groups/{groupId}/items`
- `OPTIONS /navigation/groups/{groupId}/items/{itemId}`

---

## IAM Permissions

**DynamoDB Actions:**
- `dynamodb:GetItem`
- `dynamodb:PutItem`
- `dynamodb:UpdateItem`
- `dynamodb:DeleteItem`
- `dynamodb:Query`
- `dynamodb:Scan`

**Resources:**
- `arn:aws:dynamodb:*:*:table/v_navigation_{environment}`
- `arn:aws:dynamodb:*:*:table/v_navigation_{environment}/index/*`

---

## Environment Variables

- `TABLE_NAME`: `v_navigation_{environment}`
- `DEV_MODE`: `true` (dev), `false` (prod)

---

## CORS Configuration

**Allow Origins:** `*` (dev), specific domains (prod)  
**Allow Methods:** GET, POST, PATCH, DELETE, OPTIONS  
**Allow Headers:** Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token  
**Max Age:** 300 seconds
