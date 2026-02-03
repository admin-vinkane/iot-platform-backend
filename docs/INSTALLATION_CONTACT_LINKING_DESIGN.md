# Installation Contact Linking - Design Document

## Problem Statement
Currently, when creating an installation with a `CustomerId`, contacts need to be created separately. This leads to:
- Duplicate data entry
- Potential inconsistencies between customer contacts and installation contacts
- Poor user experience

## Proposed Solution
Link existing customer contacts to installations automatically or on-demand, avoiding duplicate contact creation.

---

## Design Options

### Option 1: Direct Contact Linking During Installation Creation ⭐ **RECOMMENDED**
**Description:** Allow linking customer contacts when creating/updating an installation.

**Implementation:**
- Add `contactIds` array to POST/PUT `/installs` request body
- Validate that contacts belong to the installation's customer
- Create association records: `INSTALL#{installId}/CONTACT_ASSOC#{contactId}`
- Support `includeContacts` parameter in GET `/installs/{installId}`

**Advantages:**
- Simple, intuitive API
- Single request to create installation with contacts
- Follows existing pattern (similar to `deviceIds` linking)
- No new endpoints needed

**API Changes:**
```json
POST /installs
{
  "CustomerId": "CUSTa1b2c3d4",
  "contactIds": ["CONTx1y2z3w4", "CONT9876abcd"],  // NEW
  "StateId": "12",
  "DistrictId": "34",
  // ... other fields
}
```

```json
GET /installs/{installId}?includeContacts=true
{
  "installationId": "INSTe5f6g7h8",
  "CustomerId": "CUSTa1b2c3d4",
  "customerName": "Acme Corp",
  "linkedContacts": [  // NEW
    {
      "contactId": "CONTx1y2z3w4",
      "firstName": "John",
      "lastName": "Doe",
      "email": "john@acme.com",
      "mobileNumber": "9876543210",
      "linkedDate": "2025-01-15T10:30:00Z"
    }
  ],
  "linkedContactCount": 1,
  // ... other fields
}
```

**DynamoDB Structure:**
```
PK: INSTALL#INSTe5f6g7h8
SK: CONTACT_ASSOC#CONTx1y2z3w4
{
  "ContactId": "CONTx1y2z3w4",
  "CustomerId": "CUSTa1b2c3d4",
  "LinkedDate": "2025-01-15T10:30:00Z",
  "LinkedBy": "user@example.com",
  "EntityType": "CONTACT_ASSOC"
}
```

---

### Option 2: Separate Contact Management Endpoints
**Description:** Create dedicated endpoints for managing installation contacts post-creation.

**API:**
- `POST /installs/{installId}/contacts` - Link contacts
- `DELETE /installs/{installId}/contacts/{contactId}` - Unlink contact
- `GET /installs/{installId}/contacts` - List linked contacts

**Advantages:**
- More explicit separation of concerns
- Easier to manage contacts after installation creation
- Better for batch operations

**Disadvantages:**
- Multiple API calls needed during installation setup
- More complex workflow for common use case

---

### Option 3: Automatic Contact Inheritance
**Description:** Automatically link ALL customer contacts when `CustomerId` is set.

**Advantages:**
- Zero configuration needed
- All contacts automatically available

**Disadvantages:**
- No control over which contacts to link
- May link unnecessary contacts
- Potential performance impact with many contacts

---

## Recommended Approach: Option 1 (Hybrid)

Implement **Option 1** with additional endpoints from **Option 2** for post-creation management.

### Implementation Plan

#### Phase 1: Core Linking During Installation Creation
1. ✅ Add `contactIds` validation to POST/PUT `/installs`
2. ✅ Validate contacts belong to installation's customer
3. ✅ Create `CONTACT_ASSOC` records during installation creation
4. ✅ Add `includeContacts` parameter to GET `/installs/{installId}`
5. ✅ Fetch and include contact details in response

#### Phase 2: Post-Creation Management (Optional)
1. ⏳ `POST /installs/{installId}/contacts/link` - Link additional contacts
2. ⏳ `DELETE /installs/{installId}/contacts/{contactId}` - Unlink contact
3. ⏳ Support bulk operations

---

## Technical Implementation Details

### 1. Validation Logic
```python
def validate_contact_belongs_to_customer(contact_id, customer_id):
    """Validate that a contact belongs to the specified customer"""
    customers_table = dynamodb.Table(os.environ.get("CUSTOMERS_TABLE"))
    
    response = customers_table.get_item(
        Key={
            "PK": f"CUSTOMER#{customer_id}",
            "SK": f"ENTITY#CONTACT#{contact_id}"
        }
    )
    
    return "Item" in response
```

### 2. Contact Linking in POST /installs
```python
# After creating installation, link contacts if provided
contact_ids = body.get("contactIds", [])
if contact_ids and body.get("CustomerId"):
    customer_id = body.get("CustomerId")
    
    for contact_id in contact_ids:
        # Validate contact belongs to customer
        if not validate_contact_belongs_to_customer(contact_id, customer_id):
            logger.warning(f"Contact {contact_id} does not belong to customer {customer_id}")
            continue
        
        # Create association record
        contact_assoc_item = {
            "PK": f"INSTALL#{installation_id}",
            "SK": f"CONTACT_ASSOC#{contact_id}",
            "ContactId": contact_id,
            "CustomerId": customer_id,
            "LinkedDate": timestamp,
            "LinkedBy": created_by,
            "EntityType": "CONTACT_ASSOC"
        }
        
        table.put_item(Item=contact_assoc_item)
        logger.info(f"Linked contact {contact_id} to installation {installation_id}")
```

### 3. Fetching Contacts in GET /installs/{installId}
```python
# If includeContacts is requested, fetch linked contacts
if include_contacts:
    # Query contact associations
    contact_assocs = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
        ExpressionAttributeValues={
            ":pk": f"INSTALL#{install_id}",
            ":sk": "CONTACT_ASSOC#"
        }
    )
    
    linked_contacts = []
    for assoc in contact_assocs.get("Items", []):
        contact_id = assoc.get("ContactId")
        customer_id = assoc.get("CustomerId")
        
        if contact_id and customer_id:
            # Fetch contact details from customers table
            contact_item = customers_table.get_item(
                Key={
                    "PK": f"CUSTOMER#{customer_id}",
                    "SK": f"ENTITY#CONTACT#{contact_id}"
                }
            )
            
            if "Item" in contact_item:
                contact_data = simplify(contact_item["Item"])
                contact_data["linkedDate"] = assoc.get("LinkedDate")
                contact_data["linkedBy"] = assoc.get("LinkedBy")
                linked_contacts.append(contact_data)
    
    install_data["linkedContacts"] = linked_contacts
    install_data["linkedContactCount"] = len(linked_contacts)
```

### 4. Batch Validation for Performance
```python
def validate_contacts_batch(contact_ids, customer_id):
    """Validate multiple contacts in a single batch operation"""
    customers_table = dynamodb.Table(os.environ.get("CUSTOMERS_TABLE"))
    
    batch_keys = [
        {
            "PK": f"CUSTOMER#{customer_id}",
            "SK": f"ENTITY#CONTACT#{contact_id}"
        }
        for contact_id in contact_ids
    ]
    
    response = dynamodb_client.batch_get_item(
        RequestItems={
            customers_table.name: {"Keys": batch_keys}
        }
    )
    
    found_contacts = {
        item["SK"].split("#")[-1]
        for item in response.get("Responses", {}).get(customers_table.name, [])
    }
    
    invalid_contacts = set(contact_ids) - found_contacts
    return list(invalid_contacts)
```

---

## Benefits

### 1. User Experience
- ✅ Single form to create installation with contacts
- ✅ No duplicate data entry
- ✅ Consistent contact information across installations

### 2. Data Integrity
- ✅ Validates contacts belong to customer
- ✅ Prevents orphaned contact associations
- ✅ Maintains referential integrity

### 3. Performance
- ✅ Batch operations for validation
- ✅ Efficient querying with begins_with
- ✅ Optional inclusion via query parameter

### 4. Flexibility
- ✅ Optional contact linking (not mandatory)
- ✅ Supports multiple contacts per installation
- ✅ Can be extended with additional endpoints

---

## Edge Cases & Error Handling

### 1. Contact Doesn't Belong to Customer
**Error:** Contact validation fails
**Response:** 400 Bad Request with details
```json
{
  "error": "Invalid contacts: CONTx1y2z3w4 does not belong to customer CUSTa1b2c3d4"
}
```

### 2. Customer Not Specified
**Behavior:** Skip contact linking, log warning
**Response:** Installation created without contacts

### 3. Duplicate Contact Association
**Behavior:** Overwrite existing association (idempotent)
**Impact:** None - `put_item` is idempotent

### 4. Customer Has No Contacts
**Behavior:** Empty contacts array in response
**Response:** Normal with `linkedContacts: []`

### 5. Contact Deleted from Customer
**Behavior:** Contact association remains but returns error in response
**Future Enhancement:** Add periodic cleanup job

---

## Migration Path

### For Existing Installations
- No migration needed - existing installations continue to work
- Contact linking is optional and additive
- Can link contacts retroactively using PUT `/installs/{installId}`

### For New Installations
- Frontend can fetch customer contacts when `CustomerId` is selected
- Display contact selection UI
- Send `contactIds` array in POST request

---

## API Documentation Updates

### POST /installs - Updated

**Request Body:**
```typescript
{
  CustomerId?: string;           // Optional
  contactIds?: string[];         // NEW - Optional array of contact IDs
  StateId: string;
  DistrictId: string;
  MandalId: string;
  VillageId: string;
  HabitationId: string;
  PrimaryDevice: string;
  Status: string;
  InstallationDate: string;
  TemplateId?: string;
  WarrantyDate?: string;
  deviceIds?: string[];          // Existing device linking
}
```

**Validation:**
- If `contactIds` provided, `CustomerId` must also be provided
- Each `contactId` must belong to the specified `CustomerId`
- Contacts must exist in customers table

**Errors:**
- `400` - Invalid contact IDs or contacts don't belong to customer
- `404` - Customer not found

---

### GET /installs/{installId} - Updated

**Query Parameters:**
```
?includeDevices=true      // Existing
&includeCustomer=true     // Existing
&includeContacts=true     // NEW - Include linked contacts
```

**Response:**
```typescript
{
  installationId: string;
  CustomerId?: string;
  linkedContacts?: [        // NEW - Only if includeContacts=true
    {
      contactId: string;
      firstName: string;
      lastName: string;
      email: string;
      mobileNumber: string;
      designation?: string;
      linkedDate: string;
      linkedBy: string;
    }
  ];
  linkedContactCount?: number;  // NEW
  // ... other fields
}
```

---

## Testing Strategy

### Unit Tests
- ✅ Validate contact belongs to customer
- ✅ Batch contact validation
- ✅ Contact association creation
- ✅ Contact fetching with installation

### Integration Tests
- ✅ Create installation with contacts
- ✅ Fetch installation with includeContacts
- ✅ Invalid contact rejection
- ✅ Customer without contacts

### Performance Tests
- ✅ Batch validation with 10+ contacts
- ✅ Query performance with includeContacts
- ✅ Concurrent contact linking

---

## Rollout Plan

### Phase 1: Implementation (Day 1)
- Implement contact linking in POST /installs
- Add validation logic
- Update GET /installs to support includeContacts
- Add error handling

### Phase 2: Testing (Day 2)
- Unit tests
- Integration tests
- Manual testing with Postman

### Phase 3: Deployment (Day 3)
- Deploy to dev environment
- Validate with real data
- Monitor logs for errors

### Phase 4: Documentation (Day 3)
- Update API documentation
- Create usage examples
- Update frontend integration guide

---

## Questions for Product Team

1. **Contact Requirement:** Should contacts be mandatory when CustomerId is provided?
   - Current Design: Optional
   - Alternative: Require at least one contact

2. **Multiple Contacts:** How many contacts typically needed per installation?
   - Current Design: Unlimited
   - Alternative: Limit to 3-5 contacts

3. **Contact Updates:** If customer contact is updated, should it reflect in installations automatically?
   - Current Design: References are dynamic (fetch on-demand)
   - Alternative: Store snapshots

4. **Primary Contact:** Should installations have a "primary contact" designation?
   - Current Design: No primary designation
   - Alternative: Add `isPrimary` flag to associations

---

## Next Steps

1. Get approval on design approach
2. Implement Phase 1 (core linking)
3. Test thoroughly
4. Deploy to dev environment
5. Gather feedback
6. Implement Phase 2 (additional endpoints) if needed

