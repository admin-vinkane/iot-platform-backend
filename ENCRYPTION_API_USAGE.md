# Encryption API Usage Guide

## Overview
The API now supports field-level encryption with AWS KMS. **By default, all sensitive fields are returned ENCRYPTED** (except when KMS key doesn't exist). You must pass `?decrypt=true` to get plaintext data.

## Default Behavior (No Query Parameter)
```bash
# Returns encrypted data by default
curl "https://api.example.com/devices/DEV003"

# Response includes encrypted fields:
{
  "SerialNumber": {
    "encrypted_value": "AQIDAHhz5K...",
    "key_version": "1",
    "encrypted_at": "2026-01-29T10:00:00.000Z"
  },
  "LinkedSIM": {
    "simDetails": {
      "MobileNumber": {
        "encrypted_value": "BQKEAIlm9Z...",
        ...
      },
      "Provider": {
        "encrypted_value": "CQOFAJno0a...",
        ...
      }
    }
  }
}
```

## Requesting Decrypted Data
```bash
# Returns decrypted plaintext data
curl "https://api.example.com/devices/DEV003?decrypt=true"

# Response includes plaintext fields:
{
  "SerialNumber": "SN123456",
  "LinkedSIM": {
    "simDetails": {
      "MobileNumber": "9876543210",
      "Provider": "Airtel"
    }
  }
}
```

## API Endpoints with Encryption Support

### GET /devices (list all devices)
```bash
# Default: Returns encrypted data
curl "https://api.example.com/devices"

# With decryption: Returns plaintext
curl "https://api.example.com/devices?decrypt=true"

# With filters AND decryption
curl "https://api.example.com/devices?Status=Active&decrypt=true"
```

### GET /devices/{deviceId} (get single device)
```bash
# Default: Returns encrypted data
curl "https://api.example.com/devices/DEV003"

# With decryption: Returns plaintext
curl "https://api.example.com/devices/DEV003?decrypt=true"
```

### GET /devices/{deviceId}/sim (get linked SIM)
```bash
# Default: Returns encrypted SIM data
curl "https://api.example.com/devices/DEV003/sim"

# With decryption: Returns plaintext SIM data
curl "https://api.example.com/devices/DEV003/sim?decrypt=true"
```

## Encrypted Fields by Entity Type

### DEVICE
- `SerialNumber` - Encrypted by default

### SIM
- `MobileNumber` - Encrypted by default
- `Provider` - Encrypted by default

### CUSTOMER
- `CustomerName` - Encrypted by default
- `EmailAddress` - Encrypted by default
- `PhoneNumber` - Encrypted by default
- `Address` - Encrypted by default

## Use Cases

### Use Case 1: Normal API Consumer (Web/Mobile App)
**Requirement:** Show plaintext data to users
```bash
# Request decrypted data for UI display
curl "https://api.example.com/devices/DEV003?decrypt=true"
```

### Use Case 2: Inter-Service Communication
**Requirement:** Keep data encrypted in transit
```bash
# Don't pass decrypt parameter - data stays encrypted
curl "https://api.example.com/devices/DEV003"

# Service receives encrypted data, stores/forwards securely
# Only decrypts locally when needed with its own KMS access
```

### Use Case 3: Cross-Server Sync
**Requirement:** Server B needs to sync devices from Server A
```bash
# Server A returns encrypted data (default)
curl "https://server-a.api.com/devices?Status=Active"

# Server B receives encrypted payload and stores as-is
# Server B can decrypt if it has access to same KMS key
# Or keeps data encrypted for privacy
```

## Implementation Details

### Encryption Flow (Write Path)
1. User creates/updates device via API
2. Before saving to DynamoDB: `prepare_item_for_storage(item, "DEVICE")`
3. Specified fields are encrypted using AWS KMS
4. Encrypted item stored in DynamoDB

### Decryption Flow (Read Path)
1. User requests device via GET API
2. Lambda checks `?decrypt` query parameter
3. Retrieve item from DynamoDB (encrypted)
4. Apply: `prepare_item_for_response(item, "DEVICE", decrypt=should_decrypt)`
   - If `decrypt=true`: Decrypt fields using KMS
   - If `decrypt=false` (default): Return encrypted data as-is
5. Return response to caller

### Graceful Degradation
If KMS key is not accessible:
- Encryption/decryption gracefully fails
- Fields are stored/returned as plaintext
- Application continues to function
- Logged warnings help identify KMS issues

## KMS Setup Required

To activate actual encryption, create the KMS key:

```bash
# 1. Create KMS key
aws kms create-key \
  --description "IoT Platform Data Encryption" \
  --region ap-south-2

# 2. Create alias
aws kms create-alias \
  --alias-name alias/iot-platform-data \
  --target-key-id <KEY_ID> \
  --region ap-south-2

# 3. Update Lambda IAM role with KMS permissions
# Add to role policy:
{
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt",
    "kms:Encrypt",
    "kms:DescribeKey"
  ],
  "Resource": "arn:aws:kms:ap-south-2:ACCOUNT_ID:key/KEY_ID"
}
```

## Testing

### Test 1: Verify Default Encryption
```bash
curl "https://api.example.com/devices/DEV003" | jq '.SerialNumber'

# Should show encrypted structure (once KMS key exists):
# {
#   "encrypted_value": "AQIDAHhz5K...",
#   "key_version": "1",
#   "encrypted_at": "2026-01-29T10:00:00.000Z"
# }
```

### Test 2: Verify Decryption
```bash
curl "https://api.example.com/devices/DEV003?decrypt=true" | jq '.SerialNumber'

# Should show plaintext value:
# "SN123456"
```

### Test 3: List with Mixed Data
```bash
curl "https://api.example.com/devices?decrypt=false" | jq '.[0].LinkedSIM.simDetails'

# Should show encrypted SIM data
```

## Security Notes

1. **Default is Secure**: By default, data is encrypted in responses
2. **Explicit Decryption**: Must explicitly request `?decrypt=true` for plaintext
3. **Server-to-Server**: Inter-service communication can work with encrypted data
4. **CloudWatch**: All encryption/decryption operations are logged
5. **KMS Audit**: AWS KMS tracks all key usage for compliance

## FAQ

**Q: Is data encrypted at rest?**
A: Yes - sensitive fields are encrypted before storing in DynamoDB

**Q: Can I get encrypted data even if KMS key exists?**
A: Yes - simply don't pass `?decrypt=true`, encrypted data is returned

**Q: What if decrypt=true but KMS key fails?**
A: Decryption fails gracefully, encrypted data is returned as-is

**Q: How do different servers handle encryption?**
A: Each server can:
- Request encrypted data (default) and store securely
- Request decrypted data with `?decrypt=true` if needed
- Only decrypt if it has KMS key access
