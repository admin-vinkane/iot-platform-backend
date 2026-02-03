# Device-to-Habitation Linking - Verification (UPDATED)

## Overview
This document verifies device-to-habitation linking implementation after removing unnecessary device creation functionality.

---

## ✅ Device-to-Habitation Linking - SIMPLIFIED

**Devices are linked to habitation assets in 1 place only:**

### `POST /installs/{installId}/devices/link` - Link Existing Device

**Location**: [lambdas/v_devices/v_devices_api.py](lambdas/v_devices/v_devices_api.py#L842)

**Purpose**: Link an existing device to an installation AND automatically link it to the habitation asset in Thingsboard

**Implementation**:
- Line 842: Checks if request is for `/devices/link`
- Validates device exists
- Validates installation exists  
- Executes DynamoDB link transaction
- Line 893-920: On success, links device to habitation asset in Thingsboard (non-blocking)

**Flow**:
```
POST /installs/{installId}/devices/link
    ↓
validate device exists → validate installation exists
    ↓
execute_install_device_link_transaction() [DynamoDB]
    ↓ (on success)
link_device_to_habitation(device_id, habitation_id)
    └─ POST /api/relation (Thingsboard)
        └─ Creates ASSET→DEVICE relation with type "contains"
```

**Request Example**:
```bash
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST-001/devices/link" \
  -H "Content-Type: application/json" \
  -d '{"deviceId": "existing-device-123"}'
```

**Response**:
```json
{
  "installId": "INST-001",
  "linked": [{"deviceId": "existing-device-123", "status": "linked"}],
  "performedBy": "system",
  "timestamp": "2026-01-31T16:18:16.277375Z"
}
```

---

## Core Utility Function

### `link_device_to_habitation()`

**Location**: [shared/thingsboard_utils.py](shared/thingsboard_utils.py#L615)

**Purpose**: Creates a relation linking a device to a habitation asset in Thingsboard

**Implementation**:
```python
def link_device_to_habitation(device_id: str, habitation_id: str) -> bool:
    """Create a relation linking a device to a habitation asset."""
    # POST /api/relation with:
    # from: {"entityType": "ASSET", "id": habitation_id}
    # to: {"entityType": "DEVICE", "id": device_id}
    # type: "contains"
```

**Error Handling**:
- ✅ HTTP 200: Success - relation created
- ✅ HTTP 409: Conflict - relation already exists (treated as success)
- ✅ Other errors: Logged and returns False

---

## Removed Functionality

The following have been **removed** as they were not needed:

❌ `create_or_get_device()` - Unnecessary (devices already exist)
❌ `sync_device_to_habitation()` - Combined creation + linking (unnecessary)
❌ `POST /installs/{installId}/devices?operation=sync` - Device creation endpoint (unnecessary)

---

## Device Lifecycle

**Correct workflow:**

```
1. Devices are created externally (outside this API)
   ↓
2. Installation is created with region hierarchy
   (POST /installs)
   ↓
3. Existing devices are linked to installation
   (POST /installs/{installId}/devices/link)
   ↓
4. On successful link → device is automatically linked to habitation in Thingsboard
```

---

## Deployment Status

✅ **Lambda Deployed** - CodeSha: X2q4cCaIMHD7Btk08LMfOzbsV09o/y75LEeUyJYo6ZE=

Changes:
- ✅ Removed device sync endpoint (`/devices?operation=sync`)
- ✅ Removed `create_or_get_device()` function
- ✅ Removed `sync_device_to_habitation()` function
- ✅ Kept `link_device_to_habitation()` function (used by `/devices/link` endpoint)

---

## Testing

### Test Case: Link Existing Device

```bash
# 1. Create installation first (syncs regions)
curl -X POST https://api/installs \
  -d '{
    "InstallationId": "INST-TEST-001",
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "005",
    "Status": "active"
  }'

# 2. Link existing device to installation
curl -X POST https://api/installs/INST-TEST-001/devices/link \
  -d '{"deviceId": "device-uuid-123"}'

# Expected: Device linked in DynamoDB + linked to habitation in Thingsboard
```

---

## Summary

| Function | Status | Purpose |
|----------|--------|---------|
| `link_device_to_habitation()` | ✅ Kept | Creates device→habitation relation in Thingsboard |
| `create_or_get_device()` | ❌ Removed | Not needed - devices already exist |
| `sync_device_to_habitation()` | ❌ Removed | Not needed - separate link endpoint handles it |
| `POST /devices?operation=sync` | ❌ Removed | Not needed - device creation is external |
| `POST /devices/link` | ✅ Kept | Links existing device to installation + habitation |

---

## Conclusion

✅ **Simplified Implementation**

- Single endpoint: `POST /installs/{installId}/devices/link`
- Links existing devices (from external system) to installation AND habitation
- Non-blocking Thingsboard linking (errors don't fail main operation)
- Clean separation of concerns: Device management external, installation/linking internal

**Ready for production** ✅
