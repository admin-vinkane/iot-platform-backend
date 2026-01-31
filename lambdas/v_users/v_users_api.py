import json
import os
import boto3
import logging
from datetime import datetime
from decimal import Decimal
from shared.response_utils import SuccessResponse, ErrorResponse
from shared.encryption_utils import prepare_item_for_storage, prepare_item_for_response
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
    firebaseUid: str | None = None  # Populated on first login
    email: str
    firstName: str
    lastName: str
    name: str
    role: str
    isActive: bool = True
    emailVerified: bool = False
    createdAt: str
    updatedAt: str
    createdBy: str | None = None
    updatedBy: str | None = None

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

def verify_firebase_token(id_token):
    """
    Verify Firebase ID token and extract claims.
    Returns dict with 'uid' and 'email' if valid, None if invalid.
    
    Note: This is a placeholder. In production, you should:
    1. Install firebase-admin SDK
    2. Initialize with service account credentials
    3. Use firebase_admin.auth.verify_id_token(id_token)
    
    For now, we'll do basic JWT decode without verification for development.
    """
    try:
        import base64
        # Basic JWT decode (header.payload.signature)
        parts = id_token.split('.')
        if len(parts) != 3:
            return None
        
        # Decode payload (add padding if needed)
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)
        
        # Extract uid and email from claims
        if 'user_id' in claims and 'email' in claims:
            return {
                'uid': claims['user_id'],
                'email': claims['email'],
                'email_verified': claims.get('email_verified', False)
            }
        return None
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return None

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
    query_parameters = event.get("queryStringParameters") or {}

    # Log for debugging
    logger.info(f"Extracted method: {method}, path: {path}, pathParameters: {path_parameters}")

    if not method:
        logger.error("Could not extract HTTP method from event")
        return ErrorResponse.build("Could not determine HTTP method from request", 400)

    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return SuccessResponse.build({"message": "CORS preflight successful"}, 200)

    try:
        if query_parameters and "decrypt" in query_parameters:
            should_decrypt = query_parameters.get("decrypt", "").lower() == "true"
        else:
            should_decrypt = True
        
        if method == "GET" and not path_parameters:
            # GET /users
            response = table.scan()
            items = response.get("Items", [])
            items = [simplify(prepare_item_for_response(item, "USER", decrypt=should_decrypt)) for item in items]
            return SuccessResponse.build(items)

        elif method == "GET" and "id" in path_parameters:
            # GET /users/{id}
            user_id = path_parameters["id"]
            logger.info(f"GET user with id={user_id}")
            response = table.get_item(Key={"id": user_id})
            item = response.get("Item")
            if not item:
                return ErrorResponse.build("User not found", 404)
            item = prepare_item_for_response(item, "USER", decrypt=should_decrypt)
            return SuccessResponse.build(simplify(item))

        elif method == "POST" and "/users/sync" in path:
            # POST /users/sync - Link Firebase UID to DynamoDB user on first login
            body = event.get("body")
            if not body:
                return ErrorResponse.build("Missing request body", 400)
            
            try:
                data = json.loads(body)
                firebase_token = data.get("idToken")
                
                if not firebase_token:
                    return ErrorResponse.build("idToken is required", 400)
                
                # Verify Firebase token
                token_claims = verify_firebase_token(firebase_token)
                if not token_claims:
                    return ErrorResponse.build("Invalid Firebase token", 401)
                
                firebase_uid = token_claims['uid']
                email = token_claims['email']
                
                # Find user by email in DynamoDB
                response = table.scan(
                    FilterExpression="email = :email",
                    ExpressionAttributeValues={
                        ":email": email
                    }
                )
                
                items = response.get("Items", [])
                if not items:
                    return ErrorResponse.build(f"User with email {email} not found in system. Contact administrator.", 404)
                
                user = items[0]
                
                # Check if user is active
                if not user.get("isActive", False):
                    return ErrorResponse.build("User account is deactivated. Contact administrator.", 403)
                
                user_id = user["id"]
                
                # Update firebaseUid if not already set
                if not user.get("firebaseUid"):
                    timestamp = datetime.utcnow().isoformat() + "Z"
                    table.update_item(
                        Key={"id": user_id},
                        UpdateExpression="SET firebaseUid = :uid, updatedAt = :updated, emailVerified = :verified",
                        ExpressionAttributeValues={
                            ":uid": firebase_uid,
                            ":updated": timestamp,
                            ":verified": token_claims.get('email_verified', False)
                        }
                    )
                    user["firebaseUid"] = firebase_uid
                    user["emailVerified"] = token_claims.get('email_verified', False)
                    user["updatedAt"] = timestamp
                    logger.info(f"Linked Firebase UID {firebase_uid} to user {user_id}")
                else:
                    # Verify firebaseUid matches
                    if user["firebaseUid"] != firebase_uid:
                        return ErrorResponse.build("Email already linked to different Firebase account", 409)
                
                # Return user profile (remove sensitive fields)
                user_profile = simplify(user)
                logger.info(f"User {email} synced successfully")
                return SuccessResponse.build({
                    "message": "User synced successfully",
                    "user": user_profile
                })
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return ErrorResponse.build(f"Invalid JSON: {str(e)}", 400)
            except Exception as e:
                logger.error(f"Sync error: {str(e)}")
                return ErrorResponse.build(f"Sync error: {str(e)}", 500)

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
            
            # Set timestamps and audit fields
            timestamp = datetime.utcnow().isoformat() + "Z"
            if not item.get("createdAt"):
                item["createdAt"] = timestamp
            if not item.get("updatedAt"):
                item["updatedAt"] = timestamp
            if item.get("createdBy") and not item.get("updatedBy"):
                item["updatedBy"] = item["createdBy"]
            
            item = prepare_item_for_storage(item, "USER")
            logger.info(f"POST user creating with id={user.id}")
            table.put_item(Item=item)
            item = prepare_item_for_response(item, "USER", decrypt=True)
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
            
            # Update timestamp and audit fields
            item["updatedAt"] = datetime.utcnow().isoformat() + "Z"
            if item.get("createdBy") and not item.get("updatedBy"):
                item["updatedBy"] = item["createdBy"]
            
            item = prepare_item_for_storage(item, "USER")
            table.put_item(Item=item)
            item = prepare_item_for_response(item, "USER", decrypt=True)
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
