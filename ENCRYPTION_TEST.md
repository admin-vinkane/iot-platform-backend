# Encryption Testing Guide

## Pre-Requisites

✅ Lambda deployed with encryption code  
⏳ KMS key created (see below)  
⏳ Lambda IAM role has KMS permissions  

---

## Step 1: Create KMS Key (One-time)

```bash
# Create the key
aws kms create-key \
  --description "IoT Platform Data Encryption Key" \
  --region ap-south-2

# Create alias (use KEY_ID from above)
aws kms create-alias \
  --alias-name alias/iot-platform-data \
  --target-key-id <KEY_ID> \
  --region ap-south-2
```

---

## Step 2: Update Lambda IAM Role

```bash
# Add KMS permissions to Lambda role
aws iam put-role-policy \
  --role-name v_devices_lambda_role \
  --policy-name kms-encrypt-decrypt \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
      "Resource": "arn:aws:kms:ap-south-2:*:key/*"
    }]
  }'
```

---

## Step 3: Verify Encryption Works

### Test 1: Check if encryption is active

Lambda logs should show "KMS encryption enabled" on startup.

### Test 2: Create test data

```bash
curl -X POST "https://api/simcards" \
  -H "Content-Type: application/json" \
  -d '{
    "SIMId": "TEST-ENC-001",
    "MobileNumber": "+919876543210",
    "Provider": "Airtel"
  }'
```

Response should show plain phone number.

### Test 3: Verify DynamoDB has encrypted data

```bash
aws dynamodb get-item \
  --table-name v_devices_dev \
  --key '{"PK": {"S": "SIM#TEST-ENC-001"}, "SK": {"S": "META"}}' \
  --region ap-south-2 | jq '.Item.MobileNumber'
```

Should see encrypted structure with `encrypted_value`.

### Test 4: Get via API shows decrypted data

```bash
curl "https://api/simcards/TEST-ENC-001" | jq '.MobileNumber'
```

Should return plain phone number: `"+919876543210"`

---

## Check Logs

```bash
# View encryption logs
aws logs tail /aws/lambda/v_devices_api \
  --filter-pattern "Encrypted" \
  --region ap-south-2
```

Should show messages like: "Encrypted field: MobileNumber"

---

## Success Checklist

- [ ] KMS key created with alias
- [ ] Lambda IAM role has KMS permissions
- [ ] SIM creation returns plain phone number
- [ ] DynamoDB shows encrypted data
- [ ] Get SIM returns decrypted phone number
- [ ] CloudWatch shows "Encrypted" messages
