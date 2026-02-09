import json
import os
import boto3
import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import Optional, List, Dict, Any
from shared.response_utils import SuccessResponse, ErrorResponse
from shared.encryption_utils import prepare_item_for_storage, prepare_item_for_response
from pydantic import BaseModel, ValidationError, EmailStr, Field

# DynamoDB setup
TABLE_NAME = os.environ.get("TABLE_NAME", "v_users_dev")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "iot-platform-profile-pictures")
DEV_MODE = os.environ.get("DEV_MODE", "true").lower() == "true"  # Set to "false" in production
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

if DEV_MODE:
    logger.warning("⚠️  DEV_MODE is ENABLED - Authentication is BYPASSED! Set DEV_MODE=false in production.")

# Constants
ENTITY_TYPE_USER = "USER"
ENTITY_TYPE_PROFILE = "USER_PROFILE"
ENTITY_TYPE_ROLE = "ROLE"
ENTITY_TYPE_PERMISSION = "PERMISSION"
ENTITY_TYPE_USER_ROLE = "USER_ROLE"
ENTITY_TYPE_ROLE_PERMISSION = "ROLE_PERMISSION"
ENTITY_TYPE_COMPONENT = "COMPONENT"
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100

# Role definitions
class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    FIELD_TECHNICIAN = "field_technician"
    MANAGER = "manager"

# Permission levels for role-based access control
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        "user:read", "user:create", "user:update", "user:delete", "user:manage",
        "permission:read", "permission:manage", "permission:assign_role"
    ],
    UserRole.MANAGER: ["user:read", "user:create", "user:update"],
    UserRole.OPERATOR: ["user:read"],
    UserRole.VIEWER: ["user:read"],
    UserRole.FIELD_TECHNICIAN: ["user:read"]
}

# Pydantic model for User
class UserDetails(BaseModel):
    id: str
    PK: str
    SK: str
    entityType: str = Field(default=ENTITY_TYPE_USER)
    firebaseUid: Optional[str] = None  # Populated on first login
    email: EmailStr
    firstName: str = Field(min_length=1, max_length=100)
    lastName: str = Field(min_length=1, max_length=100)
    role: UserRole
    phoneNumber: Optional[str] = Field(default=None, pattern=r'^\+?[1-9]\d{1,14}$')
    isActive: bool = True
    emailVerified: bool = False
    lastLoginAt: Optional[str] = None
    loginCount: int = 0
    permissions: List[str] = Field(default_factory=list)
    # Region assignments
    stateId: Optional[str] = None
    districtId: Optional[str] = None
    mandalId: Optional[str] = None
    villageId: Optional[str] = None
    # Audit fields
    createdAt: str
    updatedAt: str
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None

    class Config:
        extra = "forbid"
        use_enum_values = True

# Model for partial updates (PATCH)
class UserUpdatePartial(BaseModel):
    firstName: Optional[str] = Field(default=None, min_length=1, max_length=100)
    lastName: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    phoneNumber: Optional[str] = Field(default=None, pattern=r'^\+?[1-9]\d{1,14}$')
    isActive: Optional[bool] = None
    stateId: Optional[str] = None
    districtId: Optional[str] = None
    mandalId: Optional[str] = None
    villageId: Optional[str] = None
    updatedBy: Optional[str] = None

    class Config:
        extra = "forbid"
        use_enum_values = True

# Pydantic model for User Profile
class Address(BaseModel):
    street: Optional[str] = Field(default="", max_length=200)
    city: Optional[str] = Field(default="", max_length=100)
    state: Optional[str] = Field(default="", max_length=100)
    country: Optional[str] = Field(default="", max_length=100)
    postalCode: Optional[str] = Field(default="", max_length=20)

    class Config:
        extra = "forbid"

class Preferences(BaseModel):
    notifications: bool = True
    emailAlerts: bool = True
    smsAlerts: bool = False

    class Config:
        extra = "forbid"

class UserProfile(BaseModel):
    PK: str
    SK: str
    userId: str
    entityType: str = Field(default=ENTITY_TYPE_PROFILE)
    firstName: str = Field(min_length=1, max_length=100)
    lastName: str = Field(min_length=1, max_length=100)
    phoneNumber: Optional[str] = Field(default=None, pattern=r'^\+?[1-9]\d{1,14}$')
    language: str = Field(default="en", pattern=r'^[a-z]{2}$')
    organization: Optional[str] = Field(default=None, max_length=200)
    department: Optional[str] = Field(default=None, max_length=100)
    timezone: Optional[str] = Field(default="UTC", max_length=50)
    profilePictureUrl: Optional[str] = None
    address: Address = Field(default_factory=Address)
    preferences: Preferences = Field(default_factory=Preferences)
    createdAt: str
    updatedAt: str

    class Config:
        extra = "forbid"

class UpdateProfileRequest(BaseModel):
    firstName: Optional[str] = Field(default=None, min_length=1, max_length=100)
    lastName: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phoneNumber: Optional[str] = Field(default=None, pattern=r'^\+?[1-9]\d{1,14}$')
    language: Optional[str] = Field(default=None, pattern=r'^[a-z]{2}$')
    organization: Optional[str] = Field(default=None, max_length=200)
    department: Optional[str] = Field(default=None, max_length=100)
    timezone: Optional[str] = Field(default=None, max_length=50)
    profilePictureUrl: Optional[str] = None
    address: Optional[Address] = None
    preferences: Optional[Preferences] = None

    class Config:
        extra = "forbid"

# ====== RBAC Pydantic Models ======

class RoleCreate(BaseModel):
    roleName: str = Field(..., min_length=1, max_length=100)
    displayName: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    level: int = Field(default=10, ge=0, le=100)
    isSystem: bool = False
    
class RoleUpdate(BaseModel):
    displayName: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    level: Optional[int] = Field(None, ge=0, le=100)
    isSystem: Optional[bool] = None

class PermissionCreate(BaseModel):
    permissionName: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z_]+:[a-z_]+$')
    displayName: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    category: str = Field(..., min_length=1, max_length=100)

class PermissionUpdate(BaseModel):
    displayName: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, min_length=1, max_length=100)

class UserRoleAssignment(BaseModel):
    userId: str = Field(..., min_length=1)
    roleName: str = Field(..., min_length=1)
    assignedBy: Optional[str] = None
    expiresAt: Optional[str] = None

class ComponentCreate(BaseModel):
    componentName: str = Field(..., min_length=1, max_length=100)
    path: str = Field(..., min_length=1, max_length=200)
    icon: Optional[str] = None
    order: int = Field(default=0, ge=0)
    category: Optional[str] = None
    requiredPermissions: List[str] = []
    optionalPermissions: List[str] = []

# ====== End RBAC Models ======

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

def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Firebase ID token and extract claims.
    Returns dict with user info if valid, None if invalid.
    
    In production with firebase-admin installed:
    ```python
    import firebase_admin
    from firebase_admin import auth, credentials
    
    # Initialize once (do this at module level)
    cred = credentials.Certificate('/path/to/serviceAccountKey.json')
    firebase_admin.initialize_app(cred)
    
    # Then use in this function:
    try:
        decoded_token = auth.verify_id_token(id_token)
        return {
            'uid': decoded_token['uid'],
            'email': decoded_token.get('email'),
            'email_verified': decoded_token.get('email_verified', False),
            'name': decoded_token.get('name'),
            'role': decoded_token.get('role', UserRole.VIEWER)
        }
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None
    ```
    """
    try:
        # Try to import firebase_admin
        try:
            from firebase_admin import auth
            # Attempt real verification
            decoded_token = auth.verify_id_token(id_token)
            return {
                'uid': decoded_token['uid'],
                'email': decoded_token.get('email'),
                'email_verified': decoded_token.get('email_verified', False),
                'name': decoded_token.get('name'),
                'role': decoded_token.get('role', UserRole.VIEWER.value)
            }
        except ImportError:
            # Fallback for development (INSECURE - for testing only)
            logger.warning("firebase-admin not installed. Using INSECURE token decode for development only!")
            import base64
            parts = id_token.split('.')
            if len(parts) != 3:
                return None
            
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            
            decoded = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded)
            
            if 'user_id' in claims and 'email' in claims:
                return {
                    'uid': claims['user_id'],
                    'email': claims['email'],
                    'email_verified': claims.get('email_verified', False),
                    'name': claims.get('name'),
                    'role': claims.get('role', UserRole.VIEWER.value)
                }
            return None
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return None

def extract_user_from_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract authenticated user from request event.
    Looks for Authorization header with Bearer token.
    In DEV_MODE, returns a mock admin user for testing.
    """
    # DEV_MODE: Bypass authentication and return mock admin user
    if DEV_MODE:
        logger.info("🔓 DEV_MODE: Bypassing authentication, returning mock admin user")
        return {
            'uid': 'dev-admin-uid',
            'email': 'dev-admin@test.com',
            'email_verified': True,
            'name': 'Dev Admin',
            'role': UserRole.ADMIN.value
        }
    
    try:
        headers = event.get("headers", {})
        # Headers might be lowercase or mixed case
        auth_header = headers.get("Authorization") or headers.get("authorization")
        
        if not auth_header:
            return None
        
        if not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.replace("Bearer ", "")
        return verify_firebase_token(token)
    except Exception as e:
        logger.error(f"Error extracting user from event: {e}")
        return None

def check_permission(user: Optional[Dict[str, Any]], required_permission: str) -> bool:
    """
    Check if user has the required permission based on their role.
    """
    if not user:
        return False
    
    user_role = user.get('role', UserRole.VIEWER.value)
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            return False
    
    permissions = ROLE_PERMISSIONS.get(user_role, [])
    return required_permission in permissions

def require_permission(permission: str):
    """
    Decorator to check if authenticated user has required permission.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(event, context, *args, **kwargs):
            user = extract_user_from_event(event)
            if not user:
                return ErrorResponse.build("Authentication required", 401)
            
            if not check_permission(user, permission):
                return ErrorResponse.build(
                    f"Insufficient permissions. Required: {permission}",
                    403
                )
            
            # Add user to kwargs for handler to use
            return func(event, context, authenticated_user=user, *args, **kwargs)
        return wrapper
    return decorator


# Profile Handler Functions

def handle_get_profile(user_id: str, authenticated_user: Optional[Dict[str, Any]], should_decrypt: bool):
    """GET /users/{userId}/profile - Get user profile."""
    # Users can only access their own profile unless they're admin
    if authenticated_user:
        auth_user_id = authenticated_user.get('uid')
        is_admin = authenticated_user.get('role') == UserRole.ADMIN.value
        if auth_user_id != user_id and not is_admin:
            return ErrorResponse.build("You can only access your own profile", 403)
    else:
        return ErrorResponse.build("Authentication required", 401)
    
    try:
        logger.info(f"GET profile for user_id={user_id}")
        
        # Get profile from DynamoDB
        response = table.get_item(
            Key={"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"}
        )
        
        if "Item" not in response:
            # Profile doesn't exist - create default profile
            logger.info(f"Profile not found for user {user_id}, creating default")
            return handle_create_default_profile(user_id, authenticated_user)
        
        profile_item = response["Item"]
        profile_item = prepare_item_for_response(profile_item, ENTITY_TYPE_PROFILE, decrypt=should_decrypt)
        simplified_profile = simplify(profile_item)
        
        # Remove internal DynamoDB fields
        cleaned_profile = {k: v for k, v in simplified_profile.items() if k not in ['PK', 'SK', 'entityType']}
        
        return SuccessResponse.build(cleaned_profile)
    
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        return ErrorResponse.build(f"Error getting profile: {str(e)}", 500)


def handle_create_default_profile(user_id: str, authenticated_user: Optional[Dict[str, Any]]):
    """Create a default profile for a user."""
    try:
        # Get user details first
        user_response = table.get_item(Key={"id": user_id})
        if "Item" not in user_response:
            return ErrorResponse.build(f"User {user_id} not found", 404)
        
        user = user_response["Item"]
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Create default profile
        profile_item = {
            "PK": f"USER#{user_id}",
            "SK": "PROFILE#MAIN",
            "userId": user_id,
            "entityType": ENTITY_TYPE_PROFILE,
            "firstName": user.get("firstName", ""),
            "lastName": user.get("lastName", ""),
            "phoneNumber": user.get("phoneNumber"),
            "language": "en",
            "organization": None,
            "department": None,
            "timezone": "UTC",
            "profilePictureUrl": None,
            "address": {
                "street": "",
                "city": "",
                "state": "",
                "country": "",
                "postalCode": ""
            },
            "preferences": {
                "notifications": True,
                "emailAlerts": True,
                "smsAlerts": False
            },
            "createdAt": timestamp,
            "updatedAt": timestamp
        }
        
        profile_item = prepare_item_for_storage(profile_item, ENTITY_TYPE_PROFILE)
        table.put_item(Item=profile_item)
        
        profile_item = prepare_item_for_response(profile_item, ENTITY_TYPE_PROFILE, decrypt=True)
        return SuccessResponse.build(simplify(profile_item), status_code=201)
    
    except Exception as e:
        logger.error(f"Error creating default profile: {str(e)}")
        return ErrorResponse.build(f"Error creating default profile: {str(e)}", 500)


def handle_update_profile(user_id: str, event: Dict[str, Any], authenticated_user: Optional[Dict[str, Any]]):
    """PUT /users/{userId}/profile - Update entire profile."""
    # Users can only update their own profile unless they're admin
    if authenticated_user:
        auth_user_id = authenticated_user.get('uid')
        is_admin = authenticated_user.get('role') == UserRole.ADMIN.value
        if auth_user_id != user_id and not is_admin:
            return ErrorResponse.build("You can only update your own profile", 403)
    else:
        return ErrorResponse.build("Authentication required", 401)
    
    body = event.get("body")
    if not body:
        return ErrorResponse.build("Missing request body", 400)
    
    try:
        data = json.loads(body)
        
        # Get existing profile
        response = table.get_item(
            Key={"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"}
        )
        
        existing_profile = response.get("Item", {})
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Build updated profile
        profile_item = {
            "PK": f"USER#{user_id}",
            "SK": "PROFILE#MAIN",
            "userId": user_id,
            "entityType": ENTITY_TYPE_PROFILE,
            "firstName": data.get("firstName", existing_profile.get("firstName", "")),
            "lastName": data.get("lastName", existing_profile.get("lastName", "")),
            "phoneNumber": data.get("phoneNumber", existing_profile.get("phoneNumber")),
            "language": data.get("language", existing_profile.get("language", "en")),
            "organization": data.get("organization", existing_profile.get("organization")),
            "department": data.get("department", existing_profile.get("department")),
            "timezone": data.get("timezone", existing_profile.get("timezone", "UTC")),
            "profilePictureUrl": data.get("profilePictureUrl", existing_profile.get("profilePictureUrl")),
            "address": data.get("address", existing_profile.get("address", {
                "street": "", "city": "", "state": "", "country": "", "postalCode": ""
            })),
            "preferences": data.get("preferences", existing_profile.get("preferences", {
                "notifications": True, "emailAlerts": True, "smsAlerts": False
            })),
            "createdAt": existing_profile.get("createdAt", timestamp),
            "updatedAt": timestamp
        }
        
        # Validate with Pydantic
        try:
            UserProfile(**profile_item)
        except ValidationError as e:
            return ErrorResponse.build(f"Invalid profile data: {str(e)}", 400)
        
        profile_item = prepare_item_for_storage(profile_item, ENTITY_TYPE_PROFILE)
        table.put_item(Item=profile_item)
        
        profile_item = prepare_item_for_response(profile_item, ENTITY_TYPE_PROFILE, decrypt=True)
        simplified_profile = simplify(profile_item)
        
        # Remove internal DynamoDB fields
        cleaned_profile = {k: v for k, v in simplified_profile.items() if k not in ['PK', 'SK', 'entityType']}
        
        return SuccessResponse.build({
            "message": "Profile updated successfully",
            "profile": cleaned_profile
        })
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return ErrorResponse.build(f"Invalid JSON: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return ErrorResponse.build(f"Error updating profile: {str(e)}", 500)


def handle_update_profile_partial(user_id: str, event: Dict[str, Any], authenticated_user: Optional[Dict[str, Any]]):
    """PATCH /users/{userId}/profile - Partially update profile."""
    # Users can only update their own profile unless they're admin
    if authenticated_user:
        auth_user_id = authenticated_user.get('uid')
        is_admin = authenticated_user.get('role') == UserRole.ADMIN.value
        if auth_user_id != user_id and not is_admin:
            return ErrorResponse.build("You can only update your own profile", 403)
    else:
        return ErrorResponse.build("Authentication required", 401)
    
    body = event.get("body")
    if not body:
        return ErrorResponse.build("Missing request body", 400)
    
    try:
        data = json.loads(body)
        
        # Validate with Pydantic
        try:
            update_data = UpdateProfileRequest(**data)
        except ValidationError as e:
            return ErrorResponse.build(f"Invalid profile data: {str(e)}", 400)
        
        # Get existing profile or create if doesn't exist
        response = table.get_item(
            Key={"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"}
        )
        
        if "Item" not in response:
            # Create default profile first
            create_response = handle_create_default_profile(user_id, authenticated_user)
            if create_response.get("statusCode") not in [200, 201]:
                return create_response
            response = table.get_item(
                Key={"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"}
            )
        
        # Build update expression
        update_expr_parts = []
        expr_values = {}
        expr_names = {}
        
        update_dict = update_data.dict(exclude_unset=True, exclude_none=True)
        
        if not update_dict:
            return ErrorResponse.build("No fields to update", 400)
        
        for field, value in update_dict.items():
            if field in ["address", "preferences"]:
                # Handle nested objects
                update_expr_parts.append(f"#{field} = :{field}")
                expr_names[f"#{field}"] = field
                expr_values[f":{field}"] = value if isinstance(value, dict) else value.dict()
            else:
                update_expr_parts.append(f"{field} = :{field}")
                expr_values[f":{field}"] = value
        
        # Always update timestamp
        timestamp = datetime.utcnow().isoformat() + "Z"
        update_expr_parts.append("updatedAt = :updatedAt")
        expr_values[":updatedAt"] = timestamp
        
        update_expression = "SET " + ", ".join(update_expr_parts)
        
        update_params = {
            "Key": {"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expr_values,
            "ReturnValues": "ALL_NEW"
        }
        
        if expr_names:
            update_params["ExpressionAttributeNames"] = expr_names
        
        response = table.update_item(**update_params)
        
        updated_profile = simplify(response["Attributes"])
        logger.info(f"Partially updated profile for user {user_id}: {list(update_dict.keys())}")
        
        # Remove internal DynamoDB fields
        cleaned_profile = {k: v for k, v in updated_profile.items() if k not in ['PK', 'SK', 'entityType']}
        
        return SuccessResponse.build({
            "message": "Profile updated successfully",
            "profile": cleaned_profile,
            "updatedFields": list(update_dict.keys())
        })
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return ErrorResponse.build(f"Invalid JSON: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return ErrorResponse.build(f"Error updating profile: {str(e)}", 500)


def handle_upload_profile_picture(user_id: str, event: Dict[str, Any], authenticated_user: Optional[Dict[str, Any]]):
    """POST /users/{userId}/profile/picture - Upload profile picture to S3."""
    # Users can only upload their own profile picture unless they're admin
    if authenticated_user:
        auth_user_id = authenticated_user.get('uid')
        is_admin = authenticated_user.get('role') == UserRole.ADMIN.value
        if auth_user_id != user_id and not is_admin:
            return ErrorResponse.build("You can only upload your own profile picture", 403)
    else:
        return ErrorResponse.build("Authentication required", 401)
    
    body = event.get("body")
    if not body:
        return ErrorResponse.build("Missing request body", 400)
    
    try:
        data = json.loads(body)
        
        # Expect base64 encoded image and file type
        image_data = data.get("imageData")
        content_type = data.get("contentType", "image/jpeg")
        file_extension = data.get("fileExtension", "jpg")
        
        if not image_data:
            return ErrorResponse.build("imageData is required", 400)
        
        # Validate content type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
        if content_type not in allowed_types:
            return ErrorResponse.build(f"Invalid content type. Allowed: {', '.join(allowed_types)}", 400)
        
        # Decode base64 image
        try:
            import base64
            if ',' in image_data:
                # Remove data:image/xxx;base64, prefix if present
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            return ErrorResponse.build(f"Invalid base64 image data: {str(e)}", 400)
        
        # Validate image size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(image_bytes) > max_size:
            return ErrorResponse.build("Image size exceeds 5MB limit", 400)
        
        # Generate S3 key
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        s3_key = f"profile-pictures/{user_id}/{timestamp}.{file_extension}"
        
        # Upload to S3
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=image_bytes,
                ContentType=content_type,
                Metadata={
                    "userId": user_id,
                    "uploadedAt": datetime.utcnow().isoformat()
                }
            )
            
            # Generate public URL (adjust based on your S3 configuration)
            profile_picture_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
            
            logger.info(f"Uploaded profile picture for user {user_id} to {s3_key}")
        except Exception as s3_error:
            logger.error(f"S3 upload failed: {str(s3_error)}")
            return ErrorResponse.build(f"Failed to upload image: {str(s3_error)}", 500)
        
        # Update profile with new picture URL
        try:
            timestamp_iso = datetime.utcnow().isoformat() + "Z"
            
            # Check if profile exists
            profile_response = table.get_item(
                Key={"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"}
            )
            
            if "Item" not in profile_response:
                # Create profile if doesn't exist
                create_response = handle_create_default_profile(user_id, authenticated_user)
                if create_response.get("statusCode") not in [200, 201]:
                    return create_response
            
            # Update profile with new URL
            table.update_item(
                Key={"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"},
                UpdateExpression="SET profilePictureUrl = :url, updatedAt = :updated",
                ExpressionAttributeValues={
                    ":url": profile_picture_url,
                    ":updated": timestamp_iso
                }
            )
            
            return SuccessResponse.build({
                "message": "Profile picture uploaded successfully",
                "profilePictureUrl": profile_picture_url,
                "s3Key": s3_key
            })
        
        except Exception as db_error:
            logger.error(f"Failed to update profile with picture URL: {str(db_error)}")
            return ErrorResponse.build(f"Image uploaded but failed to update profile: {str(db_error)}", 500)
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return ErrorResponse.build(f"Invalid JSON: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error uploading profile picture: {str(e)}")
        return ErrorResponse.build(f"Error uploading profile picture: {str(e)}", 500)


def handle_get_profile_picture_upload_url(user_id: str, event: Dict[str, Any], authenticated_user: Optional[Dict[str, Any]]):
    """GET /users/{userId}/profile/picture/upload-url - Generate presigned S3 URL for direct upload."""
    # Users can only get their own upload URL unless they're admin
    if authenticated_user:
        auth_user_id = authenticated_user.get('uid')
        is_admin = authenticated_user.get('role') == UserRole.ADMIN.value
        if auth_user_id != user_id and not is_admin:
            return ErrorResponse.build("You can only get your own upload URL", 403)
    else:
        return ErrorResponse.build("Authentication required", 401)
    
    query_parameters = event.get("queryStringParameters") or {}
    content_type = query_parameters.get("contentType", "image/jpeg")
    file_extension = query_parameters.get("fileExtension", "jpg")
    
    # Validate content type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if content_type not in allowed_types:
        return ErrorResponse.build(f"Invalid content type. Allowed: {', '.join(allowed_types)}", 400)
    
    try:
        # Generate S3 key
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        s3_key = f"profile-pictures/{user_id}/{timestamp}.{file_extension}"
        
        # Generate presigned POST URL (allows direct upload from client)
        presigned_post = s3_client.generate_presigned_post(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Fields={
                "Content-Type": content_type,
                "x-amz-meta-userId": user_id
            },
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 0, 5242880]  # 5MB max
            ],
            ExpiresIn=3600  # 1 hour
        )
        
        # Generate the public URL
        profile_picture_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        
        return SuccessResponse.build({
            "uploadUrl": presigned_post["url"],
            "fields": presigned_post["fields"],
            "profilePictureUrl": profile_picture_url,
            "s3Key": s3_key,
            "expiresIn": 3600,
            "instructions": {
                "method": "POST",
                "description": "Use the uploadUrl and include all fields in the form data along with the file"
            }
        })
    
    except Exception as e:
        logger.error(f"Error generating upload URL: {str(e)}")
        return ErrorResponse.build(f"Error generating upload URL: {str(e)}", 500)


# ====== RBAC HANDLERS ======

def handle_create_role(event: dict, authenticated_user: dict):
    """Create a new role"""
    if not check_permission(authenticated_user, "permission:manage"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        body = json.loads(event.get("body", "{}"))
        role_data = RoleCreate(**body)
        
        role_name = role_data.roleName.lower().replace(" ", "_")
        pk = f"ROLE#{role_name}"
        sk = "META"
        
        # Check if role already exists
        response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" in response:
            return ErrorResponse.build(f"Role '{role_name}' already exists", 409)
        
        # Create role item
        timestamp = datetime.utcnow().isoformat()
        item = {
            "PK": pk,
            "SK": sk,
            "entityType": ENTITY_TYPE_ROLE,
            "roleName": role_name,
            "displayName": role_data.displayName,
            "description": role_data.description,
            "level": role_data.level,
            "isSystem": role_data.isSystem,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "createdBy": authenticated_user["uid"]
        }
        
        table.put_item(Item=item)
        
        clean_item = simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]})
        
        return SuccessResponse.build({"message": "Role created successfully", "data": clean_item}, 201)
        
    except ValidationError as e:
        return ErrorResponse.build(f"Validation error: {str(e.errors())}", 400)
    except Exception as e:
        logger.error(f"Error creating role: {str(e)}")
        return ErrorResponse.build(f"Failed to create role: {str(e)}", 500)


def handle_get_role(role_name: str, authenticated_user: dict):
    """Get role by name"""
    if not check_permission(authenticated_user, "permission:read"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        pk = f"ROLE#{role_name}"
        sk = "META"
        
        response = table.get_item(Key={"PK": pk, "SK": sk})
        
        if "Item" not in response:
            return ErrorResponse.build(f"Role '{role_name}' not found", 404)
        
        item = response["Item"]
        clean_item = simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]})
        
        return SuccessResponse.build({"message": "Role retrieved successfully", "data": clean_item}, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving role: {str(e)}")
        return ErrorResponse.build(f"Failed to retrieve role: {str(e)}", 500)


def handle_list_roles(authenticated_user: dict):
    """List all roles"""
    if not check_permission(authenticated_user, "permission:read"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        response = table.scan(
            FilterExpression="entityType = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_ROLE}
        )
        
        items = response.get("Items", [])
        clean_items = [simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]}) for item in items]
        
        return SuccessResponse.build({
            "message": "Roles retrieved successfully",
            "data": clean_items,
            "meta": {"count": len(clean_items)}
        }, 200)
        
    except Exception as e:
        logger.error(f"Error listing roles: {str(e)}")
        return ErrorResponse.build(f"Failed to list roles: {str(e)}", 500)


def handle_update_role(role_name: str, event: dict, authenticated_user: dict):
    """Update an existing role"""
    if not check_permission(authenticated_user, "permission:manage"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        body = json.loads(event.get("body", "{}"))
        update_data = RoleUpdate(**body)
        
        pk = f"ROLE#{role_name}"
        sk = "META"
        
        # Check if role exists
        response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" not in response:
            return ErrorResponse.build(f"Role '{role_name}' not found", 404)
        
        existing_item = response["Item"]
        
        # Prevent updating system roles
        if existing_item.get("isSystem", False):
            return ErrorResponse.build("Cannot update system roles", 403)
        
        # Build update expression
        update_expr_parts = ["updatedAt = :updated_at"]
        expr_attr_values = {":updated_at": datetime.utcnow().isoformat()}
        expr_attr_names = {}
        
        if update_data.displayName is not None:
            update_expr_parts.append("displayName = :display_name")
            expr_attr_values[":display_name"] = update_data.displayName
        
        if update_data.description is not None:
            update_expr_parts.append("description = :description")
            expr_attr_values[":description"] = update_data.description
        
        if update_data.level is not None:
            update_expr_parts.append("#level = :level")
            expr_attr_values[":level"] = update_data.level
            expr_attr_names["#level"] = "level"
        
        if update_data.isSystem is not None:
            update_expr_parts.append("isSystem = :is_system")
            expr_attr_values[":is_system"] = update_data.isSystem
        
        update_expression = "SET " + ", ".join(update_expr_parts)
        
        kwargs = {
            "Key": {"PK": pk, "SK": sk},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expr_attr_values,
            "ReturnValues": "ALL_NEW"
        }
        
        if expr_attr_names:
            kwargs["ExpressionAttributeNames"] = expr_attr_names
        
        response = table.update_item(**kwargs)
        
        updated_item = response["Attributes"]
        clean_item = simplify({k: v for k, v in updated_item.items() if k not in ["PK", "SK", "entityType"]})
        
        return SuccessResponse.build({"message": "Role updated successfully", "data": clean_item}, 200)
        
    except ValidationError as e:
        return ErrorResponse.build(f"Validation error: {str(e.errors())}", 400)
    except Exception as e:
        logger.error(f"Error updating role: {str(e)}")
        return ErrorResponse.build(f"Failed to update role: {str(e)}", 500)


def handle_delete_role(role_name: str, authenticated_user: dict):
    """Delete a role"""
    if not check_permission(authenticated_user, "permission:manage"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        pk = f"ROLE#{role_name}"
        sk = "META"
        
        # Check if role exists
        response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" not in response:
            return ErrorResponse.build(f"Role '{role_name}' not found", 404)
        
        existing_item = response["Item"]
        
        # Prevent deleting system roles
        if existing_item.get("isSystem", False):
            return ErrorResponse.build("Cannot delete system roles", 403)
        
        # Delete role
        table.delete_item(Key={"PK": pk, "SK": sk})
        
        return SuccessResponse.build({"message": f"Role '{role_name}' deleted successfully"}, 200)
        
    except Exception as e:
        logger.error(f"Error deleting role: {str(e)}")
        return ErrorResponse.build(f"Failed to delete role: {str(e)}", 500)


def handle_create_permission(event: dict, authenticated_user: dict):
    """Create a new permission"""
    if not check_permission(authenticated_user, "permission:manage"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        body = json.loads(event.get("body", "{}"))
        perm_data = PermissionCreate(**body)
        
        pk = f"PERMISSION#{perm_data.permissionName}"
        sk = "META"
        
        # Check if permission already exists
        response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" in response:
            return ErrorResponse.build(f"Permission '{perm_data.permissionName}' already exists", 409)
        
        # Create permission item
        timestamp = datetime.utcnow().isoformat()
        item = {
            "PK": pk,
            "SK": sk,
            "entityType": ENTITY_TYPE_PERMISSION,
            "permissionName": perm_data.permissionName,
            "displayName": perm_data.displayName,
            "description": perm_data.description,
            "resource": perm_data.resource,
            "action": perm_data.action,
            "category": perm_data.category,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "createdBy": authenticated_user["uid"]
        }
        
        table.put_item(Item=item)
        
        clean_item = simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]})
        
        return SuccessResponse.build({"message": "Permission created successfully", "data": clean_item}, 201)
        
    except ValidationError as e:
        return ErrorResponse.build(f"Validation error: {str(e.errors())}", 400)
    except Exception as e:
        logger.error(f"Error creating permission: {str(e)}")
        return ErrorResponse.build(f"Failed to create permission: {str(e)}", 500)


def handle_get_permission(permission_name: str, authenticated_user: dict):
    """Get permission by name"""
    if not check_permission(authenticated_user, "permission:read"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        pk = f"PERMISSION#{permission_name}"
        sk = "META"
        
        response = table.get_item(Key={"PK": pk, "SK": sk})
        
        if "Item" not in response:
            return ErrorResponse.build(f"Permission '{permission_name}' not found", 404)
        
        item = response["Item"]
        clean_item = simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]})
        
        return SuccessResponse.build({"message": "Permission retrieved successfully", "data": clean_item}, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving permission: {str(e)}")
        return ErrorResponse.build(f"Failed to retrieve permission: {str(e)}", 500)


def handle_list_permissions(authenticated_user: dict):
    """List all permissions"""
    if not check_permission(authenticated_user, "permission:read"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        response = table.scan(
            FilterExpression="entityType = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_PERMISSION}
        )
        
        items = response.get("Items", [])
        clean_items = [simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]}) for item in items]
        
        return SuccessResponse.build({
            "message": "Permissions retrieved successfully",
            "data": clean_items,
            "meta": {"count": len(clean_items)}
        }, 200)
        
    except Exception as e:
        logger.error(f"Error listing permissions: {str(e)}")
        return ErrorResponse.build(f"Failed to list permissions: {str(e)}", 500)


def handle_assign_permission_to_role(role_name: str, event: dict, authenticated_user: dict):
    """Assign a permission to a role"""
    if not check_permission(authenticated_user, "permission:manage"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        body = json.loads(event.get("body", "{}"))
        permission_name = body.get("permissionName")
        
        if not permission_name:
            return ErrorResponse.build("Permission name is required", 400)
        
        # Verify role exists
        role_response = table.get_item(Key={"PK": f"ROLE#{role_name}", "SK": "META"})
        if "Item" not in role_response:
            return ErrorResponse.build(f"Role '{role_name}' not found", 404)
        
        # Verify permission exists
        perm_response = table.get_item(Key={"PK": f"PERMISSION#{permission_name}", "SK": "META"})
        if "Item" not in perm_response:
            return ErrorResponse.build(f"Permission '{permission_name}' not found", 404)
        
        # Create role-permission assignment
        pk = f"ROLE#{role_name}"
        sk = f"PERMISSION#{permission_name}"
        
        # Check if assignment already exists
        assignment_response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" in assignment_response:
            return ErrorResponse.build("Permission already assigned to role", 409)
        
        timestamp = datetime.utcnow().isoformat()
        item = {
            "PK": pk,
            "SK": sk,
            "entityType": ENTITY_TYPE_ROLE_PERMISSION,
            "roleName": role_name,
            "permissionName": permission_name,
            "assignedAt": timestamp,
            "assignedBy": authenticated_user["uid"]
        }
        
        table.put_item(Item=item)
        
        clean_item = simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]})
        
        return SuccessResponse.build({"message": "Permission assigned to role successfully", "data": clean_item}, 201)
        
    except Exception as e:
        logger.error(f"Error assigning permission to role: {str(e)}")
        return ErrorResponse.build(f"Failed to assign permission: {str(e)}", 500)


def handle_get_role_permissions(role_name: str, authenticated_user: dict):
    """Get all permissions for a role"""
    if not check_permission(authenticated_user, "permission:read"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        # Verify role exists
        role_response = table.get_item(Key={"PK": f"ROLE#{role_name}", "SK": "META"})
        if "Item" not in role_response:
            return ErrorResponse.build(f"Role '{role_name}' not found", 404)
        
        # Query role permissions
        pk = f"ROLE#{role_name}"
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": pk,
                ":sk_prefix": "PERMISSION#"
            }
        )
        
        items = response.get("Items", [])
        
        # Get full permission details
        permissions = []
        for item in items:
            perm_name = item.get("permissionName")
            perm_response = table.get_item(Key={"PK": f"PERMISSION#{perm_name}", "SK": "META"})
            if "Item" in perm_response:
                perm_item = perm_response["Item"]
                clean_perm = {k: v for k, v in perm_item.items() if k not in ["PK", "SK", "entityType"]}
                permissions.append(clean_perm)
        
        return SuccessResponse.build({
            "message": "Role permissions retrieved successfully",
            "data": permissions,
            "meta": {"count": len(permissions)}
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving role permissions: {str(e)}")
        return ErrorResponse.build(f"Failed to retrieve permissions: {str(e)}", 500)


def handle_remove_permission_from_role(role_name: str, permission_name: str, authenticated_user: dict):
    """Remove a permission from a role"""
    if not check_permission(authenticated_user, "permission:manage"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        pk = f"ROLE#{role_name}"
        sk = f"PERMISSION#{permission_name}"
        
        # Check if assignment exists
        response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" not in response:
            return ErrorResponse.build("Permission assignment not found", 404)
        
        # Delete assignment
        table.delete_item(Key={"PK": pk, "SK": sk})
        
        return SuccessResponse.build({"message": "Permission removed from role successfully"}, 200)
        
    except Exception as e:
        logger.error(f"Error removing permission from role: {str(e)}")
        return ErrorResponse.build(f"Failed to remove permission: {str(e)}", 500)


def handle_assign_role_to_user(user_id: str, event: dict, authenticated_user: dict):
    """Assign a role to a user"""
    if not check_permission(authenticated_user, "permission:assign_role"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        body = json.loads(event.get("body", "{}"))
        assignment_data = UserRoleAssignment(**body)
        
        # Verify user exists
        user_response = table.get_item(Key={"PK": f"USER#{user_id}", "SK": "ENTITY#USER"})
        if "Item" not in user_response:
            return ErrorResponse.build(f"User '{user_id}' not found", 404)
        
        # Verify role exists
        role_response = table.get_item(Key={"PK": f"ROLE#{assignment_data.roleName}", "SK": "META"})
        if "Item" not in role_response:
            return ErrorResponse.build(f"Role '{assignment_data.roleName}' not found", 404)
        
        # Create user-role assignment
        pk = f"USER#{user_id}"
        sk = f"ROLE#{assignment_data.roleName}"
        
        # Check if assignment already exists
        assignment_response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" in assignment_response:
            return ErrorResponse.build("Role already assigned to user", 409)
        
        timestamp = datetime.utcnow().isoformat()
        item = {
            "PK": pk,
            "SK": sk,
            "entityType": ENTITY_TYPE_USER_ROLE,
            "userId": user_id,
            "roleName": assignment_data.roleName,
            "assignedAt": timestamp,
            "assignedBy": assignment_data.assignedBy or authenticated_user["uid"],
            "expiresAt": assignment_data.expiresAt
        }
        
        table.put_item(Item=item)
        
        clean_item = simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]})
        
        return SuccessResponse.build({"message": "Role assigned to user successfully", "data": clean_item}, 201)
        
    except ValidationError as e:
        return ErrorResponse.build(f"Validation error: {str(e.errors())}", 400)
    except Exception as e:
        logger.error(f"Error assigning role to user: {str(e)}")
        return ErrorResponse.build(f"Failed to assign role: {str(e)}", 500)


def handle_get_user_roles(user_id: str, authenticated_user: dict):
    """Get all roles assigned to a user"""
    if not check_permission(authenticated_user, "permission:read"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        # Query user roles
        pk = f"USER#{user_id}"
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": pk,
                ":sk_prefix": "ROLE#"
            }
        )
        
        items = response.get("Items", [])
        
        # Get full role details
        roles = []
        for item in items:
            role_name = item.get("roleName")
            role_response = table.get_item(Key={"PK": f"ROLE#{role_name}", "SK": "META"})
            if "Item" in role_response:
                role_item = role_response["Item"]
                clean_role = {k: v for k, v in role_item.items() if k not in ["PK", "SK", "entityType"]}
                clean_role["assignedAt"] = item.get("assignedAt")
                clean_role["assignedBy"] = item.get("assignedBy")
                clean_role["expiresAt"] = item.get("expiresAt")
                roles.append(clean_role)
        
        return SuccessResponse.build({
            "message": "User roles retrieved successfully",
            "data": roles,
            "meta": {"count": len(roles)}
        }, 200)
        
    except Exception as e:
        logger.error(f"Error retrieving user roles: {str(e)}")
        return ErrorResponse.build(f"Failed to retrieve roles: {str(e)}", 500)


def handle_get_user_permissions(user_id: str, authenticated_user: dict):
    """Get all computed permissions for a user (from all assigned roles)"""
    if not check_permission(authenticated_user, "permission:read"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        # Get user roles
        pk = f"USER#{user_id}"
        user_roles_response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": pk,
                ":sk_prefix": "ROLE#"
            }
        )
        
        role_items = user_roles_response.get("Items", [])
        
        # Collect all permissions from all roles
        all_permissions = {}
        
        for role_item in role_items:
            role_name = role_item.get("roleName")
            
            # Get permissions for this role
            role_pk = f"ROLE#{role_name}"
            role_perms_response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": role_pk,
                    ":sk_prefix": "PERMISSION#"
                }
            )
            
            perm_items = role_perms_response.get("Items", [])
            
            for perm_item in perm_items:
                perm_name = perm_item.get("permissionName")
                
                # Get full permission details
                perm_response = table.get_item(Key={"PK": f"PERMISSION#{perm_name}", "SK": "META"})
                if "Item" in perm_response:
                    perm_data = perm_response["Item"]
                    clean_perm = {k: v for k, v in perm_data.items() if k not in ["PK", "SK", "entityType"]}
                    
                    # Track which role granted this permission
                    if perm_name not in all_permissions:
                        clean_perm["grantedBy"] = [role_name]
                        all_permissions[perm_name] = clean_perm
                    else:
                        all_permissions[perm_name]["grantedBy"].append(role_name)
        
        permissions_list = list(all_permissions.values())
        
        return SuccessResponse.build({
            "message": "User permissions computed successfully",
            "data": permissions_list,
            "meta": {"count": len(permissions_list)}
        }, 200)
        
    except Exception as e:
        logger.error(f"Error computing user permissions: {str(e)}")
        return ErrorResponse.build(f"Failed to compute permissions: {str(e)}", 500)


def handle_remove_role_from_user(user_id: str, role_name: str, authenticated_user: dict):
    """Remove a role from a user"""
    if not check_permission(authenticated_user, "permission:assign_role"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        pk = f"USER#{user_id}"
        sk = f"ROLE#{role_name}"
        
        # Check if assignment exists
        response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" not in response:
            return ErrorResponse.build("Role assignment not found", 404)
        
        # Delete assignment
        table.delete_item(Key={"PK": pk, "SK": sk})
        
        return SuccessResponse.build({"message": "Role removed from user successfully"}, 200)
        
    except Exception as e:
        logger.error(f"Error removing role from user: {str(e)}")
        return ErrorResponse.build(f"Failed to remove role: {str(e)}", 500)


def handle_create_component(event: dict, authenticated_user: dict):
    """Create a new UI component with permission requirements"""
    if not check_permission(authenticated_user, "permission:manage"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        body = json.loads(event.get("body", "{}"))
        comp_data = ComponentCreate(**body)
        
        component_name = comp_data.componentName
        pk = f"COMPONENT#{component_name}"
        sk = "META"
        
        # Check if component already exists
        response = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" in response:
            return ErrorResponse.build(f"Component '{component_name}' already exists", 409)
        
        # Create component item
        timestamp = datetime.utcnow().isoformat()
        item = {
            "PK": pk,
            "SK": sk,
            "entityType": ENTITY_TYPE_COMPONENT,
            "componentName": component_name,
            "path": comp_data.path,
            "icon": comp_data.icon,
            "order": comp_data.order,
            "category": comp_data.category,
            "requiredPermissions": comp_data.requiredPermissions,
            "optionalPermissions": comp_data.optionalPermissions,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "createdBy": authenticated_user["uid"]
        }
        
        table.put_item(Item=item)
        
        clean_item = simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]})
        
        return SuccessResponse.build({"message": "Component created successfully", "data": clean_item}, 201)
        
    except ValidationError as e:
        return ErrorResponse.build(f"Validation error: {str(e.errors())}", 400)
    except Exception as e:
        logger.error(f"Error creating component: {str(e)}")
        return ErrorResponse.build(f"Failed to create component: {str(e)}", 500)


def handle_list_components(authenticated_user: dict):
    """List all UI components"""
    if not check_permission(authenticated_user, "permission:read"):
        return ErrorResponse.build("Insufficient permissions", 403)
    
    try:
        response = table.scan(
            FilterExpression="entityType = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_COMPONENT}
        )
        
        items = response.get("Items", [])
        clean_items = [simplify({k: v for k, v in item.items() if k not in ["PK", "SK", "entityType"]}) for item in items]
        
        # Sort by order
        clean_items.sort(key=lambda x: x.get("order", 0))
        
        return SuccessResponse.build({
            "message": "Components retrieved successfully",
            "data": clean_items,
            "meta": {"count": len(clean_items)}
        }, 200)
        
    except Exception as e:
        logger.error(f"Error listing components: {str(e)}")
        return ErrorResponse.build(f"Failed to list components: {str(e)}", 500)


# ====== END RBAC HANDLERS ======


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
    
    # Normalize path: remove stage prefix (e.g., /dev) and /users base path
    # API Gateway v2 includes stage in path: /dev/users/permissions -> /permissions
    if path.startswith("/dev/"):
        path = path[4:]  # Remove /dev
    if path.startswith("/users"):
        path = path[6:]  # Remove /users prefix
    if not path:
        path = "/"

    # Log for debugging
    logger.info(f"Extracted method: {method}, path: {path}, pathParameters: {path_parameters}")

    if not method:
        logger.error("Could not extract HTTP method from event")
        return ErrorResponse.build("Could not determine HTTP method from request", 400)

    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return SuccessResponse.build({"message": "CORS preflight successful"}, 200)

    # Extract authenticated user for authorization
    authenticated_user = extract_user_from_event(event)

    try:
        # Determine if response should be decrypted
        should_decrypt = query_parameters.get("decrypt", "true").lower() == "true"
        
        # ====== RBAC ROUTES (must be checked before general /users routes) ======
        
        # Role-Permission assignments (must be checked before role endpoints)
        if method == "POST" and "/permissions/roles" in path and path.endswith("/permissions") and "roleName" in path_parameters:
            # POST /permissions/roles/{roleName}/permissions
            return handle_assign_permission_to_role(path_parameters["roleName"], event, authenticated_user)
        
        elif method == "GET" and "/permissions/roles" in path and "/permissions" in path and "roleName" in path_parameters and "permissionName" not in path_parameters:
            # GET /permissions/roles/{roleName}/permissions
            return handle_get_role_permissions(path_parameters["roleName"], authenticated_user)
        
        elif method == "DELETE" and "/permissions/roles" in path and "/permissions" in path and "permissionName" in path_parameters:
            # DELETE /permissions/roles/{roleName}/permissions/{permissionName}
            return handle_remove_permission_from_role(path_parameters["roleName"], path_parameters["permissionName"], authenticated_user)
        
        # Role endpoints
        elif method == "POST" and "/permissions/roles" in path and "roleName" not in path_parameters:
            # POST /permissions/roles
            return handle_create_role(event, authenticated_user)
        
        elif method == "GET" and "/permissions/roles" in path and "roleName" in path_parameters:
            # GET /permissions/roles/{roleName}
            return handle_get_role(path_parameters["roleName"], authenticated_user)
        
        elif method == "GET" and "/permissions/roles" in path:
            # GET /permissions/roles
            return handle_list_roles(authenticated_user)
        
        elif method == "PUT" and "/permissions/roles" in path and "roleName" in path_parameters:
            # PUT /permissions/roles/{roleName}
            return handle_update_role(path_parameters["roleName"], event, authenticated_user)
        
        elif method == "DELETE" and "/permissions/roles" in path and "roleName" in path_parameters:
            # DELETE /permissions/roles/{roleName}
            return handle_delete_role(path_parameters["roleName"], authenticated_user)
        
        # Permission endpoints
        elif method == "POST" and (path == "/permissions" or ("/permissions" in path and "permissionName" not in path_parameters and "/roles" not in path and "/users" not in path and "/components" not in path)):
            # POST /permissions
            return handle_create_permission(event, authenticated_user)
        
        elif method == "GET" and "/permissions" in path and "permissionName" in path_parameters:
            # GET /permissions/{permissionName}
            return handle_get_permission(path_parameters["permissionName"], authenticated_user)
        
        elif method == "GET" and (path == "/permissions" or (path.endswith("/permissions") and "/users" not in path and "/roles" not in path)):
            # GET /permissions
            return handle_list_permissions(authenticated_user)
        
        # User-Role assignments
        elif method == "POST" and "/permissions/users" in path and "/roles" in path and "userId" in path_parameters and "roleName" not in path_parameters:
            # POST /permissions/users/{userId}/roles
            return handle_assign_role_to_user(path_parameters["userId"], event, authenticated_user)
        
        elif method == "GET" and "/permissions/users" in path and path.endswith("/roles") and "userId" in path_parameters and "roleName" not in path_parameters:
            # GET /permissions/users/{userId}/roles
            return handle_get_user_roles(path_parameters["userId"], authenticated_user)
        
        elif method == "GET" and "/permissions/users" in path and path.endswith("/permissions") and "userId" in path_parameters:
            # GET /permissions/users/{userId}/permissions
            return handle_get_user_permissions(path_parameters["userId"], authenticated_user)
        
        elif method == "DELETE" and "/permissions/users" in path and "/roles" in path and "userId" in path_parameters and "roleName" in path_parameters:
            # DELETE /permissions/users/{userId}/roles/{roleName}
            return handle_remove_role_from_user(path_parameters["userId"], path_parameters["roleName"], authenticated_user)
        
        # Component endpoints
        elif method == "POST" and "/permissions/components" in path:
            # POST /permissions/components
            return handle_create_component(event, authenticated_user)
        
        elif method == "GET" and "/permissions/components" in path:
            # GET /permissions/components
            return handle_list_components(authenticated_user)
        
        # ====== USER PROFILE AND MANAGEMENT ROUTES ======
        
        # Profile endpoints - must be checked before user ID endpoints
        elif "/profile" in path and "id" in path_parameters:
            user_id = path_parameters["id"]
            
            if method == "GET" and "/upload-url" in path:
                # GET /users/{id}/profile/picture/upload-url
                return handle_get_profile_picture_upload_url(user_id, event, authenticated_user)
            
            elif method == "POST" and "/picture" in path:
                # POST /users/{id}/profile/picture
                return handle_upload_profile_picture(user_id, event, authenticated_user)
            
            elif method == "GET":
                # GET /users/{id}/profile
                return handle_get_profile(user_id, authenticated_user, should_decrypt)
            
            elif method == "PUT":
                # PUT /users/{id}/profile
                return handle_update_profile(user_id, event, authenticated_user)
            
            elif method == "PATCH":
                # PATCH /users/{id}/profile
                return handle_update_profile_partial(user_id, event, authenticated_user)
        
        # General user endpoints (after checking all specific routes like /permissions, /profile, etc.)
        if method == "GET" and not path_parameters and "/permissions" not in path:
            # GET /users - List users with pagination and filters
            return handle_list_users(query_parameters, authenticated_user, should_decrypt)

        elif method == "GET" and "id" in path_parameters:
            # GET /users/{id}
            return handle_get_user(path_parameters["id"], authenticated_user, should_decrypt)

        elif method == "POST" and "/users/sync" in path:
            # POST /users/sync - Link Firebase UID to DynamoDB user on first login
            return handle_user_sync(event)

        elif method == "POST" and (path == "/users" or path == "/" or path == ""):
            # POST /users - Create new user
            return handle_create_user(event, authenticated_user)

        elif method == "PUT" and "id" in path_parameters:
            # PUT /users/{id} - Full update
            return handle_update_user_full(path_parameters["id"], event, authenticated_user)

        elif method == "PATCH" and "id" in path_parameters:
            # PATCH /users/{id} - Partial update
            return handle_update_user_partial(path_parameters["id"], event, authenticated_user)

        elif method == "DELETE" and "id" in path_parameters:
            # DELETE /users/{id}
            return handle_delete_user(path_parameters["id"], authenticated_user)

        return ErrorResponse.build("Unsupported method or route", 405)

    except Exception:
        logger.exception("Unhandled error")
        return ErrorResponse.build("Internal server error", 500)


# Handler Functions

def handle_list_users(query_parameters: Dict[str, Any], authenticated_user: Optional[Dict[str, Any]], should_decrypt: bool):
    """
    GET /users - List users with pagination and filters.
    Query parameters:
    - limit: Page size (default 50, max 100)
    - lastEvaluatedKey: Pagination token
    - role: Filter by role
    - isActive: Filter by active status (true/false)
    - stateId, districtId, mandalId, villageId: Filter by region
    - search: Search by firstName, lastName, or email
    """
    # Check read permission
    if not check_permission(authenticated_user, "user:read"):
        return ErrorResponse.build("Insufficient permissions to list users", 403)
    
    try:
        # Parse pagination
        requested_limit = min(int(query_parameters.get("limit", DEFAULT_PAGE_LIMIT)), MAX_PAGE_LIMIT)
        last_key = query_parameters.get("lastEvaluatedKey")
        
        # Build filter expression
        filter_expressions = ["entityType = :entityType", "SK = :sk"]
        expression_values = {":entityType": ENTITY_TYPE_USER, ":sk": "ENTITY#USER"}
        expression_names = {}
        
        # Role filter
        if "role" in query_parameters:
            try:
                role = UserRole(query_parameters["role"])
                filter_expressions.append("#role = :role")
                expression_values[":role"] = role.value
                expression_names["#role"] = "role"
            except ValueError:
                return ErrorResponse.build(f"Invalid role. Must be one of: {[r.value for r in UserRole]}", 400)
        
        # Active status filter
        if "isActive" in query_parameters:
            is_active = query_parameters["isActive"].lower() == "true"
            filter_expressions.append("isActive = :isActive")
            expression_values[":isActive"] = is_active
        
        # Region filters
        for region_field in ["stateId", "districtId", "mandalId", "villageId"]:
            if region_field in query_parameters:
                filter_expressions.append(f"{region_field} = :{region_field}")
                expression_values[f":{region_field}"] = query_parameters[region_field]
        
        # Keep scanning until we get enough USER entities or run out of items
        collected_items = []
        scan_last_key = None
        
        if last_key:
            try:
                scan_last_key = json.loads(last_key)
            except:
                return ErrorResponse.build("Invalid lastEvaluatedKey", 400)
        
        # Scan with larger internal limit to account for filtered items
        # Multiply requested limit by 20 to increase chances of getting enough users
        max_scans = 5  # Prevent infinite loops
        scan_count = 0
        
        while len(collected_items) < requested_limit and scan_count < max_scans:
            # Build scan parameters with larger limit
            scan_params = {
                "Limit": requested_limit * 20,  # Scan more items to find enough USER entities
                "FilterExpression": " AND ".join(filter_expressions),
                "ExpressionAttributeValues": expression_values
            }
            
            if expression_names:
                scan_params["ExpressionAttributeNames"] = expression_names
            
            if scan_last_key:
                scan_params["ExclusiveStartKey"] = scan_last_key
            
            # Execute scan
            response = table.scan(**scan_params)
            items = response.get("Items", [])
            
            # Apply search filter (post-scan since DynamoDB doesn't support contains well)
            if "search" in query_parameters:
                search_term = query_parameters["search"].lower()
                items = [
                    item for item in items
                    if search_term in item.get("firstName", "").lower() or
                       search_term in item.get("lastName", "").lower() or
                       search_term in item.get("email", "").lower()
                ]
            
            # Add items to collection
            collected_items.extend(items)
            
            # Check if there are more items to scan
            if "LastEvaluatedKey" in response:
                scan_last_key = response["LastEvaluatedKey"]
                scan_count += 1
            else:
                # No more items in table
                scan_last_key = None
                break
            
            # If we have enough items, stop scanning
            if len(collected_items) >= requested_limit:
                break
        
        # Trim to requested limit
        items = collected_items[:requested_limit]
        has_more = len(collected_items) > requested_limit or scan_last_key is not None
        
        # Trim to requested limit
        items = collected_items[:requested_limit]
        has_more = len(collected_items) > requested_limit or scan_last_key is not None
        
        # Process items
        items = [simplify(prepare_item_for_response(item, ENTITY_TYPE_USER, decrypt=should_decrypt)) for item in items]
        
        # Remove internal DynamoDB fields
        cleaned_items = []
        for item in items:
            cleaned_item = {k: v for k, v in item.items() if k not in ['PK', 'SK', 'entityType']}
            cleaned_items.append(cleaned_item)
        
        # Build response
        result = {
            "users": cleaned_items,
            "count": len(cleaned_items),
            "pagination": {
                "limit": requested_limit
            }
        }
        
        if scan_last_key:
            result["pagination"]["lastEvaluatedKey"] = json.dumps(scan_last_key)
            result["pagination"]["hasMore"] = True
        else:
            result["pagination"]["hasMore"] = False
        
        return SuccessResponse.build(result)
    
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        return ErrorResponse.build(f"Error listing users: {str(e)}", 500)


def handle_get_user(user_id: str, authenticated_user: Optional[Dict[str, Any]], should_decrypt: bool):
    """GET /users/{id} - Get single user by ID."""
    # Check read permission
    if not check_permission(authenticated_user, "user:read"):
        return ErrorResponse.build("Insufficient permissions to view user", 403)
    
    try:
        logger.info(f"GET user with id={user_id}")
        # Use PK/SK composite key structure
        response = table.get_item(Key={
            "PK": f"USER#{user_id}",
            "SK": "ENTITY#USER"
        })
        item = response.get("Item")
        
        if not item:
            return ErrorResponse.build(f"User with id {user_id} not found", 404)
        
        item = prepare_item_for_response(item, ENTITY_TYPE_USER, decrypt=should_decrypt)
        item = simplify(item)
        
        # Remove internal DynamoDB fields
        cleaned_item = {k: v for k, v in item.items() if k not in ['PK', 'SK', 'entityType']}
        
        return SuccessResponse.build(cleaned_item)
    
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        return ErrorResponse.build(f"Error getting user: {str(e)}", 500)


def handle_user_sync(event: Dict[str, Any]):
    """
    POST /users/sync - Link Firebase UID to DynamoDB user on first login.
    Updates lastLoginAt and loginCount.
    """
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
        
        # Find user by email - Use Query with GSI in production
        # For now, using scan (should add GSI on email field)
        response = table.scan(
            FilterExpression="email = :email AND entityType = :entityType",
            ExpressionAttributeValues={
                ":email": email,
                ":entityType": ENTITY_TYPE_USER
            }
        )
        
        items = response.get("Items", [])
        if not items:
            return ErrorResponse.build(
                f"User with email {email} not found in system. Please contact your administrator for account setup.",
                404
            )
        
        user = items[0]
        
        # Check if user is active
        if not user.get("isActive", False):
            return ErrorResponse.build(
                "Your account has been deactivated. Please contact your administrator.",
                403
            )
        
        user_id = user["id"]
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Extract Firebase profile data
        display_name = token_claims.get('name', '')
        photo_url = token_claims.get('picture')
        
        # Split display name into firstName/lastName if available
        first_name = user.get("firstName", "")
        last_name = user.get("lastName", "")
        if display_name and not first_name:
            name_parts = display_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Update user with Firebase UID and login info
        update_expr_parts = []
        expr_values = {
            ":updated": timestamp,
            ":verified": token_claims.get('email_verified', False),
            ":lastLogin": timestamp,
            ":one": 1
        }
        
        if not user.get("firebaseUid"):
            update_expr_parts.append("firebaseUid = :uid")
            expr_values[":uid"] = firebase_uid
            logger.info(f"Linking Firebase UID {firebase_uid} to user {user_id}")
        elif user["firebaseUid"] != firebase_uid:
            return ErrorResponse.build("Email already linked to different Firebase account", 409)
        
        # Update firstName/lastName from Firebase if not set
        if first_name and not user.get("firstName"):
            update_expr_parts.append("firstName = :firstName")
            expr_values[":firstName"] = first_name
        if last_name and not user.get("lastName"):
            update_expr_parts.append("lastName = :lastName")
            expr_values[":lastName"] = last_name
        
        update_expr_parts.extend([
            "updatedAt = :updated",
            "emailVerified = :verified",
            "lastLoginAt = :lastLogin",
            "loginCount = if_not_exists(loginCount, :zero) + :one"
        ])
        expr_values[":zero"] = 0
        
        update_expression = "SET " + ", ".join(update_expr_parts)
        
        # Use PK/SK composite keys for the update
        response = table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "ENTITY#USER"
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW"
        )
        
        updated_user = simplify(response["Attributes"])
        logger.info(f"User {email} synced successfully (login count: {updated_user.get('loginCount', 1)})")
        
        # Remove internal DynamoDB fields before returning
        user_profile = {k: v for k, v in updated_user.items() if k not in ['PK', 'SK', 'entityType']}
        
        # Debug log to verify isActive is in response
        logger.info(f"Sync response for {email}: isActive={user_profile.get('isActive')}, id={user_profile.get('id')}")
        
        # Sync profile data with Firebase photoURL and name
        try:
            profile_response = table.get_item(
                Key={"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"}
            )
            
            profile_update_needed = False
            profile_update_parts = []
            profile_expr_values = {":updated": timestamp}
            
            if "Item" in profile_response:
                # Profile exists - update if needed
                profile = profile_response["Item"]
                
                # Sync photoURL if available and different
                if photo_url and profile.get("profilePictureUrl") != photo_url:
                    profile_update_parts.append("profilePictureUrl = :photoUrl")
                    profile_expr_values[":photoUrl"] = photo_url
                    profile_update_needed = True
                
                # Sync firstName/lastName to profile
                if first_name and profile.get("firstName") != first_name:
                    profile_update_parts.append("firstName = :firstName")
                    profile_expr_values[":firstName"] = first_name
                    profile_update_needed = True
                    
                if last_name and profile.get("lastName") != last_name:
                    profile_update_parts.append("lastName = :lastName")
                    profile_expr_values[":lastName"] = last_name
                    profile_update_needed = True
                
                if profile_update_needed:
                    profile_update_parts.append("updatedAt = :updated")
                    table.update_item(
                        Key={"PK": f"USER#{user_id}", "SK": "PROFILE#MAIN"},
                        UpdateExpression="SET " + ", ".join(profile_update_parts),
                        ExpressionAttributeValues=profile_expr_values
                    )
                    logger.info(f"Synced profile with Firebase data for user {user_id}")
            else:
                # Profile doesn't exist - create it with Firebase data
                logger.info(f"Creating profile with Firebase data for user {user_id}")
                profile_item = {
                    "PK": f"USER#{user_id}",
                    "SK": "PROFILE#MAIN",
                    "userId": user_id,
                    "entityType": ENTITY_TYPE_PROFILE,
                    "firstName": first_name or "",
                    "lastName": last_name or "",
                    "phoneNumber": user_profile.get("phoneNumber"),
                    "language": "en",
                    "organization": None,
                    "department": None,
                    "timezone": "UTC",
                    "profilePictureUrl": photo_url,
                    "address": {
                        "street": "",
                        "city": "",
                        "state": "",
                        "country": "",
                        "postalCode": ""
                    },
                    "preferences": {
                        "notifications": True,
                        "emailAlerts": True,
                        "smsAlerts": False
                    },
                    "createdAt": timestamp,
                    "updatedAt": timestamp
                }
                profile_item = prepare_item_for_storage(profile_item, ENTITY_TYPE_PROFILE)
                table.put_item(Item=profile_item)
        except Exception as profile_error:
            # Non-blocking - profile sync failure shouldn't fail login
            logger.warning(f"Profile sync failed for user {user_id}: {str(profile_error)}")
        
        return SuccessResponse.build({
            "message": "User synced successfully",
            "user": user_profile
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return ErrorResponse.build(f"Invalid JSON: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Sync error: {str(e)}")
        return ErrorResponse.build(f"Error during sync: {str(e)}", 500)


def handle_create_user(event: Dict[str, Any], authenticated_user: Optional[Dict[str, Any]]):
    """POST /users - Create new user."""
    # Check create permission
    if not check_permission(authenticated_user, "user:create"):
        return ErrorResponse.build("Insufficient permissions to create users", 403)
    
    body = event.get("body")
    if not body:
        return ErrorResponse.build("Missing request body", 400)
    
    try:
        data = json.loads(body)
        
        # Check if email already exists
        email = data.get("email")
        if email:
            existing = table.scan(
                FilterExpression="email = :email",
                ExpressionAttributeValues={":email": email},
                Limit=1
            )
            if existing.get("Items"):
                return ErrorResponse.build(f"User with email {email} already exists", 409)
        
        # Validate and create user
        user = UserDetails(**data)
        
        pk = f"USER#{user.id}"
        sk = "ENTITY#USER"
        item = user.dict()
        item["PK"] = pk
        item["SK"] = sk
        item["id"] = user.id
        
        # Set timestamps and audit fields
        timestamp = datetime.utcnow().isoformat() + "Z"
        item["createdAt"] = timestamp
        item["updatedAt"] = timestamp
        
        # Set audit trail from authenticated user if not provided
        if authenticated_user and not item.get("createdBy"):
            item["createdBy"] = authenticated_user.get("email", "system")
        item["updatedBy"] = item.get("createdBy", "system")
        
        # Set role permissions
        if user.role:
            item["permissions"] = ROLE_PERMISSIONS.get(user.role, [])
        
        item = prepare_item_for_storage(item, ENTITY_TYPE_USER)
        logger.info(f"Creating user with id={user.id}, email={user.email}, role={user.role}")
        table.put_item(Item=item)
        
        item = prepare_item_for_response(item, ENTITY_TYPE_USER, decrypt=True)
        item = simplify(item)
        
        # Remove internal DynamoDB fields
        cleaned_item = {k: v for k, v in item.items() if k not in ['PK', 'SK', 'entityType']}
        
        return SuccessResponse.build(cleaned_item, status_code=201)
    
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Validation error: {e}")
        return ErrorResponse.build(f"Invalid user data: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return ErrorResponse.build(f"Error creating user: {str(e)}", 500)


def handle_update_user_full(user_id: str, event: Dict[str, Any], authenticated_user: Optional[Dict[str, Any]]):
    """PUT /users/{id} - Full update (replace entire user)."""
    # Check update permission
    if not check_permission(authenticated_user, "user:update"):
        return ErrorResponse.build("Insufficient permissions to update users", 403)
    
    body = event.get("body")
    if not body:
        return ErrorResponse.build("Missing request body", 400)
    
    try:
        # Check if user exists
        response = table.get_item(Key={"id": user_id})
        if "Item" not in response:
            return ErrorResponse.build(f"User with id {user_id} not found", 404)
        
        existing_user = response["Item"]
        
        data = json.loads(body)
        user = UserDetails(**data)
        
        pk = f"USER#{user_id}"
        sk = "ENTITY#USER"
        item = user.dict()
        item["PK"] = pk
        item["SK"] = sk
        item["id"] = user_id
        
        # Preserve creation info, update modification info
        item["createdAt"] = existing_user.get("createdAt", datetime.utcnow().isoformat() + "Z")
        item["createdBy"] = existing_user.get("createdBy", "system")
        item["updatedAt"] = datetime.utcnow().isoformat() + "Z"
        
        if authenticated_user:
            item["updatedBy"] = authenticated_user.get("email", "system")
        elif not item.get("updatedBy"):
            item["updatedBy"] = "system"
        
        # Update role permissions
        if user.role:
            item["permissions"] = ROLE_PERMISSIONS.get(user.role, [])
        
        # Preserve Firebase UID and login stats
        item["firebaseUid"] = existing_user.get("firebaseUid")
        item["lastLoginAt"] = existing_user.get("lastLoginAt")
        item["loginCount"] = existing_user.get("loginCount", 0)
        
        item = prepare_item_for_storage(item, ENTITY_TYPE_USER)
        logger.info(f"Updating user {user_id} (full replace)")
        table.put_item(Item=item)
        
        item = prepare_item_for_response(item, ENTITY_TYPE_USER, decrypt=True)
        item = simplify(item)
        
        # Remove internal DynamoDB fields
        cleaned_item = {k: v for k, v in item.items() if k not in ['PK', 'SK', 'entityType']}
        
        return SuccessResponse.build(cleaned_item)
    
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Validation error: {e}")
        return ErrorResponse.build(f"Invalid user data: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return ErrorResponse.build(f"Error updating user: {str(e)}", 500)


def handle_update_user_partial(user_id: str, event: Dict[str, Any], authenticated_user: Optional[Dict[str, Any]]):
    """PATCH /users/{id} - Partial update (update only provided fields)."""
    # Check update permission
    if not check_permission(authenticated_user, "user:update"):
        return ErrorResponse.build("Insufficient permissions to update users", 403)
    
    body = event.get("body")
    if not body:
        return ErrorResponse.build("Missing request body", 400)
    
    try:
        # Check if user exists
        response = table.get_item(Key={"id": user_id})
        if "Item" not in response:
            return ErrorResponse.build(f"User with id {user_id} not found", 404)
        
        data = json.loads(body)
        
        # Validate partial update data
        try:
            update_data = UserUpdatePartial(**data)
        except ValidationError as e:
            return ErrorResponse.build(f"Invalid update data: {str(e)}", 400)
        
        # Build update expression
        update_expr_parts = []
        expr_values = {}
        expr_names = {}
        
        # Only include fields that were actually provided
        update_dict = update_data.dict(exclude_unset=True)
        
        if not update_dict:
            return ErrorResponse.build("No fields to update", 400)
        
        for field, value in update_dict.items():
            if field == "role":
                # Update role and permissions together
                update_expr_parts.append("#role = :role")
                expr_names["#role"] = "role"
                expr_values[":role"] = value.value if isinstance(value, UserRole) else value
                # Update permissions based on role
                role_enum = UserRole(value) if isinstance(value, str) else value
                update_expr_parts.append("permissions = :permissions")
                expr_values[":permissions"] = ROLE_PERMISSIONS.get(role_enum, [])
            else:
                update_expr_parts.append(f"{field} = :{field}")
                expr_values[f":{field}"] = value
        
        # Always update timestamp and updatedBy
        timestamp = datetime.utcnow().isoformat() + "Z"
        update_expr_parts.append("updatedAt = :updatedAt")
        expr_values[":updatedAt"] = timestamp
        
        if authenticated_user:
            update_expr_parts.append("updatedBy = :updatedBy")
            expr_values[":updatedBy"] = authenticated_user.get("email", "system")
        
        update_expression = "SET " + ", ".join(update_expr_parts)
        
        update_params = {
            "Key": {"id": user_id},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expr_values,
            "ReturnValues": "ALL_NEW"
        }
        
        if expr_names:
            update_params["ExpressionAttributeNames"] = expr_names
        
        response = table.update_item(**update_params)
        
        updated_user = simplify(response["Attributes"])
        logger.info(f"Partially updated user {user_id}: {list(update_dict.keys())}")
        
        return SuccessResponse.build({
            "message": "User updated successfully",
            "user": updated_user,
            "updatedFields": list(update_dict.keys())
        })
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return ErrorResponse.build(f"Invalid JSON: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return ErrorResponse.build(f"Error updating user: {str(e)}", 500)


def handle_delete_user(user_id: str, authenticated_user: Optional[Dict[str, Any]]):
    """DELETE /users/{id} - Delete user (or soft delete with ?soft=true)."""
    # Check delete permission
    if not check_permission(authenticated_user, "user:delete"):
        return ErrorResponse.build("Insufficient permissions to delete users", 403)
    
    try:
        # Check if user exists
        response = table.get_item(Key={"id": user_id})
        if "Item" not in response:
            return ErrorResponse.build(f"User with id {user_id} not found", 404)
        
        logger.info(f"Deleting user {user_id}")
        table.delete_item(Key={"id": user_id})
        
        return SuccessResponse.build({
            "message": f"User {user_id} deleted successfully"
        })
    
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        return ErrorResponse.build(f"Error deleting user: {str(e)}", 500)
