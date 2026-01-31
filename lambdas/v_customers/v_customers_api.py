import json
import os
import boto3
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from shared.response_utils import SuccessResponse, ErrorResponse
from shared.encryption_utils import prepare_item_for_storage, prepare_item_for_response
from pydantic import BaseModel, ValidationError

# Initialize DynamoDB and logging
TABLE_NAME = os.environ.get("TABLE_NAME", "v_customers_dev")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Pydantic models for validation
class CustomerDetails(BaseModel):
    PK: str
    SK: str
    entityType: str
    customerId: str = None  # Auto-generated ID
    customerNumber: str = None  # User-provided customer number
    name: str = None
    companyName: str = None
    email: str = None
    phone: str = None
    countryCode: str = None
    gstin: str = None
    pan: str = None
    totalInstallations: int = None
    activeInstallations: int = None
    isActive: bool = True
    createdAt: str = None
    createdBy: str = None
    updatedAt: str = None
    updatedBy: str = None

    class Config:
        extra = "forbid"

class ContactDetails(BaseModel):
    PK: str = None
    SK: str = None
    entityType: str
    contactId: str = None  # Auto-generated ID
    firstName: str
    lastName: str
    displayName: str
    email: str
    mobileNumber: str
    countryCode: str
    contactType: str
    createAsUser: bool
    userId: str | None = None
    isActive: bool
    createdAt: str = None
    createdBy: str
    updatedAt: str = None
    updatedBy: str = None

    class Config:
        extra = "forbid"

class AddressDetails(BaseModel):
    PK: str = None
    SK: str = None
    entityType: str
    addressId: str = None  # Auto-generated ID
    addressType: str
    addressLine1: str
    addressLine2: str = None
    city: str
    state: str
    pincode: str
    country: str
    isActive: bool
    isPrimary: bool
    createdAt: str = None
    createdBy: str
    updatedAt: str = None
    updatedBy: str = None

    class Config:
        extra = "forbid"

class AuditDetails(BaseModel):
    PK: str
    SK: str
    entityType: str
    targetEntityType: str
    targetEntityId: str
    action: str
    field: str
    oldValue: str
    newValue: str
    description: str
    performedBy: str
    performedAt: str

    class Config:
        extra = "forbid"

# Simplify DynamoDB item format
# def simplify(item):
#     def simplify_value(value):
#         if isinstance(value, dict):
#             if "S" in value:
#                 return value["S"]
#             elif "N" in value:
#                 return int(value["N"]) if value["N"].isdigit() else float(value["N"])
#             elif "BOOL" in value:
#                 return value["BOOL"]
#             elif "M" in value:
#                 return {k: simplify_value(v) for k, v in value["M"].items()}
#             elif "L" in value:
#                 return [simplify_value(v) for v in value["L"]]
#         return value

#     return {k: simplify_value(v) for k, v in item.items()}
def simplify(item):
    """
    Recursively convert DynamoDB item values to native Python types,
    including Decimal to int/float for JSON serialization.
    """
    def simplify_value(v):
        if isinstance(v, Decimal):
            # Convert Decimal to int if it's a whole number, otherwise to float
            return int(v) if v == int(v) else float(v)
        if isinstance(v, dict):
            return {k: simplify_value(nv) for k, nv in v.items()}
        if isinstance(v, list):
            return [simplify_value(x) for x in v]
        return v

    return {k: simplify_value(v) for k, v in item.items()}

# Lambda handler
def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    # Try multiple ways to extract the HTTP method
    method = (
        event.get("httpMethod") or 
        event.get("requestContext", {}).get("http", {}).get("method") or
        event.get("requestContext", {}).get("httpMethod")
    )
    
    # Extract path (HTTP API 2.0 uses rawPath, REST API uses path)
    path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path")
    path_parameters = event.get("pathParameters", {})
    query_parameters = event.get("queryStringParameters", {})
    
    # Log for debugging
    logger.info(f"Event keys: {list(event.keys())}")
    logger.info(f"Extracted method: {method}")
    logger.info(f"Extracted path: {path}")
    
    # If method is still None, return detailed error
    if not method:
        logger.error("Could not extract HTTP method from event")
        return ErrorResponse.build("Could not determine HTTP method from request", 400)

    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return SuccessResponse.build({"message": "CORS preflight successful"}, 200)

    try:
        if method == "GET":
            logger.info(f"GET request - path: '{path}', params: {path_parameters}")
            if query_parameters and "decrypt" in query_parameters:
                should_decrypt = query_parameters.get("decrypt", "").lower() == "true"
            else:
                should_decrypt = True
            
            # GET /customers - List all customers
            if path in ["/customers", "/dev/customers"]:
                response = table.scan()
                items = response.get("Items", [])
                # Filter only customer entities
                customers = [simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=should_decrypt)) for item in items if item.get("SK") == "ENTITY#CUSTOMER"]
                return SuccessResponse.build(customers)
            
            # GET /customers/{id}/contacts - List all contacts for a customer
            elif "id" in path_parameters and "/contacts" in path and "contactId" not in path_parameters:
                customer_id = path_parameters["id"]
                pk = f"CUSTOMER#{customer_id}"
                
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": pk,
                        ":sk": "ENTITY#CONTACT#"
                    }
                )
                contacts = [simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=should_decrypt)) for item in response.get("Items", [])]
                return SuccessResponse.build(contacts)
            
            # GET /customers/{id}/contacts/{contactId} - Get specific contact
            elif "id" in path_parameters and "contactId" in path_parameters:
                customer_id = path_parameters["id"]
                contact_id = path_parameters["contactId"]
                pk = f"CUSTOMER#{customer_id}"
                sk = f"ENTITY#CONTACT#{contact_id}"
                
                response = table.get_item(Key={"PK": pk, "SK": sk})
                item = response.get("Item")
                if not item:
                    return ErrorResponse.build("Contact not found", 404)
                return SuccessResponse.build(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=should_decrypt)))
            
            # GET /customers/{id}/addresses - List all addresses for a customer
            elif "id" in path_parameters and "/addresses" in path and "addressId" not in path_parameters:
                customer_id = path_parameters["id"]
                pk = f"CUSTOMER#{customer_id}"
                
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": pk,
                        ":sk": "ENTITY#ADDRESS#"
                    }
                )
                addresses = [simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=should_decrypt)) for item in response.get("Items", [])]
                return SuccessResponse.build(addresses)
            
            # GET /customers/{id}/addresses/{addressId} - Get specific address
            elif "id" in path_parameters and "addressId" in path_parameters:
                customer_id = path_parameters["id"]
                address_id = path_parameters["addressId"]
                pk = f"CUSTOMER#{customer_id}"
                sk = f"ENTITY#ADDRESS#{address_id}"
                
                response = table.get_item(Key={"PK": pk, "SK": sk})
                item = response.get("Item")
                if not item:
                    return ErrorResponse.build("Address not found", 404)
                return SuccessResponse.build(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=should_decrypt)))
            
            # GET /customers/{id} - Get customer with nested contacts and addresses
            elif "id" in path_parameters:
                customer_id = path_parameters["id"]
                pk = f"CUSTOMER#{customer_id}"
                
                # Query all items for this customer
                response = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": pk}
                )
                
                items = response.get("Items", [])
                if not items:
                    return ErrorResponse.build("Customer not found", 404)
                
                # Separate items by entity type
                customer = None
                contacts = []
                addresses = []
                
                for item in items:
                    sk = item.get("SK", "")
                    if sk == "ENTITY#CUSTOMER":
                        customer = simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=should_decrypt))
                    elif sk.startswith("ENTITY#CONTACT#"):
                        contacts.append(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=should_decrypt)))
                    elif sk.startswith("ENTITY#ADDRESS#"):
                        addresses.append(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=should_decrypt)))
                
                if not customer:
                    return ErrorResponse.build("Customer not found", 404)
                
                # Add nested data
                customer["contacts"] = contacts
                customer["addresses"] = addresses
                return SuccessResponse.build(customer)
        
        elif method == "POST":
            body = event.get("body")
            if not body:
                return ErrorResponse.build("Missing request body", 400)
            
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return ErrorResponse.build("Invalid JSON", 400)
            
            # POST /customers/{id}/contacts - Create contact
            if "id" in path_parameters and "/contacts" in path:
                customer_id = path_parameters["id"]
                pk = f"CUSTOMER#{customer_id}"
                
                # Validate customer exists
                check = table.get_item(Key={"PK": pk, "SK": "ENTITY#CUSTOMER"})
                if "Item" not in check:
                    return ErrorResponse.build("Customer not found", 404)
                
                # Generate contact ID
                contact_id = f"CONT{str(uuid.uuid4())[:8].upper()}"
                
                # Set PK, SK, contactId, and timestamp
                data["PK"] = pk
                data["SK"] = f"ENTITY#CONTACT#{contact_id}"
                data["contactId"] = contact_id
                timestamp = datetime.utcnow().isoformat()
                data["createdAt"] = timestamp
                data["updatedAt"] = timestamp
                if "createdBy" in data:
                    data["updatedBy"] = data["createdBy"]
                
                try:
                    contact = ContactDetails(**data)
                except ValidationError as e:
                    return ErrorResponse.build(f"Validation error: {str(e)}", 400)
                
                item = contact.dict()
                item = prepare_item_for_storage(item, "CUSTOMER")
                try:
                    table.put_item(
                        Item=item,
                        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
                    )
                except Exception as e:
                    if "ConditionalCheckFailedException" in str(e):
                        logger.warning(f"Duplicate contact detected: {contact_id}")
                        return ErrorResponse.build(f"Contact {contact_id} already exists", 409)
                    logger.error(f"DynamoDB error: {str(e)}")
                    raise
                return SuccessResponse.build(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=True)), status_code=201)
            
            # POST /customers/{id}/addresses - Create address
            elif "id" in path_parameters and "/addresses" in path:
                customer_id = path_parameters["id"]
                pk = f"CUSTOMER#{customer_id}"
                
                # Validate customer exists
                check = table.get_item(Key={"PK": pk, "SK": "ENTITY#CUSTOMER"})
                if "Item" not in check:
                    return ErrorResponse.build("Customer not found", 404)
                
                # Generate address ID
                address_id = f"ADDR{str(uuid.uuid4())[:8].upper()}"
                
                # Set PK, SK, addressId, and timestamp
                data["PK"] = pk
                data["SK"] = f"ENTITY#ADDRESS#{address_id}"
                data["addressId"] = address_id
                timestamp = datetime.utcnow().isoformat()
                data["createdAt"] = timestamp
                data["updatedAt"] = timestamp
                if "createdBy" in data:
                    data["updatedBy"] = data["createdBy"]
                
                try:
                    address = AddressDetails(**data)
                except ValidationError as e:
                    return ErrorResponse.build(f"Validation error: {str(e)}", 400)
                
                item = address.dict()
                item = prepare_item_for_storage(item, "CUSTOMER")
                try:
                    table.put_item(
                        Item=item,
                        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
                    )
                except Exception as e:
                    if "ConditionalCheckFailedException" in str(e):
                        logger.warning(f"Duplicate address detected: {address_id}")
                        return ErrorResponse.build(f"Address {address_id} already exists", 409)
                    logger.error(f"DynamoDB error: {str(e)}")
                    raise
                return SuccessResponse.build(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=True)), status_code=201)
            
            # POST /customers - Create customer
            else:
                # Generate customer ID if not provided
                customer_id = f"CUST{str(uuid.uuid4())[:8].upper()}"
                
                # Prepare customer data
                customer_data = data.copy()
                customer_data["PK"] = f"CUSTOMER#{customer_id}"
                customer_data["SK"] = "ENTITY#CUSTOMER"
                customer_data["customerId"] = customer_id
                # Ensure customerNumber defaults to customerId if not provided
                if not customer_data.get("customerNumber"):
                    customer_data["customerNumber"] = customer_id
                customer_data["entityType"] = "customer"
                
                # Set timestamps
                timestamp = datetime.utcnow().isoformat() + "Z"
                if not customer_data.get("createdAt"):
                    customer_data["createdAt"] = timestamp
                customer_data["updatedAt"] = timestamp
                if "createdBy" in customer_data:
                    customer_data["updatedBy"] = customer_data["createdBy"]
                
                try:
                    customer = CustomerDetails(**customer_data)
                except ValidationError as e:
                    return ErrorResponse.build(f"Validation error: {str(e)}", 400)
                
                item = customer.dict()
                item = prepare_item_for_storage(item, "CUSTOMER")
                try:
                    table.put_item(
                        Item=item,
                        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
                    )
                except Exception as e:
                    if "ConditionalCheckFailedException" in str(e):
                        logger.warning(f"Duplicate customer detected: {item.get('PK')}")
                        return ErrorResponse.build(f"Customer {customer_id} already exists", 409)
                    logger.error(f"DynamoDB error: {str(e)}")
                    raise
                
                logger.info(f"Created customer with ID: {customer_id}")
                return SuccessResponse.build(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=True)), status_code=201)
        
        elif method == "PUT":
            body = event.get("body")
            if not body:
                return ErrorResponse.build("Missing request body", 400)
            
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return ErrorResponse.build("Invalid JSON", 400)
            
            # PUT /customers/{id}/contacts/{contactId} - Update contact
            if "id" in path_parameters and "contactId" in path_parameters:
                customer_id = path_parameters["id"]
                contact_id = path_parameters["contactId"]
                pk = f"CUSTOMER#{customer_id}"
                sk = f"ENTITY#CONTACT#{contact_id}"
                
                # Check if exists
                check = table.get_item(Key={"PK": pk, "SK": sk})
                if "Item" not in check:
                    return ErrorResponse.build("Contact not found", 404)
                
                # Set updatedAt and updatedBy
                data["updatedAt"] = datetime.utcnow().isoformat()
                if "createdBy" in data:
                    data["updatedBy"] = data["createdBy"]
                
                try:
                    contact = ContactDetails(**data)
                except ValidationError as e:
                    return ErrorResponse.build(f"Validation error: {str(e)}", 400)
                
                item = contact.dict()
                item = prepare_item_for_storage(item, "CUSTOMER")
                table.put_item(Item=item)
                return SuccessResponse.build(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=True)))
            
            # PUT /customers/{id}/addresses/{addressId} - Update address
            elif "id" in path_parameters and "addressId" in path_parameters:
                customer_id = path_parameters["id"]
                address_id = path_parameters["addressId"]
                pk = f"CUSTOMER#{customer_id}"
                sk = f"ENTITY#ADDRESS#{address_id}"
                
                # Check if exists
                check = table.get_item(Key={"PK": pk, "SK": sk})
                if "Item" not in check:
                    return ErrorResponse.build("Address not found", 404)
                
                # Set updatedAt and updatedBy
                data["updatedAt"] = datetime.utcnow().isoformat()
                if "createdBy" in data:
                    data["updatedBy"] = data["createdBy"]
                
                try:
                    address = AddressDetails(**data)
                except ValidationError as e:
                    return ErrorResponse.build(f"Validation error: {str(e)}", 400)
                
                item = address.dict()
                item = prepare_item_for_storage(item, "CUSTOMER")
                table.put_item(Item=item)
                return SuccessResponse.build(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=True)))
            
            # PUT /customers/{id} - Update customer
            elif "id" in path_parameters:
                customer_id = path_parameters["id"]
                pk = f"CUSTOMER#{customer_id}"
                sk = "ENTITY#CUSTOMER"
                
                # Check if exists
                check = table.get_item(Key={"PK": pk, "SK": sk})
                if "Item" not in check:
                    return ErrorResponse.build("Customer not found", 404)
                
                existing_item = check["Item"]
                
                # Set required fields (PK, SK, entityType)
                data["PK"] = pk
                data["SK"] = sk
                data["entityType"] = "customer"
                
                # Preserve customerId and ensure customerNumber is set
                data["customerId"] = customer_id
                if not data.get("customerNumber"):
                    # Use existing customerNumber if available, otherwise use customerId
                    data["customerNumber"] = existing_item.get("customerNumber") or customer_id
                
                # Preserve createdAt and createdBy
                if "createdAt" not in data and "createdAt" in existing_item:
                    data["createdAt"] = existing_item["createdAt"]
                if "createdBy" not in data and "createdBy" in existing_item:
                    data["createdBy"] = existing_item["createdBy"]
                
                # Set updatedAt and updatedBy
                data["updatedAt"] = datetime.utcnow().isoformat()
                if "createdBy" in data:
                    data["updatedBy"] = data["createdBy"]
                
                try:
                    customer = CustomerDetails(**data)
                except ValidationError as e:
                    return ErrorResponse.build(f"Validation error: {str(e)}", 400)
                
                item = customer.dict()
                item = prepare_item_for_storage(item, "CUSTOMER")
                table.put_item(Item=item)
                return SuccessResponse.build(simplify(prepare_item_for_response(item, "CUSTOMER", decrypt=True)))
        
        elif method == "DELETE":
            # Check for soft delete parameter
            soft_delete = query_parameters.get("soft") == "true" if query_parameters else False
            
            # DELETE /customers/{id}/contacts/{contactId} - Delete contact
            if "id" in path_parameters and "contactId" in path_parameters:
                customer_id = path_parameters["id"]
                contact_id = path_parameters["contactId"]
                pk = f"CUSTOMER#{customer_id}"
                sk = f"ENTITY#CONTACT#{contact_id}"
                
                # Check if exists
                check = table.get_item(Key={"PK": pk, "SK": sk})
                if "Item" not in check:
                    return ErrorResponse.build("Contact not found", 404)
                
                if soft_delete:
                    # Soft delete - mark as inactive
                    existing_item = check["Item"]
                    existing_item["isActive"] = False
                    existing_item["updatedAt"] = datetime.utcnow().isoformat()
                    if "updatedBy" in query_parameters:
                        existing_item["updatedBy"] = query_parameters["updatedBy"]
                    table.put_item(Item=existing_item)
                    return SuccessResponse.build({"message": "Contact soft deleted", "data": simplify(existing_item)})
                else:
                    # Hard delete
                    table.delete_item(Key={"PK": pk, "SK": sk})
                    return SuccessResponse.build({"message": "Contact deleted"})
            
            # DELETE /customers/{id}/addresses/{addressId} - Delete address
            elif "id" in path_parameters and "addressId" in path_parameters:
                customer_id = path_parameters["id"]
                address_id = path_parameters["addressId"]
                pk = f"CUSTOMER#{customer_id}"
                sk = f"ENTITY#ADDRESS#{address_id}"
                
                # Check if exists
                check = table.get_item(Key={"PK": pk, "SK": sk})
                if "Item" not in check:
                    return ErrorResponse.build("Address not found", 404)
                
                if soft_delete:
                    # Soft delete - mark as inactive
                    existing_item = check["Item"]
                    existing_item["isActive"] = False
                    existing_item["updatedAt"] = datetime.utcnow().isoformat()
                    if "updatedBy" in query_parameters:
                        existing_item["updatedBy"] = query_parameters["updatedBy"]
                    table.put_item(Item=existing_item)
                    return SuccessResponse.build({"message": "Address soft deleted", "data": simplify(existing_item)})
                else:
                    # Hard delete
                    table.delete_item(Key={"PK": pk, "SK": sk})
                    return SuccessResponse.build({"message": "Address deleted"})
            
            # DELETE /customers/{id} - Delete customer and all related data
            elif "id" in path_parameters:
                customer_id = path_parameters["id"]
                pk = f"CUSTOMER#{customer_id}"
                
                # Query all items for this customer
                response = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": pk}
                )
                
                items = response.get("Items", [])
                if not items:
                    return ErrorResponse.build("Customer not found", 404)
                
                if soft_delete:
                    # Soft delete - mark all items as inactive
                    timestamp = datetime.utcnow().isoformat()
                    updated_by = query_parameters.get("updatedBy") if query_parameters else None
                    
                    for item in items:
                        item["isActive"] = False
                        item["updatedAt"] = timestamp
                        if updated_by:
                            item["updatedBy"] = updated_by
                        table.put_item(Item=item)
                    
                    return SuccessResponse.build({"message": "Customer and all related data soft deleted", "itemsUpdated": len(items)})
                else:
                    # Hard delete all items
                    for item in items:
                        table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                    
                    return SuccessResponse.build({"message": "Customer and all related data deleted"})

        return ErrorResponse.build("Unsupported method", 405)

    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return ErrorResponse.build("Internal server error", 500)