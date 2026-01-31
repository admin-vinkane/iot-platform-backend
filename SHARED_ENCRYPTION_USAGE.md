# Shared Encryption Utilities - Usage Guide

The `shared/encryption_utils.py` module provides field-level encryption/decryption for all Lambda functions.

## Location
```
shared/encryption_utils.py
```

## Available Imports

### Core Components
```python
from shared.encryption_utils import (
    FieldEncryption,                    # Main encryption class
    get_fields_to_encrypt,              # Get fields to encrypt for entity type
    get_fields_to_decrypt,              # Get fields to decrypt for entity type
    prepare_item_for_storage,           # Encrypt before storing to DB
    prepare_item_for_response,          # Decrypt for API response
    encryption,                         # Pre-initialized encryption instance
    ENCRYPTION_CONFIG                   # Field configuration
)
```

## Quick Start

### 1. Basic Usage in Lambda

```python
from shared.encryption_utils import prepare_item_for_storage, prepare_item_for_response

# In PUT/POST handler - ENCRYPT before storing
def handle_create_device(item):
    item = prepare_item_for_storage(item, "DEVICE")
    table.put_item(Item=item)
    return item

# In GET handler - OPTIONALLY DECRYPT
def handle_get_device(device_id, should_decrypt=False):
    item = table.get_item(Key={"PK": f"DEVICE#{device_id}", "SK": "META"})["Item"]
    item = prepare_item_for_response(item, "DEVICE", decrypt=should_decrypt)
    return item
```

### 2. Query Parameter Support

```python
# Get decrypt parameter from query string
params = event.get("queryStringParameters") or {}
should_decrypt = params.get("decrypt", "").lower() == "true"

# Use in your handler
item = prepare_item_for_response(item, entity_type, decrypt=should_decrypt)
```

### 3. For Different Entity Types

```python
# DEVICE - encrypts SerialNumber
prepare_item_for_storage(device_data, "DEVICE")

# SIM - encrypts MobileNumber, Provider
prepare_item_for_storage(sim_data, "SIM")

# CUSTOMER - encrypts CustomerName, EmailAddress, PhoneNumber, Address
prepare_item_for_storage(customer_data, "CUSTOMER")

# INSTALL - no encrypted fields (but ready for expansion)
prepare_item_for_storage(install_data, "INSTALL")
```

## Encrypted Fields Configuration

```python
ENCRYPTION_CONFIG = {
    'SIM': {
        'encrypt': ['MobileNumber', 'Provider'],
        'decrypt': ['MobileNumber', 'Provider']
    },
    'SIM_ASSOC': {
        'encrypt': [],
        'decrypt': []
    },
    'CUSTOMER': {
        'encrypt': ['CustomerName', 'EmailAddress', 'PhoneNumber', 'Address'],
        'decrypt': ['CustomerName', 'EmailAddress', 'PhoneNumber', 'Address']
    },
    'INSTALL': {
        'encrypt': [],
        'decrypt': []
    },
    'DEVICE': {
        'encrypt': ['SerialNumber'],
        'decrypt': ['SerialNumber']
    }
}
```

## Implementation Examples

### Example 1: v_devices API (Already Implemented)

```python
from shared.encryption_utils import prepare_item_for_storage, prepare_item_for_response

# GET handler
if method == "GET":
    should_decrypt = params.get("decrypt", "").lower() == "true"
    device = table.get_item(Key={"PK": pk, "SK": sk})["Item"]
    device = prepare_item_for_response(device, "DEVICE", decrypt=should_decrypt)
    return SuccessResponse.build(device)

# PUT handler
if method == "PUT":
    item = prepare_item_for_storage(item, "DEVICE")
    table.update_item(Key={"PK": pk, "SK": sk}, AttributeUpdates=...)
```

### Example 2: v_regions API

```python
from shared.encryption_utils import prepare_item_for_storage, prepare_item_for_response

def lambda_handler(event, context):
    method = event.get("httpMethod")
    params = event.get("queryStringParameters") or {}
    
    if method == "GET":
        should_decrypt = params.get("decrypt", "").lower() == "true"
        regions = table.scan()["Items"]
        # Apply decryption if needed (no encrypted fields in REGION, but ready)
        regions = [prepare_item_for_response(r, "REGION", decrypt=should_decrypt) for r in regions]
        return SuccessResponse.build(regions)
    
    elif method == "POST":
        body = json.loads(event.get("body", "{}"))
        # Encrypt before storing
        body = prepare_item_for_storage(body, "REGION")
        table.put_item(Item=body)
        return SuccessResponse.build(body)
```

### Example 3: v_customers API

```python
from shared.encryption_utils import prepare_item_for_storage, prepare_item_for_response

def lambda_handler(event, context):
    method = event.get("httpMethod")
    params = event.get("queryStringParameters") or {}
    
    if method == "GET":
        should_decrypt = params.get("decrypt", "").lower() == "true"
        customers = table.scan()["Items"]
        # Decrypt customer PII fields (CustomerName, EmailAddress, PhoneNumber, Address)
        customers = [prepare_item_for_response(c, "CUSTOMER", decrypt=should_decrypt) for c in customers]
        return SuccessResponse.build(customers)
    
    elif method == "POST":
        body = json.loads(event.get("body", "{}"))
        # Encrypt sensitive customer data
        body = prepare_item_for_storage(body, "CUSTOMER")
        table.put_item(Item=body)
        return SuccessResponse.build(body)
```

## Encryption Modes

### Test Mode (Active Now)
- **Trigger**: KMS key not available
- **Method**: Base64 encoding (reversible)
- **Use Case**: Development and testing
- **Auto-Activation**: Yes, automatic fallback

### Production Mode (When Ready)
- **Trigger**: KMS key `alias/iot-platform-data` exists
- **Method**: Real AWS KMS encryption
- **Use Case**: Production deployments
- **Setup Required**: Create KMS key + IAM permissions

## Data Format

### Encrypted Data (Default)
```json
{
  "SerialNumber": {
    "encrypted_value": "U05fRlJFU0hfRU5DUllQVEVEXzk5OQ==",
    "key_version": "1",
    "encrypted_at": "2026-01-29T10:02:16.700045Z"
  }
}
```

### Decrypted Data (?decrypt=true)
```json
{
  "SerialNumber": "SN_FRESH_ENCRYPTED_999"
}
```

## Performance Considerations

| Operation | Time | Notes |
|-----------|------|-------|
| Encrypt (Test Mode) | <1ms | Base64 encoding |
| Decrypt (Test Mode) | <1ms | Base64 decoding |
| Encrypt (KMS Mode) | 5-10ms | AWS KMS API call |
| Decrypt (KMS Mode) | 5-10ms | AWS KMS API call |

**Recommendation**: Cache decrypted values in Lambda memory if same data requested multiple times.

## Adding New Encrypted Fields

To add encryption to new fields:

1. **Update ENCRYPTION_CONFIG** in `encryption_utils.py`:
```python
'DEVICE': {
    'encrypt': ['SerialNumber', 'NewField'],  # Add here
    'decrypt': ['SerialNumber', 'NewField']   # Add here
}
```

2. **No code changes needed** - just deploy and it works!

## Debugging

### Enable Debug Logging
```python
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
```

### Check CloudWatch for:
```
[TEST MODE] Encrypted field: SerialNumber
Decrypted field: SerialNumber
KMS encryption enabled and key accessible
```

### Manual Testing
```python
from shared.encryption_utils import encryption

# Test encryption
encrypted = encryption.encrypt_field("test_value", "field_name")
print(encrypted)

# Test decryption
decrypted = encryption.decrypt_field(encrypted, "field_name")
print(decrypted)
```

## Common Patterns

### Pattern 1: Always Encrypt on Storage
```python
# Always applies encryption
item = prepare_item_for_storage(item, entity_type)
table.put_item(Item=item)
```

### Pattern 2: Conditional Decryption on Retrieval
```python
# Respect ?decrypt=true parameter
item = prepare_item_for_response(item, entity_type, decrypt=should_decrypt)
return SuccessResponse.build(item)
```

### Pattern 3: List with Optional Decryption
```python
items = table.scan()["Items"]
items = [prepare_item_for_response(item, entity_type, decrypt=should_decrypt) for item in items]
return SuccessResponse.build(items)
```

## Troubleshooting

### Issue: Data stored as plaintext
**Solution**: Ensure `prepare_item_for_storage()` is called before `table.put_item()` or `table.update_item()`

### Issue: Getting encrypted dicts instead of plaintext
**Solution**: Pass `decrypt=True` to `prepare_item_for_response()` or use `?decrypt=true` parameter

### Issue: Import error - "No module named 'shared'"
**Solution**: Check Lambda packaging includes `shared/` directory (already done in script)

### Issue: KMS permission errors
**Solution**: Add `kms:Decrypt`, `kms:Encrypt`, `kms:DescribeKey` to Lambda IAM role

## Migration Path

1. **For existing Lambdas** (v_regions, v_customers):
   - Import: `from shared.encryption_utils import prepare_item_for_storage, prepare_item_for_response`
   - Add: `?decrypt=true` support to GET handlers
   - Add: `prepare_item_for_storage()` call in PUT/POST handlers
   - Deploy: No configuration changes needed

2. **For new Lambdas**:
   - Include encryption from day 1
   - Follow the patterns above
   - Test in test mode first

## Support

For issues or questions:
1. Check ENCRYPTION_TESTING_COMPLETE.md for test results
2. Check ENCRYPTION_API_USAGE.md for API patterns
3. Review examples in v_devices_api.py
