# API Sample Data & Examples

Base URL: `https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev`

---

## 1. DEVICES API

**Important:** All device operations require `EntityType` and `DeviceId` as mandatory parameters.

### GET /devices
**Description:** List all devices (EntityType defaults to "DEVICE" if not provided)  
**Query Parameters (Optional):**
- `EntityType` - Defaults to "DEVICE" for backward compatibility
- `DeviceType` - Filter by device type
- `Status` - Filter by status

**Request:**
```bash
# Without EntityType (defaults to DEVICE)
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices"

# With EntityType explicitly
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?EntityType=DEVICE"
```

**Response (200):**
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

### GET /devices with filters
**Description:** Get filtered devices by status or type  
**Request:**
```bash
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?EntityType=DEVICE&Status=Active"
```

**Response (200):**
```json
[
  {
    "id": "DEV001",
    "deviceId": "DEV001",
    "deviceName": "Water Motor Unit",
    "status": "Active"
  }
]
```

### GET /devices/{deviceId}/configs
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
**Description:** Create new device (EntityType and DeviceId required)  
**Note:** Duplicate prevention is enabled - attempting to create a device with an existing DeviceId will return 409 Conflict.

**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices \
  -H "Content-Type: application/json" \
  -d '{
    "EntityType": "DEVICE",
    "DeviceId": "DEV099",
    "DeviceName": "New Water Sensor",
    "DeviceType": "Water Monitor",
    "SerialNumber": "SN999888777",
    "Status": "available",
    "Location": "Warehouse A"
  }'
```

**Response (201):**
```json
{
  "created": {
    "PK": "DEVICE#DEV099",
    "SK": "META",
    "EntityType": "DEVICE",
    "DeviceId": "DEV099",
    "DeviceName": "New Water Sensor",
    "Status": "available",
    "Location": "Warehouse A",
    "CreatedDate": "2026-01-16T11:30:00Z",
    "UpdatedDate": "2026-01-16T11:30:00Z"
  }
}
```

**Response (409 - Duplicate):**
```json
{
  "error": "DEVICE with ID DEV099 already exists"
}
```

### PUT /devices
**Description:** Update existing device (EntityType and DeviceId required)  
**⚠️ Note:** Requires Terraform route `PUT /devices` to be configured  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices \
  -H "Content-Type: application/json" \
  -d '{
    "EntityType": "DEVICE",
    "DeviceId": "DEV099",
    "DeviceName": "Updated Water Sensor",
    "Status": "Active",
    "Location": "Site B"
  }'
```

**Response (200):**
```json
{
  "updated": {
    "EntityType": "DEVICE",
    "DeviceId": "DEV099",
    "DeviceName": "Updated Water Sensor",
    "Status": "Active",
    "Location": "Site B"
  }
}
```

**Response (404) - If Terraform route not configured:**
```json
{
  "message": "Not Found"
}
```

### DELETE /devices
**Description:** Delete device metadata (query parameters required)  
**⚠️ Note:** Requires Terraform route `DELETE /devices` to be configured  
**Request:**
```bash
curl -X DELETE "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices?DeviceId=DEV099&EntityType=DEVICE"
```

**Response (200):**
```json
{
  "deleted": {
    "PK": "DEVICE#DEV099",
    "SK": "META",
    "EntityType": "DEVICE"
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
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#CUSTOMER",
    "name": "ABC Corporation",
    "companyName": "ABC Corp Pvt Ltd",
    "email": "contact@abccorp.com",
    "phone": "9876543210",
    "gstin": "29ABCDE1234F1Z5",
    "isActive": true
  }
]
```

### GET /customers/{customerId}
**Description:** Get customer with nested contacts and addresses  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST001",
  "SK": "ENTITY#CUSTOMER",
  "name": "ABC Corporation",
  "companyName": "ABC Corp Pvt Ltd",
  "email": "contact@abccorp.com",
  "phone": "9876543210",
  "contacts": [
    {
      "PK": "CUSTOMER#CUST001",
      "SK": "ENTITY#CONTACT#C1",
      "firstName": "John",
      "lastName": "Doe",
      "email": "john@abccorp.com",
      "contactType": "primary"
    }
  ],
  "addresses": [
    {
      "PK": "CUSTOMER#CUST001",
      "SK": "ENTITY#ADDRESS#A2",
      "addressType": "ship_to",
      "addressLine1": "456 Industrial Area",
      "city": "Pune",
      "state": "Maharashtra",
      "pincode": "411001"
    }
  ]
}
```

### POST /customers
**Description:** Create new customer  
**Note:** Duplicate prevention is enabled - attempting to create a customer with an existing PK/SK will return 409 Conflict.

**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST999",
    "SK": "ENTITY#CUSTOMER",
    "entityType": "customer",
    "name": "New Company Ltd",
    "companyName": "New Company Private Limited",
    "email": "info@newcompany.com",
    "phone": "9123456789",
    "countryCode": "+91",
    "gstin": "29XXXXX1234X1Z5",
    "pan": "AAAAA9999A",
    "isActive": true,
    "createdBy": "admin"
  }'
```

**Response (201):**
```json
{
  "PK": "CUSTOMER#CUST999",
  "SK": "ENTITY#CUSTOMER",
  "entityType": "customer",
  "name": "New Company Ltd",
  "companyName": "New Company Private Limited",
  "email": "info@newcompany.com",
  "phone": "9123456789",
  "countryCode": "+91",
  "gstin": "29XXXXX1234X1Z5",
  "pan": "AAAAA9999A",
  "isActive": true,
  "createdBy": "admin"
}
```

**Response (409 - Duplicate):**
```json
{
  "error": "Customer CUSTOMER#CUST999 already exists"
}
```

### GET /customers/{customerId}/contacts
**Description:** List all contacts for a customer  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/contacts
```

**Response (200):**
```json
[
  {
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#CONTACT#C1",
    "firstName": "John",
    "lastName": "Doe",
    "email": "john@abccorp.com",
    "mobileNumber": "9876543210",
    "contactType": "primary",
    "isActive": true
  },
  {
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#CONTACT#C2",
    "firstName": "Jane",
    "lastName": "Smith",
    "email": "jane@abccorp.com",
    "contactType": "secondary",
    "isActive": true
  }
]
```

### GET /customers/{customerId}/contacts/{contactId}
**Description:** Get specific contact by ID  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/contacts/C1
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST001",
  "SK": "ENTITY#CONTACT#C1",
  "firstName": "John",
  "lastName": "Doe",
  "displayName": "John Doe",
  "email": "john@abccorp.com",
  "mobileNumber": "9876543210",
  "countryCode": "+91",
  "contactType": "primary",
  "isActive": true
}
```

### POST /customers/{customerId}/contacts
**Description:** Add contact to customer  
**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#CONTACT#C999",
    "entityType": "contact",
    "firstName": "Jane",
    "lastName": "Smith",
    "displayName": "Jane Smith",
    "email": "jane.smith@example.com",
    "mobileNumber": "9988776655",
    "countryCode": "+91",
    "contactType": "secondary",
    "isActive": true
  }'
```

**Response (200):**
```json
{
  "message": "Contact created successfully"
}
```

### PUT /customers/{customerId}/contacts/{contactId}
**Description:** Update contact  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/contacts/C999 \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#CONTACT#C999",
    "firstName": "Jane",
    "lastName": "Smith Updated",
    "mobileNumber": "9988776666",
    "contactType": "primary"
  }'
```

**Response (200):**
```json
{
  "message": "Contact updated successfully"
}
```

### DELETE /customers/{customerId}/contacts/{contactId}
**Description:** Delete contact  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/contacts/C999
```

**Response (200):**
```json
{
  "message": "Contact deleted"
}
```

### GET /customers/{customerId}/addresses
**Description:** List all addresses for a customer  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/addresses
```

**Response (200):**
```json
[
  {
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#ADDRESS#A1",
    "addressType": "billing",
    "addressLine1": "123 Business Street",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
    "country": "India",
    "isPrimary": true,
    "isActive": true
  },
  {
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#ADDRESS#A2",
    "addressType": "ship_to",
    "addressLine1": "456 Industrial Area",
    "city": "Pune",
    "state": "Maharashtra",
    "pincode": "411001",
    "country": "India",
    "isPrimary": false,
    "isActive": true
  }
]
```

### GET /customers/{customerId}/addresses/{addressId}
**Description:** Get specific address by ID  
**Request:**
```bash
curl -X GET https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/addresses/A2
```

**Response (200):**
```json
{
  "PK": "CUSTOMER#CUST001",
  "SK": "ENTITY#ADDRESS#A2",
  "addressType": "ship_to",
  "addressLine1": "456 Industrial Area",
  "addressLine2": "Near Highway",
  "city": "Pune",
  "state": "Maharashtra",
  "pincode": "411001",
  "country": "India",
  "isPrimary": false,
  "isActive": true
}
```

### POST /customers/{customerId}/addresses
**Description:** Add address to customer  
**Request:**
```bash
curl -X POST https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/addresses \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#ADDRESS#A999",
    "entityType": "address",
    "addressType": "billing",
    "addressLine1": "123 Business Park",
    "addressLine2": "Tower A, Floor 5",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
    "country": "India",
    "isPrimary": false,
    "isActive": true
  }'
```

**Response (200):**
```json
{
  "message": "Address created successfully"
}
```

### PUT /customers/{customerId}/addresses/{addressId}
**Description:** Update address  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/addresses/A999 \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST001",
    "SK": "ENTITY#ADDRESS#A999",
    "addressLine1": "123 Updated Business Park",
    "addressLine2": "Tower B, Floor 10",
    "isPrimary": true
  }'
```

**Response (200):**
```json
{
  "message": "Address updated successfully"
}
```

### DELETE /customers/{customerId}/addresses/{addressId}
**Description:** Delete address  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST001/addresses/A999
```

**Response (200):**
```json
{
  "message": "Address deleted"
}
```

### PUT /customers/{customerId}
**Description:** Update customer  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST999 \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "CUSTOMER#CUST999",
    "SK": "ENTITY#CUSTOMER",
    "companyName": "Updated Company Name",
    "phone": "9999999999"
  }'
```

**Response (200):**
```json
{
  "message": "Customer updated successfully"
}
```

### DELETE /customers/{customerId}
**Description:** Delete customer (cascade deletes contacts and addresses)  
**Request:**
```bash
curl -X DELETE https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/customers/CUST999
```

**Response (200):**
```json
{
  "message": "Customer and all related data deleted"
}
```

---

## 3. USERS API

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
    "updatedAt": "2024-01-10T10:00:00Z"
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
    "updatedAt": "2026-01-16T10:00:00Z"
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
    "PK": "SIM#SIM999",
    "SK": "META",
    "simId": "SIM999",
    "iccid": "8991234567890999999",
    "phoneNumber": "+919999999999",
    "provider": "Jio",
    "status": "inactive",
    "dataLimit": "5GB",
    "assignedDevice": null,
    "activatedDate": null,
    "expiryDate": "2027-01-01T00:00:00Z"
  }'
```

**Response (200):**
```json
{
  "message": "SIM card created successfully"
}
```

### PUT /simcards/{simId}
**Description:** Update SIM card  
**Request:**
```bash
curl -X PUT https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/simcards/SIM999 \
  -H "Content-Type: application/json" \
  -d '{
    "PK": "SIM#SIM999",
    "SK": "META",
    "status": "active",
    "assignedDevice": "DEV099",
    "activatedDate": "2026-01-16T10:00:00Z"
  }'
```

**Response (200):**
```json
{
  "message": "SIM card updated successfully"
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
    "UpdatedDate": "2026-01-17T10:00:00Z"
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
