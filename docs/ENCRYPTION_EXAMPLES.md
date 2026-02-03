# Encryption Implementation Examples

## How It Works in Your Code

### 1. When Storing Data (POST)

```python
# In your POST /simcards handler

body = json.loads(event.get("body", "{}"))

# Create the SIM item
sim_item = {
    "PK": f"SIM#{body['SIMId']}",
    "SK": "META",
    "SIMId": body["SIMId"],
    "MobileNumber": body["MobileNumber"],  # Plain text from API
    "Provider": body["Provider"],
    "Status": "active",
    "EntityType": "SIM"
}

# ✨ ENCRYPT BEFORE STORING ✨
sim_item = prepare_item_for_storage(sim_item, "SIM")

# Store to DynamoDB (now encrypted)
table.put_item(Item=sim_item)

# What's in DynamoDB:
# {
#   "MobileNumber": {
#     "encrypted_value": "gAAAAABl7xK...",
#     "key_version": "1",
#     "encrypted_at": "2026-01-29T08:45:00Z"
#   }
# }
```

### 2. When Retrieving Data (GET)

```python
# In your GET /simcards/{simId} handler

# Retrieve from DynamoDB (returns encrypted)
response = table.get_item(
    Key={"PK": f"SIM#{sim_id}", "SK": "META"}
)

if "Item" not in response:
    return ErrorResponse.build("SIM not found", 404)

# ✨ DECRYPT AFTER RETRIEVING ✨
item = prepare_item_for_response(response["Item"], "SIM")

# What's returned to user:
# {
#   "SIMId": "SIM001",
#   "MobileNumber": "+919876543210",  # Decrypted automatically
#   "Provider": "Airtel"
# }

return SuccessResponse.build(simplify(item), 200)
```

### 3. Listing Data (GET all)

```python
# In your GET /simcards handler

# Query DynamoDB
response = table.scan(
    FilterExpression="EntityType = :entity_type",
    ExpressionAttributeValues={":entity_type": "SIM"}
)

sims = []
for item in response.get("Items", []):
    # ✨ DECRYPT EACH ITEM ✨
    decrypted_item = prepare_item_for_response(item, "SIM")
    sims.append(simplify(decrypted_item))

return SuccessResponse.build({"sims": sims}, 200)
```

---

## Encryption Configuration

### Current Setup

```python
# In encryption_utils.py

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

### Adding a New Field

To encrypt device location:

```python
ENCRYPTION_CONFIG = {
    'DEVICE': {
        'encrypt': ['SerialNumber', 'CurrentLocation'],  # ← Added
        'decrypt': ['SerialNumber', 'CurrentLocation']   # ← Added
    }
}
```

No other changes needed!

---

## API Examples

### Example 1: Create SIM with Encryption

**Request:**
```bash
curl -X POST https://api.endpoint/simcards \
  -H "Content-Type: application/json" \
  -d '{
    "SIMId": "SIM001",
    "MobileNumber": "+919876543210",
    "Provider": "Airtel",
    "Status": "active"
  }'
```

**What Lambda does:**
1. Parse JSON (plain text)
2. Create item with plain text values
3. Call `prepare_item_for_storage(item, "SIM")`
4. Encrypts MobileNumber and Provider
5. Stores to DynamoDB

**What DynamoDB stores:**
```json
{
  "PK": "SIM#SIM001",
  "SK": "META",
  "SIMId": "SIM001",
  "MobileNumber": {
    "encrypted_value": "gAAAAABl7xK9Vz2...",
    "key_version": "1",
    "encrypted_at": "2026-01-29T08:45:00Z"
  },
  "Provider": {
    "encrypted_value": "gAAAAABl7xK9Vz3...",
    "key_version": "1",
    "encrypted_at": "2026-01-29T08:45:00Z"
  }
}
```

**Response to user:**
```json
{
  "SIMId": "SIM001",
  "MobileNumber": "+919876543210",
  "Provider": "Airtel",
  "Status": "active"
}
```

### Example 2: Get SIM with Automatic Decryption

**Request:**
```bash
curl https://api.endpoint/simcards/SIM001
```

**What Lambda does:**
1. Query DynamoDB for SIM#SIM001
2. Receive encrypted data
3. Call `prepare_item_for_response(item, "SIM")`
4. Decrypts MobileNumber and Provider
5. Returns to user

**Response:**
```json
{
  "SIMId": "SIM001",
  "MobileNumber": "+919876543210",
  "Provider": "Airtel",
  "Status": "active"
}
```

---

## Under the Hood

### Encryption Flow

```python
class FieldEncryption:
    def encrypt_field(self, value, field_name=""):
        # 1. Convert value to bytes
        plaintext = str(value).encode('utf-8')
        
        # 2. Send to AWS KMS for encryption
        response = self.kms.encrypt(
            KeyId=self.key_id,
            Plaintext=plaintext
        )
        
        # 3. Encode ciphertext to base64
        encrypted_value = b64encode(response['CiphertextBlob']).decode('utf-8')
        
        # 4. Return with metadata
        return {
            'encrypted_value': encrypted_value,
            'key_version': '1',
            'encrypted_at': datetime.now().isoformat() + 'Z'
        }
```

### Decryption Flow

```python
    def decrypt_field(self, encrypted_data, field_name=""):
        # 1. Check if it's encrypted format
        if not isinstance(encrypted_data, dict):
            return encrypted_data  # Not encrypted
        
        # 2. Extract encrypted value
        ciphertext = encrypted_data['encrypted_value']
        ciphertext_bytes = b64decode(ciphertext.encode('utf-8'))
        
        # 3. Send to AWS KMS for decryption
        response = self.kms.decrypt(CiphertextBlob=ciphertext_bytes)
        
        # 4. Decode plaintext
        decrypted_value = response['Plaintext'].decode('utf-8')
        
        # 5. Return plain text
        return decrypted_value
```

---

## Error Handling

### Graceful Degradation

If KMS is not accessible (no permissions, key deleted, etc.):

```python
try:
    encryption = FieldEncryption()
except Exception as e:
    logger.warning(f"KMS not accessible: {e}")
    encryption.enabled = False  # ← Fall back to unencrypted
```

When encryption is disabled:
- `encrypt_field()` returns original value
- `decrypt_field()` returns original value
- Logs warning but doesn't crash
- APIs continue to work

### Decryption Failures

If data can't be decrypted:

```python
try:
    decrypted = self.kms.decrypt(CiphertextBlob=...)
except Exception as e:
    logger.error(f"Decryption failed: {e}")
    return encrypted_data  # ← Return encrypted format as-is
```

---

## Security Flow Diagram

```
┌─────────────────────────────────┐
│  API Request (Plain Text)       │
│  +919876543210                  │
└──────────────┬──────────────────┘
               │
               ↓
┌─────────────────────────────────┐
│  Lambda Handler                 │
│  Parses JSON, validates input   │
└──────────────┬──────────────────┘
               │
               ↓
┌─────────────────────────────────┐
│  prepare_item_for_storage()     │
│  Marks fields for encryption    │
└──────────────┬──────────────────┘
               │
               ↓
┌─────────────────────────────────┐
│  AWS KMS                        │
│  Encrypts: +919876543210        │
│  Returns: gAAAAABl7xK...       │
└──────────────┬──────────────────┘
               │
               ↓
┌─────────────────────────────────┐
│  DynamoDB (At Rest)             │
│  Stores encrypted data          │
│  MobileNumber: gAAAAABl7xK...  │
└──────────────┬──────────────────┘
               │
               ├─ Another Request ──→
               │
               ↓
┌─────────────────────────────────┐
│  DynamoDB (At Rest)             │
│  Retrieves encrypted data       │
│  MobileNumber: gAAAAABl7xK...  │
└──────────────┬──────────────────┘
               │
               ↓
┌─────────────────────────────────┐
│  prepare_item_for_response()    │
│  Marks fields for decryption    │
└──────────────┬──────────────────┘
               │
               ↓
┌─────────────────────────────────┐
│  AWS KMS                        │
│  Decrypts: gAAAAABl7xK...      │
│  Returns: +919876543210         │
└──────────────┬──────────────────┘
               │
               ↓
┌─────────────────────────────────┐
│  Lambda Handler                 │
│  Formats response               │
└──────────────┬──────────────────┘
               │
               ↓
┌─────────────────────────────────┐
│  API Response (Plain Text)      │
│  +919876543210                  │
└─────────────────────────────────┘
```

---

## Testing Encryption

### Test 1: Verify Data is Encrypted in DynamoDB

```bash
# Store a SIM
curl -X POST https://api/simcards \
  -d '{"SIMId": "TEST1", "MobileNumber": "+919876543210"}'

# Check what's in DynamoDB
aws dynamodb get-item \
  --table-name v_devices_dev \
  --key '{"PK": {"S": "SIM#TEST1"}, "SK": {"S": "META"}}' \
  --region ap-south-2

# You should see encrypted data:
# "MobileNumber": {
#   "M": {
#     "encrypted_value": { "S": "gAAAAABl7xK..." },
#     ...
#   }
# }
```

### Test 2: Verify API Returns Plain Text

```bash
# Get the SIM
curl https://api/simcards/TEST1

# Response should show plain text:
# {
#   "MobileNumber": "+919876543210"
# }
```

---

## Performance Characteristics

### Latency

- Encrypt 1 field: ~10-20ms (KMS call)
- Decrypt 1 field: ~10-20ms (KMS call)
- Per API with 2 fields: ~40-60ms additional

### Costs

- KMS: $0.03 per 10,000 API calls
- Per 1000 APIs: $0.003
- Per month (10k requests/day): ~$0.90

---

## Integration Checklist

- [x] `encryption_utils.py` created
- [x] `v_devices_api.py` updated with import
- [x] `prepare_item_for_storage()` available
- [x] `prepare_item_for_response()` available
- [ ] KMS key created (manual setup)
- [ ] Lambda IAM role updated (manual setup)
- [ ] Test with SIM creation
- [ ] Verify CloudWatch logs show encryption
