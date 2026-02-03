# Regions API - Query Guide

## Overview
The Regions API provides hierarchical location data with support for States, Districts, Mandals, Villages, and Habitations. The hierarchy structure is:

```
STATE 
  ├── DISTRICT (under STATE)
  │    ├── MANDAL (under DISTRICT)
  │    │    └── VILLAGE (under MANDAL)
  │    │         └── HABITATION (under VILLAGE)
```

---

## Available Endpoints

### 1. Get All Regions by Type
**Endpoint**: `GET /regions`

**Query Parameters**:
- `regionType` (required): One of `STATE`, `DISTRICT`, `MANDAL`, `VILLAGE`, `HABITATION`

**Examples**:

#### Get all states
```bash
curl "https://api.example.com/dev/regions?regionType=STATE"
```

**Response**:
```json
[
  {
    "id": "TS",
    "code": "TS",
    "name": "Telangana",
    "isActive": true,
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z"
  },
  {
    "id": "AP",
    "code": "AP",
    "name": "Andhra Pradesh",
    "isActive": true,
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z"
  }
]
```

---

### 2. Get Children by Parent Region Code
**Endpoint**: `GET /regions`

**Query Parameters**:
- `regionType` (required): `DISTRICT`, `MANDAL`, `VILLAGE`, or `HABITATION`
- `regionCode` (required): The code of the parent region

**Examples**:

#### Get all districts in Telangana (TS)
```bash
curl "https://api.example.com/dev/regions?regionType=DISTRICT&regionCode=TS"
```

**Response**:
```json
[
  {
    "id": "HYD",
    "code": "HYD",
    "name": "Hyderabad",
    "stateCode": "TS",
    "isActive": true,
    "createdAt": "2025-01-01T00:00:00Z"
  },
  {
    "id": "RNG",
    "code": "RNG",
    "name": "Rangareddy",
    "stateCode": "TS",
    "isActive": true,
    "createdAt": "2025-01-01T00:00:00Z"
  }
]
```

#### Get all mandals in Hyderabad district
```bash
curl "https://api.example.com/dev/regions?regionType=MANDAL&regionCode=HYD"
```

**Response**:
```json
[
  {
    "id": "SRNAGAR",
    "code": "SRNAGAR",
    "name": "Serilingampalli",
    "stateCode": "TS",
    "code": "HYD",
    "isActive": true
  },
  {
    "id": "UPPAL",
    "code": "UPPAL",
    "name": "Uppal",
    "stateCode": "TS",
    "code": "HYD",
    "isActive": true
  }
]
```

#### Get all villages in a mandal
```bash
curl "https://api.example.com/dev/regions?regionType=VILLAGE&regionCode=SRNAGAR"
```

**Response**:
```json
[
  {
    "id": "VILLAGE001",
    "code": "VILLAGE001",
    "name": "Madhapur",
    "stateCode": "TS",
    "code": "HYD",
    "code": "SRNAGAR",
    "population": 50000,
    "pincode": "500081",
    "isActive": true
  }
]
```

---

### 3. Get Complete Hierarchy
**Endpoint**: `GET /hierarchy`

**Query Parameters**: None required

**Description**: Returns the entire regional hierarchy organized by state, with all districts, mandals, and villages nested underneath.

**Request**:
```bash
curl "https://api.example.com/dev/hierarchy"
```

**Response**:
```json
{
  "states": [
    {
      "code": "AP",
      "name": "Andhra Pradesh"
    },
    {
      "code": "TS",
      "name": "Telangana"
    }
  ],
  "districts": {
    "TS": [
      {
        "code": "HYD",
        "name": "Hyderabad"
      },
      {
        "code": "RNG",
        "name": "Rangareddy"
      }
    ],
    "AP": [
      {
        "code": "VJY",
        "name": "Vijaywada"
      }
    ]
  },
  "mandals": {
    "HYD": [
      {
        "code": "SRNAGAR",
        "name": "Serilingampalli"
      },
      {
        "code": "UPPAL",
        "name": "Uppal"
      }
    ],
    "RNG": [
      {
        "code": "CHEVELLA",
        "name": "Chevella"
      }
    ]
  },
  "villages": {
    "SRNAGAR": [
      {
        "code": "VILLAGE001",
        "name": "Madhapur",
        "population": 50000,
        "pincode": "500081"
      },
      {
        "code": "VILLAGE002",
        "name": "Gachibowli",
        "population": 45000,
        "pincode": "500082"
      }
    ],
    "CHEVELLA": [
      {
        "code": "VILLAGE003",
        "name": "Chevella Town",
        "population": 30000,
        "pincode": "501503"
      }
    ]
  }
}
```

---

## Usage Scenarios

### Scenario 1: Populate State Dropdown
```bash
curl "https://api.example.com/dev/regions?regionType=STATE"
```
Returns all available states for initial dropdown.

---

### Scenario 2: Get Districts for Selected State
When user selects state "TS" (Telangana):
```bash
curl "https://api.example.com/dev/regions?regionType=DISTRICT&regionCode=TS"
```
Returns all districts in Telangana.

---

### Scenario 3: Get Mandals for Selected District
When user selects district "HYD" (Hyderabad):
```bash
curl "https://api.example.com/dev/regions?regionType=MANDAL&regionCode=HYD"
```
Returns all mandals in Hyderabad district.

---

### Scenario 4: Get Villages for Selected Mandal
When user selects mandal "SRNAGAR":
```bash
curl "https://api.example.com/dev/regions?regionType=VILLAGE&regionCode=SRNAGAR"
```
Returns all villages in that mandal with metadata (population, pincode).

---

### Scenario 5: Frontend Initialization - Get Complete Hierarchy
For React dropdowns that need all data upfront:
```bash
curl "https://api.example.com/dev/hierarchy"
```
Returns complete hierarchy for client-side filtering.

---

## Query Parameter Combinations

### Valid Combinations ✅

| regionType | regionCode | Description | Example |
|-----------|-----------|-------------|---------|
| STATE | - | Get all states | `?regionType=STATE` |
| DISTRICT | STATE_CODE | Get districts in state | `?regionType=DISTRICT&regionCode=TS` |
| MANDAL | DISTRICT_CODE | Get mandals in district | `?regionType=MANDAL&regionCode=HYD` |
| VILLAGE | MANDAL_CODE | Get villages in mandal | `?regionType=VILLAGE&regionCode=SRNAGAR` |
| HABITATION | VILLAGE_CODE | Get habitations in village | `?regionType=HABITATION&regionCode=VILLAGE001` |

### Invalid Combinations ❌

| Request | Error |
|---------|-------|
| `?regionType=STATE&regionCode=TS` | RegionCode not applicable for STATE queries |
| `?regionType=DISTRICT` (no regionCode) | Works but returns ALL districts (expensive) |
| `?regionType=INVALID` | Invalid regiontype error |
| No `regionType` parameter | Missing regiontype parameter error |

---

## Response Format

### Success Response (200 OK)
```json
{
  "statusCode": 200,
  "body": [
    {
      "id": "...",
      "code": "...",
      "name": "...",
      "stateCode": "...",
      "isActive": true,
      "createdAt": "...",
      "updatedAt": "..."
    }
  ]
}
```

### Error Responses

**Missing Parameter (400)**:
```json
{
  "statusCode": 400,
  "body": "Missing regiontype parameter"
}
```

**Invalid Region Type (400)**:
```json
{
  "statusCode": 400,
  "body": "Invalid regiontype. Must be one of: STATE, DISTRICT, MANDAL, VILLAGE, HABITATION"
}
```

**Not Found (404)**:
```json
{
  "statusCode": 404,
  "body": "No DISTRICT found for STATE with code TS"
}
```

---

## Best Practices

### 1. Use Hierarchy Endpoint for Initialization
```javascript
// Instead of 5 sequential API calls, get everything at once
fetch('/hierarchy')
  .then(r => r.json())
  .then(data => {
    setStates(data.states);
    setDistrictsByState(data.districts);
    setMandalsByDistrict(data.mandals);
    setVillagesByMandal(data.villages);
  });
```

### 2. Use regionCode Queries for Dependent Dropdowns
```javascript
// When state changes
const handleStateChange = (stateCode) => {
  fetch(`/regions?regionType=DISTRICT&regionCode=${stateCode}`)
    .then(r => r.json())
    .then(districts => setDistricts(districts));
};
```

### 3. Cache the Hierarchy
The hierarchy data is relatively static, so cache it client-side:
```javascript
const getHierarchy = async () => {
  if (window.hierarchyCache) {
    return window.hierarchyCache;
  }
  const data = await fetch('/hierarchy').then(r => r.json());
  window.hierarchyCache = data;
  return data;
};
```

---

## Regional Codes Reference

Common state codes:
- `TS` = Telangana
- `AP` = Andhra Pradesh
- `KA` = Karnataka
- `MH` = Maharashtra
- `UP` = Uttar Pradesh
- `DL` = Delhi
- etc.

Common district codes:
- `HYD` = Hyderabad
- `RNG` = Rangareddy
- `WGL` = Warangal
- etc.

---

## Summary

| Task | Endpoint | Query Parameters |
|------|----------|------------------|
| Get all states | `/regions` | `regionType=STATE` |
| Get districts for state | `/regions` | `regionType=DISTRICT&regionCode={STATE_CODE}` |
| Get mandals for district | `/regions` | `regionType=MANDAL&regionCode={DISTRICT_CODE}` |
| Get villages for mandal | `/regions` | `regionType=VILLAGE&regionCode={MANDAL_CODE}` |
| Get complete hierarchy | `/hierarchy` | (none) |

