import json
import os
import boto3
import logging
from decimal import Decimal
from shared.response_utils import SuccessResponse, ErrorResponse
from pydantic import BaseModel, ValidationError

# DynamoDB setup
TABLE_NAME = os.environ.get("TABLE_NAME", "v_users_dev")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Pydantic model for User
class UserDetails(BaseModel):
    id: str
    PK: str
    SK: str
    entityType: str = "USER"
    keycloakId: str
    email: str
    firstName: str
    lastName: str
    name: str
    role: str
    isActive: bool = True
    emailVerified: bool = False
    createdAt: str
    updatedAt: str

    class Config:
        extra = "forbid"

def simplify(item):
    def simplify_value(v):
        if isinstance(v, Decimal):
            return int(v) if v == int(v) else float(v)
        if isinstance(v, dict):
            return {k: simplify_value(nv) for k, nv in v.items()}
        if isinstance(v, list):
            return [simplify_value(x) for x in v]
        return v
    return {k: simplify_value(v) for k, v in item.items()}

def lambda_handler(event, context):
    logger.info(json.dumps(event))

    # Try multiple ways to extract the HTTP method (HTTP API 2.0 compatibility)
    method = (
        event.get("httpMethod") or 
        event.get("requestContext", {}).get("http", {}).get("method") or
        event.get("requestContext", {}).get("httpMethod")
    )
    
    # Extract path (HTTP API 2.0 uses rawPath, REST API uses path)
    path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path") or ""
    path_parameters = event.get("pathParameters") or {}

    # Log for debugging
    logger.info(f"Extracted method: {method}, path: {path}, pathParameters: {path_parameters}")

    if not method:
        logger.error("Could not extract HTTP method from event")
        return ErrorResponse.build("Could not determine HTTP method from request", 400)

    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return SuccessResponse.build({"message": "CORS preflight successful"}, 200)

    try:
        if method == "GET" and not path_parameters:
            # GET /users
            response = table.scan()
            items = response.get("Items", [])
            return SuccessResponse.build([simplify(item) for item in items])

        elif method == "GET" and "id" in path_parameters:
            # GET /users/{id}
            user_id = path_parameters["id"]
            logger.info(f"GET user with id={user_id}")
            response = table.get_item(Key={"id": user_id})
            item = response.get("Item")
            if not item:
                return ErrorResponse.build("User not found", 404)
            return SuccessResponse.build(simplify(item))

        elif method == "POST" and ("/users" in path or path == "/"):
            # POST /users
            body = event.get("body")
            if not body:
                return ErrorResponse.build("Missing request body", 400)
            try:
                data = json.loads(body)
                user = UserDetails(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Validation error: {e}")
                return ErrorResponse.build(f"Invalid user data: {str(e)}", 400)
            pk = f"USER#{user.id}"
            sk = "ENTITY#USER"
            item = user.dict()
            item["PK"] = pk
            item["SK"] = sk
            item["id"] = user.id
            logger.info(f"POST user creating with id={user.id}")
            table.put_item(Item=item)
            return SuccessResponse.build(simplify(item), status_code=201)

        elif method == "PUT" and "id" in path_parameters:
            # PUT /users/{id}
            user_id = path_parameters["id"]
            body = event.get("body")
            if not body:
                return ErrorResponse.build("Missing request body", 400)
            try:
                data = json.loads(body)
                user = UserDetails(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Validation error: {e}")
                return ErrorResponse.build(f"Invalid user data: {str(e)}", 400)
            pk = f"USER#{user_id}"
            sk = "ENTITY#USER"
            logger.info(f"PUT user with id={user_id}")
            # Check if user exists
            response = table.get_item(Key={"id": user_id})
            if "Item" not in response:
                return ErrorResponse.build("User not found", 404)
            item = user.dict()
            item["PK"] = pk
            item["SK"] = sk
            item["id"] = user_id
            table.put_item(Item=item)
            return SuccessResponse.build(simplify(item))

        elif method == "DELETE" and "id" in path_parameters:
            # DELETE /users/{id}
            user_id = path_parameters["id"]
            logger.info(f"DELETE user with id={user_id}")
            # Check if user exists
            response = table.get_item(Key={"id": user_id})
            if "Item" not in response:
                return ErrorResponse.build("User not found", 404)
            table.delete_item(Key={"id": user_id})
            return SuccessResponse.build({"message": "User deleted"})

        return ErrorResponse.build("Unsupported method", 405)

    except Exception:
        logger.exception("Unhandled error")
        return ErrorResponse.build("Internal server error", 500)
