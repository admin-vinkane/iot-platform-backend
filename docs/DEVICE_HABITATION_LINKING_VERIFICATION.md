# Device-to-Habitation Linking - Comprehensive Verification

## Overview
This document verifies all places in the codebase where devices are linked to habitation assets in Thingsboard.

---

## 1. **Shared Utility Functions** (shared/thingsboard_utils.py)

### Function: `link_device_to_habitation()`
**Location**: [shared/thingsboard_utils.py](shared/thingsboard_utils.py#L697-L742)

**Purpose**: Creates a relation linking a device to a habitation asset in Thingsboard

**Details**:
```python
def link_device_to_habitation(device_id: str, habitation_id: str) -> bool:
    """
    Create a relation linking a device to a habitation asset.
    
    Args:
        device_id: Thingsboard device ID
        habitation_id: Thingsboard habitation asset ID
        
    Returns:
        bool: True if relation created successfully
    """
```

**What it does**:
- Creates POST request to `/api/relation`
- Links DEVICE → HABITATION with relation type "contains"
- Handles HTTP 409 (already exists) gracefully
- Returns boolean success status

**Code**:
- Line 724: Logs device linking action
- Line 729: Logs success
- Line 735: Handles existing relation (409 conflict)
- Line 737-740: Error handling

---

### Function: `sync_device_to_habitation()`
**Location**: [shared/thingsboard_utils.py](shared/thingsboard_utils.py#L744-L782)

**Purpose**: Create/get device and link it to habitation asset

**Details**:
```python
def sync_device_to_habitation(device_name: str, device_type: str, habitation_id: str) -> Tuple[Optional[Dict], List[str]]:
    """
    Create/get device and link it to habitation asset.
    
    Args:
        device_name: Name of the device
        device_type: Type of device
        habitation_id: Thingsboard habitation asset ID
        
    Returns:
        Tuple[Optional[Dict], List[str]]: (device object, errors list)
    """
```

**What it does**:
- Line 770-772: Calls `link_device_to_habitation()` after device creation
- Line 773: Appends error if linking fails

---

## 2. **API Endpoints** (lambdas/v_devices/v_devices_api.py)

### Endpoint 1: POST `/installs/{installId}/devices?operation=sync`
**Location**: [lambdas/v_devices/v_devices_api.py](lambdas/v_devices/v_devices_api.py#L339-L412)

**Purpose**: Create a device and link it to the habitation asset

**Implementation**:
- Line 367-368: Imports `sync_device_to_habitation`
- Line 381: Logs sync action
- Line 383-387: Calls `sync_device_to_habitation()` with:
  - `device_name`: Device name from request
  - `device_type`: Device type from request
  - `habitation_id`: Habitation ID from installation
- Line 389-392: Checks response and handles errors

**Flow**:
```
Request → Get Installation → Extract Habitation ID → 
Call sync_device_to_habitation() → Returns (device, errors) → 
Response with device details
```

**Example Request**:
```bash
POST /installs/INST-001/devices?operation=sync
{
  "deviceName": "INST-001_water_pump",
  "deviceType": "WaterPump"
}
```

---

### Endpoint 2: POST `/installs/{installId}/devices/link`
**Location**: [lambdas/v_devices/v_devices_api.py](lambdas/v_devices/v_devices_api.py#L893-L920)

**Purpose**: Link an existing device to installation AND link it to habitation asset

**Implementation**:
- Line 893: Comment: "Link device to habitation asset in Thingsboard (non-blocking)"
- Line 895: Imports `link_device_to_habitation`
- Line 898-920: Thingsboard linking logic
  - Line 898: Gets installation from DynamoDB
  - Line 904: Extracts habitation asset ID
  - Line 908-909: Calls `link_device_to_habitation(device_id, habitation_id)`
  - Line 911: Logs success
  - Line 913: Logs warning on failure (non-blocking)

**Flow**:
```
Request with deviceId → Validate device exists → Validate installation exists →
Execute DynamoDB link transaction → On success:
  - Get Installation → Extract Habitation ID → 
  - Call link_device_to_habitation() → 
  - Log result (non-blocking) → Response with success
```

**Example Request**:
```bash
POST /installs/INST-001/devices/link
{
  "deviceId": "existing-device-123"
}
```

---

## 3. **Summary of Device-to-Habitation Linking**

| Location | Function | Triggered By | Blocking | Purpose |
|----------|----------|--------------|----------|---------|
| **shared/thingsboard_utils.py** | `link_device_to_habitation()` | Utility function | N/A | Creates device→habitation relation |
| **shared/thingsboard_utils.py** | `sync_device_to_habitation()` | Utility function | N/A | Creates device and links to habitation |
| **v_devices_api.py:339** | `POST /devices?operation=sync` | API request | Yes | Create device + link to habitation |
| **v_devices_api.py:893** | `POST /devices/link` | API request | No | Link existing device to habitation |

---

## 4. **Call Chain Analysis**

### When Device Sync Endpoint is Called:
```
POST /installs/{installId}/devices?operation=sync
    ↓
sync_device_to_habitation(device_name, device_type, habitation_id)
    ├─ create_or_get_device(device_name, device_type)
    └─ link_device_to_habitation(device_id, habitation_id)
        └─ POST /api/relation (Thingsboard)
            └─ Creates DEVICE→HABITATION relation
```

### When Device Link Endpoint is Called:
```
POST /installs/{installId}/devices/link
    ↓
execute_install_device_link_transaction(install_id, device_id, ...)  [DynamoDB]
    ↓ (on success)
link_device_to_habitation(device_id, habitation_id)
    └─ POST /api/relation (Thingsboard)
        └─ Creates DEVICE→HABITATION relation
```

---

## 5. **Thingsboard API Calls**

### POST /api/relation
**Called from**:
- `link_device_to_habitation()` in shared/thingsboard_utils.py

**Payload**:
```json
{
  "from": {
    "entityType": "DEVICE",
    "id": "device-uuid"
  },
  "to": {
    "entityType": "ASSET",
    "id": "habitation-uuid"
  },
  "type": "contains"
}
```

**Response Handling**:
- 200: Success - relation created
- 409: Conflict - relation already exists (treated as success)
- Other errors: Logged and handled

---

## 6. **Error Handling**

### Blocking Errors (Fail the operation):
- Device sync endpoint (`/devices?operation=sync`):
  - Invalid deviceName
  - Habitation asset not found
  - Device creation failed

### Non-Blocking Errors (Logged but don't fail):
- Device link endpoint (`/devices/link`):
  - Thingsboard linking failures
  - Habitation not found
  - Installation not found
  - These are caught and logged as warnings

---

## 7. **Verification Checklist**

✅ **Function Definitions**:
- [x] `link_device_to_habitation()` exists in shared/thingsboard_utils.py (line 697)
- [x] `sync_device_to_habitation()` exists in shared/thingsboard_utils.py (line 744)

✅ **API Endpoints**:
- [x] POST `/installs/{installId}/devices?operation=sync` implemented (line 339)
- [x] POST `/installs/{installId}/devices/link` implemented (line 842)

✅ **Device-to-Habitation Linking**:
- [x] Called in sync_device_to_habitation() (line 772)
- [x] Called in devices/link endpoint (line 909)
- [x] Total: **2 places** where device linking happens

✅ **Error Handling**:
- [x] Blocking errors in sync endpoint
- [x] Non-blocking errors in link endpoint
- [x] HTTP 409 conflict handling
- [x] Logging at all stages

✅ **Deployment**:
- [x] Lambda deployed and updated (CodeSha: ADMYEPWBXm4+mjwDyujrfiynOldtxKguq5UGCtnfeJw=)

---

## 8. **Testing Scenarios**

### Scenario 1: Sync Device (Create + Link)
```bash
# Create installation first
curl -X POST https://api/installs \
  -d '{"InstallationId":"INST-001", ...}'

# Then sync device
curl -X POST https://api/installs/INST-001/devices?operation=sync \
  -d '{"deviceName":"pump-001", "deviceType":"WaterPump"}'

# Expected: Device created in Thingsboard + linked to habitation
```

### Scenario 2: Link Existing Device
```bash
# Link existing device to installation
curl -X POST https://api/installs/INST-001/devices/link \
  -d '{"deviceId":"existing-device-123"}'

# Expected: Device linked to installation in DynamoDB + linked to habitation in Thingsboard
```

---

## 9. **Relation Verification in Thingsboard**

After linking, verify the relation exists:

```bash
# Get relations for habitation asset
curl -X GET "http://18.61.64.102:8080/api/relations?fromId={habitation_id}&fromType=ASSET" \
  -H "X-Authorization: Bearer {token}"

# Should return array including:
# {
#   "from": {"entityType": "ASSET", "id": "habitation-uuid"},
#   "to": {"entityType": "DEVICE", "id": "device-uuid"},
#   "type": "contains"
# }
```

---

## 10. **Conclusion**

✅ **Device-to-Habitation linking is implemented in 2 places**:

1. **Utility function**: `sync_device_to_habitation()` - for creating and linking devices
2. **Link endpoint**: `POST /installs/{installId}/devices/link` - for linking existing devices

Both endpoints successfully link devices to habitation assets in Thingsboard via the `/api/relation` endpoint with proper error handling and logging.

**Deployment Status**: ✅ Deployed and Ready
