# Data Encryption Guide

## Overview

This guide explains how to use the built-in encryption system for protecting sensitive data in your IoT platform. The system automatically encrypts data before storing it in DynamoDB and decrypts it when retrieving via APIs.

## How It Works

### Architecture

```
API Request → Lambda Handler
                    ↓
         Encrypt Sensitive Fields
                    ↓
         Store to DynamoDB
                    ↓
         Retrieve from DynamoDB
                    ↓
         Decrypt Sensitive Fields
                    ↓
API Response
```

### Key Management

- **KMS Key**: AWS Key Management Service handles all encryption keys
- **Key Alias**: `alias/iot-platform-data` (create this in KMS)
- **Encryption**: Fields are encrypted with 256-bit KMS keys
- **Storage Format**: Encrypted data stored as base64-encoded ciphertext with metadata

## Setup Instructions

### 1. Create KMS Key (One-time setup)

```bash
# Create the KMS key
aws kms create-key \
  --description "IoT Platform Data Encryption Key" \
  --region ap-south-2

# Create alias (note the KEY_ID from above output)
aws kms create-alias \
  --alias-name alias/iot-platform-data \
  --target-key-id <KEY_ID> \
  --region ap-south-2
```

### 2. Update Lambda IAM Role

Add the following permissions to your Lambda execution role:

```json
{
  "Sid": "KMSEncryptDecrypt",
  "Effect": "Allow",
  "Action": [
    "kms:Encrypt",
    "kms:Decrypt",
    "kms:GenerateDataKey",
    "kms:DescribeKey"
  ],
  "Resource": "arn:aws:kms:ap-south-2:ACCOUNT_ID:key/KEY_ID"
}
```

### 3. Configuration

Edit `encryption_utils.py` to configure which fields to encrypt:

```python
ENCRYPTION_CONFIG = {
    'SIM': {
        'encrypt': ['MobileNumber', 'Provider'],
        'decrypt': ['MobileNumber', 'Provider']
    },
    'DEVICE': {
        'encrypt': ['SerialNumber'],
        'decrypt': ['SerialNumber']
    },
    'CUSTOMER': {
        'encrypt': ['CustomerName', 'EmailAddress', 'PhoneNumber'],
        'decrypt': ['CustomerName', 'EmailAddress', 'PhoneNumber']
    }
}
```

## Usage Examples

### Example 1: Create SIM Card (with encrypted phone number)

**Request:**
```bash
curl -X POST "https://api.endpoint/dev/simcards" \
  -H "Content-Type: application/json" \
  -d '{
    "SIMId": "SIM001",
    "MobileNumber": "+919876543210",
    "Provider": "Airtel",
    "Plan": "IoT Data 10GB",
    "Status": "active"
  }'
```

**What happens internally:**
1. Lambda receives the request with plain phone number
2. `prepare_item_for_storage()` encrypts `MobileNumber` field
3. Encrypted data stored in DynamoDB:
   ```json
   {
     "MobileNumber": {
       "encrypted_value": "gAAAAABl7xK...",
       "key_version": "1",
       "encrypted_at": "2026-01-29T08:45:00.000000Z"
     }
   }
   ```

**Response:**
```json
{
  "message": "SIM created successfully",
  "simcard": {
    "SIMId": "SIM001",
    "MobileNumber": "+919876543210",
    "Provider": "Airtel",
    "Plan": "IoT Data 10GB"
  }
}
```

**What happened in response:**
1. Lambda retrieved encrypted data from DynamoDB
2. `prepare_item_for_response()` decrypted `MobileNumber` field
3. Response includes plain phone number (decrypted automatically)

### Example 2: Get SIM Card (automatic decryption)

**Request:**
```bash
curl -X GET "https://api.endpoint/dev/simcards/SIM001"
```

**Response:**
```json
{
  "SIMId": "SIM001",
  "MobileNumber": "+919876543210",
  "Provider": "Airtel",
  "Plan": "IoT Data 10GB"
}
```

The phone number is automatically decrypted before sending in the response.

### Example 3: List SIM Cards (batch decryption)

**Request:**
```bash
curl -X GET "https://api.endpoint/dev/simcards"
```

**Response:**
```json
[
  {
    "SIMId": "SIM001",
    "MobileNumber": "+919876543210",
    "Provider": "Airtel"
  },
  {
    "SIMId": "SIM002",
    "MobileNumber": "+919876543211",
    "Provider": "Jio"
  }
]
```

All phone numbers are automatically decrypted in the response.

## API Integration Points

### For Lambda Developers

When storing data:
```python
# Before storing to DynamoDB
encrypted_item = prepare_item_for_storage(data, 'SIM')
table.put_item(Item=encrypted_item)
```

When retrieving data:
```python
# After retrieving from DynamoDB
response = table.get_item(Key={"PK": "SIM#SIM001", "SK": "META"})
if "Item" in response:
    decrypted_item = prepare_item_for_response(response["Item"], 'SIM')
    return decrypted_item
```

### Transparent Operation

**Important:** Encryption/Decryption is handled transparently. You can:
1. Add fields to `ENCRYPTION_CONFIG`
2. No other changes needed - existing code works automatically

## Security Features

✅ **End-to-End Encryption**: Data encrypted before leaving Lambda, decrypted only when needed
✅ **Key Rotation**: AWS KMS handles automatic annual key rotation
✅ **Audit Trail**: All encryption/decryption logged in CloudWatch
✅ **Per-Field Metadata**: Tracks when each field was encrypted and with which key version
✅ **Graceful Degradation**: If KMS is unavailable, data is stored unencrypted with warning

## Monitoring & Debugging

### View Encryption Logs

```bash
# View CloudWatch logs for encryption operations
aws logs tail /aws/lambda/v_devices_api --follow --filter-pattern "Encrypted"
```

### Check KMS Key Usage

```bash
# View KMS key usage statistics
aws kms get-key-rotation-status \
  --key-id alias/iot-platform-data \
  --region ap-south-2
```

### Verify Encrypted Data

```bash
# Query DynamoDB to see encrypted format
aws dynamodb get-item \
  --table-name v_devices_dev \
  --key '{"PK": {"S": "SIM#SIM001"}, "SK": {"S": "META"}}' \
  --region ap-south-2
```

You'll see encrypted data in DynamoDB:
```json
{
  "MobileNumber": {
    "M": {
      "encrypted_value": {
        "S": "gAAAAABl7xK..."
      },
      "key_version": {
        "S": "1"
      },
      "encrypted_at": {
        "S": "2026-01-29T08:45:00.000000Z"
      }
    }
  }
}
```

## Performance Impact

- **Encryption overhead**: ~10-50ms per request (depends on number of fields)
- **KMS cost**: $0.03 per 10,000 API calls
- **Data size**: Encrypted data is ~25-50% larger due to base64 encoding

## Troubleshooting

### Issue: "KMS key not accessible"

**Cause**: Lambda role doesn't have KMS permissions

**Fix**:
```bash
# Add to Lambda IAM role policy
aws iam put-role-policy \
  --role-name v_devices_lambda_role \
  --policy-name kms-encrypt-decrypt \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
      "Resource": "arn:aws:kms:ap-south-2:ACCOUNT:key/KEY_ID"
    }]
  }'
```

### Issue: "Encryption disabled" warning

**Cause**: KMS key alias doesn't exist

**Fix**:
```bash
# Create KMS key and alias (see Setup Instructions)
aws kms create-key --description "IoT Platform"
aws kms create-alias --alias-name alias/iot-platform-data --target-key-id <KEY_ID>
```

### Issue: Decryption failing for existing data

**Cause**: Data stored before encryption was enabled

**Fix**: Data stored unencrypted won't have the encrypted format. The `decrypt_field()` function handles this gracefully and returns original values.

## Best Practices

1. **Add fields incrementally**: Start with highest priority fields (phone numbers, emails)
2. **Document encrypted fields**: Keep `ENCRYPTION_CONFIG` up-to-date
3. **Monitor KMS usage**: Watch CloudWatch metrics for encryption failures
4. **Regular key rotation**: Enable automatic key rotation in KMS
5. **Test decryption**: Verify decryption works before deploying
6. **Backup encrypted data**: Encrypted data is safe but keep KMS key safe
7. **Audit logging**: Enable CloudTrail for KMS key access audit

## Next Steps

1. ✅ Create KMS key (see Setup Instructions above)
2. ✅ Add KMS permissions to Lambda IAM role
3. ✅ Verify encryption is working with test data
4. ✅ Monitor logs in CloudWatch
5. ✅ Add more fields to encryption as needed

## Support

For issues or questions:
1. Check CloudWatch logs: `/aws/lambda/v_devices_api`
2. Review KMS access: IAM role policies
3. Verify key exists: `aws kms list-keys --region ap-south-2`
