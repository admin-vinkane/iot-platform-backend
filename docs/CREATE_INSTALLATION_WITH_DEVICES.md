# Create Installation API - Updated with Device Linking

## Endpoint
`POST /installs`

## Updated Behavior

### What Happens When Installation is Created (WITH Devices):

**1. Installation Record Created in DynamoDB**
- Stores installation metadata (StateId, DistrictId, etc.)

**2. Region Assets Synced to Thingsboard**
- Creates 5 asset types: State, District, Mandal, Village, Habitation
- Creates hierarchical relations between assets
- Stores asset IDs in installation record under `thingsboardAssets` field

**3. Devices Linked (IF PROVIDED)**
- ✅ Links each device to the installation in DynamoDB
- ✅ Links each device to the habitation asset in Thingsboard (automatically)
- Returns device linking results in response

---

## Request Body

### Minimal Request (No Devices)
```json
{
  "InstallationId": "INST-001",
  "StateId": "TS",
  "DistrictId": "HYD",
  "MandalId": "SRNAGAR",
  "VillageId": "VILLAGE001",
  "HabitationId": "005",
  "PrimaryDevice": "water",
  "Status": "active",
  "InstallationDate": "2026-01-31"
}
```

### Complete Request (WITH Device Linking - From UI)
```json
{
  "InstallationId": "INST-001",
  "StateId": "TS",
  "DistrictId": "HYD",
  "MandalId": "SRNAGAR",
  "VillageId": "VILLAGE001",
  "HabitationId": "005",
  "PrimaryDevice": "water",
  "Status": "active",
  "InstallationDate": "2026-01-31",
  "CustomerId": "CUST-001",
  "TemplateId": "TEMP-001",
  "WarrantyDate": "2027-01-31",
  "CreatedBy": "admin",
  "deviceIds": [
    "device-uuid-123",
    "device-uuid-456",
    "device-uuid-789"
  ]
}
```

**New Field**:
- `deviceIds`: Optional array of device IDs to link to the installation (passed from UI)

---

## Response (WITH Device Linking)

```json
{
  "statusCode": 201,
  "body": {
    "message": "Installation created successfully",
    "installation": {
      "InstallationId": "INST-001",
      "StateId": "TS",
      "DistrictId": "HYD",
      "MandalId": "SRNAGAR",
      "VillageId": "VILLAGE001",
      "HabitationId": "005",
      "PrimaryDevice": "water",
      "Status": "active",
      "InstallationDate": "2026-01-31",
      "EntityType": "INSTALL",
      "CreatedDate": "2026-01-31T16:18:16Z",
      "UpdatedDate": "2026-01-31T16:18:16Z",
      "CreatedBy": "admin",
      "stateName": "Telangana",
      "districtName": "Hyderabad",
      "mandalName": "Serilingampalli",
      "villageName": "Madhapur",
      "habitationName": "Default Habitation",
      "thingsboardStatus": "synced",
      "thingsboardAssets": {
        "state": {"id": "uuid", "name": "...", "code": "..."},
        "district": {"id": "uuid", "name": "...", "code": "..."},
        "mandal": {"id": "uuid", "name": "...", "code": "..."},
        "village": {"id": "uuid", "name": "...", "code": "..."},
        "habitation": {"id": "uuid", "name": "...", "code": "..."}
      },
      "deviceLinking": {
        "linked": [
          {"deviceId": "device-uuid-123", "status": "linked"},
          {"deviceId": "device-uuid-456", "status": "linked"}
        ],
        "errors": [
          {"deviceId": "device-uuid-789", "error": "Device not found"}
        ]
      }
    }
  }
}
```

**New Response Field**:
- `deviceLinking`: Contains linking results for all provided devices
  - `linked`: Array of successfully linked devices
  - `errors`: Array of devices that failed to link

---

## UI Integration Workflow

**Before (Separate Steps)**:
```
1. Create Installation Form → POST /installs → Get InstallationId
2. Link Devices Form → POST /installs/{id}/devices/link → Link each device
```

**After (Single Step)**:
```
1. Create Installation Form (with device selection) 
   → POST /installs (with deviceIds array)
   → Installation created + devices linked + response returned
```

---

## Device Linking Process (When deviceIds Provided)

```
POST /installs
{
  "InstallationId": "INST-001",
  ...region data...,
  "deviceIds": ["dev1", "dev2"]
}
    ↓
1. Create installation record in DynamoDB
    ↓
2. Sync regions to Thingsboard (5 assets + relations)
    ↓
3. For each device ID:
    ├─ Validate device exists in DynamoDB
    ├─ Link device to installation (DynamoDB transaction)
    ├─ Link device to habitation (Thingsboard relation) [non-blocking]
    └─ Collect results (success/error)
    ↓
4. Return response with:
    ├─ Installation details
    ├─ Thingsboard assets
    └─ Device linking results
```

---

## Error Handling

### Device Linking Errors (Non-Blocking)
- ✅ Installation creation succeeds even if device linking fails
- ✅ Device-not-found errors included in response
- ✅ Thingsboard linking failures don't block response
- ✅ All errors reported in `deviceLinking.errors` array

### Example: Partial Success
```json
{
  "deviceLinking": {
    "linked": [
      {"deviceId": "dev1", "status": "linked"},
      {"deviceId": "dev2", "status": "linked"}
    ],
    "errors": [
      {"deviceId": "dev3", "error": "Device not found"}
    ]
  }
}
```

---

## Backward Compatibility

✅ **Fully backward compatible**
- Requests WITHOUT `deviceIds` work exactly as before
- Device linking is optional
- Response includes `deviceLinking` object only when devices are linked

---

## Comparison: Two Approaches

| Scenario | Old Approach | New Approach |
|----------|-------------|--------------|
| Create installation only | 1 API call | 1 API call ✅ Same |
| Create + link devices | 1 + N API calls | 1 API call ✅ Fewer |
| UI workflow | 2 separate forms | 1 form ✅ Better UX |
| Error handling | Handle per call | Handle in response ✅ Better |
| Device errors | Can block | Non-blocking ✅ Better |

---

## Deployment Status

✅ **Lambda Deployed** - CodeSha: 1OVyC1rVaa3GVtgbZJCBp8iQ224rFA9kTWSZfd/uEIo=

Changes:
- ✅ Accept optional `deviceIds` array in request body
- ✅ Link each device after installation creation
- ✅ Automatically link device to habitation in Thingsboard
- ✅ Return device linking results in response
- ✅ Non-blocking device linking (errors don't fail installation)
- ✅ Fully backward compatible

---

## Testing

### Test 1: Create Installation Without Devices (Backward Compatible)
```bash
curl -X POST https://api/installs \
  -d '{
    "InstallationId": "INST-001",
    "StateId": "TS",
    ...
  }'

Response: Installation created, no deviceLinking in response
```

### Test 2: Create Installation WITH Devices (New Feature)
```bash
curl -X POST https://api/installs \
  -d '{
    "InstallationId": "INST-001",
    "StateId": "TS",
    ...
    "deviceIds": ["device-uuid-1", "device-uuid-2"]
  }'

Response: Installation created + devices linked, deviceLinking in response
```

---

## UI Integration Example

```javascript
async function createInstallation(formData) {
  const payload = {
    InstallationId: formData.installationId,
    StateId: formData.state,
    DistrictId: formData.district,
    MandalId: formData.mandal,
    VillageId: formData.village,
    HabitationId: formData.habitation,
    PrimaryDevice: formData.primaryDevice,
    Status: formData.status,
    InstallationDate: formData.installationDate,
    
    // NEW: Include selected devices
    deviceIds: formData.selectedDevices.map(d => d.deviceId)
  };
  
  const response = await fetch('/installs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  
  const result = await response.json();
  
  // Check results
  if (result.body.installation.deviceLinking) {
    console.log('Linked devices:', result.body.installation.deviceLinking.linked);
    console.log('Failed devices:', result.body.installation.deviceLinking.errors);
  }
  
  return result;
}
```

---

## Summary

✅ **Single-step installation creation with device linking**
- Create installation + sync regions + link devices in ONE API call
- Better UX - one form, one click
- Device linking errors don't block installation creation
- Fully backward compatible with existing code
- Ready for production

**Deployment Status**: ✅ Ready
