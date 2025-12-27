import json
import os
import boto3
import logging
from decimal import Decimal
from shared.response_utils import SuccessResponse, ErrorResponse
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

    class Config:
        extra = "forbid"

class ContactDetails(BaseModel):
    PK: str
    SK: str
    entityType: str
    firstName: str
    lastName: str
    displayName: str
    email: str
    mobileNumber: str
    countryCode: str
    contactType: str
    createAsUser: bool
    userId: str
    isActive: bool
    createdAt: str
    createdBy: str

    class Config:
        extra = "forbid"

class AddressDetails(BaseModel):
    PK: str
    SK: str
    entityType: str
    addressType: str
    addressLine1: str
    addressLine2: str = None
    city: str
    state: str
    pincode: str
    country: str
    isActive: bool
    isPrimary: bool
    createdAt: str
    createdBy: str

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
    logger.info(f"Received event: {json.dumps(event)}")
    method = event.get("httpMethod")
    path = event.get("path")
    path_parameters = event.get("pathParameters", {})
    query_parameters = event.get("queryStringParameters", {})

    try:
        if method == "GET":
            if path == "/customers":
                # Handle GET /customers
                response = table.scan()
                items = response.get("Items", [])
                return SuccessResponse.build([simplify(item) for item in items])

            elif path.startswith("/customers/") and "id" in path_parameters:
                # Handle GET /customers/{id}
                customer_id = path_parameters["id"]
                pk = f"CUSTOMER#{customer_id}"
                sk = "ENTITY#CUSTOMER"
                response = table.get_item(Key={"PK": pk, "SK": sk})
                item = response.get("Item")
                if not item:
                    return ErrorResponse.build("Customer not found", 404)
                return SuccessResponse.build(simplify(item))

        return ErrorResponse.build("Unsupported method", 405)

    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return ErrorResponse.build("Internal server error", 500)