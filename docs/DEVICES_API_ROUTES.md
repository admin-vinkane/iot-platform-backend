# v_devices API Routes - Complete Guide

## Overview
The v_devices API provides endpoints for managing installations, devices, SIM cards, repairs, and historical data. Below is a comprehensive list of all available routes.

---

## Installation Routes

### 1. Create Installation
**Endpoint**: `POST /installs`

**Description**: Create a new installation record and sync regions to Thingsboard

**Request Body**:
```json
{
  "InstallationId": "INST-001",
  "StateId": "TS",
  "DistrictId": "HYD",
  "MandalId": "SRNAGAR",
  "VillageId": "VILLAGE001",
  "HabitationId": "005",
  "PrimaryDevice": "device-uuid",
  "Status": "active",
  "InstallationDate": "2025-01-31",
  "CreatedBy": "admin",
  "CustomerId": "CUST-001",
  "TemplateId": "TEMP-001",
  "WarrantyDate": "2026-01-31"
}
```

**Response**:
```json
{
  "message": "Installation created successfully",
  "installation": {
    "InstallationId": "INST-001",
    "thingsboardStatus": "synced",
    "thingsboardAssets": {
      "state": {"id": "...", "name": "...", "code": "..."},
      "district": {"id": "...", "name": "...", "code": "..."},
      "mandal": {"id": "...", "name": "...", "code": "..."},
      "village": {"id": "...", "name": "...", "code": "..."},
      "habitation": {"id": "...", "name": "...", "code": "..."}
    }
  }
}
```

**Status**: ✅ Working
**Line**: 416-560

---

### 2. Get All Installations
**Endpoint**: `GET /installs`

**Description**: List all installations

**Query Parameters**: None

**Response**:
```json
{
  "count": 5,
  "installations": [
    {
      "InstallationId": "INST-001",
      "StateId": "TS",
      "DistrictId": "HYD",
      ...
    }
  ]
}
```

**Status**: ✅ Working
**Line**: 1247-1350

---

### 3. Get Single Installation
**Endpoint**: `GET /installs/{installId}`

**Description**: Get details of a specific installation

**Path Parameters**:
- `installId` (required): Installation ID

**Response**:
```json
{
  "InstallationId": "INST-001",
  "StateId": "TS",
  "DistrictId": "HYD",
  ...
}
```

**Status**: ✅ Working
**Line**: 1152-1245

---

### 4. Update Installation
**Endpoint**: `PUT /installs/{installId}`

**Description**: Update an existing installation

**Path Parameters**:
- `installId` (required): Installation ID

**Request Body**: Any fields to update

**Response**: Updated installation object

**Status**: ✅ Working
**Line**: 1720-1780

---

### 5. Get Installation History
**Endpoint**: `GET /installs/{installId}/history`

**Description**: Get change history for an installation

**Path Parameters**:
- `installId` (required): Installation ID

**Response**:
```json
{
  "installationId": "INST-001",
  "changes": [...]
}
```

**Status**: ✅ Working
**Line**: 1565-1650

---

## Device Routes

### 6. Get Installation Devices
**Endpoint**: `GET /installs/{installId}/devices`

**Description**: List all devices associated with an installation

**Path Parameters**:
- `installId` (required): Installation ID

**Response**:
```json
{
  "installationId": "INST-001",
  "deviceCount": 2,
  "devices": [...]
}
```

**Status**: ✅ Working
**Line**: 1355-1480

---

### 7. Sync Device to Habitation
**Endpoint**: `POST /installs/{installId}/devices?operation=sync`

**Description**: Create a device and link it to the habitation asset in Thingsboard

**Path Parameters**:
- `installId` (required): Installation ID

**Query Parameters**:
- `operation` (required): Must be `sync`

**Request Body**:
```json
{
  "deviceName": "INST-001_water_pump",
  "deviceType": "WaterPump"
}
```

**Response**:
```json
{
  "message": "Device synced successfully",
  "installationId": "INST-001",
  "device": {
    "id": "device-uuid",
    "name": "INST-001_water_pump",
    "type": "WaterPump"
  },
  "linkedToHabitation": true
}
```

**Status**: ✅ NEW - Recently Added
**Line**: 339-412

**Example cURL**:
```bash
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST-001/devices?operation=sync" \
  -H "Content-Type: application/json" \
  -d '{"deviceName": "INST-001_water_pump", "deviceType": "WaterPump"}'
```

---

### 8. Link Device to Installation
**Endpoint**: `POST /installs/{installId}/devices/link`

**Description**: Link an existing device to an installation

**Path Parameters**:
- `installId` (required): Installation ID

**Request Body**:
```json
{
  "deviceId": "device-uuid",
  "primaryDevice": true
}
```

**Response**:
```json
{
  "message": "Device linked successfully",
  "installationId": "INST-001",
  "deviceId": "device-uuid"
}
```

**Status**: ✅ Working
**Line**: 838-908

---

### 9. Unlink Device from Installation
**Endpoint**: `POST /installs/{installId}/devices/unlink`

**Description**: Unlink a device from an installation

**Path Parameters**:
- `installId` (required): Installation ID

**Request Body**:
```json
{
  "deviceId": "device-uuid"
}
```

**Response**:
```json
{
  "message": "Device unlinked successfully",
  "installationId": "INST-001",
  "deviceId": "device-uuid"
}
```

**Status**: ✅ Working
**Line**: 911-1000

---

### 10. Get Device Installation
**Endpoint**: `GET /devices/{deviceId}/install`

**Description**: Get the installation a device is associated with

**Path Parameters**:
- `deviceId` (required): Device ID

**Response**:
```json
{
  "deviceId": "device-uuid",
  "installationId": "INST-001"
}
```

**Status**: ✅ Working
**Line**: 1486-1560

---

## SIM Card Routes

### 11. Link SIM to Device
**Endpoint**: `POST /devices/{deviceId}/sim/link`

**Description**: Link a SIM card to a device

**Path Parameters**:
- `deviceId` (required): Device ID

**Request Body**:
```json
{
  "simId": "sim-uuid",
  "simNumber": "9876543210",
  "provider": "Jio"
}
```

**Response**:
```json
{
  "message": "SIM linked successfully",
  "deviceId": "device-uuid",
  "simId": "sim-uuid"
}
```

**Status**: ✅ Working
**Line**: 564-637

---

### 12. Unlink SIM from Device
**Endpoint**: `POST /devices/{deviceId}/sim/unlink`

**Description**: Unlink a SIM card from a device

**Path Parameters**:
- `deviceId` (required): Device ID

**Request Body**:
```json
{
  "simId": "sim-uuid"
}
```

**Response**:
```json
{
  "message": "SIM unlinked successfully",
  "deviceId": "device-uuid",
  "simId": "sim-uuid"
}
```

**Status**: ✅ Working
**Line**: 641-720

---

### 13. Get Device SIM Info
**Endpoint**: `GET /devices/{deviceId}/sim`

**Description**: Get SIM card information for a device

**Path Parameters**:
- `deviceId` (required): Device ID

**Response**:
```json
{
  "deviceId": "device-uuid",
  "sim": {
    "simId": "sim-uuid",
    "simNumber": "9876543210",
    "provider": "Jio"
  }
}
```

**Status**: ✅ Working
**Line**: 1043-1110

---

## Device Configuration Routes

### 14. Get Device Configs
**Endpoint**: `GET /devices/{deviceId}/configs`

**Description**: Get configuration details for a device

**Path Parameters**:
- `deviceId` (required): Device ID

**Response**:
```json
{
  "deviceId": "device-uuid",
  "configs": {...}
}
```

**Status**: ✅ Working
**Line**: 1115-1150

---

## Repair Routes

### 15. Create Repair Record
**Endpoint**: `POST /devices/{deviceId}/repairs`

**Description**: Create a new repair record for a device

**Path Parameters**:
- `deviceId` (required): Device ID

**Request Body**:
```json
{
  "repairType": "preventive",
  "issueDescription": "Routine maintenance",
  "technician": "John Doe",
  "repairDate": "2025-01-31",
  "cost": 500
}
```

**Response**:
```json
{
  "repairId": "repair-uuid",
  "deviceId": "device-uuid",
  "message": "Repair record created successfully"
}
```

**Status**: ✅ Working
**Line**: 724-775

---

### 16. Get Device Repairs
**Endpoint**: `GET /devices/{deviceId}/repairs`

**Description**: List all repair records for a device

**Path Parameters**:
- `deviceId` (required): Device ID

**Response**:
```json
{
  "deviceId": "device-uuid",
  "repairCount": 2,
  "repairs": [
    {
      "repairId": "repair-uuid",
      "repairType": "preventive",
      "issueDescription": "Routine maintenance",
      "technician": "John Doe",
      "repairDate": "2025-01-31",
      "cost": 500
    }
  ]
}
```

**Status**: ✅ Working
**Line**: 315-334

---

### 17. Update Repair Record
**Endpoint**: `PUT /devices/{deviceId}/repairs/{repairId}`

**Description**: Update an existing repair record

**Path Parameters**:
- `deviceId` (required): Device ID
- `repairId` (required): Repair ID

**Request Body**: Fields to update

**Response**: Updated repair object

**Status**: ✅ Working
**Line**: 781-835

---

## Route Summary Table

| Method | Path | Operation | Status | Line |
|--------|------|-----------|--------|------|
| POST | `/installs` | Create installation | ✅ | 416 |
| GET | `/installs` | List installations | ✅ | 1247 |
| GET | `/installs/{installId}` | Get installation | ✅ | 1156 |
| PUT | `/installs/{installId}` | Update installation | ✅ | 1722 |
| GET | `/installs/{installId}/history` | Installation history | ✅ | 1566 |
| GET | `/installs/{installId}/devices` | List devices | ✅ | 1356 |
| **POST** | **`/installs/{installId}/devices?operation=sync`** | **Sync device to habitation** | **✅ NEW** | **343** |
| POST | `/installs/{installId}/devices/link` | Link device | ✅ | 842 |
| POST | `/installs/{installId}/devices/unlink` | Unlink device | ✅ | 912 |
| GET | `/devices/{deviceId}/install` | Get device installation | ✅ | 1487 |
| POST | `/devices/{deviceId}/sim/link` | Link SIM to device | ✅ | 565 |
| POST | `/devices/{deviceId}/sim/unlink` | Unlink SIM from device | ✅ | 642 |
| GET | `/devices/{deviceId}/sim` | Get device SIM | ✅ | 1044 |
| GET | `/devices/{deviceId}/configs` | Get device configs | ✅ | 1116 |
| POST | `/devices/{deviceId}/repairs` | Create repair | ✅ | 725 |
| GET | `/devices/{deviceId}/repairs` | List repairs | ✅ | 315 |
| PUT | `/devices/{deviceId}/repairs/{repairId}` | Update repair | ✅ | 781 |

---

## Key Features

### Device Sync Endpoint (NEW)
The `/installs/{installId}/devices?operation=sync` endpoint provides a dedicated way to:
1. Create a device in Thingsboard
2. Link the device to the habitation asset
3. Return device details including Thingsboard ID

This is separate from installation creation, allowing devices to be synced independently.

### Error Handling
All endpoints return standardized error responses:
```json
{
  "statusCode": 400,
  "body": "Error message"
}
```

### Success Responses
All successful responses follow this format:
```json
{
  "statusCode": 200,
  "body": {...}
}
```

---

## Testing Device Sync

```bash
# 1. Create installation (syncs regions)
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs" \
  -H "Content-Type: application/json" \
  -d '{
    "InstallationId": "INST-TEST-001",
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "005",
    "Status": "active"
  }'

# 2. Sync device to habitation
curl -X POST "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST-TEST-001/devices?operation=sync" \
  -H "Content-Type: application/json" \
  -d '{
    "deviceName": "INST-TEST-001_water_pump",
    "deviceType": "WaterPump"
  }'

# 3. Get installation devices
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs/INST-TEST-001/devices"
```

---

## Next Steps

- [ ] Test device sync with various device types
- [ ] Implement device metadata syncing
- [ ] Add device telemetry endpoints
- [ ] Implement device status monitoring
