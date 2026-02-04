# API Sample Data & Examples

Base URL: `https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev`

---

## 🔐 Encryption & Decryption

**All sensitive data is decrypted by default.** Use the `?decrypt=false` query parameter to get encrypted data.

### Sensitive Fields (Encrypted)
- **DEVICE**: `SerialNumber`
- **SIM**: `MobileNumber`, `Provider`
- **CUSTOMER**: `CustomerName`, `EmailAddress`, `PhoneNumber`, `Address`

### Query Parameters
- `decrypt=true` - Returns plaintext data (default)
- `decrypt=false` - Returns encrypted data (for inter-service communication)

### Example: Default (Decrypted)
```bash
GET /devices/DEV003
# SerialNumber returns as plaintext
{
  "SerialNumber": "SN_FRESH_ENCRYPTED_999"
}
```

### Example: Encrypted
```bash
GET /devices/DEV003?decrypt=false
# SerialNumber returns as encrypted dict
{
  "SerialNumber": {
    "encrypted_value": "U05fRlJFU0hfRU5DUllQVEVEXzk5OQ==",
    "key_version": "1",
    "encrypted_at": "2026-01-29T10:02:16.700045Z"
  }
}
```

---

## 1. DEVICES API

**Important:** All device operations require `EntityType` and `DeviceId` as mandatory parameters.

**Audit Trail Fields:** All device entities automatically track:
- `CreatedDate` / `UpdatedDate` - ISO 8601 timestamps with Z suffix
- `CreatedBy` / `UpdatedBy` - User identity (email) who created/last modified the record
- POST operations set all four fields; PUT operations update only UpdatedDate and UpdatedBy

### GET /devices
**Description:** List all devices (EntityType defaults to "DEVICE" if not provided)  
**Query Parameters (Optional):**
- `EntityType` - Defaults to "DEVICE" for backward compatibility
- `DeviceType` - Filter by device type
- `Status` - Filter by status
- `decrypt` - Set to `false` to get encrypted data (default: decrypted)

**Request:**
```bash
# Default - returns plaintext data
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices"

# Encrypted - returns encrypted data
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?decrypt=false"

# With filters and encrypted response
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?Status=Active&decrypt=false"
```

**Response (200) - Default (Decrypted):**
```json
[
  {
    "id": "DEV001",
    "deviceId": "DEV001",
    "deviceName": "Water Motor Unit",
    "deviceType": "IoT Sensor",
    "serialNumber": {
      "encrypted_value": "U04xMjM0NTY3ODk=",
      "key_version": "1",
      "encrypted_at": "2026-01-29T10:02:16.700045Z"
    },
    "status": "Active",
    "currentLocation": "Site A, Building 1",
    "createdAt": "2025-09-15T10:00:00Z",
    "updatedAt": "2025-12-11T06:39:42.685696Z",
    "RepairHistory": [],
    "InstallId": null,
    "LinkedSIM": null,
    "PK": "DEVICE#DEV001",
    "SK": "META"
  }
]
```

**Response (200) - With ?decrypt=true (Plaintext):**
```json
[
  {
    "id": "DEV001",
    "deviceId": "DEV001",
    "deviceName": "Water Motor Unit",
    "deviceType": "IoT Sensor",
    "serialNumber": "SN123456789",
    "status": "Active",
    "currentLocation": "Site A, Building 1",
    "createdAt": "2025-09-15T10:00:00Z",
    "updatedAt": "2025-12-11T06:39:42.685696Z",
    "RepairHistory": [],
    "InstallId": null,
    "LinkedSIM": null,
    "PK": "DEVICE#DEV001",
    "SK": "META"
  }
]
```

**Note:** `LinkedSIM` will contain SIM details when a SIM card is linked to the device:

**Encrypted (Default):**
```json
"LinkedSIM": {
  "simId": "SIM001",
  "linkedDate": "2025-12-15T10:30:00Z",
  "linkStatus": "active",
  "simDetails": {
    "mobileNumber": {
      "encrypted_value": "QzE0NjA5Njk0MzYxOQ==",
      "key_version": "1",
      "encrypted_at": "2026-01-29T10:02:16.700045Z"
    },
    "provider": {
      "encrypted_value": "QWlyZGVs",
      "key_version": "1",
      "encrypted_at": "2026-01-29T10:02:16.700045Z"
    },
    "plan": "IoT Data 10GB"
  }
}
```

**Decrypted (?decrypt=true):**
```json
"LinkedSIM": {
  "simId": "SIM001",
  "linkedDate": "2025-12-15T10:30:00Z",
  "linkStatus": "active",
  "simDetails": {
    "mobileNumber": "+919876543210",
    "provider": "Airtel",
    "plan": "IoT Data 10GB"
  }
}
```

### GET /devices with filters & decryption
**Description:** Get filtered devices with optional decryption  
**Request:**
```bash
# Default - encrypted
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?Status=Active"

# Decrypted - for UI/apps
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?Status=Active&decrypt=true"
```

**Response (200) - Encrypted:**
```json
[
  {
    "id": "DEV001",
    "deviceId": "DEV001",
    "deviceName": "Water Motor Unit",
    "serialNumber": {
      "encrypted_value": "U04xMjM0NTY3ODk=",
      "key_version": "1",
      "encrypted_at": "2026-01-29T10:02:16.700045Z"
    },
    "status": "Active"
  }
]
```

**Response (200) - Decrypted (?decrypt=true):**
```json
[
  {
    "id": "DEV001",
    "deviceId": "DEV001",
    "deviceName": "Water Motor Unit",
    "serialNumber": "SN123456789",
    "status": "Active"
  }
]
```

### GET /devices/{deviceId}
**Description:** Get single device with optional decryption  
**Query Parameters:**
- `decrypt=true` - Returns plaintext data

**Request:**
```bash
# Default - encrypted
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV003"

# Decrypted - for UI/apps
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV003?decrypt=true"
```

**Response (200) - Encrypted (Default):**
```json
{
  "DeviceId": "DEV003",
  "DeviceName": "Water Motor Unit Updated",
  "DeviceType": "WaterMotor",
  "SerialNumber": {
    "encrypted_value": "U05fRlJFU0hfRU5DUllQVEVEXzk5OQ==",
    "key_version": "1",
    "encrypted_at": "2026-01-29T10:02:16.700045Z"
  },
  "Status": "Active",
  "Location": "Test Lab",
  "LinkedSIM": {
    "simId": "SIM001",
    "linkedDate": "2026-01-29T10:00:00Z",
    "linkStatus": "active",
    "simDetails": {
      "MobileNumber": {
        "encrypted_value": "QzE0NjA5Njk0MzYxOQ==",
        "key_version": "1",
        "encrypted_at": "2026-01-29T10:02:16.700045Z"
      },
      "Provider": {
        "encrypted_value": "QWlyZGVs",
        "key_version": "1",
        "encrypted_at": "2026-01-29T10:02:16.700045Z"
      }
    }
  }
}
```

**Response (200) - Decrypted (?decrypt=true):**
```json
{
  "DeviceId": "DEV003",
  "DeviceName": "Water Motor Unit Updated",
  "DeviceType": "WaterMotor",
  "SerialNumber": "SN_FRESH_ENCRYPTED_999",
  "Status": "Active",
  "Location": "Test Lab",
  "LinkedSIM": {
    "simId": "SIM001",
    "linkedDate": "2026-01-29T10:00:00Z",
    "linkStatus": "active",
    "simDetails": {
      "MobileNumber": "+919876543210",
      "Provider": "Airtel"
    }
  }
}
```
**Description:** Get device configurations  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV001/configs
```

**Response (200):**
```json
[
  {
    "PK": "DEVICE#DEV001",
    "SK": "CONFIG#reportingInterval",
    "configKey": "reportingInterval",
    "configValue": "300",
    "unit": "seconds",
    "updatedAt": "2025-09-15T10:00:00Z"
  },
  {
    "PK": "DEVICE#DEV001",
    "SK": "CONFIG#threshold",
    "configKey": "threshold",
    "configValue": "75",
    "unit": "percentage",
    "updatedAt": "2025-09-15T10:00:00Z"
  }
]
```

### POST /devices
**Description:** Create new device (EntityType required, DeviceId optional)  
**Note:** 
- DeviceId is auto-generated as `DEV-{UUID}` if not provided (e.g., `DEV-A1B2C3D4`)
- `devicenum` field captures the device's IMEI or unique identifier (e.g., IMEI for cellular devices)
- Duplicate prevention is enabled - attempting to create a device with an existing DeviceId will return 409 Conflict.

**Request (with DeviceId):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices \
  -H "Content-Type: application/json" \
  -d '{
    "EntityType": "DEVICE",
    "DeviceId": "DEV099",
    "DeviceName": "New Water Sensor",
    "DeviceType": "Water Monitor",
    "SerialNumber": "SN999888777",
    "devicenum": "867123456789012",
    "Status": "available",
    "Location": "Warehouse A"
  }'
```

**Request (auto-generate DeviceId):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices \
  -H "Content-Type: application/json" \
  -d '{
    "EntityType": "DEVICE",
    "DeviceName": "Auto-Generated Device",
    "DeviceType": "Water Monitor",
    "SerialNumber": "SN123456789",
    "devicenum": "867987654321098",
    "Status": "available",
    "Location": "Warehouse B"
  }'
```

**Response (201) - Encrypted:**
```json
{
  "created": {
    "PK": "DEVICE#DEV099",
    "SK": "META",
    "EntityType": "DEVICE",
    "DeviceId": "DEV099",
    "DeviceName": "New Water Sensor",
    "SerialNumber": {
      "encrypted_value": "U05fOTk5ODg4Nzc3",
      "key_version": "1",
      "encrypted_at": "2026-01-16T11:30:00Z"
    },
    "Status": "available",
    "Location": "Warehouse A",
    "CreatedDate": "2026-01-16T11:30:00Z",
    "UpdatedDate": "2026-01-16T11:30:00Z",
    "CreatedBy": "admin@example.com",
    "UpdatedBy": "admin@example.com"
  }
}
```

**Note:** To get plaintext SerialNumber in response, retrieve with: `GET /devices/DEV099?decrypt=true`

**Response (409 - Duplicate):**
```json
{
  "error": "DEVICE with ID DEV099 already exists"
}
```

### PUT /devices
**Description:** Update existing device (EntityType and DeviceId required)  
**✅ Automatically tracks changes in `changeHistory` array**  
**✅ Sensitive fields (SerialNumber) are encrypted automatically**  
**Tracked Fields:** DeviceName, DeviceType, SerialNumber, Status, Location  
**Query Parameters:**
- `decrypt=true` - Returns plaintext in response (optional)

**Request:**
```bash
# Update device
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices \
  -H "Content-Type: application/json" \
  -d '{
    "EntityType": "DEVICE",
    "DeviceId": "DEV009",
    "DeviceName": "Updated Water Sensor",
    "DeviceType": "MOTOR",
    "SerialNumber": "SN_UPDATED_009",
    "Status": "active",
    "Location": "Delhi",
    "UpdatedBy": "admin"
  }'

# Get updated device decrypted
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV009?decrypt=true
```

**Response (200) - Encrypted (Default):**
```json
{
  "updated": {
    "EntityType": "DEVICE",
    "DeviceId": "DEV009",
    "DeviceName": "Updated Water Sensor",
    "DeviceType": "MOTOR",
    "SerialNumber": {
      "encrypted_value": "U05fVVBEQVRFRF8wMDk=",
      "key_version": "1",
      "encrypted_at": "2026-01-28T10:44:38.605124Z"
    },
    "Status": "active",
    "Location": "Delhi",
    "UpdatedDate": "2026-01-28T10:44:38.605124Z",
    "UpdatedBy": "admin",
    "changeHistory": [
      {
        "timestamp": "2026-01-28T10:44:38.605124Z",
        "action": "UPDATE",
        "changes": {
          "DeviceName": {
            "from": "Water Sensor",
            "to": "Updated Water Sensor"
          },
          "Status": {
            "from": "inactive",
            "to": "active"
          },
          "Location": {
            "from": "Mumbai",
            "to": "Delhi"
          }
        },
        "updatedBy": "admin"
      }
    ]
  }
}
```

### DELETE /devices
**Description:** Delete device metadata or related records (query parameters required)  
**⚠️ Note:** Requires Terraform route `DELETE /devices` to be configured  

**Query Parameters:**
- `DeviceId` (required): Device identifier
- `EntityType` (required): Type of record to delete (DEVICE, CONFIG, REPAIR, INSTALL, RUNTIME, SIM_ASSOC)
- `soft` (optional): Set to "true" for soft delete (marks as deleted instead of removing)
- `cascade` (optional): Set to "true" to delete device and all related records
- `performedBy` (optional): User performing the delete operation (used with soft delete)

**Features:**
- **Validation**: Prevents deletion if device has active SIM or installation links (unless soft or cascade)
- **Soft Delete**: Marks device as deleted without removing data (preserves history)
- **Cascade Delete**: Deletes device and all related records (CONFIG, REPAIR, RUNTIME, INSTALL, SIM_ASSOC)
- **Enhanced Error Handling**: Provides detailed feedback on deletion conflicts

**Request (Standard Delete):**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?DeviceId=DEV099&EntityType=DEVICE"
```

**Response (200 - Success):**
```json
{
  "deleted": {
    "PK": "DEVICE#DEV099",
    "SK": "META",
    "EntityType": "DEVICE"
  }
}
```

**Response (409 - Conflict with linked resources):**
```json
{
  "error": {
    "message": "Cannot delete device with active associations",
    "linkedSIMs": 1,
    "linkedInstallations": 2,
    "suggestion": "Use ?cascade=true to delete all associations, or ?soft=true to mark as deleted"
  }
}
```

**Request (Soft Delete):**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?DeviceId=DEV099&EntityType=DEVICE&soft=true&performedBy=admin@vinkane.com"
```

**Response (200 - Soft Delete Success):**
```json
{
  "deleted": {
    "PK": "DEVICE#DEV099",
    "SK": "META",
    "EntityType": "DEVICE",
    "softDelete": true,
    "deletedAt": "2026-02-04T10:30:00Z",
    "deletedBy": "admin@vinkane.com"
  }
}
```

**Request (Cascade Delete):**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?DeviceId=DEV099&EntityType=DEVICE&cascade=true"
```

**Response (200 - Cascade Delete Success):**
```json
{
  "deleted": {
    "DeviceId": "DEV099",
    "cascadeDelete": true,
    "totalRecordsDeleted": 8,
    "deletedItems": [
      {"PK": "DEVICE#DEV099", "SK": "META", "EntityType": "DEVICE"},
      {"PK": "DEVICE#DEV099", "SK": "CONFIG#V1.0#2026-01-15T10:30:00Z", "EntityType": "CONFIG"},
      {"PK": "DEVICE#DEV099", "SK": "REPAIR#REP001#2026-01-20T08:00:00Z", "EntityType": "REPAIR"},
      {"PK": "DEVICE#DEV099", "SK": "INSTALL#INS001#2026-01-10T12:00:00Z", "EntityType": "INSTALL"},
      {"PK": "DEVICE#DEV099", "SK": "SIM_ASSOC#SIM12345", "EntityType": "SIM_ASSOC"}
    ]
  }
}
```

**Response (404) - If Terraform route not configured:**
```json
{
  "message": "Not Found"
}
```

### DELETE /devices - Config Entity
**Description:** Delete specific device configuration  
**Required Parameters:** DeviceId, EntityType, ConfigVersion, CreatedDate  
**Request:**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?DeviceId=DEV099&EntityType=CONFIG&ConfigVersion=V1.0&CreatedDate=2026-01-15T10:30:00Z"
```

**Response (200):**
```json
{
  "deleted": {
    "PK": "DEVICE#DEV099",
    "SK": "CONFIG#V1.0#2026-01-15T10:30:00Z",
    "EntityType": "CONFIG"
  }
}
```

### POST /devices/{deviceId}/repairs
**Description:** Create a repair record for a device  
**⚠️ Note:** Requires Terraform route `POST /devices/{deviceId}/repairs` to be configured  
**Request:**
```bash
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV009/repairs" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Replace water pump motor",
    "cost": 5000,
    "technician": "John Doe",
    "status": "completed",
    "createdBy": "admin@vinkane.com"
  }'
```

**Response (201):**
```json
{
  "message": "Repair record created successfully",
  "repair": {
    "PK": "DEVICE#DEV009",
    "SK": "REPAIR#REP2A3B4C5D#2026-01-28",
    "EntityType": "REPAIR",
    "DeviceId": "DEV009",
    "RepairId": "REP2A3B4C5D",
    "Description": "Replace water pump motor",
    "Cost": 5000,
    "Technician": "John Doe",
    "Status": "completed",
    "CreatedDate": "2026-01-28T04:32:15.123456Z",
    "UpdatedDate": "2026-01-28T04:32:15.123456Z",
    "CreatedBy": "admin@vinkane.com",
    "UpdatedBy": "admin@vinkane.com"
  }
}
```

**Optional Fields:**
- `repairId` - If not provided, auto-generated as `REP{UUID}`
- `description`, `cost`, `technician`, `status`, `createdBy`

### PUT /devices/{deviceId}/repairs/{repairId}
**Description:** Update an existing repair record  
**⚠️ Note:** Requires Terraform route `PUT /devices/{deviceId}/repairs/{repairId}` to be configured  
**Request:**
```bash
curl -X PUT "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV009/repairs/REP2A3B4C5D" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in-progress",
    "description": "Replace water pump motor - in progress",
    "cost": 5200,
    "technician": "Jane Smith",
    "updatedBy": "admin"
  }'
```

**Updatable Fields:**
- `description`, `cost`, `technician`, `status`, `updatedBy`

**Response (200):**
```json
{
  "message": "Repair record updated successfully",
  "repair": {
    "PK": "DEVICE#DEV009",
    "SK": "REPAIR#REP2A3B4C5D#2026-01-28",
    "EntityType": "REPAIR",
    "DeviceId": "DEV009",
    "RepairId": "REP2A3B4C5D",
    "Description": "Replace water pump motor - in progress",
    "Cost": 5200,
    "Technician": "Jane Smith",
    "Status": "in-progress",
    "CreatedDate": "2026-01-28T04:32:15.123456Z",
    "UpdatedDate": "2026-01-28T05:45:30.654321Z",
    "CreatedBy": "system",
    "UpdatedBy": "admin"
  }
}
```

### GET /devices/{deviceId}/sim
**Description:** Get linked SIM details for a device with optional decryption  
**Query Parameters:**
- `decrypt=true` - Returns plaintext SIM data

**Request:**
```bash
# Default - encrypted
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV003/sim"

# Decrypted - for UI
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV003/sim?decrypt=true"
```

**Response (200) - Encrypted (Default):**
```json
{
  "simId": "SIM001",
  "linkedDate": "2026-01-29T10:00:00Z",
  "linkStatus": "active",
  "simDetails": {
    "MobileNumber": {
      "encrypted_value": "QzE0NjA5Njk0MzYxOQ==",
      "key_version": "1",
      "encrypted_at": "2026-01-29T10:02:16.700045Z"
    },
    "Provider": {
      "encrypted_value": "QWlyZGVs",
      "key_version": "1",
      "encrypted_at": "2026-01-29T10:02:16.700045Z"
    }
  }
}
```

**Response (200) - Decrypted (?decrypt=true):**
```json
{
  "simId": "SIM001",
  "linkedDate": "2026-01-29T10:00:00Z",
  "linkStatus": "active",
  "simDetails": {
    "MobileNumber": "+919876543210",
    "Provider": "Airtel"
  }
}
```

### GET /devices/{deviceId}/repairs
**Description:** Get all repair records for a device  
**⚠️ Note:** Requires Terraform route `GET /devices/{deviceId}/repairs` to be configured  
**Request:**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV009/repairs"
```

**Response (200):**
```json
{
  "deviceId": "DEV009",
  "repairCount": 2,
  "repairs": [
    {
      "PK": "DEVICE#DEV009",
      "SK": "REPAIR#REP2A3B4C5D#2026-01-28",
      "EntityType": "REPAIR",
      "DeviceId": "DEV009",
      "RepairId": "REP2A3B4C5D",
      "Description": "Replace water pump motor",
      "Cost": 5000,
      "Technician": "John Doe",
      "Status": "completed",
      "CreatedDate": "2026-01-28T04:32:15.123456Z",
      "UpdatedDate": "2026-01-28T04:32:15.123456Z",
      "CreatedBy": "admin@vinkane.com",
      "UpdatedBy": "admin@vinkane.com"
    }
  ]
}
```

### DELETE /devices - Repair Entity
**Description:** Delete specific device repair record  
**Required Parameters:** DeviceId, EntityType, RepairId, CreatedDate  
**Request:**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?DeviceId=DEV099&EntityType=REPAIR&RepairId=REP001&CreatedDate=2026-01-15T10:30:00Z"
```

**Response (200):**
```json
{
  "deleted": {
    "PK": "DEVICE#DEV099",
    "SK": "REPAIR#REP001#2026-01-15",
    "EntityType": "REPAIR"
  }
}
```

### DELETE /devices - Install Entity
**Description:** Delete specific device installation record  
**Required Parameters:** DeviceId, EntityType, InstallId, CreatedDate  
**Request:**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?DeviceId=DEV099&EntityType=INSTALL&InstallId=INS001&CreatedDate=2026-01-14T08:00:00Z"
```

**Response (200):**
```json
{
  "deleted": {
    "PK": "DEVICE#DEV099",
    "SK": "INSTALL#INS001#2026-01-14",
    "EntityType": "INSTALL"
  }
}
```

### POST /devices/{deviceId}/sim/link
**Description:** Link a SIM card to a device (one-to-one relationship)  
**⚠️ Note:** Requires Terraform route `POST /devices/{deviceId}/sim/link` to be configured  
**Business Rules:**
- One SIM can only be linked to one device at a time
- Device cannot have multiple SIMs linked simultaneously
- SIM must be in "active" status and not already linked to another device

**Device Configuration Page - Safe API Flow:**

1. **Validate Inputs (before showing Link UI):**
   ```bash
   # Check device exists and is linkable
   GET /devices/{deviceId}
   
   # Check SIM exists, is active, and not already linked
   GET /simcards/{simId}  # Verify linkedDeviceId is null/absent
   ```

2. **Link Operation:**
   ```bash
   # Atomically links SIM to device
   POST /devices/{deviceId}/sim/link
   # This endpoint automatically:
   # - Validates device exists
   # - Validates SIM exists and is not linked to another device
   # - Writes SIM_ASSOC record (if used)
   # - Updates SIM record: linkedDeviceId = deviceId
   # - Records changeHistory/audit trail
   ```

3. **Post-Link Verification:**
   ```bash
   # Verify linkage successful
   GET /devices/{deviceId}  # Check LinkedSIM.simId matches
   GET /simcards/{simId}    # Confirm linkedDeviceId = deviceId
   ```

4. **UI Guidelines:**
   - Disable "Link" button while POST is in flight
   - On success, refresh device details automatically
   - If SIM already linked to another device, surface the specific deviceId and block the link (or offer guided unlink-from-other first)
   - Display error messages clearly if validation fails

**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV001/sim/link \
  -H "Content-Type: application/json" \
  -d '{
    "simId": "SIM001",
    "performedBy": "admin@vinkane.com"
  }'
```

**Response (200):**
```json
{
  "message": "SIM linked successfully",
  "deviceId": "DEV001",
  "simId": "SIM001",
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-01-16T14:30:00Z"
}
```

**Response (400) - SIM already linked:**
```json
{
  "error": "SIM card SIM001 is already linked to device DEV005"
}
```

**Response (400) - Device already has SIM:**
```json
{
  "error": "Device DEV001 already has a linked SIM: SIM003. Please unlink first."
}
```

**Response (400) - SIM not active:**
```json
{
  "error": "SIM card SIM001 is not active (status: inactive)"
}
```

**Response (404) - SIM not found:**
```json
{
  "error": "SIM card SIM001 not found"
}
```

**History Tracking:** Creates entry in SIM card's `changeHistory`:
```json
{
  "timestamp": "2026-01-16T14:30:00Z",
  "action": "linked",
  "deviceId": "DEV001",
  "performedBy": "admin@vinkane.com",
  "ipAddress": "203.0.113.42"
}
```

### POST /devices/{deviceId}/sim/unlink
**Description:** Unlink the currently linked SIM card from a device  
**⚠️ Note:** Requires Terraform route `POST /devices/{deviceId}/sim/unlink` to be configured  

**Unlink Flow (when needed):**
1. Call `POST /devices/{deviceId}/sim/unlink`
2. Verify with `GET /devices/{deviceId}` to confirm LinkedSIM cleared
3. Optionally verify with `GET /simcards/{simId}` to confirm linkedDeviceId removed

**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV001/sim/unlink \
  -H "Content-Type: application/json" \
  -d '{
    "performedBy": "admin@vinkane.com"
  }'
```

**Response (200):**
```json
{
  "message": "SIM unlinked successfully",
  "deviceId": "DEV001",
  "simId": "SIM001",
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-01-16T15:00:00Z"
}
```

**Response (404) - No SIM linked:**
```json
{
  "error": "No SIM card linked to device DEV001"
}
```

**History Tracking:** Creates entry in SIM card's `changeHistory`:
```json
{
  "timestamp": "2026-01-16T15:00:00Z",
  "action": "unlinked",
  "deviceId": "DEV001",
  "performedBy": "admin@vinkane.com",
  "ipAddress": "203.0.113.42"
}
```

---

## 4. INSTALL-DEVICE LINKING API

### POST /installs/{installId}/devices/link
**Description:** Link one or more devices to an installation  
**⚠️ Note:** Requires Terraform route `POST /installs/{installId}/devices/link` to be configured  
**Features:**
- Bidirectional associations (INSTALL → DEVICE and DEVICE → INSTALL)
- Automatic history tracking
- Batch linking support
- Duplicate prevention
- Atomic transactions

**Request (Single Device):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/devices/link \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "DEV001",
    "performedBy": "admin@vinkane.com",
    "reason": "Initial installation setup"
  }'
```

**Request (Multiple Devices):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/devices/link \
  -H "Content-Type: application/json" \
  -d '{
    "deviceIds": ["DEV001", "DEV002", "DEV003"],
    "performedBy": "admin@vinkane.com",
    "reason": "Bulk device installation"
  }'
```

**Response (200 - Success):**
```json
{
  "installId": "INS001",
  "linked": [
    {"deviceId": "DEV001", "status": "linked"},
    {"deviceId": "DEV002", "status": "linked"}
  ],
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-01-17T04:00:00Z"
}
```

**Response (200 - Partial Success):**
```json
{
  "installId": "INS001",
  "linked": [
    {"deviceId": "DEV001", "status": "linked"}
  ],
  "errors": [
    {"deviceId": "DEV002", "error": "Device already linked to install INS001"},
    {"deviceId": "DEV999", "error": "Device DEV999 not found"}
  ],
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-01-17T04:00:00Z"
}
```

**Response (404) - Install not found:**
```json
{
  "error": "Install INS001 not found"
}
```

**Database Records Created:**
```json
// Association: INSTALL → DEVICE
{
  "PK": "INSTALL#INS001",
  "SK": "DEVICE_ASSOC#DEV001",
  "EntityType": "INSTALL_DEVICE_ASSOC",
  "InstallId": "INS001",
  "DeviceId": "DEV001",
  "Status": "active",
  "LinkedDate": "2026-01-17T04:00:00Z",
  "LinkedBy": "admin@vinkane.com"
}

// Reverse Association: DEVICE → INSTALL
{
  "PK": "DEVICE#DEV001",
  "SK": "INSTALL_ASSOC#INS001",
  "EntityType": "DEVICE_INSTALL_ASSOC",
  "DeviceId": "DEV001",
  "InstallId": "INS001",
  "Status": "active",
  "LinkedDate": "2026-01-17T04:00:00Z",
  "LinkedBy": "admin@vinkane.com"
}

// History Record
{
  "PK": "INSTALL#INS001",
  "SK": "DEVICE_HISTORY#2026-01-17T04:00:00Z#DEV001",
  "EntityType": "INSTALL_DEVICE_HISTORY",
  "InstallId": "INS001",
  "DeviceId": "DEV001",
  "Action": "LINKED",
  "PerformedBy": "admin@vinkane.com",
  "PerformedAt": "2026-01-17T04:00:00Z",
  "Reason": "Initial installation setup",
  "IPAddress": "203.0.113.42"
}
```

### POST /installs/{installId}/devices/unlink
**Description:** Unlink one or more devices from an installation  
**⚠️ Note:** Requires Terraform route `POST /installs/{installId}/devices/unlink` to be configured  

**Request (Single Device):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/devices/unlink \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "DEV001",
    "performedBy": "admin@vinkane.com",
    "reason": "Device replaced"
  }'
```

**Request (Multiple Devices):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/devices/unlink \
  -H "Content-Type: application/json" \
  -d '{
    "deviceIds": ["DEV001", "DEV002"],
    "performedBy": "admin@vinkane.com",
    "reason": "Maintenance complete"
  }'
```

**Response (200 - Success):**
```json
{
  "installId": "INS001",
  "unlinked": [
    {"deviceId": "DEV001", "status": "unlinked"},
    {"deviceId": "DEV002", "status": "unlinked"}
  ],
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-01-17T04:05:00Z"
}
```

**Response (200 - Partial Success):**
```json
{
  "installId": "INS001",
  "unlinked": [
    {"deviceId": "DEV001", "status": "unlinked"}
  ],
  "errors": [
    {"deviceId": "DEV002", "error": "Device DEV002 is not linked to install INS001"}
  ],
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-01-17T04:05:00Z"
}
```

### GET /installs/{installId}/devices
**Description:** List all devices linked to an installation  
**⚠️ Note:** Requires Terraform route `GET /installs/{installId}/devices` to be configured  

**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/devices
```

**Response (200):**
```json
{
  "installId": "INS001",
  "deviceCount": 2,
  "devices": [
    {
      "PK": "DEVICE#DEV001",
      "SK": "META",
      "DeviceId": "DEV001",
      "DeviceName": "Water Motor Unit",
      "DeviceType": "IoT Sensor",
      "SerialNumber": "SN123456789",
      "Status": "Active",
      "Location": "Site A",
      "linkedDate": "2026-01-17T04:00:00Z",
      "linkedBy": "admin@vinkane.com",
      "linkStatus": "active"
    },
    {
      "PK": "DEVICE#DEV002",
      "SK": "META",
      "DeviceId": "DEV002",
      "DeviceName": "Pressure Sensor",
      "DeviceType": "IoT Sensor",
      "SerialNumber": "SN987654321",
      "Status": "Active",
      "Location": "Site A",
      "linkedDate": "2026-01-17T04:00:00Z",
      "linkedBy": "admin@vinkane.com",
      "linkStatus": "active"
    }
  ]
}
```

**Response (404) - Install not found:**
```json
{
  "error": "Install INS001 not found"
}
```

### GET /devices/{deviceId}/install
**Description:** Get installation information for a device  
**⚠️ Note:** Requires Terraform route `GET /devices/{deviceId}/install` to be configured  

**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV001/install
```

**Response (200):**
```json
{
  "PK": "INSTALL#INS001",
  "SK": "META",
  "InstallId": "INS001",
  "DeviceId": "DEV001",
  "Location": {
    "address": "123 Main St",
    "city": "Hyderabad",
    "state": "Telangana",
    "coordinates": {"lat": 17.385044, "lon": 78.486671}
  },
  "Installer": "Tech Team Alpha",
  "Notes": "Standard installation",
  "Status": "active",
  "Warranty": "2 years",
  "linkedDate": "2026-01-17T04:00:00Z",
  "linkedBy": "admin@vinkane.com",
  "linkStatus": "active"
}
```

**Response (404) - Device not linked:**
```json
{
  "error": "Device DEV001 is not linked to any installation"
}
```

### GET /installs/{installId}/history
**Description:** Get complete link/unlink history for an installation  
**⚠️ Note:** Requires Terraform route `GET /installs/{installId}/history` to be configured  

**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/history
```

**Response (200):**
```json
{
  "installId": "INS001",
  "historyCount": 4,
  "history": [
    {
      "PK": "INSTALL#INS001",
      "SK": "DEVICE_HISTORY#2026-01-17T04:05:00Z#DEV002",
      "EntityType": "INSTALL_DEVICE_HISTORY",
      "InstallId": "INS001",
      "DeviceId": "DEV002",
      "Action": "UNLINKED",
      "PerformedBy": "admin@vinkane.com",
      "PerformedAt": "2026-01-17T04:05:00Z",
      "Reason": "Device replaced",
      "IPAddress": "203.0.113.42"
    },
    {
      "PK": "INSTALL#INS001",
      "SK": "DEVICE_HISTORY#2026-01-17T04:00:00Z#DEV002",
      "EntityType": "INSTALL_DEVICE_HISTORY",
      "InstallId": "INS001",
      "DeviceId": "DEV002",
      "Action": "LINKED",
      "PerformedBy": "admin@vinkane.com",
      "PerformedAt": "2026-01-17T04:00:00Z",
      "Reason": "Initial installation setup",
      "IPAddress": "203.0.113.42"
    },
    {
      "PK": "INSTALL#INS001",
      "SK": "DEVICE_HISTORY#2026-01-17T04:00:00Z#DEV001",
      "EntityType": "INSTALL_DEVICE_HISTORY",
      "InstallId": "INS001",
      "DeviceId": "DEV001",
      "Action": "LINKED",
      "PerformedBy": "admin@vinkane.com",
      "PerformedAt": "2026-01-17T04:00:00Z",
      "Reason": "Initial installation setup",
      "IPAddress": "203.0.113.42"
    }
  ]
}
```

**Response (404) - Install not found:**
```json
{
  "error": "Install INS001 not found"
}
```

---

## 5. INSTALL-CONTACT LINKING API

### POST /installs/{installId}/contacts/link
**Description:** Link one or more customer contacts to an installation  
**⚠️ Note:** Requires Terraform route `POST /installs/{installId}/contacts/link` to be configured  
**Features:**
- Links existing customer contacts to installations
- Validates contacts belong to installation's customer
- Batch linking support (up to 50 contacts)
- Duplicate prevention
- Atomic transactions

**Prerequisites:**
- Installation must have a `CustomerId`
- Contacts must exist in the customer's contact list

**Request (Single Contact):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/contacts/link \
  -H "Content-Type: application/json" \
  -d '{
    "contactId": "CONTx1y2z3w4",
    "performedBy": "admin@vinkane.com",
    "reason": "Site manager assigned"
  }'
```

**Request (Multiple Contacts):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/contacts/link \
  -H "Content-Type: application/json" \
  -d '{
    "contactIds": ["CONTx1y2z3w4", "CONT9876abcd", "CONTabc123xy"],
    "performedBy": "admin@vinkane.com",
    "reason": "Installation team contacts"
  }'
```

**Response (200 - Success):**
```json
{
  "installId": "INS001",
  "customerId": "CUSTa1b2c3d4",
  "linked": [
    {"contactId": "CONTx1y2z3w4", "status": "linked"},
    {"contactId": "CONT9876abcd", "status": "linked"}
  ],
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-02-01T10:30:00Z"
}
```

**Response (200 - Partial Success):**
```json
{
  "installId": "INS001",
  "customerId": "CUSTa1b2c3d4",
  "linked": [
    {"contactId": "CONTx1y2z3w4", "status": "linked"}
  ],
  "errors": [
    {"contactId": "CONT9876abcd", "error": "Contact CONT9876abcd is already linked to install INS001"},
    {"contactId": "CONT_INVALID", "error": "Contact not found or doesn't belong to customer CUSTa1b2c3d4"}
  ],
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-02-01T10:30:00Z"
}
```

**Response (400) - Installation without CustomerId:**
```json
{
  "error": "Installation INS001 does not have a CustomerId. Cannot link contacts."
}
```

**Response (404) - Install not found:**
```json
{
  "error": "Install INS001 not found"
}
```

**Database Records Created:**
```json
// Association: INSTALL → CONTACT
{
  "PK": "INSTALL#INS001",
  "SK": "CONTACT_ASSOC#CONTx1y2z3w4",
  "EntityType": "INSTALL_CONTACT_ASSOC",
  "InstallId": "INS001",
  "ContactId": "CONTx1y2z3w4",
  "CustomerId": "CUSTa1b2c3d4",
  "Status": "active",
  "LinkedDate": "2026-02-01T10:30:00Z",
  "LinkedBy": "admin@vinkane.com",
  "CreatedDate": "2026-02-01T10:30:00Z",
  "UpdatedDate": "2026-02-01T10:30:00Z"
}
```

### POST /installs/{installId}/contacts/unlink
**Description:** Unlink one or more contacts from an installation  
**⚠️ Note:** Requires Terraform route `POST /installs/{installId}/contacts/unlink` to be configured  

**Request (Single Contact):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/contacts/unlink \
  -H "Content-Type: application/json" \
  -d '{
    "contactId": "CONTx1y2z3w4",
    "performedBy": "admin@vinkane.com",
    "reason": "Contact reassigned"
  }'
```

**Request (Multiple Contacts):**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001/contacts/unlink \
  -H "Content-Type: application/json" \
  -d '{
    "contactIds": ["CONTx1y2z3w4", "CONT9876abcd"],
    "performedBy": "admin@vinkane.com",
    "reason": "Installation handover complete"
  }'
```

**Response (200 - Success):**
```json
{
  "installId": "INS001",
  "unlinked": [
    {"contactId": "CONTx1y2z3w4", "status": "unlinked"},
    {"contactId": "CONT9876abcd", "status": "unlinked"}
  ],
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-02-01T11:00:00Z"
}
```

**Response (200 - Partial Success):**
```json
{
  "installId": "INS001",
  "unlinked": [
    {"contactId": "CONTx1y2z3w4", "status": "unlinked"}
  ],
  "errors": [
    {"contactId": "CONT9876abcd", "error": "Contact CONT9876abcd is not linked to install INS001"}
  ],
  "performedBy": "admin@vinkane.com",
  "timestamp": "2026-02-01T11:00:00Z"
}
```

### GET /installs/{installId}/contacts
**Description:** Get all contacts linked to a specific installation  
**⚠️ Note:** Requires Terraform route `GET /installs/{installId}/contacts` to be configured  
**Features:**
- Batch fetches contact details from customer table
- Returns full contact information with association metadata
- Validates installation exists and has CustomerId

**Request:**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/ebc4c2b3-f9cb-471e-9d69-bd93061ce64c/contacts"
```

**Response (200):**
```json
{
  "installId": "ebc4c2b3-f9cb-471e-9d69-bd93061ce64c",
  "contactCount": 2,
  "contacts": [
    {
      "contactId": "CONT092F151B",
      "customerId": "CUSTB8F7213D",
      "firstName": "Ramesh",
      "lastName": "Kumar",
      "displayName": "Ramesh Kumar",
      "email": {
        "encrypted_value": "cmFtZXNoa3VtYXJAdmlua2FuZS5jb20=",
        "key_version": "1",
        "encrypted_at": "2026-02-03T07:59:25.164613Z"
      },
      "mobileNumber": "890945409",
      "countryCode": "+91",
      "contactType": "primary",
      "isActive": true,
      "linkedDate": "2026-02-03T09:43:07.412648Z",
      "linkedBy": "system",
      "linkStatus": "active",
      "createdAt": "2026-02-03T07:59:25.164443Z",
      "updatedAt": "2026-02-03T07:59:25.164443Z",
      "createdBy": "Current User",
      "updatedBy": "Current User"
    },
    {
      "contactId": "C123",
      "customerId": "CUSTB8F7213D",
      "firstName": "Nag",
      "lastName": "Indra",
      "displayName": "Nag Indra",
      "email": {
        "encrypted_value": "bmFnZW5kcmFAZXhhbXBsZS5jb20=",
        "key_version": "1",
        "encrypted_at": "2026-02-03T07:59:25.087414Z"
      },
      "mobileNumber": "03453434433",
      "countryCode": "+91",
      "contactType": "primary",
      "isActive": true,
      "userId": "USER001",
      "linkedDate": "2026-02-03T16:47:38.888160Z",
      "linkedBy": "test@example.com",
      "linkStatus": "active",
      "createdAt": "2026-01-19T15:08:49.268Z",
      "updatedAt": "2026-02-03T07:59:25.087193Z",
      "createdBy": "Current User",
      "updatedBy": "admin@vinkane.com"
    }
  ]
}
```

**Response (404) - Install not found:**
```json
{
  "error": "Install ebc4c2b3-f9cb-471e-9d69-bd93061ce64c not found"
}
```

**Response (400) - Installation without CustomerId:**
```json
{
  "error": "Installation does not have a CustomerId. Cannot retrieve contacts."
}
```

---

### GET /installs/{installId}?includeContacts=true
**Description:** Retrieve installation details with linked contacts included inline  
**Query Parameters:**
- `includeContacts=true` - Include linked contact details (default: false)
- `includeDevices=true` - Include linked device details (default: false)
- `includeCustomer=true` - Include customer details (default: true)

**Request:**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INS001?includeContacts=true"
```

**Response (200):**
```json
{
  "installationId": "INS001",
  "CustomerId": "CUSTa1b2c3d4",
  "StateId": "TS",
  "DistrictId": "HYD",
  "MandalId": "SRNAGAR",
  "VillageId": "VILLAGE001",
  "HabitationId": "HAB001",
  "PrimaryDevice": "water",
  "Status": "active",
  "InstallationDate": "2026-01-15T00:00:00.000Z",
  "CreatedDate": "2026-01-15T08:00:00Z",
  "UpdatedDate": "2026-02-01T10:30:00Z",
  "linkedContacts": [
    {
      "contactId": "CONTx1y2z3w4",
      "firstName": "John",
      "lastName": "Doe",
      "email": "john.doe@example.com",
      "mobileNumber": "9876543210",
      "designation": "Site Manager",
      "customerId": "CUSTa1b2c3d4",
      "linkedDate": "2026-02-01T10:30:00Z",
      "linkedBy": "admin@vinkane.com",
      "linkStatus": "active"
    },
    {
      "contactId": "CONT9876abcd",
      "firstName": "Jane",
      "lastName": "Smith",
      "email": "jane.smith@example.com",
      "mobileNumber": "9876543211",
      "designation": "Technical Lead",
      "customerId": "CUSTa1b2c3d4",
      "linkedDate": "2026-02-01T10:30:00Z",
      "linkedBy": "admin@vinkane.com",
      "linkStatus": "active"
    }
  ],
  "linkedContactCount": 2,
  "customer": {
    "customerId": "CUSTa1b2c3d4",
    "name": "Acme Corporation",
    "companyName": "Acme Corp",
    "email": "info@acme.com",
    "phone": "9876543210"
  },
  "StateName": "Telangana",
  "DistrictName": "Hyderabad",
  "MandalName": "SR Nagar",
  "VillageName": "Village 001",
  "HabitationName": "Habitation 001"
}
```

**Response (200 - No Contacts Linked):**
```json
{
  "installationId": "INS001",
  "CustomerId": "CUSTa1b2c3d4",
  "StateId": "TS",
  "DistrictId": "HYD",
  "linkedContacts": [],
  "linkedContactCount": 0
}
```

---

## 6. DEVICE-SIM LINKING API

### GET /devices/{deviceId}/sim
**Description:** Get the currently linked SIM card for a device  
**⚠️ Note:** Requires Terraform route `GET /devices/{deviceId}/sim` to be configured  
**Note:** This endpoint does NOT require EntityType query parameter  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices/DEV001/sim
```

**Response (200):**
```json
{
  "simId": "SIM001",
  "linkedDate": "2026-01-16T14:30:00Z",
  "linkStatus": "linked",
  "simDetails": {
    "PK": "SIMCARD#SIM001",
    "SK": "ENTITY#SIMCARD",
    "entityType": "SIMCARD",
    "simCardNumber": "8991234567890123456",
    "mobileNumber": "+919876543210",
    "provider": "Airtel",
    "planType": "Unlimited",
    "simType": "4G",
    "monthlyDataLimit": 10240,
    "status": "active",
    "activationDate": "2024-01-15T10:00:00Z",
    "currentDataUsage": 2048,
    "purchaseCost": 200,
    "monthlyCharges": 499,
    "isRoamingEnabled": false,
    "linkedDeviceId": "DEV001",
    "changeHistory": [
      {
        "timestamp": "2026-01-16T14:30:00Z",
        "action": "linked",
        "deviceId": "DEV001",
        "performedBy": "admin@vinkane.com",
        "ipAddress": "203.0.113.42"
      }
    ],
    "createdAt": "2024-01-15T10:00:00Z",
    "updatedAt": "2026-01-16T14:30:00Z"
  }
}
```

**Response (404) - No SIM linked:**
```json
{
  "error": "No SIM card linked to device DEV001"
}
```

**Response (404) - Device not found:**
```json
{
  "error": "Device DEV001 not found"
}
```

---

## 2. CUSTOMERS API

**Important Changes:**
- **Auto-generated IDs**: `customerId` (CUST{UUID8}), `contactId` (CONT{UUID8}), `addressId` (ADDR{UUID8}) are now auto-generated
- **Timestamp Fields**: All entities include `createdAt`, `createdBy`, `updatedAt`, `updatedBy`
- **Soft Delete**: All DELETE operations support `?soft=true` query parameter to mark as inactive instead of permanent deletion
- **No Manual PK/SK**: Frontend no longer needs to construct PK/SK - they're generated automatically

### GET /customers
**Description:** List all customers  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers
```

**Response (200):**
```json
[
  {
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#CUSTOMER",
    "entityType": "customer",
    "customerId": "CUST2FB2591F",
    "customerNumber": "CN-2026-001",
    "name": "ABC Corporation",
    "companyName": "ABC Corp Pvt Ltd",
    "email": "contact@abccorp.com",
    "phone": "9876543210",
    "countryCode": "+91",
    "gstin": "29ABCDE1234F1Z5",
    "pan": "AAAPL1234C",
    "isActive": true,
    "createdAt": "2026-01-21T08:30:00Z",
    "createdBy": "admin@example.com",
    "updatedAt": "2026-01-21T08:30:00Z",
    "updatedBy": "admin@example.com"
  }
]
```

### GET /customers/{customerId}
**Description:** Get customer with nested contacts and addresses  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST2FB2591F",
  "SK": "ENTITY#CUSTOMER",
  "entityType": "customer",
  "customerId": "CUST2FB2591F",
  "customerNumber": "CN-2026-001",
  "name": "ABC Corporation",
  "companyName": "ABC Corp Pvt Ltd",
  "email": "contact@abccorp.com",
  "phone": "9876543210",
  "countryCode": "+91",
  "gstin": "29ABCDE1234F1Z5",
  "isActive": true,
  "createdAt": "2026-01-21T08:30:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T10:15:00Z",
  "updatedBy": "admin@example.com",
  "contacts": [
    {
      "PK": "CUSTOMER#CUST2FB2591F",
      "SK": "ENTITY#CONTACT#CONT4A3B2C1D",
      "entityType": "contact",
      "contactId": "CONT4A3B2C1D",
      "firstName": "John",
      "lastName": "Doe",
      "displayName": "John Doe",
      "email": "john@abccorp.com",
      "mobileNumber": "9876543210",
      "countryCode": "+91",
      "contactType": "primary",
      "createAsUser": false,
      "userId": "USR001",
      "isActive": true,
      "createdAt": "2026-01-21T09:00:00Z",
      "createdBy": "admin@example.com",
      "updatedAt": "2026-01-21T09:00:00Z",
      "updatedBy": "admin@example.com"
    }
  ],
  "addresses": [
    {
      "PK": "CUSTOMER#CUST2FB2591F",
      "SK": "ENTITY#ADDRESS#ADDR8E7F6G5H",
      "entityType": "address",
      "addressId": "ADDR8E7F6G5H",
      "addressType": "billing",
      "addressLine1": "123 Business Street",
      "addressLine2": "Suite 500",
      "city": "Mumbai",
      "state": "Maharashtra",
      "pincode": "400001",
      "country": "India",
      "isPrimary": true,
      "isActive": true,
      "createdAt": "2026-01-21T09:15:00Z",
      "createdBy": "admin@example.com",
      "updatedAt": "2026-01-21T09:15:00Z",
      "updatedBy": "admin@example.com"
    }
  ]
}
```

### POST /customers
**Description:** Create new customer with auto-generated ID  
**Important:** 
- `customerId` is auto-generated (CUST{UUID8})
- `customerNumber` is optional and user-provided for business reference
- No need to provide PK/SK - they are constructed automatically
- Duplicate prevention enabled - returns 409 if customer already exists

**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Company Ltd",
    "companyName": "New Company Private Limited",
    "customerNumber": "CN-2026-002",
    "email": "info@newcompany.com",
    "phone": "9123456789",
    "countryCode": "+91",
    "gstin": "29XXXXX1234X1Z5",
    "pan": "AAAAA9999A",
    "isActive": true,
    "createdBy": "admin@example.com"
  }'
```

**Response (201):**
```json
{
  "PK": "CUSTOMER#CUST9A8B7C6D",
  "SK": "ENTITY#CUSTOMER",
  "entityType": "customer",
  "customerId": "CUST9A8B7C6D",
  "customerNumber": "CN-2026-002",
  "name": "New Company Ltd",
  "companyName": "New Company Private Limited",
  "email": "info@newcompany.com",
  "phone": "9123456789",
  "countryCode": "+91",
  "gstin": "29XXXXX1234X1Z5",
  "pan": "AAAAA9999A",
  "isActive": true,
  "createdAt": "2026-01-21T11:00:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T11:00:00Z",
  "updatedBy": "admin@example.com"
}
```

**Response (409 - Duplicate):**
```json
{
  "error": "Customer CUST9A8B7C6D already exists"
}
```

### GET /customers/{customerId}/contacts
**Description:** List all contacts for a customer  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/contacts
```

**Response (200):**
```json
[
  {
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#CONTACT#CONT4A3B2C1D",
    "entityType": "contact",
    "contactId": "CONT4A3B2C1D",
    "firstName": "John",
    "lastName": "Doe",
    "displayName": "John Doe",
    "email": "john@abccorp.com",
    "mobileNumber": "9876543210",
    "countryCode": "+91",
    "contactType": "primary",
    "createAsUser": false,
    "userId": "USR001",
    "isActive": true,
    "createdAt": "2026-01-21T09:00:00Z",
    "createdBy": "admin@example.com",
    "updatedAt": "2026-01-21T09:00:00Z",
    "updatedBy": "admin@example.com"
  },
  {
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#CONTACT#CONT5D6E7F8G",
    "entityType": "contact",
    "contactId": "CONT5D6E7F8G",
    "firstName": "Jane",
    "lastName": "Smith",
    "displayName": "Jane Smith",
    "email": "jane@abccorp.com",
    "mobileNumber": "9988776655",
    "countryCode": "+91",
    "contactType": "secondary",
    "createAsUser": false,
    "userId": "USR002",
    "isActive": true,
    "createdAt": "2026-01-21T09:30:00Z",
    "createdBy": "admin@example.com",
    "updatedAt": "2026-01-21T09:30:00Z",
    "updatedBy": "admin@example.com"
  }
]
```

### GET /customers/{customerId}/contacts/{contactId}
**Description:** Get specific contact by ID  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/contacts/CONT4A3B2C1D
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST2FB2591F",
  "SK": "ENTITY#CONTACT#CONT4A3B2C1D",
  "entityType": "contact",
  "contactId": "CONT4A3B2C1D",
  "firstName": "John",
  "lastName": "Doe",
  "displayName": "John Doe",
  "email": "john@abccorp.com",
  "mobileNumber": "9876543210",
  "countryCode": "+91",
  "contactType": "primary",
  "createAsUser": false,
  "userId": "USR001",
  "isActive": true,
  "createdAt": "2026-01-21T09:00:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T10:30:00Z",
  "updatedBy": "manager@example.com"
}
```

### POST /customers/{customerId}/contacts
**Description:** Add contact to customer with auto-generated ID  
**Important:**
- `contactId` is auto-generated (CONT{UUID8})
- No need to provide PK/SK - they are constructed automatically
- `createdAt`, `updatedAt`, and `updatedBy` are set automatically

**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "entityType": "contact",
    "firstName": "Jane",
    "lastName": "Smith",
    "displayName": "Jane Smith",
    "email": "jane.smith@example.com",
    "mobileNumber": "9988776655",
    "countryCode": "+91",
    "contactType": "secondary",
    "createAsUser": false,
    "userId": "USR003",
    "isActive": true,
    "createdBy": "admin@example.com"
  }'
```

**Response (201):**
```json
{
  "PK": "CUSTOMER#CUST2FB2591F",
  "SK": "ENTITY#CONTACT#CONT9H8I7J6K",
  "entityType": "contact",
  "contactId": "CONT9H8I7J6K",
  "firstName": "Jane",
  "lastName": "Smith",
  "displayName": "Jane Smith",
  "email": "jane.smith@example.com",
  "mobileNumber": "9988776655",
  "countryCode": "+91",
  "contactType": "secondary",
  "createAsUser": false,
  "userId": "USR003",
  "isActive": true,
  "createdAt": "2026-01-21T11:30:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T11:30:00Z",
  "updatedBy": "admin@example.com"
}
```

**Response (409 - Duplicate):**
```json
{
  "error": "Contact CONT9H8I7J6K already exists"
}
```

### PUT /customers/{customerId}/contacts/{contactId}
**Description:** Update contact  
**Important:** `updatedAt` and `updatedBy` are set automatically

**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/contacts/CONT9H8I7J6K \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#CONTACT#CONT9H8I7J6K",
    "entityType": "contact",
    "contactId": "CONT9H8I7J6K",
    "firstName": "Jane",
    "lastName": "Smith Updated",
    "displayName": "Jane Smith",
    "email": "jane.smith@example.com",
    "mobileNumber": "9988776666",
    "countryCode": "+91",
    "contactType": "primary",
    "createAsUser": false,
    "userId": "USR003",
    "isActive": true,
    "createdAt": "2026-01-21T11:30:00Z",
    "createdBy": "admin@example.com"
  }'
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST2FB2591F",
  "SK": "ENTITY#CONTACT#CONT9H8I7J6K",
  "entityType": "contact",
  "contactId": "CONT9H8I7J6K",
  "firstName": "Jane",
  "lastName": "Smith Updated",
  "mobileNumber": "9988776666",
  "contactType": "primary",
  "isActive": true,
  "createdAt": "2026-01-21T11:30:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T12:00:00Z",
  "updatedBy": "admin@example.com"
}
```

### DELETE /customers/{customerId}/contacts/{contactId}
**Description:** Delete contact (supports soft delete)  
**Query Parameters:**
- `soft` - Set to "true" for soft delete (marks as inactive), omit for hard delete
- `updatedBy` - User who performed the deletion (optional, for soft delete)

**Hard Delete Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/contacts/CONT9H8I7J6K
```

**Hard Delete Response (200):**
```json
{
  "message": "Contact deleted"
}
```

**Soft Delete Request:**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/contacts/CONT9H8I7J6K?soft=true&updatedBy=admin@example.com"
```

**Soft Delete Response (200):**
```json
{
  "message": "Contact soft deleted",
  "data": {
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#CONTACT#CONT9H8I7J6K",
    "contactId": "CONT9H8I7J6K",
    "firstName": "Jane",
    "lastName": "Smith Updated",
    "isActive": false,
    "updatedAt": "2026-01-21T13:00:00Z",
    "updatedBy": "admin@example.com"
  }
}
```

### GET /customers/{customerId}/addresses
**Description:** List all addresses for a customer  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/addresses
```

**Response (200):**
```json
[
  {
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#ADDRESS#ADDR8E7F6G5H",
    "entityType": "address",
    "addressId": "ADDR8E7F6G5H",
    "addressType": "billing",
    "addressLine1": "123 Business Street",
    "addressLine2": "Suite 500",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
    "country": "India",
    "isPrimary": true,
    "isActive": true,
    "createdAt": "2026-01-21T09:15:00Z",
    "createdBy": "admin@example.com",
    "updatedAt": "2026-01-21T09:15:00Z",
    "updatedBy": "admin@example.com"
  },
  {
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#ADDRESS#ADDR1L2M3N4O",
    "entityType": "address",
    "addressId": "ADDR1L2M3N4O",
    "addressType": "ship_to",
    "addressLine1": "456 Industrial Area",
    "addressLine2": "Near Highway",
    "city": "Pune",
    "state": "Maharashtra",
    "pincode": "411001",
    "country": "India",
    "isPrimary": false,
    "isActive": true,
    "createdAt": "2026-01-21T10:00:00Z",
    "createdBy": "admin@example.com",
    "updatedAt": "2026-01-21T10:00:00Z",
    "updatedBy": "admin@example.com"
  }
]
```

### GET /customers/{customerId}/addresses/{addressId}
**Description:** Get specific address by ID  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/addresses/ADDR1L2M3N4O
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST2FB2591F",
  "SK": "ENTITY#ADDRESS#ADDR1L2M3N4O",
  "entityType": "address",
  "addressId": "ADDR1L2M3N4O",
  "addressType": "ship_to",
  "addressLine1": "456 Industrial Area",
  "addressLine2": "Near Highway",
  "city": "Pune",
  "state": "Maharashtra",
  "pincode": "411001",
  "country": "India",
  "isPrimary": false,
  "isActive": true,
  "createdAt": "2026-01-21T10:00:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T11:45:00Z",
  "updatedBy": "manager@example.com"
}
```

### POST /customers/{customerId}/addresses
**Description:** Add address to customer with auto-generated ID  
**Important:**
- `addressId` is auto-generated (ADDR{UUID8})
- No need to provide PK/SK - they are constructed automatically
- `createdAt`, `updatedAt`, and `updatedBy` are set automatically

**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/addresses \
  -H "Content-Type: application/json" \
  -d '{
    "entityType": "address",
    "addressType": "billing",
    "addressLine1": "123 Business Park",
    "addressLine2": "Tower A, Floor 5",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
    "country": "India",
    "isPrimary": false,
    "isActive": true,
    "createdBy": "admin@example.com"
  }'
```

**Response (201):**
```json
{
  "PK": "CUSTOMER#CUST2FB2591F",
  "SK": "ENTITY#ADDRESS#ADDR5P6Q7R8S",
  "entityType": "address",
  "addressId": "ADDR5P6Q7R8S",
  "addressType": "billing",
  "addressLine1": "123 Business Park",
  "addressLine2": "Tower A, Floor 5",
  "city": "Mumbai",
  "state": "Maharashtra",
  "pincode": "400001",
  "country": "India",
  "isPrimary": false,
  "isActive": true,
  "createdAt": "2026-01-21T12:30:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T12:30:00Z",
  "updatedBy": "admin@example.com"
}
```

**Response (409 - Duplicate):**
```json
{
  "error": "Address ADDR5P6Q7R8S already exists"
}
```

### PUT /customers/{customerId}/addresses/{addressId}
**Description:** Update address  
**Important:** `updatedAt` and `updatedBy` are set automatically

**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/addresses/ADDR5P6Q7R8S \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#ADDRESS#ADDR5P6Q7R8S",
    "entityType": "address",
    "addressId": "ADDR5P6Q7R8S",
    "addressType": "billing",
    "addressLine1": "123 Updated Business Park",
    "addressLine2": "Tower B, Floor 10",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
    "country": "India",
    "isPrimary": true,
    "isActive": true,
    "createdAt": "2026-01-21T12:30:00Z",
    "createdBy": "admin@example.com"
  }'
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST2FB2591F",
  "SK": "ENTITY#ADDRESS#ADDR5P6Q7R8S",
  "entityType": "address",
  "addressId": "ADDR5P6Q7R8S",
  "addressLine1": "123 Updated Business Park",
  "addressLine2": "Tower B, Floor 10",
  "isPrimary": true,
  "isActive": true,
  "createdAt": "2026-01-21T12:30:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T13:15:00Z",
  "updatedBy": "admin@example.com"
}
```

### DELETE /customers/{customerId}/addresses/{addressId}
**Description:** Delete address (supports soft delete)  
**Query Parameters:**
- `soft` - Set to "true" for soft delete (marks as inactive), omit for hard delete
- `updatedBy` - User who performed the deletion (optional, for soft delete)

**Hard Delete Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/addresses/ADDR5P6Q7R8S
```

**Hard Delete Response (200):**
```json
{
  "message": "Address deleted"
}
```

**Soft Delete Request:**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST2FB2591F/addresses/ADDR5P6Q7R8S?soft=true&updatedBy=admin@example.com"
```

**Soft Delete Response (200):**
```json
{
  "message": "Address soft deleted",
  "data": {
    "PK": "CUSTOMER#CUST2FB2591F",
    "SK": "ENTITY#ADDRESS#ADDR5P6Q7R8S",
    "addressId": "ADDR5P6Q7R8S",
    "addressLine1": "123 Updated Business Park",
    "isActive": false,
    "updatedAt": "2026-01-21T14:00:00Z",
    "updatedBy": "admin@example.com"
  }
}
```

### PUT /customers/{customerId}
**Description:** Update customer  
**Important:** `updatedAt` and `updatedBy` are set automatically

**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST9A8B7C6D \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST9A8B7C6D",
    "SK": "ENTITY#CUSTOMER",
    "entityType": "customer",
    "customerId": "CUST9A8B7C6D",
    "customerNumber": "CN-2026-002",
    "name": "New Company Ltd",
    "companyName": "Updated Company Name Private Limited",
    "email": "info@newcompany.com",
    "phone": "9999999999",
    "countryCode": "+91",
    "gstin": "29XXXXX1234X1Z5",
    "pan": "AAAAA9999A",
    "isActive": true,
    "createdAt": "2026-01-21T11:00:00Z",
    "createdBy": "admin@example.com"
  }'
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST9A8B7C6D",
  "SK": "ENTITY#CUSTOMER",
  "entityType": "customer",
  "customerId": "CUST9A8B7C6D",
  "customerNumber": "CN-2026-002",
  "companyName": "Updated Company Name Private Limited",
  "phone": "9999999999",
  "isActive": true,
  "createdAt": "2026-01-21T11:00:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-01-21T14:30:00Z",
  "updatedBy": "admin@example.com"
}
```

### DELETE /customers/{customerId}
**Description:** Delete customer (cascade deletes/marks all contacts and addresses)  
**Query Parameters:**
- `soft` - Set to "true" for soft delete (marks customer and all related data as inactive), omit for hard delete
- `updatedBy` - User who performed the deletion (optional, for soft delete)

**Hard Delete Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST9A8B7C6D
```

**Hard Delete Response (200):**
```json
{
  "message": "Customer and all related data deleted"
}
```

**Soft Delete Request:**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST9A8B7C6D?soft=true&updatedBy=admin@example.com"
```

**Soft Delete Response (200):**
```json
{
  "message": "Customer and all related data soft deleted",
  "itemsUpdated": 5
}
```

**Note:** Soft delete marks the customer, all contacts, and all addresses as `isActive: false` and updates their `updatedAt`/`updatedBy` fields. Hard delete permanently removes all records from the database.

---

## 3. USERS API

**Audit Trail Fields:** All user records automatically track:
- `createdAt` / `updatedAt` - ISO 8601 timestamps with Z suffix
- `createdBy` / `updatedBy` - User identity (email) who created/last modified the record
- POST operations set all four fields; PUT operations update only updatedAt and updatedBy

### GET /users
**Description:** List all users  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/users
```

**Response (200):**
```json
[
  {
    "id": "user-1",
    "PK": "USER#user-1",
    "SK": "ENTITY#USER",
    "entityType": "USER",
    "keycloakId": "kc-uuid-1",
    "email": "admin@vinkane.com",
    "firstName": "Super",
    "lastName": "Admin",
    "name": "Super Admin",
    "role": "Administrator",
    "isActive": true,
    "emailVerified": true,
    "createdAt": "2024-01-10T10:00:00Z",
    "updatedAt": "2024-01-10T10:00:00Z",
    "createdBy": "system",
    "updatedBy": "system"
  }
]
```

### GET /users/{userId}
**Description:** Get single user by ID  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/users/user-1
```

**Response (200):**
```json
{
  "id": "user-1",
  "email": "admin@vinkane.com",
  "firstName": "Super",
  "lastName": "Admin",
  "name": "Super Admin",
  "role": "Administrator",
  "isActive": true
}
```

### POST /users
**Description:** Create new user  
**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/users \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-999",
    "PK": "USER#user-999",
    "SK": "ENTITY#USER",
    "entityType": "USER",
    "keycloakId": "kc-uuid-999",
    "email": "newuser@vinkane.com",
    "firstName": "New",
    "lastName": "User",
    "name": "New User",
    "role": "Operator",
    "isActive": true,
    "emailVerified": false,
    "createdAt": "2026-01-16T10:00:00Z",
    "updatedAt": "2026-01-16T10:00:00Z",
    "createdBy": "admin@vinkane.com"
  }'
```

**Response (200):**
```json
{
  "message": "User created successfully"
}
```

### PUT /users/{userId}
**Description:** Update user  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/users/user-999 \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-999",
    "PK": "USER#user-999",
    "SK": "ENTITY#USER",
    "firstName": "Updated",
    "lastName": "User",
    "role": "Manager"
  }'
```

**Response (200):**
```json
{
  "message": "User updated successfully"
}
```

### DELETE /users/{userId}
**Description:** Delete user  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/users/user-999
```

**Response (200):**
```json
{
  "message": "User deleted successfully"
}
```

---

## 4. REGIONS API

### GET /regions/hierarchy
**Description:** Get complete hierarchical location structure for dropdowns (single API call)  
**Use Case:** Ideal for React/frontend applications that need cascading dropdowns (State → District → Mandal → Village)  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions/hierarchy
```

**Response (200):**
```json
{
  "states": [
    {
      "code": "TS",
      "name": "Telangana"
    },
    {
      "code": "KA",
      "name": "KARNATAKA"
    },
    {
      "code": "MH",
      "name": "Maharashtra"
    }
  ],
  "districts": {
    "TS": [
      {
        "code": "HYD",
        "name": "HYDERABAD"
      },
      {
        "code": "RAN",
        "name": "RANGAREDDY"
      }
    ],
    "KA": [
      {
        "code": "CKB",
        "name": "Chikbalapura"
      }
    ]
  },
  "mandals": {
    "HYD": [
      {
        "code": "HYDE",
        "name": "HYDERABAD"
      }
    ],
    "RAN": [
      {
        "code": "ABDU",
        "name": "ABDULLAPURMET"
      },
      {
        "code": "BALA",
        "name": "BALAPUR"
      }
    ]
  },
  "villages": {
    "HYDE": [
      {
        "code": "VIL001",
        "name": "Sample Village"
      }
    ],
    "BALA": [
      {
        "code": "VIL002",
        "name": "Another Village"
      }
    ]
  }
}
```

**Notes:**
- All arrays sorted alphabetically by name
- Returns complete hierarchy in single request
- Efficient for client-side caching
- Keys are parent region codes (e.g., districts grouped by state code)

---

### GET /regions
**Description:** List all regions  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions
```

**Response (200):**
```json
[
  {
    "PK": "STATE#TS",
    "SK": "STATE#TS",
    "regionId": "TS",
    "regionName": "Telangana",
    "regionType": "STATE",
    "parentRegion": null,
    "isActive": true,
    "createdAt": "2024-01-10T10:00:00Z"
  }
]
```

### GET /regions/{regionType}
**Description:** Get regions by type (STATE, DISTRICT, MANDAL, VILLAGE, HABITATION)  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions/STATE
```

**Response (200):**
```json
[
  {
    "PK": "STATE#TS",
    "SK": "STATE#TS",
    "regionId": "TS",
    "regionName": "Telangana",
    "regionType": "STATE",
    "isActive": true
  },
  {
    "PK": "STATE#AP",
    "SK": "STATE#AP",
    "regionId": "AP",
    "regionName": "Andhra Pradesh",
    "regionType": "STATE",
    "isActive": true
  }
]
```

### GET /regions/{regionType}/{regionCode}
**Description:** Get specific region by type and code  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions/STATE/TS
```

**Response (200):**
```json
{
  "PK": "STATE#TS",
  "SK": "STATE#TS",
  "regionId": "TS",
  "regionName": "Telangana",
  "regionType": "STATE",
  "parentRegion": null,
  "isActive": true,
  "createdAt": "2024-01-10T10:00:00Z",
  "metadata": {
    "capital": "Hyderabad",
    "population": 35193978
  }
}
```

### GET /regions with query params
**Description:** Filter regions by type  
**Request:**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions?regionType=STATE"
```

**Response (200):**
```json
[
  {
    "PK": "STATE#TS",
    "SK": "STATE#TS",
    "regionId": "TS",
    "regionName": "Telangana",
    "regionType": "STATE"
  },
  {
    "PK": "STATE#AP",
    "SK": "STATE#AP",
    "regionId": "AP",
    "regionName": "Andhra Pradesh",
    "regionType": "STATE"
  }
]
```

### POST /regions
**Description:** Create new region  
**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "STATE#KA",
    "SK": "STATE#KA",
    "regionId": "KA",
    "regionName": "Karnataka",
    "regionType": "STATE",
    "parentRegion": null,
    "isActive": true,
    "metadata": {
      "capital": "Bengaluru",
      "population": 61095297
    }
  }'
```

**Response (200):**
```json
{
  "message": "Region created successfully"
}
```

### PUT /regions
**Description:** Update region (generic path, requires PK/SK in body)  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "STATE#KA",
    "SK": "STATE#KA",
    "regionName": "Karnataka State",
    "metadata": {
      "capital": "Bengaluru",
      "population": 62000000
    }
  }'
```

**Response (200):**
```json
{
  "message": "Region updated successfully"
}
```

### DELETE /regions
**Description:** Delete region (generic, requires PK/SK in body)  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "STATE#KA",
    "SK": "STATE#KA"
  }'
```

**Response (200):**
```json
{
  "message": "Region deleted successfully"
}
```

### DELETE /regions/{regionType}/{regionCode}
**Description:** Delete region by type and code  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions/STATE/KA
```

**Response (200):**
```json
{
  "message": "Region deleted successfully"
}
```

### DELETE /regions/{regionType}/{regionCode}/{parentCode}
**Description:** Delete region by type, code, and parent code  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/regions/DISTRICT/HYD/TS
```

**Response (200):**
```json
{
  "message": "Region deleted successfully"
}
```

---

## 5. SIMCARDS API

**Audit Trail Fields:** All SIM card records automatically track:
- `createdAt` / `updatedAt` - ISO 8601 timestamps with Z suffix
- `createdBy` / `updatedBy` - User identity (email) who created/last modified the record
- POST operations set all four fields; PUT operations update only updatedAt and updatedBy

### GET /simcards
**Description:** List all SIM cards  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/simcards
```

**Response (200):**
```json
[
  {
    "PK": "SIM#SIM001",
    "SK": "META",
    "simId": "SIM001",
    "iccid": "8991234567890123456",
    "phoneNumber": "+919876543210",
    "provider": "Airtel",
    "status": "active",
    "dataLimit": "10GB",
    "assignedDevice": "DEV001",
    "activatedDate": "2024-01-15T10:00:00Z",
    "expiryDate": "2025-01-15T10:00:00Z"
  }
]
```

### GET /simcards/{simId}
**Description:** Get single SIM card by ID  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/simcards/SIM001
```

**Response (200):**
```json
{
  "simId": "SIM001",
  "iccid": "8991234567890123456",
  "phoneNumber": "+919876543210",
  "provider": "Airtel",
  "status": "active"
}
```

### POST /simcards
**Description:** Create new SIM card  
**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/simcards \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "SIM999",
    "SK": "META",
    "simCardNumber": "8991234567890999999",
    "mobileNumber": "+919999999999",
    "provider": "Jio",
    "planType": "Prepaid",
    "simType": "4G",
    "monthlyDataLimit": 5120,
    "status": "inactive",
    "createdBy": "admin@vinkane.com"
  }'
```

**Response (201):**
```json
{
  "PK": "SIMCARD#SIM999",
  "SK": "ENTITY#SIMCARD",
  "entityType": "SIMCARD",
  "simCardNumber": "8991234567890999999",
  "mobileNumber": "+919999999999",
  "provider": "Jio",
  "planType": "Prepaid",
  "simType": "4G",
  "monthlyDataLimit": 5120,
  "status": "inactive",
  "createdAt": "2026-01-21T10:53:00Z",
  "updatedAt": "2026-01-21T10:53:00Z",
  "createdBy": "admin@vinkane.com",
  "updatedBy": "admin@vinkane.com"
}
```

### PUT /simcards/{simId}
**Description:** Update SIM card  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/simcards/SIM999 \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "SIM999",
    "SK": "META",
    "simCardNumber": "8991234567890999999",
    "mobileNumber": "+919999999999",
    "provider": "Jio",
    "planType": "Prepaid",
    "simType": "4G",
    "monthlyDataLimit": 5120,
    "status": "active",
    "activationDate": "2026-01-21T10:55:00Z"
  }'
```

**Response (200):**
```json
{
  "PK": "SIMCARD#SIM999",
  "SK": "ENTITY#SIMCARD",
  "entityType": "SIMCARD",
  "simCardNumber": "8991234567890999999",
  "mobileNumber": "+919999999999",
  "provider": "Jio",
  "planType": "Prepaid",
  "simType": "4G",
  "monthlyDataLimit": 5120,
  "status": "active",
  "activationDate": "2026-01-21T10:55:00Z",
  "updatedAt": "2026-01-21T10:55:30Z",
  "updatedBy": "admin@vinkane.com"
}
```

8. **Devices API - Mandatory Fields**: 
   - POST, PUT operations require `EntityType` and `DeviceId`
   - GET /devices (list): `EntityType` is optional, defaults to "DEVICE" for backward compatibility
   - DELETE operations use query parameters only (no path parameters), require `EntityType` and `DeviceId`
   - **Terraform Requirement**: DELETE /devices and PUT /devices routes must be configured in API Gateway
   - Different entity types require additional fields:
     - `DEVICE`: Only EntityType + DeviceId
     - `CONFIG`: EntityType + DeviceId + ConfigVersion + CreatedDate
     - `REPAIR`: EntityType + DeviceId + RepairId + CreatedDate
     - `INSTALL`: EntityType + DeviceId + InstallId + CreatedDate
     - `RUNTIME`: EntityType + DeviceId + EventDate
     - `SIM_ASSOC`: EntityType + DeviceId + SIMId
9. **Single Table Design**: Devices table stores multiple entity types (DEVICE, CONFIG, REPAIR, INSTALL, RUNTIME, SIM_ASSOC) using the same PK (DEVICE#{DeviceId}) with different SK patterns for entity isolation.
10. **SIM-Device Linking**:
    - **One-to-One Relationship**: One SIM can only be linked to one device at a time
    - **Atomic Transactions**: Link/unlink operations use DynamoDB transactions to update both v_devices and v_simcards tables atomically
    - **History Tracking**: All link/unlink operations are recorded in SIM card's `changeHistory` array with unlimited retention
    - **Audit Fields**: Each history entry includes ISO timestamp, action (linked/unlinked), deviceId, performedBy (user identity), and ipAddress
    - **Validation**: SIM must be "active" status and not already linked; device cannot have multiple SIMs
    - **Cross-Table Operations**: Linking creates `SIM_ASSOC` entity in devices table AND updates `linkedDeviceId` field in simcards table
11. **Terraform Routes Required for Devices API**:
    - `GET /devices` - List all devices ✅
    - `POST /devices` - Create device ✅
    - `PUT /devices` - Update device ⚠️ **REQUIRED** (not yet configured)
    - `DELETE /devices` - Delete device ⚠️ **REQUIRED** (not yet configured)
    - `GET /devices/{deviceId}/configs` - Get device configs ✅
    - `GET /devices/{deviceId}/sim` - Get linked SIM ⚠️ **REQUIRED** (not yet configured)
    - `POST /devices/{deviceId}/sim/link` - Link SIM to device ⚠️ **REQUIRED** (not yet configured)
    - `POST /devices/{deviceId}/sim/unlink` - Unlink SIM from device ⚠️ **REQUIRED** (not yet configured)
    - `GET /devices/{deviceId}/install` - Get device installation info ⚠️ **REQUIRED** (not yet configured)
    - `POST /installs/{installId}/devices/link` - Link device(s) to installation ⚠️ **REQUIRED** (not yet configured)
    - `POST /installs/{installId}/devices/unlink` - Unlink device(s) from installation ⚠️ **REQUIRED** (not yet configured)
    - `GET /installs/{installId}/devices` - List devices in installation ⚠️ **REQUIRED** (not yet configured)
    - `GET /installs/{installId}/history` - Get device link/unlink history ⚠️ **REQUIRED** (not yet configured)
12. **Field Survey API (Surveys)**:
    - **Draft/Submit Workflow**: Surveys start as "draft" and can be edited until submitted
    - **Immutable After Submit**: Once submitted, surveys cannot be updated or deleted
    - **Required Fields**: Draft can be saved with partial data; submission requires all mandatory fields (surveyor info, location)
    - **Image Management**: S3 storage with pre-signed URLs for upload, max 10 images per survey, 5MB per image
    - **Location Integration**: State/District/Mandal/Village link to existing regions in v_regions table
    - **Filtering**: Supports filtering by location hierarchy, date range, status, surveyor name
    - **Cascade Delete**: Deleting draft survey also removes all images from S3 and DynamoDB
13. **Terraform Routes Required for Surveys API**:
    - `POST /surveys` - Create survey ⚠️ **REQUIRED** (not yet configured)
    - `GET /surveys` - List surveys ⚠️ **REQUIRED** (not yet configured)
    - `GET /surveys/{surveyId}` - Get survey ⚠️ **REQUIRED** (not yet configured)
    - `PUT /surveys/{surveyId}` - Update survey ⚠️ **REQUIRED** (not yet configured)
    - `DELETE /surveys/{surveyId}` - Delete survey ⚠️ **REQUIRED** (not yet configured)
    - `POST /surveys/{surveyId}/submit` - Submit survey ⚠️ **REQUIRED** (not yet configured)
    - `POST /surveys/{surveyId}/images` - Upload image ⚠️ **REQUIRED** (not yet configured)
    - `DELETE /surveys/{surveyId}/images/{imageId}` - Delete image ⚠️ **REQUIRED** (not yet configured)
### DELETE /simcards/{simId}
**Description:** Delete SIM card  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/simcards/SIM999
```

**Response (200):**
```json
{
  "message": "SIM card deleted successfully"
}
```

---

## 6. SURVEYS API (Field Survey)

**Audit Trail Fields:** All survey records automatically track:
- `CreatedDate` / `UpdatedDate` - ISO 8601 timestamps with Z suffix
- `CreatedBy` / `UpdatedBy` - User identity (email) who created/last modified the record
- POST operations set CreatedBy; PUT operations set UpdatedBy
- Draft surveys can be edited; submitted surveys are immutable

### POST /surveys
**Description:** Create new field survey (draft status)  
**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/surveys \
  -H "Content-Type: application/json" \
  -d '{
    "SurveyorName": "John Doe",
    "SurveyorPhone": "+919876543210",
    "SurveyorEmail": "john@example.com",
    "SurveyDate": "2026-01-17",
    "State": "TS",
    "District": "HYD",
    "Mandal": "MDPL",
    "Village": "VLG001",
    "Habitation": "Colony A",
    "Latitude": 17.385044,
    "Longitude": 78.486671,
    "TankCapacity": {"value": 1000, "unit": "Litres"},
    "TankHeight": {"value": 5, "unit": "Meters"},
    "TankToMotorDistance": {"value": 10, "unit": "Meters"},
    "TankMaterial": "RCC",
    "TankCondition": "Good",
    "MotorCapacity": {"value": 5, "unit": "HP"},
    "MotorPhaseType": "3 Phase",
    "MotorManufacturer": "Kirloskar",
    "MotorWorkingCondition": "Working",
    "StarterType": "Star Delta Starter",
    "StarterWorkingCondition": "Working",
    "PowerSupplyAtTank": "Available",
    "PowerSupplySource": "Grid Supply",
    "ConnectionType": "Wireless",
    "Voltage": 440,
    "PowerQuality": "Stable",
    "ChlorineSystemAvailable": true,
    "SiteStatus": "Open",
    "CreatedBy": "admin@vinkane.com"
  }'
```

**Response (201):**
```json
{
  "created": {
    "PK": "SURVEY#SRV12345678",
    "SK": "META",
    "EntityType": "SURVEY",
    "SurveyId": "SRV12345678",
    "Status": "draft",
    "SurveyorName": "John Doe",
    "SurveyorPhone": "+919876543210",
    "State": "TS",
    "District": "HYD",
    "CreatedDate": "2026-01-17T10:00:00Z",
    "UpdatedDate": "2026-01-17T10:00:00Z",
    "CreatedBy": "admin@vinkane.com",
    "UpdatedBy": "admin@vinkane.com"
  }
}
```

### GET /surveys
**Description:** List all surveys with optional filters  
**Query Parameters:**
- `state` - Filter by state code
- `district` - Filter by district code
- `status` - Filter by status (draft/submitted)
- `surveyor` - Filter by surveyor name (contains)
- `fromDate` - Filter surveys from date (YYYY-MM-DD)
- `toDate` - Filter surveys to date (YYYY-MM-DD)

**Request:**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/surveys?state=TS&status=draft"
```

**Response (200):**
```json
{
  "surveys": [
    {
      "PK": "SURVEY#SRV12345678",
      "SK": "META",
      "SurveyId": "SRV12345678",
      "Status": "draft",
      "SurveyorName": "John Doe",
      "SurveyDate": "2026-01-17",
      "State": "TS",
      "District": "HYD",
      "imageCount": 3,
      "CreatedDate": "2026-01-17T10:00:00Z"
    }
  ],
  "count": 1
}
```

### GET /surveys/{surveyId}
**Description:** Get single survey with all images  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/surveys/SRV12345678
```

**Response (200):**
```json
{
  "PK": "SURVEY#SRV12345678",
  "SK": "META",
  "SurveyId": "SRV12345678",
  "Status": "draft",
  "SurveyorName": "John Doe",
  "SurveyorPhone": "+919876543210",
  "SurveyDate": "2026-01-17",
  "State": "TS",
  "District": "HYD",
  "Mandal": "MDPL",
  "Village": "VLG001",
  "TankCapacity": {"value": 1000, "unit": "Litres"},
  "MotorCapacity": {"value": 5, "unit": "HP"},
  "PowerSupplyAtTank": "Available",
  "SiteStatus": "Open",
  "images": [
    {
      "PK": "SURVEY#SRV12345678",
      "SK": "IMAGE#IMG12345678",
      "ImageId": "IMG12345678",
      "ImageUrl": "s3://bucket/surveys/SRV12345678/IMG12345678_tank.jpg",
      "Description": "Tank overview",
      "UploadedDate": "2026-01-17T10:05:00Z",
      "FileSize": 1048576,
      "MimeType": "image/jpeg"
    }
  ],
  "imageCount": 1,
  "CreatedDate": "2026-01-17T10:00:00Z",
  "UpdatedDate": "2026-01-17T10:00:00Z"
}
```

### PUT /surveys/{surveyId}
**Description:** Update survey (draft only, cannot update submitted surveys)  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/surveys/SRV12345678 \
  -H "Content-Type: application/json" \
  -d '{
    "TankCondition": "Excellent",
    "MotorWorkingCondition": "Good condition",
    "GeneralNotes": "Site is ready for installation"
  }'
```

**Response (200):**
```json
{
  "updated": {
    "PK": "SURVEY#SRV12345678",
    "SK": "META",
    "SurveyId": "SRV12345678",
    "Status": "draft",
    "TankCondition": "Excellent",
    "UpdatedDate": "2026-01-17T11:00:00Z"
  }
}
```

**Response (400) - Cannot update submitted:**
```json
{
  "error": "Cannot update submitted survey"
}
```

### POST /surveys/{surveyId}/submit
**Description:** Submit draft survey (makes it immutable)  
**Validation:** Requires all mandatory fields filled before submission  
**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/surveys/SRV12345678/submit
```

**Response (200):**
```json
{
  "message": "Survey submitted successfully",
  "surveyId": "SRV12345678",
  "submittedDate": "2026-01-17T12:00:00Z"
}
```

**Response (400) - Missing required fields:**
```json
{
  "error": "Missing required fields for submission: Latitude, Longitude"
}
```

**Response (400) - Already submitted:**
```json
{
  "error": "Survey already submitted"
}
```

### POST /surveys/{surveyId}/images
**Description:** Upload image to survey (generates pre-signed S3 upload URL)  
**Limits:** Max 10 images per survey, 5MB per image  
**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/surveys/SRV12345678/images \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "tank_overview.jpg",
    "contentType": "image/jpeg",
    "fileSize": 1048576,
    "description": "Tank overview from south side"
  }'
```

**Response (200):**
```json
{
  "imageId": "IMG12345678",
  "uploadUrl": "https://my-lambda-bucket-vinkane-dev.s3.amazonaws.com/",
  "uploadFields": {
    "key": "surveys/SRV12345678/IMG12345678_tank_overview.jpg",
    "Content-Type": "image/jpeg",
    "policy": "...",
    "x-amz-algorithm": "AWS4-HMAC-SHA256",
    "x-amz-credential": "...",
    "x-amz-date": "...",
    "x-amz-signature": "..."
  },
  "imageRecord": {
    "PK": "SURVEY#SRV12345678",
    "SK": "IMAGE#IMG12345678",
    "ImageId": "IMG12345678",
    "ImageUrl": "s3://bucket/surveys/SRV12345678/IMG12345678_tank_overview.jpg",
    "Description": "Tank overview from south side",
    "UploadedDate": "2026-01-17T10:05:00Z"
  }
}
```

**Note:** Use the `uploadUrl` and `uploadFields` to perform a multipart POST upload to S3.

**Response (400) - File too large:**
```json
{
  "error": "File size exceeds 5MB limit"
}
```

**Response (400) - Too many images:**
```json
{
  "error": "Maximum 10 images per survey"
}
```

### DELETE /surveys/{surveyId}/images/{imageId}
**Description:** Delete image from survey  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/surveys/SRV12345678/images/IMG12345678
```

**Response (200):**
```json
{
  "message": "Image deleted successfully",
  "imageId": "IMG12345678"
}
```

### DELETE /surveys/{surveyId}
**Description:** Delete survey (draft only, cannot delete submitted surveys)  
**Note:** Also deletes all associated images from S3 and DynamoDB  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/surveys/SRV12345678
```

**Response (200):**
```json
{
  "message": "Survey deleted successfully",
  "surveyId": "SRV12345678"
}
```

**Response (400) - Cannot delete submitted:**
```json
{
  "error": "Cannot delete submitted survey"
}
```

---

## 3. INSTALLS API

### GET /installs
**Description:** Fetch all device installations with pagination support  
**Query Parameters (Optional):**
- `includeDevices` - Set to `true` to include full device details in response (default: `false`)
- `includeCustomer` - Set to `true` to include customer details in response (default: `true`)
- `limit` - Number of items per page, 1-100 (default: `50`)
- `nextToken` - Pagination token from previous response for fetching next page

**Response Fields:**
- `contactsCount` - Number of contacts linked to each installation (always included)
- `linkedDevices` - Array of device details (only when `includeDevices=true`)
- `customer` - Customer details object (only when `includeCustomer=true`)

**Request (basic - without devices):**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs"
```

**Response (200):**
```json
{
  "installCount": 2,
  "includeDevices": false,
  "includeCustomer": true,
  "limit": 50,
  "installs": [
    {
      "PK": "INSTALL#INST-HAB-001",
      "SK": "META",
      "InstallationId": "INST-HAB-001",
      "CustomerId": "CUSTB8F7213D",
      "Status": "inactive",
      "PrimaryDevice": "chlorine",
      "StateId": "TS",
      "DistrictId": "RR",
      "MandalId": "RR01",
      "VillageId": "RR01001",
      "HabitationId": "HAB-001",
      "stateName": "Telangana",
      "districtName": "Ranga Reddy",
      "mandalName": "Mandal 01",
      "villageName": "Village 001",
      "habitationName": "Habitation 001",
      "InstallationDate": "2026-01-20T10:00:00Z",
      "CreatedDate": "2026-01-20T10:00:00Z",
      "UpdatedDate": "2026-01-29T08:07:51.136123Z",
      "CreatedBy": "admin",
      "UpdatedBy": "admin",
      "contactsCount": 2,
      "customer": {
        "customerId": "CUSTB8F7213D",
        "name": "ABC Corporation",
        "companyName": "ABC Corp",
        "email": "contact@abccorp.com",
        "phone": "9876543210",
        "countryCode": "+91"
      },
      "changeHistory": [
        {
          "timestamp": "2026-01-29T08:07:51.136123Z",
          "updatedBy": "admin",
          "ipAddress": "49.205.252.50",
          "changes": {
            "Status": {
              "oldValue": "active",
              "newValue": "inactive"
            },
            "PrimaryDevice": {
              "oldValue": "water",
              "newValue": "chlorine"
            }
          }
        }
      ]
    },
    {
      "PK": "INSTALL#INST-HAB-003",
      "SK": "META",
      "InstallationId": "INST-HAB-003",
      "CustomerId": null,
      "Status": "active",
      "PrimaryDevice": "chlorine",
      "StateId": "TS",
      "DistrictId": "RR",
      "MandalId": "RR01",
      "VillageId": "RR01002",
      "HabitationId": "HAB-003",
      "stateName": "Telangana",
      "districtName": "Ranga Reddy",
      "mandalName": "Mandal 01",
      "villageName": "Village 002",
      "habitationName": "Habitation 003",
      "InstallationDate": "2026-01-25T09:00:00Z",
      "CreatedDate": "2026-01-25T09:00:00Z",
      "UpdatedDate": "2026-01-25T09:00:00Z",
      "CreatedBy": "technician",
      "UpdatedBy": "technician",
      "contactsCount": 0,
      "changeHistory": null
    }
  ]
}
```

**Request (with pagination):**
```bash
# First page
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs?limit=10"

# Next page using returned token
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs?limit=10&nextToken=eyJQSyI6IklOU1RBTEwjSU5TVC0wMDEiLCJTSyI6Ik1FVEEifQ=="
```

**Request (with devices - comprehensive view):**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs?includeDevices=true&includeCustomer=true"
```

**Response (200):**
```json
{
  "installCount": 2,
  "includeDevices": true,
  "installs": [
    {
      "PK": "INSTALL#INST-HAB-001",
      "SK": "META",
      "InstallationId": "INST-HAB-001",
      "Status": "inactive",
      "PrimaryDevice": "chlorine",
      "LocationHierarchy": {
        "StateId": "TS",
        "DistrictId": "RR",
        "MandalId": "RR01",
        "VillageId": "RR01001",
        "HabitationId": "HAB-001"
      },
      "InstallationDate": "2026-01-20T10:00:00Z",
      "CreatedDate": "2026-01-20T10:00:00Z",
      "UpdatedDate": "2026-01-29T08:07:51.136123Z",
      "CreatedBy": "admin",
      "UpdatedBy": "admin",
      "linkedDeviceCount": 1,
      "linkedDevices": [
        {
          "DeviceId": "DEV009",
          "linkedDate": "2026-01-29T07:57:28.910107Z",
          "linkedBy": "admin"
        }
      ],
      "changeHistory": [
        {
          "timestamp": "2026-01-29T08:07:51.136123Z",
          "updatedBy": "admin",
          "ipAddress": "49.205.252.50",
          "changes": {
            "Status": {
              "oldValue": "active",
              "newValue": "inactive"
            },
            "PrimaryDevice": {
              "oldValue": "water",
              "newValue": "chlorine"
            }
          }
        }
      ]
    },
    {
      "PK": "INSTALL#INST-HAB-003",
      "SK": "META",
      "InstallationId": "INST-HAB-003",
      "Status": "active",
      "PrimaryDevice": "chlorine",
      "LocationHierarchy": {
        "StateId": "TS",
        "DistrictId": "RR",
        "MandalId": "RR01",
        "VillageId": "RR01002",
        "HabitationId": "HAB-003"
      },
      "InstallationDate": "2026-01-25T09:00:00Z",
      "CreatedDate": "2026-01-25T09:00:00Z",
      "UpdatedDate": "2026-01-25T09:00:00Z",
      "CreatedBy": "technician",
      "UpdatedBy": "technician",
      "contactsCount": 0,
      "linkedDeviceCount": 2,
      "linkedDevices": [
        {
          "DeviceId": "DEV008",
          "linkedDate": "2026-01-29T08:19:41.349143Z",
          "linkedBy": "admin"
        },
        {
          "DeviceId": "DEV009",
          "linkedDate": "2026-01-29T08:25:22.557145Z",
          "linkedBy": "technician"
        }
      ],
      "changeHistory": null
    }
  ]
}
```

### GET /installs/{installId}/devices
**Description:** Get all devices linked to an installation  
**Request:**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST001/devices"
```

**Response (200):**
```json
{
  "installId": "INST001",
  "deviceCount": 2,
  "devices": [
    {
      "DeviceId": "DEV001",
      "DeviceName": "Water Motor Unit",
      "Status": "active",
      "linkedDate": "2026-01-20T10:15:00Z",
      "linkedBy": "admin",
      "linkStatus": "active"
    },
    {
      "DeviceId": "DEV009",
      "DeviceName": "Pump Controller",
      "Status": "active",
      "linkedDate": "2026-01-20T10:20:00Z",
      "linkedBy": "admin",
      "linkStatus": "active"
    }
  ]
}
```

### GET /installs/{installId}/history
**Description:** Get device link/unlink history for an installation  
**Request:**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST001/history"
```

**Response (200):**
```json
{
  "installId": "INST001",
  "historyCount": 2,
  "history": [
    {
      "Action": "linked",
      "DeviceId": "DEV009",
      "PerformedAt": "2026-01-20T10:20:00Z",
      "PerformedBy": "admin",
      "Reason": "Initial installation"
    },
    {
      "Action": "linked",
      "DeviceId": "DEV001",
      "PerformedAt": "2026-01-20T10:15:00Z",
      "PerformedBy": "admin",
      "Reason": "Initial installation"
    }
  ]
}
```

### POST /installs/{installId}/devices/link
**Description:** Link one or more devices to an installation  
**Request:**
```bash
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST001/devices/link" \
  -H "Content-Type: application/json" \
  -d '{
    "deviceIds": ["DEV010", "DEV011"],
    "performedBy": "admin",
    "reason": "Added as part of expansion"
  }'
```

**Response (200):**
```json
{
  "installId": "INST001",
  "linked": [
    {"deviceId": "DEV010", "status": "linked"},
    {"deviceId": "DEV011", "status": "linked"}
  ],
  "performedBy": "admin",
  "timestamp": "2026-01-28T11:05:00Z"
}
```

### POST /installs/{installId}/devices/unlink
**Description:** Unlink one or more devices from an installation  
**Request:**
```bash
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST001/devices/unlink" \
  -H "Content-Type: application/json" \
  -d '{
    "deviceIds": ["DEV010"],
    "performedBy": "admin",
    "reason": "Device removed from site"
  }'
```

**Response (200):**
```json
{
  "installId": "INST001",
  "unlinked": [
    {"deviceId": "DEV010", "status": "unlinked"}
  ],
  "performedBy": "admin",
  "timestamp": "2026-01-28T11:10:00Z"
}
```

### POST /installs
**Description:** Create a new installation with location hierarchy and optional device linking  
**Features:**
- Auto-generates UUID installation ID
- Validates region IDs (State, District, Mandal, Village, Habitation)
- Syncs region hierarchy to Thingsboard assets
- Optional device linking during creation
- Automatic Thingsboard habitation linking for devices
- Uses fallback habitation assets when API issues occur

**Request (Basic):**
```bash
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs" \
  -H "Content-Type: application/json" \
  -d '{
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "005",
    "PrimaryDevice": "water",
    "Status": "active",
    "InstallationDate": "2026-01-31T00:00:00.000Z"
  }'
```

**Request (With Optional Fields):**
```bash
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs" \
  -H "Content-Type: application/json" \
  -d '{
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "005",
    "PrimaryDevice": "water",
    "Status": "active",
    "InstallationDate": "2026-01-31T00:00:00.000Z",
    "CustomerId": "CUST-001",
    "TemplateId": "TMPL-001",
    "WarrantyDate": "2027-01-31T00:00:00.000Z",
    "CreatedBy": "admin@example.com",
    "deviceIds": ["DEV001", "DEV002"]
  }'
```

**Response (201):**
```json
{
  "created": {
    "PK": "INSTALL#a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "SK": "META",
    "EntityType": "INSTALL",
    "InstallationId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "005",
    "stateName": "Telangana",
    "districtName": "Hyderabad",
    "mandalName": "Srikakulam Nagar",
    "villageName": "Village 001",
    "habitationName": "Habitation 005",
    "PrimaryDevice": "water",
    "Status": "active",
    "InstallationDate": "2026-01-31T00:00:00.000Z",
    "CustomerId": "CUST-001",
    "TemplateId": "TMPL-001",
    "WarrantyDate": "2027-01-31T00:00:00.000Z",
    "CreatedDate": "2026-01-31T10:30:00.000Z",
    "UpdatedDate": "2026-01-31T10:30:00.000Z",
    "CreatedBy": "admin@example.com",
    "UpdatedBy": "admin@example.com",
    "thingsboardStatus": "synced",
    "thingsboardAssets": {
      "state": {
        "id": "fb123abc-4567-8901-def0-123456789abc",
        "name": "Telangana"
      },
      "district": {
        "id": "cd456def-7890-1234-abc5-678901234def",
        "name": "Hyderabad"
      },
      "mandal": {
        "id": "ef789012-3456-7890-bcd1-234567890abc",
        "name": "Srikakulam Nagar"
      },
      "village": {
        "id": "12345678-9012-3456-cde7-890123456789",
        "name": "Village 001"
      },
      "habitation": {
        "id": "90123456-7890-1234-def8-901234567890",
        "name": "Habitation 005"
      }
    }
  },
  "deviceLinking": {
    "linked": [
      {
        "deviceId": "DEV001",
        "status": "linked",
        "thingsboardLinked": true
      },
      {
        "deviceId": "DEV002",
        "status": "linked",
        "thingsboardLinked": true
      }
    ],
    "errors": []
  }
}
```

**Required Fields:**
- `StateId` - State identifier (validated against regions table)
- `DistrictId` - District identifier (validated against regions table)
- `MandalId` - Mandal identifier (validated against regions table)
- `VillageId` - Village identifier (validated against regions table)
- `HabitationId` - Habitation identifier (validated against regions table)
- `PrimaryDevice` - Must be `"water"`, `"chlorine"`, or `"none"`
- `Status` - Must be `"active"` or `"inactive"`
- `InstallationDate` - ISO 8601 date string

**Optional Fields:**
- `CustomerId` - Customer reference ID (validated if provided)
- `TemplateId` - Template reference ID (validated if provided)
- `WarrantyDate` - ISO 8601 date string
- `CreatedBy` - User who created the installation (defaults to `"system"`)
- `deviceIds` - Array of device IDs to link during creation (e.g., `["DEV001", "DEV002"]`)

**Auto-Generated Fields:**
- `InstallationId` - UUID automatically generated by the system
- `EntityType` - Always set to `"INSTALL"`
- `CreatedDate` - Auto-generated timestamp
- `UpdatedDate` - Auto-generated timestamp
- `UpdatedBy` - Initially same as CreatedBy
- Region names (`stateName`, `districtName`, `mandalName`, `villageName`, `habitationName`)
- `thingsboardStatus` - Status of Thingsboard sync
- `thingsboardAssets` - Asset IDs created in Thingsboard

**Validation Rules:**
- All region IDs must exist in the regions table
- CustomerId must exist in customers table (if provided)
- TemplateId must exist in templates table (if provided)
- Device IDs must exist and not be linked to another installation
- PrimaryDevice accepts only: `"water"`, `"chlorine"`, or `"none"`
- Status accepts only: `"active"` or `"inactive"`

**Thingsboard Integration:**
- Creates hierarchical region assets (State → District → Mandal → Village → Habitation)
- Creates "contains" relations between region levels
- Links devices to habitation asset automatically
- Uses fallback habitation IDs when API creation fails
- Non-blocking - installation succeeds even if Thingsboard sync fails

### GET /installs/{installId}
**Description:** Get a single installation by ID with optional related data  
**Query Parameters (Optional):**
- `includeDevices=true` - Include full device details (default: `false`)
- `includeCustomer=true` - Include customer details (default: `true`)
- `includeContacts=true` - Include linked contact details (default: `false`)

**Request (basic):**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/ebc4c2b3-f9cb-471e-9d69-bd93061ce64c"
```

**Request (with all related data):**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/ebc4c2b3-f9cb-471e-9d69-bd93061ce64c?includeDevices=true&includeCustomer=true&includeContacts=true"
```

**Response (200) - Basic:**
```json
{
  "PK": "INSTALL#ebc4c2b3-f9cb-471e-9d69-bd93061ce64c",
  "SK": "META",
  "InstallationId": "ebc4c2b3-f9cb-471e-9d69-bd93061ce64c",
  "CustomerId": "CUSTB8F7213D",
  "StateId": "TS",
  "DistrictId": "HYD",
  "MandalId": "SRNAGAR",
  "VillageId": "VILLAGE001",
  "HabitationId": "005",
  "stateName": "Telangana",
  "districtName": "Hyderabad",
  "mandalName": "Srikakulam Nagar",
  "villageName": "Village 001",
  "habitationName": "Habitation 005",
  "PrimaryDevice": "water",
  "Status": "active",
  "InstallationDate": "2026-01-31T00:00:00.000Z",
  "CreatedDate": "2026-01-31T10:30:00.000Z",
  "UpdatedDate": "2026-01-31T10:30:00.000Z",
  "CreatedBy": "admin@example.com",
  "UpdatedBy": "admin@example.com",
  "customer": {
    "customerId": "CUSTB8F7213D",
    "name": "ABC Corporation",
    "companyName": "ABC Corp",
    "email": "contact@abccorp.com",
    "phone": "9876543210",
    "countryCode": "+91"
  }
}
```

**Response (200) - With includeDevices=true:**
```json
{
  "PK": "INSTALL#ebc4c2b3-f9cb-471e-9d69-bd93061ce64c",
  "SK": "META",
  "InstallationId": "ebc4c2b3-f9cb-471e-9d69-bd93061ce64c",
  "CustomerId": "CUSTB8F7213D",
  "StateId": "TS",
  "stateName": "Telangana",
  "PrimaryDevice": "water",
  "Status": "active",
  "linkedDeviceCount": 2,
  "linkedDevices": [
    {
      "DeviceId": "DEV001",
      "DeviceName": "Water Motor Unit",
      "DeviceType": "IoT Sensor",
      "Status": "active",
      "SerialNumber": "SN123456789",
      "linkedDate": "2026-01-31T11:00:00.000Z",
      "linkedBy": "admin@example.com",
      "linkStatus": "active"
    },
    {
      "DeviceId": "DEV002",
      "DeviceName": "Chlorine Sensor",
      "DeviceType": "IoT Sensor",
      "Status": "active",
      "SerialNumber": "SN987654321",
      "linkedDate": "2026-01-31T11:05:00.000Z",
      "linkedBy": "admin@example.com",
      "linkStatus": "active"
    }
  ]
}
```

**Response (200) - With includeContacts=true:**
```json
{
  "InstallationId": "ebc4c2b3-f9cb-471e-9d69-bd93061ce64c",
  "CustomerId": "CUSTB8F7213D",
  "linkedContactCount": 2,
  "linkedContacts": [
    {
      "contactId": "CONT092F151B",
      "customerId": "CUSTB8F7213D",
      "firstName": "Ramesh",
      "lastName": "Kumar",
      "displayName": "Ramesh Kumar",
      "email": {
        "encrypted_value": "cmFtZXNoa3VtYXJAdmlua2FuZS5jb20=",
        "key_version": "1",
        "encrypted_at": "2026-02-03T07:59:25.164613Z"
      },
      "mobileNumber": "890945409",
      "countryCode": "+91",
      "contactType": "primary",
      "linkedDate": "2026-02-03T09:43:07.412648Z",
      "linkedBy": "system",
      "linkStatus": "active"
    }
  ]
}
```

**Response (404) - Install not found:**
```json
{
  "error": "Install ebc4c2b3-f9cb-471e-9d69-bd93061ce64c not found"
}
```

---

### PUT /installs/{installId}
**Description:** Update installation details  
**Request:**
```bash
curl -X PUT "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST-HAB-001" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "inactive",
    "primaryDevice": "chlorine",
    "warrantyDate": "2028-01-29T00:00:00.000Z",
    "updatedBy": "admin"
  }'
```

**Response (200):**
```json
{
  "message": "Installation updated successfully",
  "installation": {
    "PK": "INSTALL#INST-HAB-001",
    "SK": "META",
    "EntityType": "INSTALL",
    "InstallationId": "INST-HAB-001",
    "StateId": "STATE-001",
    "DistrictId": "DIST-001",
    "MandalId": "MANDAL-001",
    "VillageId": "VILLAGE-001",
    "HabitationId": "HAB-001",
    "PrimaryDevice": "chlorine",
    "Status": "inactive",
    "InstallationDate": "2026-01-29T00:00:00.000Z",
    "WarrantyDate": "2028-01-29T00:00:00.000Z",
    "CreatedDate": "2026-01-29T07:21:27.552251Z",
    "UpdatedDate": "2026-01-29T08:07:51.136123Z",
    "CreatedBy": "system",
    "UpdatedBy": "admin",
    "changeHistory": [
      {
        "timestamp": "2026-01-29T08:07:51.136123Z",
        "updatedBy": "admin",
        "ipAddress": "49.205.252.50",
        "changes": {
          "Status": {
            "oldValue": "active",
            "newValue": "inactive"
          },
          "PrimaryDevice": {
            "oldValue": "water",
            "newValue": "chlorine"
          }
        }
      }
    ]
  },
  "changes": {
    "Status": {
      "oldValue": "active",
      "newValue": "inactive"
    },
    "PrimaryDevice": {
      "oldValue": "water",
      "newValue": "chlorine"
    }
  }
}
```

**Updatable Fields:**
- `status` - "active" or "inactive"
- `primaryDevice` - "water", "chlorine", or "none"
- `warrantyDate` - ISO 8601 date string
- `installationDate` - ISO 8601 date string
- `customerId` - Customer reference
- `templateId` - Template reference
- `updatedBy` - User making the update (recommended)

**Features:**
- Only updates fields that have changed
- Automatically tracks change history with old/new values
- Records IP address, timestamp, and user for each change
- Returns both the updated installation and a summary of changes

---

### DELETE /installs/{installId}
**Description:** Delete an installation with optional soft delete or cascade delete  
**Query Parameters:**
- `soft` (optional): Set to "true" for soft delete (marks as deleted without removing data)
- `cascade` (optional): Set to "true" to delete installation and all associations (devices, contacts)
- `performedBy` (optional): Email/username of person performing deletion (default: "system")

**Request - Standard Delete (requires no linked resources):**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST-HAB-001?performedBy=admin@example.com"
```

**Response (200) - Success:**
```json
{
  "deleted": {
    "PK": "INSTALL#INST-HAB-001",
    "SK": "META",
    "InstallationId": "INST-HAB-001"
  }
}
```

**Response (409) - Validation Error (has linked resources):**
```json
{
  "error": {
    "message": "Cannot delete installation with active associations",
    "linkedDevices": 2,
    "linkedContacts": 1,
    "suggestion": "Use ?cascade=true to delete all associations, or ?soft=true to mark as deleted"
  }
}
```

**Request - Soft Delete:**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST-HAB-001?soft=true&performedBy=admin@example.com"
```

**Response (200):**
```json
{
  "deleted": {
    "PK": "INSTALL#INST-HAB-001",
    "SK": "META",
    "InstallationId": "INST-HAB-001",
    "softDelete": true,
    "deletedAt": "2026-02-04T10:30:00.000000Z",
    "deletedBy": "admin@example.com"
  }
}
```

**Request - Cascade Delete (removes all associations):**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST-HAB-001?cascade=true&performedBy=admin@example.com"
```

**Response (200):**
```json
{
  "deleted": {
    "InstallationId": "INST-HAB-001",
    "cascadeDelete": true,
    "totalRecordsDeleted": 5,
    "deletedItems": [
      {
        "PK": "DEVICE#DEV001",
        "SK": "INSTALL#INST-HAB-001",
        "Type": "bidirectional_device_assoc"
      },
      {
        "PK": "CUSTOMER#CUST001",
        "SK": "ENTITY#INSTALL_ASSOC#INST-HAB-001",
        "Type": "bidirectional_contact_assoc",
        "Table": "v_customers_dev"
      },
      {
        "PK": "INSTALL#INST-HAB-001",
        "SK": "META",
        "Type": "installation_record"
      },
      {
        "PK": "INSTALL#INST-HAB-001",
        "SK": "DEVICE_ASSOC#DEV001",
        "Type": "installation_record"
      },
      {
        "PK": "INSTALL#INST-HAB-001",
        "SK": "CONTACT_ASSOC#CONT001",
        "Type": "installation_record"
      }
    ]
  }
}
```

**Features:**
- **Validation**: Standard delete blocked if installation has linked devices or contacts
- **Soft Delete**: Marks installation as deleted (adds `IsDeleted=true`, `DeletedAt`, `DeletedBy`) without removing data
- **Cascade Delete**: Removes installation and all associations:
  - Device associations (bidirectional: `INSTALL#` → `DEVICE#` and `DEVICE#` → `INSTALL#`)
  - Contact associations (bidirectional: `INSTALL#` → `CUSTOMER#` contact links)
  - Removes `LinkedInstallationId` from device META records
  - Installation META and all association records
- **Audit Trail**: Tracks who performed deletion and when

**Error Responses:**
- `404`: Installation not found
- `409`: Cannot delete installation with linked resources (use cascade or soft delete)
- `500`: Database or unexpected error

---

## 4. AUDIT TRAIL & CHANGE TRACKING

### Overview
The API automatically tracks all changes to devices and SIM cards through the `changeHistory` array. This feature provides complete audit trails for compliance, troubleshooting, and understanding the evolution of entity state over time.

### Change Tracking Behavior

#### For Devices (PUT /devices)
**Tracked Fields:**
- `DeviceName` - Device display name
- `DeviceType` - Category of device (Motor, Pump, Sensor, etc.)
- `SerialNumber` - Hardware serial number
- `Status` - Device operational status (active, inactive, maintenance, etc.)
- `Location` - Device physical location

**Change History Structure:**
```json
{
  "changeHistory": [
    {
      "timestamp": "2026-01-28T14:30:00Z",
      "action": "updated",
      "changes": {
        "Status": { "from": "active", "to": "maintenance" },
        "DeviceName": { "from": "Pump Unit A", "to": "Pump Unit A (Maintenance)" },
        "Location": { "from": "Building 1", "to": "Building 1 - Service Area" }
      },
      "updatedBy": "technician@example.com",
      "ipAddress": "192.168.1.100"
    },
    {
      "timestamp": "2026-01-20T10:00:00Z",
      "action": "created",
      "changes": {
        "Status": { "from": null, "to": "active" },
        "DeviceName": { "from": null, "to": "Pump Unit A" }
      },
      "updatedBy": "admin@example.com",
      "ipAddress": "192.168.1.50"
    }
  ]
}
```

**Key Features:**
- **Selective Recording**: Only changed fields are recorded in each history entry
- **Before/After Values**: Each change includes both "from" and "to" values for comparison
- **Full History**: All updates accumulate, with most recent first in the array
- **Timestamps**: ISO 8601 format with UTC timezone
- **User Attribution**: Tracks who made the change and their IP address
- **Immutable**: History entries cannot be modified or deleted

#### Example: Device Update with Change Tracking
**Request:**
```bash
curl -X PUT "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: technician@example.com" \
  -d '{
    "EntityType": "DEVICE",
    "DeviceId": "DEV009",
    "DeviceName": "Pump Unit A (Under Maintenance)",
    "Status": "maintenance",
    "Location": "Building 1 - Service Area"
  }'
```

**Response (200):**
```json
{
  "PK": "DEVICE#DEV009",
  "SK": "META",
  "DeviceId": "DEV009",
  "DeviceName": "Pump Unit A (Under Maintenance)",
  "Status": "maintenance",
  "Location": "Building 1 - Service Area",
  "changeHistory": [
    {
      "timestamp": "2026-01-28T14:30:00Z",
      "action": "updated",
      "changes": {
        "DeviceName": {
          "from": "Pump Unit A",
          "to": "Pump Unit A (Under Maintenance)"
        },
        "Status": {
          "from": "active",
          "to": "maintenance"
        },
        "Location": {
          "from": "Building 1",
          "to": "Building 1 - Service Area"
        }
      },
      "updatedBy": "technician@example.com",
      "ipAddress": "192.168.1.100"
    },
    {
      "timestamp": "2026-01-20T10:00:00Z",
      "action": "created",
      "changes": {
        "DeviceName": {
          "from": null,
          "to": "Pump Unit A"
        },
        "Status": {
          "from": null,
          "to": "active"
        }
      },
      "updatedBy": "admin@example.com",
      "ipAddress": "192.168.1.50"
    }
  ]
}
```

#### For SIM Cards (PUT /simcards)
**Tracked Fields:**
- `status` - SIM operational status (active, inactive, suspended, etc.)
- `planType` - Data plan type (prepaid, postpaid)
- `monthlyDataLimit` - Monthly data quota in MB
- `monthlyCharges` - Cost per month
- `isRoamingEnabled` - International roaming flag
- `provider` - Telecom provider name
- `mobileNumber` - Associated phone number
- `simType` - SIM type (4G, 5G, IoT)

**Example: SIM Update with Change Tracking**
**Request:**
```bash
curl -X PUT "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/simcards" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: admin@example.com" \
  -d '{
    "simId": "SIM-4",
    "status": "inactive",
    "planType": "postpaid",
    "monthlyDataLimit": 2048,
    "monthlyCharges": 500,
    "isRoamingEnabled": true
  }'
```

**Response (200):**
```json
{
  "simId": "SIM-4",
  "status": "inactive",
  "planType": "postpaid",
  "monthlyDataLimit": 2048,
  "monthlyCharges": 500,
  "isRoamingEnabled": true,
  "provider": "Airtel",
  "mobileNumber": "+919876543210",
  "simType": "4G",
  "linkedDeviceId": null,
  "changeHistory": [
    {
      "timestamp": "2026-01-28T15:45:00Z",
      "action": "updated",
      "changes": {
        "status": {
          "from": "active",
          "to": "inactive"
        },
        "planType": {
          "from": "prepaid",
          "to": "postpaid"
        },
        "monthlyDataLimit": {
          "from": 1024,
          "to": 2048
        },
        "monthlyCharges": {
          "from": 250,
          "to": 500
        },
        "isRoamingEnabled": {
          "from": false,
          "to": true
        }
      },
      "updatedBy": "admin@example.com",
      "ipAddress": "192.168.1.75"
    }
  ]
}
```

### SIM Link/Unlink History
SIM link/unlink operations also create changeHistory entries on the SIM card with enhanced details:

**Link Operation History Entry:**
```json
{
  "timestamp": "2026-01-28T16:00:00Z",
  "action": "linked",
  "changes": {
    "deviceId": {
      "from": null,
      "to": "DEV009"
    },
    "deviceName": {
      "from": null,
      "to": "Pump Unit A"
    }
  },
  "linkedDeviceId": "DEV009",
  "linkedBy": "technician@example.com",
  "ipAddress": "192.168.1.100"
}
```

**Unlink Operation History Entry:**
```json
{
  "timestamp": "2026-01-28T16:30:00Z",
  "action": "unlinked",
  "changes": {
    "deviceId": {
      "from": "DEV009",
      "to": null
    },
    "deviceName": {
      "from": "Pump Unit A",
      "to": null
    }
  },
  "unlinkedBy": "technician@example.com",
  "ipAddress": "192.168.1.100"
}
```

### History Data Retrieval

While `changeHistory` is automatically included in single-entity GET responses, you can retrieve full history for an installation's device changes:

**GET /installs/{installId}/history** - Returns all device link/unlink operations for the installation with timestamps and performer information.

### Retention & Archival
- **No Expiration**: Change history entries are retained indefinitely
- **Immutable**: Once recorded, history entries cannot be modified or deleted
- **Compliance**: Full audit trail enables regulatory compliance (SOX, GDPR, etc.)
- **Unbounded Growth**: For high-frequency updates, changeHistory arrays may grow large; consider archival strategies for long-lived devices

---

## Common Error Responses

### 400 Bad Request
```json
{
  "error": "Malformed JSON body: Expecting value: line 1 column 1 (char 0)"
}
```

### 404 Not Found
```json
{
  "error": "Item not found"
}
```

### 405 Method Not Allowed
```json
{
  "error": "Method not allowed"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```

---

## CORS Headers

All endpoints return the following CORS headers:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: DELETE,GET,OPTIONS,POST,PUT
Access-Control-Allow-Headers: authorization,content-type,x-amz-date,x-amz-security-token,x-api-key
Access-Control-Max-Age: 300
Access-Control-Expose-Headers: content-length,content-type
```

---

## Notes

1. **Authentication**: Currently not implemented. All endpoints are publicly accessible.
2. **Data Format**: All requests and responses use `application/json` content type.
3. **Primary Keys**: Most entities use composite keys (PK + SK) for DynamoDB single-table design.
4. **Users Table Exception**: Uses simple `id` hash key instead of PK/SK composite.
5. **Cascade Deletes**: Customer deletion automatically removes all related contacts and addresses.
6. **Query Parameters**: Devices and Regions endpoints support filtering via query parameters.
7. **Nested Data**: GET /customers/{id} returns nested contacts[] and addresses[] arrays.
