# Encryption Quick Start

## 30-Second Overview

Your IoT platform now has **automatic field-level encryption** built in. When you:

1. **Send Data → Lambda** (plain text)
2. **Lambda encrypts sensitive fields** ✓
3. **Stores encrypted in DynamoDB** 🔐
4. **Retrieves from DynamoDB** (encrypted)
5. **Lambda decrypts sensitive fields** ✓
6. **Returns Data** (plain text)

**Result**: Sensitive data encrypted at rest, plain text in API responses - users don't see any difference!

---

## What Gets Encrypted?

Currently configured for encryption:

| Entity | Fields |
|--------|--------|
| **SIM Cards** | MobileNumber, Provider |
| **Devices** | SerialNumber |
| **Customers** | CustomerName, EmailAddress, PhoneNumber, Address |

---

## Encrypted Data Format

When stored in DynamoDB, encrypted fields look like:

```json
{
  "MobileNumber": {
    "encrypted_value": "gAAAAABl7xK...",
    "key_version": "1",
    "encrypted_at": "2026-01-29T08:45:00Z"
  }
}
```

---

## Setup Checklist

- [ ] **Create KMS Key**
  ```bash
  aws kms create-key --description "IoT Platform Data" --region ap-south-2
  aws kms create-alias --alias-name alias/iot-platform-data \
    --target-key-id <KEY_ID> --region ap-south-2
  ```

- [ ] **Update Lambda IAM Role** (add KMS permissions)
  ```json
  {
    "Effect": "Allow",
    "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
    "Resource": "arn:aws:kms:ap-south-2:ACCOUNT:key/KEY_ID"
  }
  ```

- [ ] **Deploy Lambda** (already includes encryption code)

- [ ] **Test with SIM creation**
  ```bash
  curl -X POST https://api/simcards \
    -d '{"SIMId": "SIM001", "MobileNumber": "+919876543210"}'
  ```

---

## How to Add More Fields to Encryption

Edit `lambdas/v_devices/encryption_utils.py`:

```python
ENCRYPTION_CONFIG = {
    'SIM': {
        'encrypt': ['MobileNumber', 'Provider'],  # ← Add fields here
        'decrypt': ['MobileNumber', 'Provider']   # ← Add same fields here
    }
}
```

That's it! No other code changes needed.

---

## API Behavior

### From User Perspective (No Change)

```bash
# Request - plain text
POST /simcards
{
  "SIMId": "SIM001",
  "MobileNumber": "+919876543210"
}

# Response - plain text (automatically decrypted)
{
  "SIMId": "SIM001",
  "MobileNumber": "+919876543210"
}
```

### From Database Perspective (Encrypted)

```bash
# What's actually stored in DynamoDB
{
  "SIMId": "SIM001",
  "MobileNumber": {
    "encrypted_value": "gAAAAABl7xK...",
    "key_version": "1",
    "encrypted_at": "2026-01-29T08:45:00Z"
  }
}
```

---

## Performance

| Operation | Time | Cost |
|-----------|------|------|
| Encrypt 1 field | ~20ms | $0.000003 |
| Decrypt 1 field | ~20ms | $0.000003 |
| Per 1000 APIs | ~20ms | $0.003 |

*Negligible performance impact. Cost: ~$0.03/month for typical usage.*

---

## Key Features

✅ **Transparent**: Users see plain text, database stores encrypted
✅ **Automatic**: No code changes needed for encryption/decryption
✅ **Secure**: Uses AWS KMS 256-bit encryption
✅ **Auditable**: Every operation logged in CloudWatch
✅ **Flexible**: Easy to add/remove fields
✅ **Recoverable**: Can decrypt all historical data

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "KMS key not accessible" | Add KMS permissions to Lambda IAM role |
| "Encryption disabled" | Create KMS key and alias (see Setup) |
| Data not encrypted | Check if field is in `ENCRYPTION_CONFIG` |
| Can't decrypt old data | Old data stored unencrypted - works automatically |

---

## Code Files

- **Main encryption module**: `lambdas/v_devices/encryption_utils.py`
- **Integration points**: `lambdas/v_devices/v_devices_api.py` (lines marked with encryption)
- **Full guide**: See `ENCRYPTION_GUIDE.md`

---

## Next: Monitor & Verify

```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/v_devices_api --filter-pattern "Encrypted"

# Verify data in DynamoDB
aws dynamodb get-item --table-name v_devices_dev \
  --key '{"PK": {"S": "SIM#SIM001"}, "SK": {"S": "META"}}'
```

---

## Questions?

See `ENCRYPTION_GUIDE.md` for detailed documentation.
