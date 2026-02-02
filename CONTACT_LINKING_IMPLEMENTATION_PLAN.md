# Contact Linking Implementation Plan

## Overview
Implement customer contact linking to installations following the **exact same pattern** as device linking currently works in the system.

---

## Current Device Linking Pattern (Reference)

### 1. **POST /installs with deviceIds** (Inline Linking)
```json
POST /installs
{
  "StateId": "TS",
  "deviceIds": ["DEV001", "DEV002"],  // Optional array
  // ... other fields
}
```
- Validates each device exists
- Calls `execute_install_device_link_transaction()` for each device
- Returns results with `deviceLinking: { linked: [], errors: [] }`

### 2. **POST /installs/{installId}/devices/link** (Post-Creation Linking)
```json
POST /installs/INST123/devices/link
{
  "deviceIds": ["DEV003", "DEV004"],  // Can link multiple
  "performedBy": "user@example.com",
  "reason": "Additional devices"
}
```
- Supports batch linking (up to 50 devices)
- Uses batch_get_item for validation
- Returns `{ linked: [], errors: [], timestamp }`

### 3. **DELETE /installs/{installId}/devices/unlink**
```json
POST /installs/INST123/devices/unlink
{
  "deviceIds": ["DEV003"],
  "performedBy": "user@example.com",
  "reason": "Device removed"
}
```

### 4. **GET /installs/{installId}?includeDevices=true**
```json
{
  "installationId": "INST123",
  "linkedDevices": [
    {
      "deviceId": "DEV001",
      "linkedDate": "2026-02-01T10:00:00Z",
      "linkedBy": "user@example.com",
      "linkStatus": "active",
      // ... device fields
    }
  ],
  "linkedDeviceCount": 1
}
```

### 5. **DynamoDB Structure**
```
INSTALL -> DEVICE Association:
PK: INSTALL#INST123
SK: DEVICE_ASSOC#DEV001
{
  "EntityType": "INSTALL_DEVICE_ASSOC",
  "InstallId": "INST123",
  "DeviceId": "DEV001",
  "Status": "active",
  "LinkedDate": "2026-02-01T10:00:00Z",
  "LinkedBy": "user@example.com",
  "CreatedDate": "2026-02-01T10:00:00Z",
  "UpdatedDate": "2026-02-01T10:00:00Z"
}

DEVICE -> INSTALL Association (bidirectional):
PK: DEVICE#DEV001
SK: INSTALL_ASSOC#INST123
{
  "EntityType": "DEVICE_INSTALL_ASSOC",
  "DeviceId": "DEV001",
  "InstallId": "INST123",
  "Status": "active",
  "LinkedDate": "2026-02-01T10:00:00Z",
  "LinkedBy": "user@example.com"
}

DEVICE META update:
PK: DEVICE#DEV001
SK: META
{
  "LinkedInstallationId": "INST123",  // Current installation
  "InstallationHistory": [            // Audit trail
    {
      "timestamp": "2026-02-01T10:00:00Z",
      "action": "linked",
      "installationId": "INST123",
      "performedBy": "user@example.com",
      "ipAddress": "192.168.1.1",
      "reason": "Initial installation"
    }
  ]
}
```

### 6. **Transaction Functions**
- `execute_install_device_link_transaction()` - Uses DynamoDB transactions with:
  - Create INSTALL -> DEVICE association
  - Create DEVICE -> INSTALL association (bidirectional)
  - Update DEVICE META with LinkedInstallationId
  - Append to InstallationHistory
  - Conditional expressions to prevent duplicates

---

## Contact Linking Implementation (Mirror Pattern)

### 1. **POST /installs with contactIds** (Phase 1)
```json
POST /installs
{
  "CustomerId": "CUSTa1b2c3d4",      // Required if contactIds provided
  "contactIds": ["CONTx1y2", "CONT9876"],  // Optional array
  "StateId": "TS",
  // ... other fields
}
```

**Implementation Steps:**
1. Add contact linking code after device linking (line ~800 in v_devices_api.py)
2. Validate CustomerId is provided if contactIds exist
3. Batch validate contacts belong to customer (from v_customers_dev table)
4. Call `execute_install_contact_link_transaction()` for each contact
5. Add results to response: `contactLinking: { linked: [], errors: [] }`

### 2. **POST /installs/{installId}/contacts/link** (Phase 2)
```json
POST /installs/INST123/contacts/link
{
  "contactIds": ["CONTx1y2", "CONT9876"],
  "performedBy": "user@example.com",
  "reason": "Additional contacts"
}
```

**Implementation Steps:**
1. Add new endpoint handler (similar to /devices/link at line ~1093)
2. Support batch linking (up to 50 contacts)
3. Validate installation has CustomerId
4. Batch validate contacts belong to installation's customer
5. Execute link transactions
6. Return `{ linked: [], errors: [], timestamp }`

### 3. **DELETE /installs/{installId}/contacts/unlink** (Phase 2)
```json
POST /installs/INST123/contacts/unlink
{
  "contactIds": ["CONTx1y2"],
  "performedBy": "user@example.com",
  "reason": "Contact removed"
}
```

### 4. **GET /installs/{installId}?includeContacts=true** (Phase 1)
```json
{
  "installationId": "INST123",
  "CustomerId": "CUSTa1b2c3d4",
  "linkedContacts": [
    {
      "contactId": "CONTx1y2",
      "firstName": "John",
      "lastName": "Doe",
      "email": "john@acme.com",
      "mobileNumber": "9876543210",
      "designation": "Site Manager",
      "linkedDate": "2026-02-01T10:00:00Z",
      "linkedBy": "user@example.com"
    }
  ],
  "linkedContactCount": 1
}
```

**Implementation Steps:**
1. Add `includeContacts` query parameter handling (around line ~1595)
2. Query CONTACT_ASSOC records for installation
3. Batch fetch contact details from v_customers_dev table
4. Merge association metadata (linkedDate, linkedBy) with contact data
5. Add to response

### 5. **DynamoDB Structure**

#### INSTALL -> CONTACT Association
```
PK: INSTALL#INST123
SK: CONTACT_ASSOC#CONTx1y2
{
  "EntityType": "INSTALL_CONTACT_ASSOC",
  "InstallId": "INST123",
  "ContactId": "CONTx1y2",
  "CustomerId": "CUSTa1b2c3d4",
  "Status": "active",
  "LinkedDate": "2026-02-01T10:00:00Z",
  "LinkedBy": "user@example.com",
  "CreatedDate": "2026-02-01T10:00:00Z",
  "UpdatedDate": "2026-02-01T10:00:00Z"
}
```

#### CONTACT -> INSTALL Association (bidirectional - optional)
```
PK: CONTACT#CUSTa1b2c3d4#CONTx1y2
SK: INSTALL_ASSOC#INST123
{
  "EntityType": "CONTACT_INSTALL_ASSOC",
  "ContactId": "CONTx1y2",
  "InstallId": "INST123",
  "CustomerId": "CUSTa1b2c3d4",
  "Status": "active",
  "LinkedDate": "2026-02-01T10:00:00Z",
  "LinkedBy": "user@example.com"
}
```

**Note:** Contacts live in v_customers_dev table, so bidirectional link would be stored there (optional - discuss with team)

---

## Implementation Phases

### Phase 1: Core Inline Linking (Highest Priority)
**Time Estimate:** 2-3 hours

#### 1.1 Add Transaction Functions
**File:** `lambdas/v_devices/v_devices_api.py`
**Location:** After `execute_install_device_unlink_transaction()` (around line 3250)

```python
def execute_install_contact_link_transaction(install_id, contact_id, customer_id, performed_by, ip_address, reason=None):
    """
    Execute atomic transaction to link a contact to an installation.
    Creates association record in v_devices_dev table.
    
    Note: Unlike device linking, we don't update the contact record itself
    since contacts live in v_customers_dev table and are managed separately.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    transact_items = [
        {
            # Create association: INSTALL -> CONTACT
            "Put": {
                "TableName": TABLE_NAME,
                "Item": {
                    "PK": {"S": f"INSTALL#{install_id}"},
                    "SK": {"S": f"CONTACT_ASSOC#{contact_id}"},
                    "EntityType": {"S": "INSTALL_CONTACT_ASSOC"},
                    "InstallId": {"S": install_id},
                    "ContactId": {"S": contact_id},
                    "CustomerId": {"S": customer_id},
                    "Status": {"S": "active"},
                    "LinkedDate": {"S": timestamp},
                    "LinkedBy": {"S": performed_by},
                    "CreatedDate": {"S": timestamp},
                    "UpdatedDate": {"S": timestamp}
                },
                "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)"
            }
        }
    ]
    
    try:
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully linked contact {contact_id} to install {install_id}")
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            reasons = e.response.get('CancellationReasons', [])
            if any(r.get('Code') == 'ConditionalCheckFailed' for r in reasons):
                return False, f"Contact {contact_id} is already linked to install {install_id}"
            return False, f"Transaction failed: {str(reasons)}"
        logger.error(f"Transaction error: {str(e)}")
        return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"


def execute_install_contact_unlink_transaction(install_id, contact_id, performed_by, ip_address, reason=None):
    """
    Execute atomic transaction to unlink a contact from an installation.
    Deletes association record.
    """
    transact_items = [
        {
            # Delete association: INSTALL -> CONTACT
            "Delete": {
                "TableName": TABLE_NAME,
                "Key": {
                    "PK": {"S": f"INSTALL#{install_id}"},
                    "SK": {"S": f"CONTACT_ASSOC#{contact_id}"}
                },
                "ConditionExpression": "attribute_exists(PK) AND attribute_exists(SK)"
            }
        }
    ]
    
    try:
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully unlinked contact {contact_id} from install {install_id}")
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            reasons = e.response.get('CancellationReasons', [])
            if any(r.get('Code') == 'ConditionalCheckFailed' for r in reasons):
                return False, f"Contact {contact_id} is not linked to install {install_id}"
            return False, f"Transaction failed: {str(reasons)}"
        logger.error(f"Transaction error: {str(e)}")
        return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"
```

#### 1.2 Add Validation Helper
**Location:** After transaction functions

```python
def validate_contacts_belong_to_customer_batch(contact_ids, customer_id):
    """
    Validate that multiple contacts belong to the specified customer.
    Uses batch_get_item for performance.
    
    Returns:
        (valid_contacts, invalid_contacts) - tuple of lists
    """
    if not contact_ids:
        return [], []
    
    try:
        customers_table_name = os.environ.get("CUSTOMERS_TABLE", "v_customers_dev")
        
        # Build batch keys
        batch_keys = [
            {
                "PK": f"CUSTOMER#{customer_id}",
                "SK": f"ENTITY#CONTACT#{contact_id}"
            }
            for contact_id in contact_ids
        ]
        
        # Batch get contacts
        response = dynamodb_client.batch_get_item(
            RequestItems={
                customers_table_name: {"Keys": batch_keys}
            }
        )
        
        # Extract found contact IDs
        found_contacts = {
            item["SK"]["S"].split("#")[-1]
            for item in response.get("Responses", {}).get(customers_table_name, [])
        }
        
        valid_contacts = [cid for cid in contact_ids if cid in found_contacts]
        invalid_contacts = [cid for cid in contact_ids if cid not in found_contacts]
        
        logger.info(f"Contact validation: {len(valid_contacts)} valid, {len(invalid_contacts)} invalid")
        return valid_contacts, invalid_contacts
        
    except Exception as e:
        logger.error(f"Error validating contacts: {str(e)}")
        # On error, treat all as invalid to be safe
        return [], contact_ids
```

#### 1.3 Add Contact Linking to POST /installs
**File:** `lambdas/v_devices/v_devices_api.py`
**Location:** After device linking code (around line 803, after device linking completes)

```python
                # Link contacts if provided in request (called from UI)
                contact_ids = body.get("contactIds", [])
                customer_id = body.get("CustomerId")
                
                if contact_ids:
                    # Validate CustomerId is provided
                    if not customer_id:
                        response_data["contactLinking"] = {
                            "linked": [],
                            "errors": [{"error": "CustomerId is required when linking contacts"}]
                        }
                    else:
                        logger.info(f"Linking {len(contact_ids)} contacts to installation {installation_id}")
                        
                        contact_link_results = []
                        contact_link_errors = []
                        
                        # Batch validate contacts belong to customer
                        valid_contacts, invalid_contacts = validate_contacts_belong_to_customer_batch(
                            contact_ids, customer_id
                        )
                        
                        # Add errors for invalid contacts
                        for contact_id in invalid_contacts:
                            contact_link_errors.append({
                                "contactId": contact_id,
                                "error": f"Contact not found or doesn't belong to customer {customer_id}"
                            })
                        
                        # Link valid contacts
                        for contact_id in valid_contacts:
                            try:
                                performed_by = body.get("CreatedBy", "system")
                                ip_address = get_client_ip(event)
                                reason = "Linked during installation creation"
                                
                                success, transaction_error = execute_install_contact_link_transaction(
                                    installation_id, contact_id, customer_id, performed_by, ip_address, reason
                                )
                                
                                if success:
                                    contact_link_results.append({"contactId": contact_id, "status": "linked"})
                                else:
                                    contact_link_errors.append({"contactId": contact_id, "error": transaction_error})
                            
                            except Exception as e:
                                logger.error(f"Error linking contact {contact_id}: {str(e)}", exc_info=True)
                                contact_link_errors.append({"contactId": contact_id, "error": str(e)})
                        
                        # Add contact linking results to response
                        response_data["contactLinking"] = {
                            "linked": contact_link_results,
                            "errors": contact_link_errors if contact_link_errors else []
                        }
                        
                        logger.info(f"Contact linking complete: {len(contact_link_results)} linked, {len(contact_link_errors)} failed")
```

#### 1.4 Add includeContacts to GET /installs/{installId}
**File:** `lambdas/v_devices/v_devices_api.py`
**Location:** After includeDevices code (around line 1580)

```python
                # If includeContacts is requested, fetch linked contacts
                include_contacts = query_params.get("includeContacts", "false").lower() == "true"
                if include_contacts:
                    try:
                        # Query contact associations
                        contact_response = table.query(
                            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                            ExpressionAttributeValues={
                                ":pk": f"INSTALL#{install_id}",
                                ":sk": "CONTACT_ASSOC#"
                            }
                        )
                        
                        # Extract contact IDs and prepare batch fetch
                        contact_assocs = {}
                        contact_ids_to_fetch = []
                        
                        for assoc in contact_response.get("Items", []):
                            contact_id = assoc.get("ContactId")
                            customer_id = assoc.get("CustomerId")
                            if contact_id and customer_id:
                                contact_assocs[contact_id] = {
                                    "customerId": customer_id,
                                    "linkedDate": assoc.get("LinkedDate"),
                                    "linkedBy": assoc.get("LinkedBy"),
                                    "linkStatus": assoc.get("Status", "active")
                                }
                                contact_ids_to_fetch.append((customer_id, contact_id))
                        
                        # Batch fetch contact details from customers table
                        linked_contacts = []
                        if contact_ids_to_fetch:
                            customers_table_name = os.environ.get("CUSTOMERS_TABLE", "v_customers_dev")
                            batch_keys = [
                                {
                                    "PK": f"CUSTOMER#{customer_id}",
                                    "SK": f"ENTITY#CONTACT#{contact_id}"
                                }
                                for customer_id, contact_id in contact_ids_to_fetch
                            ]
                            
                            try:
                                batch_response = dynamodb_client.batch_get_item(
                                    RequestItems={
                                        customers_table_name: {"Keys": batch_keys}
                                    }
                                )
                                
                                for item in batch_response.get("Responses", {}).get(customers_table_name, []):
                                    contact_data = simplify(item)
                                    contact_id = contact_data.get("contactId")
                                    
                                    if contact_id and contact_id in contact_assocs:
                                        # Merge association metadata
                                        contact_data.update(contact_assocs[contact_id])
                                        linked_contacts.append(contact_data)
                            
                            except Exception as e:
                                logger.error(f"Error batch fetching contacts: {str(e)}")
                                # Fallback to empty list
                        
                        install_data["linkedContacts"] = linked_contacts
                        install_data["linkedContactCount"] = len(linked_contacts)
                    
                    except Exception as e:
                        logger.error(f"Error fetching linked contacts: {str(e)}")
                        install_data["linkedContacts"] = []
                        install_data["linkedContactCount"] = 0
```

#### 1.5 Add includeContacts to GET /installs (list)
**File:** `lambdas/v_devices/v_devices_api.py`
**Location:** In the scan loop (around line 1650)

Similar implementation to GET single install, but within the loop that processes multiple installations.

---

### Phase 2: Standalone Link/Unlink Endpoints (Lower Priority)
**Time Estimate:** 2-3 hours

#### 2.1 POST /installs/{installId}/contacts/link
**Location:** After POST /installs/{installId}/devices/link (around line 1220)

Implementation mirrors device linking endpoint exactly - same validation pattern, batch processing, error handling.

#### 2.2 DELETE /installs/{installId}/contacts/unlink
**Location:** After DELETE /installs/{installId}/devices/unlink

Implementation mirrors device unlinking endpoint exactly.

---

## Testing Strategy

### Unit Tests
```python
def test_contact_validation_batch():
    """Test batch contact validation"""
    valid, invalid = validate_contacts_belong_to_customer_batch(
        ["CONT001", "CONT999"],
        "CUST123"
    )
    assert "CONT001" in valid
    assert "CONT999" in invalid

def test_install_contact_link_transaction():
    """Test contact linking transaction"""
    success, error = execute_install_contact_link_transaction(
        "INST123", "CONT001", "CUST123", "user@test.com", "192.168.1.1"
    )
    assert success is True
    assert error is None
```

### Integration Tests
```bash
# Test 1: Create installation with contacts
curl -X POST "$API_URL/installs" \
  -H "Content-Type: application/json" \
  -d '{
    "CustomerId": "CUSTa1b2c3d4",
    "contactIds": ["CONTx1y2z3w4", "CONT9876abcd"],
    "StateId": "TS",
    "DistrictId": "HYD",
    "MandalId": "SRNAGAR",
    "VillageId": "VILLAGE001",
    "HabitationId": "013",
    "PrimaryDevice": "water",
    "Status": "active",
    "InstallationDate": "2026-02-01T00:00:00.000Z"
  }'

# Expected response:
# {
#   "message": "Installation created successfully",
#   "installation": {
#     "installationId": "INSTxyz",
#     "contactLinking": {
#       "linked": [
#         {"contactId": "CONTx1y2z3w4", "status": "linked"},
#         {"contactId": "CONT9876abcd", "status": "linked"}
#       ],
#       "errors": []
#     }
#   }
# }

# Test 2: Fetch installation with contacts
curl "$API_URL/installs/INSTxyz?includeContacts=true"

# Expected:
# {
#   "installationId": "INSTxyz",
#   "linkedContacts": [
#     {
#       "contactId": "CONTx1y2z3w4",
#       "firstName": "John",
#       "lastName": "Doe",
#       "linkedDate": "2026-02-01T10:00:00Z",
#       "linkedBy": "system"
#     }
#   ],
#   "linkedContactCount": 2
# }

# Test 3: Invalid contact (doesn't belong to customer)
curl -X POST "$API_URL/installs" \
  -d '{
    "CustomerId": "CUST123",
    "contactIds": ["CONT_WRONG"],
    ...
  }'

# Expected:
# {
#   "contactLinking": {
#     "linked": [],
#     "errors": [
#       {
#         "contactId": "CONT_WRONG",
#         "error": "Contact not found or doesn't belong to customer CUST123"
#       }
#     ]
#   }
# }

# Test 4: No CustomerId with contactIds
curl -X POST "$API_URL/installs" \
  -d '{
    "contactIds": ["CONT001"],
    ...
  }'

# Expected:
# {
#   "contactLinking": {
#     "linked": [],
#     "errors": [{"error": "CustomerId is required when linking contacts"}]
#   }
# }
```

---

## Deployment Plan

### Step 1: Code Implementation
- [ ] Add transaction functions
- [ ] Add validation helpers
- [ ] Add inline linking to POST /installs
- [ ] Add includeContacts to GET endpoints
- [ ] Update requirements.txt if needed (already has boto3)

### Step 2: Testing
- [ ] Local testing with test data
- [ ] Integration testing with dev API
- [ ] Validate DynamoDB records created correctly
- [ ] Check batch performance (50 contacts)

### Step 3: Deployment
```bash
cd /Users/samyuktha/thajith/vinkane/admin-vinkane/iot-platform-backend
./scripts/package_and_upload_lambda.sh v_devices ap-south-2
```

### Step 4: Verification
- [ ] Test POST /installs with contactIds
- [ ] Test GET /installs?includeContacts=true
- [ ] Verify CloudWatch logs
- [ ] Check DynamoDB records
- [ ] Monitor performance metrics

---

## Benefits

### 1. **Consistency with Existing Pattern**
- Uses exact same architecture as device linking
- Developers familiar with device linking can immediately understand
- Same DynamoDB patterns, same transaction structure

### 2. **User Experience**
- ✅ Create installation with contacts in single request
- ✅ No duplicate data entry
- ✅ Consistent contact information across installations

### 3. **Data Integrity**
- ✅ Atomic transactions prevent partial linking
- ✅ Validates contacts belong to customer
- ✅ Maintains referential integrity

### 4. **Performance**
- ✅ Batch validation (50 contacts in single request)
- ✅ Batch fetching for GET operations
- ✅ Efficient DynamoDB queries with begins_with

### 5. **Scalability**
- ✅ Supports multiple contacts per installation
- ✅ Can link contacts during or after creation
- ✅ Easily extensible to unlink operations

---

## Edge Cases Handled

### 1. Contact Doesn't Belong to Customer
- **Error:** Validation fails during batch check
- **Response:** Added to errors array with clear message
- **Impact:** Other valid contacts still linked successfully

### 2. Customer Not Specified
- **Behavior:** Error added to response
- **Response:** `CustomerId is required when linking contacts`
- **Impact:** Installation created but no contacts linked

### 3. Duplicate Contact Association
- **Behavior:** Transaction fails with ConditionalCheckFailed
- **Response:** Clear error message
- **Impact:** No duplicate associations created

### 4. Contact Deleted from Customer Table
- **Behavior:** Validation fails during batch check
- **Response:** Contact not linked, error returned
- **Impact:** Association never created, data consistent

### 5. Installation Without Customer
- **Behavior:** Contact linking skipped entirely
- **Response:** Installation created normally
- **Impact:** No contact associations created

---

## Questions for Team

### 1. Bidirectional Links
**Question:** Should we store bidirectional associations like device linking?
- **Current Device Pattern:** Yes (DEVICE -> INSTALL and INSTALL -> DEVICE)
- **Contact Challenge:** Contacts live in v_customers_dev table
- **Recommendation:** Store only INSTALL -> CONTACT (simpler, cross-table complexity)

### 2. Contact Limit
**Question:** Should we limit contacts per installation?
- **Current Device Pattern:** No hard limit (validated individually)
- **Recommendation:** Allow up to 50 contacts (batch processing limit)

### 3. Mandatory Contacts
**Question:** Should installations with CustomerId require at least one contact?
- **Current Device Pattern:** Devices optional
- **Recommendation:** Keep contacts optional for flexibility

### 4. Primary Contact
**Question:** Should installations designate a primary contact?
- **Current Device Pattern:** PrimaryDevice field exists on installation
- **Recommendation:** Add later if needed (not critical for MVP)

---

## Success Metrics

### Functional Requirements
- ✅ Can link contacts during installation creation
- ✅ Can fetch linked contacts with installation
- ✅ Validates contacts belong to customer
- ✅ Handles errors gracefully
- ✅ Returns clear success/error messages

### Performance Requirements
- ✅ Batch validation completes in < 200ms (50 contacts)
- ✅ Linking completes in < 100ms per contact
- ✅ GET with includeContacts adds < 300ms overhead

### Quality Requirements
- ✅ No duplicate associations possible (atomic transactions)
- ✅ Data integrity maintained (validation)
- ✅ Clear audit trail (linkedDate, linkedBy)
- ✅ Comprehensive error handling

---

## Next Steps

1. **Get approval** on this implementation plan
2. **Implement Phase 1** (core inline linking - 2-3 hours)
3. **Test thoroughly** with dev environment
4. **Deploy** to dev
5. **Validate** with real customer/contact data
6. **Implement Phase 2** if needed (standalone endpoints)

