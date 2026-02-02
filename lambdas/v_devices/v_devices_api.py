import json
import os
import boto3
import logging
import re
import uuid
from datetime import datetime
from decimal import Decimal
import decimal
from pydantic import BaseModel, ValidationError, Field
from botocore.exceptions import ClientError
from shared.response_utils import SuccessResponse, ErrorResponse
from shared.encryption_utils import FieldEncryption, get_fields_to_encrypt, get_fields_to_decrypt

TABLE_NAME = os.environ.get("TABLE_NAME", "v_devices_dev")
SIMCARDS_TABLE_NAME = os.environ.get("SIMCARDS_TABLE_NAME", "v_simcards_dev")
dynamodb = boto3.resource("dynamodb")
dynamodb_client = boto3.client("dynamodb")
table = dynamodb.Table(TABLE_NAME)
simcards_table = dynamodb.Table(SIMCARDS_TABLE_NAME)

# Initialize encryption manager
encryption = FieldEncryption(region='ap-south-2', key_alias='alias/iot-platform-data')

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# =============== INPUT VALIDATION FUNCTIONS ===============

def validate_string_length(value, field_name, min_length=1, max_length=255):
    """Validate string length"""
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    if len(value) < min_length or len(value) > max_length:
        return False, f"{field_name} must be between {min_length} and {max_length} characters"
    return True, None

def validate_alphanumeric(value, field_name, allow_special="-_"):
    """Validate alphanumeric with optional special characters"""
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    pattern = f"^[A-Za-z0-9{re.escape(allow_special)}]+$"
    if not re.match(pattern, value):
        return False, f"{field_name} contains invalid characters (allowed: letters, numbers, {allow_special})"
    return True, None

def validate_iso8601_date(value, field_name):
    """Validate ISO8601 date format"""
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return True, None
    except ValueError:
        return False, f"{field_name} must be valid ISO8601 format (e.g., 2026-02-01T00:00:00.000Z)"

def validate_email(value, field_name):
    """Validate email format"""
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(pattern, value):
        return False, f"{field_name} must be a valid email address"
    return True, None

def validate_enum(value, field_name, allowed_values):
    """Validate value is in allowed enum list"""
    if value not in allowed_values:
        return False, f"{field_name} must be one of: {', '.join(allowed_values)}"
    return True, None

def validate_positive_number(value, field_name):
    """Validate positive number"""
    try:
        num = float(value) if not isinstance(value, (int, float, Decimal)) else value
        if num < 0:
            return False, f"{field_name} must be a positive number"
        return True, None
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number"

def sanitize_text(value, max_length=1000):
    """Sanitize text input - remove potential XSS/injection"""
    if not isinstance(value, str):
        return value
    # Remove HTML tags
    value = re.sub(r'<[^>]+>', '', value)
    # Remove SQL injection patterns
    value = re.sub(r'(--|;|\'|\"|\bOR\b|\bAND\b)', '', value, flags=re.IGNORECASE)
    # Truncate to max length
    return value[:max_length]

def validate_installation_input(body):
    """Comprehensive validation for installation creation/update"""
    errors = []
    
    # Required string fields with length limits
    string_fields = {
        "StateId": (2, 10),
        "DistrictId": (1, 50),
        "MandalId": (1, 50),
        "VillageId": (1, 50),
        "HabitationId": (1, 50)
    }
    
    for field, (min_len, max_len) in string_fields.items():
        if field in body:
            is_valid, error = validate_string_length(body[field], field, min_len, max_len)
            if not is_valid:
                errors.append(error)
    
    # Enum validations
    if "PrimaryDevice" in body:
        is_valid, error = validate_enum(body["PrimaryDevice"], "PrimaryDevice", ["water", "chlorine", "none"])
        if not is_valid:
            errors.append(error)
    
    if "Status" in body:
        is_valid, error = validate_enum(body["Status"], "Status", ["active", "inactive"])
        if not is_valid:
            errors.append(error)
    
    # Date validation
    if "InstallationDate" in body:
        is_valid, error = validate_iso8601_date(body["InstallationDate"], "InstallationDate")
        if not is_valid:
            errors.append(error)
    
    if "WarrantyDate" in body:
        is_valid, error = validate_iso8601_date(body["WarrantyDate"], "WarrantyDate")
        if not is_valid:
            errors.append(error)
    
    # Email validation if CreatedBy looks like email
    if "CreatedBy" in body and "@" in body["CreatedBy"]:
        is_valid, error = validate_email(body["CreatedBy"], "CreatedBy")
        if not is_valid:
            errors.append(error)
    
    return len(errors) == 0, errors

def validate_device_input(body):
    """Comprehensive validation for device creation/update"""
    errors = []
    
    # Required string fields
    if "DeviceName" in body:
        is_valid, error = validate_string_length(body["DeviceName"], "DeviceName", 1, 100)
        if not is_valid:
            errors.append(error)
    
    if "DeviceType" in body:
        is_valid, error = validate_string_length(body["DeviceType"], "DeviceType", 1, 50)
        if not is_valid:
            errors.append(error)
    
    if "SerialNumber" in body:
        is_valid, error = validate_string_length(body["SerialNumber"], "SerialNumber", 1, 100)
        if not is_valid:
            errors.append(error)
    
    # Status enum
    if "Status" in body:
        is_valid, error = validate_enum(body["Status"], "Status", ["active", "inactive", "maintenance", "retired"])
        if not is_valid:
            errors.append(error)
    
    # Location text
    if "Location" in body:
        is_valid, error = validate_string_length(body["Location"], "Location", 0, 500)
        if not is_valid:
            errors.append(error)
    
    return len(errors) == 0, errors

def validate_repair_input(body):
    """Comprehensive validation for repair creation/update"""
    errors = []
    
    # Description required
    if "description" in body:
        is_valid, error = validate_string_length(body["description"], "description", 1, 1000)
        if not is_valid:
            errors.append(error)
        # Sanitize description
        body["description"] = sanitize_text(body["description"], 1000)
    
    # Cost validation
    if "cost" in body:
        is_valid, error = validate_positive_number(body["cost"], "cost")
        if not is_valid:
            errors.append(error)
    
    # Technician name
    if "technician" in body:
        is_valid, error = validate_string_length(body["technician"], "technician", 1, 100)
        if not is_valid:
            errors.append(error)
    
    # Status enum
    if "status" in body:
        is_valid, error = validate_enum(body["status"], "status", ["pending", "in-progress", "completed", "cancelled"])
        if not is_valid:
            errors.append(error)
    
    return len(errors) == 0, errors

# =============== END VALIDATION FUNCTIONS ===============

class DeviceMeta(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    DeviceName: str
    DeviceType: str
    SerialNumber: str
    devicenum: str = None  # IMEI or unique device identifier
    Status: str
    Location: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None
    CreatedBy: str = None
    UpdatedBy: str = None

    class Config:
        extra = "forbid"

class DeviceConfig(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    ConfigVersion: str
    ConfigData: dict
    AppliedBy: str
    Status: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None
    CreatedBy: str = None
    UpdatedBy: str = None

    class Config:
        extra = "forbid"

class DeviceRepair(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    RepairId: str
    Description: str
    Cost: Decimal = Field(ge=0)
    Technician: str
    Status: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None
    CreatedBy: str = None
    UpdatedBy: str = None

    class Config:
        extra = "forbid"
        arbitrary_types_allowed = True

class DeviceInstall(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    InstallId: str
    Location: dict
    Installer: str
    Notes: str
    Status: str
    Warranty: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None
    CreatedBy: str = None
    UpdatedBy: str = None

    class Config:
        extra = "forbid"

class Installation(BaseModel):
    PK: str
    SK: str
    InstallationId: str
    CustomerId: str = None
    TemplateId: str = None
    StateId: str
    DistrictId: str
    MandalId: str
    VillageId: str
    HabitationId: str
    PrimaryDevice: str  # "water" | "chlorine" | "none"
    Status: str  # "active" | "inactive"
    InstallationDate: str
    WarrantyDate: str = None
    EntityType: str = "INSTALL"
    CreatedDate: str = None
    UpdatedDate: str = None
    CreatedBy: str = None
    UpdatedBy: str = None

    class Config:
        extra = "forbid"

class DeviceRuntime(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    Metrics: dict
    Events: list
    Status: str
    EntityType: str
    EventDate: str = None
    ttl: int = None
    CreatedDate: str = None
    UpdatedDate: str = None
    CreatedBy: str = None
    UpdatedBy: str = None

    class Config:
        extra = "forbid"

class SimMeta(BaseModel):
    PK: str
    SK: str
    SIMId: str
    MobileNumber: str
    Provider: str
    Plan: str
    DataUsage: Decimal = Field(ge=0)
    AssignedDeviceId: str
    Status: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None
    CreatedBy: str = None
    UpdatedBy: str = None

    class Config:
        extra = "forbid"
        arbitrary_types_allowed = True

class SimAssoc(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    SIMId: str
    Provider: str
    Status: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None
    CreatedBy: str = None
    UpdatedBy: str = None

    class Config:
        extra = "forbid"

ENTITY_MODEL_MAP = {
    "DEVICE": DeviceMeta,
    "CONFIG": DeviceConfig,
    "REPAIR": DeviceRepair,
    "INSTALL": DeviceInstall,
    "RUNTIME": DeviceRuntime,
    "SIM": SimMeta,
    "SIM_ASSOC": SimAssoc
}

def fetch_region_names(state_id=None, district_id=None, mandal_id=None, village_id=None, habitation_id=None):
    """Fetch region names from v_regions_dev table
    
    The table uses a hierarchical structure:
    - STATE#<code> contains districts as SK entries
    - DISTRICT#<code> contains mandals as SK entries  
    - MANDAL#<code> contains villages as SK entries
    - VILLAGE#<code> contains habitations as SK entries
    
    Query patterns:
    - State "TS": PK=STATE#TS, SK=STATE#TS
    - District "RAN" under TS: PK=STATE#TS, SK=DISTRICT#RAN
    - Mandal "AMAN" under RAN: PK=DISTRICT#RAN, SK=MANDAL#AMAN
    - Village "AK1012" under AMAN: PK=MANDAL#AMAN, SK=VILLAGE#AK1012
    - Habitation "AK1012_H1" under AK1012: PK=VILLAGE#AK1012, SK=HABITATION#AK1012_H1
    
    Returns a dict with stateName, districtName, mandalName, villageName, habitationName
    """
    region_names = {}
    
    try:
        regions_table = dynamodb.Table(os.environ.get("REGIONS_TABLE", "v_regions_dev"))
        logger.info(f"fetch_region_names called with: state_id={state_id}, district_id={district_id}, mandal_id={mandal_id}, village_id={village_id}, habitation_id={habitation_id}")
        
        # For STATE
        if state_id:
            state_key = state_id.replace("STATE-", "").replace("STATE#", "")  # Strip prefixes
            logger.info(f"Looking up STATE: PK=STATE#{state_key}, SK=STATE#{state_key}")
            response = regions_table.get_item(
                Key={"PK": f"STATE#{state_key}", "SK": f"STATE#{state_key}"}
            )
            if "Item" in response:
                region_names["stateName"] = response["Item"].get("RegionName")
                logger.info(f"Found state: {region_names['stateName']}")
            else:
                logger.warning(f"State not found: STATE#{state_key}")
        
        # For DISTRICT - parent is STATE
        if district_id and state_id:
            state_key = state_id.replace("STATE-", "").replace("STATE#", "")
            district_key = district_id.replace("DIST-", "").replace("DISTRICT#", "")
            logger.info(f"Looking up DISTRICT: PK=STATE#{state_key}, SK=DISTRICT#{district_key}")
            response = regions_table.get_item(
                Key={"PK": f"STATE#{state_key}", "SK": f"DISTRICT#{district_key}"}
            )
            if "Item" in response:
                region_names["districtName"] = response["Item"].get("RegionName")
                logger.info(f"Found district: {region_names['districtName']}")
            else:
                logger.warning(f"District not found under STATE#{state_key}: DISTRICT#{district_key}")
        
        # For MANDAL - parent is DISTRICT
        if mandal_id and district_id:
            district_key = district_id.replace("DIST-", "").replace("DISTRICT#", "")
            mandal_key = mandal_id.replace("MANDAL-", "").replace("MANDAL#", "")
            logger.info(f"Looking up MANDAL: PK=DISTRICT#{district_key}, SK=MANDAL#{mandal_key}")
            response = regions_table.get_item(
                Key={"PK": f"DISTRICT#{district_key}", "SK": f"MANDAL#{mandal_key}"}
            )
            if "Item" in response:
                region_names["mandalName"] = response["Item"].get("RegionName")
                logger.info(f"Found mandal: {region_names['mandalName']}")
            else:
                logger.warning(f"Mandal not found under DISTRICT#{district_key}: MANDAL#{mandal_key}")
        
        # For VILLAGE - parent is MANDAL
        if village_id and mandal_id:
            mandal_key = mandal_id.replace("MANDAL-", "").replace("MANDAL#", "")
            village_key = village_id.replace("VILLAGE-", "").replace("VILLAGE#", "")
            logger.info(f"Looking up VILLAGE: PK=MANDAL#{mandal_key}, SK=VILLAGE#{village_key}")
            response = regions_table.get_item(
                Key={"PK": f"MANDAL#{mandal_key}", "SK": f"VILLAGE#{village_key}"}
            )
            if "Item" in response:
                region_names["villageName"] = response["Item"].get("RegionName")
                logger.info(f"Found village: {region_names['villageName']}")
            else:
                logger.warning(f"Village not found under MANDAL#{mandal_key}: VILLAGE#{village_key}")
        
        # For HABITATION - parent is VILLAGE
        if habitation_id and village_id:
            village_key = village_id.replace("VILLAGE-", "").replace("VILLAGE#", "")
            habitation_key = habitation_id.replace("HAB-", "").replace("HABITATION#", "")
            logger.info(f"Looking up HABITATION: PK=VILLAGE#{village_key}, SK=HABITATION#{habitation_key}")
            response = regions_table.get_item(
                Key={"PK": f"VILLAGE#{village_key}", "SK": f"HABITATION#{habitation_key}"}
            )
            if "Item" in response:
                region_names["habitationName"] = response["Item"].get("RegionName")
                logger.info(f"Found habitation: {region_names['habitationName']}")
            else:
                logger.warning(f"Habitation not found under VILLAGE#{village_key}: HABITATION#{habitation_key}")
    
    except Exception as e:
        logger.warning(f"Failed to fetch region names: {str(e)}")
    
    return region_names

def lambda_handler(event, context):
    # Log the full event for debugging
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    # Try multiple ways to extract the HTTP method
    method = (
        event.get("httpMethod") or 
        event.get("requestContext", {}).get("http", {}).get("method") or
        event.get("requestContext", {}).get("httpMethod")
    )
    
    # Log for debugging
    logger.info(f"Event keys: {list(event.keys())}")
    logger.info(f"Extracted method: {method}")
    
    # If method is still None, return detailed error
    if not method:
        logger.error("Could not extract HTTP method from event")
        return ErrorResponse.build("Could not determine HTTP method from request", 400)

    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return SuccessResponse.build({"message": "CORS preflight successful"}, 200)

    # Extract path and path parameters (needed for all methods)
    path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path") or ""
    path_parameters = event.get("pathParameters") or {}
    
    # Check if this is a GET /devices/{deviceId}/repairs request
    if path_parameters.get("deviceId") and "/repairs" in path and method == "GET":
        device_id = path_parameters.get("deviceId")
        logger.info(f"Fetching repairs for device: {device_id}")
        
        try:
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                ExpressionAttributeValues={
                    ":pk": f"DEVICE#{device_id}",
                    ":sk": "REPAIR#"
                }
            )
            repairs = [simplify(item) for item in response.get("Items", [])]
            logger.info(f"Found {len(repairs)} repair(s) for device {device_id}")
            return SuccessResponse.build({
                "deviceId": device_id,
                "repairCount": len(repairs),
                "repairs": repairs
            }, 200)
        except Exception as e:
            logger.error(f"Error fetching repairs: {str(e)}")
            return ErrorResponse.build(f"Error fetching repairs: {str(e)}", 500)

    elif method == "POST":
        # Check if this is a POST /installs request (create installation)
        logger.debug(f"POST handler: path={path}, pathParams={path_parameters}, /installs in path: {'/installs' in path}")
        if "/installs" in path and not path_parameters.get("installId"):
            logger.info("Creating new installation")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Validate required fields
            required_fields = ["StateId", "DistrictId", "MandalId", "VillageId", "HabitationId", "PrimaryDevice", "Status", "InstallationDate"]
            missing_fields = [field for field in required_fields if not body.get(field)]
            if missing_fields:
                return ErrorResponse.build(f"Missing required fields: {', '.join(missing_fields)}", 400)
            
            # Validate devices are provided (at least one device required)
            device_ids = body.get("deviceIds") or body.get("DeviceIds", [])
            if not device_ids or not isinstance(device_ids, list) or len(device_ids) == 0:
                return ErrorResponse.build("At least one device must be provided in 'deviceIds' or 'DeviceIds' array", 400)
            
            # Comprehensive input validation
            is_valid, validation_errors = validate_installation_input(body)
            if not is_valid:
                return ErrorResponse.build(f"Validation errors: {'; '.join(validation_errors)}", 400)
            
            # Validate PrimaryDevice value (already checked in validate_installation_input, but keeping for explicitness)
            if body.get("PrimaryDevice") not in ["water", "chlorine", "none"]:
                return ErrorResponse.build("PrimaryDevice must be 'water', 'chlorine', or 'none'", 400)
            
            # Validate Status value
            if body.get("Status") not in ["active", "inactive"]:
                return ErrorResponse.build("Status must be 'active' or 'inactive'", 400)
            
            # Validate optional CustomerId if provided (skip if permission issues)
            if body.get("CustomerId"):
                try:
                    is_valid, error_msg, is_permission_error = validate_customer_id_exists(body.get("CustomerId"))
                    # Only return error if it's a real validation failure (not a permission issue)
                    if is_valid is False and not is_permission_error:
                        return ErrorResponse.build(error_msg, 400)
                    # If permission error, just log and continue
                    if is_permission_error:
                        logger.info(f"Customer validation permission issue for {body.get('CustomerId')}, allowing anyway")
                except Exception as e:
                    logger.warning(f"Customer validation skipped: {str(e)}")
            
            # Validate optional TemplateId if provided
            if body.get("TemplateId"):
                try:
                    is_valid, error_msg = validate_template_id_exists(body.get("TemplateId"))
                    if not is_valid:
                        return ErrorResponse.build(error_msg, 400)
                except Exception as e:
                    logger.warning(f"Template validation skipped: {str(e)}")
            
            # Validate all region IDs (skip if permission issues for now)
            region_validations = [
                ("STATE", body.get("StateId")),
                ("DISTRICT", body.get("DistrictId")),
                ("MANDAL", body.get("MandalId")),
                ("VILLAGE", body.get("VillageId")),
                ("HABITATION", body.get("HabitationId"))
            ]
            
            for region_type, region_id in region_validations:
                try:
                    is_valid, error_msg = validate_region_id_exists(region_type, region_id)
                    if not is_valid:
                        logger.warning(f"Region validation failed: {error_msg}. Skipping.")
                except Exception as e:
                    logger.warning(f"Region validation skipped for {region_type}: {str(e)}")
            
            # Check for duplicate installation (same region combination)
            state_id = body.get("StateId")
            district_id = body.get("DistrictId")
            mandal_id = body.get("MandalId")
            village_id = body.get("VillageId")
            habitation_id = body.get("HabitationId")
            
            # Create region combination key for atomic duplicate prevention
            region_combo_key = f"{state_id}#{district_id}#{mandal_id}#{village_id}#{habitation_id}"
            
            logger.info(f"Checking for existing installation: RegionCombo={region_combo_key}")
            
            # NOTE: We'll use a conditional expression during put_item to prevent duplicates atomically
            # This is better than a scan + check pattern which has race conditions
            
            # Create installation record
            try:
                installation_id = str(uuid.uuid4())
                timestamp = datetime.utcnow().isoformat() + "Z"
                created_by = body.get("CreatedBy", "system")
                
                installation_item = {
                    "PK": f"INSTALL#{installation_id}",
                    "SK": "META",
                    "InstallationId": installation_id,
                    "StateId": body.get("StateId"),
                    "DistrictId": body.get("DistrictId"),
                    "MandalId": body.get("MandalId"),
                    "VillageId": body.get("VillageId"),
                    "HabitationId": body.get("HabitationId"),
                    "RegionCombo": region_combo_key,  # Add for future GSI
                    "PrimaryDevice": body.get("PrimaryDevice"),
                    "Status": body.get("Status"),
                    "InstallationDate": body.get("InstallationDate"),
                    "EntityType": "INSTALL",
                    "CreatedDate": timestamp,
                    "UpdatedDate": timestamp,
                    "CreatedBy": created_by,
                    "UpdatedBy": created_by
                }
                
                # Add optional fields
                if body.get("CustomerId"):
                    installation_item["CustomerId"] = body.get("CustomerId")
                if body.get("TemplateId"):
                    installation_item["TemplateId"] = body.get("TemplateId")
                if body.get("WarrantyDate"):
                    installation_item["WarrantyDate"] = body.get("WarrantyDate")
                
                # Create a unique record for region combo to prevent duplicates
                # This will be used with conditional expression
                region_lock_item = {
                    "PK": f"REGION_LOCK#{region_combo_key}",
                    "SK": "LOCK",
                    "InstallationId": installation_id,
                    "EntityType": "REGION_LOCK",
                    "CreatedDate": timestamp
                }
                
                # First, try to create the region lock atomically
                try:
                    table.put_item(
                        Item=convert_floats_to_decimal(region_lock_item),
                        ConditionExpression="attribute_not_exists(PK)"  # Only succeeds if lock doesn't exist
                    )
                    logger.info(f"Created region lock for {region_combo_key}")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                        # Region lock already exists - duplicate installation
                        logger.warning(f"Duplicate installation attempt for region combination: {region_combo_key}")
                        # Try to find existing installation ID
                        try:
                            existing = table.get_item(Key={"PK": f"REGION_LOCK#{region_combo_key}", "SK": "LOCK"})
                            existing_id = existing.get("Item", {}).get("InstallationId", "unknown")
                        except:
                            existing_id = "unknown"
                        return ErrorResponse.build(
                            f"Installation already exists for this region combination (InstallationId: {existing_id}). "
                            f"Region: {state_id}/{district_id}/{mandal_id}/{village_id}/{habitation_id}",
                            409  # Conflict status code
                        )
                    else:
                        raise  # Re-raise if it's a different error
                
                # Region lock created successfully, now create the installation
                installation_item = convert_floats_to_decimal(installation_item)
                table.put_item(Item=installation_item)
                
                logger.info(f"Created installation {installation_id}")
                
                # Fetch and add region names to response
                response_data = simplify(installation_item)
                region_names = fetch_region_names(
                    state_id=response_data.get("StateId"),
                    district_id=response_data.get("DistrictId"),
                    mandal_id=response_data.get("MandalId"),
                    village_id=response_data.get("VillageId"),
                    habitation_id=response_data.get("HabitationId")
                )
                response_data.update(region_names)
                
                # Sync region assets to Thingsboard (non-blocking)
                try:
                    from shared.thingsboard_utils import sync_installation_regions_to_thingsboard
                    
                    logger.info(f"Syncing installation regions to Thingsboard for installation {installation_id}")
                    logger.info(f"Installation data keys: {list(response_data.keys())}")
                    logger.info(f"Installation data: {response_data}")
                    
                    # Sync all regions (state, district, mandal, village, habitation)
                    sync_results = sync_installation_regions_to_thingsboard(response_data)
                    
                    logger.info(f"Thingsboard sync results: {sync_results}")
                    
                    response_data["thingsboardStatus"] = "synced"
                    response_data["thingsboardAssets"] = sync_results
                    
                    if sync_results.get("errors"):
                        logger.warning(f"Thingsboard sync had errors: {sync_results['errors']}")
                        response_data["thingsboardStatus"] = "partial"
                        response_data["thingsboardErrors"] = sync_results["errors"]
                    else:
                        logger.info(f"Successfully synced all regions to Thingsboard for installation {installation_id}")
                    
                    # Save thingsboardAssets back to DynamoDB so device linking can access it
                    try:
                        table.update_item(
                            Key={"PK": f"INSTALL#{installation_id}", "SK": "META"},
                            UpdateExpression="SET thingsboardAssets = :assets, thingsboardStatus = :status",
                            ExpressionAttributeValues={
                                ":assets": sync_results,
                                ":status": response_data["thingsboardStatus"]
                            }
                        )
                        logger.info(f"Saved thingsboardAssets to installation record")
                    except Exception as update_error:
                        logger.error(f"Failed to save thingsboardAssets to DynamoDB: {str(update_error)}")
                        
                except Exception as e:
                    logger.error(f"Thingsboard sync failed (non-blocking): {str(e)}", exc_info=True)
                    response_data["thingsboardStatus"] = "error"
                    response_data["thingsboardError"] = str(e)
                
                # Link devices if provided in request (called from UI)
                # Support both deviceIds and DeviceIds (case variations)
                device_ids = body.get("deviceIds") or body.get("DeviceIds", [])
                if device_ids:
                    logger.info(f"Linking {len(device_ids)} devices to installation {installation_id}")
                
                    device_link_results = []
                    device_link_errors = []
                
                    for device_id in device_ids:
                        try:
                            # Validate device exists
                            device_response = table.get_item(
                                Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                            )
                            if "Item" not in device_response:
                                device_link_errors.append({"deviceId": device_id, "error": "Device not found"})
                                continue
                            
                            # Check if device is already linked to another installation
                            is_linked, existing_install_id = get_device_installation_link(device_id)
                            if is_linked:
                                device_link_errors.append({
                                    "deviceId": device_id, 
                                    "error": f"Device already linked to installation {existing_install_id}"
                                })
                                continue
                        
                            # Execute the device link transaction
                            performed_by = body.get("CreatedBy", "system")
                            ip_address = get_client_ip(event)
                            reason = "Linked during installation creation"
                        
                            success, transaction_error = execute_install_device_link_transaction(
                                installation_id, device_id, performed_by, ip_address, reason
                            )
                        
                            if success:
                                # Link device to habitation asset in Thingsboard (non-blocking)
                                try:
                                    from shared.thingsboard_utils import link_device_to_habitation
                                
                                    # Get habitation asset ID from installation
                                    install_response = table.get_item(Key={"PK": f"INSTALL#{installation_id}", "SK": "META"})
                                    if "Item" in install_response:
                                        installation = install_response["Item"]
                                        thingsboard_assets = installation.get("thingsboardAssets")
                                        habitation_id = None
                                    
                                        if isinstance(thingsboard_assets, dict):
                                            habitation_id = thingsboard_assets.get("habitation", {}).get("id")
                                    
                                        if habitation_id:
                                            logger.info(f"Linking device {device_id} to habitation {habitation_id} in Thingsboard")
                                            link_success = link_device_to_habitation(device_id, habitation_id)
                                            if link_success:
                                                logger.info(f"Successfully linked device {device_id} to habitation in Thingsboard")
                                            else:
                                                logger.warning(f"Failed to link device {device_id} to habitation in Thingsboard (non-blocking)")
                                except Exception as e:
                                    logger.warning(f"Thingsboard device linking failed (non-blocking): {str(e)}", exc_info=True)
                            
                                device_link_results.append({"deviceId": device_id, "status": "linked"})
                            else:
                                device_link_errors.append({"deviceId": device_id, "error": transaction_error})
                    
                        except Exception as e:
                            logger.error(f"Error linking device {device_id}: {str(e)}", exc_info=True)
                            device_link_errors.append({"deviceId": device_id, "error": str(e)})
                
                    # Add device linking results to response
                    response_data["deviceLinking"] = {
                        "linked": device_link_results,
                        "errors": device_link_errors if device_link_errors else []
                    }
                
                    logger.info(f"Device linking complete: {len(device_link_results)} linked, {len(device_link_errors)} failed")
                
                return SuccessResponse.build({
                    "message": "Installation created successfully",
                    "installation": response_data
                }, 201)
            except Exception as e:
                logger.error(f"Error creating installation: {str(e)}")
                return ErrorResponse.build(f"Error creating installation: {str(e)}", 500)
        
        # Check if this is a /devices/{deviceId}/sim/link request
        if path_parameters.get("deviceId") and "/sim/link" in path:
            device_id = path_parameters.get("deviceId")
            logger.info(f"Linking SIM to device: {device_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            sim_id = body.get("simId")
            if not sim_id:
                return ErrorResponse.build("simId is required in request body", 400)
            
            performed_by = body.get("performedBy", "system")
            ip_address = get_client_ip(event)
            
            # Validate deviceId format
            if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                return ErrorResponse.build("Invalid deviceId format", 400)
            
            # Check if device exists
            try:
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
            except Exception as e:
                logger.error(f"Error checking device existence: {str(e)}")
                return ErrorResponse.build(f"Error validating device: {str(e)}", 500)
            
            # Check if device already has a linked SIM
            try:
                existing_sim_response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "SIM_ASSOC#"
                    }
                )
                if existing_sim_response.get("Items"):
                    existing_sim_id = existing_sim_response["Items"][0].get("SIMId")
                    return ErrorResponse.build(f"Device {device_id} already has a linked SIM: {existing_sim_id}. Please unlink first.", 400)
            except Exception as e:
                logger.error(f"Error checking existing SIM link: {str(e)}")
                return ErrorResponse.build(f"Error checking existing link: {str(e)}", 500)
            
            # Validate SIM is available for linking
            is_valid, error_msg, sim_data = validate_sim_available(sim_id)
            if not is_valid:
                logger.warning(f"SIM validation failed: {error_msg}")
                return ErrorResponse.build(error_msg, 400)
            
            # Get device name for history
            device_name = device_response.get("Item", {}).get("DeviceName", "")
            
            # Execute atomic transaction
            sim_provider = sim_data.get("provider", "Unknown")
            success, transaction_error = execute_sim_link_transaction(
                device_id, sim_id, sim_provider, performed_by, ip_address, sim_data, device_name
            )
            
            if not success:
                logger.error(f"Transaction failed: {transaction_error}")
                return ErrorResponse.build(transaction_error, 500)
            
            logger.info(f"Successfully linked SIM {sim_id} to device {device_id}")
            return SuccessResponse.build({
                "message": "SIM linked successfully",
                "deviceId": device_id,
                "simId": sim_id,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, 200)
        
        # Check if this is a /devices/{deviceId}/sim/unlink request
        if path_parameters.get("deviceId") and "/sim/unlink" in path:
            device_id = path_parameters.get("deviceId")
            logger.info(f"Unlinking SIM from device: {device_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            performed_by = body.get("performedBy", "system")
            ip_address = get_client_ip(event)
            
            # Validate deviceId format
            if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                return ErrorResponse.build("Invalid deviceId format", 400)
            
            # Check if device exists
            try:
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
            except Exception as e:
                logger.error(f"Error checking device existence: {str(e)}")
                return ErrorResponse.build(f"Error validating device: {str(e)}", 500)
            
            # Check if device has a linked SIM
            try:
                sim_response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "SIM_ASSOC#"
                    }
                )
                items = sim_response.get("Items", [])
                if not items:
                    return ErrorResponse.build(f"No SIM card linked to device {device_id}", 404)
                
                sim_assoc = items[0]
                sim_id = sim_assoc.get("SIMId")
                
                if not sim_id:
                    logger.error(f"SIM_ASSOC for device {device_id} missing SIMId")
                    return ErrorResponse.build("Invalid SIM association data", 500)
                
            except Exception as e:
                logger.error(f"Error fetching linked SIM: {str(e)}")
                return ErrorResponse.build(f"Error fetching linked SIM: {str(e)}", 500)
            
            # Get SIM and device details for history
            try:
                sim_data_response = simcards_table.get_item(
                    Key={"PK": f"SIMCARD#{sim_id}", "SK": "ENTITY#SIMCARD"}
                )
                sim_data = sim_data_response.get("Item", {})
                device_name = device_response.get("Item", {}).get("DeviceName", "")
            except Exception as e:
                logger.error(f"Error fetching SIM/device details: {str(e)}")
                sim_data = {}
                device_name = ""
            
            # Execute atomic transaction
            success, transaction_error = execute_sim_unlink_transaction(
                device_id, sim_id, performed_by, ip_address, sim_data, device_name
            )
            
            if not success:
                logger.error(f"Transaction failed: {transaction_error}")
                return ErrorResponse.build(transaction_error, 500)
            
            logger.info(f"Successfully unlinked SIM {sim_id} from device {device_id}")
            return SuccessResponse.build({
                "message": "SIM unlinked successfully",
                "deviceId": device_id,
                "simId": sim_id,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, 200)
        
        # Check if this is a POST /devices/{deviceId}/repairs request
        if path_parameters.get("deviceId") and "/repairs" in path and method == "POST":
            device_id = path_parameters.get("deviceId")
            logger.info(f"Creating repair record for device: {device_id}")
            logger.debug(f"Path: {path}, PathParams: {path_parameters}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Validate required fields
            if not body.get("description"):
                return ErrorResponse.build("Missing required field: description", 400)
            
            # Comprehensive input validation
            is_valid, validation_errors = validate_repair_input(body)
            if not is_valid:
                return ErrorResponse.build(f"Validation errors: {'; '.join(validation_errors)}", 400)
            
            # Validate device exists
            try:
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
            except Exception as e:
                logger.error(f"Error checking device existence: {str(e)}")
                return ErrorResponse.build(f"Error validating device: {str(e)}", 500)
            
            # Generate repair ID
            repair_id = body.get("repairId") or f"REP{str(uuid.uuid4())[:8].upper()}"
            timestamp = datetime.utcnow().isoformat() + "Z"
            
            # Build repair item
            repair_item = {
                "PK": f"DEVICE#{device_id}",
                "SK": f"REPAIR#{repair_id}#{timestamp[:10]}",
                "EntityType": "REPAIR",
                "DeviceId": device_id,
                "RepairId": repair_id,
                "Description": body.get("description", ""),
                "Cost": body.get("cost", 0),
                "Technician": body.get("technician", ""),
                "Status": body.get("status", "pending"),
                "CreatedDate": timestamp,
                "UpdatedDate": timestamp,
                "CreatedBy": body.get("createdBy", "system"),
                "UpdatedBy": body.get("createdBy", "system")
            }
            
            try:
                table.put_item(Item=repair_item)
                logger.info(f"Created repair {repair_id} for device {device_id}")
                return SuccessResponse.build({
                    "message": "Repair record created successfully",
                    "repair": simplify(repair_item)
                }, 201)
            except Exception as e:
                logger.error(f"Error creating repair: {str(e)}")
                return ErrorResponse.build(f"Error creating repair: {str(e)}", 500)

        # Check if this is a PUT /devices/{deviceId}/repairs/{repairId} request
        if path_parameters.get("deviceId") and path_parameters.get("repairId") and "/repairs" in path and method == "PUT":
            device_id = path_parameters.get("deviceId")
            repair_id = path_parameters.get("repairId")
            logger.info(f"Updating repair {repair_id} for device {device_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Query for the repair record
            try:
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": f"REPAIR#{repair_id}"
                    }
                )
                items = response.get("Items", [])
                if not items:
                    return ErrorResponse.build(f"Repair {repair_id} not found for device {device_id}", 404)
                
                repair_item = items[0]
            except Exception as e:
                logger.error(f"Error querying repair: {str(e)}")
                return ErrorResponse.build(f"Error retrieving repair: {str(e)}", 500)
            
            # Update allowed fields
            updatable_fields = {
                "Description": "description",
                "Cost": "cost",
                "Technician": "technician",
                "Status": "status"
            }
            
            # Apply updates
            for db_field, request_field in updatable_fields.items():
                if request_field in body:
                    repair_item[db_field] = body[request_field]
            
            # Update metadata
            repair_item["UpdatedDate"] = datetime.utcnow().isoformat() + "Z"
            repair_item["UpdatedBy"] = body.get("updatedBy", "system")
            
            try:
                table.put_item(Item=repair_item)
                logger.info(f"Updated repair {repair_id} for device {device_id}")
                return SuccessResponse.build({
                    "message": "Repair record updated successfully",
                    "repair": simplify(repair_item)
                }, 200)
            except Exception as e:
                logger.error(f"Error updating repair: {str(e)}")
                return ErrorResponse.build(f"Error updating repair: {str(e)}", 500)

        # Check if this is a /installs/{installId}/devices/link request
        install_id_check = path_parameters.get("installId")
        link_in_path = "/devices/link" in path
        logger.debug(f"POST link check: path={path}, installId={install_id_check}, '/devices/link' in path: {link_in_path}, combined: {install_id_check and link_in_path}")
        if path_parameters.get("installId") and "/devices/link" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Linking device(s) to install: {install_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Support both single deviceId and array of deviceIds
            device_ids = body.get("deviceIds") or ([body.get("deviceId")] if body.get("deviceId") else [])
            if not device_ids:
                return ErrorResponse.build("deviceId or deviceIds array is required in request body", 400)
            
            # Validate batch size
            if len(device_ids) > 50:
                return ErrorResponse.build("Maximum 50 devices can be linked at once", 400)
            
            performed_by = body.get("performedBy", "system")
            reason = body.get("reason")
            ip_address = get_client_ip(event)
            
            # Validate install exists
            is_valid, error_msg = validate_install_exists(install_id)
            if not is_valid:
                return ErrorResponse.build(error_msg, 404)
            
            # Batch validate device existence - much faster than sequential lookups
            logger.info(f"Batch validating {len(device_ids)} devices")
            try:
                batch_keys = [{"PK": f"DEVICE#{device_id}", "SK": "META"} for device_id in device_ids]
                batch_response = dynamodb_client.batch_get_item(
                    RequestItems={
                        TABLE_NAME: {
                            "Keys": batch_keys
                        }
                    }
                )
                
                found_devices = {item["DeviceId"]["S"]: item for item in batch_response.get("Responses", {}).get(TABLE_NAME, [])}
                logger.info(f"Found {len(found_devices)} devices out of {len(device_ids)}")
            except Exception as e:
                logger.error(f"Batch device lookup failed: {str(e)}")
                # Fallback to sequential validation
                found_devices = {}
            
            # Link each device
            results = []
            errors = []
            
            for device_id in device_ids:
                # Validate device format
                if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                    errors.append({"deviceId": device_id, "error": "Invalid deviceId format"})
                    continue
                
                # Check if device exists (using batch lookup result)
                if found_devices:
                    if device_id not in found_devices:
                        errors.append({"deviceId": device_id, "error": f"Device {device_id} not found"})
                        continue
                else:
                    # Fallback: sequential validation
                    is_valid, error_msg = validate_device_exists(device_id)
                    if not is_valid:
                        errors.append({"deviceId": device_id, "error": error_msg})
                        continue
                
                # Check if already linked to THIS installation
                if check_device_install_link(device_id, install_id):
                    errors.append({"deviceId": device_id, "error": f"Device already linked to install {install_id}"})
                    continue
                
                # Check if device is already linked to ANY OTHER installation
                is_linked, existing_install_id = get_device_installation_link(device_id)
                if is_linked and existing_install_id != install_id:
                    errors.append({
                        "deviceId": device_id, 
                        "error": f"Device already linked to installation {existing_install_id}"
                    })
                    continue
                
                # Execute link transaction
                success, transaction_error = execute_install_device_link_transaction(
                    install_id, device_id, performed_by, ip_address, reason
                )
                
                if success:
                    # Link device to habitation asset in Thingsboard (non-blocking)
                    try:
                        from shared.thingsboard_utils import link_device_to_habitation
                        
                        # Get installation to find habitation asset ID
                        install_response = table.get_item(Key={"PK": f"INSTALL#{install_id}", "SK": "META"})
                        if "Item" in install_response:
                            installation = install_response["Item"]
                            thingsboard_assets = installation.get("thingsboardAssets")
                            habitation_id = None
                            
                            if isinstance(thingsboard_assets, dict):
                                habitation_id = thingsboard_assets.get("habitation", {}).get("id")
                            
                            if habitation_id:
                                logger.info(f"Linking device {device_id} to habitation {habitation_id} in Thingsboard")
                                link_success = link_device_to_habitation(device_id, habitation_id)
                                if link_success:
                                    logger.info(f"Successfully linked device {device_id} to habitation in Thingsboard")
                                else:
                                    logger.warning(f"Failed to link device {device_id} to habitation in Thingsboard (non-blocking)")
                            else:
                                logger.warning(f"Habitation asset not found for installation {install_id} (non-blocking)")
                        else:
                            logger.warning(f"Installation not found for Thingsboard linking {install_id} (non-blocking)")
                    except Exception as e:
                        logger.warning(f"Thingsboard device linking failed (non-blocking): {str(e)}", exc_info=True)
                    
                    results.append({"deviceId": device_id, "status": "linked"})
                else:
                    errors.append({"deviceId": device_id, "error": transaction_error})
            
            response_data = {
                "installId": install_id,
                "linked": results,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            if errors:
                response_data["errors"] = errors
            
            status_code = 200 if results else 400
            logger.info(f"Link operation complete: {len(results)} succeeded, {len(errors)} failed")
            return SuccessResponse.build(response_data, status_code)
        
        # Check if this is a /installs/{installId}/contacts/link request
        if path_parameters.get("installId") and "/contacts/link" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Linking contact(s) to install: {install_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Support both single contactId and array of contactIds
            contact_ids = body.get("contactIds") or ([body.get("contactId")] if body.get("contactId") else [])
            if not contact_ids:
                return ErrorResponse.build("contactId or contactIds array is required in request body", 400)
            
            # Validate batch size
            if len(contact_ids) > 50:
                return ErrorResponse.build("Maximum 50 contacts can be linked at once", 400)
            
            performed_by = body.get("performedBy", "system")
            reason = body.get("reason")
            ip_address = get_client_ip(event)
            
            # Validate install exists and get CustomerId
            is_valid, error_msg = validate_install_exists(install_id)
            if not is_valid:
                return ErrorResponse.build(error_msg, 404)
            
            # Get installation to retrieve CustomerId
            try:
                install_response = table.get_item(
                    Key={"PK": f"INSTALL#{install_id}", "SK": "META"}
                )
                if "Item" not in install_response:
                    return ErrorResponse.build(f"Installation {install_id} not found", 404)
                
                customer_id = install_response["Item"].get("CustomerId")
                if not customer_id:
                    return ErrorResponse.build(f"Installation {install_id} does not have a CustomerId. Cannot link contacts.", 400)
            except Exception as e:
                logger.error(f"Error fetching installation: {str(e)}")
                return ErrorResponse.build(f"Error fetching installation: {str(e)}", 500)
            
            # Batch validate contacts belong to customer
            logger.info(f"Batch validating {len(contact_ids)} contacts for customer {customer_id}")
            valid_contacts, invalid_contacts = validate_contacts_belong_to_customer_batch(contact_ids, customer_id)
            
            # Link each valid contact
            results = []
            errors = []
            
            # Add errors for invalid contacts
            for contact_id in invalid_contacts:
                errors.append({
                    "contactId": contact_id,
                    "error": f"Contact not found or doesn't belong to customer {customer_id}"
                })
            
            # Link valid contacts
            for contact_id in valid_contacts:
                # Execute link transaction
                success, transaction_error = execute_install_contact_link_transaction(
                    install_id, contact_id, customer_id, performed_by, ip_address, reason
                )
                
                if success:
                    results.append({"contactId": contact_id, "status": "linked"})
                else:
                    errors.append({"contactId": contact_id, "error": transaction_error})
            
            response_data = {
                "installId": install_id,
                "customerId": customer_id,
                "linked": results,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            if errors:
                response_data["errors"] = errors
            
            status_code = 200 if results else 400
            logger.info(f"Contact link operation complete: {len(results)} succeeded, {len(errors)} failed")
            return SuccessResponse.build(response_data, status_code)
        
        # Check if this is a /installs/{installId}/devices/unlink request
        if path_parameters.get("installId") and "/devices/unlink" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Unlinking device(s) from install: {install_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Support both single deviceId and array of deviceIds
            device_ids = body.get("deviceIds") or ([body.get("deviceId")] if body.get("deviceId") else [])
            if not device_ids:
                return ErrorResponse.build("deviceId or deviceIds array is required in request body", 400)
            
            performed_by = body.get("performedBy", "system")
            reason = body.get("reason")
            ip_address = get_client_ip(event)
            
            # Validate install exists
            is_valid, error_msg = validate_install_exists(install_id)
            if not is_valid:
                return ErrorResponse.build(error_msg, 404)
            
            # Unlink each device
            results = []
            errors = []
            
            for device_id in device_ids:
                # Validate device format
                if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                    errors.append({"deviceId": device_id, "error": "Invalid deviceId format"})
                    continue
                
                # Execute unlink transaction
                success, transaction_error = execute_install_device_unlink_transaction(
                    install_id, device_id, performed_by, ip_address, reason
                )
                
                if success:
                    # Unlink device from habitation asset in Thingsboard (non-blocking)
                    try:
                        from shared.thingsboard_utils import unlink_device_from_habitation

                        # Get installation to find habitation asset ID
                        install_response = table.get_item(Key={"PK": f"INSTALL#{install_id}", "SK": "META"})
                        if "Item" in install_response:
                            installation = install_response["Item"]
                            thingsboard_assets = installation.get("thingsboardAssets")
                            habitation_id = None

                            if isinstance(thingsboard_assets, dict):
                                habitation_id = thingsboard_assets.get("habitation", {}).get("id")

                            if habitation_id:
                                logger.info(f"Unlinking device {device_id} from habitation {habitation_id} in Thingsboard")
                                unlink_success = unlink_device_from_habitation(device_id, habitation_id)
                                if unlink_success:
                                    logger.info(f"Successfully unlinked device {device_id} from habitation in Thingsboard")
                                else:
                                    logger.warning(f"Failed to unlink device {device_id} from habitation in Thingsboard (non-blocking)")
                            else:
                                logger.warning(f"Habitation asset not found for installation {install_id} (non-blocking)")
                        else:
                            logger.warning(f"Installation not found for Thingsboard unlinking {install_id} (non-blocking)")
                    except Exception as e:
                        logger.warning(f"Thingsboard device unlinking failed (non-blocking): {str(e)}", exc_info=True)

                    results.append({"deviceId": device_id, "status": "unlinked"})
                else:
                    errors.append({"deviceId": device_id, "error": transaction_error})
            
            response_data = {
                "installId": install_id,
                "unlinked": results,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            if errors:
                response_data["errors"] = errors
            
            status_code = 200 if results else 400
            logger.info(f"Unlink operation complete: {len(results)} succeeded, {len(errors)} failed")
            return SuccessResponse.build(response_data, status_code)
        
        # Check if this is a /installs/{installId}/contacts/unlink request
        if path_parameters.get("installId") and "/contacts/unlink" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Unlinking contact(s) from install: {install_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Support both single contactId and array of contactIds
            contact_ids = body.get("contactIds") or ([body.get("contactId")] if body.get("contactId") else [])
            if not contact_ids:
                return ErrorResponse.build("contactId or contactIds array is required in request body", 400)
            
            performed_by = body.get("performedBy", "system")
            reason = body.get("reason")
            ip_address = get_client_ip(event)
            
            # Validate install exists
            is_valid, error_msg = validate_install_exists(install_id)
            if not is_valid:
                return ErrorResponse.build(error_msg, 404)
            
            # Unlink each contact
            results = []
            errors = []
            
            for contact_id in contact_ids:
                # Execute unlink transaction
                success, transaction_error = execute_install_contact_unlink_transaction(
                    install_id, contact_id, performed_by, ip_address, reason
                )
                
                if success:
                    results.append({"contactId": contact_id, "status": "unlinked"})
                else:
                    errors.append({"contactId": contact_id, "error": transaction_error})
            
            response_data = {
                "installId": install_id,
                "unlinked": results,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            if errors:
                response_data["errors"] = errors
            
            status_code = 200 if results else 400
            logger.info(f"Contact unlink operation complete: {len(results)} succeeded, {len(errors)} failed")
            return SuccessResponse.build(response_data, status_code)

        # Default POST handler for creating entities
        try:
            item = json.loads(event.get("body", "{}"))
            if not isinstance(item, dict):
                raise ValueError("POST body must be a dict")
            item = convert_floats_to_decimal(item)
        except Exception as e:
            logger.error(f"Failed to parse body: {e}")
            return ErrorResponse.build(f"Malformed JSON body: {e}", 400)

        entity_type = item.get("EntityType")
        if not entity_type:
            return ErrorResponse.build("EntityType is required", 400)

        # Auto-generate DeviceId if not provided
        device_id = item.get("DeviceId")
        if not device_id:
            device_id = f"DEV-{str(uuid.uuid4())[:8].upper()}"
            item["DeviceId"] = device_id
            logger.info(f"Auto-generated DeviceId: {device_id}")

        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return ErrorResponse.build(f"Unknown EntityType: {entity_type}", 400)

        # Derive PK and SK
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for insert", 400)

        # Add PK and SK to item
        item["PK"] = pk
        item["SK"] = sk

        # Set timestamps if not provided
        timestamp = datetime.utcnow().isoformat() + "Z"
        if not item.get("CreatedDate"):
            item["CreatedDate"] = timestamp
        if not item.get("UpdatedDate"):
            item["UpdatedDate"] = timestamp
        # Set CreatedBy and UpdatedBy
        if item.get("CreatedBy"):
            if not item.get("UpdatedBy"):
                item["UpdatedBy"] = item["CreatedBy"]

        try:
            # Validate with Pydantic model
            validated_item = model(**item)
        
            # Insert new item with duplicate prevention
            table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
            )
            logger.info(f"Created new {entity_type} with PK={pk}, SK={sk}")
            return SuccessResponse.build({"created": item}, 201)
        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return ErrorResponse.build(f"Validation error: {str(e)}", 400)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Duplicate {entity_type} detected: PK={pk}, SK={sk}")
                return ErrorResponse.build(f"{entity_type} with ID {device_id} already exists", 409)
            logger.error(f"DynamoDB error: {str(e)}")
            return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
        except Exception as e:
            logger.error(f"Insert error: {str(e)}")
            return ErrorResponse.build(f"Insert error: {str(e)}", 500)

    elif method == "GET":
        # Extract path (HTTP API 2.0 uses rawPath, REST API uses path)
        path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path") or ""
        path_parameters = event.get("pathParameters") or {}
        params = event.get("queryStringParameters") or {}
        device_id_param = path_parameters.get("deviceId") or path_parameters.get("id")
        
        # Check if this is a /devices/{deviceId}/sim request (no EntityType required)
        if device_id_param and "/sim" in path:
            device_id = device_id_param
            logger.info(f"Fetching linked SIM for device: {device_id}")
            
            # Check if caller wants decrypted data (default: decrypted)
            if "decrypt" in params:
                should_decrypt = params.get("decrypt", "").lower() == "true"
            else:
                should_decrypt = True
            logger.info(f"GET /devices/{device_id}/sim - decrypt={should_decrypt}")
            
            # Validate deviceId format
            if not device_id or not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                logger.warning(f"Invalid deviceId format: {device_id}")
                return ErrorResponse.build("Invalid deviceId format. Must be alphanumeric with optional _ or - (1-64 chars)", 400)
            
            try:
                # Check if device exists
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    logger.info(f"Device not found: {device_id}")
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
                
                # Query SIM_ASSOC entity for this device
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "SIM_ASSOC#"
                    }
                )
                items = response.get("Items", [])
                
                if not items:
                    logger.info(f"No SIM linked to device {device_id}")
                    return ErrorResponse.build(f"No SIM card linked to device {device_id}", 404)
                
                # Get the first (and should be only) SIM_ASSOC
                sim_assoc = items[0]
                sim_id = sim_assoc.get("SIMId")
                
                if not sim_id:
                    logger.error(f"SIM_ASSOC for device {device_id} missing SIMId")
                    return ErrorResponse.build("Invalid SIM association data", 500)
                
                # Fetch full SIM details from simcards table
                success, sim_data, error_msg = fetch_sim_details(sim_id, should_decrypt=should_decrypt)
                if not success:
                    logger.error(f"Failed to fetch SIM details: {error_msg}")
                    return ErrorResponse.build(error_msg, 500)
                
                # Merge SIM_ASSOC and SIM data
                result = {
                    "simId": sim_id,
                    "linkedDate": sim_assoc.get("CreatedDate"),
                    "linkStatus": sim_assoc.get("Status"),
                    "simDetails": sim_data
                }
                
                logger.info(f"Successfully fetched linked SIM {sim_id} for device {device_id}")
                return SuccessResponse.build(result)
                
            except ClientError as e:
                logger.error(f"Database error fetching SIM for {device_id}: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error fetching SIM for {device_id}: {str(e)}")
                return ErrorResponse.build(f"Error fetching SIM: {str(e)}", 500)
        
        # Check if this is a /devices/{deviceId}/configs request
        if device_id_param and "/configs" in path:
            device_id = device_id_param
            logger.info(f"Fetching configs for device: {device_id}")
            
            # Validate deviceId format
            if not device_id or not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                logger.warning(f"Invalid deviceId format: {device_id}")
                return ErrorResponse.build("Invalid deviceId format. Must be alphanumeric with optional _ or - (1-64 chars)", 400)
            
            try:
                # Check if device exists
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    logger.info(f"Device not found: {device_id}")
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
                
                # Query all CONFIG entities for this device
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "CONFIG#"
                    }
                )
                items = response.get("Items", [])
                logger.info(f"Found {len(items)} config(s) for device {device_id}")
                return SuccessResponse.build(transform_items_to_json(items, should_decrypt=should_decrypt))
            except ClientError as e:
                logger.error(f"Database error fetching configs for {device_id}: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error fetching configs for {device_id}: {str(e)}")
                return ErrorResponse.build(f"Error fetching configs: {str(e)}", 500)

        # Check if this is a GET /installs/{installId} request (single install) - must be before /devices and /history checks
        # This needs to check that the path is exactly /installs/{installId} without sub-paths
        install_id_param = path_parameters.get("installId")
        logger.debug(f"GET handler: path={path}, installId={install_id_param}, '/installs' in path: {'/installs' in path}, '/devices' in path: {'/devices' in path}, '/history' in path: {'/history' in path}")
        if install_id_param and "/installs" in path and "/devices" not in path and "/history" not in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Fetching install: {install_id}")

            # Check query params
            include_devices = params.get("includeDevices", "false").lower() == "true"
            include_customer = params.get("includeCustomer", "true").lower() == "true"

            try:
                response = table.get_item(
                    Key={"PK": f"INSTALL#{install_id}", "SK": "META"}
                )
                if "Item" not in response:
                    return ErrorResponse.build(f"Installation {install_id} not found", 404)

                install_data = simplify(response["Item"])

                # Fetch and add region names
                region_names = fetch_region_names(
                    state_id=install_data.get("StateId"),
                    district_id=install_data.get("DistrictId"),
                    mandal_id=install_data.get("MandalId"),
                    village_id=install_data.get("VillageId"),
                    habitation_id=install_data.get("HabitationId")
                )
                install_data.update(region_names)

                # If includeCustomer is requested, fetch customer details
                if include_customer:
                    customer_id = install_data.get("CustomerId")
                    if customer_id:
                        try:
                            customers_table = dynamodb.Table(os.environ.get("CUSTOMERS_TABLE", "v_customers_dev"))
                            customer_response = customers_table.get_item(
                                Key={"PK": f"CUSTOMER#{customer_id}", "SK": "ENTITY#CUSTOMER"}
                            )
                            if "Item" in customer_response:
                                customer_item = simplify(customer_response["Item"])
                                install_data["customerName"] = customer_item.get("name")
                                install_data["customer"] = {
                                    "customerId": customer_item.get("customerId") or customer_id,
                                    "name": customer_item.get("name"),
                                    "companyName": customer_item.get("companyName"),
                                    "email": customer_item.get("email"),
                                    "phone": customer_item.get("phone"),
                                    "countryCode": customer_item.get("countryCode"),
                                    "customerNumber": customer_item.get("customerNumber")
                                }
                            else:
                                install_data["customer"] = {"customerId": customer_id, "error": "Customer not found"}
                        except Exception as e:
                            logger.warning(f"Failed to fetch customer {customer_id}: {str(e)}")
                            install_data["customer"] = {"customerId": customer_id, "error": f"Lookup error: {str(e)}"}

                # If includeDevices is requested, fetch linked devices
                if include_devices:
                    device_response = table.query(
                        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                        ExpressionAttributeValues={
                            ":pk": f"INSTALL#{install_id}",
                            ":sk": "DEVICE_ASSOC#"
                        }
                    )

                    linked_devices = []
                    for assoc in device_response.get("Items", []):
                        device_id = assoc.get("DeviceId")
                        if device_id:
                            device_item = table.get_item(
                                Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                            )
                            if "Item" in device_item:
                                device_data = simplify(device_item["Item"])
                                device_data["linkedDate"] = assoc.get("LinkedDate")
                                device_data["linkedBy"] = assoc.get("LinkedBy")
                                device_data["linkStatus"] = assoc.get("Status")
                                linked_devices.append(device_data)

                    install_data["linkedDevices"] = linked_devices
                    install_data["linkedDeviceCount"] = len(linked_devices)

                # If includeContacts is requested, fetch linked contacts
                include_contacts = params.get("includeContacts", "false").lower() == "true"
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
                                    "PK": {"S": f"CUSTOMER#{customer_id}"},
                                    "SK": {"S": f"ENTITY#CONTACT#{contact_id}"}
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

                return SuccessResponse.build(install_data)

            except ClientError as e:
                logger.error(f"Database error fetching install {install_id}: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error fetching install {install_id}: {str(e)}")
                return ErrorResponse.build(f"Error fetching install: {str(e)}", 500)
        
        # Check if this is a GET /installs request (list all installs)
        if "/installs" in path and not path_parameters.get("installId"):
            logger.info("Fetching all installs")
            
            # Check if includeDevices query parameter is set
            query_params = event.get("queryStringParameters") or {}
            include_devices = query_params.get("includeDevices", "false").lower() == "true"
            include_customer = query_params.get("includeCustomer", "true").lower() == "true"
            
            # Pagination parameters
            limit = int(query_params.get("limit", "50"))  # Default 50 items per page
            next_token = query_params.get("nextToken")
            
            # Validate limit
            if limit < 1 or limit > 100:
                return ErrorResponse.build("Limit must be between 1 and 100", 400)
            
            try:
                # Query all INSTALL records with pagination
                scan_params = {
                    "FilterExpression": "begins_with(PK, :pk_prefix)",
                    "ExpressionAttributeValues": {
                        ":pk_prefix": "INSTALL#"
                    }
                }
                
                # Add pagination token if provided
                if next_token:
                    try:
                        import base64
                        decoded_token = json.loads(base64.b64decode(next_token).decode('utf-8'))
                        scan_params["ExclusiveStartKey"] = decoded_token
                    except Exception as e:
                        logger.error(f"Invalid nextToken: {e}")
                        return ErrorResponse.build("Invalid nextToken", 400)
                
                # Keep scanning until we have enough installations or no more data
                installs = []
                last_evaluated_key = None
                
                while len(installs) < limit:
                    response = table.scan(**scan_params)
                    
                    for item in response.get("Items", []):
                        # Only include items with SK = META (main install record)
                        if item.get("SK") == "META":
                            install_data = simplify(item)
                            
                            # Fetch and add region names
                            region_names = fetch_region_names(
                                state_id=install_data.get("StateId"),
                                district_id=install_data.get("DistrictId"),
                                mandal_id=install_data.get("MandalId"),
                                village_id=install_data.get("VillageId"),
                                habitation_id=install_data.get("HabitationId")
                            )
                            install_data.update(region_names)
                            
                            # If includeCustomer is requested, fetch customer details
                            if include_customer:
                                customer_id = install_data.get("CustomerId")
                                if customer_id:
                                    # Query customer from v_customers table
                                    try:
                                        customers_table = dynamodb.Table(os.environ.get("CUSTOMERS_TABLE", "v_customers_dev"))
                                        customer_response = customers_table.get_item(
                                            Key={"PK": f"CUSTOMER#{customer_id}", "SK": "ENTITY#CUSTOMER"}
                                        )
                                        if "Item" in customer_response:
                                            customer_item = simplify(customer_response["Item"])
                                            # Add customerName to base payload
                                            install_data["customerName"] = customer_item.get("name")
                                            # Include only relevant customer fields
                                            install_data["customer"] = {
                                                "customerId": customer_item.get("customerId") or customer_id,
                                                "name": customer_item.get("name"),
                                                "companyName": customer_item.get("companyName"),
                                                "email": customer_item.get("email"),
                                                "phone": customer_item.get("phone"),
                                                "countryCode": customer_item.get("countryCode")
                                            }
                                    except Exception as e:
                                        logger.warning(f"Failed to fetch customer {customer_id}: {str(e)}")
                                        install_data["customer"] = {"customerId": customer_id, "error": "Customer not found"}
                            
                            # If includeDevices is requested, fetch linked devices
                            if include_devices:
                                install_id = install_data.get("InstallationId")
                                if install_id:
                                    # Query device associations for this installation
                                    device_response = table.query(
                                        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                                        ExpressionAttributeValues={
                                            ":pk": f"INSTALL#{install_id}",
                                            ":sk": "DEVICE_ASSOC#"
                                        }
                                    )
                                    
                                    linked_devices = []
                                    for assoc in device_response.get("Items", []):
                                        device_id = assoc.get("DeviceId")
                                        if device_id:
                                            # Get device details
                                            device_item = table.get_item(
                                                Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                                            )
                                            if "Item" in device_item:
                                                device_data = simplify(device_item["Item"])
                                                device_data["linkedDate"] = assoc.get("LinkedDate")
                                                device_data["linkedBy"] = assoc.get("LinkedBy")
                                                device_data["linkStatus"] = assoc.get("Status")
                                                linked_devices.append(device_data)
                                    
                                    install_data["linkedDevices"] = linked_devices
                                    install_data["linkedDeviceCount"] = len(linked_devices)
                            
                            installs.append(install_data)
                            
                            # Stop if we have enough installations
                            if len(installs) >= limit:
                                break
                    
                    # Check if there are more results to scan
                    if "LastEvaluatedKey" in response:
                        last_evaluated_key = response["LastEvaluatedKey"]
                        scan_params["ExclusiveStartKey"] = last_evaluated_key
                    else:
                        # No more data to scan
                        last_evaluated_key = None
                        break
                
                # Prepare pagination response
                result = {
                    "installCount": len(installs),
                    "installs": installs,
                    "includeDevices": include_devices,
                    "includeCustomer": include_customer,
                    "limit": limit
                }
                
                # Add nextToken if there are more results
                if last_evaluated_key:
                    import base64
                    token = base64.b64encode(json.dumps(last_evaluated_key).encode('utf-8')).decode('utf-8')
                    result["nextToken"] = token
                    result["hasMore"] = True
                else:
                    result["hasMore"] = False
                
                logger.info(f"Found {len(installs)} install(s), hasMore: {result['hasMore']}")
                return SuccessResponse.build(result, 200)
                
            except ClientError as e:
                logger.error(f"Database error fetching installs: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error fetching installs: {str(e)}")
                return ErrorResponse.build(f"Error fetching installs: {str(e)}", 500)
        
        # Check if this is a /installs/{installId}/devices request
        if path_parameters.get("installId") and "/devices" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Fetching devices for install: {install_id}")
            
            try:
                # Validate install exists
                is_valid, error_msg = validate_install_exists(install_id)
                if not is_valid:
                    return ErrorResponse.build(error_msg, 404)
                
                # Query all device associations for this install
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"INSTALL#{install_id}",
                        ":sk": "DEVICE_ASSOC#"
                    }
                )
                assoc_items = response.get("Items", [])
                
                # Fetch full device details for each linked device
                devices = []
                for assoc in assoc_items:
                    device_id = assoc.get("DeviceId")
                    if device_id:
                        device_response = table.get_item(
                            Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                        )
                        if "Item" in device_response:
                            device_data = simplify(device_response["Item"])
                            device_data["linkedDate"] = assoc.get("LinkedDate")
                            device_data["linkedBy"] = assoc.get("LinkedBy")
                            device_data["linkStatus"] = assoc.get("Status")
                            devices.append(device_data)
                
                logger.info(f"Found {len(devices)} device(s) for install {install_id}")
                return SuccessResponse.build({
                    "installId": install_id,
                    "deviceCount": len(devices),
                    "devices": devices
                })
                
            except ClientError as e:
                logger.error(f"Database error: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return ErrorResponse.build(f"Error: {str(e)}", 500)


        def handle_get_device(device_id: str, should_decrypt: bool = True):
            """Fetch a single device with repair history and linked SIM details.
            
            Args:
                device_id: The device ID to fetch
                should_decrypt: If True (default), decrypt sensitive fields. If False, return encrypted data.
            """
            # Validate deviceId format
            if not device_id or not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                return ErrorResponse.build("Invalid deviceId format. Must be alphanumeric with optional _ or - (1-64 chars)", 400)

            try:
                device_response = table.get_item(Key={"PK": f"DEVICE#{device_id}", "SK": "META"})
                if "Item" not in device_response:
                    return ErrorResponse.build(f"Device {device_id} not found", 404)

                item = device_response["Item"]
                
                # Import encryption helper
                from shared.encryption_utils import prepare_item_for_response
                # Apply encryption/decryption based on decrypt parameter
                item = prepare_item_for_response(item, "DEVICE", decrypt=should_decrypt)

                # Repair history
                try:
                    repair_response = table.query(
                        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                        ExpressionAttributeValues={
                            ":pk": f"DEVICE#{device_id}",
                            ":sk": "REPAIR#"
                        }
                    )
                    item["RepairHistory"] = [simplify(r) for r in repair_response.get("Items", [])]
                except Exception as e:
                    logger.error(f"Error fetching repair history for {device_id}: {str(e)}")
                    item["RepairHistory"] = []

                # Linked SIM data
                try:
                    sim_response = table.query(
                        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                        ExpressionAttributeValues={
                            ":pk": f"DEVICE#{device_id}",
                            ":sk": "SIM_ASSOC#"
                        }
                    )
                    sim_items = sim_response.get("Items", [])
                    if sim_items:
                        sim_assoc = sim_items[0]
                        sim_id = sim_assoc.get("SIMId")
                        if sim_id:
                            success, sim_data, error_msg = fetch_sim_details(sim_id, should_decrypt=should_decrypt)
                            if success:
                                item["LinkedSIM"] = {
                                    "simId": sim_id,
                                    "linkedDate": sim_assoc.get("CreatedDate"),
                                    "linkStatus": sim_assoc.get("Status"),
                                    "simDetails": sim_data
                                }
                            else:
                                logger.warning(f"Failed to fetch SIM details for {sim_id}: {error_msg}")
                                item["LinkedSIM"] = None
                        else:
                            item["LinkedSIM"] = None
                    else:
                        # Fallback to existing field if present in META
                        item["LinkedSIM"] = item.get("LinkedSIM")
                except Exception as e:
                    logger.error(f"Error fetching SIM association for {device_id}: {str(e)}")
                    item["LinkedSIM"] = None

                return SuccessResponse.build(simplify(item))

            except ClientError as e:
                logger.error(f"Database error: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return ErrorResponse.build(f"Error fetching device: {str(e)}", 500)
        
        # Check if this is a /devices/{deviceId}/install request
        if path_parameters.get("deviceId") and "/install" in path:
            device_id = path_parameters.get("deviceId")
            logger.info(f"Fetching install info for device: {device_id}")
            
            # Validate deviceId format
            if not device_id or not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                return ErrorResponse.build("Invalid deviceId format", 400)
            
            try:
                # Validate device exists
                is_valid, error_msg = validate_device_exists(device_id)
                if not is_valid:
                    return ErrorResponse.build(error_msg, 404)
                
                # Query install association for this device
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "INSTALL_ASSOC#"
                    }
                )
                assoc_items = response.get("Items", [])
                
                if not assoc_items:
                    return ErrorResponse.build(f"Device {device_id} is not linked to any installation", 404)
                
                # Get install details
                assoc = assoc_items[0]
                install_id = assoc.get("InstallId")
                
                if install_id:
                    install_response = table.get_item(
                        Key={"PK": f"INSTALL#{install_id}", "SK": "META"}
                    )
                    if "Item" in install_response:
                        install_data = simplify(install_response["Item"])
                        install_data["linkedDate"] = assoc.get("LinkedDate")
                        install_data["linkedBy"] = assoc.get("LinkedBy")
                        install_data["linkStatus"] = assoc.get("Status")
                        
                        # Add customer information if available
                        customer_id = install_data.get("CustomerId")
                        if customer_id:
                            try:
                                customers_table = dynamodb.Table(os.environ.get("CUSTOMERS_TABLE", "v_customers_dev"))
                                customer_response = customers_table.get_item(
                                    Key={"PK": f"CUSTOMER#{customer_id}", "SK": "ENTITY#CUSTOMER"}
                                )
                                if "Item" in customer_response:
                                    customer_item = customer_response["Item"]
                                    install_data["customer"] = {
                                        "customerId": customer_item.get("customerId") or customer_id,
                                        "name": customer_item.get("name"),
                                        "companyName": customer_item.get("companyName"),
                                        "email": customer_item.get("email"),
                                        "phone": customer_item.get("phone"),
                                        "countryCode": customer_item.get("countryCode"),
                                        "customerNumber": customer_item.get("customerNumber")
                                    }
                                else:
                                    install_data["customer"] = {"customerId": customer_id, "error": "Customer not found"}
                            except Exception as e:
                                logger.warning(f"Failed to fetch customer {customer_id}: {str(e)}")
                                install_data["customer"] = {"customerId": customer_id, "error": f"Lookup error: {str(e)}"}
                        
                        logger.info(f"Found install {install_id} for device {device_id}")
                        return SuccessResponse.build(install_data)
                
                return ErrorResponse.build(f"Install details not found", 404)
                
            except ClientError as e:
                logger.error(f"Database error: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return ErrorResponse.build(f"Error: {str(e)}", 500)
        
        # Check if this is a /installs/{installId}/history request
        if path_parameters.get("installId") and "/history" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Fetching device link history for install: {install_id}")
            
            try:
                # Validate install exists
                is_valid, error_msg = validate_install_exists(install_id)
                if not is_valid:
                    return ErrorResponse.build(error_msg, 404)
                
                # Query history records
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"INSTALL#{install_id}",
                        ":sk": "DEVICE_HISTORY#"
                    }
                )
                history_items = response.get("Items", [])
                
                # Simplify and sort by timestamp descending
                history = [simplify(item) for item in history_items]
                history.sort(key=lambda x: x.get("PerformedAt", ""), reverse=True)
                
                logger.info(f"Found {len(history)} history record(s) for install {install_id}")
                return SuccessResponse.build({
                    "installId": install_id,
                    "historyCount": len(history),
                    "history": history
                })
                
            except ClientError as e:
                logger.error(f"Database error: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return ErrorResponse.build(f"Error: {str(e)}", 500)
        
        # GET /devices/{deviceId}
        if device_id_param:
            # Check if caller wants decrypted data (default: decrypted)
            if "decrypt" in params:
                should_decrypt = params.get("decrypt", "").lower() == "true"
            else:
                should_decrypt = True
            logger.info(f"GET /devices/{device_id_param} - decrypt={should_decrypt}")
            return handle_get_device(device_id_param, should_decrypt=should_decrypt)

        # Default: GET /devices - list all devices with optional filters
        # EntityType defaults to "DEVICE" if not provided for backward compatibility
        device_type = params.get("DeviceType")
        status = params.get("Status")
        
        # Pagination parameters
        limit = int(params.get("limit", "50"))  # Default 50 items per page
        next_token = params.get("nextToken")
        
        # Validate limit
        if limit < 1 or limit > 100:
            return ErrorResponse.build("Limit must be between 1 and 100", 400)
        
        # Check if caller wants decrypted data (default: decrypted)
        if "decrypt" in params:
            should_decrypt = params.get("decrypt", "").lower() == "true"
        else:
            should_decrypt = True
        logger.info(f"GET /devices - decrypt={should_decrypt}, limit={limit}")

        filter_expression = []
        expression_values = {}

        if device_type:
            filter_expression.append("DeviceType = :dt")
            expression_values[":dt"] = device_type
        if status:
            filter_expression.append("Status = :st")
            expression_values[":st"] = status

        filter_expression.append("EntityType = :et")
        expression_values[":et"] = "DEVICE"

        try:
            # Build scan parameters
            scan_params = {
                "Limit": limit
            }
            
            # Add pagination token if provided
            if next_token:
                try:
                    import base64
                    decoded_token = json.loads(base64.b64decode(next_token).decode('utf-8'))
                    scan_params["ExclusiveStartKey"] = decoded_token
                except Exception as e:
                    logger.error(f"Invalid nextToken: {e}")
                    return ErrorResponse.build("Invalid nextToken", 400)
            
            if filter_expression:
                from boto3.dynamodb.conditions import Attr
                fe = Attr("EntityType").eq("DEVICE")
                if device_type:
                    fe = fe & Attr("DeviceType").eq(device_type)
                if status:
                    fe = fe & Attr("Status").eq(status)
                scan_params["FilterExpression"] = fe
                response = table.scan(**scan_params)
            else:
                scan_params["FilterExpression"] = "EntityType = :et"
                scan_params["ExpressionAttributeValues"] = {":et": "DEVICE"}
                response = table.scan(**scan_params)

            items = response.get("Items", [])
            for item in items:
                # Import encryption helpers
                from shared.encryption_utils import prepare_item_for_response
                # Apply encryption/decryption based on decrypt parameter
                item = prepare_item_for_response(item, "DEVICE", decrypt=should_decrypt)
                device_id = item.get("DeviceId")
                if device_id:
                    # Fetch repair history
                    try:
                        repair_response = table.query(
                            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                            ExpressionAttributeValues={
                                ":pk": f"DEVICE#{device_id}",
                                ":sk": "REPAIR#"
                            }
                        )
                        repair_items = [simplify(r) for r in repair_response.get("Items", [])]
                        logger.info(f"***** repair_items: {repair_items}")
                        item["RepairHistory"] = repair_items
                    except Exception as e:
                        logger.error(f"Error fetching repair history for {device_id}: {str(e)}")
                        item["RepairHistory"] = []
                    
                    # Fetch linked SIM data
                    try:
                        sim_response = table.query(
                            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                            ExpressionAttributeValues={
                                ":pk": f"DEVICE#{device_id}",
                                ":sk": "SIM_ASSOC#"
                            }
                        )
                        sim_items = sim_response.get("Items", [])
                        if sim_items:
                            sim_assoc = sim_items[0]
                            sim_id = sim_assoc.get("SIMId")
                            if sim_id:
                                # Fetch full SIM details from simcards table
                                success, sim_data, error_msg = fetch_sim_details(sim_id, should_decrypt=should_decrypt)
                                if success:
                                    item["LinkedSIM"] = {
                                        "simId": sim_id,
                                        "linkedDate": sim_assoc.get("CreatedDate"),
                                        "linkStatus": sim_assoc.get("Status"),
                                        "simDetails": sim_data
                                    }
                                else:
                                    logger.warning(f"Failed to fetch SIM details for {sim_id}: {error_msg}")
                                    item["LinkedSIM"] = None
                            else:
                                item["LinkedSIM"] = None
                        else:
                            # Fallback to existing field if present in META
                            item["LinkedSIM"] = item.get("LinkedSIM")
                    except Exception as e:
                        logger.error(f"Error fetching linked SIM for {device_id}: {str(e)}")
                        item["LinkedSIM"] = None
            
            # Prepare pagination response
            result = {
                "deviceCount": len(items),
                "devices": transform_items_to_json(items, should_decrypt=should_decrypt),
                "limit": limit
            }
            
            # Add nextToken if there are more results
            if "LastEvaluatedKey" in response:
                import base64
                token = base64.b64encode(json.dumps(response["LastEvaluatedKey"]).encode('utf-8')).decode('utf-8')
                result["nextToken"] = token
                result["hasMore"] = True
            else:
                result["hasMore"] = False
            
            logger.info(f"Found {len(items)} device(s), hasMore: {result['hasMore']}")
            return SuccessResponse.build(result)
        except Exception as e:
            logger.error(f"DynamoDB scan error: {str(e)}")
            return ErrorResponse.build(f"DynamoDB scan error: {str(e)}", 500)

    elif method == "PUT":
        # Check if this is a PUT /installs/{installId} request
        if path_parameters.get("installId") and "/installs" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Updating installation: {install_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Validate installation exists
            try:
                install_response = table.get_item(
                    Key={"PK": f"INSTALL#{install_id}", "SK": "META"}
                )
                if "Item" not in install_response:
                    return ErrorResponse.build(f"Installation {install_id} not found", 404)
                
                existing_install = install_response["Item"]
            except Exception as e:
                logger.error(f"Error checking installation existence: {str(e)}")
                return ErrorResponse.build(f"Error validating installation: {str(e)}", 500)
            
            # Fields that can be updated
            updatable_fields = {
                "Status": "status",
                "PrimaryDevice": "primaryDevice", 
                "WarrantyDate": "warrantyDate",
                "InstallationDate": "installationDate",
                "CustomerId": "customerId",
                "TemplateId": "templateId"
            }
            
            # Track changes
            changes = {}
            updated_fields = {}
            
            for db_field, request_field in updatable_fields.items():
                if request_field in body:
                    new_value = body[request_field]
                    old_value = existing_install.get(db_field)
                    
                    # Only update if value changed
                    if new_value != old_value:
                        updated_fields[db_field] = new_value
                        changes[db_field] = {
                            "oldValue": old_value,
                            "newValue": new_value
                        }
            
            if not updated_fields:
                return ErrorResponse.build("No valid fields to update", 400)
            
            # Validate status if being updated
            if "Status" in updated_fields and updated_fields["Status"] not in ["active", "inactive"]:
                return ErrorResponse.build("Status must be 'active' or 'inactive'", 400)
            
            # Validate primaryDevice if being updated
            if "PrimaryDevice" in updated_fields and updated_fields["PrimaryDevice"] not in ["water", "chlorine", "none"]:
                return ErrorResponse.build("PrimaryDevice must be 'water', 'chlorine', or 'none'", 400)
            
            # Update the installation
            timestamp = datetime.utcnow().isoformat() + "Z"
            updated_fields["UpdatedDate"] = timestamp
            updated_fields["UpdatedBy"] = body.get("updatedBy", "system")
            
            # Build update expression with attribute name aliases for reserved keywords
            update_expr_parts = []
            expr_attr_values = {}
            expr_attr_names = {}
            
            # Reserved keywords in DynamoDB that need aliases
            reserved_keywords = {"Status"}
            
            for field, value in updated_fields.items():
                if field in reserved_keywords:
                    # Use attribute name alias for reserved keywords
                    alias = f"#{field}"
                    expr_attr_names[alias] = field
                    update_expr_parts.append(f"{alias} = :{field}")
                else:
                    update_expr_parts.append(f"{field} = :{field}")
                expr_attr_values[f":{field}"] = value
            
            # Add change history entry
            change_entry = {
                "timestamp": timestamp,
                "updatedBy": updated_fields["UpdatedBy"],
                "changes": changes,
                "ipAddress": get_client_ip(event)
            }
            
            update_expr_parts.append("changeHistory = list_append(if_not_exists(changeHistory, :empty_list), :change)")
            expr_attr_values[":empty_list"] = []
            expr_attr_values[":change"] = [change_entry]
            
            update_expression = "SET " + ", ".join(update_expr_parts)
            
            try:
                update_params = {
                    "Key": {"PK": f"INSTALL#{install_id}", "SK": "META"},
                    "UpdateExpression": update_expression,
                    "ExpressionAttributeValues": expr_attr_values,
                    "ReturnValues": "ALL_NEW"
                }
                
                # Only add ExpressionAttributeNames if we have reserved keywords
                if expr_attr_names:
                    update_params["ExpressionAttributeNames"] = expr_attr_names
                
                response = table.update_item(**update_params)
                
                updated_install = simplify(response["Attributes"])
                logger.info(f"Updated installation {install_id}: {list(changes.keys())}")
                
                # Fetch and add region names to response
                region_names = fetch_region_names(
                    state_id=updated_install.get("StateId"),
                    district_id=updated_install.get("DistrictId"),
                    mandal_id=updated_install.get("MandalId"),
                    village_id=updated_install.get("VillageId"),
                    habitation_id=updated_install.get("HabitationId")
                )
                updated_install.update(region_names)
                
                return SuccessResponse.build({
                    "message": "Installation updated successfully",
                    "installation": updated_install,
                    "changes": changes
                }, 200)
            except Exception as e:
                logger.error(f"Error updating installation: {str(e)}")
                return ErrorResponse.build(f"Error updating installation: {str(e)}", 500)
        
        # Default PUT handler for device entities
        try:
            item = json.loads(event.get("body", "{}"))
            if not isinstance(item, dict):
                raise ValueError("PUT body must be a dict")
            item = convert_floats_to_decimal(item)
        except Exception as e:
            logger.error(f"Failed to parse body: {e}")
            return ErrorResponse.build(f"Malformed JSON body: {e}", 400)

        entity_type = item.get("EntityType")
        if not entity_type:
            return ErrorResponse.build("EntityType is required", 400)
        
        device_id = item.get("DeviceId")
        if not device_id:
            return ErrorResponse.build("DeviceId is required", 400)
        
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return ErrorResponse.build(f"Unknown EntityType: {entity_type}", 400)

        # Derive PK and SK
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for update", 400)

        # Fetch existing item to track changes
        existing_item = None
        try:
            response = table.get_item(Key={"PK": pk, "SK": sk})
            existing_item = response.get("Item")
            if not existing_item:
                return ErrorResponse.build(f"Item not found: PK={pk}, SK={sk}", 404)
        except Exception as e:
            logger.error(f"Error fetching existing item: {str(e)}")
            return ErrorResponse.build(f"Error fetching item: {str(e)}", 500)

        # Set UpdatedDate and UpdatedBy
        timestamp = datetime.utcnow().isoformat() + "Z"
        item["UpdatedDate"] = timestamp
        if item.get("CreatedBy") and not item.get("UpdatedBy"):
            item["UpdatedBy"] = item["CreatedBy"]

        # Track changes for device records only
        changes = {}
        trackable_fields = ["DeviceName", "DeviceType", "SerialNumber", "Status", "Location"]
        
        if entity_type == "DEVICE":
            for field in trackable_fields:
                old_value = existing_item.get(field)
                new_value = item.get(field)
                # Only track if field is being updated and value changed
                if field in item and old_value != new_value:
                    changes[field] = {
                        "from": old_value,
                        "to": new_value
                    }

        # Remove PK and SK from update fields
        update_fields = {k: v for k, v in item.items() if k not in ["PK", "SK"]}

        # Apply encryption to sensitive fields before storing
        from shared.encryption_utils import prepare_item_for_storage
        update_fields = prepare_item_for_storage(update_fields, entity_type)

        # Build UpdateExpression and ExpressionAttributeValues
        reserved_keywords = {"Status", "Location"}
        update_expr_parts = []
        expr_attr_names = {}
        expr_attr_vals = {}

        for k, v in update_fields.items():
            if k in reserved_keywords:
                update_expr_parts.append(f"#attr_{k} = :{k}")
                expr_attr_names[f"#attr_{k}"] = k
            else:
                update_expr_parts.append(f"{k} = :{k}")
            expr_attr_vals[f":{k}"] = v

        # Add changeHistory if there are changes
        if changes:
            history_entry = {
                "timestamp": timestamp,
                "action": "UPDATE",
                "changes": changes,
                "updatedBy": item.get("UpdatedBy", "system")
            }
            
            # Append to changeHistory array
            update_expr_parts.append("changeHistory = list_append(if_not_exists(changeHistory, :empty_list), :new_history)")
            expr_attr_vals[":empty_list"] = []
            expr_attr_vals[":new_history"] = [history_entry]
            
            logger.info(f"Recording device changes: {changes}")

        update_expr = "SET " + ", ".join(update_expr_parts)

        try:
            result = table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_attr_vals,
                ExpressionAttributeNames=expr_attr_names if expr_attr_names else None,
                ReturnValues="ALL_NEW"
            )
            updated_item = result.get("Attributes", {})
            return SuccessResponse.build({"updated": simplify(updated_item)})
        except Exception as e:
            logger.error(f"Update error: {str(e)}")
            return ErrorResponse.build(f"Update error: {str(e)}", 500)
        
    elif method == "DELETE":
        # Get query parameters - all values come from query string
        params = event.get("queryStringParameters") or {}
        entity_type = params.get("EntityType")
        device_id = params.get("DeviceId")
        
        if not entity_type:
            return ErrorResponse.build("EntityType is required for delete", 400)
        
        if not device_id:
            return ErrorResponse.build("DeviceId is required for delete", 400)

        # Build item dict for PK/SK derivation based on EntityType
        item = {
            "EntityType": entity_type,
            "DeviceId": device_id
        }
        
        # Add entity-specific required fields for SK construction
        # CONFIG requires: ConfigVersion, CreatedDate
        # REPAIR requires: RepairId, CreatedDate
        # INSTALL requires: InstallId, CreatedDate
        # RUNTIME requires: EventDate
        # SIM_ASSOC requires: SIMId
        # DEVICE only needs EntityType and DeviceId
        
        if entity_type == "CONFIG":
            config_version = params.get("ConfigVersion")
            created_date = params.get("CreatedDate")
            if not config_version or not created_date:
                return ErrorResponse.build("ConfigVersion and CreatedDate are required for CONFIG delete", 400)
            item["ConfigVersion"] = config_version
            item["CreatedDate"] = created_date
        elif entity_type == "REPAIR":
            repair_id = params.get("RepairId")
            created_date = params.get("CreatedDate")
            if not repair_id or not created_date:
                return ErrorResponse.build("RepairId and CreatedDate are required for REPAIR delete", 400)
            item["RepairId"] = repair_id
            item["CreatedDate"] = created_date
        elif entity_type == "INSTALL":
            install_id = params.get("InstallId")
            created_date = params.get("CreatedDate")
            if not install_id or not created_date:
                return ErrorResponse.build("InstallId and CreatedDate are required for INSTALL delete", 400)
            item["InstallId"] = install_id
            item["CreatedDate"] = created_date
        elif entity_type == "RUNTIME":
            event_date = params.get("EventDate")
            if not event_date:
                return ErrorResponse.build("EventDate is required for RUNTIME delete", 400)
            item["EventDate"] = event_date
        elif entity_type == "SIM_ASSOC":
            sim_id = params.get("SIMId")
            if not sim_id:
                return ErrorResponse.build("SIMId is required for SIM_ASSOC delete", 400)
            item["SIMId"] = sim_id
        # DEVICE doesn't need additional fields - just EntityType and DeviceId
        
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for delete", 400)
        
        logger.info(f"Attempting to delete {entity_type} with PK={pk}, SK={sk}")
        
        try:
            table.delete_item(
                Key={
                    "PK": pk,
                    "SK": sk
                }
            )
            logger.info(f"Successfully deleted {entity_type} with PK={pk}, SK={sk}")
            return SuccessResponse.build({"deleted": {"PK": pk, "SK": sk, "EntityType": entity_type}})
        except Exception as e:
            logger.error(f"Delete error for {entity_type}: {str(e)}")
            return ErrorResponse.build(f"Delete error: {str(e)}", 500)

    return ErrorResponse.build("Method not allowed", 405)

def convert_floats_to_decimal(obj):
    """
    Recursively convert all float values in a dict or list to decimal.Decimal.
    """
    if isinstance(obj, float):
        logger.debug(f"Converting float to Decimal: {obj}")
        return decimal.Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(v) for v in obj]
    else:
        return obj

def simplify(item):
    """
    Recursively convert DynamoDB item values to native Python types,
    including Decimal to int/float for JSON serialization.
    """
    def simplify_value(v):
        if isinstance(v, Decimal):
            return int(v) if v == int(v) else float(v)
        if isinstance(v, dict):
            return {k: simplify_value(nv) for k, nv in v.items()}
        if isinstance(v, list):
            return [simplify_value(x) for x in v]
        return v

    return {k: simplify_value(v) for k, v in item.items()}

def transform_items_to_json(items, should_decrypt=True):
    """Transform a list of DynamoDB items to a list of JSON objects for devices."""
    if not items:
        return []

    # Build a lookup for InstallId by DeviceId
    install_lookup = {}
    for item in items:
        item = simplify(item)
        if item.get("EntityType") == "INSTALL" and item.get("DeviceId") and item.get("InstallId"):
            install_lookup[item["DeviceId"]] = item["InstallId"]

    results = []
    for item in items:
        from shared.encryption_utils import prepare_item_for_response
        item = prepare_item_for_response(item, "DEVICE", decrypt=should_decrypt)
        item = simplify(item)
        if not item or not isinstance(item, dict):
            continue

        entity_type = item.get("EntityType")
        if not entity_type:
            continue

        result = {
            "id": item.get("PK").split("#")[-1] if "#" in item.get("PK", "") else item.get("PK"),
            "type": entity_type,
            "deviceId": item.get("DeviceId"),
            "deviceName": item.get("DeviceName"),
            "deviceType": item.get("DeviceType"),
            "serialNumber": item.get("SerialNumber"),
            "status": item.get("Status"),
            "currentLocation": item.get("Location"),
            "createdAt": item.get("CreatedDate"),
            "updatedAt": item.get("UpdatedDate"),
            "RepairHistory": item.get("RepairHistory"),
            "InstallId": install_lookup.get(item.get("DeviceId")),  # <-- Add InstallId here
            "LinkedSIM": item.get("LinkedSIM"),  # <-- Add LinkedSIM here
            "LinkedInstallationId": item.get("LinkedInstallationId"),  # <-- Add LinkedInstallationId here
            "PK": item.get("PK"),
            "SK": item.get("SK")
        }
        if entity_type == "CONFIG":
            result["configVersion"] = item.get("ConfigVersion")
            result["configData"] = item.get("ConfigData")
            result["appliedBy"] = item.get("AppliedBy")
        elif entity_type == "REPAIR":
            result["repairId"] = item.get("RepairId")
            result["description"] = item.get("Description")
            result["cost"] = item.get("Cost")
            result["technician"] = item.get("Technician")
        elif entity_type == "INSTALL":
            result["installId"] = item.get("InstallId")
            result["installer"] = item.get("Installer")
            result["notes"] = item.get("Notes")
            result["warranty"] = item.get("Warranty")
        elif entity_type == "RUNTIME":
            result["metrics"] = item.get("Metrics")
            result["events"] = item.get("Events")
            result["eventDate"] = item.get("EventDate")
            result["ttl"] = item.get("ttl")
        elif entity_type == "SIM":
            result["simId"] = item.get("SIMId")
            result["mobileNumber"] = item.get("MobileNumber")
            result["provider"] = item.get("Provider")
            result["plan"] = item.get("Plan")
            result["dataUsage"] = item.get("DataUsage")
            result["assignedDeviceId"] = item.get("AssignedDeviceId")
        elif entity_type == "SIM_ASSOC":
            result["simId"] = item.get("SIMId")
            result["provider"] = item.get("Provider")

        results.append(result)

    return results

def derive_pk_sk(item):
    """
    Derive PK and SK values based on EntityType and other fields.
    """
    entity_type = item.get("EntityType")
    if entity_type == "DEVICE":
        pk = f'DEVICE#{item.get("DeviceId")}'
        sk = "META"
    elif entity_type == "CONFIG":
        pk = f'DEVICE#{item.get("DeviceId")}'
        version = item.get("ConfigVersion", "V1.0")
        created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
        sk = f'CONFIG#{version}#{created}'
    elif entity_type == "REPAIR":
        pk = f'DEVICE#{item.get("DeviceId")}'
        repair_id = item.get("RepairId", "REP")
        created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
        sk = f'REPAIR#{repair_id}#{created[:10]}'
    elif entity_type == "INSTALL":
        pk = f'DEVICE#{item.get("DeviceId")}'
        install_id = item.get("InstallId", "INS")
        created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
        sk = f'INSTALL#{install_id}#{created[:10]}'
    elif entity_type == "RUNTIME":
        pk = f'DEVICE#{item.get("DeviceId")}'
        event_date = item.get("EventDate", datetime.utcnow().isoformat() + "Z")
        sk = f'RUNTIME#{event_date}'
    elif entity_type == "SIM":
        pk = f'SIM#{item.get("SIMId")}'
        sk = "META"
    elif entity_type == "SIM_ASSOC":
        pk = f'DEVICE#{item.get("DeviceId")}'
        sim_id = item.get("SIMId", "SIM")
        sk = f'SIM_ASSOC#{sim_id}'
    else:
        pk = None
        sk = None
    return pk, sk

def validate_sim_available(sim_id):
    """
    Validate that a SIM card exists, is active, and not already linked to another device.
    Returns (is_valid, error_message, sim_data)
    """
    try:
        # Fetch SIM card from simcards table
        response = simcards_table.get_item(
            Key={
                "PK": f"SIMCARD#{sim_id}",
                "SK": "ENTITY#SIMCARD"
            }
        )
        
        if "Item" not in response:
            return False, f"SIM card {sim_id} not found", None
        
        sim_data = response["Item"]
        
        # Check if SIM is active
        if sim_data.get("status") != "active":
            return False, f"SIM card {sim_id} is not active (status: {sim_data.get('status')})", None
        
        # Check if SIM is already linked to another device
        linked_device = sim_data.get("linkedDeviceId")
        if linked_device:
            return False, f"SIM card {sim_id} is already linked to device {linked_device}", None
        
        return True, None, sim_data
    
    except ClientError as e:
        logger.error(f"Error validating SIM {sim_id}: {str(e)}")
        return False, f"Database error validating SIM: {e.response['Error']['Message']}", None
    except Exception as e:
        logger.error(f"Unexpected error validating SIM {sim_id}: {str(e)}")
        return False, f"Unexpected error: {str(e)}", None

def execute_sim_link_transaction(device_id, sim_id, sim_provider, performed_by, ip_address, sim_data=None, device_name=None):
    """
    Execute atomic transaction to link SIM to device across both tables.
    Creates SIM_ASSOC in devices table and updates linkedDeviceId in simcards table.
    Also adds SIM history to device record for persistent audit trail.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Extract SIM details for history
    sim_mobile = sim_data.get("mobileNumber", "") if sim_data else ""
    sim_card_number = sim_data.get("simCardNumber", "") if sim_data else ""
    
    try:
        # Prepare transaction items
        transact_items = [
            {
                # Create SIM_ASSOC in devices table
                "Put": {
                    "TableName": TABLE_NAME,
                    "Item": {
                        "PK": {"S": f"DEVICE#{device_id}"},
                        "SK": {"S": f"SIM_ASSOC#{sim_id}"},
                        "DeviceId": {"S": device_id},
                        "SIMId": {"S": sim_id},
                        "Provider": {"S": sim_provider},
                        "Status": {"S": "linked"},
                        "EntityType": {"S": "SIM_ASSOC"},
                        "CreatedDate": {"S": timestamp},
                        "UpdatedDate": {"S": timestamp}
                    }
                }
            },
            {
                # Update SIM card in simcards table with enhanced history
                "Update": {
                    "TableName": SIMCARDS_TABLE_NAME,
                    "Key": {
                        "PK": {"S": f"SIMCARD#{sim_id}"},
                        "SK": {"S": "ENTITY#SIMCARD"}
                    },
                    "UpdateExpression": "SET linkedDeviceId = :deviceId, updatedAt = :timestamp, changeHistory = list_append(if_not_exists(changeHistory, :empty_list), :new_history)",
                    "ExpressionAttributeValues": {
                        ":deviceId": {"S": device_id},
                        ":timestamp": {"S": timestamp},
                        ":empty_list": {"L": []},
                        ":new_history": {
                            "L": [
                                {
                                    "M": {
                                        "timestamp": {"S": timestamp},
                                        "action": {"S": "linked"},
                                        "deviceId": {"S": device_id},
                                        "deviceName": {"S": device_name or ""},
                                        "simId": {"S": sim_id},
                                        "mobileNumber": {"S": sim_mobile},
                                        "simCardNumber": {"S": sim_card_number},
                                        "performedBy": {"S": performed_by},
                                        "ipAddress": {"S": ip_address}
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            {
                # Add SIM history to device record for persistent audit trail
                "Update": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": {"S": f"DEVICE#{device_id}"},
                        "SK": {"S": "META"}
                    },
                    "UpdateExpression": "SET SIMHistory = list_append(if_not_exists(SIMHistory, :empty_list), :sim_history)",
                    "ExpressionAttributeValues": {
                        ":empty_list": {"L": []},
                        ":sim_history": {
                            "L": [
                                {
                                    "M": {
                                        "timestamp": {"S": timestamp},
                                        "action": {"S": "linked"},
                                        "simId": {"S": sim_id},
                                        "mobileNumber": {"S": sim_mobile},
                                        "simCardNumber": {"S": sim_card_number},
                                        "provider": {"S": sim_provider},
                                        "performedBy": {"S": performed_by},
                                        "ipAddress": {"S": ip_address}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        ]
        
        # Execute transaction
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully linked SIM {sim_id} to device {device_id}")
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            logger.error(f"Transaction cancelled for linking SIM {sim_id} to device {device_id}: {str(e)}")
            return False, "Transaction failed. One or more operations could not be completed."
        else:
            logger.error(f"Error executing link transaction: {str(e)}")
            return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in link transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"

def execute_sim_unlink_transaction(device_id, sim_id, performed_by, ip_address, sim_data=None, device_name=None):
    """
    Execute atomic transaction to unlink SIM from device across both tables.
    Deletes SIM_ASSOC from devices table and clears linkedDeviceId in simcards table.
    Also adds unlink event to device SIMHistory for persistent audit trail.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Extract SIM details for history
    sim_mobile = sim_data.get("mobileNumber", "") if sim_data else ""
    sim_card_number = sim_data.get("simCardNumber", "") if sim_data else ""
    sim_provider = sim_data.get("provider", "") if sim_data else ""
    
    try:
        # Prepare transaction items
        transact_items = [
            {
                # Delete SIM_ASSOC from devices table
                "Delete": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": {"S": f"DEVICE#{device_id}"},
                        "SK": {"S": f"SIM_ASSOC#{sim_id}"}
                    }
                }
            },
            {
                # Update SIM card in simcards table with enhanced history
                "Update": {
                    "TableName": SIMCARDS_TABLE_NAME,
                    "Key": {
                        "PK": {"S": f"SIMCARD#{sim_id}"},
                        "SK": {"S": "ENTITY#SIMCARD"}
                    },
                    "UpdateExpression": "REMOVE linkedDeviceId SET updatedAt = :timestamp, changeHistory = list_append(if_not_exists(changeHistory, :empty_list), :new_history)",
                    "ExpressionAttributeValues": {
                        ":timestamp": {"S": timestamp},
                        ":empty_list": {"L": []},
                        ":new_history": {
                            "L": [
                                {
                                    "M": {
                                        "timestamp": {"S": timestamp},
                                        "action": {"S": "unlinked"},
                                        "deviceId": {"S": device_id},
                                        "deviceName": {"S": device_name or ""},
                                        "simId": {"S": sim_id},
                                        "mobileNumber": {"S": sim_mobile},
                                        "simCardNumber": {"S": sim_card_number},
                                        "performedBy": {"S": performed_by},
                                        "ipAddress": {"S": ip_address}
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            {
                # Add unlink event to device SIMHistory
                "Update": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": {"S": f"DEVICE#{device_id}"},
                        "SK": {"S": "META"}
                    },
                    "UpdateExpression": "SET SIMHistory = list_append(if_not_exists(SIMHistory, :empty_list), :sim_history)",
                    "ExpressionAttributeValues": {
                        ":empty_list": {"L": []},
                        ":sim_history": {
                            "L": [
                                {
                                    "M": {
                                        "timestamp": {"S": timestamp},
                                        "action": {"S": "unlinked"},
                                        "simId": {"S": sim_id},
                                        "mobileNumber": {"S": sim_mobile},
                                        "simCardNumber": {"S": sim_card_number},
                                        "provider": {"S": sim_provider},
                                        "performedBy": {"S": performed_by},
                                        "ipAddress": {"S": ip_address}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        ]
        
        # Execute transaction
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully unlinked SIM {sim_id} from device {device_id}")
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            logger.error(f"Transaction cancelled for unlinking SIM {sim_id} from device {device_id}: {str(e)}")
            return False, "Transaction failed. One or more operations could not be completed."
        else:
            logger.error(f"Error executing unlink transaction: {str(e)}")
            return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in unlink transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"

def get_client_ip(event):
    """
    Extract client IP address from event.
    """
    # Try HTTP API 2.0 format
    ip = event.get("requestContext", {}).get("http", {}).get("sourceIp")
    if ip:
        return ip
    
    # Try REST API format
    ip = event.get("requestContext", {}).get("identity", {}).get("sourceIp")
    if ip:
        return ip
    
    # Fallback
    return "unknown"

def fetch_sim_details(sim_id, should_decrypt=False):
    """
    Fetch full SIM card details from simcards table.
    
    Args:
        sim_id: The SIM card ID
        should_decrypt: If True, decrypt sensitive SIM fields. If False (default), return encrypted data.
    
    Returns:
        (success, sim_data, error_message)
    """
    try:
        response = simcards_table.get_item(
            Key={
                "PK": f"SIMCARD#{sim_id}",
                "SK": "ENTITY#SIMCARD"
            }
        )
        
        if "Item" not in response:
            return False, None, f"SIM card {sim_id} not found"
        
        sim_data = response["Item"]
        
        # Apply encryption/decryption based on decrypt parameter
        from shared.encryption_utils import prepare_item_for_response
        sim_data = prepare_item_for_response(sim_data, "SIM", decrypt=should_decrypt)
        
        return True, simplify(sim_data), None
    
    except ClientError as e:
        logger.error(f"Error fetching SIM {sim_id}: {str(e)}")
        return False, None, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error fetching SIM {sim_id}: {str(e)}")
        return False, None, f"Unexpected error: {str(e)}"


# ============================================================================
# INSTALL-DEVICE LINKING FUNCTIONS
# ============================================================================

def validate_install_exists(install_id):
    """Validate that an install record exists."""
    try:
        response = table.get_item(
            Key={"PK": f"INSTALL#{install_id}", "SK": "META"}
        )
        if "Item" not in response:
            return False, f"Install {install_id} not found"
        return True, None
    except Exception as e:
        logger.error(f"Error checking install existence: {str(e)}")
        return False, f"Error validating install: {str(e)}"


def validate_device_exists(device_id):
    """Validate that a device record exists."""
    try:
        response = table.get_item(
            Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
        )
        if "Item" not in response:
            return False, f"Device {device_id} not found"
        return True, None
    except Exception as e:
        logger.error(f"Error checking device existence: {str(e)}")
        return False, f"Error validating device: {str(e)}"


def check_device_install_link(device_id, install_id):
    """Check if a device is already linked to a specific install."""
    try:
        response = table.get_item(
            Key={
                "PK": f"DEVICE#{device_id}",
                "SK": f"INSTALL_ASSOC#{install_id}"
            }
        )
        return "Item" in response
    except Exception as e:
        logger.error(f"Error checking device-install link: {str(e)}")
        return False


def get_device_installation_link(device_id):
    """
    Check if a device is already linked to any installation.
    Returns (is_linked, install_id) where:
    - is_linked: True if device is linked to an installation, False otherwise
    - install_id: The installation ID if linked, None otherwise
    """
    try:
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"DEVICE#{device_id}",
                ":sk_prefix": "INSTALL_ASSOC#"
            },
            Limit=1  # We only need to know if at least one link exists
        )
        
        if response.get("Items"):
            # Extract install_id from SK (format: INSTALL_ASSOC#<install_id>)
            sk = response["Items"][0]["SK"]
            install_id = sk.replace("INSTALL_ASSOC#", "")
            return True, install_id
        
        return False, None
    except Exception as e:
        logger.error(f"Error checking device installation link: {str(e)}")
        return False, None


def validate_region_id_exists(region_type, region_id):
    """
    Validate that a region ID exists in v_regions table.
    region_type: "STATE", "DISTRICT", "MANDAL", "VILLAGE", "HABITATION"
    Returns (success, error_message)
    """
    try:
        regions_table = dynamodb.Table("v_regions_dev")
        response = regions_table.get_item(
            Key={"PK": f"{region_type}#{region_id}", "SK": "META"}
        )
        if "Item" not in response:
            return False, f"{region_type} {region_id} not found"
        return True, None
    except Exception as e:
        logger.error(f"Error validating {region_type} {region_id}: {str(e)}")
        return False, f"Error validating {region_type}: {str(e)}"


def validate_customer_id_exists(customer_id):
    """
    Validate that a customer ID exists in v_customers table.
    Returns (success, error_message, is_permission_error)
    If permission error, returns (None, message, True) to allow graceful degradation
    """
    try:
        customers_table = dynamodb.Table("v_customers_dev")
        response = customers_table.get_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": "ENTITY#CUSTOMER"}
        )
        if "Item" not in response:
            return False, f"Customer {customer_id} not found", False
        return True, None, False
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "AccessDeniedException":
            logger.warning(f"Permission denied validating customer {customer_id} - allowing anyway: {str(e)}")
            return None, f"Customer validation skipped (permission denied)", True
        else:
            logger.error(f"Error validating customer {customer_id}: {str(e)}")
            return False, f"Error validating customer: {str(e)}", False
    except Exception as e:
        logger.error(f"Unexpected error validating customer {customer_id}: {str(e)}")
        return False, f"Error validating customer: {str(e)}", False


def validate_template_id_exists(template_id):
    """
    Validate that a template ID exists.
    For now, we'll accept any non-empty template ID (can be enhanced later).
    Returns (success, error_message)
    """
    if not template_id or not isinstance(template_id, str) or len(template_id.strip()) == 0:
        return False, "Template ID must be a non-empty string"
    return True, None


def prepare_item_for_storage(item, entity_type):
    """
    Encrypt sensitive fields before storing in DynamoDB
    Args:
        item: Dictionary of data to store
        entity_type: Type of entity (DEVICE, SIM, CUSTOMER, etc.)
    Returns:
        Item with encrypted fields
    """
    fields_to_encrypt = get_fields_to_encrypt(entity_type)
    if not fields_to_encrypt:
        return item
    
    result = item.copy()
    for field in fields_to_encrypt:
        if field in result and result[field]:
            result[field] = encryption.encrypt_field(result[field], field)
    
    logger.debug(f"Prepared {entity_type} for storage with {len(fields_to_encrypt)} encrypted fields")
    return result


def prepare_item_for_response(item, entity_type):
    """
    Decrypt sensitive fields after retrieving from DynamoDB
    Args:
        item: Dictionary of data retrieved
        entity_type: Type of entity (DEVICE, SIM, CUSTOMER, etc.)
    Returns:
        Item with decrypted fields
    """
    fields_to_decrypt = get_fields_to_decrypt(entity_type)
    if not fields_to_decrypt:
        return item
    
    result = item.copy()
    for field in fields_to_decrypt:
        if field in result and result[field]:
            result[field] = encryption.decrypt_field(result[field], field)
    
    logger.debug(f"Prepared {entity_type} for response with {len(fields_to_decrypt)} decrypted fields")
    return result


def create_install_device_history(install_id, device_id, action, performed_by, ip_address, reason=None):
    """Create a history record for install-device link/unlink operations."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    history_item = {
        "PK": f"INSTALL#{install_id}",
        "SK": f"DEVICE_HISTORY#{timestamp}#{device_id}",
        "EntityType": "INSTALL_DEVICE_HISTORY",
        "InstallId": install_id,
        "DeviceId": device_id,
        "Action": action,  # "LINKED" or "UNLINKED"
        "PerformedBy": performed_by,
        "PerformedAt": timestamp,
        "IPAddress": ip_address
    }
    
    if reason:
        history_item["Reason"] = reason
    
    try:
        table.put_item(Item=history_item)
        logger.info(f"Created history record for {action}: Install {install_id} <-> Device {device_id}")
        return True, None
    except Exception as e:
        logger.error(f"Error creating history record: {str(e)}")
        return False, f"Error creating history: {str(e)}"


def execute_install_device_link_transaction(install_id, device_id, performed_by, ip_address, reason=None):
    """
    Execute atomic transaction to link a device to an install.
    Creates bidirectional associations, updates device's META record with LinkedInstallationId,
    and adds installation history to device record.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Prepare transaction items
    transact_items = [
        {
            # Create association: INSTALL -> DEVICE
            "Put": {
                "TableName": TABLE_NAME,
                "Item": {
                    "PK": {"S": f"INSTALL#{install_id}"},
                    "SK": {"S": f"DEVICE_ASSOC#{device_id}"},
                    "EntityType": {"S": "INSTALL_DEVICE_ASSOC"},
                    "InstallId": {"S": install_id},
                    "DeviceId": {"S": device_id},
                    "Status": {"S": "active"},
                    "LinkedDate": {"S": timestamp},
                    "LinkedBy": {"S": performed_by},
                    "CreatedDate": {"S": timestamp},
                    "UpdatedDate": {"S": timestamp}
                },
                "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)"
            }
        },
        {
            # Create association: DEVICE -> INSTALL
            "Put": {
                "TableName": TABLE_NAME,
                "Item": {
                    "PK": {"S": f"DEVICE#{device_id}"},
                    "SK": {"S": f"INSTALL_ASSOC#{install_id}"},
                    "EntityType": {"S": "DEVICE_INSTALL_ASSOC"},
                    "DeviceId": {"S": device_id},
                    "InstallId": {"S": install_id},
                    "Status": {"S": "active"},
                    "LinkedDate": {"S": timestamp},
                    "LinkedBy": {"S": performed_by},
                    "CreatedDate": {"S": timestamp},
                    "UpdatedDate": {"S": timestamp}
                },
                "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)"
            }
        },
        {
            # Update device META record to store LinkedInstallationId and add installation history
            "Update": {
                "TableName": TABLE_NAME,
                "Key": {
                    "PK": {"S": f"DEVICE#{device_id}"},
                    "SK": {"S": "META"}
                },
                "UpdateExpression": "SET LinkedInstallationId = :installId, InstallationHistory = list_append(if_not_exists(InstallationHistory, :empty_list), :install_history)",
                "ExpressionAttributeValues": {
                    ":installId": {"S": install_id},
                    ":empty_list": {"L": []},
                    ":install_history": {
                        "L": [
                            {
                                "M": {
                                    "timestamp": {"S": timestamp},
                                    "action": {"S": "linked"},
                                    "installationId": {"S": install_id},
                                    "performedBy": {"S": performed_by},
                                    "ipAddress": {"S": ip_address},
                                    "reason": {"S": reason or ""}
                                }
                            }
                        ]
                    }
                },
                "ConditionExpression": "attribute_exists(PK) AND attribute_exists(SK)"
            }
        }
    ]
    
    try:
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully linked device {device_id} to install {install_id}")
        
        # Create history record (non-transactional, but logged)
        create_install_device_history(install_id, device_id, "LINKED", performed_by, ip_address, reason)
        
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            reasons = e.response.get('CancellationReasons', [])
            if any(r.get('Code') == 'ConditionalCheckFailed' for r in reasons):
                return False, f"Device {device_id} is already linked to install {install_id}"
            return False, f"Transaction failed: {str(reasons)}"
        logger.error(f"Transaction error: {str(e)}")
        return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"


def execute_install_device_unlink_transaction(install_id, device_id, performed_by, ip_address, reason=None):
    """
    Execute atomic transaction to unlink a device from an install.
    Deletes bidirectional associations, removes LinkedInstallationId from device META,
    and adds unlink history to device record.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Prepare transaction items
    transact_items = [
        {
            # Delete association: INSTALL -> DEVICE
            "Delete": {
                "TableName": TABLE_NAME,
                "Key": {
                    "PK": {"S": f"INSTALL#{install_id}"},
                    "SK": {"S": f"DEVICE_ASSOC#{device_id}"}
                },
                "ConditionExpression": "attribute_exists(PK) AND attribute_exists(SK)"
            }
        },
        {
            # Delete association: DEVICE -> INSTALL
            "Delete": {
                "TableName": TABLE_NAME,
                "Key": {
                    "PK": {"S": f"DEVICE#{device_id}"},
                    "SK": {"S": f"INSTALL_ASSOC#{install_id}"}
                },
                "ConditionExpression": "attribute_exists(PK) AND attribute_exists(SK)"
            }
        },
        {
            # Update device META record to remove LinkedInstallationId and add unlink history
            "Update": {
                "TableName": TABLE_NAME,
                "Key": {
                    "PK": {"S": f"DEVICE#{device_id}"},
                    "SK": {"S": "META"}
                },
                "UpdateExpression": "REMOVE LinkedInstallationId SET InstallationHistory = list_append(if_not_exists(InstallationHistory, :empty_list), :install_history)",
                "ExpressionAttributeValues": {
                    ":empty_list": {"L": []},
                    ":install_history": {
                        "L": [
                            {
                                "M": {
                                    "timestamp": {"S": timestamp},
                                    "action": {"S": "unlinked"},
                                    "installationId": {"S": install_id},
                                    "performedBy": {"S": performed_by},
                                    "ipAddress": {"S": ip_address},
                                    "reason": {"S": reason or ""}
                                }
                            }
                        ]
                    }
                },
                "ConditionExpression": "attribute_exists(PK) AND attribute_exists(SK)"
            }
        }
    ]
    
    try:
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully unlinked device {device_id} from install {install_id}")
        
        # Create history record
        create_install_device_history(install_id, device_id, "UNLINKED", performed_by, ip_address, reason)
        
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            reasons = e.response.get('CancellationReasons', [])
            if any(r.get('Code') == 'ConditionalCheckFailed' for r in reasons):
                return False, f"Device {device_id} is not linked to install {install_id}"
            return False, f"Transaction failed: {str(reasons)}"
        logger.error(f"Transaction error: {str(e)}")
        return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"


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
                "PK": {"S": f"CUSTOMER#{customer_id}"},
                "SK": {"S": f"ENTITY#CONTACT#{contact_id}"}
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
