# Create Installation API - Review

## Endpoint
`POST /installs`

## Current Behavior

### What Happens When Installation is Created:

**1. Installation Record Created in DynamoDB**
- Stores installation metadata (StateId, DistrictId, etc.)
- Does NOT store any device information

**2. Region Assets Synced to Thingsboard**
- Creates 5 asset types: State, District, Mandal, Village, Habitation
- Creates hierarchical relations between assets (State→District→Mandal→Village→Habitation)
- Stores asset IDs in installation record under `thingsboardAssets` field

**3. No Device Linking Happens**
- ❌ Does NOT link any devices to the installation
- ❌ Does NOT link any devices to the habitation asset in Thingsboard

---

## Request Body

```json
{
  "InstallationId": "INST-001",
  "StateId": "TS",
  "DistrictId": "HYD",
  "MandalId": "SRNAGAR",
  "VillageId": "VILLAGE001",
  "HabitationId": "005",
  "PrimaryDevice": "water",          // Required: "water", "chlorine", or "none"
  "Status": "active",                 // Required: "active" or "inactive"
  "InstallationDate": "2026-01-31",   // Required
  "CustomerId": "CUST-001",           // Optional
  "TemplateId": "TEMP-001",           // Optional
  "WarrantyDate": "2027-01-31",       // Optional
  "CreatedBy": "admin"                // Optional
}
```

**Note**: There is NO device field or parameter in the request

---

## Response

```json
{
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
    }
  }
}
```

---

## Device Linking - Separate Process

Devices are linked AFTER installation creation, not as part of it.

### Step 1: Create Installation
```bash
curl -X POST https://api/installs \
  -d '{
    "InstallationId": "INST-001",
    "StateId": "TS",
    ...
  }'
```

### Step 2: Link Devices (Separate Call)
```bash
curl -X POST https://api/installs/INST-001/devices/link \
  -d '{
    "deviceId": "device-uuid-123"
  }'
```

When device linking is successful:
- ✅ Device linked to installation in DynamoDB
- ✅ Device linked to habitation asset in Thingsboard (automatically)

---

## Analysis: Should Devices be Linked During Installation Creation?

### Current Approach (Separate Steps):
```
1. Create Installation + sync regions
2. Link devices one at a time (or in batch)
```

### Pros:
- ✅ Installations can be created without knowing devices upfront
- ✅ Devices are managed externally (not part of installation creation)
- ✅ Flexibility to link devices at any time
- ✅ Separates concerns (installation creation vs device management)

### Cons:
- ❌ Requires multiple API calls
- ❌ Two-step process instead of one

### Alternative Approach (Link During Creation):
Could accept device IDs in installation creation request:
```json
{
  "InstallationId": "INST-001",
  "StateId": "TS",
  ...
  "DeviceIds": ["device-uuid-1", "device-uuid-2"]  // NEW
}
```

---

## Recommendation

### Current Design is Correct ✅

The separation is intentional and proper because:

1. **Device Lifecycle is External**
   - Devices are created/managed outside this API
   - Installation API shouldn't depend on device creation

2. **Clean Architecture**
   - Installation creation = setup regions + assets in Thingsboard
   - Device linking = associate existing devices

3. **Flexibility**
   - Installations can exist without devices
   - Devices can be linked/unlinked independently

4. **Proper Separation of Concerns**
   - Device management API handles device creation
   - Installation API handles installation + region hierarchy
   - Linking API connects them

---

## Current Workflow

```
EXTERNAL SYSTEM
    │
    ├─ Create devices (outside this API)
    │
INSTALLATION API
    │
    ├─ POST /installs
    │  └─ Creates installation + syncs region hierarchy
    │
    └─ POST /installs/{id}/devices/link
       └─ Links existing devices + links to habitation
```

---

## Summary

| Aspect | Status |
|--------|--------|
| Installation creation | ✅ Works correctly |
| Device fields in request | ❌ None (not needed) |
| Device linking on creation | ❌ Not done (intentional) |
| Device linking on separate call | ✅ Yes, via /devices/link |
| Architecture | ✅ Clean separation |

**Conclusion**: The Create Installation API is designed correctly. Device linking is intentionally a separate operation, not part of installation creation.
