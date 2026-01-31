import json
import os
import boto3
import logging
import re
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

class DeviceMeta(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    DeviceName: str
    DeviceType: str
    SerialNumber: str
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
    """Fetch region names from regions table
    
    Returns a dict with stateName, districtName, mandalName, villageName, habitationName
    """
    region_names = {}
    
    try:
        regions_table = dynamodb.Table(os.environ.get("REGIONS_TABLE", "v_regions_dev"))
        logger.info(f"fetch_region_names called with: state_id={state_id}, district_id={district_id}, mandal_id={mandal_id}, village_id={village_id}, habitation_id={habitation_id}")
        
        # For STATE: Try both with and without STATE# prefix
        if state_id:
            # Try original state_id first
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
        
        # For DISTRICT: Try to find with parent state
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
                logger.warning(f"District not found: STATE#{state_key}, DISTRICT#{district_key}")
        
        # For MANDAL: Try to find with parent district
        if mandal_id and district_id:
            district_key = district_id.replace("DIST-", "").replace("DISTRICT#", "")
            mandal_key = mandal_id.replace("MANDAL-", "").replace("MANDAL#", "")
            response = regions_table.get_item(
                Key={"PK": f"DISTRICT#{district_key}", "SK": f"MANDAL#{mandal_key}"}
            )
            if "Item" in response:
                region_names["mandalName"] = response["Item"].get("RegionName")
        
        # For VILLAGE: Try to find with parent mandal
        if village_id and mandal_id:
            mandal_key = mandal_id.replace("MANDAL-", "").replace("MANDAL#", "")
            village_key = village_id.replace("VILLAGE-", "").replace("VILLAGE#", "")
            response = regions_table.get_item(
                Key={"PK": f"MANDAL#{mandal_key}", "SK": f"VILLAGE#{village_key}"}
            )
            if "Item" in response:
                region_names["villageName"] = response["Item"].get("RegionName")
        
        # For HABITATION: Try to find with parent village
        if habitation_id and village_id:
            village_key = village_id.replace("VILLAGE-", "").replace("VILLAGE#", "")
            habitation_key = habitation_id.replace("HAB-", "").replace("HABITATION#", "")
            response = regions_table.get_item(
                Key={"PK": f"VILLAGE#{village_key}", "SK": f"HABITATION#{habitation_key}"}
            )
            if "Item" in response:
                region_names["habitationName"] = response["Item"].get("RegionName")
    
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
            required_fields = ["InstallationId", "StateId", "DistrictId", "MandalId", "VillageId", "HabitationId", "PrimaryDevice", "Status", "InstallationDate"]
            missing_fields = [field for field in required_fields if not body.get(field)]
            if missing_fields:
                return ErrorResponse.build(f"Missing required fields: {', '.join(missing_fields)}", 400)
            
            # Validate PrimaryDevice value
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
            
            # Create installation record
            try:
                installation_id = body.get("InstallationId")
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
            import uuid
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
        
        performed_by = body.get("performedBy", "system")
        reason = body.get("reason")
        ip_address = get_client_ip(event)
        
        # Validate install exists
        is_valid, error_msg = validate_install_exists(install_id)
        if not is_valid:
            return ErrorResponse.build(error_msg, 404)
        
        # Link each device
        results = []
        errors = []
        
        for device_id in device_ids:
            # Validate device format
            if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                errors.append({"deviceId": device_id, "error": "Invalid deviceId format"})
                continue
            
            # Validate device exists
            is_valid, error_msg = validate_device_exists(device_id)
            if not is_valid:
                errors.append({"deviceId": device_id, "error": error_msg})
                continue
            
            # Check if already linked
            if check_device_install_link(device_id, install_id):
                errors.append({"deviceId": device_id, "error": f"Device already linked to install {install_id}"})
                continue
            
            # Execute link transaction
            success, transaction_error = execute_install_device_link_transaction(
                install_id, device_id, performed_by, ip_address, reason
            )
            
            if success:
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
    
        device_id = item.get("DeviceId")
        if not device_id:
            return ErrorResponse.build("DeviceId is required", 400)
    
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
            
            try:
                # Query all INSTALL records
                response = table.scan(
                    FilterExpression="begins_with(PK, :pk_prefix)",
                    ExpressionAttributeValues={
                        ":pk_prefix": "INSTALL#"
                    }
                )
                
                installs = []
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
                
                logger.info(f"Found {len(installs)} install(s)")
                return SuccessResponse.build({
                    "installCount": len(installs),
                    "installs": installs,
                    "includeDevices": include_devices,
                    "includeCustomer": include_customer
                }, 200)
                
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
        
        # Check if caller wants decrypted data (default: decrypted)
        if "decrypt" in params:
            should_decrypt = params.get("decrypt", "").lower() == "true"
        else:
            should_decrypt = True
        logger.info(f"GET /devices - decrypt={should_decrypt}")

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
            if filter_expression:
                from boto3.dynamodb.conditions import Attr
                fe = Attr("EntityType").eq("DEVICE")
                if device_type:
                    fe = fe & Attr("DeviceType").eq(device_type)
                if status:
                    fe = fe & Attr("Status").eq(status)
                response = table.scan(
                    FilterExpression=fe
                )
            else:
                response = table.scan(
                    FilterExpression="EntityType = :et",
                    ExpressionAttributeValues={":et": "DEVICE"}
                )

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
            
            return SuccessResponse.build(transform_items_to_json(items, should_decrypt=should_decrypt))
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
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": "META"}
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
