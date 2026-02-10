# IoT Platform Backend - API Overview

Complete API reference for all backend services.

**Base URL:** `https://your-api-gateway-url.amazonaws.com/{stage}`

**Stages:** `dev`, `staging`, `prod`

---

## Table of Contents

- [Navigation API](#navigation-api) 🆕
- [Users API](#users-api)
- [Devices API](#devices-api)
- [Regions API](#regions-api)
- [Customers API](#customers-api)

---

## Navigation API

**Lambda:** `v_navigation_api`  
**Base Path:** `/navigation`  
**Documentation:** [NAVIGATION_API_IMPLEMENTATION.md](NAVIGATION_API_IMPLEMENTATION.md)

Menu and navigation management with full audit trail.

### Endpoints

#### Groups

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/navigation/groups` | List all groups with nested items |
| POST | `/navigation/groups` | Create navigation group |
| PATCH | `/navigation/groups/{groupId}` | Update navigation group |
| DELETE | `/navigation/groups/{groupId}` | Delete group and all items |
| POST | `/navigation/groups/reorder` | Reorder groups |

#### Items

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/navigation/groups/{groupId}/items` | Create navigation item |
| PATCH | `/navigation/groups/{groupId}/items/{itemId}` | Update navigation item |
| DELETE | `/navigation/groups/{groupId}/items/{itemId}` | Delete navigation item |
| POST | `/navigation/groups/{groupId}/items/reorder` | Reorder items within group |
| POST | `/navigation/items/move` | Move item between groups |

#### History

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/navigation/history` | Fetch audit trail of all changes |

### Example Requests

**List all groups:**
```bash
curl https://api.example.com/navigation/groups
```

**Create group:**
```bash
curl -X POST https://api.example.com/navigation/groups \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Administration",
    "icon": "Shield",
    "order": 1,
    "isActive": true,
    "isCollapsible": true,
    "defaultExpanded": false
  }'
```

**Create item:**
```bash
curl -X POST https://api.example.com/navigation/groups/{groupId}/items \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Menu Management",
    "icon": "Grid",
    "path": "/menu-management",
    "permission": "can_manage_navigation",
    "order": 1,
    "isActive": true
  }'
```

### Data Models

**NavigationGroup:**
```json
{
  "id": "GROUP_20260210120000_abc12345",
  "label": "Administration",
  "icon": "Shield",
  "isActive": true,
  "order": 1,
  "isCollapsible": true,
  "defaultExpanded": false,
  "items": [NavigationItem],
  "createdAt": "2026-02-10T12:00:00.000Z",
  "updatedAt": "2026-02-10T12:00:00.000Z",
  "createdBy": "admin@example.com",
  "updatedBy": "admin@example.com"
}
```

**NavigationItem:**
```json
{
  "id": "ITEM_20260210120100_xyz67890",
  "label": "Menu Management",
  "icon": "Grid",
  "path": "/menu-management",
  "permission": "can_manage_navigation",
  "isActive": true,
  "order": 1,
  "parentId": "GROUP_20260210120000_abc12345",
  "children": [],
  "createdAt": "2026-02-10T12:01:00.000Z",
  "updatedAt": "2026-02-10T12:01:00.000Z",
  "createdBy": "admin@example.com",
  "updatedBy": "admin@example.com"
}
```

---

## Users API

**Lambda:** `v_users_api`  
**Base Path:** `/users`  
**Documentation:** [USERS_API_IMPROVEMENTS.md](USERS_API_IMPROVEMENTS.md)

User management, authentication, roles, and permissions (RBAC).

### Endpoints

#### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users` | List all users |
| POST | `/users` | Create user |
| GET | `/users/{userId}` | Get user details |
| PUT | `/users/{userId}` | Update user |
| PATCH | `/users/{userId}` | Partial update user |
| DELETE | `/users/{userId}` | Delete user |
| POST | `/users/sync-firebase` | Sync user with Firebase |

#### User Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/{userId}/profile` | Get user profile |
| PUT | `/users/{userId}/profile` | Update user profile |
| POST | `/users/{userId}/profile/picture` | Upload profile picture |

#### Roles & Permissions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/permissions/roles` | List all roles |
| POST | `/permissions/roles` | Create role |
| GET | `/permissions/roles/{roleName}` | Get role details |
| PUT | `/permissions/roles/{roleName}` | Update role |
| DELETE | `/permissions/roles/{roleName}` | Delete role |
| POST | `/permissions/roles/{roleName}/permissions` | Assign permission to role |
| GET | `/permissions/roles/{roleName}/permissions` | Get role permissions |
| DELETE | `/permissions/roles/{roleName}/permissions/{permissionName}` | Remove permission from role |
| GET | `/permissions` | List all permissions |
| POST | `/permissions` | Create permission |
| GET | `/permissions/{permissionName}` | Get permission details |
| PUT | `/permissions/{permissionName}` | Update permission |
| DELETE | `/permissions/{permissionName}` | Delete permission |

#### User-Role Assignments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/permissions/users/{userId}/roles` | Assign role to user |
| GET | `/permissions/users/{userId}/roles` | Get user roles |
| DELETE | `/permissions/users/{userId}/roles/{roleName}` | Remove role from user |
| GET | `/permissions/users/{userId}/permissions` | Get effective user permissions |

---

## Devices API

**Lambda:** `v_devices_api`  
**Base Path:** `/devices`  
**Documentation:** [DEVICES_API_ROUTES.md](DEVICES_API_ROUTES.md)

IoT device management and configuration.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/devices` | List all devices |
| POST | `/devices` | Create device |
| GET | `/devices/{deviceId}` | Get device details |
| PUT | `/devices/{deviceId}` | Update device |
| DELETE | `/devices/{deviceId}` | Delete device |
| GET | `/devices/{deviceId}/configs` | Get device configurations |
| POST | `/devices/{deviceId}/configs` | Create device configuration |
| GET | `/devices/{deviceId}/telemetry` | Get device telemetry data |
| POST | `/devices/{deviceId}/commands` | Send command to device |

---

## Regions API

**Lambda:** `v_regions_api`  
**Base Path:** `/regions`  
**Documentation:** [REGIONS_API_GUIDE.md](REGIONS_API_GUIDE.md)

Geographic region and administrative boundary management.

### Endpoints

#### States

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/regions/states` | List all states |
| POST | `/regions/states` | Create state |
| GET | `/regions/states/{stateId}` | Get state details |
| PUT | `/regions/states/{stateId}` | Update state |
| DELETE | `/regions/states/{stateId}` | Delete state |

#### Districts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/regions/states/{stateId}/districts` | List districts in state |
| POST | `/regions/states/{stateId}/districts` | Create district |
| GET | `/regions/districts/{districtId}` | Get district details |
| PUT | `/regions/districts/{districtId}` | Update district |
| DELETE | `/regions/districts/{districtId}` | Delete district |

#### Mandals

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/regions/districts/{districtId}/mandals` | List mandals in district |
| POST | `/regions/districts/{districtId}/mandals` | Create mandal |
| GET | `/regions/mandals/{mandalId}` | Get mandal details |
| PUT | `/regions/mandals/{mandalId}` | Update mandal |
| DELETE | `/regions/mandals/{mandalId}` | Delete mandal |

#### Villages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/regions/mandals/{mandalId}/villages` | List villages in mandal |
| POST | `/regions/mandals/{mandalId}/villages` | Create village |
| GET | `/regions/villages/{villageId}` | Get village details |
| PUT | `/regions/villages/{villageId}` | Update village |
| DELETE | `/regions/villages/{villageId}` | Delete village |

---

## Customers API

**Lambda:** `v_customers_api`  
**Base Path:** `/customers`  
**Documentation:** [CUSTOMER_ENDPOINTS_REVIEW.md](CUSTOMER_ENDPOINTS_REVIEW.md)

Customer and client management.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/customers` | List all customers |
| POST | `/customers` | Create customer |
| GET | `/customers/{customerId}` | Get customer details |
| PUT | `/customers/{customerId}` | Update customer |
| DELETE | `/customers/{customerId}` | Delete customer |
| GET | `/customers/{customerId}/devices` | List customer devices |
| GET | `/customers/{customerId}/installations` | List customer installations |

---

## Common Response Format

All APIs follow a standardized response format:

**Success Response (2xx):**
```json
{
  "statusCode": 200,
  "body": {
    "data": { ... }
  },
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  }
}
```

**Error Response (4xx/5xx):**
```json
{
  "statusCode": 400,
  "body": {
    "error": "Error message",
    "details": "Additional error details"
  },
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  }
}
```

---

## Authentication

All endpoints (except OPTIONS) require authentication via:
- **Firebase JWT Token** (Production)
- **DEV_MODE bypass** (Development only)

**Header:**
```
Authorization: Bearer <jwt-token>
```

---

## CORS

All APIs support CORS with:
- **Allow-Origins:** `*` (dev), specific domains (prod)
- **Allow-Methods:** GET, POST, PUT, PATCH, DELETE, OPTIONS
- **Allow-Headers:** Content-Type, Authorization, X-Amz-Date, X-Api-Key

---

## Rate Limiting

API Gateway rate limits (configurable per stage):
- **Burst:** 5000 requests
- **Rate:** 10000 requests/second

See [TERRAFORM_RATE_LIMITING.md](TERRAFORM_RATE_LIMITING.md) for configuration.

---

## Pagination

List endpoints support pagination via query parameters:
- `limit` - Number of items per page (default: 50, max: 100)
- `nextToken` - Continuation token from previous response

**Example:**
```bash
GET /users?limit=20&nextToken=eyJQSyI6IlVTRVIjLCJTSyI6IjEyMyJ9
```

---

## Filtering & Sorting

Some endpoints support filtering and sorting:
- `filter` - Filter expression (e.g., `isActive=true`)
- `sort` - Sort field (e.g., `createdAt`)
- `order` - Sort order: `asc` or `desc`

**Example:**
```bash
GET /devices?filter=isActive=true&sort=createdAt&order=desc
```

---

## Deployment Status

| Lambda | Status | Last Deployed | Version |
|--------|--------|---------------|---------|
| v_navigation | ✅ Active | 2026-02-10 | 20260210180859 |
| v_users | ✅ Active | - | - |
| v_devices | ✅ Active | - | - |
| v_regions | ✅ Active | - | - |
| v_customers | ✅ Active | - | - |

---

## Support

For API issues or questions:
- Check individual API documentation in `docs/` folder
- Review test files in `tests/` folder for request examples
- Contact: your-team@example.com
